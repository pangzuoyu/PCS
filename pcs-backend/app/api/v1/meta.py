"""Meta API 路由 — 4 端点 + 1 CSV 导出（enums / permissions / error-codes /
state-machine / permissions.csv）。

P4.5 前端补课 Sprint (P45-0-4) + V1.1 (P45-0-4.5)。JWT 鉴权。
"""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Response
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
    DeliverableSignStatus: list[EnumItem]
    WorkspaceType: list[EnumItem]
    EquipmentStatus: list[EnumItem]
    CalcStatus: list[EnumItem]
    ActualDataStatus: list[EnumItem]
    SnapshotStatus: list[EnumItem]
    ConfigStatus: list[EnumItem]
    ConfigTransition: list[EnumItem]
    PipeType: list[EnumItem]
    CheckResult: list[EnumItem]
    PumpOperation: list[EnumItem]
    DesignStage: list[EnumItem]
    FlowPattern: list[EnumItem]
    TwoPhaseCheck: list[EnumItem]
    StreamDataMode: list[EnumItem]
    StreamCaseType: list[EnumItem]
    StatePointCaseType: list[EnumItem]


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
    to: str
    allowed_roles: list[str]
    preconditions: list[str]
    side_effects: list[str]


class StateMachineResponse(BaseModel):
    transitions: list[StateTransition]
    allowed: dict[str, list[str]]


# === endpoints ===


@router.get("/enums", response_model=EnumsResponse)
def get_enums(
    _user: Annotated[dict[str, Any], Depends(current_user)],
) -> EnumsResponse:
    """19 组枚举字典；前端 StateBadge / Select / 筛选用。"""
    data = meta_service.get_enums()
    return EnumsResponse(**data)


@router.get("/permissions", response_model=list[PermissionItem])
def get_permissions(
    _user: Annotated[dict[str, Any], Depends(current_user)],
) -> list[PermissionItem]:
    """权限矩阵（V1.1 全集）；前端 <Can permission="..."> 按 frontend_behavior 显示/禁用。"""
    return [PermissionItem(**p) for p in meta_service.get_permissions()]


@router.get("/permissions.csv")
def get_permissions_csv(
    _user: Annotated[dict[str, Any], Depends(current_user)],
) -> Response:
    """权限矩阵 CSV 导出；前端可下载做权限审计。"""
    csv = meta_service.get_permissions_csv()
    return Response(
        content=csv,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=permissions.csv"},
    )


@router.get("/error-codes", response_model=list[ErrorCodeItem])
def get_error_codes(
    _user: Annotated[dict[str, Any], Depends(current_user)],
) -> list[ErrorCodeItem]:
    """错误码全集（全仓 AST 派生）；前端 ErrorState 按 code 渲染可读 message。"""
    return [ErrorCodeItem(**e) for e in meta_service.get_error_codes()]


@router.get("/state-machine", response_model=StateMachineResponse)
def get_state_machine(
    _user: Annotated[dict[str, Any], Depends(current_user)],
) -> StateMachineResponse:
    """13 事件 × 9 态迁移表 + 字段；前端 RecordActions 按状态渲染可执行操作。"""
    sm = meta_service.get_state_machine()
    return StateMachineResponse(
        transitions=[StateTransition.model_validate(t) for t in sm["transitions"]],
        allowed=sm["allowed"],
    )