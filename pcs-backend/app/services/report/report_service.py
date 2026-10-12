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
import hashlib
import json
import logging
import sys
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.report import ReportFile
from app.services.audit_service import AuditService
from app.services.exceptions import PcsError
from app.services.report import paths
from app.services.report.blocks import Block, HeadingBlock, TableBlock
from app.services.report.renderer_docx import render_docx
from app.services.report.renderer_pdf import render_pdf
from app.services.report.renderer_xlsx import render_xlsx
from app.services.report.style import ReportStyle

logger = logging.getLogger(__name__)

SUPPORTED_FORMATS = frozenset({"pdf", "xlsx", "docx"})
_EXT = {"pdf": "pdf", "xlsx": "xlsx", "docx": "docx"}


# --- 取数 -------------------------------------------------------------------


async def collect(*, report_type: str, project_id: uuid.UUID,
                  record_ids: list[uuid.UUID], db: AsyncSession) -> tuple[
                      list[Block], list[str], list[str]]:
    """按 report_type 产出 Block 列表、被引用记录的行哈希、假设字段名。

    TODO(T7 前置)：10 类报表的固定查询尚未实现（Task 5b Step 4 的 collector）。
    当前先产出一个最小可用的骨架，让编排链先跑通；collector 落地后本函数
    换成按 report_type 分派。**不是**在这里临时返回空表 —— 那样编排链的
    「空内容」分支永远走不到，等于没有测过。
    """
    blocks: list[Block] = [
        HeadingBlock(text="报表正文", level=1),
        TableBlock(headers=["报表类型", "记录数"],
                   rows=[[report_type, len(record_ids)]], assumed_cols=()),
    ]
    record_hashes: list[str] = []
    assumed_fields: list[str] = []
    return blocks, record_hashes, assumed_fields


# --- 渲染（同步，跑在线程池里）-----------------------------------------------


def _render_sync(*, blocks: list[Block], style: ReportStyle,
                 output_format: str, ctx: dict,
                 title: str = "报表") -> bytes:
    """**同步**渲染。ReportLab/XlsxWriter/python-docx 都是同步 CPU 密集操作。

    调用方**必须**走 `await asyncio.to_thread(report_service._render_sync, ...)`。
    ⚠️ 必须写成 `report_service._render_sync` 的**属性查找**形式 —— 若在模块
    顶层 `from .report_service import _render_sync` 绑定引用，monkeypatch
    改不到，测试就成了假绿（与 bug-150 同族）。
    """
    if output_format == "pdf":
        return render_pdf(title=title, blocks=blocks, style=style,
                          qr_payload=None, assumed_fields=[], context=ctx)
    if output_format == "docx":
        return render_docx(title=title, blocks=blocks, style=style, context=ctx)
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


async def generate(*, report_type: str, project_id: uuid.UUID,
                   record_ids: list[uuid.UUID], output_format: str,
                   style: ReportStyle, ctx: dict,
                   db: AsyncSession) -> ReportFile:
    """生成一份报表并登记 `ReportFile`。返回已 upsert 的那一行。"""
    if output_format not in SUPPORTED_FORMATS:
        # 在**渲染前**拒：渲染完才发现格式不认识，白烧一次 CPU + 一份临时文件
        raise PcsError(
            f"不支持的输出格式：{output_format!r}。支持 {sorted(SUPPORTED_FORMATS)}。",
            code="REPORT_FORMAT_UNSUPPORTED", status=400,
        )

    audit = AuditService(db)
    blocks, record_hashes, assumed_fields = await collect(
        report_type=report_type, project_id=project_id,
        record_ids=record_ids, db=db)

    try:
        payload = await asyncio.to_thread(
            # ⚠️ 必须是**属性查找**：写成 `_render_sync` 裸名会把当前时刻的
            # 函数对象绑死在这里，之后再 monkeypatch 本模块的属性改不到它，
            # 测试就成了假绿（bug-150 同族）。`sys.modules` 里取的是模块本身，
            # 属性查找在调用时才发生。
            sys.modules[__name__]._render_sync,
            blocks=blocks, style=style, output_format=output_format, ctx=ctx,
            title=report_type,
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
        has_assumption=bool(assumed_fields))

    try:
        await audit.write(action="REPORT_GENERATED", resource_type="report",
                          resource_id=row.report_file_id,
                          detail={"report_type": report_type,
                                  "output_format": output_format,
                                  "content_hash": digest,
                                  "assumed_fields": assumed_fields})
    except Exception as e:  # noqa: BLE001
        # ⚠️ **不回滚**。文件已落盘，回滚 DB 只留下无记录的孤儿文件。
        logger.warning("REPORT_GENERATED 审计写入失败，文件记录保留：%s", e)
    return row


async def _upsert_report_file(db: AsyncSession, **kw) -> ReportFile:
    """按 content_hash upsert —— 同内容复用同一行（SPEC §2.5）。"""
    existing = (await db.execute(
        select(ReportFile).where(ReportFile.content_hash == kw["content_hash"])
    )).scalar_one_or_none()
    if existing is not None:
        return existing

    row = ReportFile(
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