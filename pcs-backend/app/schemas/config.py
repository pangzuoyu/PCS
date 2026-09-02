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

    category: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=200)


class AssetResponse(BaseModel):
    """GET /assets/{id} 与 POST /assets 返回结构。"""

    asset_id: UUID
    category: str
    name: str
    status: str
    current_version: str | None = None

    model_config = {"from_attributes": True}


class CreateVersionRequest(BaseModel):
    """POST /assets/{id}/versions 请求体。"""

    content_json: dict[str, Any]


class ForkVersionRequest(BaseModel):
    """POST /assets/{id}/fork 请求体。"""

    change_note: str | None = None


class VersionResponse(BaseModel):
    """POST /versions、POST /fork 返回结构。"""

    version_id: UUID
    asset_id: UUID
    version_code: str
    status: str
    content_json: dict[str, Any]
    parent_version_id: UUID | None = None
    change_note: str | None = None

    model_config = {"from_attributes": True}


class DiffResponse(BaseModel):
    """GET /assets/{id}/diff 返回结构（深 diff 的三段式）。"""

    added: dict[str, Any] = {}
    removed: dict[str, Any] = {}
    changed: dict[str, Any] = {}