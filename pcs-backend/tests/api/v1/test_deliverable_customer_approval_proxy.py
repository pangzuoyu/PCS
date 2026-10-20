"""代录客户批准端点测试（P9A B3 / SPEC P9A-DLV-008 / ADR-0007）。

客户在系统外批准，内部授权人把凭证代录进系统。CUSTOMER 签署步骤物理上
没有系统内的人能执行（客户不会有公司 AD 账号），代录是这个缺口唯一的闭环。

## 两条 ADR-0007 的硬约束各有测试

- **代录人不得是该交付物的设计人** —— 否则「客户批准」可以是设计人自己录的，
  签署矩阵的职责分离在这一步形同虚设。
- **凭证附件必填且带 SHA-256** —— 客户批准的唯一物证。哈希由**服务端**算，
  请求里不收 file_hash（收了就等于让客户端自证）。

## 观测写入点 ③（ADR-0047 §①）

代录批准是三条受观测工作流之一，service 层写 `workflow_progress`。
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.deliverable import (
    CustomerApprovalAttachment,
    Deliverable,
    DeliverableVersion,
    ProjectSignatureMatrixBinding,
    SignatureMatrix,
)
from app.models.enums import (
    AuditAction,
    DeliverableSignStatus,
    WorkflowProgressState,
    WorkflowType,
)
from app.models.system import AuditLog
from app.models.workflow_progress import WorkflowProgress
from app.services import ldap_client

pytestmark = pytest.mark.asyncio


@pytest.fixture
def auth(sample_user_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {sample_user_token}"}


def _actor_id(subject: str = "test-user") -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_DNS, subject)


@pytest.fixture
def ldap_ok(monkeypatch):
    def _fake(username: str, password: str) -> ldap_client.LdapUser:
        return ldap_client.LdapUser(
            username=username, dn=f"CN={username}", groups=("CN=PCS",)
        )

    monkeypatch.setattr(ldap_client, "authenticate", _fake)


@pytest.fixture
def ldap_fail(monkeypatch):
    def _fake(username: str, password: str):
        raise ldap_client.LdapAuthError("bind failed")

    monkeypatch.setattr(ldap_client, "authenticate", _fake)


@pytest.fixture
def storage(tmp_path, monkeypatch):
    """把报表存储根指到 tmp_path（凭证按相对路径落盘，哈希由服务端算）。"""
    from app.services.report import paths as report_paths

    monkeypatch.setattr(report_paths, "storage_root", lambda: tmp_path)
    return tmp_path


@pytest.fixture
def credential(storage):
    """默认凭证已落盘；返回它的相对路径。"""
    return _write_credential(storage)


async def _pending(
    db: AsyncSession, project_id: uuid.UUID, *, designer_id: uuid.UUID | None = None
) -> tuple[Deliverable, DeliverableVersion]:
    matrix = SignatureMatrix(
        matrix_name="矩阵",
        module="*",
        doc_type="CALCULATION_BOOK",
        version_purpose="ISSUED_FOR_CONSTRUCTION",
        steps_json=[{"step_order": 1, "sign_role": "DESIGNER"}],
        status="ACTIVE",
    )
    db.add(matrix)
    await db.flush()
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
        signature_summary_json={"steps": []},
        created_by=designer_id if designer_id is not None else uuid.uuid4(),
    )
    db.add(version)
    await db.commit()
    await db.refresh(version)
    return deliverable, version


def _write_credential(
    storage, name: str = "approval.pdf", body: bytes = b"customer-signed"
) -> str:
    """在存储根里放一份凭证，返回它的相对路径。"""
    (storage / name).write_bytes(body)
    return name


def _proxy(client, auth, deliverable_id, version_id, **overrides):
    body = {
        "version_id": str(version_id),
        "file_path": "approval.pdf",
        "file_name": "approval.pdf",
        "file_type": "PDF",
        "approver_name": "张工",
        "approval_date": date(2026, 10, 20).isoformat(),
        "approval_method": "SIGNED_DOC",
        "secondary_username": "alice",
        "secondary_password": "correct-password",
        **overrides,
    }
    return client.post(
        f"/api/v1/deliverables/{deliverable_id}/customer-approval/proxy",
        headers=auth,
        json=body,
    )


class TestProxyRecordsApproval:
    async def test_records_approval_fields(
        self, client, auth, db_session, project_id, ldap_ok, credential
    ):
        d, v = await _pending(db_session, project_id)

        resp = await _proxy(client, auth, d.deliverable_id, v.version_id)

        assert resp.status_code == 200, resp.text
        await db_session.refresh(d)
        assert d.customer_approver_name == "张工"
        assert d.customer_approval_method == "SIGNED_DOC"
        assert d.customer_approval_is_proxy is True
        assert d.customer_approval_proxy_by is not None
        assert d.customer_approval_proxy_at is not None

    async def test_attachment_hash_is_computed_server_side(
        self, client, auth, db_session, project_id, ldap_ok, storage
    ):
        """哈希由服务端从磁盘上的真实文件算 —— 请求里**不收** file_hash。

        收了就等于让客户端自证物证；而物证是客户批准唯一的存在性证明。
        """
        content = b"customer-signed-document-bytes"
        d, v = await _pending(db_session, project_id)

        resp = await _proxy(
            client, auth, d.deliverable_id, v.version_id,
            file_path=_write_credential(storage, body=content),
        )

        assert resp.status_code == 200, resp.text
        attachment = (
            await db_session.execute(select(CustomerApprovalAttachment))
        ).scalar_one()
        assert attachment.file_hash == hashlib.sha256(content).hexdigest()

    async def test_missing_credential_file_is_rejected(
        self, client, auth, db_session, project_id, ldap_ok, storage
    ):
        """凭证不存在 ⇒ 400，不是「记一条没有物证的客户批准」。"""
        d, v = await _pending(db_session, project_id)

        resp = await _proxy(
            client, auth, d.deliverable_id, v.version_id, file_path="nope.pdf"
        )

        assert resp.status_code == 400, resp.text

    async def test_path_escape_is_rejected(
        self, client, auth, db_session, project_id, ldap_ok, credential, storage
    ):
        """`../` 逃出存储根 ⇒ 400。凭证路径来自请求，不校验就是任意文件读。"""
        d, v = await _pending(db_session, project_id)
        (storage.parent / "secret.txt").write_bytes(b"secret")

        resp = await _proxy(
            client, auth, d.deliverable_id, v.version_id,
            file_path="../secret.txt",
        )

        assert resp.status_code == 400, resp.text

    async def test_rejects_designer_recording_own_approval(
        self, client, auth, db_session, project_id, ldap_ok, credential
    ):
        """ADR-0007：代录人不得是该交付物的设计人 ⇒ 403。

        否则「客户已批准」可以是设计人自己录的，签署矩阵的职责分离在
        CUSTOMER 这一步直接失效。
        """
        d, v = await _pending(db_session, project_id, designer_id=_actor_id())

        resp = await _proxy(client, auth, d.deliverable_id, v.version_id)

        assert resp.status_code == 403, resp.text
        assert resp.json()["code"] == "PROXY_RECORDER_IS_DESIGNER"

    async def test_rejects_failed_secondary_auth(
        self, client, auth, db_session, project_id, ldap_fail, credential
    ):
        """二次认证失败 ⇒ 401，且不落任何代录数据。"""
        d, v = await _pending(db_session, project_id)

        resp = await _proxy(client, auth, d.deliverable_id, v.version_id)

        assert resp.status_code == 401, resp.text
        await db_session.refresh(d)
        assert d.customer_approver_name is None
        rows = (await db_session.execute(select(CustomerApprovalAttachment))).scalars().all()
        assert rows == []


class TestProxyAudit:
    async def test_writes_custom_approval_proxied_audit(
        self, client, auth, db_session, project_id, ldap_ok, credential
    ):
        d, v = await _pending(db_session, project_id)

        await _proxy(client, auth, d.deliverable_id, v.version_id)

        rows = (await db_session.execute(select(AuditLog))).scalars().all()
        actions = [r.action for r in rows]
        assert AuditAction.CUSTOMER_APPROVAL_PROXIED.value in actions
        assert AuditAction.SIGN_2FA_FALLBACK.value in actions


class TestProxyObservation:
    async def test_writes_workflow_progress(
        self, client, auth, db_session, project_id, ldap_ok, credential
    ):
        """观测写入点 ③（ADR-0047 §①）：代录批准也要进甘特图。"""
        d, v = await _pending(db_session, project_id)

        await _proxy(client, auth, d.deliverable_id, v.version_id)

        rows = (
            await db_session.execute(
                select(WorkflowProgress).where(
                    WorkflowProgress.workflow_id == d.deliverable_id
                )
            )
        ).scalars().all()
        assert rows, "代录批准必须写观测"
        assert rows[0].workflow_type == WorkflowType.CUSTOMER_APPROVAL_PROXY
        assert rows[0].step_status == WorkflowProgressState.COMPLETED


class TestProxyResponseContract:
    async def test_response_model_has_no_bare_fields(
        self, client, auth, db_session, project_id, ldap_ok, credential
    ):
        d, v = await _pending(db_session, project_id)

        resp = await _proxy(client, auth, d.deliverable_id, v.version_id)

        assert set(resp.json()) == {
            "deliverable_id",
            "version_id",
            "attachment_id",
            "customer_approver_name",
            "approval_date",
            "approval_method",
            "is_proxy",
            "proxied_at",
        }

    async def test_unknown_deliverable_is_404_with_code(
        self, client, auth, ldap_ok, credential
    ):
        """404 必须带 code —— 只断言 404 会在端点不存在时就绿。"""
        resp = await _proxy(client, auth, uuid.uuid4(), uuid.uuid4())

        assert resp.status_code == 404, resp.text
        assert resp.json()["code"] == "DELIVERABLE_NOT_FOUND"


class TestProxyNotificationTrigger:
    """P9A C1b：代录完成触发 PROXY_RECORDED 通知（最小接线集合之一）。

    收件人 = 版本提交人（设计人）。代录闭合的是**他**的交付物的 CUSTOMER 步骤，
    他是唯一因此状态发生变化的人。
    """

    async def test_submitter_is_notified(
        self, client, auth, db_session, project_id, ldap_ok, credential, make_user
    ):
        from app.models.notification import Notification, NotificationKind

        designer = await make_user("des", ["DESIGNER"])
        d, v = await _pending(db_session, project_id, designer_id=designer)

        resp = await _proxy(client, auth, d.deliverable_id, v.version_id)

        assert resp.status_code == 200, resp.text
        rows = (
            await db_session.execute(
                select(Notification).where(Notification.recipient_id == designer)
            )
        ).scalars().all()
        assert [r.kind for r in rows] == [NotificationKind.PROXY_RECORDED]
        assert str(d.deliverable_id) in rows[0].detail_json["deliverable_id"]

    async def test_proxy_still_succeeds_when_push_is_degraded(
        self, client, auth, db_session, project_id, ldap_ok, credential, make_user
    ):
        """Redis 挂掉时代录**照常成功**，通知**照常落库**。

        ADR-0049 §⑤ 约束 2：降级要可观测，但推送失败不得把业务请求带崩 ——
        代录已提交却返 500，用户会以为没录上而重录一次（而 MFA 还会再挡一次）。
        """
        from app.models.notification import Notification
        from app.services.broadcaster import Broadcaster, set_broadcaster

        designer = await make_user("des", ["DESIGNER"])
        d, v = await _pending(db_session, project_id, designer_id=designer)
        dead = Broadcaster("redis://127.0.0.1:6399/0")
        set_broadcaster(dead)
        try:
            resp = await _proxy(client, auth, d.deliverable_id, v.version_id)
        finally:
            set_broadcaster(None)

        assert resp.status_code == 200, resp.text
        assert dead.status == "degraded"
        rows = (
            await db_session.execute(
                select(Notification).where(Notification.recipient_id == designer)
            )
        ).scalars().all()
        assert len(rows) == 1, "推送失败时通知仍必须落库 —— 那是真值来源"
