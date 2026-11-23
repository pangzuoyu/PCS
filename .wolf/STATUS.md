---
description: session handoff, regenerate with /handoff when a quest finishes
budget_tokens: 1200
---
# STATUS — PCS

> Read this FIRST when starting a session. Last updated: 2026-11-23（第 39 轮：
> **P10-H · 项目作用域批** —— TODO-194 / 195 / 193 三条**全部落地**）。
> 保持 <2k tokens。历史细节查 `git log` / `docs/` / `TODOS.md` / `.wolf/memory.md`。

---

## ✅ Done（第 39 轮 · P10-H · 项目作用域批 · 2026-11-23）

计划 `docs/superpowers/plans/2026-11-23-p10-h-project-scope.md`
⇒ ⇒ 提交 `3cfc88c` → `ba116da` → `5d60df7` → `ef17999` → `9cfa39e` → `1a12fde`
（另含前一轮遗留的 `2619bb9` 种子修契约形状 · bug-2193）。

**T1 · TODO-194（前端能选项目）** `3cfc88c`
顶栏**项目切换**（SPEC §3.2）⇒ 候选 = `GET /user-projects/me` ∪ `GET /workspaces`
（admin 全量）· 名字走 `GET /projects/{id}` · 选择存 **store**（换页不丢）·
登出清空（防跨身份越界）· mock 补 2 个端点 + ajv 校验。

**T2 · TODO-195（PMS / BEDD 后端实体 · 人裁 ②）** `ba116da` + `5d60df7`
- **PMS** 表 `pms_items`（迁移 `p10_004`）· 继承 `RecordMixin` ⇒ ⇒ **吃通用 9 态
  工作流**（`/records/PmsItem/{id}/submit-approval`）⇒ ⇒ 不另造签署框架 · 4 个端点 ·
  `pms_no` 项目内唯一 ⇒ 409 · 只有 DRAFT 能改。
- **BEDD** = `projects.bedd_json` 的**写入路径**（`PUT` 整份替换）· 9 个分组的具名
  schema（`create_model` 从 SPEC 字段表生成 ⇒ 校验与表单**同一份真相源**）·
  新增 `bedd` uiSchema 资源 ⇒ 前端两页从**占位**变**真端点**（分组 Tab）。

**T3 · TODO-193（14 条 mock 欠账还完）** `ef17999`
`tests/mocks/contract_debt_193.test.ts`（14 条 ajv 校验）⇒ 棘轮「欠账清单」清空
（**机制保留**）。

**批末闸门抓到的真问题（已修）** `9cfa39e` + `1a12fde`
① 后端默认车道第一轮 **6 failed** = 四条计数型守卫 + p9_014 守卫的**断言形状**
（新表由 p10_004 建 ⇒ ⇒ 不能进 p9_014 的清单 ⇒ ⇒ 改为**从迁移文件 AST 推导**豁免）；
② mock 通道 e2e **2 failed** = 顶栏新增 Select ⇒ ⇒ `.first()` **位置定位**失效
⇒ ⇒ 改成指名道姓（`data-testid`）⇒ ⇒ 23/23 绿；
③ 环境级：**残留 uvicorn 占住车道锁 3.5 天** ⇒ ⇒ 车道起不来 ⇒ ⇒ 杀掉 + 教训入账。

**闸门（批末实跑）**：后端新测试 19 passed · 测试栈真 PG **alembic_version=p10_004**
· 真后端冒烟 7 端点全通 · typecheck/lint clean · vitest **1114/1115**（唯一红是
已知 flake）· mock 通道 **23/23** · 真后端通道 **9/9**（`CONSOLE_ERRORS=[]`）·
浏览器 QA 全通 · `alembic check` 两库 exit 0 · 载荷闸 RC 0（裸字段仍 71）·
迁移幂等 RC 0（50 个）· 契约漂移 RC 0。

