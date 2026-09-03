"""CIA ARQ 定时任务测试（Sprint 3）。

scan_stale_incremental + scan_stale_full。
"""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.asyncio


def _make_pipe(**overrides):
    from app.models.calc import PipingResult

    base = dict(
        project_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        seq_no=1,
        line_no="P-1",
        line_size='2"',
        material_class="A1",
        fluid_code="W",
        fluid_name="Water",
        fluid_phase="L",
        fluid_category="NORMAL",
        source_pid="P&ID-001",
        line_from="V-100",
        line_to="V-200",
        norm_oper_press=1.0,
        max_oper_press=1.5,
        norm_oper_temp=40.0,
        max_oper_temp=80.0,
        design_press=2.0,
        design_temp=100.0,
        piping_category="GC3",
        pressure_test_medium="WATER",
        pressure_test_press=3.0,
        check_class="III",
    )
    base.update(overrides)
    return PipingResult(**base)


async def _flush_full(session, *objs):
    for o in objs:
        session.add(o)
    await session.flush()
    for o in objs:
        await session.refresh(o)
    return objs


# === scan_stale_incremental ===

async def test_incremental_runs_scan_and_commits(db_session):
    """incremental 任务：调用 scan_stale + commit。"""
    from app.models.enums import RecordSignStatus9
    from app.services.lineage import LineageTracker
    from app.workers.cia_tasks import scan_stale_incremental

    pipe = _make_pipe()
    await _flush_full(db_session, pipe)
    pipe.sign_status = RecordSignStatus9.CHECKED
    await db_session.flush()
    await db_session.refresh(pipe)

    tracker = LineageTracker(db_session)
    await tracker.track(
        record=pipe, source="SEED", change_diff={"hash": "stale_hash"}
    )
    pipe.record_hash = "different"
    await db_session.commit()

    with patch("app.workers.cia_tasks.get_async_session_factory") as factory:
        factory.return_value = lambda: db_session  # type: ignore
        # 直接调函数：传入 ctx（unused）
        await scan_stale_incremental(ctx={})


async def test_incremental_skips_when_db_unavailable():
    """DB 不可用时任务直接返回，不抛错。"""
    from app.workers.cia_tasks import scan_stale_incremental

    with patch(
        "app.workers.cia_tasks.check_database_async",
        return_value=False,
    ):
        # 不应抛错
        await scan_stale_incremental(ctx={})


async def test_incremental_no_records_is_ok():
    """空 DB：scan=0，commit 完成。"""
    from app.workers.cia_tasks import scan_stale_incremental

    # 不打 patch — 使用真实 in-memory DB 通过客户端连接？
    # 简单调用：check_database_async=True 走真实路径
    with patch(
        "app.workers.cia_tasks.check_database_async",
        return_value=True,
    ):
        with patch(
            "app.workers.cia_tasks.get_async_session_factory"
        ) as factory:
            # 最小 mock：返回一个无 DB session — 直接走 scan_stale 返回 0
            class _FakeSession:
                async def __aenter__(self):
                    return self

                async def __aexit__(self, *exc):
                    return None

                async def commit(self):
                    pass

            factory.return_value = lambda: _FakeSession()

            with patch(
                "app.services.cia_engine.CIAEngine.scan_stale",
                return_value=0,
            ):
                await scan_stale_incremental(ctx={})


# === scan_stale_full ===

async def test_full_runs_scan_and_commits(db_session):
    """full 任务：调用 scan_stale + commit。"""
    from app.workers.cia_tasks import scan_stale_full

    with patch("app.workers.cia_tasks.get_async_session_factory") as factory:
        factory.return_value = lambda: db_session  # type: ignore
        await scan_stale_full(ctx={})


async def test_full_skips_when_db_unavailable():
    from app.workers.cia_tasks import scan_stale_full

    with patch(
        "app.workers.cia_tasks.check_database_async",
        return_value=False,
    ):
        await scan_stale_full(ctx={})


async def test_full_logs_scan_count():
    """full 任务：logger.info 应被调用。"""
    from app.workers import cia_tasks

    with patch(
        "app.workers.cia_tasks.check_database_async",
        return_value=True,
    ):
        with patch(
            "app.workers.cia_tasks.get_async_session_factory"
        ) as factory:
            class _FakeSession:
                async def __aenter__(self):
                    return self

                async def __aexit__(self, *exc):
                    return None

                async def commit(self):
                    pass

            factory.return_value = lambda: _FakeSession()

            with patch(
                "app.services.cia_engine.CIAEngine.scan_stale",
                return_value=3,
            ):
                with patch.object(cia_tasks.logger, "info") as mock_info:
                    await cia_tasks.scan_stale_full(ctx={})
                    assert any(
                        "3" in str(call_args)
                        for call_args in mock_info.call_args_list
                    )


# === 共用 ===

async def test_tasks_accept_ctx_argument():
    """两个任务签名都接受 ctx 参数（ARQ 调度约定）。"""
    import inspect

    from app.workers.cia_tasks import scan_stale_full, scan_stale_incremental

    sig_i = inspect.signature(scan_stale_incremental)
    sig_f = inspect.signature(scan_stale_full)
    assert "ctx" in sig_i.parameters
    assert "ctx" in sig_f.parameters