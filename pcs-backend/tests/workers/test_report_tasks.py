"""ARQ 报表异步任务 —— 状态持久化 + 重试审计 + 僵死回收。

三条要害：

1. **每次失败都写一条 `REPORT_FAILED`，带 `task_id` + `attempt_no`**
   （用户 2026-10-09 裁决）。ARQ 的 `keep_result` 默认 3600 秒 ——
   **Redis 里任务结果/异常 1 小时后被清除**，所以 `audit_logs` 是失败的
   **唯一**持久记录。这不是审计偏好，是可追溯性的唯一保障。

2. **僵死任务回收** —— ARQ 进程被 OOM kill 时状态会永远卡在 PENDING，
   前端无限轮询且无人知道。靠 `heartbeat_at` 识别。

3. **内容指纹去重必须跨异步边界成立** —— 同步路径复用同内容文件，
   异步路径新建的 PENDING 行不能在成功时与已存在的 SUCCEEDED 行撞唯一键。
"""
from __future__ import annotations

import datetime as dt
import uuid

import pytest

from app.models.enums import AuditAction
from app.models.report import REPORT_FILE_STATUSES, ReportDefinition, ReportExecutionLog
from app.models.system import AuditLog
from app.services.report.style import ReportStyle
from app.workers.report_tasks import (  # noqa: E501
    PENDING_HASH_PREFIX,
    STALE_MINUTES,
    generate_report_task,
    reclaim_stale_execution_logs,
    reclaim_stale_tasks,
)

CTX_VARS = {"project_no": "PCS-2026-001", "doc_no": "D-001", "rev": "A"}


def _job_ctx(db, *, job_id="job-1", job_try=1):
    """ARQ 传给任务的 ctx。

    ⚠️ 这里原先造的是 `{"db": db, ...}` —— **照抄了一个不存在的契约**。
    worker 的 `_on_startup` 注入的是 `session_factory`，从没注入过 `db`；
    而本函数的 docstring 又写着「实测 ctx = {job_id, job_try, ...}」，
    两句话互相矛盾，正文那个 `db` 才是被当真的那个。

    后果：任务体读 `ctx["db"]` 时测试绿、生产 `KeyError: 'db'` →
    job failed、worker 一行日志不打。2026-10-13 真跑 Redis + worker 时
    才暴露。现在按 worker 的真实注入造：
    `session_factory` 是一个「调用即返回该 session」的工厂。
    """
    return {
        "session_factory": lambda: db,
        "job_id": job_id,
        "job_try": job_try,
    }


async def _make_row(db, project_id, *, status, heartbeat_at, seed="seed"):
    """建一行指定状态的 ReportFile。`seed` 必须唯一 —— content_hash 有 UNIQUE 约束。"""
    from app.models.report import ReportFile

    row = ReportFile(
        project_id=project_id, content_hash=f"{PENDING_HASH_PREFIX}{seed}",
        file_path="pending", file_format="pdf", size_bytes=0,
        status=status, heartbeat_at=heartbeat_at,
    )
    db.add(row)
    await db.flush()
    return row


# --- 成功路径 ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_task_persists_status_and_returns_file_id(db, project_id):
    """返回 report_file_id（uuid 字符串）—— ARQ 的返回值要能回传给调用方。"""
    out = await generate_report_task(
        _job_ctx(db),
        report_type="EQUIPMENT_LIST", project_id=str(project_id),
        record_ids=[], output_format="pdf", style_json={}, ctx_vars=CTX_VARS)
    assert isinstance(out, str) and len(out) == 36


@pytest.mark.asyncio
async def test_task_creates_pending_row_before_rendering(db, project_id):
    """**先建 PENDING 行再渲染** —— 否则渲染期间状态端点无物可读、
    进程被杀时状态无处可丢（永远查不到这一次的生成）。"""
    from sqlalchemy import select

    from app.models.report import ReportFile

    seen: list[str] = []
    orig = generate_report_task.__globals__["_mark_pending"]

    async def spy(*a, **k):
        row = await orig(*a, **k)
        seen.append(row.status)
        return row

    generate_report_task.__globals__["_mark_pending"] = spy
    try:
        await generate_report_task(
            _job_ctx(db), report_type="EQUIPMENT_LIST",
            project_id=str(project_id), record_ids=[], output_format="pdf",
            style_json={}, ctx_vars=CTX_VARS)
    finally:
        generate_report_task.__globals__["_mark_pending"] = orig

    assert seen == ["PENDING"], "渲染前必须先落 PENDING 行"
    rows = (await db.execute(select(ReportFile))).scalars().all()
    assert rows and rows[0].status == "SUCCEEDED"


