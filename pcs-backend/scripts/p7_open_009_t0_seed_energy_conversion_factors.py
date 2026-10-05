"""P7 Sprint 2 T0: config_energy_conversion_factors CONFIG 数据录入（R1 修订版）。

按 P7-OPEN-009 §6.3 CONFIG 折标煤系数 seed + 工艺室 PCS-SIGN-F-P0-001-2026-10-08-R1
正式签字确认（撤回 R0 后重做，基于三层标准 GB/T 2589-2020 + GB 30251-2024 +
GB/T 50441-2016 交叉核对）：

- 27 行能源类型折标油系数（按分类拆为多行）：
  - 电 2 行：ELECTRICITY 当量值 EQUIVALENT / 等价值 EQUIVALENT_VALUE
  - 燃料气 3 行：OILFIELD_GAS / GASFIELD_GAS / REFINERY_FUEL_GAS
  - 蒸汽 9 行：按 pressure_level 9 档 (GB 30251-2024 附录A)
  - 水 9 行：按 water_type 9 类 (GB 30251-2024 附录A)
  - 氮气 1 行
  - 仪表空气 2 行：PURIFIED / NON_PURIFIED
- 数据值依据 GB 30251-2024 附录A（炼化强制国标）+ GB/T 50441-2016 附录A
- source 字段标记 GB_30251_2024_APPENDIX_A（工艺室签字来源）
- confirmed_by / confirmed_at 由工艺室 R1 签字流程固定维护
- 标准煤与标准油换算：1 kg标油 = 1.4286 kgce（1 kgce = 0.7 kg标油）

用法：

    cd pcs-backend
    uv run python scripts/p7_open_009_t0_seed_energy_conversion_factors.py --dry-run
    uv run python scripts/p7_open_009_t0_seed_energy_conversion_factors.py        # 真库

数据语义：先 DELETE 表内所有 source='SYNTHETIC_TEST_DATA' 或 'GB_T_50441_2016_APPENDIX_A'
记录，再 INSERT 全量 27 行（幂等）。confirmed_by / confirmed_at 由工艺室 R1 签字流程固定维护。
"""
# ruff: noqa — 一次性 T0 录入脚本（单点收敛），非 app 代码
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 允许 ``uv run python scripts/xxx.py`` 直接调用；app 包从 pcs-backend 根解析。
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

import datetime

from sqlalchemy import create_engine, delete, select  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.models.config import ConfigEnergyConversionFactor  # noqa: E402

