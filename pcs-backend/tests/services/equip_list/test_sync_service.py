"""S1-4 EQUIP_LIST 同步服务测试（P7-Sprint 1 T2）。

覆盖：
1. happy path — PUMP CHECKED → EquipmentList created with SourceService='pump_service'
2. 二次调用同 (project_id, tag_number) → 不重复 INSERT，更新 sign_status + equipment_status="E"
3. 不支持的 source_module → 抛 UnsupportedSourceModuleError
4. (gate pcs_test) 并发 sync_from_source 同 (project_id, tag_number) → 一成功一等待

设计：
- 用 conftest.py:118 db_session (AsyncSession, SQLite in-memory) 驱动前 3 例
- 第 4 例用 module-level ``pytest.mark.skipif`` gate pcs_test (PG)，SQLite 无
  pg_advisory_xact_lock → 跳过（advisory_lock.py 内部 try/except OperationalError no-op）
- EquipmentList composite FK (equipment_type_project_id, type_code) → equipment_type_codes；
  SQLite 默认 FK OFF 故 INSERT 不被检查；不需预建 EquipmentTypeCode 但仍建以匹配生产路径
"""

from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.calc import PumpResult
from app.models.equipment import EquipmentList, EquipmentTypeCode
from app.models.enums import RecordSignStatus9, to_value
from app.models.project import Project, Stream, Workspace
from app.services.equip_list.source_resolver import UnsupportedSourceModuleError
from app.services.equip_list.sync_service import sync_from_source
from app.services.equipment_type_code_service import EquipmentTypeCodeService


# Module-level gate: 并发测试需 pcs_test PG 库（SQLite 无 pg_advisory_xact_lock）
_RUNS_AGAINST_PCS_TEST = os.environ.get("DATABASE_URL", "").endswith("pcs_test")
skip_unless_pcs_test = pytest.mark.skipif(
    not _RUNS_AGAINST_PCS_TEST,
    reason="concurrent advisory lock test requires pcs_test (Postgres); SQLite 无 pg_advisory_xact_lock",
)


