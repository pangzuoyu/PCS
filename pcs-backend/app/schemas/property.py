"""物性相关的**具名**契约（P10-H · TODO-199）。

## 为什么有这批 schema

TODO-199：4 条端点的契约**本身就是裸 object** ⇒ ⇒ 前端拿不到任何类型 ⇒ ⇒
「形状对不对」只有**消费端**知道 ⇒ ⇒ 漂移抓不到。

⇒ ⇒ 本模块给这 4 条端点补**具名**响应：

| 端点 | 响应 schema |
|---|---|
| `GET /streams/{id}/properties` | `StreamPropertiesResponse` |
| `POST /streams/{id}/properties/estimate` | `StreamPropertiesEstimateResponse` |
| `GET/POST/PATCH /streams/{id}/state-points` | `StreamStatePointResponse`（**已存在**） |
| `POST /streams/{id}/submit` | `StreamTransitionResponse` |

## 物性袋的字段表**只有一份**

`PropertyAutoCompleter.COMMON_FIELDS` ∪ `ESTIMATABLE_FIELDS`（**公开常量**）
⇒ ⇒ `StreamPropertyBag` 用 `create_model` **从它生成** ⇒ ⇒ 抄第二份必然漂
⇒ ⇒ 「哪个 key 是物性」由**服务层**说了算（与 BEDD 的分组表同一手法）。

## 为什么 `extra="allow"`

物性袋里还有**用户手填 / Excel 导入**的键（`user_provided`）⇒ ⇒ 那些键
**不在**服务层的字段表里 ⇒ ⇒ `extra="forbid"` 会把**合法数据**判成非法
⇒ ⇒ 这里**放行**额外键（但**不声明**它们 ⇒ ⇒ 契约里仍是「已知的几个 + 其它」）。
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, create_model

from app.services.property_auto_complete import PropertyAutoCompleter


def _build_property_bag() -> type[BaseModel]:
    """从服务层的字段表生成**物性袋**模型（值 + 逐字段估算标记）。"""
    fields: dict[str, Any] = {}
    for name in sorted(
        PropertyAutoCompleter.COMMON_FIELDS | PropertyAutoCompleter.ESTIMATABLE_FIELDS
    ):
        fields[name] = (float | None, Field(default=None, description=f"物性 {name}"))
        fields[f"estimated_{name}"] = (
            bool | None,
            Field(default=None, description=f"{name} 是否为估算值"),
        )
    fields["estimated"] = (
        bool | None,
        Field(default=None, description="是否**含**估算值（总标记）"),
    )
    model = create_model(
        "StreamPropertyBag",
        __config__=ConfigDict(extra="allow"),
        **fields,
    )
    model.__doc__ = (
        "物性袋（COMMON 物性 + 逐字段估算标记）。"
        "字段表由 `PropertyAutoCompleter` 的字段集生成 ⇒ ⇒ 唯一真相源。"
    )
    return model


#: 物性袋（COMMON 物性 + 估算标记）。
StreamPropertyBag = _build_property_bag()


class StreamPropertiesResponse(BaseModel):
    """`GET /streams/{stream_id}/properties` 响应（SIM-26）。"""

    stream_id: str = Field(..., description="物流 ID")
    user_provided: StreamPropertyBag | None = Field(
        None, description="用户提供（手工 / Excel 入口）"
    )
    calculated: StreamPropertyBag | None = Field(
        None, description="SIM-3 自动补全（Joback / Lee-Kesler / Rackett / CoolProp）"
    )
    effective: StreamPropertyBag | None = Field(
        None, description="实际生效（user_provided > calculated > default）"
    )
    conflict_resolutions: StreamPropertyBag | None = Field(
        None, description="冲突消解输出（`PropertyConflictResolver`）"
    )


class StreamPropertyEstimate(BaseModel):
    """`POST /streams/{id}/properties/estimate` 的**单条**结果。"""

    model_config = ConfigDict(extra="allow")

    cas: str = Field(..., description="CAS 号")
    estimated: bool | None = Field(None, description="是否含估算值（总标记）")


class StreamPropertiesEstimateResponse(BaseModel):
    """`POST /streams/{stream_id}/properties/estimate` 响应（**不入库**）。"""

    results: list[StreamPropertyEstimate] = Field(
        default_factory=list, description="每个 CAS 一条"
    )


class StreamTransitionResponse(BaseModel):
    """`POST /streams/{stream_id}/submit`（送审校对）的响应。

    ⚠️ **只有 5 个字段** —— 这是「转移后**这条记录**的状态」⇒ ⇒ 页面据此
    刷新状态列 ⇒ ⇒ 字段名与 `StreamResponse` 里那几列**逐字一致**（同源）。
    """

    stream_id: str = Field(..., description="物流 ID")
    sign_status: str = Field(..., description="记录门禁 9 态（转移后）")
    approval_step: int | None = Field(
        None, description="IN_APPROVAL 当前步骤（1-based）"
    )
    change_pending_since: str | None = Field(
        None, description="变更待处理起始时间（ISO 8601）"
    )
    change_resolved_at: str | None = Field(
        None, description="变更处理完成时间（ISO 8601）"
    )