@pytest.mark.asyncio
async def test_task_marks_row_succeeded_with_real_path(db, project_id):
    """成功后 PENDING 行必须被**就地更新**为真实内容 —— 不是新建第二行。"""
    from sqlalchemy import func, select

    from app.models.report import ReportFile

    out = await generate_report_task(
        _job_ctx(db), report_type="EQUIPMENT_LIST", project_id=str(project_id),
        record_ids=[], output_format="pdf", style_json={}, ctx_vars=CTX_VARS)

    row = (await db.execute(select(ReportFile))).scalar_one()
    assert str(row.report_file_id) == out
    assert row.status == "SUCCEEDED"
    assert not row.content_hash.startswith(PENDING_HASH_PREFIX), \
        "成功后 content_hash 仍是占位符"
    n = await db.scalar(select(func.count()).select_from(ReportFile.__table__))
    assert n == 1, "渲染前建 PENDING + 渲染后更新，就地转换而不是又插一行"


@pytest.mark.asyncio
async def test_same_content_reuses_existing_file_across_async_boundary(db, project_id):
    """**去重必须跨异步边界成立**。

    同步路径下同内容复用同一行；异步路径先建了一个 PENDING 行，
    渲染完发现内容指纹已存在 —— 此时若直接更新会撞 `uq_report_files_content_hash`。
    正确处置：删掉自己的 PENDING 行、返回已有行（与同步路径同语义）。
    """
    a = await generate_report_task(
        _job_ctx(db, job_id="job-a"), report_type="EQUIPMENT_LIST",
        project_id=str(project_id), record_ids=[], output_format="pdf",
        style_json={}, ctx_vars=CTX_VARS)
    b = await generate_report_task(
        _job_ctx(db, job_id="job-b"), report_type="EQUIPMENT_LIST",
        project_id=str(project_id), record_ids=[], output_format="pdf",
        style_json={}, ctx_vars=CTX_VARS)
    assert a == b, "同内容两次异步生成应复用同一个 report_file_id"


# --- 失败路径 ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_failure_sets_failed_status_and_writes_audit(db, project_id, monkeypatch):
    """SPEC §六验收：失败也记录。

    ⚠️ 这条测试原先**一条断言都没有** —— 名字说「sets failed status and
    writes audit」，正文只跑了任务、确认异常冒出来就结束了。删掉
    「标 FAILED」或「写审计」两处代码，它照样绿。
    这就是 TODO-016 说的「失败路径覆盖为零」的一个具体样本。
    """
    from sqlalchemy import func, select

    from app.models.report import ReportFile
    from app.services.report import report_service
    from app.workers.worker import MAX_TRIES

    async def boom(*a, **k):
        raise RuntimeError("渲染炸了")

    monkeypatch.setattr(report_service, "generate", boom)
    # ⚠️ 用**最后一次**尝试（job_try=MAX_TRIES）：中间的尝试**不写** FAILED
    # （ARQ 还会重试，写了就是假的终态）。这条要验的正是「终态落库」，
    # 而终态只在最后一次存在。
    with pytest.raises(RuntimeError):
        await generate_report_task(
            _job_ctx(db, job_try=MAX_TRIES), report_type="EQUIPMENT_LIST",
            project_id=str(project_id), record_ids=[],
            output_format="pdf", style_json={}, ctx_vars=CTX_VARS)
    await db.commit()

    row = (await db.execute(select(ReportFile))).scalar_one()
    assert row.status == "FAILED", f"实得 {row.status}"
    assert row.error_message and "渲染炸了" in row.error_message

    n = await db.scalar(select(func.count()).select_from(AuditLog).where(
        AuditLog.action == AuditAction.REPORT_FAILED.value))
    assert n == 1, f"应写 1 条 REPORT_FAILED，实得 {n}"


