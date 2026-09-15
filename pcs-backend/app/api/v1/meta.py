"""Meta API 路由 — 4 端点（enums / permissions / error-codes / state-machine）。

P4.5 前端补课 Sprint (P45-0-4)。JWT 鉴权（用户裁决 #1 修订：meta 不再公开）。
"""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from app.api.v1.auth import current_user
from app.services import meta_service

router = APIRouter(prefix="/meta", tags=["meta"])


# === response schemas ===


class EnumItem(BaseModel):
    value: str
    label: str
    order: int
    color: str | None = None
    icon: str | None = None


class EnumsResponse(BaseModel):
    RecordSignStatus: list[EnumItem]
    StreamSignStatus: list[EnumItem]
    DeliverableStatus: list[EnumItem]
    WorkspaceType: list[EnumItem]
    EquipmentStatus: list[EnumItem]
    CalcStatus: list[EnumItem]
    SnapshotStatus: list[EnumItem]


class PermissionItem(BaseModel):
    role: str
    resource: str
    action: str
    permission_code: str
    frontend_behavior: str


class ErrorCodeItem(BaseModel):
    code: str
    http: int
    message: str
    ui_behavior: str


class StateTransition(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_: str = Field(alias="from")
    action: str


class StateMachineResponse(BaseModel):
    transitions: list[StateTransition]
    allowed: dict[str, list[str]]


# === endpoints ===


@router.get("/enums", response_model=EnumsResponse)
def get_enums(
    _user: Annotated[dict[str, Any], Depends(current_user)],
) -> EnumsResponse:
    """7 个 enum 字典（含 9 态全集）；前端 StateBadge 按 module 过滤激活子集。"""
    data = meta_service.get_enums()
    return EnumsResponse(**data)


@router.get("/permissions", response_model=list[PermissionItem])
def get_permissions(
    _user: Annotated[dict[str, Any], Depends(current_user)],
) -> list[PermissionItem]:
    """权限矩阵骨架（V1）。前端 <Can permission="..."> 组件按 frontend_behavior 决定显示/隐藏/禁用。"""  # noqa: E501
    return [PermissionItem(**p) for p in meta_service.get_permissions()]


@router.get("/error-codes", response_model=list[ErrorCodeItem])
def get_error_codes(
    _user: Annotated[dict[str, Any], Depends(current_user)],
) -> list[ErrorCodeItem]:
    """错误码表（V1 骨架）；前端 ErrorState 按 code 渲染可读 message + ui_behavior 决定交互。"""
    return [ErrorCodeItem(**e) for e in meta_service.get_error_codes()]


@router.get("/state-machine", response_model=StateMachineResponse)
def get_state_machine(
    _user: Annotated[dict[str, Any], Depends(current_user)],
) -> StateMachineResponse:
    """9 态状态机迁移表 + allowed 字典；前端 RecordActions 按状态渲染可执行操作。"""
    sm = meta_service.get_state_machine()
    return StateMachineResponse(
        transitions=[StateTransition.model_validate(t) for t in sm["transitions"]],
        allowed=sm["allowed"],
    )