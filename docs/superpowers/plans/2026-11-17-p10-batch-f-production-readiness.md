# P10-F 实施计划：生产就绪评审（10.7）· 2026-11-17

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 P10 收在「**可上线**」这个状态上 —— ① 清掉 P10-B 评审遗留的 8 条技术债（**F1/F2**）② 给出物流面外守卫覆盖的**结论**而不是「未审即没问题」（**F3**）③ 把 SPEC §3.2.7 的 10 个评审项逐项**做出来并留证据**（**F4/F5**）④ 收口：部署前置清单 + 偏离回写 + 全量闸门（**F6**）。

**Architecture:** P10-F 是**评审批**，不是功能批 ⇒ ⇒ 它的产出**不是新功能**，而是「**证据 + 清单 + 结论**」⇒ ⇒ 所以每个 Task 的交付物是**可复跑的脚本/文档 + 一条断言**，不是一段新代码。技术债部分（F1/F2）沿用 P10-B 车道的既有形状（隔离 schema + 真 PG + 变异测试），⇒ **不新建第二套验证机制**。

**Tech Stack:** FastAPI · SQLAlchemy 2.x async · alembic · pytest（asyncio_mode=auto）· Playwright · React 18 + antd 5 · docker compose · k6（**P10-D 引入**）· bandit / pip-audit / npm audit / trivy（**F4 引入**）

**Spec:** `spec/PCS-SPEC-P10 V1.3.1 P10 AI预留与测试部署开发规格说明书.md` §3.2.7（10.7 生产就绪评审）· §3.3.1~3.3.3（非功能需求）· 批次划分见 `docs/superpowers/plans/2026-11-04-p10-master-plan.md` §二 / §六 · 本批的前置批次：P10-A（`2026-11-04-p10-batch-a-preflight-ai-reserve.md`）· P10-B（`2026-11-13-p10-batch-b-fullflow-e2e.md`）· 评审与裁决：`docs/ce-code-review/20261117-013829-7e9fbabe/report.md`（末尾「裁决与执行口径」+「执行结果」两节）

---

## 〇、分批与上下文窗口容量（本计划的**结构约束**）

### 为什么分批写，而不是一份大计划

⇒ 本仓的执行方式是 **inline / 单上下文跑完一批**（`superpowers:executing-plans`）⇒ ⇒
⇒ **一份计划的体量必须小于一个上下文窗口能吃下的量**，否则后半程会被压缩 ⇒ ⇒
⇒ 而 P10-F 的内容跨了**前端通道 / 后端契约 / 守门 / 部署 / 演练**五个面 ⇒ ⇒
⇒ 一份写完 ⇒ 必然超窗 ⇒ ⇒ ⇒ **分批 = 分文件**。

### 容量口径（**执行者照此自检**）

| 项 | 口径 |
|---|---|
| **一批的任务数** | **4~6 个** |
| **一批的「必读文件」体量** | **≤ 60k token**（≈ 8~10 个中大型文件，或 20+ 个小文件）⇒ 用 `wc -c` 估：**< 240 KB** |
| **一批的产出** | 一条**可复跑**的证据（脚本/清单/结论）+ 一组断言 ⇒ ⇒ **不是**「一个长会话跑完所有批」 |
| **批间交接** | 每批结束写 `.wolf/STATUS.md` + `TODOS.md` + `.wolf/buglog.json` + 本计划的勾选框 ⇒ ⇒ **下一批从 STATUS 起步**，不从上下文起步 |
| **上下文被压缩后** | **不要**凭记忆续 ⇒ ⇒ 读 `STATUS.md` + 本文件的勾选框 + `git log` |

### 批次地图

| 批 | 主题 | 任务数 | 开工前置 | 现在能开吗 |
|---|---|---|---|---|
| **F1** | P10-B 评审残余（**技术债 · 契约/通道/守门**） | 4 | hermes 第三方裁决落地 | ✅ |
| **F2** | P10-B 评审残余（**技术债 · 隔离/前端/并发**） | 4 | F1 落地 | ✅ |
| **F3** | **守卫覆盖审计**（TODO-129）+ 三条越权债复核 | 5 | 无（车道的审查面已就位） | ✅ |
| **F4** | 生产就绪的**技术项**（安全扫描 · 依赖漏洞 · 镜像扫描 · 回滚演练 · 数据迁移演练） | 6 | **P10-C 落地**（否则没有可扫的镜像/部署物） | ❌ |
| **F5** | 生产就绪的**运维项**（告警演练 · 备份恢复 · 应急联系人 · 上线检查清单 · Go/No-Go） | 5 | **P10-C + P10-E 落地**（否则没有告警、没有 Runbook） | ❌ |
| **F6** | 收口（部署前置清单 TODO-131/137 · SPEC 偏离回写 · 账簿 · 全量闸门） | 4 | F1~F5 全部落地 | ❌ |

⇒ ⇒ **F1/F2/F3 现在就能开**（P10-C/D/E 未开工不阻塞）⇒ ⇒ **F4/F5 要等前批**。

### 每批的「批末闸门」（**全部批适用**）

```bash
# ① 契约（改了 OpenAPI 才需要）
bash pcs-backend/scripts/gate_08_openapi_contract.sh --check-baseline
uv run python pcs-backend/scripts/check_openapi_payload_coverage.py      # 裸载荷不涨
# ② 迁移（改了 alembic/versions 才需要 ⇒ 必须**一库一个进程**）
uv run python pcs-backend/scripts/check_schema_parity.py                  # 每个库 == 代码 head
uv run python pcs-backend/scripts/check_migration_idempotency.py
# ③ 车道
cd pcs-backend && bash scripts/pytest_pg.sh && bash scripts/pytest_e2e.sh
# ④ 前后端全量
cd pcs-backend && uv run pytest
cd pcs-frontend && npm run typecheck && npm run lint && npm run test
cd pcs-frontend && npm run e2e:real && npm run e2e
# ⑤ 浏览器回归报告 ⇒ 落 .gstack/qa-reports/（gitignored ⇒ 关键结论进 TODOS/STATUS）
```

---

## 执行前置（**开工第一步 · 不是可选项**）

- [x] **读 hermes 的第三方裁决**（`docs/ce-code-review/20261117-013829-7e9fbabe/hermes-adjudication.md`，**已落盘**）⇒ ⇒ 那是人**未裁决**的 6 条（#9 / #13 / #17 / #22 / #24 / #27）的第三方意见（**5 条改判 · 1 条修**）⇒ ⇒ **本计划 F1/F2 已按裁决改写**（改写处标「⚖️ hermes」）⇒ ⇒ 开工时若仍与裁决冲突 ⇒ ⇒ **改计划**（不是改实现去迁就计划）⇒ ⇒ 冲突逐条记进账簿。
- [ ] **逐条重核 F1/F2 的「事实基础」**（下表）⇒ ⇒ 事实基础是**写计划时的快照**，不是已核验的真相 ⇒ ⇒ 与当前源码不符 ⇒ **改计划**。
- [ ] **确认前批状态**：`git log --oneline -5` + `.wolf/STATUS.md` ⇒ ⇒ 前批（**F1/F2 的 8 条**）必须已落地且闸门全绿。

### F1/F2 的事实基础（**开工前逐行重核**）