@pytest.mark.asyncio
async def test_each_failed_attempt_writes_one_audit_row(db, project_id, monkeypatch):
    """**用户 2026-10-09 裁决**：每次失败都写一条，带 `task_id` + `attempt_no`。

    ARQ `keep_result` 默认 3600 秒 —— Redis 里的异常 1 小时后就清空了。
    audit_logs 是失败的唯一持久记录，所以「每次都写」不是偏好，是必然。
    """
    from sqlalchemy import select

    from app.services.report import report_service

    async def boom(*a, **k):
        raise RuntimeError("渲染炸了")

    monkeypatch.setattr(report_service, "generate", boom)
    for attempt in (1, 2):
        with pytest.raises(RuntimeError):
            await generate_report_task(
                _job_ctx(db, job_try=attempt), report_type="EQUIPMENT_LIST",
                project_id=str(project_id), record_ids=[], output_format="pdf",
                style_json={}, ctx_vars=CTX_VARS)

    rows = (await db.execute(select(AuditLog))).scalars().all()
    failed = [r for r in rows if r.action == AuditAction.REPORT_FAILED.value]
    assert len(failed) == 2, f"两次失败应写 2 条审计，实得 {len(failed)}"
    for r in failed:
        assert r.detail_json["task_id"] == "job-1"
        assert r.detail_json["attempt_no"] in (1, 2)
    assert sorted(r.detail_json["attempt_no"] for r in failed) == [1, 2]


@pytest.mark.asyncio
async def test_failure_marks_row_failed_with_error_message(db, project_id, monkeypatch):
    """失败后必须有**终结状态** —— 否则前端只能看到「转圈到超时」。"""
    from sqlalchemy import select

    from app.models.report import ReportFile
    from app.services.report import report_service
    from app.workers.worker import MAX_TRIES

    async def boom(*a, **k):
        raise RuntimeError("渲染炸了")

    monkeypatch.setattr(report_service, "generate", boom)
    # ⚠️ 用**最后一次**尝试（job_try=MAX_TRIES）：中间的尝试**不写** FAILED
    # （ARQ 还会重试，写了就是假的终态）。这条要验的正是「终态落库」，
    # 而终态只在最后一次存在。
    with pytest.raises(RuntimeError):
        await generate_report_task(
            _job_ctx(db, job_try=MAX_TRIES), report_type="EQUIPMENT_LIST",
            project_id=str(project_id), record_ids=[],
            output_format="pdf", style_json={}, ctx_vars=CTX_VARS)

    row = (await db.execute(select(ReportFile))).scalar_one()
    assert row.status == "FAILED"
    assert row.error_message and "渲染炸了" in row.error_message


@pytest.mark.asyncio
async def test_retry_and_final_failure_are_distinguishable_exceptions(
        db, project_id, monkeypatch):
    """两种结局必须是**两种异常类型**：还有次数抛 `Retry`，用尽抛原始异常。

    ⚠️ `arq.Retry` 继承自 `RuntimeError`（`class Retry(RuntimeError)`），
    所以本文件里那 8 处 `pytest.raises(RuntimeError)` 对两者都成立。
    把 `if attempt_no < MAX_TRIES: raise Retry(...)` 整个删掉、
    改成无条件抛 `Retry`，**这些断言一条都不会红** —— 而后果正是
    bug-168 修复时要防的那个：ARQ 无限重入，任务永远拿不到终态，
    行停在中间态，前端无限轮询。

    换成「原始异常」那侧同样需要钉住：若最后一次也抛 `Retry`，
    ARQ 会认为任务还该重试，`max_tries` 到顶后行为就不是我们设计的了。

    所以这条断言的是**类型本身**，并且显式排除另一种。
    """
    from arq import Retry

    from app.services.report import report_service
    from app.workers.worker import MAX_TRIES

    async def boom(*a, **k):
        raise RuntimeError("渲染炸了")

    monkeypatch.setattr(report_service, "generate", boom)

    def _call(try_no):
        return generate_report_task(
            _job_ctx(db, job_try=try_no), report_type="EQUIPMENT_LIST",
            project_id=str(project_id), record_ids=[],
            output_format="pdf", style_json={}, ctx_vars=CTX_VARS)

    # 还有次数 -> 必须是 Retry，否则 ARQ 不会重试（bug-168）
    with pytest.raises(Retry):
        await _call(1)

    # 次数用尽 -> 必须是原始 RuntimeError，且**不能**是 Retry
    with pytest.raises(RuntimeError) as ei:
        await _call(MAX_TRIES)
    assert not isinstance(ei.value, Retry), (
        "最后一次尝试抛了 Retry —— ARQ 会当成还能重试，"
        "任务拿不到终态")
    assert "渲染炸了" in str(ei.value), "终态异常应当是原始的那个，不是包装过的"


