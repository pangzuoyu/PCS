"""E2E-001：项目创建 → 输入清单（P10-B · T3）。

## ⚠️ 清单**不是「自动生成」的**

仓里**没有任何**代码在建项目时碰清单（`project_service` / `projects.py` 都不调
`bulk_seed`）⇒ 真实流程是 **`POST /api/v1/checklist/projects/{id}/seed`**
（请求体带 items 清单）⇒ 再 `GET /api/v1/checklist/projects/{id}` +
`GET .../completeness`。

⇒ 断的是「**显式 seed 之后清单非空**」+「每条的状态字段形状」，
**不是**「200 + 有个列表」（那是空壳断言）。
"""
from __future__ import annotations

import uuid

import pytest

CHECKLIST_ITEMS = [
    {
        "item_key": "BEDD-input-001",
        "item_label": "基础设计数据表",
        "module": "PMS",
        "input_category": "REQUIRED",
        "required": True,
        "note": "E2E 种子输入项",
    },
    {
        "item_key": "BEDD-input-002",
        "item_label": "工艺流程数据",
        "module": "PMS",
        "input_category": "OPTIONAL",
        "required": False,
        "note": "E2E 种子输入项（可选）",
    },
]


@pytest.mark.e2e
async def test_e2e_001_project_creation_and_input_checklist(
    e2e_client, role_headers, e2e_seed
):
    """POST /projects ⇒ 201 ⇒ **显式** seed 输入清单 ⇒ 清单**非空** + 形状正确。"""
    headers = role_headers("SYSTEM_ADMIN")

    # ⓪ **自己的 FORMAL 工作区**（2026-11-18 · P10-F 评审的 P0 修）
    #    ⇒ ⇒ 「一个工作区只挂一个项目」（TODO-169 的口径）⇒ ⇒ 种子那个工作区
    #    ⇒ ⇒ **已经挂了种子项目** ⇒ ⇒ 在它上面再建 ⇒ ⇒ 409
    #    ⇒ ⇒ ⇒ 真后端里「建项目」的真实前置就是「先有一个**空**的 FORMAL 工作区」。
    from app.services.token_issuer import derive_user_id

    admin_id = derive_user_id("e2e-admin")
    ws_resp = await e2e_client.post(
        "/api/v1/workspaces",
        params={"owner_id": str(admin_id)},
        json={"workspace_type": "FORMAL", "name": "E2E-001 工作区"},
        headers=headers,
    )
    assert ws_resp.status_code == 201, ws_resp.text
    workspace_id = ws_resp.json()["workspace_id"]

    # ① 建项目
    resp = await e2e_client.post(
        "/api/v1/projects",
        json={
            "project_no": f"E2E-001-{uuid.uuid4().hex[:8]}",
            "project_name": "E2E-001 输入清单项目",
            "owner_company": "E2E Owner",
            "location": "E2E Site",
            "project_type": "REFINERY",
            "design_phase": "DESIGN",
            "unit_system": "SI",
            # ⚠️ **必须是存在的 FORMAL 工作区** ⇒ 用刚建的那个
            # （随手编的 UUID ⇒ 404 ⇒ 症状看着像「端点坏了」）
            "workspace_id": str(workspace_id),
        },
        headers=headers,
    )
    assert resp.status_code in (200, 201), (
        f"建项目失败：{resp.status_code} {resp.text[:300]}"
        "（⚠️ `workspace_id` 必须指向一个**存在的 FORMAL 工作区** ⇒ 用种子那个）"
    )
    project_id = resp.json()["project_id"]

    # ② 显式 seed 清单
    seeded = await e2e_client.post(
        f"/api/v1/checklist/projects/{project_id}/seed",
        json={"items": CHECKLIST_ITEMS},
        headers=headers,
    )
    assert seeded.status_code in (200, 201), (
        f"seed 清单失败：{seeded.status_code} {seeded.text[:300]}"
    )

    # ③ 清单非空 + 每条形状正确
    items = await e2e_client.get(
        f"/api/v1/checklist/projects/{project_id}", headers=headers
    )
    assert items.status_code == 200, f"读清单失败：{items.status_code} {items.text[:300]}"
    rows = items.json()
    assert isinstance(rows, list), f"清单响应不是列表：{type(rows).__name__}"
    assert len(rows) == len(CHECKLIST_ITEMS), (
        f"清单行数不对：{len(rows)} ≠ {len(CHECKLIST_ITEMS)} ⇒ seed 没落库"
    )
    for row in rows:
        assert row.get("item_key"), f"清单行缺 item_key：{row}"
        assert "status" in row, f"清单行缺状态字段：{row}"

    # ④ completeness 端点
    completeness = await e2e_client.get(
        f"/api/v1/checklist/projects/{project_id}/completeness", headers=headers
    )
    assert completeness.status_code == 200, (
        f"读 completeness 失败：{completeness.status_code} {completeness.text[:300]}"
    )
    body = completeness.json()
    assert body, "completeness 响应是空的 ⇒ 清单没算出来"
