"""Lineage API（Sprint 3）。

3 端点：
- GET /lineage/{record_type}/{record_id}/upstream
- GET /lineage/{record_type}/{record_id}/downstream
- GET /lineage/{record_type}/{record_id}/graph（upstream + downstream 完整图）
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.lineage import LineageTracker

router = APIRouter(prefix="/lineage", tags=["lineage"])


@router.get("/{record_type}/{record_id}/upstream", response_model=list[dict])
async def upstream(
    record_type: str,
    record_id: uuid.UUID,
    max_depth: int = Query(10, ge=1, le=50),
    session: AsyncSession = Depends(get_db),
):
    tracker = LineageTracker(session)
    chain = await tracker.upstream(
        record_type=record_type, record_id=record_id, max_depth=max_depth
    )
    return [_serialize(c) for c in chain]


@router.get("/{record_type}/{record_id}/downstream", response_model=list[dict])
async def downstream(
    record_type: str,
    record_id: uuid.UUID,
    max_depth: int = Query(10, ge=1, le=50),
    session: AsyncSession = Depends(get_db),
):
    tracker = LineageTracker(session)
    latest = await tracker.latest(record_type=record_type, record_id=record_id)
    if latest is None:
        raise HTTPException(404, "no lineage for record")
    chain = await tracker.downstream(lineage_id=latest.lineage_id, max_depth=max_depth)
    return [_serialize(c) for c in chain]


@router.get("/{record_type}/{record_id}/graph", response_model=dict)
async def graph(
    record_type: str,
    record_id: uuid.UUID,
    max_depth: int = Query(10, ge=1, le=50),
    session: AsyncSession = Depends(get_db),
):
    tracker = LineageTracker(session)
    latest = await tracker.latest(record_type=record_type, record_id=record_id)
    if latest is None:
        raise HTTPException(404, "no lineage for record")
    up = await tracker.upstream(
        record_type=record_type, record_id=record_id, max_depth=max_depth
    )
    down = await tracker.downstream(lineage_id=latest.lineage_id, max_depth=max_depth)
    return {
        "root": _serialize(latest),
        "upstream": [_serialize(c) for c in up],
        "downstream": [_serialize(c) for c in down],
    }


def _serialize(lineage) -> dict:
    return {
        "lineage_id": str(lineage.lineage_id),
        "record_type": lineage.record_type,
        "record_id": str(lineage.record_id),
        "parent_lineage_id": (
            str(lineage.parent_lineage_id) if lineage.parent_lineage_id else None
        ),
        "source": lineage.source,
        "source_ref_type": lineage.source_ref_type,
        "source_ref_id": str(lineage.source_ref_id) if lineage.source_ref_id else None,
        "actor_user_id": str(lineage.actor_user_id) if lineage.actor_user_id else None,
        "change_summary": lineage.change_summary,
        "occurred_at": lineage.occurred_at.isoformat() if lineage.occurred_at else None,
    }