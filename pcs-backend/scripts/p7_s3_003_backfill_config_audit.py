"""F-P0-001 R1 audit backfill (P7 Sprint 3 / Issue 6).

为 ConfigEnergyConversionFactor 全表行补 R1 修订 audit 记录, 让工艺室
可通过 GET /api/v1/config-audit 查询 R1 历史 (backfill 写入 audit_logs).

source-verify 2026-10-03:
- ConfigEnergyConversionFactor 表名 "config_energy_conversion_factors"
- 该表无 project_id (公司级全局), BIGINT id
- audit_logs.resource_type = "config_energy_conversion_factors"
- audit_logs.resource_id = str(ConfigEnergyConversionFactor.id) (BIGINT → String(100))
- audit_logs.action = AuditAction.CONFIG_R1_BACKFILL (新加枚举)

用法:
    cd pcs-backend
    uv run python scripts/p7_s3_003_backfill_config_audit.py --dry-run
    uv run python scripts/p7_s3_003_backfill_config_audit.py        # 真库

幂等: 已存在 (CONFIG_R1_BACKFILL action + resource_type=config_energy_conversion_factors
       + resource_id=row.id) audit 跳过.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.models.config import ConfigEnergyConversionFactor  # noqa: E402
from app.models.enums import AuditAction  # noqa: E402
from app.models.system import AuditLog  # noqa: E402
from app.services.audit_service import AuditService  # noqa: E402


def _label(row: ConfigEnergyConversionFactor) -> str:
    """行标识, 便于日志."""
    return (
        f"id={row.id} energy_type={row.energy_type} value_type={row.value_type} "
        f"sub_type={row.sub_type} pressure_level={row.pressure_level} "
        f"water_type={row.water_type}"
    )


async def backfill_config_audit(db: AsyncSession, *, dry_run: bool = False) -> int:
    """回填 ConfigEnergyConversionFactor 全表 audit.

    Returns: number of audit rows written (0 in dry_run).
    """
    rows = (
        await db.execute(select(ConfigEnergyConversionFactor))
    ).scalars().all()
    print(f"[{'DRY-RUN' if dry_run else 'APPLY'}] 找到 {len(rows)} 行 ConfigEnergyConversionFactor")

    audit = AuditService(db)
    written = 0
    for row in rows:
        # 幂等检查: 已有同 (action, resource_type, resource_id) audit 跳过
        existing = await db.execute(
            select(AuditLog).where(
                AuditLog.action == AuditAction.CONFIG_R1_BACKFILL.value,
                AuditLog.resource_type == "config_energy_conversion_factors",
                AuditLog.resource_id == str(row.id),
            )
        )
        if existing.scalar_one_or_none() is not None:
            continue

        if dry_run:
            print(f"  [DRY] would write audit for {_label(row)}")
            written += 1
            continue

        await audit.write(
            action=AuditAction.CONFIG_R1_BACKFILL,
            resource_type="config_energy_conversion_factors",
            resource_id=str(row.id),
            user_id=None,  # 系统任务
            detail={
                "energy_type": row.energy_type,
                "value_type": row.value_type,
                "sub_type": row.sub_type,
                "pressure_level": row.pressure_level,
                "water_type": row.water_type,
                "toe_factor": row.toe_factor,
                "standard_coal_factor": row.standard_coal_factor,
                "source": row.source,
                "reason": "F-P0-001 R1 backfill (Sprint 3 Issue 6)",
            },
        )
        written += 1
        print(f"  [APPLY] audit for {_label(row)}")

    if not dry_run:
        await db.commit()
    print(f"[{'DRY-RUN' if dry_run else 'APPLY'}] 写入 {written} 行 audit (幂等跳过)")
    return written


async def main() -> None:
    parser = argparse.ArgumentParser(description="F-P0-001 R1 audit backfill")
    parser.add_argument("--dry-run", action="store_true", help="仅打印, 不写入")
    args = parser.parse_args()

    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSession(engine) as db:
        await backfill_config_audit(db, dry_run=args.dry_run)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())