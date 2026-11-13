# P10-B 实施计划：全流程 E2E（10.2）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 SPEC §3.2.2 的 **18 个 E2E 场景**（E2E-001~018）+ **SUP-007 两层状态机五类路径**（WF-PATH-01A~01E / 02 / 03 / 04）+ **权限矩阵**（AUTH-E2E-01~12）在**真 PG + 真后端**上跑起来。

**Architecture:** **两条腿** —— ① **后端全流程 E2E**（pytest + httpx + **隔离 schema 的真 PG**）覆盖 18 场景的主体（数据流、状态机、权限）；② **前端真后端通道**（Playwright `real-backend`）覆盖 **5 条用户看得见的 UI 流**。两条腿共用**同一份流程级种子**（`scripts/seed_e2e_flows.py`），种子只造**起点态**（项目 + 角色矩阵 + 物流 + 签署矩阵 + 交付物）⇒ **每个状态都由场景自己走真实端点推进**（不是「摆」一个已存在的状态来断言）。

**Tech Stack:** FastAPI · SQLAlchemy 2.x async · alembic · pytest（asyncio_mode=auto）· Playwright · React 19 + antd 5

**Spec:** `spec/PCS-SPEC-P10 V1.3.1 P10 AI预留与测试部署开发规格说明书.md` §3.2.2（10.2）· 批次顺序见 `docs/superpowers/plans/2026-11-04-p10-master-plan.md` §二 · 前批（10.0/10.1）见 `docs/superpowers/plans/2026-11-04-p10-batch-a-preflight-ai-reserve.md`

---

## Global Constraints

- **分支 `main`，不要建 worktree**；**conventional commits**；长消息写文件后 `git commit -F <file>`。
- ⚠️ **口令不要写在命令行**（只在环境变量 / 进程内派生）；⚠️ **不要用 `git checkout <commit> --detach`**。
- ⚠️ **本批不新建 CI 流水线**（既有裁决）⇒ SPEC 的「E2E 在 CI 中可自动执行」**本批不满足** ⇒ 登记偏离（见 T8）。
- ⚠️ **本批不改 `alembic/versions/*`**（种子只造数据，不改 schema）⇒ 无迁移漂移风险 ⇒ 不跑 `alembic check`。
- ⚠️ **E2E 跑在隔离 schema**（沿用 `tests/api/v1/test_stream_batch_concurrency_pg.py` 的形状）⇒ **开发库 public schema 一个字节不动** ⇒ **不许**直接往 `pcs` / `pcs_test` 写 E2E 数据。
- ⚠️ **PG 车道唯一入口仍是 `scripts/pytest_pg.sh`** ⇒ E2E 是**另一条车道**（`scripts/pytest_e2e.sh`）⇒ 不许把 `-m e2e` 混进 PG 车道。
- 契约改动 ⇒ 批末滚 OpenAPI baseline + G-08 `--check-baseline`；**裸载荷数不得上涨**。
- 前端类型**契约派生** ⇒ 后端加字段后重跑 `npm run api:gen` + 同步 MSW mock。
- ⚠️ **每批落地后必须跑 gstack-qa 浏览器回归**（`CLAUDE.md`），报告落 `.gstack/qa-reports/`（gitignored）。

---

## Review Focus

以下五类情形 SPEC 要求、但**没有现成测试**，最可能咬到真实用户；每条都在对应 Task 里落成测试。

1. **上游变更 ⇒ 下游记录变 `STALE` ⇒ 确认重算**（E2E-013 / WF-PATH-01C）—— 状态机的「陈旧」判定错了 ⇒ 用户拿着过期数据出计算书 ⇒ **比算错更严重**。
2. **代录客户批准必须落「谁代录的」**（E2E-012）—— `deliverables.customer_approval_proxy_by` 为空 ⇒ 事后无法追责 ⇒ 客户投诉时查不到人。
3. **越权的形状必须是 404（与「不存在」同形）**（E2E-016）—— 403 会**泄露资源存在性** ⇒ 枚举得出别人的项目/物流 id。
4. **AI 关着时零副作用、AI 开着时审计必落**（E2E-017）—— 501 不能破坏既有流程；审计行必须真的写进 `ai_audit_log`（不是只入队）。
5. **种子的角色矩阵必须真的被用上**（AUTH-E2E 全组）—— 种子造的用户若没带**项目内角色** ⇒ 带项目守卫的端点全 404 ⇒ 场景全飘（且症状看着像「端点坏了」）。

---

## 事实基础（2026-11-13 实测，非推断）

