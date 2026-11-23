---
module: pcs-backend 默认车道隔离（tests/conftest.py · tests/lane_guards.py）
date: 2026-11-18
problem_type: testing_issue
component: testing_framework
severity: high
symptoms:
  - "PG 车道里 `_sync_engine` 指向 **SQLite（内存）** ⇒ ⇒ 任何走 `get_engine()` 的路径**静默指向一个空库**（绿灯，假绿）"
  - "依赖真 Redis 语义的 **20 条**用例在**所有**车道都被跳过 ⇒ ⇒ 覆盖全丢，而「迁到 PG 车道」那条 TODO **照原样根本执行不了**"
  - "E2E 车道的隔离 schema 与根 conftest 的隔离**互相覆盖** ⇒ ⇒ 顺序依赖 ⇒ ⇒ 脆"
root_cause: autouse_fixture_applies_to_every_lane
resolution_type: test_and_source_fix
---

# autouse fixture 会作用于**所有**车道 ⇒ ⇒ 隔离必须**按车道限定**

## 现象

P10-F · F2-T5 给默认车道加了一层隔离（`tests/conftest.py` 的
`_isolate_default_lane`，**函数级 autouse**）：

- `_sync_engine`（`app/db/session.py` 的同步单例）⇒ SQLite（内存）
- `settings.redis_url` ⇒ `redis://127.0.0.1:1/0`（**不可路由**端口）

目的：让默认车道（`uv run pytest`）**绝不碰开发库 / 真 Redis**
（`CLAUDE.md` 的硬约束）。

⚠️ 但那层隔离是 **autouse** ⇒ ⇒ 它对 `pytest -m pg` / `-m e2e`
**同样生效** ⇒ ⇒ 两条车道**自带**的隔离（真 PG · 隔离 schema）被盖掉：

| 被盖掉的东西 | 后果 |
|---|---|
| PG 车道的 `_sync_engine` | 指向 SQLite（内存）⇒ ⇒ 走 `get_engine()` 的路径**静默**查一个空库 ⇒ ⇒ **假绿** |
| PG / E2E 车道的 `settings.redis_url` | 仍是不可路由端口 ⇒ ⇒ 依赖真 Redis 的用例**在任何车道**都被跳过 ⇒ ⇒ 覆盖全丢 |
| E2E 车道的隔离 schema 绑定 | 根 fixture 每个用例把它换回 SQLite ⇒ ⇒ `e2e_client` 再覆盖回来 ⇒ ⇒ **顺序依赖** |

## 根因

⚠️ **「autouse」是 pytest 的全局作用域，不是「这条车道」的** ⇒ ⇒
⇒ ⇒ 一个**为了保护某条车道**而写的 fixture ⇒ ⇒ 默认会**作用于所有车道**
⇒ ⇒ 而车道之间的隔离策略**本来就不同**（默认车道 = 内存 SQLite；
PG / E2E 车道 = 真 PG + 隔离 schema）⇒ ⇒ 一层覆盖全部 ⇒ ⇒ 必然打架。

⚠️ **更隐蔽的一层**：`tests/lane_guards.py::require_real_redis()` 的判据是
「`settings.redis_url` 是否被隔离成不可路由端口」⇒ ⇒ 在车道里它**也是**被
隔离的 ⇒ ⇒ ⇒ 「迁到 PG 车道时去掉那个 skip」这条补救**执行不了**
⇒ ⇒ 覆盖损失被**写成了「已登记」**，实际上一条都没跑。

## 处置

① **判据用车道脚本自己导出的环境变量**（一处真相源）：

```bash
# scripts/pytest_pg.sh —— E2E 车道 exec 进它 ⇒ ⇒ 一处生效、跨车道一致
export PCS_TEST_LANE=1
```

```python
# tests/conftest.py
def lane_is_active() -> bool:
    return bool(os.environ.get("PCS_TEST_LANE"))

def apply_default_lane_isolation() -> None:
    if lane_is_active():
        return          # ⚠️ 车道自带隔离 ⇒ ⇒ 不该被这层盖掉
    ...
```

② **判据放在**被测的**函数里**（不是只在 fixture 外层）⇒ ⇒
守卫能**直接调用**它 ⇒ ⇒ 断的是**行为**（「车道里有没有被改写」），
不是「fixture 里有没有那个 if」。

③ **守卫要断「认得出来的值」**：

