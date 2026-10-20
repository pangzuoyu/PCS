"""Change Impact API（Sprint 3 + P9A-4 D3）。

端点：

- ``POST /change-impact/{record_type}/{record_id}/confirm-recalc`` —— **P1 已交付的
  传播触发器**（无哈希判定分流，语义与下面的 `confirm` **不同**，不可合并）。
- ``POST /change-impact/{record_type}/{record_id}/confirm`` —— **P9A-CIA-001**
  哈希判定分流：结果不变 → `STALE_RESOLVED_NO_CHANGE`（**免凭证**，不必重新签署）；
  结果变化 → `CHANGE_PENDING`（**要求重新签署**）。
- ``POST /change-impact/{record_type}/{record_id}/manual-adjust`` —— **P9A-CIA-002**
  人工判定结掉 STALE（**限权 + 审计**）。

## 为什么 `confirm` 与 `confirm-recalc` 是两个端点

`confirm-recalc` 是 P1 交付的**传播触发器**：无条件跑一遍 CIA 扫描 + 链式传播。
`confirm` 是**判定分流**：先比哈希，再决定这条 STALE 记录走「免凭证回 CHECKED」
还是「进 CHANGE_PENDING 重新签署」。

⇒ 合并成一个端点 ⇒ 前端要传「要不要触发传播」才能区分两种语义 ⇒ **一个端点
两种语义** = 下次改一个必伤另一个。

## record_type 词表

**类名**（`PipingResult` / `CostEstResult` / …），与本文件既有的
`confirm-recalc` 及 `RECORD_TYPE_REGISTRY` 一致 ⇒ 同一 URL 空间不出现两套词表。
⚠️ 而 D2 的编辑 guard 用的是**表名**（`cost_est_results`）—— 那是另一个 URL
空间（`/results` 与 `/locks`），两套词表并存是**已知欠账**（与 ADR-0050 记的
`record_comments.record_type` 存类名同一形状）⇒ 已登记 **TODO-060**
（建议随前端接 §6.21 时一并归一）。

⚠️ 全部响应体**显式声明**（P9A-DLV-010 零裸字段）：`confirm-recalc` 原用
`response_model=dict` ⇒ 贡献裸字段 ⇒ 本次一并换成显式 schema。
"""
from __future__ import annotations

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1._guard import check_record_access_or_404
from app.api.v1.config import _Actor, current_actor
from app.core.errors import PcsError as CorePcsError
from app.db.session import get_db
from app.services.calc_lineage import RECORD_TYPE_REGISTRY
from app.services.cia_engine import (
    CIAEngine,
    mark_stale_then_propagate,
)
from app.services.lineage import LineageTracker, _compute_hash, _record_pk
from app.services.state_machine import StateMachineService, StateTransition

router = APIRouter(prefix="/change-impact", tags=["change-impact"])


# ============================================================================
# 响应 schema（零裸字段）
# ============================================================================


class LatestLineageResponse(BaseModel):
    """血缘摘要。"""

    lineage_id: str = Field(..., description="data_lineage.lineage_id")
    source: str = Field(..., description="血缘来源（CALC / CIA / USER …）")
    change_summary: str | None = Field(None, description="变更摘要")


class ConfirmRecalcResponse(BaseModel):
    """`confirm-recalc` 的响应（原 `response_model=dict` ⇒ 裸字段）。"""

    record_type: str = Field(
        ...,
        description="记录类型（`RECORD_TYPE_REGISTRY` 的键，如 `CostEstResult`）",
    )
    record_id: str = Field(..., description="记录 ID")
    marked_stale: int = Field(..., description="被标 STALE 的行数")
    propagated: int = Field(..., description="链式传播到的下游数")
    equipment_affected: int = Field(..., description="受影响的设备数")
    latest_lineage: LatestLineageResponse | None = Field(
        None, description="最新血缘摘要"
    )
    note: str | None = Field(None, description="不在 CIA 范围时的说明")


class ImpactConfirmResponse(BaseModel):
    """`confirm` / `manual-adjust` 的响应。"""

    record_type: str = Field(
        ...,
        description="记录类型（`RECORD_TYPE_REGISTRY` 的键，如 `CostEstResult`）",
    )
    record_id: str = Field(..., description="记录 ID")
    decision: Literal["NO_CHANGE", "CHANGED"] = Field(
        ..., description="判定结果：结果不变 / 结果变化"
    )
    basis: Literal["record_hash", "full_hash", "no_baseline", "manual"] = Field(
        ..., description="判定依据"
    )
    sign_status: str = Field(..., description="转移后的 9 态 sign_status")
    requires_re_approval: bool = Field(
        ..., description="True = 已进 CHANGE_PENDING，须走签署链重新批准"
    )
    stale_resolution_path: str = Field(
        ..., description="结掉 STALE 的路径（写进记录的 stale_resolution_path 列）"
    )
    current_hash: str | None = Field(None, description="记录当前的 record_hash")
    baseline_hash: str | None = Field(None, description="基线 hash（血缘里的）")
    message: str = Field(..., description="给用户的一句话结论")