| 事实 | 证据 |
|---|---|
| SPEC §3.2.2 存在且是 **V1.3.1**（18 场景 + WF-PATH 五类 + AUTH-E2E 12 条） | `spec/PCS-SPEC-P10 V1.3.1 …md:703-771` ⇒ ⚠️ 总纲 §四之二写的「V1.3.1 不存在 ⇒ D20」**已过时**（两个文件都在，V1.0 那份是 `spec/P10 AI预留与测试部署开发规格说明书.md`）⇒ **本批以 V1.3.1 为准** |
| 记录层 **9 态**已实现 | `app/models/enums.py::RecordSignStatus9`（DRAFT/IN_APPROVAL/CHECKED/CHECK_REJECTED/STALE/CHANGE_PENDING/CHANGED/REVERSAL_PENDING/OBSOLETE）+ `StreamSignStatus`（同 9 值） |
| 状态机 **13 事件** + 角色集 | `app/services/state_machine.py::TRANSITION_ROLES` ⇒ 全局角色词表 = **DESIGNER / CHECKER / REVIEWER / APPROVER / SYSTEM_ADMIN** ⇒ ⚠️ SPEC 写 **SYSADMIN** ⇒ **词表不一致** ⇒ 偏离登记 |
| 粗闸 ≠ 最终判据 | 同上注释：「端点仍要求 `actor.role == record.approval_role`（= 矩阵这一步该谁签）」⇒ 权限矩阵要测**两步**（谁被允许 + 谁被允许到那一步） |
| 批准链的定义源 = 项目绑定的 `module='RECORD'` 签署矩阵 | `app/api/v1/records_actions.py` 文件头 ⇒ 内置记录级矩阵第 2 步是 **REVIEWER** |
| 交付物 Rev / 代录 / 变更单 **都有** | `/api/v1/deliverables/{id}/{versions,versions/{rev}/snapshot,sign-step,issue,customer-approval/proxy}` · `deliverables.customer_approval_proxy_by` · `records/{module}/{id}/change-notice` |
| 18 场景涉及的端点**全部存在** | `pcs-backend/docs/openapi.json`（259 路径）⇒ 见 T3/T4/T6 各 Task 的端点清单 |
| 项目内角色 6 值（**无 TEST_VIEWER**） | `app/models/project.py:209` ⇒ DESIGNER/CHECKER/APPROVER/REVIEWER/VIEWER/PROJECT_LEAD ⇒ ⚠️ SPEC 的 **TEST_VIEWER 不存在**，且「测试报告页」属 **P10-C** ⇒ AUTH-E2E-11/12 **本批不做** |
| 现有种子是**冒烟级** | `scripts/seed_e2e_data.py`：1 工作区 · 1 项目 · 4 用户 · 2 物流 · **项目内角色统一 `DESIGNER`** ⇒ ⚠️ 权限矩阵要 per-user 角色 ⇒ **本批加角色维度**（不扩业务数据量，见 T2） |
| 用户 id = `uuid5(NAMESPACE_DNS, username)` | 种子与 `app/api/v1/config.py:557` **同款派生** ⇒ token 的 `sub` 必须是 **username** |
| 真后端 Playwright 通道已有，但**只有 1 条**用例 | `pcs-frontend/e2e/real_backend_smoke.spec.ts`（冒烟：登录 ⇒ 仪表盘 ⇒ **读种子项目必须 200**）· `fixtures.ts::realPage` · `playwright.config.ts` 的 `real-backend` project（`reuseExistingServer: false` · 5174） |
| mock 通道 23 条已绿 | `npm run e2e` ⇒ 23 passed ⇒ **本批不动 mock 通道** |
| 隔离 schema 的现成形状 | `tests/api/v1/test_stream_batch_concurrency_pg.py`：`CREATE SCHEMA` → `alembic upgrade head`（`options=-csearch_path=`）→ 测完 `DROP SCHEMA ... CASCADE` |
| `strict_client` 已存在（守卫测试入口） | `tests/conftest.py::strict_client` ⇒ TODO-141「全量迁 strict_client」**本批只迁新写的用例**（总纲 §四之二 8e） |
| 后端**没有**任何全流程 API 测试 | `tests/` 只有单点 API 测试 ⇒ P10-B 是**新建**这条能力 |

---

## 文件结构

| 文件 | 责任 |
|---|---|
| `pcs-backend/scripts/pytest_e2e.sh` | **新建** · E2E 车道的唯一入口（三道 fail-closed） |
| `pcs-backend/scripts/seed_e2e_flows.py` | **新建** · 流程级种子（角色矩阵 + 起点态数据，幂等） |
| `pcs-backend/tests/scripts/test_seed_e2e_flows.py` | **新建** · 种子的幂等 + 角色矩阵守卫 |
| `pcs-backend/tests/e2e/conftest.py` | **新建** · 隔离 schema + 种子 + `e2e_client` + 角色 token |
| `pcs-backend/tests/e2e/helpers.py` | **新建** · 场景共用的调用helper（造记录 / 调计算端点 / 推状态机） |
| `pcs-backend/tests/e2e/test_lane_smoke.py` | **新建** · 车道自检（schema 已迁移 + 种子在位 + 角色 token 对得上） |
| `pcs-backend/tests/e2e/test_e2e_project_config.py` | **新建** · E2E-001（项目 → BEDD → 输入清单） |
| `pcs-backend/tests/e2e/test_e2e_sim_import.py` | **新建** · E2E-002（SIM 导入 → 物流验证） |
| `pcs-backend/tests/e2e/test_e2e_calc_chains.py` | **新建** · E2E-003/004/005/006（管道/泵/安全阀/容器） |
| `pcs-backend/tests/e2e/test_e2e_equipment_util.py` | **新建** · E2E-007/008（设备表 · 能耗汇总） |
| `pcs-backend/tests/e2e/test_e2e_report.py` | **新建** · E2E-009/015（计算书 · 自定义报表） |
| `pcs-backend/tests/e2e/test_e2e_supplier.py` | **新建** · E2E-014（供应商实际值 → 偏差报告） |
| `pcs-backend/tests/e2e/test_e2e_record_workflow.py` | **新建** · E2E-010 + WF-PATH-01A~01E |
| `pcs-backend/tests/e2e/test_e2e_deliverable_rev.py` | **新建** · E2E-011/012 + WF-PATH-02/03 |
| `pcs-backend/tests/e2e/test_e2e_permission_matrix.py` | **新建** · E2E-016 + AUTH-E2E-01~10/12 |
| `pcs-backend/tests/e2e/test_e2e_ai_audit.py` | **新建** · E2E-017（501 + 审计落库） |
| `pcs-backend/tests/e2e/test_e2e_schema_parity.py` | **新建** · E2E-018（两库 schema 版本一致） |
| `pcs-frontend/e2e/real_backend_flows.spec.ts` | **新建** · 真后端通道的 5 条 UI 流 |
| `pcs-backend/pyproject.toml` | 改 · 加 `e2e` marker |

---

## 前置状态更新（相对 2026-11-04 总纲）

