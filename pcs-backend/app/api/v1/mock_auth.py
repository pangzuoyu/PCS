"""Mock 登录：仅 env != production 时挂载。固定 4 个角色账号，无 LDAP 依赖。"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.errors import PcsError
from app.core.security import create_access_token, create_refresh_token

router = APIRouter(prefix="/auth", tags=["mock-auth"])

MOCK_USERS: dict[str, str] = {
    "alice": "DESIGNER",
    "bob": "CHECKER",
    "carol": "APPROVER",
    "dan": "SYSTEM_ADMIN",
}


class MockLoginRequest(BaseModel):
    """Mock 登录请求体（POST /mock-auth/login，仅开发模式启用）。

    业务：仅传 username（不校验密码）；MOCK_USERS 表查 role 后颁发 JWT；
    生产环境通过 settings.mock_auth_enabled 关闭。
    """

    username: str = Field(
        ..., min_length=1, max_length=100, description="Mock 登录用户名"
    )


class MockLoginResponse(BaseModel):
    """Mock 登录响应（POST /mock-auth/login）。

    业务：与 TokenResponse 同构（access + refresh + bearer + role + username）；
    仅 mock 模式返回；生产模式由 LDAP Login 端点替代。
    """

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    role: str
    username: str


@router.post("/mock-login", response_model=MockLoginResponse)
def mock_login(body: MockLoginRequest) -> MockLoginResponse:
    """任何密码都接受（mock）；生产环境此路由不会被 include。"""
    if get_settings().is_production:
        # 双重保险：main.py 已不挂载，这里再 raise 防误用
        raise PcsError(
            code="MOCK_DISABLED",
            message="mock auth is disabled in production",
            status=403,
        )
    role = MOCK_USERS.get(body.username)
    if not role:
        raise PcsError(
            code="UNKNOWN_MOCK_USER",
            message=f"unknown mock user: {body.username}",
            status=404,
        )
    return MockLoginResponse(
        access_token=create_access_token(subject=body.username, role=role),
        refresh_token=create_refresh_token(subject=body.username, role=role),
        role=role,
        username=body.username,
    )
