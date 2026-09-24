"""P6-2 Task 26 PSYCHRO API 端点契约测试。

按 SPEC §3.2.5 P6-PSY-001 + §3.2.3 P6-FLR-004：
- 6 calc endpoints × (200 happy + 422 invalid) = 12 例
  → humidity-ratio / dew-point / wet-bulb / enthalpy / specific-volume /
    cooling-coil
- CRUD /api/v1/psychro/results → 201/200/200/200/204（端到端真 router
  + 真 service，session 走 in-memory SQLite 与全局 client/db fixtures
  联调）

设计要点：
- 不 mock 主断言（走真 router + 真 service 层）；client / db fixture
  来自 tests/conftest.py（async httpx + in-memory SQLite）。
- ACL 走 sample_user_token（DESIGNER 角色）。
- 不依赖真实 psychro_results 表（SQLite 全表建；PsychroResult 已通过
  Base.metadata 全表创建）。
- 6 calc endpoint 直调 chedl_wrapper → 端到端真 CoolProp 包装
  （包装层 ImportError 已被 chedl_wrapper 顶层 PcsError(503) 守住；
  若 dev 环境 CoolProp 不可用，跳过 calc happy 例）。
"""
from __future__ import annotations

import uuid
from typing import Any

import pytest

# ============================================================================
# 共用 helper：构造 POST /psychro/results 合法 body
# ============================================================================


def _create_request_body(**overrides: Any) -> dict[str, Any]:
    """构造 POST /psychro/results 合法 body。"""
    body: dict[str, Any] = {
        "project_id": str(uuid.uuid4()),
        "workspace_id": str(uuid.uuid4()),
        "tag_number": "PSY-API-001",
        "standard_profile_code": "ASHRAE_FUND_2021",
        "calc_type": "HUMIDITY_RATIO",
        "sign_status": "DRAFT",
        # 12 业务字段（payload 故意不传 coolprop_version 以验证自动填）
        "humidity_ratio_kg_kg": 0.00993,
        "dew_point_c": 13.87,
        "wet_bulb_c": 17.88,
        "enthalpy_kj_kg": 50.423,
        "specific_volume_m3_kg": 0.858,
        "input_json": {"t_c": 25.0, "rh": 0.5, "p_pa": 101325.0},
        "output_json": {"humidity_ratio_kg_kg": 0.00993},
    }
    body.update(overrides)
    return body


# ============================================================================
# 1. POST /psychro/humidity-ratio — 200 / 422 / 401
# ============================================================================


