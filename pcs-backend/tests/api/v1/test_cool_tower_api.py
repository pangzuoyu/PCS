"""P6-2 Task 25 COOL_TOWER API 端点契约测试。

按 SPEC §3.2.4 P6-CT-001（§3.2.4.5~7）：
- POST /api/v1/cool-tower/heat-load-aggregator → 200 + HeatLoadAggregatorResponse
- POST /api/v1/cool-tower/fan-power → 200 + FanPowerResponse
- POST /api/v1/cool-tower/water-balance → 200 + WaterBalanceResponse
- CRUD /api/v1/cool-tower/results → 201/200/200/204（端到端真 router
  + 真 service，session 走 in-memory SQLite 与全局 client/db fixtures
  联调）

设计要点：
- 不 mock 主断言（走真 router + 真 service 层）；client / db fixture
  来自 tests/conftest.py（async httpx + in-memory SQLite）。
- ACL 走 sample_user_token（DESIGNER 角色）。
- 不依赖真实 cooling_tower_results 表（SQLite 全表建；CoolingTowerResult
  已通过 Base.metadata 全表创建）。
"""
from __future__ import annotations

import uuid
from typing import Any

import pytest

# ============================================================================
# 1. POST /cool-tower/heat-load-aggregator — 200 / 422 / 401
# ============================================================================


