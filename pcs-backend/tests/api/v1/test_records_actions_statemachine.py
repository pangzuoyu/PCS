"""records 写端点 · 状态机面 3 个（P9A B4b）。

`submit-approval` / `approval-step` / `abandon-change` 三个端点**转发**既有的
9 态状态机（`app/services/state_machine.py`），本文件测的是**转发是否正确**：
状态对不对、角色对不对、越权/越序对不对。

## 三处按裁决实现、不是按 SPEC 原文实现的地方

1. **多级批准的角色链在本仓没有来源**（`approval_role` / `approval_depth` /
   `approval_step` 只是三个标量列；`project_templates.default_config_json` 里的
   `record_approval_config` 只有一句注释、无消费方）。
   ⇒ `approval_role` 由 `submit-approval` 请求体指定并保持到终态，
   多级 = 同一待批角色逐级批 N 次。**不发明角色链** —— 那是凭空造需求。
2. **`can_self_check` 在记录侧没有配置源** ⇒ 取其**最强形式**：
   提交人不能把 `approval_role` 设成自己的角色。宽松形式等于没有自审防护。
3. **`abandon-change` 不接线 `approve_change_notice`**（语义相反，
   见 B4a commit 的 Step 0 判定）⇒ 转发 `StateTransition.ABANDON_CHANGE`。
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.calc import PipingResult
from app.models.enums import RecordSignStatus9

pytestmark = pytest.mark.asyncio


@pytest.fixture
def auth(sample_user_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {sample_user_token}"}


def _checker_auth() -> dict[str, str]:
    from app.core.security import create_access_token

    return {
        "Authorization": f"Bearer {create_access_token(subject='chk', role='CHECKER')}"
    }


async def _make_record(
    client, auth, db_session: AsyncSession, project_id, workspace, *, line_no="P-3001", **status
) -> PipingResult:
    resp = await client.post(
        "/api/v1/records/piping",
        headers=auth,
        params={"workspace_id": str(workspace.workspace_id)},
        json={"project_id": str(project_id), "line_no": line_no},
    )
    assert resp.status_code == 200, resp.text
    rec = await db_session.get(PipingResult, uuid.UUID(resp.json()["pipe_id"]))
    for field, value in status.items():
        setattr(rec, field, value)
    await db_session.commit()
    await db_session.refresh(rec)
    return rec


def _url(rec, action: str) -> str:
    return f"/api/v1/records/PipingResult/{rec.pipe_id}/{action}"


class TestSubmitApproval:
    async def test_submit_moves_draft_to_in_approval(
        self, client, auth, db_session, project_id, workspace
    ):
        rec = await _make_record(client, auth, db_session, project_id, workspace)

        resp = await client.post(
            _url(rec, "submit-approval"), headers=auth, json={"approval_role": "CHECKER"}
        )

        assert resp.status_code == 200, resp.text
        await db_session.refresh(rec)
        assert rec.sign_status == RecordSignStatus9.IN_APPROVAL
        assert rec.approval_step == 1
        assert rec.approval_role == "CHECKER"

    async def test_submit_rejects_self_approval_role(
        self, client, auth, db_session, project_id, workspace
    ):
        """提交人不能把待批角色设成自己 ⇒ 403。

        `can_self_check` 在记录侧没有配置源，本轮取**最强形式**：恒不允许自审。
        宽松形式（只在配置说 false 时才拒）等于没有防护 ——
        配置源不存在时，「配置说 false」这件事永远不成立。
        """
        rec = await _make_record(client, auth, db_session, project_id, workspace)

        resp = await client.post(
            _url(rec, "submit-approval"), headers=auth, json={"approval_role": "DESIGNER"}
        )

        assert resp.status_code == 403, resp.text
        assert resp.json()["code"] == "APPROVAL_SELF_REVIEW_FORBIDDEN"
        await db_session.refresh(rec)
        assert rec.sign_status == RecordSignStatus9.DRAFT, "被拒的提交不得改状态"

    async def test_submit_rejects_unknown_approval_role(
        self, client, auth, db_session, project_id, workspace
    ):
        """7 值词表（`app/models/project.py:154`）之外的值 ⇒ 422。

        不能收下再说 —— `approval_role` 决定谁能批这条记录，
        写错等于让记录卡住或让不该批的人能批。
        """
        rec = await _make_record(client, auth, db_session, project_id, workspace)

        resp = await client.post(
            _url(rec, "submit-approval"), headers=auth, json={"approval_role": "BOSS"}
        )

        assert resp.status_code == 422, resp.text

    async def test_submit_is_rejected_when_already_in_approval(
        self, client, auth, db_session, project_id, workspace
    ):
        """重复提交 ⇒ 409（状态机只允许 DRAFT / CHECK_REJECTED → IN_APPROVAL）。"""
        rec = await _make_record(client, auth, db_session, project_id, workspace)
        await client.post(
            _url(rec, "submit-approval"), headers=auth, json={"approval_role": "CHECKER"}
        )

        resp = await client.post(
            _url(rec, "submit-approval"), headers=auth, json={"approval_role": "CHECKER"}
        )

        assert resp.status_code == 409, resp.text


class TestApprovalStep:
    async def _submitted(self, client, auth, db_session, project_id, workspace, depth=1, **kw):
        rec = await _make_record(client, auth, db_session, project_id, workspace, **kw)
        # 深度由 submit-approval 的请求体声明（端点会写 approval_depth），
        # 所以这里必须显式传 —— 只在建记录时设好会被 submit 覆写回缺省 1。
        r = await client.post(
            _url(rec, "submit-approval"),
            headers=auth,
            json={"approval_role": "CHECKER", "approval_depth": depth},
        )
        assert r.status_code == 200, r.text
        return rec

    async def test_pass_on_last_step_checks_the_record(
        self, client, auth, db_session, project_id, workspace
    ):
        """深度 1 ⇒ 一次通过即 CHECKED。"""
        rec = await self._submitted(client, auth, db_session, project_id, workspace)

        resp = await client.post(
            _url(rec, "approval-step"), headers=_checker_auth(), json={"decision": "PASS"}
        )

        assert resp.status_code == 200, resp.text
        await db_session.refresh(rec)
        assert rec.sign_status == RecordSignStatus9.CHECKED

    async def test_pass_before_last_depth_stays_in_approval(
        self, client, auth, db_session, project_id, workspace
    ):
        """深度 3 批第 1 次 ⇒ 仍 IN_APPROVAL，approval_step 前进。

        少了这一步，「Step n/N」的进度条永远停在 1/N，用户看不出还剩几步。
        """
        rec = await self._submitted(
            client, auth, db_session, project_id, workspace, depth=3
        )

        resp = await client.post(
            _url(rec, "approval-step"), headers=_checker_auth(), json={"decision": "PASS"}
        )

        assert resp.status_code == 200, resp.text
        assert resp.json()["approval_step"] == 2
        assert resp.json()["approval_depth"] == 3
        await db_session.refresh(rec)
        assert rec.sign_status == RecordSignStatus9.IN_APPROVAL
        assert rec.approval_step == 2

    async def test_depth_exhaustion_is_reported_as_n_of_n(
        self, client, auth, db_session, project_id, workspace
    ):
        """批到第 N/N 步 ⇒ CHECKED 且响应里的 step == depth。

        「深度耗尽后拒绝」是计划点名的行为：再往后批没有依据了，
        静默继续会让第 4 级凭空存在。
        """
        rec = await self._submitted(
            client, auth, db_session, project_id, workspace, depth=2
        )
        first = await client.post(
            _url(rec, "approval-step"), headers=_checker_auth(), json={"decision": "PASS"}
        )
        assert first.status_code == 200, first.text

        second = await client.post(
            _url(rec, "approval-step"), headers=_checker_auth(), json={"decision": "PASS"}
        )

        assert second.status_code == 200, second.text
        assert second.json()["approval_step"] == 2
        assert second.json()["approval_depth"] == 2
        await db_session.refresh(rec)
        assert rec.sign_status == RecordSignStatus9.CHECKED

        third = await client.post(
            _url(rec, "approval-step"), headers=_checker_auth(), json={"decision": "PASS"}
        )
        assert third.status_code == 409, third.text

    async def test_intermediate_step_is_audited(
        self, client, auth, db_session, project_id, workspace
    ):
        """中间步骤**必须留痕** —— 记录表上没有「第几步谁批的」列。

        深度 > 1 时记录只在深度耗尽那一步发状态机事件；不另写审计的话，
        前 N-1 步的批准人彻底无从追溯，而审计是唯一去处。
        """
        from sqlalchemy import select

        from app.models.enums import AuditAction
        from app.models.system import AuditLog

        rec = await self._submitted(
            client, auth, db_session, project_id, workspace, depth=3
        )
        await client.post(
            _url(rec, "approval-step"), headers=_checker_auth(), json={"decision": "PASS"}
        )

        rows = (await db_session.execute(select(AuditLog))).scalars().all()
        steps = [
            r.detail_json
            for r in rows
            if r.action == AuditAction.APPROVAL_STEP_PASSED.value
        ]
        assert steps, "中间步骤没有审计"
        assert steps[0]["approval_step"] == 2
        assert steps[0]["approval_depth"] == 3

    async def test_reject_returns_to_check_rejected(
        self, client, auth, db_session, project_id, workspace
    ):
        rec = await self._submitted(
            client, auth, db_session, project_id, workspace, depth=3
        )

        resp = await client.post(
            _url(rec, "approval-step"),
            headers=_checker_auth(),
            json={"decision": "REJECT", "reason": "数据有问题"},
        )

        assert resp.status_code == 200, resp.text
        await db_session.refresh(rec)
        assert rec.sign_status == RecordSignStatus9.CHECK_REJECTED

    async def test_only_the_pending_role_may_approve(
        self, client, auth, db_session, project_id, workspace
    ):
        """`approval_role=CHECKER` 时，APPROVER 也不能代批。

        矩阵把待批角色写进记录就是为了这个；端点不校验等于那列是装饰。
        """
        rec = await self._submitted(client, auth, db_session, project_id, workspace)

        from app.core.security import create_access_token

        approver = {
            "Authorization": f"Bearer {create_access_token(subject='app', role='APPROVER')}"
        }
        resp = await client.post(
            _url(rec, "approval-step"), headers=approver, json={"decision": "PASS"}
        )

        assert resp.status_code == 403, resp.text
        assert resp.json()["code"] == "APPROVAL_ROLE_MISMATCH"

    async def test_only_allowed_transitions_are_accepted(
        self, client, auth, db_session, project_id, workspace
    ):
        """非法转移的**集合**在服务端裁掉，不靠前端过滤。

        计划的点名要求：DRAFT 记录不能直接批（必须先 submit）。
        """
        rec = await _make_record(client, auth, db_session, project_id, workspace)

        resp = await client.post(
            _url(rec, "approval-step"), headers=_checker_auth(), json={"decision": "PASS"}
        )

        assert resp.status_code == 409, resp.text

    async def test_unknown_decision_is_422(self, client, auth, db_session, project_id, workspace):
        rec = await self._submitted(client, auth, db_session, project_id, workspace)

        resp = await client.post(
            _url(rec, "approval-step"), headers=_checker_auth(), json={"decision": "MAYBE"}
        )

        assert resp.status_code == 422, resp.text


class TestAbandonChange:
    async def test_abandon_returns_changed_pending_to_checked(
        self, client, auth, db_session, project_id, workspace
    ):
        """放弃变更 ⇒ CHANGE_PENDING → CHECKED，写放弃时间与理由。

        这是 B4 Step 0 判定的正面证据：`approve_change_notice` 做的是
        PENDING → APPROVED（交付物），与本端点方向相反。
        """
        rec = await _make_record(
            client, auth, db_session, project_id, workspace,
            sign_status=RecordSignStatus9.CHANGE_PENDING,
        )

        resp = await client.post(
            _url(rec, "abandon-change"), headers=auth, json={"reason": "上游撤销了变更"}
        )

        assert resp.status_code == 200, resp.text
        await db_session.refresh(rec)
        assert rec.sign_status == RecordSignStatus9.CHECKED
        assert rec.change_abandoned_at is not None
        assert rec.change_abandoned_reason == "上游撤销了变更"

    async def test_abandon_is_rejected_when_not_change_pending(
        self, client, auth, db_session, project_id, workspace
    ):
        """只有 CHANGE_PENDING 能放弃。CHECKED 直接弃 ⇒ 409。

        没有这条，用户可以对一条正常记录点「放弃变更」而系统默默接受，
        写下一条 change_abandoned_at 让它看起来「变更被放弃过」。
        """
        rec = await _make_record(client, auth, db_session, project_id, workspace)

        resp = await client.post(
            _url(rec, "abandon-change"), headers=auth, json={"reason": "x"}
        )

        assert resp.status_code == 409, resp.text

    async def test_abandon_writes_change_abandoned_audit(
        self, client, auth, db_session, project_id, workspace
    ):
        """审计必须是 `CHANGE_ABANDONED` —— 「放弃过」要能查出来。"""
        from sqlalchemy import select

        from app.models.enums import AuditAction
        from app.models.system import AuditLog

        rec = await _make_record(
            client, auth, db_session, project_id, workspace,
            sign_status=RecordSignStatus9.CHANGE_PENDING,
        )
        await client.post(
            _url(rec, "abandon-change"), headers=auth, json={"reason": "上游撤销了变更"}
        )

        rows = (await db_session.execute(select(AuditLog))).scalars().all()
        assert AuditAction.CHANGE_ABANDONED.value in [r.action for r in rows]

    async def test_abandon_requires_reason(self, client, auth, db_session, project_id, workspace):
        rec = await _make_record(
            client, auth, db_session, project_id, workspace,
            sign_status=RecordSignStatus9.CHANGE_PENDING,
        )

        resp = await client.post(_url(rec, "abandon-change"), headers=auth, json={"reason": ""})

        assert resp.status_code == 422, resp.text


class TestResponseContract:
    async def test_no_bare_dict_responses_in_new_router(self):
        """结构性断言：新 router 里不得出现 `response_model=dict`。

        逐端点测只覆盖已写测试的那几个；这条覆盖**将来新增**的端点 ——
        那才是裸字段增长的实际来源。
        """
        from app.api.v1 import records_actions

        offenders = [
            r.path
            for r in records_actions.router.routes
            if getattr(r, "response_model", None) in (dict, list[dict])
        ]
        assert not offenders, f"新 router 出现裸 dict 响应：{offenders}"
