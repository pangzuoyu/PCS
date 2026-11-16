# P10-B 实施计划：全流程 E2E（10.2）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 SPEC §3.2.2 的 **18 个 E2E 场景**（E2E-001~018）+ **SUP-007 两层状态机五类路径**（WF-PATH-01A~01E / 02 / 03 / 04）+ **权限矩阵**（AUTH-E2E-01~12）在**真 PG + 真后端**上跑起来。

**Architecture:** **两条腿** —— ① **后端全流程 E2E**（pytest + httpx + **隔离 schema 的真 PG**）覆盖 18 场景的主体（数据流、状态机、权限）；② **前端真后端通道**（Playwright `real-backend`）覆盖 **5 条用户看得见的 UI 流**。两条腿共用**同一份流程级种子**（`scripts/seed_e2e_flows.py`），种子只造**起点态**（项目 + 角色矩阵 + 物流 + 签署矩阵 + 交付物）⇒ **每个状态都由场景自己走真实端点推进**（不是「摆」一个已存在的状态来断言）。

**Tech Stack:** FastAPI · SQLAlchemy 2.x async · alembic · pytest（asyncio_mode=auto）· Playwright · React 19 + antd 5

**Spec:** `spec/PCS-SPEC-P10 V1.3.1 P10 AI预留与测试部署开发规格说明书.md` §3.2.2（10.2）· 批次顺序见 `docs/superpowers/plans/2026-11-04-p10-master-plan.md` §二 · 前批（10.0/10.1）见 `docs/superpowers/plans/2026-11-04-p10-batch-a-preflight-ai-reserve.md`

---

## 执行前置（开工第一步 · 不是可选项）

- [ ] **逐条核对「事实基础」表（23 行）** —— 2026-11-16 自查发现**计划的 20 行事实基础里
  有 4 行是错的**（折标煤表名 · E2E-002 端点 · E2E-001 清单 · E2E-018 的进程口径）
  ⇒ **事实基础不是「已核验的真相」，是「写计划时的快照」** ⇒ 开工前逐行重核
  ⇒ 每行核到**当前**的源码/库 ⇒ 与计划不符就**改计划**（不是改实现去迁就计划）。
- [ ] **hermes 的 11 条发现已折进本计划**（2026-11-16）⇒ 逐条对照「hermes 第三视角」章节
  ⇒ 确认每条都有落点（改计划 / 登记偏离 / 进 TODO）⇒ **不许「看到了但没处理」**。

---

## Global Constraints

- **分支 `main`，不要建 worktree**；**conventional commits**；长消息写文件后 `git commit -F <file>`。
- ⚠️ **口令不要写在命令行**（只在环境变量 / 进程内派生）；⚠️ **不要用 `git checkout <commit> --detach`**。
- ⚠️ **本批不新建 CI 流水线**（既有裁决）⇒ SPEC 的「E2E 在 CI 中可自动执行」**本批不满足** ⇒ 登记偏离（见 T8）。
- ⚠️ **本批不改 `alembic/versions/*`**（种子只造数据，不改 schema）⇒ 无迁移漂移风险 ⇒ 不跑 `alembic check`。
- ⚠️ **E2E 跑在隔离 schema**（沿用 `tests/api/v1/test_stream_batch_concurrency_pg.py` 的形状）⇒ **开发库 public schema 一个字节不动** ⇒ **不许**直接往 `pcs` / `pcs_test` 写 E2E 数据。
- ⚠️ **PG 车道唯一入口仍是 `scripts/pytest_pg.sh`** ⇒ E2E 是**另一条车道**（`scripts/pytest_e2e.sh`）⇒ 不许把 `-m e2e` 混进 PG 车道。
  ⇒ ⚠️ **两条车道不要同时跑**：它们在**同一个库**（`pcs_pgtest`）里各自建**隔离 schema**
  ⇒ 并发 DDL 会互相等锁 ⇒ 表现是「偶发卡住」而不是报错 ⇒ **串行跑**。
  ⇒ ⚠️ **「串行跑」必须有机制，不能只是一句叮嘱**（2026-11-16 · hermes P3-11）：
  `scripts/pytest_e2e.sh` 与 `scripts/pytest_pg.sh` **各自**用 `flock` 抢同一把锁
  （`/tmp/pcs-pgtest-lane.lock` · `flock -n` ⇒ 抢不到就**非零退出**并说清「另一条车道在跑」）
  ⇒ 零新依赖（`flock` 是 util-linux 自带）⇒ 「偶发卡住」这条失败模式被**机制化挡住**。
- ⚠️ **默认车道（`uv run pytest`）必须跳过 `e2e` 用例**（2026-11-16 · hermes P0-2）：
  `pyproject.toml` 的 `addopts` 只有 `-m 'not visual'` ⇒ **没有**任何东西排除 `e2e`
  ⇒ 不加闸门的话 `uv run pytest` 会**在开发库 `pcs` 上**建隔离 schema + 跑 `alembic upgrade head`
  ⇒ 批末「全量跑一次」就变成**误伤开发库** ⇒ **必须**在 `tests/e2e_flows/conftest.py` 里
  加 `pytest_collection_modifyitems` 闸门：**没有 `PCS_E2E_LANE=1` ⇒ 全部 skip**。
- ⚠️ **E2E 车道放 `tests/e2e_flows/`（新目录），不是 `tests/e2e/`**（2026-11-16 · hermes P1-5）：
  `tests/e2e/` **已被占用**（`test_sim_three_entry_consistency.py` · 12 条 `@pytest.mark.asyncio`
  · **无 skip** ⇒ 平时真跑）⇒ 在那儿放新 `conftest.py` ⇒ 它的 autouse/skip 逻辑会
  **连带改掉那 12 条既有用例的行为** ⇒ **换到兄弟目录 `tests/e2e_flows/`** ⇒
  既有用例**一个字节都不动**。
  ⇒ ⚠️ **E2E 车道内部也串行**（2026-11-13 · /plan-eng-review D10）：**不装 pytest-xdist**
  ⇒ 零新依赖 + 零 DDL 锁竞争；场景变多时用 `pytest -m e2e -k <域>` 分批（零依赖）。
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
| **折标煤系数表 = `config_energy_conversion_factors`** | ⚠️ **不是** `pcs_toe_conversion_factors`（那是**吨油当量 TOE** 表，另一回事）· 表由迁移 `p7_open_009_t0` 建 · **4 个 R1 分类列**由 `p7_s3_003_energy_config_classification_cols.py` 补（**bug-137 已修**）· **系数行**由 `p7_s3_004_energy_config_gb30251_a1.py` **INSERT** ⇒ ⇒ **迁移链就位 ⇒ E2E-008 的折标项不缺** ⇒ 实测 `pcs_pgtest` 有 **7 行** |
| `submit-approval` 的 403 是**自审闸**不是「角色不够」 | `app/api/v1/records_actions.py:596-604`：粗闸 `require_roles(SUBMIT_FOR_CHECK={DESIGNER,CHECKER,APPROVER,SYSTEM_ADMIN})` **放行 CHECKER** ⇒ 接着 `if actor.role in {s.sign_role for s in steps}` ⇒ **403 `APPROVAL_SELF_REVIEW_FORBIDDEN`** ⇒ AUTH-E2E-02 的 403 **必须钉住错误码**（只断状态码 ⇒ 换个原因也照样绿） |
| 9 态里**没有 `APPROVED`** | `app/models/enums.py::RecordSignStatus9` = DRAFT/IN_APPROVAL/CHECKED/CHECK_REJECTED/STALE/CHANGE_PENDING/CHANGED/REVERSAL_PENDING/OBSOLETE ⇒ 3 级链走完落在 **`CHECKED`** ⇒ 断 `APPROVED` ⇒ 字段不存在 ⇒ 断言必飘 |
| 报告端点**依赖 Redis + ARQ worker**，且**队列不可达时当场 503**（不是 202） | `app/api/v1/report.py:178` `create_pool(RedisSettings.from_dsn(...))` ⇒ Redis 不可达 ⇒ **抛 503 `REPORT_QUEUE_UNAVAILABLE`**（`report.py:196-207`）⇒ 那行被就地标 **FAILED**（不留孤儿 PENDING）· `app/api/v1/report_builder.py:409` `arq_queue.enqueue_definition_execution` ⇒ 同样**抛 503**（`report_builder.py:417-432` 改判 FAILED 后 re-raise）⇒ ⇒ **无 Redis 时「先 POST 拿 id 再轮询」根本走不通** |
| 全局角色的**白名单**在 `app/api/v1/config.py:542` | `_ALLOWED_ROLES` = {DESIGNER, PROCESS_CONTROLLER, REVIEWER, APPROVER, SYSTEM_ADMIN, VIEWER, CHECKER} ⇒ ⚠️ **不是** `app/core/config.py`（那个文件只有 309 行）⇒ `role_headers` 的角色词必须在这个集合里 |
| `tests/e2e/` **已被占用** | `tests/e2e/test_sim_three_entry_consistency.py`（18.7 KB · 12 条 `@pytest.mark.asyncio` · **无 skip**）⇒ 新车道放那儿会改到既有用例 ⇒ 搬 `tests/e2e_flows/` |
| mock 登录只有 **4 个**用户名 | `app/api/v1/mock_auth.py::MOCK_USERS` = alice(DESIGNER)/bob(CHECKER)/carol(APPROVER)/dan(SYSTEM_ADMIN) ⇒ T7 的 UI 流**只能**用这 4 个登录 ⇒ 种子里的 `e2e-*` 用户**登不进去** |
| 三库都在 **`p10_001`** | 2026-11-16 直查：`pcs`(5432) / `pcs_test`(5432) / `pcs_pgtest`(5433) 三者 `alembic_version` **都是 `p10_001`** ⇒ E2E-018 的「两库一致」今天成立 ⇒ 它防的是**漂移**不是现状 |
| **计算链的输入物流必须 `CHECKED`** | `app/services/calc_entry.py::check_calc_inputs` ⇒ 输入物流 `sign_status != CHECKED` ⇒ **403 `STREAM_NOT_CHECKED`** ⇒ ⇒ 种子里的源物流必须是 **CHECKED**（**不是** DRAFT）⇒ ⚠️ 「只造起点态」不冲突：物流是计算链的**输入**，**CHECKED 就是它的起点**；要「走」状态的是**记录**（T5 各自造 DRAFT 记录） |
| **SQLite 不强制 FK** ⇒ 外键目标缺失**只在真 PG 上炸** | `piping_results.material_class` → `pipe_classes.class_id` ⇒ 种子漏造那条管级 ⇒ 单测（内存 SQLite）**全绿** ⇒ 真 PG 插记录撞 FK ⇒ ⇒ 这条必须由 **PG 车道**兜住，且**快车道里也要钉一条**（「那个 FK 目标存在」） |

---

## 车道架构（一张图看懂两条腿）

```
                      ┌─────────────────────────────┐
                      │  pcs_pgtest（同一个库）        │
                      └──────────────┬──────────────┘
                                     │
        ┌────────────────────────────┴────────────────────────────┐
        │                                                          │
   隔离 schema A                                            隔离 schema B
   （E2E 车道 · session 级）                                  （PG 车道 · 每文件一个）
        │                                                          │
   ┌────┴─────┐   alembic upgrade head                    ┌─────┴─────┐
   │ 种子数据  │   （每次跑一次 · 末尾 DROP CASCADE）        │ 隔离 schema│
   │ flows 种子│                                            │  自己的    │
   │ + 系数表  │                                            │  迁移产物  │
   └────┬─────┘                                            └───────────┘
        │
   ┌────┴──────────────────────┐
   │ tests/e2e_flows/（18 场景）     │
   │  conftest: e2e_client      │
   │   = create_app()          │  ← 真中间件链（审计/trace/CORS）
   │   + get_db 覆盖 → schema A │
   └───────────┬───────────────┘
               │
        ┌──────┴───────┐
        │ 真 PG 真调用  │  ← 角色矩阵：6 用户 × 全局角色 × 项目内角色
        └──────────────┘

  ⚠️ public schema：**E2E 车道不写**（有测试钉着）
     ⇒ 但**真后端 Playwright 通道连的就是 public**
     ⇒ 所以 flows 种子**也要在 public 跑一遍**（D3）⇒ UI 流才有数据
     ⇒ ⚠️ **但 PG 车道的守卫会写 public**（`tests/scripts/test_compose_test_stack_pg.py`
        的 seed 跑在**没有 search_path 覆盖**的 URL 上 ⇒ 落 public）
        ⇒ ⇒ **「两条车道互不影响」这句要改口径**（2026-11-16 · hermes 事实 #15）
```