# -----------------------------------------------------------------------------
# 工艺室 R1 正式确认 27 行折标油系数（PCS-SIGN-F-P0-001-2026-10-08-R1）
# -----------------------------------------------------------------------------
# 依据：GB 30251-2024 附录A（炼化强制国标）+ GB/T 50441-2016 附录A（行业补充）
# 标准煤与标准油换算：1 kgce = 0.7 kg标油
R1_SIGNED_ENERGY_CONVERSION: list[dict] = [
    # === 电 2 行：按 §6.1.1 当量值/等价值 ===
    {
        "energy_type": "ELECTRICITY", "value_type": "EQUIVALENT",
        "toe_factor": 0.086, "standard_coal_factor": 0.1229,  # 0.086 / 0.7 ≈ 0.1229 kgce
        "comment": "GB 30251-2024 §6.1.1 当量值（其他产品用）",
    },
    {
        "energy_type": "ELECTRICITY", "value_type": "EQUIVALENT_VALUE",
        "toe_factor": 0.21, "standard_coal_factor": 0.30,  # 0.21 / 0.7 = 0.30 kgce
        "comment": "GB 30251-2024 §6.1.1 等价值（炼油/乙烯用）",
    },
    # === 燃料气 3 行：按气源分类 ===
    {
        "energy_type": "FUEL_GAS", "sub_type": "OILFIELD_GAS",
        "toe_factor": 0.93, "standard_coal_factor": 1.329,
        "comment": "GB 30251-2024 附录A 油田天然气",
    },
    {
        "energy_type": "FUEL_GAS", "sub_type": "GASFIELD_GAS",
        "toe_factor": 0.85, "standard_coal_factor": 1.214,
        "comment": "GB 30251-2024 附录A 气田天然气",
    },
    {
        "energy_type": "FUEL_GAS", "sub_type": "REFINERY_FUEL_GAS",
        "toe_factor": 950.0, "standard_coal_factor": 1357.1,
        "comment": "GB 30251-2024 附录A 炼厂燃料气（950 kg标油/t）",
    },
    # === 蒸汽 9 行：按压力等级 9 档 (GB 30251-2024 附录A) ===
    {
        "energy_type": "STEAM", "pressure_level": "GE_7_0_MPA",
        "toe_factor": 92.0, "standard_coal_factor": 131.4,
        "comment": "蒸汽 ≥7.0 MPa 级 (92 kg标油/t)",
    },
    {
        "energy_type": "STEAM", "pressure_level": "4_5_TO_7_0_MPA",
        "toe_factor": 90.0, "standard_coal_factor": 128.6,
        "comment": "蒸汽 4.5–7.0 MPa 级 (90 kg标油/t)",
    },
    {
        "energy_type": "STEAM", "pressure_level": "3_0_TO_4_5_MPA",
        "toe_factor": 88.0, "standard_coal_factor": 125.7,
        "comment": "蒸汽 3.0–4.5 MPa 级 (88 kg标油/t)",
    },
    {
        "energy_type": "STEAM", "pressure_level": "2_0_TO_3_0_MPA",
        "toe_factor": 85.0, "standard_coal_factor": 121.4,
        "comment": "蒸汽 2.0–3.0 MPa 级 (85 kg标油/t)",
    },
    {
        "energy_type": "STEAM", "pressure_level": "1_2_TO_2_0_MPA",
        "toe_factor": 80.0, "standard_coal_factor": 114.3,
        "comment": "蒸汽 1.2–2.0 MPa 级 (80 kg标油/t)",
    },
    {
        "energy_type": "STEAM", "pressure_level": "0_8_TO_1_2_MPA",
        "toe_factor": 76.0, "standard_coal_factor": 108.6,
        "comment": "蒸汽 0.8–1.2 MPa 级 (76 kg标油/t)",
    },
    {
        "energy_type": "STEAM", "pressure_level": "0_6_TO_0_8_MPA",
        "toe_factor": 72.0, "standard_coal_factor": 102.9,
        "comment": "蒸汽 0.6–0.8 MPa 级 (72 kg标油/t)",
    },
    {
        "energy_type": "STEAM", "pressure_level": "0_3_TO_0_6_MPA",
        "toe_factor": 66.0, "standard_coal_factor": 94.3,
        "comment": "蒸汽 0.3–0.6 MPa 级 (66 kg标油/t)",
    },
    {
        "energy_type": "STEAM", "pressure_level": "LT_0_3_MPA",
        "toe_factor": 55.0, "standard_coal_factor": 78.6,
        "comment": "蒸汽 <0.3 MPa 级 (55 kg标油/t)",
    },
    # === 水 9 行：按水类型 9 类 (GB 30251-2024 附录A) ===
    {
        "energy_type": "WATER", "water_type": "FRESH_WATER",
        "toe_factor": 0.15, "standard_coal_factor": 0.21,
        "comment": "新鲜水 (0.15 kg标油/t)",
    },
    {
        "energy_type": "WATER", "water_type": "CIRCULATING_WATER",
        "toe_factor": 0.06, "standard_coal_factor": 0.086,
        "comment": "循环水 (0.06 kg标油/t)",
    },
    {
        "energy_type": "WATER", "water_type": "SOFTENED_WATER",
        "toe_factor": 0.20, "standard_coal_factor": 0.286,
        "comment": "软化水 (0.20 kg标油/t)",
    },
    {
        "energy_type": "WATER", "water_type": "DEMINERALIZED_WATER",
        "toe_factor": 1.0, "standard_coal_factor": 1.428571,
        "comment": "除盐水 (1.0 kg标油/t) GB 30251-2024 附录A 序号25",
    },
    {
        "energy_type": "WATER", "water_type": "LP_DEAERATED_WATER",
        "toe_factor": 6.52, "standard_coal_factor": 9.314,
        "comment": "低压除氧水 (6.52 kg标油/t)",
    },
    {
        "energy_type": "WATER", "water_type": "HP_DEAERATED_WATER",
        "toe_factor": 10.14, "standard_coal_factor": 14.486,
        "comment": "高压除氧水 (10.14 kg标油/t)",
    },
    {
        "energy_type": "WATER", "water_type": "TURBINE_CONDENSATE",
        "toe_factor": 1.0, "standard_coal_factor": 1.428571,
        "comment": "凝汽机凝结水 (1.0 kg标油/t) GB 30251-2024 附录A 序号28",
    },
    {
        "energy_type": "WATER", "water_type": "120C_CONDENSATE_TREATED",
        "toe_factor": 5.52, "standard_coal_factor": 7.886,
        "comment": "需除油除铁 120℃凝结水 (5.52 kg标油/t)",
    },
    {
        "energy_type": "WATER", "water_type": "120C_CONDENSATE_REUSABLE",
        "toe_factor": 6.02, "standard_coal_factor": 8.6,
        "comment": "可直接回用 120℃凝结水 (6.02 kg标油/t)",
    },
    # === 氮气 1 行 ===
    {
        "energy_type": "NITROGEN",
        "toe_factor": 0.15, "standard_coal_factor": 0.214,
        "comment": "氮气 (0.15 kg标油/m³) GB 30251-2024 附录A",
    },
    # === 仪表空气 2 行：按净化/非净化 ===
    {
        "energy_type": "INSTRUMENT_AIR", "sub_type": "PURIFIED",
        "toe_factor": 0.038, "standard_coal_factor": 0.054,
        "comment": "净化压缩空气 (0.038 kg标油/m³) GB 30251-2024 附录A",
    },
    {
        "energy_type": "INSTRUMENT_AIR", "sub_type": "NON_PURIFIED",
        "toe_factor": 0.028, "standard_coal_factor": 0.040,
        "comment": "非净化压缩空气 (0.028 kg标油/m³) GB 30251-2024 附录A",
    },
    # ========================================================================
    # GB 30251-2024 附录A 表A.1 中 PCS 原未建模的行 (2026-10-05 补齐)
    #
    # energy_type="FUEL" 单列的原因 (安全, 非命名洁癖):
    #   附录A 序号 3/4/5/9/10/11 是**按吨**计的燃料 (kg标油/t),
    #   而 FUEL_GAS 下的 3 行 (序号6/7/8) 中序号6/7 是**按 Nm³** 计。
    #   _compute_totals 对 FUEL_GAS 是 `fuel_gas_by_source(Nm³) × toe_factor`,
    #   若把 LPG 的 1200 (kg标油/t) 放成 FUEL_GAS/LPG, 一旦有人设
    #   gas_source='LPG' 就会算出 **Nm³ × 1200** 的荒谬值。
    #   故按吨计的燃料一律归 FUEL, 当前聚合不经过 → 纯参考元数据, 零地雷。
    #   待「按质量计的燃料消耗」数据模型落地 (P7-6B 后续) 再接线。
    # ========================================================================
    # === 燃料 6 行：按吨计 ===
    {
        "energy_type": "FUEL", "sub_type": "FUEL_OIL",
        "toe_factor": 1000.0, "standard_coal_factor": 1428.571429,
        "comment": "燃料油 (1000 kg标油/t) GB 30251-2024 附录A 序号3",
    },
    {
        "energy_type": "FUEL", "sub_type": "LPG",
        "toe_factor": 1200.0, "standard_coal_factor": 1714.285714,
        "comment": (
            "液化石油气 (1200 kg标油/**t**) GB 30251-2024 附录A 序号4 — "
            "注意单位是吨不是 Nm³; UtilityFuelGas.fuel_type=LPG 是 R0 遗留字段, "
            "R1 聚合按 gas_source 走, 不会命中本行"
        ),
    },
    {
        "energy_type": "FUEL", "sub_type": "METHANE_H2",
        "toe_factor": 1200.0, "standard_coal_factor": 1714.285714,
        "comment": "甲烷氢 (1200 kg标油/t) GB 30251-2024 附录A 序号5",
    },
    {
        "energy_type": "FUEL", "sub_type": "PSA_OFF_GAS",
        "toe_factor": 320.0, "standard_coal_factor": 457.142857,
        "comment": "制氢 PSA 尾气 (320 kg标油/t) GB 30251-2024 附录A 序号9",
    },
    {
        "energy_type": "FUEL", "sub_type": "CATALYTIC_COKE",
        "toe_factor": 950.0, "standard_coal_factor": 1357.142857,
        "comment": "催化烧焦 (950 kg标油/t) GB 30251-2024 附录A 序号10",
    },
    {
        "energy_type": "FUEL", "sub_type": "PETROLEUM_COKE",
        "toe_factor": 800.0, "standard_coal_factor": 1142.857143,
        "comment": "石油焦 (800 kg标油/t) GB 30251-2024 附录A 序号11",
    },
    # === 低温热 1 行：按 MJ 计 ===
    # 修正 bug-135: 原 utility_energy_summary_service.py:523 硬编码
    # (0.0341, 0.0487), 偏离标准 +184.2%, 且 0.0341 实为 GB/T 2589 表A.2
    # 「热力(当量值) 0.03412 **kgce/MJ**」—— 把 kg标煤/MJ 当 kg标油/MJ 用, 量纲错。
    {
        "energy_type": "LOW_TEMP_HEAT",
        "toe_factor": 0.012, "standard_coal_factor": 0.017143,
        "comment": "低温热 (0.012 kg标油/MJ) GB 30251-2024 附录A 序号34",
    },
]

