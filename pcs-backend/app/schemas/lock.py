"""编辑锁 API 的响应 schema（ADR-0048 §①⑤ · SPEC §6.21）。

⚠️ **零裸字段**（P9A-DLV-010）：每个字段显式声明，不靠 `dict` 兜底。

## 为什么 `success` 一个字段覆盖三个操作

前端对三个操作的判断都是同一个问题：「**这次操作成没成**」：

| 操作 | success=True | success=False |
|---|---|---|
| acquire | 锁归我 | 别人持有 ⇒ 看 `holder` |
| renew | 续期成功 | 不是持有者 / 已过期 |
| release | 已释放 | 不是持有者 |

⇒ 用一个字段 + `operation` 区分，前端不必记三套字段名。
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class LockHolderResponse(BaseModel):
    """锁的持有者（体验层的全部价值：让人知道「谁在改」）。"""

    user_id: str = Field(..., description="持有者 user_id")
    acquired_at: datetime = Field(..., description="获取时刻（ISO8601）")
    username: str | None = Field(
        None, description="持有者显示名（取锁时写入，免掉一次用户查询）"
    )


class LockResponse(BaseModel):
    """三个端点共用的响应体。"""

    record_type: str = Field(..., description=(
        "记录类型：`RECORD_TYPE_REGISTRY` 的键（如 `CostEstResult`）—— 不是表名"
    ))
    record_id: str = Field(..., description="记录 ID")
    operation: Literal["acquire", "renew", "release"] = Field(..., description="操作")
    success: bool = Field(..., description="本次操作是否成功")
    holder: LockHolderResponse | None = Field(
        None, description="当前持有者（他人持锁时给出；降级时为 None）"
    )
    ttl_seconds: int = Field(..., description="剩余租约秒数（降级时为 0）")
    degraded: bool = Field(
        False, description="True = Redis 不可用，本次是降级放行（体验层失效）"
    )
    message: str | None = Field(
        None, description="横幅文案（降级时给出；前端顶栏显示）"
    )


__all__ = ["LockHolderResponse", "LockResponse"]
