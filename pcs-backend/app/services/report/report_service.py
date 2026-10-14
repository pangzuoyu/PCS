"""报表生成编排 —— 取数 → 渲染 → 落盘 → 记 `ReportFile` → 审计。

这是三套渲染器与 query_engine 的**唯一**入口。渲染器本身不知道 DB，
注册表本身不执行查询，编排层是它们之间唯一有职责的地方。

## 三条要害

1. **渲染走线程池**。ReportLab / XlsxWriter / python-docx 是 CPU 密集的**同步**
   操作，在 async 函数里直接调会阻塞整个 event loop —— 这正是 b7 改异步要
   避免的同一个错误，换个地方再犯一遍。
2. **失败路径也要写审计**（SPEC §六验收明写「失败也记录」）。
3. **审计失败不回滚文件记录**。文件已经落盘了，回滚 DB 只会留下**无记录的
   孤儿文件** —— 既没人知道它存在，也没人知道该删。比有记录更难排查。

## 内容哈希复用（SPEC §2.5 文件不可变性）

`report_files.content_hash` 唯一。同一份内容重复生成复用同一行、同一文件。
⚠️ 这条**依赖二维码载荷确定性**（见 `qr.py` 的模块 docstring）——
载荷含时间戳的话哈希每次都变，机制照常运行但永远命中不了。
"""
from __future__ import annotations

import asyncio
import dataclasses
import datetime as dt
import hashlib
import json
import logging
import sys
import uuid
from pathlib import Path

from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.report import ReportFile
from app.services.audit_service import AuditService
from app.services.exceptions import PcsError
from app.services.report import paths
from app.services.report.blocks import Block, HeadingBlock, TableBlock
from app.services.report.collector import collector_for
from app.services.report.datasource_registry import (
    DATASOURCES,
    join_key_for,
    primary_key_field,
)
from app.services.report.query_engine import (
    _column,
    apply_filters,
    apply_sort,
    assemble,
    build_select,
    paginate,
)
from app.services.report.renderer_docx import render_docx
from app.services.report.renderer_pdf import render_pdf
from app.services.report.renderer_xlsx import render_xlsx
from app.services.report.style import ReportStyle

logger = logging.getLogger(__name__)

#: 支持的输出格式。**取自 `watermark.EXPORT_FORMATS`** —— b8 落地 CSV 后
#: 曾经有三份清单（这里 / `schemas.report.SUPPORTED_OUTPUT_FORMATS` /
#: API 的 `_RENDERABLE_FORMATS`），改漏一处就是「某个格式选得到但跑不了」。
SUPPORTED_FORMATS = frozenset({"pdf", "xlsx", "docx", "csv"})
_EXT = {"pdf": "pdf", "xlsx": "xlsx", "docx": "docx", "csv": "csv"}
_MAX_ROWS = 10000      # SPEC §3.2.2(2) MaxRows 默认值
_BATCH_SIZE = 10000   # IN 列表分批，避免语句膨胀


# --- 取数 -------------------------------------------------------------------


async def collect(*, report_type: str, project_id: uuid.UUID,
                  record_ids: list[uuid.UUID], db: AsyncSession) -> tuple[
                      list[Block], list[str], list[str]]:
    """按 report_type 取数，产出 Block 列表、被引用记录的行哈希、假设字段名。

    声明来自 `collector`（SPEC §3.2.1(2) 的 10 类），取数执行走 `query_engine`
    —— 15 个操作符与 JOIN 白名单各只有一份实现（用户 2026-10-09 裁决）。

    多源按裁决走「每源一次 SELECT + Python 组装」，**不生成 SQL JOIN**：
    先查主源，用主源的关联键做 `WHERE key IN (...)` 批量查从源，
    再在 Python 里 dict lookup 关联。
    """
    spec = collector_for(report_type)

    main_fields = spec.fields[spec.primary]
    # ⚠️ 顺序：先 build_select 再 where —— `apply_filters` 返回的是
    # ColumnElement（布尔表达式），不是 Select，先过滤会得到
    # `'Comparator' object has no attribute 'order_by'`。
    stmt = build_select(spec.primary, main_fields)
    stmt = stmt.where(apply_filters(_scope_and_records(spec, project_id, record_ids)))
    stmt = apply_sort(stmt, main_fields[:1])   # 稳定排序，否则分页会抖动
    stmt = paginate(stmt, limit=_MAX_ROWS)

    result = await db.execute(stmt)
    columns = list(result.keys())
    main_rows = [dict(zip(columns, row, strict=True)) for row in result.all()]

    rows_by_source: dict[str, list[dict]] = {spec.primary: main_rows}
    join_keys: list[tuple[str, str, str, str]] = []
    for extra in spec.extra_sources:
        a_key, b_key = join_key_for(spec.primary, extra)   # 不在白名单会抛 400
        join_keys.append((spec.primary, a_key, extra, b_key))
        rows_by_source[extra] = await _fetch_join_rows(
            db, source=extra, join_field=b_key, scope=project_id,
            keys=[r.get(a_key) for r in main_rows if r.get(a_key) is not None])

    rows = assemble(rows_by_source, join_keys, spec.primary, spec.fields)
    return _to_blocks(spec, rows), _record_hashes(main_rows), _assumed_fields(rows)


