"""P6-1 Task 14 + P6-2 S-01: restriction_api POST /api/v1/restriction/calculate 端点契约测试。

按 PCS-PLAN-P6-BATCH.md §Task 14 + SPEC §3.2.2.1~4 + §3.2.2.6 + ADR-0022 V1.0 +
评审委员会 2026-09-24 闪蒸路径裁决：

端到端验证（in-memory SQLite + httpx async）：
- POST /api/v1/restriction/calculate → 201 + orifice_id + outlet_stream_id + record_hash
- OpenAPI /openapi.json 含 /restriction/calculate 路径 + 19 字段 schema（含 P6-2 S-01 flash）
- Pydantic extra='forbid' → 422 ValidationError（未知字段拦截）
- standard_profile_code 缺省 → 默认 ISO-5167
- outlet properties change_type='ISOENTHALPIC'（**关键区别 CV FRICTION**）
- P6-2 S-01 闪蒸联动：response 含 flashing / P_sat_pa / vapor_fraction_at_outlet /
  model_used 字段

DB 测试 fixture 最简 pattern（参考 .wolf/cerebrum.md Do-Not-Repeat）：
- 源流直接 ORM 构造（最简必填字段；restriction_persist 仅校验 project_id 一致）
- POST API 创建（service 层补必填）→ DB UPDATE 状态字段
"""
from __future__ import annotations

import re
import uuid
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Stream

_HASH_RE = re.compile(r"^[0-9a-f]{16}$")


# ---------------------------------------------------------------------------
# Fixtures（最小源流；RESTRICTION 不需 CHECKED 流，restriction_persist 仅校验 project_id 一致）
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def source_stream(db: AsyncSession, project_id, workspace_id) -> Stream:
    """源流（DRAFT 状态；restriction_persist 仅校验 project_id 一致即可）。

    approval_depth 在 Stream ORM 上 NOT NULL 但无 server_default；测试 fixture
    显式填 1（DRAFT 态最小校对深度）。
    """
    s = Stream(
        project_id=project_id,
        workspace_id=workspace_id,
        stream_name=f"S-RES-{project_id.hex[:8]}",
        case_type="NORMAL",
        data_mode="CHEMICAL",
        source_type="MANUAL_ENTRY",
        approval_depth=1,
    )
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return s


def _orifice_body(
    project_id: uuid.UUID,
    workspace_id: uuid.UUID,
    source_stream_id: uuid.UUID,
    **overrides: Any,
) -> dict[str, Any]:
    """最小孔板工况请求（SPEC §3.2.2.1）。

    提供 D/d/Re_D/P1/dP/rho1 完整六件套以满足 RestrictionEngine 输入校验 +
    RestrictionResult NOT NULL 约束。
    """
    body: dict[str, Any] = {
        "project_id": str(project_id),
        "workspace_id": str(workspace_id),
        "device_type": "ORIFICE",
        "fluid_phase": "LIQUID",
        "D_pipe_m": 0.1,
        "d_solved_m": 0.05,
        "Re_D": 1.0e6,
        "P1_pa": 200_000.0,
        "dP_pa": 10_000.0,
        "rho1": 1000.0,
        "stages": 1,
        "source_stream_id": str(source_stream_id),
    }
    body.update(overrides)
    return body


# ============================================================================
# 1. POST /restriction/calculate 成功路径（孔板 + 默认 standard_profile_code）
# ============================================================================


