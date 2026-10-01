"""P7 Sprint 2 T0: config_energy_conversion_factors CONFIG 数据录入（折标煤系数）。

按 P7-OPEN-009 §6.3 CONFIG 折标煤系数 seed（P7-REV-02=A 触发；user ruling
2026-10-01 接受本批落 6 行折标系数）：

- 6 行能源类型折标油 / 折标煤系数：
  ELECTRICITY / FUEL_GAS / STEAM / WATER / GAS / LOW_TEMP_HEAT；
  用于 C-16 综合能耗汇总 ``utility_energy_summary_service`` 折标计算
  + 5-min TTL 缓存替换（参考 P6-5+ ``_compound_config_cache``）。
- 本任务用 **合成数据**（GB/T 50441 附录公开典型值的近似），``source``
  字段统一标记 ``SYNTHETIC_TEST_DATA``（参照 P6-5 4 张 compound_* CONFIG
  表模式）。
- 工艺工程师从 GB/T 50441 附录真实值替换后，须同步修改 ``source`` 字段
  为真实期号（如 ``GB_T_50441_APPENDIX``），并登记工艺室 2026-10-15
  签字。

用法：

    cd pcs-backend
    uv run python scripts/p7_open_009_t0_seed_energy_conversion_factors.py --dry-run
    uv run python scripts/p7_open_009_t0_seed_energy_conversion_factors.py        # 真库

数据语义：先 DELETE 表内所有 ``source='SYNTHETIC_TEST_DATA'`` 记录，再
INSERT 全量 6 行（幂等）。``confirmed_by`` / ``confirmed_at`` 不自动覆盖
—— 由工艺室 2026-10-15 签字流程手动维护。
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

from sqlalchemy import create_engine, delete, select  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.models.config import ConfigEnergyConversionFactor  # noqa: E402

# -----------------------------------------------------------------------------
# 合成 6 行折标油 / 折标煤系数（H-2 v1 BLOCKER 锁定；GB/T 50441 附录近似）
# -----------------------------------------------------------------------------
# 真实折标系数由工艺工程师从 GB/T 50441 附录替换；本任务用合成数据占位
# （开发 / 测试用）；source 字段标记 SYNTHETIC_TEST_DATA 防误用于生产。
# 单位口径：
#   toe_factor / standard_coal_factor = kg 标油 / 单位消耗量
#   电 = kWh / 燃料 = m³ / 蒸汽 = kg / 水 = kg / 气体 = m³ / 低温余热 = GJ
SYNTHETIC_ENERGY_CONVERSION: list[dict] = [
    {
        "energy_type": "ELECTRICITY",
        "toe_factor": 0.1229,          # kWh → kg 标油（GB/T 50441 附录表 A.1）
        "standard_coal_factor": 0.4040,  # kWh → kg 标煤（折算 1 toe = 1.4286 tce 反推）
    },
    {
        "energy_type": "FUEL_GAS",
        "toe_factor": 1.0000,          # m³ → kg 标油（按 1000 kcal/Nm³ ≈ 1.0 toe/m³ 近似）
        "standard_coal_factor": 1.4286,  # m³ → kg 标煤（同上）
    },
    {
        "energy_type": "STEAM",
        "toe_factor": 0.0760,          # kg 蒸汽 → kg 标油（按 1 MPa 饱和蒸汽 ≈ 76 kg 标油/t）
        "standard_coal_factor": 0.1086,  # kg 蒸汽 → kg 标煤
    },
    {
        "energy_type": "WATER",
        "toe_factor": 0.0001,          # kg 新鲜水 → kg 标油（GB/T 50441 附录 A.3）
        "standard_coal_factor": 0.0001,  # kg → kg 标煤
    },
    {
        "energy_type": "GAS",
        "toe_factor": 0.8500,          # m³ 工艺气体 → kg 标油（典型工艺气折算）
        "standard_coal_factor": 1.2143,  # m³ → kg 标煤
    },
    {
        "energy_type": "LOW_TEMP_HEAT",
        "toe_factor": 0.0341,          # GJ 低温余热 → kg 标油（按 1 GJ ≈ 0.0341 toe）
        "standard_coal_factor": 0.0487,  # GJ → kg 标煤
    },
]


def _print_rows(label: str) -> None:
    """打印 6 行折标系数 + SYNTHETIC 注释（--dry-run 与执行后都用）。"""
    print(
        f"[{label}] config_energy_conversion_factors 共 "
        f"{len(SYNTHETIC_ENERGY_CONVERSION)} 行"
        "（GB/T 50441 附录公开值近似；6 类能源）："
    )
    print("  # 注：以下均为合成数据，仅用于开发/测试；真实折标系数由工艺工程师")
    print("  # 从 GB/T 50441 附录获取并替换。")
    print("  # 参见 docs/p7-gate-reports/gate-p7-s2-t0-energy-conversion-confirmation.md")
    print(
        f"  {'energy_type':<18}  {'toe_factor':>12}  {'standard_coal_factor':>22}"
    )
    for row in SYNTHETIC_ENERGY_CONVERSION:
        print(
            f"  {row['energy_type']:<18}  {row['toe_factor']:>12.4f}  "
            f"{row['standard_coal_factor']:>22.4f}"
        )


def _replace_seed_rows(engine) -> tuple[int, int]:
    """先 DELETE ``source='SYNTHETIC_TEST_DATA'`` 行，再 INSERT 全量。

    幂等：第二次跑只剩 INSERT 6 行（DELETE 已无目标行）。
    """
    deleted = 0
    with engine.begin() as conn:
        # 1. DELETE 旧的 SYNTHETIC 行（幂等关键）
        stmt_del = delete(ConfigEnergyConversionFactor).where(
            ConfigEnergyConversionFactor.source == "SYNTHETIC_TEST_DATA"
        )
        result_del = conn.execute(stmt_del)
        deleted = result_del.rowcount or 0

        # 2. INSERT 全量 6 行
        for row in SYNTHETIC_ENERGY_CONVERSION:
            conn.execute(
                ConfigEnergyConversionFactor.__table__.insert().values(
                    energy_type=row["energy_type"],
                    toe_factor=row["toe_factor"],
                    standard_coal_factor=row["standard_coal_factor"],
                    source="SYNTHETIC_TEST_DATA",
                    # confirmed_by / confirmed_at 保持 NULL（工艺室 2026-10-15 签署后填）
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
