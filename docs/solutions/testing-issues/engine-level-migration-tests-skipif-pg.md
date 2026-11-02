---
module: pcs-backend 测试 — alembic 引擎级测试（隔离 schema）
date: 2026-11-02
problem_type: testing_issue
component: testing_framework
severity: medium
symptoms:
  - "迁移里的 PostgreSQL 专属语义（`gen_random_uuid()` / `::jsonb` / `SELECT ... FOR UPDATE`）在单测里**从未执行过** —— 首跑就发生在生产"
  - "迁移的 `downgrade` 从未在任何引擎上执行过 ⇒ 降级路径的语法错误不可见"
  - "测试文件写着「CI 的 fresh-PG job 承担同口径验证」⇒ 下一个维护者以为 CI 在验 ⇒ 不补测试"
  - "隔离 schema 的 `DROP SCHEMA` 清理失败被静默吞掉 ⇒ 孤儿 schema 留在开发库里，而 DDL 已经落地"
root_cause: 单元测试跑在 SQLite 上（`sqlite+aiosqlite:///:memory:` + `SA_Base.metadata.create_all`）⇒ **从 ORM metadata 建表，不读迁移产物** ⇒ 迁移的 SQL 与 DDL 在单测里**根本不存在**；而本仓的 CI job（`check-api-drift`）只跑 `alembic upgrade head` / OpenAPI 导出与漂移检查 / 迁移幂等脚本 / 可视化渲染器测试 / 前端 typecheck，**一条后端 pytest 都不跑** ⇒ 引擎级测试在 CI 上永远 `pytest.skip` ⇒ 绿灯**证明不了**它们跑过
resolution_type: test_infrastructure_fix
framework_version: SQLAlchemy 2.0 / asyncpg / pytest-asyncio
related_components:
  - pcs-backend/tests/alembic/test_p9_013_bind_default_record_matrix.py
  - pcs-backend/tests/alembic/test_p9_014_record_approval_chain_snapshot.py
---

# 引擎级迁移测试：隔离 schema + 子进程 alembic（本仓无自动化 PG 通道）

## 形状

「这条迁移的 SQL 只能在 PG 上跑」（`gen_random_uuid()` / `::jsonb` /
`SELECT ... FOR UPDATE` / `DROP COLUMN` 的锁行为）⇒ 单测跑 SQLite ⇒ **测不到**
⇒ 只能另开一路：**隔离 schema + 子进程跑 alembic**。

```python
# ① 建隔离 schema（用**原** URL，不带 options）
subprocess.run([sys.executable, "-c", f'...CREATE SCHEMA {schema}...'],
               env={**os.environ, "BASE_PG_URL": url})

# ② 子进程里把 search_path 指过去，跑 alembic，再断言
script = f"""
os.environ["DATABASE_URL"] = re.sub(
    r"(\\?|$)", r"?options=-csearch_path={schema}\\1", os.environ["DATABASE_URL"], count=1
)
command.upgrade(cfg, "head")
"""

# ③ finally 里 DROP SCHEMA（**必须查返回码**）
```

## 三个最容易踩的坑

1. ⚠️ **子进程脚本里的 `{schema}` 必须用 f-string** —— 忘了 `f` 前缀 ⇒ PG 收到
   字面量 `CREATE SCHEMA {schema}` ⇒ `syntax error at or near "{"` ⇒ 而
   `finally` 里若还有一条 assert（清理失败），**它会顶掉**这条真正的错误 ⇒
   排查方向被带偏。⇒ **清理的判定放在 `try/finally` 之后**，别放 `finally` 里；
2. ⚠️ **`information_schema` 不受 `search_path` 约束** —— 查
   `information_schema.columns` 必须加 `table_schema = current_schema()`，
   否则 public 库的同名表列**跨 schema 相加** ⇒ 断言值随 public 的迁移状态
   漂移（测试写时 public 恰在旧版本 ⇒ 恰好绿；public 升级后必红）；
   普通表查询（`SELECT ... FROM signature_matrices`）受 `search_path` 约束，
   不受此影响 —— **两类查询别混用同一直觉**；
3. ⚠️ **断言留在本地、迁移在子进程** —— 断言要读**子进程跑完之后的库**，
   不是读本地 ORM 对象。

## 本仓的现状（2026-11-02）

⚠️ **本仓没有任何自动化作业跑引擎级测试**：CI 的 `check-api-drift` job
**不跑后端 pytest** ⇒ 这些测试在 CI 上永远 skip ⇒ **绿灯证明不了它们跑过**
⇒ 文档里写「CI 承担同口径验证」是**false delegation**（比没有测试更糟 ——
下一个维护者以为 CI 在验 ⇒ 不会去补测试）。

⇒ 需要验证时**手动跑**：

```bash
cd pcs-backend && uv run pytest tests/alembic/ -v
```

（本机有 PostgreSQL 时不 skip；没有则 skip —— skip 是**诚实的**，前提是
没人把 skip 当成「验过了」。）

## 教训

- 「这个验证由 CI 负责」这句话**必须**核对过 CI 的步骤清单才写得出来；
  本仓已因此产出一条**假的**QA 结论（详见
  [[guard-test-fooled-by-lying-comment]]）；
- 隔离 schema 的**清理**是测试的一部分，不是善后 —— 清理失败要**响亮**；
- 引擎级测试的价值在**降级路径**上（`downgrade` 从未跑过 ⇒ 它的语法错误
  永远不可见）⇒ 降级环必须也跑。
