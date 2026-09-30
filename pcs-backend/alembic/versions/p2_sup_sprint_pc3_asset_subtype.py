"""SUP Sprint PC-3: config_assets 加 asset_subtype 列（PIPE_CLASS 等).

V1.4 §0.5/INT-OPEN-01 裁决：ConfigAsset 增 asset_subtype str30 可空列；name 前缀不可靠。
CATEGORY_5 管道等级资产 = (category='CATEGORY_5', asset_subtype='PIPE_CLASS')；
后续 PIPE_CODE_TEMPLATE / STREAM_SYMBOL 由 SUP-002 后续 PC 落地。

Revision ID: p2_sup_sprint_pc3_asset_subtype
Revises: p2_sup_sprint_pc1_pipe_class_upgrade
Create Date: 2026-09-07
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "p2_sup_sprint_pc3_asset_subtype"
down_revision: str | None = "p2_sup_sprint_pc1_pipe_class_upgrade"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """config_assets 加 asset_subtype 列（PC-3 / V1.4 §0.5/INT-OPEN-01).

    步骤：
    - asset_subtype varchar(30) NULL：PIPE_CLASS / STREAM_SYMBOL / PIPE_CODE_TEMPLATE
    - ix_config_assets_asset_subtype 索引（按 subtype 过滤）

    业务：ConfigAsset 资产级追溯，name 前缀不可靠；
    CATEGORY_5 管道等级资产 = (category='CATEGORY_5', asset_subtype='PIPE_CLASS')；
    后续 PIPE_CODE_TEMPLATE / STREAM_SYMBOL 由 SUP-002 后续 PC 落地。
    """
    op.add_column(
        "config_assets",
        sa.Column(
            "asset_subtype",
            sa.String(30),
            nullable=True,
            comment="PIPE_CLASS/STREAM_SYMBOL/PIPE_CODE_TEMPLATE",
        ),
    )
    op.create_index(
        "ix_config_assets_asset_subtype",
        "config_assets",
        ["asset_subtype"],
    )


def downgrade() -> None:
    """config_assets 删 asset_subtype 字段 + 索引（PC-3 落地逆向).

    步骤：
    - DROP INDEX ix_config_assets_asset_subtype
    - DROP COLUMN config_assets.asset_subtype

    业务：与 upgrade 互逆；PC-3 配置资产子类型字段（pipe_class / project /
    stream_symbol 等细分）清理。
    """
    op.drop_index("ix_config_assets_asset_subtype", table_name="config_assets")
    op.drop_column("config_assets", "asset_subtype")