"""WF-PATH-01C + E2E-013：上游变更 ⇒ 下游 STALE ⇒ 确认重算（P10-B · T5 补做）。

## ⚠️ **四步是一跳跨三个端点**（hermes 断言形状病 #6）

计划原稿写「`confirm-recalc` ⇒ 变 `CHANGED`」⇒ ⚠️ **必红** ⇒
`confirm-recalc` 是**传播触发器**（不是状态转移）⇒ ⇒ **分步断言**：

| 步 | 端点 | 断言 |
|----|------|------|
| ① | `POST /change-impact/{type}/{id}/confirm-recalc` | 下游 `propagated >= 1` 且状态 = `STALE` |
| ② | `POST /change-impact/{type}/{id}/confirm` | 判定 = `CHANGED` 且状态 = `CHANGE_PENDING` |
| ③ | `POST /records/{module}/{id}/apply-change` | 状态 = `CHANGED` |
| ④ | —— | 记录哈希 **≠** 发起变更前的哈希 |

## ⚠️ **响应里有两个计数器，别混**（计划原稿写的是 `marked_stale`）

- `marked_stale` = `CIAEngine.scan_stale()` 的行数 = **「自己哈希对不上基线」**的记录
- `propagated` = **链式传播**标 STALE 的行数 = **「上游变了」的下游**

⇒ 01C 断的是**传播** ⇒ ⇒ 断 `propagated` ⇒ 断 `marked_stale` ⇒
「上游改了」这个场景压根没被验到（扫描走的是另一条路）。

## ⚠️ **为什么要改两次下游**

- **改第 1 次（重算）**：下游内容跟着上游变了 ⇒ 哈希 ≠ 血缘基线
  ⇒ ⇒ `confirm` 才判「结果**已变**」⇒ ⇒ 进 `CHANGE_PENDING`（要重新签署）
- **改第 2 次（落笔）**：`apply-change` 核「**自快照以来**改没改」
  ⇒ 快照是 `RESOLVE_STALE_CHANGED` 时拍的 ⇒ 此刻内容与快照**一样**
  ⇒ ⇒ 不再改一次 ⇒ **409 `CHANGE_NO_MODIFICATION`** ⇒ 变更单永远关不掉。

## ⚠️ 链式传播走 `parent_lineage_id`（**不是** `source_ref_*`）

`cia_engine.CIAEngine.propagate` ⇒ `LineageTracker.downstream(lineage_id=…)`
⇒ ⇒ 只写 `source_ref_type/source_ref_id` ⇒ 传播**找不到下游** ⇒ 下游永远不 STALE。
"""
from __future__ import annotations

import uuid

import pytest

from tests.e2e_flows.helpers import (
    approve_record_chain,
    bump_record,
    get_record_state,
    link_lineage,
    make_record,
)

MODULE = "PipingResult"


async def _checked_record(e2e_client, e2e_seed, role_headers, prefix: str):
    """造一条记录并走完批准链 ⇒ `CHECKED`（9 态里的终态之一）。"""
    record_id = await make_record(
        e2e_client,
        project_id=e2e_seed["project_id"],
        workspace_id=e2e_seed["workspace_id"],
        tag_number=f"{prefix}-{uuid.uuid4().hex[:8]}",
    )
    await approve_record_chain(
        e2e_client, module=MODULE, record_id=record_id, role_headers=role_headers
    )
    status, _ = await get_record_state(e2e_client, record_id)
    assert status == "CHECKED", f"记录没走到 CHECKED：{status}"
    return record_id


