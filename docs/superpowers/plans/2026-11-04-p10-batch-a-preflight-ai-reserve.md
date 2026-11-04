# P10-A 实施计划：前置与测试左移（10.0）+ AI 预留接口（10.1）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ① 把 SPEC 10.0 的「前置与测试左移」按**仓里实际缺什么**补齐（compose 测试组 · 种子数据 · 真后端 E2E 通道）；② 落地 SPEC 10.1 的 **AI 预留接口**（路由 501 · 审计表加列 · 递归脱敏 · OutboundAIClient · CIDR 校验 · 审计中间件 · `/health/ai` · 前端占位）。

**Architecture:** AI 能力**只做"预留"** —— 路由一律返回 501 `AI_NOT_IMPLEMENTED`，但**审计链路是完整的**（中间件 → ARQ → `ai_audit_log`），因为「AI 还没上线」不等于「AI 调用不用留痕」。审计表**给仓里既有的 `ai_audit_log` 加列**（SUP-006 字段不动）⇒ 一次迁移。

**Tech Stack:** FastAPI · SQLAlchemy 2.x async · Pydantic v2 · alembic · ARQ + Redis · pytest（asyncio_mode=auto）· Playwright · React 19 + antd 5 + vitest

**Spec:** `spec/PCS-SPEC-P10 V1.3.1 P10 AI预留与测试部署开发规格说明书.md` §3.2.0（10.0）· §3.2.1（10.1）· §4.1（接口定义）· 批次顺序见 `docs/superpowers/plans/2026-11-04-p10-master-plan.md`

---

## Global Constraints

- **分支 `main`，不要建 worktree**；**conventional commits，不带 attribution 行**；长消息写文件后 `git commit -F`。
- ⚠️ **口令不要写在命令行**；⚠️ **不要用 `git checkout <commit> --detach`**。
- ⚠️ **改 `alembic/versions/*` ⇒ 必须手动核对 ORM 列同步**（本仓漂移盲区）。且**两库各跑一次独立进程**的 `alembic check` + **直查库**的 `alembic_version`（⚠️ 同进程第二次改 `DATABASE_URL` 不生效 —— pydantic 缓存）。
- 迁移的 `op.create_index` **必须带 `if_not_exists=True`**（`scripts/check_migration_idempotency.py` 的规则）；`op.add_column` 不检查（PG 不支持 `IF NOT EXISTS`）。
- 契约改动 ⇒ 批末滚 OpenAPI baseline + G-08 `--check-baseline`；**裸载荷数不得上涨**（新端点用**具名 schema**）。
- 前端类型**契约派生** ⇒ 后端加字段后重跑 `npm run api:gen` + 同步 MSW mock（seed 走 ajv 校验 ⇒ 漏字段即红）。
- ⚠️ **不新建 CI 流水线**（现有 `check-api-drift.yml` 已在全新 PG 跑 `alembic upgrade head`）。
- ⚠️ **不换 compose 镜像**（`postgres:18-alpine` 不带 vector 扩展 ⇒ 本批不建 pgvector ⇒ 不需要换）。
- ⚠️ **不新建 `docker-compose.test.yml`** ⇒ 用现有 compose 的 **profile**。

---

## Review Focus

1. **AI 路由的审计必须在「认证失败」时也留下记录**（`user_id=None`）—— 否则用无效 token 探测 AI 端点**不留痕** ⇒ 审计表对探测行为完全失明。（T10）
2. **中间件读完 body 后下游 Pydantic 仍要能收到 body** —— 纯 ASGI 中间件若吞了 body，AI 路由会报 422 而不是 501 ⇒ **症状与「参数错」无法区分**。（T10）
3. **AI 审计写库必须幂等**（同一 `request_id` 重试不产生第二行）—— ARQ 的 `max_tries` 重试若不幂等 ⇒ 一次请求留下 N 条审计 ⇒ 审计表被灌水。（T11）
4. **种子数据脚本必须可重复执行**（幂等）—— E2E 每次跑之前都要重置 ⇒ 不幂等 ⇒ 第二次跑要么撞唯一约束、要么留下脏数据让断言飘。（T2）
5. **E2E 的页面导航必须走 SPA 菜单点击** —— 本仓 zustand auth store 是**内存态** ⇒ `page.goto` / `reload` 会清 session ⇒ 弹回 `/login` ⇒ 表格永远没有行。（T3）

---

## 事实基础（2026-11-04 实测，非推断）

| 事实 | 证据 |
|---|---|
| alembic head = **`p9_015`** | `alembic/versions/` 最新 = `p9_015_stream_source.py` ⇒ 本批新迁移 `p10_001`，`down_revision = "p9_015"` |
| `ai_audit_log` / `document_chunks` **已存在** | `app/models/system.py`：`AiAuditLog`（SUP-006 强制，11 个字段）· `DocumentChunk`（7 个字段，含 `embedding_vector JSONB`）⇒ **本批只给 `ai_audit_log` 加列**，`document_chunks` **不动**（偏离登记 D6） |
| 无任何 AI 代码 | 无 `app/api/v1/ai/` · 无 `app/core/ai_sanitizer.py` · 无 `app/core/outbound_ai_client.py` · 无 `/health/ai` |
| 认证依赖是 **`current_actor`**（不是 spec 的 `current_user`） | `app/api/v1/config.py:483` ⇒ 返回 `_Actor`（`user_id` / `username` / `role`）；`roles` 是 `@property` ⇒ 恒为 `[self.role]` |
| JWT 验签入口 | `app/core/security.py:115::decode_token(token) -> dict`；`app/api/v1/auth.py:119::_decode_bearer`（抛 `PcsError`）⇒ **中间件里要用 `decode_token` 并捕获异常**（不能抛 `PcsError`，那会变成 401） |
| 已有 `add_trace_id` 中间件 | `app/main.py:135` ⇒ 生成 `uuid4().hex`（**32 位无连字符**）写 `request.state.trace_id` ⇒ AI 的 `request_id` 要**另生成**标准 UUID 串（偏离登记 D8） |
| ARQ worker 已注册任务表 + 棘轮 | `app/workers/worker.py::WorkerSettings.functions`；`tests/workers/test_worker_registers_all_enqueued_tasks.py` 断言「入队的 ⊆ 已注册的」⇒ **新任务必须注册** |
| ARQ 入队 helper 存在但**语义不同** | `app/services/report/arq_queue.py::_enqueue` **失败抛 503** ⇒ AI 审计要求「失败降级写本地日志」⇒ **需要另一份不抛的 helper** |
| `system_settings` 已有 7 个键 | `app/services/system_setting_service.py::DEFAULT_SETTINGS`；前端参数页显示**全部**键 ⇒ 加 6 个 AI 键**前端自动可见** |
| compose 已有 postgres(18) / postgres-pgtest / redis / worker / openldap+seed | `docker-compose.yml` ⇒ mock AD = openldap ✅（spec 10.0(3) 的「mock AD」已有） |
| Playwright 已装且有 **8 个 spec** + `fixtures.ts::loggedInPage` + `webServer` 起 vite | `pcs-frontend/e2e/`（audit_log / cooling_water / deliverable_sign / energy_summary / record_actions / result_edit_conflict / stream_batch_submit + fixtures）⇒ **10.0(5)「E2E 框架」大部分已有** |
| E2E 跑在 **MSW mock** 上（不是真后端） | `src/main.tsx`：`if (import.meta.env.DEV)` ⇒ 挂 MSW worker ⇒ SPEC §3.2.2 的 18 个「全流程」场景**跑不了**（要真后端 + 真库）⇒ 需第二个通道 |
| vite 已把 `/api` 代理到 `localhost:8000` | `pcs-frontend/vite.config.ts` ⇒ 真后端 E2E 只要 MSW 关掉即可复用同一个 dev server |
| 后端也有 mock 登录 | `app/api/v1/mock_auth.py::POST /auth/mock-login`（非生产可用）⇒ 真后端 E2E 可用它拿 token |
| 已有架构测试目录 | `tests/architecture/` ⇒ 沿用**自定义扫描**做法，**不引入 import-linter**（spec 说「import-linter + 自定义架构测试」⇒ 仓里已有后者） |