| # | 事实（本计划写于 2026-11-17） | 核验方式 |
|---|---|---|
| #9 | `pcs-frontend/src/pages/routeWrappers.tsx:78-99` 的 `useFetch` **裸 fetch** ⇒ 非 2xx ⇒ `null` ⇒ `.catch(() => {})` 吞网络异常 ⇒ 失败态与「加载中…」同形（`:159-161`）<br>⚖️ hermes：另 4 处裸 `fetch` 里 **2 处是刻意的**（`reportBuilder.ts` blob · `ResultEditDrawer` keepalive）⇒ **不要动**；`AssetListPage.tsx:154` 写死假 token ⇒ 顺手换掉 | 读该文件 9 个 `useFetch<` 调用点 · `src/` 下 grep `fetch(`（应得 5 处） |
| #13 | `pcs-backend/app/api/v1/sim_imports_query.py:323` 的 `-> dict` **无 `response_model`** ⇒ OpenAPI 200 = `{"type":"object"}`；`:360-367` 的注释说「SIM/Excel 存 dict」**与事实相反**（两个写入点都存 list） | 读端点 + `app/services/import_service.py:496` 与 `:612` |
| #17 | `pcs-backend/scripts/seed_e2e_flows.py:513-531` 的种子管级 `dn_series_json={"DN150": 1.0}` / `sch_series_json={"DN150": 40.0}` ⇒ 违反 `PipeClassBase`（`dn_series_json: dict[str,int]` = **{min,max}** · `sch_series_json: dict[str,str]`）⇒ **按 id 查必 500**<br>⚖️ hermes：列表端点**不** 500（`list_company` 固定过滤 `source=='COMPANY_STD'`）⇒ ⇒ 500 只发生在**按 id 取**那一族 | 读 `app/schemas/pipe_class.py:59-64` 与 `_check_dn` 校验器 · `app/services/pipe_class_service.py:150` |
| #22 | `pcs-backend/tests/e2e_flows/test_lane_smoke.py:132` 的 public 基线在 **`e2e_seed` 之后**取；`:235-245` 只数 **4 张表**的 `count(*)`（无 `max(id)`）⇒ ⇒ 种子阶段的泄漏被吸收进基线<br>⚖️ hermes：车道的种子**已是 schema-scoped**（`conftest.py:253`）⇒ ⇒ **车道种子不写 public** ⇒ 「种子前基线」这条对车道**不成立** ⇒ 重心是 ③ `count(*)`-only + ④ **`_sync_engine` 是 #19 漏掉的第三个 singleton** | 读该文件 + `tests/e2e_flows/conftest.py:253` 与 `:324-327` + `app/db/session.py:22-27` |
| #24 | `pcs-frontend/src/pages/DashboardPage.tsx:20` 的 `workspaceProjectId()` 返回 `ws.project_id ?? <占位 id>` ⇒ ⇒ **选了没有 project_id 的工作区** ⇒ 面板仍渲染 ⇒ ⇒ 照旧 404<br>⚖️ hermes：**真后端下选不中它**（种子工作区 `owner_id` 也是 NULL ⇒ 切换器按 `owner_id` 过滤）⇒ ⇒ 「车道会红」**不成立**；但 **mock 种子里 PERSONAL/TEMPORARY 工作区 `project_id` 就是 null** ⇒ ⇒ 生产里**是真缺陷** | 读 DashboardPage + `WorkspaceSwitcher` 的 workspace 形状 + `src/mocks/seed/workspaces.ts:16,29,43` |
| #27 | `pcs-backend/tests/scripts/test_pytest_e2e_gate.py:93-95` 的 flock 守卫读**原文**（含注释）且只断 `"flock"` 存在（不断 `-n`）；同文件 `_body()`（`:32-43`）**会**剥注释 ⇒ 两套口径<br>⚖️ hermes：**另有更硬的新问题** —— `test_pytest_pg_gate.py:165-218` 那条**名叫「默认路径」而实测的是覆盖路径**（`:205` 设了 `PCS_PGTEST_LANE_LOCK`）⇒ ⇒ 默认路径**至今只有一条含注释的原文子串守卫** | 读该文件 + `scripts/pytest_pg.sh` 的 `flock -n 9` + `test_pytest_pg_gate.py:165-218` |
| #15① | compose 的 `migrate`（`docker-compose.yml:101-122`）与 `seed`（`:123-145`）**不经** `scripts/pytest_pg.sh` ⇒ ⇒ 不在车道锁内 | 读 compose 两个服务 + `scripts/pytest_pg.sh` 的锁段 |
| TODO-162 | `pcs-frontend/src/pages/config/FormulaEditorPage.tsx:241` 的 `rowKey={(_r, idx) => String(idx)}` ⇒ antd 5.29 起弃用 index 参数 ⇒ 控制台**错误级**告警 ⇒ 真后端通道的扫描把它列入白名单（TODO-162） | 读该行 + `e2e/real_backend_route_sweep.spec.ts` 的 `ALLOWED_CONSOLE_ERRORS` |

---

## Global Constraints

- **分支 `main`，不要建 worktree**；**conventional commits**；长消息写文件后 `git commit -F <file>`。
- ⚠️ **口令不要写在命令行**（只在环境变量 / 进程内派生）；⚠️ **不要用 `git checkout <commit> --detach`**。
- ⚠️ **本批不新建 CI 流水线**（既有裁决）⇒ ⇒ SPEC §3.2.0(2) 的「E2E 在 CI 中可自动执行」**仍不满足** ⇒ ⇒ 继续登记偏离（**不要**在 F5/F6 的「上线检查清单」里写「CI 会跑」⇒ ⇒ 那是**事实错误**）。
- ⚠️ **PG 车道唯一入口是 `scripts/pytest_pg.sh`**；**E2E 车道唯一入口是 `scripts/pytest_e2e.sh`** ⇒ ⇒ **两条车道不并发**（同一库 ⇒ DDL 等锁 ⇒ 表现是「偶发卡住」）⇒ ⇒ 锁在 `pcs-backend/.tmp/lane.lock`（项目内 ⇒ `/tmp` 会被清理 ⇒ inode 换新 ⇒ 互斥静默失效 ⇒ 评审 #15 第 ② 步）。
- ⚠️ **单测车道绝不碰开发库** ⇒ ⇒ 默认车道只用内存 SQLite ⇒ ⇒ 任何「要看真库」的检查（两库 schema / 部署前置清单）**必须**是**独立进程 + 只读**（`scripts/check_schema_parity.py` 是样板）。
- ⚠️ **改 `alembic/versions/*` ⇒ 必须手核 ORM 列**（CLAUDE.md 的「漂移盲区」）⇒ ⇒ 本批（除 #15① 外）**不改迁移** ⇒ ⇒ 不跑 `alembic check` 也不滚迁移 baseline。
- 契约改动 ⇒ 批末滚 OpenAPI baseline + G-08 `--check-baseline`；**裸载荷数不得上涨**（基线 ≤ 71 ⇒ 当前 42）。
- 前端类型**契约派生** ⇒ 后端加字段后重跑 `npm run api:gen` + 同步 MSW mock。
- ⚠️ **每批落地后必须跑浏览器回归**（CLAUDE.md）⇒ ⇒ 报告落 `.gstack/qa-reports/`（gitignored ⇒ **关键结论必须同步进 `TODOS.md` / `STATUS.md`**，否则报告随磁盘蒸发）。
- ⚠️ **F4/F5 是「演练」批** ⇒ ⇒ 演练的结论**必须区分**「真跑过」与「按步骤跑通」⇒ ⇒ 清单里每项写「**证据链接**（命令 + 输出）」⇒ ⇒ **不许**用「已验证」这种没有证据的措辞。
- ⚠️ **不许在评审批里偷偷加功能** ⇒ ⇒ F4/F5/F6 的产出是**证据与清单** ⇒ ⇒ 若发现要改产品代码 ⇒ ⇒ 登记 TODO，**另开批次**（本批不顺手做）。

---

## Review Focus

以下五类情形 SPEC 要求、但**没有现成测试**，最可能咬到真实用户；每条都在对应 Task 里落成测试。

1. **守卫覆盖的「未审即没问题」** —— 物流面外的模块（`config.py` / `report_builder.py` / `psychro.py` …）的守卫覆盖面**没人审过** ⇒ ⇒ 一个「跨项目访问」可能在那里畅通 ⇒ ⇒ **F3** 必须给出**结论**（缺口逐条登记 TODO），不能留空白（F3-T1）。
2. **token 过期后前端**「加载中…」**停住、且零提示** —— access token 30 分钟过期（`app/core/config.py:46`）⇒ ⇒ 裸 `fetch` 通道不处理 401 ⇒ ⇒ 用户看到的是「加载中」而不是「请重新登录」
   ⇒ ⇒ ⚖️ hermes：**不是「永久卡死」**（token 仅存内存 ⇒ 刷新即重登 ⇒ 可恢复）⇒ ⇒ 但**每个用户每个会话 30 分钟后必遇**
   ⇒ ⇒ **F1-T1** 必须让「失败态」与「加载态」**长得不一样**，且 401 处理与 axios **同一份真相源**。
3. **种子/回写路径让「契约可读性」失真** —— 客户端拿到 `{"type":"object"}` 的 200 ⇒ ⇒ 只能靠试 ⇒ ⇒ 契约必须写出形状（**F1-T2**）；种子造的行违反同一份契约 ⇒ ⇒ 按 id 查就 500（**F1-T3** ⇒ ⇒ ⚖️ hermes：列表端点**不** 500，只有**按 id 取**那一族 ⇒ ⇒ 但**改脚本不修已种下的老行** ⇒ ⇒ 老行订正同样是钉子）。
4. **「隔离」这件事本身被宣称、但覆盖面远小于宣称** —— 守卫只数 4 张表、只断 `count(*)` ⇒ ⇒ **同表替换/更新**看不见 ⇒ ⇒ 一个合理的人会认为「E2E 不写开发库」已被证明 ⇒ ⇒ **F2-T1** 必须扩覆盖面 + 加 `max(<pk>)` + 补 `_sync_engine` 这个第三个 singleton。
5. **「已就绪」这句话本身** —— 上线检查清单里的每一项若没有**可复跑的命令 + 输出**，就等于没验 ⇒ ⇒ **F5/F6** 的清单每行都要带证据 ⇒ ⇒ 不许写「已验证」而没有命令。

---

---

# F1 · P10-B 评审残余（技术债 · 契约 / 通道 / 守门）

> **本批前置**：hermes 的第三方裁决落地（`hermes-adjudication.md`）⇒ ⇒ 冲突 ⇒ **改计划**。
> **本批产出**：4 条技术债落地 + 各自的断言 ⇒ ⇒ **批末闸门全绿**。

### Task F1-T1: `useFetch` 的**失败态** + **401 与 axios 同一份真相源**（评审 #9 · 前端通道）

