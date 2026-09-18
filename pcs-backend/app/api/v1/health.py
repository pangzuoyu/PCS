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
    """GET /health（liveness + DB 探测）。

    步骤：
    1. 调 check_database_async（asyncpg SELECT 1）探测 DB 连接
    2. 返回 {status, database}：db ok → "ok"/"up"，db fail → "degraded"/"down"
    3. 始终 200（不依赖 DB 状态码），由调用方按字段判定

    用于：K8s liveness probe / 监控 / 容器 orchestrator 健康检查。
    不暴露敏感信息（无 DB URL / 表名 / 用户名）。
    """
    db_ok = await check_database_async()
    return HealthResponse(
        status="ok" if db_ok else "degraded",
        database="up" if db_ok else "down",
    )