---

## 文件结构

| 文件 | 责任 |
|---|---|
| `pcs-backend/app/core/ai_cidr.py` | **新建** · CIDR 解析 / 内网判定 / endpoint 校验 |
| `pcs-backend/app/core/ai_sanitizer.py` | **新建** · 递归脱敏 + 规范化哈希 |
| `pcs-backend/app/core/ai_errors.py` | **新建** · `AINotImplementedError` |
| `pcs-backend/app/core/outbound_ai_client.py` | **新建** · 唯一允许调 AI 端点的出口 |
| `pcs-backend/app/core/ai_audit_middleware.py` | **新建** · 纯 ASGI 审计中间件（body 重放 + request_id + 计时） |
| `pcs-backend/app/core/config.py` | 改 · `ai_endpoint` / `internal_cidrs` 等 env 配置 |
| `pcs-backend/app/core/errors.py` | 改 · 注册 `AINotImplementedError` handler（501） |
| `pcs-backend/app/api/v1/ai/__init__.py` + `routes.py` | **新建** · AI 路由骨架（501） |
| `pcs-backend/app/api/v1/health.py` | 改 · `/health/ai` |
| `pcs-backend/app/models/system.py` | 改 · `AiAuditLog` 加 9 列 |
| `pcs-backend/app/schemas/ai.py` | **新建** · AI 请求/响应 schema（具名） |
| `pcs-backend/app/services/ai/arq_queue.py` | **新建** · 审计入队（**失败降级，不抛**） |
| `pcs-backend/app/workers/ai_audit_tasks.py` | **新建** · 审计写库任务（幂等） |
| `pcs-backend/app/services/system_setting_service.py` | 改 · 6 个 AI 键 |
| `pcs-backend/alembic/versions/p10_001_ai_audit_request_fields.py` | **新建** · 加列 + partial 唯一索引 |
| `pcs-backend/scripts/seed_e2e_data.py` | **新建** · 种子数据（幂等） |
| `pcs-backend/tests/architecture/test_no_direct_ai_sdk.py` | **新建** · 架构守卫 |
| `pcs-frontend/src/main.tsx` | 改 · MSW 可关（`VITE_ENABLE_MOCK`） |
| `pcs-frontend/src/layouts/MainLayout.tsx` | 改 · 顶栏 AI 占位（禁用 + tooltip） |
| `pcs-frontend/playwright.config.ts` | 改 · 第二个 Playwright 项目（真后端） |

---

# 段一：10.0 前置与测试左移

## Task T1：compose 测试组（profile，不新建文件）

**Files:**
- Modify: `docker-compose.yml`（加 `profiles: ["test"]` 到需要的服务 + 一个 `seed` 一次性服务）
- Modify: `pcs-backend/README.md` 或 `CLAUDE.md`（写清「怎么起测试栈」）—— ⚠️ 只写一处，别在两处各写一份

**Interfaces:**
- Produces: `docker compose --profile test up -d` ⇒ 起出测试栈；`docker compose --profile test run --rm seed` ⇒ 灌种子数据

- [ ] **Step 1: 写失败的测试**

新建 `pcs-backend/tests/scripts/test_compose_test_profile.py`（**新建**）：

```python
def test_compose_declares_a_test_profile():
    """compose 里有 profile=test 的服务，且含 backend / worker / openldap。"""

def test_test_profile_does_not_add_a_second_postgres_service():
    """⚠️ **不新建 compose 文件**（偏离 D2）⇒ 测试栈复用既有 postgres-pgtest。"""
```

（测试用 `yaml.safe_load` 解析 `docker-compose.yml` ⇒ 断言 `services[*].profiles` 含 `"test"`。）

- [ ] **Step 2: 跑测试确认它**失败**

Run: `cd pcs-backend && uv run pytest tests/scripts/test_compose_test_profile.py -q`
Expected: FAIL —— 没有 `profiles: ["test"]`

- [ ] **Step 3: 改 compose**

给 `backend`（若 compose 里叫别的名字按实际）· `worker` · `openldap` 三个服务加 `profiles: ["test"]`；新增一个一次性服务：

```yaml
  seed:
    image: ghcr.io/astral-sh/uv:python3.12-bookworm-slim
    profiles: ["test"]
    working_dir: /app
    command: ["python", "scripts/seed_e2e_data.py"]
    environment:
      DATABASE_URL: postgresql+psycopg://${POSTGRES_USER:-pcs}:${POSTGRES_PASSWORD:-pcs_dev}@postgres-pgtest:5432/${POSTGRES_TEST_DB:-pcs_test}
      REDIS_URL: redis://redis:6379/0
    depends_on:
      postgres-pgtest: {condition: service_healthy}
```

⚠️ **不新建文件**（D2）⇒ 现有 `docker-compose.yml` 里**加**服务/加 profile，不复制一份。

- [ ] **Step 4: 跑测试确认**通过**

Run: `cd pcs-backend && uv run pytest tests/scripts/test_compose_test_profile.py -q`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add docker-compose.yml pcs-backend/tests/scripts/test_compose_test_profile.py
git commit -F <msgfile>   # 首行: chore(P10-A): compose 加 test profile（不新建 compose 文件）
```

---

## Task T2：种子数据脚本（幂等 · Review Focus #4）

**Files:**
- Create: `pcs-backend/scripts/seed_e2e_data.py`
- Create: `pcs-backend/tests/scripts/test_seed_e2e_data.py`

**Interfaces:**
- Consumes: `app.models.*`（`Workspace` / `Project` / `Stream` / `User` / `UserProject`）
- Produces: `seed_e2e_data.py --reset` ⇒ 可重复执行；退出码 0 = 成功

- [ ] **Step 1: 写失败的测试**

`pcs-backend/tests/scripts/test_seed_e2e_data.py`：

```python
async def test_seed_is_idempotent(db_session, ...):
    """⚠️ **跑两次不炸、不产生重复行**（Review Focus #4）——
    第二次跑后 project / stream / user_project 的行数与第一次相同。"""

async def test_seed_creates_the_expected_fixture_set(db_session, ...):
    """种子产出：1 个项目 + N 条物流 + 1 个用户 + 1 行 UserProject 授权。"""

async def test_seed_reset_removes_previous_rows(db_session, ...):
    """--reset ⇒ 先清掉上一轮的种子行（按固定标记筛，不碰业务数据）。"""
