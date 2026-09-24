"""P6-3 G-06：火炬地面辐射热通量 BEDD 限值 CONFIG 数据录入（API 521 真实值 + 工艺室确认占位）。

按 P6 计划 §Task 29 硬性前置 gate G-06：

- BEDD（Burnout / Exposure / Duty）三档 4.73 / 6.31 / 12.6 kW/m²
  （P6 SPEC §3.2.3.5 + API 521 §7.4.2.3）：
  - ``PROPERTY_LINE``：财产线（持续 30 min 不引起木材燃烧等财产损失）；
  - ``PERSONNEL``：人员持续暴露限值；
  - ``EMERGENCY``：紧急疏散限值。
- Task 22 ``radiation_check`` 当前硬编码以上 3 档；本任务入库后，可在
  后续批联动重构为 DB 读取（避免硬编码）。
- **本任务与 G-04/05 不同**：3 行默认数据来自 **API 521 真实公开限值**
  （非合成），``source`` 直接写 ``'API521_§7.4.2.3'``；由工艺室签字
  确认后填入 ``confirmed_by`` / ``confirmed_at``（不自动覆盖）。

用法：

    cd pcs-backend
    uv run python scripts/p6_3_gate_06_flare_radiation_limits_seed.py --dry-run
    uv run python scripts/p6_3_gate_06_flare_radiation_limits_seed.py      # 真库 upsert

upsert 语义：按 ``limit_type`` 唯一索引，存在则覆盖 ``q_kw_m2_limit`` +
``distance_m`` + ``effective_height_m`` + ``notes`` + ``source``；
``confirmed_by`` / ``confirmed_at`` / ``created_at`` 不覆盖。
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
from app.models.config import FlareRadiationLimits  # noqa: E402

# -----------------------------------------------------------------------------
# 合成 flare_radiation_limits（3 行 = API 521 §7.4.2.3 BEDD 三档真实限值）
# -----------------------------------------------------------------------------
# 真实 BEDD 限值由 API 521 §7.4.2.3 公开给出；本任务录入即用真实值，
# ``source`` 字段写 ``API521_§7.4.2.3`` 标记；confirmed_by/at 待工艺室
# 签字时填入。
SYNTHETIC_RADIATION_LIMITS = [
    {
        "limit_type": "PROPERTY_LINE",
        "q_kw_m2_limit": 4.73,
        "distance_m": None,
        "effective_height_m": None,
        "source": "API521_§7.4.2.3",
    },
    {
        "limit_type": "PERSONNEL",
        "q_kw_m2_limit": 6.31,
        "distance_m": None,
        "effective_height_m": None,
        "source": "API521_§7.4.2.3",
    },
    {
        "limit_type": "EMERGENCY",
        "q_kw_m2_limit": 12.6,
        "distance_m": None,
        "effective_height_m": None,
        "source": "API521_§7.4.2.3",
    },
]


def _print_rows(label: str) -> None:
    """打印 3 行 BEDD 限值 + API 521 来源注释（--dry-run 与执行后都用）。"""
    print(
        f"[{label}] flare_radiation_limits 共 {len(SYNTHETIC_RADIATION_LIMITS)} 行"
        "（API 521 §7.4.2.3 真实公开限值）："
    )
    print("  # 注：本表 3 行即 BEDD 三档真实公开限值（API 521 §7.4.2.3），")
    print("  # 非合成数据；工艺室签字后填入 confirmed_by/at。")
    print("  # 参见 docs/p6-gate-reports/gate-06-flare-radiation-limits-confirmation.md")
    print(
        f"  {'limit_type':<14}  {'q_kw_m2_limit':>14}  source"
    )
    for row in SYNTHETIC_RADIATION_LIMITS:
        print(
            f"  {row['limit_type']:<14}  {row['q_kw_m2_limit']:>14.2f}  "
            f"{row['source']}"
        )


def _upsert(engine) -> tuple[int, int]:
    """PostgreSQL upsert：按 limit_type 唯一索引 ON CONFLICT DO UPDATE。

    覆盖业务字段 + ``source``；``confirmed_by`` / ``confirmed_at`` /
    ``created_at`` 不覆盖（工艺室签字字段 + DB 时间戳由触发器维护）。

    返回 (affected_count, total_rows_after)。
    """
    stmt = pg_insert(FlareRadiationLimits).values(SYNTHETIC_RADIATION_LIMITS)
    stmt = stmt.on_conflict_do_update(
        index_elements=[FlareRadiationLimits.limit_type],
        set_={
            "q_kw_m2_limit": stmt.excluded.q_kw_m2_limit,
            "distance_m": stmt.excluded.distance_m,
            "effective_height_m": stmt.excluded.effective_height_m,
            "notes": stmt.excluded.notes,
            "source": stmt.excluded.source,
        },
    )
    with engine.begin() as conn:
        conn.execute(stmt)
        total = conn.execute(select(FlareRadiationLimits)).scalars().all()
    return len(SYNTHETIC_RADIATION_LIMITS), len(total)


def main() -> int:
    """CLI 入口：--dry-run 仅打印；默认 upsert 到 pcs/pcs_test 库。

    DATABASE_URL 由 ``app.core.config.get_settings()`` 解析（环境变量或
    .env 兜底）。真实数据库执行时，库内必须已应用 alembic 升级到包含
    ``p6_3_001_three_config_tables`` 的 head。
    """
    parser = argparse.ArgumentParser(
        description="G-06 火炬地面辐射热通量 BEDD 限值录入",
    )
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
        "docs/p6-gate-reports/gate-06-flare-radiation-limits-confirmation.md"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())