```python
monkeypatch.setattr(settings, "redis_url", "redis://127.0.0.1:6379/0")
apply_default_lane_isolation()
assert settings.redis_url == "redis://127.0.0.1:6379/0"
```

⇒ ⇒ 断的是「**有没有被改写**」⇒ ⇒ 只断「是不是隔离值」会被
「本来就隔离」蒙过去（**假绿**）。

## 教训

- ⚠️ **「autouse」= 全局** ⇒ ⇒ 任何「为了 X 场景」的 fixture ⇒ ⇒
  ⇒ 要么**判作用域**，要么**换作用域**（不用 autouse）。
- ⚠️ **「覆盖损失」必须能被复核** ⇒ ⇒ 「已登记 TODO」不等于「TODO 可执行」
  ⇒ ⇒ 登记时要看一眼：**按那条 TODO 写，能不能真的把用例跑起来**。
- ⚠️ **守卫的判据要看「被改成了什么」**，不能只看「现在是不是隔离值」。

---

## 补记（2026-11-23 · F4-PRE · bug-2196）：**隔离必须挂在「收集期」**，否则默认车道照样摸开发库

### 现象

F2-T5 的隔离（同步引擎 ⇒ SQLite · Redis ⇒ 不可路由端口）落地后，
`TODO-164` 被判「F2-T5 已做隔离 ⇒ 该关闭」⇒ ⇒ **2026-11-23 实测：不成立**。

单跑这个文件（**默认车道**）：

```bash
uv run pytest tests/alembic/test_p9_013_bind_default_record_matrix.py -q
# → 7 passed
```

而这 7 条用例的 `_pg_url()` 读 `DATABASE_URL` / `.env` ⇒ ⇒ 那是**开发库 `pcs`**
⇒ ⇒ 默认车道在开发库里**建隔离 schema + 跑整条 alembic 链**（**DDL 写**）。

### 根因

**`pg` 标记的用例平时也会被默认车道收集并执行** —— `addopts` 只排除 `visual`：

```toml
addopts = "-m 'not visual'"
```

⇒ ⇒ `pg` 只是**一个标记**，不是**一道闸** ⇒ ⇒ 而 F2-T5 的隔离 fixture
只管**应用侧**（`_sync_engine` / `redis_url`）⇒ ⇒ **管不到用例自己 new 出来的
连接** ⇒ ⇒ 「不碰开发库」这件事**只在应用侧成立**。

### 处置

**闸门挂在收集期**（`pytest_collection_modifyitems`）—— 不是运行时：

```python
def pytest_collection_modifyitems(config, items):
    # ① 依赖真 Redis 的用例 ⇒ 自动标 pg（按 fixture 名 ⇒ 不会漏）
    for item in items:
        if "real_redis" in getattr(item, "fixturenames", ()):
            item.add_marker(pytest.mark.pg)
    if lane_is_active():          # 车道脚本导出的 PCS_TEST_LANE
        return
    skip_pg = pytest.mark.skip(reason="pg 专属用例 ⇒ 只能经 scripts/pytest_pg.sh 跑")
    for item in items:
        if item.get_closest_marker("pg"):
            item.add_marker(skip_pg)
```

⚠️ **为什么不是运行时 skip**：运行时 skip ⇒ ⇒ 默认车道**照样把连接建起来**
（只是最后跳了断言）⇒ ⇒ 库已经被摸了 ⇒ ⇒ 不算隔离。

⚠️ **为什么「自动标 pg」比「手写标记」好**：手写 ⇒ ⇒ 新增用例的人不会记得
⇒ ⇒ 覆盖又悄悄丢 ⇒ ⇒ 判据取**fixture 名** ⇒ ⇒ 一处生效。

### 效果

- **PG 车道 7 → 46 passed**（21 条真 Redis 用例 + 漂移守卫 + schema 断言）
- 默认车道**零连真 PG**（`pg` 用例在收集期就被 skip ⇒ ⇒ 连接压根没建）

### 教训（补）

- ⚠️ **标记 ≠ 闸门** ⇒ ⇒ 「这个用例属于某条车道」要用**机制**表达
  （收集期 skip / 车道脚本的 `-m` + fail-closed），不是靠标记的**语义**。
- ⚠️ **「已隔离」的结论要看「谁 new 了连接」** ⇒ ⇒ 应用侧隔离管不到
  用例自己建的引擎 ⇒ ⇒ 审计隔离时**要问「还有谁自己 new 客户端」**。