| # | 变化 | 对本计划的影响 |
|---|---|---|
| 1 | **P10-A 已闭环**（`2ef122d`~`5b608a1` + 16 个评审修复 commit）⇒ 种子脚本 / 真后端通道 / AI 审计链 **都在** | T2 复用 P10-A 的种子形状（get-or-create + 固定 UUID）；T7 直接用现成的 `real-backend` project |
| 2 | **mock 登录默认关**（`PCS_ENABLE_MOCK_LOGIN` 双闸） | 真后端通道的后端必须带 `PCS_ENABLE_MOCK_LOGIN=true`（P10-A 已写进 `webServer` ⇒ 沿用） |
| 3 | **真后端通道现在有数据级断言**（评审 #8）⇒ 冒烟会读**种子项目** ⇒ 必须 200 | ⇒ 后端必须连**被 seed 的那个库**（`pcs_pgtest`，宿主 5433）⇒ README 已写 ⇒ T7 沿用 |
| 4 | **「不碰真库」的守卫修好了**（bug-2162）⇒ 单测车道不再连开发库 | ⇒ E2E 车道的隔离 schema **不会**被单测车道的污染影响 |
| 5 | 总纲写的「V1.3.1 不存在」**已过时**（见事实基础） | ⇒ **以 SPEC V1.3.1 为准**（18 场景）⇒ 登记修订 |

---

# 段一：地基

## Task T1：E2E 车道 + 隔离 schema + `e2e_client`

**Files:**
- Create: `pcs-backend/scripts/pytest_e2e.sh`
- Create: `pcs-backend/tests/e2e/conftest.py`
- Create: `pcs-backend/tests/e2e/test_lane_smoke.py`
- Modify: `pcs-backend/pyproject.toml`（`markers` 加 `e2e`）

**Interfaces:**
- Produces:
  - `scripts/pytest_e2e.sh` —— E2E 车道唯一入口：`pytest -m e2e`，**三道 fail-closed**
    （① PG 没起 ⇒ FAIL；② 收集到 0 个 ⇒ FAIL；③ 全 skip ⇒ FAIL）⇒ 形状照抄
    `scripts/pytest_pg.sh`（**不**新建第四种形状）
  - `tests/e2e/conftest.py` 的四个 fixture：
    | fixture | 作用域 | 产出 |
    |---|---|---|
    | `e2e_schema` | session | 隔离 schema 名（`e2e_<8hex>`）；建 schema → `alembic upgrade head`（`options=-csearch_path=`）→ 测完 `DROP SCHEMA ... CASCADE` |
    | `e2e_seed` | session | 跑 `scripts/seed_e2e_flows.py` 后的**种子 id 字典**（`project_id` / `workspace_id` / `stream_ids` / `users` / `matrix_id` / `deliverable_id` / `report_def_id`） |
    | `e2e_client` | function | `httpx.AsyncClient`，**真 app**（`create_app()` ⇒ 真中间件链）+ `get_db` 覆盖到隔离 schema 的 engine ⇒ 支持 `await e2e_client.post(...)` |
    | `role_headers` | function | `role_headers("DESIGNER")` ⇒ `{"Authorization": "Bearer <token>"}`（`create_access_token(subject=<username>, role=<role>)` ⇒ `sub` 必须是 **username** ⇒ actor 的 `user_id` 派生才对得上） |
  - ⚠️ **`e2e_client` 不用 `strict_client` 那套最小 app** —— E2E 要**真中间件链**（审计 / trace / CORS）⇒ 用 `create_app()`（同 P10-A 的 `ai_client` 形状）

- [ ] **Step 1: 写失败的测试**（`tests/e2e/test_lane_smoke.py`）

```python
@pytest.mark.e2e
async def test_lane_schema_is_migrated_and_seeded(e2e_client, e2e_seed):
    """隔离 schema 已 `alembic upgrade head` + 种子在位。
    ⇒ `GET /api/v1/projects/{project_id}` 返回 200 且项目名是种子那个。"""

@pytest.mark.e2e
async def test_lane_role_headers_map_to_seeded_users(e2e_client, e2e_seed, role_headers):
    """每个全局角色都能用自己的 token 读到种子项目（200）⇒ 角色矩阵与种子对齐。"""
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd pcs-backend && bash scripts/pytest_e2e.sh`
Expected: FAIL —— 车道脚本 / conftest 不存在

- [ ] **Step 3: 实现**

- `pytest_e2e.sh`：抄 `scripts/pytest_pg.sh` 的三道闸；**唯一差别** = `-m e2e` + 导出
  `DATABASE_URL` / `TEST_DATABASE_URL` 指向 `pcs_pgtest`（`PG_PORT` 默认 5433）
  ⇒ ⚠️ **不新建第四种「PG 车道」** —— 它是 E2E 专用入口，但**同一个库**。
- `tests/e2e/conftest.py`：
  - `e2e_schema`：**session 级**（一条车道一个 schema ⇒ 迁移只跑一次）
    ⇒ 用 `subprocess` 跑 `alembic upgrade head`，环境里的 `DATABASE_URL` 追加
    `?options=-csearch_path=<schema>`（⚠️ 与 `tests/api/v1/test_stream_batch_concurrency_pg.py` **同款**）
    ⇒ ⚠️ **`alembic` 的 `settings` 是 pydantic 缓存实例** ⇒ 子进程里**先设 `DATABASE_URL` 再导入**
  - `e2e_seed`：session 级 ⇒ 在 scoped URL 下跑 `scripts/seed_e2e_flows.py`（T2 才有 ⇒ **本 Task 先留桩**，
    冒烟用例改成断言「schema 在 + 表在」即可 ⇒ T2 落地后再补断言）
  - `e2e_client`：`create_app()` + `app.dependency_overrides[get_db]` 指向 scoped engine
  - `role_headers`：工厂 fixture ⇒ `role_headers("APPROVER")` ⇒ 找种子里的对应用户 ⇒ 造 token
- `pyproject.toml::markers` 加 `e2e: 全流程 E2E（隔离 schema · 真 PG）`

- [ ] **Step 4: 跑测试确认通过**

