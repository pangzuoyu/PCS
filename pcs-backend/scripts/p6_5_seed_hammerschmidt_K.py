"""P6-5 C5 收口：compound_hammerschmidt_K CONFIG 数据录入（C-18 水合物抑制 K 因子）。

按 P6-5 计划 Task C5 收口（user ruling 2026-09-26：4 张 CONFIG 表全在本批
落库）：

- 5 行 Hammerschmidt 1934 温降公式 ΔT = K·X / (M·(1-X)) 的 K 因子：
  MEOH=2335 / EG=2220 / DEG=2335 / TEG=2500 / NACL=1297；用于 C-18
  ``hydrate_inhibition_service._HAMMERSCHMIDT_K`` 内联常量 5 min TTL 缓存
  替换。
- 本任务用 **合成数据**（Hammerschmidt 1934 公开值的近似），``source``
  字段统一标记 ``SYNTHETIC_TEST_DATA``（参照 P6-4 G-08 P6_4_gate_03 模式）。
- 工艺工程师从 Hammerschmidt 1934 真实期号替换后，须同步修改 ``source``
  字段为真实期号（如 ``Hammerschmidt_1934``），并在
  ``docs/p6-gate-reports/gate-p6-5-hammerschmidt-confirmation.md`` 登记
  签字。

用法：

    cd pcs-backend
    uv run python scripts/p6_5_seed_hammerschmidt_K.py --dry-run
    uv run python scripts/p6_5_seed_hammerschmidt_K.py        # 真库

数据语义：先 DELETE 表内所有 ``source='SYNTHETIC_TEST_DATA'`` 记录，再
INSERT 全量 5 行（幂等）。``confirmed_by`` / ``confirmed_at`` 不自动覆盖
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
from app.models.config import CompoundHammerschmidtK  # noqa: E402

# -----------------------------------------------------------------------------
# 合成 5 行 Hammerschmidt K 因子（H-2 v1 BLOCKER 锁定）
# -----------------------------------------------------------------------------
# 真实 K 因子由工艺工程师从 Hammerschmidt 1934 论文替换；本任务用合成数据
# 占位（开发 / 测试用）；source 字段标记 SYNTHETIC_TEST_DATA 防误用于生产。
SYNTHETIC_HAMMERSCHMIDT_K: list[dict] = [
    {"inhibitor_type": "MEOH",  "K": 2335.0},
    {"inhibitor_type": "EG",    "K": 2220.0},
    {"inhibitor_type": "DEG",   "K": 2335.0},
    {"inhibitor_type": "TEG",   "K": 2500.0},
    {"inhibitor_type": "NACL",  "K": 1297.0},
]


def _print_rows(label: str) -> None:
    """打印 5 行 Hammerschmidt K 因子 + SYNTHETIC 注释（--dry-run 与执行后都用）。"""
    print(
        f"[{label}] compound_hammerschmidt_K 共 "
        f"{len(SYNTHETIC_HAMMERSCHMIDT_K)} 行"
        "（Hammerschmidt 1934 公开值近似；MEOH/EG/DEG/TEG/NACL）："
    )
    print("  # 注：以下均为合成数据，仅用于开发/测试；真实 K 因子由工艺工程师")
    print("  # 从 Hammerschmidt 1934 论文获取并替换。")
    print("  # 参见 docs/p6-gate-reports/gate-p6-5-hammerschmidt-confirmation.md")
    print(
        f"  {'inhibitor':<10}  {'K':>8}"
    )
    for row in SYNTHETIC_HAMMERSCHMIDT_K:
        print(
            f"  {row['inhibitor_type']:<10}  {row['K']:>8.1f}"
        )


def _replace_seed_rows(engine) -> tuple[int, int]:
    """先 DELETE ``source='SYNTHETIC_TEST_DATA'`` 行，再 INSERT 全量。

    幂等：第二次跑只剩 INSERT 5 行（DELETE 已无目标行）。
    不覆盖 ``confirmed_by`` / ``confirmed_at``（被工艺室签字流程手动维护）；
    但本任务 DELETE 仅针对 ``source='SYNTHETIC_TEST_DATA'``，工艺室已签字
    的真实数据行（如 ``source='Hammerschmidt_1934'``）不会被触碰。

    返回 (deleted_count, inserted_count)。
    """
    deleted = 0
    inserted = len(SYNTHETIC_HAMMERSCHMIDT_K)
    with engine.begin() as conn:
        # Step 1: DELETE 仅 SYNTHETIC 标记
        result = conn.execute(
            delete(CompoundHammerschmidtK).where(
                CompoundHammerschmidtK.source == "SYNTHETIC_TEST_DATA",
            )
        )
        deleted = result.rowcount or 0
        # Step 2: INSERT 全量 5 行（已注入 source='SYNTHETIC_TEST_DATA'）
        conn.execute(
            __import__("sqlalchemy").dialects.postgresql.insert(
                CompoundHammerschmidtK
            ).values(
                [
                    {
                        "inhibitor_type": row["inhibitor_type"],
                        "K": row["K"],
                        "source": "SYNTHETIC_TEST_DATA",
                        "confirmed_by": "工艺室_占位",
                    }
                    for row in SYNTHETIC_HAMMERSCHMIDT_K
                ]
            )
        )
    return deleted, inserted


def main() -> int:
    """CLI 入口：--dry-run 仅打印；默认 INSERT 5 行到 pcs/pcs_test 库。

    DATABASE_URL 由 ``app.core.config.get_settings()`` 解析。真实数据库执行
    时，库内必须已应用 alembic 升级到包含 ``p6_5_004_hammerschmidt_K`` 的
    head。
    """
    parser = argparse.ArgumentParser(description="C-18 Hammerschmidt K 因子数据录入")
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
                select(CompoundHammerschmidtK)
            ).scalars().all()
    finally:
        engine.dispose()
    print(
        f"[EXECUTE] DELETE 旧合成行 {deleted}；INSERT 新合成行 {inserted}；"
        f"表内总计 {len(total)} 行。"
    )
    print(
        "[EXECUTE] 工艺室确认占位文档："
        "docs/p6-gate-reports/gate-p6-5-hammerschmidt-confirmation.md"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
