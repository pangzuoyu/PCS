"""P6-3 G-04/05/06：3 张 CONFIG 元数据表新建.

含 cooling_tower_curves / filtration_media_library / flare_radiation_limits
三张 CONFIG 元数据表，被 OPEN_CHANNEL / FILTRATION / flare radiation_check
对应计算读取。

按 P6 计划 §Task 29 硬性前置 gate：

- 镜像 P6-2 G-03 模式（commit ``a64b00a`` Task 17 已落地），单迁移含 3 张
  表 + 各自唯一约束（``tower_model+source`` / ``medium_type+grade`` /
  ``limit_type``）。
- 3 张表均为元数据型 CONFIG 表（被 OPEN_CHANNEL / FILTRATION / COST_EST
  对应计算读取的物性 / 限值系数），不继承 TaggedRecordMixin/record_hash；
  故不含 sign_status / project_id / workspace_id / mixin 全套列。
- 仅保留业务字段 + 工艺室确认字段（``source`` + ``confirmed_by`` +
  ``confirmed_at``）+ 时间戳（``created_at`` + ``updated_at``），与
  ``app/models/config.py`` 中 3 个 ORM class 严格对齐。
- 录入操作由 ``scripts/p6_3_gate_*_seed.py`` 3 个脚本单独执行（upsert），
  本迁移只负责 DDL。

DOWN-REVISION = p6_2_001_flare_cool_tower_psychro_results（P6-2 末态
alembic head；2026-09-25 由 Task 18 提交）。
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "p6_3_001_three_config_tables"
down_revision = "p6_2_001_flare_cool_tower_psychro_results"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """创建 cooling_tower_curves / filtration_media_library / flare_radiation_limits.

    字段定义严格对齐 ``app/models/config.py`` 中 3 个 ORM class：

    - cooling_tower_curves：curve_id UUID PK + tower_model/curve_source/
      c_coefficient/m_exponent + l_g_ratio_min/max(可空) + notes(可空) +
      source + confirmed_by/at(可空) + created_at/updated_at；
      UQ(tower_model, source) → uq_cooling_tower_curves_model_source。
    - filtration_media_library：media_id UUID PK + medium_type/grade/
      nominal_rating_um + cake_resistance_alpha/specific_resistance_r0/
      permeability_k/porosity_eps/max_temp_c(均可空) + source +
      confirmed_by/at(可空) + created_at/updated_at；
      UQ(medium_type, grade) → uq_filtration_media_type_grade。
    - flare_radiation_limits：limit_id UUID PK + limit_type/q_kw_m2_limit +
      distance_m/effective_height_m/notes(可空) + source +
      confirmed_by/at(可空) + created_at/updated_at；
      UQ(limit_type) → uq_flare_radiation_limits_type。
    """
    op.create_table(
        "cooling_tower_curves",
        sa.Column(
            "curve_id", sa.Uuid(), nullable=False,
            comment="UUID 主键",
        ),
        sa.Column(
            "tower_model", sa.String(length=64), nullable=False,
            comment='厂商型号（如 "CTI-ATC105-MARLEY-STD"）',
        ),
        sa.Column(
            "curve_source", sa.String(length=16), nullable=False,
            comment='数据来源分类："CTI" / "MANUFACTURER"',
        ),
        sa.Column(
            "c_coefficient", sa.Float(), nullable=False,
            comment="CTI ATC-105 特性曲线 C 系数（KaV/L = C × (L/G)^(−m)）",
        ),
        sa.Column(
            "m_exponent", sa.Float(), nullable=False,
            comment="CTI ATC-105 特性曲线 m 指数",
        ),
        sa.Column(
            "l_g_ratio_min", sa.Float(), nullable=True,
            comment="适用 L/G 比下限（NULL=厂商全区间）",
        ),
        sa.Column(
            "l_g_ratio_max", sa.Float(), nullable=True,
            comment="适用 L/G 比上限（NULL=厂商全区间）",
        ),
        sa.Column(
            "notes", sa.String(length=256), nullable=True,
            comment="备注",
        ),
        sa.Column(
            "source", sa.String(length=64), nullable=False,
            comment='数据来源；SYNTHETIC_TEST_DATA 或 "CTI_ATC-105-ED7"',
        ),
        sa.Column(
            "confirmed_by", sa.String(length=64), nullable=True,
            comment="工艺室确认签字人（占位 NULL）",
        ),
        sa.Column(
            "confirmed_at", sa.DateTime(timezone=True), nullable=True,
            comment="工艺室确认签字时间（占位 NULL）",
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
            comment="记录创建时间（DB server_default）",
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=True,
            comment="记录更新时间（ORM onupdate 触发）",
        ),
        sa.PrimaryKeyConstraint("curve_id", name="pk_cooling_tower_curves"),
        sa.UniqueConstraint(
            "tower_model", "source",
            name="uq_cooling_tower_curves_model_source",
        ),
    )

    op.create_table(
        "filtration_media_library",
        sa.Column(
            "media_id", sa.Uuid(), nullable=False,
            comment="UUID 主键",
        ),
        sa.Column(
            "medium_type", sa.String(length=32), nullable=False,
            comment='介质大类："SAND"/"ANTHRACITE"/"CARBON"/"RUTH_FILTER_CLOTH"/"ERGUN_PACKING"',
        ),
        sa.Column(
            "grade", sa.String(length=32), nullable=False,
            comment='牌号/规格（如 "#20-30"/"F-400"）',
        ),
        sa.Column(
            "nominal_rating_um", sa.Float(), nullable=False,
            comment="标称过滤精度（μm）",
        ),
        sa.Column(
            "cake_resistance_alpha", sa.Float(), nullable=True,
            comment="Ruth 滤饼比阻（m/kg，恒压过滤专用）",
        ),
        sa.Column(
            "specific_resistance_r0", sa.Float(), nullable=True,
            comment="Ruth 单位阻力（1/m，恒压过滤专用）",
        ),
        sa.Column(
            "permeability_k", sa.Float(), nullable=True,
            comment="Ergun 渗透率（m²）",
        ),
        sa.Column(
            "porosity_eps", sa.Float(), nullable=True,
            comment="Ergun 孔隙率（0~1）",
        ),
        sa.Column(
            "max_temp_c", sa.Float(), nullable=True,
            comment="最高使用温度（℃）",
        ),
        sa.Column(
            "source", sa.String(length=64), nullable=False,
            comment='数据来源；SYNTHETIC_TEST_DATA 或厂商 datasheet 名称',
        ),
        sa.Column(
            "confirmed_by", sa.String(length=64), nullable=True,
            comment="工艺室确认签字人（占位 NULL）",
        ),
        sa.Column(
            "confirmed_at", sa.DateTime(timezone=True), nullable=True,
            comment="工艺室确认签字时间（占位 NULL）",
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
            comment="记录创建时间（DB server_default）",
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=True,
            comment="记录更新时间（ORM onupdate 触发）",
        ),
        sa.PrimaryKeyConstraint("media_id", name="pk_filtration_media_library"),
        sa.UniqueConstraint(
            "medium_type", "grade",
            name="uq_filtration_media_type_grade",
        ),
    )

    op.create_table(
        "flare_radiation_limits",
        sa.Column(
            "limit_id", sa.Uuid(), nullable=False,
            comment="UUID 主键",
        ),
        sa.Column(
            "limit_type", sa.String(length=16), nullable=False,
            comment='限值类型："PROPERTY_LINE"/"PERSONNEL"/"EMERGENCY"',
        ),
        sa.Column(
            "q_kw_m2_limit", sa.Float(), nullable=False,
            comment="允许辐射热通量（kW/m²）；BEDD 三档 4.73/6.31/12.6",
        ),
        sa.Column(
            "distance_m", sa.Float(), nullable=True,
            comment="对应距离（m，NULL=不限）",
        ),
        sa.Column(
            "effective_height_m", sa.Float(), nullable=True,
            comment="默认适用火炬有效高度（m，NULL=不限）",
        ),
        sa.Column(
            "notes", sa.String(length=256), nullable=True,
            comment="备注",
        ),
        sa.Column(
            "source", sa.String(length=64), nullable=False,
            comment='数据来源；本任务填 "API521_§7.4.2.3" 真实公开限值',
        ),
        sa.Column(
            "confirmed_by", sa.String(length=64), nullable=True,
            comment="工艺室确认签字人（占位 NULL）",
        ),
        sa.Column(
            "confirmed_at", sa.DateTime(timezone=True), nullable=True,
            comment="工艺室确认签字时间（占位 NULL）",
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
            comment="记录创建时间（DB server_default）",
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=True,
            comment="记录更新时间（ORM onupdate 触发）",
        ),
        sa.PrimaryKeyConstraint("limit_id", name="pk_flare_radiation_limits"),
        sa.UniqueConstraint(
            "limit_type",
            name="uq_flare_radiation_limits_type",
        ),
    )


def downgrade() -> None:
    """逆序删除 3 张表（无外键引用，仅 DDL 逆序).

    顺序：flare_radiation_limits → filtration_media_library →
    cooling_tower_curves（与创建顺序反向）。
    """
    op.drop_table("flare_radiation_limits")
    op.drop_table("filtration_media_library")
    op.drop_table("cooling_tower_curves")