---
description: session handoff, regenerate with /handoff when a quest finishes
budget_tokens: 1200
---
# STATUS — PCS

> Read this FIRST when starting a session. Last updated: 2026-10-27（P9A-DLV-011 **收尾批 #2**：TODO-088/089/090 + 「逃生口」）。
> 保持 <2k tokens。历史细节查 `git log` / `docs/` / `TODOS.md` / `.wolf/memory.md`。

---

## ✅ Done

### 第 16 轮：**P9A-DLV-011 收尾批 #2**（用户「顺序解决 1-4 未解决问题」）

| commit | 内容 |
|---|---|
| `3640a5c` | **TODO-088** —— 6 条约束按 **schema** 补齐（迁移 `p9_011`：判据 `connamespace = current_schema()::regnamespace`） |
| `1022a2c` | **TODO-089** —— 两个 `PcsError` 变体**合并成一个类**（service 侧变**别名**；基类同时吃 service / core 两种调用风格；全局 handler 2 → 1） |
| `9b445ba` | **TODO-090** —— `locked_by_deliverable` 列**写成派生标记**（变更单 APPROVED 时写 True；判据与门禁同口径） |
| `80c3bdc` | 上批前端用例的回调类型写错 ⇒ `typecheck` 红（QA 闸门拦下） |
| `ab207b6` | **TODO-082 已知代价的「逃生口」**：CHANGE_REVERSAL 反向变更单**端到端**钉住 |

**四件「不是代码风格问题」的修法**（本轮全部按「真实可判定」重做）：

1. **TODO-088**：迁移的幂等检查**只按名字**查 `pg_constraint` ⇒ **不分 schema**
   ⇒ 隔离 schema 上永远拿不到那 6 条约束（而真·全新库不受影响 ⇒ CI 一直是绿的）。
   ⇒ **不改历史**，用新迁移 `p9_011` 按 **schema** 补齐。
2. **TODO-089**：`except service.PcsError` 捕不到 core 抛的错 ⇒ 业务错误**静默变
   500**。⇒ 「让子类继承」只解决**一个方向** ⇒ 必须**合并成一个类**。
3. **TODO-090**：该列**既无写入方**也不是门禁 ⇒ 读端**恒报 False** ⇒ 前端拿到
   一个**永远为假的字段**。⇒ 选**写它**（不删列）：判据与门禁**完全一致** ⇒
   不会分叉；APPROVED 是终态 ⇒ 不会变成「陈旧的 True」。
4. **逃生口**：TODO-082 的代价「告知」了用户，但**没人证明替代路真的通** ⇒ 端到端
   用例钉住（普通撤销被拒 ⇒ 消息点名 `CHANGE_REVERSAL` ⇒ 反向变更单**建得出来**
   ⇒ 签完记录回 `CHECKED`）。

**验收**：后端 `pytest -q` **5308 passed / 77 skipped / 1 xfailed / 0 failed**；
前端 typecheck / lint exit 0、`vitest run` **840 passed / 91 files**；
两库 `pcs` / `pcs_test` 均在 **`p9_011`**（head）· `alembic check` 各 **exit 0**。

### 第 15 轮：**P9A-DLV-011 欠账清理批**（TODO-073/074/075/076/082/085 + 前端接线 + 快照加固）

`5416e5f` TODO-073（变更单编号走模板）· `e8d34c8` TODO-074（矩阵同名同状态唯一）
· `334e140` TODO-075 · `4487475` TODO-076 · `50c3e28` TODO-082 · `6febab1` TODO-085
· `30df88e` 前端「作废变更单」入口 · `a551fc1` 快照列清单自动推导 · `66dba93` 批末
用例迁移 + bug-2088（审计 `resource_id` 恒空串）。
**业务裁决（用户 2026-10-27）**：①「已对外生效」的门 ⇒ 换成**真实可判定的条件**
（**已知代价**：批准后不能再走普通撤销 ⇒ 第 16 轮已钉住逃生口）；②矩阵修改的
**申请+双审** ⇒ **本项目不做**。

---

## 🚀 Next quest

