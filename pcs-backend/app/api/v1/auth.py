"""POST /api/v1/auth/login + GET /me + POST /refresh + POST /logout。

JWT 由 app.core.security 编解码；凭据由 app.services.ldap_client 验证。
Task 10 会在 env != production 时启用 mock 旁路。
"""

from __future__ import annotations

import ipaddress
import uuid
from typing import Annotated, Any

import jwt
from fastapi import APIRouter, Depends, Header, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import PcsError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    is_jti_revoked,
    revoke_jti,
)
from app.db.session import get_db
from app.services.ldap_client import LdapAuthError, authenticate, resolve_role

# 与 Depends(current_actor) 推导保持一致: 优先从 JWT user_id 声明读取, 缺省回退
# uuid5(NAMESPACE_DNS, sub). 前端 /auth/me 拿到权威 actor id, 避免自行派生分叉.
_UUID5_NAMESPACE_DNS = uuid.NAMESPACE_DNS


def _derive_user_id(actor: dict[str, Any]) -> uuid.UUID:
    """权威 user_id 派生: JWT user_id 声明优先, 缺省回退 uuid5(NAMESPACE_DNS, sub)."""
    raw = actor.get("user_id")
    if raw:
        return uuid.UUID(str(raw))
    return uuid.uuid5(_UUID5_NAMESPACE_DNS, str(actor["sub"]))

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    """登录请求体（POST /auth/login）。

    业务：username 是 LDAP uid（min_length=1 防空）；password 必填（1~200
    字符防爆破）；登录走 LDAP bind + 派生 role；mock 模式按 MOCK_USERS 表。
    """

    username: str = Field(
        ..., min_length=1, max_length=100, description="登录用户名（LDAP uid）"
    )
    # P0-MED-006 fix（2026-09-18）：password min_length 1（不允许空字符串，
    # 避免爆破时 "" 通过校验；max_length 200 与 LDAP DN 边界对齐）。
    password: str = Field(
        ..., min_length=1, max_length=200, description="登录密码（LDAP 绑定）"
    )


class TokenResponse(BaseModel):
    """JWT token 响应（POST /auth/login 响应体）。

    业务：access_token + refresh_token（bearer 类型）；role + username 同步返回
    （前端省去再调 /me 取角色）。
    """

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    role: str
    username: str


class RefreshRequest(BaseModel):
    """刷新 token 请求体（POST /auth/refresh）。

    业务：仅传 refresh_token；服务端校验 jti + 有效期后颁发新 access + refresh。
    """

    refresh_token: str


class RefreshResponse(BaseModel):
    """刷新 token 响应（POST /auth/refresh 响应体）。

    业务：返回新 access_token + 新 refresh_token（jti 轮换防重放）。
    """

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LogoutRequest(BaseModel):
    """logout 请求体。可选传 refresh_token 以吊销 JTI；不传则仅 204。"""

    refresh_token: str | None = None


class MeResponse(BaseModel):
    """当前用户信息响应（GET /auth/me 端点）。

    业务：返回当前 token 用户的 username + role + user_id；
    user_id 优先取 JWT user_id 声明，缺省回退 uuid5(NAMESPACE_DNS, username)
    (与 Depends(current_actor) 推导保持一致, 让前端拿到权威 actor id, 避免
    frontend 自行 deterministicUuid 与 backend uuid5 派生分叉).
    """

    username: str
    role: str
    user_id: uuid.UUID


def _decode_bearer(authorization: str) -> dict[str, Any]:
    """从 Authorization Bearer 头解析 + 校验 JWT token。

    业务：authorization 必须以 "Bearer " 开头；decode_token 失败按成因分流
    —— 过期抛 EXPIRED_TOKEN、签名不符/伪造抛 INVALID_TOKEN（均 401）；
    type 必须为 "access"（防 refresh 混用）。
    """


    if not authorization.lower().startswith("bearer "):
        raise PcsError(
            code="MISSING_BEARER", message="Authorization: Bearer <token>", status=401
        )
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError as e:
        # TODO-007: 过期与无效分开报。过期是正常生命周期终点（前端可静默
        # refresh 一次）；无效是签名不符 / 伪造（该拒绝并告警）。此前两者
        # 都映射 INVALID_TOKEN，前端无法区分。
        raise PcsError(code="EXPIRED_TOKEN", message=str(e), status=401) from e
    except jwt.InvalidTokenError as e:
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


def _normalize_ip(raw: str | None) -> str | None:
    """把 client host 规整成 INET 列能接受的形式，非法则返回 None。

    `audit_logs.ip` 是 PostgreSQL INET 类型，**只接受合法 IP 字面量**。
    而 `request.client.host` 在 TestClient 下是 `"testclient"`；unix socket
    场景也会给出非 IP 串。直接塞进去会抛
    `DataError: 'testclient' does not appear to be an IPv4 or IPv6 address`，
    进而让**登录端点 500** —— 审计写入不该有能力打挂登录本身。
    """
    if not raw:
        return None
    try:
        return str(ipaddress.ip_address(raw))
    except ValueError:
        return None


async def _record_login_audit(
    db: AsyncSession,
    *,
    action: str,
    username: str,
    ip: str | None,
    user_id: uuid.UUID | None = None,
    reason: str | None = None,
) -> None:
    """记一条登录审计（成功/失败共用）。

    失败也要记：没有失败记录，暴力破解就完全无痕。username 记明文是因为
    审计的用途正是「谁在试」—— 失败时往往还不知道哪个是有效账号。
    """
    from app.services.audit_service import AuditService

    detail: dict[str, Any] = {"username": username}
    if reason:
        detail["reason"] = reason
    await AuditService(db).write(
        action=action,
        resource_type="AUTH",
        resource_id=username,
        user_id=user_id,
        detail=detail,
        ip=_normalize_ip(ip),
    )
    await db.commit()


