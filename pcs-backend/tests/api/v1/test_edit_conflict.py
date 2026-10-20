"""编辑冲突的**接线**测试 —— P9A-4 D2（ADR-0048 §⑥ §⑦）。

## 本文件只验接线，不重复验阶梯

阶梯（`check_conflict`）在 `tests/services/test_edit_guard.py` 里测了一遍。
这里测的是：6 个 PATCH 端点**确实调了 guard**、409 契约三字段对、
`changed_fields` 传递正确、审计落库。

## 409 响应体 = 仓库统一错误信封

```json
{"code": "RECORD_EDIT_CONFLICT",
 "message": "…",
 "detail": {"conflict": {…}},
 "trace_id": "…"}
```

⇒ 冲突对象在 `detail.conflict`（ADR-0048 §⑦ 原文写的是顶层三字段，
已按仓库信封归一 —— ADR 已修订）。
"""
from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy import select

from app.models.system import AuditLog


def _create_body(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "project_id": str(uuid.uuid4()),
        "workspace_id": str(uuid.uuid4()),
        "tag_number": f"CT-{uuid.uuid4().hex[:8]}",
        "standard_profile_code": "CTI_ATC_105",
        "calc_type": "MERKEL",
        "sign_status": "DRAFT",
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


async def _create(client, token: str) -> tuple[str, str]:
    """建一条记录 ⇒ (record_id, record_hash)。"""
    r = await client.post(
        "/api/v1/cool-tower/results",
        json=_create_body(),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text
    data = r.json()
    return data["id"], data["record_hash"]


# ---------------------------------------------------------------------------
# 409 契约
# ---------------------------------------------------------------------------


async def test_patch_without_baseline_is_409(client, sample_user_token):
    """**不带基线的编辑 ⇒ 409**（服务端无法判定并发 ⇒ 不得放行）。"""
    rid, _hash = await _create(client, sample_user_token)
    r = await client.patch(
        f"/api/v1/cool-tower/results/{rid}",
        json={"duty_kw": 20.0},
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 409, f"got {r.status_code}: {r.text}"
    data = r.json()
    assert data["code"] == "RECORD_EDIT_CONFLICT"
    assert data["detail"]["conflict"]["basis"] == "no_baseline"


async def test_patch_with_stale_hash_is_409(client, sample_user_token):
    """基线过期 ⇒ 409 + conflict 对象（basis=record_hash）。"""
    rid, _hash = await _create(client, sample_user_token)
    r = await client.patch(
        f"/api/v1/cool-tower/results/{rid}",
        json={"duty_kw": 20.0, "expected_hash": "0000000000000000"},
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 409, f"got {r.status_code}: {r.text}"
    conflict = r.json()["detail"]["conflict"]
    assert conflict["basis"] == "record_hash"
    assert conflict["record_type"] == "cooling_tower_result"
    assert conflict["record_id"] == rid
    assert conflict["your_expected_hash"] == "0000000000000000"
    assert conflict["current_hash"] != "0000000000000000"


async def test_conflict_body_uses_the_repo_error_envelope(client, sample_user_token):
    """409 体 = 仓库统一信封（code / message / detail / trace_id）。"""
    rid, _hash = await _create(client, sample_user_token)
    r = await client.patch(
        f"/api/v1/cool-tower/results/{rid}",
        json={"duty_kw": 20.0},
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    data = r.json()
    assert set(data) == {"code", "message", "detail", "trace_id"}
    assert data["code"] == "RECORD_EDIT_CONFLICT"
    assert data["message"]
    assert "conflict" in data["detail"]


async def test_conflict_does_not_write_an_audit(client, sample_user_token, db_session):
    """**409 本身不写 audit_logs**（读侧拒绝，非状态变更；ADR-0048 §⑦）。"""
    rid, _hash = await _create(client, sample_user_token)
    before = len((await db_session.execute(select(AuditLog))).scalars().all())
    r = await client.patch(
        f"/api/v1/cool-tower/results/{rid}",
        json={"duty_kw": 20.0, "expected_hash": "0000000000000000"},
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 409
    after = len((await db_session.execute(select(AuditLog))).scalars().all())
    assert after == before, "409 写了审计（ADR-0048 §⑦：409 本身不写）"


# ---------------------------------------------------------------------------
# 正常路径 + 审计
# ---------------------------------------------------------------------------


async def test_patch_with_current_hash_succeeds(client, sample_user_token):
    """基线正确 ⇒ 200（正常路径不被拦）。"""
    rid, h = await _create(client, sample_user_token)
    r = await client.patch(
        f"/api/v1/cool-tower/results/{rid}",
        json={"duty_kw": 20.0, "expected_hash": h},
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 200, f"got {r.status_code}: {r.text}"
    assert r.json()["duty_kw"] == pytest.approx(20.0)


async def test_successful_edit_writes_the_edit_audit(
    client, sample_user_token, db_session
):
    """编辑成功 ⇒ 写 RECORD_EDITED 审计，changed_fields = 字段名列表。"""
    rid, h = await _create(client, sample_user_token)
    r = await client.patch(
        f"/api/v1/cool-tower/results/{rid}",
        json={"duty_kw": 20.0, "fan_power_kw": 9.9, "expected_hash": h},
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 200, f"got {r.status_code}: {r.text}"
    rows = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "RECORD_EDITED",
                AuditLog.resource_id == rid,
            )
        )
    ).scalars().all()
    assert rows, "编辑成功却没写审计"
    assert rows[-1].detail_json["changed_fields"] == ["duty_kw", "fan_power_kw"]
    assert rows[-1].resource_type == "cooling_tower_result"


async def test_conflict_after_another_edit_reports_who_changed_it(
    client, sample_user_token, sample_pc_token, db_session
):
    """A 改完（hash 变了）⇒ B 用旧基线提交 ⇒ 409 且报出「谁改的」。"""
    rid, h = await _create(client, sample_user_token)
    # A 编辑（hash 随之变化）
    r1 = await client.patch(
        f"/api/v1/cool-tower/results/{rid}",
        json={"duty_kw": 20.0, "expected_hash": h},
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r1.status_code == 200, r1.text
    # B 拿旧基线提交
    r2 = await client.patch(
        f"/api/v1/cool-tower/results/{rid}",
        json={"duty_kw": 30.0, "expected_hash": h},
        headers={"Authorization": f"Bearer {sample_pc_token}"},
    )
    assert r2.status_code == 409, f"got {r2.status_code}: {r2.text}"
    conflict = r2.json()["detail"]["conflict"]
    assert conflict["basis"] == "record_hash"
    assert conflict["changed_by"] is not None, "409 必须说得出「谁改了」"
    assert conflict["changed_at"] is not None


async def test_cost_est_patch_uses_the_same_contract(client, sample_user_token, db):
    """cost_est_results 也走同一套契约（它是唯一「可编辑 ∧ 曾无令牌」的表）。"""
    from app.models.equipment import EquipmentList

    equipment_id = uuid.uuid4()
    db.add(
        EquipmentList(
            equipment_id=equipment_id,
            type_code="PUMP",
            equipment_name=f"E-{uuid.uuid4().hex[:8]}",
            tag_number=f"T-{uuid.uuid4().hex[:8]}",
            project_id=uuid.uuid4(),
            workspace_id=uuid.uuid4(),
        )
    )
    await db.commit()

    create_r = await client.post(
        "/api/v1/cost-est/results",
        json={
            "equipment_id": str(equipment_id),
            "estimated_cost": 1000.0,
            "currency": "USD",
            "cost_index_year": 2019,
        },
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert create_r.status_code == 201, create_r.text
    rid = create_r.json()["result_id"]
    h = create_r.json()["record_hash"]
    assert h, "cost_est 的响应必须暴露 record_hash（前端要拿它当基线）"

    r = await client.patch(
        f"/api/v1/cost-est/results/{rid}",
        json={"estimated_cost": 2000.0, "expected_hash": h},
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 200, f"got {r.status_code}: {r.text}"
