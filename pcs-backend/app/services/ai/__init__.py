"""AI 侧的服务层（P10-A · Task T10）。

目前只有**审计入队**（`arq_queue`）—— 写库任务在
`app/workers/ai_audit_tasks.py`（ARQ 的任务体必须在 workers 包里，
否则 worker 的 `functions` 注册表按名字找不到）。
"""
