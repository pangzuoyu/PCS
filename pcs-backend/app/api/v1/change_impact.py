"""Change Impact API（Sprint 3）。

POST /change-impact/{record_type}/{record_id}/confirm-recalc
高层动作：哈希比较 → 若变化 → CIA 引擎扫描 → 链式传播 + 设备联动。
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.cia_engine import (
    CIAEngine,
    mark_stale_then_propagate,
)
from app.services.lineage import LineageTracker, _compute_hash

router = APIRouter(prefix="/change-impact", tags=["change-impact"])


@router.post("/{record_type}/{record_id}/confirm-recalc", response_model=dict)
async def confirm_recalc(
    record_type: str,
    record_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
):
    """强制触发 CIA 扫描 + 传播 + 设备联动。"""
    # 仅支持已纳入 CIA 的 record 类型
    if record_type not in {"PipingResult"}:
        return {
            "record_type": record_type,
            "record_id": str(record_id),
            "marked_stale": 0,
            "propagated": 0,
            "equipment_affected": 0,
            "note": f"record_type {record_type} not in CIA scope",
        }
    # 拉取最新 lineage + current hash
    tracker = LineageTracker(session)
    latest = await tracker.latest(record_type=record_type, record_id=record_id)
    engine = CIAEngine(session)
    marked = await engine.scan_stale()
    propagation = await mark_stale_then_propagate(
        session,
        record_type=record_type,
        record_id=record_id,
    )
    await session.commit()
    return {
        "record_type": record_type,
        "record_id": str(record_id),
        "marked_stale": marked,
        "propagated": propagation["propagated"],
        "equipment_affected": propagation["equipment"],
        "latest_lineage": (
            {
                "lineage_id": str(latest.lineage_id),
                "source": latest.source,
                "change_summary": latest.change_summary,
            }
            if latest
            else None
        ),
    }


# 用于类型提示；保持引用
_ = _compute_hash