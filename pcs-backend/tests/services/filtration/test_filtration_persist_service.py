"""P6-3 Task 34 FILTRATION filtration_persist_service 测试（SPEC §3.2.7）。

按 SPEC §3.2.7：FiltrationResult 标准 CRUD + sign_status 流。

设计要点：
- 单元测试用 Mock session 隔离（避免外部 DB 耦合）；覆盖 input 校验 /
  status filter / project 隔离语义 / PATCH 锁定 / soft_delete。
- G-07 真库测试走 save_ruth_constant_pressure_result 直接落
  filtration_results（pcs_test；守卫同 test_open_channel_persist_service.
  _ONLY_PCS_TEST）。
- **Do-Not-Repeat**：FiltrationResult（继承 TaggedRecordMixin）:
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
from app.services.filtration import (  # noqa: E402
    FiltrationPersistInputError,
    create_filtration_result_direct,
    get_filtration_result_service,
    list_filtration_results_service,
    save_ergun_result,
    save_ruth_constant_pressure_result,
    save_ruth_constant_rate_result,
    soft_delete_filtration_result_service,
    update_filtration_result_service,
)

# 安全守卫：仅 pcs_test 库允许跑 G-07（防误触 pcs 开发库）。
_ONLY_PCS_TEST = pytest.mark.skipif(
    not get_settings().database_url.rstrip("/").endswith("pcs_test"),
    reason=(
        "G-07 集成测试仅允许 pcs_test 库（防误触 pcs 开发库）；"
        "需 DATABASE_URL=postgresql+psycopg://pcs:pcs_dev@localhost:5432/pcs_test"
    ),
)


# ============================================================================
# Helpers（Mock session + 构造 FiltrationResult-like 行）
# ============================================================================


def _make_filtration_row(
    *,
    project_id: uuid.UUID,
    filter_id: uuid.UUID | None = None,
    tag_number: str = "FIL-001",
    filter_type: str = "RUTH_CONST_PRESSURE",
    sign_status: RecordSignStatus9 = RecordSignStatus9.DRAFT,
    record_hash: str = "",
) -> Any:
    """构造 ``FiltrationResult`` 行-like 对象（Mock）。"""
    row = MagicMock()
    row.filter_id = filter_id or uuid.uuid4()
    row.project_id = project_id
    row.workspace_id = uuid.uuid4()
    row.tag_number = tag_number
    row.filter_type = filter_type
    row.media_type = "SAND"
    row.area = 1.0
    row.cycle_time = 1.0
    row.pressure_drop = 1e5
    row.cake_resistance_alpha = None
    row.specific_resistance_r0 = None
    row.permeability_k = None
    row.porosity_eps = None
    row.filter_velocity = None
    row.sign_status = sign_status
    row.record_hash = record_hash
    row.stale_resolution_path = None
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
    session.get = AsyncMock(return_value=record)
    return session


# ============================================================================
# 1. save_ruth_constant_pressure_result 输入校验
# ============================================================================


@pytest.mark.asyncio
async def test_save_ruth_constant_pressure_validates_tag_number() -> None:
    """空 tag_number → FiltrationPersistInputError。"""
    session = _mock_session()
    with pytest.raises(FiltrationPersistInputError) as exc_info:
        await save_ruth_constant_pressure_result(
            session,
            project_id=uuid.uuid4(),
            workspace_id=uuid.uuid4(),
            tag_number="",
            media_type="SAND",
            area=1.0,
            cycle_time=1.0,
            pressure_drop=1e5,
        )
    assert "tag_number" in str(exc_info.value)


@pytest.mark.asyncio
async def test_save_ruth_constant_pressure_validates_area() -> None:
    """area <= 0 → FiltrationPersistInputError。"""
    session = _mock_session()
    with pytest.raises(FiltrationPersistInputError) as exc_info:
        await save_ruth_constant_pressure_result(
            session,
            project_id=uuid.uuid4(),
            workspace_id=uuid.uuid4(),
            tag_number="FIL-A",
            media_type="SAND",
            area=0.0,
            cycle_time=1.0,
            pressure_drop=1e5,
        )
    assert "area" in str(exc_info.value)


@pytest.mark.asyncio
async def test_save_ruth_constant_pressure_validates_negative_cycle_time() -> None:
    """cycle_time < 0 → FiltrationPersistInputError。"""
    session = _mock_session()
    with pytest.raises(FiltrationPersistInputError) as exc_info:
        await save_ruth_constant_pressure_result(
            session,
            project_id=uuid.uuid4(),
            workspace_id=uuid.uuid4(),
            tag_number="FIL-T",
            media_type="SAND",
            area=1.0,
            cycle_time=-1.0,
            pressure_drop=1e5,
        )
    assert "cycle_time" in str(exc_info.value)


# ============================================================================
# 2. save_ruth_constant_rate_result 输入校验
# ============================================================================


@pytest.mark.asyncio
async def test_save_ruth_constant_rate_validates_tag_number() -> None:
    """空 tag_number → FiltrationPersistInputError。"""
    session = _mock_session()
    with pytest.raises(FiltrationPersistInputError):
        await save_ruth_constant_rate_result(
            session,
            project_id=uuid.uuid4(),
            workspace_id=uuid.uuid4(),
            tag_number="",
            media_type="ANTHRACITE",
            area=1.0,
            cycle_time=1.0,
            pressure_drop=1e5,
        )


@pytest.mark.asyncio
async def test_save_ruth_constant_rate_validates_pressure_drop() -> None:
    """pressure_drop <= 0 → FiltrationPersistInputError。"""
    session = _mock_session()
    with pytest.raises(FiltrationPersistInputError) as exc_info:
        await save_ruth_constant_rate_result(
            session,
            project_id=uuid.uuid4(),
            workspace_id=uuid.uuid4(),
            tag_number="FIL-R",
            media_type="ANTHRACITE",
            area=1.0,
            cycle_time=1.0,
            pressure_drop=0.0,
        )
    assert "pressure_drop" in str(exc_info.value)


# ============================================================================
# 3. save_ergun_result 输入校验（含 porosity_eps 边界）
# ============================================================================


@pytest.mark.asyncio
async def test_save_ergun_validates_tag_number() -> None:
    """空 tag_number → FiltrationPersistInputError。"""
    session = _mock_session()
    with pytest.raises(FiltrationPersistInputError):
        await save_ergun_result(
            session,
            project_id=uuid.uuid4(),
            workspace_id=uuid.uuid4(),
            tag_number="",
            media_type="ERGUN_PACKING",
            area=1.0,
            cycle_time=1.0,
            pressure_drop=1e5,
        )


@pytest.mark.asyncio
async def test_save_ergun_validates_porosity_eps_boundary() -> None:
    """porosity_eps ∈ (0, 1) 严格开区间；0 或 1 → FiltrationPersistInputError。"""
    session = _mock_session()
    with pytest.raises(FiltrationPersistInputError) as exc_info:
        await save_ergun_result(
            session,
            project_id=uuid.uuid4(),
            workspace_id=uuid.uuid4(),
            tag_number="FIL-E",
            media_type="ERGUN_PACKING",
            area=1.0,
            cycle_time=1.0,
            pressure_drop=1e5,
            porosity_eps=0.0,
        )
    assert "porosity_eps" in str(exc_info.value)


# ============================================================================
# 4. list_filtration_results_service：project_id 隔离
# ============================================================================


@pytest.mark.asyncio
async def test_list_filtration_results_service_filters_project() -> None:
    """2 project × 3 row → list(p1)=3 行。"""
    p1 = uuid.uuid4()
    p2 = uuid.uuid4()
    rows_p1 = [_make_filtration_row(project_id=p1) for _ in range(3)]
    rows_p2 = [_make_filtration_row(project_id=p2) for _ in range(3)]

    session = _mock_session(rows=rows_p1)
    r1 = await list_filtration_results_service(
        session, project_id=p1, limit=10
    )
    assert len(r1) == 3
    assert all(row.project_id == p1 for row in r1)
    _ = (p2, rows_p2)


@pytest.mark.asyncio
async def test_list_filtration_results_service_excludes_obsolete_default() -> None:
    """默认 include_obsolete=False → service 走 filter。"""
    session = _mock_session(rows=[])
    await list_filtration_results_service(
        session, project_id=uuid.uuid4()
    )
    assert session.execute.called


@pytest.mark.asyncio
async def test_list_filtration_results_service_passes_skip_limit() -> None:
    """skip / limit 透传。"""
    session = _mock_session(rows=[])
    await list_filtration_results_service(
        session, project_id=uuid.uuid4(), skip=10, limit=50
    )
    assert session.execute.called


# ============================================================================
# 5. get_filtration_result_service
# ============================================================================


@pytest.mark.asyncio
async def test_get_filtration_result_service_found() -> None:
    """记录存在 → 返回 ORM 行。"""
    record = _make_filtration_row(project_id=uuid.uuid4())
    session = _mock_get_session(record=record)
    r = await get_filtration_result_service(
        session, result_id=record.filter_id
    )
    assert r is record


@pytest.mark.asyncio
async def test_get_filtration_result_service_not_found() -> None:
    """记录不存在 → FiltrationPersistInputError (FILTRATION_NOT_FOUND)。"""
    session = _mock_get_session(record=None)
    with pytest.raises(FiltrationPersistInputError) as exc_info:
        await get_filtration_result_service(
            session, result_id=uuid.uuid4()
        )
    assert exc_info.value.code == "FILTRATION_NOT_FOUND"


# ============================================================================
# 6. update_filtration_result_service：白名单 + 锁定态
# ============================================================================


@pytest.mark.asyncio
async def test_update_filtration_result_service_draft_works() -> None:
    """DRAFT 状态 PATCH → 字段更新成功。"""
    project_id = uuid.uuid4()
    record = _make_filtration_row(
        project_id=project_id, sign_status=RecordSignStatus9.DRAFT
    )
    session = _mock_get_session(record=record)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    r = await update_filtration_result_service(
        session,
        result_id=record.filter_id,
        patch={"area": 2.5, "pressure_drop": 2e5},
    )
    assert r is record
    assert r.area == 2.5
    assert r.pressure_drop == 2e5


@pytest.mark.asyncio
async def test_update_filtration_result_service_checked_locked() -> None:
    """CHECKED 状态 PATCH → FiltrationPersistInputError (FILTRATION_LOCKED)。"""
    record = _make_filtration_row(
        project_id=uuid.uuid4(), sign_status=RecordSignStatus9.CHECKED
    )
    session = _mock_get_session(record=record)
    session.commit = AsyncMock()

    with pytest.raises(FiltrationPersistInputError) as exc_info:
        await update_filtration_result_service(
            session,
            result_id=record.filter_id,
            patch={"area": 2.0},
        )
    assert exc_info.value.code == "FILTRATION_LOCKED"
    assert not session.commit.called


@pytest.mark.asyncio
async def test_update_filtration_result_service_invalid_fields() -> None:
    """非法字段 → FiltrationPersistInputError (FILTRATION_INVALID_FIELDS)。"""
    record = _make_filtration_row(
        project_id=uuid.uuid4(), sign_status=RecordSignStatus9.DRAFT
    )
    session = _mock_get_session(record=record)
    with pytest.raises(FiltrationPersistInputError) as exc_info:
        await update_filtration_result_service(
            session,
            result_id=record.filter_id,
            patch={"unknown_field": 1.0},
        )
    assert exc_info.value.code == "FILTRATION_INVALID_FIELDS"


@pytest.mark.asyncio
async def test_update_filtration_result_service_not_found() -> None:
    """记录不存在 → FiltrationPersistInputError (FILTRATION_NOT_FOUND)。"""
    session = _mock_get_session(record=None)
    with pytest.raises(FiltrationPersistInputError) as exc_info:
        await update_filtration_result_service(
            session,
            result_id=uuid.uuid4(),
            patch={"area": 1.0},
        )
    assert exc_info.value.code == "FILTRATION_NOT_FOUND"


# ============================================================================
# 7. soft_delete_filtration_result_service
# ============================================================================


@pytest.mark.asyncio
async def test_soft_delete_filtration_result_service_sets_obsolete() -> None:
    """DELETE → sign_status=OBSOLETE + tag_number 加 __OBSOLETE_<ts> 后缀。"""
    record = _make_filtration_row(
        project_id=uuid.uuid4(),
        sign_status=RecordSignStatus9.DRAFT,
        tag_number="FIL-DEL-001",
    )
    session = _mock_get_session(record=record)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    r = await soft_delete_filtration_result_service(
        session, result_id=record.filter_id
    )
    assert r is record
    assert r.sign_status == RecordSignStatus9.OBSOLETE
    assert "__OBSOLETE_" in r.tag_number
    assert r.tag_number.startswith("FIL-DEL-001__OBSOLETE_")
    assert session.commit.called


@pytest.mark.asyncio
async def test_soft_delete_filtration_result_service_not_found() -> None:
    """记录不存在 → FiltrationPersistInputError。"""
    session = _mock_get_session(record=None)
    with pytest.raises(FiltrationPersistInputError) as exc_info:
        await soft_delete_filtration_result_service(
            session, result_id=uuid.uuid4()
        )
    assert exc_info.value.code == "FILTRATION_NOT_FOUND"


# ============================================================================
# 8. create_filtration_result_direct：白名单 + tag_number 校验
# ============================================================================


@pytest.mark.asyncio
async def test_create_filtration_result_direct_validates_tag_number() -> None:
    """空 tag_number → FiltrationPersistInputError。"""
    session = _mock_session()
    with pytest.raises(FiltrationPersistInputError):
        await create_filtration_result_direct(
            session,
            project_id=uuid.uuid4(),
            workspace_id=uuid.uuid4(),
            tag_number="",
            filter_type="RUTH_CONST_PRESSURE",
            media_type="SAND",
            area=1.0,
            cycle_time=1.0,
            pressure_drop=1e5,
        )


@pytest.mark.asyncio
async def test_create_filtration_result_direct_invalid_fields() -> None:
    """非法字段 → FiltrationPersistInputError (FILTRATION_INVALID_FIELDS)。"""
    session = _mock_session()
    with pytest.raises(FiltrationPersistInputError) as exc_info:
        await create_filtration_result_direct(
            session,
            project_id=uuid.uuid4(),
            workspace_id=uuid.uuid4(),
            tag_number="FIL-DIRECT",
            unknown_field=1.0,
        )
    assert exc_info.value.code == "FILTRATION_INVALID_FIELDS"


# ============================================================================
# G-07 真库测试：save → list → get → soft_delete → list filter 全链路
# ============================================================================


@_ONLY_PCS_TEST
@pytest.mark.asyncio
async def test_save_filtration_result_g07_real_pcs_test() -> None:
    """G-07：真 pcs_test 库 + save_ruth_constant_pressure_result 端到端 +
    record_hash 已写。

    构造：
    - 1 个 workspace + 1 个 project（FK 必填）
    - save_ruth_constant_pressure_result → 真实 ORM 落 filtration_results
    - get_filtration_result_service 验证 round-trip 字段
    - list_filtration_results_service 验证默认 filter（DRAFT 命中）
    - soft_delete_filtration_result_service → sign_status=OBSOLETE
    - 再 list 不命中（OBSOLETE 被过滤）

    期望：
    - record_hash 已写（finalize_calc_record，16 hex）
    - 业务字段 round-trip 一致
    - soft_delete → sign_status=OBSOLETE + tag_number 加 __OBSOLETE_ 后缀
    """
    from sqlalchemy import delete, select

    from app.db.session import get_async_session_factory
    from app.models.calc import FiltrationResult
    from app.models.enums import WorkspaceType
    from app.models.project import Project, Workspace

    await dispose_engines_async()

    project_id = uuid.uuid4()
    workspace_id = uuid.uuid4()

    factory = get_async_session_factory()
    async with factory() as session:
        # 1. 清表
        await session.execute(
            delete(FiltrationResult).where(
                FiltrationResult.project_id == project_id
            )
        )
        # 2. 建 workspace + project（FK 必填）
        workspace = Workspace(
            workspace_id=workspace_id,
            workspace_type=WorkspaceType.FORMAL.value,
            name="filtration-persist-test-workspace",
        )
        project = Project(
            project_id=project_id,
            workspace_id=workspace_id,
            project_no=f"FIL-P34-{uuid.uuid4().hex[:8]}",
            project_name="Filtration P34 G-07 Test",
            owner_company="test",
            location="test",
            project_type="test",
            design_phase="BASIC",
            unit_system="SI",
        )
        session.add_all([workspace, project])
        await session.commit()

    # 3. save_ruth_constant_pressure_result
    async with factory() as session:
        record = await save_ruth_constant_pressure_result(
            session,
            project_id=project_id,
            workspace_id=workspace_id,
            tag_number="FIL-P34-001",
            media_type="SAND",
            area=1.0,
            cycle_time=1.0,
            pressure_drop=1e5,
            cake_resistance_alpha=1e10,
            specific_resistance_r0=1e10,
            filter_velocity=1e-3,
        )
        record_id = record.filter_id
        record_hash_1 = record.record_hash
        assert record_hash_1 and len(record_hash_1) == 16, (
            f"record_hash 应为 16 hex，实际={record_hash_1!r}"
        )

    # 4. get_filtration_result_service round-trip
    async with factory() as session:
        r = await get_filtration_result_service(
            session, result_id=record_id
        )
        assert r is not None
        assert r.tag_number == "FIL-P34-001"
        assert r.filter_type == "RUTH_CONST_PRESSURE"
        assert r.media_type == "SAND"
        assert r.area == pytest.approx(1.0)
        assert r.cycle_time == pytest.approx(1.0)
        assert r.pressure_drop == pytest.approx(1e5)
        assert r.cake_resistance_alpha == pytest.approx(1e10)
        assert r.specific_resistance_r0 == pytest.approx(1e10)
        assert r.record_hash and len(r.record_hash) == 16

    # 5. list 默认 filter（DRAFT 应命中）
    async with factory() as session:
        rows = await list_filtration_results_service(
            session, project_id=project_id
        )
        assert any(r2.filter_id == record_id for r2 in rows), (
            "save 后 list 应命中"
        )

    # 6. soft_delete
    async with factory() as session:
        deleted = await soft_delete_filtration_result_service(
            session, result_id=record_id
        )
        assert deleted is not None
        assert deleted.sign_status == RecordSignStatus9.OBSOLETE

    # 7. 验证 stale_resolution_path 与 tag_number 后缀
    async with factory() as session:
        stmt = select(FiltrationResult).where(
            FiltrationResult.filter_id == record_id
        )
        result = (await session.execute(stmt)).scalars().first()
        assert result is not None
        assert result.sign_status == RecordSignStatus9.OBSOLETE
        assert "__OBSOLETE_" in result.tag_number

    # 8. list 默认 filter 不含 OBSOLETE → 软删后不再命中
    async with factory() as session:
        rows = await list_filtration_results_service(
            session, project_id=project_id
        )
        assert not any(r2.filter_id == record_id for r2 in rows), (
            "软删后默认 list 不应命中（被 OBSOLETE 过滤）"
        )

    # 9. 清表（GA 收尾）
    async with factory() as session:
        await session.execute(
            delete(FiltrationResult).where(
                FiltrationResult.project_id == project_id
            )
        )
        await session.commit()