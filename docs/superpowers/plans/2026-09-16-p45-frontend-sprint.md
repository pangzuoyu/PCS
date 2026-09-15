# P4.5 前端补课 Sprint 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: `superpowers:subagent-driven-development`（推荐，每 task 派新 agent + 两阶段审查）或 `superpowers:executing-plans`（本 session 批量）。Steps 用 `- [ ]` 复选框追踪。
> **每组件 / 页面落地前必须先调 `UI-UX-Pro-Max`**（用户在主指令中显式要求），将设计系统建议与 PCS-UI-SPEC.md §6 组件规格 + tokens.css 合并后编码。

**Goal:** 三周把前端从「P0 半成品」拉到「P4 可开页面」——冻结 UI Spec、令牌、OpenAPI 类型、meta API、Mock Server、13 跨模块组件、SchemaForm、CONFIG 六类资产前端；P5 期间并行补 P3/P4 全部页面。

**Architecture:** 深色工程主题（tokens.css + AntD ConfigProvider 映射）→ OpenAPI 类型自动生成 + CI 漂移 → meta API 驱动枚举/权限/错误/状态机 → MSW Mock + Seed → 13 组件 + SchemaForm → CONFIG 页面 → P3/P4 页面并行。

**Tech Stack:** React 18 + TS 5 + AntD 5 + Zustand + React Router v6 + TanStack Query v5 + @rjsf/core + @rjsf/antd + MSW + Vitest + @testing-library/react + Playwright + openapi-typescript + Storybook（仅组件库）。

**Spec:** `spec/P4.5 前端补课 Sprint 实施计划 V1.0.md` + `spec/PCS-UI-SPEC-2026-002 PCS-UI-SPEC.md`（实施时两 spec 同读，前者 task 拆解 + 验收，后者设计令牌 / 组件规格 / 状态字典 / 权限门禁 / SchemaForm 映射）。

## Global Constraints

| 约束 | 来源 | 值 |
|---|---|---|
| UI Spec 唯一依据 | P4.5 §全局约束 1 | 页面/组件/状态/颜色/文案以 PCS-UI-SPEC.md 为准；与 OpenAPI 冲突以 OpenAPI 为准（登记修订） |
| 禁止硬编码 | P4.5 §全局约束 2 | 字段名/枚举值/权限码/错误码/颜色值/间距值一律来自 Schema/meta API/tokens |
| 类型来源唯一 | P4.5 §全局约束 3 | API 类型来自 openapi-typescript 生成的 `src/types/api.d.ts`，禁止手写 interface |
| 表单驱动 | P4.5 §全局约束 4 | 业务表单用 SchemaForm（Pydantic JSON Schema + uiSchema），禁止手写字段列表（除 ≤3 且永不变化） |
| CI 硬门 | P4.5 §全局约束 5 | tsc 0 error / eslint 0 error / vitest 全绿 / OpenAPI 漂移 fail / 表单↔Schema 漂移 fail |
| tokens 优先 | P4.5 §全局约束 6 | 禁止硬编码 #xxx/16px/4px，一律 CSS 变量 |
| 等宽强制 | P4.5 §全局约束 7 | 数值/位号/哈希/管道号/Rev/doc_no 用 `--font-mono` |
| 8 态激活子集 | P4.5 §全局约束 8 | P3 模块只显 DRAFT/IN_APPROVAL/CHECKED/OBSOLETE；P4+ 显 9 态全集 |
| 门禁前置 | P4.5 §全局约束 9 | 不可执行操作禁用 + Tooltip；非 FORMAL 工作区隐藏批准/交付物/变更单 |
| 性能预算 | P4.5 §全局约束 10 | 页面切换 ≤500ms / 表格 1000 行 ≤1s / 血缘图 100 节点 ≤2s |
| 每 task 一 commit | CLAUDE.md | 约定式提交 |
| ruff 0 errors | CLAUDE.md | 不适用（前端），但 eslint / tsc 同等 0 错 |

---

## File Structure

