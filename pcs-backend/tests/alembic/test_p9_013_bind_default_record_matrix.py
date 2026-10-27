"""`p9_013`（存量项目回填默认 RECORD 矩阵）的迁移形状断言 —— P9B-2 · Batch F。

⚠️ 本文件只断言**迁移与运行时一致**（默认矩阵的定义 / 回填的幂等 / 降级口径），
**不跑真库升级** —— 真库升级的验证口径见 `scripts/check_migration_idempotency.py`
+ `alembic check`（每库各一次，退出码 **255**）。

## 最要紧的一条：迁移里的矩阵定义 ≡ 服务常量

⚠️ 服务 `_get_or_create_default_record_matrix` 是**按名字找**已有矩阵的
⇒ **矩阵的步骤来自 DB 行**，不是来自服务常量 ⇒ 服务改了 `DEFAULT_RECORD_STEPS`
而迁移没改 ⇒ 老库的矩阵还是**旧步骤** ⇒ 「谁该签这一步」有两个答案，
**没有任何报错**。

⇒ 这条断言是那个分叉的**唯一**闸门。

## 为什么**直接 import 迁移模块**（而不是 AST 解析）

迁移里的 SQL 是 f-string（把矩阵名 / 模块 / 步骤内联进去）⇒ AST 只能看到
`{_MATRIX_NAME}` 这样的**占位** ⇒ 断言「SQL 里有没有那个名字」就成了断言
「占位符拼对了」⇒ **测不到真正要守的东西**。⇒ 直接 import，拿**求值后的
SQL** 来断言。
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from app.services.signature_matrix_service import SignatureMatrixService

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "p9_013_bind_default_record_matrix.py"
)


def _load():
    """import 迁移模块（无副作用：只定义常量与函数）。"""
    spec = importlib.util.spec_from_file_location("p9_013_migration", MIGRATION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_exists_and_is_chained_to_p9_012():
    """`revision = p9_013` / `down_revision = p9_012`（p9_012 是当前 head）。"""
    assert MIGRATION.exists(), "p9_013 迁移文件不存在"
    module = _load()
    assert module.revision == "p9_013"
    assert module.down_revision == "p9_012", (
        f"down_revision 应为 p9_012（当前 head），实际 {module.down_revision}"
    )


def test_migration_matrix_definition_matches_service_constants():
    """⚠️ **迁移里的默认矩阵 ≡ 服务常量**（名字 / 模块 / 步骤）。"""
    module = _load()
    assert module._MATRIX_NAME == SignatureMatrixService.DEFAULT_RECORD_MATRIX_NAME
    assert module._MODULE == SignatureMatrixService.RECORD_MODULE
    steps = json.loads(module._STEPS_JSON)
    assert steps == [dict(s) for s in SignatureMatrixService.DEFAULT_RECORD_STEPS], (
        "迁移里的默认矩阵步骤与服务常量不一致 —— "
        "服务是**按名字找**矩阵的 ⇒ 定义漂了 ⇒ 老库用旧步骤、新库用新步骤 ⇒ "
        "「谁该签这一步」有两个答案且不报错。"
    )


def test_backfill_only_touches_projects_without_record_binding():
    """回填**只**给没有 RECORD 绑定的项目补（已有绑定的人工决定不被夺走）。"""
    module = _load()
    sql = module._CREATE_BINDINGS
    assert "NOT EXISTS" in sql
    assert "b.project_id = p.project_id AND b.module = 'RECORD'" in sql
    # ⚠️ **不许**无条件 INSERT（会把已有绑定换成默认矩阵）
    assert sql.count("INSERT INTO project_signature_matrix_bindings") == 1


def test_default_matrix_is_created_only_when_missing():
    """默认矩阵**有就复用**（`(matrix_name, status)` 唯一 ⇒ 天然幂等）。"""
    module = _load()
    sql = module._CREATE_MATRIX
    assert "WHERE NOT EXISTS" in sql
    assert "matrix_name = 'DEFAULT_RECORD_3_LEVEL' AND status = 'ACTIVE'" in sql
    # ⚠️ 步骤必须**真的**进 SQL（不是占位符）
    assert '"sign_role": "CHECKER"' in sql


def test_downgrade_deletes_bindings_but_keeps_the_matrix_row():
    """降级删**绑定**、留**矩阵行**（矩阵是全局模板，删了会让新建项目的绑定悬空）。"""
    module = _load()
    sql = module._DROP_BINDINGS
    assert "DELETE FROM project_signature_matrix_bindings" in sql
    assert "DELETE FROM signature_matrices" not in sql
    # ⚠️ 降级也**只**删 module=RECORD 的绑定
    assert "WHERE module = 'RECORD'" in sql
