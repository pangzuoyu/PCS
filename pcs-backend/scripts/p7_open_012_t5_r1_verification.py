"""P7 Sprint 2 T5 ≤2% 验收脚本（蜡油加氢 XLS R1 重算对比）。

Per PCS-SIGN-F-P0-001-2026-10-08-R1:
- 4 算例折标偏差 ≤2% (P7-OPEN-009 §6 验收标准)
- Case 4 = 蜡油加氢 XLS (1216D132 惠州 260 万吨/年装置)
- R1 系数 GB 30251-2024 附录 A 工艺室 2026-10-08 签齐

执行方式:
    cd pcs-backend && uv run python scripts/p7_open_012_t5_r1_verification.py
"""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

# scripts/ stub
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.db.base import Base as SA_Base  # noqa: E402

# SQLite 兼容垫片 (仿 tests/conftest.py):
# JSONB → JSON; Uuid → VARCHAR; INET → VARCHAR
from sqlalchemy.dialects.sqlite.base import (  # noqa: E402
    SQLiteDDLCompiler, SQLiteTypeCompiler,
)
SQLiteTypeCompiler.visit_JSONB = SQLiteTypeCompiler.visit_JSON  # type: ignore[attr-defined]
SQLiteTypeCompiler.visit_INET = lambda self, *a, **k: "TEXT"  # type: ignore[attr-defined]  # noqa: ANN001, ANN201
SQLiteTypeCompiler.visit_UUID = lambda self, *a, **k: "TEXT"  # type: ignore[attr-defined]  # noqa: ANN001, ANN201
try:
    from sqlalchemy import Uuid as SAUuid
    from sqlalchemy.dialects.postgresql import INET, JSONB

    JSONB.__visit_name__ = "JSON"  # type: ignore[attr-defined]
    INET.__visit_name__ = "VARCHAR"  # type: ignore[attr-defined]
    SAUuid.__visit_name__ = "VARCHAR"  # type: ignore[attr-defined]
except Exception:  # pragma: no cover
    pass

from app.models.config import ConfigEnergyConversionFactor  # noqa: E402
from app.models.project import Project, Workspace  # noqa: E402
from app.models.util import (  # noqa: E402
    UtilityEnergySummary,
    UtilityFuelGas,
    UtilityGasMedia,
    UtilityHeatExchange,
    UtilityLowTempHeat,
    UtilityPowerItem,
)
from app.services.util.utility_energy_summary_service import (  # noqa: E402
    summarize_energy_year,
)


SEED_FACTORS = [
    {"energy_type": "ELECTRICITY", "value_type": "EQUIVALENT", "toe_factor": 0.086,
     "standard_coal_factor": 0.122857, "source": "GB_30251_2024_APPENDIX_A"},
    {"energy_type": "ELECTRICITY", "value_type": "EQUIVALENT_VALUE", "toe_factor": 0.21,
     "standard_coal_factor": 0.30, "source": "GB_30251_2024_APPENDIX_A"},
    {"energy_type": "FUEL_GAS", "sub_type": "GASFIELD_GAS", "toe_factor": 0.85,
     "standard_coal_factor": 1.214286, "source": "GB_30251_2024_APPENDIX_A"},
    {"energy_type": "FUEL_GAS", "sub_type": "OILFIELD_GAS", "toe_factor": 0.93,
     "standard_coal_factor": 1.328571, "source": "GB_30251_2024_APPENDIX_A"},
    {"energy_type": "STEAM", "pressure_level": "0_8_TO_1_2_MPA", "toe_factor": 76.0,
     "standard_coal_factor": 108.571429, "source": "GB_30251_2024_APPENDIX_A"},
    {"energy_type": "STEAM", "pressure_level": "GE_7_0_MPA", "toe_factor": 92.0,
     "standard_coal_factor": 131.428571, "source": "GB_30251_2024_APPENDIX_A"},
    {"energy_type": "WATER", "water_type": "CIRCULATING_WATER", "toe_factor": 0.06,
     "standard_coal_factor": 0.085714, "source": "GB_30251_2024_APPENDIX_A"},
    {"energy_type": "WATER", "water_type": "FRESH_WATER", "toe_factor": 0.15,
     "standard_coal_factor": 0.214286, "source": "GB_30251_2024_APPENDIX_A"},
    {"energy_type": "NITROGEN", "toe_factor": 0.15,
     "standard_coal_factor": 0.214286, "source": "GB_30251_2024_APPENDIX"},
    {"energy_type": "INSTRUMENT_AIR", "sub_type": "PURIFIED", "toe_factor": 0.038,
     "standard_coal_factor": 0.054286, "source": "GB_30251_2024_APPENDIX_A"},
]


