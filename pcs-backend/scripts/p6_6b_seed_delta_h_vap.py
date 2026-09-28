"""P6-6B T12: compound_delta_h_vap_natural_gas CONFIG 数据录入（C-21 fire case）。

按 P6-6B 计划 Task 12 + brief（2026-09-27）：

- 2 行 ΔH_vap 蒸发潜热（natural gas 路径，OPEN-P6-6A-5 关闭）：
  - ``TYPICAL_2260``：2260.0 kJ/kg（GPSA §3.4 typical natural gas）
  - ``XLS_CONVENTION_208``：208.0 kJ/kg（XLS PR-025 implicit convention）
- 本批录入：典型值取 GPSA §3.4 typical natural gas 公开值（2260）；XLS
  PR-025 隐式口径 208 = 1.878 kg/s × 208 kJ/kg 对账 XLS API 520 path G35
  （OPEN-P6-6A-5 Ruling 14 / 裁决 2026-09-27）。
- ``source='GPSA §3.4 typical + XLS PR-025 implicit'``
- ``confirmed_by='P6-6B_ENG_TEAM'``（per P6-6B 裁决，已签字）
- ``confirmed_at='2026-09-28'``（占位）

⚠️ **当前取典型值**：2260 = GPSA §3.4 typical natural gas 公开圆整值
（liquefied natural gas）；208 = XLS PR-025 implicit convention 工程师对账值。
工艺工程师二次核对后须同步修改数值 + ``source`` + ``confirmed_by`` 字段。

用法：

    cd pcs-backend
    uv run python scripts/p6_6b_seed_delta_h_vap.py --dry-run
    uv run python scripts/p6_6b_seed_delta_h_vap.py        # 真库

数据语义：INSERT 2 行 ON CONFLICT DO NOTHING（幂等；重跑无副作用）。
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
from app.models.config import CompoundDeltaHVapNaturalGas  # noqa: E402

# -----------------------------------------------------------------------------
# 2 行 ΔH_vap 蒸发潜热（GPSA §3.4 typical + XLS PR-025 implicit）
# -----------------------------------------------------------------------------
# convention: 口径标识（UNIQUE）；
# dh_vap_kj_kg: 数值（kJ/kg）；
# notes: 工程备注（典型工况语境）。
DELTA_H_VAP_ROWS: list[dict] = [
    {
        "convention": "TYPICAL_2260",
        "dh_vap_kj_kg": 2260.0,
        "notes": "GPSA §3.4 typical natural gas",
    },
    {
        "convention": "XLS_CONVENTION_208",
        "dh_vap_kj_kg": 208.0,
        "notes": "XLS PR-025 implicit convention",
    },
]

SOURCE = "GPSA §3.4 typical + XLS PR-025 implicit"
CONFIRMED_BY = "P6-6B_ENG_TEAM"
CONFIRMED_AT = "2026-09-28"


def _print_rows(label: str) -> None:
    """打印 2 行 ΔH_vap + 工艺室签字标注。"""
    print(
        f"[{label}] compound_delta_h_vap_natural_gas 共 {len(DELTA_H_VAP_ROWS)} 行"
        "（GPSA §3.4 typical + XLS PR-025 implicit，OPEN-P6-6A-5 关闭）："
    )
    print(
        f"  {'convention':<22}  {'dh_vap_kj_kg':>14}  notes"
    )
    for row in DELTA_H_VAP_ROWS:
        print(
            f"  {row['convention']:<22}  {row['dh_vap_kj_kg']:>14.2f}  "
            f"{row['notes']}"
        )
    print(
        f"  source={SOURCE!r} confirmed_by={CONFIRMED_BY!r} "
        f"confirmed_at={CONFIRMED_AT!r}"
    )


def _insert_seed_rows(engine) -> int:
    """INSERT 2 行 ON CONFLICT DO NOTHING（幂等）。

    返回实际 INSERT 行数（PG dialect 返回 rowcount）。
    """
    with engine.begin() as conn:
        result = conn.execute(
            __import__("sqlalchemy").dialects.postgresql.insert(
                CompoundDeltaHVapNaturalGas
            ).values(
                [
                    {
                        "convention": row["convention"],
                        "dh_vap_kj_kg": row["dh_vap_kj_kg"],
                        "notes": row["notes"],
                        "source": SOURCE,
                        "confirmed_by": CONFIRMED_BY,
                        "confirmed_at": CONFIRMED_AT,
                    }
                    for row in DELTA_H_VAP_ROWS
                ]
            ).on_conflict_do_nothing(index_elements=["convention"])
        )
        return result.rowcount or 0


def main() -> int:
    """CLI 入口：--dry-run 仅打印；默认 INSERT 2 行到 pcs/pcs_test 库。

    DATABASE_URL 由 ``app.core.config.get_settings()`` 解析。真实数据库执行
    时，库内必须已应用 alembic 升级到包含 ``p6_6b_012_delta_h_vap`` 的 head。
    """
    parser = argparse.ArgumentParser(
        description="C-21 fire case compound_delta_h_vap_natural_gas 数据录入",
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
                select(CompoundDeltaHVapNaturalGas)
            ).scalars().all()
    finally:
        engine.dispose()
    print(
        f"[EXECUTE] INSERT 新行 {inserted}（ON CONFLICT DO NOTHING）；"
        f"表内总计 {len(total)} 行。"
    )
    print(
        "[EXECUTE] 2260 = GPSA §3.4 typical natural gas 公开典型值；"
        "208 = XLS PR-025 implicit convention 工程师对账值；OPEN-P6-6A-5 关闭。"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())