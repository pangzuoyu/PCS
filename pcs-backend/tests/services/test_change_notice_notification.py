"""变更单审批触发通知（真 DB 路径，P9A C1b / 用户 2026-10-20 最小接线集合）。

`tests/services/test_change_notice_service.py` 走 `_FakeSession`，那里收件人解析
拿不到人，所以只能证明「不会崩」。**通知真的写进去了**由本文件证明 ——
两者缺一不可：只有前者是「没接线」，只有后者是「接线了但会崩」。

## 收件人为什么是项目的 DESIGNER

`ChangeNoticeDetail` **没有申请人字段**（`triggered_by` 是
`MANUAL` / `UPSTREAM_CHANGE` 这样的来源枚举，不是用户）。唯一有既定语义的
受众是项目的设计人 —— 记录状态因这次审批而变了，而他们要重新算。
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

import pytest
from sqlalchemy import select

from app.models.deliverable import (
    ChangeNoticeDetail,
    Deliverable,
    ProjectSignatureMatrixBinding,
    SignatureMatrix,
)
from app.models.enums import DeliverableSignStatus
from app.models.notification import Notification, NotificationKind
from app.models.project import UserProject
from app.services.change_notice_service import ChangeNoticeService

pytestmark = pytest.mark.asyncio


@dataclass
class _Actor:
    user_id: uuid.UUID
    username: str = "approver"
    role: str = "APPROVER"

    @property
    def roles(self) -> list[str]:
        return [self.role]


async def _pending_change_notice(db, project_id: uuid.UUID) -> Deliverable:
    matrix = SignatureMatrix(
        matrix_name="矩阵",
        module="*",
        doc_type="CHANGE_NOTICE",
        version_purpose="ISSUED_FOR_CHANGE",
        steps_json=[{"step_order": 1, "sign_role": "APPROVER"}],
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
        deliverable_type="CHANGE_NOTICE",
        scope_type="PROJECT_ALL",
        scope_value=str(uuid.uuid4())[:8],
        doc_no="CN-001",
        doc_no_mode="MANUAL",
        title="换热器管束变更",
        current_rev="1",
        version_purpose="ISSUED_FOR_CHANGE",
        sign_status=DeliverableSignStatus.PENDING,
    )
    db.add(deliverable)
    await db.flush()
    db.add(
        ChangeNoticeDetail(
            deliverable_id=deliverable.deliverable_id,
            change_type="DESIGN_CHANGE",
            reason="管束材质变更",
            triggered_by="MANUAL",
        )
    )
    await db.commit()
    await db.refresh(deliverable)
    return deliverable


async def test_approval_notifies_project_designers(db, project_id, make_user):
    """审批通过 ⇒ 持 DESIGNER 角色的用户各收到一条 CHANGE_NOTICE_APPROVED。"""
    designer = await make_user("des", ["DESIGNER"])
    await make_user("rev", ["REVIEWER"])  # 复核人不是受众
    # ⚠️ 设计师必须有**项目授权**：通知的收件人 = 全局角色命中 **且** 有项目
    # 授权的人（矩阵的 sign_role 是全局角色，项目侧只校验成员身份）。
    db.add(
        UserProject(user_id=designer, project_id=project_id, role_in_project="VIEWER")
    )
    await db.flush()
    d = await _pending_change_notice(db, project_id)

    await ChangeNoticeService.approve_change_notice(
        db, deliverable_id=d.deliverable_id, actor=_Actor(user_id=uuid.uuid4())
    )

    rows = (await db.execute(select(Notification))).scalars().all()
    recipients = {r.recipient_id for r in rows}
    # ⚠️ conftest 的 `project_id` fixture 会自动给 `user_id` 授一个 DESIGNER 项目
    # 角色，所以收件人不止一个；断言的是**集合成员**而不是全集。
    assert designer in recipients
    assert {r.kind for r in rows} == {NotificationKind.CHANGE_NOTICE_APPROVED}
    mine = next(r for r in rows if r.recipient_id == designer)
    assert mine.detail_json["deliverable_id"] == str(d.deliverable_id)


async def test_approval_with_no_designers_still_succeeds(db, project_id):
    """项目里没有 DESIGNER 时审批照常成功 —— 「没人可通知」不是错误。"""
    d = await _pending_change_notice(db, project_id)

    result = await ChangeNoticeService.approve_change_notice(
        db, deliverable_id=d.deliverable_id, actor=_Actor(user_id=uuid.uuid4())
    )

    assert result["sign_status"] == "APPROVED"
    # `project_id` fixture 自带的那个 DESIGNER 授权仍会产生一条 ——
    # 本测试断言的是「审批不因无人可通知而失败」，不是「一行都不写」。
    assert all(
        r.kind == NotificationKind.CHANGE_NOTICE_APPROVED
        for r in (await db.execute(select(Notification))).scalars().all()
    )