async def test_heat_load_aggregator_endpoint_200(
    client, sample_user_token
) -> None:
    """POST /cool-tower/heat-load-aggregator 合法 body → 200 +
    HeatLoadAggregatorResponse（formula_ref 一致 + per_exchanger_category
    回显）。"""
    body: dict[str, Any] = {
        "project_id": str(uuid.uuid4()),
    }
    r = await client.post(
        "/api/v1/cool-tower/heat-load-aggregator",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 200, f"got {r.status_code}: {r.text}"
    data = r.json()
    # 空项目 → 全 0
    assert data["h_aggregate_kw"] == 0.0
    assert data["heat_record_count"] == 0
    assert data["per_exchanger_category"] == {}
    assert data["formula_ref"] == "API_521_§3.2.4.5"


async def test_heat_load_aggregator_endpoint_422(
    client, sample_user_token
) -> None:
    """POST filter 含 'AIR_COOL' → 422（service 层 HeatAggregatorInputError）。"""
    body: dict[str, Any] = {
        "project_id": str(uuid.uuid4()),
        "exchanger_categories_filter": ["AIR_COOL"],
    }
    r = await client.post(
        "/api/v1/cool-tower/heat-load-aggregator",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 422, f"got {r.status_code}: {r.text}"


async def test_heat_load_aggregator_endpoint_unauthenticated(client) -> None:
    """POST 缺 auth → 401/403。"""
    body: dict[str, Any] = {"project_id": str(uuid.uuid4())}
    r = await client.post(
        "/api/v1/cool-tower/heat-load-aggregator", json=body
    )
    assert r.status_code in (401, 403), f"got {r.status_code}: {r.text}"


# ============================================================================
# 2. POST /cool-tower/fan-power — 200 / 422
# ============================================================================


async def test_fan_power_endpoint_200(client, sample_user_token) -> None:
    """POST /cool-tower/fan-power 合法 body → 200 + FanPowerResponse
    （手算校核）。"""
    body: dict[str, Any] = {
        "q_air_m3_s": 10.0,
        "delta_p_total_pa": 200.0,
        "fan_efficiency": 0.7,
        "motor_efficiency": 0.9,
    }
    r = await client.post(
        "/api/v1/cool-tower/fan-power",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 200, f"got {r.status_code}: {r.text}"
    data = r.json()
    # P_fan = 10×200/(0.7×0.9×1000) = 3.1746031746... ≈ 3.1746 kW
    assert data["p_fan_kw"] == pytest.approx(3.1746031746, abs=1e-6)
    assert data["formula_ref"] == "API_521_§3.2.4.6"


async def test_fan_power_endpoint_422(client, sample_user_token) -> None:
    """POST fan_efficiency=1.5 (out of range) → 422。"""
    body: dict[str, Any] = {
        "q_air_m3_s": 10.0,
        "delta_p_total_pa": 200.0,
        "fan_efficiency": 1.5,  # 超出 (0, 1)
        "motor_efficiency": 0.9,
    }
    r = await client.post(
        "/api/v1/cool-tower/fan-power",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 422, f"got {r.status_code}: {r.text}"


# ============================================================================
# 3. POST /cool-tower/water-balance — 200 / 422
# ============================================================================


async def test_water_balance_endpoint_200(client, sample_user_token) -> None:
    """POST /cool-tower/water-balance 合法 body → 200 +
    WaterBalanceResponse（手算校核）。

    Q=0.1 m³/s, ΔT=10°C, C=4.5, drift=0.001, h_vap=2400, Cp=4.187：
    E = 0.1 × 10 × 4.187 / 2400 = 0.001744583... ≈ 1.745e-3
    D = 0.001 × 0.1 = 1e-4
    B = E / 3.5 - D ≈ 3.984e-4
    M = E + D + B ≈ 2.244e-3
    """
    body: dict[str, Any] = {
        "q_w_m3_s": 0.1,
        "delta_t_c": 10.0,
        "cycle_ratio": 4.5,
        "drift_fraction": 0.001,
        "h_vap_kj_kg": 2400.0,
        "c_water_kj_kg_k": 4.187,
    }
    r = await client.post(
        "/api/v1/cool-tower/water-balance",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 200, f"got {r.status_code}: {r.text}"
    data = r.json()
    # E ≈ 0.1 × 10 × 4.187 / 2400 = 1.7446e-3
    assert data["evaporation_m3_s"] == pytest.approx(1.7446e-3, abs=1e-6)
    # D = 0.001 × 0.1 = 1e-4
    assert data["drift_m3_s"] == pytest.approx(1e-4, abs=1e-9)
    # B = E / 3.5 - D ≈ 3.984e-4
    assert data["blowdown_m3_s"] == pytest.approx(3.984e-4, abs=1e-5)
    assert data["formula_ref"] == "API_CTI_ATC-105_§3.2.4.4"


async def test_water_balance_endpoint_422(client, sample_user_token) -> None:
    """POST q_w_m3_s=0 (≤0) → 422。"""
    body: dict[str, Any] = {
        "q_w_m3_s": 0.0,
        "delta_t_c": 10.0,
    }
    r = await client.post(
        "/api/v1/cool-tower/water-balance",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 422, f"got {r.status_code}: {r.text}"


# ============================================================================
# 4. CRUD /cool-tower/results
# ============================================================================


def _create_request_body(**overrides: Any) -> dict[str, Any]:
    """构造 POST /cool-tower/results 合法 body。"""
    body: dict[str, Any] = {
        "project_id": str(uuid.uuid4()),
        "workspace_id": str(uuid.uuid4()),
        "tag_number": "CT-API-001",
        "standard_profile_code": "CTI_ATC_105",
        "calc_type": "MERKEL",
        "sign_status": "DRAFT",
        # 10 业务字段
        "duty_kw": 1500.0,
        "water_flow_m3h": 360.0,
        "makeup_water_m3h": 7.2,
        "fan_power_kw": 3.1746,
        "merkel_integral": 0.9811,
        "input_json": {"t1_c": 40, "t2_c": 30},
        "output_json": {"kav_l": 0.9811},
    }
    body.update(overrides)
    return body


async def test_create_cool_tower_result_endpoint_201(
    client, sample_user_token
) -> None:
    """POST /cool-tower/results 合法 body → 201 + CoolTowerResultResponse
    （record_hash 已设）。"""
    body = _create_request_body()
    r = await client.post(
        "/api/v1/cool-tower/results",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 201, f"got {r.status_code}: {r.text}"
    data = r.json()
    # 顶层字段
    assert "id" in data and data["id"]
    assert data["tag_number"] == "CT-API-001"
    assert data["standard_profile_code"] == "CTI_ATC_105"
    assert data["calc_type"] == "MERKEL"
    assert data["sign_status"] == "DRAFT"
    # record_hash 已 final（ADR-0028 §决策 4）
    assert data["record_hash"] and len(data["record_hash"]) == 16, (
        f"record_hash 应为 16 hex，实际={data['record_hash']!r}"
    )
    # 业务字段 round-trip
    assert data["duty_kw"] == pytest.approx(1500.0)
    assert data["fan_power_kw"] == pytest.approx(3.1746)
    assert data["merkel_integral"] == pytest.approx(0.9811)
    assert data["input_json"] == {"t1_c": 40, "t2_c": 30}


async def test_create_cool_tower_result_endpoint_422_empty_tag(
    client, sample_user_token
) -> None:
    """POST tag_number='' → 422（service 层
    CoolTowerPersistInputError）。"""
    body = _create_request_body(tag_number="")
    r = await client.post(
        "/api/v1/cool-tower/results",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 422, f"got {r.status_code}: {r.text}"


async def test_create_cool_tower_result_endpoint_unauthenticated(
    client,
) -> None:
    """POST /cool-tower/results 缺 auth → 401/403。"""
    body = _create_request_body()
    r = await client.post("/api/v1/cool-tower/results", json=body)
    assert r.status_code in (401, 403), f"got {r.status_code}: {r.text}"


async def test_list_cool_tower_results_endpoint_200(
    client, sample_user_token
) -> None:
    """GET /cool-tower/results?project_id=X → 200 + CoolTowerResultListResponse。

    端到端：先 POST 创建 2 行 → GET list 验证命中 2 行（默认 DRAFT/CHECKED
    filter）。
    """
    project_id = uuid.uuid4()
    for i in range(2):
        body = _create_request_body(
            project_id=str(project_id), tag_number=f"CT-LIST-{i}"
        )
        create_r = await client.post(
            "/api/v1/cool-tower/results",
            json=body,
            headers={"Authorization": f"Bearer {sample_user_token}"},
        )
        assert create_r.status_code == 201, create_r.text

    r = await client.get(
        f"/api/v1/cool-tower/results?project_id={project_id}",
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 200, f"got {r.status_code}: {r.text}"
    data = r.json()
    assert "items" in data
    assert data["total"] >= 2
    assert data["limit"] == 100
    assert data["offset"] == 0
    tag_numbers = {item["tag_number"] for item in data["items"]}
    assert {"CT-LIST-0", "CT-LIST-1"}.issubset(tag_numbers)


async def test_get_cool_tower_result_endpoint_200(
    client, sample_user_token
) -> None:
    """GET /cool-tower/results/{id} 已存在 → 200 + CoolTowerResultResponse。"""
    body = _create_request_body(tag_number="CT-GET-001")
    create_r = await client.post(
        "/api/v1/cool-tower/results",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert create_r.status_code == 201, create_r.text
    rid = create_r.json()["id"]

    r = await client.get(
        f"/api/v1/cool-tower/results/{rid}",
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 200, f"got {r.status_code}: {r.text}"
    data = r.json()
    assert data["id"] == rid
    assert data["tag_number"] == "CT-GET-001"


async def test_get_cool_tower_result_endpoint_404(
    client, sample_user_token
) -> None:
    """GET /cool-tower/results/{不存在 UUID} → 404。"""
    r = await client.get(
        f"/api/v1/cool-tower/results/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 404, f"got {r.status_code}: {r.text}"


async def test_update_cool_tower_result_endpoint_200(
    client, sample_user_token
) -> None:
    """PATCH /cool-tower/results/{id} DRAFT 状态 → 200 + 字段更新。"""
    body = _create_request_body(tag_number="CT-PATCH-001", duty_kw=20.0)
    create_r = await client.post(
        "/api/v1/cool-tower/results",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert create_r.status_code == 201, create_r.text
    rid = create_r.json()["id"]

    patch_body = {"duty_kw": 35.0, "fan_power_kw": 4.5}
    r = await client.patch(
        f"/api/v1/cool-tower/results/{rid}",
        json=patch_body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 200, f"got {r.status_code}: {r.text}"
    data = r.json()
    assert data["duty_kw"] == pytest.approx(35.0)
    assert data["fan_power_kw"] == pytest.approx(4.5)


async def test_delete_cool_tower_result_endpoint_204(
    client, sample_user_token
) -> None:
    """DELETE /cool-tower/results/{id} → 204；后续 GET list 应被 OBSOLETE
    filter 过滤。"""
    project_id = uuid.uuid4()
    body = _create_request_body(
        project_id=str(project_id), tag_number="CT-DEL-001"
    )
    create_r = await client.post(
        "/api/v1/cool-tower/results",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert create_r.status_code == 201, create_r.text
    rid = create_r.json()["id"]

    r = await client.delete(
        f"/api/v1/cool-tower/results/{rid}",
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 204, f"got {r.status_code}: {r.text}"

    # list 应不命中（OBSOLETE 被默认 filter 过滤）
    list_r = await client.get(
        f"/api/v1/cool-tower/results?project_id={project_id}",
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert list_r.status_code == 200, list_r.text
    ids = [item["id"] for item in list_r.json()["items"]]
    assert rid not in ids, "软删后默认 list filter 应排除 OBSOLETE"