"""血缘端点的项目守卫 —— P9B-4 紧急批次 T5（TODO-114）。

## 这个文件在钉什么

2026-11-04 实测：`GET /lineage/streams/{B}/graph` 返回 404，但原因是
「no lineage for record」⇒ **不是权限拒绝** ⇒ 守卫**结构性缺失**
（`_guard_record_access` 里 `if record_type != "PipingResult": return` ⇒
`streams` 整个跳过访问校验）。

⇒ 本文件给 `record_type='streams'` 补上项目守卫，并钉住三条性质：

1. **跨项目 ⇒ 404**（三个血缘端点：graph / upstream / downstream）。
2. **无权 ≡ 不存在 ⇒ 逐字同形** ⇒ 枚举不出某个 UUID 是否存在。
3. **自己项目内的血缘图照常读得到**（否则「永远 404」的守卫也能让 404 测试全绿）。

## ⚠️ 测试怎么证明「守卫真的跑了」

跨项目的物流**带上血缘行** ⇒ 守卫缺失时端点会返回 **200 + 图** ⇒ 断言 404
就能区分「守卫跑了」与「守卫没跑」（光看 message 不行 —— 无权与不存在
**故意**同形）。
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.project import Project, Stream, Workspace
from app.models.system import DataLineage

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# fixtures / helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def designer_headers() -> dict[str, str]:
    token = create_access_token(subject="lineage-designer", role="DESIGNER")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def designer_user_id() -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_DNS, "lineage-designer")


@pytest_asyncio.fixture
async def make_project(db: AsyncSession):
    async def _make() -> Project:
        ws = Workspace(workspace_type="FORMAL", name=f"ws-{uuid.uuid4().hex[:8]}")
        db.add(ws)
        await db.flush()
        proj = Project(
            project_no=f"P-{uuid.uuid4().hex[:8]}",
            project_name="血缘测试",
            owner_company="测试业主",
            location="测试地点",
            project_type="CHEMICAL",
            design_phase="FEED",
            unit_system="SI",
            workspace_id=ws.workspace_id,
        )
        db.add(proj)
        await db.commit()
        await db.refresh(proj)
        return proj

    return _make


@pytest_asyncio.fixture
async def make_stream(db: AsyncSession):
    async def _make(project: Project) -> Stream:
        stream = Stream(
            project_id=project.project_id,
            workspace_id=project.workspace_id,
            stream_name=f"S-{uuid.uuid4().hex[:6]}",
            case_type="NORMAL",
            data_mode="CHEMICAL",
            source_type="MANUAL_ENTRY",
            approval_depth=1,
        )
        db.add(stream)
        await db.commit()
        await db.refresh(stream)
        return stream

    return _make


@pytest_asyncio.fixture
async def make_lineage(db: AsyncSession):
    """给一条物流落**一条血缘行**（没有它，血缘端点会 404 ⇒ 测不出守卫）。"""

    async def _make(stream: Stream) -> DataLineage:
        row = DataLineage(
            record_type="streams",
            record_id=stream.stream_id,
            source="USER",
            change_summary="创建",
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
        return row

    return _make


@pytest_asyncio.fixture
async def projects(make_project, grant_project, designer_user_id):
    """项目 A（**已授权**）+ 项目 B（**未授权**）。"""
    project_a = await make_project()
    project_b = await make_project()
    await grant_project(
        designer_user_id, project_a.project_id, username="lineage-designer"
    )
    return project_a, project_b


# ---------------------------------------------------------------------------
# 跨项目 ⇒ 404
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("suffix", ["/graph", "/upstream", "/downstream"])
async def test_lineage_of_another_project_stream_is_404(
    strict_client, make_stream, make_lineage, projects, designer_headers, suffix
):
    """`record_type='streams'` ⇒ 跨项目物流的血缘图/链 ⇒ **404**。"""
    _project_a, project_b = projects
    stream = await make_stream(project_b)
    await make_lineage(stream)

    r = await strict_client.get(
        f"/api/v1/lineage/streams/{stream.stream_id}{suffix}", headers=designer_headers
    )
    assert r.status_code == 404, r.text


# ---------------------------------------------------------------------------
# 同形：跨项目 ≡ 不存在（逐字相同）
# ---------------------------------------------------------------------------


async def test_lineage_cross_project_looks_identical_to_missing(
    strict_client, make_stream, make_lineage, projects, designer_headers
):
    """跨项目与不存在 ⇒ **逐字相同**的 404 ⇒ 枚举不出某个 UUID 是否存在。"""
    _project_a, project_b = projects
    stream = await make_stream(project_b)
    await make_lineage(stream)

    r_missing = await strict_client.get(
        f"/api/v1/lineage/streams/{uuid.uuid4()}/graph", headers=designer_headers
    )
    r_forbidden = await strict_client.get(
        f"/api/v1/lineage/streams/{stream.stream_id}/graph", headers=designer_headers
    )

    assert r_missing.status_code == r_forbidden.status_code == 404
    assert r_missing.json()["code"] == r_forbidden.json()["code"]
    assert r_missing.json()["message"] == r_forbidden.json()["message"]


# ---------------------------------------------------------------------------
# 正向：自己项目内的血缘图**照常读得到**
# ---------------------------------------------------------------------------


async def test_own_project_lineage_graph_is_readable(
    strict_client, make_stream, make_lineage, projects, designer_headers
):
    """已授权项目里的物流 ⇒ 血缘图**读得到**（守卫不能把正常路径也堵死）。"""
    project_a, _project_b = projects
    stream = await make_stream(project_a)
    await make_lineage(stream)

    r = await strict_client.get(
        f"/api/v1/lineage/streams/{stream.stream_id}/graph", headers=designer_headers
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["root"]["record_id"] == str(stream.stream_id)