---

## What already exists（复用清单 —— 不重建）

| 子问题 | 仓里已有的 | 本计划怎么用 |
|---|---|---|
| 真 PG 上跑测试 | `scripts/pytest_pg.sh`（三道 fail-closed 闸门 · marker 已参数化） | **薄封装复用**（D5）⇒ 闸门**单一真相源**，不改原脚本 |
| 隔离 schema | `tests/api/v1/test_stream_batch_concurrency_pg.py` 的形状（`options=-csearch_path=` + `DROP SCHEMA CASCADE`） | **照抄形状** ⇒ 不发明第四种隔离法 |
| 幂等种子 + get-or-create | `scripts/seed_e2e_data.py` + `docs/solutions/database-issues/get-or-create-default-row-race-savepoint-reread.md` | **抽共享 helper** ⇒ 两个种子不各写一份（D8 的同款原则） |
| 真后端 Playwright 通道 | `pcs-frontend/playwright.config.ts` 的 `real-backend` project（5174 · 不复用已有 server）+ `fixtures.ts::realPage` | **直接用** ⇒ T7 只写 spec |
| SPA 导航 helper | `fixtures.ts::gotoViaMenu` | **直接用** ⇒ 整页刷新会清内存态 session ⇒ 弹回 `/login` |
| 真后端通道的冒烟 | `pcs-frontend/e2e/real_backend_smoke.spec.ts`（读种子项目必须 200） | 保留 ⇒ T7 在它旁边加 5 条 |
| 角色矩阵的**全局**角色 | `app/services/state_machine.py::TRANSITION_ROLES`（5 值） | 种子按它铺 ⇒ 状态机路径用得到真角色 |
| 记录模块名 | `app/services/calc_lineage.py::RECORD_TYPE_REGISTRY`（**键即 `{module}`**） | 用 `PipingResult` ⇒ 不用自造模块名 |
| 9 态记录 + 签署矩阵 | `RecordSignStatus9` + `app/api/v1/records_actions.py`（矩阵是项目绑定的） | 种子造**起点态** ⇒ 其余由场景走真实端点 |
| 折标系数表 + 系统参数 | `app/main.py` lifespan 里 seed 的两张表 | E2E 车道**显式补**（D4）⇒ 不跑整个 lifespan |

## NOT in scope（**想过但明确不做**）

| 项 | 为什么不做 |
|---|---|
| **AUTH-E2E-11/12（`TEST_VIEWER`）** | 角色**不存在**（要新增第 7 个）+ 测试报告页属 **P10-C** ⇒ 提前建页会返工 ⇒ **TODO-153** |
| **E2E 进 CI / PR-nightly 拆分** | 与「不新建 CI 流水线」的既有裁决冲突 ⇒ **TODO-152**（P10-F 裁决） |
| **AI 审计的「真链路」（带 worker）** | 要起 Redis + worker ⇒ 车道变重 ⇒ 本批用**两段式**（D6）⇒ **TODO-155** |
| **计算链的**数值**断言** | 算法由单测覆盖 ⇒ E2E 重复 = 两套断言漂移 ⇒ **薄壳**（D2） |
| **`sample/` 的真实 PRO/II 工程做输入** | `sample/` **不入 git** ⇒ 别的机器没有 ⇒ 车道不可移植 ⇒ 用合成输入（与现有单测同源） |
| **迁移 / 改 `alembic/versions/*`** | 本批只造数据不改 schema ⇒ 无漂移风险 ⇒ **不跑** `alembic check` |
| **端点契约改动**（新增字段 / 改响应） | 本批只**读**已有端点 ⇒ 契约零变更 ⇒ 裸载荷基线 71 不动 |
| **前端 `strict_client` 全量迁移**（TODO-141） | 那是**另一条**技术债（原 TODO 保留）⇒ 本批的 E2E 客户端走**真 app + 真守卫** ⇒ 本就比 strict_client 更严 |
| **把 E2E 车道并进 PG 车道** | 两条车道的**库/schema/生命周期**不同 ⇒ 混在一起会让 PG 车道变慢、且两边的失败信号混在一起 ⇒ 独立入口 + 共享闸门（D5） |
| **pytest-xdist 并行** | 零新依赖 + 零 DDL 锁竞争（D10）⇒ 场景变多时用 `-k` 分批 |

---

## 文件结构

| 文件 | 责任 |
|---|---|
| `pcs-backend/scripts/pytest_e2e.sh` | **新建** · E2E 车道的唯一入口（三道 fail-closed） |
| `pcs-backend/scripts/seed_e2e_flows.py` | **新建** · 流程级种子（角色矩阵 + 起点态数据，幂等） |
| `pcs-backend/tests/scripts/test_seed_e2e_flows.py` | **新建** · 种子的幂等 + 角色矩阵 + reset 安全守卫 |
| `pcs-backend/tests/scripts/test_pytest_e2e_gate.py` | **新建** · E2E 车道入口的守卫（不复制闸门 + 确实委派） |
| `pcs-backend/tests/e2e_flows/conftest.py` | **新建** · 隔离 schema + 种子 + `e2e_client` + 角色 token |
| `pcs-backend/tests/e2e_flows/helpers.py` | **新建** · 场景共用的调用helper（造记录 / 调计算端点 / 推状态机） |
| `pcs-backend/tests/e2e_flows/test_lane_smoke.py` | **新建** · 车道自检（schema 已迁移 + 种子在位 + 角色 token 对得上） |
| `pcs-backend/tests/e2e_flows/test_e2e_project_config.py` | **新建** · E2E-001（项目 → BEDD → 输入清单） |
| `pcs-backend/tests/e2e_flows/test_e2e_sim_import.py` | **新建** · E2E-002（SIM 导入 → 物流验证） |
| `pcs-backend/tests/e2e_flows/test_e2e_calc_chains.py` | **新建** · E2E-003/004/005/006（管道/泵/安全阀/容器） |
| `pcs-backend/tests/e2e_flows/test_e2e_equipment_util.py` | **新建** · E2E-007/008（设备表 · 能耗汇总） |
| `pcs-backend/tests/e2e_flows/test_e2e_report.py` | **新建** · E2E-009/015（计算书 · 自定义报表） |
| `pcs-backend/tests/e2e_flows/test_e2e_supplier.py` | **新建** · E2E-014（供应商实际值 → 偏差报告） |
| `pcs-backend/tests/e2e_flows/test_e2e_record_workflow.py` | **新建** · E2E-010 + WF-PATH-01A~01E |
| `pcs-backend/tests/e2e_flows/test_e2e_deliverable_rev.py` | **新建** · E2E-011/012 + WF-PATH-02/03 |
| `pcs-backend/tests/e2e_flows/test_e2e_permission_matrix.py` | **新建** · E2E-016 + AUTH-E2E-01~10（**11/12 不做** ⇒ D24） |
| `pcs-backend/tests/e2e_flows/test_e2e_ai_audit.py` | **新建** · E2E-017（501 + 审计落库） |
| `pcs-backend/tests/e2e_flows/test_e2e_schema_parity.py` | **新建** · E2E-018（两库 schema 版本一致） |
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

## Task 1（T1）：E2E 车道 + 隔离 schema + `e2e_client`

**Files:**
- Create: `pcs-backend/scripts/pytest_e2e.sh`
- Create: `pcs-backend/tests/scripts/test_pytest_e2e_gate.py`（照 `test_pytest_pg_gate.py` 的形状）
- Create: `pcs-backend/tests/e2e_flows/conftest.py`
- Create: `pcs-backend/tests/e2e_flows/test_lane_smoke.py`
- Modify: `pcs-backend/pyproject.toml`（`markers` 加 `e2e`）

