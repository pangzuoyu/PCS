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

input_json 双轨（ADR-0032 V1.1 决策 6）：
  - sizing_input: VesselSizingInput dict（vessel_type + 物性 + 流量 + K 因子）
  - hydraulics_input: VesselHydraulicsInput dict（容器几何 + 进出料）

output_json 合并结果：
  - sizing: VesselSizingResult dict（V_max / D_min / liquid_volume / check / confidence）
  - hydraulics: VesselHydraulicsResult dict
    （empty_time / overflow_ok / level_volume_curve_json / vent_capacity_m3_s）

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
    actor: uuid.UUID | None = None,
) -> dict[str, Any]:
    """vessel 计算落库：sizing + hydraulics 一次调用。

    Args:
        db: async session
        source_stream_id: 源流 UUID（提供 project_id/workspace_id + 三步守卫）
        sizing_input: VesselSizingInput dataclass
        hydraulics_input: VesselHydraulicsInput dataclass

    Returns:
        {
            "calc_id": VesselResult.vessel_id,
            "record_hash": 16 hex,
            "stream_id": source_stream_id,
            "result": { "sizing": dict, "hydraulics": dict },
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

    # 3. 调两次计算（纯函数，frozen dataclass → dataclass）
    sizing_result: VesselSizingResult = calc_vessel_sizing(sizing_input)
    hydraulics_result: VesselHydraulicsResult = calc_vessel_hydraulics(hydraulics_input)

    # 4. 构造 VesselResult ORM（input_json + output_json 双轨）
    record = VesselResult(
        tag_number=_generate_tag_number(stream.project_id),
        project_id=stream.project_id,
        workspace_id=stream.workspace_id,
        input_json={
            "sizing": _dataclass_to_dict(sizing_input),
            "hydraulics": _dataclass_to_dict(hydraulics_input),
        },
        output_json={
            "sizing": _dataclass_to_dict(sizing_result),
            "hydraulics": _dataclass_to_dict(hydraulics_result),
        },
    )
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
    outlet = await create_outlet_stream(
        db,
        source_stream_id=source_stream_id,
        calc_type="VESSEL",
        source_type="VESSEL_CALCULATED",
        properties={
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
        },
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
        },
        "outlet_stream_id": outlet.stream_id,
        "outlet_stream_name": outlet.stream_name,
    }


__all__ = ["persist_vessel_calculate"]
