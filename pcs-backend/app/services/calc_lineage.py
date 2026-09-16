"""P4-0-1 统一计算记录收口（ADR-0031）。

三件套：
- RECORD_TYPE_REGISTRY：P4 批 0 record 类型占位（正式 registry 后置 P4-TASK0）
- compute_record_hash：数值规范化 6 位有效数字后 sha256 截断 16 hex
- finalize_calc_record：计算记录唯一收口（record_hash + DataLineage 血缘）

审计列护栏：stale_resolution_path / hash_changed / changed_fields 只经本模块
（或 CIA 引擎后续批次）写，业务模块禁止直写——本批次只实现 hash 写入。
"""

from __future__ import annotations

import hashlib
import json as _json
import math
import uuid

from sqlalchemy import Float
from sqlalchemy import inspect as _inspect
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.calc import (
    ColumnSizingResult,
    FlashResult,
    HeatResult,
    MixerResult,
    PipeNetworkResult,
    PipingResult,
    PumpResult,
    ReliefResult,
    TwoPhaseResult,
)
from app.models.psv_standards import ProjectCalculationStandardProfile
from app.services.lineage import LineageTracker, _compute_hash
from app.services.lineage_extension import attach_lineage_d45

# P4-TASK0 RECORD_TYPE_REGISTRY 完整化（ADR-0031 残余）：
# P4 批 0 占位 4 类 + TwoPhaseResult（P4-2-4 新增两相结果表）。
# P5-0-1a 扩展 3 类：ReliefResult / ColumnSizingResult / MixerResult
# （SUP-008 §8.3.2/§8.3.3/§8.3.5 + P5-OPEN-005 5 类 → 8 类）。
# P5-0-5 Task 24 扩展 1 类：ProjectCalculationStandardProfile（SUP-P5-PSV-001 §3.1） → 9 类
# P5-0-2 Task 2 扩展 1 类：HeatResult（ADR-0027 V1.0 决策 2，修正 P4 遗漏）→ 10 类
# Stream 不登记（Stream 是物流不是计算记录）。
# 后续扩展：
#   P5-0-1b（4 蒸汽表）后 +4 = 14 类（Q4 约束 3 修订：原 13 → 14 因 +HeatResult）
RECORD_TYPE_REGISTRY: dict[str, type] = {
    "PipingResult": PipingResult,
    "PumpResult": PumpResult,
    "FlashResult": FlashResult,
    "PipeNetworkResult": PipeNetworkResult,
    "TwoPhaseResult": TwoPhaseResult,
    # P5-0-1a 新增（2026-09-16）
    "ReliefResult": ReliefResult,
    "ColumnSizingResult": ColumnSizingResult,
    "MixerResult": MixerResult,
    # P5-0-5 Task 24 新增（2026-09-16，SUP-P5-PSV-001 §3.1）
    "ProjectCalculationStandardProfile": ProjectCalculationStandardProfile,
    # P5-0-2 Task 2 新增（2026-09-17，ADR-0027 V1.0 决策 2，修正 P4 遗漏）
    "HeatResult": HeatResult,
}

# record_hash 截断长度（16 hex = 64 bit，与 cia_engine._CONTENT_HASH_PREFIX 一致）
_HASH_PREFIX = 16

# 数值规范化有效数字位数（mixins.record_hash 注释契约）
_SIG_DIGITS = 6

# hash 输入排除列：保证 compute_record_hash 幂等
# - record_hash：自身，重复 finalize 会随上次 hash 漂移
# - created_at / created_by / updated_at / updated_by：生命周期列，由 DB / ORM
#   副作用写入，不参与业务内容指纹
_EXCLUDED_KEYS: frozenset[str] = frozenset({
    "record_hash",
    "created_at",
    "created_by",
    "updated_at",
    "updated_by",
})


def _round_sig(value: float) -> float:
    """浮点 → 6 位有效数字（%g 四舍五入语义；0 / 非有限值原样返回）。"""
    if value == 0 or not math.isfinite(value):
        return value
    return float(f"{value:.{_SIG_DIGITS}g}")


def compute_record_hash(record) -> str:
    """record 数值规范化哈希：Float 列 round 到 6 位有效数字后序列化，
    sha256 截断 16 hex。

    幂等：排除 record_hash 自身与生命周期列（created_at/created_by/updated_at
    /updated_by），同 record 重复调用结果一致——CIA hash_changed 语义依赖此
    性质（CIA 引擎后续批次复用）。

    读取顺序：state.dict → committed_state（与 lineage._compute_hash 同约束：
    禁止 getattr fallback，防 expire 后 async lazy-load 抛 MissingGreenlet）。
    """
    state = _inspect(record)
    committed = state.committed_state or {}
    payload: dict = {}
    for col in record.__table__.columns:
        if col.primary_key:
            continue
        if col.key in _EXCLUDED_KEYS:
            continue
        v = state.dict.get(col.key)
        if v is None:
            v = committed.get(col.key)
        if v is not None and isinstance(col.type, Float):
            v = _round_sig(v)
        payload[col.key] = v
    raw = _json.dumps(payload, default=str, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:_HASH_PREFIX]


async def finalize_calc_record(
    db: AsyncSession,
    record,
    *,
    source_stream_ids: list[uuid.UUID],
    formula_version: str,
) -> None:
    """计算记录统一收口（P4 批 0 唯一入口，ADR-0031）。

    做三件事：
    1. record.record_hash = compute_record_hash(record)
       （Float 列 6 位有效数字规范化 → sha256 截断 16 hex）；
    2. DataLineage 血缘：每个 source stream → record 一条（source="CALC"，
       source_ref_type="Stream"，change_diff 含 formula_version / record_hash /
       hash——hash 为全量列哈希，保持 CIA 扫描比对基准兼容）；
    3. 审计列（stale_resolution_path / hash_changed / changed_fields）只经本
       函数与 CIA 引擎写；本批次仅提供列，hash_changed / changed_fields 由
       CIA 引擎后续批次使用。

    事务：本函数 **不 commit**（flush 由 LineageTracker 内部完成），
    提交由调用方控制——一个计算批次一个事务。
    """
    tracker = LineageTracker(db)
    record.record_hash = compute_record_hash(record)
    for sid in source_stream_ids:
        entry = await tracker.track(
            record=record,
            source="CALC",
            change_summary=f"calc finalize (formula_version={formula_version})",
            change_diff={
                "hash": _compute_hash(record),
                "record_hash": record.record_hash,
                "formula_version": formula_version,
            },
            source_ref_type="Stream",
            source_ref_id=sid,
        )
        # P4-TASK0 D4/D5 扩展（ADR-0031 残余）：DataLineage 4 列增量写入。
        # 既有契约（hash + 血缘结构）不变；仅在 track 后追加元数据。
        attach_lineage_d45(entry, record=record, formula_version=formula_version)


__all__ = [
    "RECORD_TYPE_REGISTRY",
    "compute_record_hash",
    "finalize_calc_record",
]
