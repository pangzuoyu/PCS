"""P5-2-4 sep_equip 计算落库 + outlet 流（service 层）。

设计要点：
1. check_calc_inputs 三步守卫（DRAFT → 403 / 不可靠 → 422 / 不存在 → 404）
2. 5 类型分发（CYCLONE / MIST_ELIMINATOR / GRAVITY / VANE / FIBER）
3. 调 calc_cyclone / calc_mist_eliminator / calc_gravity_separator
4. 构造 SepEquipResult（input_json + output_json）+ 落库
5. finalize_calc_record（record_hash + lineage）
6. create_outlet_stream(source_type='SEP_EQUIP_CALCULATED')
7. commit + 返回 calc_id + record_hash + outlet_stream_id

input_json 双轨：
  - device_type + device_type-specific fields（由 dispatcher 构造对应 dataclass）
output_json：
  - 设备类型对应 result（frozen dataclass → dict）

不做：
- 不写 sep_equip_results 之外的派生表
- 不并发锁（与 vessel_persist 一致）
"""
from __future__ import annotations

import dataclasses
import uuid
from typing import Any, Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.calc import SepEquipResult
from app.models.project import Stream
from app.services.calc_entry import check_calc_inputs
from app.services.calc_lineage import finalize_calc_record
from app.services.exceptions import PcsError
from app.services.outlet_stream import create_outlet_stream
from app.services.sep_equip.cyclone_service import (
    CycloneInput,
    calc_cyclone,
)
from app.services.sep_equip.gravity_separator_service import (
    GravitySeparatorInput,
    calc_gravity_separator,
)
from app.services.sep_equip.mist_eliminator_service import (
    MistEliminatorInput,
    calc_mist_eliminator,
)

DeviceType = Literal[
    "CYCLONE", "MIST_ELIMINATOR", "GRAVITY", "VANE", "FIBER"
]

# P5-2-4 formula_version：固定锚点（CIA 引擎版本对齐时一并 bump）
_FORMULA_VERSION = "Se1.0-p5-2-4"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _generate_tag_number(project_id: uuid.UUID) -> str:
    """生成项目内唯一 SepEquipResult tag_number。

    格式：``SEP-{short_uuid}``（短码 8 位 hex；项目内由 DB unique 约束兜底）。
    """
    return f"SEP-{uuid.uuid4().hex[:8].upper()}"


def _dataclass_to_dict(dc: Any) -> dict:
    return dataclasses.asdict(dc)


def _dispatch_calc(
    device_type: DeviceType, params: dict[str, Any]
) -> tuple[Any, dict]:
    """按 device_type 分发到对应 calc 函数。

    Returns (input_dataclass, result_dataclass)。
    """
    if device_type == "CYCLONE":
        inp = CycloneInput(**params)
        return inp, calc_cyclone(inp)
    if device_type == "MIST_ELIMINATOR":
        inp = MistEliminatorInput(**params)
        return inp, calc_mist_eliminator(inp)
    # GRAVITY / VANE / FIBER 共享 gravity_separator；separator_type 由 device_type 映射
    sep_type_map: dict[str, str] = {
        "GRAVITY": "PLAIN",
        "VANE": "VANE",
        "FIBER": "FIBER",
    }
    inp = GravitySeparatorInput(
        separator_type=sep_type_map[device_type],  # type: ignore[arg-type]
        **params,
    )
    return inp, calc_gravity_separator(inp)


# ---------------------------------------------------------------------------
# Core entry
# ---------------------------------------------------------------------------


async def persist_sep_equip_calculate(
    db: AsyncSession,
    *,
    source_stream_id: uuid.UUID,
    device_type: DeviceType,
    params: dict[str, Any],
    actor: uuid.UUID | None = None,
) -> dict[str, Any]:
    """sep_equip 计算落库：5 类型分发 + 双轨 input_json + outlet 流。

    Args:
        db: async session
        source_stream_id: 源流 UUID
        device_type: CYCLONE / MIST_ELIMINATOR / GRAVITY / VANE / FIBER
        params: 设备类型对应参数（key 名匹配对应 Input dataclass 字段名）

    Returns:
        {
            "calc_id", "calc_type"（=device_type）, "record_hash",
            "stream_id", "result"（dict）, "outlet_stream_id", "outlet_stream_name",
        }

    Raises:
        PcsError: 三步守卫失败 / 源流不存在 / 设备类型不支持
    """
    # 1. 三步守卫
    await check_calc_inputs(db, [source_stream_id])

    # 2. 读源流
    stream = await db.get(Stream, source_stream_id)
    if stream is None:
        raise PcsError(
            f"Stream {source_stream_id} 不存在",
            code="SIM_STREAM_NOT_FOUND",
            status=404,
        )

    # 3. 设备类型校验 + dispatch
    if device_type not in ("CYCLONE", "MIST_ELIMINATOR", "GRAVITY", "VANE", "FIBER"):
        raise PcsError(
            f"device_type={device_type} 不在 5 类支持范围",
            code="SEP_EQUIP_INPUT_ERROR",
            status=422,
        )
    input_dc, result_dc = _dispatch_calc(device_type, params)

    # 4. 构造 SepEquipResult ORM
    record = SepEquipResult(
        tag_number=_generate_tag_number(stream.project_id),
        project_id=stream.project_id,
        workspace_id=stream.workspace_id,
        input_json={
            "device_type": device_type,
            "params": _dataclass_to_dict(input_dc),
        },
        output_json={
            "device_type": device_type,
            "result": _dataclass_to_dict(result_dc),
        },
    )
    db.add(record)
    await db.flush()  # 让 sep_equip_id 落库

    # 5. finalize_calc_record
    await finalize_calc_record(
        db,
        record,
        source_stream_ids=[source_stream_id],
        formula_version=_FORMULA_VERSION,
    )

    # 6. outlet 流（source_type=SEP_EQUIP_CALCULATED）
    outlet = await create_outlet_stream(
        db,
        source_stream_id=source_stream_id,
        calc_type="SEP_EQUIP",
        source_type="SEP_EQUIP_CALCULATED",
        properties={
            "_calc_type": "SEP_EQUIP",
            "device_type": device_type,
            **{k: v for k, v in _dataclass_to_dict(result_dc).items()
               if isinstance(v, (int, float, str, bool))},
        },
        project_id=stream.project_id,
        workspace_id=stream.workspace_id,
    )
    await db.flush()

    # 7. commit
    await db.commit()

    return {
        "calc_id": record.sep_equip_id,
        "calc_type": device_type,
        "record_hash": record.record_hash,
        "stream_id": source_stream_id,
        "result": _dataclass_to_dict(result_dc),
        "outlet_stream_id": outlet.stream_id,
        "outlet_stream_name": outlet.stream_name,
    }


__all__ = ["persist_sep_equip_calculate", "DeviceType"]