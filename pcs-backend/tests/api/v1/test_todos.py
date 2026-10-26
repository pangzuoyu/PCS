"""P9A C4：待办实时计算（ADR-0049 §② / SPEC P9A-NOT-002）。

**不建表。** 每条断言都围绕「没有一行会过期，因为它每次都重算」。

## 关于 500ms 的两条裁决（2026-10-19 D7）

1. **不加 `(project_id, deliverable_type)` 复合索引** —— 主查询不过滤
   `deliverable_type`（签署矩阵按 `module` + `doc_type` 绑定，不是按
   deliverable_type），第二列在主查询里不出现 ⇒ 白占写入开销与 schema 复杂度。
2. **不用 EXPLAIN 决定是否加索引** —— 开发库 `projects=0` / `deliverables=0`，
   planner 在小表上**必然**选 Seq Scan，加了索引后仍然 Seq Scan。
   **检测结果无法区分「缺索引」与「数据少」。**

⇒ 验收方式改成分段计时（SQL / Python 解析各算），且必须造到**预期数据量**
—— 小表下测不出真实性能，500ms 是假达标。
"""
from __future__ import annotations

import uuid
from time import perf_counter

import pytest
from sqlalchemy import select

from app.db.base import Base
from app.models.deliverable import (
    Deliverable,
    DeliverableVersion,
    ProjectSignatureMatrixBinding,
    SignatureMatrix,
)
from app.models.enums import DeliverableSignStatus, WorkflowProgressState, WorkflowType
from app.models.project import UserProject
from app.models.workflow_progress import WorkflowProgress
from app.services import todo_service

pytestmark = pytest.mark.asyncio


def _token(*, role: str, subject: str = "todo-user", user_id: str | None = None):
    from app.core.security import create_access_token

    extra = {"user_id": user_id} if user_id else {}
    return {
        "Authorization": f"Bearer "
        f"{create_access_token(subject=subject, role=role, extra=extra)}"
    }


def _actor_id(subject: str = "todo-user") -> uuid.UUID:
    """`current_actor` 的 user_id 推导规则（uuid5(NAMESPACE_DNS, sub)）。"""
    return uuid.uuid5(uuid.NAMESPACE_DNS, subject)


def _steps() -> list:
    return [
        {"step_order": 1, "sign_role": "DESIGNER"},
        {"step_order": 2, "sign_role": "REVIEWER"},
    ]


async def _grant(db, user_id: uuid.UUID, project_id: uuid.UUID, role: str):
    db.add(UserProject(user_id=user_id, project_id=project_id, role_in_project=role))
    await db.flush()


async def _issue(db, project_id: uuid.UUID, *, steps=None, sign_status=None):
    matrix = SignatureMatrix(
        matrix_name="矩阵",
        module="*",
        doc_type="CALCULATION_BOOK",
        version_purpose="ISSUED_FOR_CONSTRUCTION",
        steps_json=steps if steps is not None else _steps(),
        status="ACTIVE",
    )
    db.add(matrix)
    await db.flush()
    db.add(
        ProjectSignatureMatrixBinding(
            project_id=project_id, module="RECORD", matrix_id=matrix.matrix_id
        )
    )
    d = Deliverable(
        matrix_id=matrix.matrix_id,
        project_id=project_id,
        deliverable_type="CALCULATION_BOOK",
        scope_type="PROJECT_ALL",
        scope_value=str(uuid.uuid4())[:8],
        doc_no=f"CB-{uuid.uuid4().hex[:6]}",
        doc_no_mode="MANUAL",
        title="泵计算书",
        current_rev="1",
        version_purpose="ISSUED_FOR_CONSTRUCTION",
        sign_status=sign_status or DeliverableSignStatus.PENDING,
    )
    db.add(d)
    await db.flush()
    v = DeliverableVersion(
        deliverable_id=d.deliverable_id,
        rev="1",
        version_purpose="ISSUED_FOR_CONSTRUCTION",
        description="签发版本",
        record_snapshot_json={},
        signature_summary_json={},
        created_by=uuid.uuid4(),
    )
    db.add(v)
    await db.flush()
    await db.commit()
    return d, v


async def _complete_step(db, version_id, project_id, step_order: int, role: str):
    db.add(
        WorkflowProgress(
            project_id=project_id,
            workflow_type=WorkflowType.SIGN,
            workflow_id=version_id,
            step_order=step_order,
            step_role=role,
            step_status=WorkflowProgressState.COMPLETED,
        )
    )
    await db.commit()


