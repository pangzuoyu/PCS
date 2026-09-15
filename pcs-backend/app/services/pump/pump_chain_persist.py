"""P4-4-4：PUMP 链结果落 pump_results + outlet_stream 统一收口。

设计要点（与 P4-2-5 pipe_chain_persist 对齐）：
1. 写 pump_results 单行：input_json / output_json 写链完整入出参
   （P4-0-2 SUP-008 既有 JSONB 列：basic_info_json / fluid_properties_json /
   power_consumption_json / differential_pressure_json / suction_calculation_json
   按链语义填；vendor_model / selected_pump_model / actual_head / actual_efficiency
   / actual_motor_power / actual_npshr / pump_operation 按运行点填）。
2. ``finalize_calc_record`` 收口 record_hash + DataLineage
   （ADR-0031，RECORD_TYPE_REGISTRY["PumpResult"] 已注册）。
3. ``create_outlet_stream`` 复用 P4-1-3 helper（source_type="PUMP_CALCULATED"
   → upstream_equipment_type="PUMP"）；不重写 outlet 逻辑。
4. 不 commit（事务由调用方控制 — 一个计算批次一个事务）。

约束：
- PumpResult 继承 TaggedRecordMixin（tag_number NOT NULL）
- input_json / output_json 由 P4-4-4 增量加列（nullable，缺列时为 None）
"""
from __future__ import annotations

import dataclasses
import uuid
from collections.abc import Mapping
from typing import Any, Final

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.calc import PumpResult
from app.models.enums import PumpOperation
from app.models.project import Stream
from app.services.calc_lineage import finalize_calc_record
from app.services.outlet_stream import create_outlet_stream
from app.services.pump.pump_chain_service import (
    PumpChainInput,
    PumpChainResult,
)


def _json_safe(obj: Any) -> Any:
    """递归把 dataclass / UUID 容器转 JSON 安全的 dict / list / str / 标量。

    - UUID → str
    - dataclass → asdict（已嵌套处理）
    - list/tuple → list
    - dict → dict
    - 其他 → 原样

    PostgreSQL JSONB 原生接受 UUID（psycopg 适配），但 in-memory SQLite 测试
    fixture JSONB shim 不接受 UUID 对象；为跨环境一致，强制转 str。
    """
    if isinstance(obj, uuid.UUID):
        return str(obj)
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return _json_safe(dataclasses.asdict(obj))
    if isinstance(obj, Mapping):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    return obj


_DEFAULT_FORMULA_VERSION: Final[str] = "PUMP-chain-v1.0"
_PUMP_SOURCE_TYPE: Final[str] = "PUMP_CALCULATED"
_PUMP_CHAIN_CALC_TYPE: Final[str] = "PUMP_CHAIN"


