"""P6-3 Task 36 COST_EST API 端点契约测试（SPEC §3.2.8）。

按 SPEC §3.2.8：8 endpoints（3 calc + 5 CRUD）。

设计要点：
- 不 mock 主断言（走真 router + 真 service 层）；client / db fixture
  来自 tests/conftest.py（async httpx + in-memory SQLite）。
- ACL 走 sample_user_token（DESIGNER 角色）。
- 8 endpoints 全覆盖：
    - POST /cost-est/six-tenths-rule/calculate
    - POST /cost-est/cepci-adjustment/calculate
    - POST /cost-est/cost-correlation/calculate
    - POST/GET list/GET detail/PATCH/DELETE on /cost-est/results
- CostEstResult 不含 record_hash / sign_status — 验证时只关注
  result_id + equipment_id + 业务字段（estimated_cost 等）。
- FK 校验：先建一个 EquipmentList 行（in-memory SQLite，metadata.create_all
  会创建完整列集 — 无 pcs_test 库的 P4-0-1 审计列漂移）。
"""
from __future__ import annotations

import uuid
from typing import Any

import pytest

# ============================================================================
# Helpers
# ============================================================================


async def _ensure_equipment(
    db, equipment_id: uuid.UUID, tag_number: str | None = None
) -> None:
    """在 db_session 上预建一个 EquipmentList 行（FK 必填）。

    用 ORM 直构 — 测试用 in-memory SQLite，``metadata.create_all`` 已
    创齐所有列（含 P4-0-1 审计列），与 pcs_test 库漂移无关。
    """
    from app.models.equipment import EquipmentList

    eq = EquipmentList(
        equipment_id=equipment_id,
        type_code="PUMP",
        equipment_name=f"E-{uuid.uuid4().hex[:8]}",
        tag_number=tag_number or f"T-{uuid.uuid4().hex[:8]}",
        project_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
    )
    db.add(eq)
    await db.commit()


# ============================================================================
# 1. POST /cost-est/six-tenths-rule/calculate — 201
# ============================================================================


def _six_tenths_body(equipment_id: uuid.UUID, **overrides: Any) -> dict[str, Any]:
    """构造合法 SixTenthsRuleCalcRequest 主体（可覆盖字段）。"""
    body: dict[str, Any] = {
        "equipment_id": str(equipment_id),
        "reference_cost": 10000.0,
        "reference_cepci": 550.0,
        "target_cepci": 600.0,
        "scaling_exponent": 0.6,
        "estimated_cost": 10909.09,
        "currency": "USD",
        "cost_index_year": 2019,
    }
    body.update(overrides)
    return body


