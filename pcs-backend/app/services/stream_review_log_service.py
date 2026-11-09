"""读物流的「校核记录」（TODO-112 · P9B-4 紧急批次 T6）。

## ⚠️ 为什么**后端过滤**（最小暴露原则）

只返回 `SUBMIT_FOR_CHECK` / `PASS_CHECK` / `REJECT_CHECK` 三条 ⇒
前端拿到什么就显示什么 ⇒ **过滤逻辑只有一处**、可测。

（前端原来自己过滤一遍 ⇒ 两处过滤 = 两个口径 = 迟早漂移 ⇒ 本批把前端那套
删掉，改调本端点。）

## ⚠️ **不加索引**（TODO-104 的结论）

`audit_logs` 表上**已有** `ix_audit_logs_detail_json_gin`（`jsonb_path_ops`）⇒
但它只支持 `@>` / `@?` / `@@` ⇒ **`->>` 用不上它**。
而 `@>` 在**测试库 SQLite 上不可用**（`unrecognized token: "@"`）⇒
统一查询只能用 `->>` ⇒ 真要优化得**另加**表达式索引。

⇒ 加 `detail_json->>'transition'` 表达式索引是**投机性优化**（`RECORD_TRANSITION`
当前 0 行）⇒ 等生产出现性能问题、或该类行数 > 10 万再补。

⚠️ **TODO-104 的准确表述**是「**已有 GIN 索引覆盖不到本查询的写法**」，
不是「表上没索引」。

## ⚠️⚠️ **只按 `detail_json.transition` 收口，不按 `action`**（bug-2146）

原来这里还有一条 `AuditLog.action == "RECORD_TRANSITION"` ⇒ 它**冗余**，
而且正是**害死端点的那一条**：状态机给 `PASS_CHECK` / `REJECT_CHECK` 写的
是 `APPROVAL_STEP_PASSED` / `APPROVAL_STEP_REJECTED` ⇒ 两行被静默吞掉。

⇒ 去掉 `action` 谓词：
- `detail_json.transition` **已经精确**选中那三条转移（状态机**每次**转移
  都写这个字段）⇒ `action` 那一维**没有信息量**；
- 少一个依赖 ⇒ 状态机改动作名时**不会再**把端点打瞎（少一个漂移点）；
- `MARK_STALE` / `INITIATE_CHANGE` 等**自动**被 transition 白名单排除
  （它们的 `transition` 值不在白名单里）⇒ 不需要靠 `action` 区分。
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import StateTransition
from app.models.system import AuditLog
from app.schemas.stream_review_log import ReviewLogItem

#: 校对相关的状态转移（其余 transition **不显示**）。
#:
#: ⚠️ 这是**唯一**一份口径（后端过滤）⇒ 前端**不得**再过滤一遍。
#:
#: ⚠️⚠️ **词表从枚举派生，不手抄**（bug-2146）：手抄字符串当"唯一口径"，
#: 迟早与状态机漂移 —— 而且漂移过一次：手抄的 `action == "RECORD_TRANSITION"`
#: 那个过滤把 `PASS_CHECK` / `REJECT_CHECK` 两行**全吞了**（状态机给它们写的
#: 是 `APPROVAL_STEP_PASSED` / `APPROVAL_STEP_REJECTED`）⇒ 端点在生产里
#: **只能**返回「提交校对」一条，而失败是静默的（200 + 部分列表）。
REVIEW_TRANSITIONS: tuple[StateTransition, ...] = (
    StateTransition.SUBMIT_FOR_CHECK,
    StateTransition.PASS_CHECK,
    StateTransition.REJECT_CHECK,
)

#: `detail_json->>'transition'` 里存的**字符串**值（= 枚举的 `.value`）。
REVIEW_TRANSITION_VALUES: tuple[str, ...] = tuple(t.value for t in REVIEW_TRANSITIONS)


async def list_review_log(
    db: AsyncSession,
    *,
    stream_id: uuid.UUID,
) -> list[ReviewLogItem]:
    """读一条物流的校核记录（**按 `occurred_at` 升序**）。

    ⚠️ **项目守卫在端点层**（先加载物流再守卫）—— 本函数**假定**调用方
    已完成守卫 ⇒ 不要在别处直接调它。

    ⚠️ `resource_id` 是 **`String(100)`** 列（不是 UUID 列）⇒ 比较必须用
    `str(stream_id)`（写 UUID **匹配不到任何行**）。
    """
    rows = (
        await db.execute(
            select(AuditLog)
            .where(
                AuditLog.resource_type == "streams",
                AuditLog.resource_id == str(stream_id),
                AuditLog.detail_json["transition"]
                .as_string()
                .in_(REVIEW_TRANSITION_VALUES),
            )
            .order_by(AuditLog.occurred_at.asc(), AuditLog.audit_id.asc())
        )
    ).scalars().all()

    return [_to_item(row) for row in rows]


def _to_item(row: AuditLog) -> ReviewLogItem:
    """审计行 → 响应项（防御性读 `detail_json` —— 契约里它是任意 object）。"""
    detail = row.detail_json if isinstance(row.detail_json, dict) else {}
    reason = detail.get("reason")
    return ReviewLogItem(
        transition=str(detail.get("transition") or ""),
        operator=str(row.user_id) if row.user_id is not None else None,
        occurred_at=row.occurred_at.isoformat() if row.occurred_at else "",
        detail=str(reason) if reason else None,
    )