> ⚖️ **hermes 改判**：①「永久卡死」不成立（token 仅存内存 ⇒ 刷新即重登 ⇒ 可恢复）⇒ 优先级 **P2**
> ② ⚠️ **不要直接把 `useFetch` 换成 axios** —— `api` 的 `baseURL` 已含 `/api/v1`（`client.ts:4,6`），
> 而 9 个 path **也都带 `/api/v1`** ⇒ ⇒ 直接换 ⇒ **9 条路径全部 404**
> ⇒ ⇒ **正确修法**：把 `client.ts` 的 401 判定**抽成共享函数**，`useFetch` 的 `!r.ok` 分支调它
> ③ **顺手**换掉 `AssetListPage.tsx:154` 的写死 `DEV_BEARER`（bug-2169 的双胞胎）
> ④ **不要**动 `api/reportBuilder.ts` 与 `pages/results/ResultEditDrawer.tsx`（两处裸 fetch 是**刻意**的，
> 各自自带失败语义 ⇒ 动它们会破坏已被注释记录的理由）

**Files:**
- Modify: `pcs-frontend/src/api/client.ts:51-66`（**抽出** `handleSessionOver(status, code)`）
- Modify: `pcs-frontend/src/pages/routeWrappers.tsx:76-99`（`useFetch`）· `:159-161`（`StreamDetailRoute`）· 另 8 个 `useFetch<` 调用点（`:107` `:169` `:181` `:185` `:189` `:212` `:331` `:335`）
- Modify: `pcs-frontend/src/pages/config/AssetListPage.tsx:153-154`（`DEV_BEARER` ⇒ 会话 token）
- Test: `pcs-frontend/tests/pages/routeWrappers.fetch.test.tsx`（**新建** ⇒ 形状照 `pcs-frontend/tests/pages/` 下既有测试：vitest + `@testing-library/react` + `vi.stubGlobal('fetch', …)`）
- Modify: `pcs-frontend/e2e/real_backend_route_sweep.spec.ts`（**白名单不动** ⇒ 本任务不引入新的控制台 error ⇒ 若引入 ⇒ 说明实现错了）

**Interfaces:**
- Consumes: `pcs-frontend/src/store/auth.ts`（`useAuth.getState().accessToken` · `clearSession()`）· `client.ts` 的 `SESSION_OVER_CODES` 白名单
- Produces:
  - `handleSessionOver(status: number, code?: string): void` —— 导出于 `src/api/client.ts` ⇒ ⇒ **axios 通道与 `useFetch` 通道共用这一份** ⇒ ⇒ 401/会话过期 ⇒ 清会话 + 跳 `/login`
  - `useFetch<T>(path: string, initial: T): { data: T; error: string | null; loading: boolean }` —— **返回值从 `T` 改成对象** ⇒ ⇒ 9 个调用点全部改 ⇒ ⇒ **这是本任务唯一的跨文件契约** ⇒ ⇒ 后续任务（F2）若也要动 `useFetch`，一律用这个新签名。

- [ ] **Step 1: 写失败测试**（`pcs-frontend/tests/pages/routeWrappers.fetch.test.tsx`）

```ts
it('fetch 500 ⇒ 页面显示「加载失败」而不是「加载中…」', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 500 }));
  render(<StreamDetailRoute />, { wrapper: MemoryRouter });
  expect(await screen.findByText(/加载失败/)).toBeInTheDocument();
  expect(screen.queryByText('加载中…')).not.toBeInTheDocument();
});

it('fetch 抛网络异常 ⇒ 同样进入失败态（不被吞掉）', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')));
  render(<StreamDetailRoute />, { wrapper: MemoryRouter });
  expect(await screen.findByText(/加载失败/)).toBeInTheDocument();
});

it('fetch 401 ⇒ 与 axios 通道同一份真相源（清会话 + 跳 /login）', async () => {
  const clearSession = vi.fn();
  vi.mocked(useAuth.getState).mockReturnValue({ ...session, clearSession } as never);
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 401 }));
  render(<StreamDetailRoute />, { wrapper: MemoryRouter });
  await waitFor(() => expect(clearSession).toHaveBeenCalled());
});
```

⇒ ⇒ ⚠️ **第三条是本条的钉子**：它断的是「401 处理**只有一份**」⇒ ⇒ 删掉 `useFetch` 里的
`handleSessionOver` 调用 ⇒ ⇒ 测试必须红（**变异敏感**）。

- [ ] **Step 2: 跑测试确认失败**

Run: `cd pcs-frontend && npm run test -- tests/pages/routeWrappers.fetch.test.tsx`
Expected: FAIL（现在只有「加载中…」，找不到「加载失败」；401 分支也不清会话）

- [ ] **Step 3: 抽出共享的 401 处理**（`src/api/client.ts:51-66`）

⇒ 把现有 401 分支的逻辑原样搬进 `export function handleSessionOver(status: number, code?: string): void`
⇒ ⇒ **axios 拦截器改为调它** ⇒ ⇒ 行为**不变**（回归由既有 axios 测试守着）⇒ ⇒
⚠️ `SESSION_OVER_CODES` 白名单的语义**照搬**（有些 401 不该跳登录页 ⇒ 照现有实现，别改口径）。

- [ ] **Step 4: 实现 `useFetch` 的失败态**（`src/pages/routeWrappers.tsx:76-99`）

⇒ 签名改为 `{ data, error, loading }`；⇒ `fetch` 用 **`AbortController`**（cleanup 里 `abort()`）+
**15s 超时**（`setTimeout` ⇒ cleanup 里 `clearTimeout`）；⇒ `!r.ok` ⇒
**先** `if (r.status === 401) handleSessionOver(r.status)` ⇒ ⇒ **再** `error = \`HTTP ${r.status}\``；
`catch` ⇒ `error = '网络错误'`（**不吞**）。

⇒ `StreamDetailRoute`（`:159-161`）：`if (loading) return <Typography.Text>加载中…</Typography.Text>;`
`if (error) return <Alert type="error" message={`加载失败：${error}`} />;`

- [ ] **Step 5: 改 9 个调用点**（同一文件）⇒ ⇒ 每个写成
`const { data, loading, error } = useFetch<T>(path, initial)` ⇒ ⇒ **不要**改各页面的渲染逻辑
（只把 `data` 换成解构出来的 `data`）⇒ ⇒ ⚠️ `StreamDetailRoute` 额外加失败态（Step 4）。

- [ ] **Step 6: 换掉 `AssetListPage` 的写死 token**（`src/pages/config/AssetListPage.tsx:153-154`）

⇒ `DEV_BEARER` ⇒ `useAuth.getState().accessToken`（照 `routeWrappers.tsx:85-86` 的写法）⇒ ⇒
⚠️ 提交信息里写明：「`GET /api/v1/config/assets/{id}/revisions` **后端尚不存在**（今天 404）⇒ ⇒
端点补齐那天这条必须仍成立」。

- [ ] **Step 7: 跑测试确认通过 + 变异自证**

Run: `cd pcs-frontend && npm run test -- tests/pages/routeWrappers.fetch.test.tsx && npm run typecheck && npm run lint`
Expected: 新测试 PASS · typecheck/lint clean

⇒ ⇒ **变异自证**：临时删掉 Step 4 里的 `handleSessionOver(r.status)` 调用 ⇒ ⇒ 重跑 ⇒ ⇒
「401 ⇒ 清会话」那条**必须红** ⇒ ⇒ 还原。

- [ ] **Step 8: 跑真后端通道**（**白名单外必须为空**）

Run: `cd pcs-frontend && npm run e2e:real`
Expected: 7+ passed（路由扫描的 4xx/console 白名单**不变** ⇒ ⇒ 本任务没引入新的 404）

- [ ] **Step 9: 提交**

```bash
cd pcs-frontend && git add src/api/client.ts src/pages/routeWrappers.tsx \
        src/pages/config/AssetListPage.tsx tests/pages/routeWrappers.fetch.test.tsx
git commit -m "fix(P10-F): useFetch 失败态 + 401 与 axios 共用真相源（评审 #9）"
```

---

### Task F1-T2: `preview-streams` 的**契约形状**（评审 #13 · 后端契约）

**Files:**
- Modify: `pcs-backend/app/api/v1/sim_imports_query.py:323`（端点签名）· `:360-367`（**与事实相反的注释**）
- Create: `pcs-backend/app/schemas/sim_import.py`（新文件 ⇒ 只放这一个响应模型 ⇒ 名字 `SimImportPreviewStreamsResponse`）
- Modify: `pcs-frontend/src/types/api.d.ts`（**由 `npm run api:gen` 生成 ⇒ 不手改**）
- Test: `pcs-backend/tests/api/v1/test_sim_imports_query_endpoints.py`（**既有文件** ⇒ 加一条）

