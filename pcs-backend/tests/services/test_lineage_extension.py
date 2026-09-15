"""P4-TASK0 lineage D4/D5 扩展单测（fake session）。

D4/D5 = record_hash_at_track / source_record_hash / formula_version_at_track
/config_version 四个新 DataLineage 列的写入路径。
"""
from __future__ import annotations

import uuid

import pytest

from app.models.calc import PipingResult, TwoPhaseResult
from app.services.calc_lineage import (
    RECORD_TYPE_REGISTRY,
    compute_record_hash,
    finalize_calc_record,
)
from app.services.lineage_extension import attach_lineage_d45


class _FakeSession:
    def __init__(self) -> None:
        self.added: list = []

    def add(self, obj) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        return None


def _make_two_phase(**overrides) -> TwoPhaseResult:
    base = {
        "two_phase_calc_id": uuid.uuid4(),
        "input_json": {"d": 0.1, "rho_l": 800.0},
        "output_json": {"dp": 1.5},
        "Bx": 0.5,
        "By": 0.3,
        "liquid_velocity": 1.2,
        "gas_velocity": 5.0,
        "pressure_gradient": 0.8,
        "void_fraction": 0.4,
        "calc_method": "LOCKHART_MARTINELLI_BAKER",
    }
    base.update(overrides)
    return TwoPhaseResult(**base)


def test_two_phase_in_registry() -> None:
    """RECORD_TYPE_REGISTRY 含 TwoPhaseResult（P4-TASK0 完整化）。"""
    assert "TwoPhaseResult" in RECORD_TYPE_REGISTRY
    assert RECORD_TYPE_REGISTRY["TwoPhaseResult"] is TwoPhaseResult


def test_two_phase_record_hash_writable() -> None:
    """TwoPhaseResult 补 record_hash 列后 compute_record_hash 可写。"""
    rec = _make_two_phase()
    h = compute_record_hash(rec)
    assert isinstance(h, str) and len(h) == 16


@pytest.mark.asyncio
async def test_finalize_two_phase_populates_d45_fields() -> None:
    """finalize_calc_record 对 TwoPhaseResult 走同一收口：每条 DataLineage
    都被 attach_lineage_d45 注入 record_hash_at_track /
    source_record_hash / formula_version_at_track / config_version。"""
    db = _FakeSession()
    rec = _make_two_phase()
    sids = [uuid.uuid4()]
    await finalize_calc_record(
        db, rec, source_stream_ids=sids, formula_version="LM-Baker-v1.0"
    )
    assert len(db.added) == 1
    ln = db.added[0]
    # D4/D5 字段由 attach_lineage_d45 写入
    assert ln.record_hash_at_track == rec.record_hash
    assert ln.formula_version_at_track == "LM-Baker-v1.0"
    # source_record_hash：本次 finalize 无上游 → 退化为本 record hash
    assert ln.source_record_hash == rec.record_hash
    assert ln.config_version is None  # 未传 config_version 时为 None


@pytest.mark.asyncio
async def test_attach_d45_explicit_overrides() -> None:
    """attach_lineage_d45 显式传 config_version / source_record_hash 时生效。"""
    db = _FakeSession()
    rec = _make_two_phase()
    sids = [uuid.uuid4()]
    await finalize_calc_record(
        db, rec, source_stream_ids=sids, formula_version="v1"
    )
    ln = db.added[0]
    upstream_hash = "deadbeefcafebabe"[:16]
    attach_lineage_d45(
        ln,
        record=rec,
        formula_version="v1",
        source_record_hash=upstream_hash,
        config_version="cfg-42",
    )
    assert ln.source_record_hash == upstream_hash
    assert ln.config_version == "cfg-42"
    assert ln.record_hash_at_track == rec.record_hash


def test_d45_helpers_piping_backfill() -> None:
    """PipingResult 既有路径也走 D4/D5（已有 record_hash，零回归）。"""
    rec = PipingResult(
        pipe_id=uuid.uuid4(),
        seq_no=1,
        line_no="L-001",
        design_press=1.2345671,
    )
    h = compute_record_hash(rec)
    assert isinstance(h, str) and len(h) == 16