def _to_blocks(spec, rows: list[dict]) -> list[Block]:
    """取数结果 → Block 列表。**NULL → —、超长截断**都走 `blocks._cell_text`。

    表头用**注册表里的中文 label**，不是 ORM 列名 —— 两点原因：
      1. 可读性：`equipment_description` / `vendor_model` 这类列名在 A4 上
         会把单词劈成两半（`vendor_mod\nel`），而「制造商型号」不会。
      2. 一致性：用户在字段树里看到的就是这些 label，报表表头应当一致；
         用列名会让用户以为选错了字段。
    """
    headers: list[str] = []
    keys: list[str] = []
    for src in spec.sources:
        for f in spec.fields.get(src, []):
            label = DATASOURCES[src].fields[f].label
            headers.append(label if src == spec.primary else f"{src}.{label}")
            keys.append(f"{src}.{f}" if src != spec.primary else f)
    return [
        HeadingBlock(text=spec.label, level=1),
        TableBlock(headers=headers,
                   rows=[[r.get(k) for k in keys] for r in rows],
                   assumed_cols=()),
    ]


def _scope_and_records(spec, project_id: uuid.UUID | None,
                       record_ids: list[uuid.UUID]) -> dict | None:
    """项目作用域 ∩ `record_ids`，**两个都是必需项，谁也替代不了谁**。

    ## 为什么这两件事不能合成一件（2026-10-14 修，评审 P0 #1）

    `collect()` 一直收着 `project_id` 形参却**一次也没用过**：整条 WHERE
    只有 `record_ids IN (...)`。于是 `POST /report/generate` 的形状是

        project_id = 我有权的项目 B     <- 端点只校验这个的访问权
        record_ids = 项目 A 的行 UUID    <- 归属从不校验，原样入队

    → 报表 200、行数正常、列也齐，只是数据是别人的。**报错反而是好事**
    ——报错会让人停下，串数据不会。

    ⚠️ 项目过滤**不并进用户可编辑的条件列表**（那是 `_filter_spec` 的领域）：
    把它塞进去意味着将来有人改条件构造时有机会把它挤掉，而挤掉之后报表
    仍然跑得通、仍然返回 200。与 `builder_service` 的同一处决策同理由。

    ## 公司级目录是例外，且有意

    没有 `project_id` 列的源（如 `SUPPLIERS` 供应商名录）**不加**这个过滤：
    它本来就是公司级共享目录，加了就永远查不出任何行。按「该源有没有
    `project_id`」分支，不硬编码源名 —— 将来某个源从公司级变成项目级，
    行为自动跟着变。

    ## 与 bug-162 的关系

    bug-162 修的是同名函数在 `builder_service` 那条路（自定义报表构建器）。
    **固定 10 类这条路的 `_fetch_join_rows` 至今没有 `scope` 参数** ——
    两条路各有一个同名函数，只修了一条。当前 10 类的 `extra_sources`
    全为空（都是单源），所以那条 JOIN 腿目前**触发不到**；一旦某类报表
    加上从源，它就会立刻变成活着的洞。已在 `_fetch_join_rows` 同步补上。
    """
    conds: list[dict] = []
    if project_id is not None and "project_id" in DATASOURCES[spec.primary].fields:
        # ⚠️ value 必须是**原生 UUID**：`Uuid` 列的 bind processor 直接调
        # `.hex`，传 str 会炸在 SQL 层（与 builder_service 同理）。
        conds.append({"operator": "EQ", "source": spec.primary,
                      "field": "project_id", "value": project_id})
    rec = _filter_spec(spec, record_ids)
    if rec is not None:
        conds.append(rec)
    if not conds:
        return None
    # ⚠️ 总是包成组，不返回裸叶子：`apply_filters` 把**顶层** `operator`
    # 当连接符读，裸 `{"operator": "EQ", ...}` 会撞
    # 「条件组操作符只能是 AND/OR」（400）。
    return {"operator": "AND", "conditions": conds}


