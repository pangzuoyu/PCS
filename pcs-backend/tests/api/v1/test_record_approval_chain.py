"""记录级送审批准链**从项目矩阵推导**（TODO-054 · P9B-2 · T2 · R-17）。

## 为什么要有这个端点的形状

TODO-054 登记的缺口 —— 记录侧「多级批准」的角色链**无定义来源**：
`project_templates.default_config_json.record_approval_config` 只有一句注释、
**无消费方** ⇒ 当前 `submit-approval` 让**前端传** `approval_role` +
`approval_depth` ⇒ 谁该批、批几级由**客户端**说了算。

## R-17 的裁决：定义源 = 项目绑定的 `module='RECORD'` 签署矩阵

数据模型**已有这个槽位**（`project_signature_matrix_bindings.module='RECORD'`）+
绑定 API（`POST /projects/{id}/signature-matrices`）+ 管理 UI ⇒ **零新增配置面**；
且与交付物签署链**同一套矩阵** = 一份真相。

⇒ **契约破坏性变更**：`submit-approval` 的请求体不再收 `approval_role` /
`approval_depth`（多传 ⇒ 422）。

## `approval_depth` 的语义**不变**（= 链的总步数）

⚠️ 计划原文写「PASS 后 `approval_depth` 减 1」⇒ 那是**倒计时**语义 ⇒ 与它
自己写的「绑了 3 步 ⇒ 深度 3」**矛盾**（倒计时下 3 步只批得到 2 步，
第 3 个角色永远轮不上）⇒ 本实现保留**总步数**语义（`approval_depth` = 链长，
`approval_step` = 当前步）⇒ 3 步链恰好批 3 次，第 3 次后回 `CHECKED`。
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.calc import PipingResult
from app.models.deliverable import ProjectSignatureMatrixBinding
from app.models.enums import RecordSignStatus9
from app.services.signature_matrix_service import SignatureMatrixService

pytestmark = pytest.mark.asyncio


@pytest.fixture
def auth(sample_user_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {sample_user_token}"}


def _token(role: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {create_access_token(subject=f'u-{role}', role=role)}"
    }


_CHECKER = _token("CHECKER")
_REVIEWER = _token("REVIEWER")
_APPROVER = _token("APPROVER")


async def _make_record(
    client, auth, db_session: AsyncSession, project_id, workspace, *, line_no="P-5001"
) -> PipingResult:
    resp = await client.post(
        "/api/v1/records/piping",
        headers=auth,
        params={"workspace_id": str(workspace.workspace_id)},
        json={"project_id": str(project_id), "line_no": line_no},
    )
    assert resp.status_code == 200, resp.text
    rec = await db_session.get(PipingResult, uuid.UUID(resp.json()["pipe_id"]))
    await db_session.commit()
    await db_session.refresh(rec)
    return rec


async def _bind_record_matrix(
    db: AsyncSession,
    *,
    project_id: uuid.UUID,
    steps: list[dict] | None = None,
    module: str = "*",
) -> uuid.UUID:
    """给项目绑一份 RECORD 矩阵（3 步 CHECKER→REVIEWER→APPROVER）。"""
    matrix = await SignatureMatrixService.create_matrix(
        db,
        matrix_name=f"矩阵-{uuid.uuid4().hex[:8]}",
        module=module,
        doc_type="RECORD",
        version_purpose="PUBLISHED",
        steps=steps
        or [
            {"step_order": 1, "sign_role": "CHECKER"},
            {"step_order": 2, "sign_role": "REVIEWER"},
            {"step_order": 3, "sign_role": "APPROVER"},
        ],
        status="ACTIVE",
    )
    await SignatureMatrixService.bind_to_project(
        db, project_id=project_id, module="RECORD", matrix_id=matrix.matrix_id
    )
    await db.commit()
    return matrix.matrix_id


def _url(rec, action: str) -> str:
    return f"/api/v1/records/PipingResult/{rec.pipe_id}/{action}"


# ---------------------------------------------------------------------------
# 没绑矩阵 ⇒ 响亮失败
# ---------------------------------------------------------------------------


async def test_project_without_record_matrix_is_422(
    client, auth, db_session, project_id, workspace
):
    """项目**没绑** `RECORD` 矩阵 ⇒ 422 `RECORD_APPROVAL_MATRIX_NOT_BOUND`。

    ⚠️ **响亮失败**，不是「默认深度 1」—— 静默降级会让用户以为走的是
    单级审批，而实际批准链是空的。
    """
    rec = await _make_record(client, auth, db_session, project_id, workspace)

    resp = await client.post(_url(rec, "submit-approval"), headers=auth, json={})

    assert resp.status_code == 422, resp.text
    assert resp.json()["code"] == "RECORD_APPROVAL_MATRIX_NOT_BOUND"
    await db_session.refresh(rec)
    assert rec.sign_status == RecordSignStatus9.DRAFT, "被拒的提交不得改状态"


async def test_other_module_matrix_is_not_used(
    client, auth, db_session, project_id, workspace
):
    """绑的是**别的模块**的矩阵 ⇒ 不算数 ⇒ 同样 422。

    ⚠️ 「项目绑了矩阵」不等于「绑的是记录级矩阵」⇒ 不能只看「有没有绑定」。
    """
    rec = await _make_record(client, auth, db_session, project_id, workspace)
    matrix = await SignatureMatrixService.create_matrix(
        db_session,
        matrix_name=f"矩阵-{uuid.uuid4().hex[:8]}",
        module="STREAM",
        doc_type="STREAM",
        version_purpose="PUBLISHED",
        steps=[{"step_order": 1, "sign_role": "CHECKER"}],
        status="ACTIVE",
    )
    await SignatureMatrixService.bind_to_project(
        db_session,
        project_id=project_id,
        module="STREAM",
        matrix_id=matrix.matrix_id,
    )
    await db_session.commit()

    resp = await client.post(_url(rec, "submit-approval"), headers=auth, json={})

    assert resp.status_code == 422, resp.text
    assert resp.json()["code"] == "RECORD_APPROVAL_MATRIX_NOT_BOUND"


# ---------------------------------------------------------------------------
# 批准链从矩阵推导
# ---------------------------------------------------------------------------


async def test_submit_derives_first_step_role_and_depth(
    client, auth, db_session, project_id, workspace
):
    """3 步矩阵 ⇒ 第 1 步角色 + 深度 3（**不是**前端传的）。"""
    rec = await _make_record(client, auth, db_session, project_id, workspace)
    await _bind_record_matrix(db_session, project_id=project_id)

    resp = await client.post(_url(rec, "submit-approval"), headers=auth, json={})

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["approval_role"] == "CHECKER"
    assert body["approval_depth"] == 3
    assert body["approval_step"] == 1
    await db_session.refresh(rec)
    assert rec.sign_status == RecordSignStatus9.IN_APPROVAL
    assert rec.approval_role == "CHECKER"
    assert rec.approval_depth == 3


async def test_pass_advances_to_next_step_role(
    client, auth, db_session, project_id, workspace
):
    """PASS ⇒ `approval_role` **推进到第 2 步**的角色，`approval_step` +1。

    ⚠️ **推进角色是关键**：不推进 ⇒ 第 2 步的角色永远匹配不上
    `record.approval_role` ⇒ 403 `APPROVAL_ROLE_MISMATCH` ⇒ 链条卡死。
    """
    rec = await _make_record(client, auth, db_session, project_id, workspace)
    await _bind_record_matrix(db_session, project_id=project_id)
    resp = await client.post(_url(rec, "submit-approval"), headers=auth, json={})
    assert resp.status_code == 200, resp.text

    resp = await client.post(
        _url(rec, "approval-step"),
        headers=_CHECKER,
        json={"decision": "PASS", "reason": "校核通过"},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["approval_step"] == 2
    assert body["approval_depth"] == 3
    await db_session.refresh(rec)
    assert rec.sign_status == RecordSignStatus9.IN_APPROVAL, "中间步骤不该改状态"
    assert rec.approval_role == "REVIEWER"
    assert rec.approval_step == 2


async def test_last_pass_returns_to_checked(
    client, auth, db_session, project_id, workspace
):
    """3 步链批满 3 次 ⇒ 回 `CHECKED`。"""
    rec = await _make_record(client, auth, db_session, project_id, workspace)
    await _bind_record_matrix(db_session, project_id=project_id)
    resp = await client.post(_url(rec, "submit-approval"), headers=auth, json={})
    assert resp.status_code == 200, resp.text

    for headers, decision in (
        (_CHECKER, "PASS"),
        (_REVIEWER, "PASS"),
        (_APPROVER, "PASS"),
    ):
        resp = await client.post(
            _url(rec, "approval-step"), headers=headers, json={"decision": decision}
        )
        assert resp.status_code == 200, resp.text

    await db_session.refresh(rec)
    assert rec.sign_status == RecordSignStatus9.CHECKED


async def test_wrong_role_cannot_approve_the_step(
    client, auth, db_session, project_id, workspace
):
    """第 1 步只认 CHECKER ⇒ 拿 APPROVER（第 3 步的角色）去批 ⇒ 403。

    ⚠️ 用 APPROVER 而不是 REVIEWER：REVIEWER **过不了**转移的角色粗闸
    （`TRANSITION_ROLES[PASS_CHECK]`）⇒ 那样测到的是**另一道门**，
    不是「矩阵这一步该谁签」这道门。
    """
    rec = await _make_record(client, auth, db_session, project_id, workspace)
    await _bind_record_matrix(db_session, project_id=project_id)
    resp = await client.post(_url(rec, "submit-approval"), headers=auth, json={})
    assert resp.status_code == 200, resp.text

    resp = await client.post(
        _url(rec, "approval-step"), headers=_APPROVER, json={"decision": "PASS"}
    )

    assert resp.status_code == 403, resp.text
    assert resp.json()["code"] == "APPROVAL_ROLE_MISMATCH"


# ---------------------------------------------------------------------------
# 自审防护
# ---------------------------------------------------------------------------


async def test_self_review_is_rejected(client, auth, db_session, project_id, workspace):
    """提交人自己的角色出现在链里 ⇒ 403 `APPROVAL_SELF_REVIEW_FORBIDDEN`。

    ⚠️ 判据是「**链里任何一步**的角色 == 提交人自己的全局角色」——
    只挡第 1 步会留下一个洞：提交人在第 2 步自己批自己。
    """
    rec = await _make_record(client, auth, db_session, project_id, workspace)
    await _bind_record_matrix(
        db_session,
        project_id=project_id,
        steps=[
            {"step_order": 1, "sign_role": "CHECKER"},
            {"step_order": 2, "sign_role": "DESIGNER"},
        ],
    )

    resp = await client.post(_url(rec, "submit-approval"), headers=auth, json={})

    assert resp.status_code == 403, resp.text
    assert resp.json()["code"] == "APPROVAL_SELF_REVIEW_FORBIDDEN"
    await db_session.refresh(rec)
    assert rec.sign_status == RecordSignStatus9.DRAFT, "被拒的提交不得改状态"


# ---------------------------------------------------------------------------
# 契约破坏性变更
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("extra", "field"),
    [
        ({"approval_role": "CHECKER"}, "approval_role"),
        ({"approval_depth": 3}, "approval_depth"),
        ({"approval_role": "X", "approval_depth": 2}, "approval_role"),
    ],
)
async def test_request_body_rejects_client_supplied_chain(
    client, auth, db_session, project_id, workspace, extra, field
):
    """请求体**不再接受** `approval_role` / `approval_depth`（多传 ⇒ 422）。

    ⚠️ 契约破坏性变更**要显式化**：静默忽略 ⇒ 调用方以为自己传了角色，
    实际生效的是矩阵里的角色 ⇒ 「我明明选了 APPROVER」却吃 403。

    ⚠️ 只断言 422 会在**旧契约**下也绿（`approval_role` 缺失 / 值不在词表
    ⇒ 也 422）⇒ 必须断**是哪个字段被拒**。
    """
    rec = await _make_record(client, auth, db_session, project_id, workspace)
    await _bind_record_matrix(db_session, project_id=project_id)

    resp = await client.post(_url(rec, "submit-approval"), headers=auth, json=extra)

    assert resp.status_code == 422, resp.text
    body = resp.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert field in str(body["detail"]), body["detail"]


async def test_reason_is_accepted(client, auth, db_session, project_id, workspace):
    """`reason` 可选，传了要能过（送审说明）。"""
    rec = await _make_record(client, auth, db_session, project_id, workspace)
    await _bind_record_matrix(db_session, project_id=project_id)

    resp = await client.post(
        _url(rec, "submit-approval"), headers=auth, json={"reason": "初版请审"}
    )

    assert resp.status_code == 200, resp.text


# ---------------------------------------------------------------------------
# 批准链**快照**（P9B-2 评审 #1：中途重绑矩阵不得改变已提交记录的链）
#
# 攻击路径（评审 validator 确认，CWE-863）：SYSTEM_ADMIN 可送审（粗闸含）
# 也可批步（PASS_CHECK 粗闸含）⇒ 提交时链里没有自己（自审过关）⇒ 中途把
# 项目重绑到「含自己角色」的矩阵 ⇒ 第 2 步起就轮到自己批自己。
# 修法（委员会裁决：快照，与交付物侧 _steps_for_version 同构）：
# submit 时把链冻进 record.approval_chain_snapshot，中间步骤只读快照。
# ---------------------------------------------------------------------------

_ADMIN = _token("SYSTEM_ADMIN")


async def test_submit_persists_chain_snapshot(
    client, auth, db_session, project_id, workspace
):
    """submit ⇒ 链（矩阵 id + 角色序列 + 提交人）冻进 `approval_chain_snapshot`。"""
    rec = await _make_record(client, auth, db_session, project_id, workspace)
    mid = await _bind_record_matrix(db_session, project_id=project_id)

    resp = await client.post(_url(rec, "submit-approval"), headers=_ADMIN, json={})

    assert resp.status_code == 200, resp.text
    await db_session.refresh(rec)
    snap = rec.approval_chain_snapshot
    assert snap is not None, "提交必须冻结批准链"
    assert [s["sign_role"] for s in snap["steps"]] == ["CHECKER", "REVIEWER", "APPROVER"]
    assert snap["matrix_id"] == str(mid)
    assert snap["submitted_by"], "提交人必须留痕（自审二次断言的依据）"


async def test_midflight_rebind_cannot_change_pending_role(
    client, auth, db_session, project_id, workspace
):
    """提交后重绑矩阵 ⇒ 已提交记录的链**不变**（读快照，不读实时矩阵）。

    且提交人自己批任何一步 ⇒ 403 `APPROVAL_SELF_REVIEW_FORBIDDEN`
    （快照里有 submitted_by，二次断言不再只靠 submit 时的一次检查）。
    """
    rec = await _make_record(client, auth, db_session, project_id, workspace)
    await _bind_record_matrix(db_session, project_id=project_id)
    resp = await client.post(_url(rec, "submit-approval"), headers=_ADMIN, json={})
    assert resp.status_code == 200, resp.text

    # 攻击：重绑到「第 2 步是 SYSTEM_ADMIN」的矩阵
    await _bind_record_matrix(
        db_session,
        project_id=project_id,
        steps=[
            {"step_order": 1, "sign_role": "CHECKER"},
            {"step_order": 2, "sign_role": "SYSTEM_ADMIN"},
            {"step_order": 3, "sign_role": "APPROVER"},
        ],
    )

    resp = await client.post(
        _url(rec, "approval-step"), headers=_CHECKER, json={"decision": "PASS"}
    )
    assert resp.status_code == 200, resp.text
    await db_session.refresh(rec)
    assert rec.approval_role == "REVIEWER", "中途重绑不得改变已冻结的链"

    resp = await client.post(
        _url(rec, "approval-step"), headers=_ADMIN, json={"decision": "PASS"}
    )
    assert resp.status_code == 403, resp.text
    assert resp.json()["code"] == "APPROVAL_SELF_REVIEW_FORBIDDEN", (
        "提交人（即使角色恰好匹配被注入的下一步）不得批自己的记录"
    )


async def test_matrix_disabled_mid_approval_keeps_chain(
    client, auth, db_session, project_id, workspace
):
    """提交后矩阵被禁用 ⇒ 链照常走完（快照语义；实时矩阵只管「新提交」）。"""
    from app.models.deliverable import SignatureMatrix

    rec = await _make_record(client, auth, db_session, project_id, workspace)
    mid = await _bind_record_matrix(db_session, project_id=project_id)
    resp = await client.post(_url(rec, "submit-approval"), headers=_ADMIN, json={})
    assert resp.status_code == 200, resp.text

    matrix = await db_session.get(SignatureMatrix, mid)
    matrix.status = "DISABLED"
    await db_session.commit()

    resp = await client.post(
        _url(rec, "approval-step"), headers=_CHECKER, json={"decision": "PASS"}
    )
    assert resp.status_code == 200, resp.text
    await db_session.refresh(rec)
    assert rec.approval_role == "REVIEWER"

    resp = await client.post(
        _url(rec, "approval-step"), headers=_REVIEWER, json={"decision": "PASS"}
    )
    assert resp.status_code == 200, resp.text


async def test_second_submit_after_commit_is_409(
    client, auth, db_session, project_id, workspace
):
    """第二次 submit（第一个已提交）⇒ 409，且快照仍属第一个提交人。

    ⚠️ **为什么是串行不是 gather**：本仓单测的 in-memory SQLite 走
    StaticPool —— 两个请求共享**同一条连接/同一个事务域**，根本没有
    隔离 ⇒ 真并发在本 fixture 上不可表达（CLAUDE.md 已记载的坑）。

    ## ⚠️ 本测试**不**验证行锁（评审 #1 的 true 说法已删除）

    `submit_approval` 的 `FOR UPDATE` 行锁（SQLite 方言静默省略）在 **PG**
    上把并发提交串行化成与本测试等价的先后序列 —— 但**本仓没有任何自动化
    作业验证 PG 上的并发结果**：CI 的 `check-api-drift` job 只跑
    `alembic upgrade head` / OpenAPI 导出与漂移检查 / 迁移幂等脚本 /
    可视化渲染器测试 / 前端 typecheck，**一条后端 pytest 都不跑**。

    ⇒ 行锁由另外两条测试钉住（**机制** + **接线**，都不需要 PG 服务器）：
    - `test_locking_select_emits_for_update_on_postgres`（用 PG 方言编译
      加锁 SELECT，断言 SQL 里含 `FOR UPDATE`）
    - `test_write_paths_request_row_lock`（断言两个写路径都传
      `for_update=True`）

    ⇒ PG 上的**实际并发结果**（一胜一拒）目前**无自动化覆盖**，需真库
    手工验证（见 `docs/ce-code-review/20261028-074842-e15c26e8/ROLLBACK-RUNBOOK.md`）。
    """
    rec = await _make_record(client, auth, db_session, project_id, workspace)
    await _bind_record_matrix(db_session, project_id=project_id)

    r1 = await client.post(_url(rec, "submit-approval"), headers=_ADMIN, json={})
    assert r1.status_code == 200, r1.text
    r2 = await client.post(_url(rec, "submit-approval"), headers=auth, json={})
    assert r2.status_code == 409, r2.text

    await db_session.refresh(rec)
    assert rec.sign_status == RecordSignStatus9.IN_APPROVAL
    assert rec.approval_chain_snapshot["submitted_by_role"] == "SYSTEM_ADMIN", (
        "第二个 submit 被拒后，快照必须仍属于第一个提交人"
    )


async def test_inactive_bound_matrix_is_409_not_422(
    client, auth, db_session, project_id, workspace
):
    """⚠️ 评审 #9：绑了**非 ACTIVE** 矩阵 ⇒ 409 `SIGNATURE_MATRIX_NOT_ACTIVE`。

    「没绑」(422 RECORD_APPROVAL_MATRIX_NOT_BOUND) 与「绑了但配错状态」(409)
    必须分开 —— 混了 ⇒ 管理员看到 422 会去「绑矩阵」，而实际要做的是
    「把矩阵启回 ACTIVE」。该 409 分支此前无任何测试钉住。
    """
    from app.models.deliverable import SignatureMatrix

    rec = await _make_record(client, auth, db_session, project_id, workspace)
    matrix = await SignatureMatrixService.create_matrix(
        db_session,
        matrix_name=f"矩阵-{uuid.uuid4().hex[:8]}",
        module="RECORD",
        doc_type="RECORD",
        version_purpose="PUBLISHED",
        steps=[{"step_order": 1, "sign_role": "CHECKER"}],
        status="PENDING",
    )
    # 直接写绑定行（bind_to_project 会拒非 ACTIVE —— 模拟「绑过之后矩阵被停用」）
    db_session.add(
        ProjectSignatureMatrixBinding(
            project_id=project_id, module="RECORD", matrix_id=matrix.matrix_id
        )
    )
    await db_session.commit()

    resp = await client.post(_url(rec, "submit-approval"), headers=auth, json={})

    assert resp.status_code == 409, resp.text
    assert resp.json()["code"] == "SIGNATURE_MATRIX_NOT_ACTIVE"
    await db_session.refresh(rec)
    assert rec.sign_status == RecordSignStatus9.DRAFT, "被拒的提交不得改状态"


async def test_empty_steps_matrix_is_loud_not_500(
    client, auth, db_session, project_id, workspace
):
    """⚠️ 评审 #17（纵深防御）：`steps_json` 为**空数组**的矩阵（API 会拦
    min 1 步，但直插 DB / 存量脏数据可达）⇒ submit 必须**响亮失败**，
    不是 `steps[0]` IndexError ⇒ 500。"""
    from app.models.deliverable import ProjectSignatureMatrixBinding, SignatureMatrix

    rec = await _make_record(client, auth, db_session, project_id, workspace)
    matrix = SignatureMatrix(
        matrix_name=f"空链-{uuid.uuid4().hex[:6]}",
        module="RECORD",
        doc_type="RECORD",
        version_purpose="PUBLISHED",
        steps_json=[],
        status="ACTIVE",
    )
    db_session.add(matrix)
    await db_session.flush()
    db_session.add(
        ProjectSignatureMatrixBinding(
            project_id=project_id, module="RECORD", matrix_id=matrix.matrix_id
        )
    )
    await db_session.commit()

    resp = await client.post(_url(rec, "submit-approval"), headers=auth, json={})

    assert resp.status_code == 422, resp.text
    assert resp.json()["code"] == "SIGNATURE_MATRIX_EMPTY_CHAIN"


# ---------------------------------------------------------------------------
# 评审 #1（P1）：行锁**只写在注释里** ⇒ 删掉 `.with_for_update()` 套件照样全绿
# ---------------------------------------------------------------------------


async def test_locking_select_emits_for_update_on_postgres():
    """方言级断言：加锁那一条 SELECT 在 **PG 方言**下真的带 `FOR UPDATE`。

    ## 为什么是方言级而不是「真跑 PG 并发」

    - in-memory SQLite 把 `with_for_update()` **编译成空串**（压根没有锁），
      且 StaticPool 共享连接 ⇒ 真并发在本仓单测 fixture 上**不可表达**；
    - 真 PG 双连接并发要起第二个进程 + 真库 ⇒ 那是部署验证，不是单测。

    ⇒ 这里钉**机制**（SQL 形状），下一条钉**接线**（端点确实请求了锁）。
    两条合起来 ⇒ 「删掉行锁」必红。

    ⚠️ 这条**不**证明 PG 上的并发结果（一胜一拒）—— 那仍需真库，见
    `test_record_approval_chain.py::test_second_submit_after_commit_is_409`
    的 docstring（已改为如实说明 CI 不覆盖它）。
    """
    from sqlalchemy.dialects import postgresql

    from app.api.v1.records_actions import _locked_select

    stmt = _locked_select(PipingResult, uuid.uuid4())
    sql = str(stmt.compile(dialect=postgresql.dialect()))
    assert "FOR UPDATE" in sql, sql


async def test_write_paths_request_row_lock(
    client, auth, db_session, project_id, workspace, monkeypatch
):
    """接线断言：submit-approval 与 approval-step **都**请求行锁。

    上一条钉机制（SQL 形状），这条钉**接线**（端点真的传了 `for_update=True`）
    —— 少了任一条，「删掉行锁」仍可能全绿。
    """
    from app.api.v1 import records_actions

    seen: list[Any] = []
    original = records_actions.load_record

    async def spy(*args, **kwargs):
        seen.append(kwargs.get("for_update"))
        return await original(*args, **kwargs)

    monkeypatch.setattr(records_actions, "load_record", spy)

    rec = await _make_record(client, auth, db_session, project_id, workspace)
    await _bind_record_matrix(db_session, project_id=project_id)
    resp = await client.post(_url(rec, "submit-approval"), headers=_ADMIN, json={})
    assert resp.status_code == 200, resp.text
    resp = await client.post(
        _url(rec, "approval-step"), headers=_CHECKER, json={"decision": "PASS"}
    )
    assert resp.status_code == 200, resp.text
    assert seen == [True, True], f"两个写路径都必须请求行锁，实际 {seen}"


# ---------------------------------------------------------------------------
# 评审 #9：快照列上线**前**就在审批中的存量行 ⇒ 自审二次断言对它整体失效
# ---------------------------------------------------------------------------


async def _make_legacy_row(client, auth, db_session, project_id, workspace):
    """造一条「快照列上线前就在审批中」的存量行（`approval_chain_snapshot IS NULL`）。

    ⚠️ 必须用**显式 UPDATE** 抹快照：ORM 属性赋值在「该属性从未被本 session
    改过」时**不产生脏写** ⇒ 库里还留着快照 ⇒ 测的其实是新路径，不是存量路径。
    """
    from sqlalchemy import update

    rec = await _make_record(client, auth, db_session, project_id, workspace)
    await _bind_record_matrix(db_session, project_id=project_id)
    resp = await client.post(_url(rec, "submit-approval"), headers=_ADMIN, json={})
    assert resp.status_code == 200, resp.text
    # 抹掉快照 ⇒ 模拟「迁移落地时它已经在审批中」
    await db_session.execute(
        update(PipingResult)
        .where(PipingResult.pipe_id == rec.pipe_id)
        .values(approval_chain_snapshot=None)
    )
    await db_session.commit()
    await db_session.refresh(rec)
    assert rec.approval_chain_snapshot is None, "存量行必须真的没有快照"
    return rec


async def test_legacy_row_without_snapshot_blocks_submitter_self_approval(
    client, auth, db_session, project_id, workspace
):
    """⚠️ 评审 #9：`approval_chain_snapshot IS NULL` 的存量行 ⇒ 提交人不明 ⇒
    每步的 `submitted_by` 二次断言**整段跳过** ⇒ 提交人能在第 2 步批自己的记录
    （正是委员会裁决要堵的自审绕过）。

    ⇒ 修法：从**审计流水**反推当初的提交人
    （`RECORD_TRANSITION` / `detail.transition == 'SUBMIT_FOR_CHECK'`）
    ⇒ 提交人批自己的存量行 ⇒ 403 `APPROVAL_SELF_REVIEW_FORBIDDEN`。
    """
    rec = await _make_legacy_row(client, auth, db_session, project_id, workspace)

    resp = await client.post(
        _url(rec, "approval-step"), headers=_ADMIN, json={"decision": "PASS"}
    )

    assert resp.status_code == 403, resp.text
    assert resp.json()["code"] == "APPROVAL_SELF_REVIEW_FORBIDDEN", resp.text


async def test_legacy_row_freezes_chain_on_first_touch(
    client, auth, db_session, project_id, workspace
):
    """存量行第一次被批 ⇒ **当场冻结**一条链快照（含提交人）⇒ 此后每一步都有
    `submitted_by` 可比对 ⇒ 不再存在「无快照 ⇒ 零保护」的分支。"""
    rec = await _make_legacy_row(client, auth, db_session, project_id, workspace)

    resp = await client.post(
        _url(rec, "approval-step"), headers=_CHECKER, json={"decision": "PASS"}
    )

    assert resp.status_code == 200, resp.text
    await db_session.refresh(rec)
    snap = rec.approval_chain_snapshot
    assert snap is not None, "存量行首次触达必须冻结链快照"
    assert snap["submitted_by"], "快照必须带提交人（自审二次断言的依据）"
    assert snap.get("legacy") is True, "存量行冻结的快照要标出 legacy"


async def test_legacy_row_without_audit_row_is_loud_not_silent(
    client, auth, db_session, project_id, workspace
):
    """查不到提交人 ⇒ **响亮失败**（409 `APPROVAL_SUBMITTER_UNKNOWN`）。

    ⚠️ 不放行「查不到就当没有提交人」—— 那等于把自审绕过又打开一次
    （fail-open）。宁可这条记录卡住等人工处理。
    """
    from sqlalchemy import delete

    from app.models.system import AuditLog

    rec = await _make_legacy_row(client, auth, db_session, project_id, workspace)
    # 抹掉送审审计行（模拟审计流水被裁剪/归档）
    await db_session.execute(
        delete(AuditLog).where(AuditLog.resource_id == str(rec.pipe_id))
    )
    await db_session.commit()

    resp = await client.post(
        _url(rec, "approval-step"), headers=_CHECKER, json={"decision": "PASS"}
    )

    assert resp.status_code == 409, resp.text
    assert resp.json()["code"] == "APPROVAL_SUBMITTER_UNKNOWN", resp.text


async def test_legacy_row_uses_the_LATEST_submitter_not_the_first(
    client, auth, db_session, project_id, workspace
):
    """⚠️「送审 → 驳回 → 再送审」⇒ 流水里有**两条** SUBMIT_FOR_CHECK ⇒
    **当前这一轮**的提交人是**最后**那条。

    取错（拿上一轮的人）⇒ 本轮提交人就能批自己的记录 ⇒ 正是 #9 要堵的
    绕过 —— 且这在**存量行**（无快照）上才会发生（有快照的行走的是 submit
    时写入的 `submitted_by`，天然是当前轮的）。

    ⚠️ 时间戳：PG 侧 `occurred_at` 是事务时间戳（微秒）⇒ 两次请求必然不同；
    SQLite 侧 `CURRENT_TIMESTAMP` 只到**秒** ⇒ 本例**显式**把两条送审审计行
    的 `occurred_at` 设成不同的值 ⇒ 测试确定性不依赖时钟分辨率。
    """
    from datetime import datetime, timezone

    from sqlalchemy import update

    from app.models.system import AuditLog

    rec = await _make_record(client, auth, db_session, project_id, workspace)
    # ⚠️ **1 步**链（CHECKER）—— 这样「提交人」才能既**不在**链里（否则
    #    submit 时就被自审拦了）、又**有**批注权（`PASS_CHECK` 的角色集含
    #    REVIEWER）⇒ 三个角色（dan / reviewer / checker）可区分。
    await _bind_record_matrix(
        db_session,
        project_id=project_id,
        steps=[{"step_order": 1, "sign_role": "CHECKER"}],
    )

    # 第一轮：dan（SYSTEM_ADMIN，链外）送审
    resp = await client.post(_url(rec, "submit-approval"), headers=_ADMIN, json={})
    assert resp.status_code == 200, resp.text
    await db_session.execute(
        update(AuditLog)
        .where(AuditLog.resource_id == str(rec.pipe_id))
        .values(occurred_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
    )
    await db_session.commit()

    # 驳回 ⇒ 回到 CHECK_REJECTED（CHECKER 是这一步该批的角色）
    resp = await client.post(
        _url(rec, "approval-step"), headers=_CHECKER, json={"decision": "REJECT"}
    )
    assert resp.status_code == 200, resp.text

    # 第二轮：**approver**（链外、且送审/批注两个角色集都含他）送审
    # ⇒ 当前轮次的提交人是他
    # ⚠️ 不能用 REVIEWER：`TRANSITION_ROLES[SUBMIT_FOR_CHECK]` **不含**
    #    REVIEWER ⇒ 他连送审都做不了。
    resp = await client.post(_url(rec, "submit-approval"), headers=_APPROVER, json={})
    assert resp.status_code == 200, resp.text
    await db_session.execute(
        update(AuditLog)
        .where(AuditLog.resource_id == str(rec.pipe_id))
        .values(occurred_at=datetime(2026, 1, 2, tzinfo=timezone.utc))
    )
    await db_session.commit()

    # 抹掉快照 ⇒ 存量行形状
    await db_session.execute(
        update(PipingResult)
        .where(PipingResult.pipe_id == rec.pipe_id)
        .values(approval_chain_snapshot=None)
    )
    await db_session.commit()

    # ⚠️ **本轮**的提交人是 reviewer ⇒ 他批自己的记录 ⇒ 403
    #    `APPROVAL_SELF_REVIEW_FORBIDDEN`。
    #    ⚠️ 若实现取了**第一条**（dan）⇒ reviewer 不会被自审拦 ⇒ 落到角色闸
    #    ⇒ 返回的是 `APPROVAL_ROLE_MISMATCH` ⇒ **码不同** ⇒ 本例抓得住。
    resp = await client.post(
        _url(rec, "approval-step"), headers=_APPROVER, json={"decision": "PASS"}
    )
    assert resp.status_code == 403, resp.text
    assert resp.json()["code"] == "APPROVAL_SELF_REVIEW_FORBIDDEN", resp.text

    # CHECKER 批 ⇒ 放行（证明取到的确实是 approver，不是上一轮的 dan）
    resp = await client.post(
        _url(rec, "approval-step"), headers=_CHECKER, json={"decision": "PASS"}
    )
    assert resp.status_code == 200, resp.text
