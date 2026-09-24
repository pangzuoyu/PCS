"""P6-3 Task 32 OPEN_CHANNEL API 端点契约测试（SPEC §3.2.6）。

按 SPEC §3.2.6 P6-OPEN-001：9 endpoints（4 calc + 5 CRUD）。

设计要点：
- 不 mock 主断言（走真 router + 真 service 层）；client / db fixture
  来自 tests/conftest.py（async httpx + in-memory SQLite）。
- ACL 走 sample_user_token（DESIGNER 角色）。
- 9 endpoints 全覆盖：
    - POST /manning/calculate /section/calculate /critical/calculate /jump/calculate
    - POST/GET list/GET detail/PATCH/DELETE on /results
- 错误路径：ManningInputError → 422 / OpenChannelPersistInputError → 422
- ACL 负向：sample_user_token 是 DESIGNER；本测试不验证 VIEWER 拒绝
  （conftest 仅暴露 DESIGNER + PC token；ACL 行为已由 cool_tower/flare 覆盖）。
"""
from __future__ import annotations

import uuid
from typing import Any

import pytest

# ============================================================================
# 1. POST /open-channel/manning/calculate — 200 + ManningCalcResponse
# ============================================================================


def _manning_body(**overrides: Any) -> dict[str, Any]:
    """构造合法 ManningCalcRequest 主体（可覆盖字段）。"""
    body: dict[str, Any] = {
        "project_id": str(uuid.uuid4()),
        "workspace_id": str(uuid.uuid4()),
        "tag_number": "OC-M-001",
        "channel_type": "RECT",
        "cross_section_json": {"bottom_width": 2.0},
        "flow_rate": 3.0649,
        "depth": 1.0,
        "velocity": 1.5325,
        "slope": 0.001,
        "manning_n": 0.013,
    }
    body.update(overrides)
    return body


