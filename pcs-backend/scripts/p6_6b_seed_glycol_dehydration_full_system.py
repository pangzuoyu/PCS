"""P6-6B T9: glycol_dehydration_full_system CONFIG 数据录入（C-16 典型工况范围）。

按 P6-6B 计划 Task 9 + brief（2026-09-27）：

- 10 行典型工况范围（TEG 浓度 / reboiler temperature / stripping gas rate /
  column diameter / column height / NTU / reflux ratio / contactor pressure /
  water removal efficiency / reboiler duty）。
- 本批用 **估算 min/max**（per GPSA Fig. 20-XX + McKetta-Wehe 公开典型值）；
  user ruling 2026-09-27：精确数值需工艺工程师从 GPSA + McKetta-Wehe 二次核对。
- ``source='GPSA Fig. 20-XX + McKetta-Wehe (TBD engineer verify)'``
- ``confirmed_by='P6-6B_ENG_TEAM_TBD'``（占位）
- ``confirmed_at='2026-09-28'``（占位）

⚠️ **估算值非工艺室签字值**：min/max 范围按 GPSA Fig. 20-XX + McKetta-Wehe
公开典型值估算，未与原文逐位核对；工艺工程师二次核对后须同步修改
min/max 数值 + ``source`` + ``confirmed_by`` 字段。

用法：

    cd pcs-backend
    uv run python scripts/p6_6b_seed_glycol_dehydration_full_system.py --dry-run
    uv run python scripts/p6_6b_seed_glycol_dehydration_full_system.py        # 真库

数据语义：先 DELETE 表内所有 ``source LIKE 'GPSA Fig%'`` 记录，再 INSERT
全量 10 行（幂等）。``confirmed_by`` / ``confirmed_at`` 不自动覆盖
—— 由工艺室签字流程手动维护（mirror Nielsen 1988 模式）。
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

from sqlalchemy import create_engine, delete, select  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.models.config import GlycolDehydrationFullSystem  # noqa: E402

# -----------------------------------------------------------------------------
# 估算 10 行典型工况范围（user ruling 2026-09-27；待二次核对）
# -----------------------------------------------------------------------------
# 真实 min/max 由工艺工程师从 GPSA Fig. 20-XX + McKetta-Wehe 替换；本任务
# 用估算数据占位（开发 / 测试用）；source 字段标记
# 'GPSA Fig. 20-XX + McKetta-Wehe (TBD engineer verify)' 防误用于生产。
ESTIMATED_GLYCOL_DEHYDRATION_FULL_SYSTEM: list[dict] = [
    {
        "parameter": "teg_concentration",
        "min_value": 95.0,
        "max_value": 99.9,
        "unit": "wt%",
        "notes": "Lean glycol purity",
    },
    {
        "parameter": "reboiler_temperature",
        "min_value": 350.0,
        "max_value": 400.0,
        "unit": "°F",
        "notes": "TEG reboiler typical",
    },
    {
        "parameter": "stripping_gas_rate",
        "min_value": 2.0,
        "max_value": 10.0,
        "unit": "scf/gal TEG",
        "notes": "Stripping gas per TEG circulation",
    },
    {
        "parameter": "column_diameter",
        "min_value": 1.0,
        "max_value": 10.0,
        "unit": "ft",
        "notes": "Typical contactor diameter range",
    },
    {
        "parameter": "column_height",
        "min_value": 15.0,
        "max_value": 80.0,
        "unit": "ft",
        "notes": "Typical packed section height",
    },
    {
        "parameter": "n_transfer_units",
        "min_value": 1.0,
        "max_value": 10.0,
        "unit": "NTU",
        "notes": "NTU typical range",
    },
    {
        "parameter": "reflux_ratio",
        "min_value": 0.5,
        "max_value": 3.0,
        "unit": "-",
        "notes": "TEG reflux at reflux",
    },
    {
        "parameter": "contactor_pressure",
        "min_value": 100.0,
        "max_value": 1500.0,
        "unit": "psia",
        "notes": "Operating pressure range",
    },
    {
        "parameter": "water_removal_efficiency",
        "min_value": 85.0,
        "max_value": 99.5,
        "unit": "%",
        "notes": "Dehydration efficiency range",
    },
    {
        "parameter": "reboiler_duty",
        "min_value": 100.0,
        "max_value": 5000.0,
        "unit": "kBtu/hr",
        "notes": "Reboiler duty range",
    },
]

SOURCE = "GPSA Fig. 20-XX + McKetta-Wehe (TBD engineer verify)"
CONFIRMED_BY_PLACEHOLDER = "P6-6B_ENG_TEAM_TBD"
CONFIRMED_AT_PLACEHOLDER = "2026-09-28"


def _print_rows(label: str) -> None:
    """打印 10 行典型工况范围 + 估算值注释（--dry-run 与执行后都用）。"""
    print(
        f"[{label}] glycol_dehydration_full_system 共 "
        f"{len(ESTIMATED_GLYCOL_DEHYDRATION_FULL_SYSTEM)} 行"
        "（TEG 浓度 / reboiler temp / stripping gas rate / column "
        "diameter / column height / NTU / reflux ratio / contactor "
        "pressure / water removal efficiency / reboiler duty）："
    )
    print("  # 注：以下 min/max 范围为估算值（user ruling 2026-09-27），")
    print("  # 未与 GPSA Fig. 20-XX + McKetta-Wehe 原文逐位核对；工艺工程师")
    print("  # 二次核对后须同步修改 min/max 数值 + source + confirmed_by 字段。")
    print(
        f"  {'parameter':<26}  {'min':>10}  {'max':>10}  {'unit':<14}  notes"
    )
    for row in ESTIMATED_GLYCOL_DEHYDRATION_FULL_SYSTEM:
        print(
            f"  {row['parameter']:<26}  {row['min_value']:>10.2f}  "
            f"{row['max_value']:>10.2f}  {row['unit']:<14}  {row['notes']}"
        )


def _replace_seed_rows(engine) -> tuple[int, int]:
    """先 DELETE ``source LIKE 'GPSA Fig%'`` 行，再 INSERT 全量 10 行。

    幂等：第二次跑只剩 INSERT 10 行（DELETE 已无目标行）。
    不覆盖 ``confirmed_by`` / ``confirmed_at``（被工艺室签字流程手动维护）；
    但本任务 DELETE 仅针对 ``source LIKE 'GPSA Fig%'``，工艺室已签字的
    真实数据行不会被触碰。

    返回 (deleted_count, inserted_count)。
    """
    deleted = 0
    inserted = len(ESTIMATED_GLYCOL_DEHYDRATION_FULL_SYSTEM)
    with engine.begin() as conn:
        # Step 1: DELETE 仅占位估算标记的行
        result = conn.execute(
            delete(GlycolDehydrationFullSystem).where(
                GlycolDehydrationFullSystem.source.like("GPSA Fig%"),
            )
        )
        deleted = result.rowcount or 0
        # Step 2: INSERT 全量 10 行（已注入 source / confirmed_by / confirmed_at）
        conn.execute(
            __import__("sqlalchemy").dialects.postgresql.insert(
                GlycolDehydrationFullSystem
            ).values(
                [
                    {
                        "parameter": row["parameter"],
                        "min_value": row["min_value"],
                        "max_value": row["max_value"],
                        "unit": row["unit"],
                        "notes": row["notes"],
                        "source": SOURCE,
                        "confirmed_by": CONFIRMED_BY_PLACEHOLDER,
                        "confirmed_at": CONFIRMED_AT_PLACEHOLDER,
                    }
                    for row in ESTIMATED_GLYCOL_DEHYDRATION_FULL_SYSTEM
                ]
            )
        )
    return deleted, inserted


def main() -> int:
    """CLI 入口：--dry-run 仅打印；默认 INSERT 10 行到 pcs/pcs_test 库。

    DATABASE_URL 由 ``app.core.config.get_settings()`` 解析。真实数据库执行
    时，库内必须已应用 alembic 升级到包含
    ``p6_6b_009_glycol_dehydration_full_system`` 的 head。
    """
    parser = argparse.ArgumentParser(
        description="C-16 glycol dehydration full system 典型工况数据录入",
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
        deleted, inserted = _replace_seed_rows(engine)
        # 最终行数校验
        with engine.connect() as conn:
            total = conn.execute(
                select(GlycolDehydrationFullSystem)
            ).scalars().all()
    finally:
        engine.dispose()
    print(
        f"[EXECUTE] DELETE 旧占位行 {deleted}；INSERT 新占位行 {inserted}；"
        f"表内总计 {len(total)} 行。"
    )
    print(
        "[EXECUTE] ⚠️  min/max 范围为估算值，未与 GPSA Fig. 20-XX + "
        "McKetta-Wehe 原文逐位核对；工艺工程师后续批次须二次核对。"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
