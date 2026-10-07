---
description: session handoff, regenerate with /handoff when a quest finishes
budget_tokens: 1500
---
# STATUS — PCS

> Read this FIRST when starting a session. Last updated: 2026-10-07.
> 保持 <2k tokens。历史细节查 `git log` / `docs/` / `TODOS.md` / `.wolf/memory.md`。

---

## ✅ 本会话完成

**迁移守门从"坏"修到"能说真话"** —— 这是本会话的主线，其余都是它的产出。

1. **幂等闸门长期假绿**（`eb528ba`）：`check_migration.py` 用「行内子串 + 上下 8 行窗口」
   判 guard，`p7_s3_005` 的 `downgrade()` docstring 里写着「删两张子表 (if_exists 幂等)」，
   窗口里的 `if_exists` 掩盖了下面两行**实际没带** guard 的 `op.drop_table`。改 AST 判定。
   另发现 `SAFE_OPS` 把 `create_unique_constraint` 映射为需 `if_not_exists` 是**错的**
   ——alembic 1.19.1 该签名无此形参，传了被 `**kw` 静默吞掉。已移出检查范围。
   补 guard 共 **49 处**，检查范围从 4 个前缀白名单收敛为全部 **30 个 `p7_*`**。
2. **bug-143**（`89ae1b3` / `p7_s5_006`）：`user_projects.created_by` ORM 有 DB 无 →
   真库上项目授权**必失败**（`UndefinedColumn`）。根因是手写 `op.create_table` 逐列抄写
   漏了 mixin 继承列。已应用并复验（失败原因正确转为 `ForeignKeyViolation`）。
3. **bug-144**（`29a30b8` / `p7_s5_007`）：`user_projects` **4 个外键从未建出** ——
   建表迁移把裸 `sa.ForeignKey(...)` 当位置参数传给 `op.create_table`，被**静默丢弃**。
   该表是 BLOCKER-3 IDOR 守卫读的表。已应用。
   写 FK 时踩到 PG 的坑：未加引号的 `REFERENCES users.user_id` 报
   `InvalidSchemaName: schema "users" does not exist`（临时表上也复现），
   函数式 `REFERENCES users(user_id)` 正常 → 改走 `op.create_foreign_key`。
4. **COMMENT 比对关闭**（`cca173a`，用户裁决）：`alembic check` **397 → 43 条**。
   注释比对**不走 `include_object`**（先按它实现并实测确认无效），真正机制是 alembic
   1.18+ plugin，最终从 `_all_plugins` 摘掉 `alembic.autogenerate.comments`。
   代价：注释漂移不可见 + autogenerate 不再生成 COMMENT，已写进 env.py docstring。
5. **漂移口径第三次修正**：真实 397 条（先前报的 84 / 350 都错）。
   根因是**用关键词白名单过滤 `compare_metadata` 输出**，alembic 实际 op 名是
   `add_fk`/`remove_fk` 而非 `add_foreign_key`，匹配不上的类别被静默丢弃而总数看着正常。

## ✅ 早前已完成（细节查 git log）

CORS middleware、auth 安全三条（限流 + 审计 + JWT 过期细分）、`equipment_lib` 死表删除、
`app/models/__init__.py` 漏 import util、CATEGORY_6 设备库地基 4 项、CI 首次全绿。

---

## 🚀 Next quest

**`alembic check` 剩 43 条**（`TODOS.md` 有明细表）：

| 项 | 条数 | 性质 |
|---|---|---|
| `remove_constraint` | 39 | **28 CheckConstraint + 11 UniqueConstraint**，DB 有、ORM 未声明。DB 更安全，纯声明缺失。补 ORM `__table_args__` 零迁移成本 |
| `add_constraint` | 1 | `uq_compound_api521_thresholds_threshold_type` ORM 有 DB 无 |
| `add_fk`/`remove_fk` | 2 | 同名 `fk_utility_energy_summary_workspace_id_workspaces`：**DB=CASCADE vs ORM=RESTRICT** —— **需业务裁决**（删项目时是否连带删能耗汇总） |
| `add_fk` | 1 | `fk_projects_workspace_id`（`use_alter=True` 延迟外键，通常后续迁移才建） |

**其他开放项**：`TODOS.md` 的 TODO-028（10 表主键 rename）/ 032（27 个真库测试迁 SQLite）/
039、041（前端类型唯一性、MSW 契约冻结，已逾期约 20 天）/ 014、015、023；
CATEGORY_6 第 5 项（审批语义，需产品裁决）。

---

## Context

- main，工作区除 `.wolf/*`（钩子维护）外干净。**不要建 worktree** —— 历史事故见 git log。
- 全量基线：**3954 passed / 77 skipped / 1 xfailed / 0 failed**（3m36s）。
  单测跑内存 SQLite，**不需要** `alembic upgrade head` 前置；
  但 `tests/test_schema.py` 连**真实 Postgres**，改迁移后必须真跑。
- **守门现状**：幂等闸 `OK: 0 violations in 30 p7_* migrations`；
  `alembic check` 退出码 **255**（不是 1）表示检出漂移。
- ⚠️ **`grant_project_access` 在真库上仍会失败** —— 现在报 `ForeignKeyViolation`（正确行为），
  因为 `users` 与 `projects` 都是 0 行。`users` 要等 P9 的 AD 同步才有行
  （`P9-ADM-001`「同步后自动创建系统用户记录」）。**BLOCKER-3 IDOR 守卫在有真实数据
  前无法端到端验证**，P7 收尾 / P9 联调时必须知道。
- 无 CI/CD（单人开发裁决，勿再建议）。

---

## 教训（已写入 `TODOS.md` / `buglog`）

- **闸门恒绿与恒红一样可疑。** 本会话两次抓到闸门自己的 bug（字符串窗口判 guard、
  `create_unique_constraint` 的 guard 根本不存在）。查 guard 是否可信，和用 guard 一样重要。
- **过滤 `compare_metadata` 输出前，先打印真实的 op 名分布**，不要凭直觉写白名单 ——
  匹配不上的会被静默丢弃，而总数看起来仍然「合理」。同一根因已犯三次。
- **「守门没报」可能只是因为它根本没跑。** bug-143/144 藏了这么久，
  直接原因是有一个已提交但未应用的迁移让 `alembic check` 整个拒跑。
- **迁移里手写 `op.create_table` 必查两件事**：mixin 继承的列有没有漏（bug-143）、
  外键是不是写成了裸 `sa.ForeignKey` 位置参数（bug-144，静默丢弃不报错）。
- **登记缺陷前跑最小复现**，别从 code 注释或 ORM 声明推断真库状态。
- docstring 首行用 ASCII `.`，全角 `。` 触发 ruff D400/D415。
- 核验别用组合正则；`git status` 之类被 rtk 过滤层改写时，用 `rtk proxy` 拿原始输出。