Run: `cd pcs-backend && bash scripts/pytest_e2e.sh`
Expected: PASS（2 passed）· **耗时 < 60 s**

- [ ] **Step 5: 提交**

```bash
git add pcs-backend/scripts/pytest_e2e.sh pcs-backend/tests/e2e/ pcs-backend/pyproject.toml
git commit -F <msgfile>   # 首行: feat(P10-B): E2E 车道（隔离 schema · 真 PG · 三道 fail-closed）
```

---

## Task T2：流程级种子（角色矩阵 · 起点态 · 幂等）

**Files:**
- Create: `pcs-backend/scripts/seed_e2e_flows.py`
- Create: `pcs-backend/tests/scripts/test_seed_e2e_flows.py`

**Interfaces:**
- Consumes: `app.models.*`（`Workspace` / `Project` / `User` / `UserProject` / `Stream` / `Deliverable` / `SignatureMatrix` / `ReportDefinition`）
- Produces:
  - `scripts/seed_e2e_flows.py` 暴露 **`async def seed_flows(db: AsyncSession, *, reset: bool = False) -> dict[str, int]`**
    ⇒ ⚠️ 必须有**可调用入口**（同 `seed_e2e_data.py::seed`）⇒ 单测能传 `db_session`
  - 返回值 = 各造了多少行（`users` / `user_projects` / `streams` / `deliverables` / `signature_matrices` / `report_definitions`）
  - **角色矩阵**（本 Task 的核心）：6 个用户，**全局角色**各不相同
    | username | 全局角色（JWT claim） | 项目内角色（`user_projects.role_in_project`） |
    |---|---|---|
    | `e2e-designer` | `DESIGNER` | `DESIGNER` |
    | `e2e-checker` | `CHECKER` | `CHECKER` |
    | `e2e-reviewer` | `REVIEWER` | `REVIEWER` |
    | `e2e-approver` | `APPROVER` | `APPROVER` |
    | `e2e-admin` | `SYSTEM_ADMIN` | `VIEWER` |
    | `e2e-outsider` | `DESIGNER` | ——（**不授权** ⇒ 跨项目 ⇒ 404） |
    ⚠️ **全局角色 ≠ 项目内角色** —— 状态机按**全局**判（`TRANSITION_ROLES`）·
    项目守卫按**项目内**判 ⇒ 两个维度都要有 ⇒ **不能**一个角色打天下。
  - ⚠️ **`User.roles` 写空数组**（同 `seed_e2e_data.py`）⇒ 真实登录会覆盖它 ⇒ **不影响鉴权**
    （ACL 权威 = JWT 的 role claim）
  - **起点态数据**（**只造起点** ⇒ 其余状态由场景走真实端点推进）：
    1 工作区（FORMAL）+ 1 项目（绑 `module='RECORD'` 签署矩阵）+ 6 用户 + 5 条 `UserProject`
    + 2 条物流（含组成/物性）+ 1 个 **DRAFT 记录**（`piping` 模块）+ 1 个 **DRAFT 交付物**
    + 1 个签署矩阵（3 级：CHECKER→REVIEWER→APPROVER）+ 1 个自定义报表定义

- [ ] **Step 1: 写失败的测试**（`tests/scripts/test_seed_e2e_flows.py`）

```python
async def test_seed_flows_is_idempotent(db_session):
    """跑两遍 ⇒ 各表行数**不涨**。"""

async def test_seed_flows_creates_one_user_per_global_role(db_session):
    """6 个用户 ⇒ 全局角色各不相同（DESIGNER/CHECKER/REVIEWER/APPROVER/SYSTEM_ADMIN ×2）。"""

async def test_seed_flows_grants_project_roles_except_the_outsider(db_session):
    """5 条 `UserProject` ⇒ 项目内角色各异；`e2e-outsider` **没有**授权行。"""

async def test_seed_flows_only_creates_starting_states(db_session):
    """记录 = DRAFT、交付物 = DRAFT ⇒ **没有**预置 CHECKED/IN_APPROVAL 之类
    ⇒ 状态必须由场景**走**出来（否则 E2E 只是断言一个摆好的状态）。"""
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd pcs-backend && uv run pytest tests/scripts/test_seed_e2e_flows.py -q`
Expected: FAIL —— 脚本不存在

- [ ] **Step 3: 实现**

- **照抄 `scripts/seed_e2e_data.py` 的 house 形状**：固定 UUID（`uuid5(NAMESPACE_DNS, ...)`）·
  `_get_or_create`（savepoint + 重读赢家）· `--reset` **只删自己造的**（按固定 UUID 列表）
- ⚠️ **不要**再写第二份 get-or-create ⇒ 复用 `seed_e2e_data.py` 里那份（**抽到共享模块**
  或直接 import）⇒ 两份种子 = 两个真相源 ⇒ 会漂
- ⚠️ **`UserProject.role_in_project` 只接受 6 个值** ⇒ 别写 `TEST_VIEWER`
- ⚠️ **删序遵守外键**：`UserProject` → `Deliverable` → `SignatureMatrix` → `Record` → `Stream` → `Project` → `Workspace` → `User`

- [ ] **Step 4: 跑测试确认通过**

Run: `cd pcs-backend && uv run pytest tests/scripts/test_seed_e2e_flows.py -q`
Expected: PASS（4 passed）

- [ ] **Step 5: 跑真 PG 幂等（一次）**

Run: `cd pcs-backend && bash scripts/pytest_e2e.sh`
Expected: PASS（车道冒烟 + 种子在真 PG 上幂等）

- [ ] **Step 6: 提交**

```bash
git add pcs-backend/scripts/seed_e2e_flows.py pcs-backend/tests/scripts/test_seed_e2e_flows.py
git commit -F <msgfile>   # 首行: feat(P10-B): 流程级种子（角色矩阵 + 起点态 · 幂等）
```

---

# 段二：场景

