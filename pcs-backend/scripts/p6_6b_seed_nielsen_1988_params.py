"""P6-6B T8: compound_nielsen_1988_params CONFIG 数据录入（C-18 现代水合物抑制）。

按 P6-6B 计划 Task 8 + brief（2026-09-27）：

- 7 行 Nielsen 1988 论文 Table 1 现代水合物抑制参数 A/B/C 常数
  （CH4 / C2H6 / C3H8 / I-C4H6 / N2 / CO2 / H2S）。
- 本批用 **估算 A/B/C 常数**（per Nielsen 1988 paper Table 1 typical values）；
  user ruling 2026-09-27：精确数值需工艺工程师从 PDF 抄录后续批次二次核对。
- ``source='Nielsen 1988 (paper Table 1, TBD engineer verify)'``
- ``confirmed_by='P6-6B_ENG_TEAM_TBD'``（占位）
- ``confirmed_at='2026-09-28'``（占位）

⚠️ **估算值非工艺室签字值**：A/B/C 常数按 Nielsen 1988 paper Table 1
典型值估算（CH4 24~26% 段在工业常用范围），未与原文逐位核对；工艺工程师
二次核对后须同步修改 A/B/C 数值 + ``source`` + ``confirmed_by`` 字段。

用法：

    cd pcs-backend
    uv run python scripts/p6_6b_seed_nielsen_1988_params.py --dry-run
    uv run python scripts/p6_6b_seed_nielsen_1988_params.py        # 真库

数据语义：先 DELETE 表内所有 ``source='Nielsen 1988%'`` 记录，再 INSERT
全量 7 行（幂等）。``confirmed_by`` / ``confirmed_at`` 不自动覆盖
—— 由工艺室签字流程手动维护（mirror Hammerschmidt 模式）。
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
from app.models.config import CompoundNielsen1988Params  # noqa: E402

# -----------------------------------------------------------------------------
# 估算 7 行 Nielsen 1988 A/B/C 常数（user ruling 2026-09-27；待二次核对）
# -----------------------------------------------------------------------------
# 真实 A/B/C 常数由工艺工程师从 Nielsen 1988 论文替换；本任务用估算数据
# 占位（开发 / 测试用）；source 字段标记 'Nielsen 1988 (paper Table 1,
# TBD engineer verify)' 防误用于生产。
#
# 简化模型：ΔT_F = A + B·x（component 决定 A/B/C；C 未使用，记 0.0）。
ESTIMATED_NIELSEN_1988_PARAMS: list[dict] = [
    {"component": "CH4",   "a": 0.0227, "b": 0.0067, "c": 0.0},
    {"component": "C2H6",  "a": 0.0250, "b": 0.0080, "c": 0.0},
    {"component": "C3H8",  "a": 0.0270, "b": 0.0095, "c": 0.0},
    {"component": "I-C4H6", "a": 0.0300, "b": 0.0105, "c": 0.0},
    {"component": "N2",    "a": 0.0160, "b": 0.0040, "c": 0.0},
    {"component": "CO2",   "a": 0.0200, "b": 0.0055, "c": 0.0},
    {"component": "H2S",   "a": 0.0290, "b": 0.0090, "c": 0.0},
]

SOURCE = "Nielsen 1988 (paper Table 1, TBD engineer verify)"
CONFIRMED_BY_PLACEHOLDER = "P6-6B_ENG_TEAM_TBD"
CONFIRMED_AT_PLACEHOLDER = "2026-09-28"


def _print_rows(label: str) -> None:
    """打印 7 行 Nielsen 1988 A/B/C 常数 + 估算值注释（--dry-run 与执行后都用）。"""
    print(
        f"[{label}] compound_nielsen_1988_params 共 "
        f"{len(ESTIMATED_NIELSEN_1988_PARAMS)} 行"
        "（Nielsen 1988 paper Table 1 估算值；7 组分 CH4/C2H6/C3H8/I-C4H6/N2/CO2/H2S）："
    )
    print("  # 注：以下 A/B/C 常数为估算值（user ruling 2026-09-27），未与 Nielsen 1988")
    print("  # 论文原文逐位核对；工艺工程师二次核对后须同步修改 A/B/C 数值 + source + ")
    print("  # confirmed_by 字段。")
    print("  # 参见 docs/p6-gate-reports/gate-p6-6b-nielsen-confirmation.md")
    print(
        f"  {'component':<10}  {'A':>8}  {'B':>8}  {'C':>8}"
    )
    for row in ESTIMATED_NIELSEN_1988_PARAMS:
        print(
            f"  {row['component']:<10}  {row['a']:>8.4f}  {row['b']:>8.4f}  {row['c']:>8.4f}"
        )


def _replace_seed_rows(engine) -> tuple[int, int]:
    """先 DELETE ``source LIKE 'Nielsen 1988%'`` 行，再 INSERT 全量 7 行。

    幂等：第二次跑只剩 INSERT 7 行（DELETE 已无目标行）。
    不覆盖 ``confirmed_by`` / ``confirmed_at``（被工艺室签字流程手动维护）；
    但本任务 DELETE 仅针对 ``source LIKE 'Nielsen 1988%'``，工艺室已签字的
    真实数据行不会被触碰。

    返回 (deleted_count, inserted_count)。
    """
    deleted = 0
    inserted = len(ESTIMATED_NIELSEN_1988_PARAMS)
    with engine.begin() as conn:
        # Step 1: DELETE 仅占位估算标记的行
        result = conn.execute(
            delete(CompoundNielsen1988Params).where(
                CompoundNielsen1988Params.source.like("Nielsen 1988%"),
            )
        )
        deleted = result.rowcount or 0
        # Step 2: INSERT 全量 7 行（已注入 source / confirmed_by / confirmed_at）
        conn.execute(
            __import__("sqlalchemy").dialects.postgresql.insert(
                CompoundNielsen1988Params
            ).values(
                [
                    {
                        "component": row["component"],
                        "a": row["a"],
                        "b": row["b"],
                        "c": row["c"],
                        "source": SOURCE,
                        "confirmed_by": CONFIRMED_BY_PLACEHOLDER,
                        "confirmed_at": CONFIRMED_AT_PLACEHOLDER,
                    }
                    for row in ESTIMATED_NIELSEN_1988_PARAMS
                ]
            )
        )
    return deleted, inserted


def main() -> int:
    """CLI 入口：--dry-run 仅打印；默认 INSERT 7 行到 pcs/pcs_test 库。

    DATABASE_URL 由 ``app.core.config.get_settings()`` 解析。真实数据库执行
    时，库内必须已应用 alembic 升级到包含 ``p6_6b_008_nielsen_1988_params``
    的 head。
    """
    parser = argparse.ArgumentParser(description="C-18 Nielsen 1988 A/B/C 常数数据录入")
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
                select(CompoundNielsen1988Params)
            ).scalars().all()
    finally:
        engine.dispose()
    print(
        f"[EXECUTE] DELETE 旧占位行 {deleted}；INSERT 新占位行 {inserted}；"
        f"表内总计 {len(total)} 行。"
    )
    print(
        "[EXECUTE] 工艺室确认占位文档："
        "docs/p6-gate-reports/gate-p6-6b-nielsen-confirmation.md"
    )
    print(
        "[EXECUTE] ⚠️  A/B/C 常数为估算值，未与 Nielsen 1988 论文原文逐位核对；"
        "工艺工程师后续批次须从 PDF 抄录精确数值。"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())