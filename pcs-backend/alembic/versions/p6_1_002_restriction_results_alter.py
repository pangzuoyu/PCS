"""P6-1 Task 7: restriction_results 表加列（SPEC §3.2.2.6).

按 SPEC §3.2.2.6（Web 版 P6）+ DICT V3.3 PK 命名：

**既有 v3_1 stub 列保留**（不破坏现有数据；restriction_type 由 cv_engine 弃用，
但 ORM 字段暂留以防既有查询/测试引用）：
- orifice_id（PK，p5_0_4a rename 后）
- restriction_type
- input_json / output_json
- tag_number / sign_status / record_hash / approval_* / change_* /
  obsoleted_* / reversal_*
- project_id / workspace_id / created_by / created_at / updated_at

**净增 13 列**（DICT V3.3 §4.1 + SPEC §3.2.2.6 字段平铺）：
1. 装置类型：device_type
2. 几何：D_pipe_m / d_solved_m / beta_ratio
3. 流量系数：C_discharge / epsilon / Re_D
4. 压差：delta_P_pa / delta_omega_pa
5. 状态：choked / flashing / stages
6. 设计阶段：design_stage

**净增 1 索引**：
- ix_restriction_results_record_hash（SHA-256 前缀查重）

**DOWN-REVISION** = p6_1_001_cv_results_alter（依赖 Task 7 同一 batch）。
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "p6_1_002_restriction_results_alter"
down_revision = "p6_1_001_cv_results_alter"
branch_labels = None
depends_on = None


# SPEC §3.2.2.6 净增 13 列定义
# ORM nullable 按 SPEC；DB 层以 nullable=True 兼容 v3_1 stub 存量行
# （新行由 cv_engine 必填，ORM 层 nullable=False 拦截）
_RES_NEW_COLUMNS: list[tuple[str, sa.Column]] = [
    # 装置类型（NOT NULL per SPEC §3.2.2.6）
    ("device_type", sa.Column("device_type", sa.String(length=32), nullable=True,
                                comment="ORIFICE/VENTURI/NOZZLE/MULTI_STAGE（§3.2.2.6）")),
    # 几何（NOT NULL per SPEC for D/d/beta/C）
    ("D_pipe_m", sa.Column("D_pipe_m", sa.Float(), nullable=True,
                            comment="管道内径 m（SPEC §3.2.2.6）")),
    ("d_solved_m", sa.Column("d_solved_m", sa.Float(), nullable=True,
                              comment="求解的孔径 m（SPEC §3.2.2.6）")),
    ("beta_ratio", sa.Column("beta_ratio", sa.Float(), nullable=True,
                              comment="d/D（SPEC §3.2.2.6）")),
    ("C_discharge", sa.Column("C_discharge", sa.Float(), nullable=True,
                                comment="流出系数（SPEC §3.2.2.6）")),
    # 可膨胀性 / 雷诺数（nullable per SPEC）
    ("epsilon", sa.Column("epsilon", sa.Float(), nullable=True,
                           comment="可膨胀性系数（SPEC §3.2.2.6）")),
    ("Re_D", sa.Column("Re_D", sa.Float(), nullable=True,
                        comment="雷诺数（SPEC §3.2.2.6）")),
    # 压差（NOT NULL per SPEC for delta_P_pa）
    ("delta_P_pa", sa.Column("delta_P_pa", sa.Float(), nullable=True,
                              comment="压差 Pa（SPEC §3.2.2.6）")),
    ("delta_omega_pa", sa.Column("delta_omega_pa", sa.Float(), nullable=True,
                                   comment="永久压损 Pa（SPEC §3.2.2.6）")),
    # 状态 Boolean / Integer
    ("choked", sa.Column("choked", sa.Boolean(), nullable=False,
                          server_default=sa.text("FALSE"),
                          comment="阻塞流（SPEC §3.2.2.6）")),
    ("flashing", sa.Column("flashing", sa.Boolean(), nullable=False,
                            server_default=sa.text("FALSE"),
                            comment="闪蒸（SPEC §3.2.2.6）")),
    ("stages", sa.Column("stages", sa.Integer(), nullable=True,
                          comment="多级时级数（SPEC §3.2.2.6）")),
    # 设计阶段（OPEN-009 + PsvResult 同模式）
    ("design_stage", sa.Column("design_stage",
                                sa.Enum("BASIC", "DETAIL",
                                         name="design_stage_enum",
                                         native_enum=True),
                                nullable=False,
                                server_default=sa.text("'BASIC'"),
                                comment="设计阶段 BASIC/DETAIL（OPEN-009）")),
]


def upgrade() -> None:
    """restriction_results 净增 13 列 + 1 索引（P6-1 Task 7 / SPEC §3.2.2.6)."""
    # 1. ADD COLUMN × 13（按 SPEC §3.2.2.6 字段平铺）
    for _name, col in _RES_NEW_COLUMNS:
        op.add_column("restriction_results", col)

    # 2. CREATE INDEX × 1
    op.create_index(
        "ix_restriction_results_record_hash",
        "restriction_results",
        ["record_hash"],
        unique=False,
    )


def downgrade() -> None:
    """restriction_results 净增 13 列 + 1 索引回退（P6-1 Task 7 逆向)."""
    # 1. DROP INDEX × 1（先 drop 索引避免依赖残留）
    op.drop_index("ix_restriction_results_record_hash", "restriction_results")

    # 2. DROP COLUMN × 13（逆序与 upgrade 对称）
    for _name, col in reversed(_RES_NEW_COLUMNS):
        op.drop_column("restriction_results", col.name)