**Interfaces:**
- Consumes: `app/schemas/pipe_class.py` 的**具名 schema 风格**（`Field(..., description=…)` + `model_config`）⇒ ⇒ 新模型照抄那个风格。
- Produces: `SimImportPreviewStreamsResponse(streams: list[dict[str, Any]] = [])` ⇒ ⇒ **OpenAPI 里 200 的形状**从 `{"type":"object"}` 变成 `{"streams": [...]}` ⇒ ⇒ **契约破坏性变化**（前端生成类型变具体）⇒ ⇒ 批末**必须滚 baseline**。

- [ ] **Step 1: 写失败测试**（加到 `tests/api/v1/test_sim_imports_query_endpoints.py`）

```python
async def test_preview_streams_response_model_declares_the_streams_key(client, ...):
    """契约里必须能读到 `streams` 键 ⇒ 客户端不必靠试。"""
    schema = client.app.openapi()["paths"]["/api/v1/imports/{import_id}/preview-streams"]["get"]
    ref = schema["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
    assert ref.endswith("SimImportPreviewStreamsResponse")
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd pcs-backend && uv run pytest tests/api/v1/test_sim_imports_query_endpoints.py -q`
Expected: FAIL（现在 200 是 `{"type":"object"}` ⇒ 没有 `$ref`）

- [ ] **Step 3: 实现**

① `app/schemas/sim_import.py`：

```python
class SimImportPreviewStreamsResponse(BaseModel):
    """preview 阶段的 streams 列表（`GET /imports/{id}/preview-streams` 的 200）。"""
    streams: list[dict[str, Any]] = Field(default_factory=list, description="preview 阶段的物流列表")
```

② 端点签名改成 `-> SimImportPreviewStreamsResponse`（`response_model` 由返回注解推导 ⇒ ⇒ **不要**再写
`response_model=`）⇒ ⇒ 返回体改成 `SimImportPreviewStreamsResponse(streams=payload if isinstance(payload, list) else payload.get("streams", []))`。

③ **改注释**（`:360-367`）：「**PRO/II 与 EXCEL 两个写入点都存 list** ⇒ 读侧统一归一成 `{"streams": [...]}`」
⇒ ⇒ **删掉**「SIM/Excel 导入存 dict」那句（与事实相反）。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd pcs-backend && uv run pytest tests/api/v1/test_sim_imports_query_endpoints.py -q`
Expected: PASS

- [ ] **Step 5: 滚契约 + 同步前端类型**（**顺序不能反**）

```bash
cd pcs-frontend && npm run api:gen
cd ../pcs-backend && uv run python scripts/export_openapi.py
bash scripts/gate_08_openapi_contract.sh --check-baseline   # 会报漂移 ⇒ 按该脚本的提示滚 baseline
uv run python scripts/check_openapi_payload_coverage.py        # 裸载荷不涨（≤ 71）
```

⇒ ⇒ ⚠️ 滚 baseline 前**先看 diff** ⇒ ⇒ 若 diff 超出「`streams` 键 + 类型变具体」⇒ ⇒ **停下**，说明契约漂移超预期 ⇒ 登记 TODO。

- [ ] **Step 6: 提交**

```bash
git add pcs-backend/app/schemas/sim_import.py pcs-backend/app/api/v1/sim_imports_query.py \
        pcs-backend/tests/api/v1/test_sim_imports_query_endpoints.py \
        pcs-frontend/src/types/api.d.ts pcs-backend/docs/openapi.json \
        pcs-backend/docs/openapi-baseline.json pcs-frontend/openapi.snapshot.json
git commit -m "feat(P10-F): preview-streams 补 response_model（评审 #13）⇒ 契约写出形状"
```

---

### Task F1-T3: 种子的管级**按契约造** + **订正已种下的老行**（评审 #17 · 后端数据）

> ⚖️ **hermes 改判**：① 「必 500」范围**收窄** —— `list_company` 固定过滤 `source=='COMPANY_STD'`
> ⇒ **列表端点不 500**（前端管级列表没坏）⇒ ⇒ 500 只发生在**按 id 取**那一族
> ② ⚠️ **报告漏了一步** —— 种子是 `_get_or_create`（**存在就不动**）⇒ ⇒ **改脚本不修已种进
> pcs_pgtest public 的老行** ⇒ ⇒ 必须显式订正 ⇒ ⇒ 否则「修了」但现象照旧
> ③ `source` 改成 `COMPANY_STD` ⇒ ⇒ **该行会出现在公司管级列表里** ⇒ ⇒ **产品决定**（登记 TODO，不在本条代决）

**Files:**
- Modify: `pcs-backend/scripts/seed_e2e_flows.py:504-531`（`_ensure_pipe_class` 的行形状 + **老行订正**）
- Test: `pcs-backend/tests/scripts/test_seed_e2e_flows.py`（**既有** ⇒ 加一条）· `pcs-backend/tests/e2e_flows/test_e2e_pipe_class_lookup.py`（**新建** ⇒ 「按 id 查不 500」）
- Modify: `TODOS.md`（登记「公司管级列表里出现 E2E 种子管级」的产品待决项）

**Interfaces:**
- Consumes: `app/schemas/pipe_class.py::PipeClassResponse`（`dn_series_json: dict[str,int]` = **{"min","max"}** · `sch_series_json: dict[str,str]` = **DN→Sch 字符串** · `source: Literal["COMPANY_STD","PROJECT"]`）
- Produces: 种子行的形状与 `alembic/versions/p10_002_seed_placeholder_pipe_class.py:41-55` 的 `CS-STD` **同款** ⇒ ⇒ 两处占位行形状一致（评审 #2 的纪律）。

- [ ] **Step 1: 写失败测试**（`tests/scripts/test_seed_e2e_flows.py`）

```python
async def test_seed_pipe_class_row_matches_the_response_contract(db_session):
    """种子管级必须**能被 PipeClassResponse 校验** ⇒ 否则按 id 查必 500。"""
    await seed_flows(db_session)
    row = (await db_session.execute(
        select(PipeClass).where(PipeClass.class_id == FLOW_PIPE_CLASS_ID)
    )).scalar_one()
    validated = PipeClassResponse.model_validate(
        {c.name: getattr(row, c.name) for c in PipeClass.__table__.columns}
    )   # ← 违反契约时抛 ValidationError
    assert validated.dn_series_json == {"min": 150, "max": 150}
    assert validated.sch_series_json == {"DN150": "40"}
```

⇒ ⇒ ⚠️ **断的是契约本身**（`PipeClassResponse.model_validate`）⇒ ⇒ **不要**手写一份副本比对
（副本会跟契约一起漂）⇒ ⇒ 依据 `docs/solutions/testing-issues/guard-test-fooled-by-lying-comment.md` §4。

- [ ] **Step 2: 跑测试确认失败**

Run: `cd pcs-backend && uv run pytest tests/scripts/test_seed_e2e_flows.py -q`
Expected: FAIL（`dn_series_json` 缺 `min`/`max` ⇒ `ValidationError`）

- [ ] **Step 3: 改种子的行形状**（`scripts/seed_e2e_flows.py:504-531`）

⇒ `dn_series_json={"min": 150, "max": 150}`（**int**）· `sch_series_json={"DN150": "40"}`（**字符串**）
· `source="COMPANY_STD"`（⚠️ **不扩 `Literal`** ⇒ 遵守 #2 裁决）

⇒ ⇒ ⚠️ **别把 `material_class` 改指 `CS-STD`**（会牵动 `FLOW_PIPE_CLASS_ID` 这个导出常量 ⇒ 改动面更大 ⇒ 不取）。

- [ ] **Step 4: 订正已种下的老行**（同文件，**幂等**）

⇒ `_ensure_pipe_class` 在 `_get_or_create` 命中已有行时 ⇒ ⇒ **也要把形状订正过来**
（`dn_series_json` / `sch_series_json` / `source` 三列）⇒ ⇒ 否则 pcs_pgtest public 里那行**照旧 500**。
⇒ ⇒ 或等价做法：给脚本加 `--reset` 并把「批末重灌」写成动作 ⇒ ⇒ **二选一，写进提交信息**。

- [ ] **Step 5: 跑测试确认通过**

Run: `cd pcs-backend && uv run pytest tests/scripts/test_seed_e2e_flows.py -q`
Expected: PASS

- [ ] **Step 6: 加 PG 侧的「按 id 查不 500」**（`tests/e2e_flows/test_e2e_pipe_class_lookup.py`）

⇒ `GET /api/v1/pipe-classes/E2E-SEED-CS`（**按 id**）⇒ **200** ⇒ ⇒ 且响应体的 `dn_series_json` 形状正确
⇒ ⇒ ⚠️ **这条必须在 E2E 车道跑**（SQLite 不强制 FK ⇒ 单测照绿 ⇒ 真库才炸 ⇒ 评审 #17 的形状）
⇒ ⇒ 顺带断 `GET /api/v1/pipe-classes`（列表）**仍 200**（改 `source` 后它**会**含这行 ⇒ ⇒ 断言它**在**列表里 ⇒ ⇒ 把行为钉死，不留给下一个人猜）。

- [ ] **Step 7: 跑 E2E 车道**

Run: `cd pcs-backend && bash scripts/pytest_e2e.sh`
Expected: 全绿（含新增两条）

- [ ] **Step 8: 登记产品待决项 + 提交**

⇒ ⇒ `TODOS.md` 加一条：「公司管级列表里要不要出现『E2E 种子管级』（`source="COMPANY_STD"` 的副作用）？」（**交人裁决**）

```bash
git add pcs-backend/scripts/seed_e2e_flows.py pcs-backend/tests/scripts/test_seed_e2e_flows.py \
        pcs-backend/tests/e2e_flows/test_e2e_pipe_class_lookup.py TODOS.md
