"""P6-3 Task 35：cost_correlations CONFIG seed（SPEC §3.2.8）。

依据：6 设备类型成本关联式（TOWER / VESSEL / HEAT_EXCHANGER / PUMP /
COMPRESSOR / PIPING）— 与 ``app/services/cost_est/cost_correlation_lookup``
内置兜底常量严格对齐。

镜像 G-03 / G-04 / G-05 / G-06 seed 模式：

- 字段定义与 ``app/models/config.py:CostCorrelationLibrary`` ORM
  严格对齐；
- upsert 语义：按 ``(equipment_type, version)`` 唯一索引，存在则
  覆盖业务字段 + ``notes``（不变 ``base_currency`` / ``base_year``
  默认）；工艺室签字字段由 G-X 流程单独维护（本任务占位 NULL）；
- ``--dry-run`` 仅打印 [DRY-RUN] / [SKIP] 日志，不写 DB。

用法：

    cd pcs-backend
    uv run python scripts/p6_3_seed_cost_correlations.py --dry-run
    uv run python scripts/p6_3_seed_cost_correlations.py        # 真库 upsert
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
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.models.config import CostCorrelationLibrary  # noqa: E402


# 6 设备类型关联式（与 cost_correlation_lookup._COST_CORRELATIONS 严格对齐）
_CORRELATIONS: list[dict[str, object]] = [
    {
        "equipment_type": "TOWER",
        "version": "v1",
        "coefficient_a": 15000.0,
        "coefficient_b": 25000.0,
        "scaling_exponent_n": 0.85,
        "scale_unit": "D(m)",
        "valid_range_low": 0.3,
        "valid_range_high": 8.0,
        "base_currency": "USD",
        "base_year": 2019,
        "notes": "塔器成本关联式（直径 D，m；COST_EST §3.2.8）",
    },
    {
        "equipment_type": "VESSEL",
        "version": "v1",
        "coefficient_a": 8000.0,
        "coefficient_b": 12000.0,
        "scaling_exponent_n": 0.70,
        "scale_unit": "V(m³)",
        "valid_range_low": 0.1,
        "valid_range_high": 200.0,
        "base_currency": "USD",
        "base_year": 2019,
        "notes": "容器成本关联式（容积 V，m³；COST_EST §3.2.8）",
    },
    {
        "equipment_type": "HEAT_EXCHANGER",
        "version": "v1",
        "coefficient_a": 5000.0,
        "coefficient_b": 3500.0,
        "scaling_exponent_n": 0.65,
        "scale_unit": "A(m²)",
        "valid_range_low": 1.0,
        "valid_range_high": 2000.0,
        "base_currency": "USD",
        "base_year": 2019,
        "notes": "换热器成本关联式（换热面积 A，m²；COST_EST §3.2.8）",
    },
    {
        "equipment_type": "PUMP",
        "version": "v1",
        "coefficient_a": 3000.0,
        "coefficient_b": 1200.0,
        "scaling_exponent_n": 0.55,
        "scale_unit": "Q(m³/h)",
        "valid_range_low": 0.5,
        "valid_range_high": 5000.0,
        "base_currency": "USD",
        "base_year": 2019,
        "notes": "泵成本关联式（流量 Q，m³/h；COST_EST §3.2.8）",
    },
    {
        "equipment_type": "COMPRESSOR",
        "version": "v1",
        "coefficient_a": 25000.0,
        "coefficient_b": 18000.0,
        "scaling_exponent_n": 0.75,
        "scale_unit": "P(kW)",
        "valid_range_low": 5.0,
        "valid_range_high": 20000.0,
        "base_currency": "USD",
        "base_year": 2019,
        "notes": "压缩机成本关联式（轴功率 P，kW；COST_EST §3.2.8）",
    },
    {
        "equipment_type": "PIPING",
        "version": "v1",
        "coefficient_a": 200.0,
        "coefficient_b": 80.0,
        "scaling_exponent_n": 0.90,
        "scale_unit": "L·D",
        "valid_range_low": 10.0,
        "valid_range_high": 5000.0,
        "base_currency": "USD",
        "base_year": 2019,
        "notes": "管路成本关联式（长度 L×直径 D；COST_EST §3.2.8）",
    },
]


def _existing_row(session, equipment_type: str, version: str):  # noqa: ANN001
    return session.execute(
        select(CostCorrelationLibrary).where(
            CostCorrelationLibrary.equipment_type == equipment_type,
            CostCorrelationLibrary.version == version,
        )
    ).scalar_one_or_none()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="P6-3 Task 35 cost_correlations CONFIG seed 脚本",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅打印 [DRY-RUN] / [SKIP] 日志，不写 DB。",
    )
    args = parser.parse_args()

    settings = get_settings()
    print(
        f"[BOOT] cost_correlations seed (dry_run={args.dry_run}) "
        f"DB={settings.database_url.split('@')[-1] if '@' in settings.database_url else 'sqlite'}"
    )

    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    with SessionLocal() as session:
        for corr in _CORRELATIONS:
            et = str(corr["equipment_type"])
            ver = str(corr["version"])
            if args.dry_run:
                existing = _existing_row(session, et, ver)
                if existing is not None:
                    print(f"[SKIP] {et}/{ver} already exists (id={existing.id})")
                else:
                    print(
                        f"[DRY-RUN] {et}/{ver} would be inserted: "
                        f"a={corr['coefficient_a']} b={corr['coefficient_b']} "
                        f"n={corr['scaling_exponent_n']} unit={corr['scale_unit']}"
                    )
            else:
                stmt = pg_insert(CostCorrelationLibrary).values(**corr)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["equipment_type", "version"],
                    set_={
                        "coefficient_a": stmt.excluded.coefficient_a,
                        "coefficient_b": stmt.excluded.coefficient_b,
                        "scaling_exponent_n": stmt.excluded.scaling_exponent_n,
                        "scale_unit": stmt.excluded.scale_unit,
                        "valid_range_low": stmt.excluded.valid_range_low,
                        "valid_range_high": stmt.excluded.valid_range_high,
                        "notes": stmt.excluded.notes,
                    },
                )
                session.execute(stmt)
                print(f"[UPSERT] {et}/{ver}")
        if not args.dry_run:
            session.commit()
            print("[COMMIT] session committed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
