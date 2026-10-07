"""EquipLibService — 设备沉淀（CATEGORY_6）+ 检索（Task 1.9.5）。

沉淀 = 建 CATEGORY_6 ConfigAsset（content_json 为标准化信息快照，与源项目解耦），
审批复用 /config/assets 既有 submit/approve/publish；PUBLISH 即入库生效。
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.config_domain import ConfigAsset, ConfigVersion
from app.models.enums import AuditAction
from app.schemas.equip_lib import EquipLibSettleRequest
from app.services.audit_service import AuditService


class EquipLibService:
    """设备沉淀 + 检索（CATEGORY_6 / Task 1.9.5）。

    业务：settle 将设备位号沉淀到 CATEGORY_6 ConfigAsset（标准化信息快照
    content_json，与源项目解耦）；审批复用 /config/assets 既有 submit/
    approve/publish；PUBLISH 即入库生效。
    """

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
        # 设备代号：源设备优先（源是权威，避免调用方与源各报一个导致型号错配），
        # 无源时才用入参。缺它相似度就无从匹配 —— 设备库会退化成无名台账。
        resolved_type_code = await cls._resolve_type_code(
            session, src_equip, payload.type_code
        )
        if resolved_type_code:
            standard_info["type_code"] = resolved_type_code
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
    async def _resolve_type_code(
        cls,
        session: AsyncSession,
        source_equipment_id: str | None,
        fallback: str | None,
    ) -> str | None:
        """解析设备代号：源设备的 type_code 优先，无源时才用入参。

        源是权威 —— 沉淀的是那台设备，型号应与 equipment_list 一致；
        允许调用方与源各报一个会让库里的型号错配，相似度也就无从谈起。
        源不存在（可能已被删）或查不到 type_code 时退回入参。
        """
        if source_equipment_id:
            try:
                eq_uuid = UUID(str(source_equipment_id))
            except ValueError:
                eq_uuid = None
            if eq_uuid is not None:
                from app.models.equipment import EquipmentList

                found = await session.get(EquipmentList, eq_uuid)
                if found is not None and found.type_code:
                    return found.type_code
        return fallback

    @classmethod
    async def search(
        cls, session: AsyncSession, *, keyword: str | None = None,
        equipment_type: str | None = None, limit: int = 50,
        reference: dict[str, Any] | None = None,
    ) -> list[tuple[ConfigAsset, Any | None]]:
        """检索设备库（仅 PUBLISHED）。

        步骤：
        1. 固定过滤：CATEGORY_6（设备库分类） + status == PUBLISHED
           （DRAFT/pending 走 /config/assets 审批后可见）
        2. 可选 keyword：name ILIKE %kw% 模糊匹配
        3. 可选 equipment_type：content_json['equipment_type'] 精确匹配
           （PG JSONB ->> 字符串提取）
        4. limit 上限 200（min(limit, 200) 防止前端误传）
        5. 可选 reference（UI-SPEC §7.16 相似度参照物）：逐条算相似度，
           **按相似度降序排** —— 归并后操作员要先看到最像的那条。
           无 reference 时全部返回 None（无参照可比，不是 0 分）。

        返回 (asset, SimilarityResult | None) 列表。
        """
        stmt = select(ConfigAsset).where(
            ConfigAsset.category == "CATEGORY_6", ConfigAsset.status == "PUBLISHED"
        )
        if keyword:
            stmt = stmt.where(ConfigAsset.name.ilike(f"%{keyword}%"))
        if equipment_type:
            stmt = stmt.where(
                ConfigAsset.content_json["equipment_type"].as_string() == equipment_type
            )
        rows = list((await session.execute(stmt.limit(min(limit, 200)))).scalars())
        if reference is None:
            return [(a, None) for a in rows]
        from app.services.equip_lib_similarity import (
            compute_similarity,
            flatten_standard_info,
        )

        scored = [
            (a, compute_similarity(reference, flatten_standard_info(a.content_json)))
            for a in rows
        ]
        scored.sort(key=lambda pair: pair[1].score, reverse=True)
        return scored
