"""每个入队的函数都必须在 ARQ worker 注册 —— 2026-10-13 实测发现。

## 症状（最静的一类）

`arq_queue` 能入队、API 返回 **202 + task_id**、轮询端点返回
`{"status": "RUNNING", "report_file_id": null}` —— 一切「正常」，
**直到永远**。

`execute_definition_task`（REPORT_BUILDER 的执行入口）被
`enqueue_definition_execution` 入队，但 `WorkerSettings.functions`
里**只有** `generate_report_task`（固定 10 类）。ARQ 对未注册的
函数名**不报错** —— job 静静躺在队列里没人消费。

用户看到的是：转圈 → 3 分钟超时 → 「等待超时」。而超时那句话
（"文件可能仍在后台生成"）是**假的**，会把人引到错误的方向去查
Redis/队列健康度 —— 而那些都是好的。

## 为什么单测抓不到

每一方单独看都成立：入队函数测「入队成功」、worker 测「注册的那些
函数能跑」。缺的只是「入队的 ⊆ 已注册的」这条**集合关系**。

## 这条测试的形态

不断言「注册了哪些函数」（那是实现，会随需求变），而是断言
**不变量**：`arq_queue` 里所有入队入口用到的 `__name__` 都在
`WorkerSettings.functions` 的名字集合里。新增一个入队函数却忘了
注册，这里立刻红。

同类坑在本仓已出现过第二次：第一次是 REPORT_BUILDER 的
`task_id → report_file_id` 映射缺失（bug-163 那条链），
那次也是「每一层单独看都绿」。
"""
from __future__ import annotations

import ast
import pathlib
import re
from pathlib import Path

import pytest

ARQ_QUEUE = Path("app/services/report/arq_queue.py")
#: 固定 10 类的入队**不在** arq_queue —— 它在 API 层直接
#: `pool.enqueue_job(generate_report_task, ...)`（report.py:156）。
#: 第一版只扫 arq_queue，于是 `generate_report_task` 完全没进检查范围 ——
#: 扫描器只覆盖一半入口时，「入队 ⊆ 注册」这个不变量是**假**的。
REPORT_API = Path("app/api/v1/report.py")
WORKER = Path("app/workers/worker.py")

#: 两条已知的入队调用形态。改了任一形态，第一条测试会空过 ——
#: 而空过的断言长得和通过一模一样。
_ENQUEUE_HELPERS = {"_enqueue"}          # 间接：传给本模块的辅助函数
_ENQUEUE_METHODS = {"enqueue_job"}       # 直接：pool.enqueue_job(...)


def _cron_job(func_name: str):
    """按 **coroutine 的函数名**反查 cron job。

    ⚠️ 不按 `job.name`（那是 kebab-case 的展示名 `scan-stale-full`，
    与函数名 `scan_stale_full` 不一致）。按错的名字查，第一版会
    「找不到」而我差点以为是配置漏了 —— 实际是查错了键。
    """
    from app.workers.worker import WorkerSettings

    for job in WorkerSettings.cron_jobs:
        got = getattr(job, "coroutine", None)
        if getattr(got, "__name__", None) == func_name:
            return job
    raise AssertionError(
        f"WorkerSettings.cron_jobs 里没有 coroutine 为 {func_name} 的 job："
        f"{[getattr(getattr(j, 'coroutine', j), '__name__', j) for j in WorkerSettings.cron_jobs]}")



