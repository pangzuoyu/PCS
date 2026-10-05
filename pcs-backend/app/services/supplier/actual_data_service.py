"""供应商实际数据录入（手动）— P7 Sprint 4 S4-1 / ADR-0025.

设备从「设计值」流转到「实际值」。本模块负责把一次录入的实测值
校验后写入 `EquipmentList.actual_data_json`，并把 `actual_data_status`
推进到 `PENDING_CONFIRM`（确认流程在 S4-3）。

形状: ``{参数名: {"value": float, "unit": str}}``

校验三条（都抛 `ACTUAL_DATA_VALIDATION` 422）:
1. value 必须是数值（字符串数字也拒 —— 供应商表里 "100" 与 100 混用会让
   偏差报告的百分比计算行为不可预期）
2. name 非空
3. name 不重复（否则 JSONB 静默覆盖，录入者不会知道丢了一个值）
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import PcsError
from app.models.equipment import EquipmentList
from app.models.enums import ActualDataStatus


def _validation_error(message: str) -> PcsError:
    return PcsError(
        code="ACTUAL_DATA_VALIDATION", message=message, status=422
    )


def _coerce_value(raw: Any, name: str) -> float:
    """value → float；非数值抛错（不接受 '100' 这类字符串数字）."""
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise _validation_error(
            f"参数 {name!r} 的实测值必须是数值, 收到 {type(raw).__name__}: {raw!r}"
        )
    return float(raw)


def normalize_entries(entries: list[dict]) -> dict[str, dict]:
    """校验 + 归一化录入项 → actual_data_json 形状.

    Raises:
        PcsError ACTUAL_DATA_VALIDATION 422
    """
    if not entries:
        raise _validation_error("录入项为空 —— 无数据可存, 状态不应推进")

    out: dict[str, dict] = {}
    for idx, item in enumerate(entries):
        if not isinstance(item, dict):
            raise _validation_error(
                f"第 {idx + 1} 项不是对象: {type(item).__name__}"
            )
        name = item.get("name")
        if not isinstance(name, str) or not name.strip():
            raise _validation_error(f"第 {idx + 1} 项 name 为空")
        name = name.strip()
        if name in out:
            raise _validation_error(
                f"参数名重复: {name!r} —— JSONB 会静默覆盖, 录入者不会知道"
            )
        value = _coerce_value(item.get("value"), name)
        unit = item.get("unit")
        if unit is not None and not isinstance(unit, str):
            raise _validation_error(
                f"参数 {name!r} 的单位必须是字符串, 收到 {type(unit).__name__}"
            )
        out[name] = {"value": value, "unit": (unit or "").strip()}
    return out


async def record_actual_data(
    session: AsyncSession,
    equipment: EquipmentList,
    entries: list[dict],
) -> EquipmentList:
    """录入一次供应商实测值（整体替换, 非合并）.

    二次录入整体替换而非合并 —— 否则上轮残留值会混入偏差计算, 而录入者
    以为已经改过。

    已确认（CONFIRMED）的数据**锁定**, 修改需校核人先退回
    （SPEC §3.2.4(5)「已确认的实际数据修改需校核人退回」）——
    静默改掉会让"已确认"这个词失去意义。

    Returns:
        更新后的 EquipmentList (已 refresh, 调用方无需再 commit).
    """
    if equipment.actual_data_status == ActualDataStatus.CONFIRMED.value:
        raise PcsError(
            code="ACTUAL_DATA_LOCKED",
            message=(
                "实际数据已确认, 修改需校核人退回后重录 "
                "(SPEC §3.2.4(5))"
            ),
            status=422,
        )

    equipment.actual_data_json = normalize_entries(entries)
    equipment.actual_data_status = ActualDataStatus.PENDING_CONFIRM.value
    await session.commit()
    await session.refresh(equipment)
    return equipment


__all__ = ["normalize_entries", "record_actual_data"]
