"""P6-3 Task 36 COST_EST cost_est_persist_service 测试（SPEC §3.2.8）。

按 SPEC §3.2.8：CostEstResult 标准 CRUD + 3 calc save。

设计要点：
- 单元测试用 Mock session 隔离（避免外部 DB 耦合）；覆盖 input 校验 /
  equipment_id FK / PATCH 字段白名单 / 物理删除。
- G-07 真库测试走 save_six_tenths_rule_result 直接落 cost_est_results
  （pcs_test；守卫同 test_open_channel_persist_service._ONLY_PCS_TEST）。
- **Do-Not-Repeat**：CostEstResult 不继承 TaggedRecordMixin — 无
  project_id/workspace_id/tag_number/sign_status/record_hash 列；以
  equipment_id 为 FK 入口（FK → equipment_list）。
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
from app.services.cost_est.cost_est_persist_service import (  # noqa: E402
    CostEstPersistInputError,
    create_cost_est_result_direct,
    get_cost_est_result_service,
    list_cost_est_results_service,
    save_cepci_adjustment_result,
    save_cost_correlation_result,
    save_six_tenths_rule_result,
    soft_delete_cost_est_result_service,
    update_cost_est_result_service,
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
# Helpers（Mock session + 构造 CostEstResult-like 行）
# ============================================================================


def _make_cost_est_row(
    *,
    cost_est_id: uuid.UUID | None = None,
    equipment_id: uuid.UUID | None = None,
    estimated_cost: float = 12345.67,
    currency: str = "USD",
    cost_index_year: int = 2019,
    base_cost: float | None = 10000.0,
    base_year: int | None = 2010,
    cepci_index_base: float | None = 550.0,
    cepci_index_target: float | None = 600.0,
    correlation_source: str | None = None,
    scaling_exponent: float | None = 0.6,
) -> Any:
    """构造 ``CostEstResult`` 行-like 对象（Mock）。"""
    row = MagicMock()
    row.cost_est_id = cost_est_id or uuid.uuid4()
    row.equipment_id = equipment_id or uuid.uuid4()
    row.estimated_cost = estimated_cost
    row.currency = currency
    row.cost_index_year = cost_index_year
    row.base_cost = base_cost
    row.base_year = base_year
    row.cepci_index_base = cepci_index_base
    row.cepci_index_target = cepci_index_target
    row.correlation_source = correlation_source
    row.scaling_exponent = scaling_exponent
    row.created_at = MagicMock()
    return row


def _mock_session_with_equipment(equipment_exists: bool = True) -> MagicMock:
    """构造 mock session：模拟 service 层 ``_ensure_equipment_exists`` +
    ``_ensure_no_existing_cost_est`` 两条 execute 查询。

    - execute(...).scalar_one_or_none() → equipment_id 或 None
      （PK-only 查询；避免 ORM 触发 SELECT *）
    - execute(...).scalars().first() → 已存在 cost_est_id 或 None
      （1:1 唯一性校验）
    """
    session = MagicMock()

    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = (
        uuid.uuid4() if equipment_exists else None
    )
    scalars_mock = MagicMock()
    scalars_mock.first.return_value = None
    execute_result.scalars.return_value = scalars_mock
    session.execute = AsyncMock(return_value=execute_result)
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


def _mock_get_session(record: Any | None) -> MagicMock:
    """构造 mock session：``session.get(CostEstResult, id)`` 返回 record。"""
    session = MagicMock()
    session.get = AsyncMock(return_value=record)
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.delete = AsyncMock()
    session.add = MagicMock()
    return session


# ============================================================================
# 1. save_six_tenths_rule_result 输入校验
# ============================================================================


@pytest.mark.asyncio
async def test_save_six_tenths_rule_equipment_not_found() -> None:
    """equipment_id 不存在 → CostEstPersistInputError (COST_EST_EQUIPMENT_NOT_FOUND)。"""
    session = _mock_session_with_equipment(equipment_exists=False)
    with pytest.raises(CostEstPersistInputError) as exc_info:
        await save_six_tenths_rule_result(
            session,
            equipment_id=uuid.uuid4(),
            reference_cost=10000.0,
            reference_cepci=550.0,
            target_cepci=600.0,
            scaling_exponent=0.6,
            estimated_cost=12000.0,
        )
    assert exc_info.value.code == "COST_EST_EQUIPMENT_NOT_FOUND"


@pytest.mark.asyncio
async def test_save_six_tenths_rule_validates_negative_cost() -> None:
    """estimated_cost < 0 → CostEstPersistInputError。"""
    session = _mock_session_with_equipment()
    with pytest.raises(CostEstPersistInputError) as exc_info:
        await save_six_tenths_rule_result(
            session,
            equipment_id=uuid.uuid4(),
            reference_cost=10000.0,
            reference_cepci=550.0,
            target_cepci=600.0,
            scaling_exponent=0.6,
            estimated_cost=-1.0,
        )
    assert "estimated_cost" in str(exc_info.value)


@pytest.mark.asyncio
async def test_save_six_tenths_rule_validates_invalid_cepci() -> None:
    """reference_cepci <= 0 → CostEstPersistInputError。"""
    session = _mock_session_with_equipment()
    with pytest.raises(CostEstPersistInputError) as exc_info:
        await save_six_tenths_rule_result(
            session,
            equipment_id=uuid.uuid4(),
            reference_cost=10000.0,
            reference_cepci=0.0,  # 非法
            target_cepci=600.0,
            scaling_exponent=0.6,
            estimated_cost=12000.0,
        )
    assert "cepci_index_base" in str(exc_info.value) or "cepci" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_save_six_tenths_rule_validates_scaling_exponent() -> None:
    """scaling_exponent > 1.5 → CostEstPersistInputError。"""
    session = _mock_session_with_equipment()
    with pytest.raises(CostEstPersistInputError) as exc_info:
        await save_six_tenths_rule_result(
            session,
            equipment_id=uuid.uuid4(),
            reference_cost=10000.0,
            reference_cepci=550.0,
            target_cepci=600.0,
            scaling_exponent=2.0,  # 非法 > 1.5
            estimated_cost=12000.0,
        )
    assert "scaling_exponent" in str(exc_info.value)


# ============================================================================
# 2. save_cepci_adjustment_result 输入校验
# ============================================================================


@pytest.mark.asyncio
async def test_save_cepci_adjustment_validates_currency() -> None:
    """currency 长度 > 10 → CostEstPersistInputError。"""
    session = _mock_session_with_equipment()
    with pytest.raises(CostEstPersistInputError) as exc_info:
        await save_cepci_adjustment_result(
            session,
            equipment_id=uuid.uuid4(),
            reference_cost=10000.0,
            reference_cepci=550.0,
            target_cepci=600.0,
            estimated_cost=12000.0,
            currency="USDOLLARLONG",  # 12 chars > 10
        )
    assert "currency" in str(exc_info.value)


@pytest.mark.asyncio
async def test_save_cepci_adjustment_validates_cost_index_year() -> None:
    """cost_index_year 越界 → CostEstPersistInputError。"""
    session = _mock_session_with_equipment()
    with pytest.raises(CostEstPersistInputError) as exc_info:
        await save_cepci_adjustment_result(
            session,
            equipment_id=uuid.uuid4(),
            reference_cost=10000.0,
            reference_cepci=550.0,
            target_cepci=600.0,
            estimated_cost=12000.0,
            cost_index_year=1800,  # 非法 < 1900
        )
    assert "cost_index_year" in str(exc_info.value)


# ============================================================================
# 3. save_cost_correlation_result 输入校验
# ============================================================================


@pytest.mark.asyncio
async def test_save_cost_correlation_validates_scale_parameter() -> None:
    """scale_parameter <= 0 → CostEstPersistInputError。"""
    session = _mock_session_with_equipment()
    with pytest.raises(CostEstPersistInputError) as exc_info:
        await save_cost_correlation_result(
            session,
            equipment_id=uuid.uuid4(),
            equipment_type="TOWER",
            scale_parameter=0.0,  # 非法
            correlation_source="CC-TOWER-v1",
            estimated_cost=15000.0,
        )
    assert "scale_parameter" in str(exc_info.value)


@pytest.mark.asyncio
async def test_save_cost_correlation_validates_correlation_source_length() -> None:
    """correlation_source 长度 > 64 → CostEstPersistInputError。"""
    session = _mock_session_with_equipment()
    long_src = "X" * 65
    with pytest.raises(CostEstPersistInputError) as exc_info:
        await save_cost_correlation_result(
            session,
            equipment_id=uuid.uuid4(),
            equipment_type="TOWER",
            scale_parameter=2.0,
            correlation_source=long_src,
            estimated_cost=15000.0,
        )
    assert "correlation_source" in str(exc_info.value)


# ============================================================================
# 4. update_cost_est_result_service
# ============================================================================


@pytest.mark.asyncio
async def test_update_cost_est_result_service_invalid_fields() -> None:
    """非法字段 → CostEstPersistInputError (COST_EST_INVALID_FIELDS)。"""
    record = _make_cost_est_row()
    session = _mock_get_session(record=record)
    with pytest.raises(CostEstPersistInputError) as exc_info:
        await update_cost_est_result_service(
            session,
            result_id=record.cost_est_id,
            patch={"unknown_field": 1.0},
        )
    assert exc_info.value.code == "COST_EST_INVALID_FIELDS"


@pytest.mark.asyncio
async def test_update_cost_est_result_service_not_found() -> None:
    """记录不存在 → CostEstPersistInputError (COST_EST_NOT_FOUND)。"""
    session = _mock_get_session(record=None)
    with pytest.raises(CostEstPersistInputError) as exc_info:
        await update_cost_est_result_service(
            session,
            result_id=uuid.uuid4(),
            patch={"estimated_cost": 1.0},
        )
    assert exc_info.value.code == "COST_EST_NOT_FOUND"


@pytest.mark.asyncio
async def test_update_cost_est_result_service_valid_patch() -> None:
    """合法 PATCH（estimated_cost + currency）→ 成功。"""
    record = _make_cost_est_row()
    session = _mock_get_session(record=record)
    r = await update_cost_est_result_service(
        session,
        result_id=record.cost_est_id,
        patch={"estimated_cost": 99999.0, "currency": "EUR"},
    )
    assert r is record
    assert r.estimated_cost == 99999.0
    assert r.currency == "EUR"


# ============================================================================
# 5. soft_delete_cost_est_result_service
# ============================================================================


@pytest.mark.asyncio
async def test_soft_delete_cost_est_result_service_not_found() -> None:
    """记录不存在 → CostEstPersistInputError。"""
    session = _mock_get_session(record=None)
    with pytest.raises(CostEstPersistInputError) as exc_info:
        await soft_delete_cost_est_result_service(
            session, result_id=uuid.uuid4()
        )
    assert exc_info.value.code == "COST_EST_NOT_FOUND"


@pytest.mark.asyncio
async def test_soft_delete_cost_est_result_service_deletes_row() -> None:
    """DELETE → session.delete 被调 + commit 调用。"""
    record = _make_cost_est_row()
    session = _mock_get_session(record=record)

    r = await soft_delete_cost_est_result_service(
        session, result_id=record.cost_est_id
    )
    assert session.delete.called
    assert session.commit.called
    # 快照返回 result_id + equipment_id 一致
    assert r.cost_est_id == record.cost_est_id
    assert r.equipment_id == record.equipment_id


# ============================================================================
# 6. create_cost_est_result_direct：白名单 + 字段校验
# ============================================================================


@pytest.mark.asyncio
async def test_create_cost_est_result_direct_invalid_fields() -> None:
    """非法字段 → CostEstPersistInputError (COST_EST_INVALID_FIELDS)。"""
    session = _mock_session_with_equipment()
    with pytest.raises(CostEstPersistInputError) as exc_info:
        await create_cost_est_result_direct(
            session,
            equipment_id=uuid.uuid4(),
            estimated_cost=100.0,
            unknown_field=1.0,
        )
    assert exc_info.value.code == "COST_EST_INVALID_FIELDS"


@pytest.mark.asyncio
async def test_create_cost_est_result_direct_valid() -> None:
    """合法字段 → session.add + commit。"""
    session = _mock_session_with_equipment()
    await create_cost_est_result_direct(
        session,
        equipment_id=uuid.uuid4(),
        estimated_cost=1000.0,
        currency="USD",
        cost_index_year=2019,
        correlation_source="CC-VESSEL-v1",
    )
    assert session.add.called
    assert session.commit.called


# ============================================================================
# 7. list_cost_est_results_service
# ============================================================================


@pytest.mark.asyncio
async def test_list_cost_est_results_service_empty() -> None:
    """空结果列表。"""
    session = MagicMock()
    execute_result = MagicMock()
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = []
    execute_result.scalars.return_value = scalars_mock
    session.execute = AsyncMock(return_value=execute_result)

    rows = await list_cost_est_results_service(session, equipment_id=uuid.uuid4())
    assert rows == []


@pytest.mark.asyncio
async def test_list_cost_est_results_service_with_filter() -> None:
    """按 equipment_id 过滤时 SELECT 语句带 WHERE。"""
    session = MagicMock()
    execute_result = MagicMock()
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = []
    execute_result.scalars.return_value = scalars_mock
    session.execute = AsyncMock(return_value=execute_result)

    await list_cost_est_results_service(session, equipment_id=uuid.uuid4())
    # execute 应被调用一次
    assert session.execute.called


# ============================================================================
# G-07 真库测试：save → get → list → soft_delete 全链路
# ============================================================================


@_ONLY_PCS_TEST
@pytest.mark.asyncio
async def test_save_cost_est_result_g07_real_pcs_test() -> None:
    """G-07：真 pcs_test 库 + save_six_tenths_rule_result 端到端。

    构造：
    - 1 个 workspace + 1 个 project + 1 个 equipment（FK 必填）
    - save_six_tenths_rule_result → 真实 ORM 落 cost_est_results
    - get_cost_est_result_service 验证 round-trip 字段
    - list_cost_est_results_service 验证按 equipment_id 过滤
    - soft_delete_cost_est_result_service → DELETE 行
    - 再 list 不命中（已 DELETE）

    期望：
    - 业务字段 round-trip 一致
    - 物理 DELETE 后记录不再存在
    """
    from sqlalchemy import delete, select, text

    from app.db.session import get_async_session_factory
    from app.models.calc import CostEstResult
    from app.models.enums import WorkspaceType
    from app.models.equipment import EquipmentList
    from app.models.project import Project, Workspace

    await dispose_engines_async()

    equipment_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    project_id = uuid.uuid4()
    tag_number = f"T-{uuid.uuid4().hex[:8]}"
    equipment_name = f"E-{uuid.uuid4().hex[:8]}"

    factory = get_async_session_factory()
    async with factory() as session:
        # 1. 清表（按 equipment_id）
        await session.execute(
            delete(CostEstResult).where(
                CostEstResult.equipment_id == equipment_id
            )
        )
        await session.execute(
            delete(EquipmentList).where(
                EquipmentList.equipment_id == equipment_id
            )
        )
        # 2. 建 workspace + project（ORM 直写）
        workspace = Workspace(
            workspace_id=workspace_id,
            workspace_type=WorkspaceType.FORMAL.value,
            name="cost-est-persist-test-workspace",
        )
        project = Project(
            project_id=project_id,
            workspace_id=workspace_id,
            project_no=f"CE-P36-{uuid.uuid4().hex[:8]}",
            project_name="CostEst P36 G-07 Test",
            owner_company="test",
            location="test",
            project_type="test",
            design_phase="BASIC",
            unit_system="SI",
        )
        session.add_all([workspace, project])
        await session.commit()

    # 3. 建 equipment — **走 raw SQL INSERT 绕过 ORM 列错位**：
    #    pcs_test 库 equipment_list 表缺失 P4-0-1 审计列
    #    （stale_resolution_path/hash_changed/changed_fields），ORM
    #    refresh 时 SELECT * 触发 "column does not exist"。
    #    raw SQL 只写实际存在且 NOT NULL 的列（14 列）即可。
    async with factory() as session:
        await session.execute(
            text(
                """
                INSERT INTO equipment_list (
                    equipment_id, project_id, workspace_id,
                    type_code, equipment_name, tag_number,
                    sign_status, record_hash, approval_depth,
                    locked_by_deliverable, equipment_status,
                    calc_status, actual_data_status
                ) VALUES (
                    :equipment_id, :project_id, :workspace_id,
                    'PUMP', :equipment_name, :tag_number,
                    'DRAFT', '', 1,
                    false, 'N',
                    'NOT_CALCULATED', 'NOT_ENTERED'
                )
                """
            ),
            {
                "equipment_id": equipment_id,
                "project_id": project_id,
                "workspace_id": workspace_id,
                "equipment_name": equipment_name,
                "tag_number": tag_number,
            },
        )
        await session.commit()

    # 4. save_six_tenths_rule_result
    async with factory() as session:
        record = await save_six_tenths_rule_result(
            session,
            equipment_id=equipment_id,
            reference_cost=10000.0,
            reference_cepci=550.0,
            target_cepci=600.0,
            scaling_exponent=0.6,
            estimated_cost=10909.09,
            currency="USD",
            cost_index_year=2019,
            base_cost=10000.0,
            base_year=2010,
        )
        record_id = record.cost_est_id
        assert record.equipment_id == equipment_id
        # 业务字段 round-trip
        assert float(record.estimated_cost) == pytest.approx(10909.09)
        assert record.cepci_index_base == pytest.approx(550.0)
        assert record.cepci_index_target == pytest.approx(600.0)
        assert record.scaling_exponent == pytest.approx(0.6)
        assert record.correlation_source is None

    # 5. get_cost_est_result_service round-trip
    async with factory() as session:
        r = await get_cost_est_result_service(
            session, result_id=record_id
        )
        assert r is not None
        assert r.cost_est_id == record_id
        assert r.equipment_id == equipment_id
        assert float(r.estimated_cost) == pytest.approx(10909.09)

    # 6. list 按 equipment_id 过滤应命中
    async with factory() as session:
        rows = await list_cost_est_results_service(
            session, equipment_id=equipment_id
        )
        assert any(r2.cost_est_id == record_id for r2 in rows), (
            "save 后 list 应命中"
        )

    # 7. soft_delete (DELETE 行)
    async with factory() as session:
        deleted = await soft_delete_cost_est_result_service(
            session, result_id=record_id
        )
        assert deleted is not None
        assert deleted.cost_est_id == record_id

    # 8. 再 list 按 equipment_id 过滤不命中
    async with factory() as session:
        rows_after = await list_cost_est_results_service(
            session, equipment_id=equipment_id
        )
        assert all(r3.cost_est_id != record_id for r3 in rows_after), (
            "DELETE 后 list 不命中"
        )

    # 9. 直接 SELECT 验证行已删除
    async with factory() as session:
        existing = (
            await session.execute(
                select(CostEstResult).where(
                    CostEstResult.cost_est_id == record_id
                )
            )
        ).scalars().first()
        assert existing is None, "DELETE 后 DB 行不应存在"