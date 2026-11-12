"""AI 审计的**写库**任务（P10-A · Task T10）—— **幂等**。

## 为什么必须幂等

审计行以 `request_id`（服务端 UUID）为**唯一键** ⇒ 同一个请求写两次
只能留下一行。理由：

- ARQ 的 job **可能被重投**（手动重放 / 将来加 `Retry` 退避重试）；
- 中间件与 worker 之间的**至少一次**投递语义；
⇒ 幂等不是「锦上添花」，是「一次请求留下 N 条审计 ⇒ 审计表被灌水」的解药。

⚠️ **arq 0.28 只对 `Retry` 异常重试**（其余异常当场判死）⇒
「重试必然发生」在本仓**不成立** ⇒ 幂等仍要，但理由是「job 可能被重投 /
将来加退避重试」，不是「现在就在重试」。

## 方言差异（单测跑在内存 SQLite 上）

- **PG** ⇒ `INSERT ... ON CONFLICT (request_id) DO NOTHING`（原子）
- **SQLite**（单测库）⇒ `ON CONFLICT` **不可用** ⇒ 「先查后插」+
  `except IntegrityError` ⇒ 并发下第二个插入撞唯一约束时**不算失败**。
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.system import AiAuditLog

logger = logging.getLogger(__name__)

#: AI 预留请求的 **agent_id**（固定值）。
#: ⚠️ `ai_audit_log.agent_id` 是 **NOT NULL**（SUP-006 的既有列）⇒
#: AI 预留路径没有「agent」概念也得给一个 ⇒ 用一个**可识别的固定 UUID**
#: （`uuid5(NAMESPACE_DNS, "pcs-ai-assistant")`）⇒ 零迁移、可识别。
AI_AGENT_ID = uuid.uuid5(uuid.NAMESPACE_DNS, "pcs-ai-assistant")

#: 写进 `operation` 列的默认值（NOT NULL）。
DEFAULT_OPERATION = "AI_REQUEST"

#: 本任务负责写入的列（其余列由既有 SUP-006 语义或 DB 默认值填）。
_AUDIT_COLUMNS = (
    "request_id",
    "client_request_id",
    "endpoint",
    "status_code",
    "duration_ms",
    "sanitized_request_hash",
    "response_summary",
    "model_version",
)


def _row_values(fields: dict[str, Any]) -> dict[str, Any]:
    """把入参整理成**列 → 值**的映射（只留本表认得的列）。"""
    values: dict[str, Any] = {
        "agent_id": fields.get("agent_id") or AI_AGENT_ID,
        "operation": fields.get("operation") or DEFAULT_OPERATION,
    }
    for column in _AUDIT_COLUMNS:
        if column in fields:
            values[column] = fields[column]
    user_id = fields.get("user_id")
    if user_id is not None:
        values["user_id"] = (
            user_id if isinstance(user_id, uuid.UUID) else uuid.UUID(str(user_id))
        )
    return values


def _build_insert(values: dict[str, Any], *, is_postgres: bool):
    """构造插入语句（**方言相关**）。

    - PG ⇒ `INSERT ... ON CONFLICT (request_id) DO NOTHING`（原子幂等）
    - 其它（单测的 SQLite）⇒ ORM 实体（`ON CONFLICT` 在 SQLite 上不可用）
    """
    if is_postgres:
        return (
            pg_insert(AiAuditLog)
            .values(**values)
            .on_conflict_do_nothing(index_elements=["request_id"])
        )
    return AiAuditLog(**values)


async def _find_existing(session: AsyncSession, request_id: str) -> Any:
    """按 `request_id` 找已存在的审计行（**没有** ⇒ None）。"""
    result = await session.execute(
        select(AiAuditLog).where(AiAuditLog.request_id == request_id)
    )
    return result.scalars().first()


async def _insert_row(session: AsyncSession, row: Any) -> None:
    """把行写进去（方言分支在 `_build_insert` 里选好）。"""
    if isinstance(row, AiAuditLog):
        session.add(row)
        await session.commit()
        return
    await session.execute(row)
    await session.commit()


async def write_ai_audit_log(ctx: dict, **fields: Any) -> None:
    """写一条 AI 审计行（**幂等**：同一 `request_id` 只留一行）。

    Args:
        ctx: ARQ ctx（需含 `session_factory`，由 `worker.py::_on_startup` 注入）。
        **fields: 审计字段（`request_id` / `endpoint` / `status_code` …）。

    ⚠️ **写失败不抛**（除幂等冲突外都吞掉）—— 审计是旁路。
    """
    factory = ctx["session_factory"]
    request_id = fields.get("request_id")
    if not request_id:
        logger.warning("AI 审计缺 request_id ⇒ 跳过（无法保证幂等）")
        return

    async with factory() as session:
        existing = await _find_existing(session, str(request_id))
        if existing is not None:
            return  # 幂等：已写过 ⇒ 不再写
        values = _row_values(fields)
        bind = session.get_bind()
        is_postgres = bind.dialect.name == "postgresql"
        row = _build_insert(values, is_postgres=is_postgres)
        try:
            await _insert_row(session, row)
        except IntegrityError:
            # ⚠️ 并发下另一个 worker 已插入 ⇒ **幂等**，不算失败。
            await session.rollback()
            return
        except Exception:  # noqa: BLE001 — 审计失败不该让 job 反复重试
            await session.rollback()
            logger.warning("写 AI 审计行失败（已降级）", exc_info=True)
            return


__all__ = ["AI_AGENT_ID", "write_ai_audit_log"]
