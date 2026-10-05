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
from app.models.util import (  # noqa: E402
    UtilityEnergySummary,
    UtilityFuelGas,
    UtilityHeatExchange,
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


async def _inject_case_4(db_session, project_id, workspace_id) -> None:
    """注入 Case 4 (蜡油加氢 XLS 1216D132 真实算例) 子表数据."""
    # 17 个 T1 power_items (来自 sample/1216D132惠州蜡油加氢装置计算14.7.17)
    power_items = [
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
    for tag, motor_kw, hrs, load, kwh in power_items:
        db_session.add(
            UtilityPowerItem(
                project_id=project_id, workspace_id=workspace_id,
                equipment_tag=tag, motor_power_kw=motor_kw,
                operating_hours_per_year=hrs, load_factor=load,
                annual_consumption_kwh=kwh,
            )
        )

    # 6 个 T2 fuel_gas (F-101 + F-201 + 2 个 PILOT)
    fuel_items = [
        ("F-101", "STEADY", 2244564.0),
        ("F-101", "MAX", 2469012.0),
        ("F-201", "STEADY", 9017736.0),
        ("F-201", "MAX", 9919476.0),
        ("F-101-PILOT", "STEADY", 870156.0),
        ("F-201-PILOT", "STEADY", 174048.0),
    ]
    for tag, phase, nm3 in fuel_items:
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
    heat_items = [
        ("ST-E-101", 1459.5),
        ("ST-E-102", 1459.5),
        ("ST-E-103", 9949.716),
        ("ST-TRACING", 16800.0),
    ]
    for tag, annual_t in heat_items:
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
        await _inject_case_4(db, project_id, workspace_id)
        await db.commit()

        summary = await summarize_energy_year(
            db=db, project_id=project_id, workspace_id=workspace_id,
            business_year=2026,
        )
        await db.commit()

        # XLS 参考值 (R1 工艺室 2026-10-08 签齐; 蜡油加氢原始 XLS 1216D132)
        xls_reference = {
            "annual_total_energy_mj": 1242159527.8,
            "total_toe_tonne": 28532.8967,
            "total_standard_coal_kg": 40761279.4,
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
            "xls_reference": "sample/1216D132惠州蜡油加氢装置计算14.7.17计算 - 副本.xlsm",
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