git commit -m "fix(P10-F): 种子管级按 PipeClassResponse 造 + 订正老行（评审 #17）"
```

---

### Task F1-T4: 三条**守门测试**统一断「可执行部分」+ 断 `flock -n`（评审 #27）

> ⚖️ **hermes 改判**：① #15③ 已落地**行为级**互斥实测 ⇒ ⇒ 报告「互斥无证据」**今天不成立**
> ⇒ 优先级 **P2**（但不是因为报告给的理由）
> ② ⚠️ **更硬的新问题** —— `test_pytest_pg_gate.py:165-218` 那条**名叫
> `..._on_the_default_path` 而实测的是覆盖路径**（`:205` 设了 `PCS_PGTEST_LANE_LOCK`）
> ⇒ ⇒ 它**没测它命名的东西** ⇒ ⇒ **默认路径 `.tmp/lane.lock` 至今只有一条含注释的原文子串守卫**
> ③ **不要**把它改成「真占默认路径」（会与真车道抢同一把锁 ⇒ 撞「守门测试与被守机制共享资源」，
> 正是 `docs/solutions/testing-issues/guard-test-must-use-its-own-lane-lock.md` 记的病）
> ⇒ ⇒ **正确做法**：**改名**（诚实）+ **另写**一条默认路径的**静态**守卫

**Files:**
- Modify: `pcs-backend/tests/scripts/test_pytest_e2e_gate.py:32-43`（`_body()` **参数化**）· `:84-99`（flock 守卫）
- Modify: `pcs-backend/tests/scripts/test_pytest_pg_gate.py:136-146`（唯一入口守卫）· `:149-163`（默认锁路径守卫）· `:165-218`（**改名** + docstring 改诚实）
- Create: `pcs-backend/tests/scripts/lane_script_body.py`（**一处真相源**）

**Interfaces:**
- Consumes: `scripts/pytest_pg.sh` 的锁段（`exec 9>"$LOCK_FILE"` + `if ! flock -n 9; then`）
- Produces: `lane_script_body(script: Path) -> str` —— **剥掉注释后的可执行部分** ⇒ ⇒ 两个测试文件共用它
  ⇒ ⇒ 依据 `docs/solutions/testing-issues/guard-test-must-use-its-own-lane-lock.md` §4（「同一个文件里两套口径 ⇒ 至少要一致」）。

- [ ] **Step 1: 写失败测试**（改 `test_pytest_pg_gate.py` 的 flock 守卫）

```python
def test_lane_script_serializes_with_nonblocking_flock():
    body = lane_script_body(PG_SCRIPT)          # ← 剥注释
    assert "flock -n" in body, "flock 必须是**非阻塞**版（-n）⇒ 否则并发时排队卡住"
    assert "exec 9>" in body, "必须锁住 fd 9 ⇒ 整个脚本生命周期都持锁"
```

⇒ ⇒ **默认锁路径**那条守卫也改成剥注释口径，并**加严**：

```python
def test_default_lock_path_is_inside_the_project_not_tmp():
    body = lane_script_body(PG_SCRIPT)
    assert "/tmp/pcs-pgtest-lane.lock" not in body, (
        "默认锁路径还在 /tmp ⇒ 清理后 inode 换新 ⇒ 互斥静默失效（评审 #15）"
    )
    assert ".tmp/lane.lock" in body, "默认锁路径应是项目内的 .tmp/lane.lock（评审 #15）"
    assert "flock -n" in body and "exec 9>" in body, (
        "默认路径只能静态断 ⇒ 就必须断得严：非阻塞 + 锁 fd"
    )
```

⇒ ⇒ **唯一入口**那条（`:136-146`）也改成对**剥注释后**的文本计数（`body.count("uv run pytest") == 2` ⇒ **断言值不变**）。

- [ ] **Step 2: 跑测试确认失败**

Run: `cd pcs-backend && uv run pytest tests/scripts/test_pytest_pg_gate.py tests/scripts/test_pytest_e2e_gate.py -q`
Expected: FAIL（当前读的是**原文** ⇒ 「`flock -n`」/「`exec 9>`」的断言拿不到）

- [ ] **Step 3: 实现**（新建 `tests/scripts/lane_script_body.py`）

```python
def lane_script_body(script: Path) -> str:
    """脚本的**可执行部分**（去掉注释）—— 断「脚本有没有做这件事」必须断这里。"""
    lines: list[str] = []
    for line in script.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("#"):
            continue
        lines.append(line.split("#", 1)[0])
    return "\n".join(lines)
```

⇒ ⇒ `test_pytest_e2e_gate.py` 的本地 `_body()` **删掉** ⇒ ⇒ 改成 `from tests.scripts.lane_script_body import lane_script_body`
⇒ ⇒ ⚠️ `test_pytest_pg_gate.py` 里的 `_body()`（若已存在）也一并删 ⇒ ⇒ **一处真相源**。

- [ ] **Step 4: 改名 + 改 docstring**（`test_pytest_pg_gate.py:165-218`）

⇒ `test_two_lanes_are_mutually_exclusive_on_the_default_path` ⇒ ⇒
**`test_two_lanes_are_mutually_exclusive_on_an_overridden_lock_path`**
⇒ ⇒ docstring 里那句「**默认路径**下两条车道真的互斥」⇒ ⇒ 改成「**覆盖路径**（`PCS_PGTEST_LANE_LOCK`）下互斥；
**默认路径**只能静态断（不能真占默认锁 ⇒ 会与真车道抢锁）」。

- [ ] **Step 5: 跑测试确认通过 + 变异自证**

Run: `cd pcs-backend && uv run pytest tests/scripts/test_pytest_pg_gate.py tests/scripts/test_pytest_e2e_gate.py -q`
Expected: PASS

⇒ ⇒ **变异自证**（两条都要红）：
① 把 `pytest_pg.sh` 的 `flock -n 9` 改成 `flock 9`（阻塞版）⇒ ⇒ 守卫**必须红**
② 把 `.tmp/lane.lock` 改回 `/tmp/...` ⇒ ⇒ 守卫**必须红**
⇒ ⇒ 两条都还原后再进 Step 6。

- [ ] **Step 6: 提交**

```bash
git add pcs-backend/tests/scripts/lane_script_body.py pcs-backend/tests/scripts/test_pytest_pg_gate.py \
        pcs-backend/tests/scripts/test_pytest_e2e_gate.py
