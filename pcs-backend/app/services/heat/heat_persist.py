"""HEAT 换热器计算持久化 service（P5-4-5 / Task 23）。

按 PCS-PLAN-P5-DEVICE-EQUIPMENT.md V1.0 §Task 23 + ADR-0027 V1.0 + spec V1.2 §3.2.4：

- `import_htri_heat_result`：HTRI 解析 → map_htri_to_heat_input → save_heat_calc_result
  → finalize_calc_record → 可选 create_outlet_stream(source_type=HEAT_CALCULATED,
  change_type=HEAT_EXCHANGE)
- `estimate_heat_weight`：estimate_weight → 更新 `output_json.total_weight_kg` /
  `output_json.weight_segments`（P7 UTIL 消费；不入 HeatResult 独立列以避免
  alembic 迁移；plan V1.0 §Task 23 步骤 3 明确要求"字段可读"——从 output_json
  读同样满足）

公式版本：HTv1.0-p5-4-2（与 Task 20 heat_data_service 锚点一致）
"""
from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.calc import HeatResult
from app.models.project import Stream
from app.services.calc_lineage import finalize_calc_record
from app.services.exceptions import PcsError
from app.services.heat.heat_data_service import (
    HeatCalcInput,
    map_htri_to_heat_input,
    save_heat_calc_result,
)
from app.services.heat.htri_parser import HtriParsedData
from app.services.heat.weight_estimate_service import (
    WeightEstimateInput,
    WeightEstimateResult,
    estimate_weight,
)
from app.services.outlet_stream import create_outlet_stream

_FORMULA_VERSION_HEAT_IMPORT = "HTv1.0-p5-4-2"
_FORMULA_VERSION_HEAT_WEIGHT = "HTv1.0-p5-4-2"  # 沿用 HTv1.0；weight 是几何估算

# output_json 字段键（P7 UTIL 消费；统一前缀避免与原 output_json 业务字段冲突）
_OUT_TOTAL_WEIGHT_KG = "total_weight_kg"
_OUT_WEIGHT_SEGMENTS = "weight_segments"
_OUT_WEIGHT_FORMULA_REF = "weight_formula_ref"


class HeatStreamNotFoundError(PcsError):
    """源流 stream_id 不存在（404）。"""

    code = "SIM_STREAM_NOT_FOUND"
    status = 404


class HeatProjectMismatchError(PcsError):
    """heat_id 与 source stream project_id 不一致（403/422）。"""

    code = "HEAT_PROJECT_MISMATCH"
    status = 422


async def _verify_source_stream(
    db: AsyncSession, source_stream_id: uuid.UUID, project_id: uuid.UUID
) -> Stream:
    """源流存在性 + project_id 一致性校验（与 create_outlet_stream 共享语义）。"""
    source = await db.get(Stream, source_stream_id)
    if source is None:
        raise HeatStreamNotFoundError(
            f"源流 {source_stream_id} 不存在",
            code=HeatStreamNotFoundError.code,
            status=HeatStreamNotFoundError.status,
        )
    if source.project_id != project_id:
        raise HeatProjectMismatchError(
            f"源流 project_id={source.project_id} 与 heat project_id={project_id} 不一致",
            code=HeatProjectMismatchError.code,
            status=HeatProjectMismatchError.status,
        )
    return source