```

- [ ] **Step 2: 跑测试确认**失败**

Run: `cd pcs-backend && uv run pytest tests/scripts/test_seed_e2e_data.py -q`
Expected: FAIL —— 脚本不存在

- [ ] **Step 3: 实现脚本**

`pcs-backend/scripts/seed_e2e_data.py`：

- 用**固定 UUID**（不是随机）⇒ 幂等的基础
- 幂等手段：`session.merge()` 或「先查后插」；**不要**用 `add()` 无条件插
- `--reset` ⇒ 按固定 UUID 列表删旧行（**只删自己造的**，不碰业务数据）
- ⚠️ **必须造 `UserProject` 行** ⇒ 否则带项目守卫的端点全 404（这正是 P10-A 依赖的机制，见紧急批次 T0 的教训）
- 输出：一行摘要（项目 / 物流 / 用户 / 授权 各自条数）

- [ ] **Step 4: 跑测试确认**通过**

Run: `cd pcs-backend && uv run pytest tests/scripts/test_seed_e2e_data.py -q`
Expected: PASS（3 passed）

- [ ] **Step 5: 提交**

```bash
git add pcs-backend/scripts/seed_e2e_data.py pcs-backend/tests/scripts/test_seed_e2e_data.py
git commit -F <msgfile>   # 首行: feat(P10-A): E2E 种子数据脚本（幂等 + --reset）
```

---

## Task T3：真后端 E2E 通道（MSW 可关 + Playwright 第二个项目）

**Files:**
- Modify: `pcs-frontend/src/main.tsx`（MSW 开关）
- Modify: `pcs-frontend/playwright.config.ts`（第二个项目）
- Modify: `pcs-frontend/e2e/fixtures.ts`（真后端 fixture + SPA 导航 helper）
- Create: `pcs-frontend/e2e/real_backend_smoke.spec.ts`（一条冒烟，验证通道本身）

**Interfaces:**
- Produces:
  - `VITE_ENABLE_MOCK`（env，默认 `true`）⇒ `false` 时**不挂** MSW worker
  - `e2e/fixtures.ts` 导出 `realPage` fixture（真后端登录态）+ `gotoViaMenu(page, menuName)` helper

- [ ] **Step 1: 写失败的测试**

`pcs-frontend/e2e/real_backend_smoke.spec.ts`（**新建**）：

```ts
import { test, expect } from './fixtures';

// ⚠️ 这条 spec 只验证**通道本身**（真后端可达 + 登录成功 + 页面渲染），
// 业务场景在 P10-B（18 个场景）。
test('真后端通道：登录 ⇒ 仪表盘渲染 ⇒ 无控制台错误', async ({ realPage }) => {
  const errors: string[] = [];
  realPage.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  await realPage.goto('/login');
  await realPage.getByRole('button', { name: '登 录' }).click();
  await realPage.waitForURL('/', { timeout: 15000 });
  await expect(realPage.getByText('仪表盘')).toBeVisible();
  expect(errors).toEqual([]);
});
```

- [ ] **Step 2: 跑测试确认它**失败**

Run: `cd pcs-frontend && VITE_ENABLE_MOCK=false npx playwright test e2e/real_backend_smoke.spec.ts`
Expected: FAIL —— MSW 仍被挂上（请求被 mock 拦截）或 `realPage` fixture 不存在

- [ ] **Step 3: 实现 MSW 开关**

`pcs-frontend/src/main.tsx`：

```ts
  // ⚠️ `VITE_ENABLE_MOCK=false` ⇒ **不挂 MSW** ⇒ 请求打到真后端
  // （真后端 E2E 用；vite proxy 已把 /api 代理到 localhost:8000）。
  if (import.meta.env.DEV && import.meta.env.VITE_ENABLE_MOCK !== 'false') {
```

- [ ] **Step 4: 加 Playwright 第二个项目 + fixture**

`pcs-frontend/playwright.config.ts`：

```ts
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
    // ⚠️ **真后端**项目：不挂 MSW ⇒ 打真后端 ⇒ 需要后端 + 库 + 种子数据在跑。
    {
      name: 'real-backend',
      use: { ...devices['Desktop Chrome'] },
      grep: /@real-backend/,
    },
  ],
```

`pcs-frontend/e2e/fixtures.ts`：

```ts
export const test = base.extend<{ loggedInPage: Page; realPage: Page }>({ ... });

/**
 * **SPA 菜单导航** —— 不用 `page.goto`。
 *
 * ⚠️ 本仓 zustand auth store 是**内存态**（防 XSS，不落 localStorage）⇒
 * 整页刷新会清 session ⇒ `RequireAuth` 弹回 `/login` ⇒ 表格永远没有行。
 */
export async function gotoViaMenu(page: Page, menuName: string): Promise<void> {
  await page.getByRole('menuitem', { name: menuName }).click();
}
```

⚠️ `realPage` fixture 的登录：走**后端自己的** `POST /auth/mock-login`（非生产可用）⇒ 真后端 E2E 有真 token。

- [ ] **Step 5: 跑测试确认**通过**

Run: `cd pcs-frontend && VITE_ENABLE_MOCK=false npx playwright test e2e/real_backend_smoke.spec.ts`
Expected: PASS（需后端在 :8000 跑着 + 种子数据已灌）

- [ ] **Step 6: 提交**

```bash
git add pcs-frontend/src/main.tsx pcs-frontend/playwright.config.ts pcs-frontend/e2e/fixtures.ts pcs-frontend/e2e/real_backend_smoke.spec.ts
git commit -F <msgfile>   # 首行: feat(P10-A): 真后端 E2E 通道（MSW 可关 + Playwright real-backend 项目）
```

---

# 段二：10.1 AI 预留接口

## Task T4：AI 开关与配置（env + system_settings）

**Files:**
- Modify: `pcs-backend/app/core/config.py`
- Modify: `pcs-backend/app/services/system_setting_service.py`
- Test: `pcs-backend/tests/services/test_ai_settings.py`（**新建**）

**Interfaces:**
- Produces:
  - `Settings.ai_endpoint: str | None = None`（env `AI_ENDPOINT`）
  - `Settings.internal_cidrs: str = ""`（env `INTERNAL_CIDRS`，逗号分隔，**原始串** ⇒ 解析在 `ai_cidr.parse_cidrs`）
  - `Settings.ai_mask_person_name: bool = False`（env `AI_MASK_PERSON_NAME`）
  - `system_settings` 新增 6 键：`ai_enabled`(false) · `ai_model_version`(null) · `ai_endpoint`(null) · `ai_timeout`(30) · `ai_max_tokens`(4096) · `ai_temperature`(0.1)

> ⚠️ **配置来源的分工**（本 Task 拍板，写进代码注释）：
> - **env**（部署级）：`ai_endpoint` · `internal_cidrs` ⇒ CIDR 校验的输入（改它要重启）
> - **system_settings**（管理员可编辑、运行时）：6 个 AI 键 ⇒ 前端参数页**自动可见**（页面显示全部键）
> - **有效 endpoint** = `system_settings.ai_endpoint` 非空则用它，否则用 env 的

- [ ] **Step 1: 写失败的测试**

```python
async def test_ai_settings_defaults(db_session):
    """6 个 AI 键存在且默认值正确（ai_enabled=False / timeout=30 / max_tokens=4096 / temperature=0.1）。"""

async def test_ai_settings_keys_are_visible_in_the_admin_page(client):
    """参数页列出**全部**键 ⇒ AI 键自动可见（前端无需改）。"""
