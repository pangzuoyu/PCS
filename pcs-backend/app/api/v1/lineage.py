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
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.config import _Actor, current_actor, require_roles
from app.db.session import get_db
from app.models.project import Stream
from app.schemas.lineage import LineageGraphResponse, LineageNode
from app.services.lineage import LineageTracker
from app.services.lineage_registry import LINEAGE_GUARDED_RECORD_TYPES
from app.services.user_project_service import has_project_access

router = APIRouter(prefix="/lineage", tags=["lineage"])


#: 需要项目守卫的记录类型 → (ORM 模型, 主键列名)。
#:
#: ⚠️ **派生**自 `RECORD_TYPE_REGISTRY`（见 `app/services/lineage_registry.py`）
#: ⇒ **不要在这里手抄第二份** ⇒ 键 = `model.__name__`（写入方写进
#: `data_lineage.record_type` 的就是类名）。
#:
#: ⚠️ **只有带 `project_id` 的模型才能登记** ⇒ 登记一个没有项目归属的模型
#: ⇒ 守卫拿不到项目 ⇒ `record.project_id` 会炸（fail-loud，而不是静默放行）。
#:
#: ⚠️ **未登记的类型 ⇒ 404**（fail-closed）—— 守卫见下。



@router.get("/{record_type}/{record_id}/upstream", response_model=list[LineageNode])
async def upstream(
    record_type: str,
    record_id: uuid.UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    max_depth: int = Query(10, ge=1, le=50),
    session: AsyncSession = Depends(get_db),
):
    """GET 上游血缘链（沿计算记录向上回溯）。

    步骤：
    0. **角色门**（P9B-4 评审 #3 · 用户 2026-11-12 裁决「沿用 streams 白名单」）
       —— 与 `app/api/v1/streams.py` 的每个端点**同一条**白名单
       （DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN）⇒ 否则 VIEWER /
       REVIEWER / CHECKER 从 `GET /streams/{id}` 拿 403、却能从血缘端点读到
       物流自己的字段与下游计算血缘行。
       ⚠️ **角色门在项目守卫之前**（与 `streams.py` 的既有顺序一致）：
       角色判定**不看 id** ⇒ 任何 id 都得同一个 403 ⇒ 不泄漏存在性；
       反过来（先查项目）则 403 会泄漏「这个 id 在你有权限的项目里」。
    0a. BLOCKER-3 P7-7+: actor 必须有 record.project_id 访问权 (读血缘也算访问数据)
    0b. **记录不存在 ⇒ 404**（`no lineage for record`）—— 与「无权」**逐字同形**
        ⇒ 枚举不出某个 UUID 是否存在（bug-2147；`/graph` 与 `/downstream`
        本来就是这个形状，只有本端点原先漏了）
    1. LineageTracker.upstream 按 record_type + record_id 直接递归回溯
       （不走 latest()，因为上游追溯用最近一次就行）
    2. max_depth 限 1..50（防止极深递归触发 N+1 风暴）
    3. 返回 `list[LineageNode]`（**具名 schema** · P9B-4 评审 #4 ⇒ 与
       `/graph` 的 `downstream` / `upstream` **逐字同形** —— 同一行不再
       有「`Z` 与 `+00:00` 两种时间戳字符串」）

    与 downstream 区别：upstream 直接按 (record_type, record_id) 递归；
    downstream 需 latest() 解析（跨多次重算取最近一次）。
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    await _guard_record_access(
        session, user, record_type, record_id
    )
    if record_type == "streams":
        # ⚠️ 物流是**源** ⇒ **没有**上游血缘行 ⇒ 200 + []
        #    （不是「查不到」的 404 —— 「没有」与「查不到」是两件事）
        return []
    tracker = LineageTracker(session)
    chain = await tracker.upstream(
        record_type=record_type, record_id=record_id, max_depth=max_depth
    )
    return [_serialize(c) for c in chain]


@router.get("/{record_type}/{record_id}/downstream", response_model=list[LineageNode])
async def downstream(
    record_type: str,
    record_id: uuid.UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    max_depth: int = Query(10, ge=1, le=50),
    session: AsyncSession = Depends(get_db),
):
    """GET 下游血缘链（沿计算记录向下传播）。

    步骤：
    0. **角色门**（P9B-4 评审 #3）—— 与 `streams.py` 同一条白名单
       （DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN）；**在项目守卫之前**
       （角色判定不看 id ⇒ 不泄漏存在性）。
    0a. BLOCKER-3 P7-7+: actor 必须有 record.project_id 访问权
    0b. **记录不存在 / 未登记类型 ⇒ 同一个 404**（守卫抛，见 `_guard_record_access`）
    1. LineageTracker.latest 取 record_type+record_id 当前最新 lineage_id
       （record 可能多次重算，latest 取最近一次）
    2. 不存在 → 404 no lineage for record
    3. LineageTracker.downstream 从 lineage_id 沿 max_depth 向下传播
       （max_depth 限 1..50，防止极深递归触发 N+1 风暴）
    4. 返回 `list[LineageNode]`（**具名 schema** · P9B-4 评审 #4 ⇒ 与
       `/graph` 的 `downstream` **逐字同形**，不再有「`Z` 与 `+00:00` 两种
       时间戳字符串」）

    与 upstream 区别：upstream 沿 record_type+record_id 直接递归；
    downstream 需 latest() 解析到 lineage_id 再传，跨多次重算。

    ⚠️ `record_type='streams'` ⇒ 物流的「下游」= **以它为源**的血缘行
    （`finalize_calc_record` 写的正是 `source_ref_type='Stream'`）。

    ⚠️ **`streams` 入口下 `max_depth` 是「下游条数上限」**（1..50，默认 10）
    —— 本入口**没有遍历可限** ⇒ 用它当条数上限 ⇒ `data_lineage` 只增不删
    ⇒ 不限则响应随重算次数**无界增长**。**最新的在前**（`occurred_at DESC`）。
    ⚠️ 与 `/graph` **同口径**（否则两个端点对同一份数据给出不同的上限 ⇒
    「两个端点互相打脸」）。
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    await _guard_record_access(
        session, user, record_type, record_id
    )
    if record_type == "streams":
        tracker = LineageTracker(session)
        rows = await tracker.by_source_ref(
            source_ref_type="Stream", source_ref_id=record_id, limit=max_depth
        )
        return [_serialize(c) for c in rows]
    tracker = LineageTracker(session)
    latest = await tracker.latest(record_type=record_type, record_id=record_id)
    if latest is None:
        raise HTTPException(404, "no lineage for record")
    chain = await tracker.downstream(lineage_id=latest.lineage_id, max_depth=max_depth)
    return [_serialize(c) for c in chain]


