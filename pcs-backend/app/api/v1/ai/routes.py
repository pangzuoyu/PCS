"""AI 预留路由（P10-A · Task T9）—— **一律 501**。

## 为什么是 501 而不是 200 + 空实现

SPEC §3.2.1(1)：P10 阶段只**预留**接口，不实现具体模型逻辑。
⇒ 端点**存在**（契约里有、前端能看见），但调用会明确收到
「AI 功能即将上线」⇒ 调用方不必猜「是没接通还是没这个功能」。

## 为什么认证在 501 之前

`current_actor`（**不是** SPEC 写的 `current_user` —— 偏离登记 D7）
⇒ 无 token ⇒ **401**（不是 501）。
⚠️ 反过来会让「没登录」看起来像「功能没上线」⇒ 排查方向直接跑偏。

## 契约标记

`openapi_extra={"x-status": "reserved"}` —— **不是** `deprecated`
（deprecated 的语义是「曾有、现已不推荐」；这里是「还没上线」）。
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.config import _Actor, current_actor
from app.core.ai_errors import AINotImplementedError
from app.core.errors import ErrorResponse, PcsError
from app.db.session import get_db
from app.schemas.ai import (
    AiContext,
    AiDocumentExtractRequest,
    AiEquipmentRecommendRequest,
    AiExplainRequest,
    AiIntentRequest,
    AiKnowledgeSearchRequest,
    AiNotImplementedResponse,
)

#: ⚠️ 前缀是 `/ai`（**不是** `/api/v1/ai`）—— `api_router` 已带
#: `prefix="/api/v1"` ⇒ 挂载后实际路径 = `/api/v1/ai/*`（= SPEC §3.1.2）。
router = APIRouter(prefix="/ai", tags=["ai"])

#: 契约标记（见模块 docstring）。
_RESERVED = {"x-status": "reserved"}

#: **501** 的响应声明（评审 M-2：契约里不能只写 200 + 空 schema）。
#: ⚠️ 运行时仍**抛** `AINotImplementedError`（由全局 handler 渲染成 501）
#: ⇒ 这里只是让**契约**如实描述会发生什么。
_AI_501 = {
    501: {
        "model": AiNotImplementedResponse,
        "description": "AI 已预留、未实现（P10）",
    },
    # ⚠️ **401 必须在契约里**（评审 #13）—— 端点是**认证先于 501**
    # ⇒ 无 token ⇒ 401 ⇒ 只看契约的人若没有这条分支，
    # 会把「没登录」当成「功能没上线」⇒ 排查方向直接跑偏。
    401: {
        "model": ErrorResponse,
        "description": "未认证（认证先于 501）",
    },
    # ⚠️ **503 也要在契约里**（评审 #19）—— AI 开关翻开且 endpoint 不在内网
    # ⇒ 出口守卫当场拒绝（`AI_ENDPOINT_NOT_INTERNAL`）⇒ 这是**会发生**的
    # 响应 ⇒ 契约必须如实描述（否则调用方只能靠「撞到 503」才知道有这道关）。
    503: {
        "model": ErrorResponse,
        "description": "AI 已启用但出口不合法（endpoint 缺失 / 不在内网 CIDR）",
    },
}


async def _ai_egress_guard(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """AI 出口守卫（评审 #19）—— 运行时开关翻开后**当场**校验内网 CIDR。

    ⚠️ **为什么需要**：启动时校验只在 `ai_enabled` **为真**时才跑（AI 默认关
    ⇒ 启动校验是空转）⇒ 而 `ai_enabled` 是**运行时**的系统参数（管理员可翻）
    ⇒ 「启动时校验 + 调用时校验」里，**调用时那次校验根本不在请求路径上**
    （路由直接抛 501、从不构造 `OutboundAIClient`）
    ⇒ 「打开 AI 并把 endpoint 指到公网」这件事**处处没校验**。

    ⇒ 每次 AI 请求都重新读开关与 endpoint 并校验：
    - AI 关着 ⇒ 只多**一次单列查询**（不联网、不构造客户端）⇒ 今天的常态；
    - AI 开着而 endpoint 不在内网 ⇒ **503**（拒绝，而不是「先放行再说」）。
    """
    from app.core.ai_cidr import parse_cidrs, validate_ai_endpoint
    from app.core.config import get_settings
    from app.services.system_setting_service import get_setting_value

    enabled = bool(await get_setting_value(db, "ai_enabled", default=False))
    if not enabled:
        return

    settings = get_settings()
    endpoint = (await get_setting_value(db, "ai_endpoint", default=None)) or (
        settings.ai_endpoint
    )
    if not endpoint:
        raise PcsError(
            "AI 已启用但未配置 endpoint",
            code="AI_ENDPOINT_NOT_CONFIGURED",
            status=503,
        )
    try:
        cidrs = parse_cidrs(settings.internal_cidrs)
    except RuntimeError as exc:
        raise PcsError(
            f"内网 CIDR 配置非法：{exc}",
            code="AI_INTERNAL_CIDRS_INVALID",
            status=503,
        ) from exc
    try:
        validate_ai_endpoint(endpoint, cidrs)
    except RuntimeError as exc:
        raise PcsError(
            f"AI endpoint 不在内网 CIDR 内：{exc}",
            code="AI_ENDPOINT_NOT_INTERNAL",
            status=503,
        ) from exc


@router.post(
    "/intent",
    status_code=501,
    response_model=AiNotImplementedResponse,
    openapi_extra=_RESERVED,
    responses=_AI_501,
)
async def ai_intent(
    request: AiIntentRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    _guard: Annotated[None, Depends(_ai_egress_guard)],
) -> None:
    """意图识别与指令分发（预留）⇒ **501**."""
    raise AINotImplementedError()


@router.post(
    "/knowledge/search",
    status_code=501,
    response_model=AiNotImplementedResponse,
    openapi_extra=_RESERVED,
    responses=_AI_501,
)
async def ai_knowledge_search(
    request: AiKnowledgeSearchRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    _guard: Annotated[None, Depends(_ai_egress_guard)],
) -> None:
    """知识库检索（RAG 语义检索，预留）⇒ **501**."""
    raise AINotImplementedError()


@router.post(
    "/equipment/recommend",
    status_code=501,
    response_model=AiNotImplementedResponse,
    openapi_extra=_RESERVED,
    responses=_AI_501,
)
async def ai_equipment_recommend(
    request: AiEquipmentRecommendRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    _guard: Annotated[None, Depends(_ai_egress_guard)],
) -> None:
    """相似设备推荐（预留）⇒ **501**."""
    raise AINotImplementedError()


@router.post(
    "/explain",
    status_code=501,
    response_model=AiNotImplementedResponse,
    openapi_extra=_RESERVED,
    responses=_AI_501,
)
async def ai_explain(
    request: AiExplainRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    _guard: Annotated[None, Depends(_ai_egress_guard)],
) -> None:
    """自然语言解释（预留）⇒ **501**."""
    raise AINotImplementedError()


@router.post(
    "/document/extract",
    status_code=501,
    response_model=AiNotImplementedResponse,
    openapi_extra=_RESERVED,
    responses=_AI_501,
)
async def ai_document_extract(
    request: AiDocumentExtractRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    _guard: Annotated[None, Depends(_ai_egress_guard)],
) -> None:
    """文档解析（PDF/图片字段提取，预留）⇒ **501**."""
    raise AINotImplementedError()


__all__ = ["AiContext", "router"]