```

- [ ] **Step 2: 跑测试确认**失败**

Run: `cd pcs-backend && uv run pytest tests/services/test_ai_settings.py -q`
Expected: FAIL —— 键不存在

- [ ] **Step 3: 实现**

`config.py` 加 3 个字段；`system_setting_service.py::DEFAULT_SETTINGS` 加 6 项（照 SPEC §4.1.3 的默认值）。

- [ ] **Step 4: 跑测试确认**通过** + 跑前端参数页测试（默认值变了，页面测试可能红）**

Run: `cd pcs-backend && uv run pytest tests/services/test_ai_settings.py tests/api/v1/test_system_settings.py -q`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add pcs-backend/app/core/config.py pcs-backend/app/services/system_setting_service.py pcs-backend/tests/services/test_ai_settings.py
git commit -F <msgfile>   # 首行: feat(P10-A): AI 开关与配置（env + system_settings 6 键）
```

---

## Task T5：CIDR 校验模块

**Files:**
- Create: `pcs-backend/app/core/ai_cidr.py`
- Create: `pcs-backend/tests/core/test_ai_cidr.py`

**Interfaces:**
- Produces:
  - `def parse_cidrs(value: str) -> list[str]` —— 解析逗号分隔；**空值 ⇒ []**；**非法 CIDR ⇒ 抛 `RuntimeError`（带清晰信息）**
  - `def ip_in_cidrs(ip: str, cidrs: list[str]) -> bool`
  - `def resolve_ai_endpoint_ips(endpoint: str) -> list[str]`
  - `def validate_ai_endpoint(endpoint: str, cidrs: list[str]) -> None` —— 不在内网 ⇒ 抛 `RuntimeError`

- [ ] **Step 1: 写失败的测试**

```python
def test_parse_cidrs_handles_empty_and_spaces():
    """'' ⇒ []；' 10.0.0.0/8 , 192.168.0.0/16 ' ⇒ 两条（去空格）。"""

def test_parse_cidrs_rejects_invalid_cidr_with_clear_message():
    """'not-a-cidr' ⇒ RuntimeError，消息里含那个串（E2：启动时提前报清晰错误）。"""

def test_ip_in_cidrs_handles_ipv6_against_ipv4_list():
    """⚠️ **地址族不匹配不得抛** —— `IPv6Address in IPv4Network` 会 TypeError
    ⇒ 必须捕获并返回 False（否则一个 IPv6 endpoint 打 IPv4 CIDR 直接崩）。"""

def test_ip_in_cidrs_supports_ipv6():
    """'fd00::1' in ['fd00::/8'] ⇒ True。"""

def test_validate_ai_endpoint_rejects_public_ip():
    """8.8.8.8 + ['10.0.0.0/8'] ⇒ RuntimeError。"""

def test_validate_ai_endpoint_rejects_dns_resolving_outside():
    """域名解析到公网 ⇒ RuntimeError。"""
```

- [ ] **Step 2: 跑测试确认**失败**

Run: `cd pcs-backend && uv run pytest tests/core/test_ai_cidr.py -q`
Expected: FAIL —— 模块不存在

- [ ] **Step 3: 实现**（照 SPEC §3.2.1(5) 的代码，**并修两处陷阱**）

```python
def ip_in_cidrs(ip: str, cidrs: list[str]) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    for c in cidrs:
        try:
            network = ipaddress.ip_network(c, strict=False)
        except ValueError:
            continue
        if addr.version != network.version:
            # ⚠️ **地址族不同 ⇒ 不匹配**（`IPv6Address in IPv4Network` 会 TypeError）
            continue
        if addr in network:
            return True
    return False
```

⚠️ 第二处陷阱：`parse_cidrs` 里 `ipaddress.ip_network(c)` 抛的是 `ValueError` ⇒ 要**转成 RuntimeError** 并带上原文（E2 要求「清晰错误」）⇒ 启动时不会抛一个裸 ValueError 让运维看不懂。

- [ ] **Step 4: 跑测试确认**通过**

Run: `cd pcs-backend && uv run pytest tests/core/test_ai_cidr.py -q`
Expected: PASS（6 passed）

- [ ] **Step 5: 提交**

```bash
git add pcs-backend/app/core/ai_cidr.py pcs-backend/tests/core/test_ai_cidr.py
git commit -F <msgfile>   # 首行: feat(P10-A): AI 内网 CIDR 校验（IPv4/IPv6 + 地址族陷阱）
```

---

## Task T6：递归脱敏 + 规范化哈希

**Files:**
- Create: `pcs-backend/app/core/ai_sanitizer.py`
- Create: `pcs-backend/tests/core/test_ai_sanitizer.py`

**Interfaces:**
- Produces:
  - `def sanitize_for_ai(value: Any) -> Any` —— 递归 dict / list / tuple / str
  - `def hash_sanitized(body: bytes) -> str` —— `"sha256:<hex>"`
  - `def enable_person_name_mask(enabled: bool) -> None` —— 运行时开关（默认**关**）

- [ ] **Step 1: 写失败的测试**

```python
def test_sanitize_masks_email_and_phone_in_nested_payload():
    """嵌套 dict/list 里的邮箱与手机号都被替换（递归）。"""

def test_sanitize_leaves_numbers_and_booleans_untouched():
    """非字符串原样返回。"""

def test_person_name_mask_is_off_by_default():
    """默认**不**遮中文人名（开了会把几乎每个中文词都遮掉）。"""

def test_person_name_mask_can_be_enabled_at_runtime():
    """enable_person_name_mask(True) ⇒ 遮；再关掉 ⇒ 不遮（**全局状态要能复位**）。"""

def test_hash_sanitized_is_stable_for_equal_bodies():
    """同一 body 两次 ⇒ 同哈希（规范化：sort_keys + ensure_ascii=False）。"""

def test_hash_sanitized_differs_for_different_bodies():
    """不同 body ⇒ 不同哈希。"""

def test_hash_sanitized_falls_back_to_raw_bytes_on_invalid_json():
    """非 JSON ⇒ hash 原始 bytes（**不**记录内容）。"""
```

- [ ] **Step 2: 跑测试确认**失败**

Run: `cd pcs-backend && uv run pytest tests/core/test_ai_sanitizer.py -q`
Expected: FAIL —— 模块不存在

- [ ] **Step 3: 实现**（照 SPEC §3.2.1(3) 的代码 + 把 `ENABLE_PERSON_NAME_MASK` 改成运行时开关）**

- [ ] **Step 4: 跑测试确认**通过**

Run: `cd pcs-backend && uv run pytest tests/core/test_ai_sanitizer.py -q`
Expected: PASS（7 passed）

- [ ] **Step 5: 提交**

```bash
git add pcs-backend/app/core/ai_sanitizer.py pcs-backend/tests/core/test_ai_sanitizer.py
git commit -F <msgfile>   # 首行: feat(P10-A): AI 请求递归脱敏 + 规范化哈希（人名遮蔽默认关）
```

---

## Task T7：`ai_audit_log` 加列 + 迁移 `p10_001`

**Files:**
- Modify: `pcs-backend/app/models/system.py`（`AiAuditLog` 加 9 列）
- Create: `pcs-backend/alembic/versions/p10_001_ai_audit_request_fields.py`
- Create: `pcs-backend/tests/alembic/test_p10_001_ai_audit_fields.py`（**新建**）

