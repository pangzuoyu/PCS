"""ARQ 报表异步生成任务。

b7 决策：报表生成走 ARQ 异步（用户 2026-10-08 审查）—— 10k 行 PDF ≈ 10 CPU-秒，
在 async 端点里同步跑会阻塞整个 event loop。

## 状态机

    建 PENDING 行 ──┬── 渲染成功 ──→ 就地更新为 SUCCEEDED（或复用已有行）
                    ├── 渲染失败 ──→ 置 FAILED + 写审计 ──→ 抛出（ARQ 重试）
                    └── 进程被 kill ──→ 永远卡 PENDING ──→ reclaim_stale_tasks 回收

**为什么先建 PENDING 行**：渲染期间状态端点要有东西可读，且进程被杀时
状态得有地方可丢 —— 否则这一次生成在系统里不存在，用户只看到「转圈到超时」。

## 内容指纹去重跨异步边界

`report_files.content_hash` 是 UNIQUE。异步路径先建了一个占位 PENDING 行，
渲染完发现内容指纹已存在时**不能**直接更新（会撞唯一键）——
正确处置是删掉自己的占位行、返回已有行，与同步路径（`report_service.generate`
的 upsert）语义一致。

## 失败审计：每次都写（用户 2026-10-09 裁决）

`REPORT_FAILED` **每次尝试都写一条**，detail 带 `{task_id, attempt_no}`。

不是审计偏好：ARQ 的 `keep_result` 默认 **3600 秒**，任务结果与异常在 Redis 里
1 小时后被清除 —— `audit_logs` 是失败的**唯一**持久记录。而「失败过几次」
本身是有价值的信号（某类报表平均重试 2 次才成功 = 有系统性质量问题），
只写最后一次会把这个信号抹掉。

`max_tries` 由 `worker.py` 的 functions 注册显式设为 **3**（ADR-P8-004）：
报表失败通常是**确定性错误**（数据脏、字体缺、格式不认识），不是瞬时抖动，
重试 5 次和 3 次没区别，只多刷 2 条审计。
"""
from __future__ import annotations

import datetime as dt
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import AuditAction
from app.models.report import ReportFile
from app.services.audit_service import AuditService
from app.services.report.style import ReportStyle

logger = logging.getLogger(__name__)

# 占位 content_hash 的前缀。**刻意不是十六进制** —— 真内容指纹是 64 位 hex，
# 若占位符也长得像 hash，两者在日志与排查时会被误认（且有撞唯一键的想象风险）。
PENDING_HASH_PREFIX = "pending:"

# 僵死判定阈值（分钟）。10k 行 PDF 约 10 秒，15 分钟留了 90 倍余量；
# 定得太短会误杀正在跑的慢任务，定得太长用户要等更久才看到失败。
STALE_MINUTES = 15


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


async def _mark_pending(db: AsyncSession, *, project_id: uuid.UUID,
                        job_id: str, output_format: str) -> ReportFile:
    """建（或取回）本次任务的 PENDING 行。

    重试时**复用同一行** —— 否则一次失败的重试链会在库里留下一串孤儿 PENDING 行，
    而它们每一行都会被回收器当成僵死任务处理一遍。
    """
    placeholder = f"{PENDING_HASH_PREFIX}{job_id}"
    existing = (await db.execute(
        select(ReportFile).where(ReportFile.content_hash == placeholder)
    )).scalar_one_or_none()
    if existing is not None:
        existing.status = "PENDING"
        existing.heartbeat_at = _now()
        existing.error_message = None
        await db.flush()
        return existing

    row = ReportFile(
        project_id=project_id, content_hash=placeholder,
        file_path=placeholder, file_format=output_format, size_bytes=0,
        status="PENDING", heartbeat_at=_now(),
    )
    db.add(row)
    try:
        await db.flush()
    except IntegrityError:
        # 并发下同 job_id 的 PENDING 行已存在 —— 复用它
        await db.rollback()
        return (await db.execute(
            select(ReportFile).where(ReportFile.content_hash == placeholder)
        )).scalar_one()
    return row


async def _finalize(db: AsyncSession, row: ReportFile, *, digest: str,
                    relpath: str, size: int, fmt: str) -> str:
    """成功收尾：能复用就复用，否则把 PENDING 行**就地**改成真值。

    返回最终的 report_file_id 字符串。
    """
    dup = (await db.execute(
        select(ReportFile).where(
            ReportFile.content_hash == digest,
            ReportFile.report_file_id != row.report_file_id,
        )
    )).scalar_one_or_none()
    if dup is not None:
        # 同内容已存在（bug-155 修好后的复用语义）：删掉自己的占位行，返回已有行。
        await db.delete(row)
        await db.flush()
        return str(dup.report_file_id)

    row.content_hash = digest
    row.file_path = relpath
    row.file_format = fmt
    row.size_bytes = size
    row.status = "SUCCEEDED"
    row.heartbeat_at = _now()
    row.error_message = None
    await db.flush()
    return str(row.report_file_id)


