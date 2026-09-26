"""P6-5 C5 收口：compound_iso9613_atmospheric_absorption CONFIG 数据录入（C-23 大气吸收）。

按 P6-5 计划 Task C5 收口（user ruling 2026-09-26：4 张 CONFIG 表全在本批
落库）：

- 4 行 ISO 9613-2 大气吸收系数 A（dB/km），温度 10/15/20/25°C × 50% RH
  标准工况；用于 C-23 ``noise_service`` 大气吸收 5 min TTL 缓存替换。
- 本任务用 **合成数据**（ISO 9613-2 §7 公开图表的近似值），``source`` 字段
  统一标记 ``SYNTHETIC_TEST_DATA``（参照 P6-4 G-08 P6_4_gate_03 模式）。
- 工艺工程师从 ISO 9613-2 真实期号替换后，须同步修改 ``source`` 字段为
  真实期号（如 ``ISO9613-2_§7``），并在
  ``docs/p6-gate-reports/gate-p6-5-iso9613-confirmation.md`` 登记签字。

用法：

    cd pcs-backend
    uv run python scripts/p6_5_seed_iso9613_atmospheric_absorption.py --dry-run
    uv run python scripts/p6_5_seed_iso9613_atmospheric_absorption.py        # 真库

数据语义：先 DELETE 表内所有 ``source='SYNTHETIC_TEST_DATA'`` 记录，再
INSERT 全量 4 行（幂等）。``confirmed_by`` / ``confirmed_at`` 不自动覆盖
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
from app.models.config import CompoundIso9613AtmosphericAbsorption  # noqa: E402

# -----------------------------------------------------------------------------
# 合成 4 行 ISO 9613-2 大气吸收系数（标准工况：10/15/20/25°C × 50% RH）
# -----------------------------------------------------------------------------
# 真实 A 系数由工艺工程师从 ISO 9613-2 §7 替换；本任务用合成数据占位
# （开发 / 测试用）；source 字段标记 SYNTHETIC_TEST_DATA 防误用于生产。
# 注意：噪声默认采用 1.5 dB/km（C-23 noise_service _DEFAULT_ATM_ABS_DB_PER_KM），
# 合成数据围绕此值附近，工艺室签字可精细替换。
SYNTHETIC_ISO9613_ABSORPTION: list[dict] = [
    {"temperature_c": 10.0, "humidity_pct": 50.0, "alpha_db_km": 1.5},
    {"temperature_c": 15.0, "humidity_pct": 50.0, "alpha_db_km": 1.5},
    {"temperature_c": 20.0, "humidity_pct": 50.0, "alpha_db_km": 1.5},
    {"temperature_c": 25.0, "humidity_pct": 50.0, "alpha_db_km": 1.5},
]


def _print_rows(label: str) -> None:
    """打印 4 行 ISO 9613-2 大气吸收 + SYNTHETIC 注释（--dry-run 与执行后都用）。"""
    print(
        f"[{label}] compound_iso9613_atmospheric_absorption 共 "
        f"{len(SYNTHETIC_ISO9613_ABSORPTION)} 行"
        "（ISO 9613-2 §7 公开图表近似；10/15/20/25°C × 50% RH）："
    )
    print("  # 注：以下均为合成数据，仅用于开发/测试；真实 A 系数由工艺工程师")
    print("  # 从 ISO 9613-2 §7 获取并替换。")
    print("  # 参见 docs/p6-gate-reports/gate-p6-5-iso9613-confirmation.md")
    print(
        f"  {'T(°C)':>8}  {'RH(%)':>8}  {'A(dB/km)':>10}"
    )
    for row in SYNTHETIC_ISO9613_ABSORPTION:
        print(
            f"  {row['temperature_c']:>8.2f}  {row['humidity_pct']:>8.2f}  "
            f"{row['alpha_db_km']:>10.3f}"
        )


def _replace_seed_rows(engine) -> tuple[int, int]:
    """先 DELETE ``source='SYNTHETIC_TEST_DATA'`` 行，再 INSERT 全量。

    幂等：第二次跑只剩 INSERT 4 行（DELETE 已无目标行）。
    不覆盖 ``confirmed_by`` / ``confirmed_at``（被工艺室签字流程手动维护）；
    但本任务 DELETE 仅针对 ``source='SYNTHETIC_TEST_DATA'``，工艺室已签字
    的真实数据行（如 ``source='ISO9613-2_§7'``）不会被触碰。

    返回 (deleted_count, inserted_count)。
    """
    deleted = 0
    inserted = len(SYNTHETIC_ISO9613_ABSORPTION)
    with engine.begin() as conn:
        # Step 1: DELETE 仅 SYNTHETIC 标记
        result = conn.execute(
            delete(CompoundIso9613AtmosphericAbsorption).where(
                CompoundIso9613AtmosphericAbsorption.source == "SYNTHETIC_TEST_DATA",
            )
        )
        deleted = result.rowcount or 0
        # Step 2: INSERT 全量 4 行（已注入 source='SYNTHETIC_TEST_DATA'）
        conn.execute(
            __import__("sqlalchemy").dialects.postgresql.insert(
                CompoundIso9613AtmosphericAbsorption
            ).values(
                [
                    {
                        "temperature_c": row["temperature_c"],
                        "humidity_pct": row["humidity_pct"],
                        "alpha_db_km": row["alpha_db_km"],
                        "source": "SYNTHETIC_TEST_DATA",
                        "confirmed_by": "工艺室_占位",
                    }
                    for row in SYNTHETIC_ISO9613_ABSORPTION
                ]
            )
        )
    return deleted, inserted


def main() -> int:
    """CLI 入口：--dry-run 仅打印；默认 INSERT 4 行到 pcs/pcs_test 库。

    DATABASE_URL 由 ``app.core.config.get_settings()`` 解析。真实数据库执行
    时，库内必须已应用 alembic 升级到包含
    ``p6_5_003_iso9613_atmospheric_absorption`` 的 head。
    """
    parser = argparse.ArgumentParser(description="C-23 大气吸收数据录入")
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
                select(CompoundIso9613AtmosphericAbsorption)
            ).scalars().all()
    finally:
        engine.dispose()
    print(
        f"[EXECUTE] DELETE 旧合成行 {deleted}；INSERT 新合成行 {inserted}；"
        f"表内总计 {len(total)} 行。"
    )
    print(
        "[EXECUTE] 工艺室确认占位文档："
        "docs/p6-gate-reports/gate-p6-5-iso9613-confirmation.md"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
