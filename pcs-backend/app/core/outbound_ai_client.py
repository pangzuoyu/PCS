"""**唯一**允许调 AI 端点的出口（P10-A · Task T8）。

## 为什么要有这么一个「唯一出口」

- **架构守卫**（`tests/architecture/test_no_direct_ai_sdk.py`）会扫全仓：
  AI SDK（openai / ollama / vllm / langchain）与「用 httpx 调 AI 端点」
  **只允许**出现在这个文件里 ⇒ 将来有人绕过它直连，守卫会红。
- **调用时二次校验**：启动时校验过 ≠ 此刻还成立（DNS 会漂移 ⇒ 内网域名
  解析到公网）⇒ 每次调用前重判。
- **脱敏在审计之前**：审计表里存的是**脱敏后**的载荷 ⇒ 审计表不落原文。

## P10 阶段的行为

`call()` 走完「校验 → 脱敏 → 审计」三步后**抛 `AINotImplementedError`**
⇒ 端点回 501。**不真调**任何模型服务。
⇒ 但**审计链路是真的**（「AI 还没上线」≠「AI 调用不用留痕」）。
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from app.core.ai_cidr import validate_ai_endpoint
from app.core.ai_errors import AINotImplementedError
from app.core.ai_sanitizer import sanitize_for_ai

logger = logging.getLogger(__name__)

#: 审计回调的形状：`async def fn(payload: dict) -> None`
AuditFn = Callable[[dict[str, Any]], Awaitable[None]]


class OutboundAIClient:
    """出站 AI 客户端（P10 阶段只做**预留 + 审计**）。

    Args:
        endpoint: AI 服务端点（内网）。⚠️ **每次调用前都会重新校验**。
        timeout: 推理超时（秒）。
        cidrs: 允许的内网 CIDR 列表（来自 `parse_cidrs(settings.internal_cidrs)`）。
        audit_fn: 审计回调（**可注入** ⇒ 测试能观察「进 `_audit` 的载荷已脱敏」）。
            默认 `None` ⇒ `_audit` 是 no-op。
    """

    def __init__(
        self,
        *,
        endpoint: str,
        timeout: int,
        cidrs: list[str],
        audit_fn: AuditFn | None = None,
    ) -> None:
        self.endpoint = endpoint
        self.timeout = timeout
        self.cidrs = cidrs
        self._audit_fn = audit_fn

    async def call(self, payload: dict[str, Any]) -> dict[str, Any]:
        """调用 AI 服务（P10 阶段：校验 → 脱敏 → 审计 → 抛 501）。

        Raises:
            RuntimeError: endpoint 不在内网 CIDR（**在发出任何请求之前**）。
            AINotImplementedError: P10 阶段的终态（⇒ HTTP 501）。
        """
        # ① **调用时二次校验**（DNS 会漂移 ⇒ 启动时过了不代表此刻还成立）
        validate_ai_endpoint(self.endpoint, self.cidrs)
        # ② 脱敏
        sanitized = sanitize_for_ai(payload)
        # ③ 审计（**脱敏之后** ⇒ 审计表不落原文）；失败**降级**，不抛
        await self._audit(sanitized)
        # ④ P10 阶段不真调
        raise AINotImplementedError()

    async def _audit(self, payload: dict[str, Any]) -> None:
        """把**脱敏后**的载荷交给审计回调。

        ⚠️ **审计失败不得抛** —— 否则「AI 调用因审计写库失败而挂掉」
        ⇒ 降级为一条 warning。
        """
        if self._audit_fn is None:
            return
        try:
            await self._audit_fn(payload)
        except Exception:  # noqa: BLE001 — 审计失败不该影响主流程
            logger.warning("AI 审计回调失败（已降级，不影响调用）", exc_info=True)
