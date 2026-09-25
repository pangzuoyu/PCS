"""COST_EST Pydantic 请求/响应模型（SPEC §3.2.8 P6-3 Task 36）。

8 schemas：
- 3 calc request/response（SixTenthsRule / CepciAdjustment / CostCorrelation
  各 1 对）
- 5 CRUD：Create / Update / Response / ListResponse / DeleteResponse

字段 snake_case 1:1 与 CostEstResult ORM 11 业务列一致（PK cost_est_id
+ FK equipment_id + 4 v3.1 列 + 6 Task 30 派生列；含 created_at）。

端点：
- POST /api/v1/cost-est/six-tenths-rule/calculate
- POST /api/v1/cost-est/cepci-adjustment/calculate
- POST /api/v1/cost-est/cost-correlation/calculate
- POST   /api/v1/cost-est/results         创建 CostEstResult（201）
- GET    /api/v1/cost-est/results         列表（按 equipment_id 过滤）
- GET    /api/v1/cost-est/results/{id}    详情
- PATCH  /api/v1/cost-est/results/{id}    更新
- DELETE /api/v1/cost-est/results/{id}    物理删除

与 filtration/open_channel 的 schema 关键差异：
- 无 ``project_id`` / ``workspace_id`` / ``tag_number`` 字段（CostEstResult
  不含这些列）
- 以 ``equipment_id`` 取代 tag_number 作为业务标识（FK → equipment_list）
- 无 ``sign_status`` / ``record_hash`` 字段（CostEstResult 不含这些列）
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

# ───────────────────────────── 公共 base ─────────────────────────────


class CostEstCalcBase(BaseModel):
    """COST_EST calc 公共字段（3 模块共享；SixTenthsRule/CepciAdjustment
    专用；CostCorrelation 走 ``CostCorrelationCalcBase``）。

    字段与 CostEstResult ORM 6 任务 30 派生列 + 4 v3.1 列平铺：
    - 必填：estimated_cost / currency / cost_index_year
    - 可空：base_cost / base_year / cepci_index_base / cepci_index_target /
      scaling_exponent / correlation_source
    """

    model_config = ConfigDict(extra="ignore")

    estimated_cost: float = Field(..., ge=0, description="估算投资 C₂")
    currency: str = Field(default="USD", max_length=10, description="货币代码")
    cost_index_year: int = Field(
        default=2019, ge=1900, le=2200, description="目标年"
    )
    base_cost: float | None = Field(default=None, ge=0, description="基准年成本 C₁")
    base_year: int | None = Field(default=None, ge=1900, le=2200, description="基准年")
    cepci_index_base: float | None = Field(default=None, gt=0, description="基准 CEPCI")
    cepci_index_target: float | None = Field(default=None, gt=0, description="目标 CEPCI")
    scaling_exponent: float | None = Field(
        default=None, gt=0, le=1.5, description="六十法则 scaling 指数 n"
    )


class CostCorrelationCalcBase(BaseModel):
    """COST_CORRELATION calc 公共字段（不含 CEPCI/scaling_exponent）。"""

    model_config = ConfigDict(extra="ignore")

    estimated_cost: float = Field(..., ge=0)
    currency: str = Field(default="USD", max_length=10)
    cost_index_year: int = Field(default=2019, ge=1900, le=2200)
    base_cost: float | None = Field(default=None, ge=0)
    base_year: int | None = Field(default=None, ge=1900, le=2200)
    correlation_source: str | None = Field(default=None, max_length=64)


# ───────────────────────────── 3 calc schemas ─────────────────────────


class SixTenthsRuleCalcRequest(BaseModel):
    """POST /cost-est/six-tenths-rule/calculate 请求。

    必填：equipment_id + reference_cost + reference_cepci + target_cepci +
    scaling_exponent + estimated_cost。
    """

    model_config = ConfigDict(extra="ignore")

    equipment_id: uuid.UUID = Field(..., description="设备 UUID（FK → equipment_list）")
    reference_cost: float = Field(..., ge=0, description="基准投资 C₁")
    reference_cepci: float = Field(..., gt=0, description="基准 CEPCI CEPCI₁")
    target_cepci: float = Field(..., gt=0, description="目标 CEPCI CEPCI₂")
    scaling_exponent: float = Field(default=0.6, gt=0, le=1.5, description="scaling 指数 n")
    estimated_cost: float = Field(..., ge=0, description="估算投资 C₂")
    currency: str = Field(default="USD", max_length=10)
    cost_index_year: int = Field(default=2019, ge=1900, le=2200)
    base_cost: float | None = Field(default=None, ge=0)
    base_year: int | None = Field(default=None, ge=1900, le=2200)


class SixTenthsRuleCalcResponse(CostEstCalcBase):
    """POST /cost-est/six-tenths-rule/calculate 响应（201）。

    与 ``CostEstCalcBase`` 镜像（已含 estimated_cost/currency/cost_index_year
    + 6 派生列）；额外填 result_id（cost_est_id）+ equipment_id +
    created_at（CostEstResult 无 record_hash/sign_status 列）。
    """

    result_id: uuid.UUID = Field(..., description="cost_est_id（PK）")
    equipment_id: uuid.UUID = Field(..., description="设备 UUID")
    created_at: datetime = Field(..., description="创建时间")


class CepciAdjustmentCalcRequest(BaseModel):
    """POST /cost-est/cepci-adjustment/calculate 请求（§3.2.8 第二项）。"""

    model_config = ConfigDict(extra="ignore")

    equipment_id: uuid.UUID
    reference_cost: float = Field(..., ge=0)
    reference_cepci: float = Field(..., gt=0)
    target_cepci: float = Field(..., gt=0)
    estimated_cost: float = Field(..., ge=0)
    currency: str = Field(default="USD", max_length=10)
    cost_index_year: int = Field(default=2019, ge=1900, le=2200)
    base_cost: float | None = Field(default=None, ge=0)
    base_year: int | None = Field(default=None, ge=1900, le=2200)


class CepciAdjustmentCalcResponse(CostEstCalcBase):
    """POST /cost-est/cepci-adjustment/calculate 响应（201）。

    与 ``CostEstCalcBase`` 镜像（无 scaling_exponent 必填）；额外填
    result_id + equipment_id + created_at。
    """

    result_id: uuid.UUID
    equipment_id: uuid.UUID
    created_at: datetime


class CostCorrelationCalcRequest(BaseModel):
    """POST /cost-est/cost-correlation/calculate 请求（§3.2.8 第三项）。"""

    model_config = ConfigDict(extra="ignore")

    equipment_id: uuid.UUID
    equipment_type: str = Field(
        ..., description="TOWER/VESSEL/HEAT_EXCHANGER/PUMP/COMPRESSOR/PIPING"
    )
    scale_parameter: float = Field(..., gt=0)
    correlation_source: str = Field(..., max_length=64)
    estimated_cost: float = Field(..., ge=0)
    currency: str = Field(default="USD", max_length=10)
    cost_index_year: int = Field(default=2019, ge=1900, le=2200)
    base_cost: float | None = Field(default=None, ge=0)
    base_year: int | None = Field(default=None, ge=1900, le=2200)


class CostCorrelationCalcResponse(CostCorrelationCalcBase):
    """POST /cost-est/cost-correlation/calculate 响应（201）。"""

    result_id: uuid.UUID
    equipment_id: uuid.UUID
    created_at: datetime


# ───────────────────────────── 5 CRUD schemas ─────────────────────────


class CostEstCreateRequest(BaseModel):
    """POST /cost-est/results 直接创建请求（不走 calc）。

    必填：equipment_id + estimated_cost；其余字段 optional。
    """

    model_config = ConfigDict(extra="ignore")

    equipment_id: uuid.UUID
    estimated_cost: float = Field(..., ge=0)
    currency: str = Field(default="USD", max_length=10)
    cost_index_year: int = Field(default=2019, ge=1900, le=2200)
    base_cost: float | None = Field(default=None, ge=0)
    base_year: int | None = Field(default=None, ge=1900, le=2200)
    cepci_index_base: float | None = Field(default=None, gt=0)
    cepci_index_target: float | None = Field(default=None, gt=0)
    correlation_source: str | None = Field(default=None, max_length=64)
    scaling_exponent: float | None = Field(default=None, gt=0, le=1.5)


class CostEstUpdateRequest(BaseModel):
    """PATCH /cost-est/results/{id} 请求（partial update）。"""

    model_config = ConfigDict(extra="forbid")

    estimated_cost: float | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, max_length=10)
    cost_index_year: int | None = Field(default=None, ge=1900, le=2200)
    base_cost: float | None = Field(default=None, ge=0)
    base_year: int | None = Field(default=None, ge=1900, le=2200)
    cepci_index_base: float | None = Field(default=None, gt=0)
    cepci_index_target: float | None = Field(default=None, gt=0)
    correlation_source: str | None = Field(default=None, max_length=64)
    scaling_exponent: float | None = Field(default=None, gt=0, le=1.5)


class CostEstResultResponse(BaseModel):
    """GET /cost-est/results/{id} 响应（含完整业务字段）。"""

    model_config = ConfigDict(
        extra="ignore", populate_by_name=True, from_attributes=True
    )

    result_id: uuid.UUID = Field(..., description="cost_est_id（PK）")
    equipment_id: uuid.UUID = Field(..., description="设备 UUID")
    estimated_cost: float = Field(..., description="估算成本")
    currency: str = Field(..., description="货币代码")
    cost_index_year: int = Field(..., description="目标年")
    base_cost: float | None = Field(default=None)
    base_year: int | None = Field(default=None)
    cepci_index_base: float | None = Field(default=None)
    cepci_index_target: float | None = Field(default=None)
    correlation_source: str | None = Field(default=None)
    scaling_exponent: float | None = Field(default=None)
    created_at: datetime = Field(..., description="创建时间")

    @model_validator(mode="before")
    @classmethod
    def _from_orm_rename(cls, data: Any) -> Any:
        """ORM → schema 字段映射：ORM cost_est_id → schema result_id。

        支持 dict / ORM attr 输入；attr 输入（record.cost_est_id）走 getattr
        同样映射。
        """
        if data is None:
            return data
        cost_est_id = getattr(data, "cost_est_id", None)
        if cost_est_id is not None and not isinstance(data, dict):
            try:
                data.result_id = cost_est_id  # type: ignore[attr-defined]  # noqa: B010
            except AttributeError:
                if hasattr(data, "__dict__"):
                    d = dict(data.__dict__)
                    d["result_id"] = cost_est_id
                    return d
        elif isinstance(data, dict) and "cost_est_id" in data and "result_id" not in data:
            data = {**data, "result_id": data["cost_est_id"]}
        return data


class CostEstListResponse(BaseModel):
    """GET /cost-est/results 列表响应。"""

    model_config = ConfigDict(extra="ignore")

    items: list[CostEstResultResponse] = Field(..., description="CostEstResult 列表")
    total: int = Field(..., description="命中条数")
    skip: int = Field(..., description="分页偏移")
    limit: int = Field(..., description="分页上限")


class CostEstDeleteResponse(BaseModel):
    """DELETE /cost-est/results/{id} 响应（物理删除；含删除时间戳）。"""

    model_config = ConfigDict(extra="ignore")

    result_id: uuid.UUID = Field(..., description="cost_est_id（PK）")
    equipment_id: uuid.UUID = Field(..., description="设备 UUID")
    deleted_at: datetime = Field(..., description="删除时间戳")


__all__ = [
    "CostEstCalcBase",
    "CostCorrelationCalcBase",
    # 3 calc
    "SixTenthsRuleCalcRequest",
    "SixTenthsRuleCalcResponse",
    "CepciAdjustmentCalcRequest",
    "CepciAdjustmentCalcResponse",
    "CostCorrelationCalcRequest",
    "CostCorrelationCalcResponse",
    # 5 CRUD
    "CostEstCreateRequest",
    "CostEstUpdateRequest",
    "CostEstResultResponse",
    "CostEstListResponse",
    "CostEstDeleteResponse",
]