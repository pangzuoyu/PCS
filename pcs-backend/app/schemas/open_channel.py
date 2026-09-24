"""OPEN_CHANNEL Pydantic 请求/响应模型（SPEC §3.2.6 P6-3 Task 32）。

9 schemas：
- 4 calc request/response（Manning / Section / Critical / Jump 各 1 对）
- 5 CRUD：Create / Update / Response / ListResponse / DeleteResponse

字段 snake_case 1:1 与 OpenChannelResult ORM 14 字段一致（task 30 落地）。

端点：
- POST /api/v1/open-channel/manning/calculate
- POST /api/v1/open-channel/section/calculate
- POST /api/v1/open-channel/critical/calculate
- POST /api/v1/open-channel/jump/calculate
- POST   /api/v1/open-channel/results         创建 OpenChannelResult（201）
- GET    /api/v1/open-channel/results         列出（分页）
- GET    /api/v1/open-channel/results/{id}    详情
- PATCH  /api/v1/open-channel/results/{id}    更新（DRAFT/CHANGE_PENDING 可改）
- DELETE /api/v1/open-channel/results/{id}    软删除（→ OBSOLETE）
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

# ───────────────────────────── 公共 base ─────────────────────────────


class OpenChannelCalcBase(BaseModel):
    """OPEN_CHANNEL calc 公共请求/响应字段（4 模块共享）。

    字段（与 OpenChannelResult ORM 14 字段平铺一致）：
    - 必填（7 字段）：channel_type / cross_section_json / flow_rate /
      depth / velocity / slope + project_id / workspace_id / tag_number
      （在 4 calc request 中重复；保留 schema 字段命名一致性）
    - 可选（6 字段）：critical_depth / froude_number / manning_n /
      hydraulic_radius / jump_type / conjugate_depth / energy_loss
      （部分 calc 模块专用）
    """

    model_config = ConfigDict(extra="ignore")

    project_id: uuid.UUID = Field(..., description="项目 ID（isolation key）")
    workspace_id: uuid.UUID = Field(..., description="工作区 ID")
    tag_number: str = Field(..., min_length=1, max_length=64, description="位号")
    channel_type: str = Field(
        ..., description="断面类型（RECT / TRAP / CIRC）"
    )
    cross_section_json: dict[str, Any] = Field(
        ..., description="断面几何 {bottom_width, side_slope, diameter}"
    )
    flow_rate: float = Field(..., ge=0, description="流量 Q（m³/s）")
    depth: float = Field(..., ge=0, description="水深 h（m）")
    velocity: float = Field(..., ge=0, description="流速 v（m/s）")
    slope: float = Field(..., ge=0, description="坡度 S（m/m）")
    # 派生字段（可空，按 calc 模块落库）
    critical_depth: float | None = Field(default=None, ge=0, description="m 临界水深")
    froude_number: float | None = Field(default=None, ge=0, description="Fr 弗劳德数")
    manning_n: float | None = Field(default=None, gt=0, description="糙率")
    hydraulic_radius: float | None = Field(default=None, ge=0, description="m 水力半径")
    jump_type: str | None = Field(default=None, description="WAVY/WEAK/OSCILLATING/STEADY/STRONG")
    conjugate_depth: float | None = Field(default=None, ge=0, description="m 水跃共轭水深")
    energy_loss: float | None = Field(default=None, ge=0, description="m 水跃能量损失")


# ───────────────────────────── 4 calc schemas ─────────────────────────


class ManningCalcRequest(OpenChannelCalcBase):
    """POST /open-channel/manning/calculate 请求。

    字段（maning 模块必需）：channel_type + cross_section_json（含
    bottom_width/side_slope/diameter）+ depth + manning_n + slope。
    manning_n 由 cross_section_json 旁路提供（请求体独立字段）。
    """


class ManningCalcResponse(OpenChannelCalcBase):
    """POST /open-channel/manning/calculate 响应（201）。

    额外含：result_id / record_hash / sign_status / created_at。
    """

    result_id: uuid.UUID = Field(..., description="open_channel_id（PK）")
    record_hash: str | None = Field(
        default=None,
        description="record_hash（ADR-0028 §决策 4 reflection；16 hex）",
    )
    sign_status: str = Field(..., description="签审状态 9 态")
    created_at: datetime = Field(..., description="创建时间")


class SectionCalcRequest(OpenChannelCalcBase):
    """POST /open-channel/section/calculate 请求。

    字段：flow_rate + slope + manning_n + channel_type（无 depth / velocity
    输入；由 calc 反解最优水深）。
    """


class SectionCalcResponse(OpenChannelCalcBase):
    """POST /open-channel/section/calculate 响应（201）。"""

    result_id: uuid.UUID = Field(..., description="open_channel_id（PK）")
    record_hash: str | None = Field(default=None, description="record_hash（16 hex）")
    sign_status: str = Field(..., description="签审状态 9 态")
    created_at: datetime = Field(..., description="创建时间")


class CriticalCalcRequest(OpenChannelCalcBase):
    """POST /open-channel/critical/calculate 请求。

    额外要求：cross_section_json 含 bottom_width（用于 calc_critical_depth）。
    """


class CriticalCalcResponse(OpenChannelCalcBase):
    """POST /open-channel/critical/calculate 响应（201）。

    额外填 critical_depth / froude_number（由 calc 派生）。
    """

    result_id: uuid.UUID = Field(..., description="open_channel_id（PK）")
    record_hash: str | None = Field(default=None, description="record_hash（16 hex）")
    sign_status: str = Field(..., description="签审状态 9 态")
    created_at: datetime = Field(..., description="创建时间")


class JumpCalcRequest(OpenChannelCalcBase):
    """POST /open-channel/jump/calculate 请求。

    额外要求：cross_section_json 含 bottom_width（用于连续方程）。
    depth / velocity 作为跃前水深 + 流速（h1 / v1）。
    """


class JumpCalcResponse(OpenChannelCalcBase):
    """POST /open-channel/jump/calculate 响应（201）。

    额外填 jump_type / conjugate_depth / energy_loss。
    """

    result_id: uuid.UUID = Field(..., description="open_channel_id（PK）")
    record_hash: str | None = Field(default=None, description="record_hash（16 hex）")
    sign_status: str = Field(..., description="签审状态 9 态")
    created_at: datetime = Field(..., description="创建时间")


# ───────────────────────────── 5 CRUD schemas ─────────────────────────


class OpenChannelCreateRequest(BaseModel):
    """POST /open-channel/results 直接创建请求（不走 calc）。

    业务字段子集（PATCH-style）：所有 13 字段均可填；channel_type /
    cross_section_json + 4 平铺（flow_rate / depth / velocity / slope）
    必填。
    """

    model_config = ConfigDict(extra="ignore")

    project_id: uuid.UUID = Field(..., description="项目 ID")
    workspace_id: uuid.UUID = Field(..., description="工作区 ID")
    tag_number: str = Field(..., min_length=1, max_length=64, description="位号")
    channel_type: str = Field(
        ..., description="断面类型（RECT / TRAP / CIRC）"
    )
    cross_section_json: dict[str, Any] = Field(..., description="断面几何")
    flow_rate: float = Field(..., ge=0, description="流量 Q（m³/s）")
    depth: float = Field(..., ge=0, description="水深 h（m）")
    velocity: float = Field(..., ge=0, description="流速 v（m/s）")
    slope: float = Field(..., ge=0, description="坡度 S（m/m）")
    # 可选 6 字段
    critical_depth: float | None = Field(default=None, ge=0)
    froude_number: float | None = Field(default=None, ge=0)
    manning_n: float | None = Field(default=None, gt=0)
    hydraulic_radius: float | None = Field(default=None, ge=0)
    jump_type: str | None = Field(default=None)
    conjugate_depth: float | None = Field(default=None, ge=0)
    energy_loss: float | None = Field(default=None, ge=0)


class OpenChannelUpdateRequest(BaseModel):
    """PATCH /open-channel/results/{id} 请求（partial update）。

    所有字段 optional（PATCH 部分更新）。白名单由 service 层校验。
    ``extra="forbid"``：未知字段 → Pydantic 422，避免 service 层 silent drop。
    """

    model_config = ConfigDict(extra="forbid")

    channel_type: str | None = Field(default=None)
    cross_section_json: dict[str, Any] | None = Field(default=None)
    flow_rate: float | None = Field(default=None, ge=0)
    depth: float | None = Field(default=None, ge=0)
    velocity: float | None = Field(default=None, ge=0)
    slope: float | None = Field(default=None, ge=0)
    critical_depth: float | None = Field(default=None, ge=0)
    froude_number: float | None = Field(default=None, ge=0)
    manning_n: float | None = Field(default=None, gt=0)
    hydraulic_radius: float | None = Field(default=None, ge=0)
    jump_type: str | None = Field(default=None)
    conjugate_depth: float | None = Field(default=None, ge=0)
    energy_loss: float | None = Field(default=None, ge=0)


class OpenChannelResultResponse(OpenChannelCalcBase):
    """GET /open-channel/results/{id} 响应（含溯源 + 业务字段）。

    字段映射（ORM → schema）：
    - ORM open_channel_id → schema result_id（PK 重命名；前端统一用 result_id）
    """

    result_id: uuid.UUID = Field(..., description="open_channel_id（PK）")
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
        """ORM → schema 字段映射：ORM open_channel_id → schema result_id。

        支持 dict 输入（来自 model_validate(record, from_attributes=True) 透传
        的 ORM 属性访问）；attr 输入（record.xxx）也走同样的 getattr。
        """
        if data is None:
            return data
        open_channel_id = getattr(data, "open_channel_id", None)
        if open_channel_id is not None and not isinstance(data, dict):
            try:
                data.result_id = open_channel_id  # noqa: B010
            except AttributeError:
                # 不可 set（如 MagicMock 已被 frozen）→ 转 dict 处理
                if hasattr(data, "__dict__"):
                    d = dict(data.__dict__)
                    d["result_id"] = open_channel_id
                    return d
        return data


class OpenChannelListResponse(BaseModel):
    """GET /open-channel/results 列表响应。

    字段：
    - items: OpenChannelResultResponse 列表
    - total: 命中条数（受 include_obsolete 影响）
    - skip / limit: 分页参数回显
    """

    model_config = ConfigDict(extra="ignore")

    items: list[OpenChannelResultResponse] = Field(
        ..., description="OpenChannelResult 列表"
    )
    total: int = Field(..., description="命中条数")
    skip: int = Field(..., description="分页偏移")
    limit: int = Field(..., description="分页上限")


class OpenChannelDeleteResponse(BaseModel):
    """DELETE /open-channel/results/{id} 响应。

    字段：result_id + tag_number（含 __OBSOLETE_<ts> 后缀）+ sign_status +
    deleted_at。
    """

    model_config = ConfigDict(extra="ignore")

    result_id: uuid.UUID = Field(..., description="open_channel_id（PK）")
    tag_number: str = Field(
        ..., description="位号（含 __OBSOLETE_<ts> 后缀）"
    )
    sign_status: str = Field(..., description="签审状态（已改为 OBSOLETE）")
    deleted_at: datetime = Field(..., description="删除时间（updated_at）")


__all__ = [
    "OpenChannelCalcBase",
    # 4 calc
    "ManningCalcRequest",
    "ManningCalcResponse",
    "SectionCalcRequest",
    "SectionCalcResponse",
    "CriticalCalcRequest",
    "CriticalCalcResponse",
    "JumpCalcRequest",
    "JumpCalcResponse",
    # 5 CRUD
    "OpenChannelCreateRequest",
    "OpenChannelUpdateRequest",
    "OpenChannelResultResponse",
    "OpenChannelListResponse",
    "OpenChannelDeleteResponse",
]