# 工艺室签字元数据（PCS-SIGN-F-P0-001-2026-10-08-R1）
CONFIRMED_BY = "工艺室-工艺负责人-2026-10-08 (R1)"
CONFIRMED_AT = datetime.datetime(
    2026, 10, 8, 0, 0, 0,
    tzinfo=datetime.timezone(datetime.timedelta(hours=8)),
)
SOURCE = "GB_30251_2024_APPENDIX_A"


def _print_rows(label: str) -> None:
    """打印 27 行折标系数（GB 30251-2024 附录A 工艺室 R1 签字值）。"""
    print(
        f"[{label}] config_energy_conversion_factors 共 "
        f"{len(R1_SIGNED_ENERGY_CONVERSION)} 行"
        f"（GB 30251-2024 附录A 工艺室 R1 签字 PCS-SIGN-F-P0-001-2026-10-08-R1）："
    )
    print(f"  # source = {SOURCE}")
    print(f"  # confirmed_by = {CONFIRMED_BY}")
    print(f"  # confirmed_at = {CONFIRMED_AT.isoformat()}")
    print(
        f"  {'energy_type':<18}  {'value_type':<22}  {'sub_type':<22}  "
        f"{'pressure_level':<20}  {'water_type':<28}  {'toe_factor':>10}  "
        f"{'standard_coal':>12}"
    )
    for row in R1_SIGNED_ENERGY_CONVERSION:
        print(
            f"  {row['energy_type']:<18}  {row.get('value_type',''):<22}  "
            f"{row.get('sub_type',''):<22}  {row.get('pressure_level',''):<20}  "
            f"{row.get('water_type',''):<28}  {row['toe_factor']:>10.4f}  "
            f"{row['standard_coal_factor']:>12.4f}"
        )


