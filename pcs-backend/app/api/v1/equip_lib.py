"""equip-lib 端点（Task 1.9.5 / P2-EQL-001）。

沉淀（settle）建 CATEGORY_6 ConfigAsset（DRAFT），审批复用 /config/assets 既有
submit/approve/publish 链；检索（search）仅返回 PUBLISHED。

ACL：写（settle）= PROCESS_CONTROLLER + SYSTEM_ADMIN；
读（search）= DESIGNER + PROCESS_CONTROLLER + SYSTEM_ADMIN。
`current_actor / require_roles / _Actor` 与 config.py 同源（该模块 `__all__` 导出）。
"""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.config import _Actor, current_actor, require_roles
from app.db.session import get_db
from app.schemas.config import AssetResponse
from app.schemas.equip_lib import EquipLibSettleRequest, SimilarAssetResponse
from app.services.equip_lib_service import EquipLibService

router = APIRouter(prefix="/equip-lib", tags=["equip-lib"])


@router.get("/search", response_model=list[SimilarAssetResponse])
async def search(
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
    keyword: str | None = Query(None),
    equipment_type: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    # ---- 相似度参照物（UI-SPEC §7.16）----
    # 传了就按相似度降序排，并逐条回 similarity + 档位；一个都不传则
    # similarity 全为 null（无参照可比，不是 0 分）。
    ref_type_code: str | None = Query(None, description="参照：设备代号"),
    ref_material: str | None = Query(None, description="参照：材质"),
    ref_weight_kg: float | None = Query(None, gt=0, description="参照：重量 kg"),
    ref_standard_drawing_no: str | None = Query(
        None, description="参照：标准图号"
    ),
):
    """GET 检索设备库（仅 PUBLISHED）。

    - ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
    - keyword 可选模糊匹配 name（ILIKE）
    - equipment_type 可选 JSONB ->> 精确过滤
    - limit 上限 200（防前端误传大数）
    - ref_* 任一非空即启用相似度：结果按相似度降序，逐条带
      similarity(0~1) 与 similarity_tier(RECOMMEND/VERIFY/DISPLAY_ONLY)

    档位口径见 UI-SPEC §7.16：≥90% 推荐，80~90% 需校核，<80% 仅展示。
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    reference: dict[str, Any] | None = None
    # equipment_type 是过滤条件，不进参照 —— 它作为相似度维度恒真（见
    # equip_lib_similarity 模块 docstring）
    supplied = {
        "type_code": ref_type_code,
        "material": ref_material,
        "standard_drawing_no": ref_standard_drawing_no,
        "weight_kg": ref_weight_kg,
    }
    if any(v is not None for v in supplied.values()):
        reference = {k: v for k, v in supplied.items() if v is not None}

    results = await EquipLibService.search(
        db, keyword=keyword, equipment_type=equipment_type, limit=limit,
        reference=reference,
    )
    return [
        SimilarAssetResponse(
            **AssetResponse.model_validate(asset).model_dump(),
            similarity=None if sim is None else sim.score,
            similarity_tier=None if sim is None else sim.tier,
        )
        for asset, sim in results
    ]


@router.post("/settle", response_model=AssetResponse, status_code=201)
async def settle(
    payload: EquipLibSettleRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """POST 设备库沉淀（201 Created）。

    步骤：
    1. ACL：PROCESS_CONTROLLER / SYSTEM_ADMIN（设备库写权限）
    2. 调 EquipLibService.settle：从项目设备（source_equipment_id /
       source_project_id）克隆到设备库 CATEGORY_6 ConfigAsset（DRAFT）
    3. 沉淀完成走 /config/assets 既有 submit/approve/publish 链审批；
       本端点仅做沉淀（DRAFT），不直接发布
    4. 检索（search）仅返回 PUBLISHED 状态的设备库资产

    与 search 区别：settle 是写、DRAFT 状态入库；search 是读、仅 PUBLISHED。
    """
    require_roles(user, "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    return await EquipLibService.settle(
        db,
        payload=payload,
        source_equipment_id=payload.source_equipment_id,
        source_project_id=payload.source_project_id,
        created_by=user.user_id,
    )
