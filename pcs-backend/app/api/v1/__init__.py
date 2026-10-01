from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.change_impact import router as change_impact_router
from app.api.v1.checklist import router as checklist_router
from app.api.v1.common import router as common_router
from app.api.v1.config import router as config_router
from app.api.v1.cool_tower import router as cool_tower_router  # P6-2 Task 25
from app.api.v1.cost_est import router as cost_est_router  # P6-3 Task 36
from app.api.v1.cv import router as cv_router  # P6-1 Task 10
from app.api.v1.equip_lib import router as equip_lib_router
from app.api.v1.equip_list import router as equip_list_router  # P7-Sprint 1 S1-4b
from app.api.v1.filtration import router as filtration_router  # P6-3 Task 34
from app.api.v1.flare import router as flare_router  # P6-2 Task 20
from app.api.v1.flash import router as flash_router
from app.api.v1.health import router as health_router
from app.api.v1.heat import router as heat_router  # P5-4-5
from app.api.v1.imports import router as imports_router
from app.api.v1.lineage import router as lineage_router
from app.api.v1.meta import router as meta_router
from app.api.v1.open_channel import router as open_channel_router  # P6-3 Task 32
from app.api.v1.pipe import router as pipe_router
from app.api.v1.pipe_classes import router as pipe_classes_router
from app.api.v1.pipe_codes import router as pipe_codes_router
from app.api.v1.pipe_net import router as pipe_net_router
from app.api.v1.psv import router as psv_router  # P5-3-6
from app.api.v1.psv_standard_profiles import router as psv_standard_profiles_router  # P5-3-6
from app.api.v1.psychro import router as psychro_router  # P6-2 Task 26
from app.api.v1.pump import router as pump_router
from app.api.v1.records import router as records_router
from app.api.v1.restriction import router as restriction_router  # P6-1 Task 14
from app.api.v1.sep_equip import router as sep_equip_router  # P5-2-4
from app.api.v1.sim_imports_query import project_router as sim_imports_query_router
from app.api.v1.sim_imports_query import router as sim_imports_query_root_router
from app.api.v1.stream_symbols import router as stream_symbols_router
from app.api.v1.streams import router as streams_router
from app.api.v1.thermosiphon import router as thermosiphon_router  # P5-0-1b T1
from app.api.v1.util import router as util_router  # P7-Sprint 1 S1-5b
from app.api.v1.vessel import router as vessel_router  # P5-1-4
from app.api.v1.workspaces import router as workspaces_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(workspaces_router)
api_router.include_router(checklist_router)
api_router.include_router(records_router)
api_router.include_router(lineage_router)
api_router.include_router(meta_router)
api_router.include_router(change_impact_router)
api_router.include_router(config_router)
api_router.include_router(pipe_classes_router)
api_router.include_router(pipe_router)
api_router.include_router(pipe_net_router)
api_router.include_router(pump_router)
api_router.include_router(stream_symbols_router)
api_router.include_router(streams_router)
api_router.include_router(equip_lib_router)
api_router.include_router(equip_list_router)  # P7-Sprint 1 S1-4b
api_router.include_router(flash_router)
api_router.include_router(flare_router)  # P6-2 Task 20
api_router.include_router(cool_tower_router)  # P6-2 Task 25
api_router.include_router(psychro_router)  # P6-2 Task 26
api_router.include_router(vessel_router)  # P5-1-4
api_router.include_router(sep_equip_router)  # P5-2-4
api_router.include_router(psv_router)  # P5-3-6
api_router.include_router(psv_standard_profiles_router)  # P5-3-6
api_router.include_router(heat_router)  # P5-4-5
api_router.include_router(cv_router)  # P6-1 Task 10
api_router.include_router(restriction_router)  # P6-1 Task 14
api_router.include_router(thermosiphon_router)  # P5-0-1b T1
api_router.include_router(util_router)  # P7-Sprint 1 S1-5b
api_router.include_router(open_channel_router)  # P6-3 Task 32
api_router.include_router(filtration_router)  # P6-3 Task 34
api_router.include_router(cost_est_router)  # P6-3 Task 36
api_router.include_router(pipe_codes_router)
api_router.include_router(common_router)
api_router.include_router(imports_router)
api_router.include_router(sim_imports_query_router)
api_router.include_router(sim_imports_query_root_router)