@pytest.mark.asyncio
async def test_retry_after_failure_reuses_same_row(db, project_id, monkeypatch):
    """重试是**同一个任务**，不该每次新建一行 —— 否则一次失败的重试链
    会在库里留下一串孤儿 PENDING 行。"""
    from sqlalchemy import func, select

    from app.models.report import ReportFile
    from app.services.report import report_service

    calls = {"n": 0}

    async def flaky(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("第一次失败")
        return None

    monkeypatch.setattr(report_service, "generate", flaky)
    with pytest.raises(RuntimeError):
        await generate_report_task(
            _job_ctx(db, job_try=1), report_type="EQUIPMENT_LIST",
            project_id=str(project_id), record_ids=[], output_format="pdf",
            style_json={}, ctx_vars=CTX_VARS)
    # flaky 第二次返回 None → _finalize 会因 out=None 抛 AttributeError，
    # 这里断言的是「第二次**没**成功」，不关心具体异常类型。
    # ⚠️ `Retry` 也要算进去：2026-10-13 起，失败且**还有次数**时任务体改抛
    # `Retry`（ARQ 0.28 不因普通异常重试），于是异常类型被换掉了，
    # 而「第二次仍然失败」这件事没变。
    from arq import Retry
    with pytest.raises((AttributeError, TypeError, Retry)):
        await generate_report_task(
            _job_ctx(db, job_try=2), report_type="EQUIPMENT_LIST",
            project_id=str(project_id), record_ids=[], output_format="pdf",
            style_json={}, ctx_vars=CTX_VARS)

    n = await db.scalar(select(func.count()).select_from(ReportFile.__table__))
    assert n == 1, f"同一 job 重试应仍只有 1 行，实得 {n}"


# --- 僵死回收 ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_stale_pending_task_is_reclaimed(db, project_id):
    """**ARQ 进程被 OOM kill，状态会永远卡在 PENDING，前端无限轮询。**

    TODO-016 记「ARQ 失败路径覆盖为零」，这条正好落在那个已知空洞上。
    """
    stale = await _make_row(db, project_id, status="PENDING",
                            heartbeat_at=dt.datetime.now(dt.UTC) - dt.timedelta(minutes=30))
    n = await reclaim_stale_tasks(db, older_than_minutes=15)
    await db.refresh(stale)
    assert n == 1
    assert stale.status == "FAILED"
    assert stale.error_message


@pytest.mark.asyncio
async def test_cron_reclaim_commits_so_the_state_survives_its_own_session(tmp_path):
    """回收必须**提交** —— cron 入口开的是**自己的** session。

    ⚠️ 这条测试用**文件库**而不是默认的 `sqlite+aiosqlite:///:memory:`。
    原因实测过（`StaticPool`）：

        会话 A execute(insert) 不提交
        会话 B select  ->  **读到那 1 行**

    `:memory:` + aiosqlite 的默认池是 `StaticPool`，**所有 session 共享同一条
    连接**，于是「另一个 session 读」根本不是另一个连接 —— 它读的就是 A
    自己没提交的数据。**替身比被测物更宽容**：把 `await db.flush()` 换成
    一行注释，这条测试照样绿。

    这不是本条测试的私事：本文件里那条
    `test_failure_state_is_committed_not_just_left_in_the_session`
    （2026-10-13 加，docstring 明写「必须用另一个 session 读」）用的是同一个
    fixture，所以**它也没有真正证明 commit**。文件库是当前唯一能让
    「未提交」真正被观测到的办法。

    生产形态照搬：ctx 只给 factory，session 由被测代码自己开、自己关。
    """
    import uuid as _uuid

    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.db.base import Base as _SA_Base
    from app.models.report import ReportFile
    from app.workers.report_tasks import reclaim_stale_report_tasks

    # 事件监听（gen_random_uuid 等）与 conftest 相同，否则建表/插入会炸
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/reclaim.db")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(_SA_Base.metadata.create_all)

        maker = async_sessionmaker(engine, expire_on_commit=False)
        # 种子：一条僵死 PENDING，**先提交**
        async with maker() as seed:
            seed.add(ReportFile(
                project_id=_uuid.uuid4(),
                content_hash=f"{PENDING_HASH_PREFIX}commit-probe",
                file_path="pending", file_format="pdf", size_bytes=0,
                status="PENDING",
                heartbeat_at=dt.datetime.now(dt.UTC) - dt.timedelta(minutes=30),
            ))
            await seed.commit()

        # 被测代码自己开 session、自己关
        await reclaim_stale_report_tasks({"session_factory": maker})

        # 观测：另一个连接
        async with maker() as other:
            rows = (await other.execute(select(ReportFile))).scalars().all()
        assert [r.status for r in rows] == ["FAILED"], (
            f"回收后另一个**连接**读到 {[r.status for r in rows]} —— "
            "cron 的回收没有提交，session 一关就全部回滚。"
            "结果是整个僵死回收机制静默失效：ARQ 进程被 kill 之后任务永远"
            "停在 PENDING，前端无限轮询且无人知道。")
        assert rows[0].error_message
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_fresh_pending_task_is_not_reclaimed(db, project_id):
    """新鲜的 PENDING 不能被误杀 —— 10k 行 PDF 要 10 秒，不能按秒级心跳判死。"""
    ok = await _make_row(db, project_id, status="PENDING",
                         heartbeat_at=dt.datetime.now(dt.UTC))
    await reclaim_stale_tasks(db, older_than_minutes=15)
    await db.refresh(ok)
    assert ok.status == "PENDING", "新鲜的 PENDING 不能被误杀"


@pytest.mark.asyncio
async def test_reclaim_does_not_touch_succeeded_or_deleting(db, project_id):
    """`DELETING` 是 ADR-P8-004 的三步删除中间态，**不是**僵死任务 ——
    回收器把它改成 FAILED 会打断删除流程，让文件永远删不掉。"""
    deleting = await _make_row(db, project_id, status="DELETING", seed="del",
                               heartbeat_at=dt.datetime.now(dt.UTC) - dt.timedelta(minutes=30))
    done = await _make_row(db, project_id, status="SUCCEEDED", seed="done",
                           heartbeat_at=dt.datetime.now(dt.UTC) - dt.timedelta(minutes=30))
    await reclaim_stale_tasks(db, older_than_minutes=15)
    await db.refresh(deleting)
    await db.refresh(done)
    assert deleting.status == "DELETING"
    assert done.status == "SUCCEEDED"


@pytest.mark.asyncio
async def test_reclaim_writes_audit_for_each_reclaimed_task(db, project_id):
    """回收也要审计 —— 否则「为什么这一行变成 FAILED」查不到。"""
    from sqlalchemy import select

    await _make_row(db, project_id, status="PENDING",
                    heartbeat_at=dt.datetime.now(dt.UTC) - dt.timedelta(minutes=30))
    await reclaim_stale_tasks(db, older_than_minutes=15)
    rows = (await db.execute(select(AuditLog))).scalars().all()
    assert any("RECLAIM" in (r.action or "") or "STALE" in (r.action or "")
               for r in rows), f"僵死回收应写审计，实得 {[r.action for r in rows]}"


# --- 契约 -------------------------------------------------------------------


def test_audit_actions_exist_and_are_short():
    """4 个 REPORT_* 动作必须已注册，且值 ≤50 字符（有全局断言在跑）。"""
    for name in ("REPORT_GENERATED", "REPORT_DOWNLOADED", "REPORT_FAILED",
                 "REPORT_EXECUTED"):
        value = getattr(AuditAction, name).value
        assert len(value) <= 50


def test_pending_hash_prefix_cannot_collide_with_real_digest():
    """占位 content_hash 必须**不可能**等于真实 sha256 —— 否则占位行会
    撞上真实文件的唯一键，去重逻辑直接错乱。"""
    assert len(PENDING_HASH_PREFIX) > 0
    import re
    assert re.fullmatch(r"[0-9a-f]{64}", PENDING_HASH_PREFIX) is None, \
        "占位前缀长得像 sha256 十六进制，会与真实内容指纹混淆"


def test_status_state_set_includes_pending_and_deleting():
    assert {"PENDING", "SUCCEEDED", "FAILED", "DELETING"} <= REPORT_FILE_STATUSES


def test_style_json_roundtrips_through_report_style():
    """style_json 从 DB/队列传进任务，必须能还原成 ReportStyle。"""
    s = ReportStyle(page_size="A3", font_size_body=12)
    assert ReportStyle.model_validate_json(s.model_dump_json()).font_size_body == 12

@pytest.mark.asyncio
async def test_failure_state_is_committed_not_just_left_in_the_session(
        db, db_engine, project_id, monkeypatch):
    from app.workers.worker import MAX_TRIES

    """失败状态必须**提交**，不能只挂在任务自己的事务里。

    ⚠️ 观测点：必须用**另一个 session** 读。上面那些测试用任务自己的
    session 读未提交的数据 —— 替身比被测物更宽容，于是「任务从没 commit」
    这件事在单测里完全看不见。

    生产上任务体开自己的 session（`session_factory`），ARQ 复用 worker 的
    进程 —— 那个 session 一关（或被 GC），未提交的 FAILED 就没了，
    行留在 PENDING。前端于是无限轮询，而这正是
    `reclaim_stale_report_tasks` 那个 cron 存在的原因：
    **它是在补一个从没写成功过的状态，不是回收「僵死」**。
    """
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.models.report import ReportFile
    from app.services.report import report_service

    async def boom(*a, **k):
        raise RuntimeError("渲染炸了")

    monkeypatch.setattr(report_service, "generate", boom)
    # ⚠️ 用**最后一次**尝试（job_try=MAX_TRIES）：中间的尝试**不写** FAILED
    # （ARQ 还会重试，写了就是假的终态）。这条要验的正是「终态落库」，
    # 而终态只在最后一次存在。
    with pytest.raises(RuntimeError):
        await generate_report_task(
            _job_ctx(db, job_try=MAX_TRIES), report_type="EQUIPMENT_LIST",
            project_id=str(project_id), record_ids=[],
            output_format="pdf", style_json={}, ctx_vars=CTX_VARS)

    # 任务已经返回（session 已关）。**新开一个 session** 读，不复用任务那个：
    # 复用的话读的是它自己未提交的数据，commit 与否根本看不出来。
    async with async_sessionmaker(db_engine, expire_on_commit=False)() as other:
        rows = (await other.execute(select(ReportFile))).scalars().all()
    assert [r.status for r in rows] == ["FAILED"], (
        f"独立 session 读到 {[r.status for r in rows]} —— "
        "FAILED 只存在于任务自己的事务里，session 一关就没了")


@pytest.mark.asyncio
async def test_success_state_is_committed(db, db_engine, project_id):
    """成功路径同样必须 **commit** —— 失败路径提交了不代表成功路径提交了。

    同一个原因：`report_service.generate` / `_mark_pending` / `_finalize`
    全都只 `flush`。任务自己的 session 一关，没提交的东西就没了 ——
    成品 `report_files` 行连同文件登记一起消失，而前端已经拿到 202 与
    `report_file_id`，之后每个状态查询都是 404。
    """
    import uuid

    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.models.report import ReportFile

    out = await generate_report_task(
        _job_ctx(db), report_type="EQUIPMENT_LIST", project_id=str(project_id),
        record_ids=[], output_format="pdf", style_json={}, ctx_vars=CTX_VARS)

    async with async_sessionmaker(db_engine, expire_on_commit=False)() as other:
        row = (await other.execute(
            select(ReportFile).where(
                ReportFile.report_file_id == uuid.UUID(out)))).scalar_one_or_none()
    assert row is not None, (
        f"独立 session 读不到 report_file_id={out} —— 成功路径从没 commit，"
        "session 一关成品行就消失了")
    assert row.status == "SUCCEEDED"


# --- TODO-064：自定义定义执行日志的回收器 -------------------------------------


def _exec_log(db, def_id, *, status, minutes_ago=0):
    """造一行指定状态的执行日志。

    ⚠️ `created_at` / `updated_at` 要**显式**给：回收器按时间筛，而
    `TimestampMixin` 的默认是 `server_default=now()` —— 不覆盖的话
    每一行都是「刚刚」，回收器一条都扫不到，测试会假绿。
    """
    ts = dt.datetime.now(dt.UTC) - dt.timedelta(minutes=minutes_ago)
    row = ReportExecutionLog(
        def_id=def_id, def_version="0.1.0", condition_snapshot={},
        row_count=0, output_format="pdf", status=status,
        task_id=f"t-{uuid.uuid4().hex[:8]}",
        created_at=ts, updated_at=ts)
    db.add(row)
    return row


async def _published_def(db, project_id) -> uuid.UUID:
    """建一份已发布定义并返回 def_id。

    执行日志的 `def_id` 是指向 `report_definitions` 的 NOT NULL 外键 ——
    填随机 UUID 会撞外键，而错误信息指向外键，不像「你少造了个定义」。
    """
    d = ReportDefinition(
        project_id=project_id, name="回收器测试", category="设备类",
        description="", definition_json={}, output_format="pdf",
        max_rows=100, version="0.1.0", status="PUBLISHED",
        shared_with="ALL_USERS", created_by=uuid.uuid4())
    db.add(d)
    await db.flush()
    return d.def_id


@pytest.mark.asyncio
async def test_stale_queued_execution_log_is_reclaimed(db, project_id):
    """僵死的 QUEUED/RUNNING 执行日志必须被标 FAILED，且**不删行**。

    ⚠️ 这是**审计**表：删行等于「谁在什么时候请求过这次执行」从此查不到。
    所以回收器只标状态。

    2026-10-13 之前这里没有回收器：日志行由任务体建，而同日 bug-167 的修复
    把建行提到了**入队时** —— 于是「worker 全挂 ⇒ 行永远停在排队态」
    第一次成为可观测的挂起状态，也第一次需要回收器。
    """
    from sqlalchemy import func, select

    def_id = await _published_def(db, project_id)
    stale_q = _exec_log(db, def_id, status="QUEUED", minutes_ago=STALE_MINUTES + 5)
    stale_r = _exec_log(db, def_id, status="RUNNING", minutes_ago=STALE_MINUTES + 5)
    fresh = _exec_log(db, def_id, status="QUEUED", minutes_ago=0)
    done = _exec_log(db, def_id, status="FINISHED", minutes_ago=STALE_MINUTES + 5)
    await db.flush()

    n = await reclaim_stale_execution_logs(db, older_than_minutes=STALE_MINUTES)
    await db.commit()
    assert n == 2, f"应回收 2 行（僵死的 QUEUED 与 RUNNING 各一），实得 {n}"

    for row, want in ((stale_q, "FAILED"), (stale_r, "FAILED"),
                      (fresh, "QUEUED"), (done, "FINISHED")):
        await db.refresh(row)
        assert row.status == want, f"{row.status=}，期望 {want}"

    assert await db.scalar(
        select(func.count()).select_from(ReportExecutionLog)) == 4, \
        "回收器删了行 —— 这是审计表，删了「谁请求过这次执行」就查不到了"


@pytest.mark.asyncio
async def test_reclaiming_writes_an_audit_row(db, project_id):
    """回收要写审计 —— 否则「为什么这行变成 FAILED」查不到。

    与 `reclaim_stale_tasks`（report_files 那侧）同一个理由：状态是给人看的，
    没有来源就只能猜。
    """
    def_id = await _published_def(db, project_id)
    _exec_log(db, def_id, status="QUEUED", minutes_ago=STALE_MINUTES + 5)
    await db.flush()

    await reclaim_stale_execution_logs(db, older_than_minutes=STALE_MINUTES)
    await db.commit()

    from sqlalchemy import func, select

    n = await db.scalar(select(func.count()).select_from(AuditLog).where(
        AuditLog.action == AuditAction.REPORT_FAILED.value))
    assert n >= 1, "回收没写 REPORT_FAILED 审计"


@pytest.mark.asyncio
async def test_fresh_execution_log_is_never_reclaimed(db, project_id):
    """反向断言：只回收「够老且未终结」的行。

    单独列一条是因为「该杀的没杀」和「不该杀的杀了」是两种缺陷，
    而前者（上面那条）已经盖住了阈值逻辑，后者才是这个判据的职责。
    """
    def_id = await _published_def(db, project_id)
    row = _exec_log(db, def_id, status="QUEUED", minutes_ago=STALE_MINUTES - 5)
    await db.flush()

    assert await reclaim_stale_execution_logs(
        db, older_than_minutes=STALE_MINUTES) == 0
    await db.refresh(row)
    assert row.status == "QUEUED"


@pytest.mark.asyncio
async def test_status_is_not_failed_until_the_last_attempt(db, project_id, monkeypatch):
    from app.workers.worker import MAX_TRIES

    """失败一次、重试成功 ⇒ 最终状态必须是 **SUCCEEDED**，不是 FAILED。

    ⚠️ 任务原先在**每次**失败时就把行标成 FAILED。而 ARQ 会重试
    （`WorkerSettings.max_tries=3`），所以「第一次失败、第二次成功」这一条
    路 —— 用户看到的结局是「失败」，而文件其实生成了、就在库里躺着。

    这个错是「用户裁决『每次失败都写』」被**过度套用**的结果：
    那条裁决针对的是**审计**（每次失败都要留痕，可查「第 2 次为什么失败」），
    不是**终态**。终态描述的是「还会不会再来一次」，两者是不同的语义。

    ⚠️ `test_retry_after_failure_reuses_same_row` 盖不住这条：它的第二次调用
    也失败了（`flaky` 返回 None → `_finalize` 抛 AttributeError），
    所以「失败之后又成功」这条路从来没被跑过。
    """
    from sqlalchemy import select

    from app.models.report import ReportFile
    from app.services.report import report_service
    from tests.fixtures.report.seed import make_report_seed

    await make_report_seed(db, project_id, "EQUIPMENT_LIST")

    real_generate = report_service.generate
    calls = {"n": 0}

    async def flaky(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("第一次失败（会被 ARQ 重试）")
        return await real_generate(*a, **k)

    monkeypatch.setattr(report_service, "generate", flaky)

    with pytest.raises(RuntimeError):
        await generate_report_task(
            _job_ctx(db, job_try=1), report_type="EQUIPMENT_LIST",
            project_id=str(project_id), record_ids=[], output_format="pdf",
            style_json={}, ctx_vars=CTX_VARS)
    await db.commit()
    row = (await db.execute(select(ReportFile))).scalar_one()
    assert row.status != "FAILED", (
        f"第 1 次尝试就标了 FAILED：{row.status} —— 而 ARQ 还会重试 "
        f"（max_tries={MAX_TRIES}），用户此刻看到的是假的终态")

    file_id = await generate_report_task(
        _job_ctx(db, job_try=2), report_type="EQUIPMENT_LIST",
        project_id=str(project_id), record_ids=[], output_format="pdf",
        style_json={}, ctx_vars=CTX_VARS)
    await db.commit()
    row = (await db.execute(select(ReportFile))).scalar_one()
    assert str(row.report_file_id) == file_id
    assert row.status == "SUCCEEDED", (
        f"重试成功后状态是 {row.status} —— 重试链会永远带着一个假的失败结局，"
        "而文件其实已经生成")


@pytest.mark.asyncio
async def test_last_attempt_marks_the_row_failed(db, project_id, monkeypatch):
    from app.workers.worker import MAX_TRIES

    """重试耗尽 ⇒ 这次是真的 FAILED。

    与上一条成对：中间的尝试**不能**标 FAILED（ARQ 还会来），
    最后一次**必须**标 —— 否则行永远停在 PENDING，前端无限轮询，
    而真相是「已经重试 3 次都失败了」。
    """
    from sqlalchemy import select

    from app.models.report import ReportFile
    from app.services.report import report_service

    async def always_fail(*a, **k):
        raise RuntimeError("一直失败")

    monkeypatch.setattr(report_service, "generate", always_fail)

    with pytest.raises(RuntimeError):
        await generate_report_task(
            _job_ctx(db, job_try=MAX_TRIES), report_type="EQUIPMENT_LIST",
            project_id=str(project_id), record_ids=[], output_format="pdf",
            style_json={}, ctx_vars=CTX_VARS)
    await db.commit()

    row = (await db.execute(select(ReportFile))).scalar_one()
    assert row.status == "FAILED", (
        f"最后一次尝试后状态是 {row.status} —— 没有终态，前端会转圈到超时")
    assert row.error_message and "一直失败" in row.error_message


@pytest.mark.asyncio
async def test_failure_asks_arq_to_retry_instead_of_just_dying(db, project_id, monkeypatch):
    """⚠️ **ARQ 0.28 不会因为普通异常重试** —— 这是本条存在的全部理由。

    `arq/worker.py:612-637` 的分支只认三种异常：
    `Retry`（带 defer 退避）、`asyncio.CancelledError`、`RetryJob`。
    其余一律走 `else: failed, finish = True` —— **当场判死，不重试**。

    所以 `WorkerSettings.max_tries = 3` 本身**什么也没保证**：一个普通的
    `PcsError` 只会跑一次。SPEC P8 §a7 要求「失败重试（max_tries=3）」，
    要成立就必须由**任务体**在还有次数时抛 `Retry`。

    2026-10-13 真跑 Redis 时实测到的症状：任务失败 1 次、审计写了 1 条、
    retry 计数器停在 0、`report_files` 永远停在 PENDING ——
    前端无限轮询，而真相是「根本没有第 2 次」。

    对称的要求：最后一次必须抛**原始异常**，否则 ARQ 会再排一次，
    于是「重试用完了」这件事永远传不出去。
    """
    from arq import Retry

    from app.services.report import report_service
    from app.workers.worker import MAX_TRIES

    async def boom(*a, **k):
        raise RuntimeError("一直失败")

    monkeypatch.setattr(report_service, "generate", boom)

    with pytest.raises(Retry):
        await generate_report_task(
            _job_ctx(db, job_try=1), report_type="EQUIPMENT_LIST",
            project_id=str(project_id), record_ids=[], output_format="pdf",
            style_json={}, ctx_vars=CTX_VARS)

    with pytest.raises(RuntimeError):
        await generate_report_task(
            _job_ctx(db, job_try=MAX_TRIES), report_type="EQUIPMENT_LIST",
            project_id=str(project_id), record_ids=[], output_format="pdf",
            style_json={}, ctx_vars=CTX_VARS)