async def generate_report_task(
    ctx: dict, *, report_type: str, project_id: str, record_ids: list[str],
    output_format: str, style_json: dict, ctx_vars: dict,
) -> str:
    """ARQ 任务体。返回 `report_file_id` 字符串。

    `ctx` 由 ARQ 注入，含 `job_id` / `job_try`（实测 arq.worker 的
    `ctx = {job_id, job_try, enqueue_time, score}`）+ 本仓自带的 `db`。
    """
    db: AsyncSession = ctx["db"]
    job_id = ctx.get("job_id") or str(uuid.uuid4())
    attempt_no = int(ctx.get("job_try") or 1)
    audit = AuditService(db)

    pid = uuid.UUID(project_id) if isinstance(project_id, str) else project_id
    style = ReportStyle.model_validate(style_json or {})

    row = await _mark_pending(db, project_id=pid, job_id=job_id,
                              output_format=output_format)

    try:
        # ⚠️ 属性查找：`report_service.generate` 写成裸名会把当前函数对象绑死，
        # 之后 monkeypatch 本模块属性/同名 import 改不到它，测试成假绿
        # （bug-150 同族）。
        from app.services.report import report_service
        out = await report_service.generate(
            report_type=report_type, project_id=pid,
            record_ids=[uuid.UUID(r) for r in record_ids],
            output_format=output_format, style=style, ctx=ctx_vars, db=db)
        file_id = await _finalize(
            db, row, digest=out.content_hash, relpath=out.file_path,
            size=out.size_bytes, fmt=output_format)
        return file_id
    except Exception as e:  # noqa: BLE001
        row.status = "FAILED"
        row.error_message = f"{type(e).__name__}: {e}"[:500]
        row.heartbeat_at = _now()
        await audit.write(
            action=AuditAction.REPORT_FAILED, resource_type="report",
            resource_id=row.report_file_id,
            detail={"task_id": job_id, "attempt_no": attempt_no,
                    "report_type": report_type, "output_format": output_format,
                    "error": f"{type(e).__name__}: {e}"[:500]},
        )
        raise          # 交给 ARQ 重试 —— 用户裁决「每次失败都写」由这里落实


async def reclaim_stale_tasks(db: AsyncSession, *, older_than_minutes: int = STALE_MINUTES) -> int:
    """把僵死的 PENDING 任务置 FAILED，返回回收条数。

    **只回收 PENDING**：`SUCCEEDED` 是成品，`FAILED` 已是终态，
    `DELETING` 是 ADR-P8-004 三步删除的中间态 —— 把它改成 FAILED 会打断
    删除流程，让文件永远删不掉。

    回收也写审计：否则「为什么这一行变成 FAILED」查不到。
    """
    cutoff = _now() - dt.timedelta(minutes=older_than_minutes)
    rows = (await db.execute(
        select(ReportFile).where(
            ReportFile.status == "PENDING",
            ReportFile.heartbeat_at < cutoff,
        )
    )).scalars().all()
    if not rows:
        return 0

    audit = AuditService(db)
    for r in rows:
        r.status = "FAILED"
        r.error_message = (
            f"僵死任务：心跳超过 {older_than_minutes} 分钟未更新"
            "（ARQ 进程可能被 kill）")
        r.heartbeat_at = _now()
        await audit.write(
            action=AuditAction.REPORT_TASK_RECLAIMED, resource_type="report",
            resource_id=r.report_file_id,
            detail={"stale_minutes": older_than_minutes,
                    "task_id": str(r.content_hash).removeprefix(PENDING_HASH_PREFIX)},
        )
    await db.flush()
    logger.warning("回收僵死报表任务 %d 个", len(rows))
    return len(rows)


async def reclaim_stale_tasks_batch(db: AsyncSession) -> int:
    """cron 入口（ARQ cron 要的是无参函数）。"""
    return await reclaim_stale_tasks(db, older_than_minutes=STALE_MINUTES)


__all__ = ["generate_report_task", "reclaim_stale_tasks",
           "reclaim_stale_tasks_batch", "PENDING_HASH_PREFIX", "STALE_MINUTES"]