**T4 · TODO-199（4 条裸 object 端点补具名 schema）** `7b93b7e7`
`GET /streams/{id}/properties` · `POST /properties/estimate` ·
`GET/POST/PATCH /streams/{id}/state-points` · `POST /streams/{id}/submit`
⇒ ⇒ 契约里从**裸 object** 变**具名 schema**（395 → 402 个 schema）⇒ ⇒ 前端
终于有类型。⚠️ `response_model_exclude_unset=True` ⇒ ⇒ **载荷不变**（否则未赋值
字段补成 null ⇒ ⇒ 存量断言直接红）；⚠️ `composition_json` 只在**响应侧**放宽成
可空（否则裸载荷闸 71 → 72 ⇒ ⇒ 倒退）。物性袋字段表**只有一份**
（`PropertyAutoCompleter` 的字段集公开化 ⇒ ⇒ `create_model` 生成）。

---

## 🚀 Next quest

1. **P10-F · F4-PRE**（`docs/superpowers/plans/2026-11-17-p10-batch-f-production-readiness.md`
   的 F4 前置批 · 5 个任务：FP-T1 逐条裁决 14 条遗留债 · FP-T2 棘轮抬真
   （`AUDITED_PROJECT_SCOPED_ENDPOINTS` 从**计数**改成**清单**）· FP-T3 车道残留
   · FP-T4 断言缺口 · FP-T5 台账入账）⇒ ⇒ **不依赖 P10-C** ⇒ ⇒ 现在就能开。
2. **推送**：P10-H 的 T4 已提交 ⇒ ⇒ 待推（用户已授权推过一次）。
3. **仍待人裁决**：**TODO-197**（「他人发布」的入口 · 三个方案）· **TODO-196**
   （10 个 DMC 组分的 CAS ⇒ **工艺室**确认，不是人能裁的）。
4. **SPEC §7.5 的向导**里 PMS / BEDD 两步**仍是空占位** ⇒ ⇒ 另开。

---

## Context

- main。**不要建 worktree** · **不要 `git checkout <commit> --detach`**。**不得擅自 push**。
  `.wolf/*` 里 `anatomy.md` / `memory.md` / `anatomy-index.json` 由 hook 维护。
- ⚠️ **每轮开工先查残留**：`fuser -v pcs-backend/.tmp/lane.lock`（谁占着车道锁）·
  `pgrep -af "uvicorn app.main:app"`（真后端通道的后端）· `ss -ltnp | grep 5173`
  （上一轮的 vite · 端口被占 ⇒ 新 vite 会落到 5174 ⇒ ⇒ **没人注意**）。
- ⚠️ **真后端通道**：后端 `bash pcs-backend/scripts/serve_e2e_backend.sh`（库
  `pcs_pgtest` · 端口 8001）⇒ 前端 `npm run e2e:real`；**mock 登录端点是
  `/auth/mock-login`（不在 `/api/v1` 下）**。
- ⚠️ **`.env` 的口令不要写命令行** ⇒ 用 `dotenv_values('.env')` 在**进程内**派生 URL
  ⇒ ⇒ **一库一个进程**（alembic 的 settings 是 pydantic 缓存实例）。
- ⚠️ **子代理 Bash 会挂起** ⇒ 派发审阅/实现子代理**只给 Read/Grep**。

---

## 教训（**已进 cerebrum / docs/solutions**，此处只留最新两条）

- **`.first()` 是位置定位** ⇒ ⇒ 页面上多一个同类型控件就**静默失效**
  （本轮：顶栏加 Select ⇒ e2e 点到了顶栏那个）⇒ ⇒ 一律**指名道姓**。
- **残留进程会占住车道锁 ⇒ ⇒ 几天都起不来**（本轮：僵尸 uvicorn 占锁 3.5 天，
  而真后端通道照跑 ⇒ ⇒ 看起来「车道在跑」其实是「锁被占着」）。
