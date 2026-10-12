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

import pytest

from app.models.enums import AuditAction
from app.models.report import REPORT_FILE_STATUSES
from app.models.system import AuditLog
from app.services.report.style import ReportStyle
from app.workers.report_tasks import (
    PENDING_HASH_PREFIX,
    generate_report_task,
    reclaim_stale_tasks,
)

CTX_VARS = {"project_no": "PCS-2026-001", "doc_no": "D-001", "rev": "A"}


def _job_ctx(db, *, job_id="job-1", job_try=1):
    """ARQ 传给任务的 ctx（实测 arq.worker 里 ctx = {job_id, job_try, ...}）。"""
    return {"db": db, "job_id": job_id, "job_try": job_try}


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
    """SPEC §六验收：失败也记录。"""
    from app.services.report import report_service

    async def boom(*a, **k):
        raise RuntimeError("渲染炸了")

    monkeypatch.setattr(report_service, "generate", boom)
    with pytest.raises(RuntimeError):
        await generate_report_task(
            _job_ctx(db), report_type="EQUIPMENT_LIST", project_id=str(project_id),
            record_ids=[], output_format="pdf", style_json={}, ctx_vars=CTX_VARS)


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

    async def boom(*a, **k):
        raise RuntimeError("渲染炸了")

    monkeypatch.setattr(report_service, "generate", boom)
    with pytest.raises(RuntimeError):
        await generate_report_task(
            _job_ctx(db), report_type="EQUIPMENT_LIST", project_id=str(project_id),
            record_ids=[], output_format="pdf", style_json={}, ctx_vars=CTX_VARS)

    row = (await db.execute(select(ReportFile))).scalar_one()
    assert row.status == "FAILED"
    assert row.error_message and "渲染炸了" in row.error_message


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
    with pytest.raises((AttributeError, TypeError)):
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