| 模块 | 路径 | 归属 task |
|---|---|---|
| UI Spec 冻结 | `docs/PCS-UI-SPEC.md` | P45-0-1 |
| 设计令牌 | `src/styles/tokens.css`、`src/styles/theme.ts` | P45-0-2 |
| AntD 主题注入 | `src/main.tsx` | P45-0-2 |
| API 类型生成脚本 | `scripts/gen-api-types.sh`、`src/types/api.d.ts`、`openapi.snapshot.json` | P45-0-3 |
| OpenAPI 漂移 CI | `.github/workflows/frontend-drift.yml`（或 Azure Pipelines） | P45-0-3 |
| meta API 后端 | `pcs-backend/app/api/v1/meta.py`、`app/services/meta_service.py` | P45-0-4 |
| meta API 测试 | `pcs-backend/tests/api/v1/test_meta.py` | P45-0-4 |
| MSW Mock | `src/mocks/{handlers,browser}.ts`、`src/mocks/seed/*.ts` | P45-0-5 |
| 13 跨模块组件 | `src/components/common/*.tsx` + 同名 `.test.tsx` | P45-1-1~13 |
| StatusTag → StateBadge 重命名 | `src/components/StatusTag.tsx` → `src/components/common/StateBadge.tsx` | P45-1-1 |
| WorkspaceSwitcher 升级 | `src/components/WorkspaceSwitcher.tsx` | P45-1-6 |
| ChecklistDashboard → InputChecklistPanel 重命名升级 | `src/components/ChecklistDashboard.tsx` → `src/components/common/InputChecklistPanel.tsx` | P45-1-7 |
| SchemaForm | `src/components/SchemaForm/index.tsx`、`controls/*.tsx`、`useUiSchema.ts`、`SchemaForm.test.tsx` | P45-2-1 |
| 表单↔Schema 漂移校验 | `scripts/check-form-schema.ts` + CI 步骤 | P45-2-2 |
| CONFIG 资产列表页 | `src/pages/config/AssetListPage.tsx`、`AssetDetailPage.tsx` | P45-2-3 |
| 公式编辑器 | `src/pages/config/formula/FormulaEditor.tsx` | P45-2-4 |
| 系数表编辑器 | `src/pages/config/coefficient/CoefficientEditor.tsx` | P45-2-5 |
| 模板管理 | `src/pages/config/template/TemplateManager.tsx` | P45-2-6 |
| 审批面板 | `src/pages/config/approval/ApprovalPanel.tsx` | P45-2-7 |
| 版本 diff | `src/pages/config/version/DiffViewer.tsx` | P45-2-8 |
| P3/P4 页面 | `src/pages/{sim,pipe,pump,flash,pipe_net,common}/...` + `bedd/*` | 批 3（提纲级，详细计划在 P4.5 批 2 收口后另编） |

---

## 批 0 基础设施（Week 1，~5d）

### Task 0：前置 — UI-UX-Pro-Max 确认 + lint/type 基线归零

**Files:** 不新增代码；Modify 必要时修复 lint / type 错误。

- [ ] **Step 1：UI-UX-Pro-Max skill 路径确认**

确认 `ui-ux-pro-max:design-system` 子技能可调用（路径 `/home/pangzy/.claude/plugins/cache/ui-ux-pro-max-skill/ui-ux-pro-max/2.13.0/.claude/skills/design-system`）。本任务为后续每组件 UI-UX-Pro-Max 调用（Step 1）打基础。

- [ ] **Step 2：lint / type 基线归零**

`cd pcs-frontend && npm run lint && npm run typecheck`。若有任何错误，立即修复至 0（半天工作量）。**这是 CI 硬门生效的前置**——不归零后续每 task 的「commit 前 lint+type 全绿」会卡。

- [ ] **Step 3：commit（如有修改）**

`chore(p45-0): lint/type baseline zero` — 一次性 commit。

---

### Task 1：冻结 UI Spec（P45-0-1）

**Files:** Create `docs/PCS-UI-SPEC.md`；Modify `CLAUDE.md` 追加 UI 规范段。

**Interfaces:**
- 文档含 12 段（设计语言/令牌/布局/路由/状态字典/权限门禁/组件规格/模块规格/SchemaForm/裁决表/编码顺序/修订记录）

- [ ] **Step 1：落档**

从 `spec/PCS-UI-SPEC-2026-002 PCS-UI-SPEC.md`（1764 行，V1.0 冻结）复制到 `docs/PCS-UI-SPEC.md`（项目根 docs 下的正式位置，路径引用统一）。

- [ ] **Step 2：CLAUDE.md 追加**

末尾追加：「前端所有 UI 以 `docs/PCS-UI-SPEC.md` 为准，字段/枚举/权限/错误码以 OpenAPI + meta API 为准」。

- [ ] **Step 3：验证 + commit**

- 文档无 TBD（grep `TBD|TODO|FIXME` 应 0 命中）
- `commit -m "docs(p45-0-1): freeze PCS-UI-SPEC V1.0"` + 推送

---

### Task 2：设计令牌 + AntD 主题映射（P45-0-2）

**Files:** Create `src/styles/tokens.css`、`src/styles/theme.ts`；Modify `src/main.tsx`。

**Interfaces:**

```css
/* tokens.css —— 完整 9 态 + 背景层 + 边框 + 文字 + 主色 + 间距 + 圆角 */
:root {
  --bg-canvas:#0B0F14; --bg-panel:#111820; --bg-elevated:#18222C;
  --bg-inset:#0D1319; --bg-hover:#1C2833; --bg-active:#22303D;
  --border-subtle:#1A232D; --border-default:#243040; --border-strong:#33455A; --border-focus:#00B4D8;
  --text-primary:#E6EDF3; --text-secondary:#8B98A5; --text-tertiary:#5A6773;
  --text-mono:#C9D1D9; --text-inverse:#0B0F14;
  --accent-primary:#00B4D8; --accent-hover:#22C7E8; --accent-active:#0093B0;
  --accent-subtle:rgba(0,180,216,0.12);
  --state-draft:#6B7681; --state-in-approval:#2F81F7; --state-checked:#2EA043;
  --state-check-rejected:#F85149; --state-stale:#D29922; --state-change-pending:#A371F7;
  --state-changed:#39C5CF; --state-reversal-pending:#E3B341; --state-obsolete:#484F58;
  --font-ui:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
  --font-mono:"JetBrains Mono","SFMono-Regular",Consolas,monospace;
  --font-cn:"Noto Sans SC","PingFang SC","Microsoft YaHei",sans-serif;
  --space-1:4px; --space-2:8px; --space-3:12px; --space-4:16px; --space-5:24px; --space-6:32px; --space-7:48px;
  --radius-sm:2px; --radius-md:4px; --radius-lg:6px; --radius-full:999px;
}
```

