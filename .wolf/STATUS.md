---
description: session handoff, regenerate with /handoff when a quest finishes
budget_tokens: 1200
---
# STATUS — PCS

> Read this FIRST when starting a session. Last updated: 2026-11-25（第 47 轮：
> **P10-J · T1 落地** —— 公司级模板「执行时选项目」· ADR-0051 · SPEC V2.20）。
> 保持 <2k tokens。历史细节查 `git log` / `docs/` / `TODOS.md` / `.wolf/memory.md`。

---

## ✅ Done（第 47 轮 · **P10-J · T1**（公司级模板执行时选项目 · TODO-177）· 2026-11-25）

**公司级模板此前永远跑不通**（端点没 `project_id` 可传 ⇒ scope 恒 None ⇒ worker 里恒 400
⇒ 用户看到「202 已提交 → 执行失败」；产出文件 `report_files.project_id` 落 NULL ⇒ 报表无归属）。
⇒ ⇒ **scope 解析收在端点一处**（service 的 `project_id or row.project_id` **原样不动** ⇒
一条不变量一种机制）· 判定顺序**不重排既有行为**（定义不可见 404 → 定义自带项目授权 404 →
非 PUBLISHED 409 → **不一致 400** `REPORT_PROJECT_SCOPE_MISMATCH` → **没选 400**
`REPORT_PROJECT_SCOPE_REQUIRED` → 公司级对所选项目授权 404 `PROJECT_NOT_FOUND`）·
入队与快照都传**解析后的 scope** ⇒ 产出**有归属**。
⚠️ **前端**：公司级模板才出现「选项目」下拉（**必选、无默认** · 未选 ⇒ 执行按钮禁用 ·
详情未到也禁用）· 定义下拉 label **标作用域**（公司级/项目级）· 候选源**按角色分**
（普通 = 自己的授权行 · admin = 工作区）⇒ ⇒ **不复用** `useProjectScope` 那个并集
（含你无权执行的项目）· 选择是**局部 state**（不动全局顶栏）。
⚠️ **T1-7**：建定义时拒「公司级 + 主源无 `project_id` 列」（`DATALINEAGE`/`SUPPLIERS`/`CONFIG_ASSETS`）
⇒ ⇒ 那是批量生产永远跑不了的死路 ⇒ ⇒ 执行侧另给**可区分**的码
`REPORT_DATASOURCE_NOT_PROJECT_SCOPED`（不与「没选项目」混用）。
**契约**：`ReportExecuteRequest` 加**可选** `project_id` ⇒ ⇒ **三份都滚**（CI 拦不住「新增可选字段」）。
**规格/决策**：SPEC **§7.18.2** + §12.4 **V2.20**（文件头 V2.19 ⇒ V2.20）· **ADR-0051**。
**车道**：默认 **6172**（+6）· PG **47**（+1 · **直连 ORM** 真打到 `uq_report_definitions_project_name`）
· 前端 typecheck/lint clean · 前端 **1139**（+5）· `alembic check` **两库各一进程** exit 0 ·
浏览器回归（登录 → 仪表盘 → 6 路由 → 公司级闸门三面全中 · 控制台无 error · 无 404）⇒ ⇒ **CRITICAL/HIGH 0 条**。

## ✅ Done（第 46 轮 · **P10-J · T2**（「打回」动作 · TODO-197b）· 2026-11-24）

**「打回」不是新状态** ⇒ **9 态机一个字不改** ⇒ 「待审」（DRAFT 未被打回）vs「待改」（DRAFT 被打回）
是**两个态** ⇒ 队列只装前者 ⇒ 打完回离开队列 ⇒ 创建人改稿（`update()` **清标记**）⇒ 自动回来
· 三列（`rejected_at`/`rejected_by`/`reject_reason`）+ 迁移 `p10_005` · 端点
`POST /definitions/{def_id}/reject` · 通知**复用 `STEP_RETURNED`** · 前端：队列页「打回」+
原因弹窗（空原因禁用）· 列表页「被退回」badge · SPEC §7.18.1（V2.19）。

## ✅ Done（第 45/44/43 轮 · P10-C · T1 / T0 / P10-I · T2 · 2026-11-23~24）

P10-C（exporters · `GET /status` 恒 200 · 监控栈 · 备份演练 · **「测试报告页」裁为不建**）·
P10-C·T0（容器侧同 inode 车道锁 ⇒ TODO-163 闭 · 遗留账号迁移 ⇒ TODO-137 闭）·
P10-I·T2（404 文案**逐字同形** ⇒ 存在性不可枚举 · 124 处零影响）。
⇒ ⇒ 细节查 `git log`。

