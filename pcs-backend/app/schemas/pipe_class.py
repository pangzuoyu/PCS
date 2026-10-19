"""PipeClass API schemas（Pydantic v2；Task 1.9.1 / P2-STD-001）。

公司级 PipeClass：**5 态**，与 `ConfigAsset` 共用 `ConfigStatus`
（DRAFT/PENDING/APPROVED/PUBLISHED/OBSOLETE），由 `ConfigStateMachine` 驱动。
`ACTIVE` **不属于本表** —— 它只出现在 `formula_definitions` 等子表的
`default=` 上（见 `.wolf/buglog.json` bug-187）。

项目级 ProjectPipeClass：SUP-002 PC-4 schemas 集中在
``app/api/v1/pipe_classes.py``；本模块不再放已废止的 1.9 兼容 schema。

⚠️ 改词表前先读这条：docstring 里的词表**会被前端照抄**。bug-187 就是
docstring 写错 → 前端照抄 → 生产上每个真实值落进「未知状态」兜底。
本文件 docstring 只陈述事实，错误的历史留在 buglog 里 ——
因为守卫测试是 `assert <错误串> not in doc`，把错误串**引用**进 docstring
会让守卫被自己的解释触发（同一个「被注释骗」的病，见
`docs/solutions/testing-issues/guard-test-fooled-by-lying-comment.md`）。
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.models.enums import ConfigStatus


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

    业务：在基类基础上加 status 字段。

    ⚠️ 词表是 `ConfigStatus` 5 态，**不是** 1.9 时代遗留的三态。
    status 在这里是**幂等回写**用的：提交与当前状态相同才接受；
    真正的流转走 `POST /pipe-classes/{id}/{submit,approve,publish,obsolete}`
    四个端点（它们走 `ConfigStateMachine.transition`）。
    试图用 PUT 改状态 → 409，见 `PipeClassService.update`。
    """

    status: ConfigStatus = Field(
        ConfigStatus.DRAFT,
        description=(
            "管号等级状态（ConfigStatus 5 态）。PUT 只接受与当前状态相同的值；"
            "流转走 /submit /approve /publish /obsolete 端点。"
        ),
    )


class PipeClassResponse(PipeClassBase):
    """管号等级出参（GET /pipe-classes 响应体）。

    业务：含 status 字段 + base_material 显式声明（响应体不复用基类默认）；
    from_attributes=True 直接绑 ORM 行（PipeClass）。
    """

    status: ConfigStatus = Field(
        ...,
        description=(
            "管号等级状态（与 ConfigAsset 共用 ConfigStatus 5 态："
            "DRAFT/PENDING/APPROVED/PUBLISHED/OBSOLETE）。"
            "此前是裸 `str` —— 词表进不了契约，客户端只能自己猜，"
            "于是猜错（bug-187）。**改这个字段名或加值就是契约破坏**，"
            "`check-api-drift.sh` 会检出 enum 值删除。"
        ),
    )
    base_material: str | None = Field(
        None, description="材料牌号"
    )  # 重复声明：响应体明确返回
    model_config = {"from_attributes": True}