**Interfaces:**
- Produces（`AiAuditLog` 新列，全部 nullable）：

| 列 | 类型 | 说明 |
|---|---|---|
| `request_id` | `String(64)` | **服务端** UUID；唯一索引（partial：`WHERE request_id IS NOT NULL`） |
| `client_request_id` | `String(128)` | 客户端 `X-Request-ID`；**不唯一** |
| `endpoint` | `String(200)` | 如 `/api/v1/ai/intent` |
| `status_code` | `Integer` | 含 501 |
| `duration_ms` | `Integer` | |
| `sanitized_request_hash` | `String(80)` | `"sha256:..."` |
| `response_summary` | `Text` | 如 `AI_NOT_IMPLEMENTED` |
| `model_version` | `String(50)` | |
| `timestamp` | `DateTime(timezone=True)` | 与 `endpoint` 组成组合索引 |

- [ ] **Step 1: 写失败的测试**

```python
def test_migration_adds_the_nine_columns():
    """迁移 upgrade 后 ai_audit_log 有这 9 列。"""

def test_request_id_unique_index_is_partial():
    """唯一索引是 partial（WHERE request_id IS NOT NULL）——
    ⚠️ **既有 SUP-006 行 request_id 为 NULL** ⇒ 非 partial 会因重复 NULL 失败。"""

def test_orm_matches_migration():
    """ORM 声明的列与迁移一致（漂移守卫）。"""
```

- [ ] **Step 2: 跑测试确认**失败**

Run: `cd pcs-backend && uv run pytest tests/alembic/test_p10_001_ai_audit_fields.py -q`
Expected: FAIL —— 迁移不存在

- [ ] **Step 3: 写迁移**

`alembic/versions/p10_001_ai_audit_request_fields.py`：

```python
revision = "p10_001"
down_revision = "p9_015"
```

`upgrade()`：9 个 `op.add_column`（全部 `nullable=True`）⇒ `op.create_index("ux_ai_audit_log_request_id", "ai_audit_log", ["request_id"], unique=True, if_not_exists=True, postgresql_where=sa.text("request_id IS NOT NULL"))` ⇒ `op.create_index("ix_ai_audit_log_endpoint_timestamp", "ai_audit_log", ["endpoint", "timestamp"], if_not_exists=True)`。

`downgrade()`：索引（`if_exists=True`）⇒ 列（`drop_column`）。

⚠️ **`timestamp` 列名**：PG 里 `timestamp` 是类型名但可作列名（non-reserved）⇒ SQLAlchemy 会自动加引号 ⇒ 迁移里写 `sa.Column("timestamp", sa.DateTime(timezone=True), nullable=True)` 即可；**ORM 侧属性名也叫 `timestamp`** ⇒ 注意别与 `datetime.timestamp()` 混淆。

- [ ] **Step 4: 跑测试确认**通过**

Run: `cd pcs-backend && uv run pytest tests/alembic/test_p10_001_ai_audit_fields.py -q`
Expected: PASS

- [ ] **Step 5: 跑迁移闸门（两库各一次 · 独立进程）**

```bash
# pcs
cd pcs-backend && uv run alembic upgrade head && uv run alembic current && uv run alembic check
# pcs_test（**独立进程** —— 同进程改 DATABASE_URL 不生效）
cd pcs-backend && python3 - <<'PY'
import os, re
from dotenv import dotenv_values
from alembic import command
from alembic.config import Config
url = dotenv_values('.env')['DATABASE_URL']
os.environ['DATABASE_URL'] = re.sub(r'/pcs(\?|$)', r'/pcs_test\1', url)
cfg = Config('alembic.ini')
command.upgrade(cfg, 'head')
command.current(cfg)
command.check(cfg)
PY
```

Expected: 两个库都 `p10_001 (head)`；`alembic check` exit 0（**退出码是 255 表示有漂移**，不是 1）

- [ ] **Step 6: 跑幂等闸门**

Run: `cd pcs-backend && uv run python scripts/check_migration_idempotency.py`
Expected: RC=0

- [ ] **Step 7: 提交**

```bash
git add pcs-backend/app/models/system.py pcs-backend/alembic/versions/p10_001_ai_audit_request_fields.py pcs-backend/tests/alembic/test_p10_001_ai_audit_fields.py
git commit -F <msgfile>   # 首行: feat(P10-A): ai_audit_log 加 P10 请求审计 9 列（partial 唯一索引）
```

---

## Task T8：`AINotImplementedError` + 全局 handler + `OutboundAIClient`

**Files:**
- Create: `pcs-backend/app/core/ai_errors.py`
- Create: `pcs-backend/app/core/outbound_ai_client.py`
- Modify: `pcs-backend/app/core/errors.py`（注册 handler）
- Create: `pcs-backend/tests/core/test_outbound_ai_client.py`

**Interfaces:**
- Produces:
  - `class AINotImplementedError(Exception)`（`app/core/ai_errors.py`）
  - `install_exception_handlers` 里注册它 ⇒ **501** + `{"code":"AI_NOT_IMPLEMENTED","message":"AI功能即将上线","request_id":...}`
  - `class OutboundAIClient`：`__init__(self, *, endpoint: str, timeout: int, cidrs: list[str])` · `async def call(self, payload: dict) -> dict` · `async def _audit(self, payload: dict) -> None`

- [ ] **Step 1: 写失败的测试**

```python
async def test_ai_not_implemented_error_becomes_501_with_request_id(client):
    """抛 AINotImplementedError ⇒ 501 + 信封含 code/message/request_id。"""

async def test_outbound_client_validates_endpoint_before_calling():
    """endpoint 不在内网 CIDR ⇒ RuntimeError（**且没发出任何请求**）。"""

async def test_outbound_client_sanitizes_payload_before_audit():
    """进 _audit 的 payload 已脱敏（邮箱被替换）。"""

async def test_outbound_client_raises_ai_not_implemented():
    """P10 阶段：脱敏 + 审计后抛 AINotImplementedError（不真调）。"""

async def test_outbound_client_audit_failure_does_not_propagate():
    """⚠️ 审计写库失败**不得抛**（降级）—— 否则 AI 调用因审计挂掉。"""
```

- [ ] **Step 2: 跑测试确认**失败**

Run: `cd pcs-backend && uv run pytest tests/core/test_outbound_ai_client.py -q`
Expected: FAIL —— 模块不存在

- [ ] **Step 3: 实现**

实现要点：
- `OutboundAIClient.call`：① `validate_ai_endpoint(self.endpoint, self.cidrs)`（**调用时二次校验**）② `sanitized = sanitize_for_ai(payload)` ③ `await self._audit(sanitized)`（**try/except 吞掉异常**）④ `raise AINotImplementedError()`
- 全局 handler：从 `request.state.request_id` 取（缺失则 `uuid4()`）

- [ ] **Step 4: 跑测试确认**通过**

