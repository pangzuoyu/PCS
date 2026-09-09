"""P3.x SIM-23: DataLineage 反向查询服务（spec §2 引用追踪 + E-3）。

给定 record_type + record_id，查询所有 source_ref_type=record_type AND
source_ref_id=record_id 的 lineage 行（"谁引用了我"），输出：
    {
        reference_count: int,
        references: list[dict] (each 含 lineage_id/source/source_ref_type/
                                source_ref_id/actor_user_id/occurred_at),
        in_use: bool (= reference_count > 0)
    }

与 LineageTracker.downstream 的区别（spec §2）：
- downstream：沿 parent_lineage_id 链递归查子节点（树形）
- SIM-23：扁平反查 source_ref（直接 FK 命中）

下游：SIM-35 PC-C04 被引用后不可删除（用 in_use 判断）。
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.system import DataLineage


class DataLineageQueryService:
    """DataLineage 反向查询（spec §2）。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def find_references(
        self, *, record_type: str, record_id: uuid.UUID
    ) -> dict:
        """查询所有引用 record_type/record_id 的 lineage 行。

        Returns:
            dict: {
                    reference_count: int,
                    references: list[dict],
                    in_use: bool,
                }
        """
        stmt = (
            select(DataLineage)
            .where(DataLineage.source_ref_type == record_type)
            .where(DataLineage.source_ref_id == record_id)
            .order_by(DataLineage.occurred_at.desc())
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        references = [
            {
                "lineage_id": r.lineage_id,
                "source": r.source,
                "source_ref_type": r.source_ref_type,
                "source_ref_id": r.source_ref_id,
                "actor_user_id": r.actor_user_id,
                "occurred_at": r.occurred_at,
            }
            for r in rows
        ]
        reference_count = len(references)
        return {
            "reference_count": reference_count,
            "references": references,
            "in_use": reference_count > 0,
        }