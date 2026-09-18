"""Config API request/response schemas（Pydantic v2；Task 2.8）。

与 brief 一致：CreateAssetRequest / AssetResponse / CreateVersionRequest /
ForkVersionRequest / VersionResponse / DiffResponse。Pydantic v2 的
`from_attributes=True` 允许从 ORM 实例直接 model_validate。
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


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
    category: str = Field(..., description="资产类别")
    name: str = Field(..., description="资产名称")
    status: str = Field(..., description="资产状态（DRAFT/PENDING/APPROVED/PUBLISHED/OBSOLETE）")
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