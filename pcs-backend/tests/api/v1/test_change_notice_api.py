"""变更单闭环端点测试（TODO-068 · P9A-DLV-011 T4 · ADR-0002 / ADR-0008）。

## 完整链路（这组测试走通一遍）

```
CHECKED --initiate-change--> CHANGE_PENDING --apply-change--> CHANGED
       --change-notice--> 变更单（3 级矩阵）--签完最后一步--> 记录回 CHECKED
```

## 这组测试钉住的失败模式

| # | 失败模式 | 期望 |
|---|---|---|
| RF-1 | 记录**到不了 CHANGED** ⇒ 建单端点不可达 | initiate-change /
  apply-change 两个端点存在且可用 |
| RF-2 | **矩阵是装饰品**（谁都能直接批准） | 签署走 sign-step；角色/顺序生效（403/409） |
| RF-3 | 签完了但**记录没关**（永远停在 CHANGED） | 最后一步 SIGN ⇒ 记录自动
  CHECKED + change_resolved_by |
| RF-4 | 驳回后**永久卡死**（DRAFT ⇒ sign 409、issue 409） | 驳回 ⇒ 回 DRAFT +
  记录保持 CHANGED；可再签发并签完 |
| RF-5 | 个人草稿区也能建变更单 | FORMAL 工作区门禁（UI-SPEC §5.3） |
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import delete, select, update

from app.models.calc import ReliefResult
from app.models.deliverable import (
    Deliverable,
    DeliverableRecordBinding,
    DeliverableVersion,
)
from app.models.enums import (
    DeliverableSignStatus,
    RecordSignStatus9,
    ReliefScenario,
    WorkflowProgressState,
    WorkflowType,
)
from app.models.project import Project, Workspace
from app.models.workflow_progress import WorkflowProgress

pytestmark = pytest.mark.asyncio

MODULE = "ReliefResult"


def _uuid(value) -> uuid.UUID:
    """JSON 里的 UUID 是**字符串** ⇒ 与 `Uuid` 列比较前必须转回 UUID 对象。

    ⚠️ 不转的话 SQLAlchemy 的 Uuid bind processor 会去调 `value.hex`
    ⇒ AttributeError（一个看着像「UUID 列坏了」的怪错）。
    """
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def _token(*, role: str, subject: str = "cn-user"):
    from app.core.security import create_access_token

    return {
        "Authorization": f"Bearer "
        f"{create_access_token(subject=subject, role=role)}"
    }


async def _make_project(db, *, workspace_type: str = "FORMAL") -> Project:
    ws = Workspace(workspace_type=workspace_type, name=f"ws-{uuid.uuid4().hex[:8]}")
    db.add(ws)
    await db.flush()
    proj = Project(
        project_no=f"P-{uuid.uuid4().hex[:8]}",
        project_name="变更单测试项目",
        owner_company="测试业主",
        location="测试地点",
        project_type="CHEMICAL",
        design_phase="FEED",
        unit_system="SI",
        workspace_id=ws.workspace_id,
    )
    db.add(proj)
    await db.flush()
    return proj


async def _make_record(db, *, project: Project, sign_status: str) -> ReliefResult:
    rec = ReliefResult(
        project_id=project.project_id,
        workspace_id=uuid.uuid4(),
        source_equipment_id=uuid.uuid4(),
        relief_scenario=ReliefScenario.FIRE,
        sign_status=RecordSignStatus9(sign_status),
        record_hash="h1",
    )
    db.add(rec)
    await db.flush()
    return rec


async def _initiate(client, rec) -> None:
    """发起变更（CHECKED → CHANGE_PENDING）。"""
    init = await client.post(
        f"/api/v1/records/{MODULE}/{rec.relief_id}/initiate-change",
        json={"reason": "要改管径"},
        headers=_token(role="DESIGNER"),
    )
    assert init.status_code == 200, init.text


async def _to_changed(client, rec) -> None:
    """把记录推到 CHANGED（走真实端点）。"""
    await _initiate(client, rec)
    apply = await client.post(
        f"/api/v1/records/{MODULE}/{rec.relief_id}/apply-change",
        json={"reason": "改完了"},
        headers=_token(role="DESIGNER"),
    )
    assert apply.status_code == 200, apply.text


async def _create_notice(client, rec) -> dict:
    resp = await client.post(
        f"/api/v1/records/{MODULE}/{rec.relief_id}/change-notice",
        json={"change_type": "DATA_CORRECTION", "reason": "管径修正"},
        headers=_token(role="DESIGNER"),
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _sign(client, deliverable_id, version_id, *, step: int, role: str,
                decision: str = "SIGN"):
    return await client.post(
        f"/api/v1/deliverables/{deliverable_id}/sign-step",
        json={
            "version_id": str(version_id),
            "step_index": step,
            "decision": decision,
        },
        headers=_token(role=role),
    )


# ---------------------------------------------------------------------------
# RF-1：记录到得了 CHANGED
# ---------------------------------------------------------------------------


async def test_initiate_change_moves_to_change_pending(client, db):
    """CHECKED → CHANGE_PENDING（并自动写 BEFORE_CHANGE 快照）。"""
    proj = await _make_project(db)
    rec = await _make_record(db, project=proj, sign_status="CHECKED")

    resp = await client.post(
        f"/api/v1/records/{MODULE}/{rec.relief_id}/initiate-change",
        json={"reason": "要改管径"},
        headers=_token(role="DESIGNER"),
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["from_status"] == "CHECKED"
    assert resp.json()["to_status"] == "CHANGE_PENDING"


async def test_apply_change_moves_to_changed(client, db):
    """CHANGE_PENDING → CHANGED（等待变更单关闭）。"""
    proj = await _make_project(db)
    rec = await _make_record(db, project=proj, sign_status="CHECKED")
    await _initiate(client, rec)

    resp = await client.post(
        f"/api/v1/records/{MODULE}/{rec.relief_id}/apply-change",
        json={"reason": "改完了"},
        headers=_token(role="DESIGNER"),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["to_status"] == "CHANGED"


async def test_apply_change_rejects_wrong_state(client, db):
    """状态不对 ⇒ 409（`RECORD_INVALID_TRANSITION`）。"""
    proj = await _make_project(db)
    rec = await _make_record(db, project=proj, sign_status="CHECKED")

    resp = await client.post(
        f"/api/v1/records/{MODULE}/{rec.relief_id}/apply-change",
        json={"reason": "还没发起变更"},
        headers=_token(role="DESIGNER"),
    )
    assert resp.status_code == 409, resp.text


# ---------------------------------------------------------------------------
# RF-2/RF-3：建单 + 3 级矩阵 + 自动关记录
# ---------------------------------------------------------------------------


async def test_create_change_notice_from_changed_record(client, db):
    """建单 ⇒ 交付物 + 版本 + 记录绑定 + 观测 PENDING。"""
    proj = await _make_project(db)
    rec = await _make_record(db, project=proj, sign_status="CHANGED")

    body = await _create_notice(client, rec)

    assert body["sign_status"] == "PENDING"
    assert body["doc_no"].startswith("CN-")
    assert body["detail"]["change_type"] == "DATA_CORRECTION"

    deliverable = (
        await db.execute(
            select(Deliverable).where(
                Deliverable.deliverable_id == _uuid(body["deliverable_id"])
            )
        )
    ).scalar_one()
    assert deliverable.deliverable_type == "CHANGE_NOTICE"
    assert deliverable.sign_status == DeliverableSignStatus.PENDING

    versions = (
        await db.execute(
            select(DeliverableVersion).where(
                DeliverableVersion.deliverable_id == _uuid(body["deliverable_id"])
            )
        )
    ).scalars().all()
    assert len(versions) == 1
    assert versions[0].version_purpose == "ISSUED_FOR_CHANGE"

    bindings = (
        await db.execute(
            select(DeliverableRecordBinding).where(
                DeliverableRecordBinding.deliverable_version_id == _uuid(body["version_id"])
            )
        )
    ).scalars().all()
    assert len(bindings) == 1
    assert str(bindings[0].record_id) == str(rec.relief_id)

    obs = (
        await db.execute(
            select(WorkflowProgress).where(
                WorkflowProgress.workflow_type == WorkflowType.CHANGE_NOTICE
            )
        )
    ).scalars().all()
    assert len(obs) == 1
    assert obs[0].step_status == WorkflowProgressState.PENDING
    assert str(obs[0].workflow_id) == body["deliverable_id"]


async def test_create_change_notice_rejects_non_changed_record(client, db):
    """记录不是 CHANGED ⇒ 422（服务层的既有契约）。"""
    proj = await _make_project(db)
    rec = await _make_record(db, project=proj, sign_status="CHECKED")

    resp = await client.post(
        f"/api/v1/records/{MODULE}/{rec.relief_id}/change-notice",
        json={"change_type": "DATA_CORRECTION", "reason": "x"},
        headers=_token(role="DESIGNER"),
    )
    assert resp.status_code == 422, resp.text
    assert resp.json()["code"] == "CHANGE_NOTICE_BAD_STATE"


async def test_matrix_role_is_enforced(client, db):
    """⚠️ RF-2：矩阵**真的生效** —— 第 1 步要 CHECKER，REVIEWER 来签 ⇒ 403。"""
    proj = await _make_project(db)
    rec = await _make_record(db, project=proj, sign_status="CHANGED")
    body = await _create_notice(client, rec)

    resp = await _sign(
        client,
        body["deliverable_id"],
        body["version_id"],
        step=1,
        role="REVIEWER",
    )
    assert resp.status_code == 403, resp.text
    assert resp.json()["code"] == "SIGN_STEP_ROLE_MISMATCH"


async def test_full_closure_closes_the_record(client, db):
    """⚠️ RF-3：3 级签完 ⇒ 记录自动 CHECKED + change_resolved_by + 观测 COMPLETED。"""
    proj = await _make_project(db)
    rec = await _make_record(db, project=proj, sign_status="CHANGED")
    body = await _create_notice(client, rec)

    for step, role in ((1, "CHECKER"), (2, "REVIEWER"), (3, "APPROVER")):
        resp = await _sign(
            client, body["deliverable_id"], body["version_id"], step=step, role=role
        )
        assert resp.status_code == 200, resp.text

    await db.refresh(rec)
    assert rec.sign_status == RecordSignStatus9.CHECKED.value
    assert rec.change_resolved_by  # 记录了是谁关的

    obs = (
        await db.execute(
            select(WorkflowProgress).where(
                WorkflowProgress.workflow_type == WorkflowType.CHANGE_NOTICE,
                WorkflowProgress.workflow_id == _uuid(body["deliverable_id"]),
            )
        )
    ).scalar_one()
    assert obs.step_status == WorkflowProgressState.COMPLETED
    assert obs.completed_at is not None


async def test_return_keeps_record_changed_and_allows_reissue(client, db):
    """⚠️ RF-4：驳回 ⇒ 变更单回 DRAFT、**记录保持 CHANGED**；可再签发并签完。

    ADR-0008：「被驳回则回 DRAFT，绑定记录保持 CHANGED」。
    ⚠️ 不重新签发的话，变更单**永久卡死**（DRAFT ⇒ sign-step 409、
    issue 409 ⇒ 永远签不了）—— 所以这里必须能再签发。
    """
    proj = await _make_project(db)
    rec = await _make_record(db, project=proj, sign_status="CHANGED")
    body = await _create_notice(client, rec)

    rejected = await _sign(
        client,
        body["deliverable_id"],
        body["version_id"],
        step=1,
        role="CHECKER",
        decision="RETURN",
    )
    assert rejected.status_code == 200, rejected.text

    deliverable = (
        await db.execute(
            select(Deliverable).where(
                Deliverable.deliverable_id == _uuid(body["deliverable_id"])
            )
        )
    ).scalar_one()
    assert deliverable.sign_status == DeliverableSignStatus.DRAFT

    await db.refresh(rec)
    assert rec.sign_status == RecordSignStatus9.CHANGED.value, "驳回不改记录"

    # 再签发一个新版本 ⇒ 能重新走完 3 级
    issued = await client.post(
        f"/api/v1/deliverables/{body['deliverable_id']}/issue",
        json={"version_purpose": "ISSUED_FOR_CHANGE"},
        headers=_token(role="DESIGNER"),
    )
    assert issued.status_code == 200, issued.text
    new_version = issued.json()["version_id"]

    for step, role in ((1, "CHECKER"), (2, "REVIEWER"), (3, "APPROVER")):
        resp = await _sign(
            client, body["deliverable_id"], new_version, step=step, role=role
        )
        assert resp.status_code == 200, resp.text

    await db.refresh(rec)
    assert rec.sign_status == RecordSignStatus9.CHECKED.value


# ---------------------------------------------------------------------------
# RF-5：工作区门禁
# ---------------------------------------------------------------------------


async def test_change_notice_requires_formal_workspace(client, db):
    """⚠️ RF-5：个人草稿区 ⇒ 403（UI-SPEC §5.3）。"""
    proj = await _make_project(db, workspace_type="PERSONAL")
    rec = await _make_record(db, project=proj, sign_status="CHANGED")

    resp = await client.post(
        f"/api/v1/records/{MODULE}/{rec.relief_id}/change-notice",
        json={"change_type": "DATA_CORRECTION", "reason": "x"},
        headers=_token(role="DESIGNER"),
    )
    assert resp.status_code == 403, resp.text
    assert resp.json()["code"] == "WORKSPACE_TYPE_NOT_ALLOWED"


# ---------------------------------------------------------------------------
# 契约
# ---------------------------------------------------------------------------


async def test_change_notice_response_has_no_bare_fields(client, db):
    """零裸字段（P9A-DLV-010）。"""
    proj = await _make_project(db)
    rec = await _make_record(db, project=proj, sign_status="CHANGED")

    body = await _create_notice(client, rec)

    assert set(body) == {
        "deliverable_id",
        "version_id",
        "workflow_id",
        "matrix_id",
        "project_id",
        "doc_no",
        "title",
        "sign_status",
        "detail",
    }
    assert set(body["detail"]) == {
        "detail_id",
        "change_type",
        "reason",
        "triggered_by",
        "source_record_type",
    }


async def test_close_refuses_to_resurrect_a_moved_record(client, db):
    """⚠️ 记录在变更单签完前**被别处改过**（不再是 CHANGED）⇒ **不许**被关成 CHECKED。

    「关记录」是把状态写成 CHECKED ⇒ 若记录此刻已是 OBSOLETE（被弃用），
    无条件写 CHECKED 就会**复活一条已作废的记录**。
    ⇒ 关之前先看它是不是还在 CHANGED；不是 ⇒ 响亮失败（409）。
    """
    proj = await _make_project(db)
    rec = await _make_record(db, project=proj, sign_status="CHANGED")
    body = await _create_notice(client, rec)

    # 记录在变更单签完前被改成了别的状态
    rec.sign_status = RecordSignStatus9.OBSOLETE.value
    await db.flush()

    for step, role in ((1, "CHECKER"), (2, "REVIEWER"), (3, "APPROVER")):
        resp = await _sign(
            client, body["deliverable_id"], body["version_id"], step=step, role=role
        )
    assert resp.status_code == 409, resp.text
    assert resp.json()["code"] == "CHANGE_NOTICE_RECORD_BAD_STATE"

    await db.refresh(rec)
    assert rec.sign_status == RecordSignStatus9.OBSOLETE.value, "不许复活记录"


async def test_second_reissue_returns_409_not_500(client, db):
    """⚠️ **再签发一次必须是 409，不是 500**。

    R-5 放宽了 `issue` 的幂等判据（退回后可再签发）⇒ 同一 (交付物, 版本目的)
    可能有**多行**版本 ⇒ 若幂等探针是「取那一行」（`scalar_one_or_none()`）⇒
    多行时抛 `MultipleResultsFound` ⇒ **500**（而本该是 409）。
    ⇒ 「驳回 → 再签发」这条流程只能走一次，第二次就死。
    """
    proj = await _make_project(db)
    rec = await _make_record(db, project=proj, sign_status="CHANGED")
    body = await _create_notice(client, rec)

    # 第一次退回 ⇒ 交付物回 DRAFT
    rejected = await _sign(
        client,
        body["deliverable_id"],
        body["version_id"],
        step=1,
        role="CHECKER",
        decision="RETURN",
    )
    assert rejected.status_code == 200, rejected.text

    # 第一次再签发 ⇒ 版本 2
    first = await client.post(
        f"/api/v1/deliverables/{body['deliverable_id']}/issue",
        json={"version_purpose": "ISSUED_FOR_CHANGE"},
        headers=_token(role="DESIGNER"),
    )
    assert first.status_code == 200, first.text

    # 第二次再签发（此时同 purpose 已有 2 行版本）⇒ 必须 409
    second = await client.post(
        f"/api/v1/deliverables/{body['deliverable_id']}/issue",
        json={"version_purpose": "ISSUED_FOR_CHANGE"},
        headers=_token(role="DESIGNER"),
    )
    assert second.status_code == 409, second.text
    assert second.json()["code"] == "DELIVERABLE_ALREADY_ISSUED"


# ---------------------------------------------------------------------------
# RF-6：关记录时的**响亮失败**（静默跳过 = 变更单批了而记录永远停在 CHANGED）
# ---------------------------------------------------------------------------


async def test_sign_without_record_binding_fails_loudly(client, db):
    """⚠️ 变更单**没有**记录绑定 ⇒ 签到最后一步 ⇒ 409
    `CHANGE_NOTICE_RECORD_LINK_MISSING`（**不**静默跳过）。

    静默跳过 = 「变更单批了而记录永远停在 CHANGED」⇒ 业务上查不出来 ⇒
    必须响亮失败。
    """
    proj = await _make_project(db)
    rec = await _make_record(db, project=proj, sign_status="CHANGED")
    body = await _create_notice(client, rec)

    # 拆掉绑定（模拟「关联写丢了」）
    await db.execute(
        delete(DeliverableRecordBinding).where(
            DeliverableRecordBinding.deliverable_version_id == _uuid(body["version_id"])
        )
    )
    await db.commit()

    for step, role in ((1, "CHECKER"), (2, "REVIEWER")):
        resp = await _sign(
            client, body["deliverable_id"], body["version_id"], step=step, role=role
        )
        assert resp.status_code == 200, resp.text

    last = await _sign(
        client, body["deliverable_id"], body["version_id"], step=3, role="APPROVER"
    )
    assert last.status_code == 409, last.text
    assert last.json()["code"] == "CHANGE_NOTICE_RECORD_LINK_MISSING"


async def test_sign_with_unknown_record_type_fails_loudly(client, db):
    """⚠️ 绑定的记录类型**不在注册表**里 ⇒ 409 `CHANGE_NOTICE_RECORD_TYPE_UNKNOWN`。"""
    proj = await _make_project(db)
    rec = await _make_record(db, project=proj, sign_status="CHANGED")
    body = await _create_notice(client, rec)

    await db.execute(
        update(DeliverableRecordBinding)
        .where(
            DeliverableRecordBinding.deliverable_version_id
            == _uuid(body["version_id"])
        )
        .values(record_type="NoSuchRecordType")
    )
    await db.commit()

    for step, role in ((1, "CHECKER"), (2, "REVIEWER")):
        resp = await _sign(
            client, body["deliverable_id"], body["version_id"], step=step, role=role
        )
        assert resp.status_code == 200, resp.text

    last = await _sign(
        client, body["deliverable_id"], body["version_id"], step=3, role="APPROVER"
    )
    assert last.status_code == 409, last.text
    assert last.json()["code"] == "CHANGE_NOTICE_RECORD_TYPE_UNKNOWN"


async def test_rejected_notice_can_be_reworked_via_reversal(client, db):
    """⚠️ 驳回后的**重改路径**可走通（ADR-0002 §修订记录 2026-10-26 的裁决）。

    裁决：**驳回的是「单据」，不是「校核结论」** ⇒
    ① 变更单回 DRAFT，**记录保持 CHANGED**（ADR-0008）；
    ② 要改**数据** ⇒ 走**撤销 → 重来**：request-reversal → reversal-decision
    APPROVE（恢复快照 ⇒ 回 CHECKED）→ 再 initiate-change。

    ⇒ 这条测试把「重改**能走通**」钉住（否则裁决只是文档里的一句话）。
    """
    proj = await _make_project(db)
    rec = await _make_record(db, project=proj, sign_status="CHECKED")
    # 走真实链路：发起 → 提交 → 建单（这样才有 BEFORE_CHANGE 快照可恢复）
    # ⚠️ `_to_changed` 内部**已经**含 initiate ⇒ 这里不要再单独调
    await _to_changed(client, rec)
    body = await _create_notice(client, rec)

    # 第 1 步驳回 ⇒ 单据回 DRAFT，记录**不动**
    reject = await _sign(
        client,
        body["deliverable_id"],
        body["version_id"],
        step=1,
        role="CHECKER",
        decision="RETURN",
    )
    assert reject.status_code == 200, reject.text
    await db.refresh(rec)
    assert rec.sign_status == RecordSignStatus9.CHANGED.value, "驳回只动单据，不动记录"

    # 撤销 ⇒ 批准（恢复快照）⇒ 回 CHECKED
    rev = await client.post(
        f"/api/v1/records/{MODULE}/{rec.relief_id}/request-reversal",
        json={"reason": "数据要改"},
        headers=_token(role="DESIGNER"),
    )
    assert rev.status_code == 200, rev.text

    dec = await client.post(
        f"/api/v1/records/{MODULE}/{rec.relief_id}/reversal-decision",
        json={"decision": "APPROVE", "reason": "同意撤销"},
        headers=_token(role="APPROVER"),
    )
    assert dec.status_code == 200, dec.text
    await db.refresh(rec)
    assert rec.sign_status == RecordSignStatus9.CHECKED.value, "批准撤销 ⇒ 恢复快照回 CHECKED"

    # 重来：又能发起变更了
    again = await client.post(
        f"/api/v1/records/{MODULE}/{rec.relief_id}/initiate-change",
        json={"reason": "重做"},
        headers=_token(role="DESIGNER"),
    )
    assert again.status_code == 200, again.text
    assert again.json()["to_status"] == "CHANGE_PENDING"
