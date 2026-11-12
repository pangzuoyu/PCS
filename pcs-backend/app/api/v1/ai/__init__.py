"""AI 预留路由组（P10-A · Task T9）。

⚠️ **前缀是 `/ai` 而不是 `/api/v1/ai`** —— `api_router` **已经**带
`prefix="/api/v1"` ⇒ 这里再写一遍，实际路径会变成 `/api/v1/api/v1/ai/...`
（照抄 SPEC §3.2.1(1) 的示例代码就会踩）。
⇒ 挂载后实际路径 = `/api/v1/ai/*`（= SPEC §3.1.2 逐字一致）。
"""
from app.api.v1.ai.routes import router

__all__ = ["router"]
