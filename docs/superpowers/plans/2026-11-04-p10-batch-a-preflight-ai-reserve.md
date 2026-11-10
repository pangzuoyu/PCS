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

1. **AI 路由的审计必须在「认证失败」时也留下记录**（`user_id=None`）—— 否则用无效 token 探测 AI 端点**不留痕** ⇒ 审计表对探测行为完全失明。（**T11** 中间件）
2. **中间件读完 body 后下游 Pydantic 仍要能收到 body** —— 纯 ASGI 中间件若吞了 body，AI 路由会报 422 而不是 501 ⇒ **症状与「参数错」无法区分**。（**T11** 中间件）
3. **AI 审计写库必须幂等**（同一 `request_id` 重试不产生第二行）—— ARQ 的 `max_tries` 重试若不幂等 ⇒ 一次请求留下 N 条审计 ⇒ 审计表被灌水。（**T10** 审计任务）
4. **种子数据脚本必须可重复执行**（幂等）—— E2E 每次跑之前都要重置 ⇒ 不幂等 ⇒ 第二次跑要么撞唯一约束、要么留下脏数据让断言飘。（**T2** 建 / **P10-B** 用）
5. **E2E 的页面导航必须走 SPA 菜单点击** —— 本仓 zustand auth store 是**内存态** ⇒ `page.goto` / `reload` 会清 session ⇒ 弹回 `/login` ⇒ 表格永远没有行。（**T3** 建 helper / **P10-B** 的 18 场景用）

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
| `pcs-backend/app/models/system.py` | 改 · `AiAuditLog` 加 **8** 列（时间列复用 `occurred_at`） |
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
- Modify: `docker-compose.yml`（**只加 `seed` 一个服务** + 给 `postgres-pgtest` 的 profile 加 `"test"`）
- Modify: `pcs-backend/README.md`（写清「怎么起测试栈」—— ⚠️ **只写一处**）
- Create: `pcs-backend/tests/scripts/test_compose_test_profile.py`

> ⚠️⚠️ **设计修订（审查 B1/B2/B3）**：
> - **不给 `worker` / `openldap` 加 profile** —— 它们是**日常开发必用**的服务，加了 profile 之后 `docker compose up` 就不再启动它们 ⇒ 破坏现有开发流程。
> - **只给 `seed` 加 `profiles: ["test"]`** —— 它是一次性任务，本来就不该默认启动。
> - `postgres-pgtest` 已有 `profiles: ["pg"]` ⇒ **加一个 `"test"`**（`profiles: ["pg", "test"]`）⇒ 否则 `--profile test` 不会启动它 ⇒ `seed` 的 `depends_on` 报「service is not enabled」。
> - ⚠️ **compose 里没有 `backend` 服务**（只有 postgres / postgres-pgtest / redis / worker / openldap / openldap-seed）⇒ `seed` **不能**复用「backend 的镜像」⇒ 照 **`worker` 服务的写法**（uv 官方镜像 + 源码只读挂载 + `uv run --frozen`）。
> - ⚠️ `postgres-pgtest` 的库名是 **`pcs_pgtest`**（硬编码，不是 `pcs_test`）⇒ seed 的 `DATABASE_URL` 必须连它。

**Interfaces:**
- Produces:
  - `docker compose --profile test up -d` ⇒ 起出测试栈（含 `postgres-pgtest`）
  - `docker compose --profile test run --rm seed` ⇒ 灌种子数据（连 `pcs_pgtest`）
  - `seed` 服务的 `command` = `uv run --frozen python scripts/seed_e2e_data.py`

- [ ] **Step 2: 写失败的测试**

新建 `pcs-backend/tests/scripts/test_compose_test_profile.py`（**新建**）：

```python
def test_seed_service_is_in_the_test_profile():
    """`seed` 服务在 `profiles: ["test"]` 下 ⇒ 默认 `docker compose up` **不**起它。"""

def test_seed_service_mounts_the_backend_source():
    """⚠️ **seed 必须挂源码卷**（`./pcs-backend:/app`）——
    否则容器里没有 `scripts/seed_e2e_data.py` ⇒ 立刻 FileNotFoundError。"""

def test_seed_uses_the_frozen_uv_entrypoint():
    """⚠️ 与 `worker` 同款：`uv run --frozen`（不是裸 `python`）
    ⇒ 依赖由 uv 装好，且版本与本地一致。"""

def test_seed_depends_only_on_services_reachable_with_the_test_profile():
    """⚠️ **depends_on 的每个服务都要在 `--profile test` 下可达**
    ⇒ `postgres-pgtest` 的 profiles 必须含 "test"（否则 seed 起不来）。"""

def test_seed_points_at_the_pgtest_database():
    """⚠️ seed 连的是 `postgres-pgtest` 的库 **`pcs_pgtest`**（不是 `pcs_test`）。"""

def test_daily_dev_services_are_not_moved_into_a_profile():
    """⚠️ **worker / openldap / postgres / redis 必须留在默认启动集合**
    ⇒ 加了 profile 会让 `docker compose up` 不再起它们 ⇒ 破坏日常开发。"""
```

（测试用 `yaml.safe_load` 解析 `docker-compose.yml`。）

- [ ] **Step 2: 跑测试确认**失败**

Run: `cd pcs-backend && uv run pytest tests/scripts/test_compose_test_profile.py -q`
Expected: FAIL —— 没有 `seed` 服务

- [ ] **Step 3: 改 compose**

① `postgres-pgtest` 的 profile：

```yaml
    # ⚠️ **"test" 也在列表里** —— `seed` 依赖它，而 compose 的
    #    `depends_on` **不会**隐式启动不在启用 profile 内的服务
    #    ⇒ 只有 postgres-pgtest 时，`--profile test` 起不出 seed。
    profiles: ["pg", "test"]
```

② 新增 `seed` 服务（**照 `worker` 的形状**）：

