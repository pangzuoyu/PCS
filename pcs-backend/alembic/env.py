"""alembic 同步迁移。Base 来源于 app.db.base（全部 ORM 已注册）."""

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

import app.models  # noqa: F401  注册全部 53 表
from alembic import context
from app.core.config import get_settings
from app.db.base import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 数据库 URL 由 app 设置接管；alembic.ini 该项留空以防误连
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)

target_metadata = Base.metadata


def _disable_comment_comparison() -> None:
    """摘掉 alembic 的 COMMENT 比对插件（2026-10-07 用户裁决）.

    **为什么关掉**：`modify_comment` 单独占 349 条漂移（47 张表），而 COMMENT 是纯
    元数据 —— 不影响功能、不丢数据、不影响查询性能。留着它，每次 `alembic check`
    都刷 349 行噪声，守门价值被打折；而要对齐它，得为「改一句注释」写一条 schema
    迁移，等于把工具的噪声当成了模型的约束。

    **为什么不能靠 `include_object`**：注释比对不走对象过滤器，而是 alembic 1.18+
    的 plugin 机制（`autogenerate/compare/comments.py` 注册的 comparator）。
    `include_object` 只在对象级比较时回调，对注释完全无效 —— 本项目实测验证过。

    **代价（明说，两条）**：
    1. 注释漂移从此不可见 —— 接受的取舍，注释本就不该是契约；
    2. `alembic revision --autogenerate` 生成的迁移**不再带 COMMENT**。
       注释改由 ORM 声明承载，与裁决一致。

    ⚠️ `_all_plugins` 是 alembic 私有 API。已做存在性检查 + try/except：
    万一将来版本改名或移除，本函数静默跳过，行为退回「比对注释」，
    即回到本函数实施前的状态 —— 不会让 `alembic check` 直接崩掉。
    """
    try:
        from alembic.runtime.plugins import _all_plugins

        _all_plugins.pop("alembic.autogenerate.comments", None)
    except (ImportError, AttributeError):  # pragma: no cover
        pass


_disable_comment_comparison()


def run_migrations_offline() -> None:
    """离线模式：仅输出 SQL 脚本，不建立真实连接."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式：建立真实连接并执行迁移."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
