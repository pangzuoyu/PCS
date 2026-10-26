"""`DeliverableService.create_version_row` 的守卫（P9A-DLV-011 · T1）。

它是从 `issue` 里抽出来的**不 commit** 版本创建 helper ——
变更单建单要用它（建单 + 版本 + 绑定 + 观测必须**同一事务**）。

## 这组测试钉住的失败模式

| # | 失败模式 | 期望 |
|---|---|---|
| RF-A | 快照里写的是**原始** `steps_json`（未排序、未过滤、缺省未补齐），
  而签署执行的是归一化后的步骤 ⇒ 快照显示 A/B/C、签署按 C/A/B 推进 | 快照写**归一化**结果
  （与执行同源） |
| RF-B | helper 自己 commit ⇒ 变更单建单的「交付物 + 版本 + 绑定 + 观测」
  被切成两个事务（观测写失败时版本已经提交） | helper **不 commit**
  （事务边界归调用方） |
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.models.deliverable import (
    Deliverable,
    DeliverableVersion,
    ProjectSignatureMatrixBinding,
    SignatureMatrix,
)
from app.models.enums import DeliverableSignStatus
from app.services.deliverable_service import DeliverableService


@pytest.mark.asyncio
async def test_version_snapshot_steps_are_normalized(db, project_id):
    """⚠️ RF-A：快照里的 steps 必须与签署**同源**（归一化后的）。

    `steps_json` 的顺序不保证 ⇒ 原始值写进快照 ⇒ 快照显示的顺序与实际
    签署顺序不一致（甘特图/快照与执行对不上）。
    """
    matrix = SignatureMatrix(
        matrix_name="乱序矩阵",
        module="*",
        doc_type="CALCULATION_BOOK",
        version_purpose="ISSUED_FOR_CONSTRUCTION",
        steps_json=[
            {"step_order": 3, "sign_role": "APPROVER"},
            {"step_order": 1, "sign_role": "CHECKER"},
            {"step_order": 2, "sign_role": "REVIEWER"},
        ],
        status="ACTIVE",
    )
    db.add(matrix)
    await db.flush()
    db.add(
        ProjectSignatureMatrixBinding(
            project_id=project_id, module="*", matrix_id=matrix.matrix_id
        )
    )
    deliverable = Deliverable(
        project_id=project_id,
        deliverable_type="CALCULATION_BOOK",
        scope_type="PROJECT_ALL",
        scope_value="ALL",
        doc_no="CB-1",
        doc_no_mode="MANUAL",
        title="计算书",
        current_rev="0",
        version_purpose="DRAFT",
        sign_status=DeliverableSignStatus.DRAFT,
        matrix_id=matrix.matrix_id,
    )
    db.add(deliverable)
    await db.flush()

    version = await DeliverableService.create_version_row(
        db,
        deliverable=deliverable,
        version_purpose="ISSUED_FOR_CONSTRUCTION",
        actor_user_id=uuid.uuid4(),
    )

    steps = version.signature_summary_json["steps"]
    assert [s["step_order"] for s in steps] == [1, 2, 3]
    assert [s["sign_role"] for s in steps] == ["CHECKER", "REVIEWER", "APPROVER"]
    # 缺省补齐 ⇒ 快照里的步骤与签署时读到的完全一致
    assert steps[0]["can_self_check"] is True
    assert steps[0]["required"] is True
    assert steps[0]["can_skip"] is False


@pytest.mark.asyncio
async def test_create_version_row_does_not_commit(db, project_id):
    """⚠️ RF-B：helper **不 commit** —— 事务边界归调用方。

    变更单的建单要「交付物 + 版本 + 绑定 + 观测 + 审计」一次提交；
    helper 自己提交会把它们切成两段 ⇒ 观测写失败时版本已经落库。
    """
    matrix = SignatureMatrix(
        matrix_name="矩阵",
        module="*",
        doc_type="CALCULATION_BOOK",
        version_purpose="ISSUED_FOR_CONSTRUCTION",
        steps_json=[{"step_order": 1, "sign_role": "CHECKER"}],
        status="ACTIVE",
    )
    db.add(matrix)
    await db.flush()
    deliverable = Deliverable(
        project_id=project_id,
        deliverable_type="CALCULATION_BOOK",
        scope_type="PROJECT_ALL",
        scope_value="ALL",
        doc_no="CB-2",
        doc_no_mode="MANUAL",
        title="计算书",
        current_rev="0",
        version_purpose="DRAFT",
        sign_status=DeliverableSignStatus.DRAFT,
        matrix_id=matrix.matrix_id,
    )
    db.add(deliverable)
    await db.flush()

    await DeliverableService.create_version_row(
        db,
        deliverable=deliverable,
        version_purpose="ISSUED_FOR_CONSTRUCTION",
        actor_user_id=uuid.uuid4(),
    )

    # 未提交 ⇒ 另一个连接看不到这些行（用同一个 session 查得到，但那是
    # session 自己的未提交状态；这里断言的是「没有 commit 发生」：
    # 提交过的行会出现在 workflow_progress 之类的旁路证据里，
    # 故直接断言 **本 session 内未提交** 的语义 —— 用 expire 后的刷新验证）
    await db.rollback()
    rows = (
        await db.execute(
            select(DeliverableVersion).where(
                DeliverableVersion.deliverable_id == deliverable.deliverable_id
            )
        )
    ).scalars().all()
    assert rows == [], "helper 不该提交 ⇒ 回滚后版本行不存在"
