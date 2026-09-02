"""Config API — 7 端点（Task 2.8 / P2 Sprint 1.7）。

端点：
    POST   /api/v1/config/assets                  # 创建 config_asset (DRAFT)
    POST   /api/v1/config/assets/{id}/versions    # 新版本（DRAFT）
    POST   /api/v1/config/assets/{id}/fork        # 从 PUBLISHED fork 新 DRAFT 版本
    POST   /api/v1/config/assets/{id}/submit      # DRAFT → PENDING
    POST   /api/v1/config/assets/{id}/approve     # PENDING → APPROVED（CATEGORY_2 双段签）
    POST   /api/v1/config/assets/{id}/publish     # APPROVED → PUBLISHED（unit_tests 校验）
    POST   /api/v1/config/assets/{id}/obsolete    # → OBSOLETE
    GET    /api/v1/config/assets/{id}/diff?v1&v2  # 版本 diff（audit 记录）

设计要点（与 brief 偏差 / 防御性）：

1. **`commit_or_rollback` 用 async with** — carry-forward #1 已规定其是
   `asynccontextmanager`，不是普通 async 函数；本文件用 `async with` 包裹
   业务代码，事务边界明确。

2. **`Depends(get_db)`** — carry-forward #2 指出 `get_session` 不存在；正确
   的 async session 依赖来自 `app.db.session.get_db`。

3. **`current_actor` 依赖替代 brief 的 `current_user`** — carry-forward #3：
   `current_user` 返回 dict（含 `sub`/`role`），缺 `.user_id: UUID` 与
   `.roles: Iterable[str]`（`@require_role` 装饰器必需）。本文件末尾的
   `current_actor` 把 JWT payload 解码后包装成 `_Actor`：
     - `user_id`：优先取 JWT `user_id` 声明；缺省时用 uuid5(NAMESPACE_DNS, sub)
       （确定性，方便测试）。
     - `role` / `roles`：直接取 JWT `role`（roles = [role]，与 ACL 兼容）。

4. **ACL 改为内联 `require_roles(user, *roles)` 调用** — `app.core.acl` 的
   `require_role` 装饰器通过 `functools.wraps` 替换函数签名，导致 FastAPI
   的依赖注入无法识别内层 `user=Depends(current_actor)`。本文件改为
   端点第一行内联调用 helper（仍然复用 `_user_attr` 的检查语义）。

5. **`asset.current_version` 是字符串列**，每次引用 `.status` / `.X` 都得
   显式按 version_code 查 ConfigVersion — carry-forward #8。
"""

from __future__ import annotations

import uuid as _uuid
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Annotated, Any
from uuid import UUID

import jwt as _jwt
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import _decode_bearer
from app.core.acl import _user_attr
from app.core.commit_or_rollback import commit_or_rollback
from app.core.errors import PcsError
from app.db.session import get_db
from app.models.config_domain import ConfigAsset, ConfigVersion
from app.models.enums import ConfigStatus, ConfigTransition
from app.schemas.config import (
    AssetResponse,
    CreateAssetRequest,
    CreateVersionRequest,
    DiffResponse,
    ForkVersionRequest,
    VersionResponse,
)
from app.services.cia_engine import CIAEngine
from app.services.config_service import ConfigService
from app.services.config_state_machine import (
    ConfigStateMachine,
    InvalidTransitionError,
)
from app.services.formula_engine import FormulaEngine
from app.services.formula_service import FormulaService
from app.services.report_service import ConfigAssetReport, ReportService

router = APIRouter(prefix="/config", tags=["config"])


# ---------------------------------------------------------------------------
# ACL helper（内联版）
# ---------------------------------------------------------------------------


