"""PipeClass API schemas（Pydantic v2；Task 1.9.1 / P2-STD-001）。

公司级 PipeClass：3 态 DRAFT/ACTIVE/OBSOLETE。
项目级 ProjectPipeClass：SUP-002 PC-4 schemas 集中在
``app/api/v1/pipe_classes.py``；本模块不再放已废止的 1.9 兼容 schema。
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class PipeClassBase(BaseModel):
    """管号等级基础字段（公司级 PipeClass 共用基类，Create/Update/Response 继承）。

    业务：管号等级基础 16 字段（class_id/class_name/material_standard +
    design_pressure/temperature + dn_series_json/sch_series_json + flange_class +
    allowable_stress_json 等）；含 model_validator 校验 dn_series_json 完整性。
    """

    class_id: str = Field(
        ..., min_length=1, max_length=20, description="管号等级编号（公司内唯一）"
    )
    class_name: str = Field(
        ..., min_length=1, max_length=200, description="管号等级名称"
    )
    material_standard: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="材料标准（如 GB/T 12459、ASME B16.9）",
    )
    base_material: str | None = Field(
        None, max_length=100, description="材料牌号"
    )
    corrosion_allowance: float = Field(..., ge=0, description="腐蚀裕量 mm")
    design_pressure: float = Field(..., gt=0, description="设计压力（MPa，表压 MPaG）")
    design_temperature: float = Field(..., description="设计温度（°C）")
    fluid_service: str | None = Field(
        None, max_length=100, description="流体服务（工艺介质类别）"
    )
    allowable_stress_json: dict[str, Any] = Field(
        default_factory=dict, description="许用应力表 {温度(°C): 应力 MPa}"
    )
    dn_series_json: dict[str, int] = Field(
        ..., description="DN 系列范围（mm，{min, max}）"
    )
    sch_series_json: dict[str, str] = Field(
        ..., description="DN → Sch 壁厚系列映射（管壁厚对应表，DN→Sch）"
    )
    flange_class: str = Field(
        ...,
        min_length=1,
        max_length=20,
        description="法兰等级（如 150#、300#、600#）",
    )
    fitting_type: str | None = Field(
        None, max_length=50, description="管件类型（如 ELBOW、TEE、REDUCER）"
    )
    branch_table_json: dict[str, Any] | None = Field(
        None, description="支管表（接管尺寸与补强规则）"
    )
    source: Literal["COMPANY_STD", "PROJECT"] = Field(
        ..., description="数据来源：公司标准 / 项目自定义"
    )
    version: str = Field(
        ..., min_length=1, max_length=50, description="版本号（如 1.0、A1）"
    )

    @model_validator(mode="after")
    def _check_dn(self) -> PipeClassBase:
        """dn_series_json 完整性校验（Pydantic v2 model_validator）。

        业务：dn_series_json 需含 {min, max}；0 < min <= max；
        单口径（min == max）合法；缺失或越界 → ValueError。
        """
        mn, mx = self.dn_series_json.get("min"), self.dn_series_json.get("max")
        if mn is None or mx is None or not (0 < mn <= mx):
            raise ValueError("dn_series_json 需 {min,max} 且 0<min<=max（单口径 min==max 合法）")
        return self


class PipeClassCreate(PipeClassBase):
    """创建管号等级请求体（POST /pipe-classes，继承全部基类字段）。

    业务：与 PipeClassBase 完全一致；继承 model_validator（dn_series 完整性）。
    """


class PipeClassUpdate(PipeClassBase):
    """更新管号等级请求体（PUT /pipe-classes/{class_id}，含状态字段）。

    业务：在基类基础上加 status 字段（DRAFT/ACTIVE/OBSOLETE），支持
    直接通过 PUT 触发管号等级发布/作废生命周期切换。
    """

    status: Literal["DRAFT", "ACTIVE", "OBSOLETE"] = Field(
        "DRAFT", description="管号等级状态：DRAFT/ACTIVE/OBSOLETE"
    )


class PipeClassResponse(PipeClassBase):
    """管号等级出参（GET /pipe-classes 响应体）。

    业务：含 status 字段 + base_material 显式声明（响应体不复用基类默认）；
    from_attributes=True 直接绑 ORM 行（PipeClass）。
    """

    status: str = Field(..., description="管号等级状态")
    base_material: str | None = Field(
        None, description="材料牌号"
    )  # 重复声明：响应体明确返回
    model_config = {"from_attributes": True}