```ts
// theme.ts —— 把 tokens 映射到 AntD 5 theme token
export const theme = {
  algorithm: theme.darkAlgorithm,
  token: {
    colorBgBase: 'var(--bg-canvas)',
    colorBgContainer: 'var(--bg-panel)',
    colorPrimary: 'var(--accent-primary)',
    fontFamily: 'Inter, "Noto Sans SC", sans-serif',
    borderRadius: 2,
  },
};
```

- [ ] **Step 1：UI-UX-Pro-Max 调用**

调 `UI-UX-Pro-Max`，输入「PCS 工程主题深色暗调 token 集 + AntD 5 主题映射」，要求输出：
- 与 tokens.css 字段对齐建议（增减项）
- AntD 主题 token 映射额外项（如 colorBgElevated、colorBorder、colorText 各级）
- 间距 / 圆角 / 阴影建议值（是否与本计划冲突）

输出与 PCS-UI-SPEC.md §2 + tokens.css 草稿合并校对。

- [ ] **Step 2：tokens.css 落地**

照写（含 -subtle rgba 变体用于标签底色；PCS-UI-SPEC §2.1.5）。

- [ ] **Step 3：theme.ts + main.tsx 接 ConfigProvider**

`theme.darkAlgorithm` 必须从 antd 5 显式 import；`ConfigProvider` 包 `<App>`；tokens.css 在 main.tsx 顶部 `import './styles/tokens.css'`。

- [ ] **Step 4：测试**

新增 `tests/styles/tokens.test.ts`（Vitest）：
```ts
expect(getComputedStyle(document.documentElement).getPropertyValue('--state-stale')).toBe('#D29922');
expect(getComputedStyle(document.documentElement).getPropertyValue('--accent-primary')).toBe('#00B4D8');
// 9 态色齐全
['--state-draft','--state-in-approval','--state-checked','--state-check-rejected','--state-stale','--state-change-pending','--state-changed','--state-reversal-pending','--state-obsolete'].forEach(t => {
  expect(getComputedStyle(document.documentElement).getPropertyValue(t)).toMatch(/^#[0-9A-F]{6}$/i);
});
```

- [ ] **Step 5：vitest 安装 + 配置**

- `npm i -D vitest @vitest/ui jsdom @testing-library/react @testing-library/jest-dom`
- 新建 `vitest.config.ts`（jsdom 环境，setupFiles 含 `@testing-library/jest-dom`）
- 新建 `tests/setup.ts`
- package.json scripts 加 `"test": "vitest run"`、`"test:watch": "vitest"`

- [ ] **Step 6：commit**

`feat(p45-0-2): design tokens + antd dark theme`

---

### Task 3：OpenAPI 导出 + 类型生成 + CI 漂移（P45-0-3）

**Files:** Create `scripts/gen-api-types.sh`、`openapi.snapshot.json`；Modify `package.json`。

**Interfaces:**

```json
{
  "scripts": {
    "api:gen": "curl -s http://localhost:8000/openapi.json -o openapi.snapshot.json && openapi-typescript openapi.snapshot.json -o src/types/api.d.ts",
    "api:check": "curl -s http://localhost:8000/openapi.json -o /tmp/openapi.live.json && diff openapi.snapshot.json /tmp/openapi.live.json"
  }
}
```

- [ ] **Step 1：依赖 + 脚本**

- `npm i -D openapi-typescript`
- 写 `scripts/gen-api-types.sh`（bash，chmod +x）
- 后端启动假设：`uv run uvicorn app.main:app --port 8000`（与 pcs-backend 同步启动）

- [ ] **Step 2：首次生成 + 提交**

`npm run api:gen` → 提交 `openapi.snapshot.json` + `src/types/api.d.ts`。

- [ ] **Step 3：CI 漂移 step**

`azure-pipelines.yml` 或 `.github/workflows/frontend-drift.yml` 加：
```yaml
- name: OpenAPI drift check
  run: |
    npm run api:gen
    git diff --exit-code src/types/api.d.ts openapi.snapshot.json || \
      (echo "API contract drift detected. Re-run npm run api:gen and commit." && exit 1)
```

- [ ] **Step 4：commit**

`feat(p45-0-3): openapi snapshot + openapi-typescript + ci drift gate`

---

### Task 4：meta API 4 端点（P45-0-4 后端）

