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
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "development"
    # 默认值改为空字符串 sentinel；真实值在 model_validator / lru_cache 路径生成
    secret_key: str = ""
    database_url: str = "postgresql+psycopg://pcs:pcs_dev@localhost:5432/pcs"
    redis_url: str = "redis://localhost:6379/0"
    cors_allow_origins: str = "http://localhost:5173"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    ldap_url: str = "ldap://localhost:389"
    ldap_base_dn: str = "DC=test,DC=local"
    ldap_user_dn_template: str = "cn={username},CN=Users,DC=test,DC=local"
    ldap_group_role_map: str = (
        "DESIGNER_GROUP:DESIGNER,CHECKER_GROUP:CHECKER,REVIEWER_GROUP:REVIEWER,"
        "APPROVER_GROUP:APPROVER,ADMIN_GROUP:SYSADMIN"
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