class ManualAdjustRequest(BaseModel):
    """`manual-adjust` 的请求体。

    ⚠️ `reason` **必填**：人工判定必须有据可查（审计里要能看出凭什么）。
    """

    decision: Literal["NO_CHANGE", "CHANGED"] = Field(
        ..., description="人工判定：结果不变 / 结果变化"
    )
    reason: str = Field(..., min_length=1, description="人工判定的依据（必填，写入审计）")


# ============================================================================
# 内部工具
# ============================================================================


def _resolve_model(record_type: str) -> type:
    """类名 → ORM 模型（`RECORD_TYPE_REGISTRY`）。未知 ⇒ 404。"""
    model = RECORD_TYPE_REGISTRY.get(record_type)
    if model is None:
        raise HTTPException(
            status_code=404, detail=f"record_type {record_type} not supported"
        )
    return model


async def _load_record(session: AsyncSession, record_type: str, record_id: uuid.UUID):
    """按类名取记录。找不到 ⇒ 404。"""
    from sqlalchemy import select as _sa_select

    model = _resolve_model(record_type)
    pk_name = sa_inspect(model).primary_key[0].name
    record = (
        await session.execute(
            _sa_select(model).where(getattr(model, pk_name) == record_id)
        )
    ).scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail=f"{record_type} not found")
    return record


async def _classify_change(
    session: AsyncSession, record
) -> tuple[Literal["NO_CHANGE", "CHANGED"], str, str | None, str | None, str]:
    """哈希判定分流（P9A-CIA-001）。

    复用 CIA 引擎的比对范式（`cia_engine.py`：当前 hash vs `data_lineage` 最新
    基线），**不另造概念**。

    返回 (decision, basis, current_hash, baseline_hash, 说明)。

    ⚠️ **没有基线 ⇒ 判「CHANGED」**（保守）：没有基线就无从判定「不变」，
    而「不变」是**免凭证**的那条 ⇒ 宁可多要一次签署，不可少要。
    """
    tracker = LineageTracker(session)
    latest = await tracker.latest(
        record_type=type(record).__name__, record_id=_record_pk(record)
    )
    current = getattr(record, "record_hash", "") or ""
    if latest is None:
        return "CHANGED", "no_baseline", current or None, None, "无血缘基线"
    diff = latest.change_diff_json or {}
    baseline = diff.get("record_hash")
    if baseline and current:
        same = current == baseline
        return (
            ("NO_CHANGE" if same else "CHANGED"),
            "record_hash",
            current,
            baseline,
            "record_hash 一致" if same else "record_hash 已变",
        )
    # 回退：全列哈希（cia_engine 的范式）
    full_baseline = diff.get("hash")
    if full_baseline:
        same = _compute_hash(record) == full_baseline
        return (
            ("NO_CHANGE" if same else "CHANGED"),
            "full_hash",
            current or None,
            full_baseline,
            "全列哈希一致" if same else "全列哈希已变",
        )
    return "CHANGED", "no_baseline", current or None, None, "血缘里没有可比基线"


async def _resolve_stale(
    session: AsyncSession,
    *,
    record_type: str,
    record_id: uuid.UUID,
    user: _Actor,
    decision: Literal["NO_CHANGE", "CHANGED"],
    basis: str,
    reason: str,
    resolution_path: str,
) -> ImpactConfirmResponse:
    """走状态机把 STALE 结掉（免凭证 / 要求重新签署由 decision 决定）。"""
    record = await _load_record(session, record_type, record_id)
    await check_record_access_or_404(
        session,
        user_id=user.user_id,
        record=record,
        actor_roles=user.roles,
    )
    if getattr(record, "sign_status", None) != "STALE":
        raise CorePcsError(
            code="RECORD_NOT_STALE",
            message="该记录不在 STALE 状态，无需确认",
            status=409,
        )
    transition = (
        StateTransition.RESOLVE_STALE_NO_CHANGE
        if decision == "NO_CHANGE"
        else StateTransition.RESOLVE_STALE_CHANGED
    )
    fsm = StateMachineService(session)
    try:
        await fsm.transition(
            record=record,
            transition=transition,
            actor_user_id=user.user_id,
            actor_role=user.role,
            reason=reason,
        )
    except Exception as exc:  # noqa: BLE001 - 状态机的错误类型不统一
        code = getattr(exc, "code", None) or "RECORD_TRANSITION_REJECTED"
        message = str(exc)
        status = 403 if "role" in message.lower() else 409
        raise CorePcsError(code=code, message=message, status=status) from exc
    record.stale_resolution_path = resolution_path
    await session.commit()
    return ImpactConfirmResponse(
        record_type=record_type,
        record_id=str(record_id),
        decision=decision,
        basis=basis,  # type: ignore[arg-type]
        sign_status=record.sign_status.value
        if hasattr(record.sign_status, "value")
        else str(record.sign_status),
        requires_re_approval=(decision == "CHANGED"),
        stale_resolution_path=resolution_path,
        current_hash=getattr(record, "record_hash", None),
        baseline_hash=None,
        message=(
            "结果未变：已结掉 STALE，无须重新签署"
            if decision == "NO_CHANGE"
            else "结果已变：已进入 CHANGE_PENDING，须走签署链重新批准"
        ),
    )