def _filter_spec(spec, record_ids: list[uuid.UUID]) -> dict | None:
    """record_ids 非空时按主源**主键**过滤。

    ⚠️ 用 `IN` 而不是逐个 `EQ`：N 条记录就是 N 个 OR 条件，
    10000 条记录会让 SQL 膨胀到不可用（ADR-P8-004 多源裁决的同源理由）。

    ⚠️ **必须按主键过滤，不能拿第一个业务字段比**。`record_ids` 是主源行的
    主键（UUID），而 `spec.fields[primary][0]` 是业务列（如 `type_code` = "PUMP-101"）——
    两者**根本不是一个域**，拿 UUID 去比字符串，结果恒为空集。
    第一版就这么写的，症状是「表头渲染出来了但一行数据都没有」。
    """
    if not record_ids:
        return None
    return {"operator": "AND", "conditions": [{
        "source": spec.primary, "field": primary_key_field(spec.primary),
        # ⚠️ 传 **UUID 对象**而不是字符串：主键列是 `Uuid` 类型，
        # 传字符串会在驱动层炸 `'str' object has no attribute 'hex'`。
        # 字符串入参（ARQ 队列传过来的是字符串）在这里归一。
        "operator": "IN",
        "value": [r if isinstance(r, uuid.UUID) else uuid.UUID(str(r))
                  for r in record_ids],
    }]}


async def _fetch_join_rows(db: AsyncSession, *, source: str, join_field: str,
                           keys: list, scope: uuid.UUID | None = None) -> list[dict]:
    """从源**一次批量查**（`WHERE key IN (...)`），不是 N 次 —— 用户 2026-10-09 裁决第 1 条。

    ## `scope` 为什么必须有（2026-10-14 补，评审 P0 #1）

    位号的唯一性是**项目内**唯一（`TaggedRecordMixin`：`tag_number` NOT NULL
    且 unique per project）。只按关联键 `IN (...)` 取数时，两个项目用同一个
    位号会把**别人项目的行**也捞进来。而 `assemble` 对重复键是 `{k: row}`
    —— **取最后一条**，不报错也不告警。所以症状不是「行数爆炸」，而是
    悄悄挂上别人项目的那一行：报表 200、行数正常、列也齐。

    ⚠️ 本函数是 `builder_service._fetch_join_rows` 的同名副本，bug-162
    **只修了那一个**。当前固定 10 类的 `extra_sources` 全为空（都是单源），
    所以这里**暂时触发不到**；某类报表一旦加上从源，它立刻就是活着的洞。
    与其等那天，不如现在补上 —— 正确写法在同仓库 40 行外就有。

    没有 `project_id` 列的源（如 `SUPPLIERS`）**不加**这个谓词：
    公司级共享目录，加了就永远查不出行。按「该源有没有该列」分支，
    不硬编码源名。

    ⚠️ 不走 `apply_filters`：那是用户条件的通道，项目过滤是**越权边界**。
    """
    if not keys:
        return []
    cols = list(DATASOURCES[source].fields)
    base = build_select(source, cols)
    has_project = "project_id" in DATASOURCES[source].fields
    rows = []
    # 分批：IN 列表过长会让语句膨胀（参数上限），裁决第 4 条
    for i in range(0, len(keys), _BATCH_SIZE):
        chunk = keys[i:i + _BATCH_SIZE]
        where = _join_column(source, join_field).in_(chunk)
        if has_project and scope is not None:
            where = and_(where, _column(source, "project_id") == scope)
        # ⚠️ **不改写 base**：分块循环里 `stmt = stmt.where(...)` 是改写累加器，
        # 第 2 块会把 `key IN (chunk2)` AND 到已有的 `key IN (chunk1)` 上，
        # 于是返回各块的交集（空集）。每块把谓词交给 execute 而已。
        result = await db.execute(base.where(where))
        columns = list(result.keys())
        rows += [dict(zip(columns, row, strict=True)) for row in result.all()]
    return rows


