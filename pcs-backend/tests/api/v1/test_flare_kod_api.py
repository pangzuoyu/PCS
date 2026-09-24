"""P6-2 Task 21 FLARE_SYS kod_sizing API 端点契约测试。

按 SPEC §3.2.3 P6-FLR-002 + API 521 §5.15.3（Souders-Brown）+ §5.15.5
（Water Seal）：

端到端验证（in-memory SQLite + httpx async）：
- POST /api/v1/flare/kod-sizing → 200 + KodSizingResponse
- 输入校验失败 → 422（FLARE_KOD_INPUT_ERROR / FLARE_WATER_SEAL_INPUT_ERROR envelope）
- 缺 auth header → 401/403

设计要点：
- kod_sizing 是纯计算不写 DB；但 endpoint 仍注入 db session（与全局 pattern 一致）。
- 不 mock 主断言（走真 router + 真 service）。
"""
from __future__ import annotations

import uuid
from typing import Any

import pytest

# ============================================================================
# 1. 合法 body → 200
# ============================================================================


async def test_kod_sizing_endpoint_200(client, sample_user_token) -> None:
    """POST /api/v1/flare/kod-sizing 合法 body → 200 + KodSizingResponse。

    ACL：sample_user_token 默认 DESIGNER。
    """
    body: dict[str, Any] = {
        "project_id": str(uuid.uuid4()),
        "standard_profile_code": "API_521",
        # KOD 输入
        "vapor_mass_flow_kgs": 10.0,
        "vapor_density_kg_m3": 1.177,
        "liquid_density_kg_m3": 1000.0,
        "k_sb_m_s": 0.3,
        # Water Seal 输入
        "header_pressure_pa": 200000.0,
        "seal_pot_pressure_pa": 0.0,
        "water_density_kg_m3": 1000.0,
        "gravity_m_s2": 9.81,
        "safety_factor": 1.5,
        "surge_pressure_pa": 0.0,
    }
    r = await client.post(
        "/api/v1/flare/kod-sizing",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 200, f"got {r.status_code}: {r.text}"
    data = r.json()
    # 顶层字段
    assert "kod" in data
    assert "water_seal" in data
    assert data["project_id"] == body["project_id"]
    assert data["standard_profile_code"] == "API_521"
    assert data["formula_ref"] == "API_521_§5.15.3+§5.15.5"
    # KOD 子结果手算校核（与单元 test_kod_basic_air_steam 一致）
    kod = data["kod"]
    assert kod["formula_ref"] == "API_521_§5.15.3"
    assert kod["u_perm_m_s"] == pytest.approx(8.739, abs=5e-3)
    assert kod["diameter_m"] == pytest.approx(1.113, abs=5e-3)
    # Water Seal 子结果手算校核
    ws = data["water_seal"]
    assert ws["formula_ref"] == "API_521_§5.15.5"
    assert ws["delta_pressure_pa"] == 200000.0
    assert ws["h_seal_m"] == pytest.approx(20.387, abs=5e-3)
    assert ws["h_design_m"] == pytest.approx(30.580, abs=5e-3)


# ============================================================================
# 2. 输入校验失败 → 422
# ============================================================================


async def test_kod_sizing_endpoint_422_liquid_lt_vapor(
    client, sample_user_token
) -> None:
    """POST body ρ_L < ρ_V → 422（service 层 KodSizingInputError）。

    Pydantic schema 校验仅拦截 liquid_density_kg_m3 > 0 与 vapor_density_kg_m3 > 0；
    二者大小关系的语义校验由 service 层 KodSizingInputError 抛出。
    """
    body: dict[str, Any] = {
        "project_id": str(uuid.uuid4()),
        "vapor_mass_flow_kgs": 10.0,
        # 非法：ρ_L < ρ_V（无气液分离）
        "vapor_density_kg_m3": 5.0,
        "liquid_density_kg_m3": 2.0,
        "k_sb_m_s": 0.3,
        # Water Seal 输入合法
        "header_pressure_pa": 200000.0,
        "seal_pot_pressure_pa": 0.0,
        "safety_factor": 1.5,
    }
    r = await client.post(
        "/api/v1/flare/kod-sizing",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 422, f"got {r.status_code}: {r.text}"
    body_json = r.json()
    # service 层 KodSizingInputError → envelope.code == "FLARE_KOD_INPUT_ERROR"
    assert body_json.get("code") in ("VALIDATION_ERROR", "FLARE_KOD_INPUT_ERROR")


async def test_kod_sizing_endpoint_422_k_sb_out_of_range(
    client, sample_user_token
) -> None:
    """POST body k_sb_m_s=2.5 → 422（schema le=2.0 拦截）。"""
    body: dict[str, Any] = {
        "project_id": str(uuid.uuid4()),
        "vapor_mass_flow_kgs": 10.0,
        "vapor_density_kg_m3": 1.177,
        "liquid_density_kg_m3": 1000.0,
        "k_sb_m_s": 2.5,  # 非法：超出 (0, 2.0]
        "header_pressure_pa": 200000.0,
        "seal_pot_pressure_pa": 0.0,
        "safety_factor": 1.5,
    }
    r = await client.post(
        "/api/v1/flare/kod-sizing",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    # Pydantic le=2.0 校验失败 → 422
    assert r.status_code == 422
    body_json = r.json()
    assert body_json.get("code") in ("VALIDATION_ERROR", "FLARE_KOD_INPUT_ERROR")


# ============================================================================
# 3. 缺 auth header → 401/403
# ============================================================================


async def test_kod_sizing_endpoint_unauthenticated(client) -> None:
    """缺 auth header → 401/403。"""
    body: dict[str, Any] = {
        "project_id": str(uuid.uuid4()),
        "vapor_mass_flow_kgs": 10.0,
        "vapor_density_kg_m3": 1.177,
        "liquid_density_kg_m3": 1000.0,
        "k_sb_m_s": 0.3,
        "header_pressure_pa": 200000.0,
        "seal_pot_pressure_pa": 0.0,
        "safety_factor": 1.5,
    }
    r = await client.post("/api/v1/flare/kod-sizing", json=body)
    assert r.status_code in (401, 403), f"got {r.status_code}: {r.text}"
