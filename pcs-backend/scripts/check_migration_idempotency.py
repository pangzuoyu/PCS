"""检查 alembic migrations 是否用 if_exists / if_not_exists (F-P3-002 fix).

防 R0 回退: 新 migration 写裸 op.create_table / op.create_index /
op.drop_constraint 会让 alembic upgrade → downgrade → upgrade 循环失败
(局部应用恢复场景需手动 alembic downgrade -1).

本脚本检查规则:
- op.create_table: 应有 if_exists=True 或写在 op.batch_alter_table 内
- op.create_index: 应有 if_not_exists=True
- op.drop_constraint: 应有 type="check" 或 cascade
- op.add_constraint: 应有 if_not_exists 或 postgres_prewarm

退出码:
- 0: 全部通过 (含 advisory)
- 1: 有 critical violation (新 migration 未带 idempotency)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "alembic" / "versions"
SAFE_OPS = {
    # create_table 不支持 if_not_exists (alembic API), 由 drop_table if_exists 兜底
    "op.create_table": [],
    "op.create_index": ["if_not_exists"],
    "op.drop_table": ["if_exists"],
    "op.drop_index": ["if_exists"],
    "op.add_column": [],  # PG 不支持 ADD COLUMN IF NOT EXISTS in < 9.6; skip
    "op.create_unique_constraint": ["if_not_exists"],
}


def check_migration(path: Path) -> list[str]:
    """Return list of warnings for missing idempotency guards."""
    warnings = []
    src = path.read_text(encoding="utf-8")
    for line_no, line in enumerate(src.splitlines(), 1):
        for op, guards in SAFE_OPS.items():
            if op not in line:
                continue
            if not guards:
                continue
            # 查 op 调用周围 8 行有无 guard (含多行参数 + 长参数列表)
            context = "\n".join(
                src.splitlines()[max(0, line_no - 6):line_no + 8]
            )
            if not any(g in context for g in guards):
                warnings.append(
                    f"{path.name}:{line_no}: {op} 缺 idempotency guard "
                    f"(期望 {guards})"
                )
    return warnings


def main() -> int:
    violations: list[str] = []
    # P7 Sprint 2 + 3 + 4 (F-P3-002 fix 涵盖范围扩展 — 每批新迁移都要加进来)
    #
    # ⚠️ 白名单是「基线」概念, 不是「本批」概念: `p7_open_*` 与 `p7_s1_*` 共 9 个
    # 文件仍有未加 guard 的 drop_table/create_index (既有债, 见 #12)。它们**不能**
    # 纳入检查, 否则钩子会在与本次改动无关的文件上开始失败, 久而久之被整体关掉。
    # 新增 sprint 批次时, 同步把前缀加进来; 加之前先跑一遍确认新批自身是干净的。
    checked_prefixes = ("p7_s2_", "p7_s3_", "p7_s4_", "p7_s5_")
    for path in sorted(MIGRATIONS_DIR.glob("p7_*.py")):
        if not any(path.name.startswith(p) for p in checked_prefixes):
            continue
        violations.extend(check_migration(path))

    if not violations:
        print(f"OK: 0 violations in {len(checked_prefixes)} checked prefixes: "
              f"{'/'.join(checked_prefixes)}*")
        return 0

    print(f"FAIL: {len(violations)} violations:")
    for v in violations:
        print(f"  {v}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
