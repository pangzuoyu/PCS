"""WF-PATH-01A/01B/01D/01E + E2E-010：记录层状态机（P10-B · T5）。

## 9 态与 13 事件

`DRAFT → IN_APPROVAL → CHECKED`（正向链）· 驳回 ⇒ `CHECK_REJECTED`（可重交）·
撤销 ⇒ `REVERSAL_PENDING` ⇒ 裁决 ⇒ 回 `CHECKED` 或维持 `CHANGED` ·
废止 ⇒ `OBSOLETE`（终态）。

## ⚠️ 断言必须**精确**（hermes 的断言形状病 #1）

⚠️ 9 态里**没有 `APPROVED`** ⇒ 链走完落在 **`CHECKED`** ⇒
断「APPROVED」⇒ 字段不存在 ⇒ 断言必飘；断「IN_APPROVAL 或 CHECKED 都算」这种
**或**判定更毒 —— 链条**停在第 2 步**也照样绿 ⇒ ⇒ 断 **`sign_status == 'CHECKED'`**
且 **`approval_step is None`**。

## ⚠️ 每一步都要换角色

端点要求 `actor.role == record.approval_role`（= 矩阵这一步该谁签）
⇒ 用错角色 ⇒ 403 `APPROVAL_ROLE_MISMATCH` ⇒ 链条卡死。
"""
from __future__ import annotations

import uuid

import pytest

from tests.e2e_flows.helpers import (
    CHAIN_ROLES,
    approval_step,
    approve_record_chain,
    approve_record_steps,
    make_record,
    submit_for_approval,
)

MODULE = "PipingResult"


async def _new_record(e2e_client, e2e_seed) -> uuid.UUID:
    return await make_record(
        e2e_client,
        project_id=e2e_seed["project_id"],
        workspace_id=e2e_seed["workspace_id"],
        tag_number=f"E2E-WF-{uuid.uuid4().hex[:8]}",
    )


async def _bump_record(e2e_client, record_id) -> None:
    """把记录的一个数值改掉并**重算哈希**（⇒ 「结果变了没」的判据成立）。"""
    from sqlalchemy import text as _text

    from app.services.calc_lineage import compute_record_hash
    from app.models.calc import PipingResult

    async with e2e_client._e2e_session_factory() as session:  # type: ignore[attr-defined]
        record = await session.get(PipingResult, record_id)
        record.design_press = float(record.design_press or 1.0) + 0.1
        await session.flush()
        record.record_hash = compute_record_hash(record)
        await session.commit()
        assert record.record_hash, "改完的记录没有哈希"


@pytest.mark.e2e
async def test_wf_path_01a_forward_path_reaches_checked(
    e2e_client, role_headers, e2e_seed
):
    """正向链：DRAFT → submit → CHECKER → REVIEWER → APPROVER ⇒ **终态 CHECKED**。"""
    record_id = await _new_record(e2e_client, e2e_seed)

    steps = await approve_record_chain(
        e2e_client, module=MODULE, record_id=record_id, role_headers=role_headers
    )
    assert len(steps) == len(CHAIN_ROLES), f"链没走完：{len(steps)} 步"

    # ⚠️ 终态**精确**断 `CHECKED`（9 态里没有 `APPROVED`）
    # ⚠️ 状态转移端点返回的是 **`to_status`**（不是 sign_status）
    final = steps[-1]
    assert final["to_status"] == "CHECKED", (
        f"终态不是 CHECKED：{final.get('to_status')}"
    )
    # ⚠️ 端点**不清空** `approval_step`（批完是 3/3）⇒ 断「步数耗尽」而不是「为空」
    assert final.get("approval_step") == final.get("approval_depth"), (
        f"批完了但步数没耗尽：{final}"
    )


@pytest.mark.e2e
async def test_wf_path_01b_reject_returns_to_check_rejected_and_can_resubmit(
    e2e_client, role_headers, e2e_seed
):
    """驳回 ⇒ `CHECK_REJECTED` ⇒ **能重新提交**（否则是死路）。"""
    record_id = await _new_record(e2e_client, e2e_seed)

    steps = await approve_record_chain(
        e2e_client,
        module=MODULE,
        record_id=record_id,
        role_headers=role_headers,
        decision="REJECT",
        until_role="CHECKER",
    )
    rejected = steps[-1]
    assert rejected["to_status"] == "CHECK_REJECTED", (
        f"驳回后不是 CHECK_REJECTED：{rejected.get('to_status')}"
    )

    # 重新提交 ⇒ 能再走一遍
    resubmitted = await submit_for_approval(
        e2e_client,
        module=MODULE,
        record_id=record_id,
        headers=role_headers("DESIGNER"),
    )
    assert resubmitted["to_status"] == "IN_APPROVAL", (
        f"驳回后不能重新提交：{resubmitted.get('to_status')}"
    )