def require_roles(user: _Actor, *allowed_roles: str) -> None:
    """等价于 `app.core.acl.require_role` 装饰器，但不影响 FastAPI 签名。

    失败抛 HTTPException(403) — 与 brief 测试断言一致。
    """
    roles: Iterable[str] | None = _user_attr(user, "roles")
    if roles is None or not any(r in allowed_roles for r in roles):
        raise HTTPException(
            status_code=403,
            detail=f"需要角色 {list(allowed_roles)}",
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _load_asset(db: AsyncSession, asset_id: UUID) -> ConfigAsset:
    asset = await db.get(ConfigAsset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail=f"未找到 asset {asset_id}")
    return asset


async def _load_current_version(
    db: AsyncSession, asset: ConfigAsset
) -> ConfigVersion:
    """按 asset.current_version (字符串列) 查 ConfigVersion。

    缺 version_code 或查不到 → 404。
    """
    if not asset.current_version:
        raise HTTPException(status_code=404, detail="asset 缺少 current_version")
    version = (
        await db.execute(
            select(ConfigVersion).where(
                ConfigVersion.asset_id == asset.asset_id,
                ConfigVersion.version_code == asset.current_version,
            )
        )
    ).scalar_one_or_none()
    if version is None:
        raise HTTPException(
            status_code=404,
            detail=f"未找到 ConfigVersion version_code={asset.current_version}",
        )
    return version


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/assets", status_code=201, response_model=AssetResponse)
async def create_asset(
    req: CreateAssetRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AssetResponse:
    """创建 config_asset（status=DRAFT）+ 首个 v1 ConfigVersion。"""
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    async with commit_or_rollback(db):
        asset = await ConfigService(db).create_asset(
            category=req.category,
            name=req.name,
            actor=user.user_id,
        )
    return AssetResponse.model_validate(asset)


@router.post("/assets/{asset_id}/versions", status_code=201, response_model=VersionResponse)
async def create_version(
    asset_id: UUID,
    req: CreateVersionRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> VersionResponse:
    """为 DRAFT/PENDING/APPROVED asset 追加新 ConfigVersion。

    PUBLISHED 资产必须走 /fork。
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    asset = await _load_asset(db, asset_id)
    current = await _load_current_version(db, asset)
    if current.status == ConfigStatus.PUBLISHED.value:
        raise HTTPException(
            status_code=409, detail="PUBLISHED asset 必须用 /fork 创建新版本"
        )
    expression = req.content_json.get("expression", "")
    parameters_section = req.content_json.get("parameters_json") or {}
    formula_version = FormulaEngine.compute_version_hash(
        expression=expression,
        parameters=parameters_section,
    )
    async with commit_or_rollback(db):
        version = await ConfigService(db).create_version(
            asset,
            content_json=req.content_json,
            formula_version=formula_version,
            actor=user.user_id,
        )
    return VersionResponse.model_validate(version)


@router.post("/assets/{asset_id}/fork", status_code=201, response_model=VersionResponse)
async def fork_version(
    asset_id: UUID,
    req: ForkVersionRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> VersionResponse:
    """从 PUBLISHED asset 的当前 version fork 出新 DRAFT ConfigVersion。

    非 PUBLISHED 资产禁止 fork（409）。
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    asset = await _load_asset(db, asset_id)
    current = await _load_current_version(db, asset)
    if current.status != ConfigStatus.PUBLISHED.value:
        raise HTTPException(status_code=409, detail="只能 fork PUBLISHED 版本")
    src_formula_version = (
        current.content_json.get("formula_version") if current.content_json else None
    )
    async with commit_or_rollback(db):
        version = await ConfigService(db).fork_from_published(
            asset,
            change_note=req.change_note,
            formula_version=src_formula_version,
            actor=user.user_id,
        )
    return VersionResponse.model_validate(version)


@router.post("/assets/{asset_id}/submit", response_model=AssetResponse)
async def submit(
    asset_id: UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AssetResponse:
    """DRAFT → PENDING。"""
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    asset = await _load_asset(db, asset_id)
    current = await _load_current_version(db, asset)
    sm = ConfigStateMachine(db)
    async with commit_or_rollback(db):
        try:
            await sm.transition(
                asset,
                current,
                action=ConfigTransition.SUBMIT,
                actor=user,
            )
        except InvalidTransitionError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
    return AssetResponse.model_validate(asset)


@router.post("/assets/{asset_id}/approve", response_model=AssetResponse)
async def approve(
    asset_id: UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AssetResponse:
    """PENDING → APPROVED（CATEGORY_2 走 record_approval 双行；其它单层）。

    brief 仅传 `role=user.primary_role` 缺 `approver_id` / `decision`；
    此处补全：approver_id=user.user_id、decision=APPROVED。
    """
    require_roles(user, "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    asset = await _load_asset(db, asset_id)
    current = await _load_current_version(db, asset)
    sm = ConfigStateMachine(db)
    async with commit_or_rollback(db):
        try:
            await sm.record_approval(
                asset,
                current,
                approver_id=user.user_id,
                role=user.role,
                decision="APPROVED",
                actor=user,
            )
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=409, detail=str(exc)) from exc
    return AssetResponse.model_validate(asset)


@router.post("/assets/{asset_id}/publish", response_model=AssetResponse)
async def publish(
    asset_id: UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AssetResponse:
    """APPROVED → PUBLISHED。

    CATEGORY_2 公式资产必须先 unit_tests 100% pass，否则 422。
    """
    require_roles(user, "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    asset = await _load_asset(db, asset_id)
    current = await _load_current_version(db, asset)
    if asset.category == "CATEGORY_2":
        formula_service = FormulaService(db)
        result = await formula_service.run_unit_tests(asset)
        if result.passed != result.total:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"公式 unit_tests 未通过 {result.passed}/{result.total}"
                ),
            )
    sm = ConfigStateMachine(db)
    async with commit_or_rollback(db):
        try:
            await sm.transition(
                asset,
                current,
                action=ConfigTransition.PUBLISH,
                actor=user,
            )
            # Sprint 3 反向传播：PUBLISH 后把依赖该版本的下游记录标 STALE
            await CIAEngine(db).propagate_from_source(
                "config_version", current.version_id
            )
        except InvalidTransitionError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
    return AssetResponse.model_validate(asset)


@router.post("/assets/{asset_id}/obsolete", response_model=AssetResponse)
async def obsolete(
    asset_id: UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AssetResponse:
    """→ OBSOLETE。允许从 DRAFT / APPROVED / PUBLISHED 直接出局。"""
    require_roles(user, "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    asset = await _load_asset(db, asset_id)
    current = await _load_current_version(db, asset)
    sm = ConfigStateMachine(db)
    async with commit_or_rollback(db):
        try:
            await sm.transition(
                asset,
                current,
                action=ConfigTransition.OBSOLETE,
                actor=user,
            )
        except InvalidTransitionError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
    return AssetResponse.model_validate(asset)


@router.get("/assets/status-report", response_model=list[ConfigAssetReport])
async def asset_status_report(
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[ConfigAssetReport]:
    """配置资产按 category × status 分布报表（P2 Sprint 3 Task 5.1）。

    按 version 聚合（不取 latest）；按 category 字母序；空 DB 返回 ``[]``。
    ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN。
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    return await ReportService(db).config_asset_status()


@router.get("/assets/{asset_id}/diff", response_model=DiffResponse)
async def diff(
    asset_id: UUID,
    v1: UUID,
    v2: UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DiffResponse:
    """两版本 content_json 的 shallow diff；同时落 CONFIG_VERSION_DIFF_VIEWED 审计。"""
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    if v1 == v2:
        raise HTTPException(status_code=400, detail="v1 和 v2 不能相同")
    async with commit_or_rollback(db):
        delta = await ConfigService(db).diff_versions(
            asset_id,
            v1,
            v2,
            actor=user.user_id,
        )
    return DiffResponse(**delta)


# ---------------------------------------------------------------------------
# Actor wrapper（carry-forward #3 的简化方案）
# ---------------------------------------------------------------------------


@dataclass
class _Actor:
    """最小 actor 包装 — 同时满足 ConfigStateMachine (.user_id) 与
    ACL 检查 (.roles) 的 duck-typing 契约。"""

    user_id: UUID
    username: str
    role: str

    @property
    def roles(self) -> list[str]:
        return [self.role]


def current_actor(
    authorization: Annotated[str | None, Header()] = None,
) -> _Actor:
    """从 Authorization: Bearer <token> 解 JWT，构造 actor；与 ACL helper 兼容。

    优先读 JWT 的 `user_id` 声明；缺省时用 uuid5(NAMESPACE_DNS, sub) 派生
    （确定性，便于测试；生产建议改由 LDAP 同步时把 user_id 写入 token）。
    """
    if not authorization:
        raise PcsError(
            code="MISSING_BEARER",
            message="Authorization: Bearer <token>",
            status=401,
        )
    try:
        payload: dict[str, Any] = _decode_bearer(authorization)
    except _jwt.PyJWTError as e:  # pragma: no cover — _decode_bearer 已转 PcsError
        raise PcsError(code="INVALID_TOKEN", message=str(e), status=401) from e
    sub = payload.get("sub", "anonymous")
    role = payload.get("role", "DESIGNER")
    user_id_raw = payload.get("user_id")
    if user_id_raw:
        try:
            user_id = UUID(str(user_id_raw))
        except (ValueError, TypeError):
            user_id = _uuid.uuid5(_uuid.NAMESPACE_DNS, sub)
    else:
        user_id = _uuid.uuid5(_uuid.NAMESPACE_DNS, sub)
    return _Actor(user_id=user_id, username=sub, role=role)


__all__ = ["current_actor", "router", "require_roles"]