## Task T3：录入与计算链（E2E-001~006）

**Files:**
- Create: `pcs-backend/tests/e2e/test_e2e_project_config.py`
- Create: `pcs-backend/tests/e2e/test_e2e_sim_import.py`
- Create: `pcs-backend/tests/e2e/test_e2e_calc_chains.py`

**Interfaces:**
- Consumes: T1 的 `e2e_client` / `e2e_seed` / `role_headers`；T2 的种子 id
- Produces: 5 个场景的可复用 helper（放 `tests/e2e/helpers.py`）：
  - `async def post_calc(client, url, body, *, headers) -> dict` —— 统一「调计算端点 → 断言 200 → 返回结果体」
  - `async def make_record(client, *, module, payload, headers) -> uuid.UUID` —— 造一条 DRAFT 记录并返回 id

- [ ] **Step 1: 写失败的测试**

```python
# E2E-001
async def test_e2e_001_project_creation_generates_the_input_checklist(e2e_client, role_headers, e2e_seed):
    """POST /api/v1/projects ⇒ 201 ⇒ GET /api/v1/checklist/projects/{id}/completeness
    ⇒ 200 且清单**非空**（输入清单自动生成）。"""

# E2E-002
async def test_e2e_002_sim_import_creates_streams_and_completes_properties(e2e_client, role_headers):
    """POST /api/v1/imports（上传）⇒ GET /api/v1/imports/{id}/preview-streams
    ⇒ 物流数 > 0 ⇒ POST /api/v1/flash/calculate ⇒ 物性补全（有 mole/enthalpy 字段）。"""

# E2E-003
async def test_e2e_003_pipe_calc_chain_populates_the_pipe_class_table(e2e_client, role_headers, e2e_seed):
    """POST /api/v1/pipe/calc-chain ⇒ 200 ⇒ GET /api/v1/pipe-classes ⇒ 含本次的管段。"""

# E2E-004 / 005 / 006
async def test_e2e_004_pump_calc_chain_returns_a_pump_result(...)
async def test_e2e_005_psv_calculate_returns_the_relief_area(...)
async def test_e2e_006_vessel_calculate_returns_dimensions(...)
```

⚠️ **计算链的输入写在场景里**（与 `tests/api/v1/test_*_calc*.py` 的**合成输入同源**）
⇒ **不要**从 `sample/`（不入 git ⇒ 别的机器没有）取 ⇒ **不要**从种子灌输入
⇒ 种子只给项目 / 物流 / 角色。

- [ ] **Step 2: 跑测试确认失败**

Run: `cd pcs-backend && bash scripts/pytest_e2e.sh`
Expected: FAIL（场景未写 / 端点返回非预期）

- [ ] **Step 3: 实现场景**

- 每个场景 = **一串真实 API 调用**（不是直接写库）⇒ 断言落在**响应体**与**随后的 GET**
- ⚠️ **每条断言都要能区分「通过」与「假绿」**：断言具体字段值，**不是**「200 就好」
- ⚠️ **跨场景隔离**：每个场景用**自己的**项目/物流 ⇒ **不要**共用种子那一个 ⇒ 否则场景之间互相污染（顺序一换就飘）

- [ ] **Step 4: 跑测试确认通过**

Run: `cd pcs-backend && bash scripts/pytest_e2e.sh`
Expected: PASS（E2E-001~006 全绿）

- [ ] **Step 5: 提交**

```bash
git add pcs-backend/tests/e2e/
git commit -F <msgfile>   # 首行: test(P10-B): E2E-001~006 录入与计算链
```

---

## Task T4：汇总 · 报告 · 供应商（E2E-007/008/009/014/015）

**Files:**
- Create: `pcs-backend/tests/e2e/test_e2e_equipment_util.py`
- Create: `pcs-backend/tests/e2e/test_e2e_report.py`
- Create: `pcs-backend/tests/e2e/test_e2e_supplier.py`

**Interfaces:**
- Consumes: T3 的 `helpers.py`（造出来的记录 / 物流继续用）
- Produces: 无（纯场景）

- [ ] **Step 1: 写失败的测试**

```python
# E2E-007
async def test_e2e_007_equipment_list_contains_every_seeded_module(...)
    """GET /api/v1/equipment-list ⇒ 含设备 ⇒ 模块种类覆盖到种子的那几种。"""

# E2E-008
async def test_e2e_008_energy_summary_matches_the_input_items(...)
    """POST /api/v1/util/energy-summary/aggregate ⇒ 汇总值 = 各明细之和（**不是**「>0」）。"""

# E2E-009
async def test_e2e_009_report_generation_produces_a_hashed_report_file(...)
    """POST /api/v1/report/generate ⇒ GET /api/v1/report/{id}/status ⇒ 生成完成
    ⇒ GET /api/v1/report/{id}/hash ⇒ 有哈希 ⇒ GET .../download ⇒ 200。"""

# E2E-014
async def test_e2e_014_supplier_actual_value_updates_the_deviation_report(...)
    """录入实际值 ⇒ 偏差报告里出现偏差行 ⇒ 实际值状态变 CONFIRMED。"""

# E2E-015
async def test_e2e_015_custom_report_definition_executes_and_returns_data(...)
    """POST /api/v1/report-builder/definitions ⇒ publish ⇒ execute
    ⇒ GET /api/v1/report-builder/executions/{task_id} ⇒ 成功且数据非空。"""
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd pcs-backend && bash scripts/pytest_e2e.sh`
Expected: FAIL（场景未写 / 汇总值对不上）

- [ ] **Step 3: 实现场景**

- 汇总类场景（008/015）⇒ 断言**数值关系**（汇总 = 明细之和；报表数据行数 > 0）
  ⇒ **不是**「> 0」—— 那挡不住「算错但非零」
- 报告类场景（009）⇒ 走完 `generate → status → hash → download` **四步**
  ⇒ ⚠️ 生成是**异步**的 ⇒ `status` 要**轮询**（≤ 30 s）而不是查一次

