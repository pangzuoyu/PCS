"""`streams.source` 列（用户裁决 1a · P9B-3 · T2.5）。

## 这一列是什么

SPEC §7.7.1 的物流列表有「来源」列（SIM导入 / 手动 / Excel / 化验）⇒ 后端
得有一个**能筛能显示**的字段承载它。

## ⚠️ 它与既有的 `streams.source_type` **不是同一列**

| 列 | 语义 | 取值 |
|---|---|---|
| `source`（本列） | **录入通道**（怎么进系统的） | 4 值：MANUAL / SIM_IMPORT / EXCEL / LAB |
| `source_type`（既有） | **产出方式**（数据怎么算出来的） | 13 值：SIM_IMPORT / MANUAL_ENTRY / LAB_REPORT + 10 个 `*_CALCULATED` |

⚠️ 两者有 3 处取值重叠但拼写不同（SIM_IMPORT 同名 / MANUAL_ENTRY↔MANUAL /
LAB_REPORT↔LAB）⇒ **防漂移靠本文件末尾的一致性断言**，不是靠「大家记得填对」。

## 4 个取值

| 值 | 含义 | 谁写 |
|---|---|---|
| `MANUAL` | 手动创建向导 | T7 向导 |
| `SIM_IMPORT` | 模拟软件导出（**PRO/II / HYSYS / Aspen 都归它**，用户裁决 1b） | PRO/II 导入路径 |
| `EXCEL` | Excel 双 Sheet 导入 | Excel 导入路径 |
| `LAB` | 化验报告（**预留**，本批无写入路径） | — |
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.project import Project, Stream, Workspace

pytestmark = pytest.mark.asyncio


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


async def _create(client, proj, headers, **kw):
    return await client.post(
        f"/api/v1/projects/{proj.project_id}/streams",
        json={"payload": _payload(**kw)},
        headers=headers,
    )


# ---------------------------------------------------------------------------
# 断言 1 / 2 / 3：契约层（默认 MANUAL / 显式取值 / 词表外被拒）
# ---------------------------------------------------------------------------


async def test_create_without_source_defaults_to_manual(
    client, make_project, designer_headers
):
    """不传 `source` ⇒ 落库为 `MANUAL`（默认值在**契约层**兜住）。"""
    proj = await make_project()
    resp = await _create(client, proj, designer_headers)
    assert resp.status_code == 201, resp.text
    assert resp.json()["source"] == "MANUAL"


async def test_create_with_source_sim_import(
    client, make_project, designer_headers
):
    """显式传 `source='SIM_IMPORT'` ⇒ 落库正确。"""
    proj = await make_project()
    resp = await _create(client, proj, designer_headers, source="SIM_IMPORT")
    assert resp.status_code == 201, resp.text
    assert resp.json()["source"] == "SIM_IMPORT"


async def test_create_with_invalid_source_is_422(
    client, make_project, designer_headers
):
    """⚠️ 词表外的值 ⇒ **422**（API 路径上是 Pydantic 枚举先拒）。"""
    proj = await make_project()
    resp = await _create(client, proj, designer_headers, source="INVALID")
    assert resp.status_code == 422, resp.text


async def test_db_check_constraint_rejects_invalid_source(db_session):
    """⚠️ DB 路径（绕过 schema 的写入）⇒ CHECK 约束挡住。

    单测库是从 **ORM metadata** 建表的（不是迁移产物）⇒ 该 CHECK **存在**
    ⇒ 这条**不依赖 PG**，SQLite 也真跑。
    """
    row = Stream(
        project_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        stream_name="S-CHECK",
        case_type="NORMAL",
        data_mode="CHEMICAL",
        source_type="MANUAL_ENTRY",
        source="NOT_A_REAL_SOURCE",
        approval_depth=1,
        record_hash="h",
    )
    db_session.add(row)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


# ---------------------------------------------------------------------------
# 断言 4 / 5：响应带 source + 按 source 筛选
# ---------------------------------------------------------------------------


async def test_list_response_carries_source(
    client, make_project, designer_headers
):
    """列表响应带 `source` 字段。"""
    proj = await make_project()
    await _create(client, proj, designer_headers, source="EXCEL")
    resp = await client.get(
        f"/api/v1/projects/{proj.project_id}/streams", headers=designer_headers
    )
    assert resp.status_code == 200, resp.text
    items = resp.json()
    assert len(items) == 1
    assert items[0]["source"] == "EXCEL"


async def test_list_filter_by_source(client, make_project, designer_headers):
    """`?source=MANUAL` ⇒ 只返回匹配的。"""
    proj = await make_project()
    await _create(client, proj, designer_headers, stream_name="S-A")
    await _create(
        client, proj, designer_headers, stream_name="S-B", source="SIM_IMPORT"
    )

    resp = await client.get(
        f"/api/v1/projects/{proj.project_id}/streams?source=SIM_IMPORT",
        headers=designer_headers,
    )
    assert resp.status_code == 200, resp.text
    items = resp.json()
    assert [i["stream_name"] for i in items] == ["S-B"]


# ---------------------------------------------------------------------------
# 断言 6：两列在每个写入点**成对赋值**（防漂移）
# ---------------------------------------------------------------------------


async def test_proii_import_writes_sim_import_for_both_columns():
    """PRO/II 导入 ⇒ `source='SIM_IMPORT'` **且** `source_type='SIM_IMPORT'`。"""
    from app.services.import_service import _proii_preview_entry
    from app.services.property_completion import ParsedStream

    entry = _proii_preview_entry(
        ParsedStream(tag="S-1", phase="VAPOR"),
        banner_version="9.1",
        unreliable_set=set(),
        mixed_set=set(),
        warnings=[],
    )
    assert entry["source"] == "SIM_IMPORT"
    assert entry["source_type"] == "SIM_IMPORT"


async def test_excel_import_writes_excel_source_but_keeps_legacy_source_type():
    """Excel 导入 ⇒ `source='EXCEL'`，而 `source_type` **仍是** `SIM_IMPORT`。

    ⚠️ 两列取值**不同是有意的** —— `source_type` 的词表里没有 `EXCEL`，
    本批**不扩**它（已登记为未解决问题）。
    """
    from app.services.import_service import _excel_preview_entry
    from app.services.property_completion import ParsedStream

    entry = _excel_preview_entry(ParsedStream(tag="S-1", phase="LIQUID"))
    assert entry["source"] == "EXCEL"
    assert entry["source_type"] == "SIM_IMPORT"


# ---------------------------------------------------------------------------
# 断言 7：出口流**继承**上游的 source
# ---------------------------------------------------------------------------


async def test_outlet_stream_inherits_upstream_source(
    db_session, make_project
):
    """设备计算出口流 ⇒ `source` == 其上游物流的 `source`（不是默认 MANUAL）。"""
    from app.services.outlet_stream import create_outlet_stream

    proj = await make_project()
    upstream = Stream(
        project_id=proj.project_id,
        workspace_id=proj.workspace_id,
        stream_name="S-UP",
        case_type="NORMAL",
        data_mode="CHEMICAL",
        source_type="SIM_IMPORT",
        source="SIM_IMPORT",
        approval_depth=1,
        record_hash="h",
    )
    db_session.add(upstream)
    await db_session.commit()

    outlet = await create_outlet_stream(
        db_session,
        source_stream_id=upstream.stream_id,
        calc_type="PT_FLASH",
        source_type="FLASH_CALCULATED",
        properties={},
        project_id=proj.project_id,
        workspace_id=proj.workspace_id,
    )
    await db_session.commit()

    assert outlet.source == "SIM_IMPORT"

    row = (
        await db_session.execute(
            select(Stream).where(Stream.stream_id == outlet.stream_id)
        )
    ).scalar_one()
    assert row.source == "SIM_IMPORT"
