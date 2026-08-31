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
    "dan": "SYSADMIN",
}


class MockLoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)


class MockLoginResponse(BaseModel):
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
        refresh_token=create_refresh_token(subject=body.username),
        role=role,
        username=body.username,
    )