@pytest.mark.asyncio
async def test_restriction_calculate_post_success(
    client, source_stream, project_id, workspace_id
):
    """POST /restriction/calculate happy path：201 + orifice_id + outlet + hash."""
    r = await client.post(
        "/api/v1/restriction/calculate",
        json=_orifice_body(project_id, workspace_id, source_stream.stream_id),
    )
    assert r.status_code == 201, r.text
    body = r.json()

    # 主键 + 关键结果字段
    assert "restriction_result_id" in body
    uuid.UUID(body["restriction_result_id"])  # parse OK
    assert body["device_type"] == "ORIFICE"
    assert body["C_discharge"] > 0
    assert body["standard_profile_code"] == "ISO-5167"  # 默认值
    assert _HASH_RE.match(body["record_hash"]), body["record_hash"]

    # outlet stream 锚定
    assert "outlet_stream_id" in body
    uuid.UUID(body["outlet_stream_id"])
    assert body["outlet_stream_id"] != body["restriction_result_id"]

    # tag_number 8 hex（无 RES- 前缀；outlet device 字段补前缀）
    assert re.match(r"^[0-9A-F]{8}$", body["tag_number"]), body["tag_number"]


# ============================================================================
# 2. OpenAPI 契约：/restriction/calculate 路径 + 14 字段 schema
# ============================================================================


@pytest.mark.asyncio
async def test_restriction_calculate_openapi_contract(client):
    """OpenAPI /openapi.json 含 /restriction/calculate 路径 + RestrictionCalculateRequest 关键字段。

    契约：
    - 路径存在
    - Request body schema 含关键必填字段（5 context + 2 device/phase + 6 工况 + 1 source）
    - Response 201 schema 含 restriction_result_id / outlet_stream_id / record_hash
    """
    r = await client.get("/openapi.json")
    assert r.status_code == 200, r.text
    spec = r.json()

    # 路径存在 + POST 方法
    path = "/api/v1/restriction/calculate"
    assert path in spec["paths"], f"OpenAPI 缺路径 {path}: {list(spec['paths'])}"
    post = spec["paths"][path].get("post")
    assert post is not None, f"OpenAPI {path} 缺 POST 方法"
    assert "requestBody" in post
    assert "201" in post["responses"] or "200" in post["responses"]

    # 引用 RestrictionCalculateRequest schema
    schemas = spec.get("components", {}).get("schemas", {})
    assert "RestrictionCalculateRequest" in schemas, (
        f"OpenAPI 缺 RestrictionCalculateRequest schema：{list(schemas)}"
    )
    req_props = schemas["RestrictionCalculateRequest"]["properties"]
    # 关键必填字段存在
    for field in (
        "project_id", "workspace_id", "device_type",
        "D_pipe_m", "d_solved_m", "Re_D", "P1_pa", "dP_pa", "rho1",
        "source_stream_id",
    ):
        assert field in req_props, (
            f"RestrictionCalculateRequest 缺字段 {field}: {list(req_props)}"
        )

    # 引用 RestrictionCalculateResponse schema
    assert "RestrictionCalculateResponse" in schemas, (
        f"OpenAPI 缺 RestrictionCalculateResponse schema：{list(schemas)}"
    )
    resp_props = schemas["RestrictionCalculateResponse"]["properties"]
    for field in (
        "restriction_result_id", "tag_number", "device_type", "C_discharge",
        "choked", "record_hash", "outlet_stream_id",
    ):
        assert field in resp_props, (
            f"RestrictionCalculateResponse 缺字段 {field}: {list(resp_props)}"
        )


# ============================================================================
# 3. invalid input：缺 source_stream_id → 422 ValidationError
# ============================================================================


@pytest.mark.asyncio
async def test_restriction_calculate_invalid_input_missing_source_stream(
    client, project_id, workspace_id
):
    """缺 source_stream_id → 422 Pydantic ValidationError（extra='forbid' + 必填拦截）。"""
    body = _orifice_body(project_id, workspace_id, source_stream_id=uuid.uuid4())
    del body["source_stream_id"]

    r = await client.post("/api/v1/restriction/calculate", json=body)
    assert r.status_code == 422, r.text
    payload = r.json()
    # Pydantic ValidationError 标准 envelope：detail[*].type 包含 "missing"
    assert "detail" in payload
    assert any(
        "source_stream_id" in (e.get("loc") or [])
        for e in payload["detail"]
    ), f"应有 source_stream_id 字段缺失错误：{payload['detail']}"
    missing_errors = [
        e for e in payload["detail"] if e.get("type") == "missing"
    ]
    assert len(missing_errors) >= 1, (
        f"应至少 1 条 missing 类型错误，实际：{payload['detail']}"
    )


