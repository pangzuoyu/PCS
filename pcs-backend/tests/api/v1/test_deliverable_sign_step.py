"""交付物 sign-step 端点测试（P9A B2 / SPEC P9A-DLV-007）。

sign-step 是签署矩阵 `steps_json` 的**第一个消费方**（此前该列无任何 service）。
每签一步同时写一行 `workflow_progress` —— 那是甘特图唯一的���据源。

## 最要紧的两条

- `test_sign_step_writes_progress_via_service_not_api`（ADR-0047 §①）：
  直接调 service（不经 HTTP）也必须写观测。cron / 事件驱动的调用路径
  完全绕过 API 层，写在 API 层会让它们在观测层里系统性隐形且不报错。
- `test_reversal_of_a_step_does_not_silently_pass`：`decision=RETURN`
  与 `SKIP` 是**相反于** `SIGN` 的动作，只接通 SIGN 会让「退回」永远 500，
  而用户看到的是「我按了退回，什么都没发生」。
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.deliverable import (
    Deliverable,
    DeliverableVersion,
    ProjectSignatureMatrixBinding,
    SignatureMatrix,
)
from app.models.enums import DeliverableSignStatus, WorkflowProgressState, WorkflowType
from app.models.workflow_progress import WorkflowProgress
from app.models.notification import Notification, NotificationKind
from app.services.deliverable_service import DeliverableService

pytestmark = pytest.mark.asyncio


@pytest.fixture
def auth(sample_user_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {sample_user_token}"}


def _token(*, subject: str, role: str) -> dict[str, str]:
    from app.core.security import create_access_token

    return {"Authorization": f"Bearer {create_access_token(subject=subject, role=role)}"}


def _actor_id(subject: str = "test-user") -> uuid.UUID:
    """token 的 subject 推导出的 user_id（`current_actor` 的规则：uuid5(DNS, sub)）。

    必须复刻这条推导，否则测试里造不出「提交人 == 当前办理人」的情形 ——
    而那正是 can_self_check 这条矩阵配置存在的理由。
    """
    return uuid.uuid5(uuid.NAMESPACE_DNS, subject)


async def _matrix(db: AsyncSession, steps: list) -> SignatureMatrix:
    row = SignatureMatrix(
        matrix_name="签署矩阵",
        module="*",
        doc_type="CALCULATION_BOOK",
        version_purpose="ISSUED_FOR_CONSTRUCTION",
        steps_json=steps,
        status="ACTIVE",
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


def _steps(*, can_skip: bool = False, can_self_check: bool = True) -> list:
    """两步矩阵：设计 → 复核。默认不许跳过。"""
    return [
        {
            "step_order": 1,
            "sign_role": "DESIGNER",
            "required": True,
            "can_self_check": can_self_check,
            "can_skip": can_skip,
        },
        {
            "step_order": 2,
            "sign_role": "REVIEWER",
            "required": True,
            "can_self_check": True,
            "can_skip": can_skip,
        },
    ]


async def _issued(
    db: AsyncSession,
    project_id: uuid.UUID,
    *,
    steps: list | None = None,
    matrix: SignatureMatrix | None = None,
    submitter_id: uuid.UUID | None = None,
) -> tuple[Deliverable, DeliverableVersion]:
    """一个已签发（sign_status=PENDING）的交付物 + 它的版本行。"""
    matrix = matrix or await _matrix(db, steps if steps is not None else _steps())
    db.add(
        ProjectSignatureMatrixBinding(
            project_id=project_id, module="RECORD", matrix_id=matrix.matrix_id
        )
    )
    deliverable = Deliverable(
        matrix_id=matrix.matrix_id,
        project_id=project_id,
        deliverable_type="CALCULATION_BOOK",
        scope_type="PROJECT_ALL",
        scope_value=str(uuid.uuid4())[:8],
        doc_no="CB-001",
        doc_no_mode="MANUAL",
        title="泵计算书",
        current_rev="1",
        version_purpose="ISSUED_FOR_CONSTRUCTION",
        sign_status=DeliverableSignStatus.PENDING,
    )
    db.add(deliverable)
    await db.commit()
    await db.refresh(deliverable)
    version = DeliverableVersion(
        deliverable_id=deliverable.deliverable_id,
        rev="1",
        version_purpose="ISSUED_FOR_CONSTRUCTION",
        description="签发版本",
        record_snapshot_json={"record_count": 0},
        signature_summary_json={"matrix_id": str(matrix.matrix_id), "steps": []},
        created_by=submitter_id if submitter_id is not None else uuid.uuid4(),
    )
    db.add(version)
    await db.commit()
    await db.refresh(version)
    return deliverable, version


async def _sign(client, auth, deliverable_id, version_id, **body):
    payload = {"version_id": str(version_id), "step_index": 1, "decision": "SIGN", **body}
    return await client.post(
        f"/api/v1/deliverables/{deliverable_id}/sign-step", headers=auth, json=payload
    )


async def _grant_project(db: AsyncSession, user_id: uuid.UUID, project_id: uuid.UUID) -> None:
    """给用户授予项目成员身份（`user_projects` 有效行）。"""
    from app.models.project import UserProject

    db.add(UserProject(user_id=user_id, project_id=project_id, role_in_project="VIEWER"))
    await db.commit()


async def _progress(db: AsyncSession, version_id: uuid.UUID) -> list[WorkflowProgress]:
    return (
        await db.execute(
            select(WorkflowProgress)
            .where(WorkflowProgress.workflow_id == version_id)
            .order_by(WorkflowProgress.step_order)
        )
    ).scalars().all()


class TestSignStepAdvances:
    async def test_signing_first_step_advances_to_second(
        self, client, auth, db_session, project_id
    ):
        d, v = await _issued(db_session, project_id)

        resp = await _sign(client, auth, d.deliverable_id, v.version_id)

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["decision"] == "SIGN"
        assert body["step_index"] == 1
        assert body["state"] == "COMPLETED"
        assert body["deliverable_sign_status"] == "PENDING"

    async def test_signing_last_step_approves_deliverable(
        self, client, auth, db_session, project_id
    ):
        """最后一步签完 ⇒ 交付物 APPROVED。不落这一步，签署流程永远停在 PENDING。"""
        d, v = await _issued(db_session, project_id)
        await _sign(client, auth, d.deliverable_id, v.version_id, step_index=1)
        # 第 2 步矩阵要求 REVIEWER —— 用错角色会撞 403 而不是走到 APPROVED。
        reviewer = _token(subject="rev", role="REVIEWER")

        resp = await _sign(client, reviewer, d.deliverable_id, v.version_id, step_index=2)

        assert resp.status_code == 200, resp.text
        assert resp.json()["state"] == "COMPLETED"
        assert resp.json()["deliverable_sign_status"] == "APPROVED"
        await db_session.refresh(d)
        assert d.sign_status == DeliverableSignStatus.APPROVED

    async def test_only_the_signed_step_may_advance(
        self, client, auth, db_session, project_id
    ):
        """不能跳步：第 2 步在第 1 步签完前不可签。

        否则矩阵的职责分离失效 —— 复核人可以在设计人还没签时就签复核。
        """
        d, v = await _issued(db_session, project_id)

        resp = await _sign(client, auth, d.deliverable_id, v.version_id, step_index=2)

        assert resp.status_code == 409, resp.text
        assert resp.json()["code"] == "SIGN_STEP_OUT_OF_ORDER"


class TestSignStepDecision:
    async def test_return_marks_step_failed_and_reverts_to_draft(
        self, client, auth, db_session, project_id
    ):
        """RETURN 与 SIGN 相反：步骤 FAILED、交付物退回 DRAFT。

        只接通 SIGN 的话，用户按「退回」看到的是 500 ——
        而在签署流程里，退回是唯一能纠错的路径。
        """
        d, v = await _issued(db_session, project_id)

        resp = await _sign(
            client, auth, d.deliverable_id, v.version_id, decision="RETURN"
        )

        assert resp.status_code == 200, resp.text
        assert resp.json()["state"] == "FAILED"
        assert resp.json()["deliverable_sign_status"] == "DRAFT"
        await db_session.refresh(d)
        assert d.sign_status == DeliverableSignStatus.DRAFT

    async def test_skip_is_rejected_when_matrix_forbids_it(
        self, client, auth, db_session, project_id
    ):
        d, v = await _issued(db_session, project_id)  # 默认 can_skip=False

        resp = await _sign(
            client, auth, d.deliverable_id, v.version_id, decision="SKIP"
        )

        assert resp.status_code == 409, resp.text
        assert resp.json()["code"] == "SIGN_STEP_SKIP_FORBIDDEN"

    async def test_skip_is_allowed_when_matrix_permits_it(
        self, client, auth, db_session, project_id
    ):
        d, v = await _issued(db_session, project_id, steps=_steps(can_skip=True))

        resp = await _sign(
            client, auth, d.deliverable_id, v.version_id, decision="SKIP"
        )

        assert resp.status_code == 200, resp.text
        assert resp.json()["state"] == "SKIPPED"

    async def test_unknown_decision_is_422(self, client, auth, db_session, project_id):
        d, v = await _issued(db_session, project_id)

        resp = await _sign(
            client, auth, d.deliverable_id, v.version_id, decision="MAYBE"
        )

        assert resp.status_code == 422, resp.text


class TestSignStepGuards:
    async def test_wrong_role_is_rejected(self, client, db_session, project_id):
        """矩阵第 1 步要 DESIGNER —— 复核人不能代签设计那一步。"""
        d, v = await _issued(db_session, project_id)

        resp = await _sign(
            client, _token(subject="rev", role="REVIEWER"), d.deliverable_id, v.version_id
        )

        assert resp.status_code == 403, resp.text
        assert resp.json()["code"] == "SIGN_STEP_ROLE_MISMATCH"

    async def test_self_check_is_rejected_when_matrix_forbids_it(
        self, client, auth, db_session, project_id
    ):
        """`can_self_check=false` 时，提交人签自己的那一步 ⇒ 403。

        矩阵把这条设成 false 通常意味着「这步必须由第二个人做」；
        忽略它等于让 can_self_check 变成一句没人读的配置。
        """
        d, v = await _issued(
            db_session,
            project_id,
            steps=_steps(can_self_check=False),
            submitter_id=_actor_id(),
        )

        resp = await _sign(client, auth, d.deliverable_id, v.version_id)

        assert resp.status_code == 403, resp.text
        assert resp.json()["code"] == "SIGN_STEP_SELF_CHECK_FORBIDDEN"

    async def test_self_check_is_allowed_when_matrix_permits_it(
        self, client, auth, db_session, project_id
    ):
        """同一矩阵、`can_self_check=true` 时，**提交人可以签自己那一步**。

        提交人刻意设成与 actor 相同（`_actor_id()`）—— 否则这条用例其实测的是
        「别人签」而不是「自校」，矩阵开关的另一半就没被覆盖。
        """
        d, v = await _issued(db_session, project_id, submitter_id=_actor_id())

        resp = await _sign(client, auth, d.deliverable_id, v.version_id)

        assert resp.status_code == 200, resp.text

    async def test_step_index_out_of_range_is_rejected(
        self, client, auth, db_session, project_id
    ):
        """越界步骤 ⇒ 404 + 明确 code。

        ⚠️ 只断言 404 会在**端点还不存在时就绿**（FastAPI 对未注册路径也返 404）——
        那种绿会把「端点没接上」伪装成「边界处理正确」。
        """
        d, v = await _issued(db_session, project_id)

        resp = await _sign(client, auth, d.deliverable_id, v.version_id, step_index=9)

        assert resp.status_code == 404, resp.text
        assert resp.json()["code"] == "SIGN_STEP_NOT_FOUND"

    async def test_signing_a_draft_deliverable_is_rejected(
        self, client, auth, db_session, project_id
    ):
        """未签发（无版本行 / DRAFT）的交付物没有可推进的版本 ⇒ 409。"""
        d, v = await _issued(db_session, project_id)
        await db_session.execute(
            select(DeliverableVersion).where(DeliverableVersion.version_id == v.version_id)
        )
        d.sign_status = DeliverableSignStatus.DRAFT
        await db_session.commit()

        resp = await _sign(client, auth, d.deliverable_id, v.version_id)

        assert resp.status_code == 409, resp.text


class TestSignStepObservation:
    async def test_sign_step_writes_progress_via_service_not_api(
        self, db_session, project_id
    ):
        """ADR-0047 §① 🔒：写入必须在 service 层。

        直接调 service（不经 HTTP）仍要写 workflow_progress —— 否则
        cron / 事件驱动的调用路径（`cia_mark_stale` 由 ARQ cron 驱动，
        完全不过 API 层）会绕过整个观测层，且不报错。
        """
        d, v = await _issued(db_session, project_id)

        await DeliverableService.sign_step(
            db_session,
            deliverable_id=d.deliverable_id,
            version_id=v.version_id,
            step_index=1,
            decision="SIGN",
            actor_user_id=uuid.uuid4(),
            actor_role="DESIGNER",
        )

        rows = await _progress(db_session, v.version_id)
        assert rows, "service 直调必须仍然写观测"
        assert rows[0].workflow_type == WorkflowType.SIGN
        assert rows[0].step_order == 1
        assert rows[0].step_role == "DESIGNER"

    async def test_progress_rows_follow_the_steps(self, client, auth, db_session, project_id):
        """签到第 n 步 ⇒ 第 n 步 COMPLETED、第 n+1 步 IN_PROGRESS。

        甘特图就是这两行拼出来的；少写「下一步 IN_PROGRESS」的话，
        进度条永远停在第一步，看起来像卡住。
        """
        d, v = await _issued(db_session, project_id)

        await _sign(client, auth, d.deliverable_id, v.version_id, step_index=1)

        rows = await _progress(db_session, v.version_id)
        assert [(r.step_order, r.step_status) for r in rows] == [
            (1, WorkflowProgressState.COMPLETED),
            (2, WorkflowProgressState.IN_PROGRESS),
        ]

    async def test_return_records_failed_step(self, client, auth, db_session, project_id):
        d, v = await _issued(db_session, project_id)

        await _sign(client, auth, d.deliverable_id, v.version_id, decision="RETURN")

        rows = await _progress(db_session, v.version_id)
        assert rows[0].step_status == WorkflowProgressState.FAILED


class TestSignStepResponseContract:
    async def test_response_model_has_no_bare_fields(
        self, client, auth, db_session, project_id
    ):
        d, v = await _issued(db_session, project_id)

        resp = await _sign(client, auth, d.deliverable_id, v.version_id)

        assert set(resp.json()) == {
            "deliverable_id",
            "version_id",
            "step_index",
            "step_role",
            "decision",
            "state",
            "deliverable_sign_status",
            "signed_at",
        }


class TestNotificationTriggers:
    """P9A C1b：签署事件触发通知（用户 2026-10-20 裁决的最小集合）。

    断言**落库的那一行**而不是「service 调了 notify」——
    mock 一断就绿，而「接线断了但全绿」正是这条测试最该防的失败。
    """

    async def _rows(self, db, recipient=None):
        stmt = select(Notification)
        if recipient is not None:
            stmt = stmt.where(Notification.recipient_id == recipient)
        return (await db.execute(stmt)).scalars().all()

    async def test_sign_notifies_the_next_steps_role(
        self, client, db_session, project_id, make_user
    ):
        """签完第 1 步 ⇒ 第 2 步的角色（REVIEWER）收到 SIGN_COMPLETED。"""
        reviewer = await make_user("rev", ["REVIEWER"])
        await make_user("des", ["DESIGNER"])
        # ⚠️ 复核人必须有**项目授权**才能收到通知：矩阵的 sign_role 是全局
        # 角色，但项目那一侧只校验成员身份 —— 没有授权的人点进去必然 404。
        await _grant_project(db_session, reviewer, project_id)
        d, v = await _issued(db_session, project_id)

        resp = await _sign(
            client, _token(subject="des", role="DESIGNER"), d.deliverable_id, v.version_id
        )
        assert resp.status_code == 200, resp.text

        rows = await self._rows(db_session)
        assert [r.recipient_id for r in rows] == [reviewer]
        assert rows[0].kind == NotificationKind.SIGN_COMPLETED
        assert str(v.version_id) in rows[0].detail_json["deliverable_version_id"]

    async def test_return_notifies_the_designer_who_was_returned(
        self, client, db_session, project_id, make_user
    ):
        """退回 ⇒ 通知**版本提交人**（要改内容的人），而不是全体 REVIEWER。

        退回的对象是「谁要返工」，所以收件人取 `version.created_by`。
        """
        designer = await make_user("des", ["DESIGNER"])
        d, v = await _issued(db_session, project_id, submitter_id=designer)

        resp = await _sign(
            client, _token(subject="des", role="DESIGNER"),
            d.deliverable_id, v.version_id, decision="RETURN",
        )
        assert resp.status_code == 200, resp.text

        rows = await self._rows(db_session)
        assert [r.recipient_id for r in rows] == [designer]
        assert rows[0].kind == NotificationKind.STEP_RETURNED

    async def test_signer_does_not_notify_themselves(
        self, client, db_session, project_id, make_user
    ):
        """自己签完自己收到通知 = 噪声，且让人误以为还有别人待办。

        ⚠️ 同时断言 REVIEWER **确实**收到了 —— 否则这条在「一个通知都不发」
        的实现下也会绿，而那正是它最该抓的回归。
        """
        designer = await make_user("des", ["DESIGNER"])
        reviewer = await make_user("rev", ["REVIEWER"])
        await _grant_project(db_session, designer, project_id)
        await _grant_project(db_session, reviewer, project_id)
        d, v = await _issued(db_session, project_id, submitter_id=designer)

        await _sign(
            client, _token(subject="des", role="DESIGNER"), d.deliverable_id, v.version_id
        )
        assert await self._rows(db_session, recipient=designer) == []
        assert len(await self._rows(db_session, recipient=reviewer)) == 1


class TestSingleTransactionBoundary:
    """⚠️ F-1：业务变更与通知行必须**同一次提交**。

    两次提交意味着两个真相源：业务变更已落库、通知行还没落库，
    而两者之间进程挂掉 ⇒ 变更发生了但没人被告知。
    提交前推送更糟：commit 失败时用户收到一条会被回滚的通知（phantom）。
    """

    async def test_sign_step_commits_exactly_once(self, db_session, project_id, make_user):
        """签署推进 + 通知行 = **一次** commit。

        ⚠️ 必须让通知**真的发出去**（复核人有项目授权）—— 否则没人可通知时
        第二次 commit 压根不发生，这条断言就成了摆设（它对着旧代码也绿）。
        """
        await make_user("des", ["DESIGNER"])
        reviewer = await make_user("rev", ["REVIEWER"])
        await _grant_project(db_session, reviewer, project_id)
        d, v = await _issued(db_session, project_id)

        calls: list[int] = []
        original = db_session.commit

        async def _counting_commit():
            calls.append(1)
            await original()

        db_session.commit = _counting_commit
        try:
            await DeliverableService.sign_step(
                db_session,
                deliverable_id=d.deliverable_id,
                version_id=v.version_id,
                step_index=1,
                decision="SIGN",
                actor_user_id=uuid.uuid4(),
                actor_role="DESIGNER",
            )
        finally:
            db_session.commit = original

        assert len(calls) == 1, (
            f"sign_step 提交了 {len(calls)} 次 —— 通知行与业务变更不同事务"
        )

    async def test_sign_step_does_not_commit_when_the_step_is_rejected(
        self, db_session, project_id
    ):
        """被拒的签署**一次都不该提交**（否则会留下半截状态）。"""
        d, v = await _issued(db_session, project_id)

        calls: list[int] = []
        original = db_session.commit

        async def _counting_commit():
            calls.append(1)
            await original()

        db_session.commit = _counting_commit
        try:
            with pytest.raises(Exception):
                await DeliverableService.sign_step(
                    db_session,
                    deliverable_id=d.deliverable_id,
                    version_id=v.version_id,
                    step_index=1,
                    decision="SIGN",
                    actor_user_id=uuid.uuid4(),
                    actor_role="REVIEWER",  # 第 1 步要 DESIGNER ⇒ 403
                )
        finally:
            db_session.commit = original

        assert calls == [], f"被拒的签署提交了 {len(calls)} 次"

    async def test_last_step_sign_notifies_the_submitter(
        self, db_session, project_id, make_user
    ):
        """⚠️ F-2：**最后一步签完**（交付物 APPROVED）必须通知版本提交人。

        用户裁决的接线集合写的是「sign-step 成功」—— 字面包含最后一步。
        这一支原先完全没通知任何人。
        """
        designer = await make_user("des", ["DESIGNER"])
        await make_user("rev", ["REVIEWER"])
        d, v = await _issued(db_session, project_id, submitter_id=designer)

        # 第 1 步（DESIGNER）
        await DeliverableService.sign_step(
            db_session,
            deliverable_id=d.deliverable_id,
            version_id=v.version_id,
            step_index=1,
            decision="SIGN",
            actor_user_id=uuid.uuid4(),
            actor_role="DESIGNER",
        )
        # 第 2 步（REVIEWER）= 最后一步 ⇒ APPROVED
        await DeliverableService.sign_step(
            db_session,
            deliverable_id=d.deliverable_id,
            version_id=v.version_id,
            step_index=2,
            decision="SIGN",
            actor_user_id=uuid.uuid4(),
            actor_role="REVIEWER",
        )

        rows = (
            await db_session.execute(
                select(Notification).where(Notification.recipient_id == designer)
            )
        ).scalars().all()
        assert [r.kind for r in rows] == [NotificationKind.SIGN_COMPLETED], (
            "最后一步签完（交付物 APPROVED）必须通知版本提交人 —— "
            "他等的就是这个结果"
        )