**Interfaces:**
- Produces:
  - `scripts/pytest_e2e.sh` —— E2E 车道唯一入口。
    ⚠️ **薄封装**（2026-11-13 · /plan-eng-review D5）：**不复制** `scripts/pytest_pg.sh`
    的三道 fail-closed 闸门（复制 = 两份真相源 ⇒ 漂移）⇒ 只做三件事：
    ① `export PG_PYTEST_MARK=e2e`（`pytest_pg.sh` 的 marker **已经参数化**）
    ② `export PCS_E2E_LANE=1`（**默认车道的 skip 闸门靠它放行** ⇒ 见下面「`e2e` marker 闸门」）
    ③ `exec bash scripts/pytest_pg.sh`
    ⇒ 闸门逻辑**单一真相源** ⇒ 以后改闸门只改一处 ⇒ 两条车道同时生效。
    ⚠️ **不**改 `pytest_pg.sh` 本身（它在 CI 与文档里已被引用 ⇒ 零回归风险）。
    ⚠️ **不要在薄封装里导 `DATABASE_URL` / `TEST_DATABASE_URL`**（2026-11-16 · hermes 裁决 #5）：
    `scripts/pytest_pg.sh:50-51` **无条件**覆写这两个变量 ⇒ 薄封装里再导一次是**死代码**
    ⇒ 删掉（否则以后有人以为「改薄封装就能换库」⇒ 改了没效果 ⇒ 排查半天）。
    ⚠️ **`flock` 串行**（2026-11-16 · hermes P3-11）：薄封装与 `pytest_pg.sh` **各抢一把**
    `/tmp/pcs-pgtest-lane.lock`（`flock -n` ⇒ 抢不到 ⇒ **非零退出**并说清「另一条车道在跑」）
    ⇒ 零新依赖（`flock` 是 util-linux 自带）⇒ 把「两条车道并发 ⇒ DDL 等锁 ⇒ 偶发卡住」
    这条失败模式从「口头叮嘱」变成**机制**。
  - `tests/e2e_flows/conftest.py` 的四个 fixture：
    | fixture | 作用域 | 产出 |
    |---|---|---|
    | `e2e_schema` | session | 隔离 schema 名（`e2e_<8hex>`）；**起手** `DROP SCHEMA IF EXISTS … CASCADE`（2026-11-16 · hermes 交付风险 7：上次 DROP 失败留下的残留 ⇒ 下次跑「schema 已存在」直接炸）→ 建 schema → `alembic upgrade head`（`options=-csearch_path=`）→ 测完 `DROP SCHEMA … CASCADE` |
    | `e2e_seed` | session | 跑 `scripts/seed_e2e_flows.py` 后的**种子 id 字典**（`project_id` / `workspace_id` / `stream_ids` / `users` / `matrix_id` / `deliverable_id` / `report_def_id`）⇒ **id 来自 `seed_e2e_flows` 的模块级常量**（不另造真相源）<br>⚠️ **还要补两处「只有 lifespan 才会做」的 seed**（2026-11-13 · /plan-eng-review D4 · **2026-11-16 复核后修正**）：`e2e_client` 走 ASGITransport ⇒ **不跑 lifespan** ⇒ ① **CATEGORY_3 系数表的默认行**（`app/services/coefficient_service.py::CoefficientService.seed_default_tables`）② **系统参数默认**（`app/services/system_setting_service.py::seed_defaults` —— ⚠️ **不是** `seed_system_setting_defaults`，**这个名字不存在**）⇒ 缺了 ⇒ **记录编辑锁**（`edit_lock.ttl_minutes` / `edit_lock.renew_enabled`）与**兼任校核**（`record.self_check_allowed`）走兜底默认值 ⇒ 与生产不一致 ⇒ fixture 里**显式**调这两个（**不**引 asgi-lifespan、**不**跑整个 lifespan ⇒ 不碰 Redis / 关连接）<br>⚠️ **别搞混三张「系数表」**（2026-11-16 复核更正，原文写错了）：**折标煤系数**读的是 **`config_energy_conversion_factors`**（`ToeConversionService` 那张是**吨油当量 TOE**，**另一回事**）⇒ 而折标系数**行由迁移种**（`p7_s3_004_energy_config_gb30251_a1.py` 的 INSERT）⇒ ⇒ **E2E-008 的折标项不缺**（实测 `pcs_pgtest` 有 **7 行**）⇒ 真正要补的只有上面 ①②<br>⚠️ **4 个 R1 分类列**（`value_type` / `sub_type` / `pressure_level` / `water_type`）由 `p7_s3_003_energy_config_classification_cols.py` 补 ⇒ **bug-137 已修** ⇒ 新 schema 无漂移 |
    | `e2e_client` | function | `httpx.AsyncClient`，**真 app**（`create_app()` ⇒ 真中间件链）+ `get_db` 覆盖到隔离 schema 的 engine ⇒ 支持 `await e2e_client.post(...)` |
    | `role_headers` | function | `role_headers("DESIGNER")` ⇒ `{"Authorization": "Bearer <token>"}`（`create_access_token(subject=<username>, role=<role>)` ⇒ `sub` 必须是 **username** ⇒ actor 的 `user_id` 派生才对得上）<br>⚠️ **映射规则必须唯一**（2026-11-13 · /plan-eng-review D9）：种子里有**两个**全局角色是 `DESIGNER` 的用户（`e2e-designer` 有授权 / `e2e-outsider` **故意没授权**）⇒ `role_headers(<role>)` 一律解析到**有授权的**那个人；**局外人必须显式点名**：`role_headers(username="e2e-outsider")` ⇒ 否则正常场景会拿到局外人的 token ⇒ **全部变 404**（看起来像「端点坏了」）<br>⚠️ **角色词必须过白名单**（2026-11-16 · hermes 交付风险 8）：`app/api/v1/config.py:542` 的 `_ALLOWED_ROLES` = {DESIGNER, PROCESS_CONTROLLER, REVIEWER, APPROVER, SYSTEM_ADMIN, VIEWER, CHECKER} ⇒ 工厂里 **assert 角色在这个集合里** ⇒ 报错优于「发一个非法角色的 token ⇒ 全场 403」<br>⚠️ **只解析 `e2e-*` 用户**（2026-11-16 · hermes P1-4 的推论）：种子新增了 `alice`（给 UI 通道用）⇒ 她的全局角色也是 `DESIGNER` ⇒ `role_headers("DESIGNER")` **必须解析到 `e2e-designer`** ⇒ 否则后端场景拿到 alice 的 token（而 alice 的授权行只给 UI 流用） |
  - ⚠️ **`e2e_client` 不用 `strict_client` 那套最小 app** —— E2E 要**真中间件链**（审计 / trace / CORS）⇒ 用 `create_app()`（同 P10-A 的 `ai_client` 形状）
  - ⚠️ **`e2e` marker 闸门**（2026-11-16 · hermes P0-2 · **本批最危险的一条**）：
    `tests/e2e_flows/conftest.py` 里加 `pytest_collection_modifyitems` ⇒
    **没有 `PCS_E2E_LANE=1` ⇒ 全部 `e2e` 用例 skip**
    ⇒ ⚠️ **为什么必须有**：`pyproject.toml` 的 `addopts` 只有 `-m 'not visual'`
    ⇒ 仓里**没有任何**东西排除 `e2e` ⇒ 不加这闸门，`uv run pytest`（批末必跑的那条）
    会把 E2E 场景**跑到开发库 `pcs` 上** ⇒ 建隔离 schema + 跑 `alembic upgrade head`
    ⇒ **误伤开发库** ⇒ 而症状是「跑得挺快、全绿」⇒ **没人发现**。
    ⇒ 闸门放**新目录**（`tests/e2e_flows/`）⇒ `tests/e2e/` 那 12 条既有用例**不受影响**。

- [ ] **Step 1: 写失败的测试**（`tests/e2e_flows/test_lane_smoke.py`）

```python
# tests/e2e_flows/test_lane_smoke.py
@pytest.mark.e2e
async def test_lane_schema_is_migrated_and_seeded(e2e_client, e2e_seed):
    """隔离 schema 已 `alembic upgrade head` + 种子在位。
    ⇒ `GET /api/v1/projects/{project_id}` 返回 200 且项目名是种子那个。"""

@pytest.mark.e2e
async def test_lane_role_headers_map_to_seeded_users(e2e_client, e2e_seed, role_headers):
    """每个全局角色都能用自己的 token 读到种子项目（200）⇒ 角色矩阵与种子对齐。"""

@pytest.mark.e2e
async def test_lane_never_writes_to_the_public_schema(e2e_client, e2e_seed):
    """⚠️ **「隔离」这句话必须被验** —— E2E 的行**不能**出现在 public schema。

    ⚠️ **断法必须换**（2026-11-16 · hermes 断言形状病 #4）：
    **不能用「被覆盖过的 app engine」去查 public** —— 那个 engine 的
    `search_path` 指向隔离 schema ⇒ 查 public **永远查不到** ⇒ 守卫**恒绿** = 空壳。
    ⇒ 改用**独立连接**（`create_engine(<public URL>)` · **不带** `options=-csearch_path=`）
    ⇒ 对 public 的关键表（`users` / `projects` / `streams` / `user_projects` /
    `ai_audit_log`）取**场景运行前后**的 `count(*)` + `max(id)` 快照 ⇒ **断言不变**。
    ⇒ ⚠️ 且这条守卫**必须在写路径跑过之后**才断（否则库里本来就没新行 ⇒ 照样恒绿）
    ⇒ 归到 T6 末尾执行（E2E-017 写完 `ai_audit_log` 之后）。"""

def test_role_headers_rejects_an_unknown_role(role_headers):
    """未知角色 ⇒ **报错**（不是给一个错的 token ⇒ 全场 404 ⇒ 症状离病因远）。"""

def test_role_headers_rejects_a_role_outside_the_allowlist(role_headers):
    """⚠️ 角色**在白名单外**（如 `SYSADMIN` / `PROCESS_CONTROLLER` 之外的自造词）
    ⇒ **报错** ⇒ 不是发一个非法 token 让全场 403。"""

def test_e2e_items_are_skipped_without_the_lane_flag():
    """⚠️ **默认车道必须跳过 `e2e`**（hermes P0-2）—— 没有 `PCS_E2E_LANE=1`
    ⇒ `pytest_collection_modifyitems` 闸门给每个 `e2e` 用例打 skip 标记。
    ⇒ 断法：直接调闸门函数，传一个假 item ⇒ 断言 `add_marker(skip)` 被调过
    ⇒ **不**去真跑一次 `uv run pytest`（那太慢且会碰真库）。"""
```

```python
# tests/scripts/test_pytest_e2e_gate.py（照 tests/scripts/test_pytest_pg_gate.py 的形状）
def test_script_exists_and_is_executable():
def test_e2e_script_does_not_duplicate_the_fail_closed_gates():
    """⚠️ **不复制闸门** —— 薄封装的 body 里**不得**出现 `uv run pytest`
    ⇒ 闸门逻辑只有一份（`pytest_pg.sh`）⇒ 以后改一处两边生效。"""
def test_e2e_script_delegates_to_the_pg_lane_script():
    """薄封装确实 exec 到 `pytest_pg.sh` 且把 marker 设成 `e2e`。"""
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd pcs-backend && bash scripts/pytest_e2e.sh`
Expected: FAIL —— 车道脚本 / conftest 不存在

- [ ] **Step 3: 实现**

- `pytest_e2e.sh`：**薄封装**（不复制闸门）⇒ `export PG_PYTEST_MARK=e2e` +
  `export PCS_E2E_LANE=1` + `exec bash scripts/pytest_pg.sh`（库/端口由 `pytest_pg.sh` 自己导）
  ⇒ ⚠️ **不新建第四种「PG 车道」** —— 它是 E2E 专用入口，但**同一个库**。
  ⇒ ⚠️ **加 `flock -n /tmp/pcs-pgtest-lane.lock`**（抢不到 ⇒ 非零退出 + 说清原因）