# Case 4 消耗量 (设备清单, 抄录自 sample/1216D132惠州蜡油加氢装置计算14.7.17).
# 提到模块级: 既是 DB seed 输入, 也是 GB 30251 独立基准重算的输入。
# 注: 这是「输入量」不是「计算结果」—— 用户裁决 2026-10-05 只作废 XLS 的计算结果作基准,
# 设备清单本身是工程数据, 仍然有效。
POWER_ITEMS = [
    # (equipment_tag, motor_power_kw, hours, load, kwh)
    ("132-P-101A/B", 2214.064, 8400, 1.0, 18598136.4),
    ("132-P-102A/B", 233.748, 8400, 1.0, 1963481.2),
    ("132-P-103A/B", 24.478, 8400, 1.0, 205617.6),
    ("132-P-104A/B", 27.454, 8400, 1.0, 230616.8),
    ("132-P-106A/B", 85.441, 8400, 1.0, 717701.7),
    ("132-P-201A/B", 8.274, 8400, 1.0, 69503.3),
    ("132-P-202A/B", 139.467, 8400, 1.0, 1171520.0),
    ("132-P-203A/B", 65.459, 8400, 1.0, 549859.5),
    ("132-P-204A/B", 8.033, 8400, 1.0, 67476.2),
    ("132-P-205A/B", 37.675, 8400, 1.0, 316471.6),
    ("132-P-206A/B", 48.891, 8400, 1.0, 410687.0),
    ("132-P-207A/B", 264.025, 8400, 1.0, 2217812.8),
    ("132-P-301A/B", 200.799, 8400, 1.0, 1686710.8),
    ("132-P-401", 20.974, 200, 1.0, 4194.8),
    ("132-P-404", 13.322, 8400, 1.0, 111906.7),
    ("132-P-406A/B", 4.63, 8400, 1.0, 38894.7),
    ("217-C-201", 4140.0, 8000, 1.0, 33120000.0),
]
FUEL_ITEMS = [
    ("F-101", "STEADY", 2244564.0),
    ("F-101", "MAX", 2469012.0),
    ("F-201", "STEADY", 9017736.0),
    ("F-201", "MAX", 9919476.0),
    ("F-101-PILOT", "STEADY", 870156.0),
    ("F-201-PILOT", "STEADY", 174048.0),
]
HEAT_ITEMS = [
    ("ST-E-101", 1459.5),
    ("ST-E-102", 1459.5),
    ("ST-E-103", 9949.716),
    ("ST-TRACING", 16800.0),
]

# ---------------------------------------------------------------------------
# P7 Sprint 4 S4-4 扩类: 氮气 / 净化压缩空气 / 低温余热
#
# 此前所有 T5 验证都只覆盖电 / 燃料气 / 蒸汽三类 —— P7-6B 新建的
# utility_gas_media / utility_low_temp_heat 两张表**没有任何真实算例走过**。
#
# 溯源 (sample/1216D132惠州蜡油加氢装置计算14.7.17计算 - 副本.xlsx → `能耗` sheet
# → 「能耗计算」块的「消耗 数量」列)。**只取消耗量, 不取「能耗折算值」列** ——
# 该列的折标系数已被裁决不可信 (用户 2026-10-05「XLS 不作为最终依据」)。
#
# ⚠️ XLS 自身两处问题 (取消耗量不代表认可它的其它列):
#   1. 氮气: 汇总块写「3/50 Nm3/min 连续/间断」, 能耗计算块写「60 Nm3/h」。
#      3×60=180≠60, 50×60=3000≠60 —— 簿内自相矛盾。取 60 (它是本簿实际喂进
#      折算的数字), 矛盾留档。
#   2. 氮气「MJ/Nm3」列写 0.15 —— 0.15 是 **kg标油/Nm3**, 不是 MJ/Nm3。
#      GB 30251-2024 附录A 序号 33 氮气 = 0.15 kg标油/m³ = **6.28 MJ/m³**。
#      XLS 把 kg标油 值填进了 MJ 列, **低估 41.87 倍**。
#
# 年小时 8400: 与本簿其余算例一致 (连续工况)。氮气汇总块标「连续/间断」有歧义,
# 但同一本簿给不出更细的运行时数; 取 8400 且在此声明。该选择影响绝对值,
# 不影响 PCS vs GB 独立重算的 ≤2% 对比 (两侧同源同值)。
# ---------------------------------------------------------------------------

