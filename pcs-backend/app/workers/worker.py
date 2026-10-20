"""ARQ WorkerSettings（Sprint 1 + Sprint 3）。

含四个异步任务：
- cleanup_workspaces：扫描并删除过期 PERSONAL/TEMPORARY workspace
- touch_workspace：把指定 workspace last_active_at 推到 now（活跃心跳）
- scan_stale_incremental：1 分钟增量 CIA 扫描
- scan_stale_full：5 分钟全量 CIA 扫描
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from arq.connections import RedisSettings
from arq.cron import CronJob
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import dispose_engines_async, get_async_session_factory
from app.workers.ad_sync_tasks import sync_ad_users  # P9A-USR-002
from app.workers.cia_tasks import scan_stale_full, scan_stale_incremental
from app.workers.notification_tasks import cleanup_old_notifications  # P9A-NOT-004
from app.workers.report_builder_tasks import execute_definition_task
from app.workers.report_tasks import (
    generate_report_task,
    reclaim_stale_report_tasks,
)
from app.workers.workspace_tasks import (
    cleanup_expired_workspaces,
    touch_workspace,
)

#: 失败重试上限（ADR-P8-004 裁决 3 次）。
#:
#: ⚠️ ARQ 的重试上限**只**从这里来（`arq/worker.py:549`：
#: `max_tries = self.max_tries if function.max_tries is None else function.max_tries`）。
#: 原先这个数字**只写在 `functions` 列表上方的注释里**，实际从没设过 ⇒ 走 ARQ
#: 默认 25 次：一个确定性失败（数据脏 / 字体缺 / 格式不认识）会重试 25 次，
#: 每次都写一条 REPORT_FAILED 审计，把审计表刷满。TODO-016。
#:
#: 为什么定义在**这里**而不是某个任务模块：两个任务体都要用它判断
#: 「这是不是最后一次尝试」，而 ARQ 的 ctx 里**没有** max_tries，拿不到。
#: 常量分散在任务模块里就会出现两份数字，而漂移的后果是：
#: 重试早就用完了，任务体还在等 ⇒ 行永远停在 RUNNING/QUEUED，
#: 15 分钟后被回收器当成僵死的收掉，而文件其实早就该出了。
MAX_TRIES = 3

#: 重试前的退避秒数。⚠️ 给一点退避而不是立刻重排：确定性失败（字体缺失、
#: 数据脏）重排多少次都一样，而瞬时故障（DB 抖动、Redis 抖一下）退避几秒
#: 通常自己就好了。5 秒对 10 秒级的渲染任务不算久。
#:
#: 同样定义在**这里**的理由与 `MAX_TRIES` 一致：两个任务体都要用它。
RETRY_DEFER_S = 5


async def _on_startup(ctx: dict) -> None:
    """ARQ worker 启动钩子（注入 Redis 设置 + DB session factory）。

    业务：从 get_settings() 取 redis_url，构造 RedisSettings 注入 ctx；
    get_async_session_factory() 同步创建异步 session 工厂（worker 任务内复用）。
    """

    settings = get_settings()
    ctx["redis_settings"] = RedisSettings.from_dsn(settings.redis_url)
    ctx["session_factory"] = get_async_session_factory()


async def _on_shutdown(ctx: dict) -> None:
    await dispose_engines_async()


@asynccontextmanager
async def session_scope(ctx: dict):
    """ARQ ctx → AsyncSession，**并保证关掉**。

    业务：从 on_startup 注入的 session_factory 取异步 session。

    ⚠️ 为什么不给两个任务各写一遍 `try/finally: await db.close()`
    （2026-10-13 修）：**两个任务都忘了关**。session 是任务体自己开的，
    关闭的责任也在任务体 —— 而「记得关」是记性，不是结构。漏掉的后果不是
    报错，是每个 job 把一条连接挂在 session 上直到 GC 才归还，最后撞上
    `remaining connection slots are reserved for roles with the SUPERUSER`，
    **报错发生在完全无关的命令上**（比如跑迁移时），根因却在 worker 里。

    收成一个入口，漏掉就变成结构上不可能。
    """
    db = _make_session(ctx)
    try:
        yield db
    finally:
        await db.close()


def _make_session(ctx: dict) -> AsyncSession:
    """ARQ ctx → AsyncSession（每个任务调用一次）。

    业务：从 on_startup 注入的 session_factory 取异步 session；
    优先用 `session_scope`（它负责关），直接调本函数要自己 `close()`。

    ⚠️ **不是 `async def`**（2026-10-13 修）。它内部没有任何 await，
    标成 async 会让调用方拿到一个 **coroutine 而不是 session** ——
    `db.execute(...)` 立刻炸
    `'coroutine' object has no attribute 'execute'`。
    之前从没被真正调用过（任务体读的是不存在的 `ctx["db"]`），
    所以这个多余的 async 一直没暴露。
    """
    factory = ctx["session_factory"]
    return factory()


class WorkerSettings:
    """ARQ worker 配置（连接 Redis + 注册函数 + 启停钩子）。

    业务：functions 注册异步任务（cleanup_expired_workspaces/touch_workspace/
    scan_stale_incremental 等）；on_startup 初始化 DB session + LRU 缓存预热；
    on_shutdown 释放连接。
    """

    # ⚠️ **从 settings 取，不要用 `RedisSettings()` 默认值**（2026-10-13 修）。
    # 原先写 `RedisSettings()` —— 它在**类属性初始化时**求值，也就是
    # import 那一刻，拿到的是 ARQ 的默认 localhost:6379，与本仓的
    # `REDIS_URL` 配置**无关**。`_on_startup` 里那句
    # `ctx["redis_settings"] = ...` 是**连接之后**才跑的，救不了。
    # 后果：worker 永远连默认 Redis。部署时若 REDIS_URL 指别处，
    # worker 会静静连错实例 —— 入队与消费分属两个 Redis，
    # 症状与「job 没被消费」完全一样（实测踩过）。
    redis_settings: RedisSettings = RedisSettings.from_dsn(
        get_settings().redis_url)
    on_startup = _on_startup
    on_shutdown = _on_shutdown
    functions = [
        cleanup_expired_workspaces,
        touch_workspace,
        scan_stale_incremental,
        scan_stale_full,
        # P8：报表生成。重试上限见下方 `max_tries`（ADR-P8-004 裁决 3 次）。
        generate_report_task,
        # P8b：自定义报表定义执行（REPORT_BUILDER）。
        # ⚠️ **2026-10-13 补上** —— 这一条原先漏了，而漏它的症状是
        # **静默**的：入队成功、API 返 202 + task_id、轮询永远 RUNNING，
        # 三分钟后超时说「文件可能仍在后台生成」—— 而那句话是**假的**，
        # Redis/队列都是好的，只是没人注册消费者。
        # ARQ 对未注册的函数名不报错，job 静静躺在队列里。
        # 防复发：`tests/workers/test_worker_registers_all_enqueued_tasks.py`
        # 断言「入队的 ⊆ 已注册的」。
        execute_definition_task,
        # P9A-USR-002：AD 同步每日凌晨。漏注册的症状是「同步从未发生」
        # 且没有任何报错 —— ARQ 对未注册的函数名不报错。
        sync_ad_users,
        # P9A-NOT-004：通知 30 天清理（ADR-0049 §④）。同样漏注册即静默失效。
        cleanup_old_notifications,
    ]
    # ⚠️ **必须是 `CronJob` 实例，不是 dict**（2026-10-13 修）。
    # arq 0.28 的 `Worker.__init__` 直接校验类型，dict 会让 worker
    # **构造就抛** `RuntimeError: cron_jobs, must be instances of CronJob`。
    # 它此前从没被真跑起来过 —— 单测只 import 这个类看注册表，不构造 worker。
    # `CronJob` 的形态是 `(name, coroutine, month, day, weekday, hour, minute,
    # second, microsecond, ...)` —— 后 13 个是**必填位置参数**，没有默认值。
    # 旧版 dict 写法里的 `function` 关键字**不存在**。
    #
    # ⚠️ **`None` 不等于「不限」，等于「这一位不参与匹配」**
    # （`arq.cron._get_next_dt` 第一句就是 `if v is None: continue`）。
    # 秒位传 `None` ⇒ 匹配的那一分钟里**每秒**都命中：`minute={0,5,...}`
    # 的 5 分钟一次扫描变成每分钟 59 次。三个 cron 的秒位一律写 `0`。
    cron_jobs = [
        # Sprint 3.9：每 5 分钟全量；每 1 分钟增量
        CronJob(name="scan-stale-full", coroutine=scan_stale_full,
                month=None, day=None, weekday=None, hour=None, second=0,
                microsecond=0, run_at_startup=False, unique=False,
                job_id=None, timeout_s=None, keep_result_s=3600,
                keep_result_forever=False, max_tries=1,
                minute={0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55}),
        CronJob(name="scan-stale-incremental", coroutine=scan_stale_incremental,
                month=None, day=None, weekday=None, hour=None,
                microsecond=0, run_at_startup=False, unique=False,
                job_id=None, timeout_s=None, keep_result_s=3600,
                keep_result_forever=False, max_tries=1,
                second=0, minute={1, 6, 11, 16, 21, 26, 31, 36, 41, 46, 51, 56}),
        # P8：僵死报表任务回收。ARQ 进程被 OOM kill 时状态会永远卡在
        # PENDING，前端无限轮询且无人知道。10 分钟一次足够（阈值 15 分钟）。
        CronJob(name="reclaim-stale-report-tasks",
                coroutine=reclaim_stale_report_tasks,
                month=None, day=None, weekday=None, hour=None, second=0,
                microsecond=0, run_at_startup=False, unique=False,
                job_id=None, timeout_s=None, keep_result_s=3600,
                keep_result_forever=False, max_tries=1,
                minute={3, 33}),
        # P9A-USR-002：AD 同步每日凌晨 02:17。
        # ⚠️ 刻意避开 02:00 —— 那是全网备份/定时任务最挤的整点，
        #    且多个部署常在同一分钟起进程。秒位写 0（同上，`None` 会变成每秒命中）。
        # ⚠️ 未配置 LDAP_BIND_DN 时任务内 no-op（见 ad_sync_tasks.py 顶注），
        #    不是让它每晚抛 —— 常态异常会把真告警淹掉。
        CronJob(name="sync-ad-users", coroutine=sync_ad_users,
                month=None, day=None, weekday=None, hour=2, minute=17, second=0,
                microsecond=0, run_at_startup=False, unique=True,
                job_id=None, timeout_s=None, keep_result_s=3600,
                keep_result_forever=False, max_tries=1),
        # P9A-NOT-004：通知 30 天保留清理（ADR-0049 §④）。每日 03:41。
        # ⚠️ `max_tries=2` 而**不是**既有的 1：一次瞬时连接抖动不该让清理
        #   永久失效，而永久失效的症状是「30 天后通知还在，且没人知道」——
        #   与漏注册同一个失败形状。
        CronJob(name="cleanup-old-notifications",
                coroutine=cleanup_old_notifications,
                month=None, day=None, weekday=None, hour=3, minute=41, second=0,
                microsecond=0, run_at_startup=False, unique=True,
                job_id=None, timeout_s=None, keep_result_s=3600,
                keep_result_forever=False, max_tries=2),
    ]
    # ⚠️ **ADR-P8-004 裁决的 `max_tries=3` 原先只写在注释里**，
    # 实际从没设过 —— 而 ARQ 的重试上限**只**从这里来
    # （`worker.py:549`：`max_tries = self.max_tries if function.max_tries
    # is None else function.max_tries`）。不设就用 ARQ 默认 25 次：
    # 一个确定性失败（数据脏 / 字体缺）会重试 25 次，每次都写一条
    # REPORT_FAILED 审计，把审计表刷满。TODO-016。
    #
    # 取值来自模块顶部的 `MAX_TRIES`：**同一个常量**，
    # 因为任务体要靠它判断「这是不是最后一次尝试」（ARQ 的 ctx 里**没有**
    # max_tries，拿不到）。两处各写一个数字 ⇒ 重试早就用完了而任务体还在等，
    # 行永远停在 RUNNING，15 分钟后被回收器当成僵死的收掉。
    max_tries = MAX_TRIES      # 见模块顶部 MAX_TRIES
    # 队列容量。ADR-P8-004 建议把**报表任务**单独拆一个 worker 并设
    # `max(2, cores // 2)`，但那是**部署侧**的决定 —— 仓库当前没有
    # backend / worker 的部署配置（见 ADR-P8-004 前置条件 0），拆了也没人起。
    # 这里只标注现状，待部署形态确定后再改；**不要在没有部署配置的情况下
    # 自行把报表拆到独立进程**（起不来，且 max_jobs 无从验证）。
    max_jobs = 4
    # 10k 行 PDF 约 10 秒（ADR-P8-004 实测），300 秒有 30 倍余量。
    # ⚠️ 过大反而有害：真卡死的任务会占着槽位 5 分钟。
    job_timeout = 300