# ============================================================================
# 端点
# ============================================================================


@router.post(
    "/{record_type}/{record_id}/confirm-recalc", response_model=ConfirmRecalcResponse
)
async def confirm_recalc(
    record_type: str,
    record_id: uuid.UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    session: AsyncSession = Depends(get_db),
):
    """强制触发 CIA 扫描 + 传播 + 设备联动。

    ⚠️ **这是 P1 已交付的传播触发器**，**没有**哈希判定分流（那是
    `confirm` 端点，P9A-CIA-001）。两者语义不同，不可合并。

    BLOCKER-3 P7-7+ IDOR 防护: actor 必须有 record.project_id 访问权
    (先 fetch PipingResult 拿 project_id, 再 check_record_access_or_404).
    """
    # 仅支持已纳入 CIA 的 record 类型
    if record_type not in {"PipingResult"}:
        return ConfirmRecalcResponse(
            record_type=record_type,
            record_id=str(record_id),
            marked_stale=0,
            propagated=0,
            equipment_affected=0,
            latest_lineage=None,
            note=f"record_type {record_type} not in CIA scope",
        )
    # BLOCKER-3 P7-7+: 拉 PipingResult 拿 project_id, 验证 actor 访问权
    from sqlalchemy import select as _sa_select

    from app.models.calc import PipingResult
    pre_record = (await session.execute(
        _sa_select(PipingResult).where(PipingResult.pipe_id == record_id)
    )).scalar_one_or_none()
    if pre_record is not None:
        await check_record_access_or_404(
            session, user_id=user.user_id, record=pre_record,
            actor_roles=user.roles,
        )
    # 拉取最新 lineage + current hash
    tracker = LineageTracker(session)
    latest = await tracker.latest(record_type=record_type, record_id=record_id)
    engine = CIAEngine(session)
    marked = await engine.scan_stale()
    propagation = await mark_stale_then_propagate(
        session,
        record_type=record_type,
        record_id=record_id,
    )
    await session.commit()
    return ConfirmRecalcResponse(
        record_type=record_type,
        record_id=str(record_id),
        marked_stale=marked,
        propagated=propagation["propagated"],
        equipment_affected=propagation["equipment"],
        latest_lineage=(
            LatestLineageResponse(
                lineage_id=str(latest.lineage_id),
                source=latest.source,
                change_summary=latest.change_summary,
            )
            if latest
            else None
        ),
    )


@router.post(
    "/{record_type}/{record_id}/confirm", response_model=ImpactConfirmResponse
)
async def confirm_impact(
    record_type: str,
    record_id: uuid.UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    session: AsyncSession = Depends(get_db),
):
    """**哈希判定分流**（P9A-CIA-001）：确认一条 STALE 记录。

    - 结果**不变** ⇒ `STALE_RESOLVED_NO_CHANGE`，记录回 CHECKED ⇒ **免凭证**
      （不必重新签署）。
    - 结果**变化** ⇒ 记录进 `CHANGE_PENDING` ⇒ **要求重新签署**。
    """
    record = await _load_record(session, record_type, record_id)
    decision, basis, current, baseline, note = await _classify_change(session, record)
    response = await _resolve_stale(
        session,
        record_type=record_type,
        record_id=record_id,
        user=user,
        decision=decision,
        basis=basis,
        reason=f"哈希判定：{note}",
        resolution_path=(
            "cia_confirm_no_change" if decision == "NO_CHANGE" else "cia_confirm_changed"
        ),
    )
    return response.model_copy(
        update={"current_hash": current, "baseline_hash": baseline}
    )


@router.post(
    "/{record_type}/{record_id}/manual-adjust",
    response_model=ImpactConfirmResponse,
)
async def manual_adjust_impact(
    record_type: str,
    record_id: uuid.UUID,
    req: ManualAdjustRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    session: AsyncSession = Depends(get_db),
):
    """**人工判定**结掉 STALE（P9A-CIA-002）。

    与 `confirm` 的区别：`confirm` 由**系统**按哈希判定；`manual-adjust` 由
    **人**判定 ⇒ 走同一套状态机转移（⇒ 同样的限权 + 审计），但判定依据是
    `reason`（**必填**）⇒ 事后能看出「凭什么人工这么判」。

    ⚠️ 端点此前**不存在**（P9-Prep 交付面清单 §3 裁决 2）。
    """
    return await _resolve_stale(
        session,
        record_type=record_type,
        record_id=record_id,
        user=user,
        decision=req.decision,
        basis="manual",
        reason=req.reason,
        resolution_path=(
            "manual_adjust_no_change"
            if req.decision == "NO_CHANGE"
            else "manual_adjust_changed"
        ),
    )


__all__ = ["router"]
