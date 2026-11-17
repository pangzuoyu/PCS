"""E2E-016 + AUTH-E2E-01~10 + WF-PATH-04：权限矩阵（P10-B · T6）。

## ⚠️ 403 与 404 的**形状**要分开断

- **角色不对**（同项目、有授权、但角色不够）⇒ **403**
- **跨项目**（角色对、但**没授权行**）⇒ **404**（与「不存在」逐字同形
  ⇒ 不泄露存在性）

⇒ 这两件事**混成同一个码**就等于泄露了别人的资源存在性。

## ⚠️ 错误码也要断（hermes 断言形状病 #3）

只断状态码 ⇒ 换个原因也照样绿 ⇒ 矩阵改**四元组**（角色 · 操作 · 状态码 · 错误码）。

## ⚠️ AUTH-E2E-02 的 403 是**自审闸**

`submit-approval` 的粗闸 `SUBMIT_FOR_CHECK = {DESIGNER, CHECKER, APPROVER,
SYSTEM_ADMIN}` **放行 CHECKER** ⇒ 403 的真因是「提交人自己的角色出现在链里」
⇒ 错误码 `APPROVAL_SELF_REVIEW_FORBIDDEN` ⇒ ⇒ **必须钉住它**。
"""
from __future__ import annotations

import uuid

import pytest

from scripts.seed_e2e_flows import ROLE_TO_USERNAME

#: 权限矩阵（角色 × 操作 × 期望状态码 × 期望错误码）。
#: ⚠️ **四元组**：错误码也要断 ⇒ 只断状态码 ⇒ 换个原因也照样绿。
AUTH_MATRIX = [
    ("DESIGNER", "submit-approval", 200, None),  # AUTH-E2E-01
    ("CHECKER", "submit-approval", 403, "APPROVAL_SELF_REVIEW_FORBIDDEN"),  # 02 ★
    ("CHECKER", "approval-step", 200, None),  # AUTH-E2E-03（待批角色就是 CHECKER）
    ("DESIGNER", "approval-step", 403, "HTTP_403"),  # AUTH-E2E-04（粗闸就挡了）
    # ⚠️ 矩阵链是 **CHECKER → REVIEWER → APPROVER** ⇒ 第一步的「待批角色」
    # 是 **CHECKER** ⇒ ⇒ **APPROVER / REVIEWER 现在批 = 插队**
    # ⇒ ⇒ 403 `APPROVAL_ROLE_MISMATCH`（不是「角色不够」，是「轮不到你」）
    ("APPROVER", "approval-step", 403, "APPROVAL_ROLE_MISMATCH"),  # AUTH-E2E-05 ★
    ("REVIEWER", "approval-step", 403, "APPROVAL_ROLE_MISMATCH"),  # 同上（插队）
    # ★ AUTH-E2E-05b：**轮到你时**你**批得动**（200）
    # ⇒ ⇒ 先由 CHECKER、REVIEWER 各批一步 ⇒ 待批角色才轮到 APPROVER
    ("APPROVER", "approval-step-late", 200, None),
    ("DESIGNER", "audit-logs", 403, "HTTP_403"),  # AUTH-E2E-08
    ("SYSTEM_ADMIN", "audit-logs", 200, None),  # AUTH-E2E-07
]


async def _new_record(e2e_client, e2e_seed) -> uuid.UUID:
    from tests.e2e_flows.helpers import make_record

    return await make_record(
        e2e_client,
        project_id=e2e_seed["project_id"],
        workspace_id=e2e_seed["workspace_id"],
        tag_number=f"E2E-AUTH-{uuid.uuid4().hex[:8]}",
    )


