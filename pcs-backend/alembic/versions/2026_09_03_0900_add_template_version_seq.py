"""add TemplateFile.template_version_seq

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
    op.drop_column("template_files", "template_version_seq")