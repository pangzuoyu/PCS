"""JWT 编解码 + 密码哈希 + JTI 吊销。HS256，密钥由 Settings.secret_key 提供。"""

from __future__ import annotations

import hashlib
import hmac
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from app.core.config import get_settings

# H-P0-2/3: refresh token JTI 吊销集。进程内 in-memory，redis 单节点场景避免额外依赖。
# 多副本部署需切换 Redis set + 启动时从 DB 回填；当前 P5 P0 阶段最小可用。
_REVOKED_JTIS: set[str] = set()


def revoke_jti(jti: str) -> None:
    """把 JTI 加入吊销集，幂等。"""
    _REVOKED_JTIS.add(jti)


def is_jti_revoked(jti: str) -> bool:
    """检查 JTI 是否已被吊销。"""
    return jti in _REVOKED_JTIS


def hash_password(plain: str) -> str:
    """占位哈希：mock 用户用。本期不存 DB，文件 actor 即可。"""
    return hashlib.sha256(plain.encode("utf-8")).hexdigest()


def verify_password(plain: str, hashed: str) -> bool:
    return hmac.compare_digest(hash_password(plain), hashed)


def _now() -> datetime:
    return datetime.now(UTC)


def create_access_token(*, subject: str, role: str, extra: dict[str, Any] | None = None) -> str:
    """生成 HS256 JWT access token。

    步骤：
    1. 取 settings（access_token_expire_minutes / secret_key 来自环境变量）
    2. 构造 payload：sub/role/type=access/exp/iat（iat/exp 均为 UTC 时间戳）
    3. extra 合并到 payload（用于附加场景字段，如 project_id）
    4. jwt.encode(payload, secret_key, algorithm='HS256')

    安全注意：
    - secret_key 必从环境读取（不要硬编码）
    - exp 由配置驱动，不要在此处覆写
    - 返回 token 仅在响应体中泄露，不入日志
    """
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
        "jti": uuid.uuid4().hex,  # H-P0-2：每次 refresh 唯一 JTI，用于吊销
        "exp": expire,
        "iat": _now(),
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def decode_token(token: str) -> dict[str, Any]:
    """解码 JWT。InvalidTokenError / ExpiredSignatureError 由调用方转 PcsError。

    H-P0-1 强制要求 exp/iat/sub 三字段必填，防止接受过期/未签发/无主体标识的伪造 token。
    缺失必填 claim 抛 MissingRequiredClaimError（PyJWTError 子类），调用方 catch 后转 401。
    """
    settings = get_settings()
    return jwt.decode(
        token,
        settings.secret_key,
        algorithms=["HS256"],
        options={"require": ["exp", "iat", "sub"]},
    )
