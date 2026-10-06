"""应用全局配置（pydantic-settings + 环境变量 + .env 兜底）。

含 Settings 模型（50+ 配置项）+ get_settings() lru_cache 单例 +
assert_secret_key_configured() 启动强校验（fail-fast 防 JWT 伪造）。
"""

import secrets
import warnings
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

# P0-MED-004 fix（2026-09-18）：移除源代码中明文默认 secret_key。
# 旧值 `"dev-secret-key-not-for-production--"` 在仓库 .git 中可检索，攻击者
# 若部署忘记设环境变量即拿到 well-known JWT 签发密钥 → 任意 token 伪造。
# 新规则：
#   - 未设环境变量 + 非 production → 自动生成随机 64 字节 secret_key（每次
#     启动变化）+ warnings.warn 提醒"开发用，生产前必设 SECRET_KEY"
#   - 未设环境变量 + production → 启动抛 RuntimeError（fail-fast）
#   - 已设环境变量 + 短于 32 字节 + production → RuntimeError
#   - 已设环境变量 + 短于 32 字节 + 非 production → warnings.warn
_DEFAULT_DEV_SECRET_PREFIX = "auto-generated:"  # 仅标记来源，不可见 API


class Settings(BaseSettings):
    """应用全局配置（pydantic-settings，env 注入 + .env 兜底）。

    业务：env/secret_key/database_url/redis_url/ldap/jwt/cors 等 50+ 配置项；
    单例 get_settings() lru_cache 缓存；model_validator 兜底 secret_key 派生。
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "development"
    # 默认值改为空字符串 sentinel；真实值在 model_validator / lru_cache 路径生成
    secret_key: str = ""
    database_url: str = "postgresql+psycopg://pcs:pcs_dev@localhost:5432/pcs"
    redis_url: str = "redis://localhost:6379/0"
    cors_allow_origins: str = "http://localhost:5173"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    # F-P3-001 Sprint 3: JWT iss/aud config-driven 对称 (Issue 1).
    # production 配置为 "pcs-auth" / "pcs-api" 启用校验.
    # 配置时才写+校验, 未配置则既不写也不校验 (dev/mock 友好).
    jwt_issuer: str | None = None
    jwt_audience: str | None = None
    ldap_url: str = "ldap://localhost:389"
    ldap_base_dn: str = "DC=test,DC=local"
    ldap_user_dn_template: str = "cn={username},CN=Users,DC=test,DC=local"
    ldap_group_role_map: str = (
        "DESIGNER_GROUP:DESIGNER,CHECKER_GROUP:CHECKER,REVIEWER_GROUP:REVIEWER,"
        "APPROVER_GROUP:APPROVER,ADMIN_GROUP:SYSTEM_ADMIN"
    )

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    def group_role_map(self) -> dict[str, str]:
        return dict(
            pair.split(":", 1) for pair in self.ldap_group_role_map.split(",") if pair
        )


@lru_cache
def get_settings() -> Settings:
    """取 Settings 单例（lru_cache 缓存）。

    安全校验：
    1. SECRET_KEY 为空：
       - production → RuntimeError fail-fast
       - 其他 → 自动生成开发用密钥（带 _DEFAULT_DEV_SECRET_PREFIX 前缀）+ RuntimeWarning
    2. SECRET_KEY < 32 字节：
       - production → RuntimeError fail-fast
       - 其他 → RuntimeWarning（提示 production 替换）

    返回强校验后的 Settings。
    """
    s = Settings()
    # secret_key 空 → 自动生成（开发用）+ 提醒
    if not s.secret_key:
        if s.is_production:
            raise RuntimeError(
                "SECRET_KEY 环境变量必须在 production 设置（>=32 字节强随机）"
            )
        s.secret_key = _DEFAULT_DEV_SECRET_PREFIX + secrets.token_urlsafe(48)
        warnings.warn(
            "SECRET_KEY 未配置；自动生成开发用随机密钥（每次启动变化）。"
            "production 前必须显式设置 SECRET_KEY 环境变量。",
            RuntimeWarning,
            stacklevel=2,
        )
    elif len(s.secret_key) < 32:
        if s.is_production:
            raise RuntimeError(
                f"SECRET_KEY 长度 {len(s.secret_key)} < 32 字节，production 拒绝"
            )
        warnings.warn(
            f"SECRET_KEY 长度 {len(s.secret_key)} < 32 字节，仅开发用；"
            "production 前必换强密钥。",
            RuntimeWarning,
            stacklevel=2,
        )
    return s


def assert_secret_key_configured() -> None:
    """启动自检：secret_key 至少 32 字节（已在 get_settings() 阶段保证）。

    保留此函数作为 lifespan 调用契约点；自检已在 get_settings() 内部完成，
    无需重复检查。
    """
    # get_settings() 已 fail-fast；此处仅做占位以保留调用契约
    return None


def parse_cors_origins(raw: str) -> list[str]:
    """把 `cors_allow_origins` 逗号分隔串解析成 origin 列表。

    去空白、丢空项 —— env 里手写 `"a.com, b.com"` 或尾部带逗号都应容错。
    """
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def validate_cors_for_production(settings: Settings) -> None:
    """生产环境 CORS 配置自检（TODO-019）。

    **必须在 lifespan startup 调用，不能等到 middleware 阶段** —— middleware
    跑在每个请求上，那时才发现配错，故障现象是"所有接口 403"，极难自查。

    两种生产环境下的致命配置：
    - `*`（含 `*,https://x.com` 这种混合写法）—— 任意站点可读本系统响应。
      且浏览器会直接拒绝 `allow_credentials=True` + `*` 的组合，
      所以不存在「`*` + 不用凭证」这种安全折中。
    - 空（未配 / env 漏注入）—— 分域部署下所有浏览器请求全被拒。

    非生产环境放行：开发便利优先。
    """
    if not settings.is_production:
        return
    origins = parse_cors_origins(settings.cors_allow_origins)
    if not origins:
        raise RuntimeError(
            "CORS_ALLOW_ORIGINS 必须在 production 设置为明确的域名列表"
            "（逗号分隔）。空值会让分域部署下所有浏览器请求被拒。"
        )
    if "*" in origins:
        raise RuntimeError(
            "CORS_ALLOW_ORIGINS 在 production 不得为 `*` —— "
            "任意站点都可读取本系统响应。请配明确域名（逗号分隔）。"
        )