@router.get("/{record_type}/{record_id}/graph", response_model=LineageGraphResponse)
async def graph(
    record_type: str,
    record_id: uuid.UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    max_depth: int = Query(10, ge=1, le=50),
    session: AsyncSession = Depends(get_db),
):
    """取记录的全谱系图（root + upstream + downstream）。

    步骤：
    0. **角色门**（P9B-4 评审 #3）—— 与 `streams.py` 同一条白名单
       （DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN）；**在项目守卫之前**
       （角色判定不看 id ⇒ 不泄漏存在性）。
    0a. BLOCKER-3 P7-7+: actor 必须有 record.project_id 访问权 (读血缘也算访问数据)
    0b. **记录不存在 / 未登记类型 ⇒ 同一个 404**（守卫抛，见 `_guard_record_access`）
    1. 查最新 LineageRecord（lineage_id；不存在 → 404 no lineage for record）
    2. 上溯祖先（upstream）：从最新版本反向追踪到源头参数表
    3. 下溯派生（downstream）：从当前 lineage_id 出发追到所有派生版本
       （多版本分支以链式 children 形式返回）
    4. 返回 `LineageGraphResponse` { root, upstream, downstream }，
       三项**共用同一个 `LineageNode` 具名 schema**（评审 #4）⇒ 与
       `/upstream` / `/downstream` **逐字同形**

    参数 max_depth 限制上下游遍历深度（1-50，默认 10，防爆栈）。

    ⚠️ **`record_type='streams'` 走「按源引用查」**（P9B-4 T0-D · TODO-136）：
    物流在血缘行里**从不作为 `record_type`** 存在（它是 `source_ref_type='Stream'`
    的**源引用**）⇒ 走 `record_type` 那条路**永远查不到行** ⇒ root 是**合成**的
    （`data_lineage` 表里**没有**这一行）。

    ⚠️ **`streams` 入口下 `max_depth` 是「下游条数上限」**（1..50，默认 10）
    —— 本入口**没有遍历可限** ⇒ 用它当条数上限 ⇒ `data_lineage` 只增不删
    ⇒ 不限则响应随重算次数**无界增长**。**最新的在前**（`occurred_at DESC`）。
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    stream = await _guard_record_access(
        session, user, record_type, record_id
    )
    if record_type == "streams":
        # ⚠️ **守卫已经查过并放行** ⇒ 直接用它的返回值（评审 #15）⇒
        #    不必再 `session.get` 一次（少一次查询），也不必在这里
        #    重复判「不存在」（那条分支守卫已经抛了同一个 404）。
        return await _stream_graph(session, stream, max_depth=max_depth)
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
) -> Any:
    """P7-7+ BLOCKER-3：按**记录类型注册表**拉 record 拿 project_id，验证访问权。

    ⚠️ **以前这里是 `if record_type != "PipingResult": return`** ⇒ 任何其它记录
    类型（`streams` …）**完全跳过**访问校验（TODO-114）⇒ 跨项目用户能读别人
    物流的血缘图。⇒ 改成**注册表** ⇒ 加一种记录类型只要**登记一行**，不会再漏。

    ⚠️ **不在注册表里的记录类型 ⇒ 404**（fail-closed，P9B-4 T0-D）——
    此前是「跳过」（沿用旧行为）⇒ 端点落到自己的兜底：`/graph` 与 `/downstream`
    恰好 404，但 `/upstream` 返 **200 + []** ⇒ 「未登记类型」成了一个**可枚举
    信号**（与「无权」可区分）⇒ 改成**同一个 404**（fail-closed）。

    ## ⚠️ 无权 ⇒ 与「不存在」**同形**（不是 "Project not found"）

    跨项目 ⇒ 抛**与「无血缘」完全相同**的 404（`no lineage for record`）。

    为什么不用 `check_record_access_or_404` 的 `"Project not found: …"`：
    那个 message 与「这条记录不存在 ⇒ no lineage for record」**不同** ⇒
    攻击者能靠响应差异**枚举出某个 UUID 是否存在**。
    ⇒ ⚠️ 在本守卫**存在之前**，`record_type='streams'` 是**整个跳过**的 ⇒
    跨项目与不存在**都**是 `no lineage for record` ⇒ **不可枚举**；
    ⇒ 若这里改抛 `"Project not found"` ⇒ **反而引入**了枚举向量 ⇒ 守住它。

    ## ⚠️⚠️ 「记录不存在」**也**抛同一个 404（bug-2147）

    原来这里 `return`（注释写「让 endpoint 自然 404」）⇒ **端点各有各的兜底**：

    - `/graph`、`/downstream`：`tracker.latest()` 为 None ⇒ 抛 404 ⇒ 恰好同形
    - `/upstream`：`tracker.upstream()` **不抛**，返回 **200 + []** ⇒
      **与跨项目的 404 可区分** ⇒ 「这个 UUID 存在但不属于我」vs
      「这个 UUID 根本不存在」⇒ **UUID 枚举向量**（本守卫要关的正是它）。

    ⇒ 守卫**自己**抛同一个 404 ⇒ 三条路径**逐字同形**，与端点各自的兜底无关。

    ## 返回值

    返回查到的**记录行**（调用方要拿它的字段时不必再查一次）。
    """
    entry = LINEAGE_GUARDED_RECORD_TYPES.get(record_type)
    if entry is None:
        # ⚠️ **未登记的类型 ⇒ 404**（fail-closed）—— 与「记录不存在」**逐字同形**
        #    ⇒ 「这个类型不被支持」不能成为一个可枚举信号。
        raise HTTPException(404, "no lineage for record")
    model, pk_col = entry

    record = (
        await session.execute(
            select(model).where(getattr(model, pk_col) == record_id)
        )
    ).scalar_one_or_none()
    if record is None:
        # ⚠️ **不存在 ⇒ 与「无权」同一个 404**（不是 `return`）。
        #    `return` 会让端点落到自己的兜底 ⇒ `/upstream` 返 200 + [] ⇒
        #    与跨项目的 404 **可区分** ⇒ 枚举向量（bug-2147）。
        raise HTTPException(404, "no lineage for record")

    if not await has_project_access(
        session,
        user_id=user.user_id,
        project_id=record.project_id,
        actor_roles=user.roles,
    ):
        # ⚠️ **与「无血缘」逐字同形** —— 不是 403、也不是别的 code。
        raise HTTPException(404, "no lineage for record")
    return record


async def _stream_graph(
    session: AsyncSession, stream: Stream, *, max_depth: int
) -> dict:
    """物流的血缘图 —— **「按源引用查」** + **合成 root**（T0-D · TODO-136）。

    ⚠️ **物流在血缘行里从不作为 `record_type`**（它是 `source_ref_type='Stream'`
    的**源引用**）⇒ 走 `record_type` 那条路**永远查不到行** ⇒

    - **downstream** = 以该物流为**源**的血缘行；
    - **upstream** = **空**（物流是源 ⇒ 没有上游血缘行）；
    - **root** = **合成**（下面 `_synthetic_stream_root`）。

    ⚠️ **`stream` 由调用方的守卫传入**（P9B-4 评审 #15）—— 守卫已经查过
    该行并放行 ⇒ 这里**不必再查一次**（省一次 `SELECT`）⇒ 也就不必再判
    「不存在」（那条分支守卫已经抛了**同一个** 404）。
    """
    tracker = LineageTracker(session)
    # ⚠️ `max_depth` 在本入口**没有遍历可限** ⇒ 用作**下游条数上限**
    #    （1..50，默认 10）⇒ `data_lineage` 只增不删 ⇒ 不限则响应无界增长。
    rows = await tracker.by_source_ref(
        source_ref_type="Stream", source_ref_id=stream.stream_id, limit=max_depth
    )
    return {
        "root": _synthetic_stream_root(stream),
        "upstream": [],
        "downstream": [_serialize(c) for c in rows],
    }


def _synthetic_stream_root(stream: Stream) -> dict:
    """合成 root —— 形状与真实 root **完全相同**（10 个字段）。

    ⚠️ **这是合成的**：`data_lineage` 表里**没有**这一行 ⇒
    - `lineage_id` = **确定性** uuid5（否则前端 `rowKey` 每次变）
      ⇒ 约定：`uuid5(NAMESPACE_DNS, f"lineage-root:streams:{stream_id}")`；
    - `source` = **物流来源**（录入通道 4 值：怎么进系统的）
      ⇒ ⚠️ 与血缘行的 `source`（**计算来源** `CALC` 等）**是两套词表**；
    - `source_ref_*` = `None`（物流**就是**源 ⇒ 没有上游引用）。
    """
    return {
        "lineage_id": str(
            uuid.uuid5(
                uuid.NAMESPACE_DNS, f"lineage-root:streams:{stream.stream_id}"
            )
        ),
        "record_type": "streams",
        "record_id": str(stream.stream_id),
        "parent_lineage_id": None,
        "source": stream.source,
        "source_ref_type": None,
        "source_ref_id": None,
        "actor_user_id": str(stream.created_by) if stream.created_by else None,
        "change_summary": "物流本身（合成根节点）",
        "occurred_at": stream.created_at.isoformat() if stream.created_at else None,
    }