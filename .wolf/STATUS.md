---
description: session handoff, regenerate with /handoff when a quest finishes
budget_tokens: 1200
---
# STATUS — PCS

> Read this FIRST when starting a session. Last updated: 2026-10-21（P9B-1 完成 + 最终评审修复）。
> 保持 <2k tokens。历史细节查 `git log` / `docs/` / `TODOS.md` / `.wolf/memory.md`。

---

## ✅ Done

### 第 10 轮：**P9B-1**（结果记录页 + 编辑锁前端）—— T0~T7 全完成

计划 `docs/PCS-PLAN-P9B-1-结果记录页与编辑锁.md`。commit `34134ae` → `2ddd85a`。

产出：**后端** `DeliverableResponse.current_version_id`（禁 N+1）· **前端**
`records.ts` 单一来源 · 三档基线 + 编辑锁 hook（60s 心跳、不重试）·
**通用结果页 + 6 个模块描述符 + 编辑抽屉**（6 类结果记录从零建）· 顶栏降级横幅 ·
变更影响的注册表键归一 · 观测/待办/实时三面板 · 交付物进度页 · QA gate
（浏览器回归 10 项 + MSW 三场景 + Playwright 一条）。

基线：前端 809 passed / 86 files；后端 5165 passed / 77 skipped；契约一致。
报告 `.gstack/qa-reports/qa-report-pcs-frontend-2026-10-21-p9b-1.md`（本地）。

本会话另修 bug-2041（HIGH · `p9_006` 在**全新库**上崩 ⇒ CI 红灯）、
bug-2042（HIGH · 降级 store 的 `setMessage` 是**空函数**）、
bug-2043（HIGH · 跨结果页残留上一模块的行）。

### 第 11 轮：**最终整支评审**（opus，范围 `a963a76..ed58075`）

结论 **1 Critical + 5 Important + 8 Minor**。Critical + Important **已修**
（commit `20a3cc6`），8 条 Minor 延后（`TODOS.md` **TODO-067**）。

| bug | 级别 | 一句话 |
|---|---|---|
| **bug-2044** | **CRITICAL** | 编辑抽屉**每个可编辑字段都显示空白** —— `Form.Item name` 用**表单 store 的值**覆盖了 `value`，而抽屉从不 `setFieldsValue` ⇒ store 空 ⇒ 全空。⚠️ **请求体仍是对的** ⇒ QA 断言请求体时看不见 |
| **bug-2045** | IMPORTANT | 409「放弃并刷新」不把新 hash 交回列表 ⇒ 下一次编辑必 409（假冲突） |
| **bug-2046** | IMPORTANT | SPA 导航让抽屉静默卸载 ⇒ 锁白占 30min（`pagehide` 只在**文档**卸载时触发） |
| **bug-2047** | IMPORTANT | `RealtimeStatusBanner` **没有任何宿主** ⇒ SPEC §6.23 实际没交付（组件只活在测试里 = 假绿） |
| **bug-2048** | IMPORTANT | 交付物列表 `pagination={false}` + 硬编码 `limit:100` ⇒ 超额**静默截断** |
| **bug-2049** | IMPORTANT | 变更影响判定失败 = 静默 no-op + **未捕获的 promise rejection** |

⚠️ **评审的 RF 表 13 行逐行核对**：12 行满足，RF-10「部分满足」（缺口 = bug-2046，已修）。
⚠️ **教训**：bug-2044 说明「断言请求体」**不等于**「断言界面」⇒ UI 的断言要落在
**渲染出来的值**上。

### P9B-2 计划已写好（**未执行**）

`docs/PCS-PLAN-P9B-2-签署流程与ADMIN前端.md` —— T0~T7：两个后端前置
（TODO-065 聚合进度端点 / TODO-066 编辑审计读端点）+ 记录操作栏 + 批注面板 +
状态时间线 + ADMIN 用户管理 + 审计日志（查询 + 导出）。
⚠️ **尚未过 `/plan-eng-review`** ⇒ 开工前建议过一轮。