```yaml
  seed:
    # 一次性任务：灌 E2E 种子数据。与 worker 同款（uv 官方镜像 + 源码挂载 +
    # uv run --frozen）—— ⚠️ **不要**用裸 python（镜像里没有依赖）。
    image: ghcr.io/astral-sh/uv:python3.12-bookworm-slim
    profiles: ["test"]
    working_dir: /app
    command: ["uv", "run", "--frozen", "python", "scripts/seed_e2e_data.py"]
    environment:
      UV_PROJECT_ENVIRONMENT: /opt/venv
      UV_CACHE_DIR: /opt/uvcache
      PYTHONDONTWRITEBYTECODE: "1"
      # ⚠️ 连 **pcs_pgtest**（postgres-pgtest 的库名，硬编码）——
      #    连 `pcs_test` 会报 database does not exist。
      DATABASE_URL: postgresql+psycopg://${POSTGRES_USER:-pcs}:${POSTGRES_PASSWORD:-pcs_dev}@postgres-pgtest:5432/pcs_pgtest
    volumes:
      - ./pcs-backend:/app:ro
    depends_on:
      postgres-pgtest: {condition: service_healthy}
```

⚠️ **不写 `REDIS_URL`** —— 种子只写 DB，不需要 Redis（少一个配置面）。

- [ ] **Step 4: 跑测试确认**通过**

Run: `cd pcs-backend && uv run pytest tests/scripts/test_compose_test_profile.py -q`
Expected: PASS（6 passed）

- [ ] **Step 5: 实测 compose 配置可解析 + 服务可达**

```bash
docker compose --profile test config >/dev/null && echo "compose 配置 OK"
docker compose --profile test up -d postgres-pgtest && docker compose --profile test ps
```

Expected: `postgres-pgtest` 在跑（`--profile test` 就能起它，不需再带 `--profile pg`）

- [ ] **Step 6: 写「怎么起测试栈」到 README（**只写一处**）**

`pcs-backend/README.md` 里加一小节：

```
### 起 E2E 测试栈（真后端）

    docker compose --profile test up -d
    docker compose --profile test run --rm seed
    # 后端：cd pcs-backend && uv run uvicorn app.main:app --port 8000
    # 真后端 E2E：cd pcs-frontend && VITE_ENABLE_MOCK=false npx playwright test --project=real-backend
```

⚠️ **不要**把同一段命令再抄进 `CLAUDE.md`（两处各写一份 ⇒ 改一处漏一处）。

- [ ] **Step 8: 提交**

```bash
git add docker-compose.yml pcs-backend/README.md pcs-backend/tests/scripts/test_compose_test_profile.py
git commit -F <msgfile>   # 首行: chore(P10-A): compose 加 seed 一次性服务（test profile，不新建文件）
```

---

## Task T2：种子数据脚本（幂等 · Review Focus #4）

**Files:**
- Create: `pcs-backend/scripts/seed_e2e_data.py`
- Create: `pcs-backend/tests/scripts/test_seed_e2e_data.py`

**Interfaces:**
- Consumes: `app.models.*`（`Workspace` / `Project` / `Stream` / `User` / `UserProject`）
- Produces:
  - `scripts/seed_e2e_data.py` 暴露 **`async def seed(db: AsyncSession, *, reset: bool = False) -> dict[str, int]`**
    ⇒ ⚠️ **必须有这个可调用入口** —— 只有 `if __name__ == "__main__"` 的话，
    单测**没法把 `db_session` 传进去**（审查 S1）⇒ 测试用
    `from scripts.seed_e2e_data import seed`。
  - 返回值 = `{"projects": n, "streams": n, "users": n, "user_projects": n}`（各造了多少行）
  - `UserProject(user_id=..., project_id=..., role_in_project="DESIGNER")`
    ⇒ ⚠️ `role_in_project` 的合法值是 6 个项目内角色
    （`DESIGNER` / `CHECKER` / `APPROVER` / `REVIEWER` / `VIEWER` / `PROJECT_LEAD`）
    ⇒ 种子用 **`DESIGNER`**（审查 S3）
  - ⚠️ **`Workspace` 也要建**（审查 C2）：`Project.workspace_id` 是 **`nullable=False`**
    ⇒ 没有工作区就建不出项目 ⇒ 种子必须造
    `Workspace(workspace_id=<固定 UUID>, workspace_type="FORMAL", name="E2E Workspace", status="ACTIVE")`
    ⇒ ⚠️ `Workspace` 的 `workspace_type` / `name` / `status` 都是必填

- [ ] **Step 2: 跑测试确认**失败**

Run: `cd pcs-backend && uv run pytest tests/scripts/test_seed_e2e_data.py -q`
Expected: FAIL —— 脚本不存在

- [ ] **Step 3: 实现脚本**

`pcs-backend/scripts/seed_e2e_data.py`：

- ⚠️ **`--reset` 的删除顺序必须遵守外键约束**（审查 S2 + C2）：
  `UserProject` → `Stream` → **`Project` → `Workspace`** → `User`
  ⇒ ⚠️ **`Workspace` 必须在 `Project` 之后删**（`Project.workspace_id` FK → workspaces
  ⇒ 项目还在时删工作区会撞 FK）⇒ 反了就撞 FK。**只删自己造的**（按固定 UUID 列表筛），
  不碰业务数据。

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

- [ ] **Step 2: 写失败的测试**

`pcs-frontend/e2e/real_backend_smoke.spec.ts`（**新建**）：