def _join_column(source: str, join_field: str):
    ds = DATASOURCES[source]
    spec = ds.fields.get(join_field)
    if spec is None:
        raise PcsError(f"JOIN 字段 {source}.{join_field} 不在注册表中",
                       code="REPORT_FIELD_UNKNOWN", status=400)
    return _column(source, join_field)


def _record_hashes(rows: list[dict]) -> list[str]:
    """被引用记录的行哈希 —— 二维码载荷的 `record_hash_digest` 由它算出。"""
    return [str(r.get("record_hash")) for r in rows if r.get("record_hash")]


def _assumed_fields(rows: list[dict]) -> list[str]:
    """含假设数据的字段名（SPEC §3.2.1(4) 的声明页）。

    本仓的行级数据没有「该值是假设的」标记位，故当前恒为空 ——
    **宁可不加声明页，也不要加一张永远说「无假设数据」的声明页**。
    真正的假设来源是 `project_input_checklist.status ∈ {ASSUMED, NOT_STARTED}`，
    Task 6 的验收要的是那一路；接上时改这里即可。
    """
    return []


# --- 渲染（同步，跑在线程池里）-----------------------------------------------


def _render_sync(*, blocks: list[Block], style: ReportStyle,
                 output_format: str, ctx: dict,
                 title: str = "报表",
                 qr_payload: str | None = None) -> bytes:
    """**同步**渲染。ReportLab/XlsxWriter/python-docx 都是同步 CPU 密集操作。

    调用方**必须**走 `await asyncio.to_thread(report_service._render_sync, ...)`。
    ⚠️ 必须写成 `report_service._render_sync` 的**属性查找**形式 —— 若在模块
    顶层 `from .report_service import _render_sync` 绑定引用，monkeypatch
    改不到，测试就成了假绿（与 bug-150 同族）。

    ⚠️ `qr_payload` **不是** `None` 写死了（2026-10-14 修，评审 P1 #4）。
    原先这里恒传 `None`，于是 `renderer_pdf` 里 `if qr_payload:` 在生产路径
    永远为假、`build_qr_payload` 零调用者，而 `_check_sig` 要求 sig+exp 齐备
    —— 印在报表上的二维码**每一次扫码都 403**。功能看起来齐全，没有任何一层报错。
    """
    if output_format == "pdf":
        return render_pdf(title=title, blocks=blocks, style=style,
                          qr_payload=qr_payload, assumed_fields=[], context=ctx)
    if output_format == "docx":
        return render_docx(title=title, blocks=blocks, style=style, context=ctx)
    if output_format == "csv":
        from app.services.report.watermark import render_csv

        return render_csv(title=title, blocks=blocks)
    return render_xlsx(title=title, blocks=blocks, style=style, context=ctx)


