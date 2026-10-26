"""P9A-DLV-011 T2 迁移基座的 schema 断言 —— (project_id, module) 唯一约束。

⚠️ 迁移与 ORM 漂移时，**单测照绿、真库会炸**（CLAUDE.md 漂移盲区）。
本文件断言的是**元数据与迁移产物一致**，不是运行时行为。

## 为什么补这个约束（TODO-071 · bug-2052）

`ProjectSignatureMatrixBinding` 的注释写着「一个项目同一模块只能绑定一个矩阵」
⇒ 但表上既没有这个唯一约束、ORM 也没声明 ⇒ 应用层的「先查后建」挡不住并发
⇒ 同一项目同一模块绑到两个矩阵 ⇒ 之后每次解析绑定都 `MultipleResultsFound`
⇒ 该项目的变更单路径**永久 500**。

⇒ 约束是这条路径的**唯一**兜底。
"""
from __future__ import annotations

import ast
from pathlib import Path

import app.models  # noqa: F401  触发全部 model 注册
from app.models.deliverable import ProjectSignatureMatrixBinding

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "p9_008_project_matrix_binding_unique.py"
)

CONSTRAINT = "uq_project_signature_matrix_bindings_project_module"


def test_binding_table_declares_unique_project_module():
    """ORM 侧声明唯一约束（project_id, module）。"""
    names = {c.name for c in ProjectSignatureMatrixBinding.__table__.constraints}
    assert CONSTRAINT in names, f"ORM 侧缺唯一约束 {CONSTRAINT}，现有：{sorted(names)}"


def test_unique_constraint_covers_exactly_project_id_and_module():
    """约束列**恰好**是 (project_id, module) —— 多一列少一列都不对。

    少一列 ⇒ 不同模块能各绑一个（那是对的，但约束名会骗人）；
    多一列 ⇒ matrix_id 进了约束 ⇒ 换矩阵就撞约束（那会把「换绑」变成不可能）。
    """
    cons = next(
        c
        for c in ProjectSignatureMatrixBinding.__table__.constraints
        if c.name == CONSTRAINT
    )
    assert [col.name for col in cons.columns] == ["project_id", "module"]


# ---------------------------------------------------------------------------
# 迁移文件本身
# ---------------------------------------------------------------------------


def _migration_tree() -> ast.Module:
    assert MIGRATION.exists(), f"迁移文件不存在：{MIGRATION}"
    return ast.parse(MIGRATION.read_text(encoding="utf-8"), filename=str(MIGRATION))


def test_migration_revision_chain():
    """revision = p9_008，down_revision = p9_007（当前 head）。"""
    tree = _migration_tree()
    values: dict[str, ast.expr] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            values[node.targets[0].id] = node.value
    assert ast.literal_eval(values["revision"]) == "p9_008"
    assert ast.literal_eval(values["down_revision"]) == "p9_007"


def test_migration_creates_the_same_constraint_as_the_orm():
    """迁移创建的约束**名与列**都跟 ORM 一致 ⇒ `alembic check` 不报漂移。"""
    tree = _migration_tree()
    # 迁移里用的是模块级常量（`_CONSTRAINT` / `_TABLE`）⇒ 先把它们求值
    consts: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            try:
                consts[node.targets[0].id] = ast.literal_eval(node.value)
            except ValueError:
                continue

    def _value(node: ast.expr) -> object:
        if isinstance(node, ast.Name):
            return consts[node.id]
        return ast.literal_eval(node)

    created: list[ast.Call] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "create_unique_constraint"
        ):
            created.append(node)
    assert len(created) == 1, f"应只创建 1 个唯一约束，实为 {len(created)}"
    call = created[0]
    assert _value(call.args[0]) == CONSTRAINT
    assert _value(call.args[1]) == "project_signature_matrix_bindings"
    assert ast.literal_eval(call.args[2]) == ["project_id", "module"]


def test_migration_refuses_to_delete_duplicate_rows():
    """⚠️ 有重复行 ⇒ **响亮失败**，不许静默删（重复绑定是业务数据）。"""
    src = MIGRATION.read_text(encoding="utf-8")
    assert "RAISE EXCEPTION" in src, "重复行必须响亮失败"
    assert "HAVING count(*) > 1" in src, "必须先查重再建约束"
    assert "DELETE" not in src.upper(), "迁移里不许删业务数据"
