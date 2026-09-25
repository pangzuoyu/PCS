"""P6-3 Task 34 FILTRATION API 端点契约测试（SPEC §3.2.7）。

按 SPEC §3.2.7：8 endpoints（3 calc + 5 CRUD）。

设计要点：
- 不 mock 主断言（走真 router + 真 service 层）；client / db fixture
  来自 tests/conftest.py（async httpx + in-memory SQLite）。
- ACL 走 sample_user_token（DESIGNER 角色）。
- 8 endpoints 全覆盖：
    - POST /ruth-constant-pressure/calculate /ruth-constant-rate/calculate /ergun/calculate
    - POST/GET list/GET detail/PATCH/DELETE on /results
- 错误路径：RuthInputError → 422 / FiltrationPersistInputError → 422
- ACL 负向：sample_user_token 是 DESIGNER；本测试不验证 VIEWER 拒绝
  （conftest 仅暴露 DESIGNER + PC token；ACL 行为已由 cool_tower/flare 覆盖）。
"""
from __future__ import annotations

import uuid
from typing import Any

import pytest

# ============================================================================
# 1. POST /filtration/ruth-constant-pressure/calculate — 201
# ============================================================================


def _ruth_pressure_body(**overrides: Any) -> dict[str, Any]:
    """构造合法 RuthConstantPressureCalcRequest 主体（可覆盖字段）。"""
    body: dict[str, Any] = {
        "project_id": str(uuid.uuid4()),
        "workspace_id": str(uuid.uuid4()),
        "tag_number": "FIL-RP-001",
        "media_type": "SAND",
        "area": 1.0,
        "cycle_time": 1.0,
        "pressure_drop": 1e5,
        "cake_resistance_alpha": 1e10,
        "specific_resistance_r0": 1e10,
    }
    body.update(overrides)
    return body


