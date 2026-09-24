"""P6-2 Task 20 FLARE_SYS header_sizing API 端点契约测试。

按 SPEC §3.2.3 P6-FLR-001 + API 521 §5.15.4：

端到端验证（in-memory SQLite + httpx async）：
- POST /api/v1/flare/header-sizing → 200 + HeaderSizingResponse
- 输入校验失败 → 422（FLARE_HEADER_INPUT_ERROR envelope）
- 缺 auth header → 401/403

设计要点：
- header_sizing 是纯计算不写 DB；但 endpoint 仍注入 db session（与全局 pattern 一致）。
- 不 mock 主断言（走真 router + 真 service）。
"""
from __future__ import annotations

import uuid
from typing import Any

# ============================================================================
# 1. 合法 body → 200
# ============================================================================


async def test_header_sizing_endpoint_200(client, sample_user_token) -> None:
    """POST /api/v1/flare/header-sizing 合法 body → 200 + HeaderSizingResponse。

    ACL：sample_user_token 默认 DESIGNER。
    """
    body: dict[str, Any] = {
        "project_id": str(uuid.uuid4()),
        "standard_profile_code": "API_521",
        "relief_mass_flow_kgs": 10.0,
        "avg_temperature_k": 300.0,
        "avg_pressure_pa": 101325.0,
        "mw_kg_kmol": 28.97,
        "specific_heat_ratio": 1.4,
        "target_mach": 0.5,
    }
    r = await client.post(
        "/api/v1/flare/header-sizing",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 200, f"got {r.status_code}: {r.text}"
    data = r.json()
    assert "diameter_m" in data
    assert "area_m2" in data
    assert "actual_mach" in data
    assert data["actual_mach"] == 0.5
    assert data["formula_ref"] == "API_521_§5.15.4"
    assert data["project_id"] == body["project_id"]
    assert data["standard_profile_code"] == "API_521"
    # 手算校核：D ≈ 0.2496 m（与单元 test_basic_air_n2 一致）
    assert 0.24 < data["diameter_m"] < 0.26


# ============================================================================
# 2. 输入校验失败 → 422
# ============================================================================


async def test_header_sizing_endpoint_422_negative_input(client, sample_user_token) -> None:
    """POST body W=-1 → 422（Pydantic gt=0 校验拦截）。"""
    body: dict[str, Any] = {
        "project_id": str(uuid.uuid4()),
        "relief_mass_flow_kgs": -1.0,  # 非法：gt=0
        "avg_temperature_k": 300.0,
        "avg_pressure_pa": 101325.0,
        "mw_kg_kmol": 28.97,
        "specific_heat_ratio": 1.4,
    }
    r = await client.post(
        "/api/v1/flare/header-sizing",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    # Pydantic gt=0 校验失败 → 422
    assert r.status_code == 422


async def test_header_sizing_endpoint_422_target_mach_out_of_range(
    client, sample_user_token
) -> None:
    """POST body target_mach=1.5 → 422（service 层 HeaderSizingInputError）。"""
    body: dict[str, Any] = {
        "project_id": str(uuid.uuid4()),
        "relief_mass_flow_kgs": 10.0,
        "avg_temperature_k": 300.0,
        "avg_pressure_pa": 101325.0,
        "mw_kg_kmol": 28.97,
        "specific_heat_ratio": 1.4,
        "target_mach": 1.5,  # 非法：超出 [0.05, 1.0]
    }
    r = await client.post(
        "/api/v1/flare/header-sizing",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 422
    # Pydantic le=1.0 校验失败 → envelope.code == "VALIDATION_ERROR"
    body_json = r.json()
    assert body_json.get("code") in ("VALIDATION_ERROR", "FLARE_HEADER_INPUT_ERROR")


# ============================================================================
# 3. 缺 auth header → 401/403
# ============================================================================


async def test_header_sizing_endpoint_unauthenticated(client) -> None:
    """缺 auth header → 401/403。"""
    body: dict[str, Any] = {
        "project_id": str(uuid.uuid4()),
        "relief_mass_flow_kgs": 10.0,
        "avg_temperature_k": 300.0,
        "avg_pressure_pa": 101325.0,
        "mw_kg_kmol": 28.97,
        "specific_heat_ratio": 1.4,
    }
    r = await client.post("/api/v1/flare/header-sizing", json=body)
    assert r.status_code in (401, 403), f"got {r.status_code}: {r.text}"