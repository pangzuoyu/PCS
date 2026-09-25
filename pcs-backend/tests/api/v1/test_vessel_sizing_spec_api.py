"""P6-4 T2 C-08 两相分离器 sizing API 集成测试（SPEC §3.4.2 V1.2）。

端到端验证（in-memory SQLite + httpx async）：
- POST /api/v1/vessel/calculate + sizing_spec → 201 + VesselResult 6 列填充
- V1.0 兼容：sizing_spec=None 时不写 6 列（保持 nullable）
- calc_partial_volume 复用：result["sizing_spec"]["formula_ref"] 必须含
  T3 几何公式键（head / cylinder / total）+ WS-CA-PR-010 sizing 公式键
- 输入非法（SG 反推不一致）→ 422 TWO_PHASE_SEPARATOR_SIZING_INPUT_ERROR
- 落库：VesselResult.input_json["sizing_spec"] 双轨 + outlet c08_* 摘要
"""
from __future__ import annotations

import uuid
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.calc import VesselResult
from app.models.enums import StreamSignStatus
from app.models.project import Project, Stream, Workspace
from app.schemas.stream import StreamCreate
from app.services.stream_service import StreamService

# ---------------------------------------------------------------------------
# fixtures（与 test_vessel_api.py 一致；不依赖其 import 以避免耦合）
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def make_project(db: AsyncSession):
    """最小 Workspace + Project 工厂。"""

    async def _make() -> Project:
        ws = Workspace(workspace_type="FORMAL", name=f"ws-{uuid.uuid4().hex[:8]}")
        db.add(ws)
        await db.flush()
        proj = Project(
            project_no=f"P-{uuid.uuid4().hex[:8]}",
            project_name="vessel sizing_spec API 测试项目",
            owner_company="测试业主",
            location="测试地点",
            project_type="CHEMICAL",
            design_phase="FEED",
            unit_system="SI",
            workspace_id=ws.workspace_id,
        )
        db.add(proj)
        await db.commit()
        return proj

    return _make


@pytest_asyncio.fixture
async def checked_stream(db: AsyncSession, make_project) -> Stream:
    """Workspace + Project + Stream（LIQUID，CHECKED）。"""
    proj = await make_project()
    sp, _ = await StreamService.create(
        db,
        StreamCreate(
            project_id=proj.project_id,
            workspace_id=proj.workspace_id,
            stream_name="S-V-SPEC-101",
            case_type="NORMAL",
            data_mode="CHEMICAL",
            source_type="MANUAL_ENTRY",
            temp=80.0,
            press=200.0,
            phase="LIQUID",
            mass_flow=1000.0,
            composition_json={"74-98-6": 0.3, "106-97-8": 0.7},
        ),
        actor=uuid.uuid4(),
    )
    sp.sign_status = StreamSignStatus.CHECKED
    await db.commit()
    await db.refresh(sp)
    return sp


@pytest.fixture
def designer_headers() -> dict[str, str]:
    token = create_access_token(subject="test-designer", role="DESIGNER")
    return {"Authorization": f"Bearer {token}"}


def _v1_sizing_body(stream_id: uuid.UUID) -> dict[str, Any]:
    """POST /vessel/calculate V1.0 sizing + hydraulics body。"""
    return dict(
        source_stream_id=str(stream_id),
        sizing={
            "vessel_type": "VERTICAL",
            "rho_L_kg_m3": 850.0,
            "rho_V_kg_m3": 1.2,
            "liquid_flow_m3_s": 0.005,
            "vapor_flow_m3_s": 0.5,
            "residence_time_min": 5.0,
            "K_factor_ms": 0.10,
        },
        hydraulics={
            "D_m": 2.0,
            "L_m": 5.0,
            "h0_m": 1.0,
            "d_orifice_m": 0.05,
            "Cd_orifice": 0.62,
            "Q_in_liquid_m3_s": 0.005,
            "d_overflow_m": 0.1,
            "h_overflow_m": 1.0,
            "Cd_overflow": 0.62,
            "orientation": "vertical",
            "thermal_breathing_factor": 1.0,
        },
    )


