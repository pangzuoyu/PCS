"""P3.x SIM-35：DELETE /streams/{id} 被引用时不可删除。

契约：
- 被引用（其他表存在 stream_id FK 记录）→ DELETE 拒绝（409 SIM_STREAM_REFERENCED）
- 错误信息含引用表名 + 引用条数，便于前端定位
- 无引用 → DELETE 允许（204）
- 引用表清单（当前实现）：
  1. stream_state_points（项目内状态点）
  2. flash_results（flash 计算结果）
  3. streams.upstream_stream_id（自引用，删除前需清空）

注：cascade delete 显式 NOT configured（FK 未带 ondelete='CASCADE'），所以
DB 层删除会被 FK constraint 拒；但 service 层先做引用计数检查，给出更清晰
的错误信息（指明哪张表+几条），而不是裸 IntegrityError。
"""
from __future__ import annotations

import uuid
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.calc import FlashResult
from app.models.project import (
    Project,
    Stream,
    StreamStatePoint,
    Workspace,
)


@pytest_asyncio.fixture
async def make_project(db: AsyncSession):
    async def _make() -> Project:
        ws = Workspace(workspace_type="FORMAL", name=f"ws-{uuid.uuid4().hex[:8]}")
        db.add(ws)
        await db.flush()
        proj = Project(
            project_no=f"P-{uuid.uuid4().hex[:8]}",
            project_name="测试项目",
            owner_company="测试业主",
            location="测试地点",
            project_type="CHEMICAL",
            design_phase="FEED",
            unit_system="SI",
            workspace_id=ws.workspace_id,
        )
        db.add(proj)
        await db.commit()
        return proj

    return _make


@pytest.fixture
def designer_headers() -> dict[str, str]:
    token = create_access_token(subject="test-designer", role="DESIGNER")
    return {"Authorization": f"Bearer {token}"}


def _payload(**kw) -> dict[str, Any]:
    base: dict[str, Any] = dict(
        stream_name="S-101",
        case_type="NORMAL",
        data_mode="CHEMICAL",
        source_type="MANUAL_ENTRY",
        temp=80.0,
        press=200.0,
        phase="LIQUID",
        mass_flow=1000.0,
    )
    base.update(kw)
    return base