- `tests/e2e_flows/conftest.py`：
  - **`pytest_collection_modifyitems` 闸门**（**第一件事**）：没有 `PCS_E2E_LANE=1`
    ⇒ 每个 `e2e` 用例 `add_marker(skip)` ⇒ 默认车道**绝碰不到开发库**
  - `e2e_schema`：**session 级**（一条车道一个 schema ⇒ 迁移只跑一次）
    ⇒ **起手** `DROP SCHEMA IF EXISTS <name> CASCADE` ⇒ 再 `CREATE SCHEMA`
    ⇒ 用 `subprocess` 跑 `alembic upgrade head`，环境里的 `DATABASE_URL` 追加
    `?options=-csearch_path=<schema>`（⚠️ 与 `tests/api/v1/test_stream_batch_concurrency_pg.py` **同款**）
    ⇒ ⚠️ **`alembic` 的 `settings` 是 pydantic 缓存实例** ⇒ 子进程里**先设 `DATABASE_URL` 再导入**
    ⇒ ⚠️ **URL 拼接判据**：已有文件用 `("&" if "?" in url else "?")`
      ⇒ **照抄** ⇒ 抄错 ⇒ schema 建到 public ⇒ 守卫恒绿
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
git add pcs-backend/scripts/pytest_e2e.sh pcs-backend/tests/e2e_flows/ pcs-backend/pyproject.toml
git commit -F <msgfile>   # 首行: feat(P10-B): E2E 车道（隔离 schema · 真 PG · 三道 fail-closed）
```

---

## Task 2（T2）：流程级种子（角色矩阵 · 起点态 · 幂等）

**Files:**
- Create: `pcs-backend/scripts/seed_e2e_flows.py`
- Create: `pcs-backend/tests/scripts/test_seed_e2e_flows.py`

**Interfaces:**
- Consumes: `app.models.*`（`Workspace` / `Project` / `User` / `UserProject` / `Stream` / `Deliverable` / `SignatureMatrix` / `ReportDefinition`）
- Produces:
  - `scripts/seed_e2e_flows.py` 暴露 **`async def seed_flows(db: AsyncSession, *, reset: bool = False) -> dict[str, int]`**
  - ⚠️ **同时导出载荷模板** `PIPING_RECORD_PAYLOAD`（D8）⇒ 造 DRAFT 记录的那个字典
    ⇒ `make_record` 用它 ⇒ 9 个场景不各写一份
    ⇒ ⚠️ 必须有**可调用入口**（同 `seed_e2e_data.py::seed`）⇒ 单测能传 `db_session`
  - 返回值 = 各造了多少行（`users` / `user_projects` / `streams` / `deliverables` / `signature_matrices` / `report_definitions`）
  - ⚠️ **id 不走返回值** ⇒ **模块级常量导出**（`FLOW_WORKSPACE_ID` / `FLOW_PROJECT_ID` /
    `FLOW_USERNAMES` / `FLOW_MATRIX_ID` / `FLOW_DELIVERABLE_ID` / `FLOW_REPORT_DEF_ID`）
    ⇒ `tests/e2e_flows/conftest.py` **直接 import 这些常量**拿 id
    ⇒ 不另造一份「id 从哪来」的真相源
  - **角色矩阵**（本 Task 的核心）：**7** 个用户，**全局角色**各不相同
    | username | 全局角色（JWT claim） | 项目内角色（`user_projects.role_in_project`） |
    |---|---|---|
    | `e2e-designer` | `DESIGNER` | `DESIGNER` |
    | `e2e-checker` | `CHECKER` | `CHECKER` |
    | `e2e-reviewer` | `REVIEWER` | `REVIEWER` |
    | `e2e-approver` | `APPROVER` | `APPROVER` |
    | `e2e-admin` | `SYSTEM_ADMIN` | `VIEWER` |
    | `e2e-outsider` | `DESIGNER` | ——（**不授权** ⇒ 跨项目 ⇒ 404） |
    | `alice` | `DESIGNER` | `DESIGNER` |
    ⚠️ **全局角色 ≠ 项目内角色** —— 状态机按**全局**判（`TRANSITION_ROLES`）·
    项目守卫按**项目内**判 ⇒ 两个维度都要有 ⇒ **不能**一个角色打天下。
    ⚠️ **`alice` 是为 UI 通道准备的**（2026-11-16 · hermes P1-4）：
    mock 登录只认 **4 个**名字（`app/api/v1/mock_auth.py::MOCK_USERS` =
    alice/bob/carol/dan）⇒ 种子里的 `e2e-*` **一个都登不进去** ⇒
    ⇒ T7 的 UI 流用 alice 登录 ⇒ alice **必须**在 flows 项目上有授权行
    ⇒ ⚠️ **`bob`/`carol`/`dan` 故意不授权** ⇒ 他们就是 UI 通道里的「局外人」
    ⇒ ⚠️ **alice 的全局角色也是 `DESIGNER`** ⇒ `role_headers("DESIGNER")`
    必须**只解析 `e2e-*`**（D9 的映射规则收紧）⇒ 否则后端场景会拿到 alice 的 token。
  - ⚠️ **`User.roles` 写空数组**（同 `seed_e2e_data.py`）⇒ 真实登录会覆盖它 ⇒ **不影响鉴权**
    （ACL 权威 = JWT 的 role claim）
  - **起点态数据**（**只造起点** ⇒ 其余状态由场景走真实端点推进）：
    1 工作区（FORMAL）+ 1 项目（绑 `module='RECORD'` 签署矩阵）+ 6 用户 + 5 条 `UserProject`
    + 2 条物流（含组成/物性）⚠️ **必须是 `CHECKED`**（计算链的入口守卫 ⇒
      DRAFT ⇒ 403 `STREAM_NOT_CHECKED` ⇒ 见事实基础）+ 1 个 **DRAFT 记录**（`PipingResult` 模块）+ 1 个 **DRAFT 交付物**
    + 1 个签署矩阵（3 级：CHECKER→REVIEWER→APPROVER）+ 1 个自定义报表定义
    ⚠️ **那个 DRAFT 记录是给「前端真后端通道」看的**（UI 流要打开一条记录的详情页）
    ⇒ **后端场景不用它**（D7：后端场景各自造记录）⇒ 别以为「种子造了记录场景就该复用它」。

- [ ] **Step 1: 写失败的测试**（`tests/scripts/test_seed_e2e_flows.py`）

```python
async def test_seed_flows_is_idempotent(db_session):
    """跑两遍 ⇒ 各表行数**不涨**。"""

async def test_seed_flows_creates_one_user_per_global_role(db_session):
    """7 个用户 ⇒ 全局角色各不相同（DESIGNER ×3 / CHECKER / REVIEWER / APPROVER / SYSTEM_ADMIN）。"""

async def test_seed_flows_grants_project_roles_except_the_outsider(db_session):
    """6 条 `UserProject` ⇒ 项目内角色各异；`e2e-outsider` **没有**授权行。"""

async def test_seed_flows_grants_alice_for_the_ui_lane(db_session):
    """⚠️ **`alice` 必须有授权行**（2026-11-16 · hermes P1-4）：
    mock 登录只认 alice/bob/carol/dan ⇒ T7 的 UI 流只能以 alice 登录
    ⇒ alice 在 flows 项目上没有授权行 ⇒ 项目守卫端点全 **404**
    ⇒ ⇒ **UI 通道 5 条全红**，且症状看着像「端点坏了」。
    ⇒ 同时断 `bob`/`carol`/`dan` **没有**授权行（他们是 UI 通道的「局外人」）。"""

async def test_seed_flows_only_creates_starting_states(db_session):
    """记录 = DRAFT、交付物 = DRAFT ⇒ **没有**预置 CHECKED/IN_APPROVAL 之类
    ⇒ 状态必须由场景**走**出来（否则 E2E 只是断言一个摆好的状态）。"""

async def test_seed_flows_reset_only_deletes_its_own_rows(db_session):
    """⚠️ **P10-A 的原罪（#1）不能重演** —— `--reset` 先塞一行**别人的**用户/项目
    ⇒ reset 之后那行**还在** ⇒ 种子只删自己造的（按固定 UUID 列表筛）。"""

async def test_seed_flows_reset_respects_foreign_key_order(db_session):
    """`--reset` 的删序遵守外键：`UserProject` → `Deliverable` → `SignatureMatrix`
    → `Record` → `Stream` → `Project` → `Workspace` → `User`
    ⇒ 反了就撞 FK ⇒ reset 直接炸。"""

async def test_record_payload_template_has_all_required_columns():
    """`PIPING_RECORD_PAYLOAD`（~20 个必填列）**不缺列**
    ⇒ 缺一个 ⇒ 9 个场景造记录全红（且错误信息在响应体里，不在模板里）。"""
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

## Task 3（T3）：录入与计算链（E2E-001~006）

**Files:**
- Create: `pcs-backend/tests/e2e_flows/test_e2e_project_config.py`
- Create: `pcs-backend/tests/e2e_flows/test_e2e_sim_import.py`
- Create: `pcs-backend/tests/e2e_flows/test_e2e_calc_chains.py`

**Interfaces:**
- Consumes: T1 的 `e2e_client` / `e2e_seed` / `role_headers`；T2 的种子 id
- Produces: 5 个场景的可复用 helper（放 `tests/e2e_flows/helpers.py`）：
  - `async def post_calc(client, url, body, *, headers) -> dict` —— 统一「调计算端点 → 断言 200 → 返回结果体」
  - `async def make_record(client, *, module, headers) -> uuid.UUID` —— 造一条 DRAFT 记录并返回 id
    ⚠️ **载荷不逐场景传**（2026-11-13 · /plan-eng-review D8）：`PipingResult` 有 **~20 个必填列**
    ⇒ 逐场景传 payload = 同一个 20 字段字典抄 **9 遍** ⇒ 改一处要改九处
    ⇒ **种子导出模块级常量 `PIPING_RECORD_PAYLOAD`**（造 DRAFT 记录时用的那个字典）
    ⇒ `make_record` 直接用它（只换 id）⇒ **一处真相源**；模板本身也被单测引用 ⇒ 模板也被测
    ⚠️ **`module` 的值是 `RECORD_TYPE_REGISTRY` 的键** ⇒ 用 **`PipingResult`**
    ⇒ **不是** `piping` 之类的小写（错值 ⇒ 422 `RECORD_MODULE_UNKNOWN`）
    ⇒ 且 `CostEstResult` / `TwoPhaseResult` / `ProjectCalculationStandardProfile`
    **不参与** 9 态工作流（缺 `RecordMixin` 列）⇒ 422 `RECORD_MODULE_UNSUPPORTED`

- [ ] **Step 1: 写失败的测试**

```python
# E2E-001
async def test_e2e_001_project_creation_and_input_checklist(e2e_client, role_headers, e2e_seed):
    """POST /api/v1/projects ⇒ 201 ⇒ **显式** seed 输入清单 ⇒ 清单**非空**。

    ⚠️ **清单不是「自动生成」的**（2026-11-16 自查更正，hermes 断言形状病 #2 同）：
    仓里**没有任何**代码在建项目时碰清单（`project_service` / `projects.py` 都不调 `bulk_seed`）
    ⇒ 真实流程是 `POST /api/v1/checklist/projects/{id}/seed`（请求体带 items 清单）
    ⇒ 再 `GET /api/v1/checklist/projects/{id}`（**行数 > 0**）+ `GET .../completeness`
    ⇒ ⚠️ 断言必须断**行数 + 每条的状态字段形状** ⇒ 「200 + 有个列表」是空壳断言
    ⇒ ⚠️ SPEC 说「自动生成」 ⇒ **登记偏离**（**D27**）—— 代码里没有这条自动逻辑。"""

# E2E-002
async def test_e2e_002_sim_import_creates_streams_and_completes_properties(e2e_client, role_headers, e2e_seed):
    """**PRO/II 双文件上传** ⇒ 物流数 > 0 ⇒ POST /api/v1/flash/calculate ⇒ 物性补全。

    ⚠️ **端点形状**（2026-11-16 自查更正）：**没有** `POST /api/v1/imports`
    ⇒ 真路径是 `POST /api/v1/projects/{project_id}/imports/proii/preview`
    （**multipart/form-data** · 两个字段：`file_inp` + `file_out`）
    ⇒ 再 `POST /api/v1/projects/{project_id}/imports/proii/commit`
    ⇒ ⚠️ **输入用仓内已提交的夹具**：`pcs-backend/tests/fixtures/proii/sample1_34comp/`
    （`.inp` + `.out` 两个文件 · 34 组分 · CONVERGED）
    ⇒ **不用**根目录 `sample/`（不入 git ⇒ 别的机器没有 ⇒ 车道不可移植）。"""

# E2E-003
async def test_e2e_003_pipe_calc_chain_populates_the_pipe_class_table(e2e_client, role_headers, e2e_seed):
    """POST /api/v1/pipe/calc-chain ⇒ 200 ⇒ GET /api/v1/pipe-classes ⇒ 含本次的管段。"""

# E2E-004 / 005 / 006
async def test_e2e_004_pump_calc_chain_returns_a_pump_result(...)
async def test_e2e_005_psv_calculate_returns_the_relief_area(...)
async def test_e2e_006_vessel_calculate_returns_dimensions(...)
```

⚠️ **计算链场景是「薄壳」**（2026-11-13 · /plan-eng-review D2 的裁决）：
E2E 测的是**编排**（端点契约 · 结果落库 · 下游可见），
**不是算法**（算法本身已被 `tests/api/v1/test_*_calc*.py` 的单测覆盖）⇒
断言落在「**200 + 响应体形状 + 落库行存在 + 下游列表能看到**」，
**不重复**单测里的数值断言（不写「管径 = 57.15 mm」这种）⇒
避免两套数值断言漂移，也避免把 E2E 写成第二个单测。

⚠️ **计算链的输入写在场景里**（与 `tests/api/v1/test_*_calc*.py` 的**合成输入同源**）
⇒ **不要**从 `sample/`（不入 git ⇒ 别的机器没有）取 ⇒ **不要**从种子灌输入
⇒ 种子只给项目 / 物流 / 角色。

- [ ] **Step 2: 跑测试确认失败**

Run: `cd pcs-backend && bash scripts/pytest_e2e.sh`
Expected: FAIL（场景未写 / 端点返回非预期）

- [ ] **Step 3: 实现场景**

- 每个场景 = **一串真实 API 调用**（不是直接写库）⇒ 断言落在**响应体**与**随后的 GET**
- ⚠️ **每条断言都要能区分「通过」与「假绿」**：断言具体字段值，**不是**「200 就好」
  ⇒ ⚠️ **但计算链场景例外**（见上面的「薄壳」裁决）：那里断言**结构与落库**，
  **不重复**单测的数值断言
