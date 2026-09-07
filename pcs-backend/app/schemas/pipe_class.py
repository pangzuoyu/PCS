"""PipeClass API schemas（Pydantic v2；Task 1.9.1 / P2-STD-001）。"""
from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class PipeClassBase(BaseModel):
    class_id: str = Field(..., min_length=1, max_length=20)
    class_name: str = Field(..., min_length=1, max_length=200)
    material_standard: str = Field(..., min_length=1, max_length=100)
    base_material: str | None = Field(None, max_length=100, description="材料牌号")
    corrosion_allowance: float = Field(..., ge=0, description="腐蚀裕量 mm")
    design_pressure: float = Field(..., gt=0, description="MPaG")
    design_temperature: float = Field(..., description="°C")
    fluid_service: str | None = Field(None, max_length=100)
    allowable_stress_json: dict[str, Any] = Field(default_factory=dict)
    dn_series_json: dict[str, int] = Field(..., description="{min,max}")
    sch_series_json: dict[str, str] = Field(..., description="DN→Sch")
    flange_class: str = Field(..., min_length=1, max_length=20)
    fitting_type: str | None = Field(None, max_length=50)
    branch_table_json: dict[str, Any] | None = None
    source: Literal["COMPANY_STD", "PROJECT"]
    version: str = Field(..., min_length=1, max_length=50)

    @model_validator(mode="after")
    def _check_dn(self) -> PipeClassBase:
        mn, mx = self.dn_series_json.get("min"), self.dn_series_json.get("max")
        if mn is None or mx is None or not (0 < mn <= mx):
            raise ValueError("dn_series_json 需 {min,max} 且 0<min<=max（单口径 min==max 合法）")
        return self


class PipeClassCreate(PipeClassBase):
    pass


class PipeClassUpdate(PipeClassBase):
    status: Literal["DRAFT", "ACTIVE", "OBSOLETE"] = "DRAFT"


class PipeClassResponse(PipeClassBase):
    status: str
    base_material: str | None = None  # 重复声明：响应体明确返回
    model_config = {"from_attributes": True}


class ProjectAssignRequest(BaseModel):
    class_id: str = Field(..., min_length=1, max_length=20)
    enabled: bool = True
    custom_override_json: dict[str, Any] | None = None


class ProjectPipeClassResponse(BaseModel):
    project_id: UUID
    class_id: str
    enabled: bool
    custom_override_json: dict[str, Any] | None = None
    pipe_class: PipeClassResponse | None = None
    model_config = {"from_attributes": True}
