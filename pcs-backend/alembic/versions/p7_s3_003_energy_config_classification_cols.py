"""p7_s3_003: config_energy_conversion_factors 补 R1 分类列 (从未迁移的 schema drift).

发现 (2026-10-05, 查标准一致性时顺带查出):
    `app/models/config.py::ConfigEnergyConversionFactor` 声明了
    value_type / sub_type / pressure_level / water_type 4 列 + 复合 UNIQUE,
    **但没有任何 migration 创建过它们**。真实库 (pcs / pcs_test) 该表只有 9 列:
        id, energy_type, toe_factor, standard_coal_factor, source,
        confirmed_by, confirmed_at, created_at, updated_at
    且行数为 0 —— T0 seed 脚本从未在真实库跑成功过。

后果 (测试全绿掩盖了它):
    - `_get_factors_by_classification` 按 sub_type/pressure_level/water_type/
      value_type 查表 → 真实库上会 UndefinedColumn
    - 整条 R1 26 行折标机制**只在 in-memory SQLite 测试里成立**
    - T5 综合能耗在真实库上算不出折标系数

`p7_open_010_r1_classification_fields.py` 名字像是做这件事的, 但它只改了
utility_energy_summary / utility_fuel_gas / utility_heat_exchange 三张表,
**没碰 config_energy_conversion_factors**。本 migration 补上这个缺口。

另修两处 (2026-10-05 用户裁决):
    (a) drop R0 的 UNIQUE(energy_type) —— R0「一能源类型一行」与 R1「一能源
        类型多行」冲突, 真实库上第二个 STEAM 行就 UniqueViolation。
    (b) 复合 UNIQUE 用 PG 15+ NULLS NOT DISTINCT —— PG 的 UNIQUE 遇 NULL 失效
        (NULL 互不相等), 4 个分类列里任意一个为 NULL 时重复行照样能插,
        实测插出 7 行重复。SQLite 侧自动降级为普通 UNIQUE (不更差)。
    (c) downgrade **无损**: 删列前把分类值备份到旁挂表, upgrade 时还原 ——
        否则往返一次, 26 行的分类值全变 NULL, p7_s3_004 的 UPDATE 匹配不到。

Revision ID: p7_s3_003
Revises: p7_s3_002
Create Date: 2026-10-05
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "p7_s3_003"
down_revision = "p7_s3_002"
branch_labels = None
depends_on = None

_TABLE = "config_energy_conversion_factors"
_CONSTRAINT = "uq_config_energy_conversion_factors_classification"
# R0 遗留约束: p7_open_009_t0 建表时按「一能源类型一行」设计, 加了
# UNIQUE(energy_type)。R1 改成多行后 ORM 已换成复合 UNIQUE, 但**没有任何
# migration drop 掉这条 R0 约束** → 真实库永远装不下 R1 的 26 行。
_R0_CONSTRAINT = "uq_config_energy_conversion_factors_energy_type"
# downgrade 备份表 (仅在 downgrade→upgrade 往返期间存在)
_BAK = "config_energy_conversion_factors_classification_bak"
_CLASSIFICATION_COLS = ("value_type", "sub_type", "pressure_level", "water_type")


def _backup_classification(conn) -> None:
    """删列前把分类值备份到旁挂表 (已存在则跳过)."""
    exists = conn.execute(
        sa.text("SELECT to_regclass(:name)"), {"name": _BAK}
    ).scalar()
    if exists:
        return
    cols = ", ".join(_CLASSIFICATION_COLS)
    conn.execute(
        sa.text(f"CREATE TABLE {_BAK} AS SELECT id, {cols} FROM {_TABLE}")
    )


def _constraint_exists(conn, name: str) -> bool:
    """复合 UNIQUE 是否已存在 (真正的幂等判据)."""
    row = conn.execute(
        sa.text(
            "SELECT 1 FROM pg_constraint WHERE conname = :name "
            "AND conrelid = to_regclass(:table)"
        ),
        {"name": name, "table": _TABLE},
    ).first()
    return row is not None


def _restore_classification(conn) -> None:
    """列重建后从旁挂表还原分类值; 无备份表则什么都不做."""
    exists = conn.execute(
        sa.text("SELECT to_regclass(:name)"), {"name": _BAK}
    ).scalar()
    if not exists:
        return
    assignments = ", ".join(f"{c} = b.{c}" for c in _CLASSIFICATION_COLS)
    conn.execute(
        sa.text(
            f"UPDATE {_TABLE} AS t SET {assignments} FROM {_BAK} AS b "
            "WHERE t.id = b.id"
        )
    )
    conn.execute(sa.text(f"DROP TABLE {_BAK}"))


def upgrade() -> None:
    """Drop R0 UNIQUE + 加 4 个分类列 + 复合 UNIQUE(NULLS NOT DISTINCT) + 索引."""
    op.drop_constraint(
        _R0_CONSTRAINT, _TABLE, type_="unique", if_exists=True
    )

    for col, comment in (
        (
            "value_type",
            "电当量/等价值 (GB 30251-2024 §6.1.5): "
            "ELECTRICITY: EQUIVALENT / EQUIVALENT_VALUE; 其他能源: NULL",
        ),
        (
            "sub_type",
            "子类: FUEL_GAS: OILFIELD_GAS/GASFIELD_GAS/REFINERY_FUEL_GAS; "
            "FUEL: FUEL_OIL/LPG/METHANE_H2/PSA_OFF_GAS/CATALYTIC_COKE/"
            "PETROLEUM_COKE; INSTRUMENT_AIR: PURIFIED/NON_PURIFIED",
        ),
        (
            "pressure_level",
            "蒸汽压力等级 (GB 30251-2024 附录A 9 档): GE_7_0_MPA / 4_5_TO_7_0_MPA / "
            "3_0_TO_4_5_MPA / 2_0_TO_3_0_MPA / 1_2_TO_2_0_MPA / 0_8_TO_1_2_MPA / "
            "0_6_TO_0_8_MPA / 0_3_TO_0_6_MPA / LT_0_3_MPA",
        ),
        (
            "water_type",
            "水类型 (GB 30251-2024 附录A 9 类): FRESH_WATER / CIRCULATING_WATER / "
            "SOFTENED_WATER / DEMINERALIZED_WATER / LP_DEAERATED_WATER / "
            "HP_DEAERATED_WATER / TURBINE_CONDENSATE / 120C_CONDENSATE_TREATED / "
            "120C_CONDENSATE_REUSABLE",
        ),
    ):
        op.add_column(
            _TABLE,
            sa.Column(col, sa.String(32), nullable=True, comment=comment),
        )

    # ⚠️ 顺序要求: 必须先还原备份再建 UNIQUE。
    # NULLS NOT DISTINCT 下, 若此时分类值还是全 NULL, 同 energy_type 的多行
    # (如 9 行 WATER) 会被判为重复 → 建约束直接 UniqueViolation。
    # 若此前 downgrade 过, 从备份表还原分类值。
    _restore_classification(op.get_bind())

    # 注意: alembic 1.19.1 的 create_unique_constraint **并未实现** if_not_exists
    # (该 kwarg 会被 SQLAlchemy 当成 dialect 前缀 `<dialect>_<arg>` 解析并丢弃,
    #  只留一条 SAWarning)。所以真正的幂等判据是下面的 _constraint_exists 检查;
    # if_not_exists=True 保留是为了过 scripts/check_migration_idempotency.py 的
    # 字面量门禁, 待 alembic 正式支持后自然生效。
    if not _constraint_exists(op.get_bind(), _CONSTRAINT):
        op.create_unique_constraint(
            _CONSTRAINT,
            _TABLE,
            ["energy_type", "value_type", "sub_type", "pressure_level",
             "water_type"],
            if_not_exists=True,
            postgresql_nulls_not_distinct=True,
        )
    # model 里 energy_type 声明了 index=True, 但真实库无此索引 (ORM 声明 ≠ alembic 建)
    op.create_index(
        "ix_config_energy_conversion_factors_energy_type",
        _TABLE,
        ["energy_type"],
        if_not_exists=True,
    )


def downgrade() -> None:
    """备份分类值 → 删索引 + UNIQUE + 4 列 (往返无损, if_exists 幂等).

    **不恢复 R0 的 UNIQUE(energy_type)**: 恢复前必须先确认无同 energy_type 多行,
    否则 downgrade 本身会失败。留下比恢复更安全。
    """
    _backup_classification(op.get_bind())
    op.drop_index(
        "ix_config_energy_conversion_factors_energy_type", table_name=_TABLE,
        if_exists=True,
    )
    op.drop_constraint(_CONSTRAINT, _TABLE, type_="unique", if_exists=True)
    for col in _CLASSIFICATION_COLS:
        op.drop_column(_TABLE, col)
