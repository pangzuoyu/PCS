"""物流组成合计校验（SPEC §7.7.2「底部合计校验（100±0.5%）」）。

## 现状（2026-11-02 实测，与委员会 brief 的假设**不同**）

⚠️ brief 说「组成合计校验**根本不存在**（`grep COMPOSITION` = 0 命中）」——
**实测不成立**：它**存在**，但形态与计划假设的**完全不同**：

| | 既有（`conflict_resolver.py`） | 本任务要补的 |
|---|---|---|
| 位置 | **创建时**（`SIM-V09` BLOCK） | **送审时**（`POST /streams/{id}/submit`） |
| 容差 | 偏离 > **0.1%** 即 BLOCK（比 SPEC 严） | **100±0.5%**（SPEC §7.7.2） |
| 空对象 `{}` | `if not s.composition: return` ⇒ **静默跳过** | **拒绝**（未填写 ≠ 无组成） |
| 错误码 | `SIM_STREAM_BLOCKED` | `SIM_STREAM_COMPOSITION_OUT_OF_RANGE` |

⇒ **真正的缺口**是「送审这一关没有门禁」：一条物流若从**别的入口**进库
（导入路径覆盖 BLOCK 判定 / 直连 SQL / 脚本），组成不合法的它照样能进校对
⇒ 校对人在 Tab「组成」里看到合计 98.7% 却已经被要求签字（SPEC §5.1 门禁前置）。

## 口径（**已按实测钉死**）

`composition_json` 是 **`{CAS 号: 摩尔分率}` 字典**，值域 **0~1 的小数**
（**不是**百分数）—— 实测真库 `pcs_test` 的组成合计恒为 `1.0000`，
且 `flash_persist._extract_composition` 直接把 `comp[c]` 当摩尔分率喂闪蒸。

⇒ 合计 = `sum(float(v) for v in composition_json.values())`
⇒ 判定 `|合计 − 1| ≤ 0.005`（≡ SPEC §7.7.2 的「100±0.5%」）

## 为什么测试**直连 DB** 改组成

创建端点自己就跑 `SIM-V09`（BLOCK，0.1%）⇒ 组成偏离 1.3% 的物流**根本建不出来**
⇒ 走 API 创建**测不到**送审门禁。

⇒ 本文件**先正常创建**（组成合法）⇒ 再**直连 DB** 把 `composition_json` 改成
不合法的值（模拟「从别的入口进库」）⇒ 然后**送审** ⇒ 断言被拒。
这正是门禁要防的场景。
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.project import Project, Stream, Workspace

pytestmark = pytest.mark.asyncio

OUT_OF_RANGE_CODE = "SIM_STREAM_COMPOSITION_OUT_OF_RANGE"


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
        composition_json={"7732-18-5": 1.0},
    )
    base.update(kw)
    return base


async def _create_stream(client, proj, headers, **kw) -> dict[str, Any]:
    resp = await client.post(
        f"/api/v1/projects/{proj.project_id}/streams",
        json={"payload": _payload(**kw)},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _force_composition(db: AsyncSession, stream_id: str, value: Any) -> None:
    """直连 DB 改组成（模拟「从别的入口进库」的物流）。"""
    from sqlalchemy import update

    await db.execute(
        update(Stream)
        .where(Stream.stream_id == uuid.UUID(stream_id))
        .values(composition_json=value)
    )
    await db.commit()


# ---------------------------------------------------------------------------
# 断言 1：合计 98.7% ⇒ 送审被拒（422 + 具名错误码），且状态**不变**
# ---------------------------------------------------------------------------


async def test_submit_rejected_when_composition_sum_out_of_range(
    client, db_session, make_project, designer_headers
):
    """⚠️ 组成合计 98.7% ⇒ 送审**被拒**（422 具名错误码），状态仍是 DRAFT。"""
    proj = await make_project()
    stream = await _create_stream(client, proj, designer_headers)
    await _force_composition(
        db_session, stream["stream_id"], {"7732-18-5": 0.6, "7440-23-5": 0.387}
    )

    resp = await client.post(
        f"/api/v1/streams/{stream['stream_id']}/submit",
        headers=designer_headers,
    )

    assert resp.status_code == 422, resp.text
    assert resp.json()["code"] == OUT_OF_RANGE_CODE, resp.text

    # ⚠️ 状态**不变**（没进校对）—— 门禁前置的要点
    detail = await client.get(
        f"/api/v1/streams/{stream['stream_id']}", headers=designer_headers
    )
    assert detail.json()["sign_status"] == "DRAFT", detail.text


# ---------------------------------------------------------------------------
# 断言 2：合计 100% ⇒ 放行
# ---------------------------------------------------------------------------


async def test_submit_allowed_when_composition_sum_is_one(
    client, db_session, make_project, designer_headers
):
    """合计 = 1.0 ⇒ 放行（不是那个错误码）。"""
    proj = await make_project()
    stream = await _create_stream(client, proj, designer_headers)
    await _force_composition(
        db_session, stream["stream_id"], {"7732-18-5": 0.6, "7440-23-5": 0.4}
    )

    resp = await client.post(
        f"/api/v1/streams/{stream['stream_id']}/submit",
        headers=designer_headers,
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["sign_status"] == "IN_APPROVAL", resp.text


# ---------------------------------------------------------------------------
# 断言 3（P2-1）：空组成的两种形态**行为不同**
# ---------------------------------------------------------------------------


async def test_submit_rejected_when_composition_is_empty_object(
    client, db_session, make_project, designer_headers
):
    """`composition_json = {}` ⇒ **未填写** ⇒ 拒绝提交校对。

    ⚠️ 既有 `SIM-V09` 是 `if not s.composition: return` ⇒ 空对象**静默跳过**
    ⇒ 「忘了填」与「无组成」在那边分不开。
    """
    proj = await make_project()
    stream = await _create_stream(client, proj, designer_headers)
    await _force_composition(db_session, stream["stream_id"], {})

    resp = await client.post(
        f"/api/v1/streams/{stream['stream_id']}/submit",
        headers=designer_headers,
    )

    assert resp.status_code == 422, resp.text
    assert resp.json()["code"] == OUT_OF_RANGE_CODE, resp.text


async def test_submit_allowed_when_composition_is_absent(
    client, db_session, make_project, designer_headers
):
    """`composition_json = null` ⇒ **无组成**（纯物质）⇒ 跳过校验，放行。"""
    proj = await make_project()
    stream = await _create_stream(client, proj, designer_headers)
    await _force_composition(db_session, stream["stream_id"], None)

    resp = await client.post(
        f"/api/v1/streams/{stream['stream_id']}/submit",
        headers=designer_headers,
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["sign_status"] == "IN_APPROVAL", resp.text