async def test_manning_endpoint_201(client, sample_user_token) -> None:
    """POST /manning/calculate 合法 body → 201 + ManningCalcResponse（record_hash 已设）。"""
    body = _manning_body()
    r = await client.post(
        "/api/v1/open-channel/manning/calculate",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 201, f"got {r.status_code}: {r.text}"
    data = r.json()
    # 顶层字段
    assert "result_id" in data and data["result_id"]
    assert data["tag_number"] == "OC-M-001"
    assert data["channel_type"] == "RECT"
    assert data["sign_status"] == "DRAFT"
    # record_hash 已 final（ADR-0028 §决策 4）
    assert data["record_hash"] and len(data["record_hash"]) == 16, (
        f"record_hash 应为 16 hex，实际={data['record_hash']!r}"
    )
    # 业务字段 round-trip（calc 派生值）
    assert data["flow_rate"] == pytest.approx(3.0648, abs=1e-3)
    assert data["depth"] == pytest.approx(1.0)
    assert data["slope"] == pytest.approx(0.001)
    assert data["hydraulic_radius"] == pytest.approx(0.5)


async def test_manning_endpoint_422_invalid_input(client, sample_user_token) -> None:
    """POST /manning/calculate slope=0 → 422（ManningInputError）。"""
    body = _manning_body(slope=0.0)
    r = await client.post(
        "/api/v1/open-channel/manning/calculate",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 422, f"got {r.status_code}: {r.text}"


# ============================================================================
# 2. POST /open-channel/section/calculate — 201
# ============================================================================


def _section_body(**overrides: Any) -> dict[str, Any]:
    """构造合法 SectionCalcRequest 主体。"""
    body: dict[str, Any] = {
        "project_id": str(uuid.uuid4()),
        "workspace_id": str(uuid.uuid4()),
        "tag_number": "OC-S-001",
        "channel_type": "RECT",
        "cross_section_json": {"bottom_width": 2.0},
        "flow_rate": 2.0,
        "depth": 0.8522,
        "velocity": 1.0,
        "slope": 0.001,
        "manning_n": 0.013,
    }
    body.update(overrides)
    return body


async def test_section_endpoint_201(client, sample_user_token) -> None:
    """POST /section/calculate 合法 body → 201 + record_hash。"""
    body = _section_body()
    r = await client.post(
        "/api/v1/open-channel/section/calculate",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 201, f"got {r.status_code}: {r.text}"
    data = r.json()
    assert data["tag_number"] == "OC-S-001"
    assert data["record_hash"] and len(data["record_hash"]) == 16


# ============================================================================
# 3. POST /open-channel/critical/calculate — 201
# ============================================================================


def _critical_body(**overrides: Any) -> dict[str, Any]:
    """构造合法 CriticalCalcRequest 主体。"""
    body: dict[str, Any] = {
        "project_id": str(uuid.uuid4()),
        "workspace_id": str(uuid.uuid4()),
        "tag_number": "OC-C-001",
        "channel_type": "RECT",
        "cross_section_json": {"bottom_width": 2.0},
        "flow_rate": 2.0,
        "depth": 1.0,
        "velocity": 1.0,
        "slope": 0.001,
        "manning_n": 0.013,
    }
    body.update(overrides)
    return body


async def test_critical_endpoint_201(client, sample_user_token) -> None:
    """POST /critical/calculate → 201 + critical_depth / froude_number 派生。"""
    body = _critical_body()
    r = await client.post(
        "/api/v1/open-channel/critical/calculate",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 201, f"got {r.status_code}: {r.text}"
    data = r.json()
    assert data["critical_depth"] is not None
    assert data["froude_number"] is not None
    assert data["critical_depth"] == pytest.approx(0.4666, abs=1e-3)


# ============================================================================
# 4. POST /open-channel/jump/calculate — 201
# ============================================================================


def _jump_body(**overrides: Any) -> dict[str, Any]:
    """构造合法 JumpCalcRequest 主体。"""
    body: dict[str, Any] = {
        "project_id": str(uuid.uuid4()),
        "workspace_id": str(uuid.uuid4()),
        "tag_number": "OC-J-001",
        "channel_type": "RECT",
        "cross_section_json": {"bottom_width": 2.0},
        "flow_rate": 10.0,
        "depth": 0.5,
        "velocity": 5.0,
        "slope": 0.001,
    }
    body.update(overrides)
    return body


async def test_jump_endpoint_201(client, sample_user_token) -> None:
    """POST /jump/calculate → 201 + jump_type / conjugate_depth / energy_loss。"""
    body = _jump_body()
    r = await client.post(
        "/api/v1/open-channel/jump/calculate",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 201, f"got {r.status_code}: {r.text}"
    data = r.json()
    assert data["jump_type"] == "WEAK"
    assert data["conjugate_depth"] is not None
    assert data["energy_loss"] is not None
    assert data["conjugate_depth"] == pytest.approx(1.366, abs=1e-2)


# ============================================================================
# 5. POST /open-channel/results — 201 + OpenChannelResultResponse
# ============================================================================


def _create_request_body(**overrides: Any) -> dict[str, Any]:
    """构造合法 OpenChannelCreateRequest 主体。"""
    body: dict[str, Any] = {
        "project_id": str(uuid.uuid4()),
        "workspace_id": str(uuid.uuid4()),
        "tag_number": "OC-CR-001",
        "channel_type": "RECT",
        "cross_section_json": {"bottom_width": 2.0},
        "flow_rate": 1.0,
        "depth": 1.0,
        "velocity": 1.0,
        "slope": 0.001,
        "manning_n": 0.013,
    }
    body.update(overrides)
    return body


async def test_create_open_channel_result_endpoint_201(
    client, sample_user_token
) -> None:
    """POST /open-channel/results 合法 body → 201 + OpenChannelResultResponse。"""
    body = _create_request_body()
    r = await client.post(
        "/api/v1/open-channel/results",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 201, f"got {r.status_code}: {r.text}"
    data = r.json()
    assert "result_id" in data and data["result_id"]
    assert data["tag_number"] == "OC-CR-001"
    assert data["channel_type"] == "RECT"
    assert data["sign_status"] == "DRAFT"
    assert data["record_hash"] and len(data["record_hash"]) == 16


async def test_create_open_channel_result_endpoint_401(client) -> None:
    """POST /open-channel/results 缺 auth → 401/403。"""
    body = _create_request_body()
    r = await client.post("/api/v1/open-channel/results", json=body)
    assert r.status_code in (401, 403), f"got {r.status_code}: {r.text}"


# ============================================================================
# 6. GET /open-channel/results — 200 + OpenChannelListResponse
# ============================================================================


async def test_list_open_channel_results_endpoint_200(
    client, sample_user_token
) -> None:
    """GET /open-channel/results?project_id=X → 200 + 列表。"""
    project_id = uuid.uuid4()
    for i in range(2):
        body = _create_request_body(
            project_id=str(project_id), tag_number=f"OC-LIST-{i}"
        )
        create_r = await client.post(
            "/api/v1/open-channel/results",
            json=body,
            headers={"Authorization": f"Bearer {sample_user_token}"},
        )
        assert create_r.status_code == 201, create_r.text

    r = await client.get(
        f"/api/v1/open-channel/results?project_id={project_id}",
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 200, f"got {r.status_code}: {r.text}"
    data = r.json()
    assert "items" in data
    assert data["total"] >= 2
    tag_numbers = {item["tag_number"] for item in data["items"]}
    assert {"OC-LIST-0", "OC-LIST-1"}.issubset(tag_numbers)


async def test_list_open_channel_results_endpoint_401(client) -> None:
    """GET /open-channel/results 缺 auth → 401/403。"""
    r = await client.get(
        f"/api/v1/open-channel/results?project_id={uuid.uuid4()}"
    )
    assert r.status_code in (401, 403), f"got {r.status_code}: {r.text}"


# ============================================================================
# 7. GET /open-channel/results/{id} — 200 / 404
# ============================================================================


async def test_get_open_channel_result_endpoint_200(
    client, sample_user_token
) -> None:
    """GET /open-channel/results/{id} 已存在 → 200 + OpenChannelResultResponse。"""
    body = _create_request_body(tag_number="OC-GET-001")
    create_r = await client.post(
        "/api/v1/open-channel/results",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert create_r.status_code == 201, create_r.text
    rid = create_r.json()["result_id"]

    r = await client.get(
        f"/api/v1/open-channel/results/{rid}",
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 200, f"got {r.status_code}: {r.text}"
    data = r.json()
    assert data["result_id"] == rid
    assert data["tag_number"] == "OC-GET-001"


async def test_get_open_channel_result_endpoint_404(
    client, sample_user_token
) -> None:
    """GET /open-channel/results/{不存在 UUID} → 404。"""
    r = await client.get(
        f"/api/v1/open-channel/results/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 404, f"got {r.status_code}: {r.text}"


# ============================================================================
# 8. PATCH /open-channel/results/{id} — 200（DRAFT 可改）
# ============================================================================


async def test_update_open_channel_result_endpoint_200(
    client, sample_user_token
) -> None:
    """PATCH /open-channel/results/{id} DRAFT 状态 → 200 + 字段更新。"""
    body = _create_request_body(
        tag_number="OC-PATCH-001",
        depth=1.0,
    )
    create_r = await client.post(
        "/api/v1/open-channel/results",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert create_r.status_code == 201, create_r.text
    rid = create_r.json()["result_id"]

    patch_body = {"depth": 2.5, "velocity": 2.0}
    r = await client.patch(
        f"/api/v1/open-channel/results/{rid}",
        json=patch_body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 200, f"got {r.status_code}: {r.text}"
    data = r.json()
    assert data["depth"] == pytest.approx(2.5)
    assert data["velocity"] == pytest.approx(2.0)


async def test_update_open_channel_result_endpoint_422_invalid_field(
    client, sample_user_token
) -> None:
    """PATCH 含非法字段 → 422 (OPEN_CHANNEL_INVALID_FIELDS)。"""
    body = _create_request_body(tag_number="OC-PATCH-INV")
    create_r = await client.post(
        "/api/v1/open-channel/results",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert create_r.status_code == 201, create_r.text
    rid = create_r.json()["result_id"]

    patch_body = {"unknown_field": 1.0}
    r = await client.patch(
        f"/api/v1/open-channel/results/{rid}",
        json=patch_body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 422, f"got {r.status_code}: {r.text}"


# ============================================================================
# 9. DELETE /open-channel/results/{id} — 200 + OpenChannelDeleteResponse
# ============================================================================


async def test_soft_delete_open_channel_result_endpoint_200(
    client, sample_user_token
) -> None:
    """DELETE /open-channel/results/{id} → 200 + tag_number 加 __OBSOLETE_ 后缀。"""
    body = _create_request_body(tag_number="OC-DEL-001")
    create_r = await client.post(
        "/api/v1/open-channel/results",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert create_r.status_code == 201, create_r.text
    rid = create_r.json()["result_id"]

    r = await client.delete(
        f"/api/v1/open-channel/results/{rid}",
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 200, f"got {r.status_code}: {r.text}"
    data = r.json()
    assert data["result_id"] == rid
    assert "__OBSOLETE_" in data["tag_number"]
    assert data["sign_status"] == "OBSOLETE"


async def test_soft_delete_open_channel_result_endpoint_404(
    client, sample_user_token
) -> None:
    """DELETE /open-channel/results/{不存在 UUID} → 404。"""
    r = await client.delete(
        f"/api/v1/open-channel/results/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 404, f"got {r.status_code}: {r.text}"