"""P3.x SIM-23: DataLineage 反向查询（spec §2 引用追踪 + E-3）。

query: 给定 record_type + record_id，列出所有 source_ref_type=record_type
       AND source_ref_id=record_id 的 lineage 行（"谁引用了我"）。

output shape:
    {
        reference_count: int,
        references: list[dict] (each: lineage_id/source/source_ref_type/
                                source_ref_id/actor_user_id/occurred_at),
        in_use: bool (= reference_count > 0)
    }

与 LineageTracker.downstream 区别：
- downstream：沿 parent_lineage_id 链查子节点（递归）
- SIM-23：直接 source_ref 匹配（无递归，扁平）
"""
from __future__ import annotations

import uuid

import pytest

from app.models.system import DataLineage
from app.services.data_lineage_query import DataLineageQueryService


@pytest.mark.asyncio
async def test_find_references_empty(db_session):
    """无引用 → reference_count=0, in_use=False, references=[]。"""
    svc = DataLineageQueryService(db_session)
    result = await svc.find_references(
        record_type="PIPE_CLASS", record_id=uuid.uuid4()
    )
    assert result["reference_count"] == 0
    assert result["in_use"] is False
    assert result["references"] == []


@pytest.mark.asyncio
async def test_find_references_single(db_session):
    """1 条引用 → reference_count=1, in_use=True, 1 项 references。"""
    target_id = uuid.uuid4()
    entry = DataLineage(
        record_type="PIPING_RESULT",
        record_id=uuid.uuid4(),
        source="IMPORT",
        source_ref_type="PIPE_CLASS",
        source_ref_id=target_id,
    )
    db_session.add(entry)
    await db_session.commit()

    svc = DataLineageQueryService(db_session)
    result = await svc.find_references(
        record_type="PIPE_CLASS", record_id=target_id
    )
    assert result["reference_count"] == 1
    assert result["in_use"] is True
    assert len(result["references"]) == 1
    ref = result["references"][0]
    assert ref["lineage_id"] == entry.lineage_id
    assert ref["source"] == "IMPORT"
    assert ref["source_ref_type"] == "PIPE_CLASS"
    assert ref["source_ref_id"] == target_id


@pytest.mark.asyncio
async def test_find_references_multiple(db_session):
    """多条引用 → 全部列出，按 occurred_at 倒序。"""
    target_id = uuid.uuid4()
    entries: list[DataLineage] = []
    for _ in range(3):
        e = DataLineage(
            record_type="PIPING_RESULT",
            record_id=uuid.uuid4(),
            source="USER",
            source_ref_type="PIPE_CLASS",
            source_ref_id=target_id,
        )
        db_session.add(e)
        entries.append(e)
    await db_session.commit()

    svc = DataLineageQueryService(db_session)
    result = await svc.find_references(
        record_type="PIPE_CLASS", record_id=target_id
    )
    assert result["reference_count"] == 3
    assert result["in_use"] is True
    assert len(result["references"]) == 3
    returned_ids = {r["lineage_id"] for r in result["references"]}
    assert returned_ids == {e.lineage_id for e in entries}


@pytest.mark.asyncio
async def test_find_references_filters_by_record_type(db_session):
    """不同 record_type 不互相命中。"""
    pc_id = uuid.uuid4()
    e1 = DataLineage(
        record_type="PIPING_RESULT",
        record_id=uuid.uuid4(),
        source="USER",
        source_ref_type="PIPE_CLASS",
        source_ref_id=pc_id,
    )
    e2 = DataLineage(
        record_type="OTHER",
        record_id=uuid.uuid4(),
        source="USER",
        source_ref_type="STREAM",
        source_ref_id=pc_id,
    )
    db_session.add_all([e1, e2])
    await db_session.commit()

    svc = DataLineageQueryService(db_session)
    # 查 PIPE_CLASS 应只命中 e1
    result = await svc.find_references(
        record_type="PIPE_CLASS", record_id=pc_id
    )
    assert result["reference_count"] == 1
    assert result["in_use"] is True
    assert result["references"][0]["source_ref_type"] == "PIPE_CLASS"


@pytest.mark.asyncio
async def test_find_references_in_use_boundary(db_session):
    """reference_count 边界：1 即 in_use=True。"""
    target_id = uuid.uuid4()
    svc = DataLineageQueryService(db_session)
    # 空时
    empty = await svc.find_references(
        record_type="PIPE_CLASS", record_id=target_id
    )
    assert empty["in_use"] is False
    # 添加 1 条
    db_session.add(
        DataLineage(
            record_type="PIPING_RESULT",
            record_id=uuid.uuid4(),
            source="USER",
            source_ref_type="PIPE_CLASS",
            source_ref_id=target_id,
        )
    )
    await db_session.commit()
    one = await svc.find_references(
        record_type="PIPE_CLASS", record_id=target_id
    )
    assert one["in_use"] is True


@pytest.mark.asyncio
async def test_find_references_includes_actor(db_session):
    """references 项含 actor_user_id + occurred_at 字段。"""
    target_id = uuid.uuid4()
    user_id = uuid.uuid4()
    e = DataLineage(
        record_type="PIPING_RESULT",
        record_id=uuid.uuid4(),
        source="USER",
        source_ref_type="PIPE_CLASS",
        source_ref_id=target_id,
        actor_user_id=user_id,
    )
    db_session.add(e)
    await db_session.commit()

    svc = DataLineageQueryService(db_session)
    result = await svc.find_references(
        record_type="PIPE_CLASS", record_id=target_id
    )
    ref = result["references"][0]
    assert ref["actor_user_id"] == user_id
    assert ref["occurred_at"] is not None  # server_default func.now()