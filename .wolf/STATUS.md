---
description: session handoff, regenerate with /handoff when a quest finishes
budget_tokens: 1200
---
# STATUS — PCS

> Read this FIRST when starting a session. Last updated: 2026-11-17（第 33 轮：
> **P10-F 批 1（F1）** —— 生产就绪评审的 4 条技术债落地 + 1 条上批遗留红；
> **未 push**）。
> 保持 <2k tokens。历史细节查 `git log` / `docs/` / `TODOS.md` / `.wolf/memory.md`。

---

## ✅ Done（第 33 轮：P10-F · F1 批）

计划：`docs/superpowers/plans/2026-11-17-p10-batch-f-production-readiness.md`
· 账簿 `.superpowers/sdd/2026-11-17-p10-batch-f-production-readiness/progress.md`
· QA 报告 `.gstack/qa-reports/qa-report-pcs-frontend-2026-11-17-p10f-f1.md`
（**gitignored** ⇒ 结论已同步进本文 + `TODOS.md` + 提交信息）
· commits `f26bdcb` → `120677b`（**未 push**）。

**F1 的 4 条技术债**（评审 #9 / #13 / #17 / #27）：

- **#9**：`useFetch` 返回值从 `T` 改成 `{data,error,loading}` ⇒ 失败态与加载态
  **长得不一样**（500 / 网络异常 / **15s 超时**）⇒ **401 与 axios 共用一份真相源**
  （新导出 `handleSessionOver`）⇒ `AssetListPage` 的写死 `DEV_BEARER` 换成会话 token。
  测试：`tests/pages/routeWrappers.fetch.test.tsx`（**新建** · 9 条）· 变异自证过。
- **#13**：`preview-streams` 补 `response_model=SimImportPreviewStreamsResponse`
  ⇒ OpenAPI 的 200 从 `{"type":"object"}` 变成 `{"streams":[...]}` ⇒ **契约滚了 4 份**。
- **#17**：种子管级按 `PipeClassResponse` 造（`{"min","max"}` / DN→Sch **字符串** /
  `source="COMPANY_STD"`）⇒ **且订正已种下的老行**（`_get_or_create` 存在就不动 ⇒
  只改脚本不修老行 ⇒ 现象照旧）⇒ E2E 车道 +2 条（**真 PG** 才验得出）。
- **#27**：守门测试统一断「可执行部分」（**一处真相源** `tests/scripts/lane_script_body.py`）
  ⇒ 默认锁路径守卫**加严**（`-n` + `exec 9>`）⇒ 那条「名叫默认路径、实测覆盖路径」的
  测试**改名 + 改 docstring**（诚实）。

**⚠️ 额外修掉一条上批遗留红**（不在计划内 · 批末闸门实测到的）：
`test_ui_schema_drift.py::test_stream_required_matches_pydantic` 红 ⇒
根因是 P10-B 评审 #26（`f22f3a9`）把 `case_type` 改成请求侧可省略、但
`ui_schema_service.py` 仍写 `required: True` ⇒ ⇒ **P10-B 的「默认车道全量绿」不准确**
⇒ 修法：`ui_schema_service.py` 的 `case_type` ⇒ `required: False`
（方向唯一）· commit `120677b` · buglog `bug-2181`。

**闸门**：默认车道 **5839 passed / 109 skipped / 1 xfailed**（11m18s）· PG 车道 **7** ·
E2E 车道 **33**（上批 31）· 真后端 Playwright **7**（白名单不变）· mock 通道 **23** ·
vitest **1063**（上批 1054）· typecheck/lint clean · G-08 `--check-baseline` 过 ·
裸载荷 **42** ≤ 71 · 浏览器回归：6 个 `useFetch` 页 + 物流详情页**数据都进 DOM** ·
控制台无 error · 网络无 4xx/5xx。

**新登记**：TODO-166（公司管级列表要不要出现 E2E 种子管级 · **产品决定**）· bug-2181。

---

## 🚀 Next quest

1. **P10-F 批 2（F2 · 5 任务）**：F2-T1（public 守卫快照**全部表** + 补 `_sync_engine`）·
   F2-T2（仪表盘守卫条件 + PERSONAL 工作区）· F2-T3（compose 的 migrate/seed 进锁）·
   F2-T4（rowKey 棘轮扩到函数形式）· F2-T5（**默认车道连开发库 + 真 Redis** ⇒ 隔离）。
   ⇒ 前置 = F1 已落地 ✓ ⇒ **现在就能开**。
