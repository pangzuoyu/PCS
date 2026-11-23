# P10-H · 项目作用域批（TODO-194 → TODO-195 → TODO-193）· 2026-11-23

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans（本批自己实现，不派子代理 —— 子代理 Bash 会挂起）。

**Goal:** 前端能**选**项目（不只取「第一个」）⇒ ⇒ PMS / BEDD 两页接到**真**端点 ⇒ ⇒ mock ↔ 契约的漂移棘轮把 **14 条欠账**还完。

**顺序是硬依赖**：194（选择器）→ 195（PMS/BEDD）→ 193（mock 补债）。
⇒ ⇒ 195 落在 193 之后会因为「PMS/BEDD 的新端点也要进棘轮」而返工。

**Tech Stack:** React 18 · antd 5 · zustand · TypeScript · FastAPI · SQLAlchemy 2（async）· alembic · pytest · vitest

**Spec:** `docs/PCS-UI-SPEC.md`（V1.0 冻结）· **§3.2 TopBar「项目切换：下拉，显示最近项目 + 搜索」** ⇒ ⇒ 选择器有 SPEC 依据 · **§7.5**（PMS / BEDD）· 字段/权限以 **OpenAPI** 为准

**前置：** P10-G 已落地（`576d40c`）· 本批不依赖 P10-C 的部署物 ⇒ ⇒ 现在就能开。

---

## T1 · TODO-194 · 项目选择器 🟡

**现状**：`useProjectScope` 从 `GET /workspaces` 取**第一个**有项目的工作区 ⇒ ⇒ 多项目时是**猜一个**。

**后端不用改**：`GET /user-projects/me` **已在契约里**（我的全部授权）⇒ ⇒ 走它。

- [x] 前端 store：`src/store/projectScope.ts`（zustand）⇒ `projects` / `currentProjectId` / `selectProject` / `ensureLoaded`（幂等 ⇒ 多组件共用一次拉取）
- [x] hook 重写：`useProjectScope` ⇒ ① `GET /user-projects/me` 取授权 ⇒ ⇒ ② 并行 `GET /projects/{id}` 取**项目名**（`ProjectOut.project_name`）⇒ ⇒ ③ 选中项 = 已选 > `VITE_PROJECT_ID` hint > 第一个
- [x] UI：`src/components/common/ProjectSelector.tsx`（antd `Select` + `showSearch`）⇒ ⇒ 挂在 `MainLayout` 的 TopBar（SPEC §3.2）
- [x] mock：补 `GET /api/v1/user-projects/me` + `GET /api/v1/projects/:project_id` 两个 handler ⇒ ⇒ **契约形状**（不是随手编的字段）
- [x] 测试：hook（4 条：授权列表 / 名字解析 / 选中保持 / 空列表）+ 组件（渲染 + 切换）+ 变形自证
- [x] `useProjectScope` 的 `workspaceId` ⇒ **无人消费** ⇒ ⇒ 删掉

**验收**：`npm run typecheck` clean · `npm run lint` clean · `npm run test` ≥ 基线（1091）。

---

## T2 · TODO-195 · PMS / BEDD 后端实体 🔴（人裁 ②：补后端实体）

**前置**：T1（否则两页只能取「第一个项目」⇒ ⇒ 仍是半成品）。

- [x] **PMS**：项目级表 `pms_items`（迁移 `p10_004`）+ 端点 ⇒ ⇒ **人裁 2026-11-23：沿用前端形状 + 签署流** ⇒ ⇒ 继承 `RecordMixin` ⇒ ⇒ 吃**通用 9 态工作流** ⇒ ⇒ 前端 `/pms` 页接真端点（列不变 · 状态列现在是真的 9 态）
- [x] **BEDD**：`projects.bedd_json` 的**写入路径**（`PUT`，**整份替换**）⇒ ⇒ **人裁 2026-11-23：按 SPEC 的 9 个分组** ⇒ ⇒ 分组模型由 `create_model` 从字段表生成 ⇒ ⇒ 前端 `/bedd` 页改成**分组 Tab**（uiSchema 驱动）
- [x] alembic 迁移 + **ORM 列同步手工核对** ⇒ ⇒ `pcs` 与 `pcs_test` **两库各跑一次 · 独立进程** ⇒ ⇒ `pcs_test` 直查 `alembic_version=p10_004` + 直查 `pms_items` 的 35 列 ⇒ ⇒ 两库 `alembic check` 都是「无新升级操作」
- [x] 前端：两页去掉「数据源尚未接入」的占位 Alert ⇒ ⇒ 接真端点 ⇒ ⇒ 手写的 `PmsItem`/`BeddSection` **删掉** ⇒ ⇒ 改用生成的契约类型

