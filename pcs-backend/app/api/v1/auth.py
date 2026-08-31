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
from app.core.security import create_access_token, create_refresh_token, decode_token
from app.services.ldap_client import LdapAuthError, authenticate, resolve_role

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=0, max_length=200)


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
    token_type: str = "bearer"


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
    if not authorization:
        raise PcsError(
            code="MISSING_BEARER", message="Authorization: Bearer <token>", status=401
        )
    return _decode_bearer(authorization)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest) -> TokenResponse:
    try:
        user = authenticate(body.username, body.password)
    except LdapAuthError as e:
        raise PcsError(code="INVALID_CREDENTIALS", message=str(e), status=401) from e
    role = resolve_role(user.groups)
    return TokenResponse(
        access_token=create_access_token(subject=user.username, role=role),
        refresh_token=create_refresh_token(subject=user.username),
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
    try:
        payload = decode_token(body.refresh_token)
    except jwt.PyJWTError as e:
        raise PcsError(code="INVALID_REFRESH", message=str(e), status=401) from e
    if payload.get("type") != "refresh":
        raise PcsError(
            code="WRONG_TOKEN_TYPE", message="not a refresh token", status=401
        )
    return RefreshResponse(
        access_token=create_access_token(subject=payload["sub"], role="DESIGNER")
    )


@router.post("/logout", status_code=204)
def logout() -> None:
    """无服务端会话，前端仅清空内存 token；保留端点供审计与未来扩展。"""
    return None