def _valid_sizing_spec() -> dict[str, Any]:
    """P6-4 T2 C-08 V1.2 sizing_spec body（HORIZONTAL 单相气液）。"""
    return {
        "vessel_shape": "HORIZONTAL",
        "diameter_m": 2.0,
        "length_m": 6.0,
        "head_type": "HEMISPHERICAL",
        "operating_pressure_kpa": 600.0,
        "operating_temperature_c": 70.0,
        "oil_mass_rate_kg_d": 100000.0,
        "water_mass_rate_kg_d": 0.0,
        "gas_mass_rate_kg_d": 80000.0,
        "oil_density_kg_m3": 850.0,
        "water_density_kg_m3": 1000.0,
        "gas_density_kg_m3": 12.0,
        # SG 严格按反推公式填：ρ/999（水）或 ρ/1.225（气）
        "oil_sg": 850.0 / 999.0,
        "water_sg": 1000.0 / 999.0,
        "gas_sg": 12.0 / 1.225,
        "gas_mw_kg_kmol": 19.5,
        "k_factor": 0.08,
        "nozzle_inlet_momentum_limit_kg_m_s2": 150.0,
        "nozzle_outlet_momentum_limit_kg_m_s2": 80.0,
        "instrument_response_time_s": 60.0,
        "n_vessels": 1,
        "imperial_units": False,
    }


# ============================================================================
# 1) sizing_spec happy path：POST → 201 + VesselResult 6 列填充 + 双轨
# ============================================================================


@pytest.mark.asyncio
async def test_calculate_vessel_with_sizing_spec_happy_path(
    client, checked_stream, designer_headers
):
    """P6-4 T2 C-08 V1.2 happy path：

    POST /api/v1/vessel/calculate + sizing_spec → 201，
    result.sizing_spec 含完整 5 段 sizing 输出。
    """
    body = _v1_sizing_body(checked_stream.stream_id)
    body["sizing_spec"] = _valid_sizing_spec()

    r = await client.post(
        "/api/v1/vessel/calculate",
        json=body,
        headers=designer_headers,
    )
    assert r.status_code == 201, r.text
    resp = r.json()

    # result 含 sizing + hydraulics + sizing_spec 三轨
    assert "sizing_spec" in resp["result"]
    spec = resp["result"]["sizing_spec"]
    assert spec is not None

    # Stage 1~5 关键字段
    assert spec["vmax_m_s"] > 0
    assert spec["csa_min_m2"] > 0
    assert spec["csa_actual_m2"] > 0
    assert spec["nozzle_inlet_min_id_m"] > 0
    assert spec["nozzle_outlet_min_id_m"] > 0
    assert spec["control_height_m"] > 0
    assert spec["control_volume_m3"] > 0
    assert spec["residence_time_s"] > 0


@pytest.mark.asyncio
async def test_calculate_vessel_sizing_spec_in_db_six_columns(
    client, db: AsyncSession, checked_stream, designer_headers
):
    """VesselResult 6 列 sizing 必须填充（vmax / csa_min / csa_actual / nozzle /
    control_height / residence_time）。

    V1.0 兼容路径：sizing_spec=None 时 6 列全 NULL（由 alembic p6_4_002 设为
    nullable Float 满足）。
    """
    body = _v1_sizing_body(checked_stream.stream_id)
    body["sizing_spec"] = _valid_sizing_spec()

    r = await client.post(
        "/api/v1/vessel/calculate",
        json=body,
        headers=designer_headers,
    )
    assert r.status_code == 201
    calc_id = uuid.UUID(r.json()["calc_id"])

    record = await db.get(VesselResult, calc_id)
    assert record is not None
    # 6 列填充
    assert record.vmax_m_s is not None and record.vmax_m_s > 0
    assert record.csa_min_m2 is not None and record.csa_min_m2 > 0
    assert record.csa_actual_m2 is not None and record.csa_actual_m2 > 0
    assert record.nozzle_min_id_m is not None and record.nozzle_min_id_m > 0
    assert record.control_height_m is not None and record.control_height_m > 0
    assert record.residence_time_s is not None and record.residence_time_s > 0
    # input_json 双轨：sizing + hydraulics + sizing_spec
    assert "sizing_spec" in record.input_json
    assert record.input_json["sizing_spec"]["vessel_shape"] == "HORIZONTAL"
    assert "sizing_spec" in record.output_json


# ============================================================================
# 2) V1.0 兼容：sizing_spec=None → 6 列 NULL（无 T2 调用）
# ============================================================================


@pytest.mark.asyncio
async def test_calculate_vessel_sizing_spec_none_keeps_v1_compat(
    client, db: AsyncSession, checked_stream, designer_headers
):
    """sizing_spec=None 时不触发 C-08 V1.2 计算；6 列全 NULL（V1.0 兼容）。"""
    body = _v1_sizing_body(checked_stream.stream_id)
    # 不放 sizing_spec 字段

    r = await client.post(
        "/api/v1/vessel/calculate",
        json=body,
        headers=designer_headers,
    )
    assert r.status_code == 201
    resp = r.json()
    # result.sizing_spec = None
    assert resp["result"]["sizing_spec"] is None

    calc_id = uuid.UUID(resp["calc_id"])
    record = await db.get(VesselResult, calc_id)
    assert record is not None
    # 6 列全 NULL
    assert record.vmax_m_s is None
    assert record.csa_min_m2 is None
    assert record.csa_actual_m2 is None
    assert record.nozzle_min_id_m is None
    assert record.control_height_m is None
    assert record.residence_time_s is None


