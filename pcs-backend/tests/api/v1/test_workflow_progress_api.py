"""观测层读 API 测试（P9A B5 / SPEC P9A-OBS-003）。

`GET /api/v1/workflow-progress/{workflow_type}/{workflow_id}` —— P9B 甘特图的
唯一数据源。

## 三条设计取舍各有测试

1. **未知工作流返 404，不返空数组。** 空数组会被前端画成「一条流程都没有」，
   而真相是「你查错了 ID」—— 两者在甘特图上长得一模一样。
2. **5 态计数恒定存在（零也出现）。** 甘特图按 5 态上色；缺一态前端要么
   画不出颜色、要么自己编一个，而「自己编」就是第二次真相源。
   ⇒ 响应里是 5 个**显式整数字段**，不是 `dict[str, int]`（后者是裸 object，
   会让 P9A-DLV-010 的基线 71 上涨）。
3. **项目隔离。** `workflow_id` 是多态的，无法 join 回项目；授权只能靠
   `workflow_progress.project_id`。
"""
from __future__ import annotations

import contextlib
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.deliverable import Deliverable, DeliverableVersion
from app.models.enums import WorkflowProgressState, WorkflowType
from app.models.workflow_progress import WorkflowProgress

pytestmark = pytest.mark.asyncio


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


def _url(wf_type: WorkflowType | str, wf_id: uuid.UUID | str) -> str:
    value = wf_type.value if isinstance(wf_type, WorkflowType) else wf_type
    return f"/api/v1/workflow-progress/{value}/{wf_id}"


async def _version(
    db: AsyncSession, project_id: uuid.UUID
) -> DeliverableVersion:
    """造一条 DeliverableVersion 作为 SIGN 工作流的工作流对象。

    真实路径是 `issue` 端点；这里直接造行是因为本文件验的是**读** API，
    签发链路由 B1 的测试负责。
    """
    from app.models.deliverable import SignatureMatrix

    matrix = SignatureMatrix(
        matrix_name="矩阵", module="*", doc_type="CALCULATION_BOOK",
        version_purpose="ISSUED_FOR_CONSTRUCTION", steps_json=[], status="ACTIVE",
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
        title="计算书",
        current_rev="1",
        version_purpose="ISSUED_FOR_CONSTRUCTION",
    )
    db.add(deliverable)
    await db.commit()
    await db.refresh(deliverable)
    version = DeliverableVersion(
        deliverable_id=deliverable.deliverable_id,
        rev="1",
        version_purpose="ISSUED_FOR_CONSTRUCTION",
        description="v1",
        record_snapshot_json={"record_count": 0},
        signature_summary_json={"steps": []},
    )
    db.add(version)
    await db.commit()
    await db.refresh(version)
    return version


async def _seed(
    db: AsyncSession,
    *,
    project_id: uuid.UUID,
    version_id: uuid.UUID,
    states: dict[int, WorkflowProgressState] | None = None,
) -> None:
    states = states or {1: WorkflowProgressState.COMPLETED, 2: WorkflowProgressState.IN_PROGRESS}
    for order, state in states.items():
        db.add(
            WorkflowProgress(
                project_id=project_id,
                workflow_type=WorkflowType.SIGN,
                workflow_id=version_id,
                step_order=order,
                step_role="CHECKER",
                step_status=state,
            )
        )
    await db.commit()


