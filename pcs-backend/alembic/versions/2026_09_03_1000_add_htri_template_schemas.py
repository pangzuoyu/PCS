"""add htri_template_schemas

Revision ID: 2026_09_03_1000_add_htri_template_schemas
Revises: 2026_09_03_0900_add_template_version_seq
Create Date: 2026-09-03
"""
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "2026_09_03_1000_add_htri_template_schemas"
down_revision = "2026_09_03_0900_add_template_version_seq"

def upgrade():
    op.create_table(
        "htri_template_schemas",
        sa.Column("schema_id", sa.Uuid(), nullable=False),
        sa.Column("device_type", sa.String(length=20), nullable=False,
                  comment="ACHE/SHELL_TUBE"),
        sa.Column("column_count", sa.Integer(), nullable=False),
        sa.Column("columns_json", JSONB(), nullable=False,
                  comment="[{name, type, required, unit}, ...]"),
        sa.Column("tema_type", sa.String(length=10), nullable=True,
                  comment="BEM/AES/AKT（仅 SHELL_TUBE 适用）"),
        sa.Column("version", sa.String(length=50), nullable=False),
        sa.Column("source_file_ref", sa.String(length=200), nullable=True,
                  comment="原始 .xls 文件引用"),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("schema_id", name=op.f("pk_htri_template_schemas")),
    )

def downgrade():
    op.drop_table("htri_template_schemas")
