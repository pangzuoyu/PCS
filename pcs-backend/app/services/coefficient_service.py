"""CoefficientService — 系数库 CRUD + 批量修改（Task 2.5）。

薄包装：直接对 CoefficientTable 行做 add/get + 写 audit。
不引入 AssetRepository（brief 仅文字提及，方法签名未消费）。
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.config_domain import CoefficientTable
from app.models.enums import AuditAction
from app.services.audit_service import AuditService


class CoefficientNotFoundError(Exception):
    """查不到指定 CoefficientTable 时抛出。"""


class CoefficientService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.audit = AuditService(session)

    async def create_table(
        self,
        *,
        asset_id: UUID,
        name: str,
        data_json: dict,
        applicable_range: str | None = None,
    ) -> CoefficientTable:
        table = CoefficientTable(
            asset_id=asset_id,
            name=name,
            data_json=data_json,
            applicable_range=applicable_range,
            version="v1",  # 防御性：model.version NOT NULL String(50) — brief 未指定
            status="DRAFT",
        )
        self.session.add(table)
        await self.session.flush()
        return table

    async def bulk_update(
        self, table_id: UUID, data_json: dict, *, actor: UUID
    ) -> CoefficientTable:
        table = await self.session.get(CoefficientTable, table_id)
        if table is None:
            raise CoefficientNotFoundError(f"未找到 table_id={table_id}")
        table.data_json = data_json
        await self.session.flush()
        await self.audit.write(
            user_id=actor,
            action=AuditAction.CONFIG_VERSION_CREATED,
            resource_type="coefficient_table",
            resource_id=str(table_id),
        )
        return table

    async def query(self, table_id: UUID) -> CoefficientTable:
        table = await self.session.get(CoefficientTable, table_id)
        if table is None:
            raise CoefficientNotFoundError(f"未找到 table_id={table_id}")
        return table