- ⚠️ **跨场景隔离的单位是「记录」，不是「项目」**（2026-11-13 · /plan-eng-review D7）：
  场景**共享**种子那一个项目；隔离靠**每个场景造自己的记录**（`make_record`）
  ⇒ 状态机/计算链天然互不碰 ⇒ 不用每个场景重复「建项目 + 造授权行」
  ⇒ ⚠️ **项目级的共享状态**（设备表汇总 / 能耗汇总）会被多个场景**叠加**
  ⇒ 汇总类断言要比对**增量**（前后差），**不是**绝对值

- [ ] **Step 4: 跑测试确认通过**

Run: `cd pcs-backend && bash scripts/pytest_e2e.sh`
Expected: PASS（E2E-001~006 全绿）

- [ ] **Step 5: 提交**

```bash
git add pcs-backend/tests/e2e_flows/
git commit -F <msgfile>   # 首行: test(P10-B): E2E-001~006 录入与计算链
```

---

## Task 4（T4）：汇总 · 报告 · 供应商（E2E-007/008/009/014/015）

**Files:**
- Create: `pcs-backend/tests/e2e_flows/test_e2e_equipment_util.py`
- Create: `pcs-backend/tests/e2e_flows/test_e2e_report.py`
- Create: `pcs-backend/tests/e2e_flows/test_e2e_supplier.py`

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
    """**三段**：① 队列不可达时端点**当场 503**（不留孤儿行）
    ⇒ ② **直调** worker 任务体生成文件 ⇒ ③ 终态 SUCCESS + 哈希非空 + 下载字节数 > 0。

    ⚠️ **不能只轮询**（2026-11-16 · hermes P0-1 · 本批最贵的发现）：
    `POST /api/v1/report/generate` 走的是 **ARQ + Redis**（`app/api/v1/report.py:178`
    `create_pool(RedisSettings.from_dsn(...))`）⇒ **没有 Redis ⇒ 入队失败 ⇒
    端点抛 503 `REPORT_QUEUE_UNAVAILABLE`**（`report.py:196-207`）
    ⇒ ⚠️ **不是 202** ⇒ 「先 POST 拿 id 再轮询」这条写法**根本走不通**
    ⇒ ⇒ 「轮询到 SUCCESS」**永远不可达** ⇒ 只写「202 + 轮询」⇒ 车道**必挂**
    （红因是「车道缺件」不是「产品缺陷」）。

    ⇒ **三段断言**（各自独立可失败）：
    ① **HTTP 段**：`POST /api/v1/report/generate` ⇒ **503** +
       `code == "REPORT_QUEUE_UNAVAILABLE"` ⇒ 且**那行被就地标 `FAILED`**
       （**不留孤儿 PENDING** —— 这是一条**真实的 fail-closed 产品行为**，
       不是「车道缺件」⇒ 值得钉）
    ② **产物段**：**直调** `app.workers.report_tasks.generate_report_task(ctx, …)`
       ⇒ ⚠️ `ctx` 里必须放 **`session_factory`**（绑到**隔离 schema** 的引擎），
       **不是** `ctx["db"]`（worker 从不注入那个键 ⇒ 实测过 `KeyError`）
       ⇒ 拿到 `report_file_id`
    ③ **产物断言**：`GET /api/v1/report/{id}/status` ⇒ **终态 `SUCCESS`**
       ⇒ `GET /api/v1/report/{id}/hash` ⇒ **哈希非空**
       ⇒ `GET .../download` ⇒ 200 且**字节数 > 0**
    ⇒ ⚠️ **「HTTP 202 → Redis → worker 消费 → 状态变更」那条真链路仍未覆盖**
    ⇒ ⇒ 登记 **TODO-155**（与 AI 审计那条一起补：一次起 Redis+worker 补两条）。"""

# E2E-014
async def test_e2e_014_supplier_actual_value_updates_the_deviation_report(...)
    """录入实际值 ⇒ 偏差报告里出现偏差行 ⇒ 实际值状态变 CONFIRMED。"""

# E2E-015
async def test_e2e_015_custom_report_definition_executes_and_returns_data(...)
    """**三段**：① execute 在队列不可达时**当场 503**（执行行被改判 FAILED）
    ⇒ ② **直调** worker 任务体执行定义 ⇒ ③ 执行状态成功 + 数据行数 > 0。

    ⚠️ **同样不能只轮询**（hermes P0-1）：`POST /api/v1/report-builder/definitions/{id}/execute`
    走 `app/services/report/arq_queue.py::enqueue_definition_execution`（Redis 必需）
    ⇒ 无 Redis ⇒ `arq_queue` 抛 `PcsError(503)` ⇒ 端点把执行行改判 `FAILED`
    （`report_builder.py:417-432`）⇒ **再 re-raise** ⇒ ⚠️ **不是 202**
    ⇒ ⇒ 「先 execute 拿 task_id 再轮询」**走不通**。

    ⇒ **三段断言**：
    ① **HTTP 段**：`POST .../execute` ⇒ **503** ⇒ 且执行行被改判 `FAILED`
       （**不留孤儿 QUEUED** —— 又一条 fail-closed 产品行为）
    ② **产物段**：**直调**
       `app.workers.report_builder_tasks.execute_definition_task(ctx, …)`
       （⚠️ `ctx` 里放 `session_factory` ⇒ 绑隔离 schema）
    ③ **产物断言**：`GET /api/v1/report-builder/executions/{task_id}`
       ⇒ 状态成功 ⇒ **数据行数 > 0** ⇒ 且**不是**「有个列表就算」。"""
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd pcs-backend && bash scripts/pytest_e2e.sh`
Expected: FAIL（场景未写 / 汇总值对不上）

- [ ] **Step 3: 实现场景**

- 汇总类场景（008/015）⇒ 断言**数值关系**（汇总 = 明细之和；报表数据行数 > 0）
  ⇒ **不是**「> 0」—— 那挡不住「算错但非零」
- 报告类场景（009/015）⇒ **三段式**（2026-11-16 · hermes P0-1 · **2026-11-16 复核再修**）：
  ① **HTTP 段**：队列不可达 ⇒ 端点**当场 503**（`REPORT_QUEUE_UNAVAILABLE`）
  ⇒ 且那行被就地标 `FAILED` ⇒ **不留孤儿行**（这是一条**真实的 fail-closed 行为**）
  ② **产物段**：**直调 worker 任务体**（`generate_report_task` /
  `execute_definition_task`）⇒ 拿到 `report_file_id` / `task_id`
  ③ **产物断言**：status 终态 / hash / download 字节数 / 执行数据行数
  ⇒ ⚠️ **为什么不能只靠轮询**：车道**不起 Redis**（不引新依赖）⇒
  **入队就失败** ⇒ 端点 503 ⇒ 「轮询到 `SUCCESS`」**不可达**
  ⇒ ⇒ **不起 worker，但要把 worker 的那段代码**（同一个任务函数）**在测试里跑一次**
  ⇒ ⚠️ **直调时 `ctx` 里塞 `session_factory`**（绑到隔离 schema 的引擎）
  ⇒ **不是** `ctx["db"]`（worker 从不注入那个键 ⇒ 实测过 `KeyError` ⇒ bug-166 的教训）
  ⇒ ⚠️ 任务函数的**签名以源码为准**（`report_tasks.py:124` /
  `report_builder_tasks.py:37` ⇒ 都收 `ctx` + 关键字参数）

- [ ] **Step 4: 跑测试确认通过**

Run: `cd pcs-backend && bash scripts/pytest_e2e.sh`
Expected: PASS（E2E-007/008/009/014/015 全绿）

- [ ] **Step 5: 提交**

```bash
git add pcs-backend/tests/e2e_flows/
git commit -F <msgfile>   # 首行: test(P10-B): E2E-007/008/009/014/015 汇总·报告·供应商
```

---

## Task 5（T5）：记录层状态机 + 交付物 Rev（E2E-010~013 + WF-PATH）

**Files:**
- Create: `pcs-backend/tests/e2e_flows/test_e2e_record_workflow.py`
- Create: `pcs-backend/tests/e2e_flows/test_e2e_deliverable_rev.py`

**Interfaces:**
- Consumes: T2 的签署矩阵 + DRAFT 记录 + DRAFT 交付物；T3 的 `make_record`
- Produces: `helpers.py` 加 `async def advance_record(client, *, record_id, module, step, headers) -> dict`
  （走 `submit-approval` / `approval-step`）
  + ⚠️ **加 `async def make_deliverable(client, *, project_id, headers) -> uuid.UUID`**
  （2026-11-16 · hermes 漏掉发现 #10）：交付物场景（E2E-011/012 · WF-PATH-02/03）
  需要**多条**交付物（改 Rev 要有 Rev 1、代录客户批准要另一条）⇒ 共用种子那一条
  ⇒ 场景之间互相踩 ⇒ ⇒ **helper 造**（`PIPING_RECORD_PAYLOAD` 的同款原则 ⇒ 一处真相源）

- [ ] **Step 1: 写失败的测试**

```python
# WF-PATH-01A 正向 + E2E-010
async def test_wf_path_01a_forward_path_reaches_checked(...)
    """DRAFT → submit-approval → approval-step(CHECKER) → approval-step(REVIEWER)
    ⇒ approval-step(APPROVER) ⇒ **终态 = `CHECKED`**（不是 `APPROVED` —— 9 态里没有这个值）
    ⇒ 且**每一步都要用对角色**（用错角色 ⇒ 403）。

    ⚠️ **终态必须精确断 `CHECKED`**（2026-11-16 · hermes 断言形状病 #1）：
    计划原稿写「= APPROVED/IN_APPROVAL（按矩阵第 3 级）」⇒ ⚠️ **`APPROVED` 不存在**
    （`RecordSignStatus9` 9 态里没有）⇒ 断 `APPROVED` ⇒ 字段不存在 ⇒ 断言必飘；
    ⚠️ 而「IN_APPROVAL 或 CHECKED 都算」这种**或**写法更毒：链条**停在第 2 步**
    （还差 APPROVER 那一步）也照样绿 ⇒ ⇒ 断 **`sign_status == 'CHECKED'`** 且
    **`approval_step is None`** 且 **`approval_role` 已清空**
    ⇒ 且**每步之后**断「当前 `approval_role` == 链上下一步的 `sign_role`」
    ⇒ 这样「第 3 步没走」必红。"""

# WF-PATH-01B 驳回
async def test_wf_path_01b_reject_returns_to_check_rejected_and_can_resubmit(...)

