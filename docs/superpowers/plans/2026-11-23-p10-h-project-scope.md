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

- [ ] **PMS**：项目级表 + 端点（列表 + 增删改？⇒ ⇒ 按 SPEC §7.5 向导第 2 步的语义定）⇒ ⇒ 前端 `/pms` 页接真端点（列以契约为准）
- [ ] **BEDD**：`projects.bedd_json` 的**写入路径**（现在只有建表迁移提到它 ⇒ ⇒ 补出来的端点**永远返回空**）⇒ ⇒ 前端 `/bedd` 页接真端点
- [ ] alembic 迁移 + **ORM 列同步手工核对**（改迁移后 `uv run alembic check` 在 **pcs / pcs_test 两库各跑一次 · 独立进程** ⇒ ⇒ 只信退出码不够 ⇒ ⇒ 直查 `alembic_version`）
- [ ] 前端：两页去掉「数据源尚未接入」的占位 Alert ⇒ ⇒ 接真端点

⚠️ **PMS 语义未定义**（SPEC §7.5 只给了章节标题 + BEDD 的 10 个分组，**没给 PMS 字段**）⇒ ⇒ **人裁**（见「未解决问题」）。

---

## T3 · TODO-193 · mock ↔ 契约的漂移棘轮：14 条欠账 🟡

**欠账清单**：`pcs-frontend/tests/mocks/handlers.test.ts` 的 `CONTRACT_ENDPOINTS_NOT_YET_VALIDATED`（14 条）。

- [ ] **逐条**核字段形状（对着 `pcs-backend/docs/openapi.json`）⇒ ⇒ 每条补一条 ajv 校验用例 ⇒ ⇒ 从清单里删一条
- [ ] 清单**不许悄悄少**：端点从 mock 删了 ⇒ 断言要红（已有）
- [ ] 变异自证：把某条的校验去掉 ⇒ ⇒ 对应用例转红

---

## 批末闸门

- [ ] 前端 `typecheck` / `lint` / `vitest` ≥ 上批基线
- [ ] 后端默认车道 `pytest` EXIT=0
- [ ] `uv run alembic check`（两库 · **独立进程** · 直查 revision）
- [ ] `check_openapi_payload_coverage.py` RC 0 · `check_migration_idempotency.py` RC 0
- [ ] 真后端通道（`bash pcs-backend/scripts/serve_e2e_backend.sh` ⇒ `npm run e2e:real`）无 4xx/5xx
- [ ] 浏览器 QA（`browse`）· 报告落 `.gstack/qa-reports/qa-report-pcs-frontend-2026-11-23-p10h.md`
- [ ] `TODOS.md` 逐条记结果 + `fix_commit`

---

## 未解决问题（开工时挂着的）

1. **PMS 的字段集**（T2 的前置）—— SPEC 没给 ⇒ ⇒ 待人裁。
2. **BEDD 的粒度** —— `bedd_json` 存**结构化 10 分组**（SPEC §7.5）还是**自由章节**（前端 `/bedd` 页现在的形状）？⇒ ⇒ 待人裁。
3. **TODO-197**（「他人发布报表定义」的入口）—— 三个方案待裁（与本批无关，挂着）。
4. **TODO-196**（10 个 DMC 组分的 CAS）—— 工艺室确认，不是人能裁的。