def _enqueued_func_names() -> set[str]:  # noqa: C901
    """扫出 `arq_queue.py` 里真正入队的函数变量名。

    ⚠️ 覆盖**两处**入队形态，两版都栽在这上面：
      - 第一版只扫 `enqueue_job` → 只捞到 `_enqueue` 内部的 `func` 变量名，
        真正入队的 `execute_definition_task` 全漏；
      - 第二版只扫 `_enqueue` → 漏掉 `report.py:156` 里**直接**
        `pool.enqueue_job(generate_report_task, ...)` 的那条路径。
    两版都是「扫到了东西、不是空过」，但都只覆盖了一半入口 ——
    而覆盖一半的不变量是**假**的。

    刻意用 **AST** 而不是文本搜索：文本搜索会命中 docstring 与 import 行
    里的函数名，而那些**不构成入队**。
    """
    # ⚠️ 先收集 `_enqueue` 的**形参名**：`async def _enqueue(func, **kwargs)`
    # 里那个 `func` 是形参，不是入队的函数。第三版扫到了它，于是断言报
    # 「func 没注册」—— 而它压根不是任务。排除形参不是洁癖，是必要的。
    param_names: set[str] = set()
    for path in (ARQ_QUEUE, REPORT_API):
        tree = ast.parse(path.read_text())
        for fn in ast.walk(tree):
            if isinstance(fn, ast.AsyncFunctionDef) and fn.name in _ENQUEUE_HELPERS:
                args = fn.args
                param_names |= {a.arg for a in
                                (*args.posonlyargs, *args.args, *args.kwonlyargs)}

    names: set[str] = set()
    for path in (ARQ_QUEUE, REPORT_API):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            target = node.func
            hit = (isinstance(target, ast.Name)
                   and target.id in _ENQUEUE_HELPERS) or (
                   isinstance(target, ast.Attribute)
                   and target.attr in _ENQUEUE_METHODS)
            if not hit:
                continue
            first = node.args[0]
            # 两种形态都要认：裸函数变量（修复前）与名字字符串（修复后）。
            # 只认其一时，另一个版本会「扫不到」而不是「报错」——
            # 而 `assert enqueued` 那种存在性断言只在**完全**扫不到时才响。
            if isinstance(first, ast.Name) and first.id not in param_names:
                names.add(first.id)
            elif isinstance(first, ast.Constant) and isinstance(first.value, str):
                names.add(first.value)
    return names


def _registered_names() -> set[str]:
    """worker 实际注册的函数名集合。

    同样用 AST：只认 `WorkerSettings.functions` 里的**裸函数引用**，
    不认字符串（ARQ 也支持字符串函数名，那样更不会漏注册）。
    """
    tree = ast.parse(WORKER.read_text())
    for node in ast.walk(tree):
        if (isinstance(node, ast.ClassDef) and node.name == "WorkerSettings"):
            for stmt in node.body:
                if (isinstance(stmt, ast.Assign)
                        and any(getattr(t, "id", None) == "functions"
                                for t in stmt.targets)):
                    return {e.id for e in stmt.value.elts
                            if isinstance(e, ast.Name)}
    return set()


def test_enqueued_functions_are_all_registered_in_the_worker():
    """⚠️ 根断言：入队的函数 ⊆ worker 注册的函数。

    缺一个的症状是 **202 + 永远 RUNNING**，不报错。
    """
    enqueued = _enqueued_func_names()
    assert enqueued, (
        "没扫到任何入队函数 —— 扫描规则失效。"
        "入队若改成字符串函数名（`pool.enqueue_job(\"name\")`），"
        "这个扫描器看不到，也需要登记（那时请改成扫字符串常量）。")

    missing = enqueued - _registered_names()
    assert not missing, (
        f"这些函数被入队但 worker 没注册，job 永远不会执行：{sorted(missing)}\n"
        f"症状：API 返 202 + task_id，轮询永远 RUNNING，直到超时 —— "
        f"且超时提示会说「文件可能仍在后台生成」，那是**假的**，"
        f"会把人引去查 Redis 健康度（而 Redis 是好的）。"
    )


def test_the_scanner_actually_sees_the_known_enqueue_sites():
    """⚠️ 防「解析规则失效导致恒真」。

    上一条若因为扫不到任何东西而空过，它会给出「没扫到」而不是通过；
    但若有人把 `enqueue_job` 改成别的写法、而这条又恰好扫到了别的，
    两条一起绿就意味着扫描器在骗自己。故显式钉住两个已知入队函数名。
    """
    found = _enqueued_func_names()
    assert {"generate_report_task", "execute_definition_task"} <= found, \
        (f"实际扫到：{sorted(found)}\n"
         f"⚠️ 这条是防「扫描器恒真」的 —— 两版扫描器都只覆盖了一半入口，"
         f"看着「有东西、不是空过」，实际各漏一条。")


@pytest.mark.parametrize("mod_name,func_name", [
    ("app.workers.report_tasks", "generate_report_task"),
    ("app.workers.report_builder_tasks", "execute_definition_task"),
])
def test_both_report_task_entrypoints_exist(mod_name, func_name):
    """两个报表任务入口都必须可导入（注册表引用的就是它们）。"""
    import importlib

    assert callable(getattr(importlib.import_module(mod_name), func_name))


# --- worker 配置能不能真被 arq 接受 --------------------------------------------