# WF-PATH-01C 变更闭环（★ Review Focus #1）
async def test_wf_path_01c_upstream_change_marks_downstream_stale_and_confirm_recalc(...)
    """上游记录改 ⇒ 下游记录变 STALE ⇒ **四步**走到 CHANGED，且哈希变了。

    ⚠️ **「confirm-recalc ⇒ 变 CHANGED」是一跳跨了三个端点**（2026-11-16 ·
    hermes 断言形状病 #6）⇒ 照字面写会**在 `CHANGE_PENDING` 上断 `CHANGED`** ⇒ 必红。
    ⇒ **分步断言**（每步一个独立断言 ⇒ 红了能立刻知道红在哪一步）：
    ① `POST /api/v1/change-impact/{module}/{id}/confirm-recalc`
       ⇒ 下游记录 `marked_stale >= 1`（**这是「传播触发器」**，不是状态转移 ——
       `app/api/v1/change_impact.py:275`；它跑 CIA 扫描 + 链式传播）
    ② `POST /api/v1/change-impact/{module}/{id}/confirm`
       ⇒ 哈希判定「结果**有变**」⇒ 记录进 **`CHANGE_PENDING`**（要求重新签署）
       ⇒ ⚠️ 若判定「无变化」则回 **`CHECKED`** ⇒ 种子必须**保证下游记录的哈希会变**
       ⇒ 断言要断在 `CHANGE_PENDING` 这条分支上
    ③ `POST /api/v1/records/{module}/{id}/apply-change`
       ⇒ **`CHANGED`**（`records_actions.py:986`）
    ④ 记录哈希 **≠** 发起变更前的哈希。"""

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
git add pcs-backend/tests/e2e_flows/
git commit -F <msgfile>   # 首行: test(P10-B): WF-PATH 五类路径 + E2E-010~013
```

---

## Task 6（T6）：权限矩阵 + AI 审计 + schema 一致（E2E-016/017/018 + AUTH-E2E）

**Files:**
- Create: `pcs-backend/tests/e2e_flows/test_e2e_permission_matrix.py`
- Create: `pcs-backend/tests/e2e_flows/test_e2e_ai_audit.py`
- Create: `pcs-backend/tests/e2e_flows/test_e2e_schema_parity.py`

**Interfaces:**
- Consumes: T2 的角色矩阵（T6 的全部输入）
- Produces: `tests/e2e_flows/test_e2e_permission_matrix.py` 里一张**参数化表**（角色 × 操作 × 期望码）⇒
  加新用例只改表，不改逻辑

- [ ] **Step 1: 写失败的测试**

```python
# AUTH-E2E-01~10（参数化）
# ⚠️ **四元组**（2026-11-16 · hermes 断言形状病 #3）：**错误码也要断**
# ⇒ 只断状态码 ⇒ 换个原因也照样绿 ⇒ 断言与被测行为**脱钩**。
AUTH_MATRIX = [
    # (全局角色, 操作, 期望状态码, 期望错误码)
    ("DESIGNER", "submit-approval", 200, None),                   # AUTH-E2E-01
    ("CHECKER",  "submit-approval", 403, "APPROVAL_SELF_REVIEW_FORBIDDEN"),  # AUTH-E2E-02 ★
    ("CHECKER",  "approval-step",   200, None),                   # AUTH-E2E-03
    ("DESIGNER", "approval-step",   403, "HTTP_403"),              # AUTH-E2E-04
    ("APPROVER", "approval-step",   200, None),                   # AUTH-E2E-05
    ("DESIGNER", "approval-step",   403, "HTTP_403"),              # AUTH-E2E-06
    ("SYSTEM_ADMIN", "audit-logs",  200, None),                   # AUTH-E2E-07
    ("DESIGNER",     "audit-logs",  403, "HTTP_403"),              # AUTH-E2E-08
    ("APPROVER", "proxy-approval",  200, None),                   # AUTH-E2E-09
    # ★ 补一行钉住「粗闸放行、矩阵细判」两层语义（hermes 建议）：
    ("SYSTEM_ADMIN", "submit-approval", 200, None),  # 粗闸放行 + 角色不在链里 ⇒ 200
]

⚠️ **AUTH-E2E-02 的 403 是「自审闸」不是「角色不够」**（2026-11-16 · hermes 漏掉发现 #8）：
`app/api/v1/records_actions.py` 的 `submit_approval` 先过粗闸
`require_roles(SUBMIT_FOR_CHECK = {DESIGNER, CHECKER, APPROVER, SYSTEM_ADMIN})`
⇒ **`CHECKER` 是放行的** ⇒ 接着撞自审闸
`if actor.role in {s.sign_role for s in steps}`（矩阵第 1 步就是 CHECKER）
⇒ **403 `APPROVAL_SELF_REVIEW_FORBIDDEN`**。
⇒ ⚠️ 也就是说：SPEC 的 AUTH-E2E-02「CHECKER 送审被拒」在代码里的**真实原因**
是「提交人自己的角色在批准链里」⇒ ⇒ **必须钉住错误码**（否则换个矩阵、换个原因也照样绿）
⇒ ⇒ **登记偏离**（D28）。

async def test_permission_matrix(...)
    """⚠️ 403 与 404 的**形状**要分开断言：越权（角色不对）⇒ 403；
    跨项目（角色对但没授权）⇒ **404**（与「不存在」同形 ⇒ 不泄露存在性）。"""

# E2E-016
async def test_e2e_016_cross_project_access_is_404_not_403(...)

# E2E-017（★ Review Focus #4）
async def test_e2e_017_ai_endpoint_returns_501_and_the_audit_row_is_persisted(...)
    """POST /api/v1/ai/intent ⇒ 501 + code=AI_NOT_IMPLEMENTED
    ⇒ **两段都断**（2026-11-13 · /plan-eng-review D6）：
    ① **入队** —— spy `app.core.ai_audit_middleware.enqueue_ai_audit_log`
       ⇒ 断言「被调了」且**参数对**（request_id / user_id / status_code）
       ⇒ ⚠️ **只断落库会漏掉中间件那段**（压根没入队时照样绿）
    ② **落库** —— 直调 `app.workers.ai_audit_tasks` 的写库任务
       ⇒ **真 PG** 里 `ai_audit_log` 有一行
    ⇒ **不起 ARQ worker**（车道不引 Redis / worker 进程）"""

# E2E-018
async def test_e2e_018_pcs_and_pcs_test_schema_versions_match(...)
    """直查两库的 `alembic_version` ⇒ **相同**（CLAUDE.md 的两库口径）。

    ⚠️ **必须一库一个进程**（CLAUDE.md §测试前检查 · 2026-11-01 实测打脸）：
    alembic 的 `settings` 是 **pydantic 缓存实例** ⇒ **同进程**第二次改
    `DATABASE_URL` **不生效** ⇒ 两条命令各起一个**独立子进程** ⇒ 再比。
    ⚠️ **更不能只信命令输出**：CLAUDE.md 记着一次「`current` 打出 `(head)`、
    `check` 打出 `No new upgrade operations detected`（exit 0）⇒ 看着全绿，
    实际**根本没在 `pcs_test` 上跑**」⇒ ⇒ **必须直查库的 `alembic_version`**
    （`SELECT version_num FROM alembic_version`）⇒ 而不只是看命令的输出。
    ⚠️ **口令只在环境变量里**（子进程继承 `DATABASE_URL`，不写命令行）。
    实测（2026-11-16）：`pcs` / `pcs_test` / `pcs_pgtest` **三个库都在 `p10_001`**
    ⇒ 这条断言今天成立 ⇒ 它防的是**漂移**。"""

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
- ⚠️ **E2E-017 拆两段**（D6）：① spy 入队（断「请求真的产生了审计」）
  ② 直调写库任务（断「落库这一段是对的」）⇒ 合起来覆盖链路，**不起 worker**
- ⚠️ **E2E-018** 直查两库 `alembic_version` ⇒ **不一致就登记**（本批不修）

- [ ] **Step 4: 跑测试确认通过**

Run: `cd pcs-backend && bash scripts/pytest_e2e.sh`
Expected: PASS（AUTH-E2E-01~10 + WF-PATH-04 + E2E-016/017/018 全绿）

- [ ] **Step 5: 提交**

```bash
git add pcs-backend/tests/e2e_flows/
git commit -F <msgfile>   # 首行: test(P10-B): 权限矩阵 + E2E-016/017/018
```

---

# 段三：前端与收口

## Task 7（T7）：真后端通道的 UI 流（5 条）

**Files:**
- Create: `pcs-frontend/e2e/real_backend_flows.spec.ts`
- Modify: `pcs-backend/scripts/seed_e2e_flows.py`（若 UI 流需要额外起点态数据）

**Interfaces:**
- Consumes: 现成的 `real-backend` Playwright project（`reuseExistingServer: false` · 5174）·
  `fixtures.ts::realPage` · 后端连 `pcs_pgtest`（**被 seed 的那个库**）
- ⚠️ **数据在哪个房间**（2026-11-13 · /plan-eng-review D3）：
  后端 E2E 车道的数据在**隔离 schema**（自己的小房间）里 ⇒
  真后端通道的后端连的是 **public schema**（大房间）⇒ **两个房间不通**
  ⇒ ⇒ **`scripts/seed_e2e_flows.py` 也要在 public schema 跑一遍**（脚本幂等 ✓）
  ⇒ ⚠️ **PG 车道不受影响**：实测 5 个 PG 用例文件**全部**用隔离 schema ⇒ 不碰 public
  ⇒ ⇒ 起真后端通道前（或本 Task 内）把 flows 种子跑到 public ⇒ T7 的 5 条流才有数据可断言
- ⚠️ **UI 流必须有一个「能登录 + 有授权」的用户**（2026-11-16 · hermes P1-4）：
  mock 登录只认 **4 个**名字（alice/bob/carol/dan）⇒ 种子的 `e2e-*` **登不进去**
  ⇒ ⇒ **`alice` 必须有 flows 项目的授权行**（T2 已加）
  ⇒ ⚠️ **`bob`/`carol`/`dan` 故意不授权** ⇒ 他们就是「越权用户看不到别人的项目」
  这条 UI 流的**局外人** ⇒ ⚠️ 不要给他们也发授权行 ⇒ 那条 UI 流就没有对照了。
- ⚠️ **首跑（新机器 / CI）不能有手动步骤**（2026-11-16 · hermes 交付风险 4）：
  `postgres-pgtest` 没起、或 public 里没有 flows 种子 ⇒ 真后端通道 6 条**全红**
  ⇒ ⇒ **把 flows 种子（连同 migrate）写进 compose 的 seed 服务**或
  `scripts/compose_test_stack.sh` 的启动序列 ⇒ README 同步 ⇒ **不留手动步骤**。
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

## Task 8（T8）：契约 / SPEC 偏离回写 / 账簿 / QA 收口

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
| **D27** | 项目创建后输入清单**自动生成** | 仓里**没有**任何建项目时碰清单的代码 ⇒ 真实流程是 `POST /api/v1/checklist/projects/{id}/seed` **显式** seed | **以代码为准** ⇒ E2E-001 断「显式 seed 后清单非空」⇒ SPEC 措辞修订 |
| **D28** | AUTH-E2E-02「CHECKER 送审被拒（角色不够）」 | 代码里 `CHECKER` **过得了**粗闸（`SUBMIT_FOR_CHECK` 含 CHECKER）⇒ 403 的真因是**自审闸**（提交人角色出现在批准链里）⇒ 错误码 `APPROVAL_SELF_REVIEW_FORBIDDEN` | **以代码为准** ⇒ 矩阵断**错误码**而非只断状态码 ⇒ SPEC 的「角色不够」措辞修订 |
| **D30** | 批准链走完后的状态词（若 SPEC 写 `APPROVED`） | 9 态里**没有 `APPROVED`** ⇒ 链尾是 **`CHECKED`**（`IN_APPROVAL` 只在链中途） | **以代码为准** ⇒ 断言精确断 `CHECKED` + `approval_step is None` ⇒ SPEC 词表订正 |
| **D29** | 报表生成是**异步**的（HTTP 202 + 轮询） | 入队依赖 **Redis + ARQ worker** ⇒ 本批**不引 Redis/worker** ⇒ 队列不可达时端点**当场 503** ⇒ 轮询到 `SUCCESS` **不可达** | **本批用三段式**（HTTP 503 fail-closed + 直调 worker 任务体 + 产物断言）⇒ 「真过 Redis + worker」延到 **TODO-155** |
| **D31** | 导入 ⇒ 物性补全（E2E-002 一气呵成） | **PRO/II 解析器不抽组成**（`app/services/import_service.py:135` 明写「SIM-10 MVP 仅 T/P/flow/phase 落库」）⇒ 导入的物流 `composition_json is None` ⇒ **进不了计算链**（flash 要求有组成） | **E2E-002 拆两段**（导入段断「物流落库 + 能进审批流」· 物性补全段断「有组成的 CHECKED 物流能算出物性」）⇒ 「导入的物流进不了计算链」是**产品缺口** ⇒ **TODO-156** |
| **D32** | 容器计算返回**尺寸**（E2E-006） | 尺寸要 `sizing_spec`（C-08 **V1.2** 的两相分离器尺寸，Souders-Brown）⇒ 那是 **P6-4 的遗留债**（SPEC V1.1 内部不一致 ⇒ 计划已停工待 V1.2） | **本批断「结果里有 `sizing` + `hydraulics` 两块」**，**不断尺寸数值** ⇒ 尺寸留给 P6-4 的 V1.2 |

