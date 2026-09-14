"""P4-2-4：两相压降落库 helper（two_phase_results 表）。

只写入 P4-0-2 已落的 two_phase_results 13 字段（PK + input/output JSONB + 业务 + 时间戳）。

不写 record_hash / DataLineage：
- TwoPhaseResult 模型无 record_hash 列（模型注释明确：bit_number / record_hash /
  审批等门禁由 P4-TASK0 批次按需扩展；当前仅"纯计算结果落库"）。
- finalize_calc_record 调用 RECORD_TYPE_REGISTRY，TwoPhaseResult 未注册；
  本批不引入新注册，避免破坏 P4-0-2 既有契约。

PG enum 字符串直接传：SQLAlchemy native_enum 接受 enum 值或 enum 实例（按字符串名匹配）；
本批选择直接传 result.flow_pattern / two_phase_check 字符串（P4-0-2 模型注释明确）。

formula_version：占位标注（LGB-Baker-v1.0）；当前 calc_method 字段存放 LOCKHART_MARTINELLI_BAKER，
formula_version 仅作为版本标记便于后续演进；不写回行（不污染模型字段）。
"""
from __future__ import annotations

import dataclasses
from datetime import UTC, datetime
from typing import Final

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.calc import TwoPhaseResult as TwoPhaseResultRow
from app.services.pipe.two_phase_service import TwoPhaseInput, TwoPhaseResult

# 默认 formula_version（占位标注；与 calc_method 字段独立）
_DEFAULT_FORMULA_VERSION: Final[str] = "LM-Baker-v1.0"


async def persist_two_phase_result(
    db: AsyncSession,
    inp: TwoPhaseInput,
    result: TwoPhaseResult,
    formula_version: str = _DEFAULT_FORMULA_VERSION,
) -> TwoPhaseResultRow:
    """两相压降结果落 two_phase_results 表。

    字段对齐 P4-0-2（13 字段全写入）：
    - input_json: dataclass asdict(inp)
    - output_json: dataclass asdict(result)
    - Bx / By Float
    - flow_pattern / two_phase_check：PG enum（字符串直接传）
    - liquid_velocity / gas_velocity / pressure_gradient / void_fraction Float
    - calc_method String(50)
    - created_at DateTime（UTC now）

    Args:
        db: 异步 session（不 commit；提交由调用方控制 — 一个计算批次一个事务）
        inp: TwoPhaseInput dataclass
        result: TwoPhaseResult dataclass（calc_two_phase 输出）
        formula_version: 版本标记（占位；当前不写回行）

    Returns:
        TwoPhaseResultRow ORM 行（含 PK）；已 flush 但未 commit
    """
    row = TwoPhaseResultRow(
        input_json=dataclasses.asdict(inp),
        output_json=dataclasses.asdict(result),
        Bx=result.Bx,
        By=result.By,
        flow_pattern=result.flow_pattern,  # PG enum string
        two_phase_check=result.two_phase_check,  # PG enum string
        liquid_velocity=result.liquid_velocity,
        gas_velocity=result.gas_velocity,
        pressure_gradient=result.pressure_gradient,
        void_fraction=result.void_fraction,
        calc_method=result.calc_method,
        created_at=datetime.now(UTC),
    )
    db.add(row)
    await db.flush()
    return row


__all__ = ["persist_two_phase_result"]