@pytest.mark.e2e
async def test_wf_path_01c_upstream_change_marks_downstream_stale_and_confirm_recalc(
    e2e_client, role_headers, e2e_seed
):
    """上游记录改 ⇒ 下游记录变 `STALE` ⇒ 四步走到 `CHANGED` 且哈希变了。"""
    headers = role_headers("DESIGNER")

    # ── 准备：一条上游 + 一条下游，都已 CHECKED ──
    upstream_id = await _checked_record(
        e2e_client, e2e_seed, role_headers, "E2E-CIA-UP"
    )
    downstream_id = await _checked_record(
        e2e_client, e2e_seed, role_headers, "E2E-CIA-DOWN"
    )

    # ── 血缘链：下游挂在上游的血缘行下面（`parent_lineage_id`）──
    await link_lineage(
        e2e_client, upstream_id=upstream_id, downstream_id=downstream_id
    )

    # ── 上游走**真实端点**改（不是直接改库）──
    up_status_before, up_hash_before = await get_record_state(
        e2e_client, upstream_id
    )
    assert up_status_before == "CHECKED"

    initiated = await e2e_client.post(
        f"/api/v1/records/{MODULE}/{upstream_id}/initiate-change",
        json={"reason": "E2E 上游变更"},
        headers=headers,
    )
    assert initiated.status_code == 200, (
        f"发起上游变更失败：{initiated.status_code} {initiated.text[:300]}"
    )
    await bump_record(e2e_client, upstream_id)
    applied = await e2e_client.post(
        f"/api/v1/records/{MODULE}/{upstream_id}/apply-change",
        json={"reason": "E2E 上游变更完成"},
        headers=headers,
    )
    assert applied.status_code == 200, (
        f"上游 apply-change 失败：{applied.status_code} {applied.text[:300]}"
    )
    up_status_after, up_hash_after = await get_record_state(
        e2e_client, upstream_id
    )
    assert up_status_after == "CHANGED", f"上游状态不对：{up_status_after}"
    assert up_hash_after != up_hash_before, "上游哈希没变 ⇒ 这条变更没生效"

    # ── ① 传播触发器：confirm-recalc ⇒ 下游 STALE ──
    recalc = await e2e_client.post(
        f"/api/v1/change-impact/{MODULE}/{upstream_id}/confirm-recalc",
        headers=headers,
    )
    assert recalc.status_code == 200, (
        f"confirm-recalc 失败：{recalc.status_code} {recalc.text[:300]}"
    )
    recalc_body = recalc.json()
    assert recalc_body["propagated"] >= 1, (
        f"**没有传播到下游**：{recalc_body} ⇒ 上游变了、下游却没人被标 STALE"
    )
    down_status, down_hash_before = await get_record_state(
        e2e_client, downstream_id
    )
    assert down_status == "STALE", f"下游状态不是 STALE：{down_status}"

    # ── ② 哈希判定分流：confirm ⇒ 「结果已变」⇒ CHANGE_PENDING ──
    # ⚠️ 先改下游（= 上游变了 ⇒ 下游跟着重算）⇒ 哈希 ≠ 血缘基线
    await bump_record(e2e_client, downstream_id)
    confirmed = await e2e_client.post(
        f"/api/v1/change-impact/{MODULE}/{downstream_id}/confirm",
        headers=headers,
    )
    assert confirmed.status_code == 200, (
        f"confirm 失败：{confirmed.status_code} {confirmed.text[:300]}"
    )
    confirm_body = confirmed.json()
    assert confirm_body["decision"] == "CHANGED", (
        f"判定不是「结果已变」：{confirm_body} ⇒ 下游被当成「没变」⇒ 免凭证放行"
    )
    down_status, _ = await get_record_state(e2e_client, downstream_id)
    assert down_status == "CHANGE_PENDING", f"下游状态不对：{down_status}"

    # ── ③ 完成变更：再改一次（apply-change 核「自快照以来改没改」）──
    await bump_record(e2e_client, downstream_id)
    applied = await e2e_client.post(
        f"/api/v1/records/{MODULE}/{downstream_id}/apply-change",
        json={"reason": "E2E 下游变更完成"},
        headers=headers,
    )
    assert applied.status_code == 200, (
        f"下游 apply-change 失败：{applied.status_code} {applied.text[:300]}"
    )
    down_status, down_hash_after = await get_record_state(e2e_client, downstream_id)
    assert down_status == "CHANGED", f"下游终态不对：{down_status}"

    # ── ④ 哈希确实变了 ──
    assert down_hash_after != down_hash_before, (
        "下游哈希没变 ⇒ 这一整条链什么都没改到"
    )


@pytest.mark.e2e
async def test_e2e_013_change_impact_lists_downstream_records(
    e2e_client, role_headers, e2e_seed
):
    """影响分析 ⇒ **列得出**下游记录（不然用户只看到一个数字，不知道该找谁）。"""
    headers = role_headers("DESIGNER")

    upstream_id = await _checked_record(
        e2e_client, e2e_seed, role_headers, "E2E-CIA-UP"
    )
    downstream_id = await _checked_record(
        e2e_client, e2e_seed, role_headers, "E2E-CIA-DOWN"
    )
    await link_lineage(
        e2e_client, upstream_id=upstream_id, downstream_id=downstream_id
    )

    resp = await e2e_client.get(
        f"/api/v1/lineage/{MODULE}/{upstream_id}/downstream", headers=headers
    )
    assert resp.status_code == 200, (
        f"读下游血缘失败：{resp.status_code} {resp.text[:300]}"
    )
    nodes = resp.json()
    downstream_ids = {n["record_id"] for n in nodes}
    assert str(downstream_id) in downstream_ids, (
        f"下游列表里没有那条记录：{[n['record_id'] for n in nodes]}"
    )
