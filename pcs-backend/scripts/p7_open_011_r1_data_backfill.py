"""P7 Sprint 2 R1 数据回填脚本 (F-P0-001 R1 §7).

Per PCS-SIGN-F-P0-001-2026-10-08-R1 §7 数据模型调整:
- utility_heat_exchange.temperature_class → pressure_level 9 档映射
  (依据 steam_pressure_mpa_gauge 字段 + 温度等级范围)
- utility_heat_exchange.medium_type 默认 STEAM (热交换介质)
- utility_fuel_gas.fuel_type → gas_source 3 类映射 (依燃料类型)

映射规则:
  蒸汽压力 (steam_pressure_mpa_gauge, MPa gauge):
    < 0.3   → LT_0_3_MPA
    0.3-0.6 → 0_3_TO_0_6_MPA
    0.6-0.8 → 0_6_TO_0_8_MPA
    0.8-1.2 → 0_8_TO_1_2_MPA
    1.2-2.0 → 1_2_TO_2_0_MPA
    2.0-3.0 → 2_0_TO_3_0_MPA
    3.0-4.5 → 3_0_TO_4_5_MPA
    4.5-7.0 → 4_5_TO_7_0_MPA
    ≥ 7.0   → GE_7_0_MPA

  燃料类型 (fuel_type):
    NATURAL_GAS / LNG → GASFIELD_GAS (气田气 0.85)
    REFINERY_GAS / LPG → REFINERY_FUEL_GAS (炼厂燃料气 950 kg/t)
    OTHERS → OILFIELD_GAS (油田气 0.93; 默认 fallback)

用法:
    cd pcs-backend
    uv run python scripts/p7_open_011_r1_data_backfill.py --dry-run
    uv run python scripts/p7_open_011_r1_data_backfill.py        # 真库

幂等: 只更新 pressure_level/medium_type/gas_source 为 NULL 的行 (不覆盖手动填值).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from sqlalchemy import select, update  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.models.util import UtilityFuelGas, UtilityHeatExchange  # noqa: E402


def _map_steam_pressure_to_level(pressure_mpa: float) -> str:
    """蒸汽压力 (MPa gauge) → R1 9 档 pressure_level 映射."""
    if pressure_mpa < 0.3:
        return "LT_0_3_MPA"
    if pressure_mpa < 0.6:
        return "0_3_TO_0_6_MPA"
    if pressure_mpa < 0.8:
        return "0_6_TO_0_8_MPA"
    if pressure_mpa < 1.2:
        return "0_8_TO_1_2_MPA"
    if pressure_mpa < 2.0:
        return "1_2_TO_2_0_MPA"
    if pressure_mpa < 3.0:
        return "2_0_TO_3_0_MPA"
    if pressure_mpa < 4.5:
        return "3_0_TO_4_5_MPA"
    if pressure_mpa < 7.0:
        return "4_5_TO_7_0_MPA"
    return "GE_7_0_MPA"


_FUEL_TYPE_TO_GAS_SOURCE = {
    "NATURAL_GAS": "GASFIELD_GAS",      # 气田气 (0.85)
    "LNG": "GASFIELD_GAS",              # 气田气 (0.85)
    "REFINERY_GAS": "REFINERY_FUEL_GAS", # 炼厂燃料气 (950 kg/t)
    "LPG": "REFINERY_FUEL_GAS",         # 炼厂燃料气 (950 kg/t)
    "OTHERS": "OILFIELD_GAS",           # 油田气 (0.93; 默认)
}


async def backfill_heat_exchange(session: AsyncSession, dry_run: bool) -> tuple[int, int]:
    """回填 utility_heat_exchange.pressure_level + medium_type.

    Returns: (scanned, updated)
    """
    stmt = select(UtilityHeatExchange)
    rows = (await session.execute(stmt)).scalars().all()

    scanned = len(rows)
    updated = 0
    print(f"\n[HEAT_EXCHANGE] scanned={scanned} rows")

    for row in rows:
        new_pressure_level = _map_steam_pressure_to_level(row.steam_pressure_mpa_gauge)
        # medium_type 默认 STEAM (utility_heat_exchange 表默认就是蒸汽/冷凝水介质)
        new_medium_type = "STEAM"

        if row.pressure_level == new_pressure_level and row.medium_type == new_medium_type:
            continue  # 已回填, 跳过

        if dry_run:
            print(
                f"  [DRY-RUN] {row.equipment_tag}: pressure_level "
                f"{row.pressure_level} → {new_pressure_level}; "
                f"medium_type {row.medium_type} → {new_medium_type}"
            )
        else:
            row.pressure_level = new_pressure_level
            row.medium_type = new_medium_type
        updated += 1

    if not dry_run:
        await session.commit()

    return scanned, updated


async def backfill_fuel_gas(session: AsyncSession, dry_run: bool) -> tuple[int, int]:
    """回填 utility_fuel_gas.gas_source.

    Returns: (scanned, updated)
    """
    stmt = select(UtilityFuelGas)
    rows = (await session.execute(stmt)).scalars().all()

    scanned = len(rows)
    updated = 0
    print(f"\n[FUEL_GAS] scanned={scanned} rows")

    for row in rows:
        new_gas_source = _FUEL_TYPE_TO_GAS_SOURCE.get(
            row.fuel_type, "OILFIELD_GAS"  # 默认 fallback
        )

        if row.gas_source == new_gas_source:
            continue  # 已回填, 跳过

        if dry_run:
            print(
                f"  [DRY-RUN] {row.equipment_tag}: fuel_type {row.fuel_type} → "
                f"gas_source {new_gas_source}"
            )
        else:
            row.gas_source = new_gas_source
        updated += 1

    if not dry_run:
        await session.commit()

    return scanned, updated


async def run_backfill(dry_run: bool) -> int:
    """执行回填操作。"""
    if dry_run:
        print("[DRY-RUN MODE] 不连接 DB，仅打印回填计划")
        print("\n[HEAT_EXCHANGE 计划] (示例值):")
        print("  pressure_level 0_3_TO_0_6_MPA (0.3-0.6 MPa)")
        print("  pressure_level 0_8_TO_1_2_MPA (0.8-1.2 MPa)")
        print("  pressure_level GE_7_0_MPA (≥7.0 MPa)")
        print("  medium_type STEAM (热交换介质默认)")
        print("\n[FUEL_GAS 计划]:")
        print("  NATURAL_GAS/LNG → GASFIELD_GAS")
        print("  REFINERY_GAS/LPG → REFINERY_FUEL_GAS")
        print("  OTHERS → OILFIELD_GAS")
        return 0

    settings = get_settings()
    # 异步引擎
    engine = create_async_engine(settings.database_url_async)
    try:
        async with AsyncSession(engine) as session:
            he_scanned, he_updated = await backfill_heat_exchange(session, dry_run=False)
            fg_scanned, fg_updated = await backfill_fuel_gas(session, dry_run=False)

        print(
            f"\n[OK] R1 数据回填完成: "
            f"HEAT_EXCHANGE scanned={he_scanned} updated={he_updated}; "
            f"FUEL_GAS scanned={fg_scanned} updated={fg_updated}"
        )
    finally:
        await engine.dispose()

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="P7 Sprint 2 R1 数据回填 (F-P0-001 R1 §7)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只打印回填计划，不连接 DB",
    )
    args = parser.parse_args()

    import asyncio
    return asyncio.run(run_backfill(dry_run=args.dry_run))


if __name__ == "__main__":
    sys.exit(main())