- [ ] **Step 4: 跑测试确认通过**

Run: `cd pcs-backend && bash scripts/pytest_e2e.sh`
Expected: PASS（E2E-007/008/009/014/015 全绿）

- [ ] **Step 5: 提交**

```bash
git add pcs-backend/tests/e2e/
git commit -F <msgfile>   # 首行: test(P10-B): E2E-007/008/009/014/015 汇总·报告·供应商
```

---

## Task T5：记录层状态机 + 交付物 Rev（E2E-010~013 + WF-PATH）

**Files:**
- Create: `pcs-backend/tests/e2e/test_e2e_record_workflow.py`
- Create: `pcs-backend/tests/e2e/test_e2e_deliverable_rev.py`

**Interfaces:**
- Consumes: T2 的签署矩阵 + DRAFT 记录 + DRAFT 交付物；T3 的 `make_record`
- Produces: `helpers.py` 加 `async def advance_record(client, *, record_id, module, step, headers) -> dict`
  （走 `submit-approval` / `approval-step`）

- [ ] **Step 1: 写失败的测试**

```python
# WF-PATH-01A 正向 + E2E-010
async def test_wf_path_01a_forward_path_reaches_approved(...)
    """DRAFT → submit-approval → approval-step(CHECKER) → approval-step(REVIEWER)
    ⇒ approval-step(APPROVER) ⇒ 状态 = APPROVED/IN_APPROVAL（按矩阵第 3 级）
    ⇒ 且**每一步都要用对角色**（用错角色 ⇒ 403）。"""

# WF-PATH-01B 驳回
async def test_wf_path_01b_reject_returns_to_check_rejected_and_can_resubmit(...)

# WF-PATH-01C 变更闭环（★ Review Focus #1）
async def test_wf_path_01c_upstream_change_marks_downstream_stale_and_confirm_recalc(...)
    """上游记录改 ⇒ 下游记录变 STALE ⇒ confirm-recalc ⇒ 变 CHANGED 且哈希变了。"""

# WF-PATH-01D 撤销/反转
async def test_wf_path_01d_reversal_pending_then_decision_restores_the_record(...)

# WF-PATH-01E 废止
async def test_wf_path_01e_obsolete_is_terminal(...)

# WF-PATH-02 交付物 Rev + E2E-011
async def test_wf_path_02_issuing_a_new_rev_bumps_the_version(...)

# WF-PATH-03 变更单 / 代录 + E2E-012（★ Review Focus #2）
async def test_wf_path_03_proxy_customer_approval_records_who_recorded_it(...)
    """代录客户批准 ⇒ customer_approval_proxy_by = 代录人 id（**非空**）"""

# E2E-013 上游变更影响分析
async def test_e2e_013_change_impact_lists_downstream_records(...)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd pcs-backend && bash scripts/pytest_e2e.sh`
Expected: FAIL（状态机路径未走通）

- [ ] **Step 3: 实现场景**

- ⚠️ **每条路径都必须用「对的那一步的角色」** ⇒ 状态机的粗闸（`TRANSITION_ROLES`）
  **和**签署矩阵的细判据（`actor.role == record.approval_role`）**都要满足**
  ⇒ 路径用例要显式换 token（`role_headers("CHECKER")` → `role_headers("REVIEWER")` → …）
- ⚠️ **驳回路径（01B）**⇒ 驳回后状态 = `CHECK_REJECTED` ⇒ **能重新提交**（否则是死路）
- ⚠️ **变更闭环（01C）**⇒ 上游改动的**触发方式**要用**真实端点**
  （`initiate-change` / `apply-change`）⇒ 不是直接改库
- ⚠️ **交付物 Rev（02）**⇒ `issue` 之后 `versions` 里 **rev + 1** ⇒ 且旧 rev 的 snapshot 仍可读

- [ ] **Step 4: 跑测试确认通过**

Run: `cd pcs-backend && bash scripts/pytest_e2e.sh`
Expected: PASS（WF-PATH-01A~01E / 02 / 03 + E2E-010~013 全绿）

- [ ] **Step 5: 提交**

```bash
git add pcs-backend/tests/e2e/
git commit -F <msgfile>   # 首行: test(P10-B): WF-PATH 五类路径 + E2E-010~013
```

---

## Task T6：权限矩阵 + AI 审计 + schema 一致（E2E-016/017/018 + AUTH-E2E）

**Files:**
- Create: `pcs-backend/tests/e2e/test_e2e_permission_matrix.py`
- Create: `pcs-backend/tests/e2e/test_e2e_ai_audit.py`
- Create: `pcs-backend/tests/e2e/test_e2e_schema_parity.py`

**Interfaces:**
- Consumes: T2 的角色矩阵（T6 的全部输入）
- Produces: `tests/e2e/test_e2e_permission_matrix.py` 里一张**参数化表**（角色 × 操作 × 期望码）⇒
  加新用例只改表，不改逻辑

- [ ] **Step 1: 写失败的测试**