2. **推送本轮**（P10-B 12 个 + 本批 5 个提交未 push ⇒ 需明确授权）。
3. **P10-C / D / E** 未开工 ⇒ ⇒ F4（依赖漏洞/镜像扫描/回滚演练）与 F5（告警/备份/Go-No-Go）
   的**前置不满足**。
4. **待人裁决**：#17 的 `source` 副作用（TODO-166）· #24 的 FORMAL 工作区回填 ·
   F3 的审计范围（Q10 · 只开 T1 提范围提案）。

---

## Context

> ⚠️ **迁移 / PG 车道 / 裸载荷基线 / 发布前检查** ⇒ 见 `CLAUDE.md` ⇒ **不重复**。

- main。**不要建 worktree**（历史事故）· **不要 `git checkout <commit> --detach`**。
  **不得擅自 push**。`.wolf/*` 里 `anatomy.md` / `memory.md` / `anatomy-index.json` 由 hook 维护。
- 提交约定：conventional commits，**带** `Co-Authored-By: Claude Code` 行；长消息写文件后 `git commit -F`。
- ⚠️ **计划里的 Task 标签带批次前缀**（F1-T1）⇒ 内置 `task-brief` 只认纯数字 ⇒
  本批自建 `.superpowers/sdd/<plan>/brief.sh`（等价抽取）⇒ 下一批沿用。
- ⚠️ **真后端通道统一入口**（评审 #23）：后端 `bash pcs-backend/scripts/serve_e2e_backend.sh`
  （库 `pcs_pgtest` · 端口 **8001** · mock 登录开）⇒ 前端 `npm run e2e:real`
  ⇒ 三个变量由 `playwright.config.ts` 的 webServer.env **默认**给。
  ⇒ ⚠️ `pcs-postgres-pgtest-1` 容器**在跑**（宿主 5433）⇒ `pg_isready -p 5433`
  **不带 `-h`** 会说「no response」（走的是 socket）⇒ 要 `-h localhost`。
- ⚠️ **`.env` 的 `DATABASE_URL` 指向开发库 `pcs`** ⇒ 跑真后端通道必须**显式覆盖**
  ⇒ alembic 的 `settings` 是 pydantic **缓存实例** ⇒ **一库一个进程**。
- ⚠️ **antd 的 `role="option"` 是隐藏副本**（宽 0）⇒ Playwright 判「不可见」
  ⇒ 用 `.ant-select-item-option`；状态徽标上写的是**中文**（「已核验」）。
- ⚠️ **跑 pytest 前先清掉残留进程** ⇒ 满负载 ⇒ Playwright 的 `locator.click` **30s 超时假红**。
- ⚠️ **子代理 Bash 会挂起** ⇒ 派发审阅/实现子代理**只给 Read/Grep**。
- ⚠️ **`.env` 的口令不要写命令行** ⇒ 用 `dotenv_values('.env')` 在**进程内**派生 URL。
- ⚠️ **本机无外网** ⇒ compose 的一次性服务（`seed` / `migrate`）**构建不了**
  ⇒ ⇒ compose 侧改动**无法验证** ⇒ 别盲改（TODO-163 就是这么留下的）。

---

## 教训（**已进 cerebrum / docs/solutions**，此处只留最新三条）

- **守卫要断「可执行部分」，不是原文** ⇒ 注释里写一句 `flock` 就足以让守卫绿
  ⇒ ⇒ 一处真相源 + 剥注释按 shell 的**词边界**规则（引号里的 `#` 是字面量）。
- **「存在就不动」的写法 ⇒ 改了工厂函数也修不了老行** ⇒ ⇒ 订正必须**显式**做
  （幂等：只在形状真的不对时才写）。
- **断言要断的分支必须先「到达」** ⇒ 身份不对 ⇒ 比较的是**另一个闸门**的码
  ⇒ ⇒ 用**变异测试**证明敏感（删掉被守卫的代码 ⇒ 断言必须红）（bug-2174）。
⇒ 其余历史教训查 `.wolf/cerebrum.md` 的 Do-Not-Repeat（**先查顶部索引表，别通读**）
   与 `docs/solutions/`。
