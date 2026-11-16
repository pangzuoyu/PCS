"""E2E-007/008：设备表 · 能耗汇总（P10-B · T4）。

## E2E-007：设备表

`GET /api/v1/equipment-list` ⇒ **种子设备可见**（按位号找）⇒
「设备表」这条数据线是通的。

## E2E-008：能耗汇总 = **明细之和**

⚠️ **断言必须是「汇总 == 明细之和」**，**不是**「> 0」—— 「> 0」挡不住
「算错但非零」⇒ ⇒ 先录一条用电明细（`POST /api/v1/util/power-items`）⇒
再聚合（`POST /api/v1/util/energy-summary/aggregate`）⇒
再把汇总值与**明细行**的年耗电逐个比对。

⚠️ **聚合端点有滑动窗口限流**（5 次/分钟/用户）⇒ 本场景只调**一次**。
"""
from __future__ import annotations

import pytest

from scripts.seed_e2e_flows import FLOW_EQUIPMENT_TAG

#: 一条用电明细（电机功率 × 年运行小时 × 负载系数 ⇒ 年耗电）。
POWER_ITEM = {
    "equipment_tag": FLOW_EQUIPMENT_TAG,
    "motor_power_kw": 250.0,
    "operating_hours_per_year": 8000.0,
    "load_factor": 0.8,
}


@pytest.mark.e2e
async def test_e2e_007_equipment_list_contains_every_seeded_equipment(
    e2e_client, role_headers, e2e_seed
):
    """GET /equipment-list ⇒ 种子设备在列表里（按位号找）。"""
    headers = role_headers("DESIGNER")

    resp = await e2e_client.get(
        "/api/v1/equipment-list",
        params={"project_id": str(e2e_seed["project_id"])},
        headers=headers,
    )
    assert resp.status_code == 200, (
        f"读设备表失败：{resp.status_code} {resp.text[:300]}"
    )
    body = resp.json()
    items = body["items"] if isinstance(body, dict) else body
    tags = {row.get("tag_number") for row in items}
    assert FLOW_EQUIPMENT_TAG in tags, (
        f"设备表里没有种子设备 {FLOW_EQUIPMENT_TAG!r}（列表里的位号：{sorted(tags)[:8]}）"
    )


@pytest.mark.e2e
async def test_e2e_008_energy_summary_matches_the_input_items(
    e2e_client, role_headers, e2e_seed
):
    """录一条用电明细 ⇒ 聚合 ⇒ **汇总 == 明细之和**（不是「> 0」）。"""
    headers = role_headers("DESIGNER")
    project_id = str(e2e_seed["project_id"])
    workspace_id = str(e2e_seed["workspace_id"])

    # ① 录一条用电明细
    created = await e2e_client.post(
        "/api/v1/util/power-items",
        json={
            "project_id": project_id,
            "workspace_id": workspace_id,
            **POWER_ITEM,
        },
        headers=headers,
    )
    assert created.status_code in (200, 201), (
        f"录用电明细失败：{created.status_code} {created.text[:300]}"
    )

    # ② 读回明细（拿它自己的年耗电）
    listed = await e2e_client.get(
        "/api/v1/util/power-items",
        params={"project_id": project_id},
        headers=headers,
    )
    assert listed.status_code == 200, (
        f"读用电明细失败：{listed.status_code} {listed.text[:300]}"
    )
    rows = listed.json()
    rows = rows["items"] if isinstance(rows, dict) else rows
    mine = [r for r in rows if r.get("equipment_tag") == FLOW_EQUIPMENT_TAG]
    assert mine, f"回读不到刚录的明细（位号 {FLOW_EQUIPMENT_TAG!r}）"

    # ③ 聚合（⚠️ 限流 5 次/分钟 ⇒ 只调一次）
    summary = await e2e_client.post(
        "/api/v1/util/energy-summary/aggregate",
        json={"project_id": project_id, "workspace_id": workspace_id},
        headers=headers,
    )
    assert summary.status_code in (200, 201), (
        f"能耗汇总失败：{summary.status_code} {summary.text[:300]}"
    )
    total = summary.json()

    # ④ **汇总 == 明细之和** —— 不是「> 0」
    detail_sum = sum(float(r.get("annual_consumption_kwh") or 0.0) for r in mine)
    assert detail_sum > 0, f"明细的年耗电是 0 ⇒ 断言无意义：{mine}"
    assert float(total["electricity_kwh_yr"]) == detail_sum, (
        f"汇总 ≠ 明细之和：汇总={total['electricity_kwh_yr']} 明细之和={detail_sum}"
    )
