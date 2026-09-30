"""P6-1.5 C-07: cv_results.standard_profile_code 字段宽度 32→16 回归（评审委员会 2026-09-24).

按 C-07 裁决：GB/T 4213 等同采用 IEC 60534-2-1:2011，无公式差异；
standard_profile_code 字段仅溯源不参与公式分支，最大值 `IEC_60534` 9 字符，
16 字符已覆盖未来 CUSTOM profile。

变更内容：
- `standard_profile_code` 列类型：String(32) → String(16)
- 加 NOT NULL server_default='IEC_60534'（防止空字符串被写入）

DOWN-REVISION = p6_1_002_restriction_results_alter（依赖 P6-1 Task 7）。
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "p6_1_c07_cv_standard_profile_code_16"
down_revision = "p6_1_002_restriction_results_alter"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """cv_results.standard_profile_code：String(32) → String(16) + NOT NULL 默认 IEC_60534.

    1. ALTER COLUMN TYPE：String(32) → String(16)
       存量数据应已 ≤16 字符（pre-existing 值 "API-60534" 9 字符 < 16）；
       若历史数据 > 16 字符则此步会失败（fail-fast 暴露异常）。
    2. ALTER COLUMN SET NOT NULL + server_default='IEC_60534'
       兜底防 NULL（cv_engine 永远填充 IEC_60534，但 DB 层加保险）。
    """
    # 1. 列类型回归
    op.alter_column(
        "cv_results",
        "standard_profile_code",
        type_=sa.String(length=16),
        existing_type=sa.String(length=32),
        postgresql_using="standard_profile_code::VARCHAR(16)",
    )
    # 2. NOT NULL + 默认值兜底（与 ORM 层 mapped_column 一致）
    op.alter_column(
        "cv_results",
        "standard_profile_code",
        existing_type=sa.String(length=16),
        nullable=False,
        server_default=sa.text("'IEC_60534'"),
    )


def downgrade() -> None:
    """cv_results.standard_profile_code 长度回归逆向：String(16) → String(32).

    逆序：先去除 NOT NULL/server_default，再扩列宽到 32。
    """
    # 1. 移除 NOT NULL + server_default
    op.alter_column(
        "cv_results",
        "standard_profile_code",
        existing_type=sa.String(length=16),
        nullable=True,
        server_default=None,
    )
    # 2. 列类型扩展
    op.alter_column(
        "cv_results",
        "standard_profile_code",
        type_=sa.String(length=32),
        existing_type=sa.String(length=16),
        postgresql_using="standard_profile_code::VARCHAR(32)",
    )