def _content_hash(*, blocks: list[Block], style: ReportStyle,
                  output_format: str, ctx: dict) -> str:
    """报表的**内容指纹** —— 刻意**不**对渲染后的字节取哈希。

    ⚠️ 计划原本写 `sha256(rendered_bytes)`，那条路走不通（实测）：
      - **PDF 永远不是字节相同的**：reportlab 每次生成随机的 `/ID`，
        同一秒内两次生成也不同 → 哈希永远不同 → 永远不命中。
      - **XLSX 也不是**：`docProps/core.xml` 里带 `dcterms:created`。
      - 即便二者都确定，`CreationDate` 一到下一秒就变。

    改为对**规范化内容**（Blocks + 解析后的样式 + 格式 + ctx）取哈希：
    语义相同就该复用同一个文件 —— 这正是 SPEC §2.5「文件不可变性」的本意。
    比事后解析 PDF 去掉时间戳稳得多，也不用多一遍渲染。

    `font_dir` 被排除：它是部署路径不是样式内容，混进去会让同一份报表在
    两台机器上算成两个哈希。
    """
    style_payload = {k: v for k, v in sorted(style.model_dump().items())
                     if k != "font_dir"}
    canonical = json.dumps({
        "format": output_format,
        "style": style_payload,
        "ctx": {k: ctx[k] for k in sorted(ctx)},
        "blocks": [_block_canon(b) for b in blocks],
    }, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _block_canon(b: Block) -> dict:
    """Block 的规范化表示（dataclass → dict，JSONB 无关，全是标量/列表）。"""
    return dataclasses.asdict(b)


def _write_file(abs_path: Path, payload: bytes) -> None:
    """落盘。**先写临时文件再改名** —— 半截文件当成品会被下一个人当成有效数据。

    这里**不**把 OSError 转成 PcsError：转换放在调用方 `generate` 里。
    放在本函数内部的话，任何替换掉本函数的路径（测试、故障注入、将来别的
    存储后端）都会绕过那个守卫 —— 守卫必须在边界上，不能在被守卫者里面。
    """
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = abs_path.with_suffix(abs_path.suffix + ".part")
    tmp.write_bytes(payload)
    tmp.replace(abs_path)


# --- 编排 -------------------------------------------------------------------


#: 占位 content_hash 的前缀。**刻意不是十六进制** —— 真内容指纹是 64 位 hex，
#: 若占位符也长得像 hash，两者在日志与排查时会被误认。
PENDING_HASH_PREFIX = "pending:"


async def ensure_pending_row(db: AsyncSession, *, project_id: uuid.UUID | None,
                             task_id: str, output_format: str):
    """建（或取回）本次任务那一行 PENDING。

    ⚠️ **端点与 worker 共用这一份实现**（2026-10-13，TODO-063）。
    两处各写一遍的后果不是「重复」，而是**时序**：只有 worker 建行的话，
    202 返回与「行存在」之间有窗口，轮询端点在那段时间只能 404 ——
    report-builder 那条路已经踩过（bug-167）。端点在入队时就建，
    worker 靠 `content_hash` 占位符找回**同一行**，于是 ARQ 重试
    （`_job_id` 不变）复用一行，不留孤儿 PENDING。

    重试时**复用同一行**：否则一次失败的重试链会在库里留下一串孤儿 PENDING，
    而它们每一行都会被回收器当成僵死任务处理一遍。
    """
    from sqlalchemy import select
    from sqlalchemy.exc import IntegrityError

    from app.models.report import ReportFile

    placeholder = f"{PENDING_HASH_PREFIX}{task_id}"
    existing = (await db.execute(
        select(ReportFile).where(ReportFile.content_hash == placeholder)
    )).scalar_one_or_none()
    if existing is not None:
        existing.status = "PENDING"
        existing.heartbeat_at = dt.datetime.now(dt.UTC)
        existing.error_message = None
        await db.flush()
        return existing

    row = ReportFile(
        project_id=project_id, content_hash=placeholder,
        file_path=placeholder, file_format=output_format, size_bytes=0,
        status="PENDING", heartbeat_at=dt.datetime.now(dt.UTC),
        task_id=task_id,
    )
    db.add(row)
    try:
        await db.flush()
    except IntegrityError:
        # 并发下同 task_id 的 PENDING 行已存在 —— 复用它
        await db.rollback()
        return (await db.execute(
            select(ReportFile).where(ReportFile.content_hash == placeholder)
        )).scalar_one()
    return row


async def generate(*, report_type: str, project_id: uuid.UUID,
                   record_ids: list[uuid.UUID], output_format: str,
                   style: ReportStyle, ctx: dict,
                   db: AsyncSession) -> ReportFile:
    """生成一份报表并登记 `ReportFile`。返回已 upsert 的那一行。"""
    blocks, record_hashes, assumed_fields = await collect(
        report_type=report_type, project_id=project_id,
        record_ids=record_ids, db=db)
    return await store_rendered(
        db, blocks=blocks, project_id=project_id,
        output_format=output_format, style=style, ctx=ctx,
        title=report_type, assumed_fields=assumed_fields,
        audit_detail={"report_type": report_type,
                      "record_hashes": record_hashes},
    )


async def store_rendered(db: AsyncSession, *, blocks: list, project_id,
                         output_format: str, style: ReportStyle, ctx: dict,
                         title: str, assumed_fields: list[str] | None = None,
                         audit_detail: dict | None = None) -> ReportFile:
    """把**已经取好数**的 Block 渲染成文件并登记 `ReportFile`。

    与 `generate` 分开是因为两者只有「怎么取数」不同 —— 渲染、内容哈希
    命名、写盘守卫、跨边界去重、审计这几段**必须只有一份**。复制一份到
    自定义报表的执行路径上，意味着将来改内容哈希算法时改漏一处，
    而那处不会报错，只会让两份报表的去重行为不一致。
    """
    if output_format not in SUPPORTED_FORMATS:
        # 在**渲染前**拒：渲染完才发现格式不认识，白烧一次 CPU + 一份临时文件
        raise PcsError(
            f"不支持的输出格式：{output_format!r}。支持 {sorted(SUPPORTED_FORMATS)}。",
            code="REPORT_FORMAT_UNSUPPORTED", status=400,
        )
    audit = AuditService(db)
    assumed_fields = assumed_fields or []
    report_type = title

    # ⚠️ **先自选 report_file_id，再渲染**（2026-10-14 修，评审 P1 #4）。
    # 二维码签名要绑定 id，而 id 是主键、要等 upsert 才知道 —— 但渲染发生在
    # upsert 之前。所以这里自选一个，并保证**同一个 id** 一路传下去：
    # 签名用它、落库用它。
    #
    # 评审建议的替代方案（把顺序改成「先 upsert PENDING 行 → 用它的 id 签名
    # → 渲染 → 落盘」）**不需要**：它担心签名的时间戳会污染 `_content_hash`，
    # 而 `_content_hash` 哈希的是 Blocks + style + format + ctx，
    # **qr_payload 根本不在里面**（见该函数 docstring：刻意不对渲染字节取哈希）。
    #
    # 去重命中时：签名用的是新自选的 id，而落盘/返回的是既有那一行 ——
    # 刚渲染出来的字节被丢弃，磁盘上留下的旧文件里的二维码签的是它自己的 id。
    # 自洽。代价是「修复前生成的旧文件里没有二维码」，它们不会被重新渲染。
    new_file_id = uuid.uuid4()
    qr_payload = _build_qr_payload_for(
        report_file_id=new_file_id, title=report_type, ctx=ctx,
        record_hashes=(audit_detail or {}).get("record_hashes") or [],
        output_format=output_format)

    try:
        payload = await asyncio.to_thread(
            # ⚠️ 必须是**属性查找**：写成 `_render_sync` 裸名会把当前时刻的
            # 函数对象绑死在这里，之后再 monkeypatch 本模块的属性改不到它，
            # 测试就成了假绿（bug-150 同族）。`sys.modules` 里取的是模块本身，
            # 属性查找在调用时才发生。
            sys.modules[__name__]._render_sync,
            blocks=blocks, style=style, output_format=output_format, ctx=ctx,
            title=title, qr_payload=qr_payload,
        )
    except Exception as e:
        await audit.write(action="REPORT_FAILED", resource_type="report",
                          resource_id=None,
                          detail={"report_type": report_type,
                                  "output_format": output_format,
                                  "error": f"{type(e).__name__}: {e}"})
        raise

    digest = _content_hash(blocks=blocks, style=style,
                           output_format=output_format, ctx=ctx)
    relpath = paths.new_file_path(digest, _EXT[output_format])
    try:
        _write_file(paths.resolve_path(relpath), payload)
    except OSError as e:
        # 磁盘满 / 权限不足 / 只读文件系统 —— 全部收敛成一个可排查的错误码，
        # 不让裸 OSError 漏到 API 层。
        await audit.write(action="REPORT_FAILED", resource_type="report",
                          resource_id=None,
                          detail={"report_type": report_type,
                                  "output_format": output_format,
                                  "error": f"{type(e).__name__}: {e}"})
        raise PcsError(
            f"报表文件写入失败：{relpath}（{type(e).__name__}: {e}）。",
            code="REPORT_STORAGE_FAILED", status=500,
        ) from e

    row = await _upsert_report_file(
        db, project_id=project_id, content_hash=digest, relpath=relpath,
        size=len(payload), fmt=output_format,
        has_assumption=bool(assumed_fields),
        report_file_id=new_file_id)

    try:
        await audit.write(action="REPORT_GENERATED", resource_type="report",
                          resource_id=row.report_file_id,
                          detail={**(audit_detail or {}),
                                  "report_type": report_type,
                                  "output_format": output_format,
                                  "content_hash": digest,
                                  "assumed_fields": assumed_fields})
    except Exception as e:  # noqa: BLE001
        # ⚠️ **不回滚**。文件已落盘，回滚 DB 只留下无记录的孤儿文件。
        logger.warning("REPORT_GENERATED 审计写入失败，文件记录保留：%s", e)
    return row


def _build_qr_payload_for(*, report_file_id: uuid.UUID, title: str, ctx: dict,
                          record_hashes: list[str],
                          output_format: str) -> str | None:
    """给 PDF 用的二维码载荷；**不该出现时返回 None**（不印空壳）。

    返回 None 的三种情况：

    - **没有配签名密钥** —— 与 `/report/verify` 的 fail-closed 对齐：
      签不出来就不印，而不是印一个注定 403 的。
    - **没配对外基址** —— 印一个扫不通的二维码比不印更糟：用户看到
      「有二维码」就会去扫，扫不开只会以为文件有问题。
    - **不是 PDF** —— docx/xlsx 的渲染器不接受 `qr_payload`。

    ## ⚠️ `record_hashes` 为空**照样**印（2026-10-14，评审 P1 #4 的连带发现）

    `build_qr_payload` 的旧 docstring 说「记录哈希为空就不加二维码，
    因为没有可比对的凭据」。**那条规则已经与实际实现脱节**：

    - `/report/verify`（用户 2026-10-08 裁决：「比对」的主语是**系统**）
      验签之后做的是**文件完整性校验** —— 重算磁盘文件的 sha256，与
      登记时的 `content_hash` 比。**它从头到尾没读过 `record_hash_digest`。**
    - 而 `_record_hashes` 从 `row["record_hash"]` 取值，可 `record_hash`
      **没有登记进 datasource_registry**（grep 命中 0）⇒ 10 类报表的
      `record_hashes` 恒为空。

    照旧规则执行的结果是：**二维码一次都不会出现** —— 那等于把 #4
    修成了一个「正确地什么都不做」。

    所以真正让核验成立的是**签名 + report_file_id**，两者恒在；
    fragment 里的 `record_hash_digest` 是给人看的凭据，为空时它就是
    `sha256('')`，如实反映「本报表没有逐记录凭据」。
    """
    secret = get_settings().report_verify_secret
    base_url = get_settings().report_verify_base_url
    if not secret or not base_url or output_format != "pdf":
        return None
    from app.services.report import qr

    return qr.build_qr_payload(
        report_id=str(report_file_id),
        doc_no=str(ctx.get("doc_no") or ""),
        rev=str(ctx.get("rev") or ""),
        version_purpose=title,
        record_hashes=record_hashes,
        verify_base_url=base_url,
        report_file_id=report_file_id, secret=secret)


async def _upsert_report_file(db: AsyncSession, **kw) -> ReportFile:
    """按 content_hash upsert —— 同内容复用同一行（SPEC §2.5）。

    ⚠️ `report_file_id` 由调用方**预先自选**并传进来（2026-10-14），
    因为二维码签名要绑定它，而签名必须在渲染前就定下来。
    这里新建行时用它，而不是让 ORM 现生成一个 ——
    否则画进 PDF 的二维码签的是 A、登记的是 B，扫出来必然 403。
    命中既有行时忽略它（走的是那一行自己的 id，其自洽）。
    """
    existing = (await db.execute(
        select(ReportFile).where(ReportFile.content_hash == kw["content_hash"])
    )).scalar_one_or_none()
    if existing is not None:
        return existing

    row = ReportFile(
        report_file_id=kw["report_file_id"],
        project_id=kw["project_id"], content_hash=kw["content_hash"],
        file_path=kw["relpath"], file_format=kw["fmt"],
        size_bytes=kw["size"], status="SUCCEEDED",
        has_assumption_page=kw["has_assumption"],
    )
    db.add(row)
    try:
        await db.flush()
    except IntegrityError:
        # 并发下另一个请求刚插了同一 content_hash —— 回滚自己的插入，复用它的
        await db.rollback()
        return (await db.execute(
            select(ReportFile).where(ReportFile.content_hash == kw["content_hash"])
        )).scalar_one()
    return row


__all__ = ["generate", "collect", "paths", "AuditService"]