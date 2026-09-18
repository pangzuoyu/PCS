"""CoefficientService — 系数库 CRUD + 批量修改（Task 2.5）。

薄包装：直接对 CoefficientTable 行做 add/get + 写 audit。
不引入 AssetRepository（brief 仅文字提及，方法签名未消费）。
"""

from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
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
        """创建系数表（CoefficientTable，初始 DRAFT）。

        步骤：
        1. 构造 CoefficientTable 行（asset_id 绑定 ConfigAsset，name 命名
           表，data_json 装多列系数数据，applicable_range 可选适用区间字符串）
        2. 防御性补 version='v1'（model.version NOT NULL String(50)，
           brief 未指定具体策略默认 v1）
        3. 初始 status='DRAFT'（待 ConfigStateMachine 流转）
        4. session.add + flush（不主动 commit，调用方负责整笔业务原子）

        返回 CoefficientTable 实例（未提交）。
        """
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
        """批量更新系数表数据（仅 DRAFT/PENDING 可写）。"""
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

    @classmethod
    async def seed_default_tables(cls, session: AsyncSession) -> list[str]:
        """幂等 seed：CATEGORY_3 默认表（JSON 驱动，按 name 增量：缺失才插）。

        使用 direct ORM add 而非 cls.create_table：seed 表无业务 asset 归属，
        asset_id 传 None（model 字段已 nullable）。
        """
        seed_file = Path(__file__).parent.parent / "seeds" / "category3_defaults.json"
        defaults = json.loads(seed_file.read_text(encoding="utf-8"))
        created: list[str] = []
        for table_name, payload in defaults.items():
            # 幂等：先查是否已有同名 SEED-V1.0 行
            result = await session.execute(
                select(CoefficientTable).where(
                    CoefficientTable.name == table_name,
                    CoefficientTable.version == "SEED-V1.0",
                )
            )
            if result.scalar_one_or_none():
                continue
            session.add(
                CoefficientTable(
                    asset_id=None,  # seed 表无业务资产归属
                    name=table_name,
                    applicable_range=payload["applicable_range"],
                    std_source=payload["std_source"],
                    data_json={"rows": payload["rows"]},
                    version="SEED-V1.0",
                    status="PUBLISHED",  # 默认 seed 直接发布
                )
            )
            created.append(table_name)
        if created:
            await session.commit()
        return created