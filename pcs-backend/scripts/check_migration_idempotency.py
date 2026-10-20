"""检查 alembic migrations 是否用 if_exists / if_not_exists (F-P3-002 fix).

防 R0 回退: 新 migration 写裸 op.create_table / op.create_index /
op.drop_constraint 会让 alembic upgrade → downgrade → upgrade 循环失败
(局部应用恢复场景需手动 alembic downgrade -1).

本脚本检查规则（见 SAFE_OPS，空列表 = 该 op 无法幂等化，不检查）:
- op.create_index: 应有 if_not_exists=True
- op.drop_index / op.drop_table: 应有 if_exists=True

⚠️ **约束类 op 无法幂等化，故不检查**。alembic 1.19.1 的
`Operations.create_unique_constraint` / `create_check_constraint` 签名里**没有**
`if_not_exists` 形参（只有 `**kw`），而 PG 也不支持 `ADD CONSTRAINT IF NOT
EXISTS`。实测把 `if_not_exists=True` 传进去不报错，但会被 `**kw` 静默吞掉、
最终不产生任何 if-not-exists 语义 —— 属于「看起来加了 guard 其实没加」，
比不加更危险。故约束幂等只能靠 downgrade 侧 `drop_constraint(if_exists=True)`
兜底。

退出码:
- 0: 全部通过 (含 advisory)
- 1: 有 critical violation (新 migration 未带 idempotency)
"""
from __future__ import annotations

import ast
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
    # 约束类: alembic/PG 均无 if_not_exists, 见模块 docstring —— 不可检查
    "op.create_unique_constraint": [],
    "op.create_check_constraint": [],
}


# op.create_table(*args) 转发给 DDL 编译器, 编译器按对象类型分派; 不是 Column 或
# Constraint 的会被**静默丢弃 —— 不报错不告警**。bug-144: 4 条外键全部这样丢了,
# 而 user_projects 是 BLOCKER-3 IDOR 守卫读的表。
#
# ⚠️ **`sa.ForeignKey` 刻意不在允许列表里** —— 它是「被引用目标描述符」, 不是
# Constraint, 属于必须嵌进 Column 里的东西。允许列表只收真正的表元素:
# Column 与四种 *Constraint。
_CREATE_TABLE_ALLOWED_ARGS = frozenset({
    "Column",
    "PrimaryKeyConstraint",
    "UniqueConstraint",
    "ForeignKeyConstraint",
    "CheckConstraint",
})
# 第一个位置参数是表名字符串, 不查
_CREATE_TABLE_SKIP_ARGS = 1

# 已知历史缺陷的迁移: 缺陷本身**已被后续迁移修掉**, 但原迁移已应用, 不能改写
# （改了会让已部署库的 alembic_version 与文件内容对不上）。
# 故显式豁免并标注 bug 号 —— 新写的迁移落到这个形态时闸门必须拦。
# 加新条目前先确认: 该缺陷确已被某条 down_revision 在后的迁移修复。
KNOWN_HISTORICAL_DEFECTS = {
    # bug-144: 4 条外键被静默丢弃。已由 p7_s5_007_user_projects_fks 补回,
    #          该迁移 down_revision = p7_s5_006, 在本文件之后。
    "p7_open_010_user_projects_blocker3.py",
}


def _check_create_table_args(node: ast.Call, filename: str) -> list[str]:
    """op.create_table 的位置参数必须是 Column / Constraint, 否则会被静默丢弃."""
    violations = []
    for arg in node.args[_CREATE_TABLE_SKIP_ARGS:]:
        if not isinstance(arg, ast.Call):
            continue
        func = arg.func
        if not isinstance(func, ast.Attribute):
            continue
        if func.attr not in _CREATE_TABLE_ALLOWED_ARGS:
            hint = "（应嵌进 sa.Column 内）" if func.attr == "ForeignKey" else ""
            violations.append(
                f"{filename}:{arg.lineno}: op.create_table 位置参数 "
                f"sa.{func.attr}(...) 不是 Column/Constraint, 会被 alembic 静默丢弃{hint}"
            )
    return violations


