"""P7 Sprint 2 T0: config_energy_conversion_factors CONFIG 数据录入（折标煤系数）。

按 P7-OPEN-009 §6.3 CONFIG 折标煤系数 seed（P7-REV-02=A 触发）+ 工艺室
PCS-SIGN-F-P0-001-2026-10-08 正式签字确认：

- 6 行能源类型折标油 / 折标煤系数（per-tonne / per-Nm³ / per-kWh 混合口径）：
  ELECTRICITY / FUEL_GAS / STEAM / WATER / NITROGEN / INSTRUMENT_AIR；
  用于 C-16 综合能耗汇总 ``utility_energy_summary_service`` 折标计算。
- 数据值依据 GB/T 50441-2016《石油化工企业能耗计算标准》附录 A：
  - 蒸汽 94.4 per-tonne = 0.0944 kg标油/kg × 1000
  - 水 0.1 per-tonne = 0.0001 kg标油/kg × 1000
  - 其他 4 类 per-Nm³ 或 per-kWh 直接引用附录 A
- ``source`` 字段标记 ``GB_T_50441_2016_APPENDIX_A``（工艺室签字来源）。
- ``confirmed_by`` = "工艺室-工艺负责人-2026-10-08"
- ``confirmed_at`` = "2026-10-08T00:00:00+08:00"

用法：

    cd pcs-backend
    uv run python scripts/p7_open_009_t0_seed_energy_conversion_factors.py --dry-run
    uv run python scripts/p7_open_009_t0_seed_energy_conversion_factors.py        # 真库

数据语义：先 DELETE 表内所有 ``source='SYNTHETIC_TEST_DATA'`` 记录，再
INSERT 全量 6 行（幂等）。``confirmed_by`` / ``confirmed_at`` 由工艺室
2026-10-08 签字流程固定维护（Sprint 2 之后正式值）。
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
# 工艺室正式确认 6 行折标油 / 折标煤系数（PCS-SIGN-F-P0-001-2026-10-08）
# -----------------------------------------------------------------------------
# 依据 GB/T 50441-2016《石油化工企业能耗计算标准》附录 A：
# - 质量类能源（蒸汽、水）per-tonne（GB/T 50441 附录 per-kg × 1000）
# - 体积类能源（燃料气、氮气、仪表空气）per-Nm³（附录 A 直接引用）
# - 电 per-kWh（附录 A 直接引用）
# source 字段 = "GB_T_50441_2016_APPENDIX_A"（工艺室签字来源）
# confirmed_by / confirmed_at 由工艺室 2026-10-08 签字流程固定维护
SIGNED_ENERGY_CONVERSION: list[dict] = [
    {
        "energy_type": "ELECTRICITY",
        "toe_factor": 0.1229,            # kWh → kg 标油（GB/T 50441 附录 A.1 直接引用）
        "standard_coal_factor": 0.1229,  # kWh → kg 标煤（工艺室 2026-10-08 确认值）
    },
    {
        "energy_type": "FUEL_GAS",
        "toe_factor": 1.0000,            # Nm³ → kg 标油（GB/T 50441 附录 A.2 直接引用）
        "standard_coal_factor": 1.4286,  # Nm³ → kg 标煤（1 toe × 1.4286）
    },
    {
        "energy_type": "STEAM",
        "toe_factor": 94.4,              # t per-tonne 口径；0.0944 kg标油/kg × 1000（GB/T 50441-2016 附录 A.3）
        "standard_coal_factor": 128.6,  # t per-tonne 口径；0.1286 kg标煤/kg × 1000
    },
    {
        "energy_type": "WATER",
        "toe_factor": 0.1,               # t per-tonne 口径；0.0001 kg标油/kg × 1000（GB/T 50441-2016 附录 A.5 冷却水）
        "standard_coal_factor": 0.136,   # t per-tonne 口径；0.000136 kg标煤/kg × 1000
    },
    {
        "energy_type": "NITROGEN",
        "toe_factor": 0.0004,            # Nm³ → kg 标油（GB/T 50441 附录 A 直接引用）
        "standard_coal_factor": 0.000571,  # Nm³ → kg 标煤
    },
    {
        "energy_type": "INSTRUMENT_AIR",
        "toe_factor": 0.00012,           # Nm³ → kg 标油（GB/T 50441 附录 A 直接引用）
        "standard_coal_factor": 0.000171,  # Nm³ → kg 标煤
    },
]

# 工艺室签字元数据（PCS-SIGN-F-P0-001-2026-10-08）
CONFIRMED_BY = "工艺室-工艺负责人-2026-10-08"
CONFIRMED_AT = datetime.datetime(
    2026, 10, 8, 0, 0, 0,
    tzinfo=datetime.timezone(datetime.timedelta(hours=8)),
)
SOURCE = "GB_T_50441_2016_APPENDIX_A"


def _print_rows(label: str) -> None:
    """打印 6 行折标系数（GB/T 50441-2016 附录 A 工艺室签字值）。"""
    print(
        f"[{label}] config_energy_conversion_factors 共 "
        f"{len(SIGNED_ENERGY_CONVERSION)} 行"
        f"（GB/T 50441-2016 附录 A 工艺室签字 PCS-SIGN-F-P0-001-2026-10-08）："
    )
    print(f"  # source = {SOURCE}")
    print(f"  # confirmed_by = {CONFIRMED_BY}")
    print(f"  # confirmed_at = {CONFIRMED_AT.isoformat()}")
    print(
        f"  {'energy_type':<18}  {'toe_factor':>12}  {'standard_coal_factor':>22}"
    )
    for row in SIGNED_ENERGY_CONVERSION:
        print(
            f"  {row['energy_type']:<18}  {row['toe_factor']:>12.4f}  "
            f"{row['standard_coal_factor']:>22.4f}"
        )


def _replace_seed_rows(engine) -> tuple[int, int]:
    """先 DELETE 旧 source 行（含 SYNTHETIC_TEST_DATA 与 GB_T_50441_2016_APPENDIX_A），再 INSERT 全量。

    幂等：第二次跑只剩 INSERT 6 行（DELETE 已无目标行）。
    """
    deleted = 0
    with engine.begin() as conn:
        # 1. DELETE 旧行（幂等关键：SYNTHETIC_TEST_DATA + GB_T_50441_2016_APPENDIX_A 都删）
        stmt_del = delete(ConfigEnergyConversionFactor).where(
            ConfigEnergyConversionFactor.source.in_([
                "SYNTHETIC_TEST_DATA",
                SOURCE,
            ])
        )
        result_del = conn.execute(stmt_del)
        deleted = result_del.rowcount or 0

        # 2. INSERT 全量 6 行（工艺室签字值）
        for row in SIGNED_ENERGY_CONVERSION:
            conn.execute(
                ConfigEnergyConversionFactor.__table__.insert().values(
                    energy_type=row["energy_type"],
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
        description="P7 Sprint 2 T0: config_energy_conversion_factors seed"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只打印 6 行内容，不连接 DB",
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
