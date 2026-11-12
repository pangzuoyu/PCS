"""AI 侧的异常类型（P10-A · Task T8）。

## 为什么单独一个模块

`app/core/errors.py` 是**全仓唯一的错误信封**出口；AI 的 501 有自己的
信封形状（多一个 `request_id`、多一个 `status`）⇒ 单独放这里，
`errors.py` 只负责**注册** handler。

## 为什么是 501 而不是 404

SPEC §3.1.2 / §4.1.1：AI 端点在 P10 阶段**已存在但未实现** ⇒ 501
（Not Implemented）比 404 诚实 —— 404 会让调用方以为「这个端点不存在」，
而它存在，只是还没上线。
"""

from __future__ import annotations


class AINotImplementedError(Exception):
    """AI 能力「已预留、未实现」（P10 阶段）。

    ⇒ 由 `app/core/errors.py` 的全局 handler 渲染成 **501** +
    `{code, message, status, request_id}` 信封。
    """

    code: str = "AI_NOT_IMPLEMENTED"
    message: str = "AI功能即将上线"

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.message)
        if message:
            self.message = message