```python
# AUTH-E2E-01~10（参数化）
AUTH_MATRIX = [
    ("DESIGNER", "submit-approval", 200),    # AUTH-E2E-01
    ("CHECKER",  "submit-approval", 403),    # AUTH-E2E-02
    ("CHECKER",  "approval-step",   200),    # AUTH-E2E-03
    ("DESIGNER", "approval-step",   403),    # AUTH-E2E-04
    ("APPROVER", "approval-step",   200),    # AUTH-E2E-05
    ("DESIGNER", "approval-step",   403),    # AUTH-E2E-06
    ("SYSTEM_ADMIN", "audit-logs",  200),    # AUTH-E2E-07
    ("DESIGNER",     "audit-logs",  403),    # AUTH-E2E-08
    ("APPROVER", "proxy-approval",  200),    # AUTH-E2E-09
]

async def test_permission_matrix(...)
    """⚠️ 403 与 404 的**形状**要分开断言：越权（角色不对）⇒ 403；
    跨项目（角色对但没授权）⇒ **404**（与「不存在」同形 ⇒ 不泄露存在性）。"""

# E2E-016
async def test_e2e_016_cross_project_access_is_404_not_403(...)

# E2E-017（★ Review Focus #4）
async def test_e2e_017_ai_endpoint_returns_501_and_the_audit_row_is_persisted(...)
    """POST /api/v1/ai/intent ⇒ 501 + code=AI_NOT_IMPLEMENTED
    ⇒ **真 PG** 里 `ai_audit_log` 有一行（等 ARQ worker 落库 ⇒ 轮询 ≤10 s）"""

# E2E-018
async def test_e2e_018_pcs_and_pcs_test_schema_versions_match(...)
    """直查两库的 `alembic_version` ⇒ **相同**（CLAUDE.md 的两库口径）。"""

# WF-PATH-04 权限矩阵与签署矩阵一致性
async def test_wf_path_04_matrix_and_signature_matrix_agree(...)
    """⚠️ 权限矩阵（代码里的 `TRANSITION_ROLES` 粗闸）与**项目绑定的签署矩阵**
    （细判据）**不能打架** ⇒ 粗闸放行的角色在矩阵那一步也必须被允许
    ⇒ 否则出现「谁都能过粗闸、但矩阵这一步没人能签」的**死链**。"""
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd pcs-backend && bash scripts/pytest_e2e.sh`
Expected: FAIL（矩阵未跑 / 审计行未落）

- [ ] **Step 3: 实现场景**

- ⚠️ **403 与 404 分开断言**（Review Focus #3）：
  **角色不对**（同项目、有授权、但角色不够）⇒ **403**；
  **跨项目**（角色对、但**没授权行**）⇒ **404**（与「不存在」同形 ⇒ 不泄露存在性）
  ⇒ 这两件事**混成同一个码**就等于泄露了别人的资源存在性
- ⚠️ **E2E-017 不起 ARQ worker** ⇒ 直接调写库任务（`app.workers.ai_audit_tasks`）
  ⇒ 车道依赖更少（不引 Redis/worker）⇒ 断言「审计行**在真 PG 里**」而不是「入队了」
- ⚠️ **E2E-018** 直查两库 `alembic_version` ⇒ **不一致就登记**（本批不修）

- [ ] **Step 4: 跑测试确认通过**

Run: `cd pcs-backend && bash scripts/pytest_e2e.sh`
Expected: PASS（AUTH-E2E-01~10 + WF-PATH-04 + E2E-016/017/018 全绿）

- [ ] **Step 5: 提交**

```bash
git add pcs-backend/tests/e2e/
git commit -F <msgfile>   # 首行: test(P10-B): 权限矩阵 + E2E-016/017/018
```

---

# 段三：前端与收口

## Task T7：真后端通道的 UI 流（5 条）

**Files:**
- Create: `pcs-frontend/e2e/real_backend_flows.spec.ts`
- Modify: `pcs-backend/scripts/seed_e2e_flows.py`（若 UI 流需要额外起点态数据）

**Interfaces:**
- Consumes: 现成的 `real-backend` Playwright project（`reuseExistingServer: false` · 5174）·
  `fixtures.ts::realPage` · 后端连 `pcs_pgtest`（**被 seed 的那个库**）
- Produces: 无（纯场景）

- [ ] **Step 1: 写失败的 spec**

```ts
test('@real-backend 物流列表：种子物流可见', async ({ realPage }) => { ... });
test('@real-backend 记录详情：状态徽标与批准链可见', async ({ realPage }) => { ... });
test('@real-backend 交付物：Rev 列表可见', async ({ realPage }) => { ... });
test('@real-backend 设备表：种子设备可见', async ({ realPage }) => { ... });
test('@real-backend 权限：越权用户看不到别人的项目', async ({ realPage }) => { ... });
```

⚠️ **导航必须走 SPA 菜单点击**（`gotoViaMenu`）⇒ 整页刷新会清内存态 session ⇒ 弹回 `/login`
⚠️ **每个用例自己走 UI 登录**（token 只在 zustand 内存里 ⇒ 塞不进去）
⚠️ **真后端通道的后端必须带 `PCS_ENABLE_MOCK_LOGIN=true`** 且连 **`pcs_pgtest`**

- [ ] **Step 2: 跑测试确认失败**

Run: `cd pcs-frontend && npx playwright test --project=real-backend`
Expected: FAIL（spec 未写 / 数据未 seed）

- [ ] **Step 3: 实现 spec**（5 条，断言**具体行内容**，不是「页面没报错」）

- [ ] **Step 4: 跑测试确认通过**

Run: `cd pcs-frontend && npx playwright test --project=real-backend`
Expected: PASS（6 passed —— 5 条新 + P10-A 的冒烟 1 条）

- [ ] **Step 5: 提交**

```bash
git add pcs-frontend/e2e/real_backend_flows.spec.ts pcs-backend/scripts/seed_e2e_flows.py
git commit -F <msgfile>   # 首行: test(P10-B): 真后端通道的 5 条 UI 流
```

---

## Task T8：契约 / SPEC 偏离回写 / 账簿 / QA 收口

**Files:**
- Modify: `spec/PCS-SPEC-P10 V1.3.1 P10 AI预留与测试部署开发规格说明书.md`（第五部分「偏离登记」）
- Modify: `TODOS.md` · `.wolf/STATUS.md` · `.wolf/buglog.json`
- Create: `.gstack/qa-reports/qa-report-pcs-frontend-YYYY-MM-DD-p10b.md`（gitignored）

- [ ] **Step 1: 回写 SPEC 偏离登记**（新增 D23~D26）