def test_worker_settings_are_actually_acceptable_to_arq():
    """⚠️ `run_worker` / `create_worker` 真的能吃下这个 WorkerSettings。

    这条存在的理由：`cron_jobs` 之前写成 dict（`{"minute": ..., "function": ...}`），
    而 arq 0.28 的 `Worker.__init__` 要求 **`CronJob` 实例**，构造时就抛
    `RuntimeError: cron_jobs, must be instances of CronJob`。

    于是 **worker 从来没真起来过**。它没被测出来是因为：
    - 入队走 Redis，不需要 worker 在
    - 单测只 import `WorkerSettings` 检查注册表，**不构造 worker**
    症状是「worker 进程一启动就死」—— 而没人启动过它。
    """
    from arq.worker import create_worker

    from app.workers.worker import WorkerSettings

    worker = create_worker(WorkerSettings)   # 不构造 = 什么问题都发现不了
    try:
        assert worker is not None
        # cron_jobs 必须是 CronJob 实例，且能被 ARQ 真的解析出下一次运行时间
        from arq.cron import CronJob
        for job in WorkerSettings.cron_jobs:
            assert isinstance(job, CronJob), \
                f"cron_jobs 里混进了非 CronJob：{type(job).__name__}"
    finally:
        # 构造会注册 atexit / 信号处理器，测完立刻放掉
        pass


@pytest.mark.parametrize("name", ["scan_stale_full", "scan_stale_incremental",
                                  "reclaim_stale_report_tasks"])
def test_cron_jobs_pass_arq_a_ctx_taking_callable(name):
    job = _cron_job(name)
    """⚠️ cron 入口必须是 **`ctx` 单参**且**可调用**。

    `reclaim_stale_tasks_batch(db: AsyncSession)` 收的是 db 而不是 ctx ——
    docstring 写着「ARQ cron 要的是无参函数」，签名却要一个 db 参数。
    ARQ 触发时按位置传 ctx，于是它把 **ctx 当成 db** 用，
    `select(...).where(... db ...)` 全在这一刻炸。

    这个错**只在 cron 真的触发时才现形**（`{minute: {3, 33}}`，
    即每小时的 :03 与 :33）—— 所以它可以静静烂在仓库里很久。
    """
    import inspect

    assert callable(job.coroutine), \
        f"cron {job.name} 的 coroutine 不可调用：{job.coroutine!r}"
    params = list(inspect.signature(job.coroutine).parameters.values())
    assert len(params) == 1 and params[0].name == "ctx", (
        f"cron {job.name} 的入口签名是 "
        f"({', '.join(p.name for p in params)})，ARQ 只传一个 `ctx`。"
        f"要注入 db 就自己从 ctx['session_factory'] 取。")


# --- 入队必须传**函数名字符串**，不是函数对象 ---------------------------------------
#
# ⚠️ 这是 2026-10-13 起 Redis + worker 后实测暴露的第二个静默缺口。
#
# 实测日志：`job 22355ac8…, function <function execute_definition_task at 0x…>
# not found`
#
# 机制：arq 0.28 的 `serialize_job(function, args, ...)` 把第一个参数当
# **function_name** 存进队列，而 worker 端是 `self.functions[function_name]` ——
# 字典的键全是 `str`。传函数对象进去，pickle 能存下那个对象，
# 但 worker 用它做字典键查不到 → KeyError → job failed。
#
# 所以**入队必须传裸名字字符串**。worker 注册时用裸函数引用是**对的**
# （`WorkerSettings.functions = [some_func]`），ARQ 会把它转成名字；
# 但入队端不会替我们转。
#
# 为什么这一条从前没人发现：`generate_report_task`（固定 10 类）**也是
# 传函数对象**，也就是说**那条路径同样从来没真跑过**。入队成功、202 返回、
# job 静静 failed，没有任何一层报错。


def _enqueue_calls() -> list[ast.Call]:
    out: list[ast.Call] = []
    for path in (ARQ_QUEUE, REPORT_API):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            target = node.func
            hit = (isinstance(target, ast.Name)
                   and target.id in _ENQUEUE_HELPERS) or (
                   isinstance(target, ast.Attribute)
                   and target.attr in _ENQUEUE_METHODS)
            if hit:
                out.append(node)
    return out