```ts
import { test, expect } from './fixtures';

// ⚠️ 这条 spec 只验证**通道本身**（真后端可达 + 登录成功 + 页面渲染），
// 业务场景在 P10-B（18 个场景）。
// ⚠️ **标题必须带 `@real-backend`** —— Playwright 的 `grep` 匹配的是
//    **测试标题**（不是文件路径）⇒ 不带 tag ⇒ `--project=real-backend`
//    收集到 **0 个测试** ⇒ 看起来「全绿」实则什么都没跑（审查 B4）。
test('@real-backend 真后端通道：登录 ⇒ 仪表盘渲染 ⇒ 无控制台错误', async ({ realPage }) => {
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
    // ⚠️ `grep` 匹配**测试标题** ⇒ 标题里必须有 `@real-backend`
    //    （或用 `test('…', { tag: '@real-backend' })`）⇒ 否则收集到 0 个测试。
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

⚠️ **`realPage` 的登录机制 = 走 UI**（不是调 API 塞 token）：
`goto('/login')` → 点「登 录」⇒ 前端 LoginPage 调 `POST /auth/mock-login`
⇒ MSW 关掉后这个请求**打到真后端**（后端的 mock 登录在非生产环境可用）⇒
拿到**真 token** ⇒ 写进 zustand 内存态 store。

⚠️ **不用填凭据**（审查 C3 · 已核实）：
- 后端 `MockLoginRequest` **只有 `username` 一个字段**（`password` 根本不校验），
  且 `MOCK_USERS` 里预置了 `alice` / `bob` / `carol` / `dan`；
- 前端 `LoginPage` 的用户名**默认值就是 `alice`** ⇒ 表单是**预填**的。
⇒ 所以「`goto('/login')` → 点登录」即可通过。⚠️ 但若将来 LoginPage 清空默认值 ⇒
测试会失败在「未知 mock 用户」⇒ 届时在测试里显式 `fill('alice')`。

⚠️ **不要**试图用 `page.evaluate` 把 token 塞进 store —— zustand store **没有**
暴露到 `window`（审查 S5）⇒ 塞不进去 ⇒ 只能走 UI 登录。

- [ ] **Step 5: 跑测试确认**通过**

Run: `cd pcs-frontend && VITE_ENABLE_MOCK=false npx playwright test --project=real-backend`
Expected: PASS（**且报告里显示跑了 1 个测试** —— ⚠️ 若显示「0 passed」说明 grep 没匹配上 ⇒ 标题漏了 tag）
⚠️ 需后端在 :8000 跑着 + 种子数据已灌（见 T1 的起栈命令）

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
  - ⚠️ **env 侧不设 `AI_ENABLED`** —— 见下面的裁决
  - `system_settings` 新增 6 键：`ai_enabled`(false) · `ai_model_version`(null) · `ai_endpoint`(null) · `ai_timeout`(30) · `ai_max_tokens`(4096) · `ai_temperature`(0.1)

> ⚠️ **配置来源的分工**（本 Task 拍板，写进代码注释）：
> - **env**（部署级）：`ai_endpoint` · `internal_cidrs` · `ai_mask_person_name` ⇒ CIDR 校验的输入（改它要重启）
> - **system_settings**（管理员可编辑、运行时）：6 个 AI 键 ⇒ 前端参数页**自动可见**（页面显示全部键）
> - **有效 endpoint** = `system_settings.ai_endpoint` 非空则用它，否则用 env 的
>
> ⚠️⚠️ **`ai_enabled` 的单一真相源 = `system_settings`**（审查 I7）。
> SPEC 的 env 清单里有 `AI_ENABLED`，但若 env 与 system_settings 各有一个开关 ⇒
> 就会出现「两个开关、AND 语义、admin 在页面上翻了却没生效」⇒ **本批 env 侧不设
> AI 开关**（偏离登记 **D13**）⇒ 有效值 = `system_settings.ai_enabled`。
> ⇒ **启动时校验**（T5 Step 4）读的就是这个值。

- [ ] **Step 2: 写失败的测试**

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

- [ ] **Step 2: 写失败的测试**

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

def test_validate_ai_endpoint_rejects_dns_resolving_outside(monkeypatch):
    """域名解析到公网 ⇒ RuntimeError。
    ⚠️ **必须 mock DNS**（`monkeypatch.setattr(socket, "getaddrinfo", fake)`）
    —— 真解析依赖网络 ⇒ 测试环境可能无网/不稳定 ⇒ **flaky 测试**（审查 S7）。"""
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

- [ ] **Step 5: 接到启动时校验（SPEC §3.2.1(5) · 审查 I6）**

⚠️ 光有 `validate_ai_endpoint` **不算**落实「启动时校验」⇒ 必须真的在启动路径上调用。

`pcs-backend/app/main.py` 的 `lifespan` 里 —— ⚠️ **必须放在现有的
`async with factory() as session:` 块内**（`session` 只在那个块里有作用域；
块外引用它 ⇒ `NameError`）：

```python
    factory = get_async_session_factory()
    async with factory() as session:
        await CoefficientService.seed_default_tables(session)
        await seed_system_setting_defaults(session)
        # ↓↓↓ AI 启动校验放这里（与上面同一段、同一个 session）↓↓↓
```

⚠️ `get_setting_value` 的签名是 **`(db, key, *, default=None)`** ⇒ **有** `default`
参数 ⇒ 下面那句成立（审查 C1 已核实）。

```python
    # ⚠️ **启动时校验 AI endpoint**（SPEC §3.2.1(5)）：`ai_enabled` 为真时
    #    endpoint 必须存在、且必须解析到内网 CIDR ⇒ 否则**启动即失败**
    #    （而不是等到第一次调用才发现打到了公网）。
    #    ⚠️ 有效开关 = `system_settings.ai_enabled`（单一真相源 · 偏离 D13）。
    #    ⚠️ 读不到 DB 时**降级为跳过 + 记 warning** ⇒ 不因 AI 配置挡住整个服务启动。
    from app.core.ai_cidr import parse_cidrs, validate_ai_endpoint
    from app.services.system_setting_service import get_setting_value

    try:
        enabled = bool(await get_setting_value(session, "ai_enabled", default=False))
    except Exception as exc:  # noqa: BLE001 — 读不到库不该挡住启动
        logger.warning("读取 ai_enabled 失败，跳过 AI 启动校验：%s", exc)
        enabled = False
    if enabled:
        endpoint = (await get_setting_value(session, "ai_endpoint", default=None)) \
            or settings.ai_endpoint
        if not endpoint:
            raise RuntimeError("ai_enabled=true 但 AI endpoint 为空")
        validate_ai_endpoint(endpoint, parse_cidrs(settings.internal_cidrs))
```

⚠️ 这段**依赖 T4 的 `ai_enabled` 键** ⇒ T4 必须先落地（T4 在 T5 之前 ✅）。

- [ ] **Step 6: 提交**

```bash
git add pcs-backend/app/core/ai_cidr.py pcs-backend/app/main.py pcs-backend/tests/core/test_ai_cidr.py
git commit -F <msgfile>   # 首行: feat(P10-A): AI 内网 CIDR 校验 + 启动时校验接线
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

