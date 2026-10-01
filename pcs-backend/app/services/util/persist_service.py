"""S1-5b UTIL persist service。

Per R5 ruling 补 API 层；summary_service (S1-5) 是 read-only 聚合，本文件是
写入 + 列表查询 helper：
- save_util_results: INSERT UtilResults + 返回 record
- aggregate_and_save: 调 source_aggregator + save_util_results 一体化
- list_util_results: 按 project_id/workspace_id 分页查询
- get_util_result: 单条查询

设计要点：
- 不直接调 summary_service 写路径（summary_service 只读）；本文件负责写
- 写路径触发后调用方按需调 summary_service 读
"""

from __future__ import annotations

from typing import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.util import UtilResults
from app.services.util.source_aggregator import aggregate_consumption


async def save_util_results(
    db: AsyncSession,
    *,
    project_id: UUID,
    workspace_id: UUID,
    consumption_json: dict,
    business_date=None,
    source: str | None = None,
) -> UtilResults:
    """INSERT UtilResults 记录。

    Args:
        db: AsyncSession
        project_id / workspace_id: 必填
        consumption_json: 13 类 flat map
        business_date: 可选（折标煤按年查询用）
        source: 数据来源描述

    Returns:
        新创建的 UtilResults 记录（已 commit + refresh）
    """
    record = UtilResults(
        project_id=project_id,
        workspace_id=workspace_id,
        business_date=business_date,
        consumption_json=consumption_json,
        source=source,
        jsonb_deprecated=False,  # Sprint 1 JSONB 权威
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


async def aggregate_and_save(
    db: AsyncSession,
    *,
    project_id: UUID,
    workspace_id: UUID,
    modules: list[str] | None = None,
    business_date=None,
    source: str | None = "source_aggregator",
) -> UtilResults:
    """调 source_aggregator 聚合 PUMP/HEAT/COOL_TOWER/OPEN_CHANNEL → 13 类 → INSERT UtilResults。

    Args:
        db: AsyncSession
        project_id / workspace_id: 必填
        modules: 要聚合的 SourceModule；默认全部 4 个
        business_date: 可选
        source: 数据来源描述（默认 'source_aggregator'）

    Returns:
        新创建的 UtilResults 记录（已 commit + refresh）
    """
    consumption = await aggregate_consumption(project_id, db, modules=modules)
    return await save_util_results(
        db,
        project_id=project_id,
        workspace_id=workspace_id,
        consumption_json=consumption,
        business_date=business_date,
        source=source,
    )


async def list_util_results(
    db: AsyncSession,
    *,
    project_id: UUID | None = None,
    workspace_id: UUID | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[Sequence[UtilResults], int]:
    """按过滤条件分页查询 UtilResults。"""
    stmt = select(UtilResults)
    count_stmt = select(func.count()).select_from(UtilResults)
    if project_id is not None:
        stmt = stmt.where(UtilResults.project_id == project_id)
        count_stmt = count_stmt.where(UtilResults.project_id == project_id)
    if workspace_id is not None:
        stmt = stmt.where(UtilResults.workspace_id == workspace_id)
        count_stmt = count_stmt.where(UtilResults.workspace_id == workspace_id)
    stmt = stmt.order_by(UtilResults.util_result_id.desc()).limit(limit).offset(offset)
    rows = (await db.execute(stmt)).scalars().all()
    total = (await db.execute(count_stmt)).scalar_one()
    return rows, int(total)


async def get_util_result(
    db: AsyncSession, util_result_id: UUID
) -> UtilResults | None:
    """单条 UtilResults 查询。"""
    return (
        await db.execute(
            select(UtilResults).where(UtilResults.util_result_id == util_result_id)
        )
    ).scalar_one_or_none()
