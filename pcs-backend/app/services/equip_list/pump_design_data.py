"""泵设计参数（P7 Sprint 4 · S4-2 设计值缺口收口）.

`EquipmentList.design_parameters_json` 此前**无任何写入方**（恒 NULL）—— 偏差报告与
确认流程因此在生产路径上恒为「缺设计值（不可判）」，跑不出任何真实结论。

数据源: `sample/1216D132惠州蜡油加氢装置计算14.7.17计算 - 副本.xlsx`
→ `机泵选型(基础设计)` sheet。该表是**转置**的（列=泵，行=参数），`泵设备编号`
与已同步进 `utility_power_items` / `EquipmentList` 的 `tag_number` 逐台吻合。

**为什么用「基础设计」而不是「详细设计新模板」**（用户裁决 2026-10-06）:
详细设计表 36 列，同一台泵按入口/出口/不同工况点重复出现多列，无法确定哪列权威；
且与基础设计**互相矛盾** —— 132-P-101A/B 两表轴功率同为 2214.06 kW，但选配电机
基础设计 2500 kW、详细设计 1400 kW，差 1.8 倍；其「功率裕量系数」行还有 `#DIV/0!`。
基础设计 18 列结构干净，且 PCS 现有 `motor_power_kw` 本就取自本表轴功率，
换表不引入不一致。

格式与 `actual_data_json` 对称: ``{参数名: {"value": float, "unit": str}}``，
供 S4-2 偏差报告按参数名逐项比对。

⚠️ **本模块只放设计值，不放折标系数** —— 折标系数归 `config_energy_conversion_factors`，
两者混在一处会让人误以为泵参数也是 CONFIG。
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.equipment import EquipmentList

# ---------------------------------------------------------------------------
# 转录数据（tag → {参数名: 值}；None = 该表本格为空）
# ---------------------------------------------------------------------------

PUMP_DESIGN: dict[str, dict[str, float | None]] = {
    "132-P-101A/B": {"扬程": 2100.0, "效率": 0.8, "NPSHr": 2.0, "轴功率": 2214.06,
                     "电机额定功率": 2500.0, "电机配用功率": 3300.0, "转速": 2982.0},
    # 液力透平 —— 靠介质驱动, 无电机。电机字段留 None, 不编。
    "132-P-101-T": {"扬程": 2000.0, "效率": 0.8, "NPSHr": 2.0, "轴功率": 1363.08,
                    "电机额定功率": None, "电机配用功率": 2500.0, "转速": None},
    "132-P-102A/B": {"扬程": 120.0, "效率": 0.6, "NPSHr": 2.0, "轴功率": 233.748,
                     "电机额定功率": 280.0, "电机配用功率": None, "转速": 2980.0},
    "132-P-103A/B": {"扬程": 336.0, "效率": 0.49, "NPSHr": 1.25, "轴功率": 24.4783,
                     "电机额定功率": 37.0, "电机配用功率": 31.8193, "转速": 2950.0},
    "132-P-104A/B": {"扬程": 130.0, "效率": 0.4, "NPSHr": 3.5, "轴功率": 27.4544,
                     "电机额定功率": 37.0, "电机配用功率": 31.8038, "转速": 2950.0},
    "132-P-106A/B": {"扬程": 78.0, "效率": 0.77, "NPSHr": 4.8, "轴功率": 85.4407,
                     "电机额定功率": 110.0, "电机配用功率": 95.6792, "转速": 2980.0},
    "132-P-201A/B": {"扬程": 90.0, "效率": 0.45, "NPSHr": 2.5, "轴功率": 8.2742,
                     "电机额定功率": 15.0, "电机配用功率": 12.7428, "转速": 2930.0},
    "132-P-202A/B": {"扬程": 131.0, "效率": 0.75, "NPSHr": 6.0, "轴功率": 139.467,
                     "电机额定功率": 185.0, "电机配用功率": 169.646, "转速": 2980.0},
    "132-P-203A/B": {"扬程": 210.0, "效率": 0.48, "NPSHr": 3.0, "轴功率": 65.4595,
                     "电机额定功率": 90.0, "电机配用功率": 82.3935, "转速": 2970.0},
    "132-P-204A/B": {"扬程": 116.0, "效率": 0.39, "NPSHr": 3.6, "轴功率": 8.03288,
                     "电机额定功率": 15.0, "电机配用功率": 10.4735, "转速": 2930.0},
    "132-P-205A/B": {"扬程": 73.0, "效率": 0.66, "NPSHr": 4.0, "轴功率": 37.6752,
                     "电机额定功率": 55.0, "电机配用功率": 59.6615, "转速": 2970.0},
    "132-P-206A/B": {"扬程": 225.0, "效率": 0.34, "NPSHr": 1.25, "轴功率": 48.8913,
                     "电机额定功率": 75.0, "电机配用功率": 63.1481, "转速": 2970.0},
    "132-P-207A/B": {"扬程": 263.0, "效率": 0.73, "NPSHr": 3.2, "轴功率": 264.025,
                     "电机额定功率": 355.0, "电机配用功率": 363.691, "转速": 2982.0},
    "132-P-301A/B": {"扬程": 328.0, "效率": 0.73, "NPSHr": 4.0, "轴功率": 200.799,
                     "电机额定功率": 250.0, "电机配用功率": 221.992, "转速": 2980.0},
    "132-P-401": {"扬程": 127.0, "效率": 0.33, "NPSHr": None, "轴功率": 20.9742,
                  "电机额定功率": 30.0, "电机配用功率": 30.7614, "转速": 2950.0},
    "132-P-404": {"扬程": 88.0, "效率": 0.36, "NPSHr": None, "轴功率": 13.3222,
                  "电机额定功率": 18.5, "电机配用功率": 16.6528, "转速": 2930.0},
    "132-P-406A/B": {"扬程": 48.0, "效率": 0.5, "NPSHr": 2.5, "轴功率": 4.63032,
                     "电机额定功率": 11.0, "电机配用功率": 5.85174, "转速": 2930.0},
}

# 坏值 —— 按用户裁决 2026-10-06「坏值放弃不用」排除。理由必填: 免得日后有人
# 「顺手」把它加回 PUMP_DESIGN, 那正是坏值当初混进来的路径。
PUMP_DESIGN_EXCLUDED: dict[str, str] = {
    "132-P-105A/B/C/D": "轴功率 0.166 kW / 电机 18.5 kW, 比值 111.7× —— 数量级错误",
    "132-P-102A/B#电机配用功率": "该格为 #DIV/0!（轴功率/电机功率本身正常, 单列作废）",
}

# 参数 → 单位。与 actual_data_json 的 unit 字段同口径。
_UNITS: dict[str, str] = {
    "扬程": "m",
    "效率": "-",
    "NPSHr": "m",
    "轴功率": "kW",
    "电机额定功率": "kW",
    "电机配用功率": "kW",
    "转速": "r/min",
}


def design_params_for_tag(tag_number: str) -> dict[str, dict[str, float | str]]:
    """位号 → design_parameters_json 形状。未知位号返回 {}（不编造）。"""
    raw = PUMP_DESIGN.get(tag_number)
    if not raw:
        return {}
    # None 不进 JSONB —— 下游会把「空」读成 0, 那比缺字段更危险
    return {
        name: {"value": float(value), "unit": _UNITS.get(name, "")}
        for name, value in raw.items()
        if value is not None
    }


async def apply_design_parameters(
    session: AsyncSession,
    project_id: uuid.UUID,
    *,
    overwrite: bool = False,
    dry_run: bool = False,
) -> int:
    """把设计值写进该 project 下位号匹配的 `EquipmentList`.

    幂等: 重复执行结果相同, 不累加不清空。

    **不碰** `actual_data_json` / `actual_data_status` —— 设计值与实测值是两条
    独立的流（SPEC §3.2.4(5)「实际数据与设计数据分离存储」），这里越界写会
    把「已确认」的实际值搞乱。

    位号不在设计表内的设备一律跳过, **不写空对象** —— 那会覆盖已有值。

    覆盖策略（审查 #14，用户裁决）:
      - `overwrite=False`（默认）: 已有非空 `design_parameters_json` 的设备
        **跳过不写**。设计值是设计人签过的东西，静默覆盖等于绕过签署。
      - `dry_run=False`（默认）: 正常写入并 commit。脚本层默认 dry-run
        （`p7_s4_003_seed_pump_design.py` 不加 `--apply` 只报告不落库），
        首次真跑须在脚本侧显式加 `--apply`。

    Returns:
        实际写入的设备数（dry_run 时为「将会写入」的台数）。
    """
    records = await matching_pump_records(session, project_id)

    written = skipped = 0
    for record in records:
        params = design_params_for_tag(record.tag_number)
        if not params:
            continue
        if record.design_parameters_json and not overwrite:
            # 已有非空设计值 = 设计人签过的东西。静默覆盖等于绕过签署（审查 #14）。
            skipped += 1
            continue
        record.design_parameters_json = params
        written += 1

    if written and not dry_run:
        await session.commit()
    return written


async def matching_pump_records(session, project_id) -> list:
    """本 project 下位号命中 `PUMP_DESIGN` 的设备（审查 #27）.

    `apply_design_parameters` 与种子脚本的「before」快照此前各自写了一份逐字相同
    的 WHERE 子句。脚本并排打印的「位号匹配 N 台 / 写入设计值 M 台」读起来像 M 由
    N 派生 —— 只在两份 WHERE 一致时成立。任一方加了过滤条件就会静默漂移，而脚本
    输出是这次回填唯一的可见性来源。故收敛到这一个函数，两处都调它。
    """
    return (
        await session.execute(
            select(EquipmentList).where(
                EquipmentList.project_id == project_id,
                EquipmentList.tag_number.in_(list(PUMP_DESIGN)),
            )
        )
    ).scalars().all()


__all__ = [
    "PUMP_DESIGN",
    "PUMP_DESIGN_EXCLUDED",
    "apply_design_parameters",
    "design_params_for_tag",
]
