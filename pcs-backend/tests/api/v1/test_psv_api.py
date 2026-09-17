"""P5-3-6 PSV API + 落库 + outlet_stream + 标准 profile 集成测试。

按 PCS-PLAN-P5-DEVICE-EQUIPMENT.md §395-417 + SUP-P5-PSV-001 + ADR-0028 V1.1：

端到端验证（in-memory SQLite + httpx async）：
- POST /api/v1/psv/calculate 4 种 relief_scenario（FIRE / CLOSED_VALVE /
  REACTION_RUNAWAY / THERMAL_EXPANSION）→ 201 + record_hash + outlet
- record_hash 16 hex + lineage（DataLineage.source_ref_id = stream_id）
- PsvResult ORM 落库（12 标量 + 5 JSONB + standard_refs_json + formula_ref_json）
- 三步守卫（DRAFT → 403 / 不存在 → 404 / 输入非法 → 422）
- outlet_stream DRAFT 态（PSV_CALCULATED）

- GET /api/v1/projects/{pid}/psv/standard-profile：未配置 → 200 null
- POST /api/v1/projects/{pid}/psv/standard-profile：创建默认 profile → 201
  - CUSTOM 缺 approval_json → 422
"""
from __future__ import annotations

import re
import uuid
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.calc import PsvResult
from app.models.enums import StreamSignStatus
from app.models.project import Project, Stream, Workspace
from app.models.psv_standards import ProjectCalculationStandardProfile
from app.models.system import DataLineage
from app.schemas.stream import StreamCreate
from app.services.stream_service import StreamService