git commit -m "fix(P10-F): 守门测试统一断可执行部分 + 默认路径断 flock -n（评审 #27）"
```

---

# F2 · P10-B 评审残余（技术债 · 隔离 / 前端 / 并发）

> **本批前置**：F1 落地（若 hermes 裁决把 F1 的某条改判 ⇒ 先改本批）。
> **本批产出**：4 条技术债落地 ⇒ ⇒ **批末闸门全绿**。

### Task F2-T1: 「不写 public」守卫**扩覆盖面** + **补第三个 singleton** + **session 级基线**（评审 #22）

> ⚖️ **hermes 改判**：① 「种子前基线」对车道**已失效** —— 车道的种子**已是 schema-scoped 引擎**
> （`tests/e2e_flows/conftest.py:253`）⇒ ⇒ **车道种子不写 public** ⇒ ⇒ 原计划那条「基线前置到种子前」
> **作废** ⇒ ⇒ 改为「**车道启动时取一次 / 车道结束再取一次**」的 session 级基线
> （`e2e_schema` fixture 已是 session scope，`conftest.py:166-167`）⇒ ⇒ 比「单条写路径前后」更强，
> 且能覆盖 #19 之外的新写路径
> ② ⚠️ **真盲区**是「**同表内的替换与更新都看不见**」（守卫只断 `count(*)`）⇒ ⇒ 必须加 `max(<pk>)`
> ③ ⚠️ **`_sync_engine` 是 #19 漏掉的第三个 singleton**（`app/db/session.py:22,27-39`）⇒ ⇒ #19 只覆写了
> 两个 async 的 ⇒ ⇒ 任何走 `get_engine()` 的路径在车道里读写的是 public ⇒ ⇒ 今天**没有**活的泄漏路径
> （`get_engine()` 只被 `session.py:42 check_database()` 用，health 走 async 版）⇒ ⇒ 是**未来泄漏点**
> ④ ⚠️ `max(id)` 那句要**逐表核 PK 列名**（本仓 PK 列名不统一 ⇒ 照抄 `max(id)` 会**恒为 0** ⇒ 等于没加）
> ⑤ ⚠️ `public.` **显式限定是对的**（`information_schema` 不受 `search_path` 约束）⇒ ⇒ **不要**改成 `current_schema()`

**Files:**
- Modify: `pcs-backend/tests/e2e_flows/test_lane_smoke.py:102-157`（守卫）· `:234-243`（`_public_snapshot`）
- Modify: `pcs-backend/tests/e2e_flows/conftest.py:324-327`（**扩到 `_sync_engine`**）· 加 session 级 public 基线 fixture

**Interfaces:**
- Consumes: `scripts/seed_e2e_flows.py` 实际写的表清单（**以代码为准** ⇒ 开工时用
`grep -oE "(Workspace|Project|UserProject|Stream|PipeClass|EquipmentTypeCode|Equipment|SignatureMatrix|ProjectSignatureMatrixBinding|Deliverable|PipingResult|ReportDefinition|CoefficientTable|SystemSetting)" scripts/seed_e2e_flows.py | sort -u` 取）
  ⚠️ **不要手抄** ⇒ ⇒ 但也要知道：**手抄一次就漂一次** ⇒ ⇒ 把「表清单」**写成仓库里的一份清单文件**
  （如 `tests/e2e_flows/lane_written_tables.py`）⇒ ⇒ 至少漂的时候**只改一处** ⇒ ⇒ 登记 TODO：
  「结构性的解法是从 ORM 模型集合 ∪ 迁移建表清单推出来，而不是第二次手抄」
- Produces: `public_snapshot(engine) -> dict[str, tuple[int, int]]`（每张表 **count(\*) + max(<pk>)**）
  ⇒ ⇒ 断言「session 启动时 == session 结束时」⇒ ⇒ **逐张相等**

- [ ] **Step 1: 写失败测试**（**先证伪现守卫**）

⇒ ⇒ 加一条**自检**：故意往 public 写一行 / 改一行 / 删一行（用**独立连接**）⇒ ⇒ 守卫**必须红**
⇒ ⇒ 证明「它看得见泄漏」（守门测试自证 ⇒ 同族纪律：`docs/solutions/testing-issues/guard-test-fooled-by-lying-comment.md`）。

```python
@pytest.mark.e2e
async def test_public_guard_detects_a_leaked_row(public_engine, lane_written_tables):
    """守卫自证：往 public 写一行 ⇒ 快照必须变化 ⇒ 否则它是空壳。"""
    table = lane_written_tables[0]                    # ← 守卫覆盖范围内的表
    pk = lane_written_tables_pk[table]
    before = public_snapshot(public_engine)
    with public_engine.begin() as conn:
        conn.execute(text(f"INSERT INTO public.{table} ..."))   # ← 用该表的最小可插列
    after = public_snapshot(public_engine)
    assert before[table] != after[table]
```

- [ ] **Step 2: 跑测试确认失败**（现快照只数 4 张表 ⇒ 探针写进别的表 ⇒ 看不见 ⇒ 失败）

- [ ] **Step 3: 实现**
① `_public_snapshot` 扩到**车道会写的全部表** + 每张断 `count(*)` 与 `max(<pk>)`（**PK 列名逐表核**）
⇒ ⇒ 表清单落 `tests/e2e_flows/lane_written_tables.py`（**一处真相源**）
② **session 级基线**：新增 session scope 的 fixture，在 `e2e_schema` 就绪后取一次 public 快照，
   在 session 结束时再取一次 ⇒ ⇒ 断言**逐张相等** ⇒ ⇒ ⚠️ **两种基线时机不能混**（车道内的
   `POST /api/v1/projects` 那条守卫仍保留 ⇒ ⇒ 它断「这条写路径没碰 public」⇒ ⇒ 两者**并存**）
③ **第三个 singleton**：把 `conftest.py:324-327` 的覆写**扩到 `_sync_engine`**
（造一个 schema-scoped 的 sync engine 赋给 `db_session_mod._sync_engine`）⇒ ⇒ 堵住未来的 `get_engine()` 路径
④ 写路径仍断「必须 200/201」（断**后果**不断**动作** ⇒ 已有，不要改）

- [ ] **Step 4: 跑 E2E 车道 + 变异自证**

Run: `cd pcs-backend && bash scripts/pytest_e2e.sh`
Expected: 全绿

⇒ ⇒ **变异自证**：在 public 里手工插一行 / 删一行 / **改一行**（同表替换）⇒ ⇒ 守卫**必须红**
⇒ ⇒ 三种都验过才进 Step 5。

- [ ] **Step 5: 提交**（`fix(P10-F): public 守卫扩覆盖面 + 补 _sync_engine + session 级基线（评审 #22）`）

---

### Task F2-T2: 仪表盘的守卫条件改成「**拿到了真 project_id**」（评审 #24）

> ⚖️ **hermes 改判**：① 报告的「真后端通道会红」**今天不成立** —— 种子工作区 **`owner_id` 也是 NULL**
> ⇒ ⇒ 切换器按 `owner_id` 过滤（`app/services/workspace_service.py:98-99`）⇒ ⇒ **真后端下根本选不中它**
> ⇒ ⇒ ⚠️ **前置的一步是补 `owner_id`**（否则「补 `project_id`」根本轮不到）
> ② 但**缺陷本身在生产里成立** —— mock 种子的 PERSONAL/TEMPORARY 工作区 `project_id` **就是 null**
> （`src/mocks/seed/workspaces.ts:29,43`）⇒ ⇒ 任何真实用户选中它们 ⇒ ⇒ **两条 404 + 控制台 error**
> ③ ⚠️ 报告漏了**顺序约束** —— 工作区**先于**项目创建（`Project.workspace_id` NOT NULL）⇒ ⇒
> `workspace.project_id` 只能在 `_ensure_project` **之后**回填 ⇒ ⇒ 否则撞 FK

**Files:**
- Modify: `pcs-frontend/src/constants/env.ts:13`（导出 `PLACEHOLDER_PROJECT_ID` 共享常量）
- Modify: `pcs-frontend/src/pages/DashboardPage.tsx:8-10`（**删掉** `workspaceProjectId`）· `:20`（`effectiveProjectId`）· `:38`（面板渲染条件）
- Modify: `pcs-backend/scripts/seed_e2e_flows.py:340-352`（`_ensure_workspace` **补 `owner_id`** ⇒ ⇒ `_ensure_project` 之后**回填 `project_id`**）
- Test: `pcs-frontend/tests/pages/DashboardPage.test.tsx`（**新建**，若已存在则**加一条**）· `pcs-backend/tests/e2e_flows/test_e2e_workspaces_visible.py`（**新建** ⇒ 「种子工作区在切换器里可见」）

**Interfaces:**
- Consumes: `app/models/project.py:116-119`（`owner_id` · `project_id` **均可空**）· `derive_user_id(username)`（与 `tests/e2e_flows/conftest.py:273` 同一口径 ⇒ **填派生 id，不是用户名**）
- Produces: `PLACEHOLDER_PROJECT_ID`（导出于 `src/constants/env.ts`）⇒ ⇒ `env.ts` 的兜底与 `DashboardPage` **共用一份**

- [ ] **Step 1: 写失败测试**（前端）

```tsx
it('选中的工作区没有 project_id ⇒ 不渲染清单面板（不产生 404）', async () => {
  render(<DashboardPage />);
  await user.click(screen.getByRole('combobox'));           // WorkspaceSwitcher 的选择器
  await user.click(screen.getByText('无项目工作区'));
  expect(screen.queryByTestId('input-checklist-panel')).not.toBeInTheDocument();
});
```

⇒ ⇒ ⚠️ 断言的**形状**要能区分「没渲染面板」与「渲染了但没发请求」⇒ ⇒ **两个都断**：
面板不存在 **且** `checklistApi.list` / `checklistApi.completeness` **一次都没被调**。

- [ ] **Step 2: 跑测试确认失败**（现在 `selected` truthy ⇒ 面板渲染 ⇒ 用了占位 id ⇒ 404）

- [ ] **Step 3: 实现前端**⇒ ⇒ `const effectiveProjectId = selected?.project_id ?? null;` ⇒ ⇒
`{effectiveProjectId ? <InputChecklistPanel projectId={effectiveProjectId} /> : null}` ⇒ ⇒
`workspaceProjectId()` **删掉**（它的占位兜底正是缺陷来源）⇒ ⇒ 卡片标题区分
`selected ? (effectiveProjectId ? \`项目 ${effectiveProjectId.slice(0,8)}…\` : '该工作区未关联项目') : '选择工作区后查看清单'`
⇒ ⇒ `env.ts` 导出 `PLACEHOLDER_PROJECT_ID`，`env.ts` 的兜底与别处引用**统一引它**。

- [ ] **Step 4: 写失败测试**（后端 · 「种子工作区可见」）

```python
@pytest.mark.e2e
async def test_seeded_workspace_is_visible_to_its_owner(client, ...):
    """种子工作区必须**在切换器里可见** ⇒ owner_id 要填派生 id（不是用户名）。"""
    r = await client.get(f"/api/v1/workspaces?owner_id={derive_user_id('alice')}")
    assert r.status_code == 200
    assert any(w["id"] == FLOW_WORKSPACE_ID for w in r.json())
```