1. **P9B-2**：签署流程前端（操作栏 / 批注 / 状态时间线）+ ADMIN 前端（用户管理 /
   审计日志）+ **两个后端前置**（**TODO-065** `GET /deliverables/{id}/progress`、
   **TODO-066** 按项目守卫的编辑审计读端点）。
   ✅ 计划 `docs/PCS-PLAN-P9B-2-签署流程与ADMIN前端.md` **已于 2026-10-27 过
   `/plan-eng-review`**（commit `694ba21`）⇒ 追加 **9 条裁决**（R-11~R-19）⇒
   任务 **T0~T10**（新增 T2 批准链推导 / T8 交付物级签署写面 / T9 TODO-067
   七条）⇒ **开工前先读计划的「2026-10-27 复审裁决」节**（与正文冲突时以它为准）。
   ⚠️ 复审的核心发现：计划写于 2026-10-21，**R-1 / R-3 / R-6 的前提已全部失效**
   （P9A-DLV-011 落了矩阵管理面 + 变更单链路）⇒ 原样开工会做出**三个永远点不动
   的按钮** + 一个**永远查不到**的聚合段。
2. **P9B-3**：系统参数前端 + 物流手动创建向导 + 校对 UI。
3. **本批仍开着**：**TODO-073~090** ⇒ **全部闭环**；剩下的开放项见 TODOS.md
   （TODO-065 / TODO-066 / P9B-1 的 7 条 deferred minor / 迁移幂等守门的 93 个
   历史文件盲区 / 57 个手写类型与生成 schema 同名的长期债）。
4. **ADR-0050**：用户 2026-10-20 裁决「先不做」⇒ 再开工按 P1~P6。

---

## Context

- main，工作区干净。**不要建 worktree**（历史事故）。
- 两库均在 **`p9_011`**（head）· `alembic check` 两库各 exit 0（退出码 **255** = 真
  漂移；先 `current` vs `heads`；`pcs_test` 的 URL 从 `.env` 派生，**不要把口令写在
  命令行** —— 用 `uv run python` 在**进程内**改 `DATABASE_URL`）。
- ⚠️ **CI 现在是活的**（`.github/workflows/check-api-drift.yml`，全新 Postgres）⇒ 改了
  迁移必须**在全新库上验**（本机用隔离 schema：`options=-csearch_path=<schema>`；URL
  里**不能有 `%`**）—— ✅ TODO-088 之后，那个隔离 schema 从零 `upgrade head` ⇒
  **6 条约束都在** ⇒ `alembic check` **exit 0**（此前是 6 条**假漂移**）。
- **Redis**：跨进程/锁的测试需要真 Redis（`docker compose up -d redis`）。
- 契约：批末滚 `pcs-backend/docs/openapi-baseline.json`（前端 snapshot / api.d.ts 由
  `gate_08_openapi_contract.sh` 重生成）⇒ 本轮**无契约变化**（247 path / 349 schema）。
- 提交约定：conventional commits，**无 attribution 行**；长消息写文件后
  `git commit -F <file>`。
- ⚠️ **API 测试的 `client` fixture 把 `check_user_project_access` mock 成恒 True** ⇒
  **项目授权（404）在 API 测试里测不了** ⇒ 要测 404 必须用 `_guard_client`。
- ⚠️ **in-memory SQLite 的 StaticPool 让 `db` 与独立 client 共用同一条连接** ⇒ 独立
  client 退出时的 rollback 会把 `db` 这边**未提交**的 INSERT 一起回滚 ⇒ 造完 fixture
  必须先 `await db.commit()`。

---

## 教训（本批新增，已进 cerebrum）

- **同名 ≠ 同一个类**：两个同名 `PcsError` ⇒ `except` 捕不到 ⇒ 业务错静默变 500。
  「让子类继承」只解决**一个方向** ⇒ 要双向可捕，必须**合并成一个类**。
- **判据变严 ⇒ 必须配「逃生口」**：被挡的人还有哪条路？那条路**通不通**？只测
  「门拒了」不够 —— 那正是「代价 = 死路」时的样子。
- **派生标记必须照真相字段写**：`close_on_approved` **不**把单推成 APPROVED（那是
  `sign_step` 的动作）⇒ 标记照 `deliverables.sign_status` 写，否则列与门禁
  **两个真相**。
- **计划也会过期**：P9B-2 的计划写于 2026-10-21 ⇒ 6 天后复审发现**三条前提全部
  失效**（中间那批落地了矩阵管理面 + 变更单链路）⇒ **开工前先核对计划的「事实
  基础」**（逐条查代码，别信文档）⇒ 一份计划的「已交付/未交付」清单比计划本身更
  先过期。