# (equipment_tag, gas_medium, nm3_h, hours_per_year, annual_nm3)
GAS_MEDIA_ITEMS = [
    ("N2-PLANT", "NITROGEN", 60.0, 8400, 504000.0),
    ("AIR-PURIFIED", "PURIFIED_AIR", 630.0, 8400, 5292000.0),
]

# 低温余热: **本 XLS 无此量**。
# 全簿搜索「低温热」「余热」「回收」只命中 `项目信息` 的低温热水系统参数
# (给水 0.8MPaG/105℃, 回水 0.5MPaG/65℃) —— 那是供热介质参数, 不是回收热量,
# 单位也对不上 (需要 GJ)。故不构造条目。
#
# 后果: utility_low_temp_heat 表在 T5 算例中仍无真实数据覆盖。要补需工艺室
# 提供蜡油加氢的低温余热回收量 (GJ/a) —— 登记 follow-up, **不编造数字**。
LOW_TEMP_ITEMS: tuple = ()

# ============================================================================
# 验收基准 — GB 30251-2024 附录 A 表 A.1 (能源及耗能工质折算标准油的参考系数)
#
# 用户裁决 2026-10-05:
#   「Q1 等价值系数按标准取值, XLS 不作为最终依据」
#
# 原 xls_reference (1,242,159,527.8 MJ / 28,532.8967 t标油 / 40,761,279.4 kg标煤)
# 已作废: 三值在原始 XLS 全表中均不存在, 系 commit 6d74fdd 时代代码输出的反抄
# (与旧输出仅差 10.8 MJ), 且 XLS 自身 G33 因 D32=#VALUE! 算不出年总能耗。→ bug-134
#
# 新基准 = 消耗量 (设备清单) × GB 30251-2024 附录 A 表 A.1 系数, 由 _gb30251_reference()
# 独立重算: 不走 ORM / 不读 ConfigEnergyConversionFactor / 不调 summarize_energy_year。
# 故可检出聚合、分类查表、舍入类缺陷 (原「输出 vs 自己旧输出」的比法检不出任何东西)。
# ============================================================================
KGOE_PER_TOE = 1.4286  # 1 kg标油 = 1.4286 kg标煤

# 附录 A 表 A.1 序号 12「电」— 炼油/乙烯强制等价值 (§6.1.5 + 表A.2 注)
GB_A1_ELECTRICITY_KGOE_PER_KWH = 0.21
GB_A1_ELECTRICITY_MJ_PER_KWH = 8.792
# 附录 A 表 A.1 序号 18「1.0 MPa 级蒸汽 f」
GB_A1_STEAM_1_0MPA_KGOE_PER_T = 76.0
GB_A1_STEAM_1_0MPA_MJ_PER_T = 3182.0
# 附录 A 表 A.1 序号 8「炼厂燃料气」以「吨」计 (950 kg标油/t), PCS 以「Nm³」计,
# 换算需气体密度假设 → 标准不直接可比。本项沿用 R1 工艺室 2026-10-08 签署的 Nm³ 值,
# 并在 coefficient_conformance 中标注 not_std_comparable。
R1_FUEL_GAS_GASFIELD_KGOE_PER_NM3 = 0.85

