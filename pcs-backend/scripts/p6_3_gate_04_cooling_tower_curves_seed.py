"""P6-3 G-04：冷却塔特性曲线系数 CONFIG 数据录入（合成数据 + 工艺室确认占位）。

按 P6 计划 §Task 29 硬性前置 gate G-04：

- 冷却塔特性曲线 KaV/L = C × (L/G)^(−m)（P6 SPEC §3.2.4.2 CTI ATC-105
  通用参数），OPEN_CHANNEL 模块按 ``tower_model`` 匹配做 Merkel 冷却塔
  数值计算（Task 24 ``calc_tower_curve_kav_l``）。
- 本任务用 **合成数据**（4 行 CTI 通用型号），``source`` 字段统一标记
  ``SYNTHETIC_TEST_DATA``（参照 P5-OPEN-10 Kb 厂商数据合成模式）。
- 工艺工程师从 CTI ATC-105 ED7 替换真实参数后，须同步修改
  ``source`` 字段为具体期号（如 ``CTI_ATC-105_ED7_Table-3``），并在
  ``docs/p6-gate-reports/gate-04-cooling-tower-curves-confirmation.md``
  登记签字（``confirmed_by`` + ``confirmed_at``）。

用法：

    cd pcs-backend
    uv run python scripts/p6_3_gate_04_cooling_tower_curves_seed.py --dry-run
    uv run python scripts/p6_3_gate_04_cooling_tower_curves_seed.py      # 真库 upsert

upsert 语义：按 ``(tower_model, source)`` 唯一索引，存在则覆盖业务字段 +
``source``（``confirmed_by`` / ``confirmed_at`` / ``created_at`` 不自动覆盖
—— 由工艺室签字流程手动维护）。
"""
# ruff: noqa — 一次性 gate 录入脚本（单点收敛），非 app 代码
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 允许 ``uv run python scripts/xxx.py`` 直接调用；app 包从 pcs-backend 根解析。
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.dialects.postgresql import insert as pg_insert  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.models.config import CoolingTowerCurves  # noqa: E402

# -----------------------------------------------------------------------------
# 合成 cooling_tower_curves（4 行 CTI 通用型号）
# -----------------------------------------------------------------------------
# 真实 KaV/L 系数 C/m 由工艺工程师从 CTI ATC-105 ED7 获取；本任务用合成数
# 据占位（开发 / 测试用）；source 字段标记 SYNTHETIC_TEST_DATA 防误用于生产
# 报价。替换触发条件参见
# docs/p6-gate-reports/gate-04-cooling-tower-curves-confirmation.md。
SYNTHETIC_CTI_CURVES = [
    {
        "tower_model": "MARLEY-MD-STD",
        "curve_source": "CTI",
        "c_coefficient": 1.85,
        "m_exponent": 0.50,
        "l_g_ratio_min": 0.5,
        "l_g_ratio_max": 3.0,
        "source": "SYNTHETIC_TEST_DATA",
    },
    {
        "tower_model": "HAMON-FCC-STD",
        "curve_source": "CTI",
        "c_coefficient": 2.10,
        "m_exponent": 0.55,
        "l_g_ratio_min": 0.6,
        "l_g_ratio_max": 2.8,
        "source": "SYNTHETIC_TEST_DATA",
    },
    {
        "tower_model": "EVAPCO-LS-STD",
        "curve_source": "CTI",
        "c_coefficient": 1.95,
        "m_exponent": 0.52,
        "l_g_ratio_min": 0.7,
        "l_g_ratio_max": 3.5,
        "source": "SYNTHETIC_TEST_DATA",
    },
    {
        "tower_model": "BALTIMORE-TX-STD",
        "curve_source": "CTI",
        "c_coefficient": 2.05,
        "m_exponent": 0.48,
        "l_g_ratio_min": 0.5,
        "l_g_ratio_max": 3.2,
        "source": "SYNTHETIC_TEST_DATA",
    },
]


