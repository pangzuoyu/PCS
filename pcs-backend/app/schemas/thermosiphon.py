"""热虹吸循环安装高度 Pydantic schema（P5-0-1b T1 / SUP-010 §3.5）。

ThermosiphonCalculateRequest 字段对齐 service 层 ThermosiphonCirculationInput
（frozen dataclass，单位后缀显式 —— 工艺室 §5.2）；ThermosiphonCalculateResponse
回填 ThermosiphonCirculationResult 全部字段 + formula_ref（service 层承载，
不入 DDL —— 与 P5-0 sibling 模式一致）。

设计要点：
- `extra='forbid'` 拒绝未知字段（.wolf/cerebrum.md Do-Not-Repeat：
  PsvCalculateRequest 历史教训）
- 所有 Field description 含中文
- safety_factor 默认 1.5（SUP-010 §3.5 声明）
- circulation_type / check_result 用 Literal 收窄（DDL 层用 String + CHECK）

不做：
- 不实现 record_hash 算法（service 层复用 calc_lineage.compute_record_hash）
- 不落库（thermosiphon_persist_service 负责）
- 不实现立式 Martinelli Xtt / φ 计算（XLS 职责）
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CirculationTypeLit = Literal["HORIZONTAL", "VERTICAL"]
CheckResultLit = Literal["PASS", "FAIL"]


class ThermosiphonCalculateRequest(BaseModel):
    """POST /api/v1/thermosiphon/calculate 请求体（SUP-010 §3.5）。"""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    circulation_type: CirculationTypeLit = Field(..., description="循环类型")
    shell_diameter_m: float = Field(..., gt=0, description="壳程直径 Ds（m）")
    drum_diameter_m: float = Field(..., gt=0, description="汽包直径（m）")
    drum_liquid_level_m: float = Field(..., ge=0, description="汽包液位高 H1（m）")
    drum_liquid_density_kg_m3: float = Field(..., gt=0, description="汽包液体密度 ρ（kg/m³）")
    shell_avg_density_kg_m3: float = Field(
        ..., gt=0, description="壳程两相流平均密度（kg/m³）"
    )
    drum_temperature_c: float = Field(
        default=0.0, gt=-273.15, description="汽包液体温度（°C）"
    )
    inlet_pressure_drop_const_m: float = Field(
        default=0.0, ge=0, description="入口管线摩阻常数项 P11（m 液柱）"
    )
    inlet_pressure_drop_coeff: float = Field(
        default=0.0, ge=0, description="入口管线摩阻系数 P12（m/m，乘 Hx）"
    )
    outlet_pressure_drop_const_m: float = Field(
        default=0.0, ge=0, description="出口管线摩阻常数项 P11（m 液柱）"
    )
    outlet_pressure_drop_coeff: float = Field(
        default=0.0, ge=0, description="出口管线摩阻系数 P12（m/m，乘 Hx）"
    )
    shell_pressure_drop_const_m: float = Field(
        default=0.0, ge=0, description="壳程摩阻常数项 P11（m 液柱）"
    )
    shell_pressure_drop_coeff: float = Field(
        default=0.0, ge=0, description="壳程摩阻系数 P12（m/m，乘 Hx）"
    )
    safety_factor: float = Field(default=1.5, gt=0, description="最终安装高度余量倍数")


class ThermosiphonCalculateResponse(BaseModel):
    """POST /api/v1/thermosiphon/calculate 响应体（200）。

    字段对齐 service 层 ThermosiphonCirculationResult（frozen dataclass）。
    """

    model_config = ConfigDict(protected_namespaces=())

    installation_height_calc_m: float = Field(..., description="计算安装高度 Hx（m）")
    installation_height_final_m: float = Field(..., description="最终安装高度 Hxo（m）")
    driving_coeff_per_m: float = Field(..., description="驱动压头梯度（m/m）")
    resistance_const_m: float = Field(..., description="ΣP11 总阻力常数项（m 液柱）")
    resistance_coeff_per_m: float = Field(..., description="ΣP12 总阻力系数（m/m）")
    circulation_drive_ratio: float = Field(..., description="循环推动力 / 总压降之比")
    check_result: CheckResultLit = Field(..., description="校核结果 PASS / FAIL")
    formula_ref_standard: str = Field(..., description="公式溯源：标准")
    formula_ref_version: str = Field(..., description="公式溯源：版本")
    formula_ref_clause: str = Field(..., description="公式溯源：条款")
    formula_ref_source: str = Field(..., description="公式溯源：数据来源")


__all__ = [
    "CirculationTypeLit",
    "CheckResultLit",
    "ThermosiphonCalculateRequest",
    "ThermosiphonCalculateResponse",
]