- [ ] **Step 2: 写失败的测试**

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

- [ ] **Step 5: 接到 env 开关（审查 I5）**

⚠️ **不接线 ⇒ `AI_MASK_PERSON_NAME=true` 不生效**（T4 加了 env 字段、T6 加了运行时开关，
但中间没人把它们连起来 ⇒ 这正是「看起来做了、其实没做」的典型）。

`pcs-backend/app/main.py` 的 `lifespan` 里（与 T5 的启动校验同一处）加一行：

```python
    from app.core.ai_sanitizer import enable_person_name_mask
    enable_person_name_mask(settings.ai_mask_person_name)
```

⚠️ **默认仍是关的**（开了会把几乎每个中文词都遮成 `[PERSON_NAME]`）。

- [ ] **Step 6: 提交**

```bash
git add pcs-backend/app/core/ai_sanitizer.py pcs-backend/app/main.py pcs-backend/tests/core/test_ai_sanitizer.py
git commit -F <msgfile>   # 首行: feat(P10-A): AI 请求递归脱敏 + 规范化哈希（人名遮蔽默认关）
```

---

## Task T7：`ai_audit_log` 加列 + 迁移 `p10_001`

**Files:**
- Modify: `pcs-backend/app/models/system.py`（`AiAuditLog` 加 **8** 列；⚠️ 时间列**复用既有 `occurred_at`**，不新增 `timestamp` ⇒ D16）
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
| ~~`timestamp`~~ | — | ⚠️ **不新增** —— 复用既有 `occurred_at`（D16） |

- [ ] **Step 1: 核实既有列名（**先做这一步，否则迁移可能直接失败** · 审查 B5）**

```bash
cd pcs-backend && uv run python -c "
from app.models.system import AiAuditLog
cols = [c.name for c in AiAuditLog.__table__.columns]
print('既有列:', cols)
new = ['request_id','client_request_id','endpoint','status_code','duration_ms','sanitized_request_hash','response_summary','model_version']
print('冲突:', [c for c in new if c in cols])
"
```

**2026-11-04 实测结果**：既有 16 列 = `ai_log_id` · `agent_id` · `session_id` · `user_id` ·
`operation` · `prompt_text` · `response_text` · `prompt_tokens` · `response_tokens` ·
`model` · `cost_usd` · `decision_ref_type` · `decision_ref_id` · `human_approved` ·
`human_approver_id` · **`occurred_at`** ⇒ **与要加的 8 列无冲突** ✅

⚠️⚠️ **但发现一件事**：既有表**已经有 `occurred_at`**（时间列）⇒ SPEC 的
`timestamp` 会变成**第二个时间列** ⇒ 两个时间列语义重叠 ⇒ 以后没人知道该读哪个
⇒ **本批复用 `occurred_at`，不新增 `timestamp` 列**（偏离登记 **D16**）⇒
新增列数 **8**（不是 9）。

- [ ] **Step 2: 写失败的测试**

```python
def test_migration_adds_the_eight_columns():
    """迁移 upgrade 后 ai_audit_log 有这 8 个新列（时间列复用既有 occurred_at ⇒ 不含 timestamp）。"""

def test_request_id_unique_index_is_partial():
    """唯一索引是 partial（WHERE request_id IS NOT NULL）——
    ⚠️ **既有 SUP-006 行 request_id 为 NULL** ⇒ 非 partial 会因重复 NULL 失败。"""

def test_orm_matches_migration():
    """ORM 声明的列与迁移一致（漂移守卫）。"""
```

- [ ] **Step 3: 跑测试确认**失败**

Run: `cd pcs-backend && uv run pytest tests/alembic/test_p10_001_ai_audit_fields.py -q`
Expected: FAIL —— 迁移不存在

- [ ] **Step 4: 写迁移**

`alembic/versions/p10_001_ai_audit_request_fields.py`：

```python
revision = "p10_001"
down_revision = "p9_015"
```

`upgrade()`：**8 个** `op.add_column`（全部 `nullable=True`）⇒ `op.create_index("ux_ai_audit_log_request_id", "ai_audit_log", ["request_id"], unique=True, if_not_exists=True, postgresql_where=sa.text("request_id IS NOT NULL"))` ⇒ `op.create_index("ix_ai_audit_log_endpoint_occurred_at", "ai_audit_log", ["endpoint", "occurred_at"], if_not_exists=True)`（⚠️ 复用既有 `occurred_at`，**不新增** `timestamp` ⇒ D16）。

`downgrade()`：索引（`if_exists=True`）⇒ 列（`drop_column`）。

⚠️ **时间列复用既有 `occurred_at`**（D16）⇒ 迁移里**不**出现 `timestamp` ⇒
既有的 16 列一行不动 ⇒ SUP-006 的审计语义完全不变。

- [ ] **Step 5: 跑测试确认**通过**

Run: `cd pcs-backend && uv run pytest tests/alembic/test_p10_001_ai_audit_fields.py -q`
Expected: PASS

- [ ] **Step 6: 跑迁移闸门（两库各一次 · 独立进程）**

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

- [ ] **Step 7: 跑幂等闸门**

Run: `cd pcs-backend && uv run python scripts/check_migration_idempotency.py`
Expected: RC=0

- [ ] **Step 8: 提交**

```bash
git add pcs-backend/app/models/system.py pcs-backend/alembic/versions/p10_001_ai_audit_request_fields.py pcs-backend/tests/alembic/test_p10_001_ai_audit_fields.py
git commit -F <msgfile>   # 首行: feat(P10-A): ai_audit_log 加 P10 请求审计 8 列（partial 唯一索引；时间列复用 occurred_at）
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
  - `class OutboundAIClient`：`__init__(self, *, endpoint: str, timeout: int, cidrs: list[str], audit_fn: Callable[[dict], Awaitable[None]] | None = None)` · `async def call(self, payload: dict) -> dict` · `async def _audit(self, payload: dict) -> None`
    ⇒ ⚠️ **`audit_fn` 必须可注入**（审查 I4）：P10 阶段 `_audit` 是 no-op
    ⇒ **测试没法观察「进 `_audit` 的 payload 已脱敏」** ⇒ 注入一个 fake 才有断言对象

- [ ] **Step 2: 写失败的测试**

```python
async def test_ai_not_implemented_error_becomes_501_with_request_id(client):
    """抛 AINotImplementedError ⇒ 501 + 信封含 code/message/request_id。"""

