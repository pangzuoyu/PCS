"""E2E-014：供应商实际值 → 偏差报告（P10-B · T4）。

## ⚠️ 两个「两个人」的门禁

SPEC §3.2.4(4)：**设计人（录入/确认）与校核人是两个角色** ⇒ 同一人既提交又
校核等于没有校核 ⇒ ⇒ 场景**必须换 token**：

- 录入实际值 + 确认 ⇒ **DESIGNER**（`e2e-designer`）
- 校核 ⇒ **REVIEWER**（`e2e-reviewer`）

⇒ 这正是本批种子加**角色维度**的用处（冒烟级种子全项目都是 DESIGNER ⇒
这条场景根本写不出来）。

## ⚠️ 设备的位号必须是 `PUMP_DESIGN` 里的那 17 个之一

设计值来自 `equipment.design_parameters_json`（种子从 `PUMP_DESIGN` 抄）
⇒ 位号在集合外 ⇒ 「缺设计值（不可判）」⇒ `can_confirm` 恒 False。
"""
from __future__ import annotations

import pytest

#: 实际值 —— ⚠️ **必须覆盖「应检集」的全部 5 项**
#: （`app/services/supplier/deviation_service.py::SPEC_RULES` 的参数：
#: 扬程 / 效率 / NPSHr / 电机额定功率 / 转速 ⇒ 缺一项就是「不可判」
#: ⇒ `can_confirm` 恒 False ⇒ 场景断不了）。
#:
#: 设计值（`PUMP_DESIGN["132-P-101A/B"]`）：扬程 2100 · 效率 0.8 ·
#: NPSHr 2.0 · 轴功率 2214.06 · 电机额定功率 2500 · 转速 2982。
#: 各条规则：扬程 [设计, 设计×1.05] · 效率 ≥ 设计×0.95 · NPSHr ≤ 设计
#: · 电机额定功率 ≥ 轴功率×1.10（>55kW 档）· 转速 须与设计一致。
ACTUAL_ENTRIES = [
    {"name": "扬程", "value": 2150.0, "unit": "m"},
    {"name": "效率", "value": 0.79, "unit": ""},
    {"name": "NPSHr", "value": 1.8, "unit": "m"},
    {"name": "电机额定功率", "value": 2500.0, "unit": "kW"},
    {"name": "转速", "value": 2982.0, "unit": "r/min"},
]


@pytest.mark.e2e
async def test_e2e_014_supplier_actual_value_updates_the_deviation_report(
    e2e_client, role_headers, e2e_seed
):
    """录入实际值 ⇒ 偏差报告出现偏差行 ⇒ **两个人**（设计人 + 校核人）⇒ 确认。"""
    designer = role_headers("DESIGNER")
    reviewer = role_headers("REVIEWER")
    equipment_id = str(e2e_seed["equipment_id"])

    # ① 录实际值（设计人）
    recorded = await e2e_client.put(
        f"/api/v1/equipment/{equipment_id}/actual-data",
        json={"entries": ACTUAL_ENTRIES},
        headers=designer,
    )
    assert recorded.status_code == 200, (
        f"录实际值失败：{recorded.status_code} {recorded.text[:300]}"
    )
    assert recorded.json()["actual_data_status"] == "PENDING_CONFIRM", (
        f"录完的状态不是 PENDING_CONFIRM：{recorded.json()}"
    )

    # ② 偏差报告：出现偏差行 + 允许确认
    report = await e2e_client.get(
        f"/api/v1/equipment/{equipment_id}/deviation-report", headers=designer
    )
    assert report.status_code == 200, (
        f"读偏差报告失败：{report.status_code} {report.text[:300]}"
    )
    body = report.json()
    assert body["rows"], f"偏差报告没有行（设备没有设计值？）：{body}"
    assert body["can_confirm"], f"偏差报告说不能确认：{body.get('blocking_reason')}"

    # ③ **设计人确认**（⇒ 提交校核；`reason` 可选）
    confirmed = await e2e_client.post(
        f"/api/v1/equipment/{equipment_id}/actual-data/confirm",
        json={"reason": "E2E 场景确认"},
        headers=designer,
    )
    assert confirmed.status_code == 200, (
        f"确认失败：{confirmed.status_code} {confirmed.text[:300]}"
    )

    # ④ **校核人校核**（**另一个人** ⇒ REVIEWER ⇒ 同一人既提交又校核等于没有校核）
    checked = await e2e_client.post(
        f"/api/v1/equipment/{equipment_id}/actual-data/check",
        json={"decision": "pass"},
        headers=reviewer,
    )
    assert checked.status_code == 200, (
        f"校核失败：{checked.status_code} {checked.text[:300]}"
    )
    assert checked.json()["actual_data_status"] == "CONFIRMED", (
        f"校核后状态不是 CONFIRMED：{checked.json()}"
    )
