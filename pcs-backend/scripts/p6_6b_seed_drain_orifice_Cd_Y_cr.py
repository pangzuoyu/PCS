"""P6-6B T13: ``drain_orifice_Cd_Y_cr`` CONFIG 数据录入（C-19 排污孔板 Cd/Y_cr）。

按 P6-6B 计划 Task 13 + brief（2026-09-27）：

- 6 行介质 → Cd / Y_cr / β range（C-19 排污孔板，OPEN-P6-6A-4 关闭）：
  - ``NATURAL_GAS``：β=0.0~0.7, Cd=0.83932, Y_cr=0.687
    （XLS PR-023 默认；notes='XLS PR-023 default'）
  - ``AIR``：β=0.0~0.7, Cd=0.84, Y_cr=0.72
  - ``STEAM``：β=0.0~0.7, Cd=0.83, Y_cr=0.55
  - ``WATER``：β=0.0~0.7, Cd=0.85, Y_cr=0.58
  - ``N2``：β=0.0~0.7, Cd=0.84, Y_cr=0.72
  - ``CO2``：β=0.0~0.7, Cd=0.83, Y_cr=0.65
- 本批录入：典型值取 XLS PR-023 + Miller (1990) discharge coefficients
  公开圆整值（NATURAL_GAS 用 XLS 默认；AIR/N2 典型 0.84/0.72；STEAM 0.83/0.55；
  WATER 0.85/0.58；CO2 0.83/0.65）。
- ``source='XLS PR-023 + Miller (1990) discharge coefficients'``
- ``confirmed_by='P6-6B_ENG_TEAM'``（per P6-6B 裁决，已签字）
- ``confirmed_at='2026-09-28'``（占位）

⚠️ **当前取典型值**：典型圆整值由工艺工程师从 XLS PR-023 + Miller 1990
公开论文二次核对。工艺工程师二次核对后须同步修改数值 + ``source`` +
``confirmed_by`` 字段。

用法：

    cd pcs-backend
    uv run python scripts/p6_6b_seed_drain_orifice_Cd_Y_cr.py --dry-run
    uv run python scripts/p6_6b_seed_drain_orifice_Cd_Y_cr.py        # 真库

数据语义：INSERT 6 行 ON CONFLICT DO NOTHING（幂等；重跑无副作用）。
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

from app.core.config import get_settings  # noqa: E402
from app.models.config import DrainOrificeCdYCr  # noqa: E402

# -----------------------------------------------------------------------------
# 6 行 Cd/Y_cr 流量系数（XLS PR-023 + Miller 1990 公开圆整值）
# -----------------------------------------------------------------------------
# fluid: 介质 UNIQUE；
# beta_range_min / beta_range_max: β 直径比范围（无量纲）；
# cd: 流量系数（无量纲）；
# y_cr: 临界压力比（无量纲）；
# notes: 工程备注。
DRAIN_ORIFICE_CD_Y_CR_ROWS: list[dict] = [
    {
        "fluid": "NATURAL_GAS",
        "beta_range_min": 0.0,
        "beta_range_max": 0.7,
        "cd": 0.83932,
        "y_cr": 0.687,
        "notes": "XLS PR-023 default",
    },
    {
        "fluid": "AIR",
        "beta_range_min": 0.0,
        "beta_range_max": 0.7,
        "cd": 0.84,
        "y_cr": 0.72,
        "notes": None,
    },
    {
        "fluid": "STEAM",
        "beta_range_min": 0.0,
        "beta_range_max": 0.7,
        "cd": 0.83,
        "y_cr": 0.55,
        "notes": None,
    },
    {
        "fluid": "WATER",
        "beta_range_min": 0.0,
        "beta_range_max": 0.7,
        "cd": 0.85,
        "y_cr": 0.58,
        "notes": None,
    },
    {
        "fluid": "N2",
        "beta_range_min": 0.0,
        "beta_range_max": 0.7,
        "cd": 0.84,
        "y_cr": 0.72,
        "notes": None,
    },
    {
        "fluid": "CO2",
        "beta_range_min": 0.0,
        "beta_range_max": 0.7,
        "cd": 0.83,
        "y_cr": 0.65,
        "notes": None,
    },
]

SOURCE = "XLS PR-023 + Miller (1990) discharge coefficients"
CONFIRMED_BY = "P6-6B_ENG_TEAM"
CONFIRMED_AT = "2026-09-28"


def _print_rows(label: str) -> None:
    """打印 6 行 Cd/Y_cr + 工艺室签字标注。"""
    print(
        f"[{label}] drain_orifice_Cd_Y_cr 共 {len(DRAIN_ORIFICE_CD_Y_CR_ROWS)} 行"
        "（XLS PR-023 + Miller 1990，OPEN-P6-6A-4 关闭）："
    )
    print(
        f"  {'fluid':<14}  {'beta_min':>8}  {'beta_max':>8}  {'cd':>8}  {'y_cr':>10}  notes"
    )
    for row in DRAIN_ORIFICE_CD_Y_CR_ROWS:
        notes_str = row["notes"] if row["notes"] else ""
        print(
            f"  {row['fluid']:<14}  {row['beta_range_min']:>8.2f}  "
            f"{row['beta_range_max']:>8.2f}  {row['cd']:>8.5f}  "
            f"{row['y_cr']:>10.4f}  {notes_str}"
        )
    print(
        f"  source={SOURCE!r} confirmed_by={CONFIRMED_BY!r} "
        f"confirmed_at={CONFIRMED_AT!r}"
    )


def _insert_seed_rows(engine) -> int:
    """INSERT 6 行 ON CONFLICT DO NOTHING（幂等）。

    返回实际 INSERT 行数（PG dialect 返回 rowcount）。
    """
    with engine.begin() as conn:
        result = conn.execute(
            __import__("sqlalchemy").dialects.postgresql.insert(
                DrainOrificeCdYCr
            ).values(
                [
                    {
                        "fluid": row["fluid"],
                        "beta_range_min": row["beta_range_min"],
                        "beta_range_max": row["beta_range_max"],
                        "cd": row["cd"],
                        "y_cr": row["y_cr"],
                        "notes": row["notes"],
                        "source": SOURCE,
                        "confirmed_by": CONFIRMED_BY,
                        "confirmed_at": CONFIRMED_AT,
                    }
                    for row in DRAIN_ORIFICE_CD_Y_CR_ROWS
                ]
            ).on_conflict_do_nothing(index_elements=["fluid"])
        )
        return result.rowcount or 0


def main() -> int:
    """CLI 入口：--dry-run 仅打印；默认 INSERT 6 行到 pcs/pcs_test 库。

    DATABASE_URL 由 ``app.core.config.get_settings()`` 解析。真实数据库执行
    时，库内必须已应用 alembic 升级到包含 ``p6_6b_013_drain_orifice_Cd_Y_cr``
    的 head。
    """
    parser = argparse.ArgumentParser(
        description="C-19 drain_orifice Cd/Y_cr CONFIG 数据录入",
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
        inserted = _insert_seed_rows(engine)
        with engine.connect() as conn:
            total = conn.execute(
                select(DrainOrificeCdYCr)
            ).scalars().all()
    finally:
        engine.dispose()
    print(
        f"[EXECUTE] INSERT 新行 {inserted}（ON CONFLICT DO NOTHING）；"
        f"表内总计 {len(total)} 行。"
    )
    print(
        "[EXECUTE] 典型值取 XLS PR-023 + Miller (1990) 公开圆整值；"
        "OPEN-P6-6A-4 关闭；feature flag _USE_XLS_CD_Y_CR 默认 False。"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())