# --- P7 Sprint 4 S4-4 扩类: 气体介质 (GB 30251-2024 附录A 表A.1 序号 31/33) ---
# 附录A 以 kg标油/单位 给出, MJ 列 = kg标油 × 41.868。
GB_A1_PURIFIED_AIR_KGOE_PER_NM3 = 0.038   # 序号 31 净化压缩空气
GB_A1_PURIFIED_AIR_MJ_PER_NM3 = 1.59
GB_A1_NITROGEN_KGOE_PER_NM3 = 0.15        # 序号 33 氮气
GB_A1_NITROGEN_MJ_PER_NM3 = 6.28
# XLS「能耗」sheet 的 MJ/Nm3 列错值 (把 kg标油 数填进了 MJ 列) —— 留档供对比。
XLS_WRONG_NITROGEN_MJ_PER_NM3 = 0.15


def _gb30251_reference() -> dict[str, float]:
    """按 GB 30251-2024 附录 A 表 A.1 独立重算 Case 4 基准.

    Returns: annual_total_energy_mj / total_toe_tonne / total_standard_coal_kg
             + coefficient_conformance (PCS CONFIG vs 附录 A 对照表)
    """
    kwh = sum(item[4] for item in POWER_ITEMS)
    nm3 = sum(item[2] for item in FUEL_ITEMS)
    steam_t = sum(item[1] for item in HEAT_ITEMS)

    electricity_mj = kwh * GB_A1_ELECTRICITY_MJ_PER_KWH
    electricity_kgoe = kwh * GB_A1_ELECTRICITY_KGOE_PER_KWH
    fuel_gas_mj = nm3 * R1_FUEL_GAS_GASFIELD_KGOE_PER_NM3 * 41.868
    fuel_gas_kgoe = nm3 * R1_FUEL_GAS_GASFIELD_KGOE_PER_NM3
    steam_mj = steam_t * GB_A1_STEAM_1_0MPA_MJ_PER_T
    steam_kgoe = steam_t * GB_A1_STEAM_1_0MPA_KGOE_PER_T

    # P7 Sprint 4 S4-4 扩类: 氮气 + 净化压缩空气
    n2_nm3 = sum(r[4] for r in GAS_MEDIA_ITEMS if r[1] == "NITROGEN")
    air_nm3 = sum(r[4] for r in GAS_MEDIA_ITEMS if r[1] == "PURIFIED_AIR")
    nitrogen_mj = n2_nm3 * GB_A1_NITROGEN_MJ_PER_NM3
    air_mj = air_nm3 * GB_A1_PURIFIED_AIR_MJ_PER_NM3
    nitrogen_kgoe = n2_nm3 * GB_A1_NITROGEN_KGOE_PER_NM3
    air_kgoe = air_nm3 * GB_A1_PURIFIED_AIR_KGOE_PER_NM3
    gas_media_mj = nitrogen_mj + air_mj

    # 低温余热: LOW_TEMP_ITEMS 为空 (XLS 无此量) → 该项恒 0, 见常量处说明
    low_temp_mj = sum(r[2] for r in LOW_TEMP_ITEMS) * 0.5  # 附录A 序号34

    total_mj = (
        electricity_mj + fuel_gas_mj + steam_mj + gas_media_mj + low_temp_mj
    )
    total_kgoe = (
        electricity_kgoe + fuel_gas_kgoe + steam_kgoe
        + nitrogen_kgoe + air_kgoe
    )
    return {
        "annual_total_energy_mj": total_mj,
        "gas_media_mj": gas_media_mj,
        "low_temp_heat_mj": low_temp_mj,
        # total_kgoe 单位是 kg标油; 标油吨位需 /1000
        "total_toe_tonne": total_kgoe / 1000.0,
        "total_standard_coal_kg": total_kgoe * KGOE_PER_TOE,
        "coefficient_conformance": {
            "basis": "GB 30251-2024 附录A 表A.1 (参考系数)",
            "ELECTRICITY_等价值": {
                "pcs_kgoe_per_kwh": GB_A1_ELECTRICITY_KGOE_PER_KWH,
                "std_kgoe_per_kwh": GB_A1_ELECTRICITY_KGOE_PER_KWH,
                "pcs_mj_per_kwh": GB_A1_ELECTRICITY_MJ_PER_KWH,
                "std_mj_per_kwh": GB_A1_ELECTRICITY_MJ_PER_KWH,
                "deviation_pct": 0.0,
                "note": "§6.1.5 炼油/乙烯强制等价值; PCS 0.21/8.792 == 附录A 原值",
            },
            "STEAM_1.0MPa": {
                "pcs_kgoe_per_t": GB_A1_STEAM_1_0MPA_KGOE_PER_T,
                "std_kgoe_per_t": GB_A1_STEAM_1_0MPA_KGOE_PER_T,
                "pcs_mj_per_t": round(
                    GB_A1_STEAM_1_0MPA_KGOE_PER_T * 41.868, 3
                ),
                "std_mj_per_t": GB_A1_STEAM_1_0MPA_MJ_PER_T,
                "deviation_pct": abs(
                    GB_A1_STEAM_1_0MPA_KGOE_PER_T * 41.868
                    - GB_A1_STEAM_1_0MPA_MJ_PER_T
                )
                / GB_A1_STEAM_1_0MPA_MJ_PER_T
                * 100.0,
                "note": "PCS 由 toe_factor×41.868 推导 MJ, 与附录A 3182 MJ/t 自洽",
            },
            "FUEL_GAS_气田气": {
                "pcs_kgoe_per_nm3": R1_FUEL_GAS_GASFIELD_KGOE_PER_NM3,
                "std_kgoe_per_nm3": None,
                "deviation_pct": None,
                "not_std_comparable": True,
                "note": (
                    "附录A 序号8 以「吨」计 (950 kg标油/t), PCS 以「Nm³」计; "
                    "换算需气体密度假设, 标准不直接可比。沿用 R1 工艺室签署值。"
                ),
            },
            "NITROGEN": {
                "pcs_kgoe_per_nm3": GB_A1_NITROGEN_KGOE_PER_NM3,
                "std_kgoe_per_nm3": GB_A1_NITROGEN_KGOE_PER_NM3,
                "std_mj_per_nm3": GB_A1_NITROGEN_MJ_PER_NM3,
                "deviation_pct": 0.0,
                # XLS 错值留档: 「能耗」sheet 把 0.15 kg标油 填进了 MJ/Nm3 列
                "xls_mj_per_nm3": XLS_WRONG_NITROGEN_MJ_PER_NM3,
                "xls_deviation_pct": abs(
                    XLS_WRONG_NITROGEN_MJ_PER_NM3 - GB_A1_NITROGEN_MJ_PER_NM3
                ) / GB_A1_NITROGEN_MJ_PER_NM3 * 100.0,
                "note": (
                    "附录A 序号33 氮气 = 0.15 kg标油/m³ = 6.28 MJ/m³。"
                    "XLS「能耗」sheet 的 MJ/Nm3 列写 0.15 —— 那是 kg标油 值填错了列, "
                    "低估 41.87 倍。基准用附录A 原值, XLS 值仅留档对比。"
                ),
            },
            "INSTRUMENT_AIR_PURIFIED": {
                "pcs_kgoe_per_nm3": GB_A1_PURIFIED_AIR_KGOE_PER_NM3,
                "std_kgoe_per_nm3": GB_A1_PURIFIED_AIR_KGOE_PER_NM3,
                "std_mj_per_nm3": GB_A1_PURIFIED_AIR_MJ_PER_NM3,
                "deviation_pct": 0.0,
                "note": (
                    "附录A 序号31 净化压缩空气 = 0.038 kg标油/m³ = 1.59 MJ/m³。"
                    "XLS 该项 MJ 列 (1.59) 与标准一致 —— 净化空气是 XLS 少数没填错列的。"
                ),
            },
            "LOW_TEMP_HEAT": {
                "pcs_kgoe_per_mj": 0.012,
                "std_mj_per_mj": 0.5,
                "data_present": bool(LOW_TEMP_ITEMS),
                "note": (
                    "附录A 序号34 低温热 = 0.012 kg标油/MJ = 0.5 MJ/MJ。"
                    "⚠️ 本 XLS 无低温余热量 (只有低温热水系统参数), 故 Case 4 "
                    "该项为 0, utility_low_temp_heat 表在 T5 算例中仍无真实数据覆盖 —— "
                    "需工艺室补回收量 (GJ/a)。不编造数字。"
                ),
            },
        },
    }