---

## 🚀 Next quest

1. **P9B-2**：签署流程前端（操作栏 / 批注 / 状态时间线）+ ADMIN 前端（用户管理 /
   审计日志）+ **两个后端前置**（**TODO-065** 聚合端点 `GET /deliverables/{id}/progress`、
   **TODO-066** 按项目守卫的编辑审计读端点）⇒ 这两条**都已在 `TODOS.md` 登记**，
   触发条件写在条目里。
2. **P9B-3**：系统参数前端 + 物流手动创建向导 + 校对 UI。
3. **P9A-DLV-007**（TODO-057）：`SignatureMatrixService` +
   `change_notice_service.create_change_notice`（现 `NotImplementedError`）
   ⇒ workflow_progress 三工作流只能记 2/3。
4. **ADR-0050**：用户 2026-10-20 裁决「先不做」⇒ 再开工按 P1~P6。
5. **P9A-1 遗留**（未变）：access token 不带 `tv`；AD 同步需运维服务账号。

---

## Context

- main，工作区干净。**不要建 worktree**（历史事故）。
- 两库均在 `p9_007`（head），`alembic check` 均 exit 0（**每个库各跑一次**）。
  改迁移的纪律见 CLAUDE.md（退出码 **255**；先 `current` vs `heads`）。
  `pcs_test` 的跑法：URL 从 `.env` 派生，**不要把口令写在命令行**。
- **本机需要真 Redis** 才能跑锁的跨进程测试：`docker compose up redis`。
  没起 Redis 时那批测试会 **skip**（不是绿）。
- 契约产物由 G-08 钩子在 commit **之后**重生成，而 `git add` 在钩子之前
  ⇒ 偶尔漏提交，commit 后要 `git add -A && git commit --amend --no-edit` 补。
- ⚠️ **CI 现在是活的**（`.github/workflows/check-api-drift.yml`）⇒ **改了迁移必须
  在全新库上验**（本会话的 bug-2041 就是 dev 库看不见、只有 CI 全新库炸）。
  本机没权限建库 ⇒ 用**隔离 schema** 验（`search_path` + `alembic upgrade head`）。
- 无 CI/CD 的历史裁决已**部分过期**（CI 存在且会跑）；但**不要新增流水线**。
- 提交约定：conventional commits，**无 attribution 行**（本仓全局禁用）。
- ⚠️ commit message 里用 `!` `（）` 会被 shell 吃掉 —— 长消息写文件后
  `git commit -F <file>`。

---

## 教训（本会话新增 4 条，已进 cerebrum）

- **zustand 的初始化函数要把 `set` 接上**：`create(() => ({ …, setMessage: () => {} }))`
  ⇒ setter 是**空函数** ⇒ 状态永远存不进去 ⇒ 症状是「横幅不出现」而不是
  「文案不对」。⚠️ **单测直接 `setState` 会彻底掩盖它** ⇒ 守卫必须走 setter。
- **React Router 复用同类型组件实例 ⇒ state 会泄漏到下一个实例**：换模块时旧行
  留着，而新模块的主键名不同 ⇒ 取不到主键 ⇒ 一排 undefined key。⇒ 换「模块」
  这种**数据形状变了**的场景要 `key={module}`（整页重建）+ 换时先清空。
- **只测一个实例 ⇒ 跨实例那条路径根本没被走到**：本会话的跨模块 bug 就是
  「单模块用例全绿」漏出来的。⇒ 通用组件**至少测两种形状**。
- **迁移里跑 ORM 查询 ⇒ ORM 后加的列会把老迁移打破**（且**只在全新库**炸）：
  dev 库在迁移写好之前就应用过它 ⇒ 天然免疫。⇒ 迁移里**不要**用 ORM 实体查询
  整表（要按**此刻 DB 实际存在的列**裁剪 SELECT）。
