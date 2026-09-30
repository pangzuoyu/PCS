"""SUP Sprint PC-4: config_approvals.version_id 改 nullable（V1.4 §2.4/§五、#1).

项目级管道等级审批不挂 ConfigVersion（CATEGORY_5 公司级专属），其审批行
ConfigApproval.version_id 应为 NULL、project_class_id 必填。PC-1 仅加了
project_class_id 列，未放宽 version_id NOT NULL（彼时未到 PC-4 落地时机）。
PC-4 落地时一并放宽，避免 PR 阻塞 PC-4 端到端验收。

注：CATEGORY_5 公司级审批行 version_id 仍非空（PC-3 ConfigStateMachine 驱动），
迁移仅放宽 NOT NULL 约束，业务层语义不变。
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "p2_sup_sprint_pc4_config_approval_nullable"
down_revision: str | None = "p2_sup_sprint_pc3_asset_subtype"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """config_approvals.version_id 改 nullable（PC-4 / V1.4 §2.4/§五、#1).

    步骤：
    - config_approvals.version_id Uuid() → nullable=True

    不动：CATEGORY_5 公司级审批行 version_id 仍非空（PC-3 ConfigStateMachine
    驱动），业务层语义不变；仅放宽 NOT NULL 约束。

    业务：项目级管道等级审批不挂 ConfigVersion（CATEGORY_5 公司级专属），
    其审批行 ConfigApproval.version_id 应为 NULL、project_class_id 必填。
    PC-1 仅加 project_class_id 列未放宽 version_id，PC-4 一并放宽避免阻塞端到端。
    """
    op.alter_column(
        "config_approvals",
        "version_id",
        existing_type=sa.Uuid(),
        nullable=True,
    )


def downgrade() -> None:
    """config_approvals.version_id 回滚 nullable=False（PC-4 落地逆向).

    步骤：
    - DELETE FROM config_approvals WHERE version_id IS NULL（先清项目级审批）
    - ALTER COLUMN version_id SET NOT NULL

    业务：与 upgrade 互逆；回滚前必须先 DELETE 项目级审批行（version_id=NULL），
    否则 NOT NULL 违例报错。本迁移是 PC-4 配套，落地有 project 级审批的
    config_approvals 行（如 DRAFT 项目模板审批）须先清，否则 reverse 失败。
    """
    # 回滚前需清空 version_id IS NULL 的行（项目级审批），否则 NOT NULL 违例
    op.execute("DELETE FROM config_approvals WHERE version_id IS NULL")
    op.alter_column(
        "config_approvals",
        "version_id",
        existing_type=sa.Uuid(),
        nullable=False,
    )