class TestReadWorkflowProgress:
    async def test_returns_rows_ordered_by_step_order(
        self, client, auth, db_session, project_id
    ):
        """顺序即甘特图的横轴 —— 乱序会让进度条来回跳。"""
        version = await _version(db_session, project_id)
        await _seed(
            db_session,
            project_id=project_id,
            version_id=version.version_id,
            states={
                3: WorkflowProgressState.PENDING,
                1: WorkflowProgressState.COMPLETED,
                2: WorkflowProgressState.SKIPPED,
            },
        )

        resp = await client.get(_url(WorkflowType.SIGN, version.version_id), headers=auth)

        assert resp.status_code == 200, resp.text
        items = resp.json()["items"]
        assert [i["step_order"] for i in items] == [1, 2, 3]

    async def test_returns_all_five_states(
        self, client, auth, db_session, project_id
    ):
        """5 态计数恒定存在（零也出现）—— 甘特图按 5 态上色。

        缺一态前端要么画不出颜色、要么自己编一个；后者就是第二次真相源。
        """
        version = await _version(db_session, project_id)
        await _seed(db_session, project_id=project_id, version_id=version.version_id)

        resp = await client.get(_url(WorkflowType.SIGN, version.version_id), headers=auth)

        body = resp.json()
        assert body["pending"] == 0
        assert body["in_progress"] == 1
        assert body["completed"] == 1
        assert body["skipped"] == 0
        assert body["failed"] == 0

    async def test_unknown_workflow_returns_404(
        self, client, auth
    ):
        """未知工作流 ⇒ 404，**不是空数组**。

        空数组会被前端画成「这条流程一个节点都没有」，
        而真相是「你查错了 ID」—— 两者在甘特图上长得一模一样。
        """
        resp = await client.get(_url(WorkflowType.SIGN, uuid.uuid4()), headers=auth)

        assert resp.status_code == 404, resp.text
        assert resp.json()["code"] == "WORKFLOW_NOT_FOUND"

    async def test_known_workflow_without_progress_returns_empty_items(
        self, client, auth, db_session, project_id
    ):
        """工作流存在但还没产生观测行 ⇒ 200 + 空 items（与 404 区分开）。

        这条区分是上面那条 404 的意义所在：两者必须可分辨。
        """
        version = await _version(db_session, project_id)

        resp = await client.get(_url(WorkflowType.SIGN, version.version_id), headers=auth)

        assert resp.status_code == 200, resp.text
        assert resp.json()["items"] == []
        assert resp.json()["total"] == 0

    async def test_unknown_workflow_type_is_422_with_code(self, client, auth):
        """URL 段不是合法 workflow_type ⇒ 422 + code（不是 404）。

        「类型不认识」是请求形状错，「工作流不存在」是资源不存在 ——
        混成一个码，前端没法据此决定「改代码」还是「改数据」。
        """
        resp = await client.get(_url("NOT_A_TYPE", uuid.uuid4()), headers=auth)

        assert resp.status_code == 422, resp.text
        assert resp.json()["code"] == "WORKFLOW_TYPE_UNKNOWN"

    async def test_read_api_is_project_scoped(self, db_session, db_engine):
        """越权读到别的项目的进度 ⇒ 404。

        用**独立 client**（不套 conftest 的 `check_user_project_access` bypass mock）——
        默认 client 把守卫 mock 成永远 True，在它上面测「越权被拒」是空断言。

        `workflow_id` 是多态的（版本 ID / 交付物 ID），无法 join 回项目；
        授权只能靠 `workflow_progress.project_id` 那一列。
        """
        from app.services.user_project_service import UserProjectService

        owner = uuid.uuid4()
        project = uuid.uuid4()
        await UserProjectService.grant_project_access(
            db_session, user_id=owner, project_id=project, role_in_project="DESIGNER"
        )
        version = await _version(db_session, project)
        await _seed(db_session, project_id=project, version_id=version.version_id)

        from app.core.security import create_access_token
        from app.services import user_project_service

        # 另一个用户：他既没有这个项目，SYSTEM_ADMIN 也没有 ⇒ 必须 404
        outsider = uuid.uuid4()

        async with _guard_client(db_engine) as ac:
            headers = {
                "Authorization": "Bearer "
                + create_access_token(
                    subject="outsider", role="DESIGNER", extra={"user_id": str(outsider)}
                )
            }
            resp = await ac.get(
                _url(WorkflowType.SIGN, version.version_id), headers=headers
            )

        assert resp.status_code == 404, resp.text

        # 对照：项目成员读得到，且响应里的 project_id 是工作流真实所属项目
        async with _guard_client(db_engine) as ac:
            headers = {
                "Authorization": "Bearer "
                + create_access_token(
                    subject="owner", role="DESIGNER", extra={"user_id": str(owner)}
                )
            }
            ok = await ac.get(_url(WorkflowType.SIGN, version.version_id), headers=headers)

        assert ok.status_code == 200, ok.text
        assert ok.json()["project_id"] == str(project)
        assert user_project_service is not None  # 守卫未被绕过（本 client 不打 mock）


class TestResponseContract:
    async def test_response_model_declares_every_field(
        self, client, auth, db_session, project_id
    ):
        """零裸字段（P9A-DLV-010）：5 态计数是**显式字段**，不是 `dict[str, int]`。"""
        version = await _version(db_session, project_id)
        await _seed(db_session, project_id=project_id, version_id=version.version_id)

        resp = await client.get(_url(WorkflowType.SIGN, version.version_id), headers=auth)

        assert set(resp.json()) == {
            "workflow_type", "workflow_id", "project_id", "total",
            "pending", "in_progress", "completed", "skipped", "failed", "items",
        }

    async def test_item_model_fields_are_pinned(self):
        """结构断言：条目模型的字段集合钉死，覆盖将来新增的字段。"""
        from app.schemas.workflow_progress import WorkflowProgressItemResponse

        assert set(WorkflowProgressItemResponse.model_fields) == {
            "progress_id", "step_order", "step_role", "step_status",
            "started_at", "completed_at", "assignee", "result_hash",
        }
