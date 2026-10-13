"""ARQ 报表异步生成任务。

b7 决策：报表生成走 ARQ 异步（用户 2026-10-08 审查）—— 10k 行 PDF ≈ 10 CPU-秒，
在 async 端点里同步跑会阻塞整个 event loop。

## 状态机

    建 PENDING 行 ──┬── 渲染成功 ──→ 就地更新为 SUCCEEDED（或复用已有行）
                    ├── 渲染失败 ──→ 置 FAILED + 写审计 ──→ 抛出（ARQ 重试）
                    └── 进程被 kill ──→ 永远卡 PENDING ──→ reclaim_stale_tasks 回收

**为什么先建 PENDING 行**：渲染期间状态端点要有东西可读，且进程被杀时
状态得有地方可丢 —— 否则这一次生成在系统里不存在，用户只看到「转圈到超时」。

## 本模块的每个状态变更都必须 commit

session 是任务体自己开的（`worker.session_scope`），**关掉就等于没写**。
而这一层从 service 到 `_mark_pending` / `_finalize` **全都只 `flush`** ——
它符合本仓「service 只 flush、端点/任务负责 commit」的约定，但约定得由
**调用方**兑现。调用方此前一次都没兑现，于是：PENDING 行从不落库
（回收器永远扫不到它）、成功件从不落库（前端拿着 report_file_id 轮询，
每个状态查询都 404）、FAILED 也从不落库（行停在 PENDING）。

⚠️ 这三条在单测里**全是绿的**：测试复用任务自己的 session，读的是它未提交
的数据 —— 替身比被测物更宽容。真正的观测点是「任务返回之后，用另一个
session 读」，见 `test_report_tasks.py` 里两个 `_is_committed` 测试。

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

    实现**委托给 `report_service.ensure_pending_row`** —— 端点在入队时就用
    同一个函数建行（TODO-063），两处各写一份不是「重复」而是**时序**问题：
    只有 worker 建行的话，202 与「行存在」之间有 404 窗口（bug-167）。
    ARQ 重试时 job_id 不变，故这里取回的正是端点建的那一行。
    """
    from app.services.report import report_service

    row = await report_service.ensure_pending_row(
        db, project_id=project_id, task_id=job_id,
        output_format=output_format)
    await db.commit()      # ⚠️ 必须提交，见模块 docstring
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

    `ctx` 里 `job_id` / `job_try` 由 **ARQ** 注入；session 走 worker
    注入的 `session_factory`（经 `_make_session` 取）。

    ⚠️ 原先写 `ctx["db"]` —— **worker 从不注入这个键**（它注入的是
    `session_factory`）。实测：job 被消费、结果是 `KeyError: 'db'`、
    worker 一行日志不打 → API 早就返回 202 了，于是「固定 10 类报表
    生成」这条路径**从来没成功跑过**。
    """

    from arq import Retry

    from app.workers.worker import MAX_TRIES, RETRY_DEFER_S, session_scope

    # ⚠️ 用 `session_scope` 而不是裸 `_make_session(ctx)`：session 是本函数
    # 开的，关闭的责任也在本函数，而两处任务**都曾忘了关**（2026-10-13 修）。
    async with session_scope(ctx) as db:
        job_id = ctx.get("job_id") or str(uuid.uuid4())
        attempt_no = int(ctx.get("job_try") or 1)
        audit = AuditService(db)

        pid = uuid.UUID(project_id) if isinstance(project_id, str) else project_id
        style = ReportStyle.model_validate(style_json or {})

        row = await _mark_pending(db, project_id=pid, job_id=job_id,
                                  output_format=output_format)
        row_id = row.report_file_id

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
            # ⚠️ 必须提交：`_finalize` 只 flush。不提交的话任务 session 一关，
            # 成品行连同文件登记一起消失，而前端已经拿到 202 与 report_file_id，
            # 之后每个状态查询都是 404。
            await db.commit()
            return file_id
        except Exception as e:  # noqa: BLE001
            # ⚠️ 先 rollback：渲染中途失败时事务可能已经 aborted，
            # 此时任何写都会报 `current transaction is aborted`。
            # rollback 之后 `row` 已过期，按主键重取，不读它的属性。
            await db.rollback()
            failed = (await db.execute(
                select(ReportFile).where(
                    ReportFile.report_file_id == row_id))).scalar_one_or_none()
            # ⚠️ **只有最后一次尝试才标 FAILED**。ARQ 会重试
            # （`WorkerSettings.max_tries`），中途就标 FAILED 会让状态端点
            # 提前显示「失败」，而任务随后重试成功 —— 用户拿到一个**假的**
            # 终态，而文件其实生成了、就在库里。
            #
            # 审计**每次失败都写**（用户裁决）：那是「第 2 次为什么又失败」
            # 的唯一线索，与「现在是不是终态」是两件不同的事。
            if failed is not None and attempt_no >= MAX_TRIES:
                failed.status = "FAILED"
                failed.error_message = f"{type(e).__name__}: {e}"[:500]
                failed.heartbeat_at = _now()
            await audit.write(
                action=AuditAction.REPORT_FAILED, resource_type="report",
                resource_id=row_id,
                detail={"task_id": job_id, "attempt_no": attempt_no,
                        "report_type": report_type, "output_format": output_format,
                        "error": f"{type(e).__name__}: {e}"[:500]},
            )
            # ⚠️ **必须提交**，否则行停在 PENDING，前端无限轮询 ——
            # 而 `reclaim_stale_report_tasks` 那个 cron 存在的原因正是
            # 这个状态压根写不进去（它是在补一个从没写成功过的状态）。
            await db.commit()
            # ⚠️ **ARQ 0.28 不会因为普通异常重试**（`arq/worker.py:612-637`
            # 的分支只认 `Retry` / `CancelledError` / `RetryJob`，其余一律
            # `failed, finish = True` 当场判死）。所以「还有次数就抛 `Retry`」
            # 是重试能发生的**唯一**前提 —— 只配 `WorkerSettings.max_tries`
            # 的话，一个普通 `PcsError` 永远只跑一次。
            #
            # 2026-10-13 真跑 Redis 实测到的症状正是如此：审计只写 1 条、
            # retry 计数器停在 0、行永远 PENDING、前端无限轮询。
            if attempt_no < MAX_TRIES:
                raise Retry(defer=RETRY_DEFER_S) from e
            raise      # 次数用尽：抛原始异常，ARQ 据此判死并记下原因


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
    """**不**是 cron 入口 —— 它要一个 db，ARQ cron 只传 ctx。

    保留它是为了单测能直接注入 session 调用。cron 走下面的
    `reclaim_stale_report_tasks`（ctx 单参）。
    """
    return await reclaim_stale_tasks(db, older_than_minutes=STALE_MINUTES)


async def reclaim_stale_execution_logs(
        db: AsyncSession, *, older_than_minutes: int = STALE_MINUTES) -> int:
    """回收**自定义定义**执行日志里僵死的行，返回回收条数。

    只碰 `status IN ('QUEUED', 'RUNNING')` 且 `updated_at` 早于阈值的行 ——
    FINISHED / FAILED 已是终态，再动它们就是篡改审计记录。

    ⚠️ **不删行**。这张表是审计：删了，「谁在什么时候请求过这次执行、
    当时用的什么条件」就再也复现不出来。回收只是补上一个结局。

    阈值复用 `STALE_MINUTES`（15 分钟）—— 与 `reclaim_stale_tasks`
    （report_files 那侧）同一个数字是刻意的：两边的「多久算僵死」应该
    跟着同一件事（渲染耗时）走，没有理由一个 15 分钟一个 5 分钟。
    """
    from sqlalchemy import or_

    from app.models.report import ReportExecutionLog

    cutoff = _now() - dt.timedelta(minutes=older_than_minutes)
    rows = (await db.execute(
        select(ReportExecutionLog).where(
            ReportExecutionLog.status.in_(("QUEUED", "RUNNING")),
            or_(ReportExecutionLog.updated_at < cutoff,
                ReportExecutionLog.created_at < cutoff),
        )
    )).scalars().all()
    if not rows:
        return 0

    audit = AuditService(db)
    for row in rows:
        row.status = "FAILED"
        row.condition_snapshot = {
            **dict(row.condition_snapshot or {}),
            "reclaimed_at": _now().isoformat(),
            "reclaim_reason": f"超过 {older_than_minutes} 分钟未出文件（worker 未完成）",
        }
        await audit.write(
            action=AuditAction.REPORT_FAILED,
            resource_type="report_definition", resource_id=row.def_id,
            detail={"task_id": row.task_id, "reclaimed": True,
                    "stale_minutes": older_than_minutes,
                    "def_id": str(row.def_id)},
        )
    await db.flush()
    return len(rows)


async def reclaim_stale_report_tasks(ctx) -> None:
    """**cron 入口**（ARQ cron 只传一个 `ctx`）。

    ⚠️ 原先 cron_jobs 里挂的是 `reclaim_stale_tasks_batch(db: AsyncSession)`，
    而它的 docstring 写着「ARQ cron 要的是无参函数」—— 签名与自述矛盾。
    ARQ 按位置传 ctx，于是它把 **ctx 当 db** 用：
    `select(...)` 那里一碰 `.execute()` 就炸。

    这个错只在 cron **真的触发**时才现形（每小时 :03 / :33），
    所以它可以静静烂在仓库里 —— 与「worker 根本没起来」是两回事，
    后者把它彻底遮住了。
    """
    db: AsyncSession = _ctx_session(ctx)
    await reclaim_stale_tasks(db, older_than_minutes=STALE_MINUTES)
    # 自定义定义那条路的执行日志也要回收（TODO-064）。此前只有 report_files
    # 侧有回收器，而日志行在 bug-167 修复后从「worker 跑才有」变成
    # 「入队就有」—— 于是「worker 全挂」第一次变成了可观测的永久挂起。
    await reclaim_stale_execution_logs(db, older_than_minutes=STALE_MINUTES)


def _ctx_session(ctx) -> AsyncSession:
    """从 ARQ ctx 取 session（worker 的 `on_startup` 注入 session_factory）。"""
    factory = ctx.get("session_factory")
    if factory is None:
        raise RuntimeError(
            "ctx 里没有 session_factory —— worker 的 on_startup 没跑。"
            "（直接调用本函数做单测时请注入 session_factory=...）")
    return factory()


__all__ = ["generate_report_task", "reclaim_stale_tasks",
           "reclaim_stale_tasks_batch", "PENDING_HASH_PREFIX", "STALE_MINUTES"]