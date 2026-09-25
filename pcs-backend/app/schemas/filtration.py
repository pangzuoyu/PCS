"""FILTRATION Pydantic 请求/响应模型（SPEC §3.2.7 P6-3 Task 34）。

8 schemas：
- 3 calc request/response（RuthPressure / RuthRate / Ergun 各 1 对）
- 5 CRUD：Create / Update / Response / ListResponse / DeleteResponse

字段 snake_case 1:1 与 FiltrationResult ORM 11 业务字段一致（task 30 落地）。

端点：
- POST /api/v1/filtration/ruth-constant-pressure/calculate
- POST /api/v1/filtration/ruth-constant-rate/calculate
- POST /api/v1/filtration/ergun/calculate
- POST   /api/v1/filtration/results         创建 FiltrationResult（201）
- GET    /api/v1/filtration/results         列出（分页）
- GET    /api/v1/filtration/results/{id}    详情
- PATCH  /api/v1/filtration/results/{id}    更新（DRAFT/CHANGE_PENDING 可改）
- DELETE /api/v1/filtration/results/{id}    软删除（→ OBSOLETE）
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

# ───────────────────────────── 公共 base ─────────────────────────────


class FiltrationCalcBase(BaseModel):
    """FILTRATION calc 公共请求/响应字段（3 模块共享）。

    字段（与 FiltrationResult ORM 11 业务字段平铺一致）：
    - 必填（4 字段）：media_type / area / cycle_time / pressure_drop +
      project_id / workspace_id / tag_number（在 3 calc request 中重复；
      保留 schema 字段命名一致性）
    - 可空（6 字段）：cake_resistance_alpha / specific_resistance_r0 /
      permeability_k / porosity_eps / filter_velocity（按 calc 模块落库）
    """

    model_config = ConfigDict(extra="ignore")

    project_id: uuid.UUID = Field(..., description="项目 ID（isolation key）")
    workspace_id: uuid.UUID = Field(..., description="工作区 ID")
    tag_number: str = Field(..., min_length=1, max_length=64, description="位号")
    media_type: str = Field(
        ...,
        description="介质代码（SAND/ANTHRACITE/CARBON/RUTH_FILTER_CLOTH/ERGUN_PACKING）",
    )
    area: float = Field(..., gt=0, description="过滤面积 A（m²）")
    cycle_time: float = Field(..., ge=0, description="过滤周期（h）")
    pressure_drop: float = Field(..., gt=0, description="压降（Pa）")
    # 派生字段（可空，按 calc 模块落库）
    cake_resistance_alpha: float | None = Field(
        default=None, ge=0, description="m/kg 滤饼比阻"
    )
    specific_resistance_r0: float | None = Field(
        default=None, ge=0, description="1/m 介质单位阻力"
    )
    permeability_k: float | None = Field(
        default=None, gt=0, description="m² 渗透率"
    )
    porosity_eps: float | None = Field(
        default=None, gt=0, lt=1, description="无量纲 床层空隙率"
    )
    filter_velocity: float | None = Field(
        default=None, ge=0, description="m/s 过滤速率"
    )


# ───────────────────────────── 3 calc schemas ─────────────────────────


class RuthConstantPressureCalcRequest(FiltrationCalcBase):
    """POST /filtration/ruth-constant-pressure/calculate 请求。

    字段：4 公共必填 + cake_resistance_alpha（可选）+ specific_resistance_r0
    （可选）。filter_velocity 由 calc 派生，可不传。
    """


class RuthConstantPressureCalcResponse(FiltrationCalcBase):
    """POST /filtration/ruth-constant-pressure/calculate 响应（201）。

    额外含：result_id / record_hash / sign_status / created_at。
    """

    result_id: uuid.UUID = Field(..., description="filter_id（PK）")
    record_hash: str | None = Field(
        default=None,
        description="record_hash（ADR-0028 §决策 4 reflection；16 hex）",
    )
    sign_status: str = Field(..., description="签审状态 9 态")
    created_at: datetime = Field(..., description="创建时间")


class RuthConstantRateCalcRequest(FiltrationCalcBase):
    """POST /filtration/ruth-constant-rate/calculate 请求。

    字段：与 RuthConstantPressureCalcRequest 镜像（恒速泵入场景）。
    """


class RuthConstantRateCalcResponse(FiltrationCalcBase):
    """POST /filtration/ruth-constant-rate/calculate 响应（201）。"""

    result_id: uuid.UUID = Field(..., description="filter_id（PK）")
    record_hash: str | None = Field(default=None, description="record_hash（16 hex）")
    sign_status: str = Field(..., description="签审状态 9 态")
    created_at: datetime = Field(..., description="创建时间")


class ErgunCalcRequest(FiltrationCalcBase):
    """POST /filtration/ergun/calculate 请求。

    额外字段：permeability_k / porosity_eps（深层过滤介质阻力）。
    """

    model_config = ConfigDict(extra="ignore")


class ErgunCalcResponse(FiltrationCalcBase):
    """POST /filtration/ergun/calculate 响应（201）。

    额外填 permeability_k / porosity_eps（calc 派生）。
    """

    result_id: uuid.UUID = Field(..., description="filter_id（PK）")
    record_hash: str | None = Field(default=None, description="record_hash（16 hex）")
    sign_status: str = Field(..., description="签审状态 9 态")
    created_at: datetime = Field(..., description="创建时间")


# ───────────────────────────── 5 CRUD schemas ─────────────────────────


class FiltrationCreateRequest(BaseModel):
    """POST /filtration/results 直接创建请求（不走 calc）。

    业务字段子集（PATCH-style）：所有 10 业务字段均可填；filter_type /
    media_type + 3 平铺（area / cycle_time / pressure_drop）必填。
    """

    model_config = ConfigDict(extra="ignore")

    project_id: uuid.UUID = Field(..., description="项目 ID")
    workspace_id: uuid.UUID = Field(..., description="工作区 ID")
    tag_number: str = Field(..., min_length=1, max_length=64, description="位号")
    filter_type: str = Field(
        ..., description="过滤类型（RUTH_CONST_PRESSURE/RUTH_CONST_RATE/ERGUN_DEEP_BED）"
    )
    media_type: str = Field(..., description="介质代码")
    area: float = Field(..., gt=0, description="m² 过滤面积")
    cycle_time: float = Field(..., ge=0, description="h 过滤周期")
    pressure_drop: float = Field(..., gt=0, description="Pa 压降")
    # 可选 6 字段
    cake_resistance_alpha: float | None = Field(default=None, ge=0)
    specific_resistance_r0: float | None = Field(default=None, ge=0)
    permeability_k: float | None = Field(default=None, gt=0)
    porosity_eps: float | None = Field(default=None, gt=0, lt=1)
    filter_velocity: float | None = Field(default=None, ge=0)


class FiltrationUpdateRequest(BaseModel):
    """PATCH /filtration/results/{id} 请求（partial update）。

    所有字段 optional（PATCH 部分更新）。白名单由 service 层校验。
    ``extra="forbid"``：未知字段 → Pydantic 422，避免 service 层 silent drop。
    """

    model_config = ConfigDict(extra="forbid")

    filter_type: str | None = Field(default=None)
    media_type: str | None = Field(default=None)
    area: float | None = Field(default=None, gt=0)
    cycle_time: float | None = Field(default=None, ge=0)
    pressure_drop: float | None = Field(default=None, gt=0)
    cake_resistance_alpha: float | None = Field(default=None, ge=0)
    specific_resistance_r0: float | None = Field(default=None, ge=0)
    permeability_k: float | None = Field(default=None, gt=0)
    porosity_eps: float | None = Field(default=None, gt=0, lt=1)
    filter_velocity: float | None = Field(default=None, ge=0)


class FiltrationResultResponse(FiltrationCalcBase):
    """GET /filtration/results/{id} 响应（含溯源 + 业务字段）。

    字段映射（ORM → schema）：
    - ORM filter_id → schema result_id（PK 重命名；前端统一用 result_id）
    """

    result_id: uuid.UUID = Field(..., description="filter_id（PK）")
    filter_type: str = Field(..., description="过滤类型")
    sign_status: str = Field(..., description="签审状态 9 态")
    record_hash: str | None = Field(
        default=None, description="record_hash（16 hex）"
    )
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime | None = Field(default=None, description="更新时间")

    model_config = ConfigDict(
        extra="ignore", populate_by_name=True, from_attributes=True
    )

    @model_validator(mode="before")
    @classmethod
    def _from_orm_rename(cls, data: Any) -> Any:
        """ORM → schema 字段映射：ORM filter_id → schema result_id。

        支持 dict 输入（来自 model_validate(record, from_attributes=True) 透传
        的 ORM 属性访问）；attr 输入（record.xxx）也走同样的 getattr。
        """
        if data is None:
            return data
        filter_id = getattr(data, "filter_id", None)
        if filter_id is not None and not isinstance(data, dict):
            try:
                data.result_id = filter_id  # noqa: B010
            except AttributeError:
                # 不可 set（如 MagicMock 已被 frozen）→ 转 dict 处理
                if hasattr(data, "__dict__"):
                    d = dict(data.__dict__)
                    d["result_id"] = filter_id
                    return d
        return data


class FiltrationListResponse(BaseModel):
    """GET /filtration/results 列表响应。

    字段：
    - items: FiltrationResultResponse 列表
    - total: 命中条数（受 include_obsolete 影响）
    - skip / limit: 分页参数回显
    """

    model_config = ConfigDict(extra="ignore")

    items: list[FiltrationResultResponse] = Field(
        ..., description="FiltrationResult 列表"
    )
    total: int = Field(..., description="命中条数")
    skip: int = Field(..., description="分页偏移")
    limit: int = Field(..., description="分页上限")


class FiltrationDeleteResponse(BaseModel):
    """DELETE /filtration/results/{id} 响应。

    字段：result_id + tag_number（含 __OBSOLETE_<ts> 后缀）+ sign_status +
    deleted_at。
    """

    model_config = ConfigDict(extra="ignore")

    result_id: uuid.UUID = Field(..., description="filter_id（PK）")
    tag_number: str = Field(
        ..., description="位号（含 __OBSOLETE_<ts> 后缀）"
    )
    sign_status: str = Field(..., description="签审状态（已改为 OBSOLETE）")
    deleted_at: datetime = Field(..., description="删除时间（updated_at）")


__all__ = [
    "FiltrationCalcBase",
    # 3 calc
    "RuthConstantPressureCalcRequest",
    "RuthConstantPressureCalcResponse",
    "RuthConstantRateCalcRequest",
    "RuthConstantRateCalcResponse",
    "ErgunCalcRequest",
    "ErgunCalcResponse",
    # 5 CRUD
    "FiltrationCreateRequest",
    "FiltrationUpdateRequest",
    "FiltrationResultResponse",
    "FiltrationListResponse",
    "FiltrationDeleteResponse",
]