"""P6-2 G-03：CEPCI 年度指数 CONFIG 数据录入（合成数据 + 工艺室确认占位）。

按 P6 计划 §Task 17 硬性前置 gate G-03：

- CEPCI = Chemical Engineering Plant Cost Index（年度指数，Chemical
  Engineering 杂志每年第 4 季度发布）。
- 本任务用 **合成数据**（2018~2024 共 7 行），``source`` 字段统一标记
  ``SYNTHETIC_TEST_DATA``（参照 P5-OPEN-10 Kb 厂商数据合成模式）。
- 工艺工程师从 Chemical Engineering 杂志替换真实数据后，须同步修改
  ``source`` 字段为真实期号（如 ``Chemical Engineering Magazine
  2024-Q4``），并在 ``docs/p6-gate-reports/gate-03-cepci-confirmation.md``
  登记签字（``confirmed_by`` + ``confirmed_at``）。

用法：

    cd pcs-backend
    uv run python scripts/p6_2_gate_03_cepci_seed.py --dry-run
    uv run python scripts/p6_2_gate_03_cepci_seed.py           # 真库 upsert

upsert 语义：按 ``year`` 唯一索引，存在则覆盖 ``cepci_value`` + ``source``
（``confirmed_by`` / ``confirmed_at`` 不自动覆盖 — 由工艺室签字流程手动
维护）。
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
from app.models.config import CepciIndexSeries  # noqa: E402

# -----------------------------------------------------------------------------
# 合成 CEPCI 2018~2024（7 行）
# -----------------------------------------------------------------------------
# 真实 CEPCI 由工艺工程师从 Chemical Engineering 杂志获取，本任务用合成数据
# 占位（开发 / 测试用）；source 字段标记 SYNTHETIC_TEST_DATA 防误用于生产报价。
# 替换触发条件参见 docs/p6-gate-reports/gate-03-cepci-confirmation.md。
SYNTHETIC_CEPCI = [
    {"year": 2018, "cepci_value": 599.0, "source": "SYNTHETIC_TEST_DATA"},
    {"year": 2019, "cepci_value": 607.5, "source": "SYNTHETIC_TEST_DATA"},
    {"year": 2020, "cepci_value": 596.2, "source": "SYNTHETIC_TEST_DATA"},
    {"year": 2021, "cepci_value": 708.8, "source": "SYNTHETIC_TEST_DATA"},
    {"year": 2022, "cepci_value": 816.0, "source": "SYNTHETIC_TEST_DATA"},
    {"year": 2023, "cepci_value": 797.9, "source": "SYNTHETIC_TEST_DATA"},
    {"year": 2024, "cepci_value": 800.0, "source": "SYNTHETIC_TEST_DATA"},
]


def _print_rows(label: str) -> None:
    """打印 7 行 CEPCI + SYNTHETIC 注释（--dry-run 与执行后都用）。"""
    print(f"[{label}] CEPCI 2018~2024 共 {len(SYNTHETIC_CEPCI)} 行（合成数据占位）：")
    print("  # 注：以下均为合成数据，仅用于开发/测试；真实 CEPCI 由工艺工程师从")
    print("  # Chemical Engineering 杂志获取并替换。参见 docs/p6-gate-reports/gate-03-cepci-confirmation.md")
    print(f"  {'year':>6}  {'cepci_value':>12}  source")
    for row in SYNTHETIC_CEPCI:
        print(f"  {row['year']:>6}  {row['cepci_value']:>12.1f}  {row['source']}")


def _upsert(engine) -> tuple[int, int]:
    """PostgreSQL upsert：按 year 唯一索引 ON CONFLICT DO UPDATE。

    仅覆盖 ``cepci_value`` + ``source``；``confirmed_by`` / ``confirmed_at``
    不覆盖（工艺室签字字段由人工流程维护，不被脚本清空）。

    返回 (inserted_or_updated_count, total_rows_after)。
    """
    stmt = pg_insert(CepciIndexSeries).values(SYNTHETIC_CEPCI)
    stmt = stmt.on_conflict_do_update(
        index_elements=[CepciIndexSeries.year],
        set_={
            "cepci_value": stmt.excluded.cepci_value,
            "source": stmt.excluded.source,
        },
    )
    with engine.begin() as conn:
        conn.execute(stmt)
        total = conn.execute(select(CepciIndexSeries)).scalars().all()
    return len(SYNTHETIC_CEPCI), len(total)


def main() -> int:
    """CLI 入口：--dry-run 仅打印；默认 upsert 到 pcs/pcs_test 库。

    DATABASE_URL 由 ``app.core.config.get_settings()`` 解析（环境变量或
    .env 兜底）。真实数据库执行时，库内必须已应用 alembic 升级到包含
    ``p6_2_gate_03_cepci_seed`` 的 head。
    """
    parser = argparse.ArgumentParser(description="G-03 CEPCI 数据录入")
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
    print(f"[EXECUTE] upsert 完成：受影响 {affected} 行；表内总计 {total} 行。")
    print("[EXECUTE] 工艺室确认占位文档：docs/p6-gate-reports/gate-03-cepci-confirmation.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
