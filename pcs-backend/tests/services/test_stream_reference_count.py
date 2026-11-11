"""物流「被引用数」的口径（P9B-4 · TODO-108）。

## 这个文件在钉什么

「引用 📎×N」列要回答一个 question：**这条物流被别的记录引用了几次**。
⚠️ 口径必须**钉死**（同一个词在两处含义不同 ⇒ 迟早打架）：

| 引用方 | 表 | 关系 | 计入 |
|---|---|---|---|
| 下游物流 | `streams.upstream_stream_id` | 别的物流把本物流当上游 | ✅ |
| 闪蒸结果 | `flash_results.stream_id` | 计算结果引用本物流 | ✅ |
| 状态点 | `stream_state_points.stream_id` | 物流自己的工况点（**子表**） | ❌ |
| 设备 | `sim_unit_op.*_streams_json` | JSONB 数组里的 id（**无索引**） | ❌ 延后 |

⚠️ **与删除门禁 `_collect_references` 的口径不同**（那边**含**状态点，
因为状态点会阻塞删除）⇒ 两个数字**不要**混用。

⚠️ **两条聚合查询**（整个列表 2 次往返）⇒ **不是 N+1**。
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.calc import FlashResult
from app.models.project import Project, Stream, Workspace
from app.services.stream_service import StreamService

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def project(db: AsyncSession) -> Project:
    """一个项目 + 它的专属工作区（`Stream` 两个 FK 都指它）。"""
    ws = Workspace(workspace_type="FORMAL", name=f"ws-{uuid.uuid4().hex[:8]}")
    db.add(ws)
    await db.flush()

    proj = Project(
        project_no=f"P-{uuid.uuid4().hex[:8]}",
        project_name="引用计数测试",
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


async def _make_stream(
    db: AsyncSession,
    project,
    *,
    upstream_stream_id: uuid.UUID | None = None,
) -> Stream:
    stream = Stream(
        project_id=project.project_id,
        workspace_id=project.workspace_id,
        stream_name=f"S-{uuid.uuid4().hex[:6]}",
        case_type="NORMAL",
        data_mode="CHEMICAL",
        source_type="MANUAL_ENTRY",
        approval_depth=1,
        upstream_stream_id=upstream_stream_id,
    )
    db.add(stream)
    await db.commit()
    await db.refresh(stream)
    return stream


async def _make_flash(db: AsyncSession, project, stream: Stream) -> FlashResult:
    row = FlashResult(
        project_id=project.project_id,
        workspace_id=project.workspace_id,
        stream_id=stream.stream_id,
        calc_type="T",
        method="PHI",
        input_json={},
        output_json={},
        tag_number=f"F-{uuid.uuid4().hex[:6]}",
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


# ---------------------------------------------------------------------------
# 口径
# ---------------------------------------------------------------------------


async def test_reference_count_counts_downstream_streams(db_session, project):
    """下游物流（`upstream_stream_id = S`）⇒ 计入。"""
    source = await _make_stream(db_session, project)
    await _make_stream(db_session, project, upstream_stream_id=source.stream_id)

    counts = await StreamService.reference_counts(db_session, [source.stream_id])
    assert counts[source.stream_id] == 1


async def test_reference_count_counts_flash_results(db_session, project):
    """闪蒸结果（`flash_results.stream_id = S`）⇒ 计入。"""
    source = await _make_stream(db_session, project)
    await _make_flash(db_session, project, source)

    counts = await StreamService.reference_counts(db_session, [source.stream_id])
    assert counts[source.stream_id] == 1


async def test_reference_count_excludes_own_state_points(db_session, project):
    """⚠️ **状态点不计入** —— 它是物流自己的子表，不是引用。

    （与删除门禁 `_collect_references` 的口径**有意不同**。）
    """
    from app.models.project import StreamStatePoint

    source = await _make_stream(db_session, project)
    db_session.add(
        StreamStatePoint(
            stream_id=source.stream_id,
            state_label="NORMAL",
            case_type="NORMAL",
            temp=25.0,
            press=1.0,
            phase="L",
            mass_flow=1000.0,
            composition_json={"7732-18-5": 1.0},
            source_type="MANUAL_ENTRY",
        )
    )
    await db_session.commit()

    counts = await StreamService.reference_counts(db_session, [source.stream_id])
    assert counts[source.stream_id] == 0


async def test_reference_count_is_zero_for_unreferenced_stream(db_session, project):
    """无引用 ⇒ 0。"""
    source = await _make_stream(db_session, project)
    counts = await StreamService.reference_counts(db_session, [source.stream_id])
    assert counts.get(source.stream_id, 0) == 0


async def test_reference_counts_returns_only_requested_ids(db_session, project):
    """只统计传入的 ids（不越权统计别人的）。"""
    a = await _make_stream(db_session, project)
    b = await _make_stream(db_session, project)
    await _make_stream(db_session, project, upstream_stream_id=b.stream_id)

    counts = await StreamService.reference_counts(db_session, [a.stream_id])
    assert set(counts) == {a.stream_id}
    assert counts[a.stream_id] == 0


async def test_reference_counts_with_empty_input_returns_empty_dict(db_session):
    """⚠️ **空入参**（筛选后列表为空）⇒ 必须早返回空 dict。

    `IN ()` 在 PG 上是**语法错误** ⇒ 不早返回会让列表接口直接 500。
    """
    assert await StreamService.reference_counts(db_session, []) == {}


async def test_reference_count_accumulates_across_both_tables(db_session, project):
    """既是下游物流的源、又是闪蒸结果的源 ⇒ 计数**累加**（2 + 1 = 3）。

    不是后者覆盖前者。
    """
    source = await _make_stream(db_session, project)
    await _make_stream(db_session, project, upstream_stream_id=source.stream_id)
    await _make_stream(db_session, project, upstream_stream_id=source.stream_id)
    await _make_flash(db_session, project, source)

    counts = await StreamService.reference_counts(db_session, [source.stream_id])
    assert counts[source.stream_id] == 3


async def test_reference_counts_with_none_input_returns_empty_dict(db_session):
    """⚠️ **传 None**（类型上不该发生）⇒ 仍返回空 dict，不炸。

    签名标的是 `Sequence[uuid.UUID]`，但 `if not stream_ids` 对 None 也成立
    ⇒ 行为安全 ⇒ 用测试把它**钉住**，免得将来有人改成 `len()` 判断而炸掉。
    """
    assert await StreamService.reference_counts(db_session, None) == {}  # type: ignore[arg-type]