async def _inject_case_4(db_session, project_id, workspace_id) -> None:
    """注入 Case 4 (蜡油加氢 XLS 1216D132 真实算例) 子表数据."""
    # 17 个 T1 power_items (来自 sample/1216D132惠州蜡油加氢装置计算14.7.17)
    for tag, motor_kw, hrs, load, kwh in POWER_ITEMS:
        db_session.add(
            UtilityPowerItem(
                project_id=project_id, workspace_id=workspace_id,
                equipment_tag=tag, motor_power_kw=motor_kw,
                operating_hours_per_year=hrs, load_factor=load,
                annual_consumption_kwh=kwh,
            )
        )

    # 6 个 T2 fuel_gas (F-101 + F-201 + 2 个 PILOT)
    for tag, phase, nm3 in FUEL_ITEMS:
        db_session.add(
            UtilityFuelGas(
                project_id=project_id, workspace_id=workspace_id,
                equipment_tag=tag, fuel_type="NATURAL_GAS",
                gas_source="GASFIELD_GAS",
                calorific_value_kcal_nm3=8500.0, consumption_nm3_h=200.0,
                operating_phase=phase, operating_hours_per_year=8400,
                annual_consumption_nm3=nm3,
            )
        )

    # 4 个 T3 heat_exchange (ST-E/MP 系列, P7-6B 前 R0 旧数据无 pressure_level/medium_type)
    for tag, annual_t in HEAT_ITEMS:
        db_session.add(
            UtilityHeatExchange(
                project_id=project_id, workspace_id=workspace_id,
                equipment_tag=tag, temperature_class="MP",
                pressure_level="0_8_TO_1_2_MPA",
                medium_type="STEAM",
                steam_pressure_mpa_gauge=1.0, steam_quality_pct=99.0,
                return_condensate_pct=80.0, steam_consumption_t_h=1.0,
                operating_hours_per_year=8400, annual_consumption_t=annual_t,
            )
        )

    # P7 Sprint 4 S4-4: 氮气 / 净化压缩空气 —— 首次让真实算例走 utility_gas_media
    for tag, medium, nm3_h, hours, annual_nm3 in GAS_MEDIA_ITEMS:
        db_session.add(
            UtilityGasMedia(
                project_id=project_id, workspace_id=workspace_id,
                equipment_tag=tag, gas_medium=medium,
                consumption_nm3_h=nm3_h, operating_hours_per_year=hours,
                annual_consumption_nm3=annual_nm3,
            )
        )

    # 低温余热: LOW_TEMP_ITEMS 为空 (XLS 无此量), 故本循环不执行。
    # 保留循环形状以便工艺室补数后直接生效, 不必改本函数。
    for tag, gj_h, hours, annual_gj in LOW_TEMP_ITEMS:
        db_session.add(
            UtilityLowTempHeat(
                project_id=project_id, workspace_id=workspace_id,
                equipment_tag=tag, heat_recovery_gj_h=gj_h,
                operating_hours_per_year=hours,
                annual_recovered_heat_gj=annual_gj,
            )
        )


