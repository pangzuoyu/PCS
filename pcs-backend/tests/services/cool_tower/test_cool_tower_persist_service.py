"""P6-2 Task 25 COOL_TOWER cool_tower_persist_service 测试
（SPEC §3.2.3 P6-FLR-004）。

按 SPEC §3.2.3 P6-FLR-004：CoolingTowerResult 标准 CRUD + sign_status 流。

设计要点：
- 单元测试用 Mock session 隔离（避免外部 DB 耦合）；覆盖 input 校验 /
  status filter / project 隔离语义 / PATCH 锁定 / soft_delete。
- G-07 真库测试走 save_cool_tower_result 直接落 cooling_tower_results
  （pcs_test；守卫同 test_relief_aggregator._ONLY_PCS_TEST）。
- **Do-Not-Repeat**：CoolingTowerResult（继承 TaggedRecordMixin）:
  tag_number NOT NULL + project_id FK + workspace_id；fixture pattern =
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
from app.services.cool_tower import (  # noqa: E402
    CoolTowerPersistInputError,
    get_cool_tower_result,
    list_cool_tower_results,
    save_cool_tower_result,
    soft_delete_cool_tower_result,
    update_cool_tower_result,
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
# Helpers（Mock session + 构造 CoolingTowerResult-like 行）
# ============================================================================


def _make_cool_tower_row(
    *,
    project_id: uuid.UUID,
    cooling_tower_id: uuid.UUID | None = None,
    tag_number: str = "CT-001",
    standard_profile_code: str = "CTI_ATC_105",
    calc_type: str = "MERKEL",
    sign_status: RecordSignStatus9 = RecordSignStatus9.DRAFT,
    record_hash: str = "",
    duty_kw: float | None = None,
    fan_power_kw: float | None = None,
    merkel_integral: float | None = None,
) -> Any:
    """构造 ``CoolingTowerResult`` 行-like 对象（Mock）。"""
    row = MagicMock()
    row.cooling_tower_id = cooling_tower_id or uuid.uuid4()
    row.project_id = project_id
    row.workspace_id = uuid.uuid4()
    row.tag_number = tag_number
    row.standard_profile_code = standard_profile_code
    row.calc_type = calc_type
    row.sign_status = sign_status
    row.record_hash = record_hash
    row.tower_type = None
    row.duty_kw = duty_kw
    row.water_flow_m3h = None
    row.makeup_water_m3h = None
    row.fan_power_kw = fan_power_kw
    row.merkel_integral = merkel_integral
    row.data_sheet_json = None
    row.input_json = None
    row.output_json = None
    row.created_at = MagicMock()
    row.updated_at = MagicMock()
    return row


def _mock_session(rows: list[Any] | None = None) -> MagicMock:
    """构造 mock session，``await session.execute(...).scalars()...`` 返回 rows。"""
    session = MagicMock()
    execute_result = MagicMock()
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = rows or []
    scalars_mock.first.return_value = (rows[0] if rows else None)
    execute_result.scalars.return_value = scalars_mock
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
# 1. save_cool_tower_result 输入校验（无需 DB；纯校验逻辑）
# ============================================================================


@pytest.mark.asyncio
async def test_save_cool_tower_result_validates_tag_number() -> None:
    """空 tag_number → CoolTowerPersistInputError。"""
    session = _mock_session()
    with pytest.raises(CoolTowerPersistInputError) as exc_info:
        await save_cool_tower_result(
            session,
            project_id=uuid.uuid4(),
            workspace_id=uuid.uuid4(),
            tag_number="",
            standard_profile_code="CTI_ATC_105",
            payload={"duty_kw": 1500.0},
        )
    assert "tag_number" in str(exc_info.value)


@pytest.mark.asyncio
async def test_save_cool_tower_result_validates_standard_profile_code() -> None:
    """空 standard_profile_code → CoolTowerPersistInputError。"""
    session = _mock_session()
    with pytest.raises(CoolTowerPersistInputError) as exc_info:
        await save_cool_tower_result(
            session,
            project_id=uuid.uuid4(),
            workspace_id=uuid.uuid4(),
            tag_number="CT-001",
            standard_profile_code="",
            payload={"duty_kw": 1500.0},
        )
    assert "standard_profile_code" in str(exc_info.value)


@pytest.mark.asyncio
async def test_save_cool_tower_result_validates_empty_payload() -> None:
    """空 payload / 全部字段被白名单过滤 → CoolTowerPersistInputError。"""
    session = _mock_session()
    with pytest.raises(CoolTowerPersistInputError):
        await save_cool_tower_result(
            session,
            project_id=uuid.uuid4(),
            workspace_id=uuid.uuid4(),
            tag_number="CT-001",
            standard_profile_code="CTI_ATC_105",
            payload={"unknown_field": 1.0},  # 全部被白名单过滤掉
        )


# ============================================================================
# 2. list_cool_tower_results：project_id 隔离 + sign_status filter
# ============================================================================


@pytest.mark.asyncio
async def test_list_cool_tower_results_filters_project() -> None:
    """2 project × 3 row → list(p1)=3 行（单次调用只返 p1 行）。"""
    p1 = uuid.uuid4()
    p2 = uuid.uuid4()
    rows_p1 = [_make_cool_tower_row(project_id=p1) for _ in range(3)]
    rows_p2 = [_make_cool_tower_row(project_id=p2) for _ in range(3)]

    session = _mock_session(rows=rows_p1)

    r1 = await list_cool_tower_results(session, project_id=p1, limit=10)
    assert len(r1) == 3
    assert all(row.project_id == p1 for row in r1)
    _ = (p2, rows_p2)


@pytest.mark.asyncio
async def test_list_cool_tower_results_filters_sign_status() -> None:
    """默认 sign_status_filter = (DRAFT, CHECKED) → OBSOLETE 被过滤。"""
    session = _mock_session(rows=[])
    await list_cool_tower_results(session, project_id=uuid.uuid4())
    assert session.execute.called


@pytest.mark.asyncio
async def test_list_cool_tower_results_passes_limit_offset() -> None:
    """limit / offset 透传。"""
    session = _mock_session(rows=[])
    await list_cool_tower_results(
        session, project_id=uuid.uuid4(), limit=50, offset=10
    )
    assert session.execute.called


# ============================================================================
# 3. get_cool_tower_result：project_id 隔离
# ============================================================================


@pytest.mark.asyncio
async def test_get_cool_tower_result_with_project_isolation_match() -> None:
    """project_id 匹配 → 返回行。"""
    record = _make_cool_tower_row(project_id=uuid.uuid4())
    session = _mock_get_session(record=record)
    r = await get_cool_tower_result(
        session,
        record_id=record.cooling_tower_id,
        project_id=record.project_id,
    )
    assert r is record


@pytest.mark.asyncio
async def test_get_cool_tower_result_with_project_isolation_mismatch() -> None:
    """project_id 不匹配 → first() 返回 None。"""
    session = _mock_get_session(record=None)
    r = await get_cool_tower_result(
        session,
        record_id=uuid.uuid4(),
        project_id=uuid.uuid4(),  # 不同 project
    )
    assert r is None


# ============================================================================
# 4. update_cool_tower_result：sign_status 锁定（用 Mock 直接 stub 行为）
# ============================================================================


@pytest.mark.asyncio
async def test_update_cool_tower_result_draft_works() -> None:
    """DRAFT 状态 PATCH → 字段更新成功。"""
    project_id = uuid.uuid4()
    record = _make_cool_tower_row(
        project_id=project_id, sign_status=RecordSignStatus9.DRAFT
    )
    session = _mock_get_session(record=record)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    r = await update_cool_tower_result(
        session,
        record_id=record.cooling_tower_id,
        project_id=project_id,
        payload={"duty_kw": 2000.0},
    )
    assert r is record
    assert r.sign_status == RecordSignStatus9.DRAFT


@pytest.mark.asyncio
async def test_update_cool_tower_result_checked_locked() -> None:
    """CHECKED 状态 PATCH → CoolTowerPersistInputError
    code=COOL_TOWER_PERSIST_SIGN_STATUS_LOCKED。"""
    project_id = uuid.uuid4()
    record = _make_cool_tower_row(
        project_id=project_id, sign_status=RecordSignStatus9.CHECKED
    )
    session = _mock_get_session(record=record)
    session.commit = AsyncMock()

    with pytest.raises(CoolTowerPersistInputError) as exc_info:
        await update_cool_tower_result(
            session,
            record_id=record.cooling_tower_id,
            project_id=project_id,
            payload={"duty_kw": 2000.0},
        )
    assert "COOL_TOWER_PERSIST_SIGN_STATUS_LOCKED" in str(exc_info.value.code)
    assert not session.commit.called


@pytest.mark.asyncio
async def test_update_cool_tower_result_record_not_found() -> None:
    """记录不存在 / 隔离不匹配 → None。"""
    session = _mock_get_session(record=None)
    r = await update_cool_tower_result(
        session,
        record_id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        payload={"duty_kw": 2000.0},
    )
    assert r is None


# ============================================================================
# 5. soft_delete_cool_tower_result：sign_status=OBSOLETE +
#    stale_resolution_path
# ============================================================================


@pytest.mark.asyncio
async def test_soft_delete_cool_tower_result_sets_obsolete() -> None:
    """DELETE → sign_status=OBSOLETE +
    stale_resolution_path='COOL_TOWER_RESULT_SOFT_DELETE'。"""
    project_id = uuid.uuid4()
    record = _make_cool_tower_row(
        project_id=project_id, sign_status=RecordSignStatus9.DRAFT
    )
    session = _mock_get_session(record=record)
    session.commit = AsyncMock()

    ok = await soft_delete_cool_tower_result(
        session,
        record_id=record.cooling_tower_id,
        project_id=project_id,
    )
    assert ok is True
    assert record.sign_status == RecordSignStatus9.OBSOLETE
    assert record.stale_resolution_path == "COOL_TOWER_RESULT_SOFT_DELETE"
    assert session.commit.called


@pytest.mark.asyncio
async def test_soft_delete_cool_tower_result_not_found() -> None:
    """记录不存在 → 返回 False。"""
    session = _mock_get_session(record=None)
    ok = await soft_delete_cool_tower_result(
        session,
        record_id=uuid.uuid4(),
        project_id=uuid.uuid4(),
    )
    assert ok is False


# ============================================================================
# G-07 真库测试：save → get → list → soft_delete → list filter 全链路
# ============================================================================


@_ONLY_PCS_TEST
@pytest.mark.asyncio
async def test_save_cool_tower_result_g07_real_pcs_test() -> None:
    """G-07：真 pcs_test 库 + save_cool_tower_result 端到端 +
    record_hash 已写。

    构造：

    - 1 个 workspace + 1 个 project（FK 必填）
    - save_cool_tower_result → 真实 ORM 落 cooling_tower_results
    - get_cool_tower_result 验证 round-trip 字段
    - list_cool_tower_results 验证默认 filter（DRAFT 命中）
    - soft_delete_cool_tower_result → sign_status=OBSOLETE +
      stale_resolution_path 已写
    - 再 list 不命中（OBSOLETE 被过滤）

    期望：

    - record_hash 已写（finalize_calc_record，16 hex）
    - 业务字段 round-trip 一致
    - soft_delete → sign_status=OBSOLETE + stale_resolution_path 已写
    """
    from sqlalchemy import delete, select

    from app.db.session import get_async_session_factory
    from app.models.calc import CoolingTowerResult
    from app.models.enums import WorkspaceType
    from app.models.project import Project, Workspace

    await dispose_engines_async()

    project_id = uuid.uuid4()
    workspace_id = uuid.uuid4()

    factory = get_async_session_factory()
    async with factory() as session:
        # 1. 清表（本测试项目 ID 唯一）
        await session.execute(
            delete(CoolingTowerResult).where(
                CoolingTowerResult.project_id == project_id
            )
        )
        # 2. 建 workspace + project（FK 必填）
        workspace = Workspace(
            workspace_id=workspace_id,
            workspace_type=WorkspaceType.FORMAL.value,
            name="cool-tower-persist-test-workspace",
        )
        project = Project(
            project_id=project_id,
            workspace_id=workspace_id,
            project_no=f"CT-P25-{uuid.uuid4().hex[:8]}",
            project_name="CoolTower P25 G-07 Test",
            owner_company="test",
            location="test",
            project_type="test",
            design_phase="BASIC",
            unit_system="SI",
        )
        session.add_all([workspace, project])
        await session.commit()

    # 3. save_cool_tower_result（独立 session 写入）
    async with factory() as session:
        record = await save_cool_tower_result(
            session,
            project_id=project_id,
            workspace_id=workspace_id,
            tag_number="CT-P25-001",
            standard_profile_code="CTI_ATC_105",
            calc_type="MERKEL",
            payload={
                "duty_kw": 1500.0,
                "water_flow_m3h": 360.0,
                "makeup_water_m3h": 7.2,
                "fan_power_kw": 3.1746,
                "merkel_integral": 0.9811,
                "input_json": {"t1_c": 40, "t2_c": 30},
                "output_json": {"kav_l": 0.9811},
            },
            created_by=None,
        )
        record_id = record.cooling_tower_id
        record_hash_1 = record.record_hash
        assert record_hash_1 and len(record_hash_1) == 16, (
            f"record_hash 应为 16 hex，实际={record_hash_1!r}"
        )

    # 4. get_cool_tower_result 验证 round-trip 字段
    async with factory() as session:
        r = await get_cool_tower_result(
            session,
            record_id=record_id,
            project_id=project_id,
        )
        assert r is not None
        assert r.tag_number == "CT-P25-001"
        assert r.standard_profile_code == "CTI_ATC_105"
        assert r.calc_type == "MERKEL"
        assert r.duty_kw == pytest.approx(1500.0)
        assert r.water_flow_m3h == pytest.approx(360.0)
        assert r.makeup_water_m3h == pytest.approx(7.2)
        assert r.fan_power_kw == pytest.approx(3.1746)
        assert r.merkel_integral == pytest.approx(0.9811)
        assert r.input_json == {"t1_c": 40, "t2_c": 30}
        assert r.output_json == {"kav_l": 0.9811}
        assert r.record_hash and len(r.record_hash) == 16

    # 5. list_cool_tower_results（DRAFT 默认 filter；刚 save 默认 DRAFT 应命中）
    async with factory() as session:
        rows = await list_cool_tower_results(
            session, project_id=project_id, limit=10
        )
        assert any(r2.cooling_tower_id == record_id for r2 in rows), (
            "save 后 list 应命中"
        )

    # 6. soft_delete → sign_status=OBSOLETE + stale_resolution_path
    async with factory() as session:
        ok = await soft_delete_cool_tower_result(
            session,
            record_id=record_id,
            project_id=project_id,
        )
        assert ok is True

    # 7. 验证 stale_resolution_path 与 sign_status 落库
    async with factory() as session:
        stmt = select(CoolingTowerResult).where(
            CoolingTowerResult.cooling_tower_id == record_id
        )
        result = (await session.execute(stmt)).scalars().first()
        assert result is not None
        assert result.sign_status == RecordSignStatus9.OBSOLETE
        assert result.stale_resolution_path == "COOL_TOWER_RESULT_SOFT_DELETE"

    # 8. list 默认 filter 不含 OBSOLETE → 软删后不再命中
    async with factory() as session:
        rows = await list_cool_tower_results(
            session, project_id=project_id, limit=10
        )
        assert not any(r2.cooling_tower_id == record_id for r2 in rows), (
            "软删后默认 list 不应命中（被 OBSOLETE 过滤）"
        )

    # 9. 清表（GA 收尾）
    async with factory() as session:
        await session.execute(
            delete(CoolingTowerResult).where(
                CoolingTowerResult.project_id == project_id
            )
        )
        await session.commit()