⇒ ⇒ ⚠️ 断**后果**（「列表里有它」），不断**动作**（「我们调用了 seed」）。

- [ ] **Step 5: 跑测试确认失败**（现在 `owner_id` 是 NULL ⇒ 列表为空）

- [ ] **Step 6: 实现种子侧**（`scripts/seed_e2e_flows.py:340-352`）

① `_ensure_workspace` 填 `owner_id = derive_user_id(<种子的那个用户名>)`（**派生 id**）
② `_ensure_project` **之后**回填 `workspace.project_id = project.project_id` ⇒ ⇒
⚠️ **顺序约束写进注释**（工作区先于项目创建 ⇒ 提前填会撞 FK）
⇒ ⇒ ⚠️ **产品决定**：「FORMAL 工作区要不要回填 `project_id`」⇒ ⇒ **交人裁决** ⇒ ⇒ 本条**默认不回填**
（只补 `owner_id`）⇒ ⇒ 回填作为 **TODO** 登记 ⇒ ⇒ 理由：回填会让「无项目工作区」在真后端消失 ⇒ ⇒
而那正是要测的形态 ⇒ ⇒ 保留 mock 通道提供「无项目工作区」的形态。

- [ ] **Step 7: 跑测试 + typecheck + lint**

Run: `cd pcs-frontend && npm run test -- tests/pages/DashboardPage.test.tsx && npm run typecheck && npm run lint`
Run: `cd pcs-backend && bash scripts/pytest_e2e.sh`
Expected: 全绿

- [ ] **Step 8: 提交**（`fix(P10-F): 仪表盘守卫条件改成「拿到了真 project_id」（评审 #24）`）
⇒ ⇒ 顺带在 `TODOS.md` 登记：「FORMAL 工作区要不要回填 `project_id`？」+「前端还有别处把占位常量当真值用」

---

### Task F2-T3: compose 的 `migrate`/`seed` **进同一把锁**（评审 #15 第 ① 步 · TODO-163）

**Files:**
- Modify: `pcs-backend/scripts/compose_test_stack.sh`（**宿主侧**取锁）· `docker-compose.yml`（`migrate`/`seed` 两个服务的 `command` ⇒ 注明「必须经宿主脚本」）
- Test: `pcs-backend/tests/scripts/test_compose_test_profile.py`（**既有** ⇒ 加一条）

**Interfaces:**
- Consumes: `scripts/pytest_pg.sh` 的锁路径口径（`$BACKEND_DIR/.tmp/lane.lock`）⇒ ⇒ **同一把锁**
- Produces: `compose_test_stack.sh` 在调用 compose **之前**抢锁 ⇒ ⇒ 抢不到 ⇒ **非零退出**并说清「另一条车道在跑」

- [ ] **Step 1: 写失败测试**（`tests/scripts/test_compose_test_profile.py`）

```python
def test_compose_test_stack_takes_the_lane_lock_before_invoking_compose():
    body = lane_script_body(BACKEND / "scripts" / "compose_test_stack.sh")
    assert "lane.lock" in body, "起测试栈的脚本没抢车道锁 ⇒ 与车道并发 ⇒ DDL 等锁"
    assert body.index("lane.lock") < body.index("docker compose"), "锁必须在调 compose **之前**抢"
```

- [ ] **Step 2: 跑测试确认失败**
- [ ] **Step 3: 实现**（`compose_test_stack.sh`）⇒ ⇒ 与 `pytest_pg.sh` **同款**的锁段
（`exec 9>"$LOCK_FILE"` + `flock -n 9` ⇒ 抢不到 ⇒ 退出码 1 + 「另一条车道正在跑」）⇒ ⇒
⚠️ **路径口径必须一致**（`${BACKEND_DIR}/.tmp/lane.lock`）⇒ ⇒ `mkdir -p` 也要有。
⇒ ⇒ `docker-compose.yml` 两个服务的注释补一句「**必须**经 `scripts/compose_test_stack.sh` 起（它抢车道锁）⇒ 直接 `docker compose run` 会绕过锁」。
- [ ] **Step 4: 跑测试 + 手工验一次**（`bash scripts/compose_test_stack.sh` ⇒ 应正常跑完 ⇒ 且 `pcs-backend/.tmp/lane.lock` 被创建）
- [ ] **Step 5: 提交**（`fix(P10-F): 测试栈起服也进车道锁（评审 #15 第 ① 步）`）
⇒ ⇒ ⚠️ **同时关闭 TODO-163**（在 `TODOS.md` 里标「2026-11-17 关闭 · `<commit>`」）

---

### Task F2-T4: 公式编辑器的 `rowKey` 去掉 **index** 参数（TODO-162）

**Files:**
- Modify: `pcs-frontend/src/pages/config/FormulaEditorPage.tsx:241`
- Modify: `pcs-frontend/e2e/real_backend_route_sweep.spec.ts`（**删掉白名单里那条** ⇒ ⇒ 白名单外必须为空 ⇒ ⇒ 删条目后仍要绿 ⇒ ⇒ **这本身就是验证**）
- Test: `pcs-frontend/tests/pages/FormulaEditorPage.test.tsx`（**既有则加**，否则新建）

- [ ] **Step 1: 写失败测试**

```tsx
it('参数表的 rowKey 不依赖 antd 回调的 index 参数', () => {
  // ⇒ 断言：渲染两行同名的参数 ⇒ 控制台**没有** antd 的 rowKey 弃用告警
  const errSpy = vi.spyOn(console, 'error');
  render(<FormulaEditorPage formula={formulaWithTwoEmptyParams} />);
  expect(errSpy.mock.calls.flat().join(' ')).not.toMatch(/rowKey/);
});
```

- [ ] **Step 2: 跑测试确认失败**（现在有 antd 弃用告警 ⇒ 控制台 error ⇒ 断不到 ⇒ RED）
- [ ] **Step 3: 实现**⇒ ⇒ ⚠️ **不能**简单改成 `rowKey={(r) => r.name}`（参数名**允许空/重复** ⇒ antd 会报
Duplicate row key ⇒ 换成另一种告警）⇒ ⇒ **做法**：在 `FormulaEditorPage` 的 **draft 之外**维护一份
「每行的稳定 key」⇒ ⇒ 用 `useState<string[]>` 存 key（新增行 ⇒ `crypto.randomUUID()`）⇒ ⇒
`rowKey` 用字符串字段 ⇒ ⇒ ⚠️ **key 不得进 `FormulaEditor` 公开形状**（会漏进保存的载荷）⇒ ⇒
⇒ 若实现发现必须改公开类型 ⇒ ⇒ **停下并登记 TODO**（契约面 ⇒ 属另一批）。
- [ ] **Step 4: 跑测试 + 真后端通道**（`npm run e2e:real` ⇒ 扫描的白名单删掉那条后仍全绿 ⇒ ⇒ 这就是「端点/组件修好后删条目」的证据）
- [ ] **Step 5: 提交**（`fix(P10-F): 公式编辑器 rowKey 去掉 index 参数（TODO-162）`）

---

# F3 · 守卫覆盖审计（TODO-129）+ 三条越权债复核

> **本批前置**：无（P10-B 的车道与真后端通道已就位 ⇒ 审计有观测面）。
> **本批产出**：**结论**（不是「未审即没问题」）⇒ ⇒ 一份缺口清单（每条带 TODO）+ 一份「已覆盖」清单（带断言位置）。

### Task F3-T1: 划定**审计范围**（用户裁决 Q10 的落地）

⇒ ⇒ 候选模块：`app/api/v1/config.py`（12 端点）· `report_builder.py`（9）· `psychro.py`（13）· 其它
非物流面模块 ⇒ ⇒ **范围由人裁决**（主计划 Q10）⇒ ⇒ **本任务的产出是「范围提案 + 每条候选的初判」**
⇒ ⇒ 提交给人 ⇒ ⇒ **不要**自己把范围定死。

### Task F3-T2 ~ T3: 逐模块**审计**（守卫覆盖面）

⇒ ⇒ 每个模块一条：**列出全部端点 → 每个端点判「有没有项目/资源级守卫」→ 给出证据（端点号 + 守卫调用）**
⇒ ⇒ 缺口 ⇒ **逐条登记 TODO**（不许合并成「若干缺口」）⇒ ⇒ 已覆盖的 ⇒ **给出断言位置**（哪个测试守着）。

### Task F3-T4: 三条越权债**复核**（不重做）

⇒ ⇒ TODO-132（禁用用户）· TODO-133（workspace 归属）· TODO-135（mock 旁路）⇒ ⇒ ✅ 已由 P9B-4 闭合
⇒ ⇒ 本批**只复核**：每条找一条**现存**的断言 + 跑一次 ⇒ ⇒ 写「复核结论 + 证据」。

### Task F3-T5: 审计结论**落文档 + 账簿**