Run: `cd pcs-backend && uv run pytest tests/core/test_outbound_ai_client.py tests/test_errors.py -q`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add pcs-backend/app/core/ai_errors.py pcs-backend/app/core/outbound_ai_client.py pcs-backend/app/core/errors.py pcs-backend/tests/core/test_outbound_ai_client.py
git commit -F <msgfile>   # 首行: feat(P10-A): AINotImplementedError + 全局 501 handler + OutboundAIClient
```

---

## Task T9：AI 路由骨架（501）

**Files:**
- Create: `pcs-backend/app/api/v1/ai/__init__.py`
- Create: `pcs-backend/app/api/v1/ai/routes.py`
- Create: `pcs-backend/app/schemas/ai.py`
- Modify: `pcs-backend/app/api/v1/__init__.py`（挂 `ai_router`）
- Create: `pcs-backend/tests/api/v1/test_ai_routes.py`

**Interfaces:**
- Produces:
  - `POST /api/v1/ai/intent` —— 请求 `AiIntentRequest{text: str, context: dict | None}` ⇒ **501**
  - `POST /api/v1/ai/knowledge/search` —— 请求 `AiKnowledgeSearchRequest{query: str, top_k: int = 5}` ⇒ **501**
  - 两个路由都带 `openapi_extra={"x-status": "reserved"}`（**不用** `deprecated`）

- [ ] **Step 1: 写失败的测试**

```python
async def test_ai_intent_returns_501(client, designer_headers):
    """501 + 信封 {code:'AI_NOT_IMPLEMENTED', message:'AI功能即将上线', request_id:...}。"""

async def test_ai_knowledge_search_returns_501(client, designer_headers):
    ...

async def test_ai_routes_require_auth(client):
    """无 bearer ⇒ 401（**不是** 501）—— 认证在 501 之前。"""

async def test_ai_routes_have_x_status_reserved_in_openapi():
    """契约里两个端点带 x-status=reserved 且**不是** deprecated。"""
```

- [ ] **Step 2: 跑测试确认**失败**

Run: `cd pcs-backend && uv run pytest tests/api/v1/test_ai_routes.py -q`
Expected: FAIL —— 路由不存在（404）

- [ ] **Step 3: 实现**

实现要点：
- 用 `current_actor`（**不是** spec 的 `current_user`，偏离 D7）
- 501 响应体：`{"code": "AI_NOT_IMPLEMENTED", "message": "AI功能即将上线", "request_id": <request.state.request_id 或 uuid4()>}`
- 响应头带 `X-Request-ID`（由中间件加，见 T10；路由自身不重复加）

- [ ] **Step 4: 跑测试确认**通过**

Run: `cd pcs-backend && uv run pytest tests/api/v1/test_ai_routes.py -q`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add pcs-backend/app/api/v1/ai pcs-backend/app/schemas/ai.py pcs-backend/app/api/v1/__init__.py pcs-backend/tests/api/v1/test_ai_routes.py
git commit -F <msgfile>   # 首行: feat(P10-A): AI 路由骨架（intent / knowledge-search，一律 501）
```

---

## Task T10：纯 ASGI 审计中间件（Review Focus #1 #2）

**Files:**
- Create: `pcs-backend/app/core/ai_audit_middleware.py`
- Modify: `pcs-backend/app/main.py`（注册中间件）
- Create: `pcs-backend/tests/api/v1/test_ai_audit_middleware.py`

**Interfaces:**
- Produces: `class AIAuditMiddleware`（纯 ASGI，非 `BaseHTTPMiddleware`）
  - 只作用于 `/api/v1/ai/` 前缀
  - 生成 `request_id`（**标准 UUID 串**）写 `scope["state"]["request_id"]` ⇒ 路由与 handler 都从这儿取
  - 读 `X-Request-ID` 头 ⇒ `client_request_id`（**不生成、不信任**）
  - `user_id`：**用 `decode_token` 验签**（与认证依赖同一套逻辑），失败 ⇒ `None`，**不抛**
  - body：缓存并**重放** ⇒ 下游 Pydantic 仍能收到
  - 响应头追加 `X-Request-ID`
  - 审计入队（ARQ）⇒ 失败降级（见 T11）

- [ ] **Step 1: 写失败的测试**

```python
async def test_ai_request_body_still_reaches_pydantic(client, designer_headers):
    """⚠️ **Review Focus #2** —— 中间件读 body 后，下游仍能校验 body
    ⇒ 缺字段 ⇒ **422**（不是 501）。"""

async def test_request_id_is_server_generated_uuid(client, designer_headers):
    """响应 X-Request-ID 是**标准 UUID 串**（36 位带连字符）。"""

async def test_client_request_id_is_stored_not_generated(client, designer_headers):
    """带 X-Request-ID ⇒ 审计里 client_request_id = 该值；不带 ⇒ None（**服务端不造**）。"""

async def test_audit_is_written_even_when_auth_fails(client):
    """⚠️ **Review Focus #1** —— 无效 token ⇒ 仍然落审计，user_id=None。"""

async def test_non_ai_paths_are_not_audited(client, designer_headers):
    """`/api/v1/projects/...` 不进 AI 审计（中间件按前缀过滤）。"""

async def test_audit_is_enqueued_not_written_inline(client, designer_headers):
    """审计**异步**（入队）⇒ 端点不因审计写库慢而变慢。"""
```

- [ ] **Step 2: 跑测试确认**失败**

Run: `cd pcs-backend && uv run pytest tests/api/v1/test_ai_audit_middleware.py -q`
Expected: FAIL —— 中间件不存在（请求不走审计）

- [ ] **Step 3: 实现**

实现要点（照 SPEC §3.2.1(4) 的纯 ASGI 示意，**修三处**）：
- ⚠️ **body 重放**：`receive_cached` 第一次调用时把 body 存下来；后续调用要**重放**已缓存的 chunk，否则下游收不到 body ⇒ 标准做法是缓存后**重放**再继续读原 receive
- ⚠️ **`user_id` 提取**：`scope["headers"]` 里找 `authorization` ⇒ `decode_token` ⇒ `sub` → `user_id = uuid5(NAMESPACE_DNS, sub)`（**与 `current_actor` 同一套派生逻辑** ⇒ 抽成共用函数，别写两套）
- ⚠️ **异常路径**：中间件**不捕获** `AINotImplementedError`（H4）⇒ 只在 `finally` 里记录响应状态

- [ ] **Step 4: 跑测试确认**通过**

Run: `cd pcs-backend && uv run pytest tests/api/v1/test_ai_audit_middleware.py -q`
Expected: PASS（6 passed）

- [ ] **Step 5: 提交**

```bash
git add pcs-backend/app/core/ai_audit_middleware.py pcs-backend/app/main.py pcs-backend/tests/api/v1/test_ai_audit_middleware.py
git commit -F <msgfile>   # 首行: feat(P10-A): AI 审计中间件（纯 ASGI · body 重放 · 认证失败也留痕）
```

---

## Task T11：ARQ 审计任务（幂等 · Review Focus #3）

**Files:**
- Create: `pcs-backend/app/services/ai/__init__.py` + `arq_queue.py`
- Create: `pcs-backend/app/workers/ai_audit_tasks.py`
- Modify: `pcs-backend/app/workers/worker.py`（注册函数）
- Create: `pcs-backend/tests/services/ai/test_ai_audit_task.py`
- Modify: `pcs-backend/tests/workers/test_worker_registers_all_enqueued_tasks.py`（若它是自动发现式则无需改）

**Interfaces:**
- Produces:
  - `app/services/ai/arq_queue.py::enqueue_ai_audit_log(**fields) -> bool` —— **返回 True/False，绝不抛**（降级写本地日志）
  - `app/workers/ai_audit_tasks.py::write_ai_audit_log(ctx, **fields) -> None` —— `INSERT ... ON CONFLICT (request_id) DO NOTHING`