async def test_humidity_ratio_endpoint_200(
    client, sample_user_token
) -> None:
    """POST /psychro/humidity-ratio 合法 body → 200 + HumidityRatioResponse。

    T=25°C, RH=0.5, P=101325（ASHRAE Psychrometric Chart 参考值）：
    W ≈ 0.00993 kg/kg dry air。
    """
    body: dict[str, Any] = {
        "t_c": 25.0,
        "rh": 0.5,
        "p_pa": 101325.0,
    }
    r = await client.post(
        "/api/v1/psychro/humidity-ratio",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 200, f"got {r.status_code}: {r.text}"
    data = r.json()
    assert data["humidity_ratio_kg_kg"] == pytest.approx(0.00993, abs=1e-4)
    assert data["formula_ref"] == "ASHRAE_RP-1845_CoolProp"


async def test_humidity_ratio_endpoint_422_invalid_rh(
    client, sample_user_token
) -> None:
    """POST RH=1.5 (out of range) → 422（chedl_wrapper ValueError）。"""
    body: dict[str, Any] = {
        "t_c": 25.0,
        "rh": 1.5,  # 超出 [0, 1]
        "p_pa": 101325.0,
    }
    r = await client.post(
        "/api/v1/psychro/humidity-ratio",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 422, f"got {r.status_code}: {r.text}"


async def test_humidity_ratio_endpoint_unauthenticated(client) -> None:
    """POST 缺 auth → 401/403。"""
    body: dict[str, Any] = {
        "t_c": 25.0,
        "rh": 0.5,
        "p_pa": 101325.0,
    }
    r = await client.post("/api/v1/psychro/humidity-ratio", json=body)
    assert r.status_code in (401, 403), f"got {r.status_code}: {r.text}"


# ============================================================================
# 2. POST /psychro/dew-point — 200 / 422
# ============================================================================


async def test_dew_point_endpoint_200(client, sample_user_token) -> None:
    """POST /psychro/dew-point 合法 body → 200 + DewPointResponse。

    T=25°C, RH=0.5, P=101325 → D ≈ 13.87°C（CoolProp 6.6.0 自洽生成）。
    """
    body: dict[str, Any] = {
        "t_c": 25.0,
        "rh": 0.5,
        "p_pa": 101325.0,
    }
    r = await client.post(
        "/api/v1/psychro/dew-point",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 200, f"got {r.status_code}: {r.text}"
    data = r.json()
    assert data["dew_point_c"] == pytest.approx(13.87, abs=0.1)
    assert data["formula_ref"] == "ASHRAE_RP-1845_CoolProp"


async def test_dew_point_endpoint_422_invalid_p(
    client, sample_user_token
) -> None:
    """POST p_pa=-100 (非正) → 422。"""
    body: dict[str, Any] = {
        "t_c": 25.0,
        "rh": 0.5,
        "p_pa": -100.0,
    }
    r = await client.post(
        "/api/v1/psychro/dew-point",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 422, f"got {r.status_code}: {r.text}"


# ============================================================================
# 3. POST /psychro/wet-bulb — 200 / 422
# ============================================================================


async def test_wet_bulb_endpoint_200(client, sample_user_token) -> None:
    """POST /psychro/wet-bulb 合法 body → 200 + WetBulbResponse。

    T=25°C, RH=0.5, P=101325 → B ≈ 17.88°C（CoolProp 6.6.0）。
    """
    body: dict[str, Any] = {
        "t_c": 25.0,
        "rh": 0.5,
        "p_pa": 101325.0,
    }
    r = await client.post(
        "/api/v1/psychro/wet-bulb",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 200, f"got {r.status_code}: {r.text}"
    data = r.json()
    assert data["wet_bulb_c"] == pytest.approx(17.88, abs=0.1)
    assert data["formula_ref"] == "ASHRAE_RP-1845_CoolProp"


async def test_wet_bulb_endpoint_422_invalid_rh(
    client, sample_user_token
) -> None:
    """POST rh=-0.1 (out of range) → 422。"""
    body: dict[str, Any] = {
        "t_c": 25.0,
        "rh": -0.1,
        "p_pa": 101325.0,
    }
    r = await client.post(
        "/api/v1/psychro/wet-bulb",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 422, f"got {r.status_code}: {r.text}"


# ============================================================================
# 4. POST /psychro/enthalpy — 200 / 422
# ============================================================================


async def test_enthalpy_endpoint_200(client, sample_user_token) -> None:
    """POST /psychro/enthalpy 合法 body → 200 + EnthalpyResponse。

    T=25°C, RH=0.5, P=101325 → H ≈ 50.423 kJ/kg dry air（CoolProp 6.6.0）。
    """
    body: dict[str, Any] = {
        "t_c": 25.0,
        "rh": 0.5,
        "p_pa": 101325.0,
    }
    r = await client.post(
        "/api/v1/psychro/enthalpy",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 200, f"got {r.status_code}: {r.text}"
    data = r.json()
    assert data["enthalpy_kj_kg"] == pytest.approx(50.423, abs=0.1)
    assert data["formula_ref"] == "ASHRAE_RP-1845_CoolProp"


async def test_enthalpy_endpoint_422_invalid_p(
    client, sample_user_token
) -> None:
    """POST p_pa=0 (≤0) → 422。"""
    body: dict[str, Any] = {
        "t_c": 25.0,
        "rh": 0.5,
        "p_pa": 0.0,
    }
    r = await client.post(
        "/api/v1/psychro/enthalpy",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 422, f"got {r.status_code}: {r.text}"


# ============================================================================
# 5. POST /psychro/specific-volume — 200 / 422
# ============================================================================


async def test_specific_volume_endpoint_200(
    client, sample_user_token
) -> None:
    """POST /psychro/specific-volume 合法 body → 200 + SpecificVolumeResponse。

    T=25°C, RH=0.5, P=101325 → V ≈ 0.858 m³/kg dry air（CoolProp 6.6.0）。
    """
    body: dict[str, Any] = {
        "t_c": 25.0,
        "rh": 0.5,
        "p_pa": 101325.0,
    }
    r = await client.post(
        "/api/v1/psychro/specific-volume",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 200, f"got {r.status_code}: {r.text}"
    data = r.json()
    assert data["specific_volume_m3_kg"] == pytest.approx(0.858, abs=0.01)
    assert data["formula_ref"] == "ASHRAE_RP-1845_CoolProp"


async def test_specific_volume_endpoint_422_invalid_t(
    client, sample_user_token
) -> None:
    """POST t_c=-300 (低于绝对零度) → 422（schema gt=-273.15 校验）。"""
    body: dict[str, Any] = {
        "t_c": -300.0,
        "rh": 0.5,
        "p_pa": 101325.0,
    }
    r = await client.post(
        "/api/v1/psychro/specific-volume",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 422, f"got {r.status_code}: {r.text}"


# ============================================================================
# 6. POST /psychro/cooling-coil — 200 / 422
# ============================================================================


async def test_cooling_coil_endpoint_200(client, sample_user_token) -> None:
    """POST /psychro/cooling-coil 合法 body → 200 + CoolingCoilResponse。

    T1=27°C, RH1=0.5 → T2=13°C, RH2=0.95, P=101325, q=10 m³/s：
    ASHRAE HF2021 §1.2 拆分 — 显热 + 潜热均正（冷却除湿典型）。
    """
    body: dict[str, Any] = {
        "t1_c": 27.0,
        "rh1": 0.5,
        "t2_c": 13.0,
        "rh2": 0.95,
        "p_pa": 101325.0,
        "q_air_m3_s": 10.0,
    }
    r = await client.post(
        "/api/v1/psychro/cooling-coil",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 200, f"got {r.status_code}: {r.text}"
    data = r.json()
    # 显热 + 潜热均应为正（冷却除湿场景）
    assert data["sensible_heat_kw"] > 0
    assert data["latent_heat_kw"] > 0
    assert data["formula_ref"] == "ASHRAE_HF2021_§1.2"


async def test_cooling_coil_endpoint_422_negative_flow(
    client, sample_user_token
) -> None:
    """POST q_air_m3_s=-1 (≤0) → 422。"""
    body: dict[str, Any] = {
        "t1_c": 27.0,
        "rh1": 0.5,
        "t2_c": 13.0,
        "rh2": 0.95,
        "p_pa": 101325.0,
        "q_air_m3_s": -1.0,
    }
    r = await client.post(
        "/api/v1/psychro/cooling-coil",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 422, f"got {r.status_code}: {r.text}"


# ============================================================================
# 7. CRUD /psychro/results
# ============================================================================


async def test_create_psychro_result_endpoint_201(
    client, sample_user_token
) -> None:
    """POST /psychro/results 合法 body → 201 + PsychroResultResponse
    （record_hash 已设 + coolprop_version 自动填）。"""
    body = _create_request_body()
    r = await client.post(
        "/api/v1/psychro/results",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 201, f"got {r.status_code}: {r.text}"
    data = r.json()
    # 顶层字段
    assert "id" in data and data["id"]
    assert data["tag_number"] == "PSY-API-001"
    assert data["standard_profile_code"] == "ASHRAE_FUND_2021"
    assert data["calc_type"] == "HUMIDITY_RATIO"
    assert data["sign_status"] == "DRAFT"
    # record_hash 已 final（ADR-0028 §决策 4）
    assert data["record_hash"] and len(data["record_hash"]) == 16, (
        f"record_hash 应为 16 hex，实际={data['record_hash']!r}"
    )
    # coolprop_version 自动填（payload 未传）
    assert data["coolprop_version"] is not None
    assert isinstance(data["coolprop_version"], str)
    assert data["coolprop_version"] != ""
    # 业务字段 round-trip
    assert data["humidity_ratio_kg_kg"] == pytest.approx(0.00993, abs=1e-6)
    assert data["enthalpy_kj_kg"] == pytest.approx(50.423, abs=1e-6)
    assert data["input_json"] == {
        "t_c": 25.0,
        "rh": 0.5,
        "p_pa": 101325.0,
    }


async def test_create_psychro_result_endpoint_422_empty_tag(
    client, sample_user_token
) -> None:
    """POST tag_number='' → 422（service 层 PsychroPersistInputError）。"""
    body = _create_request_body(tag_number="")
    r = await client.post(
        "/api/v1/psychro/results",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 422, f"got {r.status_code}: {r.text}"


async def test_create_psychro_result_endpoint_unauthenticated(
    client,
) -> None:
    """POST /psychro/results 缺 auth → 401/403。"""
    body = _create_request_body()
    r = await client.post("/api/v1/psychro/results", json=body)
    assert r.status_code in (401, 403), f"got {r.status_code}: {r.text}"


async def test_list_psychro_results_endpoint_200(
    client, sample_user_token
) -> None:
    """GET /psychro/results?project_id=X → 200 + PsychroResultListResponse。

    端到端：先 POST 创建 2 行 → GET list 验证命中 2 行（默认 DRAFT/CHECKED
    filter）。
    """
    project_id = uuid.uuid4()
    for i in range(2):
        body = _create_request_body(
            project_id=str(project_id), tag_number=f"PSY-LIST-{i}"
        )
        create_r = await client.post(
            "/api/v1/psychro/results",
            json=body,
            headers={"Authorization": f"Bearer {sample_user_token}"},
        )
        assert create_r.status_code == 201, create_r.text

    r = await client.get(
        f"/api/v1/psychro/results?project_id={project_id}",
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 200, f"got {r.status_code}: {r.text}"
    data = r.json()
    assert "items" in data
    assert data["total"] >= 2
    assert data["limit"] == 100
    assert data["offset"] == 0
    tag_numbers = {item["tag_number"] for item in data["items"]}
    assert {"PSY-LIST-0", "PSY-LIST-1"}.issubset(tag_numbers)


async def test_get_psychro_result_endpoint_200(
    client, sample_user_token
) -> None:
    """GET /psychro/results/{id} 已存在 → 200 + PsychroResultResponse。"""
    body = _create_request_body(tag_number="PSY-GET-001")
    create_r = await client.post(
        "/api/v1/psychro/results",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert create_r.status_code == 201, create_r.text
    rid = create_r.json()["id"]

    r = await client.get(
        f"/api/v1/psychro/results/{rid}",
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 200, f"got {r.status_code}: {r.text}"
    data = r.json()
    assert data["id"] == rid
    assert data["tag_number"] == "PSY-GET-001"


async def test_get_psychro_result_endpoint_404(
    client, sample_user_token
) -> None:
    """GET /psychro/results/{不存在 UUID} → 404。"""
    r = await client.get(
        f"/api/v1/psychro/results/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 404, f"got {r.status_code}: {r.text}"


async def test_update_psychro_result_endpoint_200(
    client, sample_user_token
) -> None:
    """PATCH /psychro/results/{id} DRAFT 状态 → 200 + 字段更新。"""
    body = _create_request_body(tag_number="PSY-PATCH-001", enthalpy_kj_kg=20.0)
    create_r = await client.post(
        "/api/v1/psychro/results",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert create_r.status_code == 201, create_r.text
    rid = create_r.json()["id"]

    patch_body = {"humidity_ratio_kg_kg": 0.012, "enthalpy_kj_kg": 35.5}
    r = await client.patch(
        f"/api/v1/psychro/results/{rid}",
        json=patch_body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 200, f"got {r.status_code}: {r.text}"
    data = r.json()
    assert data["humidity_ratio_kg_kg"] == pytest.approx(0.012)
    assert data["enthalpy_kj_kg"] == pytest.approx(35.5)


async def test_delete_psychro_result_endpoint_204(
    client, sample_user_token
) -> None:
    """DELETE /psychro/results/{id} → 204；后续 GET list 应被 OBSOLETE
    filter 过滤。"""
    project_id = uuid.uuid4()
    body = _create_request_body(
        project_id=str(project_id), tag_number="PSY-DEL-001"
    )
    create_r = await client.post(
        "/api/v1/psychro/results",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert create_r.status_code == 201, create_r.text
    rid = create_r.json()["id"]

    r = await client.delete(
        f"/api/v1/psychro/results/{rid}",
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 204, f"got {r.status_code}: {r.text}"

    # list 应不命中（OBSOLETE 被默认 filter 过滤）
    list_r = await client.get(
        f"/api/v1/psychro/results?project_id={project_id}",
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert list_r.status_code == 200, list_r.text
    ids = [item["id"] for item in list_r.json()["items"]]
    assert rid not in ids, "软删后默认 list filter 应排除 OBSOLETE"
