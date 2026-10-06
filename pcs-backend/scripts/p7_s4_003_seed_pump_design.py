"""把泵设计参数写入 `EquipmentList.design_parameters_json`（P7 Sprint 4 S4-2 配套）.

`design_parameters_json` 此前无任何写入方（恒 NULL），偏差报告与确认流程因此在生产
路径上恒为「缺设计值（不可判）」。本脚本把
`app/services/equip_list/pump_design_data.py::PUMP_DESIGN`
（转录自 `sample/1216D132*.xlsx` 的 `机泵选型(基础设计)` sheet）落到位号匹配的设备上。

幂等：重复执行结果相同。位号不在设计表内的设备一律跳过，不写空对象。

⚠️ **默认 dry-run**（审查 #14 用户裁决）：不加 `--apply` 只报告不写。写入路径对
已有非空 `design_parameters_json` 的设备**默认跳过**，`--overwrite` 才覆盖。

⚠️ **首次真跑前必须备份** —— 覆盖时旧值无快照，回滚只能靠这个::

    CREATE TABLE design_params_backup_20261006 AS
    SELECT equipment_id, tag_number, design_parameters_json
    FROM equipment_list
    WHERE design_parameters_json IS NOT NULL;

用法::

    # 1) 先 dry-run 看会写什么（默认）
    cd pcs-backend && uv run python scripts/p7_s4_003_seed_pump_design.py --project-id <UUID>

    # 2) 备份（首次真跑前必做）
    # 3) 真跑
    cd pcs-backend && uv run python scripts/p7_s4_003_seed_pump_design.py --project-id <UUID> --apply

先查项目 ID::

    cd pcs-backend && uv run python -c "
    from app.db.session import get_async_session_factory; from app.models.project import Project
    from sqlalchemy import select
    import asyncio
    async def m():
        async with get_async_session_factory()() as s:
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

from app.db.session import get_async_session_factory  # noqa: E402
from app.models.equipment import EquipmentList  # noqa: E402
from app.services.equip_list.pump_design_data import (  # noqa: E402
    PUMP_DESIGN,
    PUMP_DESIGN_EXCLUDED,
    apply_design_parameters,
    matching_pump_records,
)


async def _main(project_id: uuid.UUID, *, apply: bool, overwrite: bool) -> int:
    async with get_async_session_factory()() as session:
        before = await matching_pump_records(session, project_id)
        already = sum(1 for e in before if e.design_parameters_json)
        print(f"项目 {project_id}: 位号匹配 {len(before)} 台, 已有设计值 {already} 台")

        if already and not overwrite and apply:
            print(
                f"\n✗ 有 {already} 台设备的 design_parameters_json 已非空 —— "
                "加 --overwrite 才会覆盖, 否则本脚本拒绝写入以免绕过设计签署。\n"
                "  确认要覆盖时, 先跑一遍本脚本的 dry-run 看清清单, 并备份旧值:\n"
                "  CREATE TABLE design_params_backup_20261006 AS\n"
                "  SELECT equipment_id, tag_number, design_parameters_json\n"
                "  FROM equipment_list WHERE design_parameters_json IS NOT NULL;",
                file=sys.stderr,
            )
            return 2

        n = await apply_design_parameters(
            session, project_id, overwrite=overwrite, dry_run=not apply
        )
        verb = "写入" if apply else "将写入(dry-run)"
        print(f"{verb}设计值: {n} 台")

        # 断言落库结果与位号匹配数一致（审查 #32）。真实失效模式是**静默部分匹配**
        # —— Excel 同步时位号写法有细微差异就会产出一行「写入 0 台」而操作者没注意，
        # 而下游结果恰好是这次改动本来要修的东西（报告继续读「缺设计值（不可判）」）。
        if not apply:
            missing = len(before) - n
            print(f"⚠️  dry-run: {missing} 台未命中（已有设计值被跳过或位号不匹配）")
        elif n != len(before):
            print(
                f"✗ 落库数 {n} != 位号匹配数 {len(before)} —— 回填静默空转，"
                "请核对位号写法（见下方验证 SQL）",
                file=sys.stderr,
            )
            return 1

        for e in before:
            d = e.design_parameters_json or {}
            shaft = (d.get("轴功率") or {}).get("value")
            motor = (d.get("电机额定功率") or {}).get("value")
            print(f"  {e.tag_number:<20} 轴功率={shaft} kW  电机={motor} kW")

    print()
    print("部署后验证 SQL（只读，逐条人工核对）:")
    print(f"  -- 1) 本项目应有 {len(PUMP_DESIGN)} 台位号命中")
    print(f"  SELECT count(*) FROM equipment_list WHERE project_id = '{project_id}'")
    print("    AND tag_number = ANY(ARRAY(SELECT jsonb_object_keys(%s)));" % _pump_design_json())
    print("  -- 2) 这些行应全部有非空设计值（期望 0 缺失）")
    print(f"  SELECT tag_number FROM equipment_list WHERE project_id = '{project_id}'")
    print("    AND design_parameters_json IS NULL;")
    print("  -- 3) 录入状态分布 —— 佐证 SPEC §3.2.4(5) 的实际/设计分流声明")
    print("  SELECT actual_data_status, count(*) FROM equipment_list")
    print(f"    WHERE project_id = '{project_id}' GROUP BY 1;")
    print("  -- 4) 轴功率/电机额定功率齐备性（电机规则要靠轴功率当参照量）")
    print("  SELECT tag_number FROM equipment_list")
    print(f"    WHERE project_id = '{project_id}'")
    print("    AND (design_parameters_json->'轴功率') IS NULL;")

    print()
    print(f"已排除的坏值 {len(PUMP_DESIGN_EXCLUDED)} 条（不写入）:")
    for tag, why in PUMP_DESIGN_EXCLUDED.items():
        print(f"  {tag}: {why}")
    return 0


def _pump_design_json() -> str:
    """把 PUMP_DESIGN 渲染成可直接贴进 psql 的 jsonb 字面量（验证 SQL 用）。"""
    import json as _json
    return _json.dumps(list(PUMP_DESIGN), ensure_ascii=False)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project-id", required=True, type=uuid.UUID)
    ap.add_argument(
        "--apply", action="store_true",
        help="真正写入。默认 dry-run: 只报告将写什么, 不落库",
    )
    ap.add_argument(
        "--overwrite", action="store_true",
        help="允许覆盖已有非空 design_parameters_json（须先备份, 见 --help）",
    )
    args = ap.parse_args()
    return asyncio.run(
        _main(args.project_id, apply=args.apply, overwrite=args.overwrite)
    )


if __name__ == "__main__":
    raise SystemExit(main())
