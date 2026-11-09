"""Lineage API（Sprint 3）。

3 端点：
- GET /lineage/{record_type}/{record_id}/upstream
- GET /lineage/{record_type}/{record_id}/downstream
- GET /lineage/{record_type}/{record_id}/graph（upstream + downstream 完整图）

P7-7+ BLOCKER-3 IDOR 防护: actor 必须有 record.project_id 访问权
(读血缘也算访问数据; 防止恶意用户跨 project 探测血缘拓扑)
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.config import _Actor, current_actor
from app.db.session import get_db
from app.models.calc import PipingResult
from app.models.project import Stream
from app.services.lineage import LineageTracker
from app.services.user_project_service import has_project_access

router = APIRouter(prefix="/lineage", tags=["lineage"])


#: 需要项目守卫的记录类型 → (ORM 模型, 主键列名)。
#:
#: ⚠️ **必须带主键列名** —— `PipingResult` 的主键是 `pipe_id`、`Stream` 的是
#: `stream_id` ⇒ 一个 `record_id` 要按类型映射到不同的列。
#:
#: ⚠️ **只有带 `project_id` 的模型才能登记** ⇒ 登记一个没有项目归属的模型
#: ⇒ 守卫拿不到项目 ⇒ `record.project_id` 会炸（fail-loud，而不是静默放行）。
LINEAGE_GUARDED_RECORD_TYPES: dict[str, tuple[type, str]] = {
    "PipingResult": (PipingResult, "pipe_id"),
    "streams": (Stream, "stream_id"),
}


@router.get("/{record_type}/{record_id}/upstream", response_model=list[dict])
async def upstream(
    record_type: str,
    record_id: uuid.UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    max_depth: int = Query(10, ge=1, le=50),
    session: AsyncSession = Depends(get_db),
):
    """GET 上游血缘链（沿计算记录向上回溯）。

    步骤：
    0. BLOCKER-3 P7-7+: actor 必须有 record.project_id 访问权 (读血缘也算访问数据)
    1. LineageTracker.upstream 按 record_type + record_id 直接递归回溯
       （不走 latest()，因为上游追溯用最近一次就行）
    2. max_depth 限 1..50（防止极深递归触发 N+1 风暴）
    3. 返回 [dict, ...]（按 _serialize 统一字段：record_type/record_id/
       lineage_id/relation/depth）

    与 downstream 区别：upstream 直接按 (record_type, record_id) 递归；
    downstream 需 latest() 解析（跨多次重算取最近一次）。
    """
    await _guard_record_access(
        session, user, record_type, record_id
    )
    tracker = LineageTracker(session)
    chain = await tracker.upstream(
        record_type=record_type, record_id=record_id, max_depth=max_depth
    )
    return [_serialize(c) for c in chain]


@router.get("/{record_type}/{record_id}/downstream", response_model=list[dict])
async def downstream(
    record_type: str,
    record_id: uuid.UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    max_depth: int = Query(10, ge=1, le=50),
    session: AsyncSession = Depends(get_db),
):
    """GET 下游血缘链（沿计算记录向下传播）。

    步骤：
    1. LineageTracker.latest 取 record_type+record_id 当前最新 lineage_id
       （record 可能多次重算，latest 取最近一次）
    2. 不存在 → 404 no lineage for record
    3. LineageTracker.downstream 从 lineage_id 沿 max_depth 向下传播
       （max_depth 限 1..50，防止极深递归触发 N+1 风暴）
    4. 返回 [dict, ...]（按 _serialize 统一字段：record_type/record_id/
       lineage_id/relation/depth）

    与 upstream 区别：upstream 沿 record_type+record_id 直接递归；
    downstream 需 latest() 解析到 lineage_id 再传，跨多次重算。
    """
    await _guard_record_access(
        session, user, record_type, record_id
    )
    tracker = LineageTracker(session)
    latest = await tracker.latest(record_type=record_type, record_id=record_id)
    if latest is None:
        raise HTTPException(404, "no lineage for record")
    chain = await tracker.downstream(lineage_id=latest.lineage_id, max_depth=max_depth)
    return [_serialize(c) for c in chain]


@router.get("/{record_type}/{record_id}/graph", response_model=dict)
async def graph(
    record_type: str,
    record_id: uuid.UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    max_depth: int = Query(10, ge=1, le=50),
    session: AsyncSession = Depends(get_db),
):
    """取记录的全谱系图（root + upstream + downstream）。

    步骤：
    0. BLOCKER-3 P7-7+: actor 必须有 record.project_id 访问权 (读血缘也算访问数据)
    1. 查最新 LineageRecord（lineage_id；不存在 → 404 no lineage for record）
    2. 上溯祖先（upstream）：从最新版本反向追踪到源头参数表
    3. 下溯派生（downstream）：从当前 lineage_id 出发追到所有派生版本
       （多版本分支以链式 children 形式返回）
    4. 返回 dict { root, upstream, downstream }，每项均经 _serialize 转 dict

    参数 max_depth 限制上下游遍历深度（1-50，默认 10，防爆栈）。
    """
    await _guard_record_access(
        session, user, record_type, record_id
    )
    tracker = LineageTracker(session)
    latest = await tracker.latest(record_type=record_type, record_id=record_id)
    if latest is None:
        raise HTTPException(404, "no lineage for record")
    up = await tracker.upstream(
        record_type=record_type, record_id=record_id, max_depth=max_depth
    )
    down = await tracker.downstream(lineage_id=latest.lineage_id, max_depth=max_depth)
    return {
        "root": _serialize(latest),
        "upstream": [_serialize(c) for c in up],
        "downstream": [_serialize(c) for c in down],
    }


def _serialize(lineage) -> dict:
    """DataLineage ORM 行 → API dict（UUID 字符串化 + parent/source_ref 字段 nullable 兼容）。"""
    return {
        "lineage_id": str(lineage.lineage_id),
        "record_type": lineage.record_type,
        "record_id": str(lineage.record_id),
        "parent_lineage_id": (
            str(lineage.parent_lineage_id) if lineage.parent_lineage_id else None
        ),
        "source": lineage.source,
        "source_ref_type": lineage.source_ref_type,
        "source_ref_id": str(lineage.source_ref_id) if lineage.source_ref_id else None,
        "actor_user_id": str(lineage.actor_user_id) if lineage.actor_user_id else None,
        "change_summary": lineage.change_summary,
        "occurred_at": lineage.occurred_at.isoformat() if lineage.occurred_at else None,
    }


async def _guard_record_access(
    session: AsyncSession,
    user: _Actor,
    record_type: str,
    record_id: uuid.UUID,
) -> None:
    """P7-7+ BLOCKER-3：按**记录类型注册表**拉 record 拿 project_id，验证访问权。

    ⚠️ **以前这里是 `if record_type != "PipingResult": return`** ⇒ 任何其它记录
    类型（`streams` …）**完全跳过**访问校验（TODO-114）⇒ 跨项目用户能读别人
    物流的血缘图。⇒ 改成**注册表** ⇒ 加一种记录类型只要**登记一行**，不会再漏。

    ⚠️ **不在注册表里的记录类型 ⇒ 跳过**（沿用旧行为）⇒ 但**新增记录类型必须
    登记**，否则又是同一个洞。

    ## ⚠️ 无权 ⇒ 与「不存在」**同形**（不是 "Project not found"）

    跨项目 ⇒ 抛**与「无血缘」完全相同**的 404（`no lineage for record`）。

    为什么不用 `check_record_access_or_404` 的 `"Project not found: …"`：
    那个 message 与「这条记录不存在 ⇒ no lineage for record」**不同** ⇒
    攻击者能靠响应差异**枚举出某个 UUID 是否存在**。
    ⇒ ⚠️ 在本守卫**存在之前**，`record_type='streams'` 是**整个跳过**的 ⇒
    跨项目与不存在**都**是 `no lineage for record` ⇒ **不可枚举**；
    ⇒ 若这里改抛 `"Project not found"` ⇒ **反而引入**了枚举向量 ⇒ 守住它。
    """
    entry = LINEAGE_GUARDED_RECORD_TYPES.get(record_type)
    if entry is None:
        return  # 未登记的类型 ⇒ 跳过（旧行为）
    model, pk_col = entry

    record = (
        await session.execute(
            select(model).where(getattr(model, pk_col) == record_id)
        )
    ).scalar_one_or_none()
    if record is None:
        return  # 不存在 → 让 lineage endpoint 自然 404（与「无权」同形）

    if not await has_project_access(
        session,
        user_id=user.user_id,
        project_id=record.project_id,
        actor_roles=user.roles,
    ):
        # ⚠️ **与「无血缘」逐字同形** —— 不是 403、也不是别的 code。
        raise HTTPException(404, "no lineage for record")