"""P5-1-4 vessel 计算落库 + outlet 流（service 层）。

设计要点（ADR-0032 V1.1 决策 6 + P5-1-4 plan §180-197）：
1. check_calc_inputs 三步守卫：DRAFT → 403 / 不可靠 → 422 / 不存在 → 404
2. 读源流（vessel 计算输入是物理量；源流提供 project_id/workspace_id + 可选物性）
3. 调 calc_vessel_sizing + calc_vessel_hydraulics 两次计算
4. 构造 VesselResult（input_json + output_json）+ 落库
5. finalize_calc_record（record_hash + lineage）
6. create_outlet_stream(source_type="VESSEL_CALCULATED")，properties 承载
   vessel 几何 + 物性
7. commit + 返回 vessel_id + record_hash + outlet_stream_id

P6-4 T2 扩展（C-08 V1.2 重写）：
- 可选 sizing_spec_input → 调 calc_two_phase_separator_sizing
- 落库时填充 vessel_results 6 列 sizing（vmax_m_s / csa_min_m2 /
  csa_actual_m2 / nozzle_min_id_m / control_height_m / residence_time_s）
- sizing_spec_input=None 时保持 V1.0 兼容（6 列 nullable 全部 NULL）

input_json 双轨（ADR-0032 V1.1 决策 6）+ P6-4 T2 三轨：
  - sizing_input: VesselSizingInput dict（vessel_type + 物性 + 流量 + K 因子）
  - hydraulics_input: VesselHydraulicsInput dict（容器几何 + 进出料）
  - sizing_spec_input: TwoPhaseSeparatorSizingInput dict（C-08 两相 sizing）

output_json 合并结果 + P6-4 T2：
  - sizing: VesselSizingResult dict（V_max / D_min / liquid_volume / check / confidence）
  - hydraulics: VesselHydraulicsResult dict
    （empty_time / overflow_ok / level_volume_curve_json / vent_capacity_m3_s）
  - sizing_spec: TwoPhaseSeparatorSizingResult dict（C-08 V1.2 5 段计算输出）

不做：
- 不写 vessel_results 之外的派生表
- 不并发锁（与 flash_persist 一致；batch 入口由 StateMachineService 兜底）
"""
from __future__ import annotations

import dataclasses
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.calc import VesselResult
from app.models.project import Stream
from app.services.calc_entry import check_calc_inputs
from app.services.calc_lineage import finalize_calc_record
from app.services.outlet_stream import create_outlet_stream
from app.services.vessel.two_phase_separator_sizing_service import (
    TwoPhaseSeparatorSizingInput,
    TwoPhaseSeparatorSizingResult,
    calc_two_phase_separator_sizing,
)
from app.services.vessel.vessel_service import (
    VesselHydraulicsInput,
    VesselHydraulicsResult,
    VesselSizingInput,
    VesselSizingResult,
    calc_vessel_hydraulics,
    calc_vessel_sizing,
)

# P5-1-4 formula_version：固定锚点（CIA 引擎版本对齐时一并 bump）
_FORMULA_VERSION = "Vv1.0-p5-1-4"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _generate_tag_number(project_id: uuid.UUID) -> str:
    """生成项目内唯一 VesselResult tag_number（TaggedRecordMixin NOT NULL 兜底）。

    格式：``VESSEL-{short_uuid}``（短码 8 位 hex；项目内由 DB unique 约束兜底）。
    P5-TASK0 批次替换为 NumberingService 编号（届时本函数删除）。
    """
    return f"VESSEL-{uuid.uuid4().hex[:8].upper()}"


def _dataclass_to_dict(dc: Any) -> dict:
    """frozen dataclass → dict（用于 input_json / output_json 序列化）。

    dataclasses.asdict 即可，无需自定义 JSON encoder。
    """
    return dataclasses.asdict(dc)


# ---------------------------------------------------------------------------
# Core entry
# ---------------------------------------------------------------------------