@pytest.mark.asyncio
async def test_restriction_calculate_invalid_input_unknown_field(
    client, source_stream, project_id, workspace_id
):
    """未知字段 → 422（extra='forbid' 严格模式；不静默吞字段）。"""
    body = _orifice_body(project_id, workspace_id, source_stream.stream_id)
    body["unknown_field_xyz"] = "should be rejected"

    r = await client.post("/api/v1/restriction/calculate", json=body)
    assert r.status_code == 422, r.text
    payload = r.json()
    # extra='forbid' → Pydantic 抛 "extra_forbidden" 类型错误
    extra_errors = [
        e for e in payload["detail"] if e.get("type") == "extra_forbidden"
    ]
    assert len(extra_errors) >= 1, (
        f"应至少 1 条 extra_forbidden 错误，实际：{payload['detail']}"
    )


# ============================================================================
# 4. ISOENTHALPIC outlet change_type（区别 CV FRICTION_PRESSURE_DROP）
# ============================================================================


@pytest.mark.asyncio
async def test_restriction_calculate_isoentropic_outlet_change_type(
    client, db, source_stream, project_id, workspace_id
):
    """response + DB outlet properties change_type=ISOENTHALPIC。

    **关键区别于 CV**：限制装置是等熵焓降设备（SPEC §3.2.2 line 192 + ADR-0022），
    控制阀是摩擦压降设备（CV FRICTION_PRESSURE_DROP）。本测试验证 RESTRICTION
    走 ISOENTHALPIC 路径，确保 P6-1 ADR-0022 区分正确落地。
    """
    r = await client.post(
        "/api/v1/restriction/calculate",
        json=_orifice_body(project_id, workspace_id, source_stream.stream_id),
    )
    assert r.status_code == 201, r.text
    body = r.json()

    # 1. outlet_stream_id 可在 DB 反查
    outlet_stmt = select(Stream).where(
        Stream.stream_id == uuid.UUID(body["outlet_stream_id"])
    )
    outlet = (await db.execute(outlet_stmt)).scalar_one()
    assert outlet.source_type == "RESTRICTION_CALCULATED", (
        f"outlet source_type 应为 RESTRICTION_CALCULATED，实际 {outlet.source_type}"
    )

    # 2. properties.change_type == ISOENTHALPIC（区别 CV FRICTION_PRESSURE_DROP）
    props = outlet.stream_properties_json or {}
    assert props.get("change_type") == "ISOENTHALPIC", (
        f"outlet change_type 应为 ISOENTHALPIC，实际 {props.get('change_type')!r}；"
        f"此区别于 CV 的 FRICTION_PRESSURE_DROP（ADR-0022 区分）"
    )
    assert props.get("device_type") == "ORIFICE"
    # device 命名格式：RES-{tag_number}
    expected_device = f"RES-{body['tag_number']}"
    assert props.get("device") == expected_device, (
        f"device 应为 {expected_device!r}，实际 {props.get('device')!r}"
    )


# ============================================================================
# 5. P6-2 S-01 闪蒸路径：response.flashing / P_sat_pa / model_used=HEM
# ============================================================================