@pytest.mark.e2e
async def test_permission_matrix(e2e_client, role_headers, e2e_seed):
    """参数化跑权限矩阵 ⇒ 状态码与**错误码**都对。"""
    from tests.e2e_flows.helpers import approve_record_steps, submit_for_approval

    for role, action, want_status, want_code in AUTH_MATRIX:
        record_id = await _new_record(e2e_client, e2e_seed)
        headers = role_headers(role)

        if action == "submit-approval":
            resp = await e2e_client.post(
                f"/api/v1/records/PipingResult/{record_id}/submit-approval",
                json={"reason": "E2E 权限矩阵"},
                headers=headers,
            )
        elif action == "approval-step-late":
            # 先由 CHECKER、REVIEWER 各批一步 ⇒ 待批角色才轮到被测角色
            await submit_for_approval(
                e2e_client,
                module="PipingResult",
                record_id=record_id,
                headers=role_headers("DESIGNER"),
            )
            await approve_record_steps(
                e2e_client,
                module="PipingResult",
                record_id=record_id,
                role_headers=role_headers,
                until_role="REVIEWER",
            )
            resp = await e2e_client.post(
                f"/api/v1/records/PipingResult/{record_id}/approval-step",
                json={"decision": "PASS"},
                headers=headers,
            )
        elif action == "approval-step":
            # 先让记录进审批中（用有权的角色送审）⇒ 再用被测角色去批
            await submit_for_approval(
                e2e_client,
                module="PipingResult",
                record_id=record_id,
                headers=role_headers("DESIGNER"),
            )
            resp = await e2e_client.post(
                f"/api/v1/records/PipingResult/{record_id}/approval-step",
                json={"decision": "PASS"},
                headers=headers,
            )
        else:  # audit-logs
            resp = await e2e_client.get("/api/v1/audit-logs", headers=headers)

        assert resp.status_code == want_status, (
            f"[{role} · {action}] 状态码 {resp.status_code} ≠ {want_status}"
            f"（body={resp.text[:200]}）"
        )
        if want_code is not None:
            body = resp.json()
            assert body.get("code") == want_code, (
                f"[{role} · {action}] 错误码 {body.get('code')!r} ≠ {want_code!r}"
                f"（body={body}）"
            )


@pytest.mark.e2e
async def test_rbac_denial_writes_an_audit_row(e2e_client, role_headers):
    """⚠️ **403 ⇒ 审计行**（P10-B 评审 #10）⇒ 「越权 ⇒ 留痕」**不是空跑**。

    ⚠️ **限流要先清** —— RBAC 拒绝是 per-IP 滑动窗口（>5/min ⇒ 429）⇒ ⇒
    车道里已经有若干次拒绝 ⇒ 不清 ⇒ 这一条拿到的是 **429** 而不是 403。

    ⚠️ **断「多了一行」而不是「有一行」** —— 车道里别的用例也会写审计
    ⇒ ⇒ 断绝对数量会被别的用例带偏 ⇒ ⇒ 断**写前/写后的差**。
    """
    from sqlalchemy import select

    from app.models.system import AuditLog
    from app.services._sliding_window_rate_limit import clear_all_rate_limits
    from app.services.token_issuer import derive_user_id

    from scripts.seed_e2e_flows import ROLE_TO_USERNAME

    clear_all_rate_limits()
    try:
        async with e2e_client._e2e_session_factory() as session:  # type: ignore[attr-defined]
            before = len(
                (
                    await session.execute(
                        select(AuditLog).where(AuditLog.action == "RBAC_DENIED")
                    )
                ).scalars().all()
            )

        resp = await e2e_client.get(
            "/api/v1/audit-logs", headers=role_headers("DESIGNER")
        )
        assert resp.status_code == 403, (
            f"DESIGNER 访问 audit-logs 应 403，却拿到 {resp.status_code}"
            "⇒ 本用例没走到 RBAC 拒绝路径"
        )

        async with e2e_client._e2e_session_factory() as session:  # type: ignore[attr-defined]
            rows = (
                await session.execute(
                    select(AuditLog)
                    .where(AuditLog.action == "RBAC_DENIED")
                    .order_by(AuditLog.occurred_at.desc())
                )
            ).scalars().all()
    finally:
        # ⚠️ 还原 ⇒ 别把限流额度留给后面的用例（否则矩阵那条会拿到 429）
        clear_all_rate_limits()

    assert len(rows) == before + 1, (
        f"403 之后审计行数 {before} → {len(rows)}（期望 +1）"
        "⇒ RBAC 审计在车道里是空跑（评审 #10）"
    )
    latest = rows[0]
    assert latest.resource_type == "AUTHZ"
    assert latest.user_id == derive_user_id(ROLE_TO_USERNAME["DESIGNER"]), (
        f"审计行的 user_id = {latest.user_id}，不是被测用户的派生 id"
    )
    assert latest.detail_json["path"] == "/api/v1/audit-logs"
    assert latest.detail_json["status"] == 403