- [ ] **Step 1: 写失败的测试**

```python
async def test_audit_write_is_idempotent(db_session, ...):
    """⚠️ **Review Focus #3** —— 同一 request_id 写两次 ⇒ 只有一行。"""

async def test_enqueue_failure_is_swallowed(monkeypatch):
    """Redis 挂 ⇒ enqueue 返回 False，**不抛**（降级）。"""

async def test_task_is_registered_in_worker_functions():
    """⚠️ ARQ 对**未注册**的函数名不报错 ⇒ job 静静躺着 ⇒ 棘轮会抓。"""

async def test_failed_audit_write_does_not_break_the_request(client, designer_headers):
    """审计写库炸 ⇒ 端点仍返回 501（业务不被审计拖死）。"""
```

- [ ] **Step 2: 跑测试确认**失败**

Run: `cd pcs-backend && uv run pytest tests/services/ai/ -q`
Expected: FAIL —— 模块不存在

- [ ] **Step 3: 实现**

实现要点：
- 入队 helper **照 `app/services/report/arq_queue.py` 的形状但语义相反**：那里失败抛 503；这里失败**返回 False** + `logger.warning`
- 写库：`sqlalchemy.dialects.postgresql.insert(...).on_conflict_do_nothing(index_elements=["request_id"])` ⇒ ⚠️ SQLite 上 `on_conflict_do_nothing` **不支持** ⇒ 单测跑 SQLite ⇒ ⇒ **改用「先查后插 + 唯一约束兜底」**（`INSERT ... ON CONFLICT` 在 PG 用、SQLite 走查询分支）⚠️ 实施时按方言分支写
- 注册进 `WorkerSettings.functions`

- [ ] **Step 4: 跑测试确认**通过**

Run: `cd pcs-backend && uv run pytest tests/services/ai/ tests/workers/ -q`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add pcs-backend/app/services/ai pcs-backend/app/workers/ai_audit_tasks.py pcs-backend/app/workers/worker.py pcs-backend/tests/services/ai
git commit -F <msgfile>   # 首行: feat(P10-A): AI 审计 ARQ 任务（幂等写库 + 失败降级）
```

---

## Task T12：`/health/ai`

**Files:**
- Modify: `pcs-backend/app/api/v1/health.py`
- Create: `pcs-backend/tests/api/v1/test_health_ai.py`

**Interfaces:**
- Produces: `GET /health/ai` ⇒ `{"status": "not_configured" | "ok" | "degraded", "ai_enabled": bool, "endpoint_configured": bool, "cidrs_configured": bool}`

- [ ] **Step 1: 写失败的测试**

```python
async def test_health_ai_reports_not_configured_by_default(client):
    """默认 ⇒ status='not_configured'，且 **始终 200**（不因 AI 未配置而报错）。"""

async def test_health_ai_reports_endpoint_not_in_cidrs(client, monkeypatch):
    """endpoint 配了但不在 CIDR 内 ⇒ 'degraded'（**不是** 500）。"""
```

- [ ] **Step 2: 跑测试确认**失败**

Run: `cd pcs-backend && uv run pytest tests/api/v1/test_health_ai.py -q`
Expected: FAIL —— 端点不存在（404）

- [ ] **Step 3: 实现**（**不探测外部 DNS** ⇒ 只做本地判定，避免健康检查拖慢 / 被墙）

- [ ] **Step 4: 跑测试确认**通过**

Run: `cd pcs-backend && uv run pytest tests/api/v1/test_health_ai.py -q`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add pcs-backend/app/api/v1/health.py pcs-backend/tests/api/v1/test_health_ai.py
git commit -F <msgfile>   # 首行: feat(P10-A): /health/ai 端点（未配置 ⇒ not_configured）
```

---

## Task T13：前端顶栏 AI 占位

**Files:**
- Modify: `pcs-frontend/src/layouts/MainLayout.tsx`
- Create: `pcs-frontend/tests/layouts/MainLayout.test.tsx`（**新建或改**）

**Interfaces:**
- Produces: 顶栏一个**禁用**的 `[AI]` 按钮 + tooltip「AI 助手（P10 预留，暂未开放）」

- [ ] **Step 1: 写失败的测试**

```tsx
it('顶栏有 AI 按钮，但**禁用**并说明「预留」', async () => {
  // 断言按钮存在 + disabled + tooltip 文案
});
```

- [ ] **Step 2: 跑测试确认**失败**

Run: `cd pcs-frontend && npx vitest run tests/layouts/MainLayout.test.tsx`
Expected: FAIL —— 顶栏没有 AI 按钮

- [ ] **Step 3: 实现**（照 UI-SPEC §顶栏：AI → 「打开 AI 助手抽屉（P10 预留，先禁用并提示）」⇒ **只做禁用按钮，不做抽屉**）

- [ ] **Step 4: 跑测试确认**通过**

Run: `cd pcs-frontend && npx vitest run tests/layouts/MainLayout.test.tsx`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add pcs-frontend/src/layouts/MainLayout.tsx pcs-frontend/tests/layouts/MainLayout.test.tsx
git commit -F <msgfile>   # 首行: feat(P10-A): 前端顶栏 AI 占位（禁用 + 预留提示）
```

---

## Task T14：架构守卫（禁直接 import AI SDK）

**Files:**
- Create: `pcs-backend/tests/architecture/test_no_direct_ai_sdk.py`

**Interfaces:**
- Produces: 架构测试（沿用仓里 `tests/architecture/` 的自定义扫描做法，**不引入 import-linter**）

- [ ] **Step 1: 写测试（本身就是守卫）**

```python
def test_no_module_outside_outbound_client_imports_ai_sdks():
    """openai / ollama / vllm / langchain **只**允许出现在
    `app/core/outbound_ai_client.py`（若本批还没装这些包，则全仓零命中也通过）。"""

def test_only_outbound_client_calls_httpx_with_an_ai_endpoint():
    """⚠️ **httpx 允许被多处用**（不是禁 httpx）⇒ 守卫的是「httpx 调 **AI 端点**」
    ⇒ 只允许 `app/core/outbound_ai_client.py`。
    ⇒ 实现：扫 `app/` 下 `.call(` / `post(` 的 URL 字面量，含 ai 端点特征（settings.ai_endpoint / /api/v1/ai）⇒ 非白名单文件即红。"""
```

- [ ] **Step 2: 实现扫描逻辑**（测试即守卫 ⇒ 扫描与断言同一步写）

- [ ] **Step 4: 跑测试确认**通过**

Run: `cd pcs-backend && uv run pytest tests/architecture/test_no_direct_ai_sdk.py -q`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add pcs-backend/tests/architecture/test_no_direct_ai_sdk.py
git commit -F <msgfile>   # 首行: test(P10-A): 架构守卫 —— AI SDK 只能从 OutboundAIClient 出
```

---

## Task T15：契约 / SPEC 偏离回写 / 账簿 / QA 收口