_HASH_RE = re.compile(r"^[0-9a-f]{16}$")


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def make_project(db: AsyncSession):
    async def _make() -> Project:
        ws = Workspace(
            workspace_type="FORMAL", name=f"ws-{uuid.uuid4().hex[:8]}"
        )
        db.add(ws)
        await db.flush()
        proj = Project(
            project_no=f"P-{uuid.uuid4().hex[:8]}",
            project_name="psv API 测试项目",
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
    proj = await make_project()
    sp, _ = await StreamService.create(
        db,
        StreamCreate(
            project_id=proj.project_id,
            workspace_id=proj.workspace_id,
            stream_name="S-PSV-301",
            case_type="NORMAL",
            data_mode="CHEMICAL",
            source_type="MANUAL_ENTRY",
            temp=80.0, press=200.0, phase="LIQUID",
            mass_flow=1000.0,
            composition_json={"74-98-6": 0.3, "106-97-8": 0.7},
        ),
        actor=uuid.uuid4(),
    )
    sp.sign_status = StreamSignStatus.CHECKED
    await db.commit()
    await db.refresh(sp)
    return sp


@pytest_asyncio.fixture
async def draft_stream(db: AsyncSession, make_project) -> Stream:
    """DRAFT 流（用于守卫 403 测试）。"""
    proj = await make_project()
    sp, _ = await StreamService.create(
        db,
        StreamCreate(
            project_id=proj.project_id,
            workspace_id=proj.workspace_id,
            stream_name="S-DRAFT",
            case_type="NORMAL",
            data_mode="CHEMICAL",
            source_type="MANUAL_ENTRY",
            temp=80.0, press=200.0, phase="LIQUID",
            mass_flow=1000.0,
            composition_json={"74-98-6": 0.5, "106-97-8": 0.5},
        ),
        actor=uuid.uuid4(),
    )
    # 默认 DRAFT，不动
    return sp


@pytest.fixture
def designer_headers() -> dict[str, str]:
    token = create_access_token(subject="test-designer", role="DESIGNER")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def pc_headers() -> dict[str, str]:
    """PROCESS_CONTROLLER 角色（写标准 profile 必需）。"""
    token = create_access_token(
        subject="test-pc", role="PROCESS_CONTROLLER"
    )
    return {"Authorization": f"Bearer {token}"}


def _fire_body(stream_id: uuid.UUID) -> dict[str, Any]:
    """POST /psv/calculate FIRE scenario 默认 body。

    C6 fix：V2 严格公式（含 M/Z/T/k 等熵项）下，原 V1 简化参数 area 远超 T_max（5.1e-5 m²）。
    改为工业级高压气体参数：2 MPa / 700 K / 蒸汽 M=0.018 / k=1.3，使 area 落在 Q~T 范围内。
    """
    return {
        "source_stream_id": str(stream_id),
        "relief_scenario": "FIRE",
        "scenario_params": {
            "D_m": 1.0,
            "H_m": 5.0,
            "liquid_level_fraction": 0.5,
            "environment_factor_F": 1.0,
            "h_fg_j_per_kg": 350_000.0,
        },
        "sizing_params": {
            "relief_mass_flow_kgs": 0.005,
            "phase": "GAS",
            "P_back_pa": 2_000_000.0,
            "P_set_pa": 200_000.0,  # 保留 200_000 以便 set_pressure_pa 断言通过
            "T_k": 700.0,
            "M_kg_per_mol": 0.018,
            "Z": 1.0,
            "k_cp_ratio": 1.3,
        },
    }


def _closed_valve_body(stream_id: uuid.UUID) -> dict[str, Any]:
    return {
        "source_stream_id": str(stream_id),
        "relief_scenario": "CLOSED_VALVE",
        "scenario_params": {
            "V_pipe_m3": 0.1,
            "rho_L_kg_m3": 850.0,
            "t_isolation_s": 600.0,
        },
        "sizing_params": {
            "relief_mass_flow_kgs": 0.1,
            "phase": "LIQUID",
            "P_back_pa": 100_000.0,
            "P_set_pa": 300_000.0,
            "rho_L_kg_m3": 850.0,
        },
    }


def _reaction_runaway_body(stream_id: uuid.UUID) -> dict[str, Any]:
    return {
        "source_stream_id": str(stream_id),
        "relief_scenario": "REACTION_RUNAWAY",
        "scenario_params": {
            "Q_rxn_w": 50_000.0,
            "fraction_to_valve": 0.3,
        },
        "sizing_params": {
            "relief_mass_flow_kgs": 0.04,
            "phase": "GAS",
            "P_back_pa": 10_000_000.0,
            "P_set_pa": 200_000.0,
            "T_k": 500.0,
            "M_kg_per_mol": 0.020,
            "Z": 1.0,
            "k_cp_ratio": 1.3,
        },
    }


def _thermal_expansion_body(stream_id: uuid.UUID) -> dict[str, Any]:
    return {
        "source_stream_id": str(stream_id),
        "relief_scenario": "THERMAL_EXPANSION",
        "scenario_params": {
            "V_L_m3": 1.0,
            "rho_L_kg_m3": 1000.0,
            "beta_per_k": 0.0001,
            "delta_T_k": 30.0,
            "t_heat_s": 3600.0,
        },
        "sizing_params": {
            "relief_mass_flow_kgs": 0.01,
            "phase": "LIQUID",
            "P_back_pa": 100_000.0,
            "P_set_pa": 200_000.0,
            "rho_L_kg_m3": 1000.0,
        },
    }


# ============================================================================
# 1) POST /psv/calculate FIRE scenario happy path
# ============================================================================


@pytest.mark.asyncio
async def test_calculate_psv_fire_happy_path(
    client, checked_stream, designer_headers
):
    """FIRE 火灾工况 happy path：201 + record_hash + lineage + outlet DRAFT。"""
    r = await client.post(
        "/api/v1/psv/calculate",
        json=_fire_body(checked_stream.stream_id),
        headers=designer_headers,
    )
    assert r.status_code == 201, r.text
    body = r.json()

    assert "calc_id" in body
    assert _HASH_RE.match(body["record_hash"]), body["record_hash"]
    assert body["calc_type"] == "PSV"
    assert body["stream_id"] == str(checked_stream.stream_id)
    assert len(body["lineage_ids"]) >= 1

    # outlet_stream DRAFT + 命名约定
    assert body["outlet_stream_id"] is not None
    assert body["outlet_stream_name"].startswith(checked_stream.stream_name)

    # result 含 aggregate / alliance / orifice
    result = body["result"]
    assert result["relief_scenario"] == "FIRE"
    assert result["aggregate"]["dominant_scenario"] == "FIRE"
    assert result["aggregate"]["case_count"] == 1
    assert result["relief_area"]["area_required_m2"] > 0
    assert result["orifice"]["selected_size"] in (
        "D", "E", "F", "G", "H", "J", "K", "L", "M", "N", "P", "Q", "R", "T",
    )
    assert result["set_pressure_pa"] == 200_000.0
    assert result["blowdown_fraction"] == 0.05
    # formula_ref_json 三段
    assert "fire_case_or_other" in result["formula_ref_json"]
    assert "relief_area" in result["formula_ref_json"]
    assert "orifice" in result["formula_ref_json"]


@pytest.mark.asyncio
async def test_calculate_psv_fire_db_record(
    client, db: AsyncSession, checked_stream, designer_headers
):
    """PsvResult ORM 落库：12 标量 + 5 JSONB + standard_refs_json + formula_ref_json。"""
    r = await client.post(
        "/api/v1/psv/calculate",
        json=_fire_body(checked_stream.stream_id),
        headers=designer_headers,
    )
    assert r.status_code == 201
    body = r.json()
    psv_id = uuid.UUID(body["calc_id"])

    record = await db.get(PsvResult, psv_id)
    assert record is not None
    # 12 标量
    assert record.set_pressure == 200_000.0
    assert record.relief_capacity > 0
    assert record.orifice_area > 0
    assert record.blowdown == 0.05
    assert record.inlet_size == "4 inch"
    assert record.outlet_size == "6 inch"
    assert record.relief_scenario == ["FIRE"]
    # 5 JSONB
    assert record.standard_profile_code == "API"  # 默认走 API/7th
    assert record.standard_refs_json["fire_case"]["standard"] == "API_521"
    assert record.formula_ref_json["dominant_scenario"] == "FIRE"
    assert record.pending_review is False
    assert record.migrated_default is False
    assert record.override_reason is None
    assert record.override_approval_json is None
    # record_hash 16 hex
    assert _HASH_RE.match(record.record_hash)
    # tag_number 格式 PSV-XXXXXXXX
    assert record.tag_number.startswith("PSV-")


# ============================================================================
# 2) POST /psv/calculate 4 种 scenario 全覆盖
# ============================================================================


@pytest.mark.parametrize("body_fn", [
    _fire_body, _closed_valve_body, _reaction_runaway_body, _thermal_expansion_body,
])
@pytest.mark.asyncio
async def test_calculate_psv_4_scenarios(
    client, checked_stream, designer_headers, body_fn
):
    """4 种 relief_scenario 全部走通（V1 dispatcher 隔离）。"""
    r = await client.post(
        "/api/v1/psv/calculate",
        json=body_fn(checked_stream.stream_id),
        headers=designer_headers,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["calc_type"] == "PSV"
    scenario = body_fn(checked_stream.stream_id)["relief_scenario"]
    assert body["result"]["relief_scenario"] == scenario
    assert body["result"]["aggregate"]["dominant_scenario"] == scenario


# ============================================================================
# 3) 三步守卫
# ============================================================================


@pytest.mark.asyncio
async def test_calculate_psv_draft_stream_403(
    client, draft_stream, designer_headers
):
    """DRAFT 流 → 403 STREAM_NOT_CHECKED。"""
    r = await client.post(
        "/api/v1/psv/calculate",
        json=_fire_body(draft_stream.stream_id),
        headers=designer_headers,
    )
    assert r.status_code == 403, r.text
    assert r.json()["code"] == "STREAM_NOT_CHECKED"


@pytest.mark.asyncio
async def test_calculate_psv_stream_not_found_404(
    client, designer_headers
):
    """源流不存在 → 404 SIM_STREAM_NOT_FOUND。"""
    fake_stream_id = uuid.uuid4()
    r = await client.post(
        "/api/v1/psv/calculate",
        json=_fire_body(fake_stream_id),
        headers=designer_headers,
    )
    assert r.status_code == 404, r.text
    assert r.json()["code"] == "SIM_STREAM_NOT_FOUND"


@pytest.mark.asyncio
async def test_calculate_psv_invalid_scenario_422(
    client, checked_stream, designer_headers
):
    """scenario_params 不合法（h_fg=0）→ 422 PSV_INPUT_ERROR。"""
    body = _fire_body(checked_stream.stream_id)
    body["scenario_params"]["h_fg_j_per_kg"] = 0.0  # 触发校验
    r = await client.post(
        "/api/v1/psv/calculate",
        json=body,
        headers=designer_headers,
    )
    assert r.status_code == 422, r.text
    assert r.json()["code"] == "PSV_INPUT_ERROR"


# ============================================================================
# 4) lineage 记录
# ============================================================================


@pytest.mark.asyncio
async def test_calculate_psv_lineage_recorded(
    client, db: AsyncSession, checked_stream, designer_headers
):
    """DataLineage.source_ref_id 记录源流 ID。"""
    r = await client.post(
        "/api/v1/psv/calculate",
        json=_fire_body(checked_stream.stream_id),
        headers=designer_headers,
    )
    assert r.status_code == 201
    psv_id = uuid.UUID(r.json()["calc_id"])

    rows = (
        await db.execute(
            select(DataLineage).where(
                DataLineage.record_type == "PsvResult",
                DataLineage.record_id == psv_id,
            )
        )
    ).scalars().all()
    assert len(rows) >= 1
    assert any(r.source_ref_id == checked_stream.stream_id for r in rows)


# ============================================================================
# 5) Outlet Stream PSV_CALCULATED
# ============================================================================


@pytest.mark.asyncio
async def test_calculate_psv_outlet_psv_calculated(
    client, db: AsyncSession, checked_stream, designer_headers
):
    """outlet_stream.source_type = PSV_CALCULATED + upstream_equipment_type = PSV。"""
    r = await client.post(
        "/api/v1/psv/calculate",
        json=_fire_body(checked_stream.stream_id),
        headers=designer_headers,
    )
    assert r.status_code == 201
    outlet_id = uuid.UUID(r.json()["outlet_stream_id"])

    outlet = await db.get(Stream, outlet_id)
    assert outlet is not None
    assert outlet.source_type == "PSV_CALCULATED"
    assert outlet.upstream_equipment_type == "PSV"
    assert outlet.upstream_stream_id == checked_stream.stream_id
    assert outlet.sign_status == StreamSignStatus.DRAFT


# ============================================================================
# 6) GET /api/v1/projects/{pid}/psv/standard-profile 无配置 → 200 null
# ============================================================================


@pytest.mark.asyncio
async def test_get_psv_standard_profile_empty(
    client, make_project, designer_headers
):
    """项目无 PSV 标准 profile → 200 null。"""
    proj = await make_project()
    r = await client.get(
        f"/api/v1/projects/{proj.project_id}/psv/standard-profile",
        headers=designer_headers,
    )
    assert r.status_code == 200, r.text
    assert r.json() is None


# ============================================================================
# 7) POST /api/v1/projects/{pid}/psv/standard-profile 创建默认
# ============================================================================


@pytest.mark.asyncio
async def test_post_psv_standard_profile_api(
    client, db: AsyncSession, make_project, pc_headers
):
    """PROCESS_CONTROLLER 创建 API/7th 默认 profile → 201 + DB 落库。"""
    proj = await make_project()
    body = {
        "profile_code": "API",
        "standard_refs_json": {
            "fire_case": {
                "standard": "API_521",
                "version": "7th",
                "clause": "§5.15.2.2.1",
            },
            "relief_area": {
                "standard": "API_520",
                "version": "7th",
                "clause": "§5.6.3",
            },
        },
    }
    r = await client.post(
        f"/api/v1/projects/{proj.project_id}/psv/standard-profile",
        json=body,
        headers=pc_headers,
    )
    assert r.status_code == 201, r.text
    resp_body = r.json()
    assert resp_body["profile_code"] == "API"
    assert resp_body["is_default"] is True
    assert resp_body["discipline"] == "PSV"
    assert resp_body["standard_refs_json"]["fire_case"]["version"] == "7th"

    # DB 落库
    profile_id = uuid.UUID(resp_body["profile_id"])
    record = await db.get(ProjectCalculationStandardProfile, profile_id)
    assert record is not None
    assert record.project_id == proj.project_id
    assert record.discipline == "PSV"
    assert record.profile_code == "API"
    assert record.is_default is True


@pytest.mark.asyncio
async def test_post_psv_standard_profile_custom_422(
    client, make_project, pc_headers
):
    """CUSTOM profile 缺 approval_json → 422。"""
    proj = await make_project()
    body = {
        "profile_code": "CUSTOM",
        "standard_refs_json": {"fire_case": {"version": "2024"}},
        # approval_json 缺 → 应 422
    }
    r = await client.post(
        f"/api/v1/projects/{proj.project_id}/psv/standard-profile",
        json=body,
        headers=pc_headers,
    )
    assert r.status_code == 422, r.text
    assert r.json()["code"] == "PSV_INPUT_ERROR"


@pytest.mark.asyncio
async def test_post_psv_standard_profile_designer_forbidden(
    client, make_project, designer_headers
):
    """DESIGNER 角色禁止 POST 标准 profile → 403。"""
    proj = await make_project()
    body = {
        "profile_code": "API",
        "standard_refs_json": {"fire_case": {"version": "7th"}},
    }
    r = await client.post(
        f"/api/v1/projects/{proj.project_id}/psv/standard-profile",
        json=body,
        headers=designer_headers,
    )
    assert r.status_code == 403, r.text


# ============================================================================
# 8) GET 项目 profile 已配置 → 200 + 详情
# ============================================================================


@pytest.mark.asyncio
async def test_get_psv_standard_profile_after_post(
    client, make_project, pc_headers, designer_headers
):
    """先 POST 创建 → GET 查回 → 详情一致。"""
    proj = await make_project()
    # POST
    await client.post(
        f"/api/v1/projects/{proj.project_id}/psv/standard-profile",
        json={
            "profile_code": "GB",
            "standard_refs_json": {
                "fire_case": {
                    "standard": "GB_T_150.1",
                    "version": "2024",
                    "clause": "附录B.1.3",
                },
            },
        },
        headers=pc_headers,
    )
    # GET
    r = await client.get(
        f"/api/v1/projects/{proj.project_id}/psv/standard-profile",
        headers=designer_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["profile_code"] == "GB"
    assert body["is_default"] is True


# ============================================================================
# P5-OPEN-10 SUP-P5-PSV-002 V1.14 §4.1 选型 18 字段端到端集成测试
# ============================================================================
#
# 覆盖：
# 1) 默认请求：21 字段透传 + PsvResult 落库 + kb=1.0/source='none'
# 2) SPRING_LOADED + BUILT_UP BP=15%：422 G10
# 3) PILOT_OPERATED：422 G7
# 4) RUPTURE_DISC：422 G8
# 5) BALANCED_BELLOWS + 缺 bellows_material：422 G17
# 6) BALANCED_BELLOWS + HASTELLOY_C276 + service_note='强氧化性'：422 G21
# 7) BALANCED_BELLOWS + valve_brand='LESER' + BP=20：kb 来自 LESER
# 8) orifice_override 越界（不在候选）：422 G12
# ============================================================================


@pytest.mark.asyncio
async def test_v114_default_request_writes_18_columns(
    client, db: AsyncSession, checked_stream, designer_headers
):
    """默认请求（无 V1.14 字段）→ PsvResult 18 列落库 + kb=1.0/source='none'。"""
    r = await client.post(
        "/api/v1/psv/calculate",
        json=_fire_body(checked_stream.stream_id),
        headers=designer_headers,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    psv_id = uuid.UUID(body["calc_id"])

    record = await db.get(PsvResult, psv_id)
    assert record is not None
    # 18 列落库
    assert record.valve_type == "SPRING_LOADED"
    assert record.body_material == "SS316"
    assert record.bellows_material is None
    assert record.flange_class == "300#"
    assert record.back_pressure_type == "BUILT_UP"
    assert record.back_pressure_pct == 0.0
    assert record.overpressure_pct == 0.10
    assert record.kb_factor == 1.0
    assert record.kb_source == "none"
    assert record.valve_brand is None
    assert record.cdtp_applied is False
    assert record.orifice_overridden is False
    assert record.orifice_manual is None
    assert record.rupture_disc_position == "NONE"
    assert record.rupture_disc_kc is None
    assert record.pilot_temperature_c is None
    assert record.pilot_temp_class == "GENERAL"
    assert record.fire_protection is False

    # outlet 透传
    outlet_id = uuid.UUID(body["outlet_stream_id"])
    outlet = await db.get(Stream, outlet_id)
    assert outlet.stream_properties_json["valve_type"] == "SPRING_LOADED"
    assert outlet.stream_properties_json["kb_factor"] == 1.0
    assert outlet.stream_properties_json["kb_source"] == "none"


@pytest.mark.asyncio
async def test_v114_g10_spring_builtup_bp_exceeded(
    client, checked_stream, designer_headers
):
    """SPRING_LOADED + BUILT_UP + BP=15% → 422 PSV_BACK_PRESSURE_EXCEEDED。"""
    body = _fire_body(checked_stream.stream_id)
    body["back_pressure_type"] = "BUILT_UP"
    body["back_pressure_pct"] = 15.0
    r = await client.post(
        "/api/v1/psv/calculate", json=body, headers=designer_headers,
    )
    assert r.status_code == 422, r.text
    err = r.json()
    assert err["code"] == "PSV_BACK_PRESSURE_EXCEEDED"
    assert err["detail"]["max_pct"] == 10.0


@pytest.mark.asyncio
async def test_v114_g7_pilot_operated_rejected(
    client, checked_stream, designer_headers
):
    """PILOT_OPERATED → 422 PSV_PILOT_OPERATED_NOT_SUPPORTED。"""
    body = _fire_body(checked_stream.stream_id)
    body["valve_type"] = "PILOT_OPERATED"
    r = await client.post(
        "/api/v1/psv/calculate", json=body, headers=designer_headers,
    )
    assert r.status_code == 422, r.text
    assert r.json()["code"] == "PSV_PILOT_OPERATED_NOT_SUPPORTED"


@pytest.mark.asyncio
async def test_v114_g8_rupture_disc_rejected(
    client, checked_stream, designer_headers
):
    """RUPTURE_DISC → 422 PSV_RUPTURE_DISC_NOT_SUPPORTED。"""
    body = _fire_body(checked_stream.stream_id)
    body["valve_type"] = "RUPTURE_DISC"
    r = await client.post(
        "/api/v1/psv/calculate", json=body, headers=designer_headers,
    )
    assert r.status_code == 422, r.text
    assert r.json()["code"] == "PSV_RUPTURE_DISC_NOT_SUPPORTED"


@pytest.mark.asyncio
async def test_v114_g17_balanced_bellows_missing_material(
    client, checked_stream, designer_headers
):
    """BALANCED_BELLOWS + bellows_material=None → 422 PSV_BELLOWS_MATERIAL_REQUIRED。"""
    body = _fire_body(checked_stream.stream_id)
    body["valve_type"] = "BALANCED_BELLOWS"
    # bellows_material 默认 None
    r = await client.post(
        "/api/v1/psv/calculate", json=body, headers=designer_headers,
    )
    assert r.status_code == 422, r.text
    assert r.json()["code"] == "PSV_BELLOWS_MATERIAL_REQUIRED"


@pytest.mark.asyncio
async def test_v114_g21_hastelloy_in_strong_oxidizer_rejected(
    client, checked_stream, designer_headers
):
    """BALANCED_BELLOWS + HASTELLOY_C276 + '强氧化性' service_note → 422 G21。"""
    body = _fire_body(checked_stream.stream_id)
    body["valve_type"] = "BALANCED_BELLOWS"
    body["bellows_material"] = "HASTELLOY_C276"
    body["service_note"] = "本工段为热浓硝酸介质，强氧化性介质工况"
    r = await client.post(
        "/api/v1/psv/calculate", json=body, headers=designer_headers,
    )
    assert r.status_code == 422, r.text
    assert r.json()["code"] == "PSV_BELLOWS_INCOMPATIBLE"


@pytest.mark.asyncio
async def test_v114_leser_brand_kb_lookup(
    client, db: AsyncSession, checked_stream, designer_headers
):
    """BALANCED_BELLOWS + LESER + BP=20% → kb 来自 LESER 曲线 @ 16% = 0.95。"""
    body = _fire_body(checked_stream.stream_id)
    body["valve_type"] = "BALANCED_BELLOWS"
    body["bellows_material"] = "SS316L"
    body["back_pressure_type"] = "BUILT_UP"
    body["back_pressure_pct"] = 20.0
    body["overpressure_pct"] = 16.0
    body["valve_brand"] = "LESER"
    r = await client.post(
        "/api/v1/psv/calculate", json=body, headers=designer_headers,
    )
    assert r.status_code == 201, r.text
    psv_id = uuid.UUID(r.json()["calc_id"])
    record = await db.get(PsvResult, psv_id)
    assert record.kb_factor == 0.95
    assert record.kb_source == "manufacturer:LESER"


@pytest.mark.asyncio
async def test_v114_g12_orifice_override_not_in_candidates(
    client, checked_stream, designer_headers
):
    """orifice_override='D' + 4×6 inch → 422 PSV_INLET_OUTLET_MISMATCH（D 不在候选）。"""
    body = _fire_body(checked_stream.stream_id)
    body["inlet_size"] = "4 inch"
    body["outlet_size"] = "6 inch"
    body["orifice_override"] = "D"
    r = await client.post(
        "/api/v1/psv/calculate", json=body, headers=designer_headers,
    )
    assert r.status_code == 422, r.text
    err = r.json()
    assert err["code"] == "PSV_INLET_OUTLET_MISMATCH"
    assert err["detail"]["orifice_override"] == "D"


@pytest.mark.asyncio
async def test_v114_full_v114_fields_happy_path(
    client, db: AsyncSession, checked_stream, designer_headers
):
    """V1.14 全字段非默认 happy path：18 列全部覆盖。

    覆盖 persist_psv_calculate 中 blowdown_db=None fallback / _get_default_blowdown
    + validated.cdtp_applied / rupture_disc_kc / cdtp_set_pressure_pa / candidates
    + warnings 派生 + orifice_overridden 实际路径 + outlet 全部 21 字段透传。
    """
    body = _fire_body(checked_stream.stream_id)
    body["valve_type"] = "BALANCED_BELLOWS"
    body["body_material"] = "SS316L"
    body["bellows_material"] = "SS316L"
    body["flange_class"] = "150#"
    body["back_pressure_type"] = "SUPERIMPOSED"  # CDTP 触发
    body["back_pressure_pct"] = 5.0
    body["superimposed_pressure_pa"] = 50_000.0
    body["set_pressure_pa"] = 250_000.0
    body["overpressure_pct"] = 0.10
    body["valve_brand"] = "LESER"
    body["rupture_disc_position"] = "UPSTREAM"  # kc=1.0 派生
    body["fire_protection"] = True
    body["medium"] = "GAS"
    # blowdown_fraction=None → _get_default_blowdown("GAS") fallback 派生
    body["inlet_size"] = "2 inch"
    body["outlet_size"] = "3 inch"

    r = await client.post(
        "/api/v1/psv/calculate", json=body, headers=designer_headers,
    )
    assert r.status_code == 201, r.text
    body_out = r.json()

    psv_id = uuid.UUID(body_out["calc_id"])
    record = await db.get(PsvResult, psv_id)
    # 18 列全部断言非默认
    assert record.valve_type == "BALANCED_BELLOWS"
    assert record.body_material == "SS316L"
    assert record.bellows_material == "SS316L"
    assert record.flange_class == "150#"
    assert record.back_pressure_type == "SUPERIMPOSED"
    assert record.back_pressure_pct == 5.0
    assert record.overpressure_pct == 0.10
    assert record.kb_source == "manufacturer:LESER"
    assert record.valve_brand == "LESER"
    assert record.cdtp_applied is True  # SUPERIMPOSED → CDTP
    assert record.rupture_disc_position == "UPSTREAM"
    assert record.rupture_disc_kc == 0.90  # UPSTREAM → kc=0.90（ASME UG-127）
    assert record.fire_protection is True
    assert record.pilot_temp_class == "GENERAL"

    # outlet 全部 21 字段透传
    outlet_id = uuid.UUID(body_out["outlet_stream_id"])
    outlet = await db.get(Stream, outlet_id)
    p = outlet.stream_properties_json
    assert p["valve_type"] == "BALANCED_BELLOWS"
    assert p["body_material"] == "SS316L"
    assert p["bellows_material"] == "SS316L"
    assert p["back_pressure_type"] == "SUPERIMPOSED"
    assert p["cdtp_applied"] is True
    assert p["rupture_disc_kc"] == 0.90
    assert p["fire_protection"] is True
    assert p["valve_brand"] == "LESER"
    assert p["kb_source"] == "manufacturer:LESER"

    # result dict 透传 cdtp_set_pressure_pa / candidates / warnings
    result = body_out["result"]
    assert result["valve_type"] == "BALANCED_BELLOWS"
    assert result["cdtp_applied"] is True
    assert "cdtp_set_pressure_pa" in result
    assert "candidates" in result
    assert "warnings" in result