"""PCS 折标系数 vs GB 30251-2024 附录A 表A.1 一致性审计.

用户要求 (2026-10-05): 「还要检查 pcs 当前取值和标准是否一致」。

审计两个层面:
1. **系数值** — PCS ConfigEnergyConversionFactor 的 26 行 (工艺室 R1 签署)
   逐行对 GB 30251-2024 附录A 表A.1 的 kg标油 值, 报偏差。
2. **标煤换算** — standard_coal_factor 是否 == toe_factor × 1.4286
   (1 kg标油 = 1.4286 kg标煤, PCS 写成 toe_factor / 0.7, 数值等价)。

标准原文转录自 sample/GB+30251-2024.pdf 附录A 表A.1 (34 行), 逐行可核:
    pdftotext -layout sample/GB+30251-2024.pdf - | sed -n '1015,1200p'

PCS 系数来源: scripts/p7_open_009_t0_seed_energy_conversion_factors.py
    的 R1_SIGNED_ENERGY_CONVERSION (直接 import, 不复制, 防漂移)。

执行:
    cd pcs-backend && uv run python scripts/p7_open_016_config_conformance_audit.py

退出码: 0 = 全部在容差内; 1 = 有超容差项。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

# 1 kg标油 = 1.4286 kg标煤
KGOE_PER_KGCE = 1.4286
# toe 偏差容差: 附录A 本身只给 1~3 位有效数字 (1.0 / 6.5 / 0.038),
# 取整到 2 位即 0.5% — 超过此值视为 PCS 取值与标准不一致
TOLERANCE_PCT = 0.5
# 标煤列容差: standard_coal_factor 是 PCS 自有的派生列 (toe_factor/0.7),
# 实际记录 2~3 位有效数字 (0.21 而非 0.21429), 舍入损失可达 ~2%.
# 此项按「记录精度」而非「换算正确性」判定。
COAL_TOLERANCE_PCT = 2.5

# ---------------------------------------------------------------------------
# GB 30251-2024 附录A 表A.1 原文转录
# key = (energy_type, sub_type, pressure_level, water_type, value_type)
# value = (序号, 项目名, 单位, kg标油, MJ)
# ---------------------------------------------------------------------------
# 附录A 表A.1 中 PCS 未建模的项 (记录在 UNMAPPED_STANDARD_ROWS 里做缺口披露)
GB30251_A1: dict[tuple, tuple] = {
    ("ELECTRICITY", None, None, None, "EQUIVALENT"):
        (12, "电 当量值", "kW·h", 0.086, 3.6),
    ("ELECTRICITY", None, None, None, "EQUIVALENT_VALUE"):
        (12, "电 等价值", "kW·h", 0.21, 8.792),
    ("FUEL_GAS", "OILFIELD_GAS", None, None, None):
        (6, "油田天然气", "m3", 0.93, 38.94),
    ("FUEL_GAS", "GASFIELD_GAS", None, None, None):
        (7, "气田天然气", "m3", 0.85, 35.59),
    ("FUEL_GAS", "REFINERY_FUEL_GAS", None, None, None):
        (8, "炼厂燃料气", "t", 950.0, 39775.0),
    ("STEAM", None, "GE_7_0_MPA", None, None):
        (13, "10.0 MPa级蒸汽a", "t", 92.0, 3852.0),
    ("STEAM", None, "4_5_TO_7_0_MPA", None, None):
        (14, "5.0 MPa级蒸汽b", "t", 90.0, 3768.0),
    ("STEAM", None, "3_0_TO_4_5_MPA", None, None):
        (15, "3.5 MPa级蒸汽c", "t", 88.0, 3684.0),
    ("STEAM", None, "2_0_TO_3_0_MPA", None, None):
        (16, "2.5 MPa级蒸汽d", "t", 85.0, 3559.0),
    ("STEAM", None, "1_2_TO_2_0_MPA", None, None):
        (17, "1.5 MPa级蒸汽e", "t", 80.0, 3349.0),
    ("STEAM", None, "0_8_TO_1_2_MPA", None, None):
        (18, "1.0 MPa级蒸汽f", "t", 76.0, 3182.0),
    ("STEAM", None, "0_6_TO_0_8_MPA", None, None):
        (19, "0.7 MPa级蒸汽g", "t", 72.0, 3014.0),
    ("STEAM", None, "0_3_TO_0_6_MPA", None, None):
        (20, "0.3 MPa级蒸汽h", "t", 66.0, 2763.0),
    ("STEAM", None, "LT_0_3_MPA", None, None):
        (21, "<0.3 MPa级蒸汽i", "t", 55.0, 2303.0),
    ("WATER", None, None, "FRESH_WATER", None):
        (22, "新鲜水", "t", 0.15, 6.28),
    ("WATER", None, None, "CIRCULATING_WATER", None):
        (23, "循环水", "t", 0.06, 2.51),
    ("WATER", None, None, "SOFTENED_WATER", None):
        (24, "软化水", "t", 0.20, 8.37),
    ("WATER", None, None, "DEMINERALIZED_WATER", None):
        (25, "除盐水", "t", 1.0, 41.87),
    ("WATER", None, None, "LP_DEAERATED_WATER", None):
        (26, "低压除氧水j", "t", 6.5, 272.15),
    ("WATER", None, None, "HP_DEAERATED_WATER", None):
        (27, "高压除氧水k", "t", 10.1, 422.87),
    ("WATER", None, None, "TURBINE_CONDENSATE", None):
        (28, "凝汽机凝结水", "t", 1.0, 41.87),
    ("WATER", None, None, "120C_CONDENSATE_TREATED", None):
        (29, "需除油除铁的120℃凝结水", "t", 5.5, 230.27),
    ("WATER", None, None, "120C_CONDENSATE_REUSABLE", None):
        (30, "可直接回用的120℃凝结水", "t", 6.0, 251.21),
    ("INSTRUMENT_AIR", "PURIFIED", None, None, None):
        (31, "净化压缩空气", "m3", 0.038, 1.59),
    ("INSTRUMENT_AIR", "NON_PURIFIED", None, None, None):
        (32, "非净化压缩空气", "m3", 0.028, 1.17),
    ("NITROGEN", None, None, None, None):
        (33, "氮气", "m3", 0.15, 6.28),
}

# 附录A 表A.1 中 PCS ConfigEnergyConversionFactor 未建模的行 (缺口披露, 非偏差)
UNMAPPED_STANDARD_ROWS = [
    (1, "标准油", "t oe", "换算基准, 不需系数行"),
    (2, "标准煤", "t ce", "换算基准, 不需系数行"),
    (3, "燃料油", "t", "PCS UtilityFuelGas 无燃料油分支"),
    (4, "液化石油气", "t", "PCS UtilityFuelGas 有 LPG 枚举但 CONFIG 无系数行"),
    (5, "甲烷氢", "t", "PCS 无对应"),
    (9, "制氢PSA尾气", "t", "PCS 无对应"),
    (10, "催化烧焦", "t", "PCS 无对应"),
    (11, "石油焦", "t", "PCS 无对应"),
    (34, "低温热", "MJ", "PCS CONFIG 无该行, _compute_totals 用硬编码 fallback"),
]

# 附录A 序号34 低温热 — PCS CONFIG 未建模, service 用硬编码 fallback。
# fallback 值与标准的偏离必须单列: 无 CONFIG 行 + 硬编码 = 静默生效, 无告警。
GB_A1_LOW_TEMP_HEAT_KGOE_PER_MJ = 0.012
LOW_TEMP_HEAT_FALLBACK_RE = (
    r'factors\.get\(\s*"LOW_TEMP_HEAT"\s*,\s*\(\s*([0-9.]+)\s*,\s*([0-9.]+)\s*\)'
)


def audit_low_temp_heat_fallback() -> dict:
    """审计 _compute_totals 的 LOW_TEMP_HEAT 硬编码 fallback vs 附录A 序号34."""
    import re

    src = (ROOT / "app" / "services" / "util"
           / "utility_energy_summary_service.py").read_text(encoding="utf-8")
    m = re.search(LOW_TEMP_HEAT_FALLBACK_RE, src)
    if m is None:
        return {
            "status": "OK",
            "detail": "未检出 LOW_TEMP_HEAT 硬编码 fallback (已改为查表或已删除)",
        }
    actual = float(m.group(1))
    pct = abs(actual - GB_A1_LOW_TEMP_HEAT_KGOE_PER_MJ) / \
        GB_A1_LOW_TEMP_HEAT_KGOE_PER_MJ * 100.0
    return {
        "status": "FAIL" if pct > TOLERANCE_PCT else "OK",
        "pcs_toe_per_mj": actual,
        "pcs_coal_per_mj": float(m.group(2)),
        "std_toe_per_mj": GB_A1_LOW_TEMP_HEAT_KGOE_PER_MJ,
        "deviation_pct": round(pct, 2),
        "detail": (
            "硬编码 fallback 且 CONFIG 表无 LOW_TEMP_HEAT 行 → 静默生效无告警。"
            "另: 0.0341 是 GB/T 2589 表A.2「热力(当量值) 0.03412 kgce/MJ」, "
            "把 **kg标煤/MJ** 当成 **kg标油/MJ** 用, 量纲也错。"
        ),
    }


def _key(row: dict) -> tuple:
    return (
        row.get("energy_type"),
        row.get("sub_type"),
        row.get("pressure_level"),
        row.get("water_type"),
        row.get("value_type"),
    )


def _label(row: dict) -> str:
    for field in ("value_type", "sub_type", "pressure_level", "water_type"):
        if row.get(field):
            return f"{row['energy_type']}/{row[field]}"
    return str(row["energy_type"])


def main() -> int:
    from p7_open_009_t0_seed_energy_conversion_factors import (
        R1_SIGNED_ENERGY_CONVERSION,
    )

    rows = R1_SIGNED_ENERGY_CONVERSION
    print(f"PCS 系数行数: {len(rows)}  |  标准附录A 可比对行数: {len(GB30251_A1)}")
    print(f"偏差容差: {TOLERANCE_PCT}%\n")

    print(
        f"{'PCS 行':<42}{'序号':<5}{'标准项':<24}"
        f"{'PCS':<10}{'标准':<10}{'偏差%':<9}{'标煤核对':<10}判定"
    )
    print("-" * 130)

    deviations: list[dict] = []
    coal_mismatches: list[dict] = []
    unmapped_pcs: list[dict] = []

    for row in rows:
        key = _key(row)
        std = GB30251_A1.get(key)
        label = _label(row)
        if std is None:
            unmapped_pcs.append({"pcs": label, "key": key})
            print(f"{label:<42}{'-':<5}{'【标准无对应行】':<24}"
                  f"{row['toe_factor']:<10}{'-':<10}{'-':<9}{'-':<10}⚠️ 未比对")
            continue

        seq, std_name, _unit, std_kgoe, _std_mj = std
        pct = abs(row["toe_factor"] - std_kgoe) / std_kgoe * 100.0
        ok = pct <= TOLERANCE_PCT

        # 标煤换算自洽: standard_coal_factor == toe_factor × 1.4286
        expect_coal = row["toe_factor"] * KGOE_PER_KGCE
        coal_pct = abs(row["standard_coal_factor"] - expect_coal) / expect_coal * 100
        coal_ok = coal_pct <= COAL_TOLERANCE_PCT
        if not coal_ok:
            coal_mismatches.append(
                {"pcs": label, "actual": row["standard_coal_factor"],
                 "expected": round(expect_coal, 6)}
            )

        verdict = "✅" if ok else "❌ 超容差"
        print(
            f"{label:<42}{seq:<5}{std_name:<24}"
            f"{row['toe_factor']:<10}{std_kgoe:<10}{pct:<9.4f}"
            f"{'✅' if coal_ok else '❌':<10}{verdict}"
        )
        if not ok:
            deviations.append(
                {"pcs": label, "序号": seq, "标准项": std_name,
                 "pcs_value": row["toe_factor"], "std_value": std_kgoe,
                 "deviation_pct": round(pct, 4)}
            )

    print("\n" + "=" * 130)
    print("PCS 系数 vs GB 30251-2024 附录A 表A.1 偏差汇总")
    print("=" * 130)
    if deviations:
        print(f"\n❌ {len(deviations)} 行超出 {TOLERANCE_PCT}% 容差:\n")
        for d in deviations:
            print(
                f"  序号{d['序号']:<3} {d['标准项']:<24} "
                f"PCS={d['pcs_value']:<8} 标准={d['std_value']:<8} "
                f"偏差 {d['deviation_pct']:+.2f}%   [{d['pcs']}]"
            )
    else:
        print(f"\n✅ 全部 {len(rows)} 行在 {TOLERANCE_PCT}% 容差内")

    if coal_mismatches:
        print(f"\n❌ {len(coal_mismatches)} 行标煤换算不自洽 "
              f"(应 = toe_factor × 1.4286):\n")
        for m in coal_mismatches:
            print(f"  {m['pcs']:<42} 实际={m['actual']:<10} 应为={m['expected']}")

    if unmapped_pcs:
        print(f"\n⚠️  {len(unmapped_pcs)} 个 PCS 行在标准表中无对应项 (未比对):\n")
        for u in unmapped_pcs:
            print(f"  {u['pcs']}")

    print(f"\n标准附录A 表A.1 中 PCS 未建模的 {len(UNMAPPED_STANDARD_ROWS)} 行 "
          f"(缺口, 非偏差):\n")
    for seq, name, unit, note in UNMAPPED_STANDARD_ROWS:
        print(f"  序号{seq:<3} {name:<22} {unit:<8} {note}")

    # --- 专项: LOW_TEMP_HEAT 硬编码 fallback (附录A 序号34) ---
    lt = audit_low_temp_heat_fallback()
    print("\n" + "=" * 130)
    print("专项审计: LOW_TEMP_HEAT (GB 30251-2024 附录A 序号34 低温热)")
    print("=" * 130)
    if lt["status"] == "OK":
        print(f"\n✅ {lt['detail']}")
    else:
        print(
            f"\n❌ 偏离标准 {lt['deviation_pct']:+.1f}%\n"
            f"     PCS 硬编码 fallback : {lt['pcs_toe_per_mj']} kg标油/MJ "
            f"({lt['pcs_coal_per_mj']} kg标煤/MJ)\n"
            f"     标准 附录A 序号34    : {lt['std_toe_per_mj']} kg标油/MJ "
            f"(0.0171 kg标煤/MJ)\n"
            f"     {lt['detail']}"
        )

    return 1 if (deviations or coal_mismatches or unmapped_pcs
                 or lt["status"] == "FAIL") else 0


if __name__ == "__main__":
    sys.exit(main())
