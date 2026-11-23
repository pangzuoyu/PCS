"""`report.py` 的**项目守卫**必须真的拦住无权用户（TODO-181）。

## 为什么有本文件

TODO-181（P10-F · F3-T2b 的**抽样变异**实测）：

| 变异 | 删掉的东西 | 实测 |
|---|---|---|
| M4 | `report.py::_guard_project` 的守卫调用 | **45 个测试全绿** |
| M5 | `report.py::generate_report` 的守卫调用 | **29 个测试全绿** |

⇒ ⇒ **守卫删了没有任何测试变红** ⇒ ⇒ 「已覆盖」只是**代码上的**。

⚠️ **根因**：这些端点的测试都用**默认 `client`** ⇒ ⇒ 默认 `client` 把
`UserProjectService.check_user_project_access` mock 成**永远 True**
⇒ ⇒ 「无权 ⇒ 404」的断言即便写了也是 **no-op**。

⇒ ⇒ 本文件全部用 **`strict_client`**（不 mock 守卫）⇒ ⇒ 断言是**真的**。
⚠️ 与 TODO-173 的区别：那边走的是**角色字符串**（不受那个 mock 影响）
⇒ ⇒ 这边必须换 client 才有效。

⇒ ⇒ 另外：`GET /report/{id}/download` 原有的那条断言是
`status_code in (200, 404)` ⇒ ⇒ **恒真**（两个值都可能）⇒ ⇒ 不算覆盖
⇒ ⇒ 本文件用**真断言**取代它（有权 ⇒ ⇒ 200 · 无权 ⇒ ⇒ 404）。
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.project import Project
from app.models.report import ReportFile

pytestmark = pytest.mark.asyncio


def _auth(subject: str, *, user_id: uuid.UUID | None = None, role: str = "DESIGNER"):
    extra = {"user_id": str(user_id)} if user_id else None
    token = create_access_token(subject=subject, role=role, extra=extra)
    return {"Authorization": f"Bearer {token}"}


async def _mk_project(db: AsyncSession) -> Project:
    proj = Project(
        project_no=f"RPT-{uuid.uuid4().hex[:8]}",
        project_name="别人的项目",
        owner_company="X",
        location="X",
        project_type="CHEMICAL",
        design_phase="FEED",
        unit_system="SI",
        status="ACTIVE",
        workspace_id=uuid.uuid4(),
    )
    db.add(proj)
    await db.flush()
    return proj


async def _mk_report_file(db: AsyncSession, project_id: uuid.UUID) -> ReportFile:
    row = ReportFile(
        project_id=project_id,
        content_hash=uuid.uuid4().hex,
        file_path=f"/tmp/{uuid.uuid4().hex}.xlsx",
        file_format="xlsx",
        size_bytes=1,
        status="SUCCEEDED",
    )
    db.add(row)
    await db.flush()
    return row


# ---------------------------------------------------------------------------
# ① 无权用户 ⇒ ⇒ 404（与「不存在」同形）
# ---------------------------------------------------------------------------


async def test_report_status_is_404_without_project_access(
    strict_client, db: AsyncSession
):
    """⚠️ **无权用户拿状态 ⇒ ⇒ 404**（守卫删了 ⇒ ⇒ 这里红）。"""
    proj = await _mk_project(db)
    row = await _mk_report_file(db, proj.project_id)

    r = await strict_client.get(
        f"/api/v1/report/{row.report_file_id}/status",
        headers=_auth("intruder"),
    )
    assert r.status_code == 404, r.text


async def test_report_download_is_404_without_project_access(
    strict_client, db: AsyncSession
):
    """⚠️ **无权用户下载 ⇒ ⇒ 404**（原来那条 `in (200, 404)` 是恒真的）。"""
    proj = await _mk_project(db)
    row = await _mk_report_file(db, proj.project_id)

    r = await strict_client.get(
        f"/api/v1/report/{row.report_file_id}/download",
        headers=_auth("intruder"),
    )
    assert r.status_code == 404, r.text


async def test_report_hash_is_404_without_project_access(
    strict_client, db: AsyncSession
):
    """⚠️ **无权用户取哈希 ⇒ ⇒ 404**。"""
    proj = await _mk_project(db)
    row = await _mk_report_file(db, proj.project_id)

    r = await strict_client.get(
        f"/api/v1/report/{row.report_file_id}/hash",
        headers=_auth("intruder"),
    )
    assert r.status_code == 404, r.text


async def test_generate_into_an_unauthorized_project_is_404(
    strict_client, db: AsyncSession
):
    """⚠️ **不能入队到别人的项目** ⇒ ⇒ 404（守卫删了 ⇒ ⇒ 这里红）。"""
    proj = await _mk_project(db)

    r = await strict_client.post(
        "/api/v1/report/generate",
        headers=_auth("intruder"),
        json={
            "project_id": str(proj.project_id),
            "report_type": "EQUIPMENT_LIST",
            "output_format": "xlsx",
        },
    )
    assert r.status_code == 404, r.text


# ---------------------------------------------------------------------------
# ② 正对照：**有权**的用户不被误伤
# ---------------------------------------------------------------------------


async def test_report_status_is_200_for_an_authorized_user(
    strict_client, db: AsyncSession, grant_project
):
    """⚠️ **正对照**：有授权 ⇒ ⇒ 200（否则上面的 404 可能来自别处）。"""
    proj = await _mk_project(db)
    row = await _mk_report_file(db, proj.project_id)
    user_id = uuid.uuid4()
    await grant_project(user_id=user_id, project_id=proj.project_id)

    r = await strict_client.get(
        f"/api/v1/report/{row.report_file_id}/status",
        headers=_auth("owner", user_id=user_id),
    )
    assert r.status_code == 200, r.text