---

## 🚀 Next quest

1. ✅ **P10-C 全部细项落地** ⇒ 收批
2. ✅ **2026-11-24 · 8 条待裁项逐条裁完** ⇒ TODO-196 已签字 ⇒ TODO-200/201/202/153 关闭
3. ✅ **P10-J · T2「打回」已落地**（第 46 轮）⇒ 默认 6166 · PG 46 · 前端 1134
4. ✅ **两份计划已批准**（2026-11-25 · 人裁「approve」）
5. ✅ **P10-J · T1 已落地**（第 47 轮 · commit `5fc7b7e0`）⇒ ⇒ ⇒ **TODO-177 关闭**
6. ⏭ **下一批 = P10-K（SPEC §7.5 项目向导 · 25 个任务 · 已批准）**
   ⇒ ⇒ 计划 `docs/superpowers/plans/2026-11-24-p10-k-spec75-project-wizard.md`
   ⇒ ⇒ ⚠️ **本批会新增端点**（模板列表 · 套用模板 · 项目状态 PATCH …）⇒ ⇒ ⇒
   **必须跑 `check_openapi_payload_coverage.py`**（棘轮**已顶满 71** ⇒ 新端点一律用
   **命名响应模型**，别抄同域最旧那个端点）⇒ ⇒ ⇒ 见 `TODOS.md` **TODO-209**
   ⇒ ⇒ ⚠️ **SPEC 版本号从 V2.21 起算**（V2.20 已被 P10-J-T1 占用）
   ⇒ ⇒ ⚠️ 待裁项在计划 §十一（已全部收口）· 模板运营流程仍开着 = **TODO-206**
7. **推送**：本轮提交**已授权 ⇒ 已推**

---

## Context

- main。**不要建 worktree** · **不要 `git checkout <commit> --detach`**。**不得擅自 push**。
  `.wolf/*` 里 `anatomy.md` / `memory.md` / `anatomy-index.json` 由 hook 维护。
- ⚠️ **每轮开工先查残留**：`fuser -v pcs-backend/.tmp/lane.lock` ·
  `pgrep -af "uvicorn app.main:app"` · `ss -ltnp | grep 5173`。
  ⚠️ **PG 车道被占 ⇒ 脚本直接 FAIL**（`flock -n`）⇒ ⇒ 先 `TaskStop` 掉旧的后台车道再跑。
- ⚠️ **默认车道零连真 PG** ⇒ ⇒ 跑 `pg` 用例**必须**走 `bash scripts/pytest_pg.sh`（**唯一入口**
  · 需 redis 起着）。
- ⚠️ **`.env` 口令不要写命令行** ⇒ 用 `dotenv_values('.env')` **进程内**派生 URL
  ⇒ ⇒ **一库一个进程**（alembic settings 是 pydantic 缓存实例）。
- ⚠️ **antd Select 的 placeholder 不是 `<input placeholder>`** ⇒ ⇒ `getByPlaceholderText`
  找不到 ⇒ ⇒ 用 `.ant-select-selection-placeholder` 的文本；驱动下拉照
  `tests/components/common/ProjectSelector.test.tsx`（`mouseDown(.ant-select-selector)`）。
  ⚠️ 按钮带图标 ⇒ 可访问名含图标 aria-label ⇒ ⇒ 用**正则**不用全等。
- ⚠️ **子代理 Bash 会挂起** ⇒ 派发审阅/实现子代理**只给 Read/Grep**。

---

## 教训（**已进 cerebrum / docs/solutions / buglog**，此处只留最新）

- ⚠️ **「查不到元素」有三种原因**：元素真没渲染 · **查询方式不对**（antd Select 的 placeholder）
  · **断言恒真**（`queryByPlaceholderText` 找不到就恒 null ⇒ 假绿 ⇒ ⇒ 换真断言）。
- ⚠️ **「走 API 建会先被应用层 409」⇒ 那条 DB 约束的测试是假证据** ⇒ ⇒ 必须**直连 ORM**
  ⇒ ⇒ ⇒ PG 独有语义（`postgresql_nulls_not_distinct`）**SQLite 证不了**。
- ⚠️ **契约新增可选字段 ⇒ CI 不红** ⇒ ⇒ ⇒ 实现纪律 = **手工跑 `npm run api:gen`** +
  **三份都提交** + 手工 `npm run api:check`。
- ⚠️ **「已覆盖」要能复核** ⇒ 判据 = **这条断言用的是 `strict_client`**。
- ⚠️ **指标「定义了」≠「有值」** ⇒ 无标签 gauge **创建即报 0** ⇒ 假零比没有更坏。