@pytest.mark.asyncio
async def test_restriction_calculate_flash_path_hem(
    client, source_stream, project_id, workspace_id
):
    """P6-2 S-01 闪蒸路径：response.flashing=True + P_sat_pa 合理 + model_used=HEM。

    工况：水 200°C + 节流到 200 kPa → P_sat ≈ 1.55 MPa > P_outlet=200 kPa → 闪蒸。
    验证：
    1. response.flashing = True（P6-2 S-01 替代 P1<50 kPa 启发式）
    2. response.P_sat_pa 合理（1.5 MPa ~ 1.6 MPa 范围）
    3. response.vapor_fraction_at_outlet > 0.8
    4. response.model_used = "HEM"（API STD 520 Annex C 切换）
    5. response 含新增字段（openapi 契约）
    """
    body = _orifice_body(project_id, workspace_id, source_stream.stream_id)
    body.update({
        "P1_pa": 2_000_000.0,
        "dP_pa": 1_800_000.0,
        "fluid": "WATER",
        "upstream_T_K": 473.15,  # 200 °C
        "rho_l_kg_m3": 864.0,
        "rho_v_kg_m3": 7.8,
    })

    r = await client.post("/api/v1/restriction/calculate", json=body)
    assert r.status_code == 201, r.text
    resp = r.json()

    # P6-2 S-01 闪蒸元数据
    assert resp["flashing"] is True
    assert resp["P_sat_pa"] is not None
    assert 1_500_000 < resp["P_sat_pa"] < 1_600_000, (
        f"水 200°C P_sat 应 ≈ 1.55 MPa，实际 {resp['P_sat_pa']}"
    )
    assert resp["vapor_fraction_at_outlet"] > 0.8
    assert resp["model_used"] == "HEM"


@pytest.mark.asyncio
async def test_restriction_calculate_non_flash_default_iso_5167(
    client, source_stream, project_id, workspace_id
):
    """P6-2 S-01 非闪蒸路径：response.model_used=ISO_5167（缺省 fluid/T 即水 25°C）。"""
    body = _orifice_body(project_id, workspace_id, source_stream.stream_id)
    # 缺省 fluid=WATER, upstream_T_K=298.15；P_outlet=190 kPa >> P_sat(水 25°C)=3.17 kPa
    r = await client.post("/api/v1/restriction/calculate", json=body)
    assert r.status_code == 201, r.text
    resp = r.json()

    assert resp["flashing"] is False
    assert resp["P_sat_pa"] is not None
    assert 3_000 < resp["P_sat_pa"] < 4_000
    assert resp["vapor_fraction_at_outlet"] == 0.0
    assert resp["model_used"] == "ISO_5167"


# ============================================================================
# 6. P6-6A-7 drain orifice sizing（POST /restriction/drain-orifice/size）
# ============================================================================


import json as _json
from pathlib import Path as _Path

_FIX_DIR = _Path(__file__).parent.parent.parent / "services" / "restriction" / "fixtures"


def _drain_size_body(**overrides: Any) -> dict[str, Any]:
    """最小 sizing 请求（XLS PR-023 黄金 fixture；OPEN-P6-6A-7）。"""
    golden = _json.loads(
        (_FIX_DIR / "golden_drain_orifice_size_pr023.json").read_text()
    )
    body = dict(golden["service_inputs"])
    body.update(overrides)
    return body


