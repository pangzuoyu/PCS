---
module: pcs-backend 测试 — alembic 隔离 schema 的元数据查询
date: 2026-11-02
problem_type: database_issue
component: database / introspection
severity: medium
symptoms:
  - "隔离 schema 里查 `information_schema.columns` 得到的列数**比预期多** —— public 库的同名表也被数进来"
  - "断言值随 **public 库的迁移状态**漂移：public 停在旧版本时恰好绿，public 一升级就必红"
  - "同一个查询在隔离 schema 与 public 上跑出**不同的计数**，但 SQL 一模一样"
root_cause: "`information_schema` 是**标准视图**，**不受 `search_path` 约束** ⇒ `WHERE table_name = 'x'` 会跨**所有** schema 匹配；`search_path` 只约束**普通表名解析**（`SELECT ... FROM x`）。⇒ 隔离 schema 测试里必须按 `table_schema = current_schema()` 限定，否则计数跨库相加"
resolution_type: query_fix
framework_version: PostgreSQL 18 / SQLAlchemy 2.0
related_components:
  - pcs-backend/tests/alembic/test_p9_013_bind_default_record_matrix.py
  - pcs-backend/tests/alembic/test_p9_014_record_approval_chain_snapshot.py
---

# `information_schema` 不受 `search_path` 约束 —— 隔离 schema 测试的隐形跨库计数

## 形状

隔离 schema 测试（见 [[engine-level-migration-tests-skipif-pg]]）里要问
「这张表有没有某列」。直觉写法：

```sql
SELECT count(*) FROM information_schema.columns
WHERE table_name = 'deliverables' AND column_name = 'parent_deliverable_id'
```

⇒ **错**。`information_schema` 是**标准视图**，它的 `table_schema` 维度
**不由 `search_path` 决定** ⇒ 这条 SQL 会把 **public 库里同名表的列也数进来**
⇒ 隔离 schema 里的计数 = 隔离 schema 的 + public 的。

## 为什么难发现

⚠️ **`search_path` 确实约束普通表名解析**（`SELECT ... FROM signature_matrices`
在隔离 schema 里查到的是隔离 schema 的表）⇒ 直觉会说「search_path 已经把我
限定住了」⇒ 而元数据视图是**另一套规则** ⇒ 两类查询**长得一样、行为不同**
⇒ 混用同一直觉 ⇒ 静默错。

⚠️ 而且错法**不是恒错**：断言值随 **public 库的迁移状态**漂移 ——
写测试时 public 恰在旧版本 ⇒ 断言值恰好对 ⇒ 绿；哪天 public 升级了 ⇒
计数变了 ⇒ 测试**变红**，而红的原因离真因很远。

## 修法

```sql
SELECT count(*) FROM information_schema.columns
WHERE table_schema = current_schema()      -- ⚠️ 这一句不能少
  AND table_name = 'deliverables'
  AND column_name = 'parent_deliverable_id'
```

`current_schema()` = 当前 `search_path` 的**第一个**存在的 schema ⇒ 与
`search_path` 语义一致 ⇒ 隔离 schema 隔离 schema。

## 判定规则（记住这一条就够）

| 查询类型 | 受 `search_path` 约束？ | 要不要加 schema 限定 |
|---|---|---|
| 普通表（`SELECT ... FROM t`） | **是** | 不用 |
| `information_schema.*` | **否** | **必须** `table_schema = current_schema()` |
| `pg_catalog.*` | **否**（按 OID 走） | 视情况 |

## 教训

- 「隔离 schema」这个隔离**只对普通表名解析成立** ⇒ 用**元数据视图**做断言时
  必须**显式**限定 schema，否则隔离是假的；
- 断言值**依赖外部状态**（public 的迁移进度）的测试 = **时炸弹** ⇒ 写完
  立刻去把 public 也升级一遍，看它还绿不绿 —— 这就是本条被发现的经过。
