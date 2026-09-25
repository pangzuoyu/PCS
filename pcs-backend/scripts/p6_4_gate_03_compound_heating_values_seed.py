"""P6-4 G-08：化合物热值 CONFIG 数据录入（C-06 气体热值 / SPEC §3.2.3.6）。

按 P6 计划 §Task 1 硬性前置 gate：

- 64 种化合物的 HHV / LHV（高位 / 低位热值）+ 分子量（g/mol）；
  涵盖 GPSA FIG. 23-2（烃类 ~35 种）+ API 5B6（醇/酮/醚/硫醇等含氧
  含硫 + 酸气 + 惰性气）。
- 本任务用 **合成数据**（GPSA Engineering Data Book 公开值的近似值），
  ``source`` 字段统一标记 ``SYNTHETIC_TEST_DATA``（参照 P5-OPEN-10
  Kb 厂商数据合成模式）。
- 工艺工程师从 GPSA FIG. 23-2 真实期号替换后，须同步修改 ``source``
  字段为真实期号（如 ``GPSA_ED13_FIG23-2``），并在
  ``docs/p6-gate-reports/gate-03-compound-heating-values-confirmation.md``
  登记签字（``confirmed_by`` + ``confirmed_at``）。

数据分类（按 GPSA + API 5B6 常见组分）：

- 轻烃 C1~C10（n-/iso- 烷 + 环烷）共 18 种；
- 烯烃 / 炔烃 7 种；
- 芳香烃 7 种；
- 含氧有机物（醇 / 酮 / 醚 / 醛 / 酸）11 种；
- 含硫有机物（硫醇 / 硫醚 / CS2 / COS / H2S / SO2）6 种；
- 含氮 / 无机（H2 / CO / NH3 / HCN）4 种；
- 惰性气 / 空气 / 水（无可燃性 HHV = 0）9 种；
- 1-己烯 / 异辛烷（异构烯 + 高辛烷值组分）2 种；
- 共计 64 种。

用法：

    cd pcs-backend
    uv run python scripts/p6_4_gate_03_compound_heating_values_seed.py --dry-run
    uv run python scripts/p6_4_gate_03_compound_heating_values_seed.py        # 真库

数据语义：先 DELETE 表内所有 ``source='SYNTHETIC_TEST_DATA'`` 记录，再
INSERT 全量 64 行（幂等）。``confirmed_by`` / ``confirmed_at`` 不自动
覆盖 — 由工艺室签字流程手动维护。
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
from app.models.config import CompoundHeatingValues  # noqa: E402

# -----------------------------------------------------------------------------
# 合成 64 种化合物热值（GPSA FIG. 23-2 + API 5B6 公开值的近似）
# -----------------------------------------------------------------------------
# 真实 HHV/LHV 由工艺工程师从 GPSA Engineering Data Book 真实期号替换；
# 本任务用合成数据占位（开发 / 测试用）；source 字段标记 SYNTHETIC_TEST_DATA
# 防误用于生产。HHV 在 liquid H2O 条件下；LHV 在 gaseous H2O 条件下。
SYNTHETIC_COMPOUNDS: list[dict] = [
    # ---- 轻烃 C1~C10（n-/iso- 烷 + 环烷）18 种 ----
    {"cas": "74-82-8",   "name": "methane",            "hhv_mj_kg": 55.53, "lhv_mj_kg": 50.02, "mw_g_mol": 16.043},
    {"cas": "74-84-0",   "name": "ethane",             "hhv_mj_kg": 51.90, "lhv_mj_kg": 47.49, "mw_g_mol": 30.070},
    {"cas": "74-98-6",   "name": "propane",            "hhv_mj_kg": 50.35, "lhv_mj_kg": 46.34, "mw_g_mol": 44.097},
    {"cas": "106-97-8",  "name": "n-butane",           "hhv_mj_kg": 49.50, "lhv_mj_kg": 45.72, "mw_g_mol": 58.123},
    {"cas": "75-28-5",   "name": "isobutane",          "hhv_mj_kg": 49.36, "lhv_mj_kg": 45.58, "mw_g_mol": 58.123},
    {"cas": "109-66-0",  "name": "n-pentane",          "hhv_mj_kg": 48.95, "lhv_mj_kg": 45.35, "mw_g_mol": 72.150},
    {"cas": "78-78-4",   "name": "isopentane",         "hhv_mj_kg": 48.74, "lhv_mj_kg": 45.13, "mw_g_mol": 72.150},
    {"cas": "110-54-3",  "name": "n-hexane",           "hhv_mj_kg": 48.56, "lhv_mj_kg": 45.10, "mw_g_mol": 86.178},
    {"cas": "107-83-5",  "name": "2-methylpentane",    "hhv_mj_kg": 48.32, "lhv_mj_kg": 44.81, "mw_g_mol": 86.178},
    {"cas": "96-14-0",   "name": "3-methylpentane",    "hhv_mj_kg": 48.31, "lhv_mj_kg": 44.78, "mw_g_mol": 86.178},
    {"cas": "142-82-5",  "name": "n-heptane",          "hhv_mj_kg": 48.28, "lhv_mj_kg": 44.92, "mw_g_mol": 100.205},
    {"cas": "111-65-9",  "name": "n-octane",           "hhv_mj_kg": 48.07, "lhv_mj_kg": 44.79, "mw_g_mol": 114.232},
    {"cas": "111-84-2",  "name": "n-nonane",           "hhv_mj_kg": 47.91, "lhv_mj_kg": 44.69, "mw_g_mol": 128.259},
    {"cas": "124-18-5",  "name": "n-decane",           "hhv_mj_kg": 47.79, "lhv_mj_kg": 44.62, "mw_g_mol": 142.286},
    {"cas": "287-92-3",  "name": "cyclopentane",       "hhv_mj_kg": 48.51, "lhv_mj_kg": 45.01, "mw_g_mol": 70.135},
    {"cas": "110-82-7",  "name": "cyclohexane",        "hhv_mj_kg": 48.24, "lhv_mj_kg": 44.85, "mw_g_mol": 84.162},
    {"cas": "96-37-7",   "name": "methylcyclopentane", "hhv_mj_kg": 48.05, "lhv_mj_kg": 44.64, "mw_g_mol": 84.162},
    {"cas": "108-87-2",  "name": "methylcyclohexane",  "hhv_mj_kg": 47.78, "lhv_mj_kg": 44.46, "mw_g_mol": 98.190},
    # ---- 烯烃 / 炔烃 7 种 ----
    {"cas": "74-85-1",   "name": "ethylene",           "hhv_mj_kg": 50.32, "lhv_mj_kg": 47.16, "mw_g_mol": 28.054},
    {"cas": "115-07-1",  "name": "propylene",          "hhv_mj_kg": 48.92, "lhv_mj_kg": 45.95, "mw_g_mol": 42.081},
    {"cas": "106-98-9",  "name": "1-butene",           "hhv_mj_kg": 48.44, "lhv_mj_kg": 45.32, "mw_g_mol": 56.108},
    {"cas": "590-18-1",  "name": "cis-2-butene",       "hhv_mj_kg": 47.91, "lhv_mj_kg": 44.79, "mw_g_mol": 56.108},
    {"cas": "624-64-6",  "name": "trans-2-butene",     "hhv_mj_kg": 47.86, "lhv_mj_kg": 44.74, "mw_g_mol": 56.108},
    {"cas": "115-11-7",  "name": "isobutene",          "hhv_mj_kg": 48.17, "lhv_mj_kg": 45.04, "mw_g_mol": 56.108},
    {"cas": "74-86-2",   "name": "acetylene",          "hhv_mj_kg": 49.91, "lhv_mj_kg": 48.22, "mw_g_mol": 26.038},
    # ---- 芳香烃 7 种 ----
    {"cas": "71-43-2",   "name": "benzene",            "hhv_mj_kg": 42.41, "lhv_mj_kg": 40.18, "mw_g_mol": 78.114},
    {"cas": "108-88-3",  "name": "toluene",            "hhv_mj_kg": 42.45, "lhv_mj_kg": 40.52, "mw_g_mol": 92.141},
    {"cas": "100-41-4",  "name": "ethylbenzene",       "hhv_mj_kg": 43.00, "lhv_mj_kg": 41.16, "mw_g_mol": 106.168},
    {"cas": "95-47-6",   "name": "o-xylene",           "hhv_mj_kg": 43.40, "lhv_mj_kg": 41.55, "mw_g_mol": 106.168},
    {"cas": "108-38-3",  "name": "m-xylene",           "hhv_mj_kg": 43.35, "lhv_mj_kg": 41.51, "mw_g_mol": 106.168},
    {"cas": "106-42-3",  "name": "p-xylene",           "hhv_mj_kg": 43.31, "lhv_mj_kg": 41.47, "mw_g_mol": 106.168},
    {"cas": "91-20-3",   "name": "naphthalene",        "hhv_mj_kg": 40.05, "lhv_mj_kg": 38.65, "mw_g_mol": 128.174},
    {"cas": "100-42-5",  "name": "styrene",            "hhv_mj_kg": 43.80, "lhv_mj_kg": 41.85, "mw_g_mol": 104.152},
    # ---- 含氧有机物 11 种（醇 / 酮 / 醚 / 醛 / 酸）----
    {"cas": "67-56-1",   "name": "methanol",           "hhv_mj_kg": 22.69, "lhv_mj_kg": 19.94, "mw_g_mol": 32.042},
    {"cas": "64-17-5",   "name": "ethanol",            "hhv_mj_kg": 29.67, "lhv_mj_kg": 26.90, "mw_g_mol": 46.069},
    {"cas": "67-63-0",   "name": "isopropanol",        "hhv_mj_kg": 33.40, "lhv_mj_kg": 30.20, "mw_g_mol": 60.096},
    {"cas": "71-23-8",   "name": "n-propanol",         "hhv_mj_kg": 33.60, "lhv_mj_kg": 30.40, "mw_g_mol": 60.096},
    {"cas": "71-36-3",   "name": "n-butanol",          "hhv_mj_kg": 36.10, "lhv_mj_kg": 33.00, "mw_g_mol": 74.123},
    {"cas": "67-64-1",   "name": "acetone",            "hhv_mj_kg": 31.35, "lhv_mj_kg": 29.10, "mw_g_mol": 58.080},
    {"cas": "78-93-3",   "name": "methyl ethyl ketone","hhv_mj_kg": 36.90, "lhv_mj_kg": 33.70, "mw_g_mol": 72.107},
    {"cas": "1634-04-4", "name": "MTBE",               "hhv_mj_kg": 38.20, "lhv_mj_kg": 35.20, "mw_g_mol": 88.150},
    {"cas": "115-10-6",  "name": "dimethyl ether",     "hhv_mj_kg": 31.70, "lhv_mj_kg": 28.85, "mw_g_mol": 46.069},
    {"cas": "50-00-0",   "name": "formaldehyde",       "hhv_mj_kg": 19.00, "lhv_mj_kg": 17.10, "mw_g_mol": 30.026},
    {"cas": "75-07-0",   "name": "acetaldehyde",       "hhv_mj_kg": 26.40, "lhv_mj_kg": 24.40, "mw_g_mol": 44.053},
    {"cas": "64-19-7",   "name": "acetic acid",        "hhv_mj_kg": 14.60, "lhv_mj_kg": 13.20, "mw_g_mol": 60.052},
    # ---- 含硫有机物 6 种（硫醇 / 硫醚 / CS2 / COS / H2S / SO2）----
    {"cas": "74-93-1",   "name": "methyl mercaptan",   "hhv_mj_kg": 25.00, "lhv_mj_kg": 23.20, "mw_g_mol": 48.109},
    {"cas": "75-08-1",   "name": "ethyl mercaptan",    "hhv_mj_kg": 31.40, "lhv_mj_kg": 29.80, "mw_g_mol": 62.136},
    {"cas": "75-18-3",   "name": "dimethyl sulfide",   "hhv_mj_kg": 31.60, "lhv_mj_kg": 29.70, "mw_g_mol": 62.136},
    {"cas": "75-15-0",   "name": "carbon disulfide",   "hhv_mj_kg": 14.30, "lhv_mj_kg": 14.30, "mw_g_mol": 76.140},
    {"cas": "463-58-1",  "name": "carbonyl sulfide",   "hhv_mj_kg": 11.30, "lhv_mj_kg": 11.30, "mw_g_mol": 60.070},
    {"cas": "7783-06-4", "name": "hydrogen sulfide",   "hhv_mj_kg": 16.30, "lhv_mj_kg": 15.20, "mw_g_mol": 34.080},
    # ---- 含氮 / 无机 4 种 ----
    {"cas": "1333-74-0", "name": "hydrogen",           "hhv_mj_kg": 141.80, "lhv_mj_kg": 119.96, "mw_g_mol": 2.016},
    {"cas": "630-08-0",  "name": "carbon monoxide",    "hhv_mj_kg": 10.10, "lhv_mj_kg": 10.10, "mw_g_mol": 28.010},
    {"cas": "7664-41-7", "name": "ammonia",            "hhv_mj_kg": 22.50, "lhv_mj_kg": 18.60, "mw_g_mol": 17.031},
    {"cas": "74-90-8",   "name": "hydrogen cyanide",   "hhv_mj_kg": 22.50, "lhv_mj_kg": 20.30, "mw_g_mol": 27.026},
    # ---- 不可燃 / 惰性 7 种（HHV = 0）----
    {"cas": "7446-09-5", "name": "sulfur dioxide",     "hhv_mj_kg": 0.00, "lhv_mj_kg": 0.00, "mw_g_mol": 64.066},
    {"cas": "7727-37-9", "name": "nitrogen",           "hhv_mj_kg": 0.00, "lhv_mj_kg": 0.00, "mw_g_mol": 28.014},
    {"cas": "7782-44-7", "name": "oxygen",             "hhv_mj_kg": 0.00, "lhv_mj_kg": 0.00, "mw_g_mol": 31.998},
    {"cas": "7732-18-5", "name": "water",              "hhv_mj_kg": 0.00, "lhv_mj_kg": 0.00, "mw_g_mol": 18.015},
    {"cas": "124-38-9",  "name": "carbon dioxide",     "hhv_mj_kg": 0.00, "lhv_mj_kg": 0.00, "mw_g_mol": 44.009},
    {"cas": "7440-59-7", "name": "helium",             "hhv_mj_kg": 0.00, "lhv_mj_kg": 0.00, "mw_g_mol": 4.003},
    {"cas": "7440-37-1", "name": "argon",              "hhv_mj_kg": 0.00, "lhv_mj_kg": 0.00, "mw_g_mol": 39.948},
    # ---- 异构烯 / 高辛烷值 2 种（凑齐 64）----
    {"cas": "540-84-1",  "name": "isooctane",          "hhv_mj_kg": 47.78, "lhv_mj_kg": 44.50, "mw_g_mol": 114.232},
    {"cas": "592-41-6",  "name": "1-hexene",           "hhv_mj_kg": 47.95, "lhv_mj_kg": 44.83, "mw_g_mol": 84.162},
]


def _print_rows(label: str) -> None:
    """打印 64 行化合物热值 + SYNTHETIC 注释（--dry-run 与执行后都用）。"""
    print(
        f"[{label}] compound_heating_values 共 {len(SYNTHETIC_COMPOUNDS)} 行"
        "（GPSA FIG. 23-2 + API 5B6 公开值近似）："
    )
    print("  # 注：以下均为合成数据，仅用于开发/测试；真实 HHV/LHV 由工艺工程师")
    print("  # 从 GPSA Engineering Data Book FIG. 23-2 + API 5B6 获取并替换。")
    print("  # 参见 docs/p6-gate-reports/gate-03-compound-heating-values-confirmation.md")
    print(
        f"  {'cas':<11}  {'name':<22}  {'hhv':>8}  {'lhv':>8}  {'mw':>8}"
    )
    for row in SYNTHETIC_COMPOUNDS:
        print(
            f"  {row['cas']:<11}  {row['name']:<22}  {row['hhv_mj_kg']:>8.2f}  "
            f"{row['lhv_mj_kg']:>8.2f}  {row['mw_g_mol']:>8.3f}"
        )


def _replace_seed_rows(engine) -> tuple[int, int]:
    """先 DELETE ``source='SYNTHETIC_TEST_DATA'`` 行，再 INSERT 全量。

    幂等：第二次跑只剩 INSERT 64 行（DELETE 已无目标行）。
    不覆盖 ``confirmed_by`` / ``confirmed_at``（被工艺室签字流程手动维护）；
    但本任务 DELETE 仅针对 ``source='SYNTHETIC_TEST_DATA'``，工艺室已签字
    的真实数据行（如 ``source='GPSA_ED13_FIG23-2'``）不会被触碰。

    返回 (deleted_count, inserted_count)。
    """
    deleted = 0
    inserted = len(SYNTHETIC_COMPOUNDS)
    with engine.begin() as conn:
        # Step 1: DELETE 仅 SYNTHETIC 标记
        result = conn.execute(
            delete(CompoundHeatingValues).where(
                CompoundHeatingValues.source == "SYNTHETIC_TEST_DATA",
            )
        )
        deleted = result.rowcount or 0
        # Step 2: INSERT 全量 64 行（已注入 source='SYNTHETIC_TEST_DATA'）
        conn.execute(
            __import__("sqlalchemy").dialects.postgresql.insert(
                CompoundHeatingValues
            ).values(
                [
                    {
                        "cas": row["cas"],
                        "name": row["name"],
                        "hhv_mj_kg": row["hhv_mj_kg"],
                        "lhv_mj_kg": row["lhv_mj_kg"],
                        "mw_g_mol": row["mw_g_mol"],
                        "source": "SYNTHETIC_TEST_DATA",
                    }
                    for row in SYNTHETIC_COMPOUNDS
                ]
            )
        )
    return deleted, inserted


def main() -> int:
    """CLI 入口：--dry-run 仅打印；默认 INSERT 64 行到 pcs/pcs_test 库。

    DATABASE_URL 由 ``app.core.config.get_settings()`` 解析。真实数据库执行
    时，库内必须已应用 alembic 升级到包含 ``p6_4_001_compound_heating_values``
    的 head。
    """
    parser = argparse.ArgumentParser(description="C-06 气体热值数据录入")
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
                select(CompoundHeatingValues)
            ).scalars().all()
    finally:
        engine.dispose()
    print(
        f"[EXECUTE] DELETE 旧合成行 {deleted}；INSERT 新合成行 {inserted}；"
        f"表内总计 {len(total)} 行。"
    )
    print(
        "[EXECUTE] 工艺室确认占位文档："
        "docs/p6-gate-reports/gate-03-compound-heating-values-confirmation.md"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())