async def test_six_tenths_rule_endpoint_201(
    client, sample_user_token, db
) -> None:
    """POST /six-tenths-rule/calculate 合法 body → 201 + result_id。"""
    equipment_id = uuid.uuid4()
    await _ensure_equipment(db, equipment_id)
    body = _six_tenths_body(equipment_id)
    r = await client.post(
        "/api/v1/cost-est/six-tenths-rule/calculate",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 201, f"got {r.status_code}: {r.text}"
    data = r.json()
    # 顶层字段
    assert "result_id" in data and data["result_id"]
    assert data["equipment_id"] == str(equipment_id)
    # 业务字段 round-trip
    assert data["estimated_cost"] == pytest.approx(10909.09)
    assert data["currency"] == "USD"
    assert data["cost_index_year"] == 2019
    assert data["cepci_index_base"] == pytest.approx(550.0)
    assert data["cepci_index_target"] == pytest.approx(600.0)
    assert data["scaling_exponent"] == pytest.approx(0.6)


async def test_six_tenths_rule_endpoint_404_equipment(
    client, sample_user_token
) -> None:
    """POST /six-tenths-rule/calculate equipment_id 不存在 → 422。"""
    body = _six_tenths_body(uuid.uuid4())
    r = await client.post(
        "/api/v1/cost-est/six-tenths-rule/calculate",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 422, f"got {r.status_code}: {r.text}"


# ============================================================================
# 2. POST /cost-est/cepci-adjustment/calculate — 201
# ============================================================================


def _cepci_body(equipment_id: uuid.UUID, **overrides: Any) -> dict[str, Any]:
    """构造合法 CepciAdjustmentCalcRequest 主体。"""
    body: dict[str, Any] = {
        "equipment_id": str(equipment_id),
        "reference_cost": 10000.0,
        "reference_cepci": 550.0,
        "target_cepci": 600.0,
        "estimated_cost": 10909.09,
        "currency": "USD",
        "cost_index_year": 2019,
    }
    body.update(overrides)
    return body


async def test_cepci_adjustment_endpoint_201(
    client, sample_user_token, db
) -> None:
    """POST /cepci-adjustment/calculate 合法 body → 201 + result_id。"""
    equipment_id = uuid.uuid4()
    await _ensure_equipment(db, equipment_id)
    body = _cepci_body(equipment_id)
    r = await client.post(
        "/api/v1/cost-est/cepci-adjustment/calculate",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 201, f"got {r.status_code}: {r.text}"
    data = r.json()
    assert "result_id" in data and data["result_id"]
    assert data["equipment_id"] == str(equipment_id)
    assert data["cepci_index_base"] == pytest.approx(550.0)
    assert data["cepci_index_target"] == pytest.approx(600.0)


# ============================================================================
# 3. POST /cost-est/cost-correlation/calculate — 201
# ============================================================================


def _cost_correlation_body(
    equipment_id: uuid.UUID, **overrides: Any
) -> dict[str, Any]:
    """构造合法 CostCorrelationCalcRequest 主体。"""
    body: dict[str, Any] = {
        "equipment_id": str(equipment_id),
        "equipment_type": "TOWER",
        "scale_parameter": 2.0,
        "correlation_source": "CC-TOWER-v1",
        "estimated_cost": 15000.0,
        "currency": "USD",
        "cost_index_year": 2019,
    }
    body.update(overrides)
    return body


async def test_cost_correlation_endpoint_201(
    client, sample_user_token, db
) -> None:
    """POST /cost-correlation/calculate 合法 body → 201 + result_id。"""
    equipment_id = uuid.uuid4()
    await _ensure_equipment(db, equipment_id)
    body = _cost_correlation_body(equipment_id)
    r = await client.post(
        "/api/v1/cost-est/cost-correlation/calculate",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 201, f"got {r.status_code}: {r.text}"
    data = r.json()
    assert "result_id" in data and data["result_id"]
    assert data["equipment_id"] == str(equipment_id)
    assert data["correlation_source"] == "CC-TOWER-v1"


# ============================================================================
# 4. POST /cost-est/results — 201 + CostEstResultResponse
# ============================================================================


def _create_request_body(
    equipment_id: uuid.UUID, **overrides: Any
) -> dict[str, Any]:
    """构造合法 CostEstCreateRequest 主体。"""
    body: dict[str, Any] = {
        "equipment_id": str(equipment_id),
        "estimated_cost": 1000.0,
        "currency": "USD",
        "cost_index_year": 2019,
    }
    body.update(overrides)
    return body


async def test_create_cost_est_result_endpoint_201(
    client, sample_user_token, db
) -> None:
    """POST /cost-est/results 合法 body → 201 + CostEstResultResponse。"""
    equipment_id = uuid.uuid4()
    await _ensure_equipment(db, equipment_id)
    body = _create_request_body(equipment_id)
    r = await client.post(
        "/api/v1/cost-est/results",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 201, f"got {r.status_code}: {r.text}"
    data = r.json()
    assert "result_id" in data and data["result_id"]
    assert data["equipment_id"] == str(equipment_id)
    assert data["estimated_cost"] == pytest.approx(1000.0)
    assert data["currency"] == "USD"
    assert data["cost_index_year"] == 2019


async def test_create_cost_est_result_endpoint_401(client, db) -> None:
    """POST /cost-est/results 缺 auth → 401/403。"""
    body = _create_request_body(uuid.uuid4())
    r = await client.post("/api/v1/cost-est/results", json=body)
    assert r.status_code in (401, 403), f"got {r.status_code}: {r.text}"


# ============================================================================
# 5. GET /cost-est/results — 200 + CostEstListResponse
# ============================================================================


async def test_list_cost_est_results_endpoint_200(
    client, sample_user_token, db
) -> None:
    """GET /cost-est/results?equipment_id=X → 200 + 列表。"""
    equipment_id = uuid.uuid4()
    await _ensure_equipment(db, equipment_id)
    # 两条 record（cost_est 1:1 跟 equipment，需要不同 equipment 各自创建）
    equipment_ids = [equipment_id, uuid.uuid4()]
    for eq in equipment_ids:
        if eq != equipment_id:
            await _ensure_equipment(db, eq)
    for eq in equipment_ids:
        body = _create_request_body(eq, estimated_cost=1000.0 + equipment_ids.index(eq))
        create_r = await client.post(
            "/api/v1/cost-est/results",
            json=body,
            headers={"Authorization": f"Bearer {sample_user_token}"},
        )
        assert create_r.status_code == 201, create_r.text

    r = await client.get(
        f"/api/v1/cost-est/results?equipment_id={equipment_id}",
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 200, f"got {r.status_code}: {r.text}"
    data = r.json()
    assert "items" in data
    assert data["total"] >= 1
    assert any(item["equipment_id"] == str(equipment_id) for item in data["items"])


async def test_list_cost_est_results_endpoint_401(client) -> None:
    """GET /cost-est/results 缺 auth → 401/403。"""
    r = await client.get(
        f"/api/v1/cost-est/results?equipment_id={uuid.uuid4()}"
    )
    assert r.status_code in (401, 403), f"got {r.status_code}: {r.text}"


# ============================================================================
# 6. GET /cost-est/results/{id} — 200 / 404
# ============================================================================


async def test_get_cost_est_result_endpoint_200(
    client, sample_user_token, db
) -> None:
    """GET /cost-est/results/{id} 已存在 → 200 + CostEstResultResponse。"""
    equipment_id = uuid.uuid4()
    await _ensure_equipment(db, equipment_id)
    body = _create_request_body(equipment_id)
    create_r = await client.post(
        "/api/v1/cost-est/results",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert create_r.status_code == 201, create_r.text
    rid = create_r.json()["result_id"]

    r = await client.get(
        f"/api/v1/cost-est/results/{rid}",
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 200, f"got {r.status_code}: {r.text}"
    data = r.json()
    assert data["result_id"] == rid
    assert data["equipment_id"] == str(equipment_id)


async def test_get_cost_est_result_endpoint_404(
    client, sample_user_token
) -> None:
    """GET /cost-est/results/{不存在 UUID} → 404。"""
    r = await client.get(
        f"/api/v1/cost-est/results/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 404, f"got {r.status_code}: {r.text}"


# ============================================================================
# 7. PATCH /cost-est/results/{id} — 200（业务字段更新）
# ============================================================================


async def test_update_cost_est_result_endpoint_200(
    client, sample_user_token, db
) -> None:
    """PATCH /cost-est/results/{id} → 200 + 字段更新。"""
    equipment_id = uuid.uuid4()
    await _ensure_equipment(db, equipment_id)
    body = _create_request_body(equipment_id, estimated_cost=1000.0)
    create_r = await client.post(
        "/api/v1/cost-est/results",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert create_r.status_code == 201, create_r.text
    rid = create_r.json()["result_id"]

    patch_body = {"estimated_cost": 99999.0, "currency": "EUR"}
    r = await client.patch(
        f"/api/v1/cost-est/results/{rid}",
        json=patch_body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 200, f"got {r.status_code}: {r.text}"
    data = r.json()
    assert data["estimated_cost"] == pytest.approx(99999.0)
    assert data["currency"] == "EUR"


async def test_update_cost_est_result_endpoint_422_invalid_field(
    client, sample_user_token, db
) -> None:
    """PATCH 含非法字段 → 422 (COST_EST_INVALID_FIELDS)。"""
    equipment_id = uuid.uuid4()
    await _ensure_equipment(db, equipment_id)
    body = _create_request_body(equipment_id)
    create_r = await client.post(
        "/api/v1/cost-est/results",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert create_r.status_code == 201, create_r.text
    rid = create_r.json()["result_id"]

    patch_body = {"unknown_field": 1.0}
    r = await client.patch(
        f"/api/v1/cost-est/results/{rid}",
        json=patch_body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 422, f"got {r.status_code}: {r.text}"


# ============================================================================
# 8. DELETE /cost-est/results/{id} — 200 + CostEstDeleteResponse
# ============================================================================


async def test_soft_delete_cost_est_result_endpoint_200(
    client, sample_user_token, db
) -> None:
    """DELETE /cost-est/results/{id} → 200 + result_id（物理删除）。"""
    equipment_id = uuid.uuid4()
    await _ensure_equipment(db, equipment_id)
    body = _create_request_body(equipment_id)
    create_r = await client.post(
        "/api/v1/cost-est/results",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert create_r.status_code == 201, create_r.text
    rid = create_r.json()["result_id"]

    r = await client.delete(
        f"/api/v1/cost-est/results/{rid}",
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 200, f"got {r.status_code}: {r.text}"
    data = r.json()
    assert data["result_id"] == rid
    assert data["equipment_id"] == str(equipment_id)
    # 删除时间戳
    assert "deleted_at" in data


async def test_soft_delete_cost_est_result_endpoint_404(
    client, sample_user_token
) -> None:
    """DELETE /cost-est/results/{不存在 UUID} → 404。"""
    r = await client.delete(
        f"/api/v1/cost-est/results/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 404, f"got {r.status_code}: {r.text}"