@pytest.mark.asyncio
async def test_drain_orifice_size_post_success(client, sample_user_token):
    """POST /restriction/drain-orifice/size 黄金 fixture → 200 + d ≈ 12.762 mm。

    ACL：DESIGNER 默认（sample_user_token 默认 DESIGNER 角色）。
    XLS PR-023 E42 报 d=15.204 mm vs PCS 收敛 d=12.762 mm（19% gap；fixture._doc_xls_vs_pcs_gap
    文档化 Ruling 7 family mismatch + XLS safety margin convention）。本测试断言 PCS 收敛值。
    """
    r = await client.post(
        "/api/v1/restriction/drain-orifice/size",
        json=_drain_size_body(),
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 200, r.text
    resp = r.json()

    # 黄金 fixture 期望 d ≈ 12.762 mm；Ruling 7 family mismatch 0.2% 容差
    expected = 0.012761815015983
    assert resp["orifice_diameter_m"] == pytest.approx(expected, rel=2e-3)
    assert resp["is_choked"] is True
    assert resp["converged"] is True
    assert resp["iterations"] <= 15
    assert resp["beta_ratio"] == pytest.approx(0.2593, rel=2e-3)
    assert "formula_ref" in resp
    assert "fluid_density" in resp["formula_ref"]


@pytest.mark.asyncio
async def test_drain_orifice_size_post_no_auth_rejected(client):
    """缺 auth → 401/403（current_actor 拦截；ACL DESIGNER / PROCESS_CONTROLLER）。

    current_actor 依赖先校验 bearer token（缺 → 401 MISSING_BEARER）；
    即使有 token，require_roles 仍可能抛 403。两条路径都属 ACL 拒绝。
    """
    r = await client.post(
        "/api/v1/restriction/drain-orifice/size",
        json=_drain_size_body(),
    )
    assert r.status_code in (401, 403), r.text


@pytest.mark.asyncio
async def test_drain_orifice_size_post_non_choked_422(client, sample_user_token):
    """非阻塞流（P2/P1 > r_c）→ 422 DRAIN_ORIFICE_INPUT_ERROR（sizing 仅适用临界流）。

    service 层 DrainOrificeInputError 由 install_exception_handlers 兜底转 422 envelope。
    """
    # P2 = 0.95 * P1 → p_ratio=0.95 > r_c(1.18)≈0.568 → 非阻塞
    body = _drain_size_body(outlet_pressure_kpa=0.95 * 6300.0)
    r = await client.post(
        "/api/v1/restriction/drain-orifice/size",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 422, r.text
    payload = r.json()
    assert payload.get("code") == "DRAIN_ORIFICE_INPUT_ERROR"
    assert "非阻塞流" in payload.get("message", "")


@pytest.mark.asyncio
async def test_drain_orifice_size_openapi_contract(client):
    """OpenAPI /openapi.json 含 /restriction/drain-orifice/size + DrainOrificeSize{Req,Resp}schema。

    契约：
    - 路径存在 + POST 方法
    - Request schema 含关键必填字段（8 工况 + 3 收敛控制）
    - Response schema 含关键计算字段（orifice_diameter_m, beta_ratio, converged, iterations）
    """
    r = await client.get("/openapi.json")
    assert r.status_code == 200, r.text
    spec = r.json()

    path = "/api/v1/restriction/drain-orifice/size"
    assert path in spec["paths"], (
        f"OpenAPI 缺路径 {path}: {list(spec['paths'])}"
    )
    post = spec["paths"][path].get("post")
    assert post is not None, f"OpenAPI {path} 缺 POST 方法"
    assert "requestBody" in post
    assert "200" in post["responses"]

    schemas = spec.get("components", {}).get("schemas", {})
    assert "DrainOrificeSizeRequest" in schemas, (
        f"OpenAPI 缺 DrainOrificeSizeRequest schema：{list(schemas)}"
    )
    req_props = schemas["DrainOrificeSizeRequest"]["properties"]
    for field in (
        "inlet_pressure_kpa", "outlet_pressure_kpa", "temperature_k",
        "relief_flow_kg_s", "compressibility_z", "molecular_weight_kg_kmol",
        "pipe_diameter_m", "specific_heat_ratio", "specific_gravity",
        "discharge_coefficient", "initial_d_m", "tol", "max_iter",
        "imperial_units",
    ):
        assert field in req_props, (
            f"DrainOrificeSizeRequest 缺字段 {field}: {list(req_props)}"
        )

    assert "DrainOrificeSizeResponse" in schemas, (
        f"OpenAPI 缺 DrainOrificeSizeResponse schema：{list(schemas)}"
    )
    resp_props = schemas["DrainOrificeSizeResponse"]["properties"]
    for field in (
        "orifice_diameter_m", "orifice_area_m2", "beta_ratio", "ftp_factor",
        "y_cr_sqrt", "critical_pressure_ratio", "actual_pressure_ratio",
        "is_choked", "iterations", "converged", "residual_kg_s",
        "formula_ref",
    ):
        assert field in resp_props, (
            f"DrainOrificeSizeResponse 缺字段 {field}: {list(resp_props)}"
        )