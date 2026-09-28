"""P6-6B T3: 管材弹性模量 E CONFIG 数据录入（C-13 Joukowsky 输入 / SPEC §3.2.3 V1.8）。

按 P6-6B 计划 §T3 录入：

- 8 行管材等级 E 模量（典型值 70°F）：
  - API 5L (2018): ``X42`` / ``X52`` / ``X65`` / ``X70`` / ``X80``
  - ASTM A106:     ``A106-B``
  - ASTM A335:     ``A335-P11`` / ``A335-P22``
- 来源：本批录入即用 API 5L (2018) + ASTM A106/A335 真实公开值，
  ``source`` 字段统一标记 ``'API 5L (2018) + ASTM A106/A335'``（参照
  P6-6B 裁决：API 5L + ASTM A106/A335 真实公开值，非合成）。
- 工艺工程师已签字（per P6-6B 裁决）：``confirmed_by='P6-6B_ENG_TEAM'``，
  ``confirmed_at='2026-09-28'``。

精确数值说明：

API 5L (2018) line pipe 各等级 E 模量典型值 70°F = 30,000,000 psi（API 5L
PSL 1/PSL 2 范围 30.0~30.5×10^6 psi；工程圆整取 30.0×10^6 psi）。
ASTM A106-B（高温碳钢）/ A335-P11（1.25Cr-0.5Mo）/ A335-P22（2.25Cr-1Mo）
典型值 70°F 工程圆整取 29,000,000 / 29,000,000 / 28,000,000 psi
（高温抗蠕变合金 Cr-Mo 钢略低于碳钢，与 ASME B31.1/B31.3 设计值一致）。

用法：

    cd pcs-backend
    uv run python scripts/p6_6b_seed_pipe_e_modulus.py --dry-run
    uv run python scripts/p6_6b_seed_pipe_e_modulus.py        # 真库

数据语义：INSERT 8 行 ON CONFLICT DO NOTHING（幂等；重跑无副作用）。
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
from app.models.config import PipeEModulus  # noqa: E402

# -----------------------------------------------------------------------------
# 8 行管材等级 E 模量（API 5L (2018) + ASTM A106/A335 真实公开值）
# -----------------------------------------------------------------------------
# 典型值 70°F；e_psi 单位 psi；spec_source 为对应标准号；source 为本批统一标记。
PIPE_E_MODULUS_ROWS: list[dict] = [
    # ---- API 5L (2018) line pipe ----
    {"grade": "X42",     "e_psi": 30_000_000, "spec_source": "API 5L"},
    {"grade": "X52",     "e_psi": 30_000_000, "spec_source": "API 5L"},
    {"grade": "X65",     "e_psi": 30_000_000, "spec_source": "API 5L"},
    {"grade": "X70",     "e_psi": 30_000_000, "spec_source": "API 5L"},
    {"grade": "X80",     "e_psi": 30_000_000, "spec_source": "API 5L"},
    # ---- ASTM A106 ----
    {"grade": "A106-B",  "e_psi": 29_000_000, "spec_source": "ASTM A106"},
    # ---- ASTM A335 ----
    {"grade": "A335-P11", "e_psi": 29_000_000, "spec_source": "ASTM A335"},
    {"grade": "A335-P22", "e_psi": 28_000_000, "spec_source": "ASTM A335"},
]

SOURCE = "API 5L (2018) + ASTM A106/A335"
CONFIRMED_BY = "P6-6B_ENG_TEAM"
CONFIRMED_AT = "2026-09-28"


def _print_rows(label: str) -> None:
    """打印 8 行管材 E 模量 + 工艺室签字标注。"""
    print(
        f"[{label}] pipe_e_modulus 共 {len(PIPE_E_MODULUS_ROWS)} 行"
        "（API 5L (2018) + ASTM A106/A335 真实公开值，70°F 典型）："
    )
    print(
        f"  {'grade':<10}  {'e_psi':>12}  {'spec_source':<14}"
    )
    for row in PIPE_E_MODULUS_ROWS:
        print(
            f"  {row['grade']:<10}  {row['e_psi']:>12,}  {row['spec_source']:<14}"
        )
    print(f"  source={SOURCE!r} confirmed_by={CONFIRMED_BY!r} confirmed_at={CONFIRMED_AT!r}")


def _insert_seed_rows(engine) -> int:
    """INSERT 8 行 ON CONFLICT DO NOTHING（幂等）。

    返回实际 INSERT 行数（PG dialect 返回 rowcount）。
    """
    with engine.begin() as conn:
        result = conn.execute(
            __import__("sqlalchemy").dialects.postgresql.insert(
                PipeEModulus
            ).values(
                [
                    {
                        "grade": row["grade"],
                        "e_psi": row["e_psi"],
                        "spec_source": row["spec_source"],
                        "source": SOURCE,
                        "confirmed_by": CONFIRMED_BY,
                        "confirmed_at": CONFIRMED_AT,
                    }
                    for row in PIPE_E_MODULUS_ROWS
                ]
            ).on_conflict_do_nothing(index_elements=["grade"])
        )
        return result.rowcount or 0


def main() -> int:
    """CLI 入口：--dry-run 仅打印；默认 INSERT 8 行到 pcs/pcs_test 库。

    DATABASE_URL 由 ``app.core.config.get_settings()`` 解析。真实数据库执行
    时，库内必须已应用 alembic 升级到包含 ``p6_6b_003_pipe_e_modulus`` 的 head。
    """
    parser = argparse.ArgumentParser(description="C-13 pipe_e_modulus 数据录入")
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
            total = conn.execute(select(PipeEModulus)).scalars().all()
    finally:
        engine.dispose()
    print(
        f"[EXECUTE] INSERT 新行 {inserted}（ON CONFLICT DO NOTHING）；"
        f"表内总计 {len(total)} 行。"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
