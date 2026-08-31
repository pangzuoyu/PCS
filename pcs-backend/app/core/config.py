from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "development"
    secret_key: str = "dev-secret-key-not-for-production--"
    database_url: str = "postgresql+psycopg://pcs:pcs_dev@localhost:5432/pcs"
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
    return Settings()


def assert_secret_key_configured() -> None:
    """production 启动自检：SECRET_KEY 不得为默认值或短于 32 字节。"""
    s = get_settings()
    if s.is_production and (
        s.secret_key == "dev-secret-key-not-for-production--" or len(s.secret_key) < 32
    ):
        raise RuntimeError("SECRET_KEY must be a strong value (>=32 chars) in production")