**Files:**
- Modify: `pcs-backend/docs/openapi.json` + `docs/openapi-baseline.json`
- Modify: `pcs-frontend/openapi.snapshot.json` + `src/types/api.d.ts`
- Modify: `spec/PCS-SPEC-P10 V1.3.1 P10 AI预留与测试部署开发规格说明书.md`（**偏离登记 D1~D9 回写**）
- Modify: `TODOS.md` · `.wolf/buglog.json` · `.wolf/cerebrum.md` · `.wolf/STATUS.md`

- [ ] **Step 1: 重新生成契约 + 滚 baseline**

Run: `cd pcs-backend && uv run python scripts/export_openapi.py && cp docs/openapi.json docs/openapi-baseline.json && cd ../pcs-frontend && npm run api:gen`
Expected: 契约里出现 `/api/v1/ai/intent` · `/api/v1/ai/knowledge/search` · `/health/ai` + 具名 schema

- [ ] **Step 2: 跑契约闸门**

Run: `cd pcs-backend && uv run python scripts/check_openapi_payload_coverage.py && bash scripts/gate_08_openapi_contract.sh --check-baseline`
Expected: RC=0；裸载荷 **不涨**（基线 71）

- [ ] **Step 3: 后端全量 + PG 车道**

Run: `cd pcs-backend && uv run pytest -q && bash scripts/pytest_pg.sh`
Expected: 后端 0 failed（基线 5481 ⇒ 净增）；PG 车道 exit 0 且 `N passed`

- [ ] **Step 4: 前端全量 + E2E（mock 通道）**

Run: `cd pcs-frontend && npm run typecheck && npm run lint && npm run test && npx playwright test --project=chromium`
Expected: 全绿

- [ ] **Step 5: 浏览器回归（gstack）**

- 顶栏 AI 按钮**存在且禁用**
- AI 端点可直连：`curl -i -X POST http://localhost:8000/api/v1/ai/intent -H 'Authorization: Bearer <token>' -d '{"text":"x"}'` ⇒ **501** + `AI_NOT_IMPLEMENTED`
- 控制台 0 error；网络 0×404
- 报告落 `.gstack/qa-reports/qa-report-pcs-frontend-2026-11-04-p10a.md`

- [ ] **Step 6: 回写 SPEC 偏离登记 D1~D9**

在 `spec/PCS-SPEC-P10 V1.3.1 ….md` 里新增一节「**与仓库现状的偏离登记（2026-11-04）**」⇒ 逐条写：SPEC 原文 / 仓里实际 / 裁决 / 影响面。**D1~D9 一条都不能少**（总纲里有完整表格）。

- [ ] **Step 7: 更新账簿**

- `TODOS.md`：登记 P10-OPEN-002（pgvector 扩展延后）· P10-OPEN-010（CIDR 清单待 IT）· 「P10-B 启动前需量种子数据规模」
- `.wolf/buglog.json`：本批若无缺陷则不记
- `.wolf/cerebrum.md` Do-Not-Repeat 新增：
  - 「**审计/日志类需求先查既有表** ⇒ 本仓 `ai_audit_log` 已存在（SUP-006）⇒ spec 说『建表』时先核字段」
  - 「**纯 ASGI 中间件读 body ⇒ 必须重放** ⇒ 否则下游 Pydantic 收不到 ⇒ 症状是 422 不是 501」
  - 「**ARQ 未注册的函数名不报错** ⇒ job 静静躺着 ⇒ 入队 ⊆ 已注册 要有棘轮」
- `.wolf/STATUS.md`：第 28 轮

- [ ] **Step 8: 提交**

```bash
git add -A
git commit -F <msgfile>   # 首行: docs(P10-A): 契约滚动 + SPEC 偏离登记 D1~D9 + 账簿同步
```

---

## 验收

| 门 | 判据 |
|---|---|
| AI 路由 | `/ai/intent` · `/ai/knowledge/search` ⇒ **501** + `AI_NOT_IMPLEMENTED` + `request_id` |
| 认证 | 无 token ⇒ **401**（不是 501） |
| OpenAPI | 两个端点带 `x-status: reserved`、**不是** `deprecated` |
| 中间件 | body 重放 ⇒ 缺字段报 **422**；响应头带 `X-Request-ID`（标准 UUID） |
| 审计 | 认证失败**也**落审计（`user_id=None`）；非 AI 路径**不**落 |
| 审计幂等 | 同 `request_id` 重试 ⇒ 只有一行 |
| 审计降级 | Redis 挂 ⇒ 端点仍 501（不抛） |
| 脱敏 | 嵌套结构里的邮箱/手机号被替换；人名遮蔽**默认关** |
| CIDR | IPv4/IPv6 都支持；地址族不匹配**不崩**；非法 CIDR 启动即报清晰错误 |
| 迁移 | `p10_001` 在 **pcs / pcs_test** 两库都到 head；`alembic check` exit 0；幂等闸门 RC=0 |
| 健康端点 | `/health/ai` 恒 **200**；未配置 ⇒ `not_configured` |
| 架构守卫 | AI SDK 只能从 `OutboundAIClient` 出；httpx 调 AI 端点只允许它 |
| 种子 | 跑两次不炸、不重复；`--reset` 只删自己的行 |
| E2E | MSW 可关；真后端通道冒烟通过；**导航走 SPA 菜单** |
| 契约 | G-08 4/4；裸载荷 **不涨**；前后端类型同步 |
| 后端全量 | 0 failed（基线 5481 ⇒ 净增）；PG 车道 exit 0 |
| 前端全量 | typecheck + lint + vitest 全绿；Playwright mock 通道全绿 |
| SPEC | **偏离登记 D1~D9 全部回写** |
| 浏览器 | 顶栏 AI 禁用按钮；控制台 0 error；0×404 |

---

## 尚未解决的问题（开工前需裁决或登记）

| # | 问题 | 现状 | 本批处置 |
|---|---|---|---|
| 1 | **P10-OPEN-010 内网 CIDR 清单** | 待 IT 提供 ⇒ 本批只做机制（可配置 + 非法即启动报错）⇒ 用回环地址测试 | **不阻塞** ⇒ 登记 TODO |
| 2 | **P10-OPEN-002 pgvector 维度** | 未定 ⇒ 本批**不建扩展**（偏离 D3）⇒ `document_chunks.embedding_vector` 仍是 JSONB | 登记 TODO（P10-A 收口） |
| 3 | **PgBouncer 引入** | SPEC 部署图有、仓里没有 ⇒ 引入要改所有服务的 `DATABASE_URL` + 会话级特性约束 | **本批不做** ⇒ P10-D 开工前裁决（总纲 Q1） |
| 4 | **`ai_audit_log` 的 `timestamp` 列名** | 与 PG 类型名同名（non-reserved，可作列名）⇒ 与仓里 `AuditLog.occurred_at` 命名**不一致** | 照 SPEC 用 `timestamp` ⇒ 若将来统一命名，登记一条技术债 |
| 5 | **`document_chunks` 字段与 SPEC 不同** | 仓里已有 7 个字段（含 `embedding_vector JSONB`），SPEC 描述的是另 4 个字段 | 本批**不动**（偏离 D6）⇒ P10-OPEN-002 一并处理 |
| 6 | **AI 端点的权限模型** | SPEC 只说 `Depends(current_user)`，没说什么角色能调 | 本批：**任何已认证用户**都能调（但一律 501）⇒ 将来真开时再定 |
| 7 | **18 个 E2E 场景的种子规模** | 未知 | P10-B 开工前量一次（总纲开放问题 6） |