async def test_outbound_client_validates_endpoint_before_calling():
    """endpoint 不在内网 CIDR ⇒ RuntimeError（**且没发出任何请求**）。"""

async def test_outbound_client_sanitizes_payload_before_audit():
    """进 `_audit` 的 payload 已脱敏（邮箱被替换）。
    ⚠️ **靠注入的 `audit_fn` 观察** —— `_audit` 默认是 no-op ⇒ 没有别的观察点（审查 I4）。"""

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
- `_audit`：`if self._audit_fn is not None: await self._audit_fn(payload)` ⇒ 默认 no-op
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
  - `POST /api/v1/ai/knowledge/search` —— 请求 `AiKnowledgeSearchRequest{query: str, top_k: int = Field(5, alias="topK")}` ⇒ **501**
    ⇒ ⚠️ **必须带 alias `topK`**（审查 B7）：SPEC §4.1.2 的请求体字段名是 **`topK`**；
    若 schema 只写 `top_k` ⇒ Pydantic 默认**忽略** `topK` ⇒ 前端传的值**静默失效**、
    而且**不报错** ⇒ 契约字段名必须仍是 `topK`（`populate_by_name=True` 允许两种写法都能进）
  - 两个路由都带 `openapi_extra={"x-status": "reserved"}`（**不用** `deprecated`）
  - `AiContext`（**具名** schema）：`project_id: str | None = Field(None, alias="projectId")` · `module: str | None = None` · `record_id: str | None = Field(None, alias="recordId")` + `model_config = ConfigDict(populate_by_name=True)`
    ⇒ ⚠️ **必须带 alias**（审查 M2）：SPEC §4.1.1 的 `context` 用**驼峰**
      （`projectId` / `module` / `recordId`）⇒ 若只写蛇形字段名，
      Pydantic 默认**忽略未知字段** ⇒ 前端传的 `projectId` **静默变成 None**
      ⇒ **与 B7（topK）完全同型**的缺陷。
    ⇒ `populate_by_name=True` ⇒ 蛇形与驼峰**两种写法都能进**（内部仍用蛇形）
    ⇒ ⚠️ SPEC §4.1.1 的 `context` 有 3 个字段 ⇒ 声明成**具名 schema**而不是裸 dict
    （仓的纪律：新增端点必须显式声明结构）
    ⇒ ⚠️ **注**：裸 `dict | None` 其实**不会**让裸载荷数上涨 —— 闸门的 `_TYPED_KEYS`
      含 `anyOf`，而 `dict | None` 在 OpenAPI 里是 `anyOf` ⇒ 不计裸
      （审查 B8 的「裸载荷会涨 72」是**误报**，已实测验证）⇒ 但**仍然**用具名 schema，
      理由是 **SPEC 要求 + 字段名有编译期约束**，不是「怕涨裸载荷」

- [ ] **Step 2: 写失败的测试**

```python
async def test_ai_intent_returns_501(client, designer_headers):
    """501 + 信封 {code:'AI_NOT_IMPLEMENTED', message:'AI功能即将上线', request_id:...}。"""

async def test_ai_knowledge_search_returns_501(client, designer_headers):
    ...

async def test_ai_routes_require_auth(client):
    """无 bearer ⇒ 401（**不是** 501）—— 认证在 501 之前。"""

async def test_ai_routes_have_x_status_reserved_in_openapi():
    """契约里两个端点带 x-status=reserved 且**不是** deprecated。"""

async def test_ai_knowledge_search_accepts_topK_alias(client, designer_headers):
    """⚠️ **契约里的字段名是 `topK`**（SPEC §4.1.2）⇒ 传 topK 能被收到
    （审查 B7）—— 否则前端传的值静默失效。"""

async def test_ai_intent_context_is_a_named_schema():
    """`context` 是具名 schema（`AiContext`）⇒ 字段名有编译期约束。"""

async def test_ai_intent_context_accepts_camelCase_aliases(client, designer_headers):
    """⚠️ **SPEC §4.1.1 的 context 用驼峰**（`projectId` / `recordId`）
    ⇒ 必须能收到（审查 M2）—— 否则前端传的值静默变 None（同 B7）。"""
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

## Task T10：ARQ 审计任务与入队（幂等 · 失败降级 · Review Focus #3）

> ⚠️ **顺序已调整**（审查 B6）：本 Task **先于**中间件落地 —— 中间件要调
> `enqueue_ai_audit_log`，它不存在的话中间件的测试直接 ImportError ⇒ TDD 走不下去。

**Files:**
- Create: `pcs-backend/app/services/ai/__init__.py` + `pcs-backend/app/services/ai/arq_queue.py`
- Create: `pcs-backend/app/workers/ai_audit_tasks.py`
- Modify: `pcs-backend/app/workers/worker.py`（注册函数）
- Create: `pcs-backend/tests/services/ai/test_ai_audit_task.py`

**Interfaces:**
- Produces:
  - `app/services/ai/arq_queue.py::async def enqueue_ai_audit_log(**fields) -> bool`
    ⇒ ⚠️ **必须是 `async`**（`pool.enqueue_job` 是 async；审查 I3 —— 原计划写成同步签名，与中间件里的 `await` 不一致）
    ⇒ ⚠️ **绝不抛**：失败 ⇒ `logger.warning` + 返回 `False`（降级）
  - `app/workers/ai_audit_tasks.py::async def write_ai_audit_log(ctx, **fields) -> None`
    ⇒ 幂等写库（`request_id` 唯一）
    ⇒ ⚠️ **ARQ 默认 `max_tries=5`**（本批不显式改它）⇒ 幂等测试**直接调它两次**来模拟重试，
      而不是依赖 ARQ 的重试机制（审查 I13）

- [ ] **Step 2: 写失败的测试**

```python
async def test_audit_write_is_idempotent(db_session, ...):
    """⚠️ **Review Focus #3** —— 同一 request_id 写两次 ⇒ 只有一行。
    （ARQ 默认 max_tries=5 ⇒ 重试必然发生 ⇒ 幂等不是「锦上添花」。）"""

