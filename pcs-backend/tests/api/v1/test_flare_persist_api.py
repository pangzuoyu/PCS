"""P6-2 Task 23 FLARE_SYS flare_persist + flare_tip API 端点契约测试。

按 SPEC §3.2.3 P6-FLR-004 + API 521 §5.15.6：
- POST /api/v1/flare/tip → 200 + FlareTipResponse
- CRUD /api/v1/flare/results → 201/200/200/204（端到端真 router + 真
  service，session 走 in-memory SQLite 与全局 client/db fixtures 联调）

设计要点：
- 不 mock 主断言（走真 router + 真 service 层）；client / db fixture
  来自 tests/conftest.py（async httpx + in-memory SQLite）。
- ACL 走 sample_user_token（DESIGNER 角色）。
- 不依赖真实 flare_system_results 表（SQLite 全表建；FlareSystemResult
  已通过 Base.metadata 全表创建）。
"""
from __future__ import annotations

import uuid
from typing import Any

import pytest

# ============================================================================
# 1. POST /flare/tip — 200 + FlareTipResponse
# ============================================================================


async def test_flare_tip_endpoint_200(client, sample_user_token) -> None:
    """POST /flare/tip 合法 body → 200 + FlareTipResponse（手算校核）。"""
    body: dict[str, Any] = {
        "project_id": str(uuid.uuid4()),
        "standard_profile_code": "API_521",
        "header_diameter_m": 0.25,
        "mw_kg_kmol": 28.97,
        "tip_temperature_k": 300.0,
        "tip_pressure_pa": 101325.0,
        "specific_heat_ratio": 1.4,
        "target_mach": 0.2,
    }
    r = await client.post(
        "/api/v1/flare/tip",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 200, f"got {r.status_code}: {r.text}"
    data = r.json()
    # 手算校核
    assert data["tip_diameter_m"] == pytest.approx(0.25, abs=1e-12)
    assert data["tip_velocity_m_s"] == pytest.approx(69.44, abs=1e-2)
    assert data["sound_speed_m_s"] == pytest.approx(347.2, abs=1e-1)
    assert data["actual_mach"] == pytest.approx(0.2, abs=1e-9)
    assert data["gas_density_kg_m3"] == pytest.approx(1.177, abs=1e-3)
    assert data["mass_flux_kgs_m2"] == pytest.approx(81.71, abs=1e-2)
    assert data["formula_ref"] == "API_521_§5.15.6"


async def test_flare_tip_endpoint_422(client, sample_user_token) -> None:
    """POST /flare/tip P<=0 → 422 + FlareTipInputError envelope。"""
    body: dict[str, Any] = {
        "project_id": str(uuid.uuid4()),
        "header_diameter_m": 0.25,
        "mw_kg_kmol": 28.97,
        "tip_temperature_k": 300.0,
        "tip_pressure_pa": -101325.0,  # 非法
        "specific_heat_ratio": 1.4,
        "target_mach": 0.2,
    }
    r = await client.post(
        "/api/v1/flare/tip",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 422, f"got {r.status_code}: {r.text}"


async def test_flare_tip_endpoint_unauthenticated(client) -> None:
    """POST /flare/tip 缺 auth header → 401/403。"""
    body: dict[str, Any] = {
        "project_id": str(uuid.uuid4()),
        "header_diameter_m": 0.25,
        "mw_kg_kmol": 28.97,
        "tip_temperature_k": 300.0,
        "tip_pressure_pa": 101325.0,
        "specific_heat_ratio": 1.4,
    }
    r = await client.post("/api/v1/flare/tip", json=body)
    assert r.status_code in (401, 403), f"got {r.status_code}: {r.text}"


# ============================================================================
# 2. POST /flare/results — 201 + FlareResultResponse
# ============================================================================


def _create_request_body(**overrides: Any) -> dict[str, Any]:
    """构造合法 FlareResultCreateRequest 主体（可覆盖字段）。"""
    body: dict[str, Any] = {
        "project_id": str(uuid.uuid4()),
        "workspace_id": str(uuid.uuid4()),
        "tag_number": "FL-API-001",
        "standard_profile_code": "API_521",
        "calc_type": "FLARE_TIP",
        "sign_status": "DRAFT",
        # 18 业务字段（ORM 列名平铺）
        "header_diameter_mm": 250.0,
        "header_mach": 0.5,
        "flare_tip_diameter_mm": 250.0,
        "stack_height_m": 30.0,
        "radiation_at_grade_kw_m2": 4.5,
        "radiation_limit_kw_m2": 4.73,
        "pass": True,
        "input_json": {"tip_T": 300, "tip_P": 101325},
        "output_json": {"u_tip": 69.4},
    }
    body.update(overrides)
    return body


async def test_create_flare_result_endpoint_201(client, sample_user_token) -> None:
    """POST /flare/results 合法 body → 201 + FlareResultResponse（record_hash 已设）。"""
    body = _create_request_body()
    r = await client.post(
        "/api/v1/flare/results",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 201, f"got {r.status_code}: {r.text}"
    data = r.json()
    # 顶层字段
    assert "id" in data and data["id"]
    assert data["tag_number"] == "FL-API-001"
    assert data["standard_profile_code"] == "API_521"
    assert data["calc_type"] == "FLARE_TIP"
    assert data["sign_status"] == "DRAFT"
    # record_hash 已 final（ADR-0028 §决策 4）
    assert data["record_hash"] and len(data["record_hash"]) == 16, (
        f"record_hash 应为 16 hex，实际={data['record_hash']!r}"
    )
    # 业务字段 round-trip
    assert data["header_diameter_mm"] == pytest.approx(250.0)
    assert data["flare_tip_diameter_mm"] == pytest.approx(250.0)
    assert data["stack_height_m"] == pytest.approx(30.0)
    assert data["radiation_at_grade_kw_m2"] == pytest.approx(4.5)
    assert data["pass"] is True
    assert data["input_json"] == {"tip_T": 300, "tip_P": 101325}


async def test_create_flare_result_endpoint_422_empty_tag(
    client, sample_user_token
) -> None:
    """POST tag_number='' → 422（service 层 FlarePersistInputError）。"""
    body = _create_request_body(tag_number="")
    r = await client.post(
        "/api/v1/flare/results",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 422, f"got {r.status_code}: {r.text}"


async def test_create_flare_result_endpoint_422_invalid_status(
    client, sample_user_token
) -> None:
    """POST sign_status='NOT_A_STATUS' → 422（enum 解析失败）。"""
    body = _create_request_body(sign_status="NOT_A_STATUS")
    r = await client.post(
        "/api/v1/flare/results",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 422, f"got {r.status_code}: {r.text}"


async def test_create_flare_result_endpoint_unauthenticated(client) -> None:
    """POST /flare/results 缺 auth → 401/403。"""
    body = _create_request_body()
    r = await client.post("/api/v1/flare/results", json=body)
    assert r.status_code in (401, 403), f"got {r.status_code}: {r.text}"


# ============================================================================
# 3. GET /flare/results — 200 + FlareResultListResponse
# ============================================================================


async def test_list_flare_results_endpoint_200(client, sample_user_token) -> None:
    """GET /flare/results?project_id=X → 200 + FlareResultListResponse。

    端到端：先 POST 创建 2 行 → GET list 验证命中 2 行（默认 DRAFT/CHECKED
    filter）。
    """
    project_id = uuid.uuid4()
    # 创建 2 行（相同 project_id / 不同 tag_number）
    for i in range(2):
        body = _create_request_body(
            project_id=str(project_id),
            tag_number=f"FL-LIST-{i}",
        )
        create_r = await client.post(
            "/api/v1/flare/results",
            json=body,
            headers={"Authorization": f"Bearer {sample_user_token}"},
        )
        assert create_r.status_code == 201, create_r.text

    # GET list
    r = await client.get(
        f"/api/v1/flare/results?project_id={project_id}",
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 200, f"got {r.status_code}: {r.text}"
    data = r.json()
    assert "items" in data
    assert data["total"] >= 2
    assert data["limit"] == 100
    assert data["offset"] == 0
    # 应能命中刚创建的 2 行
    tag_numbers = {item["tag_number"] for item in data["items"]}
    assert {"FL-LIST-0", "FL-LIST-1"}.issubset(tag_numbers)


async def test_list_flare_results_endpoint_401(client) -> None:
    """GET /flare/results 缺 auth → 401/403。"""
    r = await client.get(f"/api/v1/flare/results?project_id={uuid.uuid4()}")
    assert r.status_code in (401, 403), f"got {r.status_code}: {r.text}"


# ============================================================================
# 4. GET /flare/results/{id} — 200 / 404
# ============================================================================


async def test_get_flare_result_endpoint_200(client, sample_user_token) -> None:
    """GET /flare/results/{id} 已存在 → 200 + FlareResultResponse。"""
    body = _create_request_body(tag_number="FL-GET-001")
    create_r = await client.post(
        "/api/v1/flare/results",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert create_r.status_code == 201, create_r.text
    rid = create_r.json()["id"]

    r = await client.get(
        f"/api/v1/flare/results/{rid}",
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 200, f"got {r.status_code}: {r.text}"
    data = r.json()
    assert data["id"] == rid
    assert data["tag_number"] == "FL-GET-001"


async def test_get_flare_result_endpoint_404(client, sample_user_token) -> None:
    """GET /flare/results/{不存在 UUID} → 404。"""
    r = await client.get(
        f"/api/v1/flare/results/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 404, f"got {r.status_code}: {r.text}"


# ============================================================================
# 5. PATCH /flare/results/{id} — 200（DRAFT 可改）
# ============================================================================


async def test_update_flare_result_endpoint_200(client, sample_user_token) -> None:
    """PATCH /flare/results/{id} DRAFT 状态 → 200 + FlareResultResponse（字段更新）。"""
    # 创建（DRAFT 默认）
    body = _create_request_body(
        tag_number="FL-PATCH-001",
        stack_height_m=20.0,
    )
    create_r = await client.post(
        "/api/v1/flare/results",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert create_r.status_code == 201, create_r.text
    rid = create_r.json()["id"]

    # PATCH
    patch_body = {"stack_height_m": 35.0, "radiation_at_grade_kw_m2": 3.8}
    r = await client.patch(
        f"/api/v1/flare/results/{rid}",
        json=patch_body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 200, f"got {r.status_code}: {r.text}"
    data = r.json()
    assert data["stack_height_m"] == pytest.approx(35.0)
    assert data["radiation_at_grade_kw_m2"] == pytest.approx(3.8)


async def test_update_flare_result_endpoint_404(client, sample_user_token) -> None:
    """PATCH /flare/results/{不存在 UUID} → 404。"""
    r = await client.patch(
        f"/api/v1/flare/results/{uuid.uuid4()}",
        json={"stack_height_m": 35.0},
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 404, f"got {r.status_code}: {r.text}"


# ============================================================================
# 6. DELETE /flare/results/{id} — 204
# ============================================================================


async def test_delete_flare_result_endpoint_204(client, sample_user_token) -> None:
    """DELETE /flare/results/{id} → 204；后续 GET list 应被 OBSOLETE filter 过滤。"""
    # 创建
    project_id = uuid.uuid4()
    body = _create_request_body(
        project_id=str(project_id),
        tag_number="FL-DEL-001",
    )
    create_r = await client.post(
        "/api/v1/flare/results",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert create_r.status_code == 201, create_r.text
    rid = create_r.json()["id"]

    # DELETE
    r = await client.delete(
        f"/api/v1/flare/results/{rid}",
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 204, f"got {r.status_code}: {r.text}"

    # list 应不命中（OBSOLETE 被默认 filter 过滤）
    list_r = await client.get(
        f"/api/v1/flare/results?project_id={project_id}",
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert list_r.status_code == 200, list_r.text
    ids = [item["id"] for item in list_r.json()["items"]]
    assert rid not in ids, "软删后默认 list filter 应排除 OBSOLETE"


async def test_delete_flare_result_endpoint_404(client, sample_user_token) -> None:
    """DELETE /flare/results/{不存在 UUID} → 404。"""
    r = await client.delete(
        f"/api/v1/flare/results/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 404, f"got {r.status_code}: {r.text}"
