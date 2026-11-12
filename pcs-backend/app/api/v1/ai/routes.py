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

from app.api.v1.config import _Actor, current_actor
from app.core.ai_errors import AINotImplementedError
from app.schemas.ai import (
    AiContext,
    AiDocumentExtractRequest,
    AiEquipmentRecommendRequest,
    AiExplainRequest,
    AiIntentRequest,
    AiKnowledgeSearchRequest,
)

#: ⚠️ 前缀是 `/ai`（**不是** `/api/v1/ai`）—— `api_router` 已带
#: `prefix="/api/v1"` ⇒ 挂载后实际路径 = `/api/v1/ai/*`（= SPEC §3.1.2）。
router = APIRouter(prefix="/ai", tags=["ai"])

#: 契约标记（见模块 docstring）。
_RESERVED = {"x-status": "reserved"}


@router.post("/intent", openapi_extra=_RESERVED)
async def ai_intent(
    request: AiIntentRequest,
    user: Annotated[_Actor, Depends(current_actor)],
) -> None:
    """意图识别与指令分发（预留）⇒ **501**."""
    raise AINotImplementedError()


@router.post("/knowledge/search", openapi_extra=_RESERVED)
async def ai_knowledge_search(
    request: AiKnowledgeSearchRequest,
    user: Annotated[_Actor, Depends(current_actor)],
) -> None:
    """知识库检索（RAG 语义检索，预留）⇒ **501**."""
    raise AINotImplementedError()


@router.post("/equipment/recommend", openapi_extra=_RESERVED)
async def ai_equipment_recommend(
    request: AiEquipmentRecommendRequest,
    user: Annotated[_Actor, Depends(current_actor)],
) -> None:
    """相似设备推荐（预留）⇒ **501**."""
    raise AINotImplementedError()


@router.post("/explain", openapi_extra=_RESERVED)
async def ai_explain(
    request: AiExplainRequest,
    user: Annotated[_Actor, Depends(current_actor)],
) -> None:
    """自然语言解释（预留）⇒ **501**."""
    raise AINotImplementedError()


@router.post("/document/extract", openapi_extra=_RESERVED)
async def ai_document_extract(
    request: AiDocumentExtractRequest,
    user: Annotated[_Actor, Depends(current_actor)],
) -> None:
    """文档解析（PDF/图片字段提取，预留）⇒ **501**."""
    raise AINotImplementedError()


__all__ = ["AiContext", "router"]
