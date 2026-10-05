"""把泵设计参数写入 `EquipmentList.design_parameters_json`（P7 Sprint 4 S4-2 配套）.

`design_parameters_json` 此前无任何写入方（恒 NULL），偏差报告与确认流程因此在生产
路径上恒为「缺设计值（不可判）」。本脚本把
`app/services/equip_list/pump_design_data.py::PUMP_DESIGN`
（转录自 `sample/1216D132*.xlsx` 的 `机泵选型(基础设计)` sheet）落到位号匹配的设备上。

幂等：重复执行结果相同。位号不在设计表内的设备一律跳过，不写空对象。

用法::

    cd pcs-backend && uv run python scripts/p7_s4_003_seed_pump_design.py --project-id <UUID>

先查项目 ID::

    cd pcs-backend && uv run python -c "
    from app.db.session import SessionLocal; from app.models.project import Project
    from sqlalchemy import select
    import asyncio
    async def m():
        async with SessionLocal() as s:
            for p in (await s.execute(select(Project))).scalars().all():
                print(p.project_id, p.project_name)
    asyncio.run(m())"
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sqlalchemy import select  # noqa: E402

from app.db.session import SessionLocal  # noqa: E402
from app.models.equipment import EquipmentList  # noqa: E402
from app.services.equip_list.pump_design_data import (  # noqa: E402
    PUMP_DESIGN,
    PUMP_DESIGN_EXCLUDED,
    apply_design_parameters,
)


async def _main(project_id: uuid.UUID) -> int:
    async with SessionLocal() as session:
        before = (
            await session.execute(
                select(EquipmentList).where(
                    EquipmentList.project_id == project_id,
                    EquipmentList.tag_number.in_(list(PUMP_DESIGN)),
                )
            )
        ).scalars().all()
        already = sum(1 for e in before if e.design_parameters_json)
        print(f"项目 {project_id}: 位号匹配 {len(before)} 台, 已有设计值 {already} 台")

        n = await apply_design_parameters(session, project_id)
        print(f"写入设计值: {n} 台")
        for e in before:
            d = e.design_parameters_json or {}
            shaft = (d.get("轴功率") or {}).get("value")
            motor = (d.get("电机额定功率") or {}).get("value")
            print(f"  {e.tag_number:<20} 轴功率={shaft} kW  电机={motor} kW")

    print()
    print(f"已排除的坏值 {len(PUMP_DESIGN_EXCLUDED)} 条（不写入）:")
    for tag, why in PUMP_DESIGN_EXCLUDED.items():
        print(f"  {tag}: {why}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project-id", required=True, type=uuid.UUID)
    args = ap.parse_args()
    return asyncio.run(_main(args.project_id))


if __name__ == "__main__":
    raise SystemExit(main())
