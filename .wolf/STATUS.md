---
description: session handoff, regenerate with /handoff when a quest finishes
budget_tokens: 1500
---
# STATUS — PCS

> Read this FIRST when starting a session. Last updated: 2026-10-21（P9A Z 收口完成 + 生产崩溃修复）。
> 保持 <2k tokens。历史细节查 `git log` / `docs/` / `TODOS.md` / `.wolf/memory.md`。

---

## ✅ Done

### 第 9 轮（本会话）：**P9A Z 收口**（全 lane 收尾）—— P9A 至此完成

commit `99948d7` → `0fa461f`（4 笔）。

| 产出 | 内容 |
|---|---|
| **SPEC 欠账补写** | ADR-0047 §后果 / ADR-0049 §⑥ 承诺的 `P9A-OBS-001~004` / `P9A-NOT-001~006` **十条**（两版 SPEC 都登记为欠账，至今 0 命中）⇒ UI-SPEC **V2.1**：§6.22 TodoPanel / §6.23 RealtimeStatus / §6.24 WorkflowProgressPanel + §6.20 扩写 |
| **验收登记** | P9 SPEC **V2.1 §7.2.1**（实测状态表，**不改** §7.2 的验收标准）。状态只有三档：✅ 通过 / ⚠️ 代码就绪待运维账号 / ⚠️ 部分（记明缺哪一项） |
| **OpenAPI 冻结** | baseline 滚动至 `p9_007` 终态（**+60 path / +105 schema / 0 删除**）；裸字段仍 **71**（未升未降） |
| **补验收证据** | 通知 ≤500ms **此前零断言** ⇒ 新增 `test_notification_list_budget.py`（2800 行）；`test_observed_p99_under_500ms` 的 **parametrize 是装饰性的**（三类实际只跑 SIGN）⇒ 修 |
| **修生产崩溃** | **bug-2040（CRITICAL）**：P9A 交付真 `/notifications` 后，前端仍按自造数组消费 ⇒ 生产构建下 `MainLayout` 整个壳崩（`notifications.filter is not a function`）⇒ 前端按契约重绑 + mock 同形 + 守卫 |

**基线**：后端 **5157 passed / 77 skipped / 0 failed**（+2）；前端 **725 passed**（+9，75 files）；
两端 typecheck + lint clean；两库均在 `p9_007`（head），`alembic check` 均 exit 0；
浏览器回归 10 项全过（报告 `.gstack/qa-reports/qa-report-pcs-frontend-2026-10-21-p9a-z-closeout.md`）。

### 前一轮（第 8 轮）：P9A-4「编辑锁与 CIA」lane 全 lane 完成（D0→D3）

`b4470e0`→`bbb4a37` + 安全修复 `b22d0bd`。Redis 锁三端点 / 409 契约 + 编辑审计 /
CIA 哈希判定分流。**bug-2039（越权洞）** 同期修复。

---

## 🚀 Next quest

1. **P9B-1（下一条 lane）**：前端接 §6.21 / §6.7.1 —— 编辑锁 UI（取锁 / 60s 心跳 /
   他人持锁只读化 / 降级横幅）、409 弹窗（按 basis 三值分流）、PATCH 回传
   `expected_hash`、ChangeImpactPanel 的「确认」动作、**6 个结果页**（从零建）。
   计划 `docs/PCS-PLAN-P9B-1-结果记录页与编辑锁.md` —— **已过 `/plan-eng-review`
   + 决策委员会复审**（2026-10-21，commit `86bc4fc`），**T0~T7 七个任务可直接开工**。
   ⚠️ 计划里两条最容易漏的：**基线分三档**（hash 空 ⇒ 退到 `expected_updated_at`；
   两档皆无 ⇒ 该行不可编辑）+ **基线时间戳原样透传**（过 `new Date()` ⇒ 微秒丢失
   ⇒ 每次假 409）。这两条都有守卫测试（RF-8 / RF-9 / RF-13）。
   ⚠️ 计划表里的 `record_type` **写错了 3 个**（写 `CoolingTowerResult` 等类名，
   实际注册表键是 `cooling_tower_result` 等 snake_case）⇒ 以
   `src/api/locks.ts::EDITABLE_RECORD_TYPES` 为准。
   ⚠️ **本会话补写的 §6.22~§6.24 是它的输入**（待办 / 实时状态 / 观测进度面板）。
   ⚠️ **开工前跑一次浏览器回归**（Per-Batch QA Gate）。
2. **P9A-DLV-007**（TODO-057）：`SignatureMatrixService` +
   `change_notice_service.create_change_notice`（现 `NotImplementedError`）
   ⇒ workflow_progress 三工作流只能记 2/3。**不占 P9A 验收**（已按措辞登记）。
3. **ADR-0050**：用户 2026-10-20 裁决「先不做」⇒ 不实施；再开工按 P1~P6。
4. **P9A-1 遗留**（未变）：access token 不带 `tv`；AD 同步需运维服务账号
   ⇒ P9A-USR-002/003 只算**代码就绪**，不得标「通过」。

---

## Context

- main，工作区干净。**不要建 worktree**（历史事故）。
- 两库均在 `p9_007`（head），`alembic check` 均 exit 0（**每个库各跑一次**）。
  改迁移的纪律见 CLAUDE.md（退出码 **255**；先 `current` vs `heads`；
  闸门在 DB 落后时会 exit 0 但**根本没跑** —— 2026-10-20 又撞了一次）。
  `pcs_test` 的跑法：URL 从 `.env` 派生，**不要把口令写在命令行**。
- **本机需要真 Redis** 才能跑 C2/D1 的跨进程测试：`docker compose up redis`。
  没起 Redis 时那批测试会 **skip**（不是绿）。
- 契约产物由 G-08 钩子在 commit **之后**重生成，而 `git add` 在钩子之前
  ⇒ 偶尔漏提交，commit 后要 `git add -A && git commit --amend --no-edit` 补。
- 无 CI/CD（单人开发裁决，勿再建议）。本地 gate 走 `.githooks/`。
- 提交约定：conventional commits，**无 attribution 行**（本仓全局禁用）。
- ⚠️ commit message 里用 `!` `（）` 会被 shell 吃掉 —— 长消息写文件后
  `git commit -F <file>`。

---

## 教训（本会话新增 5 条，已进 cerebrum）

- **mock 是契约的替身，不是它的装饰**。mock 返回自造形状 ⇒ 漂移被藏住 ⇒
  **只有生产构建才炸**（dev 恒挂 MSW）。⇒ 契约端点的 mock 响应体一律用
  ajv 对着 OpenAPI 校验；「mock-only 名单」会过期，端点后来有了契约
  ⇒ 名单**不会自己更新**（已加**棘轮**守卫）。
- **类型断言不是运行时检查**。`as Notification[]` 只骗编译器 ⇒ 崩点出现在
  **下一行**（`notifications.filter`），报错**不指向**真正的原因。
- **验收标准里写着的指标，没有自动化断言 = 没验收过**（通知 ≤500ms 缺了
  整整一季）。补性能断言要：① 造到预期数据量 ② 断言能对旧代码变红
  （`after` 切点取「切出条数 < limit」处，否则过滤被忽略时也绿）。
- **参数化可能装饰了一个从未生效的变量**（helper 里写死 `WorkflowType.SIGN`
  ⇒ 三类用例只跑了一类，而 docstring 说「三类逐类」）。
- **「实现完成」≠「验收通过」**：收口时要把验收标准**逐条对上一条自动化
  断言**，对不上的要么补断言，要么在验收表里写明「无自动化验收」。