async def import_htri_heat_result(
    db: AsyncSession,
    *,
    project_id: uuid.UUID,
    workspace_id: uuid.UUID,
    equipment_no: str,
    equipment_name: str | None,
    tag_number: str,
    exchanger_category: str,
    htri: HtriParsedData,
    source_stream_id: uuid.UUID | None = None,
) -> tuple[HeatResult, Stream | None]:
    """HTRI 解析 → HeatResult 落库 + finalize + 可选 outlet stream。

    Args:
        db: async session
        project_id / workspace_id: FK（TaggedRecordMixin 强制）
        equipment_no: 设备位号（业务展示）
        equipment_name: 设备名（默认用 htri.case_name）
        tag_number: HeatResult 必填（NOT NULL 约束）
        exchanger_category: SHELL_TUBE / AIR_COOL / PLATE
        htri: HtriParsedData（Task 19 解析）
        source_stream_id: 可选；提供则创建 HEAT_CALCULATED outlet stream

    Returns:
        (HeatResult, Stream | None) — outlet stream 在 source_stream_id 提供时返回
    """
    # 1. map_htri_to_heat_input
    inp: HeatCalcInput = map_htri_to_heat_input(
        htri=htri, equipment_no=equipment_no, equipment_name=equipment_name
    )

    # 2. 落库 heat_results
    record = await save_heat_calc_result(
        db,
        project_id=project_id,
        workspace_id=workspace_id,
        tag_number=tag_number,
        exchanger_category=exchanger_category,
        inp=inp,
    )

    # 3. finalize_calc_record（record_hash + DataLineage 血缘；source 为空列表
    #    表示无源流，HTRI 是文件输入而非 stream 计算）
    await finalize_calc_record(
        db,
        record,
        source_stream_ids=(
            [source_stream_id] if source_stream_id is not None else []
        ),
        formula_version=_FORMULA_VERSION_HEAT_IMPORT,
    )

    # 4. 可选 outlet stream（HEAT_CALCULATED / HEAT_EXCHANGE）
    outlet: Stream | None = None
    if source_stream_id is not None:
        await _verify_source_stream(db, source_stream_id, project_id)
        outlet = await create_outlet_stream(
            db,
            source_stream_id=source_stream_id,
            calc_type="HEAT_EXCHANGE",
            source_type="HEAT_CALCULATED",
            properties={
                "heat_exchanger_id": str(record.heat_exchanger_id),
                "equipment_no": equipment_no,
                "tag_number": tag_number,
                "exchanger_category": exchanger_category,
                "duty_w": inp.duty,
                "change_type": "HEAT_EXCHANGE",
            },
            project_id=project_id,
            workspace_id=workspace_id,
        )

    # 5. commit（与 vessel_persist 一致；保证 record_hash + outlet 已持久）
    await db.commit()

    return record, outlet


async def estimate_heat_weight(
    db: AsyncSession,
    *,
    heat_id: uuid.UUID,
    weight_input: WeightEstimateInput,
) -> tuple[HeatResult, WeightEstimateResult]:
    """estimate_weight → 写入 HeatResult.output_json（P7 UTIL 消费）。

    Args:
        db: async session
        heat_id: 既有 HeatResult 主键
        weight_input: 重量估算输入

    Returns:
        (HeatResult, WeightEstimateResult) — 已写入 output_json.total_weight_kg /
        weight_segments / weight_formula_ref

    Raises:
        PcsError: heat_id 不存在
    """
    record = await db.get(HeatResult, heat_id)
    if record is None:
        raise PcsError(
            f"HeatResult {heat_id} not found",
            code="HEAT_NOT_FOUND",
            status=404,
        )

    # 1. 估算重量
    wres = estimate_weight(weight_input)

    # 2. 写入 output_json（保留原 output_json 业务字段；新增 3 个 weight 字段）
    output = dict(record.output_json or {})
    output[_OUT_TOTAL_WEIGHT_KG] = wres.total.weight_kg
    output[_OUT_WEIGHT_SEGMENTS] = {
        "shell_cylinder_kg": wres.shell_cylinder.weight_kg,
        "shell_heads_kg": wres.shell_heads.weight_kg,
        "shell_flanges_kg": wres.shell_flanges.weight_kg,
        "shell_nozzles_kg": wres.shell_nozzles.weight_kg,
        "shell_saddles_kg": wres.shell_saddles.weight_kg,
        "shell_total_kg": wres.shell_total.weight_kg,
        "tube_kg": wres.tube.weight_kg,
        "baffle_kg": wres.baffle.weight_kg,
        "channels_kg": wres.channels.weight_kg,
    }
    output[_OUT_WEIGHT_FORMULA_REF] = wres.formula_ref
    record.output_json = output

    # 3. 刷新 record_hash（output_json 变更 → 哈希需重算）
    await finalize_calc_record(
        db,
        record,
        source_stream_ids=[],
        formula_version=_FORMULA_VERSION_HEAT_WEIGHT,
    )
    await db.commit()

    return record, wres


__all__ = [
    "HeatStreamNotFoundError",
    "HeatProjectMismatchError",
    "import_htri_heat_result",
    "estimate_heat_weight",
]
