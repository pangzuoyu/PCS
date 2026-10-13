"""ARQ：自定义报表定义执行任务（b7）。

`POST /definitions/{id}/execute` 只入队；取数与渲染都在这里。

## 为什么任务体里重新取 session

ARQ 任务的 `ctx` 由 worker 启动时注入（见 `app/worker.py`），含一个
`db`。任务体**复用**它而不是自己开 session：同一个执行里的
「建 PENDING 行 → 渲染 → finalize → 写审计」要在一个事务边界里才看得到
一致的中间态；换 session 会让状态端点在 commit 之前读到空行。

## 失败处理沿用 `report_tasks` 的裁决

`REPORT_FAILED` **每次尝试都写一条**（detail 带 `{task_id, attempt_no}`），
不只写最后一次 —— ARQ 的 `keep_result` 默认 3600 秒，重试链本身是
「这类报表平均试几次才成」的唯一记录。
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import AuditAction
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)

PENDING_HASH_PREFIX = "pending:"


async def execute_definition_task(
    ctx: dict, *, def_id: str, project_id: str, user_id: str,
    filters: dict[str, Any] | None = None,
    max_rows: int | None = None,
    output_format: str | None = None,
) -> str:
    """ARQ 任务体。返回 `report_file_id` 字符串。"""
    db: AsyncSession = ctx["db"]
    job_id = ctx.get("job_id") or str(uuid.uuid4())
    attempt_no = int(ctx.get("job_try") or 1)
    audit = AuditService(db)

    pid = uuid.UUID(project_id) if project_id else None
    did = uuid.UUID(def_id)
    uid = uuid.UUID(user_id) if user_id else None

    from app.services.report import builder_service

    try:
        out = await builder_service.execute_definition(
            db, def_id=did, user_id=uid, project_id=pid,
            temporary_filters=filters, temporary_max_rows=max_rows,
            output_format=output_format,
        )
        file_id = await _render_and_store(
            db, out=out, project_id=pid, job_id=job_id,
            output_format=out.snapshot.get("output_format") or "pdf")
        await db.commit()
    except Exception as e:  # noqa: BLE001
        await db.rollback()
        await audit.write(
            action=AuditAction.REPORT_FAILED, resource_type="report_definition",
            resource_id=did,
            detail={"task_id": job_id, "attempt_no": attempt_no,
                    "def_id": str(did), "error": f"{type(e).__name__}: {e}"[:500]},
        )
        await db.commit()
        raise          # 交给 ARQ 重试；「每次失败都写」由这里落实

    await audit.write(
        action=AuditAction.REPORT_EXECUTED, resource_type="report_definition",
        resource_id=did,
        detail={"task_id": job_id, "def_id": str(did),
                "def_version": out.def_version, "row_count": out.row_count,
                "truncated": out.truncated,
                "condition_snapshot": out.snapshot},
    )
    await db.commit()
    return file_id


async def _build_style(db: AsyncSession, *, out, project_id):
    """按定义的 `detailLevel` + 主数据源取样式。

    ⚠️ **主数据源当 report_type**：公司标准与项目样式都按 `report_type`
    分作用域（`uq_report_styles_scope_version` 如此），而自定义报表的
    report_type 就是它的主数据源。用一个自造的 `"CUSTOM"` 分类会让
    所有自定义报表共用同一条样式 —— 一条改字号全改。
    """
    from app.services.report.datasource_registry import DATASOURCES
    from app.services.report.style_service import build_style

    snapshot = out.snapshot or {}
    sources = [d.get("source") for d in (snapshot.get("DataSources") or [])]
    primary = next((s for s in sources if s in DATASOURCES), None)
    level = snapshot.get("detailLevel") or "BASIC"
    exchanger = _exchanger_type(snapshot)
    return await build_style(db, report_type=primary or "CUSTOM",
                             project_id=project_id, level=level,
                             exchanger_type=exchanger)


def _exchanger_type(snapshot: dict) -> str | None:
    """换热器类型 —— 渲染器据此选表格结构（ADR-0028）。

    只能从**已登记的 AIR_COOLER 字段**反推：注册表里带
    `exchanger_type="AIR_COOLER"` 的字段（如 `fan_count`）只有空冷器会选。
    没选任何这类字段 → 不是空冷器 → 不设该值（SHELL_TUBE 与 None
    在渲染器里走同一分支，显式写死反而会掩盖数据）。
    """
    from app.services.report.datasource_registry import DATASOURCES

    ds = DATASOURCES.get("HEAT_RESULTS")
    if ds is None:
        return None
    chosen = {(s.get("source"), s.get("field"))
              for s in (snapshot.get("SelectedFields") or [])}
    for source, field in chosen:
        spec = ds.fields.get(field)
        if spec is not None and spec.exchanger_type == "AIR_COOLER":
            return "AIR_COOLER"
    return None


async def _render_and_store(db: AsyncSession, *, out, project_id, job_id: str,
                            output_format: str) -> str:
    """把执行结果渲染成文件并登记 `ReportFile`，返回 report_file_id。

    走 `report_service.store_rendered` 而不是自己写一份 —— 内容哈希命名、
    写盘的临时文件 + 改名、跨异步边界的去重、生成审计都在那一份里。
    复制一份到自定义报表路径上，等于给「同一份内容算两次哈希」开了口子。
    """
    from app.services.report import report_service, watermark
    from app.services.report.blocks import HeadingBlock, TableBlock
    from app.services.report.style_service import build_style

    blocks: list = [HeadingBlock(text="自定义报表", level=1)]
    if out.truncated:
        blocks.append(HeadingBlock(
            text=f"⚠ 结果已截断：最多 {out.snapshot.get('max_rows')} 行", level=1))
    blocks.append(TableBlock(headers=out.headers, rows=out.rows, assumed_cols=()))

    # ⚠️ 水印加在**这里**（即席导出路径），不加在 `report_service.generate`
    # 里 —— 后者是固定 10 类的**交付物**流程（SUP-007：带 Rev 与签署），
    # 标「非发布件」是相反的语义。
    blocks = watermark.apply(blocks)

    # ⚠️ 这里原先传的是裸 `ReportStyle()` —— 样式系统整段与生成脱钩：
    # 用户在 UI 里改样式对输出毫无影响，ADR-0028 的「DETAIL 必须横向」
    # 也从来没落到任何一份文件上。改走四层合并。
    style = await _build_style(db, out=out, project_id=project_id)

    row = await report_service.store_rendered(
        db, blocks=blocks, project_id=project_id,
        output_format=output_format, style=style, ctx={},
        title=f"CUSTOM_{out.def_version}",
        assumed_fields=[],
        audit_detail={"def_id": str(out.snapshot.get("def_id", "")),
                      "row_count": out.row_count,
                      "truncated": out.truncated,
                      "watermark": watermark.watermark_text()},
    )
    return str(row.report_file_id)


__all__ = ["execute_definition_task"]