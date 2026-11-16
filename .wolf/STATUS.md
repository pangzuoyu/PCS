---
description: session handoff, regenerate with /handoff when a quest finishes
budget_tokens: 1200
---
# STATUS — PCS

> Read this FIRST when starting a session. Last updated: 2026-11-16（第 31 轮：
> **P10-B（全流程 E2E）T1~T7 落地** —— 真 PG 隔离 schema 车道 + 18 场景 +
> 权限矩阵 + 真后端 5 条 UI 流；**未 push**）。
> 保持 <2k tokens。历史细节查 `git log` / `docs/` / `TODOS.md` / `.wolf/memory.md`。

---

## ✅ Done（第 31 轮：P10-B · 全流程 E2E）

计划：`docs/superpowers/plans/2026-11-13-p10-batch-b-fullflow-e2e.md` ·
账簿 `.superpowers/sdd/2026-11-13-p10-batch-b-fullflow-e2e/progress.md`
· commits `540dc9b` → `dd00d93`（**未 push**）。

**车道**：`scripts/pytest_e2e.sh`（薄封装 ⇒ 复用 `pytest_pg.sh` 的三道闸门）·
隔离 schema（`CREATE SCHEMA` → `alembic upgrade head` → `DROP CASCADE`）·
默认车道由 `PCS_E2E_LANE` 闸门**跳过** e2e 用例（否则会打到开发库 `pcs`）·
两条车道**共用一把 flock**（同一个库不能并发建 schema）。

**覆盖**：E2E 车道 **28 passed + 1 xfailed**（18 个 SPEC 场景 + 5 条路径 +
权限矩阵 + AI 审计 + 两库 schema 一致）· PG 车道 7 passed ·
真后端 Playwright **6 passed**（5 条新 UI 流 + P10-A 冒烟）·
mock 通道 23 passed · 前端 typecheck/lint clean · vitest 1054 passed。

**抓到的真缺陷（9 个）**：bug-2163（预览响应形状）· 2164（管道等级占位行）·
2165（报表审计哈希 · **根因未闭环 ⇒ TODO-158**）· **2166**（种子塞 int 进
VARCHAR ⇒ 生产驱动 asyncpg 上必炸 ⇒ **根因是车道用了跟生产不同的驱动**
⇒ 车道改 asyncpg）· **2167**（`GET /projects/{id}/streams` 500 ——
`case_type` DB 可空而响应必填枚举 ⇒ 物流一览页打不开）·
**2168**（仪表盘每次开 2 条 404）· **2169**（`useFetch` 发**写死的假 token**
⇒ 真后端 401 ⇒ 详情页永远「加载中…」）· **2170**（PG 守门测试与车道锁打架）。

**变异实测**（守卫不是空壳）：去掉 `parent_lineage_id` ⇒ 01C/E2E-013 同时红；
给 bob 发一条 VIEWER 授权行 ⇒ 权限流红。

**SPEC 偏离登记 D23~D38 已回写**（该 SPEC 实际是 **V1.0** ⇒ D20）。

---

## 🚀 Next quest

1. **T8 收口**：批末闸门（`alembic check` 两库各一进程 · `scripts/pytest_pg.sh` ·
   `check_openapi_payload_coverage.py` · `check_migration_idempotency.py` ·
   前后端全量 · Playwright 两条通道）· **gstack-qa 浏览器回归报告**
   （`.gstack/qa-reports/qa-report-pcs-frontend-2026-11-16-p10b.md`）⇒
   ⇒ **本轮还没跑**（T8 Step 2~5）。
2. **P10-C/D/E/F** 仍未开工（部署可观测 / 压测 / 文档 / 生产就绪评审）。
3. **本轮未 push**（用户未要求）。
4. **新增 TODO**：155（真过 Redis + ARQ worker）· 156（PRO/II 不抽组成）·
   **157**（前端**没有设备清单页** ⇒ `/equipment-list` 无页面）·
   **158**（报表审计哈希根因未闭环 · bug-2165 残余）。
5. **E2E 进 CI 延到 P10-F**（既有裁决「不新建流水线」⇒ D25）。

---

## Context

> ⚠️ **迁移 / PG 车道 / 裸载荷基线 / 发布前检查** ⇒ 见 `CLAUDE.md` ⇒ **不重复**。

- main。**不要建 worktree**（历史事故）· **不要 `git checkout <commit> --detach`**。
  **不得擅自 push**。`.wolf/*` 里 `anatomy.md` / `memory.md` / `anatomy-index.json` 由 hook 维护。
- 提交约定：conventional commits，**带** `Co-Authored-By: Claude Code` 行；长消息写文件后 `git commit -F`。
- ⚠️ **真后端通道的跑法**（T7 实测）：后端连 **`pcs_pgtest`（宿主 5433）**
  （`DATABASE_URL` + `PCS_ENABLE_MOCK_LOGIN=true` ⇒ 起 uvicorn）
  ⇒ 前端 `VITE_ENABLE_MOCK=false` + `VITE_PROJECT_ID=<flows 项目 id>`
  + `VITE_API_PROXY_TARGET=http://127.0.0.1:<后端端口>`
  ⇒ `npx playwright test --project=real-backend`。
  ⇒ ⚠️ **后端端口不是 8000**（本机 8000 被别的服务占着）。
- ⚠️ **`streams.case_type` 可空** ⇒ 任何物流列表的种子都要显式填（否则端点 500）。
- ⚠️ **antd 的 `role="option"` 是隐藏副本**（宽 0）⇒ Playwright 判「不可见」
  ⇒ 用 `.ant-select-item-option`；状态徽标上写的是**中文**（「已核验」）。
- ⚠️ **跑 pytest 前先清掉残留进程**（本机多次出现上几轮遗留的 pytest）⇒ 满负载 ⇒
  Playwright 的 `locator.click` **30s 超时假红**。
- ⚠️ **子代理 Bash 会挂起** ⇒ 派发审阅/实现子代理**只给 Read/Grep**。
- ⚠️ **`.wolf/cerebrum.md` 已 ≈28k token** ⇒ 清退窗口已到 ⇒ 但**别机械搬最旧的**。
- ⚠️ **`.env` 的 `DATABASE_URL` 指向开发库 `pcs`** ⇒ 跑真后端通道必须**显式覆盖**
  ⇒ 且 alembic 的 `settings` 是 pydantic **缓存实例** ⇒ **一库一个进程**。

---

## 教训（**已进 cerebrum / docs/solutions**，此处只留最新三条）

- **车道的驱动必须与生产一致** ⇒ 否则「int 塞进 VARCHAR」这类缺陷**隐形**（bug-2166）。
- **前端有两条取数通道**（axios 拦截器 vs 裸 `fetch`）⇒ 后者**默认没有 token** ⇒
  真后端通道才抓到（bug-2169）。
- **守卫测试必须与被守卫的机制隔离** ⇒ 车道锁 ⇒ 守门测试抢同一把锁 ⇒
  测的不是它声称的东西（bug-2170）。
⇒ 其余历史教训查 `.wolf/cerebrum.md` 的 Do-Not-Repeat（**先查顶部索引表，别通读**）
   与 `docs/solutions/`。
