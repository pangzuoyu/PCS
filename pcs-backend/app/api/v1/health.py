from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    database: str


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Task 1 阶段固定 ok/unknown；Task 2 接入 check_database 后改为真实探测。"""
    return HealthResponse(status="ok", database="unknown")
