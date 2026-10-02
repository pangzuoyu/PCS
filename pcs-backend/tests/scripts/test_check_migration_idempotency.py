"""F-P3-002 fix: 测试 check_migration_idempotency 脚本行为.

锁死:
1. 新批 p7_s2_* migration 必须有 if_not_exists/if_exists
2. 脚本对 p7_s1_* 老 migration 只 advisory (不阻断)
3. 故意漏 if_exists 的 migration 应被检测出
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parent.parent.parent / "scripts" / "check_migration_idempotency.py"


def _load_check_module(migrations_dir: Path):
    """动态加载脚本, 注入 MIGRATIONS_DIR."""
    spec = importlib.util.spec_from_file_location("check_migration_idempotency", SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.MIGRATIONS_DIR = migrations_dir
    return mod


def test_check_passes_current_p7_s2_migrations():
    """p7_s2_001 + p7_s2_002 当前都已带 idempotency guard, 应通过."""
    real_dir = SCRIPT_PATH.parent.parent / "alembic" / "versions"
    mod = _load_check_module(real_dir)
    rc = mod.main()
    assert rc == 0, f"应通过, 实际 exit {rc}"


def test_check_detects_missing_if_not_exists(tmp_path):
    """故意写一个裸 op.create_index (无 if_not_exists), 应被检测出."""
    (tmp_path / "p7_s2_test_bad.py").write_text(
        '"""test bad migration"""\n'
        'from alembic import op\n'
        'revision = "p7_s2_test_bad"\n'
        'down_revision = "p7_s2_002"\n\n'
        'def upgrade():\n'
        '    op.create_index(\n'
        '        "ix_bad",\n'
        '        "tbl",\n'
        '        ["col"],\n'
        '    )\n',
        encoding="utf-8",
    )
    mod = _load_check_module(tmp_path)
    rc = mod.main()
    assert rc == 1, "应 FAIL (裸 op.create_index 无 if_not_exists)"
    # 验证 violation 列表捕获到错误
    violations = mod.check_migration(tmp_path / "p7_s2_test_bad.py")
    assert any("if_not_exists" in v for v in violations)


def test_check_detects_missing_if_exists_on_drop_table(tmp_path):
    """故意写一个裸 op.drop_table (无 if_exists), 应被检测出."""
    (tmp_path / "p7_s2_test_bad_drop.py").write_text(
        '"""test bad drop"""\n'
        'from alembic import op\n'
        'revision = "p7_s2_test_bad_drop"\n'
        'down_revision = "p7_s2_002"\n\n'
        'def downgrade():\n'
        '    op.drop_table("foo")\n',
        encoding="utf-8",
    )
    mod = _load_check_module(tmp_path)
    rc = mod.main()
    assert rc == 1
    violations = mod.check_migration(tmp_path / "p7_s2_test_bad_drop.py")
    assert any("if_exists" in v for v in violations)


def test_check_advisory_only_for_old_p7_s1_migrations(tmp_path):
    """老 p7_s1_* migration 不强制 (script 只检查 p7_s2_*); 用空目录模拟无新批."""
    mod = _load_check_module(tmp_path)  # 空目录, 无 p7_s2_*.py
    rc = mod.main()
    assert rc == 0, "无新批 migration 应直接通过 (advisory only)"
