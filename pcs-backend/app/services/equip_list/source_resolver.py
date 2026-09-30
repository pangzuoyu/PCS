"""S1-4 R3: SourceModule → ORM class dispatcher。

Per D2 裁决 2A: SourceModule string（PUMP/VESSEL/HEAT/PSV/CV/COOL_TOWER/
PSYCHRO/OPEN_CHANNEL）需 dispatch 到对应 ORM class（pump_results/...）
以加载 source 记录供 sync_from_source 使用。

扩展：SourceModule 增多时在 ``_MODULE_DISPATCH`` append 新条目即可。
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.calc import (
    CoolingTowerResult,
    CvResult,
    HeatResult,
    OpenChannelResult,
    PsychroResult,
    PsvResult,
    PumpResult,
    VesselResult,
)


class UnsupportedSourceModuleError(ValueError):
    """source_module 不在 dispatcher 表内。"""


# module → (ORM class, id-column name)
_MODULE_DISPATCH: dict[str, tuple[type, str]] = {
    "PUMP": (PumpResult, "pump_id"),
    "VESSEL": (VesselResult, "vessel_id"),
    "HEAT": (HeatResult, "heat_id"),
    "PSV": (PsvResult, "psv_id"),
    "CV": (CvResult, "cv_id"),
    "COOL_TOWER": (CoolingTowerResult, "cooling_tower_id"),
    "PSYCHRO": (PsychroResult, "psychro_id"),
    "OPEN_CHANNEL": (OpenChannelResult, "open_channel_id"),
}


async def get_source_record(
    source_module: str,
    source_record_id: UUID,
    db: AsyncSession,
):
    """R3: dispatch source_module → ORM class → load by source_record_id.

    Returns the source ORM record（any of the *Result models）。Caller uses
    ``source.sign_status`` / ``project_id`` / ``workspace_id`` /
    ``tag_number`` / ``approval_*`` fields.

    Returns ``None`` if source_module 在 dispatcher 表内但 id 找不到记录。

    Raises:
        UnsupportedSourceModuleError: source_module 不在 dispatcher 表内。
    """
    if source_module not in _MODULE_DISPATCH:
        raise UnsupportedSourceModuleError(
            f"source_module {source_module!r} not supported; "
            f"valid: {sorted(_MODULE_DISPATCH.keys())}"
        )
    orm_cls, id_col = _MODULE_DISPATCH[source_module]
    stmt = select(orm_cls).where(getattr(orm_cls, id_col) == source_record_id)
    return (await db.execute(stmt)).scalar_one_or_none()
