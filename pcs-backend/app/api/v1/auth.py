"""POST /api/v1/auth/login + GET /me + POST /refresh + POST /logout。

JWT 由 app.core.security 编解码；凭据由 app.services.ldap_client 验证。
Task 10 会在 env != production 时启用 mock 旁路。
"""

from __future__ import annotations

from typing import Annotated, Any

import jwt
from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field

from app.core.errors import PcsError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    is_jti_revoked,
    revoke_jti,
)
from app.services.ldap_client import LdapAuthError, authenticate, resolve_role

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str = Field(
        ..., min_length=1, max_length=100, description="登录用户名（LDAP uid）"
    )
    # P0-MED-006 fix（2026-09-18）：password min_length 1（不允许空字符串，
    # 避免爆破时 "" 通过校验；max_length 200 与 LDAP DN 边界对齐）。
    password: str = Field(
        ..., min_length=1, max_length=200, description="登录密码（LDAP 绑定）"
    )


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    role: str
    username: str


class RefreshRequest(BaseModel):
    refresh_token: str


class RefreshResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LogoutRequest(BaseModel):
    """logout 请求体。可选传 refresh_token 以吊销 JTI；不传则仅 204。"""

    refresh_token: str | None = None


class MeResponse(BaseModel):
    username: str
    role: str


def _decode_bearer(authorization: str) -> dict[str, Any]:
    if not authorization.lower().startswith("bearer "):
        raise PcsError(
            code="MISSING_BEARER", message="Authorization: Bearer <token>", status=401
        )
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = decode_token(token)
    except jwt.PyJWTError as e:
        raise PcsError(code="INVALID_TOKEN", message=str(e), status=401) from e
    if payload.get("type") != "access":
        raise PcsError(
            code="WRONG_TOKEN_TYPE", message="not an access token", status=401
        )
    return payload


def current_user(authorization: Annotated[str | None, Header()] = None) -> dict[str, Any]:
    """FastAPI 依赖：取 Authorization Bearer JWT 解析 payload。

    步骤：
    1. 无 Authorization header → MISSING_BEARER 401
    2. 调 _decode_bearer 解析 JWT（HS256 + 密钥校验 + 过期检查）
    3. 返回 payload dict（含 user_id / role / exp / iat 等）

    返回 _Actor TypedDict（FastAPI Depends 注入端点）。
    与 login 区别：login 颁发 JWT；current_user 解析验证。
    """
    if not authorization:
        raise PcsError(
            code="MISSING_BEARER", message="Authorization: Bearer <token>", status=401
        )
    return _decode_bearer(authorization)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest) -> TokenResponse:
    """POST /login：LDAP 登录换取 access/refresh token。

    步骤：
    1. authenticate(username, password) 走 LDAP bind（service 层封装）
       - LDAP 失败（LdapAuthError）→ INVALID_CREDENTIALS 401
    2. resolve_role(user.groups) 由 LDAP 组映射到内部角色
       （DESIGNER / PROCESS_CONTROLLER / REVIEWER / APPROVER / SYSTEM_ADMIN）
    3. create_access_token / create_refresh_token 签发 JWT 对（HS256）
    4. 不写 Audit（login 是公开端点，无 user_id 上下文）

    返回 TokenResponse：{access_token, refresh_token, role, username}。
    """
    try:
        user = authenticate(body.username, body.password)
    except LdapAuthError as e:
        raise PcsError(code="INVALID_CREDENTIALS", message=str(e), status=401) from e
    role = resolve_role(user.groups)
    return TokenResponse(
        access_token=create_access_token(subject=user.username, role=role),
        refresh_token=create_refresh_token(subject=user.username, role=role),
        role=role,
        username=user.username,
    )


@router.get("/me", response_model=MeResponse)
def me(
    user: Annotated[dict[str, Any], Depends(current_user)],
) -> MeResponse:
    return MeResponse(username=user["sub"], role=user["role"])


@router.post("/refresh", response_model=RefreshResponse)
def refresh(body: RefreshRequest) -> RefreshResponse:
    """刷新 token：旧 refresh 一次性使用，签发新 access + 新 refresh。

    安全约束：
    1. JWT 解码失败 → INVALID_REFRESH（401）
    2. type != 'refresh' → WRONG_TOKEN_TYPE（401）
    3. 缺 role claim（P0-2 防回归）→ INVALID_REFRESH（401）
    4. JTI 已被吊销（重放/截获）→ INVALID_REFRESH（401，H-P0-2 防重放）
    5. 旧 JTI 一次性使用：成功签发后立即 revoke 旧 JTI，缩小泄露窗口
    """
    try:
        payload = decode_token(body.refresh_token)
    except jwt.PyJWTError as e:
        raise PcsError(code="INVALID_REFRESH", message=str(e), status=401) from e
    if payload.get("type") != "refresh":
        raise PcsError(
            code="WRONG_TOKEN_TYPE", message="not a refresh token", status=401
        )
    # P0-2 防回归：refresh token 必须含 role 字段；缺则视为伪造/过期格式，拒绝授权
    role = payload.get("role")
    if not role:
        raise PcsError(
            code="INVALID_REFRESH",
            message="refresh token missing role claim",
            status=401,
        )
    # H-P0-2：refresh token JTI 吊销检查 + 轮换。旧 refresh 一次性使用后吊销，
    # 重放/截获旧 refresh → 401 INVALID_REFRESH。轮换可缩小 token 泄露窗口。
    old_jti = payload.get("jti")
    if old_jti and is_jti_revoked(old_jti):
        raise PcsError(
            code="INVALID_REFRESH",
            message="refresh token revoked",
            status=401,
        )
    if old_jti:
        revoke_jti(old_jti)
    sub = payload["sub"]
    return RefreshResponse(
        access_token=create_access_token(subject=sub, role=role),
        refresh_token=create_refresh_token(subject=sub, role=role),
    )


@router.post("/logout", status_code=204)
def logout(body: LogoutRequest | None = None) -> None:
    """H-P0-3：logout 接收可选 refresh_token，吊销其 JTI；不传则幂等 204。

    旧 refresh 永不再可用（即使没到 exp）；前端无需记忆，多副本部署需切 Redis set。
    """
    if body is not None and body.refresh_token:
        try:
            payload = decode_token(body.refresh_token)
        except jwt.PyJWTError:
            # 无效/伪造 token：仍返回 204，避免泄露 token 状态（防御侧信道）
            return None
        if payload.get("type") == "refresh":
            jti = payload.get("jti")
            if jti:
                revoke_jti(jti)
    return None