async def test_ruth_constant_pressure_endpoint_201(
    client, sample_user_token
) -> None:
    """POST /ruth-constant-pressure/calculate 合法 body → 201 + record_hash。"""
    body = _ruth_pressure_body()
    r = await client.post(
        "/api/v1/filtration/ruth-constant-pressure/calculate",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 201, f"got {r.status_code}: {r.text}"
    data = r.json()
    # 顶层字段
    assert "result_id" in data and data["result_id"]
    assert data["tag_number"] == "FIL-RP-001"
    assert data["media_type"] == "SAND"
    assert data["sign_status"] == "DRAFT"
    # record_hash 已 final（ADR-0028 §决策 4）
    assert data["record_hash"] and len(data["record_hash"]) == 16, (
        f"record_hash 应为 16 hex，实际={data['record_hash']!r}"
    )
    # 业务字段 round-trip
    assert data["area"] == pytest.approx(1.0)
    assert data["cycle_time"] == pytest.approx(1.0)
    assert data["pressure_drop"] == pytest.approx(1e5)
    assert data["cake_resistance_alpha"] == pytest.approx(1e10)


async def test_ruth_constant_pressure_endpoint_422_invalid_input(
    client, sample_user_token
) -> None:
    """POST /ruth-constant-pressure/calculate area=0 → 422。"""
    body = _ruth_pressure_body(area=0.0)
    r = await client.post(
        "/api/v1/filtration/ruth-constant-pressure/calculate",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 422, f"got {r.status_code}: {r.text}"


# ============================================================================
# 2. POST /filtration/ruth-constant-rate/calculate — 201
# ============================================================================


def _ruth_rate_body(**overrides: Any) -> dict[str, Any]:
    """构造合法 RuthConstantRateCalcRequest 主体。"""
    body: dict[str, Any] = {
        "project_id": str(uuid.uuid4()),
        "workspace_id": str(uuid.uuid4()),
        "tag_number": "FIL-RR-001",
        "media_type": "ANTHRACITE",
        "area": 1.0,
        "cycle_time": 1.0,
        "pressure_drop": 1e5,
        "filter_velocity": 1e-3,
    }
    body.update(overrides)
    return body


async def test_ruth_constant_rate_endpoint_201(
    client, sample_user_token
) -> None:
    """POST /ruth-constant-rate/calculate 合法 body → 201 + record_hash。"""
    body = _ruth_rate_body()
    r = await client.post(
        "/api/v1/filtration/ruth-constant-rate/calculate",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 201, f"got {r.status_code}: {r.text}"
    data = r.json()
    assert data["tag_number"] == "FIL-RR-001"
    assert data["media_type"] == "ANTHRACITE"
    assert data["record_hash"] and len(data["record_hash"]) == 16


# ============================================================================
# 3. POST /filtration/ergun/calculate — 201
# ============================================================================


def _ergun_body(**overrides: Any) -> dict[str, Any]:
    """构造合法 ErgunCalcRequest 主体。"""
    body: dict[str, Any] = {
        "project_id": str(uuid.uuid4()),
        "workspace_id": str(uuid.uuid4()),
        "tag_number": "FIL-ERG-001",
        "media_type": "ERGUN_PACKING",
        "area": 1.0,
        "cycle_time": 1.0,
        "pressure_drop": 1e3,
        "porosity_eps": 0.4,
        "filter_velocity": 1e-3,
        "permeability_k": 1e-10,
    }
    body.update(overrides)
    return body


async def test_ergun_endpoint_201(client, sample_user_token) -> None:
    """POST /ergun/calculate 合法 body → 201 + record_hash。"""
    body = _ergun_body()
    r = await client.post(
        "/api/v1/filtration/ergun/calculate",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 201, f"got {r.status_code}: {r.text}"
    data = r.json()
    assert data["tag_number"] == "FIL-ERG-001"
    assert data["media_type"] == "ERGUN_PACKING"
    assert data["porosity_eps"] == pytest.approx(0.4)
    assert data["record_hash"] and len(data["record_hash"]) == 16


# ============================================================================
# 4. POST /filtration/results — 201 + FiltrationResultResponse
# ============================================================================


def _create_request_body(**overrides: Any) -> dict[str, Any]:
    """构造合法 FiltrationCreateRequest 主体。"""
    body: dict[str, Any] = {
        "project_id": str(uuid.uuid4()),
        "workspace_id": str(uuid.uuid4()),
        "tag_number": "FIL-CR-001",
        "filter_type": "RUTH_CONST_PRESSURE",
        "media_type": "SAND",
        "area": 1.0,
        "cycle_time": 1.0,
        "pressure_drop": 1e5,
    }
    body.update(overrides)
    return body


async def test_create_filtration_result_endpoint_201(
    client, sample_user_token
) -> None:
    """POST /filtration/results 合法 body → 201 + FiltrationResultResponse。"""
    body = _create_request_body()
    r = await client.post(
        "/api/v1/filtration/results",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 201, f"got {r.status_code}: {r.text}"
    data = r.json()
    assert "result_id" in data and data["result_id"]
    assert data["tag_number"] == "FIL-CR-001"
    assert data["filter_type"] == "RUTH_CONST_PRESSURE"
    assert data["sign_status"] == "DRAFT"
    assert data["record_hash"] and len(data["record_hash"]) == 16


async def test_create_filtration_result_endpoint_401(client) -> None:
    """POST /filtration/results 缺 auth → 401/403。"""
    body = _create_request_body()
    r = await client.post("/api/v1/filtration/results", json=body)
    assert r.status_code in (401, 403), f"got {r.status_code}: {r.text}"


# ============================================================================
# 5. GET /filtration/results — 200 + FiltrationListResponse
# ============================================================================


async def test_list_filtration_results_endpoint_200(
    client, sample_user_token
) -> None:
    """GET /filtration/results?project_id=X → 200 + 列表。"""
    project_id = uuid.uuid4()
    for i in range(2):
        body = _create_request_body(
            project_id=str(project_id), tag_number=f"FIL-LIST-{i}"
        )
        create_r = await client.post(
            "/api/v1/filtration/results",
            json=body,
            headers={"Authorization": f"Bearer {sample_user_token}"},
        )
        assert create_r.status_code == 201, create_r.text

    r = await client.get(
        f"/api/v1/filtration/results?project_id={project_id}",
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 200, f"got {r.status_code}: {r.text}"
    data = r.json()
    assert "items" in data
    assert data["total"] >= 2
    tag_numbers = {item["tag_number"] for item in data["items"]}
    assert {"FIL-LIST-0", "FIL-LIST-1"}.issubset(tag_numbers)


async def test_list_filtration_results_endpoint_401(client) -> None:
    """GET /filtration/results 缺 auth → 401/403。"""
    r = await client.get(
        f"/api/v1/filtration/results?project_id={uuid.uuid4()}"
    )
    assert r.status_code in (401, 403), f"got {r.status_code}: {r.text}"


# ============================================================================
# 6. GET /filtration/results/{id} — 200 / 404
# ============================================================================


async def test_get_filtration_result_endpoint_200(
    client, sample_user_token
) -> None:
    """GET /filtration/results/{id} 已存在 → 200 + FiltrationResultResponse。"""
    body = _create_request_body(tag_number="FIL-GET-001")
    create_r = await client.post(
        "/api/v1/filtration/results",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert create_r.status_code == 201, create_r.text
    rid = create_r.json()["result_id"]

    r = await client.get(
        f"/api/v1/filtration/results/{rid}",
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 200, f"got {r.status_code}: {r.text}"
    data = r.json()
    assert data["result_id"] == rid
    assert data["tag_number"] == "FIL-GET-001"


async def test_get_filtration_result_endpoint_404(
    client, sample_user_token
) -> None:
    """GET /filtration/results/{不存在 UUID} → 404。"""
    r = await client.get(
        f"/api/v1/filtration/results/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 404, f"got {r.status_code}: {r.text}"


# ============================================================================
# 7. PATCH /filtration/results/{id} — 200（DRAFT 可改）
# ============================================================================


async def test_update_filtration_result_endpoint_200(
    client, sample_user_token
) -> None:
    """PATCH /filtration/results/{id} DRAFT 状态 → 200 + 字段更新。"""
    body = _create_request_body(
        tag_number="FIL-PATCH-001",
        area=1.0,
    )
    create_r = await client.post(
        "/api/v1/filtration/results",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert create_r.status_code == 201, create_r.text
    rid = create_r.json()["result_id"]

    patch_body = {"area": 2.5, "pressure_drop": 2e5}
    r = await client.patch(
        f"/api/v1/filtration/results/{rid}",
        json=patch_body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 200, f"got {r.status_code}: {r.text}"
    data = r.json()
    assert data["area"] == pytest.approx(2.5)
    assert data["pressure_drop"] == pytest.approx(2e5)


async def test_update_filtration_result_endpoint_422_invalid_field(
    client, sample_user_token
) -> None:
    """PATCH 含非法字段 → 422 (FILTRATION_INVALID_FIELDS)。"""
    body = _create_request_body(tag_number="FIL-PATCH-INV")
    create_r = await client.post(
        "/api/v1/filtration/results",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert create_r.status_code == 201, create_r.text
    rid = create_r.json()["result_id"]

    patch_body = {"unknown_field": 1.0}
    r = await client.patch(
        f"/api/v1/filtration/results/{rid}",
        json=patch_body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 422, f"got {r.status_code}: {r.text}"


# ============================================================================
# 8. DELETE /filtration/results/{id} — 200 + FiltrationDeleteResponse
# ============================================================================


async def test_soft_delete_filtration_result_endpoint_200(
    client, sample_user_token
) -> None:
    """DELETE /filtration/results/{id} → 200 + tag_number 加 __OBSOLETE_ 后缀。"""
    body = _create_request_body(tag_number="FIL-DEL-001")
    create_r = await client.post(
        "/api/v1/filtration/results",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert create_r.status_code == 201, create_r.text
    rid = create_r.json()["result_id"]

    r = await client.delete(
        f"/api/v1/filtration/results/{rid}",
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 200, f"got {r.status_code}: {r.text}"
    data = r.json()
    assert data["result_id"] == rid
    assert "__OBSOLETE_" in data["tag_number"]
    assert data["sign_status"] == "OBSOLETE"


async def test_soft_delete_filtration_result_endpoint_404(
    client, sample_user_token
) -> None:
    """DELETE /filtration/results/{不存在 UUID} → 404。"""
    r = await client.delete(
        f"/api/v1/filtration/results/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 404, f"got {r.status_code}: {r.text}"