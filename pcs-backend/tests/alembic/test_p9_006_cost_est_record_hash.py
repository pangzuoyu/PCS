"""P9A-4 D0 迁移基座的 schema 断言 —— cost_est_results.record_hash（ADR-0048 §⑥）。

⚠️ 迁移与 ORM 漂移时，**单测照绿、真库会炸**（CLAUDE.md 漂移盲区）。
本文件断言的是**元数据与迁移产物一致**，不是运行时行为。

## 列形状：`String(64)` NOT NULL default ''

计划原文写 `String(16)` + nullable。**实测否决**：

- 全库 **25 张**已有 `record_hash` 的表**全部**是 `VARCHAR(64) NOT NULL`
  （`RecordMixin.record_hash` 声明 `app/models/mixins.py:61`；初始 schema
  `dd47298c9c38`；给 `two_phase_results` 补列的先例 `p4_task0_lineage_extension`）。
- 16 是**值**的长度（`calc_lineage._HASH_PREFIX = 16`），不是列宽。
  SHA-256 完整 hex 恰好 64 字符 ⇒ 64 是有意的余量。
- 空串是「未计算」的唯一哨兵，**ADR-0048 §⑥ 的退化阶梯就是按
  `record_hash == ""` 分支写的** ⇒ 用 NULL 会让阶梯漏判（`NULL != ""`）。

⇒ 本文件用 `test_every_record_hash_column_in_the_repo_has_the_same_shape`
把「全库同形」钉成守卫：将来任何一张表用别的宽度/可空性，这条会红。
"""
from __future__ import annotations

import ast
from pathlib import Path

import app.models  # noqa: F401  触发全部 model 注册
from app.db.base import Base
from app.models.calc import CoolingTowerResult, CostEstResult

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "p9_006_cost_est_record_hash.py"
)


def _col():
    return CostEstResult.__table__.columns["record_hash"]


def test_cost_est_has_record_hash_column():
    """D0 的全部意义：给唯一「可编辑 ∧ 无任何并发令牌」的表补上令牌。"""
    assert "record_hash" in CostEstResult.__table__.columns


def test_record_hash_shape_matches_the_other_tables():
    """String(64) NOT NULL default '' —— 与全库另外 25 张表同形。"""
    col = _col()
    assert col.type.length == 64, f"列宽应为 64（与全库另外 25 张表同形），实为 {col.type.length}"
    assert col.nullable is False, "应为 NOT NULL（空串是「未计算」的唯一哨兵）"
    assert col.default is not None and col.default.arg == "", (
        "ORM 侧默认值应为 ''（未计算时空串）"
    )


def test_record_hash_declaration_matches_the_record_mixin_tables():
    """单一来源：与走 RecordMixin 的结果表逐项同形。

    比的是**已映射的表列**（`RecordMixin.__dict__["record_hash"]` 在
    SQLAlchemy 2.0 里还是 `MappedColumn`，未落成 Column ⇒ 比不了）。
    """
    mixin_col = CoolingTowerResult.__table__.columns["record_hash"]
    col = _col()
    assert col.type.length == mixin_col.type.length
    assert col.nullable == mixin_col.nullable
    assert (col.default.arg if col.default else None) == (
        mixin_col.default.arg if mixin_col.default else None
    )
    assert (col.comment or "") == (mixin_col.comment or "")


def test_every_record_hash_column_in_the_repo_has_the_same_shape():
    """全库同形守卫 —— 防止第 26 张异形表出现。

    口径：列名**恰好** `record_hash`。`data_lineage.record_hash_at_track`
    是另一个概念（16 hex 的血缘快照），不在此列。
    """
    shapes: dict[str, tuple[int | None, bool]] = {}
    for table in Base.metadata.tables.values():
        if "record_hash" in table.columns:
            col = table.columns["record_hash"]
            shapes[table.name] = (col.type.length, col.nullable)
    assert len(shapes) == 26, f"应有 26 张表带 record_hash，实为 {len(shapes)}：{sorted(shapes)}"
    assert set(shapes.values()) == {(64, False)}, (
        f"record_hash 列形状不一致：{ {k: v for k, v in shapes.items() if v != (64, False)} }"
    )


def test_cost_est_still_has_no_updated_at():
    """cost_est_results 仍无 updated_at —— 退化阶梯对它只有 record_hash 一档。

    刻意钉住：若将来给它补了 updated_at，ADR-0048 §⑥ 的阶梯分支要跟着改
    （现在写「无 updated_at」是对现状的描述，不是永久承诺）。
    """
    assert "updated_at" not in CostEstResult.__table__.columns


# ---------------------------------------------------------------------------
# 迁移文件本身
# ---------------------------------------------------------------------------


def _migration_tree() -> ast.Module:
    assert MIGRATION.exists(), f"迁移文件不存在：{MIGRATION}"
    return ast.parse(MIGRATION.read_text(encoding="utf-8"), filename=str(MIGRATION))


def test_migration_revision_chain():
    """revision = p9_006，down_revision = p9_005。

    ⚠️ 计划原文写 `p9_004` —— 那个号已被 `p9_004_record_comments_type_width`
    占用，当前 head 是 `p9_005`。
    """
    tree = _migration_tree()
    values = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            values[node.targets[0].id] = node.value
    assert ast.literal_eval(values["revision"]) == "p9_006"
    assert ast.literal_eval(values["down_revision"]) == "p9_005"


def test_migration_adds_a_single_string64_not_null_column():
    """单列、String(64)、NOT NULL、server_default '' —— 照 two_phase 先例。"""
    tree = _migration_tree()
    added: list[dict] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        if isinstance(fn, ast.Attribute) and fn.attr == "add_column":
            added.append(node)
    assert len(added) == 1, f"应只加 1 列，实为 {len(added)}"
    call = added[0]
    assert call.args[0].value == "cost_est_results"

    # sa.Column(name, type, **kwargs) —— name/type 是位置参数
    col_call = call.args[1]
    assert isinstance(col_call, ast.Call)
    assert col_call.args[0].value == "record_hash"
    assert ast.unparse(col_call.args[1]) == "sa.String(64)"
    kwargs = {kw.arg: kw.value for kw in col_call.keywords}
    assert ast.literal_eval(kwargs["nullable"]) is False
    assert ast.literal_eval(kwargs["server_default"]) == ""


def test_migration_backfills_using_the_single_hash_implementation():
    """回填必须走 app 侧唯一的哈希实现，不许在迁移里复制第二份算法。"""
    src = MIGRATION.read_text(encoding="utf-8")
    assert "from app.services.calc_lineage import" in src, (
        "回填应复用 app 侧 compute_record_hash（单一来源），"
        "不得在迁移里复制哈希算法"
    )
    assert "import hashlib" not in src, "迁移里不得自行实现哈希"
