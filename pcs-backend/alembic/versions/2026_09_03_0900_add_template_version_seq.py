"""add TemplateFile.template_version_seq.

Revision ID: 2026_09_03_0900_add_template_version_seq
Revises: 2026_09_03_0800_add_toe_conversion
Create Date: 2026-09-03

V1.4 P2-OPEN-005：模板版本序列号字段（Task 1.10.2）。
"""
import sqlalchemy as sa

from alembic import op

revision = "2026_09_03_0900_add_template_version_seq"
down_revision = "2026_09_03_0800_add_toe_conversion"


def upgrade():
    """template_files 加 template_version_seq 字段（V1.4 P2-OPEN-005 / Task 1.10.2）.

    步骤：
    - template_version_seq Integer NOT NULL default 0：模板版本序列号

    业务：模板版本序列号（V1.4 P2-OPEN-005）；与 SUP-009 模板上传 SHA-256
    去重 + version_seq 自增策略配套使用。
    """
    op.add_column(
        "template_files",
        sa.Column(
            "template_version_seq",
            sa.Integer,
            nullable=False,
            server_default="0",
            comment="V1.4 P2-OPEN-005：模板版本序列号",
        ),
    )


def downgrade():
    """template_files 删 template_version_seq 字段（V1.4 P2-OPEN-005 落地逆向）.

    步骤：
    - DROP COLUMN template_version_seq

    业务：与 upgrade 互逆；模板版本序列号（V1.4 P2-OPEN-005）移除。
    """
    op.drop_column("template_files", "template_version_seq")