| # | SPEC 原文 | 仓里实际 | 裁决 |
|---|---|---|---|
| **D23** | 权限矩阵用 `SYSADMIN` | 代码词表是 `SYSTEM_ADMIN`（`state_machine.TRANSITION_ROLES`） | **以代码为准** ⇒ SPEC 词表订正 |
| **D24** | AUTH-E2E-11/12（`TEST_VIEWER` 看测试报告页） | `TEST_VIEWER` **不存在**（项目内角色 6 值里没有）· 测试报告页属 **P10-C** | **本批不做** ⇒ 角色登记随 P10-C 一并做 |
| **D25** | 「E2E 在 CI 中可自动执行」+「PR 跑关键 E2E；nightly 跑全量 E2E」 | 既有裁决「**不新建 CI 流水线**」 | **本批只给本地车道脚本**（`scripts/pytest_e2e.sh` 跑全量）⇒ 「进 CI」与「PR/nightly 拆分」两项验收**一并延到 P10-F**（生产就绪评审）裁决 ⇒ **本批不假装满足** |
| **D26** | 18 场景「全部通过」 | 本批：后端 18 条 + 前端 5 条 UI 流（UI 不重复覆盖 18 条） | **后端为权威覆盖**，前端是**抽样 UI 复验** |

- [ ] **Step 2: 跑批末闸门**

```bash
cd pcs-backend && uv run pytest                    # 全量（新增 e2e 用例默认跳过）
cd pcs-backend && bash scripts/pytest_pg.sh        # PG 车道
cd pcs-backend && bash scripts/pytest_e2e.sh       # E2E 车道
cd pcs-backend && uv run python scripts/check_openapi_payload_coverage.py
bash pcs-backend/scripts/gate_08_openapi_contract.sh --check-baseline
cd pcs-frontend && npm run typecheck && npm run lint && npm run test
cd pcs-frontend && npx playwright test --project=chromium   # mock 通道不许回归
```
Expected: 全绿；**裸载荷 ≤ 71**；E2E 车道 ≥ **18 passed**

- [ ] **Step 3: 写账簿**

- `TODOS.md`：新增条目（**AUTH-E2E-11/12 延到 P10-C** · **E2E 进 CI 延到 P10-F** ·
  **TODO-141 strict_client 迁移进度**（本批只迁新写的用例 ⇒ 原 TODO 保留））
- `.wolf/STATUS.md`：续写新一轮（**保持 < 2k token**）
- `.wolf/buglog.json`：本批修的 bug 各补一条（**`fix_commit` 必填**）

- [ ] **Step 4: 浏览器回归（gstack-qa）**

- vite dev :5173 · 36 条路由可达 · 0 console error · 0×404/500
- 报告落 `.gstack/qa-reports/qa-report-pcs-frontend-2026-11-13-p10b.md`
- **CRITICAL / HIGH 必修完**才能开下一批

- [ ] **Step 5: 提交**

```bash
git add -A
git commit -F <msgfile>   # 首行: docs(P10-B): 偏离登记 + 账簿 + QA 收口
```

---

## 验收

| 门 | 判据 |
|---|---|
| **E2E-001~018** | 18 条后端 E2E **全部通过**（`bash scripts/pytest_e2e.sh` ⇒ **≥ 18 passed**） |
| **WF-PATH** | 五类路径（01A~01E / 02 / 03 / 04）**全覆盖** ⇒ 01A~01E/02/03 在 T5；**04（权限一致性）** 在 T6（矩阵 × 签署矩阵一致性） |
| **权限矩阵** | AUTH-E2E-01~10 全过；**AUTH-E2E-11/12 延到 P10-C**（D24） |
| **前端** | 真后端通道 **6 passed**（5 新 + 1 冒烟）· mock 通道 **23 passed**（不许回归） |
| **回归** | 后端全量 / PG 车道 / 裸载荷 71 / G-08 4/4 全绿 |
| **浏览器** | gstack-qa 回归 0 CRITICAL / 0 HIGH |
| **迁移** | 本批**未改** `alembic/versions/*` ⇒ 无漂移风险 |
| **账簿** | `STATUS.md` + `TODOS.md` + `buglog.json` 更新 |

---

## 尚未解决的问题（开工前需裁决或登记）

| # | 问题 | 现状 | 归属 |
|---|---|---|---|
| 1 | **AUTH-E2E-11/12（`TEST_VIEWER` + 测试报告页）** | 角色不存在 · 页面属 P10-C | **本批不做**（D24）⇒ 登记 TODO ⇒ P10-C 一并做 |
| 2 | **「E2E 在 CI 中可自动执行」** | 与「不新建 CI 流水线」的既有裁决冲突 | **本批只给本地车道**（D25）⇒ P10-F 裁决 |
| 3 | **SPEC 的 `SYSADMIN` vs 代码的 `SYSTEM_ADMIN`** | 词表不一致 | 本批按代码写并登记（D23）⇒ 建议把 SPEC 词表订正 |
| 4 | **E2E 车道与 PG 车道同库（`pcs_pgtest`）** | E2E 用**隔离 schema** ⇒ 不碰 public schema ⇒ 可同库 | 无需裁决（已定） |
| 5 | **ARQ worker 在 E2E 里要不要起** | 审计落库是异步的 | 本批**不起 worker** ⇒ 直接调写库任务 ⇒ 车道依赖更少（已定） |
| 6 | **E2E-018 的两库口径** | SPEC 写 `pcs` 与 `pcs_test`；本机 `pcs_test` 存在 | 本批直查两库 `alembic_version` ⇒ 不一致就**登记**（不修） |
| 7 | **TODO-141（全量测试迁 `strict_client`）** | 本批只迁**新写的**用例 | 原 TODO **保留** ⇒ 迁完才是「关闭」 |
| 8 | **计算链输入用合成数据（不取 `sample/`）** | `sample/` 不入 git ⇒ 别的机器没有 ⇒ 车道不可移植 | 本批用合成输入（已定）⇒ 真 PRO/II 回归另由 SIM 解析测试承担 |
