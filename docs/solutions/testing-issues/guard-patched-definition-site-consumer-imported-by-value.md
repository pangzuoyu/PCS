---
module: pcs-backend 测试夹具
date: 2026-11-13
problem_type: testing_issue
component: testing_framework
severity: high
symptoms:
  - "单测车道「不碰真库」的守卫（autouse fixture，patch 掉 health 的 DB 探测）其实**一直是空壳** —— 单测真的连了开发库"
  - "全量测试里一条**与本批改动毫无关系**的用例红：RuntimeError: Future attached to a different loop（asyncpg）"
  - "症状落在**别的文件**的用例上 ⇒ 排查方向完全跑偏（先怀疑 WS 路由、再怀疑 AI 审计中间件）"
root_cause: patch_target_mismatch_import_by_value
resolution_type: test_and_source_fix
framework_version: pytest 9.1.1 / SQLAlchemy 2.0 / asyncpg / PostgreSQL 18
related_components:
  - testing_framework
  - db
  - ai
tags:
  - false-green
  - empty-shell-guard
  - import-by-value
  - monkeypatch
  - event-loop
  - asyncpg
  - test-isolation
---

# 守卫 patch 了「定义处」，而消费者是「按值导入」的 ⇒ 守卫是空壳

`docs/solutions/testing-issues/guard-test-fooled-by-lying-comment.md`
讲的是「守门被它守护的那行注释骗过」。
这里是同一族的**另一种失效方式**：守门**确实执行了**、
**确实没有报错**，但它**管不到它声称要管的东西**。

## 1. 守门长什么样

`tests/conftest.py` 里有一个 autouse 守卫，注释写得很清楚：

```python
@pytest.fixture(autouse=True)
def _avoid_real_db_probe(monkeypatch):
    """patch 同步 health check 为 True，避免 lifespan 触发真实连接。"""
    import app.db.session as db_session

    async def fake_async() -> bool:
        return True

    monkeypatch.setattr(db_session, "check_database", lambda: True, raising=True)
    monkeypatch.setattr(db_session, "check_database_async", fake_async, raising=True)
```

它 patch 的是**定义处**（`app.db.session`）。

## 2. 消费者是**按值导入**的

```python
# app/api/v1/health.py
from app.db.session import check_database_async, get_db   # ← 绑定到本模块的名字上

@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    db_ok = await check_database_async()                   # ← 走的是本模块的名字
```

`from X import name` 把**当前那一刻的值**绑到本模块的名字上。
之后 monkeypatch 改的是 `app.db.session.check_database_async`，
而 `app.api.v1.health.check_database_async` **仍然是原函数**
⇒ 守卫**够不着消费者** ⇒ `/api/v1/health` 照样去**真库**探测。

⇒ **守卫从来没有生效过**，而它的形态（autouse + `raising=True` +
有注释）让人以为它在生效。

## 3. 后果不是「脏」，是**别人的用例红**

那次探测会创建**模块级单例**的 async engine：

```python
# app/db/session.py
_async_engine: AsyncEngine | None = None   # 进程级单例 + 连接池
```

asyncpg 的连接**绑定在创建它那个 event loop 上**。单测里
pytest-asyncio 每个用例一个 loop：

- 用例 A（`/api/v1/health`）在 **loop A** 里创建引擎 ⇒ 池里那条连接属于 loop A
- 用例 A 结束 ⇒ **loop A 关闭** ⇒ 引擎**还在**（模块级单例）
- 另一个**文件**的用例 B 在 **loop B** 里启动 app 的 lifespan
  ⇒ 引擎从池里拿出那条**属于已死的 loop A** 的连接
  ⇒ `pool_pre_ping` 触发 ⇒ asyncpg 报
  **`Future attached to a different loop`** ⇒ **用例 B 红**

⇒ 症状落在**离病因隔了一个文件**的地方。
⇒ 本仓**已经栽过同一个陷阱**（bug-041：工厂是模块级单例），
   既有形状是「用例前后 `dispose_engines_async()`」——
   但那是在**下游**堵（把每个碰过它的文件都兜住），
   这次是**更上游**：让守卫**真的生效** ⇒ 根本不创建那个引擎。

## 4. 修法

```python
    # ⚠️ 消费者侧（按值导入的那一份）
    import app.api.v1.health as health_module
    import app.workers.cia_tasks as cia_tasks_module

    monkeypatch.setattr(health_module, "check_database_async", fake_async, raising=True)
    monkeypatch.setattr(cia_tasks_module, "check_database_async", fake_async, raising=True)
```

⇒ **patch 守卫要 patch「消费者模块上的绑定」**，不是只有定义处。
⇒ 新增消费者时**必须**在守卫里补一行 —— 否则守卫又变空壳。

## 5. 钉子（防复发）

守卫本身又是一个「只断言形状」的守卫 ⇒ 同样要能被证伪：

```python
async def test_unit_lane_health_probe_never_touches_the_real_db(client) -> None:
    import app.db.session as db_session

    resp = await client.get("/api/v1/health")

    assert resp.status_code == 200, resp.text
    assert db_session._async_engine is None, (
        "单测车道创建了全局 async engine ⇒ 它连的是真库，且它的连接"
        "绑定在本用例的 event loop 上 ⇒ 下一个文件的用例会拿到"
        "「attached to a different loop」的连接而红（bug-2162）"
    )
```

这条钉子直接断言**后果**（全局引擎没被创建），而不是断言
「某个函数被 patch 了」—— 后者正是空壳守卫能骗过的那种断言。

## 6. 通则

- **patch 一个函数 ⇒ 先问「消费者怎么拿到它的」**：
  `import X`（按模块取值）vs `from X import f`（按值绑定）vs
  `X.f()`（每次现取）。只有第三种能被「patch 定义处」覆盖。
- **守卫要断言「后果」，不要断言「动作」**：
  「我 patch 了 X」是动作；「全局引擎仍是 None」是后果。
  ⇒ 动作可以空转，后果不会。
- **模块级单例 + 事件循环 = 定时炸弹**：
  单例活过它创建的 loop 之后，下一个 loop 拿到的是**死连接**。
  ⇒ 单例要么按 loop 分桶，要么在 loop 结束时 dispose。