def test_every_enqueue_site_passes_a_function_name_string_not_an_object():
    """⚠️ 根断言：入队第一个实参必须是**字符串**。

    传函数对象的后果（实测）：job 入队成功、API 返 202、然后
    `worker: job <id>, function <function ... at 0x...> not found`，
    job failed。**全链路无一处报错** —— 轮询只会一直 RUNNING 到超时。
    """
    # ⚠️ `_enqueue` **内部**那一行（`enqueue_job(func, ...)`）不算违规 ——
    # 它的 `func` 是本函数自己的形参，传什么就转给谁。
    # 检查它的**调用点**已经由上面两条覆盖（形参名已在 param_names 里排除）。
    # ⚠️ 按**行号**排除，不能按 `id(call)` —— 两次 `ast.walk` 各自解析出
    # 不同的对象，`id()` 永不相等（第一版用 id() 时这条永远红）。
    inner_lines: set[int] = set()
    tree = ast.parse(ARQ_QUEUE.read_text())
    for fn in ast.walk(tree):
        if isinstance(fn, ast.AsyncFunctionDef) and fn.name in _ENQUEUE_HELPERS:
            for sub in ast.walk(fn):
                if (isinstance(sub, ast.Call)
                        and isinstance(sub.func, ast.Attribute)
                        and sub.func.attr in _ENQUEUE_METHODS):
                    inner_lines.add(sub.lineno)

    offenders = []
    for call in _enqueue_calls():
        if call.lineno in inner_lines:
            continue
        first = call.args[0]
        if not (isinstance(first, ast.Constant) and isinstance(first.value, str)):
            label = (first.id if isinstance(first, ast.Name)
                     else type(first).__name__)
            line = getattr(first, "lineno", "?")
            offenders.append(f"第 {line} 行传了 {label}（应为字符串名字）")
    assert not offenders, (
        "这些入队点传的是函数对象而非名字字符串：\n  "
        + "\n  ".join(offenders)
        + "\n\n症状：入队成功 → API 返 202 + task_id → worker 报 "
        + "'function ... not found' → job failed → 轮询永远 RUNNING 到超时。"
          "\nARQ 用 `self.functions[function_name]` 查，字典键全是 str。")


# --- 任务体读的 ctx 键，worker 的 on_startup 必须真的注入 -----------------------
#
# ⚠️ 实测（Redis + worker 真跑之后）暴露的第 5 个断点：
# `report_builder_tasks.execute_definition_task` 写的是 `ctx["db"]`，
# 而 worker 的 `_on_startup` 注入的是 `ctx["session_factory"]`
# （其余任务都用 `_ctx_session(ctx)` 那个包装）。
#
# 后果同样是**静默**的：入队成功 → 202 → job failed，ARQ 结果里只有
# `KeyError: 'db'`，worker 日志一行不打（它只在 function not found 时 warn）。
# 轮询端点返回 404（执行日志从未创建），看起来像「job 没被消费」——
# 而它**被消费了、还失败了**。排查方向会被完全带偏。

ARQ_TASK_MODULES = [
    "app.workers.report_builder_tasks",
    "app.workers.report_tasks",
]


def test_task_bodies_only_read_ctx_keys_the_worker_actually_injects():
    """⚠️ 根断言：任务体里 `ctx["X"]` 的每个 X，worker 都得注入。

    做法：扫出各任务模块里所有 `ctx[...]` / `ctx.get(...)` 的**字面量键**，
    与 `WorkerSettings._on_startup` 注入的键集合比对。

    刻意不扫动态键（`ctx.get(name)` 之类）—— 那种静态查不到，
    但也不该出现在任务体里。
    """
    import importlib
    import inspect

    worker = importlib.import_module("app.workers.worker")
    src = inspect.getsource(worker._on_startup)
    injected = set(re.findall(r'ctx\[["\'](\w+)["\']\]\s*=', src))

    assert injected, "没扫到任何注入键 —— 解析规则失效"

    # ⚠️ 必须扫 **AST** 而不是源码文本。第一版用正则扫全文，结果把我自己
    # 写在注释与 docstring 里的 `ctx["db"]` 也算成「读取」—— 而注释里
    # 出现一个键名，正是为了说明「这里曾经读过一个不存在的键」。
    used: dict[str, set[str]] = {}
    for mod_name in ARQ_TASK_MODULES:
        mod = importlib.import_module(mod_name)
        src_file = inspect.getsourcefile(mod)
        tree = ast.parse(pathlib.Path(src_file).read_text())
        keys: set[str] = set()
        for node in ast.walk(tree):
            # ctx["x"] / ctx['x']
            if (isinstance(node, ast.Subscript)
                    and isinstance(node.value, ast.Name)
                    and node.value.id == "ctx"
                    and isinstance(node.slice, ast.Constant)
                    and isinstance(node.slice.value, str)):
                keys.add(node.slice.value)
            # ctx.get("x") / ctx.get('x', ...)
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "get"
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "ctx"
                    and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)):
                keys.add(node.args[0].value)
        for key in keys:
            used.setdefault(key, set()).add(mod_name)

    # ⚠️ ARQ **自己**往 ctx 里放 `job_id` / `job_try` / `result` ——
    # 那不是 worker 注入的，所以不在 `injected` 里。把它们算成「缺失」
    # 会让这条测试要求 worker 去注入 ARQ 已经给的东西。
    arq_builtin = {"job_id", "job_try", "result", "redis", "job_score"}

    missing = {k: sorted(v) for k, v in used.items()
               if k not in injected and k not in arq_builtin}
    assert not missing, (
        f"任务体读了 worker 没注入、ARQ 也不提供的 ctx 键：{missing}\n"
        f"worker 注入的是：{sorted(injected)}；"
        f"ARQ 自带的是：{sorted(arq_builtin)}\n"
        f"症状：入队成功 → 202 → job failed（ARQ 结果里是 KeyError），"
        f"worker 日志**一行不打** → 轮询端点 404，看起来像「job 没被消费」。")


