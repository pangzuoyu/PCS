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
    """htri_template_schemas 主表创建（HEAT/HTRI 模板 schema）。

    步骤：
    - schema_id UUID PK
    - device_type varchar(20) NOT NULL：ACHE / SHELL_TUBE
    - column_count Integer NOT NULL
    - columns_json JSONB NOT NULL：[{name, type, required, unit}, ...]
    - tema_type varchar(10) NULL：BEM / AES / AKT（仅 SHELL_TUBE 适用）
    - version varchar(50) NOT NULL
    - source_file_ref varchar(200) NULL：原始 .xls 文件引用
    - created_by / created_at timezone / updated_at timezone nullable

    业务：HTRI 模板 schema 持久化（空冷器/管壳式换热器列定义 + TEMA 类型 +
    版本管理），HEAT 计算 service 按 schema 解析 .xls 上传模板。
    """
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
