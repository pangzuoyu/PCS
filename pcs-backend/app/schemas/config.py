"""Config API request/response schemas（Pydantic v2；Task 2.8）。

与 brief 一致：CreateAssetRequest / AssetResponse / CreateVersionRequest /
ForkVersionRequest / VersionResponse / DiffResponse。Pydantic v2 的
`from_attributes=True` 允许从 ORM 实例直接 model_validate。
"""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import ConfigStatus

#: `config_assets.category` 取值域。DB 侧有 CheckConstraint
#: `config_assets_category_chk` 兜底；这里写出来是为了让**契约可枚举** ——
#: 此前是裸 `str`（词表只在 DB 约束里），客户端只能猜，而前端确实猜错过
#: （它猜成了 FORMULA/COEFFICIENT/…，真实数据永远是 CATEGORY_N ⇒
#: 按类别过滤的 Tabs 在生产上一档都命中不了）。bug-188/189 同族。
#:
#: 取值域见 `合并数据字典.md:905`（`ConfigCategory`）；各值的业务含义见
#: `src/types/configAsset.ts` 里那张带依据的映射表。
ConfigCategory = Literal[
    "CATEGORY_1", "CATEGORY_2", "CATEGORY_3",
    "CATEGORY_4", "CATEGORY_5", "CATEGORY_6",
]


class CreateAssetRequest(BaseModel):
    """POST /assets 请求体。"""

    category: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="资产类别（如 PIPE_CLASS / STREAM_SYMBOL / TEMPLATE）",
    )
    name: str = Field(
        ..., min_length=1, max_length=200, description="资产名称（公司内唯一）"
    )


class AssetResponse(BaseModel):
    """GET /assets/{id} 与 POST /assets 返回结构。"""

    asset_id: UUID = Field(..., description="资产唯一 ID")
    category: ConfigCategory = Field(
        ..., description="资产类别（CATEGORY_1~6；业务含义见合并数据字典）"
    )
    name: str = Field(..., description="资产名称")
    # 此前是裸 `str`，词表只写在 description 里 —— 机器读不到，于是前端
    # 编了一个 `IN_APPROVAL`（bug-188，同 bug-187 一族）。
    status: ConfigStatus = Field(
        ...,
        description=(
            "资产状态（ConfigStatus 5 态）。流转由 ConfigStateMachine 驱动，"
            "对应端点 submit/approve/publish/obsolete。"
        ),
    )
    current_version: str | None = Field(None, description="当前版本号")

    model_config = {"from_attributes": True}


class CreateVersionRequest(BaseModel):
    """POST /assets/{id}/versions 请求体。"""

    content_json: dict[str, Any] = Field(..., description="版本内容 JSON（任意非语义行 schema）")


class ForkVersionRequest(BaseModel):
    """POST /assets/{id}/fork 请求体。"""

    change_note: str | None = Field(None, max_length=500, description="分叉说明")


class VersionResponse(BaseModel):
    """POST /versions、POST /fork 返回结构。"""

    version_id: UUID = Field(..., description="版本唯一 ID")
    asset_id: UUID = Field(..., description="所属资产 ID")
    version_code: str = Field(..., description="版本号（如 1.0、A1）")
    status: str = Field(..., description="版本状态")
    content_json: dict[str, Any] = Field(..., description="版本内容 JSON")
    parent_version_id: UUID | None = Field(None, description="父版本 ID（分叉时记录）")
    change_note: str | None = Field(None, description="变更说明")

    model_config = {"from_attributes": True}


class DiffResponse(BaseModel):
    """GET /assets/{id}/diff 返回结构（深 diff 的三段式）。"""

    added: dict[str, Any] = Field(default_factory=dict, description="新增字段 {path: value}")
    removed: dict[str, Any] = Field(default_factory=dict, description="删除字段 {path: value}")
    changed: dict[str, Any] = Field(default_factory=dict, description="修改字段 {path: {from, to}}")