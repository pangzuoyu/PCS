---
module: pcs-backend E2E 车道（tests/e2e_flows/）
date: 2026-11-17
problem_type: testing_issue
component: testing_framework / database
severity: high
symptoms:
  - "E2E 车道全绿，而同一份种子数据在生产上让端点 500：`asyncpg.exceptions.DataError: invalid input for query argument $9: 1 (expected str, got int)`"
  - "缺陷只在真库上炸：列是 VARCHAR、代码塞 int ⇒ PG 自己会转 ⇒ 车道（用 psycopg）静悄悄转了"
  - "车道的绿灯不携带任何信息 —— 它连「类型严格性」这一类缺陷都看不见"
root_cause: test_lane_driver_diverges_from_production_driver
resolution_type: test_and_source_fix
framework_version: pytest / SQLAlchemy 2.0 / asyncpg / psycopg 3
related_components:
  - testing_framework
  - database
  - driver
tags:
  - false-green
  - driver-parity
  - type-strictness
  - e2e-lane
---

# 测试车道的驱动必须与生产**同一个** —— 否则一整类缺陷隐形

## 1. 现象：车道绿、生产炸

P10-B 的流程级种子把 `version=1`（**int**）塞进
`report_definitions.version` —— 而该列是 **VARCHAR**（`app/models/report.py`）。
车道**全绿**，真库上端点 **500**：

```
asyncpg.exceptions.DataError: invalid input for query argument $9: 1 (expected str, got int)
```

## 2. 根因：两个驱动，两种严格性

车道的 `DATABASE_URL` 是 `postgresql+psycopg://` ⇒ 车道里**同步**部分用
psycopg（asyncpg 没有同步 API）⇒ ⇒ **异步**部分最初也用了 psycopg ⇒ ⇒
**libpq 让 PG 自己转换类型**（int → VARCHAR）⇒ ⇒ 缺陷隐形。

生产用的是 **asyncpg**（`app/db/session.py::_build_async_url` 把
`postgresql+psycopg://` 换成 `postgresql+asyncpg://`）⇒ asyncpg
**不做隐式转换** ⇒ ⇒ 同样一条 INSERT 立刻报错。

⇒ ⇒ **车道的严格性 < 生产的严格性** ⇒ ⇒ 「车道绿」**证明不了**类型类缺陷。

## 3. 形状（可复用）

> **测试车道的驱动必须与生产同一个。**
> 任何「更宽容」的地方（类型转换、隐式排序、NULL 容忍）都是缺陷的藏身处。

⇒ 车道的**异步**引擎统一用 **asyncpg**（`tests/e2e_flows/conftest.py::_async_url`）；
⇒ **同步**部分仍用 psycopg（asyncpg 没有同步 API）⇒ ⇒ 但同步部分只做
建 schema / 跑 alembic / 读 `alembic_version` ⇒ **不写业务数据** ⇒ 不受影响。

## 4. 连带的一条：asyncpg 不认 `options=-csearch_path=`

⇒ `TypeError: connect() got an unexpected keyword argument 'options'`
⇒ ⇒ 隔离 schema 走**启动参数**：

```python
connect_args={"server_settings": {"search_path": schema}}
```

（`search_path` 是 PGC_USERSET ⇒ 允许在启动包里设。）

⚠️ 这条与
`docs/solutions/database-issues/information-schema-not-scoped-by-search-path.md`
同源：**隔离 schema 靠的是 `search_path`，不是「连哪个库」**。

## 5. 怎么发现这类问题

⇒ 车道建好之后，**故意写一条类型不合的数据** ⇒ ⇒ 车道应当**当场红**
（而不是「绿着，等真库炸」）⇒ ⇒ 这就是「驱动一致性」的自检。
