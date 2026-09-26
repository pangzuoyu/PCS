"""P6-5 C5 收口：compound_pasquill_sigma CONFIG 数据录入（C-22 扩散）。

按 P6-5 计划 Task C5 收口（user ruling 2026-09-26：4 张 CONFIG 表全在本批
落库；不分拆 Worker 1+3）：

- 6 行 Pasquill-Gifford 稳定度（A/B/C/D/E/F）的 Briggs 1973 系数 (a_y,
  b_y, a_z, b_z)；用于 C-22 ``dispersion_service._BRIGGS_SIGMA`` 内联常量
  的 5 min TTL 缓存替换。
- 本任务用 **合成数据**（Briggs 1973 公开值的近似值），``source`` 字段统一
  标记 ``SYNTHETIC_TEST_DATA``（参照 P6-4 G-08 P6_4_gate_03 模式）。
- 工艺工程师从 Briggs 1973 真实期号替换后，须同步修改 ``source`` 字段为
  真实期号（如 ``Briggs_1973_open_terrain``），并在
  ``docs/p6-gate-reports/gate-p6-5-pasquill-sigma-confirmation.md`` 登记
  签字（``confirmed_by`` + ``confirmed_at``）。

用法：

    cd pcs-backend
    uv run python scripts/p6_5_seed_pasquill_sigma.py --dry-run
    uv run python scripts/p6_5_seed_pasquill_sigma.py        # 真库

数据语义：先 DELETE 表内所有 ``source='SYNTHETIC_TEST_DATA'`` 记录，再
INSERT 全量 6 行（幂等）。``confirmed_by`` / ``confirmed_at`` 不自动覆盖
—— 由工艺室签字流程手动维护。
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
from app.models.config import CompoundPasquillSigma  # noqa: E402

# -----------------------------------------------------------------------------
# 合成 6 行 Pasquill-Gifford 稳定度 Briggs 1973 系数（公开值近似）
# -----------------------------------------------------------------------------
# 真实 (a_y, b_y, a_z, b_z) 由工艺工程师从 Briggs 1973 论文 / GPSA 替换；
# 本任务用合成数据占位（开发 / 测试用）；source 字段标记 SYNTHETIC_TEST_DATA
# 防误用于生产。
SYNTHETIC_PASQUILL_SIGMA: list[dict] = [
    # (stability_class, a_y, b_y, a_z, b_z)
    {"stability_class": "A", "a_y": 0.22,  "b_y": 0.0001, "a_z": 0.20,  "b_z": 0.0},
    {"stability_class": "B", "a_y": 0.16,  "b_y": 0.0001, "a_z": 0.12,  "b_z": 0.0},
    {"stability_class": "C", "a_y": 0.11,  "b_y": 0.0001, "a_z": 0.08,  "b_z": 0.0002},
    {"stability_class": "D", "a_y": 0.08,  "b_y": 0.0001, "a_z": 0.06,  "b_z": 0.0015},
    {"stability_class": "E", "a_y": 0.06,  "b_y": 0.0001, "a_z": 0.03,  "b_z": 0.0003},
    {"stability_class": "F", "a_y": 0.04,  "b_y": 0.0001, "a_z": 0.016, "b_z": 0.0003},
]


def _print_rows(label: str) -> None:
    """打印 6 行 Pasquill 系数 + SYNTHETIC 注释（--dry-run 与执行后都用）。"""
    print(
        f"[{label}] compound_pasquill_sigma 共 {len(SYNTHETIC_PASQUILL_SIGMA)} 行"
        "（Briggs 1973 公开值近似，A-F 6 类稳定度）："
    )
    print("  # 注：以下均为合成数据，仅用于开发/测试；真实系数由工艺工程师")
    print("  # 从 Briggs 1973 论文 / GPSA Engineering Data Book 获取并替换。")
    print("  # 参见 docs/p6-gate-reports/gate-p6-5-pasquill-sigma-confirmation.md")
    print(
        f"  {'class':<5}  {'a_y':>8}  {'b_y':>10}  {'a_z':>8}  {'b_z':>10}"
    )
    for row in SYNTHETIC_PASQUILL_SIGMA:
        print(
            f"  {row['stability_class']:<5}  {row['a_y']:>8.4f}  "
            f"{row['b_y']:>10.6f}  {row['a_z']:>8.4f}  {row['b_z']:>10.6f}"
        )


def _replace_seed_rows(engine) -> tuple[int, int]:
    """先 DELETE ``source='SYNTHETIC_TEST_DATA'`` 行，再 INSERT 全量。

    幂等：第二次跑只剩 INSERT 6 行（DELETE 已无目标行）。
    不覆盖 ``confirmed_by`` / ``confirmed_at``（被工艺室签字流程手动维护）；
    但本任务 DELETE 仅针对 ``source='SYNTHETIC_TEST_DATA'``，工艺室已签字
    的真实数据行（如 ``source='Briggs_1973_open_terrain'``）不会被触碰。

    返回 (deleted_count, inserted_count)。
    """
    deleted = 0
    inserted = len(SYNTHETIC_PASQUILL_SIGMA)
    with engine.begin() as conn:
        # Step 1: DELETE 仅 SYNTHETIC 标记
        result = conn.execute(
            delete(CompoundPasquillSigma).where(
                CompoundPasquillSigma.source == "SYNTHETIC_TEST_DATA",
            )
        )
        deleted = result.rowcount or 0
        # Step 2: INSERT 全量 6 行（已注入 source='SYNTHETIC_TEST_DATA'）
        conn.execute(
            __import__("sqlalchemy").dialects.postgresql.insert(
                CompoundPasquillSigma
            ).values(
                [
                    {
                        "stability_class": row["stability_class"],
                        "a_y": row["a_y"],
                        "b_y": row["b_y"],
                        "a_z": row["a_z"],
                        "b_z": row["b_z"],
                        "source": "SYNTHETIC_TEST_DATA",
                        "confirmed_by": "工艺室_占位",
                    }
                    for row in SYNTHETIC_PASQUILL_SIGMA
                ]
            )
        )
    return deleted, inserted


def main() -> int:
    """CLI 入口：--dry-run 仅打印；默认 INSERT 6 行到 pcs/pcs_test 库。

    DATABASE_URL 由 ``app.core.config.get_settings()`` 解析。真实数据库执行
    时，库内必须已应用 alembic 升级到包含 ``p6_5_001_pasquill_sigma`` 的 head。
    """
    parser = argparse.ArgumentParser(description="C-22 Pasquill 系数数据录入")
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
                select(CompoundPasquillSigma)
            ).scalars().all()
    finally:
        engine.dispose()
    print(
        f"[EXECUTE] DELETE 旧合成行 {deleted}；INSERT 新合成行 {inserted}；"
        f"表内总计 {len(total)} 行。"
    )
    print(
        "[EXECUTE] 工艺室确认占位文档："
        "docs/p6-gate-reports/gate-p6-5-pasquill-sigma-confirmation.md"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