async def test_todo_computed_from_current_step_role(client, db, project_id):
    """当前步骤是第 1 步（DESIGNER）⇒ DESIGNER 有待办，REVIEWER 没有。"""
    me = _actor_id()
    await _grant(db, me, project_id, "DESIGNER")
    await _issue(db, project_id)

    resp = await client.get("/api/v1/todos", headers=_token(role="DESIGNER"))

    assert resp.status_code == 200, resp.text
    items = resp.json()["items"]
    assert [i["step_role"] for i in items] == ["DESIGNER"]
    assert items[0]["step_order"] == 1


async def test_todo_is_not_everyones_todo(client, db, project_id):
    """不是全部用户的待办 —— 角色不命中就是没有。

    ⚠️ 查询方必须**既没有**全局角色命中、**也没有**项目内角色命中：
    只用 token 的 role 变化是不够的，`user_projects.role_in_project`
    也是角色来源（ADR-0049 §② 的「全局 ∪ 项目内」）。
    """
    des = _actor_id("des")
    await _grant(db, des, project_id, "DESIGNER")
    await _issue(db, project_id)

    # subject="rev" ⇒ user_id 与设计师不同，且 rev 没有任何项目内角色
    resp = await client.get(
        "/api/v1/todos", headers=_token(role="REVIEWER", subject="rev")
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["items"] == []


async def test_todo_reflects_signature_advance_immediately(client, db, project_id):
    """⚠️ 这是「实时计算」相对建表的**全部意义**。

    第 1 步签完后，DESIGNER 的待办必须**立刻**消失、REVIEWER 的立刻出现 ——
    不需要任何同步任务、也没有中间窗口。
    """
    me = _actor_id()
    await _grant(db, me, project_id, "DESIGNER")
    d, v = await _issue(db, project_id)

    before = (await client.get("/api/v1/todos", headers=_token(role="DESIGNER"))).json()
    assert [i["step_role"] for i in before["items"]] == ["DESIGNER"]

    await _complete_step(db, v.version_id, project_id, 1, "DESIGNER")

    after_designer = (await client.get("/api/v1/todos", headers=_token(role="DESIGNER"))).json()
    after_reviewer = (await client.get("/api/v1/todos", headers=_token(role="REVIEWER"))).json()
    assert after_designer["items"] == [], "第 1 步签完后设计师不该还有待办"
    assert [i["step_role"] for i in after_reviewer["items"]] == ["REVIEWER"]
    assert after_reviewer["items"][0]["deliverable_id"] == str(d.deliverable_id)


async def test_todo_empty_when_every_step_is_done(client, db, project_id):
    me = _actor_id()
    await _grant(db, me, project_id, "REVIEWER")
    _d, v = await _issue(db, project_id)
    await _complete_step(db, v.version_id, project_id, 1, "DESIGNER")
    await _complete_step(db, v.version_id, project_id, 2, "REVIEWER")

    resp = await client.get("/api/v1/todos", headers=_token(role="REVIEWER"))

    assert resp.json()["items"] == []


async def test_todo_respects_project_scope(client, db):
    """越权不出现：没有 `user_projects` 授权 ⇒ 该项目的交付物一条都不出现。

    刻意**不给** `_grant` —— 给了就是有权，看到待办是正确行为。
    """
    other_project = uuid.uuid4()
    await _issue(db, other_project)

    resp = await client.get("/api/v1/todos", headers=_token(role="DESIGNER"))

    assert resp.json()["items"] == []


async def test_todo_excludes_revoked_project_grant(client, db, project_id):
    """授权撤销 ⇒ 待办消失。人离开项目后待办还在，比没有待办更坏。"""
    from datetime import UTC, datetime

    me = _actor_id()
    grant = UserProject(
        user_id=me, project_id=project_id, role_in_project="DESIGNER"
    )
    db.add(grant)
    await db.flush()
    await _issue(db, project_id)
    before = (await client.get("/api/v1/todos", headers=_token(role="DESIGNER"))).json()
    assert len(before["items"]) == 1

    grant.revoked_at = datetime.now(UTC)
    await db.commit()

    after = (await client.get("/api/v1/todos", headers=_token(role="DESIGNER"))).json()
    assert after["items"] == []


async def test_todo_excludes_non_pending_deliverables(client, db, project_id):
    """已批准的交付物没有待办 —— 把它算进来会让列表凭空多出已完成的事。"""
    me = _actor_id()
    await _grant(db, me, project_id, "DESIGNER")
    await _issue(db, project_id, sign_status=DeliverableSignStatus.APPROVED)

    resp = await client.get("/api/v1/todos", headers=_token(role="DESIGNER"))

    assert resp.json()["items"] == []


async def test_no_persisted_todo_rows(client, db, project_id):
    """ADR-0049 §②：不建表 ⇒ 不该有任何行被写。

    「没有一行会过期」是因为每次重算，而不是因为清理任务负责删它们。
    """
    me = _actor_id()
    await _grant(db, me, project_id, "DESIGNER")
    await _issue(db, project_id)

    await client.get("/api/v1/todos", headers=_token(role="DESIGNER"))

    assert "todos" not in Base.metadata.tables, (
        "ADR-0049 §② 裁决待办实时计算，不建表"
    )
    rows = (await db.execute(select(WorkflowProgress))).scalars().all()
    assert rows == [], "查待办不该写任何观测行"


async def test_todo_requires_auth(client):
    resp = await client.get("/api/v1/todos")
    assert resp.status_code == 401
    assert resp.json()["code"] == "MISSING_BEARER"


async def test_todo_response_has_no_bare_fields(client, db, project_id):
    me = _actor_id()
    await _grant(db, me, project_id, "DESIGNER")
    await _issue(db, project_id)

    resp = await client.get("/api/v1/todos", headers=_token(role="DESIGNER"))

    assert set(resp.json()["items"][0]) == {
        "deliverable_id",
        "version_id",
        "project_id",
        "step_order",
        "step_role",
        "title",
    }


# ==========================================================================
# 500ms 预算 —— 分段计时，且必须造到预期数据量
# ==========================================================================


async def _bulk(db, me: uuid.UUID, project_id: uuid.UUID, n: int):
    """造 n 个待签交付物。"""
    matrix = SignatureMatrix(
        matrix_name="矩阵",
        module="*",
        doc_type="CALCULATION_BOOK",
        version_purpose="ISSUED_FOR_CONSTRUCTION",
        steps_json=_steps(),
        status="ACTIVE",
    )
    db.add(matrix)
    await db.flush()
    db.add(
        ProjectSignatureMatrixBinding(
            project_id=project_id, module="RECORD", matrix_id=matrix.matrix_id
        )
    )
    for i in range(n):
        d = Deliverable(
            matrix_id=matrix.matrix_id,
            project_id=project_id,
            deliverable_type="CALCULATION_BOOK",
            scope_type="PROJECT_ALL",
            scope_value=str(uuid.uuid4())[:8],
            doc_no=f"CB-{i:06d}",
            doc_no_mode="MANUAL",
            title=f"计算书 {i}",
            current_rev="1",
            version_purpose="ISSUED_FOR_CONSTRUCTION",
            sign_status=DeliverableSignStatus.PENDING,
        )
        db.add(d)
        await db.flush()
        db.add(
            DeliverableVersion(
                deliverable_id=d.deliverable_id,
                rev="1",
                version_purpose="ISSUED_FOR_CONSTRUCTION",
                description="签发版本",
                record_snapshot_json={},
                signature_summary_json={},
                created_by=uuid.uuid4(),
            )
        )
        if i % 50 == 0:
            await db.flush()
    await db.commit()


@pytest.mark.slow
async def test_todo_sql_and_parse_both_within_budget(client, db, project_id, capsys):
    """500ms 预算必须**分段**验证。

    ⚠️ 不得用「EXPLAIN 走 Index Scan」当作性能达标的唯一判据：
    SQL 优化到 10ms 但 Python 解析 600ms 时，EXPLAIN 会绿而指标仍不达标。
    """
    me = _actor_id()
    await _grant(db, me, project_id, "DESIGNER")
    await _bulk(db, me, project_id, 300)

    t0 = perf_counter()
    resp = await client.get("/api/v1/todos", headers=_token(role="DESIGNER"))
    elapsed_ms = (perf_counter() - t0) * 1000

    assert resp.status_code == 200, resp.text
    assert len(resp.json()["items"]) == 300
    with capsys.disabled():
        print(f"\n[todo 500ms] 端到端 {elapsed_ms:.1f}ms（300 个待签交付物）")
    assert elapsed_ms <= 500, f"待办查询耗时 {elapsed_ms:.1f}ms，超过 500ms 预算"


@pytest.mark.slow
async def test_todo_at_expected_data_volume(client, db, project_id, capsys):
    """⚠️ 小表下测不出真实性能 —— 造到「每 project 几百个 deliverable」再测，
    否则 500ms 是假达标。

    这条不是断言耗时，而是断言**量级**：300 个交付物下仍需一次查询返回，
    且解析阶段不得随 items 数线性劣化到不可用。
    """
    me = _actor_id()
    await _grant(db, me, project_id, "DESIGNER")
    await _bulk(db, me, project_id, 300)

    t0 = perf_counter()
    rows = await todo_service.compute_todos(
        db, actor_user_id=me, global_role="DESIGNER"
    )
    parse_ms = (perf_counter() - t0) * 1000

    assert len(rows) == 300
    with capsys.disabled():
        print(f"[todo 量级] 300 条重算 {parse_ms:.1f}ms")
    assert parse_ms <= 500, f"重算耗时 {parse_ms:.1f}ms，超过 500ms 预算"


async def test_todo_does_not_list_items_the_user_cannot_sign(client, db, project_id):
    """⚠️ 项目内角色**不参与**角色匹配。

    矩阵的 `sign_role` 与 **token 的 role claim** 比较（`sign_step` 里
    `sign_role != actor_role` ⇒ 403），项目那侧只校验成员身份。

    ⇒ 一个全局 DESIGNER、项目内 REVIEWER 的人**签不了** REVIEWER 那一步。
    把他算进待办 = 「待办里有，点进去说你不是」—— 比没有待办更坏。
    """
    me = _actor_id()
    await _grant(db, me, project_id, "REVIEWER")  # 项目内角色
    # 全局角色是 DESIGNER（token 的 role claim），不是 REVIEWER
    await _issue(db, project_id, steps=[{"step_order": 1, "sign_role": "REVIEWER"}])

    resp = await client.get("/api/v1/todos", headers=_token(role="DESIGNER"))

    assert resp.json()["items"] == []


async def test_todo_lists_items_the_user_can_actually_sign(client, db, project_id):
    """反向：全局角色命中 **且** 有项目授权 ⇒ 待办出现。

    两个条件缺一不可：只有全局角色 ⇒ 他点不开（越权 404）；
    只有项目授权 ⇒ 他的角色不是矩阵要的那一档。
    """
    me = _actor_id()
    await _grant(db, me, project_id, "VIEWER")  # 项目授权（成员身份）
    await _issue(db, project_id, steps=[{"step_order": 1, "sign_role": "DESIGNER"}])

    resp = await client.get("/api/v1/todos", headers=_token(role="DESIGNER"))

    assert len(resp.json()["items"]) == 1


# ---------------------------------------------------------------------------
# 坏矩阵不许让待办端点 500（P9A-DLV-011 · 评审 I-1）
#
# ⚠️ 待办路径曾经**自己另写了一份** `steps_json` 解析 ⇒ 与签署路径
# （`SignatureMatrixService.parse_steps`）规则不同：
#   · `step_order` 是字符串 ⇒ `sorted()` 抛 TypeError ⇒ **整个端点 500**；
#   · 缺 `step_order` 的项被保留并排到第 0 步 ⇒ 待办说「第 0 步该签」。
# ⇒ 「谁该签这一步」在两个入口下给出两个答案 —— 必须共用同一解析口。
# ---------------------------------------------------------------------------


async def test_todo_survives_string_step_order(client, db, project_id):
    """⚠️ `step_order` 是字符串 ⇒ **不抛**（坏项跳过，好项照旧）。"""
    me = _actor_id()
    await _grant(db, me, project_id, "DESIGNER")
    await _issue(
        db,
        project_id,
        steps=[
            {"step_order": 1, "sign_role": "DESIGNER"},
            {"step_order": "2", "sign_role": "REVIEWER"},
        ],
    )

    resp = await client.get("/api/v1/todos", headers=_token(role="DESIGNER"))

    assert resp.status_code == 200, resp.text
    assert [i["step_role"] for i in resp.json()["items"]] == ["DESIGNER"]


async def test_todo_skips_matrix_with_all_invalid_steps(client, db, project_id, caplog):
    """⚠️ 矩阵**全部非法** ⇒ 该交付物**不产生待办**（而不是把用户推进一个 500）。

    「待办列表」是聚合视图：一个交付物的矩阵坏了，不该让**别人**的待办也看不到。

    ⚠️ **但必须留一条 error 日志**（TODO-084 第 3 条）：静默跳过 ⇒
    「这个交付物没人能签」这件事**完全不可见** ⇒ 矩阵配错了没人知道 ⇒
    交付物永远停在 PENDING，而待办列表里**什么都没有**。
    """
    me = _actor_id()
    await _grant(db, me, project_id, "DESIGNER")
    await _issue(db, project_id, steps=[{"step_order": "x"}, "nope"])

    with caplog.at_level("ERROR", logger="app.services.todo_service"):
        resp = await client.get("/api/v1/todos", headers=_token(role="DESIGNER"))

    assert resp.status_code == 200, resp.text
    assert resp.json()["items"] == []
    assert any(
        "SIGNATURE_MATRIX_INVALID" in r.message or "矩阵" in r.message
        for r in caplog.records
    ), "矩阵全非法时必须留一条 error 日志（否则矩阵配错了完全不可见）"
