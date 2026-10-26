"""`GET /deliverables/{id}/actions` 测试（P9A B4d）。

## 数据源：本轮定为 `audit_logs`（总纲「尚未解决」第 2 条到此关闭）

原问题：「4 个既有读端点里没有『动作历史』。来自 `audit_logs` 还是新表？」
⇒ **选 `audit_logs`，不建新表**。理由：

1. 动作已经**逐条**写进审计了（`DELIVERABLE_ISSUED` / `DELIVERABLE_SIGNED` /
   `CUSTOMER_APPROVAL_PROXIED` / `CHANGE_NOTICE_APPROVED`），再建一张表就是
   **第二份动作历史** —— 两份会漂移，而漂移的那份没人会去对。
2. 新表要额外回答「谁负责往里写」；审计已有唯一的写入口（`AuditService.write`）。

⚠️ `resource_id` 是**多态**的：`deliverable` 类动作记交付物 ID，
`deliverable_version` 类动作记版本 ID。所以要把该交付物名下所有版本的
动作并进来 —— 漏了它，`sign-step` 的历史在时间线上会整段消失。

## `detail_json` 在响应里是 JSON **文本**，不是裸 object

`detail_json` 的结构随 action 而变（P9A-DLV-010 的裸字段基线 71 不得上涨）。
铺平成 `dict` 就会算成第 72 个裸字段 ⇒ 前端每次都要自己猜结构，
那正是 P8 治理掉的那类「词表不在契约里」。
"""
from __future__ import annotations

import json
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
from app.models.enums import DeliverableSignStatus, WorkflowProgressState

pytestmark = pytest.mark.asyncio