async def test_enqueue_failure_is_swallowed(monkeypatch):
    """Redis 挂 ⇒ enqueue 返回 False，**不抛**（降级）。"""

async def test_task_is_registered_in_worker_functions():
    """⚠️ ARQ 对**未注册**的函数名不报错 ⇒ job 静静躺着 ⇒ 棘轮会抓。

    ⚠️ **与既有棘轮的关系**（审查 m3）：仓里已有
    `tests/workers/test_worker_registers_all_enqueued_tasks.py` 断言
    「入队的 ⊆ 已注册的」⇒ **那条是通用棘轮**；本条是**具体的**断言
    （`write_ai_audit_log` 在 `WorkerSettings.functions` 里）⇒ **两条不重复**：
    通用棘轮防「漏注册任何任务」，本条防「这个任务被改名后忘了同步注册表」。"""

async def test_audit_write_uses_the_pg_conflict_clause_on_postgres():
    """PG 分支走 `ON CONFLICT DO NOTHING`（方言级断言）。"""

async def test_audit_write_swallows_integrity_error_on_sqlite(db_session, monkeypatch):
    """⚠️ SQLite 分支是「先查后插」⇒ 并发下第二个插入抛 IntegrityError
    ⇒ 必须 catch 掉，不算失败（审查 S8）。

    ⚠️ **单线程里造不出这个竞态** ⇒ 必须**显式构造**（审查 C4）：
    monkeypatch 掉查询，让它**返回空**（模拟「查的时候不存在」），
    再让插入抛 `IntegrityError`（模拟「插的时候已经存在」）⇒
    断言 `write_ai_audit_log` **不抛**且**返回 None**。
    ⇒ ⚠️ 不这样构造的话，这条测试**永远绿**（第二次调用时查询确实查到了 ⇒ 走的是
    「跳过」分支 ⇒ 根本没碰 IntegrityError）⇒ **假测试**。"""
```

- [ ] **Step 2: 跑测试确认**失败**

Run: `cd pcs-backend && uv run pytest tests/services/ai/ -q`
Expected: FAIL —— 模块不存在

- [ ] **Step 3: 实现**

实现要点：
- 入队 helper **照 `app/services/report/arq_queue.py` 的形状但语义相反**：
  那里失败抛 503；这里失败**返回 False** + `logger.warning`
  ⇒ ⚠️ **不要**复用那个 `_enqueue`（它会抛 ⇒ 端点 503 ⇒ 审计拖死业务）
- 写库**分方言**：
  - PG：`sqlalchemy.dialects.postgresql.insert(...).on_conflict_do_nothing(index_elements=["request_id"])`
  - SQLite（**单测库**）：先 `SELECT` 查 ⇒ 有就跳过；没有就插 ⇒ **并 `except IntegrityError: pass`**
    ⇒ ⚠️ `ON CONFLICT` 在 SQLite 上不可用（审查 S8 / 原计划的坑）
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

## Task T11：纯 ASGI 审计中间件（Review Focus #1 #2）

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
  - 审计入队（`await enqueue_ai_audit_log(...)`，T10 已落地）⇒ 失败降级

- [ ] **Step 2: 写失败的测试**

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
    """审计**异步**（入队）⇒ 端点不因审计写库慢而变慢。
    ⚠️ 单测里 monkeypatch `enqueue_ai_audit_log`（别真连 Redis）。
    ⚠️ **patch 的是中间件模块里的那个引用**
    （`app.core.ai_audit_middleware.enqueue_ai_audit_log`），
    **不是**源模块 `app.services.ai.arq_queue` ⇒ 因为中间件是
    `from ... import enqueue_ai_audit_log`（**绑定了名字**），
    patch 源模块**不会**影响中间件手里的引用（审查 m4）。"""

async def test_audit_records_500_when_no_response_is_sent(client, designer_headers):
    """⚠️ **SPEC E10** —— 下游异常**未产生响应**时 ⇒ status_code 记 **500**
    （不是 None、不是 0）。"""

async def test_large_body_is_not_hashed(client, designer_headers):
    """⚠️ body > **1MB** ⇒ `sanitized_request_hash` 为 **None**（不哈希大 body）。"""
```

- [ ] **Step 2: 跑测试确认**失败**

Run: `cd pcs-backend && uv run pytest tests/api/v1/test_ai_audit_middleware.py -q`
Expected: FAIL —— 中间件不存在（请求不走审计）

- [ ] **Step 3: 实现**

实现要点（照 SPEC §3.2.1(4) 的纯 ASGI 示意，**修五处**）：
- ⚠️ **body 重放**：`receive_cached` 第一次调用时把 body 存下来；后续调用要**重放**已缓存的 chunk，否则下游收不到 body ⇒ 标准做法是缓存后**重放**再继续读原 receive
- ⚠️ **`user_id` 提取**：`scope["headers"]` 里找 `authorization` ⇒ `decode_token` ⇒ `sub` → `user_id = uuid5(NAMESPACE_DNS, sub)`（**与 `current_actor` 同一套派生逻辑** ⇒ 抽成共用函数，别写两套）
- ⚠️ **异常路径**：中间件**不捕获** `AINotImplementedError`（H4）⇒ 只在 `finally` 里记录响应状态
- ⚠️ **E10**：`effective_status = status_code if status_code is not None else 500`
- ⚠️ **1MB 上限**：`sanitized_hash = hash_sanitized(body) if len(body) <= 1024 * 1024 else None`

- [ ] **Step 4: 跑测试确认**通过**

Run: `cd pcs-backend && uv run pytest tests/api/v1/test_ai_audit_middleware.py -q`
Expected: PASS（8 passed）

- [ ] **Step 5: 提交**

```bash
git add pcs-backend/app/core/ai_audit_middleware.py pcs-backend/app/main.py pcs-backend/tests/api/v1/test_ai_audit_middleware.py
git commit -F <msgfile>   # 首行: feat(P10-A): AI 审计中间件（纯 ASGI · body 重放 · 认证失败也留痕）
```

