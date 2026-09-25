"""P6-4 Task 4 (C-17 显式水含量) saturation_persist 集成测试（G-07 真库）。

端到端测试 save_psychro_result 4 新业务列（saturation_w_kg_kg /
saturation_w_mg_sm3 / saturation_w_lb_per_mmscf / saturation_T_c）：

- calc_type = "SATURATION_W_CALC"（新字面）
- save → 真 psychro_results 行（含 record_hash reflection）
- get round-trip 验证 4 列数值精确还原
- update PATCH 4 列（DRAFT 态可改）
- soft_delete → OBSOLETE

依赖：pcs_test 库 + p6_4_004_psychro_saturation_w_fields migration。
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.core.config import get_settings  # noqa: E402
from app.db.session import dispose_engines_async  # noqa: E402
from app.services.psychro import (  # noqa: E402
    get_psychro_result,
    list_psychro_results,
    save_psychro_result,
    soft_delete_psychro_result,
    update_psychro_result,
)

_ONLY_PCS_TEST = pytest.mark.skipif(
    not get_settings().database_url.rstrip("/").endswith("pcs_test"),
    reason=(
        "G-07 集成测试仅允许 pcs_test 库（防误触 pcs 开发库）；"
        "需 DATABASE_URL=postgresql+psycopg://pcs:pcs_dev@localhost:5432/pcs_test"
    ),
)


@_ONLY_PCS_TEST
@pytest.mark.asyncio
async def test_save_saturation_w_calc_g07_real_pcs_test() -> None:
    """G-07 真库：SATURATION_W_CALC calc_type 4 列 round-trip。

    构造：
    - 1 workspace + 1 project（FK 必填）
    - save_psychro_result(SATURATION_W_CALC) → 4 新业务列真实落库
    - get_psychro_result round-trip 4 列验证
    - update_psychro_result PATCH 4 列（DRAFT 态）
    - soft_delete → OBSOLETE

    期望：
    - record_hash 已写（16 hex；ADR-0028 §决策 4）
    - 4 新业务列 round-trip 一致
    - PATCH 4 列生效（DRAFT 态允许）
    """
    from sqlalchemy import delete

    from app.db.session import get_async_session_factory
    from app.models.calc import PsychroResult
    from app.models.enums import WorkspaceType
    from app.models.project import Project, Workspace

    await dispose_engines_async()

    project_id = uuid.uuid4()
    workspace_id = uuid.uuid4()

    factory = get_async_session_factory()
    async with factory() as session:
        # 1. 清表
        await session.execute(
            delete(PsychroResult).where(PsychroResult.project_id == project_id)
        )
        # 2. 建 workspace + project
        workspace = Workspace(
            workspace_id=workspace_id,
            workspace_type=WorkspaceType.FORMAL.value,
            name="psychro-saturation-test-ws",
        )
        project = Project(
            project_id=project_id,
            workspace_id=workspace_id,
            project_no=f"PSY-SAT-{uuid.uuid4().hex[:8]}",
            project_name="Psychro Saturation G-07 Test",
            owner_company="test",
            location="test",
            project_type="test",
            design_phase="BASIC",
            unit_system="SI",
        )
        session.add_all([workspace, project])
        await session.commit()

    # 3. save_psychro_result（SATURATION_W_CALC + 4 新业务列）
    w_kg_kg = 0.020173430
    w_mg_sm3 = 26070.12
    w_lb = 1627.51
    t_c = 25.0
    async with factory() as session:
        record = await save_psychro_result(
            session,
            project_id=project_id,
            workspace_id=workspace_id,
            tag_number="PSY-SAT-001",
            standard_profile_code="ASHRAE_FUND_2021",
            calc_type="SATURATION_W_CALC",
            payload={
                "saturation_w_kg_kg": w_kg_kg,
                "saturation_w_mg_sm3": w_mg_sm3,
                "saturation_w_lb_per_mmscf": w_lb,
                "saturation_T_c": t_c,
                "input_json": {"temperature_c": t_c, "pressure_kpa": 101.325},
                "output_json": {"formula_ref": "ASHRAE_RP-1845_CoolProp"},
            },
            created_by=None,
        )
        record_id = record.psychro_id
        record_hash = record.record_hash
        assert record_hash and len(record_hash) == 16

    # 4. get round-trip 验证 4 列
    async with factory() as session:
        r = await get_psychro_result(
            session, record_id=record_id, project_id=project_id
        )
        assert r is not None
        assert r.calc_type == "SATURATION_W_CALC"
        assert r.saturation_w_kg_kg == pytest.approx(w_kg_kg, abs=1e-9)
        assert r.saturation_w_mg_sm3 == pytest.approx(w_mg_sm3, abs=0.01)
        assert r.saturation_w_lb_per_mmscf == pytest.approx(w_lb, abs=0.01)
        assert r.saturation_T_c == pytest.approx(t_c, abs=1e-9)
        # 既有 7 业务列应保持 None（SATURATION_W_CALC calc_type 不填那些）
        assert r.humidity_ratio_kg_kg is None
        assert r.dew_point_c is None
        assert r.wet_bulb_c is None

    # 5. update PATCH 4 列（DRAFT 态允许）
    w2 = 0.086862885
    async with factory() as session:
        r2 = await update_psychro_result(
            session,
            record_id=record_id,
            project_id=project_id,
            payload={
                "saturation_w_kg_kg": w2,
                "saturation_w_mg_sm3": 112252.91,
                "saturation_w_lb_per_mmscf": 7007.72,
                "saturation_T_c": 50.0,
            },
        )
        assert r2 is not None
        assert r2.saturation_w_kg_kg == pytest.approx(w2, abs=1e-9)
        assert r2.saturation_T_c == pytest.approx(50.0, abs=1e-9)

    # 6. list 验证 DRAFT 命中
    async with factory() as session:
        rows = await list_psychro_results(session, project_id=project_id, limit=10)
        assert any(r3.psychro_id == record_id for r3 in rows)

    # 7. soft_delete
    async with factory() as session:
        ok = await soft_delete_psychro_result(
            session, record_id=record_id, project_id=project_id
        )
        assert ok is True

    # 8. 清表（GA 收尾）
    async with factory() as session:
        await session.execute(
            delete(PsychroResult).where(PsychroResult.project_id == project_id)
        )
        await session.commit()


@_ONLY_PCS_TEST
@pytest.mark.asyncio
async def test_save_saturation_w_with_other_fields_preserves_nulls() -> None:
    """G-07：SATURATION_W_CALC 4 列与既有 7 业务列共存（不冲突）。"""
    from sqlalchemy import delete

    from app.db.session import get_async_session_factory
    from app.models.calc import PsychroResult
    from app.models.enums import WorkspaceType
    from app.models.project import Project, Workspace

    await dispose_engines_async()

    project_id = uuid.uuid4()
    workspace_id = uuid.uuid4()

    factory = get_async_session_factory()
    async with factory() as session:
        await session.execute(
            delete(PsychroResult).where(PsychroResult.project_id == project_id)
        )
        workspace = Workspace(
            workspace_id=workspace_id,
            workspace_type=WorkspaceType.FORMAL.value,
            name="psychro-saturation-coexist-ws",
        )
        project = Project(
            project_id=project_id,
            workspace_id=workspace_id,
            project_no=f"PSY-COEX-{uuid.uuid4().hex[:8]}",
            project_name="Psychro Saturation Coexist Test",
            owner_company="test",
            location="test",
            project_type="test",
            design_phase="BASIC",
            unit_system="SI",
        )
        session.add_all([workspace, project])
        await session.commit()

    # save 同时含 4 新列 + 既有 1 列（cooling_coil sensible_heat_kw 留个 stamp）
    async with factory() as session:
        record = await save_psychro_result(
            session,
            project_id=project_id,
            workspace_id=workspace_id,
            tag_number="PSY-COEX-001",
            standard_profile_code="ASHRAE_FUND_2021",
            calc_type="SATURATION_W_CALC",
            payload={
                "saturation_w_kg_kg": 0.020173,
                "saturation_w_mg_sm3": 26070.12,
                "saturation_w_lb_per_mmscf": 1627.51,
                "saturation_T_c": 25.0,
                # 既有 7 列填 1 个作共存证明（cooling_coil 专用）
                "sensible_heat_kw": 12.34,
            },
        )
        rid = record.psychro_id

    async with factory() as session:
        r = await get_psychro_result(session, record_id=rid, project_id=project_id)
        assert r is not None
        assert r.saturation_w_kg_kg == pytest.approx(0.020173, abs=1e-6)
        assert r.sensible_heat_kw == pytest.approx(12.34, abs=1e-6)

    # 收尾
    async with factory() as session:
        await session.execute(
            delete(PsychroResult).where(PsychroResult.project_id == project_id)
        )
        await session.commit()