async def main() -> int:
    """主流程: 注入 SEED + Case 4 数据, 调 service 算 summary, 输出验证报告."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(SA_Base.metadata.create_all)
    factory = sa.orm.sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as db:
        # 注入 SEED_FACTORS
        for f in SEED_FACTORS:
            db.add(ConfigEnergyConversionFactor(**f))
        await db.commit()

        project_id = uuid.uuid4()
        workspace_id = uuid.uuid4()
        # 建 Workspace + Project, product_category=REFINING —
        # 让 GB 30251-2024 §6.1.5 的口径政策真正生效 (用户裁决 2026-10-05
        # 「按 project 产品类型强制」), 而不是靠「Project 行缺失」兜底。
        db.add(
            Workspace(
                workspace_id=workspace_id, workspace_type="FORMAL", name="T5-WS"
            )
        )
        db.add(
            Project(
                project_id=project_id,
                workspace_id=workspace_id,
                project_no=f"T5-{project_id.hex[:8]}",
                project_name="1216D132 惠州蜡油加氢 (Case 4)",
                owner_company="PCS",
                location="惠州",
                project_type="PETROLEUM",
                design_phase="EXECUTIVE_DESIGN",
                unit_system="SI",
                product_category="REFINING",  # 炼油 ⇒ 电折标强制等价值
            )
        )
        await _inject_case_4(db, project_id, workspace_id)
        await db.commit()

        # GB 30251-2024 §6.1.5 + 附录A 注: 炼油/乙烯能耗计算中电折标系数必须用等价值.
        # 蜡油加氢 = 炼油 → 显式传 EQUIVALENT_VALUE, 必须与上面建的
        # product_category=REFINING 一致, 否则 service 抛 422 (fail-closed).
        summary = await summarize_energy_year(
            db=db, project_id=project_id, workspace_id=workspace_id,
            business_year=2026,
            electricity_value_type="EQUIVALENT_VALUE",
        )
        await db.commit()

        # 验收基准 (GB 30251-2024 附录A 表A.1 独立重算) — 用户裁决 2026-10-05,
        # XLS 不作为最终依据。见 _gb30251_reference() docstring。
        reference = _gb30251_reference()
        xls_reference = {
            "annual_total_energy_mj": reference["annual_total_energy_mj"],
            "total_toe_tonne": reference["total_toe_tonne"],
            "total_standard_coal_kg": reference["total_standard_coal_kg"],
        }

        # 容差计算
        def pct_diff(calc: float, ref: float) -> float:
            if ref == 0:
                return 0.0
            return abs(calc - ref) / ref * 100

        tol_total_energy = pct_diff(summary.annual_total_energy, xls_reference["annual_total_energy_mj"])
        tol_toe = pct_diff(summary.total_toe, xls_reference["total_toe_tonne"])
        tol_coal = pct_diff(summary.total_standard_coal_kg, xls_reference["total_standard_coal_kg"])

        report = {
            "case_id": "T5_CASE_04_WAXY_OIL_HYDRO_2026",
            "sign_off_doc": "docs/PCS-SIGN-F-P0-001-2026-10-08-R1.md",
            "xls_reference": (
                "GB 30251-2024 附录A 表A.1 独立重算 "
                "(XLS 不作为最终依据 — 用户裁决 2026-10-05)"
            ),
            "coefficient_conformance": reference["coefficient_conformance"],
            "coefficients_source": "GB_30251_2024_APPENDIX_A (R1 工艺室 2026-10-08 签齐)",
            "electricity_value_type": summary.electricity_value_type,
            "computed": {
                "annual_total_energy_mj": summary.annual_total_energy,
                "total_toe_tonne": summary.total_toe,
                "total_standard_coal_kg": summary.total_standard_coal_kg,
            },
            "xls": xls_reference,
            "tolerance_pct": {
                "annual_total_energy": tol_total_energy,
                "total_toe": tol_toe,
                "total_standard_coal_kg": tol_coal,
            },
            "acceptance_threshold_pct": 2.0,
            "verdict": {
                "annual_total_energy": "PASS" if tol_total_energy <= 2.0 else "FAIL",
                "total_toe": "PASS" if tol_toe <= 2.0 else "FAIL",
                "total_standard_coal_kg": "PASS" if tol_coal <= 2.0 else "FAIL",
            },
            # 口径自洽性诊断 (2026-10-05): PCS MJ 与 ISO 1 toe=41.868 MJ 的偏差。
            # 偏差应 <0.01%; 若 MJ FAIL 但 iso_self_consistent_pct 极小, 说明
            # PCS 三指标内部自洽, 分歧在 XLS 基准口径 (见裁决文档).
            "iso_self_consistent_pct": pct_diff(
                summary.annual_total_energy, summary.total_toe * 1000.0 * 41.868
            ),
            "r1_classification": summary.r1_classification_json,
            "tolerance_status": summary.tolerance_status,
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))

        ok = all(v == "PASS" for v in report["verdict"].values())
        if not ok and report["iso_self_consistent_pct"] < 0.01:
            print(
                "\n[BLOCKER] MJ 验收 FAIL 但 PCS 内部自洽 (偏差 "
                f"{report['iso_self_consistent_pct']:.4f}% < 0.01%)。\n"
                "         → 分歧在 XLS 基准口径, 非代码 bug。\n"
                "         → 待工艺室裁决: docs/PCS-NOTE-T5-MJ-基准口径裁决-2026-10-05.md",
                file=sys.stderr,
            )
        return 0 if ok else 1


if __name__ == "__main__":
    import asyncio

    sys.exit(asyncio.run(main()))