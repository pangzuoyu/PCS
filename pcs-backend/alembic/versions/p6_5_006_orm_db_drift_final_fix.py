"""P6-5 终扫：ORM↔DB 全库 drift 清零（p6_5_005 补扫，3 表）。

p6_5_005 修了审计三件套 5 表 drift 后，全库 ORM↔DB 元数据扫描又暴露
3 处（手写表名清单遗漏）：

- ``sep_equip_results``：审计三件套缺失（同 p6_5_005 的 bug-101 模式，
  P4 前旧表未进 p4_calc_audit_fields 清单）。
- ``pipe_class_import_previews``：TimestampMixin ``created_by`` /
  ``updated_at`` 缺失（ORM 映射，迁移未落）。
- ``project_template_pipe_classes``：``created_by`` 缺失。

全部用 ``ADD COLUMN IF NOT EXISTS`` 幂等写法（两库状态可能不同步）。
"""
from __future__ import annotations

from alembic import op

revision = "p6_5_006_orm_db_drift_final_fix"
down_revision = "p6_5_005_audit_trio_drift_fix"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """3 表补列（幂等 IF NOT EXISTS，对齐各表 ORM 定义）。"""
    # 1. sep_equip_results 审计三件套（同 p6_5_005 定义）
    for col_ddl in (
        "stale_resolution_path VARCHAR(30)",
        "hash_changed BOOLEAN DEFAULT false",
        "changed_fields JSONB",
    ):
        op.execute(
            f"ALTER TABLE sep_equip_results "
            f"ADD COLUMN IF NOT EXISTS {col_ddl}"
        )
    # 2. pipe_class_import_previews TimestampMixin 2 列
    op.execute(
        "ALTER TABLE pipe_class_import_previews "
        "ADD COLUMN IF NOT EXISTS created_by CHAR(32)"
    )
    op.execute(
        "ALTER TABLE pipe_class_import_previews "
        "ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ"
    )
    # 3. project_template_pipe_classes created_by（updated_at 库内已有）
    op.execute(
        "ALTER TABLE project_template_pipe_classes "
        "ADD COLUMN IF NOT EXISTS created_by CHAR(32)"
    )


def downgrade() -> None:
    """3 表删补列（幂等 IF EXISTS，与 upgrade 互逆）。"""
    op.execute(
        "ALTER TABLE project_template_pipe_classes "
        "DROP COLUMN IF EXISTS created_by"
    )
    op.execute(
        "ALTER TABLE pipe_class_import_previews "
        "DROP COLUMN IF EXISTS updated_at"
    )
    op.execute(
        "ALTER TABLE pipe_class_import_previews "
        "DROP COLUMN IF EXISTS created_by"
    )
    for col in ("changed_fields", "hash_changed", "stale_resolution_path"):
        op.execute(
            f"ALTER TABLE sep_equip_results DROP COLUMN IF EXISTS {col}"
        )
