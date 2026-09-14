"""P4-2-5：链式管道压降落库 helper + 出口物流（piping_results + outlet_stream）。

统一收口（与 P4-1-3 FLASH / P4-2-4 两相对齐）：
1. 写 piping_results 单行（P4-0-2 SUP-008 OPEN-008 已建 11 字段；本批按
   实际列名落库：line_description 写链摘要；pressure_drop_per_100m 写
   链压降梯度 (kPa/100m)；selected_diameter 写首段内径 (mm)；
   cleaning_method (JSONB) 写完整 chain input/output JSON。
2. ``finalize_calc_record`` 收口 record_hash + DataLineage
   （ADR-0031，RECORD_TYPE_REGISTRY["PipingResult"] 已注册）。
3. ``create_outlet_stream`` 复用 P4-1-3 helper（``source_type="PIPE_CALCULATED"``
   → upstream_equipment_type="PIPE"），不重写 outlet 逻辑。
4. 不 commit（事务由调用方控制 — 一个计算批次一个事务）。

design：
- piping_results 模型无 input_json / output_json（只有 cleaning_method JSONB
  列）。链 input/output 全量 JSON 入 cleaning_method（doc 已记录为 PI/PA/DG/SO
  多选，本批扩展用途：链计算完整入出参；下个 P4 批次若建新表可迁）。
- 11 P4-0-2 SUP-008 字段按链意义填（line_description 链摘要 / pressure_drop_per_100m
  链 dp/100m / selected_diameter 首段内径 mm / line_no=tag_number）；其他
  SIZING 字段（pipe_type / max_flow_factor / liquid_velocity_max 等）保持 None
  （不是链概念；本批不造数据）。
- line_no 用 inp.tag_number（项目内唯一由 RecordMixin 命名约定约束；后续
  P4-TASK0 编号服务接管时再迁）。
"""
from __future__ import annotations

