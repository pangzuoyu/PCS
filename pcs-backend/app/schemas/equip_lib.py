"""equip-lib 沉淀 schemas（Task 1.9.5 / P2-EQL-001 + P7 §3.2.3(4) 标准化要求）。"""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class ApplicableConditions(BaseModel):
    pressure_mpa: str | None = Field(None, description="适用压力区间，如 0.1~2.5 MPa")
    temperature_c: str | None = Field(None, description="适用温度区间，如 -20~200 °C")
    medium: str | None = Field(None, max_length=200, description="适用介质（工艺物料类别）")


class EquipLibSettleRequest(BaseModel):
    """标准化信息校验规则（必填项照 P7 表）：材质/关键尺寸/原项目位号/投用日期必填；
    标准图号如有则必填→简化为可选字段+非空校验由前端承担（P2）；重量必填（如有）。
    """

    equipment_name: str = Field(
        ..., min_length=1, max_length=200, description="设备名称（如 离心泵 P-101A）"
    )
    equipment_type: str = Field(
        ...,
        min_length=1,
        max_length=30,
        description="设备类型（如 PUMP/COMPRESSOR/HEAT_EXCHANGER/VESSEL/COLUMN）",
    )
    standard_drawing_no: str | None = Field(
        None, max_length=100, description="标准图号（如 HG/T 1234-2018）"
    )
    applicable_conditions: ApplicableConditions | None = Field(
        None, description="适用工况区间"
    )
    material: str = Field(
        ..., min_length=1, max_length=200, description="主体材质（如 SS316、20#）"
    )
    weight_kg: float | None = Field(None, gt=0, description="重量 kg")
    key_dimensions: dict = Field(..., description="关键尺寸，必填（至少一键）")
    original_tag: str = Field(..., min_length=1, max_length=50, description="原项目位号")
    commissioning_date: str = Field(..., description="投用日期 YYYY-MM-DD")
    source_equipment_id: str | None = Field(None, description="源设备 ID（项目内）")
    source_project_id: str | None = Field(None, description="源项目 ID")

    @field_validator("key_dimensions")
    @classmethod
    def require_any_dimension(cls, v: dict) -> dict:
        if not v:
            raise ValueError("key_dimensions 不能为空")
        return v
