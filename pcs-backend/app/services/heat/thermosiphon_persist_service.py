"""thermosiphon_persist_service 热虹吸循环安装高度结果落库（P5-0-1b T1 / SUP-010 §3.5）。

流程：
1. 调 calc_thermosiphon_circulation（纯函数，壳程压力平衡）得到 result
2. 构造 ThermosiphonCirculationResult ORM 实例（11 业务列 + 4 JSONB 容器）
3. db.add + db.flush（thermosiphon_id 分配）
4. record_hash = compute_record_hash（复用 calc_lineage；ADR-0031 统一收口）
5. db.commit + db.refresh

DDL 落列映射（SUP-010 §3.5 逐字命名，不带单位后缀；单位后缀只在
service / dataclass 层显式 —— 工艺室 §5.2）：
  installation_height_calc_m  → installation_height_calc
  installation_height_final_m → installation_height_final
  shell_diameter_m            → shell_diameter
  drum_diameter_m             → drum_diameter
  drum_liquid_level_m         → drum_liquid_level

4 JSONB 容器按 §3.5 逐字命名：inlet_pipe_params / outlet_pipe_params /
shell_side_params / other_params。formula_ref / input_json / output_json
只在 service 层（P5-0 sibling 模式），不入 DDL。

不做：
- 不创建出口物流 stream（热虹吸安装高度是安装尺寸核算，不产生物流变化；
  与 restriction / cv 的 ADR-0022 出口物流模型不同）
- 不做立式 Martinelli Xtt / φ 计算（XLS 职责；由调用方经 other_params 带入）
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.calc import ThermosiphonCirculationResult
from app.services.calc_lineage import compute_record_hash
from app.services.heat.thermosiphon_service import (
    ThermosiphonCirculationInput,
    calc_thermosiphon_circulation,
)
from app.services.heat.thermosiphon_service import (
    ThermosiphonCirculationResult as ThermosiphonCalc,
)

# P5-0-1b T1 formula_version（SUP-010 §3.5 + GPSA §20.4 壳程压力平衡）
_FORMULA_VERSION = "THRMv1.0-p5-0-1b"


def _generate_tag_number() -> str:
    """生成 tag_number（8 hex，无前缀；与 column_sizing / mixer_results 同模式）。"""
    return uuid.uuid4().hex[:8].upper()


def _build_inlet_pipe_params(
    inp: ThermosiphonCirculationInput, payload: dict[str, Any] | None
) -> dict:
    """inlet_pipe_params JSONB 容器（SUP-010 §3.5 示例结构 + 服务层 P11/P12）。"""
    base = dict(payload or {})
    base.setdefault("pressure_drop_const", inp.inlet_pressure_drop_const_m)
    base.setdefault("pressure_drop_coeff", inp.inlet_pressure_drop_coeff)
    return base


def _build_outlet_pipe_params(
    inp: ThermosiphonCirculationInput, payload: dict[str, Any] | None
) -> dict:
    """outlet_pipe_params JSONB 容器（两相流：另带 vapor_fraction / mixture_*）。"""
    base = dict(payload or {})
    base.setdefault("pressure_drop_const", inp.outlet_pressure_drop_const_m)
    base.setdefault("pressure_drop_coeff", inp.outlet_pressure_drop_coeff)
    return base


def _build_shell_side_params(
    inp: ThermosiphonCirculationInput, payload: dict[str, Any] | None
) -> dict:
    """shell_side_params JSONB 容器（avg_density / static_head / friction_drop）。"""
    base = dict(payload or {})
    base.setdefault("avg_density", inp.shell_avg_density_kg_m3)
    base.setdefault("pressure_drop_const", inp.shell_pressure_drop_const_m)
    base.setdefault("pressure_drop_coeff", inp.shell_pressure_drop_coeff)
    return base


class ThermosiphonCirculationPersistService:
    """热虹吸循环安装高度落库 service（P5-0-1b T1）。"""

    @staticmethod
    async def persist_calculate(
        db: AsyncSession,
        *,
        project_id: uuid.UUID,
        workspace_id: uuid.UUID,
        equipment_tag: str,
        equipment_name: str | None,
        input_kwargs: dict[str, Any],
        inlet_pipe_params: dict[str, Any] | None = None,
        outlet_pipe_params: dict[str, Any] | None = None,
        shell_side_params: dict[str, Any] | None = None,
        other_params: dict[str, Any] | None = None,
        tag_number: str | None = None,
    ) -> ThermosiphonCirculationResult:
        """计算 + 落 thermosiphon_circulation_results + record_hash + commit。

        Args:
            db: 异步 session
            project_id / workspace_id: 必填 FK
            equipment_tag: 蒸汽发生器编号（E-106 等）；(project_id, equipment_tag)
                唯一由 DB UNIQUE + service 层共同强制
            equipment_name: 设备名称（可空）
            input_kwargs: ThermosiphonCirculationInput 字段（几何 + 物性 + P11/P12）
            inlet_pipe_params / outlet_pipe_params / shell_side_params /
            other_params: XLS 原始参数容器（可空；缺项由服务层补 P11/P12 / avg_density）
            tag_number: 可选；缺省自生成 8 hex

        Returns:
            ThermosiphonCirculationResult ORM 实例（已 commit + refresh）
        """
        inp = ThermosiphonCirculationInput(**input_kwargs)
        result: ThermosiphonCalc = calc_thermosiphon_circulation(inp)

        record = ThermosiphonCirculationResult(
            tag_number=tag_number or _generate_tag_number(),
            project_id=project_id,
            workspace_id=workspace_id,
            equipment_tag=equipment_tag,
            equipment_name=equipment_name,
            circulation_type=inp.circulation_type,
            shell_diameter=inp.shell_diameter_m,
            drum_diameter=inp.drum_diameter_m,
            drum_liquid_level=inp.drum_liquid_level_m,
            installation_height_calc=result.installation_height_calc_m,
            installation_height_final=result.installation_height_final_m,
            safety_factor=inp.safety_factor,
            check_result=result.check_result,
            circulation_drive_ratio=result.circulation_drive_ratio,
            inlet_pipe_params=_build_inlet_pipe_params(inp, inlet_pipe_params),
            outlet_pipe_params=_build_outlet_pipe_params(inp, outlet_pipe_params),
            shell_side_params=_build_shell_side_params(inp, shell_side_params),
            other_params={
                **(other_params or {}),
                # formula_ref 只在 service 层承载（不入 DDL；P5-0 sibling 模式）
                "formula_ref": {
                    "standard": result.formula_ref.standard,
                    "version": result.formula_ref.version,
                    "clause": result.formula_ref.clause,
                    "source": result.formula_ref.source,
                },
                "input_json": {
                    "drum_liquid_density_kg_m3": inp.drum_liquid_density_kg_m3,
                    "shell_avg_density_kg_m3": inp.shell_avg_density_kg_m3,
                    "drum_temperature_c": inp.drum_temperature_c,
                    "safety_factor": inp.safety_factor,
                },
                "output_json": {
                    "driving_coeff_per_m": result.driving_coeff_per_m,
                    "resistance_const_m": result.resistance_const_m,
                    "resistance_coeff_per_m": result.resistance_coeff_per_m,
                    "circulation_drive_ratio": result.circulation_drive_ratio,
                    "check_result": result.check_result,
                    "formula_version": _FORMULA_VERSION,
                },
            },
        )
        db.add(record)
        await db.flush()  # thermosiphon_id 分配（record_hash 计算前置）
        record.record_hash = compute_record_hash(record)
        await db.commit()
        await db.refresh(record)
        return record


__all__ = [
    "ThermosiphonCirculationPersistService",
    "_FORMULA_VERSION",
    "_generate_tag_number",
]