import dataclasses
import uuid
from collections.abc import Mapping
from typing import Any, Final

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.calc import PipingResult
from app.models.project import Stream
from app.services.calc_lineage import finalize_calc_record
from app.services.outlet_stream import create_outlet_stream
from app.services.pipe.pipe_chain_service import (
    PipeChainInput,
    PipeChainResult,
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

# 默认 formula_version（占位标注；与 calc_method 字段独立；本表无 calc_method
# 列，formula_version 仅作 finalize_calc_record 的 change_summary 元数据）
_DEFAULT_FORMULA_VERSION: Final[str] = "DW+LM-Baker-v1.0"

# source_type（Stream.source_type 字符串列无 enum；与 P4-1-3 outlet_stream
# 约定一致）
_PIPE_SOURCE_TYPE: Final[str] = "PIPE_CALCULATED"

# calc_type（写 record_hash change_summary + outlet stream_name 后缀）
_PIPE_CHAIN_CALC_TYPE: Final[str] = "PIPE_CHAIN"

# piping_results 列名（与 calc.py PipingResult 一致；不在模型注释外的"幽灵"字段）
_COL_LINE_NO: Final[str] = "line_no"
_COL_LINE_DESCRIPTION: Final[str] = "line_description"
_COL_PRESSURE_DROP_PER_100M: Final[str] = "pressure_drop_per_100m"
_COL_SELECTED_DIAMETER: Final[str] = "selected_diameter"
_COL_CLEANING_METHOD: Final[str] = "cleaning_method"


async def persist_pipe_chain_result(
    db: AsyncSession,
    inp: PipeChainInput,
    result: PipeChainResult,
    formula_version: str = _DEFAULT_FORMULA_VERSION,
) -> tuple[PipingResult, Stream]:
    """链式管道压降结果落 piping_results + outlet_stream 统一收口。

    写入字段（按 calc.py PipingResult 实际列名）：
    - line_no = inp.tag_number
    - line_description = "PIPE_CHAIN: {N}seg dp={total_dp:.1f}Pa"
    - pressure_drop_per_100m = result.pressure_gradient_kpa_m × 100/1000
      (kPa/100m)
    - selected_diameter = 首段内径 (mm)
    - cleaning_method (JSONB) = {"_chain_calc": True, "input": asdict(inp),
      "output": asdict(result)}（链完整入出参 JSON；列原始定义 PI/PA/DG/SO
      多选，本批扩展用途）
    - line_size / material_class / fluid_code / fluid_name / fluid_phase /
      norm_oper_press / max_oper_press / norm_oper_temp / max_oper_temp /
      design_press / design_temp / pressure_test_medium / pressure_test_press
      / check_class：必填（model 不可空）— 取合理默认占位，下游 P4-TASK0
      接管时再补强

    Args:
        db: 异步 session（不 commit；提交由调用方控制 — 一个计算批次一个事务）
        inp: PipeChainInput dataclass
        result: PipeChainResult dataclass（calc_chain 输出）
        formula_version: 版本标记（占位；写 finalize_calc_record change_summary）

    Returns:
        (PipingResult, outlet Stream)：已 flush，调用方需 db.commit()

    Raises:
        OutletStreamProjectMismatchError: project_id 与源流 project_id 不一致
        StreamNotFoundError: 源流不存在（由 create_outlet_stream 内部 raise）
    """
    # 计算链摘要字段
    n_seg = len(inp.segments)
    first_seg = inp.segments[0]
    line_description = (
        f"PIPE_CHAIN: {n_seg}seg dp={result.total_dp_pa:.1f}Pa"
    )
    # 压降梯度 (kPa/m) → (kPa/100m)：× 100
    pressure_drop_per_100m = result.pressure_gradient_kpa_m * 100.0
    selected_diameter_mm = first_seg.pipe_diameter_m * 1000.0

    # cleaning_method JSONB：链完整 input/output + 元数据（UUID→str 跨环境安全）
    chain_json: dict = {
        "_chain_calc": True,
        "_tag_number": inp.tag_number,
        "input": _json_safe(inp),
        "output": _json_safe(result),
        "formula_version": formula_version,
    }

    # 必填字段占位（PipingResult 表 model 不可空；链计算不涉尺寸/材料，
    # 此处按最小有效占位填，model 校验放行；下游 P4-TASK0 接管再补强）
    placeholder_dn = (
        f"DN{int(first_seg.pipe_diameter_m * 1000.0)}"
        if first_seg.pipe_diameter_m > 0
        else "DN50"
    )

    row = PipingResult(
        seq_no=1,  # 一览表序号（占位 1；下游 P4-TASK0 接管编号服务）
        line_no=inp.tag_number,
        line_size=placeholder_dn,
        material_class="CS-STD",  # 碳钢标准（占位；下游 P4-TASK0 接管）
        fluid_code="",
        fluid_name="",
        fluid_phase=inp.segments[0].fluid_phase,
        fluid_category="NORMAL",
        toxic_class=None,
        pipe_grade=None,
        insulation_code=None,
        insulation_thickness=None,
        paint_code=None,
        tracing_type=None,
        holding_temp=None,
        source_pid="",
        line_from=inp.tag_number,
        line_to=f"{inp.tag_number}-OUT",
        norm_oper_press=inp.inlet_pressure_pa / 1.0e6,  # Pa → MPaG（近似）
        max_oper_press=inp.inlet_pressure_pa / 1.0e6,
        norm_oper_temp=(
            inp.inlet_temperature_K - 273.15
            if inp.inlet_temperature_K is not None
            else 25.0
        ),
        max_oper_temp=(
            inp.inlet_temperature_K - 273.15
            if inp.inlet_temperature_K is not None
            else 25.0
        ),
        design_press=inp.inlet_pressure_pa / 1.0e6,
        design_temp=(
            inp.inlet_temperature_K - 273.15
            if inp.inlet_temperature_K is not None
            else 25.0
        ),
        pressure_test_medium="WATER",
        pressure_test_press=inp.inlet_pressure_pa / 1.0e6 * 1.5,
        piping_category="GC3",  # 占位（链计算无 GC 类；下游 P4-TASK0 接管）
        check_class="III",
        # P4-0-2 11 字段（链意义填）
        line_description=line_description,
        pressure_drop_per_100m=pressure_drop_per_100m,
        selected_diameter=selected_diameter_mm,
        # 全量 JSON 入 cleaning_method（JSONB）
        cleaning_method=[chain_json],
    )
    # PipingResult 走 RecordMixin（带 project_id / workspace_id 必填）
    row.project_id = inp.project_id
    row.workspace_id = inp.workspace_id
    # 链计算无 record_hash 直写；finalize_calc_record 内部填充
    row.record_hash = ""

    db.add(row)
    await db.flush()  # 让 pipe_id 落库

    await finalize_calc_record(
        db,
        row,
        source_stream_ids=[inp.source_stream_id],
        formula_version=formula_version,
    )

    # outlet stream（复用 P4-1-3 helper；source_type=PIPE_CALCULATED →
    # upstream_equipment_type="PIPE"）
    outlet = await create_outlet_stream(
        db,
        source_stream_id=inp.source_stream_id,
        calc_type=_PIPE_CHAIN_CALC_TYPE,
        source_type=_PIPE_SOURCE_TYPE,
        properties={
            "total_dp_pa": result.total_dp_pa,
            "total_length_m": result.total_length_m,
            "outlet_pressure_pa": result.outlet_pressure_pa,
            "pressure_gradient_kpa_m": result.pressure_gradient_kpa_m,
            "need_two_phase": result.need_two_phase,
            "flow_pattern": result.flow_pattern,
            "_calc_type": _PIPE_CHAIN_CALC_TYPE,
            "_tag_number": inp.tag_number,
        },
        project_id=inp.project_id,
        workspace_id=inp.workspace_id,
    )

    # outlet 回填 outlet_pressure（press 字段；outlet.press = P_outlet）
    outlet.press = result.outlet_pressure_pa
    outlet.temp = (
        inp.inlet_temperature_K if inp.inlet_temperature_K is not None else outlet.temp
    )
    await db.flush()

    return row, outlet


__all__ = ["persist_pipe_chain_result"]
