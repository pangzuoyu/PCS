"""P4-0-1 calc_lineage 收口单测（fake session，无 DB）。

- finalize_calc_record 写 record_hash（16 hex）+ DataLineage 血缘
  （source→record，change_diff 含 formula_version）
- 6 位有效数字规范化：第 7 位有效数字变化 hash 不变
- RECORD_TYPE_REGISTRY 占位 4 类（裁决 #1）
"""
from __future__ import annotations

import re
import uuid

import pytest

from app.models.calc import PipingResult
from app.services.calc_lineage import (
    RECORD_TYPE_REGISTRY,
    finalize_calc_record,
)

_HASH_RE = re.compile(r"^[0-9a-f]{16}$")


class _FakeSession:
    """最小 AsyncSession 占位（仿 test_reversal_approval._FakeSession）。"""

    def __init__(self) -> None:
        self.added: list = []
        self.commits = 0

    def add(self, obj) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1


def _make_record(**overrides) -> PipingResult:
    """构造最小 PipingResult（fake session 无 DB 约束，只填 hash 相关字段）。

    pipe_id 显式给值：mapped_column(default) 在 flush 时才生效，fake session
    的 flush 是 no-op，PK 默认值不会被应用（真实 session 由 LineageTracker
    内部首笔 flush 落 PK）。
    """
    base = {
        "pipe_id": uuid.uuid4(),
        "seq_no": 1,
        "line_no": "L-001",
        "design_press": 1.2345671,
    }
    base.update(overrides)
    return PipingResult(**base)


# ============================================================================
# 1. RECORD_TYPE_REGISTRY 占位
# ============================================================================


def test_registry_contains_all_calc_record_types() -> None:
    """registry 覆盖 P4-TASK0 完整化的全部 5 类 record（P4 批 0 4 类 + TwoPhaseResult）。"""
    assert set(RECORD_TYPE_REGISTRY) == {
        "PipingResult",
        "PumpResult",
        "FlashResult",
        "PipeNetworkResult",
        "TwoPhaseResult",
    }


# ============================================================================
# 2. finalize_calc_record：record_hash + 血缘
# ============================================================================


@pytest.mark.asyncio
async def test_finalize_writes_record_hash_and_lineage() -> None:
    """record_hash 非空 16 hex；每个 source stream 一条血缘，含 formula_version。"""
    db = _FakeSession()
    rec = _make_record()
    sids = [uuid.uuid4(), uuid.uuid4()]
    await finalize_calc_record(
        db, rec, source_stream_ids=sids, formula_version="Fv1.0"
    )
    assert _HASH_RE.match(rec.record_hash), f"hash 非 16 hex: {rec.record_hash}"
    assert len(db.added) == len(sids)
    # 精确比对：每条血缘 → 对应一个 source stream + record 主键
    paired = sorted(db.added, key=lambda x: x.source_ref_id)
    expected = sorted(sids)
    for ln, sid in zip(paired, expected, strict=True):
        assert ln.record_type == "PipingResult"
        assert ln.source_ref_type == "Stream"
        assert ln.source_ref_id == sid
        assert ln.record_id == rec.pipe_id
        diff = ln.change_diff_json
        assert diff["formula_version"] == "Fv1.0"
        assert diff["record_hash"] == rec.record_hash
        assert isinstance(diff["hash"], str) and diff["hash"]
    # 事务由调用方控制：本函数不 commit
    assert db.commits == 0


@pytest.mark.asyncio
async def test_finalize_idempotent_same_hash() -> None:
    """同 record finalize 两次 → hash 相同（Finding 1 Important：幂等性）。

    第二次调用前不重置 record_hash（业务场景：重复收口/重放），hash 必须稳定。
    """
    db1 = _FakeSession()
    rec1 = _make_record()
    await finalize_calc_record(
        db1, rec1, source_stream_ids=[uuid.uuid4()], formula_version="v"
    )
    db2 = _FakeSession()
    rec2 = _make_record()
    await finalize_calc_record(
        db2, rec2, source_stream_ids=[uuid.uuid4()], formula_version="v"
    )
    # 业务重放场景：第二次 finalize 前 record_hash 已被上一次写入
    rec1.record_hash = "stale-from-prior-finalize"  # noqa: S105
    await finalize_calc_record(
        db1, rec1, source_stream_ids=[uuid.uuid4()], formula_version="v"
    )
    assert rec1.record_hash == rec2.record_hash


@pytest.mark.asyncio
async def test_hash_deterministic_same_input() -> None:
    """同输入 → hash 确定（两次独立构造）。"""
    hashes = []
    for _ in range(2):
        db = _FakeSession()
        rec = _make_record()
        await finalize_calc_record(
            db, rec, source_stream_ids=[uuid.uuid4()], formula_version="v"
        )
        hashes.append(rec.record_hash)
    assert hashes[0] == hashes[1]


@pytest.mark.asyncio
async def test_hash_stable_at_7th_significant_digit() -> None:
    """数值第 7 位有效数字变化 → 6 位规范化 → hash 不变；第 6 位变化 → hash 变。"""
    base = _make_record(design_press=1.2345671)
    db = _FakeSession()
    await finalize_calc_record(
        db, base, source_stream_ids=[uuid.uuid4()], formula_version="v"
    )

    bump7 = _make_record(design_press=1.2345679)  # 第 7 位有效数字 7→9
    db7 = _FakeSession()
    await finalize_calc_record(
        db7, bump7, source_stream_ids=[uuid.uuid4()], formula_version="v"
    )
    assert bump7.record_hash == base.record_hash

    bump6 = _make_record(design_press=1.2345771)  # 第 6 位有效数字 6→7
    db6 = _FakeSession()
    await finalize_calc_record(
        db6, bump6, source_stream_ids=[uuid.uuid4()], formula_version="v"
    )
    assert bump6.record_hash != base.record_hash

    bump1 = _make_record(design_press=2.2345671)  # 第 1 位有效数字 1→2
    db1 = _FakeSession()
    await finalize_calc_record(
        db1, bump1, source_stream_ids=[uuid.uuid4()], formula_version="v"
    )
    assert bump1.record_hash != base.record_hash