@pytest.fixture
def auth(sample_user_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {sample_user_token}"}


def _checker_auth() -> dict[str, str]:
    from app.core.security import create_access_token

    return {
        "Authorization": f"Bearer {create_access_token(subject='chk', role='CHECKER')}"
    }


async def _pending(
    db: AsyncSession, project_id: uuid.UUID, *, steps: list | None = None
) -> tuple[Deliverable, DeliverableVersion]:
    # ⚠️ **同一项目同一模块只绑一个矩阵**（唯一约束，迁移 `p9_008`）⇒
    # 已有绑定时**复用那个矩阵**（新建一个再改绑，会让先前那条交付物指向的
    # 矩阵**不再绑定** ⇒ 签署路径 409）。
    binding = (
        await db.execute(
            select(ProjectSignatureMatrixBinding).where(
                ProjectSignatureMatrixBinding.project_id == project_id,
                ProjectSignatureMatrixBinding.module == "RECORD",
            )
        )
    ).scalar_one_or_none()
    matrix = await db.get(SignatureMatrix, binding.matrix_id) if binding else None
    if matrix is None:
        matrix = SignatureMatrix(
            matrix_name="矩阵",
            module="*",
            doc_type="CALCULATION_BOOK",
            version_purpose="ISSUED_FOR_CONSTRUCTION",
            steps_json=steps or [
                {"step_order": 1, "sign_role": "CHECKER", "can_self_check": True}
            ],
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
        # doc_no 必须逐条不同：UNIQUE(project_id, doc_no)
        doc_no=f"CB-{uuid.uuid4().hex[:8]}",
        doc_no_mode="MANUAL",
        title="泵计算书",
        current_rev="0",
        version_purpose="INTERNAL_REVIEW",
        sign_status=DeliverableSignStatus.DRAFT,
    )
    db.add(deliverable)
    await db.commit()
    await db.refresh(deliverable)
    version = DeliverableVersion(
        deliverable_id=deliverable.deliverable_id,
        rev="0",
        version_purpose="INTERNAL_REVIEW",
        description="草稿",
        record_snapshot_json={"record_count": 0},
        signature_summary_json={"steps": []},
        created_by=uuid.uuid4(),
    )
    db.add(version)
    await db.commit()
    await db.refresh(version)
    return deliverable, version


class TestDeliverableActions:
    async def test_lists_issue_and_sign_actions(
        self, client, auth, db_session, project_id
    ):
        """签发 + 签署两条动作都要出现在时间线上。

        `sign-step` 的审计记的是**版本 ID**（resource_type=deliverable_version），
        只按交付物 ID 查会漏掉它 —— 而签署历史恰恰是这个端点的主要用途。
        """
        d, v = await _pending(db_session, project_id)
        r = await client.post(
            f"/api/v1/deliverables/{d.deliverable_id}/issue",
            headers=auth,
            json={"version_purpose": "ISSUED_FOR_CONSTRUCTION"},
        )
        assert r.status_code == 200, r.text
        r = await client.post(
            f"/api/v1/deliverables/{d.deliverable_id}/sign-step",
            headers=_checker_auth(),
            json={
                "version_id": r.json()["version_id"],
                "step_index": 1,
                "decision": "SIGN",
            },
        )
        assert r.status_code == 200, r.text

        resp = await client.get(
            f"/api/v1/deliverables/{d.deliverable_id}/actions", headers=auth
        )

        assert resp.status_code == 200, resp.text
        body = resp.json()
        actions = [a["action"] for a in body["items"]]
        assert "DELIVERABLE_ISSUED" in actions, actions
        assert "DELIVERABLE_SIGNED" in actions, actions
        assert body["total"] == len(body["items"])

    async def test_detail_is_json_text_not_a_bare_object(
        self, client, auth, db_session, project_id
    ):
        d, _ = await _pending(db_session, project_id)
        await client.post(
            f"/api/v1/deliverables/{d.deliverable_id}/issue",
            headers=auth,
            json={"version_purpose": "ISSUED_FOR_CONSTRUCTION"},
        )

        resp = await client.get(
            f"/api/v1/deliverables/{d.deliverable_id}/actions", headers=auth
        )

        item = resp.json()["items"][0]
        assert isinstance(item["detail_json"], str)
        parsed = json.loads(item["detail_json"])
        assert parsed["version_purpose"] == "ISSUED_FOR_CONSTRUCTION"

    async def test_actions_are_ordered_oldest_first(
        self, client, auth, db_session, project_id
    ):
        d, _ = await _pending(db_session, project_id)
        for purpose in ("ISSUED_FOR_DESIGN", "ISSUED_FOR_CONSTRUCTION"):
            await client.post(
                f"/api/v1/deliverables/{d.deliverable_id}/issue",
                headers=auth, json={"version_purpose": purpose},
            )

        resp = await client.get(
            f"/api/v1/deliverables/{d.deliverable_id}/actions", headers=auth
        )

        items = resp.json()["items"]
        assert [i["action"] for i in items] == ["DELIVERABLE_ISSUED"] * 2
        assert items[0]["created_at"] <= items[1]["created_at"]

    async def test_does_not_leak_other_deliverables(
        self, client, auth, db_session, project_id
    ):
        """A 的时间线不得含 B 的动作 —— 同项目内也���。"""
        a, _ = await _pending(db_session, project_id)
        b, _ = await _pending(db_session, project_id)
        await client.post(
            f"/api/v1/deliverables/{a.deliverable_id}/issue",
            headers=auth, json={"version_purpose": "ISSUED_FOR_DESIGN"},
        )
        await client.post(
            f"/api/v1/deliverables/{b.deliverable_id}/issue",
            headers=auth, json={"version_purpose": "ISSUED_FOR_BID"},
        )

        resp = await client.get(
            f"/api/v1/deliverables/{a.deliverable_id}/actions", headers=auth
        )

        assert resp.json()["total"] == 1

    async def test_new_deliverable_has_empty_timeline(
        self, client, auth, db_session, project_id
    ):
        d, _ = await _pending(db_session, project_id)

        resp = await client.get(
            f"/api/v1/deliverables/{d.deliverable_id}/actions", headers=auth
        )

        assert resp.status_code == 200, resp.text
        assert resp.json() == {"deliverable_id": str(d.deliverable_id), "items": [], "total": 0}

    async def test_unknown_deliverable_is_404_with_code(self, client, auth):
        """404 必须带 code —— 只断言 404 会在端点不存在时就绿。"""
        resp = await client.get(
            f"/api/v1/deliverables/{uuid.uuid4()}/actions", headers=auth
        )

        assert resp.status_code == 404, resp.text
        assert resp.json()["code"] == "DELIVERABLE_NOT_FOUND"


class TestResponseContract:
    async def test_response_model_has_no_bare_fields(self, client, auth, db_session, project_id):
        d, _ = await _pending(db_session, project_id)

        resp = await client.get(
            f"/api/v1/deliverables/{d.deliverable_id}/actions", headers=auth
        )

        assert set(resp.json()) == {"deliverable_id", "items", "total"}

    async def test_item_model_declares_every_field(self):
        """结构断言：条目模型的字段集合钉死。

        逐端点测只能覆盖已建的那一行；这条覆盖**将来新增**的字段 ——
        而裸字段增长的实际来源就是「顺手往 schema 上加一列」。
        """
        from app.schemas.deliverable_actions import DeliverableActionResponse

        assert set(DeliverableActionResponse.model_fields) == {
            "action", "resource_type", "resource_id",
            "actor_user_id", "detail_json", "created_at",
        }

    async def test_reading_actions_writes_no_observation_rows(
        self, client, auth, db_session, project_id
    ):
        """这个端点是**读审计**，不是观测层 —— 读它不得产生观测行。

        `workflow_progress` 回答「流程到哪一步了」，actions 回答「谁做了什么」。
        两者混在一起，甘特图就会把「有人查过一眼」也算成活动。
        """
        from app.models.workflow_progress import WorkflowProgress

        d, _ = await _pending(db_session, project_id)
        issued = await client.post(
            f"/api/v1/deliverables/{d.deliverable_id}/issue",
            headers=auth, json={"version_purpose": "ISSUED_FOR_DESIGN"},
        )
        await client.post(
            f"/api/v1/deliverables/{d.deliverable_id}/sign-step",
            headers=_checker_auth(),
            json={
                "version_id": issued.json()["version_id"],
                "step_index": 1,
                "decision": "SIGN",
            },
        )
        before = (
            await db_session.execute(select(WorkflowProgress))
        ).scalars().all()
        assert before, "先确认观测行确实存在，否则「没新增」是空断言"

        await client.get(
            f"/api/v1/deliverables/{d.deliverable_id}/actions", headers=auth
        )

        after = (await db_session.execute(select(WorkflowProgress))).scalars().all()
        assert len(after) == len(before)
        assert WorkflowProgressState.COMPLETED in {r.step_status for r in after}
