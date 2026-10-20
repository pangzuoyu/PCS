---
description: session handoff, regenerate with /handoff when a quest finishes
budget_tokens: 1500
---
# STATUS — PCS

> Read this FIRST when starting a session. Last updated: 2026-10-20（P9A C lane 收口 + 终审修复）。
> 保持 <2k tokens。历史细节查 `git log` / `docs/` / `TODOS.md` / `.wolf/memory.md`。

---

## ✅ Done

### 第 7 轮（本会话）：P9A-3「通知待办」lane（C0→C4）落地 + 终审修复

9 笔 commit（`397bd52`→`a996577`），全部在 main。

| task | 产出 |
|---|---|
| C0 | `notifications` 表（10 列，`p9_005`）+ 2 个索引 + 21 例 |
| C1 | `NotificationChannel` 协议 / `InAppChannel` / `NotificationDetail` + 16 例 |
| **C1b** | **触发接线（用户裁决增补）+ `notify()` 唯一写侧入口** |
| C2 | Redis pub/sub broadcaster + WS 端点 + 断线兜底 API + `/health` realtime + 21 例 |
| C3 | ARQ 清理任务（只删已读、`max_tries=2`）+ 9 例 |
| C4 | 待办实时计算，**不建表** + 14 例（300 交付物 195ms / 重算 12.4ms） |
| 终审 | fresh reviewer 10 findings → 修 F-1~F-9（bug-2030~2034） |

**基线**：后端 **5005 passed / 77 skipped / 0 failed**（原 4868，+137）；前端 704 passed；
两端 typecheck + lint clean；裸字段仍 **71**；两库均在 `p9_005`（head），
`alembic check` 均 exit 0 且**守门真的跑了**。

### 用户 2026-10-20 的两条裁决（已落地 + 回写 ADR-0049）
1. 通知写侧**同步**（ADR §① 原「未锁」→ 已回补，含「同一次提交、同一套事务边界」）。
2. 触发源接线**最小集合**：sign-step 成功 / 退回 / proxy 代录 / 变更单审批。

### 终审抓到并修掉的（每条都有 RED→GREEN 守卫）
- **双 commit + 提交前推送** ⇒ phantom notification。改成「只写不提交 → 一次提交 → 再推」。
- **最后一步 sign-step（转 APPROVED）不通知任何人** ⇒ 补通知版本提交人。
- **subscribe 失败泄漏 PubSub + Redis 连接**；**pump 遇 Redis 抖动静默死亡**
  ⇒ 后者让该用户推送**永久失效且不报错**（TODO-047 / bug-2027 同形状）⇒ 自愈重连。
- **`to_detail` 不兜 ValidationError** ⇒ 将来改 schema 一次，整个列表端点 500。
- **收件人越权**：原本只看全局角色、不看项目授权 ⇒ 收到带交付物标题的他人项目通知。

---

## 🚀 Next quest

1. **P9A-4「编辑锁与 CIA」lane（D0→D3）** —— **D1 必须在 B 之后**（B 已完成，可开工）。
   读 `docs/PCS-PLAN-P9A-4-编辑锁与CIA.md`。D0 迁移与 A/B/C 并行不冲突；
   注意 `RECORD_TYPE_REGISTRY` 里 `CostEstResult` **没有 `record_hash` 列**（TODO-048）。
2. **Z 收口**（OpenAPI 冻结 + 全量回归）—— 等 D lane 完成。
3. **需要用户裁决的一条**：**TODO-059**（新登记）—— 签署矩阵的 `sign_role` 是
   **全局角色**（`sign_step` 拿 token 的 role claim 比），而
   `user_projects.role_in_project` 在签署链路上**没有消费方**。本 lane 已把
   通知/待办对齐到**已实际执行**的口径（全局角色 ∩ 项目授权），但「矩阵该
   对齐哪一套」是产品口径问题 —— 改它要动 `sign_step` 与矩阵数据契约，
   属行为变更。三个选项见 `TODOS.md`。
4. **P9A-1 的遗留项**（未变）：access token 不带 `tv`（停用后在手 access 仍可用至过期）；
   AD 同步需服务账号 `LDAP_BIND_DN`/`LDAP_BIND_PASSWORD`/`LDAP_USER_FILTER`/`LDAP_USER_ATTRS`
   —— 运维给账号前 P9A-USR-002/003 只算**代码就绪**，不算验收通过。
   整体验收时标「代码就绪，待运维账号」，**不得标「通过」**。

---

## Context

- main，工作区干净。**不要建 worktree**（历史事故，见上轮 STATUS）。
- 两库均在 `p9_005`（head），`alembic check` 均 exit 0。改迁移的纪律见 CLAUDE.md
  （退出码 **255**；先 `current` vs `heads`；**每库各跑一次**；
  ⚠️ 闸门在 DB 落后时会 exit 0 但**根本没跑** —— 2026-10-20 又撞了一次）。
  `pcs_test` 的跑法：URL 从 `.env` 派生（`DATABASE_URL` 改库名），
  **不要把口令写在命令行**（会被权限分类器拦）。
- **本机需要真 Redis 才能跑 C2 的跨进程推送测试**：`docker compose up redis`。
  没起 Redis 时那批测试会 **skip**（不是绿）—— 看输出别误读。
- 契约产物由 G-08 钩子在 commit **之后**重生成，而 `git add` 在钩子之前
  ⇒ 偶尔漏提交，commit 后要 `git add -A && git commit --amend --no-edit` 补。
- 无 CI/CD（单人开发裁决，勿再建议）。本地 gate 走 `.githooks/`。
- 提交约定：conventional commits，**无 attribution 行**（本仓全局禁用）。
- ⚠️ commit message 里用 `!` `（）` 会被 shell 吃掉 —— 长消息写文件后
  `git commit -F <file>`。

---

## 教训（本会话新增）

- **「同一个真相源」不等于「同一个口径」**。收件人解析与待办解析共用了一个
  helper，却**方向相反**：一个解析「全体用户里谁有这角色」，一个解析
  「我有没有这角色」⇒ 通知越权、待办缺项。共用 helper 只防了「抄两份」，
  没防「同一份用出两个意思」。
- **注释与代码字面冲突，是 bug 的气味**。`_notify_sign_outcome` 里我写着
  「本行自身不再 commit」，代码却 commit 了 —— 终审第一个 finding 就是它。
  注释写下的意图比注释本身更值得当断言用。
- **「守卫测试」要能对旧代码变红**。「notify 不自己提交」那条对着旧代码也绿
  （旧代码的 commit 在调用方）⇒ 真正的守卫必须落在**调用方**的提交次数上，
  而且场景要让通知**真的发出去**（没人可通知时第二次 commit 压根不发生）。
- **实测会推翻计划的前提**。计划写「部分索引是 500ms 指标的全部支撑」，
  真库 EXPLAIN 证明**不成立**（ORDER BY created_at ⇒ 排不了序 ⇒ 用的是
  另一个索引）。⇒ 「建了索引」不等于「被用上了」；空表上的 EXPLAIN
  更是什么都证明不了。
- **我曾把自己发现的泄漏判成「不是 bug」**（先按「全局 ∪ 项目内」实现，
  事后才按 `sign_step` 的**实际执行口径**改成「全局 ∩ 项目授权」）。
  判据应当是**系统实际执行的那条路径**，不是我以为的语义。
