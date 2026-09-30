"""P6-1 Task 7: cv_results 表加列（SPEC §3.2.1.6).

按 SPEC §3.2.1.6（Web 版 P6）+ DICT V3.3 PK 命名：

**既有 v3_1 stub 列保留**（不破坏现有数据；cv_value/flow_rate/
pressure_drop/choked_flow 由 cv_engine 弃用，但 ORM 字段暂留以防既有查询/测试
引用）：
- cv_id（PK，p5_0_4a rename 后）
- cv_value / flow_rate / pressure_drop / choked_flow
- input_json / output_json
- tag_number / sign_status / record_hash / approval_* / change_* /
  obsoleted_* / reversal_*
- project_id / workspace_id / created_by / created_at / updated_at

**净增 21 列**（DICT V3.3 §4.1 + SPEC §3.2.1.6 字段平铺）：
1. 阀体/流体：valve_type / fluid_phase
2. 工况：P1_pa / P2_pa / T1_k / Q_m3_per_h
3. 物性：rho / SG / FL / xT / gamma / M / Z
4. 结果：Cv_calculated / Cv_selected
5. 状态：choked / cavitation / flashing / noise_sil_db
6. 标准：standard_profile_code
7. 设计阶段：design_stage

**净增 2 索引**：
- ix_cv_results_record_hash（SHA-256 前缀查重）
- ix_cv_results_standard_profile_code（按 ADR-0028 标准分组）

**DOWN-REVISION** = p5_4_heat_duty_split（P5 末态 alembic head；2026-09-19）。
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "p6_1_001_cv_results_alter"
down_revision = "p5_4_heat_duty_split"
branch_labels = None
depends_on = None


# SPEC §3.2.1.6 净增 21 列定义
# ORM nullable 按 SPEC；DB 层以 nullable=True 兼容 v3_1 stub 存量行
# （新行由 cv_engine 必填，ORM 层 nullable=False 拦截）
_CV_NEW_COLUMNS: list[tuple[str, sa.Column]] = [
    # 阀型 + 流体相（NOT NULL per SPEC §3.2.1.6）
    ("valve_type", sa.Column("valve_type", sa.String(length=32), nullable=True,
                              comment="线性/等百分比/快开（SPEC §3.2.1.6）")),
    ("fluid_phase", sa.Column("fluid_phase", sa.String(length=16), nullable=True,
                               comment="LIQUID/GAS/VAPOR/TWO_PHASE（SPEC §3.2.1.6）")),
    # 工况（NOT NULL per SPEC）
    ("P1_pa", sa.Column("P1_pa", sa.Float(), nullable=True,
                         comment="入口绝压 Pa（SPEC §3.2.1.6）")),
    ("P2_pa", sa.Column("P2_pa", sa.Float(), nullable=True,
                         comment="出口绝压 Pa（SPEC §3.2.1.6）")),
    ("T1_k", sa.Column("T1_k", sa.Float(), nullable=True,
                        comment="入口温度 K（SPEC §3.2.1.6）")),
    ("Q_m3_per_h", sa.Column("Q_m3_per_h", sa.Float(), nullable=True,
                              comment="体积流量 m³/h（SPEC §3.2.1.6）")),
    # 物性（nullable per SPEC）
    ("rho", sa.Column("rho", sa.Float(), nullable=True,
                       comment="密度 kg/m³（SPEC §3.2.1.6，brief 短名）")),
    ("SG", sa.Column("SG", sa.Float(), nullable=True,
                      comment="相对密度（无量纲；SPEC §3.2.1.6）")),
    ("FL", sa.Column("FL", sa.Float(), nullable=True,
                      comment="压力恢复系数（SPEC §3.2.1.6）")),
    ("xT", sa.Column("xT", sa.Float(), nullable=True,
                      comment="压差比系数（SPEC §3.2.1.6）")),
    ("gamma", sa.Column("gamma", sa.Float(), nullable=True,
                         comment="比热比（SPEC §3.2.1.6）")),
    ("M", sa.Column("M", sa.Float(), nullable=True,
                     comment="分子量 g/mol（SPEC §3.2.1.6，brief 短名）")),
    ("Z", sa.Column("Z", sa.Float(), nullable=True,
                     comment="压缩因子（SPEC §3.2.1.6）")),
    # 结果（NOT NULL per SPEC for Cv_calculated）
    ("Cv_calculated", sa.Column("Cv_calculated", sa.Float(), nullable=True,
                                  comment="计算 Cv（SPEC §3.2.1.6）")),
    ("Cv_selected", sa.Column("Cv_selected", sa.Float(), nullable=True,
                                comment="圆整到标准系列的 Cv（SPEC §3.2.1.6）")),
    # 状态 Boolean
    ("choked", sa.Column("choked", sa.Boolean(), nullable=False,
                          server_default=sa.text("FALSE"),
                          comment="是否阻塞流（SPEC §3.2.1.6）")),
    ("cavitation", sa.Column("cavitation", sa.Boolean(), nullable=False,
                               server_default=sa.text("FALSE"),
                               comment="液体空化标记（SPEC §3.2.1.6）")),
    ("flashing", sa.Column("flashing", sa.Boolean(), nullable=False,
                            server_default=sa.text("FALSE"),
                            comment="液体闪蒸标记（SPEC §3.2.1.6）")),
    ("noise_sil_db", sa.Column("noise_sil_db", sa.Float(), nullable=True,
                                 comment="简化法噪音 dB（SPEC §3.2.1.6）")),
    # 标准代码（NOT NULL per SPEC）
    ("standard_profile_code", sa.Column("standard_profile_code",
                                          sa.String(length=32), nullable=True,
                                          comment="API/GB/CUSTOM（ADR-0028，brief 32）")),
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
    """cv_results 净增 21 列 + 2 索引（P6-1 Task 7 / SPEC §3.2.1.6)."""
    # 1. ADD COLUMN × 21（按 SPEC §3.2.1.6 字段平铺）
    for _name, col in _CV_NEW_COLUMNS:
        op.add_column("cv_results", col)

    # 2. CREATE INDEX × 2
    op.create_index(
        "ix_cv_results_record_hash",
        "cv_results",
        ["record_hash"],
        unique=False,
    )
    op.create_index(
        "ix_cv_results_standard_profile_code",
        "cv_results",
        ["standard_profile_code"],
        unique=False,
    )


def downgrade() -> None:
    """cv_results 净增 21 列 + 2 索引回退（P6-1 Task 7 逆向)."""
    # 1. DROP INDEX × 2（先 drop 索引避免依赖残留）
    op.drop_index("ix_cv_results_standard_profile_code", "cv_results")
    op.drop_index("ix_cv_results_record_hash", "cv_results")

    # 2. DROP COLUMN × 21（逆序与 upgrade 对称）
    for _name, col in reversed(_CV_NEW_COLUMNS):
        op.drop_column("cv_results", col.name)