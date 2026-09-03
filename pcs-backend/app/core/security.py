"""JWT 编解码 + 密码哈希。HS256，密钥由 Settings.secret_key 提供。"""

from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from app.core.config import get_settings


def hash_password(plain: str) -> str:
    """占位哈希：mock 用户用。本期不存 DB，文件 actor 即可。"""
    return hashlib.sha256(plain.encode("utf-8")).hexdigest()


def verify_password(plain: str, hashed: str) -> bool:
    return hmac.compare_digest(hash_password(plain), hashed)


def _now() -> datetime:
    return datetime.now(UTC)


def create_access_token(*, subject: str, role: str, extra: dict[str, Any] | None = None) -> str:
    settings = get_settings()
    expire = _now() + timedelta(minutes=settings.access_token_expire_minutes)
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "type": "access",
        "exp": expire,
        "iat": _now(),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def create_refresh_token(*, subject: str, role: str) -> str:
    settings = get_settings()
    expire = _now() + timedelta(days=settings.refresh_token_expire_days)
    payload = {
        "sub": subject,
        "role": role,
        "type": "refresh",
        "exp": expire,
        "iat": _now(),
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def decode_token(token: str) -> dict[str, Any]:
    """解码 JWT。InvalidTokenError / ExpiredSignatureError 由调用方转 PcsError。"""
    settings = get_settings()
    return jwt.decode(token, settings.secret_key, algorithms=["HS256"])