⚠️ **PMS 语义未定义**（SPEC §7.5 只给了章节标题 + BEDD 的 10 个分组，**没给 PMS 字段**）⇒ ⇒ **人裁**（见「未解决问题」）。

---

## T3 · TODO-193 · mock ↔ 契约的漂移棘轮：14 条欠账 🟡

**欠账清单**：`pcs-frontend/tests/mocks/handlers.test.ts` 的 `CONTRACT_ENDPOINTS_NOT_YET_VALIDATED`（14 条）。

- [x] **逐条**核字段形状（对着 `pcs-backend/docs/openapi.json`）⇒ ⇒ 每条补一条 ajv 校验用例 ⇒ ⇒ 从清单里删一条 ⇒ ⇒ 新增 `tests/mocks/contract_debt_193.test.ts`（14 条）
- [x] 清单**不许悄悄少**：端点从 mock 删了 ⇒ 断言要红（已有）⇒ ⇒ 清单现在是**空集** ⇒ ⇒ **机制保留**（新增契约端点出现在 devOnly ⇒ ⇒ 立刻红）
- [x] 变异自证：把某条的校验去掉 ⇒ ⇒ 对应用例转红 ⇒ ⇒ 实测（`stream_name` 改 `undefined` ⇒ ⇒ 精确报 `missingProperty`）

---

## 批末闸门

- [x] 前端 `typecheck` / `lint` clean · `vitest` **1117/1118**（上批 1091 ⇒ +26）
      ⇒ ⇒ 唯一红的是**已知 flake**（`result_page.test.tsx` · 满负载超时 · 单独跑绿）
- [x] 后端默认车道 ⇒ ⇒ **5963 passed / EXIT=0**（11m16s）
      ⇒ ⇒ 第一轮 **6 failed**（全是**新表带来的守卫同步** ⇒ ⇒ 已修）⇒ ⇒
      四条计数型守卫 + p9_014 守卫的**断言形状**（从迁移文件 AST 推导豁免）
- [x] `uv run alembic check`（两库 · **独立进程** · 直查 revision）⇒ ⇒ `pcs` exit 0 ·
      `pcs_test` 直查 `alembic_version=p10_004` + 直查 `pms_items` 的 35 列
- [x] `check_openapi_payload_coverage.py` RC 0（裸字段仍 71）·
      `check_migration_idempotency.py` RC 0（50 个迁移）
- [x] 测试栈（compose · **真 PG**）⇒ ⇒ `alembic_version=p10_004` · seed ×2 幂等
- [x] **PG 车道 7 passed**（`scripts/pytest_pg.sh`）· **E2E 车道 40 passed**
      （`scripts/pytest_e2e.sh`）⇒ ⇒ 本批闸门**全部收口**
- [x] 真后端通道（`serve_e2e_backend.sh` ⇒ `npm run e2e:real`）⇒ ⇒ **9/9** ·
      `CONSOLE_ERRORS=[]` · `BAD_RESPONSES=[]` · 46 条路由全可达
- [x] mock 通道（`npm run e2e`）⇒ ⇒ **23/23**（第一轮 2 failed = 顶栏新增 Select
      ⇒ ⇒ `.first()` 位置定位失效 ⇒ ⇒ 改成指名道姓）
- [x] 浏览器 QA（`browse`）⇒ ⇒ 登录 / 仪表盘 / 项目切换 / `/pms` / `/bedd` 全通 ·
      控制台无 error · 报告落 `.gstack/qa-reports/qa-report-pcs-frontend-2026-11-23-p10h.md`
- [x] `TODOS.md` 逐条记结果 + commit

---

## 未解决问题（**批末**）

1. ✅ **PMS 的字段集** —— 人裁 2026-11-23：**沿用前端形状 + 签署流**（已落地）。
2. ✅ **BEDD 的粒度** —— 人裁 2026-11-23：**按 SPEC 的 9 个分组**（已落地）。
3. ⚠️ **TODO-199**（**本批新登记**）—— 4 条端点的契约**本身就是裸 object**
   ⇒ ⇒ ajv 只能证明「是个 object」⇒ ⇒ 要后端补具名 schema。
4. ⚠️ **SPEC §7.5 的向导**里 PMS / BEDD 两步**仍是空占位** ⇒ ⇒ 本批只把**独立页**做实。
5. **TODO-197**（「他人发布报表定义」的入口）—— 三个方案待裁（与本批无关，挂着）。
6. **TODO-196**（10 个 DMC 组分的 CAS）—— 工艺室确认，不是人能裁的。
7. **推送**：P10-G + P10-H 都**未 push** ⇒ ⇒ 待明确授权。
