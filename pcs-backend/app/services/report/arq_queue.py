"""ARQ 入队 helper —— 把「怎么建 pool、传什么参数」收在一处。

`app/api/v1/report.py` 与 `report_builder.py` 都要入队。**两处各写一遍
`create_pool(RedisSettings.from_dsn(...))`** 时，第二个改参数就会漏掉第一个
—— 而漏掉的症状是任务静默不执行（pool 建好、job_id 有了、worker 那边
函数名对不上）。

## ⚠️ 两个已踩过的坑，写在这里免得重踩

1. **`create_pool` 收 `RedisSettings` 而不是 DSN 字符串** ——
   传字符串会在连接时炸 `'str' object has no attribute 'host'`。
2. **入队失败必须让端点知道**：抛 `PcsError(503)`，端点据此返回 503。
   **不能**返回 202 + 空 `task_id` —— 那会让前端拿着一个查不到任何东西的
   ID 无限转圈，而后台根本没在跑。也不能报 500「生成失败」：任务压根
   没开始，说「失败」同样是撒谎。是「**没入队**」，第三种状态。
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


async def _enqueue(func, **kwargs) -> str:
    """入队并返回 job_id；**入队失败抛 503**，不返回空串。

    空串是最容易写出来的「处理方式」，也最坏：端点照样回 202，
    前端拿着一个永远查不到结果的 task_id 一直转圈。
    """
    from arq import create_pool
    from arq.connections import RedisSettings

    from app.core.config import get_settings
    from app.services.exceptions import PcsError

    def _unavailable(e: Exception) -> PcsError:
        logger.warning("ARQ 入队失败：%s: %s", type(e).__name__, e)
        return PcsError(
            f"任务队列不可用，本次报表未入队（{type(e).__name__}: {e}）。"
            "**这不是执行失败** —— 任务从未开始，请稍后重试。",
            code="REPORT_QUEUE_UNAVAILABLE", status=503,
        )

    try:
        pool = await create_pool(RedisSettings.from_dsn(get_settings().redis_url))
    except Exception as e:  # noqa: BLE001 — Redis 各种连接异常
        raise _unavailable(e) from e
    try:
        job = await pool.enqueue_job(func, **kwargs)
    except Exception as e:  # noqa: BLE001
        raise _unavailable(e) from e
    finally:
        await pool.aclose()
    if job is None:
        raise PcsError("入队未返回任务句柄", code="REPORT_QUEUE_UNAVAILABLE", status=503)
    return job.job_id


async def enqueue_definition_execution(*, def_id: str, project_id: str,
                                       user_id: str,
                                       filters: dict | None = None,
                                       max_rows: int | None = None,
                                       output_format: str | None = None,
                                       job_id: str | None = None) -> str:
    """入队一次自定义报表定义执行（b7）。

    ⚠️ `job_id` 让**调用方自选** ARQ job id（2026-10-14，评审 P1 #3）。
    ARQ 的 `enqueue_job` 支持 `_job_id`（`arq/connections.py:148`
    的 `job_id = _job_id or uuid4().hex`）。

    为什么需要：端点要**先**把 `report_execution_logs` 那一行落库
    （否则 worker 可能抢在 commit 前面跑完并去回填一个尚不存在的行），
    而那一行必须写 `task_id`。若 task_id 只能由入队返回，端点就非得
    「先入队再写行」—— 顺序也就反了。自选 id 让两边对上。
    """
    # ⚠️ 传**名字字符串**，不是函数对象（2026-10-13 实测）。
    # arq 0.28 的 `serialize_job(function, ...)` 把首参当 function_name 存进
    # 队列，worker 端用 `self.functions[function_name]` 查 —— 字典键全是 str。
    # 传函数对象：入队成功、API 返 202，然后
    # `worker: job <id>, function <function ... at 0x…> not found` → job failed，
    # 全链路无一处报错，轮询只会一直 RUNNING 到超时。
    # 仍 import 一下：让「函数不存在」在**入队前**就炸，而不是静默。
    from app.workers.report_builder_tasks import execute_definition_task  # noqa: F401

    # ⚠️ **不要**在这里设重试次数 —— 两处都试过且都不对：
    #   1. `max_tries=3`：`enqueue_job` 没有这个形参，未识别的 kwargs 会被
    #      当成**任务函数的参数**传进去（`**kwargs` 照收不误，不报错、不生效）。
    #   2. `retry=Retry(max=3)`：ARQ 0.28 的 `Retry` 是**异常类**不是配置对象
    #      （`class Retry(RuntimeError)`），直接 TypeError。
    # 重试上限唯一的入口是 `WorkerSettings.max_tries`
    # （`worker.py:549`：`self.max_tries if function.max_tries is None`）。
    extra = {"_job_id": job_id} if job_id else {}
    return await _enqueue(
        "execute_definition_task",
        def_id=def_id, project_id=project_id, user_id=user_id,
        filters=filters, max_rows=max_rows, output_format=output_format,
        **extra,
    )


__all__ = ["enqueue_definition_execution"]