"""ReportService — P2 Sprint 3 Task 5.1 + 5.2。

Task 5.1：按 category × status 聚合 config_versions 计数（不取 latest）：
- 每个 asset 可能有多个 version，统计按 version 算，与 brief 测试
  "按版本状态分布"语义一致。
- 用 ORM select + group_by + func.count()，跨 DB 兼容（替代 brief 的 raw
  ``text(...)``）。
- 5 个状态字段兜底为 0：未出现的状态不出现在 GROUP BY 结果中，但
  ConfigAssetReport 仍要求 5 个 count 字段齐全。

Task 5.2：按 numbering_template 聚合 doc_no_sequences 用量：
- LEFT JOIN 保留所有模板（含没有 sequence 的），HAVING SUM>0 把零计数过滤
  掉。空 DB / 全是 0 → ``[]``。
- ORM 等价 brief 的 ``COALESCE(SUM(current_value),0) HAVING SUM(...)>0``。
  注意 HAVING 用 SUM 表达式而非 aliased label，跨 SQLite/Postgres 行为一致。
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.config_domain import (
    ConfigAsset,
    ConfigVersion,
    DocNoSequence,
    NumberingTemplate,
)


class ConfigAssetReport(BaseModel):
    """按 category 聚合的 status 计数（按 version 算，不取 latest）。"""

    category: str
    draft: int = 0
    pending: int = 0
    approved: int = 0
    published: int = 0
    obsolete: int = 0


class DocNoUsage(BaseModel):
    """按 numbering_template 聚合的 doc_no_sequences 用量（current_value 求和）。"""

    template_id: uuid.UUID
    template_name: str
    total: int


class ReportService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def config_asset_status(self) -> list[ConfigAssetReport]:
        """返回按 category 字母序排列的分布报告。空 DB 返回 ``[]``。"""
        stmt = (
            select(
                ConfigAsset.category,
                ConfigVersion.status,
                func.count().label("n"),
            )
            .join(ConfigVersion, ConfigVersion.asset_id == ConfigAsset.asset_id)
            .group_by(ConfigAsset.category, ConfigVersion.status)
            .order_by(ConfigAsset.category)
        )
        rows = (await self.session.execute(stmt)).all()

        # category → {status: count}
        agg: dict[str, dict[str, int]] = {}
        for category, status, n in rows:
            agg.setdefault(category, {})[status] = int(n)

        return [
            ConfigAssetReport(
                category=category,
                draft=counts.get("DRAFT", 0),
                pending=counts.get("PENDING", 0),
                approved=counts.get("APPROVED", 0),
                published=counts.get("PUBLISHED", 0),
                obsolete=counts.get("OBSOLETE", 0),
            )
            for category, counts in sorted(agg.items())
        ]

    async def doc_no_sequence_usage(self) -> list[DocNoUsage]:
        """返回按 template_name 字母序排列的编号模板用量报告。

        LEFT JOIN 让「没有 sequence 的模板」也参与聚合（NULL → COALESCE 0），
        HAVING SUM(current_value) > 0 把零计数模板过滤掉。
        空 DB / 全是 0 → ``[]``。
        """
        total_expr = func.coalesce(func.sum(DocNoSequence.current_value), 0)
        stmt = (
            select(
                NumberingTemplate.template_id,
                NumberingTemplate.template_name,
                total_expr.label("total"),
            )
            .select_from(NumberingTemplate)
            .outerjoin(
                DocNoSequence,
                DocNoSequence.template_id == NumberingTemplate.template_id,
            )
            .group_by(NumberingTemplate.template_id, NumberingTemplate.template_name)
            .having(func.sum(DocNoSequence.current_value) > 0)
            .order_by(NumberingTemplate.template_name)
        )
        rows = (await self.session.execute(stmt)).all()
        return [
            DocNoUsage(
                template_id=tid,
                template_name=name,
                total=int(total),
            )
            for tid, name, total in rows
        ]
