import json
import logging
import sys
import uuid
from contextvars import ContextVar, Token

# P0-MED-003 fix（2026-09-18）：trace_id 通过 contextvar 在请求范围内传播，
# 中间件 set token → 任意下游代码路径 logging → JsonFormatter 读 contextvar
# 写入 JSON 日志，无需显式透传。lifespan 外（启动/CRON）trace_id 为 None。

_trace_id_var: ContextVar[str | None] = ContextVar("pcs_trace_id", default=None)


def bind_trace_id(trace_id: str) -> Token[str | None]:
    """中间件调用：把 trace_id 写入当前上下文。返回 Token 用于 reset。"""
    return _trace_id_var.set(trace_id)


def get_current_trace_id() -> str | None:
    """供 logging.Filter 与 errors 调用：取当前 trace_id。"""
    return _trace_id_var.get()


class TraceIdFilter(logging.Filter):
    """logging Filter：把 contextvar 中的 trace_id 写入 LogRecord。

    JsonFormatter 优先读 record.__dict__["trace_id"]（filter 阶段注入），
    兜底用 getattr(record, "trace_id", None)（手工 log.extra 路径）。
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """logging filter：注入 trace_id 到 record（contextvar 自动派生）。

        步骤：
        1. 跳过已有 trace_id 的 record（手工 log.extra 路径保留原值）
        2. 从 _trace_id_var ContextVar 取当前请求 trace_id
        3. 非空 → 注入 record.trace_id（供 JsonFormatter 输出）
        4. 始终返回 True（不拦截日志，仅补充字段）

        与 JsonFormatter 区别：filter 注入字段；formatter 序列化输出。
        """
        if not hasattr(record, "trace_id") or not getattr(record, "trace_id", None):
            current = _trace_id_var.get()
            if current is not None:
                record.trace_id = current
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        """日志 → 单行 JSON（structlog 风格）。

        步骤：
        1. 构造 payload：ts/level/logger/msg/trace_id
           （trace_id 来自 record 注入，由 TraceIdFilter 设置）
        2. 异常时附 exc（exc_info → str，保留 traceback）
        3. json.dumps(ensure_ascii=False)：中文日志不转义，便于 ELK 直接读

        输出格式：{"ts": ..., "level": "INFO", "logger": "...", "msg": "...",
                  "trace_id": "...", "exc": "..."}
        """
        payload: dict[str, object] = {
            "ts": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "trace_id": getattr(record, "trace_id", None),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def setup_logging() -> None:
    """初始化全局 logging（stdout + JSON formatter + trace_id filter）。

    步骤：
    1. 创建 StreamHandler（sys.stdout，容器内默认 stdout 日志）
    2. 绑定 JsonFormatter（structlog JSON 输出）
    3. 添加 TraceIdFilter（contextvar 自动派生 trace_id）
    4. root logger 单 handler + INFO 级别（覆盖 uvicorn/sqlalchemy 等三方）

    在 app/main.py lifespan 启动时调用一次。
    与 setup_logging_for_worker 区别：本函数初始化根 logger；
    worker 场景（RQ/Celery）需单独调 setup_logging_for_worker 避免重复初始化。
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(TraceIdFilter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)


def new_trace_id() -> str:
    return uuid.uuid4().hex
