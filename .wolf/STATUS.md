---
description: session handoff, regenerate with /handoff when a quest finishes
budget_tokens: 1200
---
# STATUS — PCS

> Read this FIRST when starting a session. Last updated: 2026-10-28（**P9B-2 延后的 minor 批 B~F 全落地**；上批：P9B-2 全批收口）。
> 保持 <2k tokens。历史细节查 `git log` / `docs/` / `TODOS.md` / `.wolf/memory.md`。

---

## ✅ Done

### 第 19 轮：**P9B-2 延后的 minor 批（B~F）全落地**（commit `8a6d05a..7346c94`）

整支评审留下的「延后 minor」**五批全做完**（每条一个**先红**的测试）：

| commit | 批 | 内容 |
|---|---|---|
| `8a6d05a` | B+C | 审计导出补 `audit_id`（LogID，第一列）· 用户列表补 email/department/last_login_at · **停用二次确认** · 审计表**服务端分页**（此前只加载 50 行却写「共 N 条」）· **权限错误提示不可关闭 + 不渲染空表**（关掉退化成「共 0 条」⇒ 读成「什么都没有」⇒ 真相是「你没权限」）|
| `e159926` | D | **mock 保真度**：sign-step **真的改状态**（后端同口径：终态 + 下一步 IN_PROGRESS + 越步 409）· PROXY 段恒 available · 交付物 `matrix_id` 不能再是 null（⇒「签发」永远禁用）· `sign_status` 用**合法枚举** · `/audit-logs` mock 认 limit/offset · **顺带修好一条先前就红的 e2e**（`deliverable_sign` 用 bob 签发 ⇒ 上一提交 5800a8b 加了角色门禁后必红 ⇒ 改 alice）|
| `0459c95` | E | LOW 一组：批注**追加末尾**（与后端升序一致）· `available=false` 时 **reason 必填**（钉进 schema）· 聚合端点补**行级 project_id 校验**（与单条端点同口径）· 恰好 5000 行**不**误报截断 · 导出用**已应用**筛选值 · `skipped_empty` 用 **warning** 条 · `revokeObjectURL` 延后一个 tick · 时间线截断**明说** · seed 多余 cast 删掉 · **状态机守卫不再会悄悄消失**（skipif 只在前端包整个不在时才跳过）|
| `595384a` | F | **建项目入口**（`/admin/projects` + 菜单按角色隐藏 + mock 补 8 字段校验与自动绑矩阵）+ **存量项目回填默认 RECORD 矩阵**（迁移 `p9_013`，三处库各跑一次）|
| `5c1172a` `7346c94` | — | SPEC **V2.4** 登记本批前端行为 · 修用户可见文案里的 markdown 记号（`**` 原样上屏）|

**验收**：后端 **5377 passed / 77 skipped / 1 xfailed**；前端 **974 passed / 105 files**；
Playwright **21 passed**；typecheck + lint exit 0；G-08 契约门禁通过；**迁移三处**
（`pcs` / `pcs_test` / 隔离 schema 从零）`alembic check` 均 **exit 0**；浏览器 QA
`.gstack/qa-reports/qa-report-pcs-frontend-2026-10-28-p9b-2-minors.md`（0 critical /
0 high / 1 medium 已修；控制台 0 error、404-500 计数 0）。

### 第 18 轮：**P9B-2 全批落地 + 收口**（13 个任务 T-1…T10，commit `979119b..33706d8`）

计划 `docs/PCS-PLAN-P9B-2-签署流程与ADMIN前端.md`（2348 行，13 任务）**全部执行完**：

| commit | 内容 |
|---|---|
| `979119b` | **T-1** `POST /projects`（SYSTEM_ADMIN）⇒ 建项目 + **自动绑一份 ACTIVE 的 RECORD 矩阵**（CHECKER→REVIEWER→APPROVER）⇒ 新项目当场能送审 |
| `fc4c9e2` | **T-2** 删死列 `deliverables.parent_deliverable_id`（迁移 `p9_012`）—— 三处库（`pcs` / `pcs_test` / 隔离 schema 从零）均 `p9_012` head + `alembic check` exit 0 |
| `f646b48` | **T0** TODO-065 聚合端点 `GET /deliverables/{id}/progress`（**两段**：SIGN / CUSTOMER_APPROVAL_PROXY；每段带 `available`+`reason`；一条批量查询 ⇒ 3 SELECT） |
| `c68bbf0` | **T1** TODO-066 `GET /records/{module}/{id}/edits`（按项目守卫 ⇒ 越权 **404**；只回 `changed_fields`）＋ 409 弹窗改打新端点（R-14，普通用户点得开差异） |
| `678cc7b` | **T2** TODO-054 批准链**从项目 RECORD 矩阵推导**（R-17）⇒ `submit-approval` **契约破坏性变更**（`extra="forbid"`） |
| `701d48e` | **T3** 4 个 api 客户端（recordActions / deliverables / admin / meta） |
| `bb123bb` | **T4** `RecordActions`（meta 驱动 + 角色门禁 + 送审无角色选择器） |
| `5852465` | **T5** 记录详情抽屉 + 批注面板 + 记录状态时间线 |
| `7fe7e29` | **T6** 交付物进度页接聚合端点（受控面板 ⇒ 展开一行 = **1 个请求**）+ 动作时间线 |
| `1a0097a` | **T7** ADMIN 用户管理页 + 审计日志筛选与 **CSV 导出**（RFC 4180 转义 + 公式注入防护） |
| `a293269` | **T8** 交付物级签署写面（签发 / 逐步签署 / 代录）+ 后端给 sign-step **补 `reason`**（原契约没有 ⇒ 前端必填的理由会被静默丢弃） |
| `6b0db55` `012dd04` `d9c2548` | **T9** TODO-067 七条 deferred minor **全闭环**（#3 降级横幅不消失 / #4 enabled 翻 false 不复位 / #5 释放路径硬编码） |
| `f033a8f` | **T10** 新端点 mock + **状态机 seed 改为后端生成**（R-19）+ 两条 e2e |
| `36d9296` `478b547` | antd `destroyOnHidden` 修正 + TODO-054/065/066/067 结项 + buglog 3 条 |

