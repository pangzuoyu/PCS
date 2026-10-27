"""TODO-065 聚合进度端点（`GET /deliverables/{id}/progress`）—— P9B-2 · T0。

## 为什么这个端点必须存在

`GET /workflow-progress/{workflow_type}/{workflow_id}` 是**单条**查询，
而两类工作流的 `workflow_id` 语义**各不相同**（实测 2026-10-21 / 复核 2026-10-27）：

| 工作流 | workflow_id | 依据（`deliverable_service.py` 的 grep 锚） |
|---|---|---|
| SIGN | **版本 id** | `workflow_type=WorkflowType.SIGN`（`sign_step`） |
| CUSTOMER_APPROVAL_PROXY | **交付物 id** | `workflow_type=WorkflowType.CUSTOMER_APPROVAL_PROXY` |

⇒ 前端要拿「这个交付物的全部流程进度」就得**自己**拼这两个 id ⇒ 关联规则
（哪类工作流用哪个 id）就成了**前端的一份业务规则** ⇒ 后端加一类工作流，
前端就得跟着改，否则前端查的是**空的**那一段。

⚠️ **P9B-1 计划把 CUSTOMER_APPROVAL_PROXY 写成「版本 ID」，与代码不符** ——
本测试把**代码的语义**钉死（R-2）。

## 三条设计取舍各有测试

1. **每段都带 `available` + `reason`**：空数组会被读成「这条流程一个节点都没有」，
   而真相是「这类工作流对本交付物不存在」—— 两者在界面上**长得一样**。
2. **只有两段**（R-13）：`CHANGE_NOTICE` 段**删掉** —— 变更单**本身就是交付物**
   （`deliverable_type=CHANGE_NOTICE`）⇒ 它在进度页上**自己一行**、自己有
   SIGN 进度；而计划原口径用的 `Deliverable.parent_deliverable_id`
   **全仓从未被写** ⇒ 那一段**永远**返回「不可用」⇒ 留着一个**永远为假的段**
   比没有更坏（用户会以为是数据问题）。
3. **禁 N+1**（R-16）：一次请求的 SELECT 数 ≤ 5 ⇒ 靠**一条批量查询**
   （两段的观测行一起取回）+ 一条取版本 ⇒ 达成。
"""

from __future__ import annotations

import contextlib
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.deliverable import Deliverable, DeliverableVersion, SignatureMatrix
from app.models.enums import (
    DeliverableSignStatus,
    WorkflowProgressState,
    WorkflowType,
)
from app.models.workflow_progress import WorkflowProgress

pytestmark = pytest.mark.asyncio

_SIGN = "SIGN"
_PROXY = "CUSTOMER_APPROVAL_PROXY"