- [ ] **Step 2: 跑批末闸门**

```bash
cd pcs-backend && uv run pytest                    # 全量（e2e 用例被「默认车道 skip 闸门」跳过 ⇒ 不碰开发库）
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

## Failure modes（每个新增代码路径一条）

| 新增代码路径 | 一个真实的失败方式 | 有测试吗 | 有错误处理吗 | 用户看到什么 |
|---|---|---|---|---|
| `scripts/pytest_e2e.sh`（薄封装） | marker 传错 ⇒ 跑成了 PG 车道（**看起来绿、其实没跑 E2E**） | ✅ `test_e2e_script_delegates_to_the_pg_lane_script` | ✅ 闸门②「收集到 0 个 ⇒ FAIL」 | 车道报「收集到 0 个测试」⇒ 红 |
| `e2e_schema`（建 schema → upgrade → DROP） | `alembic upgrade` 失败 ⇒ 场景全在**没有表的库**上跑 | ✅ 迁移失败 ⇒ fixture 抛 ⇒ 用例红 | ✅ 不静默跳过 | 红（不是绿） |
| `e2e_schema`（DROP） | DROP 失败 ⇒ 隔离 schema **残留**在库里 | ⚠️ 无（失败会打日志） | ✅ `DROP SCHEMA ... CASCADE` | 下次跑时「schema 已存在」⇒ 需先手清 |
| `e2e_seed`（跑 flows 种子） | 种子抛错（外键/唯一约束）⇒ 场景全在**半套数据**上跑 | ✅ 种子失败 ⇒ fixture 抛 | ✅ 不静默 | 红 |
| `e2e_seed`（补两张 lifespan 表） | 忘了补 ⇒ 折标煤恒为 0 | ✅ E2E-008 断言**汇总 = 明细之和** ⇒ 折标项对不上就红 | ⚠️ 无显式报错 | 红 |
| `e2e_client`（`create_app()` + 覆盖 `get_db`） | 覆盖漏了某个端点用别的 session ⇒ 半条链路读开发库 | ✅ `test_lane_never_writes_to_the_public_schema` | ✅ 覆盖是全局的 | 红 |
| `role_headers`（role → 用户） | 拿到**没授权**的那个用户 ⇒ 全场 404 | ✅ 角色矩阵用例 + 未知角色报错 | ✅ D9 的映射规则 | 红（但症状像「端点坏了」） |
| `helpers.make_record`（用载荷模板） | 模板缺一个必填列 ⇒ 9 个场景造记录全红 | ✅ `test_record_payload_template_has_all_required_columns` | ✅ 模板被测 | 红（错在响应体里 ⇒ 难定位） |
| `helpers.advance_record`（走一步状态机） | 状态机非法转移 ⇒ 403/422 ⇒ 场景看不懂 | ✅ 每条路径用例断言**期望的状态码** | ✅ 端点返回错误信封 | 红 |
| `seed_e2e_flows._get_or_create` | 并发下撞唯一约束 | ✅ house 形状（savepoint + 重读赢家） | ✅ | 红 |
| `seed_e2e_flows._delete_own_rows`（`--reset`） | 删序错 ⇒ 撞 FK；或删多了 ⇒ 删了别人的行 | ✅ 两条守卫（删序 + 只删自己造的） | ✅ | 红 |
| ⚠️ **`e2e` marker 闸门缺失**（hermes P0-2） | 默认车道 `uv run pytest` **把 E2E 场景跑到开发库 `pcs` 上** ⇒ 建隔离 schema + 跑 `alembic upgrade head` | ✅ `test_e2e_items_are_skipped_without_the_lane_flag` | ✅ 闸门在 `tests/e2e_flows/conftest.py` ⇒ **默认车道全 skip** | **没有症状**（跑得挺快、全绿）⇒ **误伤开发库而没人发现** |
| ⚠️ **报告场景只写「202 + 轮询」**（hermes P0-1） | 无 Redis ⇒ 入队失败 ⇒ 端点**当场 503** ⇒ 轮询永远等不到 `SUCCESS`（且**根本没 id 可轮询**） | ✅ **三段式**（HTTP 503 fail-closed + 直调任务体 + 产物断言） | ✅ 端点 fail-closed + 那行被标 `FAILED`（不留孤儿） | 车道**必红**（红因是「车道缺件」不是「产品缺陷」）⇒ 容易误判成产品 bug |
| ⚠️ **`alice` 没有授权行**（hermes P1-4） | UI 流用 alice 登录 ⇒ 项目守卫端点全 **404** ⇒ 5 条 UI 流全红 | ✅ `test_seed_flows_grants_alice_for_the_ui_lane` | ✅ 种子显式建行 | 红（症状像「端点坏了」） |
| ⚠️ **public schema 守卫用错连接**（hermes 断言形状病 #4） | 用被 `search_path` 覆盖的 app engine 去查 public ⇒ **永远查不到** ⇒ 守卫**恒绿** | ✅ 独立连接 + 前后快照 + 在写路径跑过之后断 | ✅ 连接不共享 `search_path` | **恒绿 = 空壳** ⇒ 隔离承诺是假的 |
| ⚠️ **`flock` 没加**（hermes P3-11） | 两条车道并发 ⇒ 同库 DDL 等锁 ⇒ **偶发卡住**（不是报错） | ⚠️ 无（靠人别同时跑） | ✅ `flock -n` ⇒ 抢不到就**非零退出** | 偶发卡住 ⇒ 排查成本极高 |

⚠️ **无「静默失败」缺口**：上表每一行的失败**都会让车道红**（不是绿）
⇒ 符合本仓「fail-closed」纪律。

---

## 并行化策略

**顺序实施，无并行化机会。** 理由：T1 的 fixture（`e2e_schema` / `e2e_seed` /
`e2e_client` / `role_headers`）与 T2 的种子常量是 T3~T6 **每一个场景文件**的
共同依赖 ⇒ 共享同一批模块（`tests/e2e_flows/` + `scripts/`）⇒ 分叉必冲突
⇒ 且本仓**明令不要建 worktree**（历史事故）。

| Step | 模块 | 依赖 |
|---|---|---|
| T1 车道 + fixture | `scripts/` · `tests/e2e_flows/` · `pyproject.toml` | — |
| T2 种子 | `scripts/` · `tests/scripts/` | T1（车道要能跑） |
| T3 计算链场景 | `tests/e2e_flows/` | T1 · T2 |
| T4 汇总/报告场景 | `tests/e2e_flows/` | T3（造出来的记录） |
| T5 状态机场景 | `tests/e2e_flows/` | T1 · T2 |
| T6 权限/AI/schema | `tests/e2e_flows/` | T1 · T2 · T5（矩阵步骤） |
| T7 前端 UI 流 | `pcs-frontend/e2e/` · `scripts/` | T2（public schema 的数据） |
| T8 收口 | 文档 + 账簿 | 全部 |

---

## 验收

| 门 | 判据 |
|---|---|
| **E2E-001~018** | 18 条场景**全部通过**（`bash scripts/pytest_e2e.sh` ⇒ 用例数 **≥ 18**；参数化的权限矩阵会再多几条） |
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
| 4 | **E2E 车道与 PG 车道同库（`pcs_pgtest`）** | **E2E 车道自己**用隔离 schema ⇒ 不碰 public ⇒ 可同库（⚠️ 但 **PG 车道**会写 public ⇒ 见 #14） | 无需裁决（已定） |
| 5 | **ARQ worker 在 E2E 里要不要起** | 审计落库是异步的 | 本批**不起 worker** ⇒ 直接调写库任务 ⇒ 车道依赖更少（已定） |
| 6 | **E2E-018 的两库口径** | SPEC 写 `pcs` 与 `pcs_test`；本机 `pcs_test` 存在 | 本批直查两库 `alembic_version` ⇒ 不一致就**登记**（不修） |
| 7 | **TODO-141（全量测试迁 `strict_client`）** | 本批只迁**新写的**用例 | 原 TODO **保留** ⇒ 迁完才是「关闭」 |
| 8 | **计算链输入用合成数据（不取 `sample/`）** | `sample/` 不入 git ⇒ 别的机器没有 ⇒ 车道不可移植 | 本批用合成输入（已定）⇒ 真 PRO/II 回归另由 SIM 解析测试承担 |

### /plan-eng-review（2026-11-13）新增的登记项

| # | 问题 | 现状 | 归属 |
|---|---|---|---|
| 9 | **public schema 里的 E2E 流程级数据** | D3 定了「flows 种子也在 public 跑一遍」⇒ 测试库 public 多一份测试数据 | **TODO-154** ⇒ 发布前清单里说明 + 清理脚本 |
| 10 | **AI 审计的「真链路」没被端到端覆盖** | D6 的两段式只断「入队」与「落库」⇒ 「真过 Redis + worker」那段没验 | **TODO-155** ⇒ 与 TODO-152 同批做（P10-F） |
| 11 | **两条车道的并发** | 同一个库 ⇒ 并发 DDL 等锁 ⇒ 表现是「偶发卡住」 | 计划已写「**串行跑**」⇒ 无需 TODO |

### hermes 第三视角（2026-11-16）新增的登记项

| # | 问题 | 现状 | 归属 |
|---|---|---|---|
| 12 | **E2E-009/015 的「真过 Redis + ARQ worker」没被覆盖** | 本批用三段式（HTTP 503 fail-closed + 直调任务体 + 产物断言）⇒ 「HTTP 202 → 入队 → Redis → worker 消费 → 状态变更」那段**没端到端验** | 与 **TODO-155** 同批做（P10-F）⇒ 本批不引 Redis/worker |
| 13 | **默认车道的 `e2e` 闸门只在本仓生效** | 若将来有人 `pytest -m e2e` 直接跑（不经 `pytest_e2e.sh`）⇒ 闸门**照跳**（因为没有 `PCS_E2E_LANE=1`）⇒ 看着像「收集到 0 个测试」 | 闸门**照跳是对的**（fail-closed）⇒ README 写明「E2E 车道只能经 `scripts/pytest_e2e.sh` 跑」 |
| 14 | **`e2e` 车道与 `pg` 车道的库是同一个 `pcs_pgtest`** | PG 车道的守卫 `test_compose_test_stack_pg.py` 的 seed **落 public**（无 `search_path` 覆盖）⇒ **两条车道并非互不影响** | 登记 ⇒ **TODO-154**（public 的测试残留）一并说明 |
| 15 | **UI 通道只能登 alice/bob/carol/dan** | 其余真账号（LDAP）不可用 ⇒ UI 流覆盖不到那些角色 | 本批只覆盖 alice（+ 3 个未授权的对照）⇒ 其余留 P10-C/P10-F |
| 16 | **状态机断言的「终态词表」** | 9 态无 `APPROVED`；链尾是 `CHECKED` ⇒ SPEC 措辞若用 `APPROVED` 要订正 | 已登记 **D30** 一并修订 SPEC 措辞 |

---

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | — |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | — | — |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | **clean** | **16 issues**（架构 7 · 质量 2 · 测试 7 · 性能 0）· 0 critical gaps · 0 unresolved |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | — |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | — |
| **hermes 第三视角** | `hermes chat`（glm-5.2 · Z.AI） | **跨模型对抗性审查**（不同模型家族 ⇒ 不共享盲区） | 1 | **partly** | **20 条事实里 18 条属实**（2 条它判错、但我的复核证明**它是对的**）· **11 条漏掉的发现**（2 个 P0 · 3 个 P1 · 4 个 P2 · 2 个 P3）· **6 条断言形状病** · **8 条交付风险** ⇒ **全部已折进本计划** |

- **UNRESOLVED:** 0（**18 个决策**全部当场定完：D2 批次体量 · D3 前端数据落点 · D4 lifespan 的两张表 ·
  D5 车道闸门复用 · D6 审计两段式 · D7 隔离单位 · D8 载荷模板 · D9 角色→用户映射 · D10 串行 ·
  D11 外部视角跳过 · **D12 报告三段式 · D13 默认车道 skip 闸 · D14 车道目录搬家 · D15 alice 授权 ·
  D16 终态/错误码钉死 · D17 public 守卫换连接 · D18 flock 串行** · 6 条 TODO）
- **VERDICT:** ENG CLEARED — 计划可实施（**16 条 eng-review 发现已全部落进计划或入账 TODO**）；
  **hermes 第三视角复核后追加 11 条发现也已全部落进计划**（含 2 个 P0）⇒ **计划可实施**
- **外部视角:** ⚠️ **eng-review 阶段**跳过（用户裁决 D11）⇒ **但 2026-11-16 补跑了
  hermes 第三视角**（glm-5.2 · Z.AI · 跨模型家族）⇒ **有跨模型结论可比对**
  ⇒ 它判 **partly**（2 个 P0 + 3 个 P1 + 4 个 P2 + 2 个 P3）⇒ **这 11 条已全部折进本计划**
  ⇒ ⇒ **当前计划 = eng-review(16) + 自查(4) + hermes(11) 三路合并后的版本**
- **计划改动:** 架构 5 条 + 代码质量 2 条 + 测试 7 条 + 笔误 2 处 ⇒ 全部已落进本文件并 commit

---

## hermes 第三视角（glm-5.2 · 2026-11-16）

**为什么请它**：跨模型审查的价值在于**不共享盲区** —— 本批的 16 条 eng-review 发现
与 4 条自查错误**全是同一模型家族**发现的 ⇒ 加一路不同家族（glm-5.2）做对抗性复核。
**产物**：`docs/superpowers/plans/reviews/2026-11-13-p10-b-hermes/`（brief + 原始输出 + 解析后的 JSON）。

### 总评（hermes 原话口径）

> partly —— 骨架（车道/种子/隔离/复用清单）扎实，20 条事实里 18 条属实；
> 但有一个 P0（E2E-009/015 的 Redis 依赖使「18 条全绿」当前不可达）和一个 P0 级缺口
> （`e2e` 默认车道 skip 机制缺失会让全量跑打到开发库），加上 E2E-001 的断言前提不存在。
> ⇒ **这三处修完之前不应开工**；修法都是局部的，不动批次结构。

### 新决策（D12~D18）—— hermes 触发的当场裁决

| # | 决策 | 为什么这么定 | 代价（若错） |
|---|---|---|---|
| **D12** | 报告类场景（009/015）改**三段式**：HTTP **503 fail-closed** + **直调 worker 任务体** + 产物断言 | 车道**不引 Redis/worker** ⇒ 两个端点在入队失败时都**抛 503**（不是 202 ⇒ 「先 POST 拿 id 再轮询」走不通）⇒ 轮询到 `SUCCESS` 不可达 ⇒ ⇒ 三段各自独立可失败 | 真链路（HTTP 202 → Redis → worker 消费 → 状态变更）**仍未覆盖** ⇒ 登记 TODO-155 |
| **D13** | `e2e` marker 加**默认车道 skip 闸门**（`PCS_E2E_LANE=1` 才放行） | `addopts` 只有 `-m 'not visual'` ⇒ 不加闸门则批末「跑一次全量」**误伤开发库**且无症状 | 直接 `pytest -m e2e` 会被**全跳**（fail-closed）⇒ README 写明唯一入口 |
| **D14** | 车道搬到 **`tests/e2e_flows/`**（不占 `tests/e2e/`） | `tests/e2e/` 已有 12 条**无 skip** 的既有用例 ⇒ 新 conftest 会改到它们 | 目录名与 SPEC/别的计划里写的 `tests/e2e/` 不一致 ⇒ 以本计划为准 |
| **D15** | 种子给 **`alice` 加授权行**（`bob`/`carol`/`dan` 留作局外人） | mock 登录只认 4 个名字 ⇒ `e2e-*` 登不进去 ⇒ UI 流必须有可登录且有授权的人 | 后端场景里 `alice` 也是 `DESIGNER` ⇒ `role_headers` 必须**只解析 `e2e-*`** |
| **D16** | 状态机断言**钉终态 `CHECKED`** + **钉错误码** | 9 态无 `APPROVED`；「或」判定会让「停在第 2 步」也绿 | 链定义若改（多一级）⇒ 断言要跟着改 |
| **D17** | public schema 守卫改用**独立连接 + 前后快照**，且**在写路径跑过之后**断 | 用被 `search_path` 覆盖的 engine 查 ⇒ **恒绿** ⇒ 隔离承诺是假的 | 守卫变重（要另开一条连接） |
| **D18** | 两条车道用 **`flock -n`** 抢同一把锁 | 「别同时跑」只是叮嘱 ⇒ 竞态照样发生 | `flock` 不可用（极简容器）⇒ 闸门降级为警告（要显式处理，别静默） |

### 11 条漏掉的发现 ⇒ 落点

| 级别 | 发现 | 落点 |
|---|---|---|
| **P0** | E2E-009/015 依赖 ARQ + Redis + worker ⇒ 车道无 Redis ⇒ 两条场景必挂 ⇒ 「≥18 passed」不可达 | **D12** ⇒ **三段式**（HTTP 503 fail-closed + 直调 `generate_report_task` / `execute_definition_task` + 产物断言）⇒ T4 重写<br>⚠️ 复核再修一次：初稿写「202 受理」**是错的** —— 两个端点在入队失败时都**抛 503**（`report.py:196-207` / `report_builder.py:417-432`）⇒ 「先 POST 拿 id 再轮询」**走不通** ⇒ 改成「HTTP 段断 503 + 那行被标 FAILED（不留孤儿）」 |
| **P0** | `e2e` marker **没有默认车道 skip 判据** ⇒ `uv run pytest` 会在**开发库**上建 schema + 跑 alembic + 灌种子 | **D13** ⇒ `tests/e2e_flows/conftest.py` 的 `pytest_collection_modifyitems` 闸门（`PCS_E2E_LANE=1` 才放行）⇒ T1 |
| **P1** | E2E-001 的清单不是「自动生成」⇒ 断言守的是一段不存在的逻辑 | **D27** ⇒ 改「显式 seed 后清单非空」⇒ 与自查 Fix-C **同源**（独立撞上） |
| **P1** | T7 **没有可登录 + 有授权**的用户（`MOCK_USERS` ∩ flows 用户 = ∅） | **D15** ⇒ 种子给 `alice` 加授权行；`bob`/`carol`/`dan` 留作局外人 |
| **P1** | `tests/e2e/` **已被占用** ⇒ 新 conftest 会改掉既有用例的行为 | **D14** ⇒ 车道搬到兄弟目录 `tests/e2e_flows/` |
| **P2** | WF-PATH-01C 的链写错：confirm-recalc 是**传播触发器**不是状态转移 | T5 ⇒ 四步断言（confirm-recalc → `/confirm` → apply-change → 哈希比对） |
| **P2** | WF-PATH-01A 终态写 `APPROVED`（**不存在**）/ `IN_APPROVAL`（或判定太松） | T5 ⇒ 精确断 `CHECKED` + `approval_step is None` |
| **P2** | AUTH-E2E-01/02 **被悄悄替换**：403 来自自审闸而非角色闸 | **D28** ⇒ 矩阵改四元组（断错误码）+ 补 `SYSTEM_ADMIN` 行 |
| **P2** | 缺 `make_deliverable` helper ⇒ 交付物场景共用一条种子交付物 | T5 ⇒ 加 helper（同 D8 的「一处真相源」原则） |
| **P3** | 文件结构表写「AUTH-E2E-01~10/12」与 D24 矛盾 | 文件结构表 ⇒ 改「01~10」 |
| **P3** | 「两条车道不要同时跑」**没有机制** | **D18** ⇒ `flock -n /tmp/pcs-pgtest-lane.lock` |

### 6 条断言形状病 ⇒ 全部改成「断实质，不断形状」

1. 01A 终态 ⇒ 精确断 `CHECKED`（原写法会让「停在第 2 步」也绿）
2. E2E-001 ⇒ 显式 seed 后断**行数 + 字段形状**
3. AUTH 矩阵 ⇒ **断错误码**，不只断状态码（403 有很多种原因）
4. public schema 守卫 ⇒ **独立连接 + 前后快照**（用被覆盖的 engine 查 ⇒ 恒绿）
5. E2E-009/015 轮询 ⇒ **三段独立可失败**（受理 / 执行 / 产物）
6. WF-PATH-01C ⇒ **分步断言**（一跳跨三个端点 ⇒ 字面写必红）

### 8 条交付风险 ⇒ 处置

Redis/worker（→ D12）· 默认车道 skip（→ D13）· `tests/e2e/` 住客（→ D14）·
T7 首跑零手动步骤（→ T7）· 两车道并发（→ D18）· alembic URL 拼接判据（→ T1 照抄现有文件）·
`DROP SCHEMA` 残留（→ T1 起手 `DROP IF EXISTS`）· 角色白名单（→ T1 `role_headers` assert）。

### 它判错的两条（我复核后确认「它是对的」）

| 它说 | 实情 |
|---|---|
| #13 「`tests/e2e/` 是空的」 | **不空** —— `test_sim_three_entry_consistency.py`（12 条用例）在那儿 ⇒ 它的**推论**（新 conftest 会改到既有用例）反而成立 ⇒ 已按它的推论搬目录 |
| #15 「PG 车道不碰 public」 | **PG 车道确实写 public** —— `tests/scripts/test_compose_test_stack_pg.py` 的 seed 跑在**没有 `search_path` 覆盖**的 URL 上 ⇒ 「两条车道互不影响」这句口径要改 |

### 我自己的 4 条（写 brief 时自查发现，与 hermes 撞上 2 条）

| # | 自查发现 | hermes 是否独立撞上 |
|---|---|---|
| A | D4 的**折标煤理由**错：折标系数表是 `config_energy_conversion_factors`（**不是** `pcs_toe_conversion_factors` —— 那是吨油当量表） | 未撞（hermes 没审这一段）⇒ 我复核后**又发现自己的修正也写错了**：真正的名字是 `system_setting_service.seed_defaults` |
| B | E2E-002 的端点错：**没有** `POST /api/v1/imports` ⇒ 真路径是 `projects/{id}/imports/proii/preview` + `/commit` | 未撞 |
| C | E2E-001 的清单不是「自动生成」 | **撞上了**（P1）⇒ 独立同源 ⇒ 置信度高 |
| D | E2E-018 必须**一库一个进程**（CLAUDE.md 口径） | 未撞 |

⚠️ **A 的复核过程本身是个教训**：我把「折标系数由迁移种」这个**结论**查对了（`p7_s3_004` 确实 INSERT 了系数行 ⇒ E2E-008 的折标项不缺），
但把**表名**写错了 ⇒ ⇒ **结论对、依据错** ⇒ 两者都要核对。
⇒ 这也是「开工第一步：逐条核对事实基础」那一步存在的理由。
