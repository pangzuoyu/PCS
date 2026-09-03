"""Health endpoint（async via check_database_async，Sprint 1）。"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.db.session import check_database_async

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    database: str


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    db_ok = await check_database_async()
    return HealthResponse(
        status="ok" if db_ok else "degraded",
        database="up" if db_ok else "down",
    )