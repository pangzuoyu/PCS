"""P6-3 G-05：过滤介质物性 CONFIG 数据录入（合成数据 + 工艺室确认占位）。

按 P6 计划 §Task 29 硬性前置 gate G-05：

- 过滤介质物性（P6 SPEC §3.2.7 Ruth 恒压/恒速过滤 + Ergun 深层过滤），
  FILTRATION 模块按 ``(medium_type, grade)`` 匹配做介质参数读取
  （Task 33/34）。
- 本任务用 **合成数据**（5 行：SAND / ANTHRACITE / CARBON /
  RUTH_FILTER_CLOTH / ERGUN_PACKING），``source`` 字段统一标记
  ``SYNTHETIC_TEST_DATA``。
- 工艺工程师从厂商 datasheet 替换真实物性后，须同步修改 ``source`` 字
  段为具体 datasheet 名称，并在
  ``docs/p6-gate-reports/gate-05-filtration-media-library-confirmation.md``
  登记签字（``confirmed_by`` + ``confirmed_at``）。

用法：

    cd pcs-backend
    uv run python scripts/p6_3_gate_05_filtration_media_library_seed.py --dry-run
    uv run python scripts/p6_3_gate_05_filtration_media_library_seed.py      # 真库 upsert

upsert 语义：按 ``(medium_type, grade)`` 唯一索引，存在则覆盖业务字段 +
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
from app.models.config import FiltrationMediaLibrary  # noqa: E402

# -----------------------------------------------------------------------------
# 合成 filtration_media_library（5 行 5 大介质类）
# -----------------------------------------------------------------------------
# 真实介质物性由工艺工程师从厂商 datasheet 获取；本任务用合成数据占位
# （开发 / 测试用）；source 字段标记 SYNTHETIC_TEST_DATA 防误用于生产报价。
# 替换触发条件参见
# docs/p6-gate-reports/gate-05-filtration-media-library-confirmation.md。
#
# Ruth 滤饼参数（cake_resistance_alpha / specific_resistance_r0）只在
# RUTH_FILTER_CLOTH 行填；Ergun 渗透率/孔隙率在 SAND / ANTHRACITE /
# CARBON / ERGUN_PACKING 行填；nominal_rating_um 在所有可分级行填
# （ERGUN_PACKING 是 Raschig 环填料，标称精度无意义故填 NULL）。
SYNTHETIC_FILTER_MEDIA = [
    {
        "medium_type": "SAND",
        "grade": "#20-30",
        "nominal_rating_um": 500.0,
        "cake_resistance_alpha": None,
        "specific_resistance_r0": None,
        "permeability_k": 5e-11,
        "porosity_eps": 0.40,
        "max_temp_c": 80.0,
        "source": "SYNTHETIC_TEST_DATA",
    },
    {
        "medium_type": "ANTHRACITE",
        "grade": "#1.0mm",
        "nominal_rating_um": 800.0,
        "cake_resistance_alpha": None,
        "specific_resistance_r0": None,
        "permeability_k": 8e-11,
        "porosity_eps": 0.50,
        "max_temp_c": 100.0,
        "source": "SYNTHETIC_TEST_DATA",
    },
    {
        "medium_type": "CARBON",
        "grade": "F-400",
        "nominal_rating_um": 25.0,
        "cake_resistance_alpha": None,
        "specific_resistance_r0": None,
        "permeability_k": 2e-11,
        "porosity_eps": 0.45,
        "max_temp_c": 60.0,
        "source": "SYNTHETIC_TEST_DATA",
    },
    {
        "medium_type": "RUTH_FILTER_CLOTH",
        "grade": "PE-900",
        "nominal_rating_um": 25.0,
        "cake_resistance_alpha": 1.5e10,
        "specific_resistance_r0": 1.0e10,
        "permeability_k": None,
        "porosity_eps": None,
        "max_temp_c": 90.0,
        "source": "SYNTHETIC_TEST_DATA",
    },
    {
        "medium_type": "ERGUN_PACKING",
        "grade": "RASCHIG-25",
        # Raschig 环填料无「标称过滤精度」概念；用 0.0 占位（nominal_rating_um
        # NOT NULL 约束由 brief 锁定）。FILTRATION 模块读取时遇到
        # medium_type == 'ERGUN_PACKING' 应忽略 rating_um。
        "nominal_rating_um": 0.0,
        "cake_resistance_alpha": None,
        "specific_resistance_r0": None,
        "permeability_k": 1.5e-9,
        "porosity_eps": 0.68,
        "max_temp_c": 200.0,
        "source": "SYNTHETIC_TEST_DATA",
    },
]


def _print_rows(label: str) -> None:
    """打印 5 行过滤介质 + SYNTHETIC 注释（--dry-run 与执行后都用）。"""
    print(
        f"[{label}] filtration_media_library 共 {len(SYNTHETIC_FILTER_MEDIA)} 行"
        "（合成数据占位）："
    )
    print("  # 注：以下均为合成数据，仅用于开发/测试；真实介质物性由工艺")
    print("  # 工程师从厂商 datasheet 获取并替换。")
    print("  # 参见 docs/p6-gate-reports/gate-05-filtration-media-library-confirmation.md")
    print(
        f"  {'medium_type':<20}  {'grade':<12}  {'rating_um':>9}  "
        f"{'alpha':>10}  {'r0':>10}  {'k_perm':>10}  {'eps':>5}  "
        f"{'T_max':>5}  source"
    )
    for row in SYNTHETIC_FILTER_MEDIA:
        rating = row["nominal_rating_um"]
        alpha = row.get("cake_resistance_alpha")
        r0 = row.get("specific_resistance_r0")
        k_perm = row.get("permeability_k")
        eps = row.get("porosity_eps")
        t_max = row.get("max_temp_c")
        print(
            f"  {row['medium_type']:<20}  {row['grade']:<12}  "
            f"{rating if rating is not None else 'NULL':>9}  "
            f"{alpha if alpha is not None else 'NULL':>10}  "
            f"{r0 if r0 is not None else 'NULL':>10}  "
            f"{k_perm if k_perm is not None else 'NULL':>10}  "
            f"{eps if eps is not None else 'NULL':>5}  "
            f"{t_max if t_max is not None else 'NULL':>5}  "
            f"{row['source']}"
        )


def _upsert(engine) -> tuple[int, int]:
    """PostgreSQL upsert：按 (medium_type, grade) 唯一索引 ON CONFLICT DO UPDATE。

    覆盖业务字段 + ``source``；``confirmed_by`` / ``confirmed_at`` /
    ``created_at`` 不覆盖（工艺室签字字段 + DB 时间戳由触发器维护）。

    返回 (affected_count, total_rows_after)。
    """
    stmt = pg_insert(FiltrationMediaLibrary).values(SYNTHETIC_FILTER_MEDIA)
    stmt = stmt.on_conflict_do_update(
        index_elements=[
            FiltrationMediaLibrary.medium_type,
            FiltrationMediaLibrary.grade,
        ],
        set_={
            "nominal_rating_um": stmt.excluded.nominal_rating_um,
            "cake_resistance_alpha": stmt.excluded.cake_resistance_alpha,
            "specific_resistance_r0": stmt.excluded.specific_resistance_r0,
            "permeability_k": stmt.excluded.permeability_k,
            "porosity_eps": stmt.excluded.porosity_eps,
            "max_temp_c": stmt.excluded.max_temp_c,
            "source": stmt.excluded.source,
        },
    )
    with engine.begin() as conn:
        conn.execute(stmt)
        total = conn.execute(select(FiltrationMediaLibrary)).scalars().all()
    return len(SYNTHETIC_FILTER_MEDIA), len(total)


def main() -> int:
    """CLI 入口：--dry-run 仅打印；默认 upsert 到 pcs/pcs_test 库。

    DATABASE_URL 由 ``app.core.config.get_settings()`` 解析（环境变量或
    .env 兜底）。真实数据库执行时，库内必须已应用 alembic 升级到包含
    ``p6_3_001_three_config_tables`` 的 head。
    """
    parser = argparse.ArgumentParser(description="G-05 过滤介质物性数据录入")
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
        "docs/p6-gate-reports/gate-05-filtration-media-library-confirmation.md"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())