@pytest.mark.e2e
async def test_wf_path_01d_reversal_pending_then_decision_restores_the_record(
    e2e_client, role_headers, e2e_seed
):
    """撤销：CHECKED → `REVERSAL_PENDING` ⇒ 裁决（批准）⇒ 回 `CHECKED`。"""
    record_id = await _new_record(e2e_client, e2e_seed)
    await approve_record_chain(
        e2e_client, module=MODULE, record_id=record_id, role_headers=role_headers
    )
    # ⚠️ **撤销只能从 `CHANGED` 发起**（`REVERSAL_BAD_STATE` 明写「仅 CHANGED 可发起」）
    # ⇒ ⇒ 先走一遍变更：initiate-change（CHECKED→CHANGE_PENDING）→ apply-change（→CHANGED）
    initiated = await e2e_client.post(
        f"/api/v1/records/{MODULE}/{record_id}/initiate-change",
        json={"reason": "E2E 场景变更"},
        headers=role_headers("DESIGNER"),
    )
    assert initiated.status_code == 200, (
        f"initiate-change 失败：{initiated.status_code} {initiated.text[:300]}"
    )

    # ⚠️ **必须真的改记录** —— `apply-change` 会核「自发起变更以来哈希变了没」
    # ⇒ 没改 ⇒ **409 `CHANGE_NO_MODIFICATION`**（并提示改用「放弃变更」）。
    # ⇒ ⚠️ 仓里**没有**记录编辑端点 ⇒ 改数据只能直写库
    # ⇒ 但**状态转移仍全部走真实端点** ⇒ 守的是状态机，不是编辑路径。
    await _bump_record(e2e_client, record_id)

    changed = await e2e_client.post(
        f"/api/v1/records/{MODULE}/{record_id}/apply-change",
        json={"reason": "E2E 场景变更完成"},
        headers=role_headers("DESIGNER"),
    )
    assert changed.status_code == 200, (
        f"apply-change 失败：{changed.status_code} {changed.text[:300]}"
    )

    # ① 申请撤销
    requested = await e2e_client.post(
        f"/api/v1/records/{MODULE}/{record_id}/request-reversal",
        json={"reason": "E2E 场景撤销"},
        headers=role_headers("DESIGNER"),
    )
    assert requested.status_code == 200, (
        f"申请撤销失败：{requested.status_code} {requested.text[:300]}"
    )
    assert requested.json()["to_status"] == "REVERSAL_PENDING", (
        f"申请撤销后不是 REVERSAL_PENDING：{requested.json().get('to_status')}"
    )

    # ② 裁决（APPROVE_REVERSAL 要 APPROVER/SYSTEM_ADMIN）
    decided = await e2e_client.post(
        f"/api/v1/records/{MODULE}/{record_id}/reversal-decision",
        json={"decision": "APPROVE", "reason": "E2E 场景批准撤销"},
        headers=role_headers("APPROVER"),
    )
    assert decided.status_code == 200, (
        f"撤销裁决失败：{decided.status_code} {decided.text[:300]}"
    )
    assert decided.json()["to_status"] == "CHECKED", (
        f"批准撤销后不是 CHECKED：{decided.json().get('to_status')}"
    )


@pytest.mark.e2e
async def test_wf_path_01e_obsolete_is_terminal(e2e_client, role_headers, e2e_seed):
    """废止：CHECKED → `OBSOLETE`（终态）⇒ 再废止 ⇒ 不许。"""
    record_id = await _new_record(e2e_client, e2e_seed)
    await approve_record_chain(
        e2e_client, module=MODULE, record_id=record_id, role_headers=role_headers
    )

    obsoleted = await e2e_client.post(
        f"/api/v1/records/{MODULE}/{record_id}/obsolete",
        json={"reason": "E2E 场景废止"},
        headers=role_headers("DESIGNER"),
    )
    assert obsoleted.status_code == 200, (
        f"废止失败：{obsoleted.status_code} {obsoleted.text[:300]}"
    )
    assert obsoleted.json()["to_status"] == "OBSOLETE", (
        f"废止后不是 OBSOLETE：{obsoleted.json().get('to_status')}"
    )

    # 终态 ⇒ 再废止必须被拒（409）
    again = await e2e_client.post(
        f"/api/v1/records/{MODULE}/{record_id}/obsolete",
        json={"reason": "E2E 场景二次废止"},
        headers=role_headers("DESIGNER"),
    )
    assert again.status_code >= 400, (
        f"已废止的记录还能再废止：{again.status_code} {again.text[:200]}"
    )


@pytest.mark.e2e
async def test_e2e_010_record_approval_chain_walks_the_whole_matrix(
    e2e_client, role_headers, e2e_seed
):
    """E2E-010：**每一步都用对角色** ⇒ 用错角色 ⇒ 403（链条卡死）。

    ⚠️ 断言「用错角色被拒」比只断「走完了」更强：后者在**粗闸放行所有角色**时
    也会绿 ⇒ ⇒ 断「错的角色被 403 挡住」。
    """
    record_id = await _new_record(e2e_client, e2e_seed)
    await submit_for_approval(
        e2e_client,
        module=MODULE,
        record_id=record_id,
        headers=role_headers("DESIGNER"),
    )

    # 第 1 步该 CHECKER 签 ⇒ 拿 REVIEWER 去批 ⇒ 必须被拒
    wrong = await e2e_client.post(
        f"/api/v1/records/{MODULE}/{record_id}/approval-step",
        json={"decision": "PASS"},
        headers=role_headers("REVIEWER"),
    )
    assert wrong.status_code == 403, (
        f"错的角色竟然能批这一步：{wrong.status_code} {wrong.text[:200]}"
        "（⇒ 细判据没生效 ⇒ 矩阵是装饰）"
    )

    # 用对的角色 ⇒ 走完（⚠️ **不能再送审一次** —— 已经 IN_APPROVAL 了）
    steps = await approve_record_steps(
        e2e_client, module=MODULE, record_id=record_id, role_headers=role_headers
    )
    assert steps[-1]["to_status"] == "CHECKED"