# M1 fix: 删除本地 _sign_status_value helper，统一用 app.models.enums.to_value
# (跨 DB enum/str dual-format 兼容)
_sign_status_value = to_value


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def pws_setup(db_session: AsyncSession) -> AsyncIterator[dict]:
    """最小 Project + Workspace + Stream + EquipmentTypeCode('P') + PumpResult(CHECKED)。"""
    project_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    stream_id = uuid.uuid4()
    pump_id = uuid.uuid4()

    ws = Workspace(
        workspace_id=workspace_id,
        workspace_type="FORMAL",
        project_id=project_id,
        name="t",
    )
    proj = Project(
        project_id=project_id,
        project_no=f"P-{project_id.hex[:8]}",
        project_name="t",
        owner_company="t",
        location="t",
        project_type="test",
        design_phase="BASIC",
        unit_system="SI",
        status="ACTIVE",
        workspace_id=workspace_id,
    )
    stream = Stream(
        stream_id=stream_id,
        project_id=project_id,
        workspace_id=workspace_id,
        stream_name=f"S-{stream_id.hex[:8]}",
        case_type="NORMAL",
        data_mode="CHEMICAL",
        source_type="MANUAL_ENTRY",
        approval_depth=1,
        press=200_000.0,
        temp=298.15,
        composition_json={"H2O": 1.0},
    )
    pump = PumpResult(
        pump_id=pump_id,
        project_id=project_id,
        workspace_id=workspace_id,
        tag_number="P-1001",
        sign_status=RecordSignStatus9.CHECKED,
        approval_depth=2,
        basic_info_json={},
        fluid_properties_json={},
        flow_rates_json={},
        suction_calculation_json={},
        discharge_calculation_json={},
        differential_pressure_json={},
        design_pressure_json={},
        power_consumption_json={},
    )
    type_code = EquipmentTypeCode(
        project_id=project_id,
        type_code="P",
        equipment_description="Pump",
        category="ROTATING",
    )
    db_session.add_all([ws, proj, stream, type_code, pump])
    await db_session.commit()
    yield {
        "project_id": project_id,
        "workspace_id": workspace_id,
        "stream_id": stream_id,
        "pump_id": pump_id,
        "tag_number": "P-1001",
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sync_from_source_creates_equipment_list(db_session, pws_setup):
    """happy path: PUMP CHECKED → EquipmentList 创建 + SourceService='pump_service'。"""
    pws = pws_setup
    result = await sync_from_source(
        source_module="PUMP",
        source_service="pump_service",
        source_record_id=pws["pump_id"],
        db=db_session,
    )
    assert isinstance(result, EquipmentList)
    assert result.source_module == "PUMP"
    assert result.source_service == "pump_service"
    assert result.source_record_id == pws["pump_id"]
    assert result.tag_number == "P-1001"
    assert _sign_status_value(result.sign_status) == "CHECKED"
    assert result.equipment_status == "N"  # New（首次创建）

    # DB roundtrip
    found = (
        await db_session.execute(
            select(EquipmentList).where(EquipmentList.equipment_id == result.equipment_id)
        )
    ).scalar_one()
    assert found.source_service == "pump_service"


@pytest.mark.asyncio
async def test_sync_from_source_updates_existing_equipment_list(db_session, pws_setup):
    """二次调用同 (project_id, tag_number) → 不重复 INSERT + equipment_status='E' 联动。"""
    pws = pws_setup
    r1 = await sync_from_source(
        source_module="PUMP",
        source_service="pump_service",
        source_record_id=pws["pump_id"],
        db=db_session,
    )
    r2 = await sync_from_source(
        source_module="PUMP",
        source_service="pump_service",
        source_record_id=pws["pump_id"],
        db=db_session,
    )
    assert r1.equipment_id == r2.equipment_id  # 同一条
    assert r2.equipment_status == "E"  # Existing（联动）

    # DB 中仅一条 EquipmentList 记录
    rows = (
        await db_session.execute(
            select(EquipmentList).where(
                EquipmentList.project_id == pws["project_id"],
                EquipmentList.tag_number == "P-1001",
            )
        )
    ).scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_sync_from_source_uses_company_level_type_code_when_no_project_override(
    db_session,
):
    """Final-review I1 fix: 无项目级 type_code override 时 → equipment_type_project_id=None（公司级 fallback）。

    T1.5 seed 仅 seed 公司级（project_id NULL）codes；sync_from_source 在无项目级
    override 时必须 fallback 到公司级 FK target，否则生产 PG 首次 sync 触发 FK violation。
    """
    project_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    pump_id = uuid.uuid4()

    # 仅 seed 公司级（不建项目级 override）
    await EquipmentTypeCodeService.seed_defaults(db_session)

    # Project + Workspace + PumpResult
    ws = Workspace(
        workspace_id=workspace_id,
        workspace_type="FORMAL",
        project_id=project_id,
        name="t",
    )
    proj = Project(
        project_id=project_id,
        project_no=f"P-{project_id.hex[:8]}",
        project_name="t",
        owner_company="t",
        location="t",
        project_type="test",
        design_phase="BASIC",
        unit_system="SI",
        status="ACTIVE",
        workspace_id=workspace_id,
    )
    stream = Stream(
        stream_id=uuid.uuid4(),
        project_id=project_id,
        workspace_id=workspace_id,
        stream_name="S-test",
        case_type="NORMAL",
        data_mode="CHEMICAL",
        source_type="MANUAL_ENTRY",
        approval_depth=1,
        press=200_000.0,
        temp=298.15,
        composition_json={"H2O": 1.0},
    )
    pump = PumpResult(
        pump_id=pump_id,
        project_id=project_id,
        workspace_id=workspace_id,
        tag_number="P-2002",
        sign_status=RecordSignStatus9.CHECKED,
        approval_depth=2,
        basic_info_json={},
        fluid_properties_json={},
        flow_rates_json={},
        suction_calculation_json={},
        discharge_calculation_json={},
        differential_pressure_json={},
        design_pressure_json={},
        power_consumption_json={},
    )
    db_session.add_all([ws, proj, stream, pump])
    await db_session.commit()

    result = await sync_from_source(
        source_module="PUMP",
        source_service="pump_service",
        source_record_id=pump_id,
        db=db_session,
    )
    # I1 fix: equipment_type_project_id 应为 None（公司级 fallback）
    assert result.equipment_type_project_id is None
    assert result.type_code == "P"


@pytest.mark.asyncio
async def test_sync_from_source_unsupported_module_raises(db_session):
    """不支持的 source_module 抛 UnsupportedSourceModuleError。"""
    with pytest.raises(UnsupportedSourceModuleError):
        await sync_from_source(
            source_module="UNKNOWN_MODULE",
            source_service="x",
            source_record_id=uuid.uuid4(),
            db=db_session,
        )


@pytest.mark.asyncio
@skip_unless_pcs_test
async def test_sync_from_source_concurrent_same_tag_serializes(db_engine, pws_setup):
    """D2 裁决 2A: 两路并发 sync_from_source 同 (project_id, tag_number) 一成功一等待。

    用 pcs_test (Postgres) 跑：两个并发任务竞争同一 advisory lock key，
    第二个任务在第一个释放锁前阻塞 → 串行执行；最终仅一条 EquipmentList 记录。

    Runtime guard: conftest.py:84 db_engine 用 SQLite in-memory（即使 env
    DATABASE_URL 指向 pcs_test）；SQLite 无 pg_advisory_xact_lock → 跳过。
    """
    if db_engine.dialect.name != "postgresql":
        pytest.skip(
            f"concurrent advisory lock test requires postgresql; "
            f"db_engine dialect = {db_engine.dialect.name}"
        )
    from sqlalchemy.ext.asyncio import async_sessionmaker

    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    pws = pws_setup
    pump_id = pws["pump_id"]

    async def _sync_one() -> str:
        async with factory() as session:
            try:
                await sync_from_source(
                    source_module="PUMP",
                    source_service="pump_service",
                    source_record_id=pump_id,
                    db=session,
                )
                return "ok"
            except Exception as e:  # noqa: BLE001
                return type(e).__name__

    # 起两个并发任务竞争同一 (project_id, tag_number)
    t1, t2 = asyncio.create_task(_sync_one()), asyncio.create_task(_sync_one())
    r1, r2 = await asyncio.gather(t1, t2)
    assert r1 == "ok"
    assert r2 == "ok"  # 都成功（一个创建，一个更新）

    # 仅一条 EquipmentList
    async with factory() as verify_session:
        rows = (
            await verify_session.execute(
                select(EquipmentList).where(
                    EquipmentList.project_id == pws["project_id"],
                    EquipmentList.tag_number == "P-1001",
                )
            )
        ).scalars().all()
        assert len(rows) == 1