async def persist_pump_chain_result(
    db: AsyncSession,
    inp: PumpChainInput,
    result: PumpChainResult,
    formula_version: str = _DEFAULT_FORMULA_VERSION,
) -> tuple[PumpResult, Stream]:
    """PUMP 链结果落 pump_results + outlet_stream 统一收口。

    写入字段（按 calc.py PumpResult 实际列名）：
    - tag_number = inp.tag_number（TaggedRecordMixin 强制 NOT NULL）
    - basic_info_json = {"_chain_calc": True, "tag_number": ..., "calc_type":
      "PUMP_CHAIN", "input": asdict(inp), "formula_version": ...}（链摘要 +
      入参 JSON）
    - output_json = {"selection": asdict(selection), "npsha": asdict(npsha),
      "operating_point": asdict(operating_point), "margin_m": ..., "margin_pct":
      ..., "deviation_from_rated_pct": ..., "overall_confidence": ...,
      "overall_check_result": ..., "overall_check_result_reason": ...}
    - fluid_properties_json = {"density_kg_m3": ..., "viscosity_pa_s": ...,
      "vapor_pressure_pa": ..., "system_pressure_pa": ...}
    - flow_rates_json = {"flow_m3_s": ..., "head_m": ..., "speed_rpm": ...}
    - suction_calculation_json = asdict(npsha)（吸入侧全部）
    - discharge_calculation_json = {"_discharge_pipe_chain_used": True/False}
    - differential_pressure_json = {"operating_head_m": ..., "rated_head_m": ...}
    - design_pressure_json = {"system_pressure_pa": ..., "vapor_pressure_pa":
      ...}
    - power_consumption_json = {"estimated_power_kw": ...,
      "estimated_efficiency": ..., "operating_efficiency": ...,
      "selected_motor_power_kw": ...}
    - selected_pump_model = "{api610_type} ns={ns:.0f}"（占位厂商型号）
    - selected_motor_power = estimated_power_kw
    - pump_operation = CONTINUOUS（占位）
    - vendor_model = curve.pump_tag（厂家给定）
    - actual_head / actual_efficiency / actual_motor_power / actual_npshr：按
      链结果填
    - record_hash 由 finalize_calc_record 填

    Args:
        db: 异步 session（不 commit）
        inp: PumpChainInput dataclass
        result: PumpChainResult dataclass（calc_pump_chain 输出）
        formula_version: 版本标记（写入 finalize_calc_record change_summary）

    Returns:
        (PumpResult, outlet Stream)：已 flush，调用方需 db.commit()
    """
    chain_json = {
        "_chain_calc": True,
        "_calc_type": _PUMP_CHAIN_CALC_TYPE,
        "_tag_number": inp.tag_number,
        "input": _json_safe(inp),
        "formula_version": formula_version,
    }
    output_json = {
        "selection": _json_safe(result.selection),
        "npsha": _json_safe(result.npsha),
        "operating_point": _json_safe(result.operating_point),
        "margin_m": result.margin_m,
        "margin_pct": result.margin_pct,
        "deviation_from_rated_pct": result.deviation_from_rated_pct,
        "overall_confidence": result.overall_confidence,
        "overall_check_result": result.overall_check_result,
        "overall_check_result_reason": result.overall_check_result_reason,
        "formula_version": formula_version,
    }

    row = PumpResult(
        tag_number=inp.tag_number,
        # P4-4-4 增量：链完整入出参 JSON
        input_json=chain_json,
        output_json=output_json,
        # 链语义填既有 JSONB 列
        basic_info_json={
            "calc_type": _PUMP_CHAIN_CALC_TYPE,
            "tag_number": inp.tag_number,
            "formula_version": formula_version,
        },
        fluid_properties_json={
            "density_kg_m3": inp.fluid_density_kg_m3,
            "viscosity_pa_s": inp.fluid_viscosity_pa_s,
            "vapor_pressure_pa": inp.vapor_pressure_pa,
            "system_pressure_pa": inp.system_pressure_pa,
        },
        flow_rates_json={
            "flow_m3_s": inp.flow_m3_s,
            "head_m": inp.head_m,
            "speed_rpm": inp.speed_rpm,
        },
        suction_calculation_json=_json_safe(result.npsha),
        discharge_calculation_json={
            "_discharge_pipe_chain_used": inp.discharge_pipe_chain is not None,
        },
        differential_pressure_json={
            "operating_head_m": result.operating_point.head_m,
            "rated_head_m": inp.pump_curve.rated_head_m,
            "operating_flow_m3_s": result.operating_point.flow_m3_s,
            "rated_flow_m3_s": inp.pump_curve.rated_flow_m3_s,
        },
        design_pressure_json={
            "system_pressure_pa": inp.system_pressure_pa,
            "vapor_pressure_pa": inp.vapor_pressure_pa,
        },
        power_consumption_json={
            "estimated_power_kw": result.selection.estimated_power_kw,
            "estimated_efficiency": result.selection.estimated_efficiency,
            "operating_efficiency": result.operating_point.efficiency,
            "selected_motor_power_kw": result.selection.estimated_power_kw,
        },
        # 选型字段
        selected_pump_model=(
            f"{result.selection.api610_type} ns={result.selection.specific_speed_ns:.0f}"
        ),
        selected_motor_power=result.selection.estimated_power_kw,
        pump_operation=PumpOperation.NORMAL,
        # 实际工况
        actual_head=result.operating_point.head_m,
        actual_efficiency=result.operating_point.efficiency,
        actual_motor_power=result.selection.estimated_power_kw,
        actual_npshr=result.operating_point.npshr_m,
        vendor_model=inp.pump_curve.pump_tag,
    )
    # PumpResult 走 TaggedRecordMixin（带 project_id / workspace_id 必填）
    row.project_id = inp.project_id
    row.workspace_id = inp.workspace_id
    # 链计算无 record_hash 直写；finalize_calc_record 内部填充
    row.record_hash = ""

    db.add(row)
    await db.flush()  # 让 pump_id 落库

    await finalize_calc_record(
        db,
        row,
        source_stream_ids=[inp.source_stream_id],
        formula_version=formula_version,
    )

    # outlet stream（复用 P4-1-3 helper；source_type=PUMP_CALCULATED →
    # upstream_equipment_type="PUMP"）
    outlet = await create_outlet_stream(
        db,
        source_stream_id=inp.source_stream_id,
        calc_type=_PUMP_CHAIN_CALC_TYPE,
        source_type=_PUMP_SOURCE_TYPE,
        properties={
            "tag_number": inp.tag_number,
            "flow_m3_s": inp.flow_m3_s,
            "head_m": inp.head_m,
            "operating_head_m": result.operating_point.head_m,
            "operating_efficiency": result.operating_point.efficiency,
            "estimated_power_kw": result.selection.estimated_power_kw,
            "pump_type": result.selection.pump_type,
            "api610_type": result.selection.api610_type,
            "npsha_m": result.npsha.npsha_m,
            "npshr_m": result.operating_point.npshr_m,
            "margin_m": result.margin_m,
            "margin_pct": result.margin_pct,
            "overall_check_result": result.overall_check_result,
            "overall_confidence": result.overall_confidence,
            "_calc_type": _PUMP_CHAIN_CALC_TYPE,
        },
        project_id=inp.project_id,
        workspace_id=inp.workspace_id,
    )

    await db.flush()
    return row, outlet


__all__ = ["persist_pump_chain_result"]