async def persist_vessel_calculate(
    db: AsyncSession,
    *,
    source_stream_id: uuid.UUID,
    sizing_input: VesselSizingInput,
    hydraulics_input: VesselHydraulicsInput,
    sizing_spec_input: TwoPhaseSeparatorSizingInput | None = None,
    actor: uuid.UUID | None = None,
) -> dict[str, Any]:
    """vessel 计算落库：sizing + hydraulics + 可选 sizing_spec（C-08 V1.2）。

    Args:
        db: async session
        source_stream_id: 源流 UUID（提供 project_id/workspace_id + 三步守卫）
        sizing_input: VesselSizingInput dataclass
        hydraulics_input: VesselHydraulicsInput dataclass
        sizing_spec_input: P6-4 T2 TwoPhaseSeparatorSizingInput（None = V1.0 兼容）

    Returns:
        {
            "calc_id": VesselResult.vessel_id,
            "record_hash": 16 hex,
            "stream_id": source_stream_id,
            "result": {
                "sizing": dict,
                "hydraulics": dict,
                "sizing_spec": dict | None,
            },
            "outlet_stream_id": outlet.stream_id,
            "outlet_stream_name": outlet.stream_name,
        }

    Raises:
        PcsError: 三步守卫失败 / 源流不存在 / 输入非法（vessel_service 内部）
    """
    # 1. 三步守卫（源流 CHECKED 状态）
    await check_calc_inputs(db, [source_stream_id])

    # 2. 读源流（vessel 输入是物理量；源流提供 project_id/workspace_id）
    stream = await db.get(Stream, source_stream_id)
    if stream is None:
        from app.services.exceptions import PcsError

        raise PcsError(
            f"Stream {source_stream_id} 不存在",
            code="SIM_STREAM_NOT_FOUND",
            status=404,
        )

    # 3. 调 P5-1-1/2 两次计算（纯函数，frozen dataclass → dataclass）
    sizing_result: VesselSizingResult = calc_vessel_sizing(sizing_input)
    hydraulics_result: VesselHydraulicsResult = calc_vessel_hydraulics(hydraulics_input)

    # 3b. P6-4 T2 可选 sizing_spec → C-08 V1.2 两相 sizing（5 段）
    sizing_spec_result: TwoPhaseSeparatorSizingResult | None = None
    if sizing_spec_input is not None:
        sizing_spec_result = calc_two_phase_separator_sizing(sizing_spec_input)

    # 4. 构造 VesselResult ORM（input_json + output_json 三轨；6 列 nullable）
    input_json: dict[str, Any] = {
        "sizing": _dataclass_to_dict(sizing_input),
        "hydraulics": _dataclass_to_dict(hydraulics_input),
    }
    output_json: dict[str, Any] = {
        "sizing": _dataclass_to_dict(sizing_result),
        "hydraulics": _dataclass_to_dict(hydraulics_result),
    }
    record_kwargs: dict[str, Any] = {
        "tag_number": _generate_tag_number(stream.project_id),
        "project_id": stream.project_id,
        "workspace_id": stream.workspace_id,
        "input_json": input_json,
        "output_json": output_json,
    }
    if sizing_spec_input is not None:
        input_json["sizing_spec"] = _dataclass_to_dict(sizing_spec_input)
        output_json["sizing_spec"] = _dataclass_to_dict(sizing_spec_result)
        # P6-4 T2 填充 6 列 sizing
        record_kwargs.update(
            vmax_m_s=sizing_spec_result.vmax_m_s,
            csa_min_m2=sizing_spec_result.csa_min_m2,
            csa_actual_m2=sizing_spec_result.csa_actual_m2,
            nozzle_min_id_m=sizing_spec_result.nozzle_inlet_min_id_m,
            control_height_m=sizing_spec_result.control_height_m,
            residence_time_s=sizing_spec_result.residence_time_s,
        )
    record = VesselResult(**record_kwargs)
    db.add(record)
    await db.flush()  # 让 vessel_id 落库（finalize 内 LineageTracker 需要 PK）

    # 5. finalize_calc_record（record_hash + lineage）
    await finalize_calc_record(
        db,
        record,
        source_stream_ids=[source_stream_id],
        formula_version=_FORMULA_VERSION,
    )

    # 6. 出口物流（source_type=VESSEL_CALCULATED）
    outlet_properties: dict[str, Any] = {
        # vessel 几何 + 物性摘要（供下游 PIPE / PUMP 引用）
        "_calc_type": "VESSEL",
        "vessel_type": sizing_result.vessel_type,
        "K_factor_ms": sizing_result.K_factor_ms,
        "V_max_ms": sizing_result.V_max_ms,
        "D_min_m": sizing_result.D_min_m,
        "liquid_volume_m3": sizing_result.liquid_volume_m3,
        "empty_time_s": hydraulics_result.empty_time_s,
        "overflow_ok": hydraulics_result.overflow_ok,
        "vent_capacity_m3_s": hydraulics_result.vent_capacity_m3_s,
        "applicable_orientation": hydraulics_result.applicable_orientation,
    }
    if sizing_spec_result is not None:
        # P6-4 T2 C-08 sizing 摘要（供下游 / 调试追溯）
        outlet_properties["c08_vmax_m_s"] = sizing_spec_result.vmax_m_s
        outlet_properties["c08_csa_min_m2"] = sizing_spec_result.csa_min_m2
        outlet_properties["c08_csa_actual_m2"] = sizing_spec_result.csa_actual_m2
        outlet_properties["c08_nozzle_inlet_id_m"] = (
            sizing_spec_result.nozzle_inlet_min_id_m
        )
        outlet_properties["c08_control_height_m"] = sizing_spec_result.control_height_m
        outlet_properties["c08_residence_time_s"] = sizing_spec_result.residence_time_s
    outlet = await create_outlet_stream(
        db,
        source_stream_id=source_stream_id,
        calc_type="VESSEL",
        source_type="VESSEL_CALCULATED",
        properties=outlet_properties,
        project_id=stream.project_id,
        workspace_id=stream.workspace_id,
    )
    await db.flush()

    # 7. commit
    await db.commit()

    return {
        "calc_id": record.vessel_id,
        "calc_type": "VESSEL",
        "record_hash": record.record_hash,
        "stream_id": source_stream_id,
        "result": {
            "sizing": _dataclass_to_dict(sizing_result),
            "hydraulics": _dataclass_to_dict(hydraulics_result),
            "sizing_spec": (
                _dataclass_to_dict(sizing_spec_result)
                if sizing_spec_result is not None
                else None
            ),
        },
        "outlet_stream_id": outlet.stream_id,
        "outlet_stream_name": outlet.stream_name,
    }


__all__ = ["persist_vessel_calculate"]