@pytest.mark.e2e
async def test_e2e_016_cross_project_access_is_404_not_403(
    e2e_client, role_headers, e2e_seed
):
    """跨项目（**没授权行**）⇒ **404**（与「不存在」逐字同形）⇒ 不是 403。

    ⚠️ **403 会泄露资源存在性** ⇒ 枚举得出别人的项目 id。
    ⇒ ⇒ 断言必须是 **404**（且 404 与「真不存在」的响应**同形**）。
    """
    headers = role_headers(username="e2e-outsider")
    project_id = str(e2e_seed["project_id"])

    resp = await e2e_client.get(f"/api/v1/projects/{project_id}", headers=headers)
    assert resp.status_code == 404, (
        f"跨项目访问返回 {resp.status_code}（应为 404）⇒ 403 会泄露存在性"
    )

    # 与「真不存在」的响应**同形**
    missing = await e2e_client.get(
        f"/api/v1/projects/{uuid.uuid4()}", headers=headers
    )
    assert missing.status_code == resp.status_code, (
        f"跨项目({resp.status_code}) 与 真不存在({missing.status_code}) 不同形"
    )
    assert missing.json().get("code") == resp.json().get("code"), (
        f"错误码也不同形：{resp.json().get('code')} vs {missing.json().get('code')}"
    )


@pytest.mark.e2e
async def test_wf_path_04_matrix_and_signature_matrix_agree(
    e2e_client, role_headers, e2e_seed
):
    """粗闸（`TRANSITION_ROLES`）与**项目绑定的签署矩阵**不能打架。

    ⇒ 粗闸放行的角色，在矩阵那一步**也**必须被允许
    ⇒ 否则出现「谁都能过粗闸、但矩阵这一步没人能签」的**死链**。

    ⇒ 断法：矩阵的每一步角色 ⇒ 都能过状态机的粗闸
    （`TRANSITION_ROLES[PASS_CHECK]` 必须**包含**它）。
    """
    from app.services.state_machine import TRANSITION_ROLES, StateTransition

    allowed = TRANSITION_ROLES[StateTransition.PASS_CHECK]
    for role in ("CHECKER", "REVIEWER", "APPROVER"):
        assert role in allowed, (
            f"矩阵这一步该 {role} 签，但它**过不了状态机粗闸**"
            f"（PASS_CHECK 只允许 {sorted(allowed)}）⇒ 死链"
        )

    # 且矩阵本身得是 ACTIVE + 有步骤（否则批准链是空的 ⇒ 送审直接 422）
    from app.models.deliverable import SignatureMatrix
    from sqlalchemy import select

    async with e2e_client._e2e_session_factory() as session:  # type: ignore[attr-defined]
        matrix = (
            await session.execute(
                select(SignatureMatrix).where(
                    SignatureMatrix.matrix_id == e2e_seed["matrix_id"]
                )
            )
        ).scalar_one()
    assert matrix.status == "ACTIVE", f"矩阵不是 ACTIVE：{matrix.status}"
    assert matrix.steps_json, "矩阵没有步骤 ⇒ 批准链是空的"
    roles = [s["sign_role"] for s in matrix.steps_json]
    for role in roles:
        assert role in allowed, f"矩阵里的 {role} 过不了状态机粗闸 ⇒ 死链"
    assert roles == ["CHECKER", "REVIEWER", "APPROVER"], f"矩阵的链不对：{roles}"