def _replace_seed_rows(engine) -> tuple[int, int]:
    """先 DELETE 旧 source 行（GB_T_50441_2016_APPENDIX_A + SYNTHETIC_TEST_DATA），
    再 INSERT 全量 27 行。R0 已 RETRACTED，R1 替换。

    幂等：第二次跑只剩 INSERT 27 行（DELETE 已无目标行）。
    """
    deleted = 0
    with engine.begin() as conn:
        # 1. DELETE 旧 R0 行
        stmt_del = delete(ConfigEnergyConversionFactor).where(
            ConfigEnergyConversionFactor.source.in_([
                "SYNTHETIC_TEST_DATA",
                "GB_T_50441_2016_APPENDIX_A",
                SOURCE,  # 也删旧 R1 (如已部分写入)
            ])
        )
        result_del = conn.execute(stmt_del)
        deleted = result_del.rowcount or 0

        # 2. INSERT 全量 27 行
        for row in R1_SIGNED_ENERGY_CONVERSION:
            conn.execute(
                ConfigEnergyConversionFactor.__table__.insert().values(
                    energy_type=row["energy_type"],
                    value_type=row.get("value_type"),
                    sub_type=row.get("sub_type"),
                    pressure_level=row.get("pressure_level"),
                    water_type=row.get("water_type"),
                    toe_factor=row["toe_factor"],
                    standard_coal_factor=row["standard_coal_factor"],
                    source=SOURCE,
                    confirmed_by=CONFIRMED_BY,
                    confirmed_at=CONFIRMED_AT,
                )
            )

    # 3. 二次 COUNT 校验
    with engine.connect() as conn:
        stmt_sel = select(ConfigEnergyConversionFactor)
        inserted = len(conn.execute(stmt_sel).fetchall())

    return deleted, inserted


def main() -> int:
    parser = argparse.ArgumentParser(
        description="P7 Sprint 2 T0: config_energy_conversion_factors seed (R1)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只打印 27 行内容，不连接 DB",
    )
    args = parser.parse_args()

    if args.dry_run:
        _print_rows("DRY-RUN")
        return 0

    settings = get_settings()
    engine = create_engine(settings.database_url)
    try:
        deleted, inserted = _replace_seed_rows(engine)
    finally:
        engine.dispose()

    print(
        f"[OK] config_energy_conversion_factors seed 完成: "
        f"deleted={deleted}, total_rows={inserted}"
    )
    _print_rows("AFTER-SEED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
