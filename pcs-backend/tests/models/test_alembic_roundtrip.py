"""P3.x SIM-39 / TODO-040: Alembic migration round-trip 单测（可逆段）。

范围（CLOSE-REPORT TODO-040）：
- 验证 head ↔ 不可逆锚点之间的迁移链 round-trip（downgrade → upgrade）
- 锚点 = p3sim_stream_sign_status_extend（PG enum ADD VALUE 不可 DROP VALUE，
  其 downgrade 抛 NotImplementedError，round-trip 不得跨越）
- 该设计覆盖 head 侧全部新迁移（P3.x SIM 批次活跃段）的可逆性

跑前需（CLAUDE.md 测试前检查）：
    DATABASE_URL=postgresql+psycopg://pcs:pcs_dev@localhost:5432/pcs_test \\
        uv run alembic upgrade head

安全守卫：仅当 database_url 指向 pcs_test 才执行（防误降 pcs 开发库）。
"""
from __future__ import annotations

from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text

from alembic import command
from app.core.config import get_settings

# 不可逆锚点：enum ADD VALUE 迁移（round-trip 下界，不 downgrade 它本身）
IRREVERSIBLE_ANCHOR = "p3sim_stream_sign_status_extend"

BACKEND_DIR = Path(__file__).resolve().parents[2]

# 安全守卫：round-trip 仅允许 pcs_test 库（防误降 pcs 开发库）
_ONLY_PCS_TEST = pytest.mark.skipif(
    not get_settings().database_url.rstrip("/").endswith("pcs_test"),
    reason="round-trip 仅允许 pcs_test 库（防误降 pcs 开发库）；"
           "需 DATABASE_URL=postgresql+psycopg://pcs:pcs_dev@localhost:5432/pcs_test",
)


def _alembic_config() -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    return cfg


# ============================================================================
# 可逆段 round-trip（TODO-040 核心）
# ============================================================================


@_ONLY_PCS_TEST
def test_reversible_segment_roundtrip() -> None:
    """head → downgrade 到不可逆锚点 → upgrade head：版本还原 + schema 抽查。"""
    cfg = _alembic_config()
    script = ScriptDirectory.from_config(cfg)
    head = script.get_current_head()

    if head == IRREVERSIBLE_ANCHOR:
        pytest.skip("head 即不可逆锚点，无可逆段")

    # 起点对齐 head（幂等）
    command.upgrade(cfg, "head")

    # round-trip：downgrade 到锚点（不含锚点自身）再升回 head
    command.downgrade(cfg, IRREVERSIBLE_ANCHOR)
    command.upgrade(cfg, "head")

    # DB 版本还原 + schema 抽查（同步 engine 直查，与 alembic 驱动一致）
    engine = create_engine(get_settings().database_url)
    try:
        with engine.connect() as conn:
            version = conn.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar()
            stream_cols = {
                row[0]
                for row in conn.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_name = 'streams'"
                    )
                )
            }
            enum_labels = {
                row[0]
                for row in conn.execute(
                    text("SELECT unnest(enum_range(NULL::streamsignstatus))::text")
                )
            }
    finally:
        engine.dispose()

    assert version == head, f"round-trip 后版本未还原：{version} != {head}"
    # SIM-34 新列仍在（round-trip 不破坏 head schema）
    assert "rvp" in stream_cols, "SIM-34 rvp 列缺失（round-trip 破坏 schema？）"
    assert "distillation_curves" in stream_cols, (
        "SIM-34 distillation_curves 列缺失（round-trip 破坏 schema？）"
    )
    # 锚点迁移未被跨越：enum 仍 9 态
    expected = {
        "DRAFT", "IN_APPROVAL", "CHECKED", "OBSOLETE",
        "CHECK_REJECTED", "STALE", "CHANGE_PENDING", "CHANGED",
        "REVERSAL_PENDING",
    }
    assert enum_labels == expected, f"enum 9 态漂移：{enum_labels ^ expected}"


# ============================================================================
# 不可逆锚点契约（纯函数，无 DB）
# ============================================================================


def test_enum_migration_downgrade_raises_not_implemented() -> None:
    """锚点迁移 downgrade 抛 NotImplementedError（PG enum ADD VALUE 不可逆）。"""
    import importlib.util

    mod_path = (
        BACKEND_DIR / "alembic" / "versions"
        / "p3_sim_stream_sign_status_extend.py"
    )
    spec = importlib.util.spec_from_file_location(
        "p3_sim_stream_sign_status_extend", mod_path,
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    with pytest.raises(NotImplementedError, match="不可逆"):
        mod.downgrade()