def _print_rows(label: str) -> None:
    """打印 4 行 CTI 曲线 + SYNTHETIC 注释（--dry-run 与执行后都用）。"""
    print(f"[{label}] cooling_tower_curves 共 {len(SYNTHETIC_CTI_CURVES)} 行（合成数据占位）：")
    print("  # 注：以下均为合成数据，仅用于开发/测试；真实 KaV/L 系数 C/m")
    print("  # 由工艺工程师从 CTI ATC-105 ED7 获取并替换。")
    print("  # 参见 docs/p6-gate-reports/gate-04-cooling-tower-curves-confirmation.md")
    print(
        f"  {'tower_model':<22}  {'src':<4}  {'C':>5}  {'m':>5}  "
        f"{'L/G_min':>7}  {'L/G_max':>7}  source"
    )
    for row in SYNTHETIC_CTI_CURVES:
        print(
            f"  {row['tower_model']:<22}  {row['curve_source']:<4}  "
            f"{row['c_coefficient']:>5.2f}  {row['m_exponent']:>5.2f}  "
            f"{row['l_g_ratio_min']:>7.2f}  {row['l_g_ratio_max']:>7.2f}  "
            f"{row['source']}"
        )


def _upsert(engine) -> tuple[int, int]:
    """PostgreSQL upsert：按 (tower_model, source) 唯一索引 ON CONFLICT DO UPDATE。

    覆盖业务字段 + ``source``；``confirmed_by`` / ``confirmed_at`` /
    ``created_at`` 不覆盖（工艺室签字字段 + DB 时间戳由触发器维护）。

    返回 (affected_count, total_rows_after)。
    """
    stmt = pg_insert(CoolingTowerCurves).values(SYNTHETIC_CTI_CURVES)
    stmt = stmt.on_conflict_do_update(
        index_elements=[
            CoolingTowerCurves.tower_model,
            CoolingTowerCurves.source,
        ],
        set_={
            "curve_source": stmt.excluded.curve_source,
            "c_coefficient": stmt.excluded.c_coefficient,
            "m_exponent": stmt.excluded.m_exponent,
            "l_g_ratio_min": stmt.excluded.l_g_ratio_min,
            "l_g_ratio_max": stmt.excluded.l_g_ratio_max,
            "notes": stmt.excluded.notes,
            "source": stmt.excluded.source,
        },
    )
    with engine.begin() as conn:
        conn.execute(stmt)
        total = conn.execute(select(CoolingTowerCurves)).scalars().all()
    return len(SYNTHETIC_CTI_CURVES), len(total)


def main() -> int:
    """CLI 入口：--dry-run 仅打印；默认 upsert 到 pcs/pcs_test 库。

    DATABASE_URL 由 ``app.core.config.get_settings()`` 解析（环境变量或
    .env 兜底）。真实数据库执行时，库内必须已应用 alembic 升级到包含
    ``p6_3_001_three_config_tables`` 的 head。
    """
    parser = argparse.ArgumentParser(description="G-04 冷却塔曲线数据录入")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅打印待录入数据，不连接数据库",
    )
    args = parser.parse_args()

    _print_rows(label="DRY-RUN" if args.dry_run else "EXECUTE")

    if args.dry_run:
        print("[DRY-RUN] 未连接数据库，未写入任何行。")
        return 0

    settings = get_settings()
    print(f"[EXECUTE] 数据库：{settings.database_url}")
    engine = create_engine(settings.database_url)
    try:
        affected, total = _upsert(engine)
    finally:
        engine.dispose()
    print(
        f"[EXECUTE] upsert 完成：受影响 {affected} 行；表内总计 {total} 行。"
    )
    print(
        "[EXECUTE] 工艺室确认占位文档："
        "docs/p6-gate-reports/gate-04-cooling-tower-curves-confirmation.md"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())