# ============================================================================
# 3) T3 calc_partial_volume 衔接：formula_ref 必含 head/cylinder/total +
#    WS-CA-PR-010 sizing 公式键（合并而非覆盖）
# ============================================================================


@pytest.mark.asyncio
async def test_calculate_vessel_sizing_spec_formula_ref_integration(
    client, checked_stream, designer_headers
):
    """result.sizing_spec.formula_ref 必须含 T3 几何 + WS-CA-PR-010 sizing
    两部分（合并而非覆盖）。
    """
    body = _v1_sizing_body(checked_stream.stream_id)
    body["sizing_spec"] = _valid_sizing_spec()

    r = await client.post(
        "/api/v1/vessel/calculate",
        json=body,
        headers=designer_headers,
    )
    assert r.status_code == 201
    spec = r.json()["result"]["sizing_spec"]
    formula_ref = spec["formula_ref"]

    # T3 几何公式键（calc_partial_volume 输出）
    t3_keys = {"head", "cylinder", "total"}
    assert t3_keys.issubset(formula_ref.keys()), (
        f"T3 几何 formula_ref 缺失: {t3_keys - set(formula_ref.keys())}"
    )
    # T2 WS-CA-PR-010 sizing 公式键
    sizing_keys = {
        "stage1_volumetric", "stage2_mixed_density", "stage3_souders_brown",
        "stage4_csa", "stage5_nozzle", "stage5_control", "stage5_residence",
        "ws_ca_pr_010_sizing",
    }
    assert sizing_keys.issubset(formula_ref.keys()), (
        f"sizing formula_ref 缺失: {sizing_keys - set(formula_ref.keys())}"
    )


# ============================================================================
# 4) 出口流 c08_* 摘要（P6-4 T2 outlet_properties 字段）
# ============================================================================


@pytest.mark.asyncio
async def test_calculate_vessel_sizing_spec_outlet_c08_summary(
    client, db: AsyncSession, checked_stream, designer_headers
):
    """sizing_spec 触发时 outlet 流必须含 c08_* 6 字段摘要。"""
    from app.models.project import Stream as StreamModel

    body = _v1_sizing_body(checked_stream.stream_id)
    body["sizing_spec"] = _valid_sizing_spec()

    r = await client.post(
        "/api/v1/vessel/calculate",
        json=body,
        headers=designer_headers,
    )
    assert r.status_code == 201
    outlet_stream_id = uuid.UUID(r.json()["outlet_stream_id"])

    outlet = await db.get(StreamModel, outlet_stream_id)
    assert outlet is not None
    props = outlet.stream_properties_json

    # c08_* 6 字段（与 sizing_spec_result 同步）
    expected_keys = {
        "c08_vmax_m_s", "c08_csa_min_m2", "c08_csa_actual_m2",
        "c08_nozzle_inlet_id_m", "c08_control_height_m", "c08_residence_time_s",
    }
    assert expected_keys.issubset(set(props.keys())), (
        f"outlet c08_* 摘要缺失: {expected_keys - set(props.keys())}"
    )
    assert props["c08_vmax_m_s"] > 0


# ============================================================================
# 5) SG 反推不一致 → 422 TWO_PHASE_SEPARATOR_SIZING_INPUT_ERROR
# ============================================================================


@pytest.mark.asyncio
async def test_calculate_vessel_sizing_spec_sg_mismatch_422(
    client, checked_stream, designer_headers
):
    """SG 与 density 反推不一致（>1%）应抛 422 TWO_PHASE_SEPARATOR_SIZING_INPUT_ERROR。

    V1.2 SPEC §3.4.2 强校验：oil_sg = oil_density/999.0；gas_sg = gas_density/1.225。
    """
    body = _v1_sizing_body(checked_stream.stream_id)
    spec = _valid_sizing_spec()
    # 故意把 gas_sg 改成与 density 反推不符（density=12 → sg=9.7959；这里填 5.0）
    spec["gas_sg"] = 5.0
    body["sizing_spec"] = spec

    r = await client.post(
        "/api/v1/vessel/calculate",
        json=body,
        headers=designer_headers,
    )
    assert r.status_code == 422, r.text
    assert r.json()["code"] == "TWO_PHASE_SEPARATOR_SIZING_INPUT_ERROR"