**验收**（含最终整支评审的修复批）：后端 **5368 passed / 77 skipped / 1 xfailed**；
前端 typecheck / lint exit 0、`vitest run` **944 passed / 103 files**；Playwright
**21 passed**；G-08 契约门禁**含 `--check-baseline`** 通过；浏览器 QA
`.gstack/qa-reports/qa-report-pcs-frontend-2026-10-27-p9b-2.md`（0 critical /
0 high；修复批后控制台 0 error、404-500 计数 0）。

**本批抓到的真缺陷**：**bug-2092** 手写的 `meta/state-machine` seed 漏了
`REVERSAL_PENDING → OBSOLETE` ⇒ 「撤销审批中」的记录**没有**「弃用」按钮（后端允许）
⇒ 改成后端生成 + pytest 逐条比对；**bug-2093** `SignStepRequest` 没有 `reason`
⇒ 退回理由会被静默丢弃。**最终整支评审**又抓到 1 CRITICAL（三个变更动作**每次
都 422** ⇒「放弃变更」永远点不动）+ 6 HIGH（自审门禁只挡第 1 步 / 没绑矩阵不禁用 /
401 误登出 / 多行展开串数据 / 列表 403 吞成空表 / 导出宣称「全部」不核对 `total`）
⇒ **全部已修**（每条一个先红的测试）；**CHECKER 读交付物**是用户裁决放行。

---

## 🚀 Next quest

1. **P9B-3**：系统参数前端 + 物流手动创建向导 + 校对 UI（SPEC §7.20 的
   「AI 开关 / 系统参数 / Prompt 模板 / 角色分配」几页仍未落地）。
2. **本批仍开着**：TODO-073~090 全部闭环；剩余开放项见 TODOS.md（迁移幂等守门的
   历史文件盲区 / 57 个手写类型的长期债 / ADR-0050 用户裁决「先不做」）。
3. ⚠️ **开发库 `pcs` 目前 0 个项目** ⇒ 迁移 `p9_013` 的回填在真数据上是 no-op
   （只建了默认矩阵）⇒ 要验「存量项目被回填」得先有项目数据。

---

## Context

- main，工作区干净（`.wolf/*` 由 hook 自动维护）。**不要建 worktree**（历史事故）。
- 两库均在 **`p9_013`**（head）· `alembic check` 两库 + 隔离 schema 各 exit 0
  （退出码 **255** = 真漂移；先 `current` vs `heads`；`pcs_test` 的 URL 从 `.env`
  **进程内**派生，**不要把口令写在命令行**）。
- ⚠️ **CI 是活的**（全新 Postgres）⇒ 改迁移必须**在全新库上验**（隔离 schema：
  `options=-csearch_path=<schema>`；URL 里**不能有 `%`**）。
- **Redis**：跨进程/锁的测试需要真 Redis（`docker compose up -d redis`）。
- 契约：批末滚 `pcs-backend/docs/openapi-baseline.json`（`gate_08_openapi_contract.sh`
  重生成前端 snapshot / api.d.ts）。
- 提交约定：conventional commits，**无 attribution 行**；长消息写文件后 `git commit -F <file>`。
- ⚠️ **API 测试的 `client` fixture 把 `check_user_project_access` mock 成恒 True** ⇒
  项目授权（404）在 API 测试里测不了 ⇒ 要测 404 必须用 `_guard_client`（且那条用例
  **不能**碰 `client` fixture —— monkeypatch 整个用例期都生效）。
- ⚠️ **in-memory SQLite 的 StaticPool 让 `db` 与独立 client 共用连接** ⇒ 独立 client
  退出时的 rollback 会回滚 `db` 这边**未提交**的 INSERT ⇒ 造完 fixture 先 `commit()`。
- ⚠️ 前端 e2e：**SPA 菜单导航**（`page.goto` 整页刷新会清 zustand 内存 session ⇒
  弹回 /login）；dev 下 app 等 MSW service worker 就绪才渲染 ⇒ 首屏可能空白 ⇒ 显式
  `waitForSelector`；antd 两个汉字的按钮标签**插空格**（"登 录"）⇒ 用正则。

---

## 教训（本批新增，已进 cerebrum）

- **计划写的请求体形状也要核**：计划说 sign-step 收 `{version_id, decision, reason?}`，
  实际契约是 `{version_id, step_index, decision}`（**没有** reason）⇒ 「前端必填
  理由」会被 FastAPI **静默丢弃** ⇒ 必填门禁必须有**载体**，否则是骗用户。
- **手写的「后端生成物」= 漂移温床**：前端 `meta/state-machine` seed 手写 ⇒ 漏一条
  转移 ⇒ 用户**少一个按钮**（功能消失，不是报错）⇒ 一律**后端生成 + 后端 pytest
  逐条比对**（跨包 ⇒ `skipif`：后端-only 检出**跳过**不是**失败**）。
- **禁用优先于报错**：能提前判定的（已有版本还签发、角色不是这一步的）⇒ **按钮禁用
  + 写明原因**，别让用户点了吃 403/409。