---

## Task T12：`/health/ai`

**Files:**
- Modify: `pcs-backend/app/api/v1/health.py`
- Create: `pcs-backend/tests/api/v1/test_health_ai.py`

**Interfaces:**
- Produces: `GET /health/ai` ⇒ `{"status": "not_configured" | "ok" | "degraded", "reason": str | None, "ai_enabled": bool, "endpoint_configured": bool, "cidrs_configured": bool}`
  ⇒ ⚠️ **`cidrs_configured` 的判据 = `parse_cidrs()` 之后**非空（不是原始串非空）
  ⇒ ⚠️ **非法 CIDR 不许让健康端点崩**（审查 C6）：`parse_cidrs` 会抛 `RuntimeError`
    ⇒ 必须 `try/except` ⇒ 降级为 `cidrs_configured=False` + `reason="invalid_cidrs"`
    ⇒ 健康端点**恒 200**

- [ ] **Step 2: 写失败的测试**

```python
async def test_health_ai_reports_not_configured_by_default(client):
    """默认 ⇒ status='not_configured'，且 **始终 200**（不因 AI 未配置而报错）。"""

async def test_health_ai_reports_endpoint_not_in_cidrs(client, monkeypatch):
    """endpoint 是 **IP 字面量**且不在 CIDR 内 ⇒ 'degraded'（**不是** 500）。"""

async def test_health_ai_does_not_resolve_dns_for_a_domain_endpoint(client, monkeypatch):
    """⚠️ **域名 endpoint 不做 DNS 解析**（审查 I8）⇒ 恒 degraded +
    reason='endpoint_is_domain_not_verified'。"""

async def test_health_ai_does_not_crash_on_invalid_cidrs(client, monkeypatch):
    """⚠️ **非法 CIDR 不许让健康端点崩**（审查 C6）⇒ 恒 200 +
    cidrs_configured=False + reason='invalid_cidrs'。"""
```

- [ ] **Step 2: 跑测试确认**失败**

Run: `cd pcs-backend && uv run pytest tests/api/v1/test_health_ai.py -q`
Expected: FAIL —— 端点不存在（404）

- [ ] **Step 3: 实现**

⚠️ **判定范围要写清楚**（审查 I8）：「不探测 DNS」与「判断域名是否在内网」**互相矛盾**
—— 域名不在内网这件事**必须解析 DNS 才知道**。⇒ 本批的裁决：

| endpoint 形态 | 判定 | `status` |
|---|---|---|
| 未配置 | 不判 | `not_configured` |
| **IP 字面量** | 本地比对 CIDR（不联网） | 在内网 ⇒ `ok`；不在 ⇒ `degraded` |
| **域名** | **不解析**（避免健康检查被墙/变慢） | 恒 `degraded` + `reason="endpoint_is_domain_not_verified"` |

⇒ **域名 endpoint 永远不会是 `ok`** —— 这是**如实**的（没验证过就不能说它在内网）
⇒ 测试用 IP 字面量（`8.8.8.8`）而不是真域名 ⇒ 不依赖 DNS。

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

- [ ] **Step 2: 写失败的测试**

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

⚠️ **静态扫描的局限要写进注释**（审查 S9）：本守卫扫的是 **URL 字面量** ⇒
`httpx.post(url_var, ...)`（url 是变量）**扫不到** ⇒ 将来若有人用变量调 AI 端点，
守卫**抓不到**。⇒ 约定：**AI 端点的 URL 必须直接写 `settings.ai_endpoint` 或字面量**，
否则绕过守卫。

- [ ] **Step 4: 加 AI 可选依赖（SPEC §3.2.1(8) · 审查 I11）**

`pcs-backend/pyproject.toml`：

```toml
[project.optional-dependencies]
# ⚠️ **默认不安装** —— `uv sync` 不装 optional 组 ⇒ 默认安装不 import 失败
# （SPEC §3.2.1(8) 的原话）。⇒ 架构守卫的「全仓零命中」仍然成立。
ai = [
    "langchain>=0.2",
    "ollama>=0.3",
    "vllm>=0.5",
]
```

⚠️ 加完要跑一次 `uv sync`（**不加** `--extra ai`）确认默认环境仍能装得上、且不拉这三个包。

- [ ] **Step 5: 跑测试确认**通过**

Run: `cd pcs-backend && uv run pytest tests/architecture/test_no_direct_ai_sdk.py -q && uv sync && uv run pytest tests/architecture/test_no_direct_ai_sdk.py -q`
Expected: 两次都 PASS（第二次证明默认环境没被 optional 依赖污染）

- [ ] **Step 6: 提交**

```bash
git add pcs-backend/tests/architecture/test_no_direct_ai_sdk.py pcs-backend/pyproject.toml pcs-backend/uv.lock
git commit -F <msgfile>   # 首行: test(P10-A): 架构守卫 + AI 可选依赖隔离（默认不装）
```

---

## Task T15：契约 / SPEC 偏离回写 / 账簿 / QA 收口

**Files:**
- Modify: `pcs-backend/docs/openapi.json` + `docs/openapi-baseline.json`
- Modify: `pcs-frontend/openapi.snapshot.json` + `src/types/api.d.ts`
- Modify: `spec/PCS-SPEC-P10 V1.3.1 P10 AI预留与测试部署开发规格说明书.md`（**偏离登记 D1~D16 回写**）
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

⚠️ **MSW mock 本批无需改**（审查 S10）：前端只加了一个**禁用**的 AI 按钮 ⇒
**不调**任何 AI API ⇒ 没有新的 mock handler 要加 ⇒ seed 的 ajv 校验不受影响。

- [ ] **Step 5: 浏览器回归（gstack）**

- 顶栏 AI 按钮**存在且禁用**
- AI 端点可直连：

```bash
curl -i -X POST http://localhost:8000/api/v1/ai/intent \
  -H 'Authorization: Bearer <token>' \
  -H 'Content-Type: application/json' \
  -d '{"text":"x"}'
```

  ⚠️ **`Content-Type` 必须带**（审查 S4）—— 不带 ⇒ FastAPI 解析 body 失败 ⇒
  返回 **422** 而不是 501 ⇒ 会误判成「端点没实现对」。
