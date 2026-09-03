from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.change_impact import router as change_impact_router
from app.api.v1.checklist import router as checklist_router
from app.api.v1.config import router as config_router
from app.api.v1.health import router as health_router
from app.api.v1.lineage import router as lineage_router
from app.api.v1.records import router as records_router
from app.api.v1.workspaces import router as workspaces_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(workspaces_router)
api_router.include_router(checklist_router)
api_router.include_router(records_router)
api_router.include_router(lineage_router)
api_router.include_router(change_impact_router)
api_router.include_router(config_router)