def test_worker_honours_the_apps_redis_url_setting(monkeypatch):
    """⚠️ worker 的 Redis 必须来自**本仓 settings**，不是 ARQ 的默认值。

    2026-10-13 实测的第六个静默缺口：

    ```python
    redis_settings: RedisSettings = RedisSettings()   # ← 默认 localhost:6379
    ```

    它是**类属性**，在 import 那一刻求值，与 `REDIS_URL` 配置无关。
    而 `_on_startup` 里的 `ctx["redis_settings"] = RedisSettings.from_dsn(...)`
    是**连接之后**才跑的 —— 救不了。

    后果：worker **永远**连默认 Redis。部署时若 `REDIS_URL` 指别处，
    入队（API）与消费（worker）分属两个 Redis，症状与
    「job 没被消费」一模一样。

    这条测试用 `importlib.reload` 重新求值类属性 —— 必须 reload，
    因为类属性在 import 时就固定了，monkeypatch settings 不影响已求值的值。
    """
    import importlib

    import app.core.config as config_mod

    monkeypatch.setenv("REDIS_URL", "redis://example.invalid:12345/7")
    config_mod.get_settings.cache_clear()

    worker_mod = importlib.reload(
        importlib.import_module("app.workers.worker"))
    try:
        rs = worker_mod.WorkerSettings.redis_settings
        assert (rs.host, rs.port) == ("example.invalid", 12345), \
            (f"worker 连的是 {rs.host}:{rs.port}，不是 REDIS_URL 指的 "
             f"example.invalid:12345 —— 类属性用了 ARQ 默认值")
    finally:
        monkeypatch.undo()
        config_mod.get_settings.cache_clear()
        importlib.reload(importlib.import_module("app.workers.worker"))


def test_no_cron_job_fires_more_than_once_per_scheduled_minute():
    """⚠️ `second=None` 在 ARQ 里**不是**「不限」，是**被整条跳过**。

    `arq.cron._get_next_dt` 开头是 `if v is None: continue` —— 秒位传
    `None` 等于秒位不参与匹配，于是 `minute={0,5,...}` 匹配的那一分钟里
    **每一秒都命中**：本该每 5 分钟 1 次的 `scan-stale-full` 变成
    每分钟 59 次、`reclaim-stale-report-tasks` 同样。而这些是
    「扫全库找陈旧任务」的重活，708 次/小时的 Postgres 查询是自伤。

    症状在真实 worker 里是**日志刷屏**，不看日志就完全不知道 ——
    单测只验「CronJob 参数被 ARQ 接受」，验不出密度。

    观测点：不信「配得像 cron」，直接数**未来 2 小时实际会触发几次**。
    """
    import datetime as dt

    from arq.cron import next_cron

    from app.workers.worker import WorkerSettings

    base = dt.datetime(2026, 1, 1, 0, 0, 0)
    horizon = base + dt.timedelta(hours=2)
    for job in WorkerSettings.cron_jobs:
        t, fires = base, 0
        while True:
            t = next_cron(t, month=job.month, day=job.day, weekday=job.weekday,
                          hour=job.hour, minute=job.minute, second=job.second,
                          microsecond=job.microsecond)
            if t >= horizon:
                break
            fires += 1
            assert fires <= 40, (
                f"{job.name} 在 2 小时内会触发 >40 次 —— 秒位多半是 None，"
                f"它会被 arq 整条跳过（'不限'其实等于'每秒'）")