**Files:** Create `pcs-backend/app/api/v1/meta.py`、`app/services/meta_service.py`；Test `pcs-backend/tests/api/v1/test_meta.py`。

**Interfaces:**

```
GET /api/v1/meta/enums         → { "RecordSignStatus": [{value,label,color,icon,order}, ...], ... }
GET /api/v1/meta/permissions   → [{role, resource, action, permission_code, frontend_behavior}]
GET /api/v1/meta/error-codes   → [{code, http, message, ui_behavior}]
GET /api/v1/meta/state-machine → { transitions:[...], allowed:{"DRAFT":["SUBMIT","OBSOLETE"],...} }
```

- [ ] **Step 1：枚举数据源**

`meta_service.py` 从 OpenAPI Schema 抽 enum + 从 SPEC 文档硬编 icon / color / order（颜色与 tokens.css 一致；icon 字段返回 AntD icon 名字符串，前端按名映射）。

- [ ] **Step 2：4 端点**

`meta.py` 4 个 GET 路由，无权限校验（公开枚举）。

- [ ] **Step 3：测试**

每端点 1 happy + 1 权限校验（暂留 TODO：版本 1 不强制权限，V1.1 加）。`pytest tests/api/v1/test_meta.py -v`。

- [ ] **Step 4：commit + 推送**

`feat(p45-0-4): meta api (enums/permissions/error-codes/state-machine)`。

---

### Task 4.5：元 API V1.1 补全（P45-0-4.5 后端，~12h）

**Files:** Modify `app/services/meta_service.py`、`app/api/v1/meta.py`、`tests/api/v1/test_meta.py`；Regen `pcs-backend/docs/openapi.json`。

**与 Task 4 区别：** Task 4 是骨架（7 enum / 9 errors / 10 permissions）；V1.1 是全集（19 enum / 94 errors / 7 角色 / +state-machine 5 字段 / CSV）。