# TODO-006 认证加固：同 IP 每分钟最多 10 次登录尝试。
# 单实例滑动窗口（`_sliding_window_rate_limit`），多实例部署需换 Redis
# —— 与 util 端点同一约束，模块 docstring 已标注。
_LOGIN_RATE_LIMIT = 10
_LOGIN_RATE_WINDOW_SECONDS = 60.0


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """POST /login：LDAP 登录换取 access/refresh token。

    步骤：
    1. 按 IP 限流（10 次/分钟）—— 防暴力破解
    2. authenticate(username, password) 走 LDAP bind（service 层封装）
       - LDAP 失败（LdapAuthError）→ INVALID_CREDENTIALS 401
    3. resolve_role(user.groups) 由 LDAP 组映射到内部角色
       （DESIGNER / PROCESS_CONTROLLER / REVIEWER / APPROVER / SYSTEM_ADMIN）
    4. create_access_token / create_refresh_token 签发 JWT 对（HS256）
    5. 成功/失败**都**写 audit_logs（LOGIN_SUCCESS / LOGIN_FAILED + ip）

    返回 TokenResponse：{access_token, refresh_token, role, username}。

    ⚠️ 与旧版差异：端点由同步改异步并依赖 DB —— 审计落库需要 session。
    代价是 DB 不可用时登录一并失败（fail-closed on audit）。
    对 PCS 这类几乎所有端点都依赖 DB 的系统是可接受的。
    """
    client_ip = request.client.host if request.client else None
    from app.services._sliding_window_rate_limit import check_rate_limit

    if not await check_rate_limit(
        f"auth_login:{client_ip}",
        limit=_LOGIN_RATE_LIMIT,
        window_seconds=_LOGIN_RATE_WINDOW_SECONDS,
    ):
        raise PcsError(
            code="LOGIN_RATE_LIMITED",
            message=f"登录尝试过于频繁，请稍后再试 (limit {_LOGIN_RATE_LIMIT}/min/IP)",
            status=429,
        )
    try:
        user = authenticate(body.username, body.password)
    except LdapAuthError as e:
        await _record_login_audit(
            db, action="LOGIN_FAILED", username=body.username, ip=client_ip,
            reason=str(e),
        )
        raise PcsError(code="INVALID_CREDENTIALS", message=str(e), status=401) from e
    role = resolve_role(user.groups)
    # P7-7+ actor 上下文一致: 在 JWT payload 嵌入 user_id 声明, 让
    # Depends(current_actor) 直接取到权威 id (避免每次回退 uuid5 派生).
    user_id = uuid.uuid5(_UUID5_NAMESPACE_DNS, user.username)
    await _record_login_audit(
        db, action="LOGIN_SUCCESS", username=user.username, ip=client_ip,
        user_id=user_id,
    )
    return TokenResponse(
        access_token=create_access_token(
            subject=user.username, role=role, extra={"user_id": str(user_id)},
        ),
        refresh_token=create_refresh_token(
            subject=user.username, role=role, extra={"user_id": str(user_id)},
        ),
        role=role,
        username=user.username,
    )


@router.get("/me", response_model=MeResponse)
def me(
    user: Annotated[dict[str, Any], Depends(current_user)],
) -> MeResponse:
    return MeResponse(
        username=user["sub"],
        role=user["role"],
        user_id=_derive_user_id(user),
    )


@router.post("/refresh", response_model=RefreshResponse)
async def refresh(
    body: RefreshRequest, request: Request,
) -> RefreshResponse:
    """刷新 token：旧 refresh 一次性使用，签发新 access + 新 refresh。

    安全约束：
    1. JWT 解码失败按成因分流 → 过期 EXPIRED_REFRESH / 无效 INVALID_REFRESH（均 401）
    2. type != 'refresh' → WRONG_TOKEN_TYPE（401）
    3. 缺 role claim（P0-2 防回归）→ INVALID_REFRESH（401）
    4. JTI 已被吊销（重放/截获）→ INVALID_REFRESH（401，H-P0-2 防重放）
    5. 旧 JTI 一次性使用：成功签发后立即 revoke 旧 JTI，缩小泄露窗口
    """
    # TODO-006: refresh 同样限流。refresh 本身不涉及口令，威胁模型弱于
    # login，但无限制仍可被用来打满签发路径（每次都要跑一次 JWT 校验）。
    from app.services._sliding_window_rate_limit import check_rate_limit

    if not await check_rate_limit(
        f"auth_refresh:{request.client.host if request.client else None}",
        limit=_LOGIN_RATE_LIMIT,
        window_seconds=_LOGIN_RATE_WINDOW_SECONDS,
    ):
        raise PcsError(
            code="REFRESH_RATE_LIMITED",
            message=f"刷新过于频繁，请稍后再试 (limit {_LOGIN_RATE_LIMIT}/min/IP)",
            status=429,
        )
    try:
        payload = decode_token(body.refresh_token)
    except jwt.ExpiredSignatureError as e:
        # 与 access 侧对称：过期 refresh 也给独立码，前端可区分
        # 「会话到期，重登」vs「token 被篡改」
        raise PcsError(code="EXPIRED_REFRESH", message=str(e), status=401) from e
    except jwt.InvalidTokenError as e:
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
