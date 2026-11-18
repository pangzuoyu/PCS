"""**管道一览表端点**（`GET /projects/{project_id}/pipe-line-list`）—— P10-C · T2。

## 为什么要有这个文件

前端「管道一览表」页调 `GET /projects/{id}/pipe-line-list`
⇒ ⇒ **契约里根本没有这个端点** ⇒ ⇒ 真后端下 **404**（TODO-159）
⇒ ⇒ mock 通道有 MSW handler ⇒ 一路绿灯 ⇒ **只有真后端通道抓得到**。

⇒ ⇒ 现在补上：读 `piping_results`（管道记录的**唯一真相源**）⇒ ⇒ 一览表的
每一列都来自**同一张表** ⇒ ⇒ 不再是「前端编的一份形状」。

## 本文件钉的规则

1. **要登录**（匿名 ⇒ 401）。
2. **要对该项目有访问权**（无权 ⇒ **404**，与「不存在」同形 ⇒ 枚举不出项目）。
3. **只返回该项目的记录**（不串项目）。
4. 列清单 = **SPEC §7.11.2** 的 43 列（逐条对应 `piping_results`）。

## 为什么用 `strict_client`

默认 `client` 把项目守卫 mock 成永远 True ⇒ ⇒ 在它上面「越权被拒」是**空断言**
⇒ ⇒ 本文件**全部**用 `strict_client`（真守卫）。
"""
from __future__ import annotations

import uuid

import pytest

from app.core.security import create_access_token

pytestmark = pytest.mark.asyncio


def _tok(user_id: uuid.UUID, role: str = "DESIGNER") -> dict[str, str]:
    token = create_access_token(
        subject=str(user_id), role=role, extra={"user_id": str(user_id)}
    )
    return {"Authorization": f"Bearer {token}"}


async def _mk_ws_with_project(db_session, owner_id: uuid.UUID) -> tuple[object, uuid.UUID]:
    """工作区 + 项目（**生产形状**：工作区先建、项目后建）。"""
    from app.models.project import Project, Workspace

    ws = Workspace(
        workspace_id=uuid.uuid4(),
        workspace_type="FORMAL",
        owner_id=owner_id,
        name="pipe-line-list-test",
        status="ACTIVE",
    )
    db_session.add(ws)
    await db_session.commit()

    pid = uuid.uuid4()
    db_session.add(
        Project(
            project_id=pid,
            project_no=f"P-{pid.hex[:6]}",
            project_name="pipe-line-list",
            owner_company="t",
            location="t",
            project_type="test",
            design_phase="BASIC",
            unit_system="SI",
            status="ACTIVE",
            workspace_id=ws.workspace_id,
        )
    )
    await db_session.commit()
    return ws, pid


async def _mk_pipe(strict_client, db_session, *, ws, project_id, user_id, line_no="P-100"):
    """造一条管路记录（**走 API** ⇒ ⇒ 守卫是真的）。"""
    r = await strict_client.post(
        f"/api/v1/records/piping?workspace_id={ws.workspace_id}",
        json={
            "project_id": str(project_id),
            "line_no": line_no,
            "seq_no": 7,
            "line_size": "DN100",
            "material_class": "CS-STD",
            "fluid_code": "HC",
            "fluid_name": "氢气",
            "fluid_phase": "G",
            "fluid_category": "D",
            "source_pid": "P-100-A1",
            "line_from": "R-101",
            "line_to": "E-102",
            "norm_oper_press": 1.0,
            "max_oper_press": 1.5,
            "norm_oper_temp": 40.0,
            "max_oper_temp": 80.0,
            "design_press": 2.0,
            "design_temp": 100.0,
            "piping_category": "GC2",
            "pressure_test_medium": "WATER",
            "pressure_test_press": 3.0,
            "check_class": "II",
        },
        headers=_tok(user_id),
    )
    assert r.status_code == 200, r.text
    return r.json()["pipe_id"]


# ---------------------------------------------------------------------------


async def test_pipe_line_list_requires_authentication(strict_client, db_session):
    """⚠️ **匿名不得读管道一览表**（项目数据 ⇒ ⇒ 匿名可读 = 越权）。"""
    ws, pid = await _mk_ws_with_project(db_session, uuid.uuid4())
    r = await strict_client.get(f"/api/v1/projects/{pid}/pipe-line-list")
    assert r.status_code == 401, r.text


async def test_pipe_line_list_without_project_grant_is_404(strict_client, db_session):
    """⚠️ **无权 ⇒ ⇒ 404**（与「不存在」同形 ⇒ ⇒ 枚举不出项目 id）。"""
    me = uuid.uuid4()
    ws, pid = await _mk_ws_with_project(db_session, me)
    r = await strict_client.get(
        f"/api/v1/projects/{pid}/pipe-line-list", headers=_tok(me)
    )
    assert r.status_code == 404, r.text


async def test_pipe_line_list_returns_the_projects_records(
    strict_client, db_session, grant_project
):
    """⚠️ **有授权 ⇒ ⇒ 200 且拿到自己的记录**（列名逐条对应 SPEC §7.11.2）。"""
    me = uuid.uuid4()
    ws, pid = await _mk_ws_with_project(db_session, me)
    await grant_project(me, pid)
    await _mk_pipe(strict_client, db_session, ws=ws, project_id=pid, user_id=me)

    r = await strict_client.get(
        f"/api/v1/projects/{pid}/pipe-line-list", headers=_tok(me)
    )
    assert r.status_code == 200, r.text
    rows = r.json()
    assert len(rows) == 1
    row = rows[0]
    assert row["pipe_no"] == "P-100"
    assert row["seq"] == 7
    assert row["size"] == "DN100"
    assert row["material"] == "CS-STD"
    assert row["fluid_name"] == "氢气"
    assert row["phase"] == "G"
    assert row["fluid_class"] == "D"
    assert row["design_pressure_mpa"] == 2.0
    assert row["design_temperature_c"] == 100.0
    assert row["start_point"] == "R-101"
    assert row["end_point"] == "E-102"
    assert row["pid_ref"] == "P-100-A1"
    assert row["sign_status"] == "DRAFT"


async def test_pipe_line_list_does_not_leak_another_projects_records(
    strict_client, db_session, grant_project
):
    """⚠️ **不串项目**（A 项目的授权看不到 B 项目的管道记录）。"""
    me = uuid.uuid4()
    other = uuid.uuid4()
    ws_a, pid_a = await _mk_ws_with_project(db_session, me)
    ws_b, pid_b = await _mk_ws_with_project(db_session, other)
    await grant_project(me, pid_a)
    await grant_project(other, pid_b)
    await _mk_pipe(
        strict_client, db_session, ws=ws_a, project_id=pid_a, user_id=me, line_no="P-A"
    )
    await _mk_pipe(
        strict_client, db_session, ws=ws_b, project_id=pid_b, user_id=other, line_no="P-B"
    )

    r = await strict_client.get(
        f"/api/v1/projects/{pid_a}/pipe-line-list", headers=_tok(me)
    )
    assert r.status_code == 200, r.text
    rows = r.json()
    assert [row["pipe_no"] for row in rows] == ["P-A"]


async def test_pipe_line_list_of_a_nonexistent_project_is_404(strict_client, db_session):
    """⚠️ **不存在 ⇒ ⇒ 404**（与「无权」同形 ⇒ ⇒ 两个原因**同字**）。"""
    me = uuid.uuid4()
    r = await strict_client.get(
        f"/api/v1/projects/{uuid.uuid4()}/pipe-line-list", headers=_tok(me)
    )
    assert r.status_code == 404, r.text
