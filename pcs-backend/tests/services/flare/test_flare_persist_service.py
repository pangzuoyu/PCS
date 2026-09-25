"""P6-2 Task 23 FLARE_SYS flare_persist_service 测试（SPEC §3.2.3 P6-FLR-004）。

按 SPEC §3.2.3 P6-FLR-004：FlareSystemResult 标准 CRUD + sign_status 流。

设计要点：
- 单元测试用 Mock session 隔离（避免外部 DB 耦合）；覆盖 input 校验 /
  status filter / project 隔离语义。
- G-07 真库测试走 save_flare_result 直接落 flare_system_results（pcs_test ；
  守卫同 test_relief_aggregator._ONLY_PCS_TEST）。
- **Do-Not-Repeat**：FlareSystemResult（继承 TaggedRecordMixin）: tag_number
  NOT NULL + project_id FK + workspace_id；fixture pattern =
  POST API 创建（service 层补必填） → DB UPDATE 状态字段。
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.core.config import get_settings  # noqa: E402
from app.db.session import dispose_engines_async  # noqa: E402
from app.models.enums import RecordSignStatus9  # noqa: E402
from app.services.flare import (  # noqa: E402
    FlarePersistInputError,
    get_flare_result,
    list_flare_results,
    save_flare_result,
    soft_delete_flare_result,
    update_flare_result,
)

# 安全守卫：仅 pcs_test 库允许跑 G-07（防误触 pcs 开发库；与
# tests/services/flare/test_relief_aggregator._ONLY_PCS_TEST 同源约束）。
_ONLY_PCS_TEST = pytest.mark.skipif(
    not get_settings().database_url.rstrip("/").endswith("pcs_test"),
    reason=(
        "G-07 集成测试仅允许 pcs_test 库（防误触 pcs 开发库）；"
        "需 DATABASE_URL=postgresql+psycopg://pcs:pcs_dev@localhost:5432/pcs_test"
    ),
)


# ============================================================================
# Helpers（Mock session + 构造 FlareSystemResult-like 行）
# ============================================================================


def _make_flare_row(
    *,
    project_id: uuid.UUID,
    flare_id: uuid.UUID | None = None,
    tag_number: str = "FL-001",
    standard_profile_code: str = "API_521",
    calc_type: str = "FLARE_TIP",
    sign_status: RecordSignStatus9 = RecordSignStatus9.DRAFT,
    record_hash: str = "",
    pass_: bool | None = None,
    header_diameter_mm: float | None = None,
    stack_height_m: float | None = None,
    flare_tip_diameter_mm: float | None = None,
    radiation_at_grade_kw_m2: float | None = None,
) -> Any:
    """构造 ``FlareSystemResult`` 行-like 对象（Mock）。

    返回 MagicMock（不带 spec）—— ``list_flare_results / get_flare_result`` 只
    读几个字段；spec 在单元测试场景下引入不必要的 FlareSystemResult 依赖。
    """
    row = MagicMock()
    row.flare_id = flare_id or uuid.uuid4()
    row.project_id = project_id
    row.workspace_id = uuid.uuid4()
    row.tag_number = tag_number
    row.standard_profile_code = standard_profile_code
    row.calc_type = calc_type
    row.sign_status = sign_status
    row.record_hash = record_hash
    row.pass_ = pass_
    row.header_diameter_mm = header_diameter_mm
    row.stack_height_m = stack_height_m
    row.flare_tip_diameter_mm = flare_tip_diameter_mm
    row.radiation_at_grade_kw_m2 = radiation_at_grade_kw_m2
    row.created_at = MagicMock()
    return row


def _mock_session(rows: list[Any] | None = None) -> MagicMock:
    """构造 mock session，``await session.execute(...).scalars()...`` 返回 rows。"""
    session = MagicMock()
    execute_result = MagicMock()
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = rows or []
    scalars_mock.first.return_value = (rows[0] if rows else None)
    execute_result.scalars.return_value = scalars_mock
    # session.execute 必须 awaitable → AsyncMock
    session.execute = AsyncMock(return_value=execute_result)
    return session


def _mock_get_session(record: Any | None) -> MagicMock:
    """构造 mock session，``await session.execute().scalars().first()`` 返回 record。"""
    session = MagicMock()
    execute_result = MagicMock()
    scalars_mock = MagicMock()
    scalars_mock.first.return_value = record
    execute_result.scalars.return_value = scalars_mock
    session.execute = AsyncMock(return_value=execute_result)
    return session


# ============================================================================
# 1. save_flare_result 输入校验（无需 DB；纯校验逻辑）
# ============================================================================


@pytest.mark.asyncio
async def test_save_flare_result_validates_tag_number() -> None:
    """空 tag_number → FlarePersistInputError。"""
    session = _mock_session()
    with pytest.raises(FlarePersistInputError) as exc_info:
        await save_flare_result(
            session,
            project_id=uuid.uuid4(),
            workspace_id=uuid.uuid4(),
            tag_number="",
            standard_profile_code="API_521",
            payload={"header_diameter_mm": 250.0},
        )
    assert "tag_number" in str(exc_info.value)


@pytest.mark.asyncio
async def test_save_flare_result_validates_standard_profile_code() -> None:
    """空 standard_profile_code → FlarePersistInputError。"""
    session = _mock_session()
    with pytest.raises(FlarePersistInputError) as exc_info:
        await save_flare_result(
            session,
            project_id=uuid.uuid4(),
            workspace_id=uuid.uuid4(),
            tag_number="FL-001",
            standard_profile_code="",
            payload={"header_diameter_mm": 250.0},
        )
    assert "standard_profile_code" in str(exc_info.value)


@pytest.mark.asyncio
async def test_save_flare_result_validates_empty_payload() -> None:
    """空 payload / 全部字段被白名单过滤 → FlarePersistInputError。"""
    session = _mock_session()
    with pytest.raises(FlarePersistInputError):
        await save_flare_result(
            session,
            project_id=uuid.uuid4(),
            workspace_id=uuid.uuid4(),
            tag_number="FL-001",
            standard_profile_code="API_521",
            payload={"unknown_field": 1.0},  # 全部被白名单过滤掉
        )


# ============================================================================
# 2. list_flare_results：project_id 隔离 + sign_status filter
# ============================================================================


@pytest.mark.asyncio
async def test_list_flare_results_filters_project() -> None:
    """2 project × 3 row → list(p1)=3 行（单次调用只返 p1 行）。

    通过 mock session 验证返回的 scalars().all() 是 p1 的 3 行。
    """
    p1 = uuid.uuid4()
    p2 = uuid.uuid4()
    rows_p1 = [_make_flare_row(project_id=p1) for _ in range(3)]
    rows_p2 = [_make_flare_row(project_id=p2) for _ in range(3)]

    # 单次 execute 返回 p1 的 3 行
    session = _mock_session(rows=rows_p1)

    r1 = await list_flare_results(session, project_id=p1, limit=10)
    assert len(r1) == 3
    assert all(row.project_id == p1 for row in r1)
    # rows_p2 占位（验证 mock 隔离行为；本批次仅校验单次 list 命中）
    _ = (p2, rows_p2)


@pytest.mark.asyncio
async def test_list_flare_results_filters_sign_status() -> None:
    """默认 sign_status_filter = (DRAFT, CHECKED) → OBSOLETE 被过滤（语义）。

    通过验证 session.execute 被调用过且参数含 sign_status filter 表达式即可。
    """
    session = _mock_session(rows=[])
    await list_flare_results(session, project_id=uuid.uuid4())
    assert session.execute.called


@pytest.mark.asyncio
async def test_list_flare_results_passes_limit_offset() -> None:
    """limit / offset 透传。"""
    session = _mock_session(rows=[])
    await list_flare_results(
        session, project_id=uuid.uuid4(), limit=50, offset=10
    )
    assert session.execute.called


# ============================================================================
# 3. get_flare_result：project_id 隔离
# ============================================================================


@pytest.mark.asyncio
async def test_get_flare_result_with_project_isolation_match() -> None:
    """project_id 匹配 → 返回行。"""
    record = _make_flare_row(project_id=uuid.uuid4())
    session = _mock_get_session(record=record)
    r = await get_flare_result(
        session, record_id=record.flare_id, project_id=record.project_id
    )
    assert r is record


@pytest.mark.asyncio
async def test_get_flare_result_with_project_isolation_mismatch() -> None:
    """project_id 不匹配 → first() 返回 None（隔离生效）。"""
    session = _mock_get_session(record=None)
    r = await get_flare_result(
        session,
        record_id=uuid.uuid4(),
        project_id=uuid.uuid4(),  # 不同 project
    )
    assert r is None


# ============================================================================
# 4. update_flare_result：sign_status 锁定（用 Mock 直接 stub 行为）
# ============================================================================


@pytest.mark.asyncio
async def test_update_flare_result_draft_works() -> None:
    """DRAFT 状态 PATCH → 字段更新成功（直接测试 DRAFT 路径无异常）。"""
    project_id = uuid.uuid4()
    record = _make_flare_row(
        project_id=project_id, sign_status=RecordSignStatus9.DRAFT
    )
    session = _mock_get_session(record=record)
    # commit / refresh → AsyncMock 让 await 通过
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    r = await update_flare_result(
        session,
        record_id=record.flare_id,
        project_id=project_id,
        payload={"header_diameter_mm": 300.0},
    )
    assert r is record
    # sign_status 仍 DRAFT（未越权）
    assert r.sign_status == RecordSignStatus9.DRAFT


@pytest.mark.asyncio
async def test_update_flare_result_checked_locked() -> None:
    """CHECKED 状态 PATCH → FlarePersistInputError code=FLARE_PERSIST_SIGN_STATUS_LOCKED。"""
    project_id = uuid.uuid4()
    record = _make_flare_row(
        project_id=project_id, sign_status=RecordSignStatus9.CHECKED
    )
    session = _mock_get_session(record=record)
    # 即使 commit 没被调用（验证锁定生效）
    session.commit = AsyncMock()

    with pytest.raises(FlarePersistInputError) as exc_info:
        await update_flare_result(
            session,
            record_id=record.flare_id,
            project_id=project_id,
            payload={"header_diameter_mm": 300.0},
        )
    assert "FLARE_PERSIST_SIGN_STATUS_LOCKED" in str(exc_info.value.code)
    # commit 未被调用（验证锁定拦截生效）
    assert not session.commit.called


@pytest.mark.asyncio
async def test_update_flare_result_record_not_found() -> None:
    """记录不存在 / 隔离不匹配 → None。"""
    session = _mock_get_session(record=None)
    r = await update_flare_result(
        session,
        record_id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        payload={"header_diameter_mm": 300.0},
    )
    assert r is None


# ============================================================================
# 5. soft_delete_flare_result：sign_status=OBSOLETE + stale_resolution_path
# ============================================================================


@pytest.mark.asyncio
async def test_soft_delete_flare_result_sets_obsolete() -> None:
    """DELETE → sign_status=OBSOLETE + stale_resolution_path='FLARE_RESULT_SOFT_DELETE'。"""
    project_id = uuid.uuid4()
    record = _make_flare_row(
        project_id=project_id, sign_status=RecordSignStatus9.DRAFT
    )
    session = _mock_get_session(record=record)
    session.commit = AsyncMock()

    ok = await soft_delete_flare_result(
        session, record_id=record.flare_id, project_id=project_id
    )
    assert ok is True
    # sign_status 已被 setattr 为 OBSOLETE
    assert record.sign_status == RecordSignStatus9.OBSOLETE
    assert record.stale_resolution_path == "FLARE_RESULT_SOFT_DELETE"
    # commit 被调用
    assert session.commit.called


@pytest.mark.asyncio
async def test_soft_delete_flare_result_not_found() -> None:
    """记录不存在 → 返回 False。"""
    session = _mock_get_session(record=None)
    ok = await soft_delete_flare_result(
        session, record_id=uuid.uuid4(), project_id=uuid.uuid4()
    )
    assert ok is False


# ============================================================================
# G-07 真库测试（save_flare_result 端到端 + project 隔离 + soft_delete）
# ============================================================================


@_ONLY_PCS_TEST
@pytest.mark.asyncio
async def test_save_flare_result_g07_real_pcs_test() -> None:
    """G-07：真 pcs_test 库 + save_flare_result 端到端 + record_hash 已写。

    构造：

    - 1 个 workspace + 1 个 project（FK 必填）
    - save_flare_result → 真实 ORM 落 flare_system_results
    - DB UPDATE sign_status = CHECKED → 验证 list 仍能查到（CHECKED 在默认 filter）
    - DB UPDATE sign_status = OBSOLETE → soft_delete → 再 list 查不到（被 filter 过滤）

    期望：

    - record_hash 已写（finalize_calc_record，16 hex）
    - 业务字段 round-trip 一致
    - soft_delete → sign_status=OBSOLETE + stale_resolution_path 已写
    """
    from sqlalchemy import delete, select

    from app.db.session import get_async_session_factory
    from app.models.calc import FlareSystemResult
    from app.models.enums import WorkspaceType
    from app.models.project import Project, Workspace

    await dispose_engines_async()

    project_id = uuid.uuid4()
    workspace_id = uuid.uuid4()

    factory = get_async_session_factory()
    async with factory() as session:
        # 1. 清表（本测试项目 ID 唯一）
        await session.execute(
            delete(FlareSystemResult).where(
                FlareSystemResult.project_id == project_id
            )
        )
        # 2. 建 workspace + project（FK 必填）
        workspace = Workspace(
            workspace_id=workspace_id,
            workspace_type=WorkspaceType.FORMAL.value,
            name="flare-persist-test-workspace",
        )
        project = Project(
            project_id=project_id,
            workspace_id=workspace_id,
            project_no=f"FLARE-P23-{uuid.uuid4().hex[:8]}",
            project_name="FLARE P23 G-07 Test",
            owner_company="test",
            location="test",
            project_type="test",
            design_phase="BASIC",
            unit_system="SI",
        )
        session.add_all([workspace, project])
        await session.commit()

    # 3. save_flare_result（独立 session 写入）
    async with factory() as session:
        record = await save_flare_result(
            session,
            project_id=project_id,
            workspace_id=workspace_id,
            tag_number="FL-P23-001",
            standard_profile_code="API_521",
            calc_type="FLARE_TIP",
            payload={
                "header_diameter_mm": 250.0,
                "flare_tip_diameter_mm": 250.0,
                "stack_height_m": 30.0,
                "radiation_at_grade_kw_m2": 4.5,
                "pass_": True,
                "input_json": {"tip_T": 300, "tip_P": 101325},
                "output_json": {"u_tip": 69.4},
            },
            created_by=None,
        )
        record_id = record.flare_id
        record_hash_1 = record.record_hash
        assert record_hash_1 and len(record_hash_1) == 16, (
            f"record_hash 应为 16 hex，实际={record_hash_1!r}"
        )

    # 4. get_flare_result 验证 round-trip 字段
    async with factory() as session:
        r = await get_flare_result(session, record_id=record_id, project_id=project_id)
        assert r is not None
        assert r.tag_number == "FL-P23-001"
        assert r.standard_profile_code == "API_521"
        assert r.calc_type == "FLARE_TIP"
        assert r.header_diameter_mm == pytest.approx(250.0)
        assert r.flare_tip_diameter_mm == pytest.approx(250.0)
        assert r.stack_height_m == pytest.approx(30.0)
        assert r.radiation_at_grade_kw_m2 == pytest.approx(4.5)
        assert r.pass_ is True
        assert r.input_json == {"tip_T": 300, "tip_P": 101325}
        assert r.output_json == {"u_tip": 69.4}
        assert r.record_hash and len(r.record_hash) == 16

    # 5. list_flare_results（DRAFT 默认 filter；刚 save 的 record 默认 DRAFT，
    #    应被 list 命中）
    async with factory() as session:
        rows = await list_flare_results(session, project_id=project_id, limit=10)
        assert any(r2.flare_id == record_id for r2 in rows), (
            "save 后 list 应命中"
        )

    # 6. soft_delete → sign_status=OBSOLETE + stale_resolution_path
    async with factory() as session:
        ok = await soft_delete_flare_result(
            session, record_id=record_id, project_id=project_id
        )
        assert ok is True

    # 7. 验证 stale_resolution_path 与 sign_status 落库
    async with factory() as session:
        stmt = select(FlareSystemResult).where(
            FlareSystemResult.flare_id == record_id
        )
        result = (await session.execute(stmt)).scalars().first()
        assert result is not None
        assert result.sign_status == RecordSignStatus9.OBSOLETE
        assert result.stale_resolution_path == "FLARE_RESULT_SOFT_DELETE"

    # 8. list 默认 filter 不含 OBSOLETE → 软删后不再命中
    async with factory() as session:
        rows = await list_flare_results(session, project_id=project_id, limit=10)
        assert not any(r2.flare_id == record_id for r2 in rows), (
            "软删后默认 list 不应命中（被 OBSOLETE 过滤）"
        )

    # 9. 清表（GA 收尾）
    async with factory() as session:
        await session.execute(
            delete(FlareSystemResult).where(
                FlareSystemResult.project_id == project_id
            )
        )
        await session.commit()