- 控制台 0 error；网络 0×404
- 报告落 `.gstack/qa-reports/qa-report-pcs-frontend-2026-11-04-p10a.md`

- [ ] **Step 5b: 验真后端 E2E 通道（审查 I9）**

⚠️ T3 建了 `real-backend` 通道，**批末不验 ⇒ 下一个改坏它的人不会被发现**
⇒ 本步必须跑（需后端在 :8000 + 种子数据已灌，见 T1 的起栈命令）：

```bash
# 起栈
docker compose --profile test up -d
docker compose --profile test run --rm seed
cd pcs-backend && uv run uvicorn app.main:app --port 8000 &
# 跑真后端 E2E
cd pcs-frontend && VITE_ENABLE_MOCK=false npx playwright test --project=real-backend
```

Expected: **至少 1 passed**（⚠️ 若显示「0 passed」⇒ grep 没匹配上 ⇒ 回看 T3 的 tag）

- [ ] **Step 6: 回写 SPEC 偏离登记 D1~D16**

在 `spec/PCS-SPEC-P10 V1.3.1 ….md` 里新增一节「**与仓库现状的偏离登记（2026-11-04）**」⇒ 逐条写：SPEC 原文 / 仓里实际 / 裁决 / 影响面。**D1~D9 一条都不能少**（总纲里有完整表格）。

- [ ] **Step 7: 更新账簿**

- **开发计划升 V1.4**（P10-OPEN-008 · 总纲 Q5 · 审查 S12）：更新 `docs/PCS-PLAN-*.md` 的 P10 部分（批次划分 + 偏离登记）
- `TODOS.md`：登记 P10-OPEN-002（pgvector 扩展延后）· P10-OPEN-010（CIDR 清单待 IT）· 「P10-B 启动前需量种子数据规模」
- `.wolf/buglog.json`：本批若无缺陷则不记
- `.wolf/cerebrum.md` Do-Not-Repeat 新增：
  - 「**审计/日志类需求先查既有表** ⇒ 本仓 `ai_audit_log` 已存在（SUP-006）⇒ spec 说『建表』时先核字段」
- 「**纯 ASGI 中间件读 body ⇒ 必须重放** ⇒ 否则下游 Pydantic 收不到 ⇒ 症状是 422 不是 501」
- 「**compose profile：日常开发服务绝不加 profile**」⇒ 加了之后 `docker compose up` 不再起它们 ⇒ 破坏开发流程；profile 只给**一次性任务**（如 seed）
- 「**一次性容器服务必须挂源码卷 + 用 `uv run --frozen`**」⇒ uv 官方镜像里**没有**项目依赖 ⇒ 裸 `python scripts/x.py` 立刻 ModuleNotFoundError
- 「**改既有表前先列一遍既有列名**」⇒ 与要加的列**撞名** ⇒ `op.add_column` 直接失败（PG: column already exists）
  - 「**ARQ 未注册的函数名不报错** ⇒ job 静静躺着 ⇒ 入队 ⊆ 已注册 要有棘轮」
- `.wolf/STATUS.md`：第 28 轮

- [ ] **Step 8: 提交**

```bash
git add -A
git commit -F <msgfile>   # 首行: docs(P10-A): 契约滚动 + SPEC 偏离登记 D1~D16 + 账簿同步
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
| 迁移 | `p10_001` 在 **pcs / pcs_test** 两库都到 head；`alembic check` exit 0；幂等闸门 RC=0；**8 个新列无撞名** |
| 健康端点 | `/health/ai` 恒 **200**；未配置 ⇒ `not_configured` |
| 架构守卫 | AI SDK 只能从 `OutboundAIClient` 出；httpx 调 AI 端点只允许它 |
| 种子 | 跑两次不炸、不重复；`--reset` 只删自己的行 |
| E2E | MSW 可关；真后端通道冒烟通过；**导航走 SPA 菜单** |
| 契约 | G-08 4/4；裸载荷 **不涨**；前后端类型同步 |
| 后端全量 | 0 failed（基线 5481 ⇒ 净增）；PG 车道 exit 0 |
| 前端全量 | typecheck + lint + vitest 全绿；Playwright mock 通道全绿 |
| SPEC | **偏离登记 D1~D16 全部回写** |
| 浏览器 | 顶栏 AI 禁用按钮；控制台 0 error；0×404 |

---

## 尚未解决的问题（开工前需裁决或登记）

| # | 问题 | 现状 | 本批处置 |
|---|---|---|---|
| 1 | **P10-OPEN-010 内网 CIDR 清单** | 待 IT 提供 ⇒ 本批只做机制（可配置 + 非法即启动报错）⇒ 用回环地址测试 | **不阻塞** ⇒ 登记 TODO |
| 2 | **P10-OPEN-002 pgvector 维度** | 未定 ⇒ 本批**不建扩展**（偏离 D3）⇒ `document_chunks.embedding_vector` 仍是 JSONB | 登记 TODO（P10-A 收口） |
| 3 | **PgBouncer 引入** | SPEC 部署图有、仓里没有 ⇒ 引入要改所有服务的 `DATABASE_URL` + 会话级特性约束 | **本批不做** ⇒ P10-D 开工前裁决（总纲 Q1） |
| 4 | ~~`ai_audit_log` 的 `timestamp` 列名~~ | —— | ✅ **已由 D16 裁决**：既有表已有 `occurred_at` ⇒ **复用它、不新增 `timestamp`** ⇒ 本批加 **8** 列（不是 9） |
| 5 | **`document_chunks` 字段与 SPEC 不同** | 仓里已有 7 个字段（含 `embedding_vector JSONB`），SPEC 描述的是另 4 个字段 | 本批**不动**（偏离 D6）⇒ P10-OPEN-002 一并处理 |
| 6 | **AI 端点的权限模型** | SPEC 只说 `Depends(current_user)`，没说什么角色能调 | 本批：**任何已认证用户**都能调（但一律 501）⇒ 将来真开时再定 |
| 7 | **18 个 E2E 场景的种子规模** | 未知 | P10-B 开工前量一次（总纲开放问题 6） |