def check_migration(path: Path) -> list[str]:
    """Return list of violations for missing idempotency guards.

    ⚠️ **必须用 AST 判定，不能用「行内子串 + 上下 8 行窗口」**。旧实现栽在
    `p7_s3_005_gas_media_and_low_temp_heat.py`：该文件 `downgrade()` 的 docstring
    写着「删两张子表 (if_exists 幂等)」，而下面两行 `op.drop_table` 实际**没带**
    `if_exists` —— docstring 里的 `if_exists` 落进了上下文窗口，闸门判为已加 guard，
    长期报 0 violations。这与此前「84 条」漂移低估是同一类根因：拿字符串猜结构。

    同时检查 `op.create_table` 的位置参数类型（bug-144）。这是**纯 AST** 判定,
    不比对 metadata, 因此不受 `TODOS.md` 记录的「循环式迁移导致列覆盖比对
    257 假阳性」那个问题影响。
    """
    violations = []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError as exc:  # 语法错误不该被当成「通过」
        return [f"{path.name}: 语法错误 {exc}"]

    check_args = path.name not in KNOWN_HISTORICAL_DEFECTS

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute) or not isinstance(func.value, ast.Name):
            continue
        op_name = f"op.{func.attr}"
        if op_name == "op.create_table" and check_args:
            violations.extend(_check_create_table_args(node, path.name))
        guards = SAFE_OPS.get(op_name)
        if not guards:
            continue
        present = {kw.arg for kw in node.keywords}
        missing = [g for g in guards if g not in present]
        if missing:
            violations.append(
                f"{path.name}:{node.lineno}: {op_name} 缺 idempotency guard "
                f"(期望 {missing})"
            )
    return violations


#: 守门覆盖的迁移前缀。历史演进（覆盖范围随修完随推进）：
#:   ① 4 个前缀的白名单 → ② 2026-10-07 收敛为 `p7_*`（那 9 个既有文件
#:      已补齐 guard，白名单随之取消）→ ③ **2026-10-20 补上 `p9_*`**。
#:
#: ⚠️ ③ 的起因：实测 `p9_001`~`p9_007` 这 7 个文件**从未被检查过**，
#:    其中 `p9_002` / `p9_003` / `p9_005` 共 17 处违规，而守门每次都报 OK
#:    —— 这正是本仓反复吃的亏：**守门没跑，却看着是绿的**。
#:
#: ⚠️ **前缀白名单天生会漏掉「新一串前缀」** ⇒ ① 加新一波迁移时**必须**把
#:    它的前缀加进这里（`tests/scripts/test_check_migration_idempotency.py::
#:    test_covered_globs_include_every_migration_prefix` 会红），② 或把它写进
#:    `LEGACY_PREFIXES` 并在 TODO-063 里记账。
GLOBS = ("p7_*.py", "p9_*.py")

#: **有意留在覆盖外**的历史前缀（实测 93 个文件 / 350 处违规，含
#: `dd47298c9c38` 全 schema 迁移）。一次补 350 处会淹没 diff、且要逐个确认
#: 语义（`if_exists` 在某些 drop 上会掩盖真实错误）⇒ 已登记 TODO-063。
LEGACY_PREFIXES = (
    "dd47298c9c38",  # v3.1 全 schema 迁移（53 张表）
    "2026_",         # 最早的裸时间戳命名
    "15421f7d5afb",  # p2 merge
    "p1", "p2", "p3", "p4", "p5", "p6", "p8",
)


def main() -> int:
    violations: list[str] = []
    paths = sorted({p for g in GLOBS for p in MIGRATIONS_DIR.glob(g)})
    for path in paths:
        violations.extend(check_migration(path))

    if not violations:
        print(f"OK: 0 violations in {len(paths)} migrations ({' '.join(GLOBS)})")
        return 0

    print(f"FAIL: {len(violations)} violations:")
    for v in violations:
        print(f"  {v}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
