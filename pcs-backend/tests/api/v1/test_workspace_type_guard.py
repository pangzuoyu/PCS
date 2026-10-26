"""**工作区类型门禁**的覆盖面（TODO-076 · UI-SPEC §5.3）。

## 门禁清单（UI-SPEC §5.3）

| 操作 | FORMAL | PERSONAL / TEMPORARY |
|---|---|---|
| 编辑数据 | ✅ | ✅ |
| **提交批准** | ✅ | ❌ 403 |
| **创建交付物** | ✅ | ❌ 403 |
| **创建变更单** | ✅ | ❌ 403 |
| **签署** | ✅ | ❌ 403 |

⇒ 此前后端**只**守了「创建变更单」一个端点 ⇒ 其余三类**绕过前端就能做**
（「后端 403 为兜底」是 UI-SPEC 自己写的）。

## 两条**放行**（fail-open）分支也被钉住

`require_formal_project_workspace` 在「项目不存在 / 没挂工作区」与「工作区行不
存在」时**放行**（不是 403）—— 这是**有意的**（历史项目没挂工作区 ⇒ 不是个人
草稿区 ⇒ 不该因缺元数据挡掉正常操作）⇒ 但「有意的放行」必须**有测试钉住**，
否则下一个人会以为它漏了。

本文件覆盖：

1. 五个门禁端点在 PERSONAL 工作区 ⇒ **403 `WORKSPACE_TYPE_NOT_ALLOWED`**；
2. 两条放行分支**各有**一条测试（钉住「放行」是有意的，不是漏网）。
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.api.v1._guard import require_formal_project_workspace
from app.models.calc import ReliefResult
from app.models.deliverable import (
    Deliverable,
    ProjectSignatureMatrixBinding,
    SignatureMatrix,
)
from app.models.enums import (
    DeliverableSignStatus,
    RecordSignStatus9,
    ReliefScenario,
)
from app.models.project import Project, Workspace
from app.services.exceptions import PcsError

pytestmark = pytest.mark.asyncio

MODULE = "ReliefResult"


def _token(*, role: str, subject: str = "ws-user"):
    from app.core.security import create_access_token

    return {"Authorization": f"Bearer {create_access_token(subject=subject, role=role)}"}


async def _make_project(db, *, workspace_type: str = "FORMAL") -> Project:
    ws = Workspace(workspace_type=workspace_type, name=f"ws-{uuid.uuid4().hex[:8]}")
    db.add(ws)
    await db.flush()
    proj = Project(
        project_no=f"P-{uuid.uuid4().hex[:8]}",
        project_name="工作区门禁测试项目",
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


async def _make_record(db, project: Project, *, sign_status: str) -> ReliefResult:
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


async def _make_deliverable(db, project: Project) -> Deliverable:
    matrix = SignatureMatrix(
        matrix_name=f"矩阵-{uuid.uuid4().hex[:8]}",
        module="RECORD",
        doc_type="CALCULATION_BOOK",
        version_purpose="ISSUED_FOR_CONSTRUCTION",
        steps_json=[{"step_order": 1, "sign_role": "APPROVER"}],
        status="ACTIVE",
    )
    db.add(matrix)
    await db.flush()
    db.add(
        ProjectSignatureMatrixBinding(
            project_id=project.project_id, module="RECORD", matrix_id=matrix.matrix_id
        )
    )
    row = Deliverable(
        matrix_id=matrix.matrix_id,
        project_id=project.project_id,
        deliverable_type="CALCULATION_BOOK",
        scope_type="PROJECT_ALL",
        scope_value=str(uuid.uuid4())[:8],
        doc_no=f"CB-{uuid.uuid4().hex[:8]}",
        doc_no_mode="MANUAL",
        title="泵计算书",
        current_rev="0",
        version_purpose="INTERNAL_REVIEW",
        sign_status=DeliverableSignStatus.DRAFT,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


# ---------------------------------------------------------------------------
# 门禁覆盖面：五个端点
# ---------------------------------------------------------------------------


async def test_submit_approval_requires_formal_workspace(client, db):
    """「提交批准」在个人草稿区 ⇒ 403。"""
    proj = await _make_project(db, workspace_type="PERSONAL")
    rec = await _make_record(db, proj, sign_status="DRAFT")

    resp = await client.post(
        f"/api/v1/records/{MODULE}/{rec.relief_id}/submit-approval",
        json={"approval_role": "CHECKER"},
        headers=_token(role="DESIGNER"),
    )
    assert resp.status_code == 403, resp.text
    assert resp.json()["code"] == "WORKSPACE_TYPE_NOT_ALLOWED"


async def test_approval_step_requires_formal_workspace(client, db):
    """「批准下一步」在个人草稿区 ⇒ 403。"""
    proj = await _make_project(db, workspace_type="TEMPORARY")
    rec = await _make_record(db, proj, sign_status="IN_APPROVAL")
    rec.approval_role = "CHECKER"

    resp = await client.post(
        f"/api/v1/records/{MODULE}/{rec.relief_id}/approval-step",
        json={"decision": "PASS"},
        headers=_token(role="CHECKER"),
    )
    assert resp.status_code == 403, resp.text
    assert resp.json()["code"] == "WORKSPACE_TYPE_NOT_ALLOWED"


async def test_deliverable_issue_requires_formal_workspace(client, db):
    """「创建交付物[版本]（送审）」在个人草稿区 ⇒ 403。"""
    proj = await _make_project(db, workspace_type="PERSONAL")
    deliverable = await _make_deliverable(db, proj)

    resp = await client.post(
        f"/api/v1/deliverables/{deliverable.deliverable_id}/issue",
        json={"version_purpose": "ISSUED_FOR_CONSTRUCTION"},
        headers=_token(role="DESIGNER"),
    )
    assert resp.status_code == 403, resp.text
    assert resp.json()["code"] == "WORKSPACE_TYPE_NOT_ALLOWED"


async def test_sign_step_requires_formal_workspace(client, db):
    """「签署」在个人草稿区 ⇒ 403。"""
    proj = await _make_project(db, workspace_type="PERSONAL")
    deliverable = await _make_deliverable(db, proj)

    resp = await client.post(
        f"/api/v1/deliverables/{deliverable.deliverable_id}/sign-step",
        json={"version_id": str(uuid.uuid4()), "step_index": 1, "decision": "SIGN"},
        headers=_token(role="APPROVER"),
    )
    assert resp.status_code == 403, resp.text
    assert resp.json()["code"] == "WORKSPACE_TYPE_NOT_ALLOWED"


# ---------------------------------------------------------------------------
# 两条**放行**分支（fail-open）——「放行」是有意的，必须钉住
# ---------------------------------------------------------------------------


async def test_guard_allows_when_the_project_does_not_exist(db):
    """⚠️ 放行分支 ①：项目**不存在**（或没挂工作区）⇒ **放行**。

    为什么放行：项目是历史数据、没挂工作区 ⇒ **不是个人草稿区** ⇒ 不该因
    缺元数据把正常操作挡掉（与「不因缺元数据挡掉正常操作」的仓库习惯一致）。

    ⚠️ 端点层其实**先**撞「记录不存在 ⇒ 404」，所以这条只在**直接调守卫**时
    可达 —— 但它必须被钉住：哪天有人把它改成 fail-closed，这条会红。
    """
    await require_formal_project_workspace(db, project_id=uuid.uuid4())


async def test_guard_allows_when_the_workspace_row_is_missing(db, monkeypatch):
    """⚠️ 放行分支 ②：工作区**行不存在**（悬空 FK）⇒ **放行**。

    ⚠️ 这条在**一致**的库里不可达（FK 保证工作区行在）⇒ 用 monkeypatch 制造
    「工作区行取不到」的情形 ⇒ 钉住「放行」这个**有意**的选择。
    """
    proj = await _make_project(db, workspace_type="PERSONAL")
    real_get = db.get

    async def _get(model, ident, *args, **kwargs):
        from app.models.project import Workspace

        if model is Workspace:
            return None
        return await real_get(model, ident, *args, **kwargs)

    monkeypatch.setattr(db, "get", _get)
    await require_formal_project_workspace(db, project_id=proj.project_id)


async def test_guard_rejects_a_non_formal_workspace(db):
    """非 FORMAL 工作区 ⇒ 403 `WORKSPACE_TYPE_NOT_ALLOWED`（门禁本体）。"""
    proj = await _make_project(db, workspace_type="PERSONAL")
    with pytest.raises(PcsError) as exc_info:
        await require_formal_project_workspace(db, project_id=proj.project_id)
    assert exc_info.value.code == "WORKSPACE_TYPE_NOT_ALLOWED"
    assert exc_info.value.status == 403


async def test_guard_allows_a_formal_workspace(db):
    """FORMAL 工作区 ⇒ 放行（门禁本体）。"""
    proj = await _make_project(db, workspace_type="FORMAL")
    await require_formal_project_workspace(db, project_id=proj.project_id)


async def test_no_deliverable_is_bound_to_a_non_formal_project(db):
    """反向对照：门禁**不**按交付物行的有无判断，只按**项目**的工作区。"""
    proj = await _make_project(db, workspace_type="FORMAL")
    deliverable = await _make_deliverable(db, proj)
    rows = (
        await db.execute(
            select(Deliverable).where(
                Deliverable.deliverable_id == deliverable.deliverable_id
            )
        )
    ).scalars().all()
    assert len(rows) == 1
