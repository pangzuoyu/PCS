"""EquipLibService — 设备沉淀（CATEGORY_6）+ 检索（Task 1.9.5）。

沉淀 = 建 CATEGORY_6 ConfigAsset（content_json 为标准化信息快照，与源项目解耦），
审批复用 /config/assets 既有 submit/approve/publish；PUBLISH 即入库生效。
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.config_domain import ConfigAsset, ConfigVersion
from app.models.enums import AuditAction
from app.schemas.equip_lib import EquipLibSettleRequest
from app.services.audit_service import AuditService


class EquipLibService:
    @classmethod
    async def settle(
        cls,
        session: AsyncSession,
        *,
        payload: EquipLibSettleRequest,
        source_equipment_id: str | None = None,
        source_project_id: str | None = None,
        created_by: UUID | None = None,
    ) -> ConfigAsset:
        """将设备位号沉淀到 CATEGORY_6 设备库（标准化信息快照，与源项目解耦）。

        步骤：
        1. 显式入参优先于 payload 内嵌字段（同一语义两入口）
        2. 创建 ConfigAsset（CATEGORY_6 / DRAFT / settle-v1）
           - name = "{equipment_name} [{original_tag}]"（String(200) 截断）
           - content_json = {equipment_type, standard_info}
        3. 同步创建 ConfigVersion 行（DRAFT，与 config_service 创建 asset 同款两步）
        4. 写 Audit（CONFIG_ASSET_CREATED，detail 含 settle=True + source 追溯）

        提交由本函数负责（session.commit()）。
        """
        # 显式入参优先于 payload 内嵌字段（同一语义，两个入口）
        src_equip = source_equipment_id or payload.source_equipment_id
        src_proj = source_project_id or payload.source_project_id
        standard_info = payload.model_dump(exclude={"equipment_name", "equipment_type"})
        standard_info["source_equipment_id"] = src_equip
        standard_info["source_project_id"] = src_proj
        asset = ConfigAsset(
            category="CATEGORY_6",
            name=f"{payload.equipment_name} [{payload.original_tag}]"[:200],  # name 列 String(200)
            description=f"{payload.equipment_type} 沉淀快照（源位号 {payload.original_tag}）",
            current_version="settle-v1",
            status="DRAFT",
            content_json={
                "equipment_type": payload.equipment_type,
                "standard_info": standard_info,
            },
        )
        session.add(asset)
        # 沉淀版本行：与 ConfigVersion 语义对齐（config_service 创建 asset 时同款两步）
        await session.flush()
        session.add(ConfigVersion(
            asset_id=asset.asset_id, version_code="settle-v1",
            content_json=asset.content_json, status="DRAFT",
        ))
        await AuditService(session).write(
            user_id=created_by,
            action=AuditAction.CONFIG_ASSET_CREATED,
            resource_type="CONFIG",
            resource_id=str(asset.asset_id),
            detail={
                "category": "CATEGORY_6",
                "settle": True,
                "source_equipment_id": src_equip,
                "source_project_id": src_proj,
                "original_tag": payload.original_tag,
            },
        )
        await session.commit()
        return asset

    @classmethod
    async def search(
        cls, session: AsyncSession, *, keyword: str | None = None,
        equipment_type: str | None = None, limit: int = 50,
    ) -> list[ConfigAsset]:
        stmt = select(ConfigAsset).where(
            ConfigAsset.category == "CATEGORY_6", ConfigAsset.status == "PUBLISHED"
        )
        if keyword:
            stmt = stmt.where(ConfigAsset.name.ilike(f"%{keyword}%"))
        if equipment_type:
            stmt = stmt.where(
                ConfigAsset.content_json["equipment_type"].as_string() == equipment_type
            )
        return list((await session.execute(stmt.limit(min(limit, 200)))).scalars())