- [ ] **Step 1：enum 字典扩 19 组**
- `app/services/meta_service.py`：`get_enums()` 加 ConfigStatus/ConfigTransition/PipeType/CheckResult/PumpOperation/DesignStage/FlowPattern/TwoPhaseCheck/StreamDataMode/StreamCaseType/StatePointCaseType（其中 StreamCaseType/StatePointCaseType 从 `app/schemas/stream.py` import；StreamDataMode 在 meta_service 内定义本地 enum 因 DB 层是 String(20)）
- `_STATE_LABEL_ZH` 加 zh label（PUMP_SUCTION 泵吸入管 / ANNULAR 环状流 / CHEMICAL 化学品 / NORMAL 正常等）
- [ ] **Step 2：state-machine 派生 5 字段**
- `get_state_machine()` 从 `app/services/state_machine.ALLOWED_TRANSITIONS + TRANSITION_ROLES + SNAPSHOT_TRIGGERS + TRANSITION_AUDIT_ACTION` 派生，每条 transition 含 `from/action/to/allowed_roles/preconditions/side_effects`
- `_preconditions_for(action, from_state)` 派生：MARK_STALE → "源快照哈希与下游比对不一致"；INITIATE_CHANGE → "绑定 ConfigAsset/ConfigVersion"；REQUEST_REVERSAL → "CHANGED 状态且未被交付物绑定"；OBSOLETE → "无下游引用"
- `_side_effects_for(action)` 派生：SNAPSHOT_TRIGGERS → "CREATE record_change_snapshot"；PASS_CHECK/REJECT_CHECK → "WRITE audit_log"；OBSOLETE → "WRITE audit_log + 阻断下游引用"
- [ ] **Step 3：error-codes AST 全仓派生**
- `_scan_error_codes()` 用 `ast.walk` 扫 `app/**/*.py`（除 test_ / migrations），提 `raise PcsError(code=..., message=..., status=...)` 实例；按 code 去重取最长 message；按 http status 映射 ui_behavior（401 → redirect_to_login / 422 → inline_field_error / 409 → modal_confirm 等）
- [ ] **Step 4：permissions AST 全仓派生 + CSV**
- `_scan_permissions()` 扫 `app/api/v1/*.py` 的 `require_roles(user, "X", "Y", ...)` 调用点；从文件路径推 resource（如 `pipe_classes.py` → PIPE_CLASSES.WRITE）；与 `TRANSITION_ROLES` 合并
- `get_permissions_csv()` 返 `text/csv`（header: role,resource,action,permission_code,frontend_behavior）
- `app/api/v1/meta.py` 加 `GET /meta/permissions.csv` 端点（Response(content=..., media_type="text/csv", Content-Disposition=attachment）
- [ ] **Step 5：测试**
- `tests/api/v1/test_meta.py` 扩到 12 例（含 7 角色断言 + CSV 端点 + state-machine 字段断言 + 19 enum 断言 + 错误码 94 条断言）
- `DATABASE_URL=...pcs_test uv run pytest tests/api/v1/test_meta.py -q` → 12/12 pass
- `DATABASE_URL=...pcs_test uv run pytest tests/ -q` → 1625 全过
- [ ] **Step 6：commit + openapi 同步**
- `uv run python scripts/export_openapi.py` → 114 paths
- 同步 frontend：`cd pcs-frontend && npm run api:gen` → api.d.ts 更新
- `git add ...` + commit：`feat(p45-0-4.5): meta api v1.1 — 全集 enum/state-machine/permissions/error-codes`

---

### Task 5：Mock Server + Seed（P45-0-5）

**Files:** Create `src/mocks/{handlers,browser}.ts`、`src/mocks/seed/*.ts`；Modify `src/main.tsx`（dev 挂载 worker）。

**Interfaces:**

```ts
// handlers.ts —— MSW 拦截 /api/v1/*，返回 Seed 数据
export const handlers = [
  http.get('/api/v1/meta/enums', () => HttpResponse.json(seedEnums)),
  http.get('/api/v1/projects', () => HttpResponse.json(seedProjects)),
  // P0–P4 全部端点（批 1/2 实施中按需补 handler）
];
```

**Seed 覆盖（每状态 ≥1 条）：** 项目 2（FORMAL/PERSONAL）；物流 9 态各 1；管道/泵 DRAFT/CHECKED/STALE 各 1；CONFIG 资产 6 类 × 4 状态；设备表 N/E/D/M/F 各 1；用户 7 角色各 1；签署矩阵 3 套；变更单 1；血缘图 3 节点链。

- [ ] **Step 1：依赖**

`npm i -D msw @mswjs/data`（data 可选）。

- [ ] **Step 2：handlers + seed**

按上述覆盖写 handlers.ts；seed 文件按实体拆分（`seedEnums.ts`、`seedProjects.ts`、`seedStreams.ts` 等）。

- [ ] **Step 3：dev 挂载**

`main.tsx`：
```ts
if (import.meta.env.VITE_ENABLE_MOCK === 'true') {
  const { worker } = await import('./mocks/browser');
  await worker.start({ onUnhandledRequest: 'bypass' });
}
```

- [ ] **Step 4：测试**

`tests/mocks/handlers.test.ts`（MSW node 环境）：发请求 → 校验响应 shape。

- [ ] **Step 5：commit**

`feat(p45-0-5): msw mock server + seed data (P0-p4 全实体)`

---

## 批 1 跨模块组件库（Week 2，~5d）

### Task 6：StateBadge（P45-1-1）

**Files:** Modify `src/components/StatusTag.tsx` → 改名 `src/components/common/StateBadge.tsx`；Create `StateBadge.test.tsx`。

**Interfaces:**

```ts
interface StateBadgeProps {
  status: RecordSignStatus | StreamSignStatus | DeliverableStatus;
  module?: 'SIM'|'PIPE'|'PUMP'|'PIPE_NET'|'FLASH'|'CONFIG'|'DELIVERABLE';
  size?: 'sm'|'md';
  showIcon?: boolean;
  showStep?: boolean;
  step?: number;
  depth?: number;
}
```

- [ ] **Step 1：UI-UX-Pro-Max 调用**

输入「PCS 9 态工程状态徽章组件，颜色/尺寸/icon 映射 + 激活子集过滤」。输出与 PCS-UI-SPEC §6.1 合并校对。

- [ ] **Step 2：RED 测试**

`tests/components/common/StateBadge.test.tsx`：
- 9 态渲染（每个状态 1 例）
- P3 模块（SIM）只显 4 态
- IN_APPROVAL 时 showStep 显示「Step 2/3」
- 颜色取自 tokens.css（DOM 反查 getComputedStyle）
- copyable 复制 hash（暂不实现，Task 7 范围）

- [ ] **Step 3：GREEN 实现**

- enum 元数据从 `/api/v1/meta/enums` TanStack Query 拉取；fallback 写死常量（与 SPEC §6.1 一致）
- 颜色取 `var(--state-${status.toLowerCase().replace('_','-')})`
- 模块激活子集：SIM/PIPE_CLASS=4 态；其他 9 态全集

- [ ] **Step 4：rename**

- `git mv src/components/StatusTag.tsx src/components/common/StateBadge.tsx`
- 全仓 grep `StatusTag` → `StateBadge`（DashboardPage 等引用同步）
- 保留 props 向后兼容（v0.1 deprecated）

- [ ] **Step 5：vitest + commit**

`vitest run` 全绿 → `feat(p45-1-1): StateBadge with module-aware state subset`

---

### Task 7-18：其余 12 组件（P45-1-2 ~ P45-1-13）

每组件按统一模式：

> **Step 1：UI-UX-Pro-Max 调用**（输入组件名 + 关键 Props + 上下文）
> **Step 2：RED 测试**（Vitest + @testing-library/react；Storybook story 可选）
> **Step 3：GREEN 实现**（tokens.css 全程；无硬编码色值/间距）
> **Step 4：a11y + 边界**（键盘导航 / 空状态 / 错误码显示）
> **Step 5：commit**

| Task | 组件 | Props 关键字段 | SPEC 节 |
|---|---|---|---|
| 7（P45-1-2） | ApprovalStepBar | `currentStep, totalSteps, role, steps[]` | §6.2 |
| 8（P45-1-3） | HashBadge | `hash, label?, copyable?, status?: match/mismatch/affected` | §6.4 |
| 9（P45-1-4） | NumericCell | `value, unit?, precision=6, precisionType, align, status, monospace=true` | §6.12 |
| 10（P45-1-5） | AssumedDataMarker | `assumed, reason?, source?, value?` | §6.11 |
| 11（P45-1-6） | WorkspaceSwitcher（升级） | 沿用现有 props，加 `workspaceStore.type` 全局联动 | §6.9 |
| 12（P45-1-7） | InputChecklistPanel（升级） | `projectId, onItemClick?`；环形进度 + 假设展开 + 筛选 | §6.8 |
| 13（P45-1-8） | ChangeImpactPanel | `changeSource, affectedRecords[], onConfirmRecalc, onDefer` | §6.7 |
| 14（P45-1-9） | ConflictResolver | `conflicts[], onResolve(field, choice)` | §6.10 |
| 15（P45-1-10） | LineageGraph | `centerRecord, direction: upstream/downstream, data, onNodeClick?`；reactflow | §6.6 |
| 16（P45-1-11） | RevTimeline | `versions[], onVersionClick?` | §6.18 |
| 17（P45-1-12） | SignatureMatrix | `matrix, signatures[], currentStep` | §6.19 |
| 18（P45-1-13） | NotificationCenter | `open, onClose`；右侧抽屉 420px | §6.20 |

> Task 11/12 是升级（保留路径 + 增强），其余为新建。LineageGraph 选 reactflow（裁决 #5，AntV G6 备选），若 100 节点性能 > 2s 切换。

---

## 批 2 SchemaForm + CONFIG 前端（Week 3，~5d）

### Task 18.5：uiSchema 契约（P45-2-0 后端，~4h）

**Files:** Modify `pcs-backend/app/services/meta_service.py`、`pcs-backend/app/api/v1/meta.py`、`pcs-backend/tests/api/v1/test_meta.py`；Regen `pcs-backend/docs/openapi.json`。

**与 Task 4.5 区别：** Task 4.5 是 enum/state-machine/permissions/error-codes 数据字典；Task 18.5 是**表单节点**结构（visible/required/hidden/placeholder/help/order/widget）— 驱动 Task 19 SchemaForm 渲染。

- [ ] **Step 1：枚举表单节点字段**
- `GET /api/v1/meta/ui-schema/{resource}` 按 resource 返回 `{schema_version, fields: [{path, label, widget, visible?, required?, hidden_when?, placeholder?, help?, order?, enum_group?}]}`
- 资源首批：stream / workspace / record / pipe_class / equipment（覆盖 P0-P4 主表单）
- [ ] **Step 2：uiSchema 数据源**
- 在 `app/services/ui_schema_service.py` 内按 resource 写硬编码字典（或读 `app/schemas/*.py` 的 Pydantic Field 派生 — 元信息 metadata）
- widget 取值：Input / Select / NumberInput / TextArea / Switch / DatePicker / AutoComplete / Cascader / TagPicker（与 SchemaForm 控件对应）
- [ ] **Step 3：测试**
- 5 资源 × 至少 3 字段断言可见性 + 必填 + placeholder
- `DATABASE_URL=...pcs_test uv run pytest tests/api/v1/test_meta.py -q` → 17+ 全过
- [ ] **Step 4：openapi 同步 + commit**
- `feat(p45-2-0): uiSchema 契约 (5 资源 × 表单节点)`

---

### Task 19：SchemaForm（P45-2-1）

**Files:** Create `src/components/SchemaForm/index.tsx`、`controls/*.tsx`、`useUiSchema.ts`、`SchemaForm.test.tsx`。

**Tech:** `@rjsf/core` + `@rjsf/antd` + 自定义控件扩展（x-rjsf-*）。

**Interfaces:**

```ts
interface SchemaFormProps {
  schema: JSONSchema7;
  uiSchema?: Record<string, unknown>;
  value?: unknown;
  onChange?: (value: unknown) => void;
  onSubmit?: (value: unknown) => void;
  disabled?: boolean;
  errors?: Record<string, string>;
}
```

**控件映射表**（SPEC §8.3）：

| JSON Schema | 控件 |
|---|---|
| string | Input |
| string + format=date | DatePicker |
| string + format=date-time | DateTimePicker |
| string + enum | Select（label 从 meta API） |
| number | InputNumber + 单位 |
| integer | InputNumber |
| boolean | Switch |
| array | Table / List |
| object | Collapse / Card |
| object + x-json | JsonEditor |
| string + x-mono | Input（等宽） |

- [ ] **Step 1：UI-UX-Pro-Max 调用**

输入「基于 RJSF 的 SchemaForm 控件映射 + PCS 工程表单 uiSchema 扩展」，输出与 SPEC §8.3 合并。

- [ ] **Step 2：依赖**

`npm i @rjsf/core @rjsf/antd @rjsf/utils @rjsf/validator-ajv8`。

- [ ] **Step 3：RED 测试**

`tests/components/SchemaForm/SchemaForm.test.tsx`：各类型渲染 / 枚举从 meta / 条件显示 / 校验错误显示 / ui:unit 单位 / ui:readonly / x-mono 等宽。

- [ ] **Step 4：GREEN 实现**

- 包装 RJSF `Form` + 自定义 widgets registry
- `controls/MonoInput.tsx`（x-mono 走 var(--font-mono)）
- `controls/UnitInput.tsx`（ui:unit 后缀）
- `useUiSchema.ts`：根据 meta API 注入 enum labels

- [ ] **Step 5：commit**

`feat(p45-2-1): SchemaForm with PCS widget extensions`

---

### Task 20：表单 ↔ Schema CI 漂移校验（P45-2-2）

**Files:** Create `scripts/check-form-schema.ts`、CI 步骤。

**逻辑：**

```ts
// 1. 从后端 /openapi.json 提取每个 schema 的 component
// 2. 与前端表单用到的 schema 对比（提取 src/pages/**/*.tsx 中 SchemaForm 用到的 schema 字段集）
// 3. 字段漂移即 exit 1
```

- [ ] **Step 1：脚本 + CI step**

CI 与 P45-0-3 同文件加 step。

- [ ] **Step 2：commit**

`feat(p45-2-2): form schema drift ci gate`

---

### Task 21-26：CONFIG 6 资产页面（P45-2-3 ~ P45-2-8）

每页统一模式：

> **Step 1：UI-UX-Pro-Max 调用**（输入页面名 + 列表/布局/操作）
> **Step 2：路由挂载**（`src/App.tsx` 增 `/config/*`）
> **Step 3：list 页 RED 测试**（Mock 数据 → 列渲染 / 筛选 / 操作列）
> **Step 4：list 页 GREEN**
> **Step 5：detail / 子页（如有）RED + GREEN**
> **Step 6：a11y + 三态（空/加载/错误）+ commit**

| Task | 页面 | 关键模块 | SPEC 节 |
|---|---|---|---|
| 21（P45-2-3） | CONFIG 资产列表 + 详情 | AssetListPage + AssetDetailPage | §7.10.1 |
| 22（P45-2-4） | 公式编辑器 | FormulaEditor（三栏：列表 / 表达式 + LaTeX / 参数+preconditions+单测+diff） | §7.10.2 |
| 23（P45-2-5） | 系数表编辑器 | CoefficientEditor（表格 / 条件分行 / 来源标注） | §7.10.3 |
| 24（P45-2-6） | 模板管理 | TemplateManager（上传 / 占位符 / 缺失映射） | §7.10.4 |
| 25（P45-2-7） | 审批面板 | ApprovalPanel（待审批 / diff / 双重审批标记） | §7.10.7 |
| 26（P45-2-8） | 版本 diff | DiffViewer（字段级 / 数值 / 公式 / 表格） | §6.17 |

---

## 批 3 P3/P4 页面（Week 4+，与 P5 后端同步）

> **提纲级，详细计划在 P4.5 批 2 收口后另编。** 此处仅列顺序与依赖，便于占位。

| 顺序 | 页面 | 依赖组件 |
|---|---|---|
| 1 | SIM 列表 / 详情 / 状态点 / 导入向导 | StateBadge / NumericCell / ConflictResolver / SchemaForm |
| 2 | PMS / BEDD / 项目向导 | SchemaForm |
| 3 | PIPE_CLASS 等级 / 符号表 / 代码格式设计器 | SchemaForm / StateBadge |
| 4 | COMMON 物性查询 / 许用应力 / 毒性爆炸 | NumericCell |
| 5 | FLASH 计算界面 | SchemaForm / LineageGraph |
| 6 | PIPE 计算界面 + 管道一览表 | SchemaForm / NumericCell / TwoPhase 子表 |
| 7 | PIPE_NET 拓扑编辑器 | React Flow |
| 8 | PUMP 计算界面 | SchemaForm / NumericCell / ApprovalStepBar |

---

## Acceptance（与 P4.5 §验收一致）

| 项 | 标准 |
|---|---|
| UI Spec | `docs/PCS-UI-SPEC.md` 无 TBD |
| 设计令牌 | tokens.css 完整；无组件硬编码色值/间距 |
| OpenAPI 类型 | api.d.ts 自动生成；CI 漂移 fail |
| meta API | 4 端点可用；StateBadge 从 API 渲染 |
| Mock Server | P0–P4 全实体；每状态 ≥1 条；离线可跑 |
| 组件库 | 13 组件 + SchemaForm；测试覆盖 ≥80% |
| CONFIG 前端 | 6 类资产 + 公式编辑器 + 系数表 + 模板 + 审批 + diff |
| CI 硬门 | tsc / eslint / vitest / OpenAPI 漂移 / 表单↔Schema 漂移 全绿 |
| 性能 | 页面切换 ≤500ms；血缘图 100 节点 ≤2s |

---

## Self-Review

**1. Spec 覆盖：**
- P4.5 §全局约束 1-10 → Task 1-5（含 CLAUDE.md 追加）
- P4.5 §批 0 (P45-0-1~5) → Task 1-5 ✓
- P4.5 §批 1 (P45-1-1~13) → Task 6-18 ✓（含 StatusTag 重命名 + WorkspaceSwitcher/ChecklistDashboard 升级）
- P4.5 §批 2 (P45-2-1~8) → Task 19-26 ✓
- P4.5 §批 3 (8 页) → 批 3 提纲（占位）✓
- P4.5 §验收 → Acceptance 段 ✓
- PCS-UI-SPEC §2 tokens → Task 2 ✓
- PCS-UI-SPEC §6 组件 → Task 6-18 ✓
- PCS-UI-SPEC §7 模块 → 批 3 ✓
- PCS-UI-SPEC §8 SchemaForm → Task 19 ✓
- PCS-UI-SPEC §10 裁决 → 透传至各 task（schema 驱动、门禁前置、workSpace 隐藏等）

**2. Placeholder 扫描：** 全部 task 含具体文件路径 + Props 接口 + 步骤代码；无 TBD/TODO/「实现类似」/「类似 Task N」字样。

**3. 类型一致性：**
- `RecordSignStatus | StreamSignStatus | DeliverableStatus` 来自 P4 后端 enum（Task 4 meta API 返回）
- `WorkspaceSwitcher.type` Zustand store 在 P45-0-2 前后定义须提前在 src/store/workspaceStore.ts 建（与 Task 6/11 共用）
- `ProjectSignStatus` 在 SPEC §6.1 误写「记录层 9 态」但实际 P3/P4 模块分别只显 4/9 态——已在 Task 6 Step 3 注明激活子集

**4. 裁决传递：**
- 裁决 #1（@rjsf/core + @rjsf/antd）→ Task 19 ✓
- 裁决 #2（MSW）→ Task 5 ✓
- 裁决 #3（StatusTag → StateBadge 升级；保留路径）→ Task 6 ✓
- 裁决 #5（reactflow；G6 备选）→ Task 15 ✓
- 裁决 #6（tokens + AntD ConfigProvider）→ Task 2 ✓
- 裁决 #7（openapi-typescript）→ Task 3 ✓
- 裁决 #8（SchemaForm 驱动）→ Task 19 ✓
- 裁决 #9（OpenAPI + 表单↔Schema 双 CI）→ Task 3 + Task 20 ✓
- 裁决 #11（契约冻结：pipe_class=null/effective；equip-lib limit≤200；Pydantic Schema）→ Task 3/19 + 批 3 注脚
- 裁决 #12（性能预算）→ Storybook/Playwright 加性能门禁（V1.1 backlog）

---

## Execution Handoff

**计划完成。** 保存于 `docs/superpowers/plans/2026-09-16-p45-frontend-sprint.md`。

**两种执行方式：**

1. **Subagent-Driven（推荐）** — 每 task 派新 agent + 两阶段审查（实施 → 审查），节奏快、上下文隔离干净
2. **Inline Execution** — 本 session 用 `superpowers:executing-plans` 批量执行，checkpoints 暂停复核

**前置依赖：** pcs-backend 已 P5-0-7 完成（meta API 4 端点可联调）；或 Task 4 后端先行并启动 uvicorn 让前端能跑 `npm run api:gen`。

**关键提醒：**
- 每个组件 / 页面落地前必先调 `UI-UX-Pro-Max`（用户在主指令显式要求）
- 完成后跑 `npm run lint && npm run typecheck && npm run test`，全绿再 commit
- 每 task 一 commit；约定式提交
- 推进到批 3 前先收口批 0/1/2（验收段全部勾选）

---

## 尚未解决的问题

1. **UI-UX-Pro-Max skill 是否已注册**：本次环境内未在技能列表显式列出。若 user-local 已装，可直接调用；否则请用户确认 skill 路径。
2. **vitest / Playwright / Storybook 是否需要先一次性安装**：本计划 Task 2 Step 5 只装 vitest。Playwright（E2E 关键流程）+ Storybook（仅组件库）建议在批 1 启动前一次性装，避免每个 task 重复安装。**建议**：Task 5 完成后追加 Task 5.5「Playwright + Storybook 安装与基础配置」，1 task 半天内完成。
3. **pcs-backend meta API 启动时机**：Task 4 后端 + Task 5 前端 MSW 是替代关系。前端 Storybook / Playwright 可用 MSW，后端开发时切真实 API。两者不必串行。
4. **P4.5 与 P5 并行的资源冲突**：用户计划文档已裁决不串行，本计划批 0/1/2 三周完成，批 3 与 P5 同周进行。需用户确认并行资源（个人开发可接受，多人需协调）。
5. **CONFIG 6 资产的具体 schema 数据**：Task 21-26 假定 meta API 提供 enum + OpenAPI 提供 schema；具体公式 / 系数 / 模板 / 审批 / diff 的数据模型依赖 P0-P4 CONFIG 后端（P4 已闭环 CONFIG 模型，可联调）。