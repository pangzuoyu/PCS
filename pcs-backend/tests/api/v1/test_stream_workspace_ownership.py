"""物流创建的 **workspace 归属** —— P9B-4 T0-C（TODO-133）。

## 这个文件在钉什么

2026-11-10 实测：`POST /projects/{id}/streams` 的 `workspace_id` 取自
**请求体**（`req.workspace_id or project.workspace_id`）⇒ **从不校验它属于
URL 里的那个项目** ⇒ 只拥有项目 A 权限的用户能把物流**挂到项目 B 的工作区**。

⚠️ 上批补的是 URL 那一维（`project_id` 的项目守卫）⇒ **工作区那一维一直
空着** ⇒ 两个维度都补齐才算「物流挂不到别处」。

## 裁决：**静默纠正**（不是报错）

传了**别的项目**的 `workspace_id` ⇒ 创建**成功**（201），但落点工作区
== **URL 那个项目的** `project.workspace_id`。

为什么静默而不是报错：
- 报错要**多一次查询**（校验那个 workspace 属于哪个项目）⇒ 而结果是**同一件事**
  （落点还是项目的）；
- 前端**根本不发**这个字段（实测：`grep -rn "workspace_id"
  pcs-frontend/src/pages/sim/ pcs-frontend/src/api/stream.ts` ⇒ **0 命中**）⇒
  报错路径**没有真实调用方**；
- ⚠️ **静默纠正的取舍**：调用方以为自己挂到 B ⇒ 实际落 A ⇒
  **数据落在正确的地方**（不是越权）⇒ 比「报错」更接近「零影响」。

⚠️ **契约不删字段**（删 = 破坏性契约变更）⇒ 字段保留但标 **deprecated**
（见 `app/api/v1/streams.py::CreateStreamRequest.workspace_id`）。
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.project import Project, Workspace

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# fixtures / helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def designer_headers() -> dict[str, str]:
    token = create_access_token(subject="ws-owner", role="DESIGNER")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def designer_user_id() -> uuid.UUID:
    """`ws-owner` 派生 UUID（与 `current_actor` 一致：uuid5(DNS, sub)）。"""
    return uuid.uuid5(uuid.NAMESPACE_DNS, "ws-owner")


@pytest_asyncio.fixture
async def make_project(db: AsyncSession):
    """项目工厂：每个项目**自带一个专属工作区**（这样「别的项目的工作区」可辨）。"""

    async def _make() -> Project:
        ws = Workspace(workspace_type="FORMAL", name=f"ws-{uuid.uuid4().hex[:8]}")
        db.add(ws)
        await db.flush()
        project = Project(
            project_no=f"P-{uuid.uuid4().hex[:8]}",
            project_name="测试项目",
            owner_company="测试业主",
            location="测试地点",
            project_type="CHEMICAL",
            design_phase="FEED",
            unit_system="SI",
            workspace_id=ws.workspace_id,
        )
        db.add(project)
        await db.commit()
        await db.refresh(project)
        return project

    return _make


def _payload() -> dict:
    """合法的 StreamBase 载荷（组成合计 100% ⇒ 过物性补全门禁）。"""
    return {
        "stream_name": f"S-{uuid.uuid4().hex[:6]}",
        "case_type": "NORMAL",
        "data_mode": "CHEMICAL",
        "source_type": "MANUAL_ENTRY",
        "phase": "LIQUID",
        "temp": 80.0,
        "press": 200.0,
        "mass_flow": 1000.0,
        "composition_json": {"7732-18-5": 1.0},
    }


# ---------------------------------------------------------------------------
# 核心：落点工作区**恒等于** URL 项目的 workspace_id
# ---------------------------------------------------------------------------
#
# ⚠️ **断言打在 DB 行上**（不是响应体）：`StreamResponse` **不含**
# `workspace_id` 字段 ⇒ 响应体里根本读不到落点 ⇒ 断言落点只能查库。
# （前端列表页也不显示工作区 ⇒ 这是后端**隔离维度**，不是展示字段。）

async def _created_stream_workspace(db: AsyncSession, stream_id: uuid.UUID) -> uuid.UUID:
    from app.models.project import Stream

    row = await db.get(Stream, stream_id)
    assert row is not None, "物流没落库"
    return row.workspace_id


async def test_foreign_workspace_id_is_ignored(
    strict_client, db_session, grant_project, make_project, designer_user_id, designer_headers
):
    """传**别的项目**的 `workspace_id` ⇒ 创建成功，但落点是 **URL 项目**的工作区。

    ⚠️ 断言**落点**（不是「报错了」）—— 这是「静默纠正」裁决本身。
    """
    project_a = await make_project()
    project_b = await make_project()
    await grant_project(
        designer_user_id, project_a.project_id, username="ws-owner"
    )

    r = await strict_client.post(
        f"/api/v1/projects/{project_a.project_id}/streams",
        json={"workspace_id": str(project_b.workspace_id), "payload": _payload()},
        headers=designer_headers,
    )
    assert r.status_code == 201, r.text
    landed = await _created_stream_workspace(
        db_session, uuid.UUID(r.json()["stream_id"])
    )
    assert landed == project_a.workspace_id, (
        "落点用了请求体里那个工作区 ⇒ 物流挂到了别的项目的工作区下"
    )


async def test_own_workspace_id_is_accepted(
    strict_client, db_session, grant_project, make_project, designer_user_id, designer_headers
):
    """对照组：传**本项目**的 `workspace_id` ⇒ 放行且落点相同。"""
    project_a = await make_project()
    await grant_project(
        designer_user_id, project_a.project_id, username="ws-owner"
    )

    r = await strict_client.post(
        f"/api/v1/projects/{project_a.project_id}/streams",
        json={"workspace_id": str(project_a.workspace_id), "payload": _payload()},
        headers=designer_headers,
    )
    assert r.status_code == 201, r.text
    landed = await _created_stream_workspace(
        db_session, uuid.UUID(r.json()["stream_id"])
    )
    assert landed == project_a.workspace_id


async def test_omitted_workspace_id_uses_project_workspace(
    strict_client, db_session, grant_project, make_project, designer_user_id, designer_headers
):
    """对照组：**不传** ⇒ 落点 = `project.workspace_id`（既有行为，不回归）。"""
    project_a = await make_project()
    await grant_project(
        designer_user_id, project_a.project_id, username="ws-owner"
    )

    r = await strict_client.post(
        f"/api/v1/projects/{project_a.project_id}/streams",
        json={"payload": _payload()},
        headers=designer_headers,
    )
    assert r.status_code == 201, r.text
    landed = await _created_stream_workspace(
        db_session, uuid.UUID(r.json()["stream_id"])
    )
    assert landed == project_a.workspace_id


async def test_validate_endpoint_also_ignores_foreign_workspace_id(
    monkeypatch,
    strict_client,
    db_session,
    grant_project,
    make_project,
    designer_user_id,
    designer_headers,
):
    """⚠️ **预演端点**（`/validate`）也得同口径。

    它**不写库**、**响应里也没有** `workspace_id` ⇒ 只能**窥探它构造
    `StreamCreate` 时用的 `workspace_id`**（monkeypatch 记录实参）⇒
    钉住「预演用的工作区 == URL 项目的工作区」。

    为什么这条也要管：预演跑的是**物性补全 + 冲突检测** ⇒ 若这里用请求体
    那个工作区 ⇒ **预演结论与实际落点不同口径**（前端拿预演结果提交，
    落点却不同）⇒ 同一个洞的另一个出口。
    """
    from app.api.v1 import streams as streams_mod

    project_a = await make_project()
    project_b = await make_project()
    await grant_project(
        designer_user_id, project_a.project_id, username="ws-owner"
    )

    captured: dict = {}
    real_stream_create = streams_mod.StreamCreate

    def _spy(**kwargs):
        captured.update(kwargs)
        return real_stream_create(**kwargs)

    monkeypatch.setattr(streams_mod, "StreamCreate", _spy)

    r = await strict_client.post(
        f"/api/v1/projects/{project_a.project_id}/streams/validate",
        json={"workspace_id": str(project_b.workspace_id), "payload": _payload()},
        headers=designer_headers,
    )
    assert r.status_code == 200, r.text
    assert captured.get("workspace_id") == project_a.workspace_id, (
        "预演端点仍用请求体的 workspace_id ⇒ 预演与落点不同口径"
    )