async def _create_stream(client, project_id, headers) -> str:
    r = await client.post(
        f"/api/v1/projects/{project_id}/streams",
        json={"payload": _payload()},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()["stream_id"]


# ---------------------------------------------------------------------------
# 无引用：DELETE 允许（204）
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_unreferenced_stream_succeeds(
    client, make_project, designer_headers
):
    """无任何引用 → DELETE 204。"""
    proj = await make_project()
    sid = await _create_stream(client, proj.project_id, designer_headers)

    r = await client.delete(f"/api/v1/streams/{sid}", headers=designer_headers)
    assert r.status_code == 204, r.text


# ---------------------------------------------------------------------------
# 被 stream_state_points 引用：拒绝
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_blocked_when_state_point_references(
    client, db, make_project, designer_headers
):
    """存在 stream_state_points 引用 → 409 SIM_STREAM_REFERENCED。"""
    proj = await make_project()
    sid = await _create_stream(client, proj.project_id, designer_headers)

    # 直接 DB 写入状态点
    sp = StreamStatePoint(
        stream_id=uuid.UUID(sid),
        state_label="BASE",
        case_type="NORMAL",
        temp=80.0,
        press=200.0,
        phase="LIQUID",
        mass_flow=1000.0,
        composition_json={"71-43-2": 1.0},
        source_type="MANUAL_ENTRY",
    )
    db.add(sp)
    await db.commit()

    r = await client.delete(f"/api/v1/streams/{sid}", headers=designer_headers)
    assert r.status_code == 409, r.text
    body = r.json()
    assert body["code"] == "SIM_STREAM_REFERENCED"
    # 错误信息含引用表名
    assert "stream_state_points" in body["message"] or "state_point" in body["message"].lower()


# ---------------------------------------------------------------------------
# 被 flash_results 引用：拒绝
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_blocked_when_flash_result_references(
    client, db, make_project, designer_headers
):
    """存在 flash_results 引用 → 409 SIM_STREAM_REFERENCED。"""
    proj = await make_project()
    sid = await _create_stream(client, proj.project_id, designer_headers)

    flash = FlashResult(
        stream_id=uuid.UUID(sid),
        project_id=proj.project_id,
        workspace_id=proj.workspace_id,
        tag_number=f"FR-{uuid.uuid4().hex[:6]}",
        calc_type="FLASH",
        method="PRO/II",
        input_json={"temp": 80.0, "press": 200.0},
        output_json={"vapor_fraction": 0.0},
    )
    db.add(flash)
    await db.commit()

    r = await client.delete(f"/api/v1/streams/{sid}", headers=designer_headers)
    assert r.status_code == 409, r.text
    body = r.json()
    assert body["code"] == "SIM_STREAM_REFERENCED"
    assert "flash" in body["message"].lower() or "flash_results" in body["message"]


# ---------------------------------------------------------------------------
# 被下游物流引用（streams.upstream_stream_id 自引用）：拒绝
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_blocked_when_downstream_stream_references(
    client, db, make_project, designer_headers
):
    """存在**下游物流**引用（`streams.upstream_stream_id`）→ 409。

    ⚠️ **本模块 docstring 的引用表清单第三条就是它**（`streams.upstream_stream_id`
    自引用）⇒ 下面是「**已写下的契约没实现**」，不是新需求。

    ⚠️ **为什么这条要紧**：本批的「引用 📎×N」列（第①条聚合）数的就是
    `streams.upstream_stream_id` ⇒ 操作员看到「📎1 ⇒ 被引用」⇒ 删除 ⇒
    旧实现（清单里只有状态点与闪蒸结果）**查不到引用** ⇒ 直接 `db.delete` ⇒
    撞 FK（该 FK **无 `ondelete`** ⇒ PG 默认 NO ACTION）⇒ `IntegrityError`
    ⇒ 端点只捕 `PcsError` ⇒ **裸穿成 500**（用户看到一个无任何解释的 500，
    也不知道「先删下游 B」这条唯一出路）。
    """
    proj = await make_project()
    sid = await _create_stream(client, proj.project_id, designer_headers)

    # 下游物流：B 的 upstream_stream_id = A（计算出口流就是这么写的）
    downstream = Stream(
        project_id=proj.project_id,
        workspace_id=proj.workspace_id,
        stream_name=f"S-102-{uuid.uuid4().hex[:6]}",
        case_type="NORMAL",
        data_mode="CHEMICAL",
        source_type="MANUAL_ENTRY",
        approval_depth=1,
        upstream_stream_id=uuid.UUID(sid),
    )
    db.add(downstream)
    await db.commit()

    r = await client.delete(f"/api/v1/streams/{sid}", headers=designer_headers)
    assert r.status_code == 409, r.text
    body = r.json()
    assert body["code"] == "SIM_STREAM_REFERENCED"
    # 错误信息要指明是哪张表 + 几条（SIM-35 的契约）
    assert "streams" in body["message"].lower()


# ---------------------------------------------------------------------------
# 多处引用：报告所有引用表
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_blocked_lists_all_referencing_tables(
    client, db, make_project, designer_headers
):
    """多处引用时，错误信息应含所有引用表名（按表名去重）。"""
    proj = await make_project()
    sid = await _create_stream(client, proj.project_id, designer_headers)

    sp = StreamStatePoint(
        stream_id=uuid.UUID(sid),
        state_label="BASE",
        case_type="NORMAL",
        temp=80.0,
        press=200.0,
        phase="LIQUID",
        mass_flow=1000.0,
        composition_json={"71-43-2": 1.0},
        source_type="MANUAL_ENTRY",
    )
    flash = FlashResult(
        stream_id=uuid.UUID(sid),
        project_id=proj.project_id,
        workspace_id=proj.workspace_id,
        tag_number=f"FR-{uuid.uuid4().hex[:6]}",
        calc_type="FLASH",
        method="PRO/II",
        input_json={"temp": 80.0, "press": 200.0},
        output_json={"vapor_fraction": 0.0},
    )
    db.add_all([sp, flash])
    await db.commit()

    r = await client.delete(f"/api/v1/streams/{sid}", headers=designer_headers)
    assert r.status_code == 409
    body = r.json()
    assert body["code"] == "SIM_STREAM_REFERENCED"
    msg = body["message"].lower()
    assert "state_point" in msg
    assert "flash" in msg


# ---------------------------------------------------------------------------
# 404 / 401 / 403 契约不破坏
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_unknown_stream_returns_404(client, designer_headers):
    r = await client.delete(
        f"/api/v1/streams/{uuid.uuid4()}", headers=designer_headers
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_delete_missing_bearer_returns_401(
    client, make_project, designer_headers
):
    proj = await make_project()
    sid = await _create_stream(client, proj.project_id, designer_headers)
    r = await client.delete(f"/api/v1/streams/{sid}")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_delete_viewer_role_forbidden(
    client, make_project, designer_headers
):
    proj = await make_project()
    sid = await _create_stream(client, proj.project_id, designer_headers)
    viewer_token = create_access_token(subject="viewer", role="VIEWER")
    headers = {"Authorization": f"Bearer {viewer_token}"}
    r = await client.delete(f"/api/v1/streams/{sid}", headers=headers)
    assert r.status_code == 403