@pytest.fixture
def auth(sample_user_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {sample_user_token}"}


@contextlib.asynccontextmanager
async def _guard_client(db_engine):
    """独立 client —— **不**套 conftest 的 `check_user_project_access` bypass mock。

    默认 `client` fixture 把项目守卫 mock 成永远 True，在它上面测「越权被拒」
    是空断言：守卫根本没跑，测的只是一条不存在的路径。
    """
    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.api.v1 import api_router
    from app.core.errors import install_exception_handlers
    from app.db.session import get_db

    factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async def _override_get_db():
        async with factory() as session:
            yield session

    app = FastAPI(title="PCS Test Guard")
    install_exception_handlers(app)
    app.include_router(api_router)
    app.dependency_overrides[get_db] = _override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


@pytest.fixture
def select_counter(db_engine):
    """数 SELECT（禁 N+1 的守卫用）。"""
    counter = {"n": 0}

    def _hook(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
        if statement.lstrip().upper().startswith("SELECT"):
            counter["n"] += 1

    event.listen(db_engine.sync_engine, "before_cursor_execute", _hook)
    yield counter
    event.remove(db_engine.sync_engine, "before_cursor_execute", _hook)


async def _make_deliverable(
    db: AsyncSession,
    project_id: uuid.UUID,
    *,
    with_version: bool = True,
) -> tuple[Deliverable, DeliverableVersion | None]:
    """造一个交付物（可选带一个版本行）。

    ⚠️ `current_rev` 必须与版本行的 `rev` 一致 —— 「当前版本 id」是**派生**的
    （`rev == current_rev` 的那条版本行），`deliverables` 表**没有**
    `current_version_id` 列。
    """
    matrix = SignatureMatrix(
        matrix_name=f"矩阵-{uuid.uuid4().hex[:8]}",
        module="*",
        doc_type="CALCULATION_BOOK",
        version_purpose="ISSUED_FOR_CONSTRUCTION",
        steps_json=[{"step_order": 1, "sign_role": "CHECKER"}],
        status="ACTIVE",
    )
    db.add(matrix)
    await db.flush()
    deliverable = Deliverable(
        matrix_id=matrix.matrix_id,
        project_id=project_id,
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
    db.add(deliverable)
    await db.commit()
    await db.refresh(deliverable)
    version = None
    if with_version:
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


async def _seed_progress(
    db: AsyncSession,
    *,
    project_id: uuid.UUID,
    workflow_type: WorkflowType,
    workflow_id: uuid.UUID,
    step_order: int = 1,
    step_role: str = "CHECKER",
    state: WorkflowProgressState = WorkflowProgressState.COMPLETED,
) -> None:
    db.add(
        WorkflowProgress(
            project_id=project_id,
            workflow_type=workflow_type,
            workflow_id=workflow_id,
            step_order=step_order,
            step_role=step_role,
            step_status=state,
        )
    )
    await db.commit()


# ---------------------------------------------------------------------------
# 两段都在 / 段的身份
# ---------------------------------------------------------------------------


async def test_progress_sections_cover_two_workflow_types(
    client, auth, db_session, project_id
):
    """两段都在，顺序固定；没有第三段（R-13）。"""
    deliverable, version = await _make_deliverable(db_session, project_id)
    assert version is not None
    await _seed_progress(
        db_session,
        project_id=project_id,
        workflow_type=WorkflowType.SIGN,
        workflow_id=version.version_id,
    )
    await _seed_progress(
        db_session,
        project_id=project_id,
        workflow_type=WorkflowType.CUSTOMER_APPROVAL_PROXY,
        workflow_id=deliverable.deliverable_id,
        step_role="CUSTOMER",
    )

    resp = await client.get(
        f"/api/v1/deliverables/{deliverable.deliverable_id}/progress", headers=auth
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["deliverable_id"] == str(deliverable.deliverable_id)
    types = [s["workflow_type"] for s in body["sections"]]
    assert types == [_SIGN, _PROXY]
    # ⚠️ R-13：**没有** CHANGE_NOTICE 段（变更单自己就是交付物）
    assert "CHANGE_NOTICE" not in types


async def test_sign_section_uses_version_id_as_workflow_id(
    client, auth, db_session, project_id
):
    """SIGN 段的 `workflow_id` = **版本 id**（不是交付物 id）。"""
    deliverable, version = await _make_deliverable(db_session, project_id)
    assert version is not None

    resp = await client.get(
        f"/api/v1/deliverables/{deliverable.deliverable_id}/progress", headers=auth
    )

    assert resp.status_code == 200, resp.text
    sign = resp.json()["sections"][0]
    assert sign["workflow_type"] == _SIGN
    assert sign["workflow_id"] == str(version.version_id)


async def test_customer_approval_proxy_section_uses_deliverable_id(
    client, auth, db_session, project_id
):
    """CUSTOMER_APPROVAL_PROXY 段的 `workflow_id` = **交付物 id**（R-2 的钉子）。

    ⚠️ **不是** version_id —— 写入点是 `deliverable_service.py` 的客户批准代录
    ⇒ `record_step(workflow_type=CUSTOMER_APPROVAL_PROXY, workflow_id=deliverable_id)`。
    """
    deliverable, _ = await _make_deliverable(db_session, project_id)

    resp = await client.get(
        f"/api/v1/deliverables/{deliverable.deliverable_id}/progress", headers=auth
    )

    assert resp.status_code == 200, resp.text
    proxy = resp.json()["sections"][1]
    assert proxy["workflow_type"] == _PROXY
    assert proxy["workflow_id"] == str(deliverable.deliverable_id)


async def test_progress_sections_exclude_rows_of_other_projects(
    client, auth, db_session, project_id
):
    """⚠️ **行级 `project_id` 一致性校验**（批量端点与单条端点同口径）。

    单条端点 `workflow_progress_service.get` 会比对「宿主行的 project」与
    调用方授权的 project ⇒ 不一致 ⇒ 404 ⇒ **脏数据不会出现在结果里**。

    批量端点（R-16 的一条批量查询）**曾经丢掉了这一步** ⇒ 两个端点对同一份
    脏数据给**不同答案** ⇒ 前端按聚合端点渲染 ⇒ 把**别的项目**的观测行
    画进这个交付物的甘特图。

    ⇒ 批量端点也要按 `project_id` 过滤观测行。
    """
    deliverable, version = await _make_deliverable(db_session, project_id)
    assert version is not None
    # ⚠️ 脏数据：观测行的 project_id = **别的项目**
    await _seed_progress(
        db_session,
        project_id=uuid.uuid4(),
        workflow_type=WorkflowType.SIGN,
        workflow_id=version.version_id,
    )

    resp = await client.get(
        f"/api/v1/deliverables/{deliverable.deliverable_id}/progress", headers=auth
    )

    assert resp.status_code == 200, resp.text
    sign = resp.json()["sections"][0]
    assert sign["items"] == []
    assert sign["total"] == 0


# ---------------------------------------------------------------------------
# available / reason（RF-6）
# ---------------------------------------------------------------------------


async def test_sign_section_unavailable_when_no_version(
    client, auth, db_session, project_id
):
    """交付物**无版本** ⇒ SIGN 段 `available=false` + `reason` 非空。

    ⚠️ **不得**返回空数组冒充「无步骤」—— 空数组会被读成「这条流程一个节点
    都没有」，而真相是「这类工作流对本交付物不存在」。
    """
    deliverable, _ = await _make_deliverable(db_session, project_id, with_version=False)

    resp = await client.get(
        f"/api/v1/deliverables/{deliverable.deliverable_id}/progress", headers=auth
    )

    assert resp.status_code == 200, resp.text
    sign = resp.json()["sections"][0]
    assert sign["workflow_type"] == _SIGN
    assert sign["available"] is False
    assert sign["reason"]
    assert sign["workflow_id"] is None


async def test_available_section_with_zero_steps_is_not_unavailable(
    client, auth, db_session, project_id
):
    """`available=true` 但 `total=0` ⇒ **不是**「不可用」—— 两种空态必须可分辨。"""
    deliverable, _ = await _make_deliverable(db_session, project_id)

    resp = await client.get(
        f"/api/v1/deliverables/{deliverable.deliverable_id}/progress", headers=auth
    )

    assert resp.status_code == 200, resp.text
    sign = resp.json()["sections"][0]
    assert sign["available"] is True
    assert sign["reason"] is None
    assert sign["total"] == 0


# ---------------------------------------------------------------------------
# 5 态计数恒存在
# ---------------------------------------------------------------------------


async def test_five_state_counts_always_present(client, auth, db_session, project_id):
    """5 态计数**恒存在**（含 0）—— 甘特图按 5 态上色，缺一态前端要么画不出
    颜色、要么自己编一个（= 第二份真相源）。"""
    deliverable, _ = await _make_deliverable(db_session, project_id)

    resp = await client.get(
        f"/api/v1/deliverables/{deliverable.deliverable_id}/progress", headers=auth
    )

    assert resp.status_code == 200, resp.text
    for section in resp.json()["sections"]:
        for key in ("pending", "in_progress", "completed", "skipped", "failed"):
            assert key in section, f"{key} 缺失于 {section['workflow_type']}"
            assert isinstance(section[key], int)


async def test_counts_reflect_seeded_rows(client, auth, db_session, project_id):
    """计数真的来自观测行。"""
    deliverable, version = await _make_deliverable(db_session, project_id)
    assert version is not None
    await _seed_progress(
        db_session,
        project_id=project_id,
        workflow_type=WorkflowType.SIGN,
        workflow_id=version.version_id,
        step_order=1,
        state=WorkflowProgressState.COMPLETED,
    )
    await _seed_progress(
        db_session,
        project_id=project_id,
        workflow_type=WorkflowType.SIGN,
        workflow_id=version.version_id,
        step_order=2,
        state=WorkflowProgressState.IN_PROGRESS,
    )

    resp = await client.get(
        f"/api/v1/deliverables/{deliverable.deliverable_id}/progress", headers=auth
    )

    assert resp.status_code == 200, resp.text
    sign = resp.json()["sections"][0]
    assert sign["total"] == 2
    assert sign["completed"] == 1
    assert sign["in_progress"] == 1
    assert sign["pending"] == 0
    assert len(sign["items"]) == 2
    # 步骤序号升序
    assert [i["step_order"] for i in sign["items"]] == [1, 2]


# ---------------------------------------------------------------------------
# 越权 404
# ---------------------------------------------------------------------------


async def test_other_project_deliverable_is_404(
    db_engine, db_session, auth, project_id
):
    """别的项目的交付物 ⇒ 404（不是 403）。

    ⚠️ 必须用 `_guard_client` —— 默认 `client` fixture 把项目守卫 mock 成恒
    True，在它上面测「越权被拒」是**空断言**。
    """
    other_project = uuid.uuid4()
    deliverable, _ = await _make_deliverable(db_session, other_project)

    async with _guard_client(db_engine) as ac:
        resp = await ac.get(
            f"/api/v1/deliverables/{deliverable.deliverable_id}/progress", headers=auth
        )

    assert resp.status_code == 404
    # ⚠️ 只断言 404 会在「端点还不存在」时也绿 ⇒ 断**消息**（路由未命中的
    #    404 说的是 "Not Found"，项目守卫说的是 "Project not found: ..."）。
    assert "Project not found" in resp.json()["message"]


async def test_unknown_deliverable_is_404_with_code(client, auth):
    """交付物不存在 ⇒ 404 且带 code（只断言 404 会在端点不存在时就绿）。"""
    resp = await client.get(
        f"/api/v1/deliverables/{uuid.uuid4()}/progress", headers=auth
    )

    assert resp.status_code == 404, resp.text
    assert resp.json()["code"] == "DELIVERABLE_NOT_FOUND"


# ---------------------------------------------------------------------------
# 禁 N+1（R-16）
# ---------------------------------------------------------------------------


async def test_request_does_not_n_plus_one(
    client, auth, db_session, project_id, select_counter
):
    """整次请求的 SELECT 数 ≤ 5（禁 N+1）⇒ 靠**一条批量查询**取回两段的观测行。

    ⚠️ 计数**只算请求期间**的 SELECT —— 造数据的查询不计入。
    ⚠️ 现状实测 **3 条**（取交付物 1 + 取当前版本 1 + 批量取观测行 1）。
    ⇒ 若有人退回「每段各查一次 + 每段反查项目」，就是 7 条 ⇒ 本条变红。
    """
    deliverable, version = await _make_deliverable(db_session, project_id)
    assert version is not None
    await _seed_progress(
        db_session,
        project_id=project_id,
        workflow_type=WorkflowType.SIGN,
        workflow_id=version.version_id,
    )
    await _seed_progress(
        db_session,
        project_id=project_id,
        workflow_type=WorkflowType.CUSTOMER_APPROVAL_PROXY,
        workflow_id=deliverable.deliverable_id,
        step_role="CUSTOMER",
    )

    select_counter["n"] = 0
    resp = await client.get(
        f"/api/v1/deliverables/{deliverable.deliverable_id}/progress", headers=auth
    )

    assert resp.status_code == 200, resp.text
    assert select_counter["n"] <= 5, f"SELECT 数 {select_counter['n']} > 5（N+1）"