⇒ ⇒ 落 `docs/solutions/security-issues/guard-coverage-audit-logistics-adjacent-modules.md`
（**新建** ⇒ frontmatter 照同目录既有条目）⇒ ⇒ 内容 = 范围 · 方法 · 逐端点结论 · 缺口 TODO 清单 ⇒ ⇒
⇒ ⇒ 同时更新 `TODOS.md`（每条缺口一条）⇒ ⇒ **不许**写「未审即没问题」。

---

# F4 · 生产就绪的**技术项**（前置：P10-C 落地）

> **本批前置**：P10-C（部署与可观测性）落地 ⇒ ⇒ 否则没有可扫的镜像、没有部署物、没有告警。
> **SPEC 依据**：§3.2.7 的「安全扫描 / 依赖漏洞 / 容器镜像扫描 / 回滚演练 / 数据迁移演练」。

### 任务清单（开工时把每个任务写成 TDD 步骤）

- **F4-T1 安全扫描**（SAST：bandit · DAST：无 ⇒ 用 §3.2.7 的「无高危」判据 ⇒ 工具与基线写进 `scripts/`）
- **F4-T2 依赖漏洞**（pip-audit + npm audit + 基础镜像 CVE ⇒ **高危为 0** ⇒ 输出可复跑）
- **F4-T3 容器镜像扫描**（trivy ⇒ 镜像来自 P10-C ⇒ 高危为 0）
- **F4-T4 回滚演练**（版本回滚流程 ⇒ 真的回滚一次 ⇒ 记录命令 + 输出）
- **F4-T5 数据迁移演练**（迁移 + **回滚**的数据兼容性 ⇒ 在**隔离 schema** 上跑 upgrade→downgrade→upgrade）
- **F4-T6 证据落盘**（每项一条「命令 + 输出 + 结论」⇒ 落 `docs/` ⇒ **不许**写「已验证」而没有命令）

---

# F5 · 生产就绪的**运维项**（前置：P10-C + P10-E 落地）

- **F5-T1 监控告警演练**（告警**触发** / **静默** / **升级**三条路径各留证据 ⇒ ⚠️ 依赖 P10-C 的 exporters 与告警规则）
- **F5-T2 备份恢复演练**（RPO ≤ 30min · RTO ≤ 2h ⇒ 记**模板**与**实测耗时**）
- **F5-T3 应急联系人**（明确到人/角色 ⇒ ⚠️ 涉及真实人员 ⇒ **交人确认**，不代填）
- **F5-T4 上线检查清单**（SPEC §3.2.7 的「上线检查清单」⇒ 逐项带证据链接）
- **F5-T5 Go/No-Go 会议纪要模板**（模板 + 填写指引 ⇒ ⚠️ 模板里的「决策」栏留空 ⇒ 不代签）

---

# F6 · 收口

- **F6-T1 部署前置清单**（TODO-131 `scripts/seed_user_project_access.py` 的一次性授权 · TODO-137 遗留账号迁移 ⇒
⚠️ **真跑一次** ⇒ ⇒ 查 `SELECT count(*) FROM users WHERE user_id <> uuid5_derived(username)` ⇒ ⇒ 0 才算过）
- **F6-T2 SPEC 偏离回写**（F1~F5 产生的偏离 ⇒ 写进 **权威** `spec/PCS-SPEC-P10 V1.3.1 …md` 的「第六部分：偏离登记」⇒
⇒ **编号续 D41 起** ⇒ ⇒ V1.0 那份只留历史）
- **F6-T3 账簿**（`.wolf/STATUS.md` · `TODOS.md` · `.wolf/buglog.json`（每个新缺陷一条，`fix_commit` 必填）⇒ ⇒ 本计划的勾选框）
- **F6-T4 全量闸门 + 浏览器回归报告**（跑 §〇 的五组闸门 ⇒ ⇒ 报告落 `.gstack/qa-reports/qa-report-pcs-frontend-YYYY-MM-DD-p10f.md`
⇒ ⇒ ⚠️ **关键结论必须同步进 `TODOS.md` / `STATUS.md`**（`.gstack/` 是 gitignored ⇒ 报告随磁盘蒸发））

---

## 尚未解决的问题（开工前需裁决或登记）

| # | 问题 | 现状 | 归属 |
|---|---|---|---|
| 1 | **hermes 的第三方裁决与本计划的任务描述冲突** | ✅ **已解决** —— 裁决已落盘（`hermes-adjudication.md`）⇒ ⇒ **F1/F2 已按裁决改写**（5 条改判 · 1 条修）⇒ ⇒ 开工时仍冲突 ⇒ 改计划 | F1 开工前置 |
| 2 | ⚖️ **#17 的产品决定**：`source` 改成 `COMPANY_STD` ⇒ 该行**会出现在公司管级列表里** | 「能不能出现 / 要不要过滤」**交人裁决** ⇒ ⇒ F1-T3 默认照改并**登记 TODO** | F1-T3 |
| 3 | ⚖️ **#24 的产品决定**：FORMAL 工作区**要不要**回填 `project_id`（+「个人/临时工作区」在仪表盘上的文案） | **交人裁决** ⇒ ⇒ F2-T2 默认**只补 `owner_id`**（保留「无项目工作区」的形态供测）⇒ ⇒ 回填登记 TODO | F2-T2 |
| 4 | **F3 的审计范围有多大**（主计划 Q10 · TODO-129） | 候选：`config.py` 12 端点 / `report_builder.py` 9 / `psychro.py` 13 … ⇒ ⇒ 范围**交人裁决** | F3-T1 |
| 5 | **#15① 的锁覆盖**：compose 侧改宿主脚本（免装 `flock`）⇒ ⇒ **直接 `docker compose run --rm seed` 仍能绕过锁** | 本计划选了宿主侧方案（零镜像改动、可在本机验证）⇒ ⇒ 残留风险登记 | F2-T3 · 残留 |
| 6 | **P10-C / P10-D / P10-E 都未开工** | ⇒ ⇒ F4/F5 的前置不满足 ⇒ ⇒ F1/F2/F3 现在可开 | F4/F5 开工前置 |
| 7 | **E2E 进 CI**（SPEC §3.2.0(2)） | 既有裁决「不新建 CI 流水线」⇒ ⇒ F6 的上线清单**不得**写「CI 会跑」 | F5/F6 |
| 8 | **PgBouncer 引入与否**（主计划 Q1） | 未裁 ⇒ ⇒ **P10-F 不涉及**（F4 的扫描面按「直连 PG」写） | P10-D 开工前置 |
| 9 | **F1-T2 的契约破坏性变化**（preview-streams 200 形状变具体） | 前端生成类型会变 ⇒ ⇒ 可能连带改前端消费点 ⇒ ⇒ 若发现 ⇒ 登记 TODO 而非顺手改 | F1-T2 |
| 10 | ⚖️ **前端没有 refresh 通路**（后端有 `POST /auth/refresh` + 7 天 refresh token ⇒ 前端**零处**调用） | 「每 30 分钟必须重新登录」是产品事实 ⇒ ⇒ **本计划不修**（属通道问题之外的另一个缺口）⇒ ⇒ 登记 TODO + 给 refresh 流程加一条真后端通道用例 | TODO（新增） |
| 11 | ⚖️ **前端裸 `fetch(` 没有静态守卫** | `src/` 下已有 5 处裸 fetch ⇒ ⇒ 下一个新页面还会写 ⇒ ⇒ 建议加 lint/测试级守卫（禁 `src/pages`·`src/components` 的裸 fetch）⇒ ⇒ 本计划**不做**（属另一批）⇒ ⇒ 登记 TODO | TODO（新增） |
| 12 | ⚖️ **「改动 → 该跑哪几个闸」没有索引** | `tests/scripts/` 下已有多份静态守卫，各自 docstring 自述 ⇒ ⇒ 下一个维护者改锁 ⇒ 不知道该跑哪几条 ⇒ ⇒ 建议在 `tests/scripts/README.md` 列一张表 ⇒ ⇒ 登记 TODO | TODO（新增） |
| 13 | ⚖️ **「隔离表清单」没有仓库级真相源** | 表清单只存在于 `scripts/seed_e2e_flows.py` 的代码里 ⇒ ⇒ 手抄一次就漂一次 ⇒ ⇒ F2-T1 先落一份 `lane_written_tables.py`（一处）⇒ ⇒ 结构性解法（从 ORM ∪ 迁移推）登记 TODO | F2-T1 · TODO |

---

## 执行方式（**开工前由人定**）

- **Subagent-driven**（每个任务一个全新子代理 + 任务间一次独立评审）⇒ 最彻底 ⇒ 成本 = 每任务一份上下文。
- **Native**（本会话 inline 跑完**一批** ⇒ 批末一次整体评审）⇒ 与本仓现状一致（`.superpowers/sdd/<plan>/progress.md` 账簿制）⇒ ⇒
**推荐 Native**（理由：F1~F3 的任务彼此**接口耦合少**（F1-T1 的 `useFetch` 新签名是唯一跨任务契约）⇒ ⇒ 且**一批 = 一个上下文窗口**⇒ ⇒ 分批执行比逐任务换上下文更省）。
