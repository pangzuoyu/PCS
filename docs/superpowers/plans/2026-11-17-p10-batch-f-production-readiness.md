# P10-F 实施计划：生产就绪评审（10.7）· 2026-11-17

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 P10 收在「**可上线**」这个状态上 —— ① 清掉 P10-B 评审遗留的 8 条技术债 + 1 条评审期间新发现（**F1/F2**）② 给出物流面外守卫覆盖的**结论**而不是「未审即没问题」（**F3**）③ 把 SPEC §3.2.7 的 10 个评审项逐项**做出来并留证据**（**F4/F5**）④ 收口：部署前置清单 + 偏离回写 + 全量闸门（**F6**）。

**Architecture:** P10-F 是**评审批**，不是功能批 ⇒ ⇒ 它的产出**不是新功能**，而是「**证据 + 清单 + 结论**」⇒ ⇒ 所以每个 Task 的交付物是**可复跑的脚本/文档 + 一条断言**，不是一段新代码。技术债部分（F1/F2）沿用 P10-B 车道的既有形状（隔离 schema + 真 PG + 变异测试），⇒ **不新建第二套验证机制**。

**Tech Stack:** FastAPI · SQLAlchemy 2.x async · alembic · pytest（asyncio_mode=auto）· Playwright · React 18 + antd 5 · docker compose · **bandit**（已装）· **uv audit**（内建于 uv 0.11.2）· npm audit · k6（**P10-D 引入**）· trivy（**F4-T3 待 P10-C 出镜像后再定**）

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
| **F2** | P10-B 评审残余（**技术债 · 隔离/前端/并发**）+ **默认车道隔离性（新发现）** | 5 | F1 落地 | ✅ |
| **F3** | **守卫覆盖审计**（TODO-129）+ 三条越权债复核 | 5 | 无（车道的审查面已就位） | ✅ |
| **F4 前置（F4-PRE）** | 清「F3/F4 遗留清单」里**谁做/何时做仍未定**的那部分（裁决 + 棘轮抬真 + 车道残留） | 5 | 无（**不依赖 P10-C**）⇒ ⇒ F4 开不了时正好先做 | ✅ |
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

## ce review 队列的**完整去向**（一条不漏 —— 2026-11-17 评审后补）

⇒ ⇒ **为什么要有这一节**：本计划开头的「8 条技术债」只列了 **F1/F2 要做的** ⇒ ⇒
⇒ ⇒ 读者若只看本计划，会以为 ce review 的其余条目**没人管** ⇒ ⇒ 而实际上**大部分已由
P10-B 的「评审修复批」落地**（报告 `docs/ce-code-review/20261117-013829-7e9fbabe/report.md`
的「执行结果」节自带完整清单 + commit）⇒ ⇒ 这里**逐条摊开**，让「生产就绪」这个说法
与「审计哈希 / 车道打错库 / 绿灯假绿」这三件事**不并存**。

### ① 已由 P10-B 落地（**不在本批**）—— 证据在仓库里，不在记忆里

> ⚠️ **本表的 commit 与文件行号是 2026-11-17 写计划时的快照** ⇒ ⇒ 开工前应当
> `git show <commit> --stat` + `grep` **逐个确认**（尤其是 `report.py:487-495` 是否真读
> `content_hash`、`conftest.py:324-327` 是否真覆写了两个 async 单例 ⇒ ⇒ **有没有漏第三个**）
> ⇒ ⇒ 这是防止「**P10-B 声称修了但实际没修**」的唯一手段 ⇒ ⇒ 而那正是 ce review #3 抓到的病
> ⇒ ⇒ **（2026-11-17 已核过一次：三条均通过）**

| 发现 | 落地形状 | commit | **现在能核到的证据** |
|---|---|---|---|
| **A1 / #14**（+ #3 / #4 / #12 随之） | 审计端点读 `content_hash`；删掉 `dup` 早退后**永不可达**的 `data_version = digest` | `cebf48d` | `app/api/v1/report.py:486-495`（`_expected_digest` 读 `content_hash`）· `app/workers/report_tasks.py:114`（「不再写 `data_version`」）· `tests/e2e_flows/test_e2e_report.py:86`（「**不再 xfail**」+ 断「等于该文件的 sha256 · 64 位 hex」） |
| **#2**（⇒ #1 作废） | 迁移 `p10_002` 种 `CS-STD` + lifespan 幂等 ensure ⇒ **请求路径不再写配置主表** | `062110a` | `alembic/versions/p10_002_seed_placeholder_pipe_class.py` **存在** · `app/main.py:164-166`（lifespan ensure）· `app/services/pipe_class_service.py:862-871`（幂等兜底，注释写明「**启动时**调 ⇒ 不在请求路径」） |
| **#8** | 目标库白名单（判据 = **真实连接**的 `current_database()`） | `c75b505` | `app/core/db_guard.py:43`（`ALLOWED_LANE_DATABASES = {pcs_pgtest, pcs_test}`）· **调用点**：`tests/e2e_flows/conftest.py:110,184` + `scripts/seed_e2e_flows.py:854` ⇒ ⇒ **车道与种子脚本都过这道闸** ⇒ ⇒ 计划里「单测车道绝不碰开发库」这条约束**有代码背书** |
| **#16** | 闸门③ 不再接受「跑 1 条、skip 29 条」 | `7f394c1` | `scripts/pytest_pg.sh:99-107`（摘要行里有 `skipped` ⇒ **FAIL**） |
| **#19** | 隔离扩到**进程级 session factory** | `832f9c0` | `tests/e2e_flows/conftest.py:324-327` · ⚠️ **只覆写了两个 async 单例** ⇒ ⇒ 第三个（`_sync_engine`）由 **F2-T1** 补 |
| **#10** | RBAC 审计早退 ⇒ 按**真实连接**判车道上下文 | `4bb6a79` | `app/core/errors.py:50`（`_audit_target_is_lane`） |
| **#5** | 越权断言换「角色够、授权缺」身份 ⇒ 断 404 + code/message 模板 | `0bf78fd` | `pcs-frontend/e2e/real_backend_flows.spec.ts`（`erin` 身份）· 已做**变异实测** |
| **#6** | 矩阵断言改断种子那张 | `0bf78fd` | `E2E_FLOWS_RECORD_3_LEVEL` |
| **#7** | 路由扫描改真断言 ⇒ **白名单外**必须为空 | `c82a1e8` | `pcs-frontend/e2e/real_backend_route_sweep.spec.ts:99,208-219`（`ALLOWED_BAD_RESPONSES` + 「白名单外必须为空」） |
| **#18** | 种子显式调生产用的两个 seed 函数 | `6718ab4` | `scripts/seed_e2e_flows.py::_seed_production_defaults`（9 / 13 ⇒ D39） |
| **#20 / #21** | 两库 schema 检查挪到发布前闸门 | `7a0737e` | `pcs-backend/scripts/check_schema_parity.py`（逐库独立进程 + 断「== 代码 head」） |
| **#23** | 三个变量落到三层各自的位置 + fail-fast | `d29598a` | `pcs-backend/scripts/serve_e2e_backend.sh` **存在** · `pcs-frontend/playwright.config.ts` 的 `webServer.env` · `pcs-frontend/e2e/global-setup.ts`（占位 id ⇒ 拒绝） |
| **#11** | 5 份 `docs/solutions/` 回写 | `b95a463` | `docs/solutions/{testing,database,frontend,security}-issues/` |
| **#25** | 偏离登记同步到权威 V1.3.1（D23~D40） | `e03889a` | `spec/PCS-SPEC-P10 V1.3.1 …md`「第六部分：偏离登记」 |
| **#26** | 请求侧 `case_type` 可省略 | `f22f3a9` | `pcs-backend/app/schemas/stream.py` |
| **#15**（②③） | 默认锁路径项目内 + 默认路径互斥**子进程实测** | `1e27216` | `pcs-backend/scripts/pytest_pg.sh` · `tests/scripts/test_pytest_pg_gate.py:149-218` |

⇒ ⇒ **#1** 因 #2 落地而**作废**（不再单列）。

### ② 本批要做（**F1 / F2 / F3**）

| 发现 | 去向 |
|---|---|
| #9 · #13 · #17 · #22 · #24 · #27 | **F1** / **F2**（hermes 裁决后改写 ⇒ 逐条见对应 Task） |
| **#15 ①**（compose 的 `migrate`/`seed` 进锁） | **F2-T3**（宿主侧取锁 ⇒ 容器侧路线见 ③） |
| **F2-T5**（默认车道连开发库 + 真 Redis） | **F2-T5**（2026-11-17 评审期间**新发现** ⇒ 不在原 ce review 队列里） |
| **TODO-129 / #131 / #137**（守卫审计 / 部署前置 / 遗留账号） | **F3** / **F6-T1** |

### ③ 明确**延后**（附理由与归属）

| 条目 | 延后到 | 理由 |
|---|---|---|
| **#15 ① 的容器侧路线**（容器内装 `flock`） | **P10-C** | 本机 docker registry 拉不动 ⇒ ⇒ 改完**无法验证** ⇒ ⇒ 本批只做宿主侧（残留登记 TODO-163） |
| **TODO-159 / TODO-160**（3 个页面调不存在的端点 · 3 个 common 页首屏 422） | 独立批 | 与「生产就绪」无直接关系 ⇒ ⇒ 但它们是**真后端通道白名单**的 6 个条目 ⇒ ⇒ 白名单不空 ⇒ ⇒ **真后端通道的「白名单外为空」只能证明「没有新的」** ⇒ ⇒ 登记在 `TODOS.md` |
| **TODO-154**（E2E 流程级数据落在 `pcs_pgtest` 的 public schema） | 独立批 | 与 **F2-T1** 的 session 基线相关（public 里有 E2E 数据）⇒ ⇒ F2-T1 的基线**在车道启动时取** ⇒ ⇒ 不受影响 ⇒ ⇒ 单独治 |
| **前端 refresh 通路 / 裸 `fetch(` 静态守卫 / 「改动→该跑哪几个闸」索引** | 独立批 | 见「尚未解决的问题」表 #10~#12 |

### ④ 判定**不需要修**（附理由）

| 条目 | 理由 |
|---|---|
| **#1** | 因 #2 落地而作废（人裁决已明说） |
| **#13 的「前端消费者」担忧** | 前端**零处**消费 `preview-streams` ⇒ ⇒ 不是功能坏 ⇒ ⇒ 但**契约债是真的** ⇒ ⇒ 故 F1-T2 仍修（形状写进 OpenAPI） |

---

## 执行前置（**开工第一步 · 不是可选项**）

- [x] **读 hermes 的第三方裁决**（`docs/ce-code-review/20261117-013829-7e9fbabe/hermes-adjudication.md`，**已落盘**）⇒ ⇒ 那是人**未裁决**的 6 条（#9 / #13 / #17 / #22 / #24 / #27）的第三方意见（**5 条改判 · 1 条修**）⇒ ⇒ **本计划 F1/F2 已按裁决改写**（改写处标「⚖️ hermes」）⇒ ⇒ 开工时若仍与裁决冲突 ⇒ ⇒ **改计划**（不是改实现去迁就计划）⇒ ⇒ 冲突逐条记进账簿。
- [x] **逐条重核 F1/F2 的「事实基础」**（下表）⇒ ⇒ 事实基础是**写计划时的快照**，不是已核验的真相 ⇒ ⇒ 与当前源码不符 ⇒ **改计划**。
  ⇒ ⇒ **2026-11-18 重核结论**：**8 行全部成立**（逐行的核验记录在账簿 `progress.md` 各 Task 的
  「事实基础重核」小节）⇒ ⇒ 唯一偏差是 **#9 的行号**（`useFetch` 实为 `:76-96`，
  「加载中…」实为 `:160`，非计划写的 `:78-99` / `:159-161`）⇒ ⇒ **内容一致，不改计划**。
- [x] **确认前批状态**：`git log --oneline -5` + `.wolf/STATUS.md` ⇒ ⇒ 前批（**F1/F2 的 8 条**）必须已落地且闸门全绿。
  ⇒ ⇒ **2026-11-18 确认**：P10-B 的 8 条评审残余**已落地**（#9 · #13 · #17 · #22 · #24 · #27 ·
  #15① · TODO-162）⇒ ⇒ 前批 STATUS 声称的「默认车道全量绿」**不准确**（P10-B 遗留一条
  uiSchema 漂移红 ⇒ 本轮批末修掉，见账簿「批末闸门之外的额外修复」）。

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

- [x] **Step 1: 写失败测试**（`pcs-frontend/tests/pages/routeWrappers.fetch.test.tsx`）

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

- [x] **Step 2: 跑测试确认失败**

Run: `cd pcs-frontend && npm run test -- tests/pages/routeWrappers.fetch.test.tsx`
Expected: FAIL（现在只有「加载中…」，找不到「加载失败」；401 分支也不清会话）

- [x] **Step 2b: 前置检查**（⚠️ 失败模式表里那条「⚠️ 依赖既有 axios 测试」⇒ ⇒ **开工前核**）

```bash
cd pcs-frontend && npm run test -- tests/api/session_over_codes.test.ts
```
⇒ ⇒ 必须看到 **401 / 会话过期**相关的用例**存在且绿** ⇒ ⇒
⇒ ⇒ ⚠️ **路径在前端的 `tests/` 下，不在 `src/api/`**（`src/api/` 里**没有**测试文件 ⇒
⇒ ⇒ `npm run test -- src/api` 会报「No test files found」⇒ ⇒ 那不是「测试不存在」的证据）
⇒ ⇒ ⇒ 已核（2026-11-17）：`tests/api/session_over_codes.test.ts` **存在**（5 tests · MSW 打真 401
⇒ ⇒ ⇒ 断拦截器的「清会话 + 跳 /login」**和**「不该登出的 code 白名单」）⇒ ⇒ **回归网已就位** ⇒ ⇒
⇒ ⇒ **不存在** ⇒ ⇒ **停下**：先把那条测试补出来（它就是抽取函数的**回归网**）⇒ ⇒ 再抽
⇒ ⇒ **存在** ⇒ ⇒ 记录用例名（进提交信息）⇒ ⇒ 继续 Step 3

- [x] **Step 3: 抽出共享的 401 处理**（`src/api/client.ts:51-66`）

⇒ 把现有 401 分支的逻辑原样搬进 `export function handleSessionOver(status: number, code?: string): void`
⇒ ⇒ **axios 拦截器改为调它** ⇒ ⇒ 行为**不变**（回归由既有 axios 测试守着）⇒ ⇒
⚠️ `SESSION_OVER_CODES` 白名单的语义**照搬**（有些 401 不该跳登录页 ⇒ 照现有实现，别改口径）。

- [x] **Step 4: 实现 `useFetch` 的失败态**（`src/pages/routeWrappers.tsx:76-99`）

⇒ 签名改为 `{ data, error, loading }`；⇒ `fetch` 用 **`AbortController`**（cleanup 里 `abort()`）+
**15s 超时**（`setTimeout` ⇒ cleanup 里 `clearTimeout`）；⇒ `!r.ok` ⇒
**先** `if (r.status === 401) handleSessionOver(r.status)` ⇒ ⇒ **再** `error = \`HTTP ${r.status}\``；
`catch` ⇒ **区分两类失败**：**超时**（`err.name === 'AbortError'`）⇒ `error = '请求超时（15s）'`；
其余（`TypeError` 等）⇒ `error = '网络错误'`（**不吞**）。

⇒ `StreamDetailRoute`（`:159-161`）：`if (loading) return <Typography.Text>加载中…</Typography.Text>;`
`if (error) return <Alert type="error" message={`加载失败：${error}`} />;`

- [x] **Step 5: 改 9 个调用点**（同一文件）⇒ ⇒ 每个写成
`const { data, loading, error } = useFetch<T>(path, initial)` ⇒ ⇒ **不要**改各页面的渲染逻辑
（只把 `data` 换成解构出来的 `data`）⇒ ⇒ ⚠️ `StreamDetailRoute` 额外加失败态（Step 4）。
⇒ ⇒ ⚠️ 其中 3 个（`:212` `:331` `:335`）用的是**占位** `PROJECT_ID` ⇒ ⇒ 那些页面的 404 是
TODO-159/160 的既有白名单项，**不是本任务引入的** ⇒ ⇒ 不要在白名单里新增。

- [x] **Step 6: 换掉 `AssetListPage` 的写死 token**（`src/pages/config/AssetListPage.tsx:153-154`）

⇒ `DEV_BEARER` ⇒ `useAuth.getState().accessToken`（照 `routeWrappers.tsx:85-86` 的写法）⇒ ⇒
⚠️ **该端点后端根本不存在**（`GET /api/v1/config/assets/{id}/revisions` ⇒ 今天 404）⇒ ⇒
**这一步的行为不可观测** ⇒ ⇒ 必须靠 Step 7 的请求头断言把它变成可观测 ⇒ ⇒
提交信息里写明：「端点补齐那天这条必须仍成立」。

- [x] **Step 7: 补齐四个边界测试**（⚖️ 评审 D11：四个都补）

| 测试 | 断什么 | 怎么断 |
|---|---|---|
| **超时** | 15s 后进入失败态，文案是「请求超时」 | `vi.useFakeTimers()` ⇒ 推进 15s ⇒ 断文案 |
| **卸载清理** | 卸载时 `abort()` 被调 + `clearTimeout` 被调（防 timer 泄漏） | `vi.spyOn(AbortController.prototype,'abort')` + 卸载 ⇒ 断两个 spy |
| **9 个调用点回归** | 改签名后各页渲染不变（至少 3 个代表页：`/pipe-classes` · `/streams/{id}` · 一个 common 页） | 断关键行内容 ⇒ ⇒ **不是**断「渲染了」 |
| **请求头** | `AssetListPage` 发出的请求带的是**会话 token**，不是写死的 `mock-jwt-token` | stub `fetch` ⇒ 断 `Authorization` 头 |

- [x] **Step 8: 跑测试确认通过 + 变异自证**

Run: `cd pcs-frontend && npm run test -- tests/pages/routeWrappers.fetch.test.tsx && npm run typecheck && npm run lint`
Expected: 新测试 PASS · typecheck/lint clean

⇒ ⇒ **变异自证**：临时删掉 Step 4 里的 `handleSessionOver(r.status)` 调用 ⇒ ⇒ 重跑 ⇒ ⇒
「401 ⇒ 清会话」那条**必须红** ⇒ ⇒ 还原。

- [x] **Step 9: 跑真后端通道**（**白名单外必须为空**）

Run: `cd pcs-frontend && npm run e2e:real`
Expected: 7+ passed（路由扫描的 4xx/console 白名单**不变** ⇒ ⇒ 本任务没引入新的 404）
⚠️ 跑法：**先**在终端 A 起后端 `cd pcs-backend && bash scripts/serve_e2e_backend.sh`
⇒ ⇒ **再**在终端 B 跑 `npm run e2e:real` ⇒ ⇒（否则通道起不来，报错与本任务无关）。

- [x] **Step 10: 提交**

```bash
cd pcs-frontend && git add src/api/client.ts src/pages/routeWrappers.tsx \
        src/pages/config/AssetListPage.tsx tests/pages/routeWrappers.fetch.test.tsx
git commit -m "fix(P10-F): useFetch 失败态 + 401 与 axios 共用真相源（评审 #9）"
```

---

### Task F1-T2: `preview-streams` 的**契约形状**（评审 #13 · 后端契约）

**Files:**
- Modify: `pcs-backend/app/api/v1/sim_imports_query.py:118` 之后（**新增** `SimImportPreviewStreamsResponse` ⇒ **与 4 个兄弟模型同文件**）· `:325-330`（端点签名）· `:360-367`（**与事实相反的注释**）
- Modify: `pcs-frontend/src/types/api.d.ts`（**由 `npm run api:gen` 生成 ⇒ 不手改**）
- Test: `pcs-backend/tests/api/v1/test_sim_imports_query_endpoints.py`（**既有文件** ⇒ 加两条）

**Interfaces:**
- Consumes: 兄弟模型 `SimImportListResponse`（`:76`）· `SimImportDetailResponse`（`:85`）· `SimImportWarningListResponse`（`:118`）—— **都定义在本文件里**（全仓**没有** `app/schemas/sim_*.py`）⇒ ⇒ 新模型**紧跟它们**，**不新建 schemas 模块**（⚖️ 评审 D7）。
- Produces: `SimImportPreviewStreamsResponse(streams: list[dict[str, Any]] = [])` ⇒ ⇒ **OpenAPI 里 200 的形状**从 `{"type":"object"}` 变成 `{"streams": [...]}` ⇒ ⇒ **契约破坏性变化**（前端生成类型变具体）⇒ ⇒ 批末**必须滚 baseline**。

- [x] **Step 1: 写失败测试**（加到 `tests/api/v1/test_sim_imports_query_endpoints.py`）

```python
async def test_preview_streams_response_model_declares_the_streams_key(client, ...):
    """契约里必须能读到 `streams` 键 ⇒ 客户端不必靠试。"""
    schema = client.app.openapi()["paths"]["/api/v1/imports/{import_id}/preview-streams"]["get"]
    ref = schema["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
    assert ref.endswith("SimImportPreviewStreamsResponse")
```

- [x] **Step 2: 跑测试确认失败**

Run: `cd pcs-backend && uv run pytest tests/api/v1/test_sim_imports_query_endpoints.py -q`
Expected: FAIL（现在 200 是 `{"type":"object"}` ⇒ 没有 `$ref`）

- [x] **Step 3: 实现**

① 在 `sim_imports_query.py` 里（`:118` 的 `SimImportWarningListResponse` 之后）**新增**：

```python
class SimImportPreviewStreamsResponse(BaseModel):
    """preview 阶段的物流列表（`GET /imports/{id}/preview-streams` 的 200）。"""
    streams: list[dict[str, Any]] = Field(default_factory=list, description="preview 阶段的物流列表")
```

⇒ ⇒ ⚠️ 若 `Field` 尚未 import ⇒ 加进 `from pydantic import BaseModel` 那一行 ⇒ ⇒
⚠️ `Any` 需 `from typing import Annotated, Any, Literal`。

② 端点改成 **与 4 个兄弟完全同形**（⚖️ 评审 D7：**显式 `response_model=`**，不用注解推导）：

```python
@router.get("/{import_id}/preview-streams", response_model=SimImportPreviewStreamsResponse)
async def get_preview_streams(...) -> SimImportPreviewStreamsResponse:
```

⇒ ⇒ 返回体改成 `SimImportPreviewStreamsResponse(streams=payload if isinstance(payload, list) else payload.get("streams", []))`
⇒ ⇒ ⚠️ **读侧的 `isinstance(payload, list)` 分支不能删**（老数据是 list ⇒ 删了老数据就 500）。

③ **改注释**（`:360-367`）：「**PRO/II 与 EXCEL 两个写入点都存 list** ⇒ 读侧统一归一成 `{"streams": [...]}`」
⇒ ⇒ **删掉**「SIM/Excel 导入存 dict」那句（与事实相反）。

- [x] **Step 3b: 补「两种历史形状」的钉子**（⚖️ 评审 D9：两条都补）

```python
async def test_preview_streams_reads_both_historical_shapes(client, ...):
    """老数据是 list、归一化后是 dict ⇒ **两种都要能读** ⇒ 否则「加了 response_model
    反而把老数据 500 了」这类回归没有钉子。"""
    # 造一条 preview_streams_json = [ {...} ] 的老行 ⇒ GET ⇒ 200 且 body["streams"] 有值
    # 造一条 preview_streams_json = {"streams": [ {...} ]} 的新行 ⇒ GET ⇒ 200 且 body["streams"] 有值
```

⇒ ⇒ **两条历史形状各一行** ⇒ ⇒ 跑完确认 RED（现在没有 `response_model` ⇒ 第一条会因为返回体形状不对而红）。

- [x] **Step 4: 跑测试确认通过**

Run: `cd pcs-backend && uv run pytest tests/api/v1/test_sim_imports_query_endpoints.py -q`
Expected: PASS

- [x] **Step 5: 滚契约 + 同步前端类型**（**顺序不能反**）

```bash
cd pcs-frontend && npm run api:gen
cd ../pcs-backend && uv run python scripts/export_openapi.py
bash scripts/gate_08_openapi_contract.sh --check-baseline   # 会报漂移 ⇒ 按该脚本的提示滚 baseline
uv run python scripts/check_openapi_payload_coverage.py        # 裸载荷不涨（≤ 71）
```

⇒ ⇒ ⚠️ 滚 baseline 前**先看 diff** ⇒ ⇒ 若 diff 超出「`streams` 键 + 类型变具体」⇒ ⇒ **停下**，说明契约漂移超预期 ⇒ 登记 TODO。

⇒ ⇒ ⚠️ **滚完必须确认四份都在**（否则 Step 6 的 `git add` 会报 pathspec 不匹配）：

```bash
git status --short pcs-backend/docs/openapi.json pcs-backend/docs/openapi-baseline.json \
                pcs-frontend/openapi.snapshot.json pcs-frontend/src/types/api.d.ts
```
⇒ ⇒ 期望：**四个都有改动** ⇒ ⇒ 若 `openapi-baseline.json` 没变 ⇒ ⇒ 说明 baseline **没滚** ⇒ ⇒ 重跑
⇒ ⇒ 若 `api.d.ts` 没变 ⇒ ⇒ 说明 `npm run api:gen` 没生效 ⇒ ⇒ 重跑。

- [x] **Step 6: 提交**

```bash
git add pcs-backend/app/api/v1/sim_imports_query.py \
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

- [x] **Step 1: 写失败测试**（`tests/scripts/test_seed_e2e_flows.py`）

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

- [x] **Step 2: 跑测试确认失败**

Run: `cd pcs-backend && uv run pytest tests/scripts/test_seed_e2e_flows.py -q`
Expected: FAIL（`dn_series_json` 缺 `min`/`max` ⇒ `ValidationError`）

- [x] **Step 3: 改种子的行形状**（`scripts/seed_e2e_flows.py:504-531`）

⇒ `dn_series_json={"min": 150, "max": 150}`（**int**）· `sch_series_json={"DN150": "40"}`（**字符串**）
· `source="COMPANY_STD"`（⚠️ **不扩 `Literal`** ⇒ 遵守 #2 裁决）

⇒ ⇒ ⚠️ **别把 `material_class` 改指 `CS-STD`**（会牵动 `FLOW_PIPE_CLASS_ID` 这个导出常量 ⇒ 改动面更大 ⇒ 不取）。

- [x] **Step 4: 订正已种下的老行**（同文件，**幂等**）

⇒ `_ensure_pipe_class` 在 `_get_or_create` 命中已有行时 ⇒ ⇒ **也要把形状订正过来**
（`dn_series_json` / `sch_series_json` / `source` 三列）⇒ ⇒ 否则 pcs_pgtest public 里那行**照旧 500**。
⇒ ⇒ 或等价做法：给脚本加 `--reset` 并把「批末重灌」写成动作 ⇒ ⇒ **二选一，写进提交信息**。

- [x] **Step 4b: 补「老行会被订正」的钉子**（⚖️ 评审 D9：**两条都补**）

```python
async def test_seed_corrects_an_existing_legacy_row(db_session):
    """库里**已存在**契约外形状的老行 ⇒ 重跑种子 ⇒ **老行被订正** ⇒
    否则「改了脚本但现象照旧」（hermes：`_get_or_create` 存在就不动）。"""
    await db_session.execute(insert(PipeClass).values(
        class_id=FLOW_PIPE_CLASS_ID,
        dn_series_json={"DN150": 1.0},          # ← 契约外的旧形状
        sch_series_json={"DN150": 40.0},
        source="E2E_SEED",
    ))
    await db_session.commit()
    await seed_flows(db_session)                    # ← 重跑
    row = (await db_session.execute(
        select(PipeClass).where(PipeClass.class_id == FLOW_PIPE_CLASS_ID)
    )).scalar_one()
    PipeClassResponse.model_validate(
        {c.name: getattr(row, c.name) for c in PipeClass.__table__.columns}
    )   # ← 不抛错 ⇒ 老行被订正过
```

⇒ ⇒ **必须先跑一次确认它红**（老形状不被订正 ⇒ `ValidationError`）⇒ ⇒ 再改实现 ⇒ ⇒ 再绿。

- [x] **Step 5: 跑测试确认通过**

Run: `cd pcs-backend && uv run pytest tests/scripts/test_seed_e2e_flows.py -q`
Expected: PASS

- [x] **Step 6: 加 PG 侧的「按 id 查不 500」**（`tests/e2e_flows/test_e2e_pipe_class_lookup.py`）

⇒ `GET /api/v1/pipe-classes/E2E-SEED-CS`（**按 id**）⇒ **200** ⇒ ⇒ 且响应体的 `dn_series_json` 形状正确
⇒ ⇒ ⚠️ **这条必须在 E2E 车道跑**（SQLite 不强制 FK ⇒ 单测照绿 ⇒ 真库才炸 ⇒ 评审 #17 的形状）
⇒ ⇒ 顺带断 `GET /api/v1/pipe-classes`（列表）**仍 200**（改 `source` 后它**会**含这行 ⇒ ⇒ 断言它**在**列表里 ⇒ ⇒ 把行为钉死，不留给下一个人猜）。

- [x] **Step 7: 跑 E2E 车道**

Run: `cd pcs-backend && bash scripts/pytest_e2e.sh`
Expected: 全绿（含新增两条）

- [x] **Step 8: 登记产品待决项 + 提交**

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

- [x] **Step 1: 写失败测试**（改 `test_pytest_pg_gate.py` 的 flock 守卫）

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

- [x] **Step 2: 跑测试确认失败**

Run: `cd pcs-backend && uv run pytest tests/scripts/test_pytest_pg_gate.py tests/scripts/test_pytest_e2e_gate.py -q`
Expected: FAIL（当前读的是**原文** ⇒ 「`flock -n`」/「`exec 9>`」的断言拿不到）

- [x] **Step 3: 实现**（新建 `tests/scripts/lane_script_body.py`）

```python
def lane_script_body(script: Path) -> str:
    """脚本的**可执行部分**（去掉注释）—— 断「脚本有没有做这件事」必须断这里。

    ⚠️ **按 shell 的词边界规则剥**：`#` 只有在**词首**（行首或前面是空白）才是注释
    ⇒ ⇒ `echo "a # b"` 里的 `#` 是**字面量** ⇒ ⇒ `echo a#b` 里的 `#` 也是字面量
    ⇒ ⇒ ⇒ 早先的 `line.split("#", 1)[0]` 会把这两类**一起剥掉** ⇒ ⇒ 守卫会在
    「脚本里只剩注释」时**误判为可执行**（⇒ ⇒ 假绿）。

    ⚠️ **不支持**：反引号（`` `…` ``）与 heredoc（`<<EOF`）⇒ ⇒ 这两种写法里的 `#`
    会被误剥 ⇒ ⇒ **守卫脚本自己不应使用这两种写法** ⇒ ⇒ 若将来要用 ⇒ ⇒ 换 `shlex` 解析。
    """
    out: list[str] = []
    for line in script.read_text(encoding="utf-8").splitlines():
        if line.lstrip().startswith("#"):
            continue
        cut = len(line)
        quote = ""
        for i, ch in enumerate(line):
            if quote:
                if ch == quote:
                    quote = ""
                continue
            if ch in "'\"":
                quote = ch
                continue
            if ch == "#" and (i == 0 or line[i - 1].isspace()):
                cut = i
                break
        out.append(line[:cut])
    return "\n".join(out)
```

⇒ ⇒ ⚠️ **docstring 里写明这个限制**：不支持「引号跨行」等边角 ⇒ ⇒
⇒ ⇒ 守卫脚本自己不该写那种写法 ⇒ ⇒ 若将来要支持 ⇒ ⇒ 换 `shlex` 解析。

⇒ ⇒ `test_pytest_e2e_gate.py` 的本地 `_body()` **删掉** ⇒ ⇒ 改成 `from tests.scripts.lane_script_body import lane_script_body`
⇒ ⇒ ⚠️ `test_pytest_pg_gate.py` 里的 `_body()`（若已存在）也一并删 ⇒ ⇒ **一处真相源**。

- [x] **Step 4: 改名 + 改 docstring**（`test_pytest_pg_gate.py:165-218`）

⇒ `test_two_lanes_are_mutually_exclusive_on_the_default_path` ⇒ ⇒
**`test_two_lanes_are_mutually_exclusive_on_an_overridden_lock_path`**
⇒ ⇒ docstring 里那句「**默认路径**下两条车道真的互斥」⇒ ⇒ 改成「**覆盖路径**（`PCS_PGTEST_LANE_LOCK`）下互斥；
**默认路径**只能静态断（不能真占默认锁 ⇒ 会与真车道抢锁）」。

- [x] **Step 5: 跑测试确认通过 + 变异自证**

Run: `cd pcs-backend && uv run pytest tests/scripts/test_pytest_pg_gate.py tests/scripts/test_pytest_e2e_gate.py -q`
Expected: PASS

⇒ ⇒ **变异自证**（两条都要红）：
① 把 `pytest_pg.sh` 的 `flock -n 9` 改成 `flock 9`（阻塞版）⇒ ⇒ 守卫**必须红**
② 把 `.tmp/lane.lock` 改回 `/tmp/...` ⇒ ⇒ 守卫**必须红**
⇒ ⇒ 两条都还原后再进 Step 6。

- [x] **Step 6: 提交**

```bash
git add pcs-backend/tests/scripts/lane_script_body.py pcs-backend/tests/scripts/test_pytest_pg_gate.py \
        pcs-backend/tests/scripts/test_pytest_e2e_gate.py
git commit -m "fix(P10-F): 守门测试统一断可执行部分 + 默认路径断 flock -n（评审 #27）"
```

---

# F2 · P10-B 评审残余（技术债 · 隔离 / 前端 / 并发）

> **本批前置**：F1 落地（若 hermes 裁决把 F1 的某条改判 ⇒ 先改本批）。
> **本批产出**：4 条技术债 + 1 条**评审期间新发现**落地 ⇒ ⇒ **批末闸门全绿**。

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
>
> ⚖️ **评审改判（D3 · D10 · D12）**：
> ⑥ ⭐ **不再枚举「车道会写的表」** ⇒ ⇒ 改为**快照 `public` schema 的全部表** ⇒ ⇒
>    **彻底不需要手抄清单** ⇒ ⇒ 直接闭合 hermes residual #2（「抄一次就漂一次」）⇒ ⇒
>    守卫要的属性从来是「**public 没被动过**」，不是「我知道车道写了哪些表」
> ⑦ ⭐ 判据用 **`count(*)` + `max(xmin::text::bigint)`**（不是内容哈希）⇒ ⇒ 流式聚合**不物化** ⇒ ⇒
>    插入/删除/**更新**都会让它变 ⇒ ⇒ 捕获能力相同 ⇒ ⇒ ⚠️ 代价：VACUUM FREEZE 会把 `xmin` 归 2 ⇒ ⇒
>    两个快照之间若发生 freeze ⇒ **误报**（车道库里几乎不会发生 ⇒ **必须写进注释**）
> ⑧ ⭐ **不只要静态守卫** ⇒ ⇒ 要**行为测试**：①「插/删/**改**一行 ⇒ 快照必变」②
>    「基线早于车道任何写入」用**双快照**钉住

**Files:**
- Modify: `pcs-backend/tests/e2e_flows/test_lane_smoke.py:102-157`（守卫）· `:234-243`（`_public_snapshot`）
- Modify: `pcs-backend/tests/e2e_flows/conftest.py:324-327`（**扩到 `_sync_engine`**）· 加 session 级 public 基线 fixture + 「第一时刻快照」fixture

**Interfaces:**
- Consumes: `information_schema.tables`（`table_schema = 'public'`）⇒ ⇒ **表清单来自数据库自己** ⇒ ⇒
  **不需要任何手抄清单**（⚖️ D3 ⇒ ⇒ 计划里**不再有** `lane_written_tables.py` ⇒ ⇒ 也不再有「表清单漂移」这个 TODO）
- Produces: `public_snapshot(engine) -> dict[str, tuple[int, int]]`（每张表 **count(\*) + max(xmin)**）
  ⇒ ⇒ 断言「session 启动时 == session 结束时」⇒ ⇒ **逐张相等**

- [x] **Step 1: 写失败测试**（**先证伪现守卫**）

⇒ ⇒ 加一条**自检**：故意往 public 写一行 / 改一行 / 删一行（用**独立连接**）⇒ ⇒ 守卫**必须红**
⇒ ⇒ 证明「它看得见泄漏」（守门测试自证 ⇒ 同族纪律：`docs/solutions/testing-issues/guard-test-fooled-by-lying-comment.md`）。

```python
@pytest.mark.e2e
async def test_public_guard_detects_a_leaked_row(public_engine, public_snapshot):
    """守卫自证：往 public 写一行 ⇒ 快照必须变化 ⇒ 否则它是空壳。"""
    before = public_snapshot(public_engine)
    with public_engine.begin() as conn:
        conn.execute(text("INSERT INTO public.audit_logs (action, resource_type) "
                          "VALUES ('E2E_LEAK_PROBE','PROBE')"))
    after = public_snapshot(public_engine)
    assert before["audit_logs"] != after["audit_logs"]
```

⇒ ⇒ ⚠️ **探针表要选「`public` 里存在、且**现守卫没数**它」的那张** ⇒ ⇒ 才有证明力
⇒ ⇒ 探针写的是 **`public` 里的一行**，模拟「如果车道泄漏会怎样」
⇒ ⇒ ⇒ **不需要**这张表在隔离 schema 里真的被车道写过（车道本来就不该写 public）
⇒ ⇒ `audit_logs` 是候选（它不在现守卫的 4 张表 `users/projects/streams/user_projects` 里）
⇒ ⇒ 开工时确认它**在 public 里存在**且**有可插的最小列**。

- [x] **Step 2: 跑测试确认失败**（现快照只数 4 张表 ⇒ 探针写进别的表 ⇒ 看不见 ⇒ 失败）

- [x] **Step 3: 实现**
① `_public_snapshot` 改成：**从 `information_schema.tables` 枚举 `public` 的全部表**
⇒ ⇒ 每张表取 `SELECT count(*), coalesce(max(xmin::text::bigint), 0) FROM public.<t>`
⇒ ⇒ ⚠️ **这个守卫只能在 E2E 车道（真 PG）跑** —— `xmin` 是 **PG 专有列** ⇒ ⇒
⇒ ⇒ 挪到默认车道（SQLite）会报 `no such column: xmin` ⇒ ⇒ 它的 `@pytest.mark.e2e`
**不许摘掉** ⇒ ⇒ ⚠️ 写进注释（否则下一个人会「顺手把它改成单测」）。
⇒ ⇒ ⚠️ **`xmin` 的语义写进注释**：事务 id 单调增 ⇒ 插入/删除/更新都会让它变 ⇒ ⇒
⚠️ **VACUUM FREEZE ⇒ 误报**（车道库不会 freeze ⇒ 但要知道）
⇒ ⇒ ⚠️ `public.` **显式限定**（`information_schema` 不受 `search_path` 约束 ⇒ cerebrum:1651）
② **session 级基线**：新增 session scope 的 fixture，在 `e2e_schema` 就绪后取一次 public 快照，
   在 session 结束时再取一次 ⇒ ⇒ 断言**逐张相等** ⇒ ⇒ ⚠️ **两种基线时机不能混**（车道内的
   `POST /api/v1/projects` 那条守卫仍保留 ⇒ ⇒ 它断「这条写路径没碰 public」⇒ ⇒ 两者**并存**）
③ **第三个 singleton**：把 `conftest.py:324-327` 的覆写**扩到 `_sync_engine`**
⇒ ⇒ **具体做法**（同步引擎的 schema 绑定与 async 不同，别照抄 async 那段）：

```python
# 同步引擎 ⇒ 用 **psycopg** 的 connect_args["options"] 绑 search_path
db_session_mod._sync_engine = create_engine(
    _lane_url(),                       # postgresql+psycopg://…（不是 asyncpg）
    connect_args={"options": f"-csearch_path={e2e_schema}"},
)
```

⇒ ⇒ ⚠️ `options=-csearch_path=…` 是 **psycopg** 的写法 ⇒ ⇒ `asyncpg` **不适用**
（async 侧现有那行用的是 `server_settings={'search_path': …}` ⇒ ⇒ 两者不可混抄）
⇒ ⇒ ⚠️ 造完记得**还原**（与 `_async_engine` 同一套 try/finally 形状）
⇒ ⇒ 目的：堵住「将来有人写一条走 `get_engine()` 的路径」
④ 写路径仍断「必须 200/201」（断**后果**不断**动作** ⇒ 已有，不要改）

- [x] **Step 3b: 补「基线早于任何写入」的钉子**（⚖️ D10：双快照）

```python
@pytest.mark.e2e
async def test_public_baseline_is_taken_before_any_lane_write(first_snapshot, public_baseline):
    """基线必须**早于**车道的任何写入 ⇒ ⇒ 两份「最初时刻」的快照必须相等。
    （若中间有写入 ⇒ 不等 ⇒ 顺序被写错时这条立刻红）"""
    assert first_snapshot == public_baseline
```

⇒ ⇒ `first_snapshot` = session 里**第一个**跑的 fixture 取的快照；`public_baseline` = 基线 fixture 取的快照
⇒ ⇒ 两者相等 ⇒ ⇒ 中间没有写入 ⇒ ⇒ 顺序对。

- [x] **Step 4: 跑 E2E 车道 + 变异自证**

Run: `cd pcs-backend && bash scripts/pytest_e2e.sh`
Expected: 全绿

⇒ ⇒ **变异自证**（三种都要红）：在 public 里手工插一行 / 删一行 / **改一行**（同表 UPDATE）
⇒ ⇒ ⚠️ **UPDATE 那条是本任务的核心**（`count` 不变 ⇒ 只有 `max(xmin)` 能看见）⇒ ⇒ 必须验过。

- [x] **Step 5: 提交**（`fix(P10-F): public 守卫快照全部表 + 补 _sync_engine + session 级基线（评审 #22）`）

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
- Modify: `pcs-backend/scripts/seed_e2e_flows.py:340-352`（`_ensure_workspace` **补 `owner_id`** ⇒ ⇒ `_ensure_project` 之后**回填 `project_id`**）· **新增 `_ensure_personal_workspace()`**（PERSONAL 类型 · `project_id` **留空** · owner=alice）
- Test: `pcs-frontend/tests/pages/DashboardPage.test.tsx`（**新建**，若已存在则**加一条**）· `pcs-backend/tests/e2e_flows/test_e2e_workspaces_visible.py`（**新建** ⇒ 「种子工作区在切换器里可见」）

**Interfaces:**
- Consumes: `app/models/project.py:116-119`（`owner_id` · `project_id` **均可空**）· `derive_user_id(username)`（与 `tests/e2e_flows/conftest.py:273` 同一口径 ⇒ **填派生 id，不是用户名**）
- Produces: `PLACEHOLDER_PROJECT_ID`（导出于 `src/constants/env.ts`）⇒ ⇒ `env.ts` 的兜底与 `DashboardPage` **共用一份**

⚠️ **两条已核实的硬事实**（决定本任务怎么做 ⇒ ⇒ **别再改这两条**）：

| 事实 | 证据 | 后果 |
|---|---|---|
| **前端永远带 `owner_id`** | `DashboardPage.tsx:28` ⇒ `<WorkspaceSwitcher ownerId={userId}>` ⇒ `WorkspaceSwitcher.tsx:55` ⇒ `workspaceApi.list(ownerId)` ⇒ `src/api/sprint1.ts:16` ⇒ `params: ownerId ? { owner_id: ownerId } : {}` | ⇒ ⇒ **dan 看不到 alice 的工作区**（后端 `owner_id=None` 才不过滤 ⇒ 但前端从不省略）⇒ ⇒ **E2E 必须用 alice 登录** |
| **种子只有**一个**工作区，且是 FORMAL** | `seed_e2e_flows.py:338-352`（`_ensure_workspace` 建 `FLOW_WORKSPACE_ID` · `workspace_type="FORMAL"`） | ⇒ ⇒ FORMAL 按设计**归属一个项目** ⇒ ⇒ 回填 `project_id` 后它**有**项目 ⇒ ⇒ **真后端里今天没有「无项目工作区」这个形态** ⇒ ⇒ ⇒ 必须**另建一个 PERSONAL 工作区**（`project_id` 留空）才测得了 ⇒ ⇒ 那正是**真实产品里「无项目工作区」的形态**（PERSONAL / TEMPORARY）⇒ ⇒ **按真实语义建**

- [x] **Step 1: 写失败测试**（前端）

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

⇒ ⇒ ⚖️ **评审 D11：正向路径也要断**（否则「永远不渲染面板」也能过）：

```tsx
it('选中的工作区**有** project_id ⇒ 面板渲染且发出 2 个请求（用真 project id）', async () => {
  render(<DashboardPage />);
  await user.click(screen.getByRole('combobox'));
  await user.click(screen.getByText('有项目工作区'));
  expect(await screen.findByTestId('input-checklist-panel')).toBeInTheDocument();
  expect(checklistApi.list).toHaveBeenCalledWith(REAL_PROJECT_ID);
  expect(checklistApi.completeness).toHaveBeenCalledWith(REAL_PROJECT_ID);
});
```

⇒ ⇒ ⚠️ **必须断 `projectId` 的值是「真项目 id」** ⇒ ⇒ 不是「渲染了」那种烟测 ⇒ ⇒
⇒ ⇒ 这条同时钉住「占位常量被当真值用」这个病（`src/constants/env.ts:13` 的 `PROJECT_ID`）。

- [x] **Step 2: 跑测试确认失败**（现在 `selected` truthy ⇒ 面板渲染 ⇒ 用了占位 id ⇒ 404）

- [x] **Step 3: 实现前端**⇒ ⇒ `const effectiveProjectId = selected?.project_id ?? null;` ⇒ ⇒
`{effectiveProjectId ? <InputChecklistPanel projectId={effectiveProjectId} /> : null}` ⇒ ⇒
`workspaceProjectId()` **删掉**（它的占位兜底正是缺陷来源）⇒ ⇒ 卡片标题区分
`selected ? (effectiveProjectId ? \`项目 ${effectiveProjectId.slice(0,8)}…\` : '该工作区未关联项目') : '选择工作区后查看清单'`
⇒ ⇒ `env.ts` 导出 `PLACEHOLDER_PROJECT_ID`，`env.ts` 的兜底与别处引用**统一引它**。

- [x] **Step 4: 写失败测试**（后端 · 「种子工作区可见」）

```python
@pytest.mark.e2e
async def test_seeded_workspace_is_visible_to_its_owner(client, ...):
    """种子工作区必须**在切换器里可见** ⇒ owner_id 要填派生 id（不是用户名）。"""
    r = await client.get(f"/api/v1/workspaces?owner_id={derive_user_id('alice')}")
    assert r.status_code == 200
    assert any(w["id"] == FLOW_WORKSPACE_ID for w in r.json())
```

⇒ ⇒ ⚠️ 断**后果**（「列表里有它」），不断**动作**（「我们调用了 seed」）。

- [x] **Step 5: 跑测试确认失败**（现在 `owner_id` 是 NULL ⇒ 列表为空）

- [x] **Step 6: 实现种子侧**（`scripts/seed_e2e_flows.py:340-352` + 新增一个函数）

① `_ensure_workspace`（FORMAL）填 `owner_id = derive_user_id("alice")`（**派生 id**）
② `_ensure_project` **之后**回填 `workspace.project_id = project.project_id` ⇒ ⇒
⚠️ **顺序约束写进注释**（工作区先于项目创建 ⇒ 提前填会撞 FK）
⇒ ⇒ ⚠️ 「FORMAL 工作区要不要回填 `project_id`」⇒ ⇒ **按真实语义回填**（FORMAL 归属一个项目）
⇒ ⇒ ⇒ 代价：「无项目工作区」在真后端消失 ⇒ ⇒ ⇒ **所以要 ③**

③ ⭐ **新增 `_ensure_personal_workspace()`**：建一个 **PERSONAL** 类型的工作区
   （`workspace_type="PERSONAL"` · `project_id` **留空** · `owner_id = derive_user_id("alice")`
   · `status="ACTIVE"` · 名字带「无项目」以便 E2E 按文本选）
   ⇒ ⇒ **为什么**：真实产品里「个人/临时工作区」**按设计**没有项目
   （mock 种子的 `ws-personal-002` / `ws-temp-003` 就是 `project_id: null`）
   ⇒ ⇒ 真后端要有这个形态可测 ⇒ ⇒ **按真实语义建一个** ⇒ ⇒ 不新增「第三种」工作区类型
   ⇒ ⇒ ⚠️ **不建 TEMPORARY**（一个就够 ⇒ ⇒ YAGNI）⇒ ⇒ ⚠️ 名字要**唯一**（`_get_or_create` 按 id 查 ⇒ ⇒ 给它一个常量 id）

- [x] **Step 6b: 加真后端 E2E 断言**（⚠️ **「保留无项目工作区供测」是意图，不是证据**）

⇒ ⇒ ⚠️ **登录身份必须是 `alice`**（不是 `dan`）⇒ ⇒ 理由见上面「两条已核实的硬事实」：
⇒ ⇒ **前端永远带 `owner_id`** ⇒ ⇒ dan 看不到 alice 的工作区 ⇒ ⇒ 用 dan 会**选不中** ⇒ ⇒
⇒ ⇒ ⇒ alice 是种子工作区的 owner ⇒ ⇒ **它俩一致** ⇒ ⇒
⇒ ⇒ ⇒ 备选：若将来决定让 SYSTEM_ADMIN 能看全部 ⇒ ⇒ 那要改**前端**（`ownerId` 可选）⇒ ⇒ 属另一批。

```ts
// pcs-frontend/e2e/real_backend_flows.spec.ts（新增一条）
test('真后端：选「无项目的工作区」⇒ 清单面板不渲染且无 404 / 无 console error', async ({ page }) => {
  await loginViaUi(page, 'alice');
  await page.getByRole('combobox').click();          // WorkspaceSwitcher
  await page.locator('.ant-select-item-option', { hasText: '无项目' }).click();
  await expect(page.getByTestId('input-checklist-panel')).toHaveCount(0);
  // ⇒ 白名单外的 4xx / console error 必须为空（本仓既有断言会兜住）
});
```

⇒ ⇒ ⭐ **再补一条正向断言**（同一身份 ⇒ ⇒ 选 FORMAL 工作区 ⇒ ⇒ 面板**要**渲染且请求带**真项目 id**）：

```ts
test('真后端：选有项目的工作区 ⇒ 面板渲染且请求带真 project id', async ({ page }) => {
  await loginViaUi(page, 'alice');
  await page.getByRole('combobox').click();
  await page.locator('.ant-select-item-option', { hasText: 'E2E Flows Workspace' }).click();
  await expect(page.getByTestId('input-checklist-panel')).toBeVisible();
  // ⇒ 断请求里的 projectId 是**真项目 id**，不是占位常量
});
```

⇒ ⇒ ⚠️ **这两条必须用真后端通道跑**（`npm run e2e:real`）⇒ ⇒ mock 通道**证明不了**它们
⇒ ⇒ ⇒ 理由：mock 的工作区种子**本来就**把 PERSONAL 的 `project_id` 设成 null ⇒ ⇒ mock 下第一条恒绿
⇒ ⇒ ⇒ 而 mock 的 FORMAL 工作区用的**就是占位 id** ⇒ ⇒ 第二条在 mock 下**会红**（这正是它该抓的病）。

- [x] **Step 7: 跑测试 + typecheck + lint**

Run: `cd pcs-frontend && npm run test -- tests/pages/DashboardPage.test.tsx && npm run typecheck && npm run lint`
Run: `cd pcs-backend && bash scripts/pytest_e2e.sh`
Run: `cd pcs-frontend && npm run e2e:real`      # ← Step 6b 那条在此跑
Expected: 全绿

- [x] **Step 8: 提交**（`fix(P10-F): 仪表盘守卫条件改成「拿到了真 project_id」（评审 #24）`）
⇒ ⇒ 顺带在 `TODOS.md` 登记：「**前端还有别处把占位常量当真值用**」（`env.ts:13` 的 `PROJECT_ID`
被 `routeWrappers.tsx:136,212,331,335` 当**真 id** 用 ⇒ ⇒ 那是 TODO-159 那 3 个页面的根因之一）

---

### Task F2-T3: compose 的 `migrate`/`seed` **进同一把锁**（评审 #15 第 ① 步 · TODO-163）

**Files:**
- Modify: `pcs-backend/scripts/compose_test_stack.sh`（**宿主侧**取锁）· `docker-compose.yml`（`migrate`/`seed` 两个服务的 `command` ⇒ 注明「必须经宿主脚本」）
- Test: `pcs-backend/tests/scripts/test_compose_test_profile.py`（**既有** ⇒ 加一条）

**Interfaces:**
- Consumes: `scripts/pytest_pg.sh` 的锁路径口径（`$BACKEND_DIR/.tmp/lane.lock`）⇒ ⇒ **同一把锁**
- Produces: `compose_test_stack.sh` 在调用 compose **之前**抢锁 ⇒ ⇒ 抢不到 ⇒ **非零退出**并说清「另一条车道在跑」

- [x] **Step 1: 写失败测试**（`tests/scripts/test_compose_test_profile.py`）

```python
def test_compose_test_stack_takes_the_lane_lock_before_invoking_compose():
    body = lane_script_body(BACKEND / "scripts" / "compose_test_stack.sh")
    assert "lane.lock" in body, "起测试栈的脚本没抢车道锁 ⇒ 与车道并发 ⇒ DDL 等锁"
    assert body.index("lane.lock") < body.index("docker compose"), "锁必须在调 compose **之前**抢"
```

- [x] **Step 1b: 补「抢不到锁」的行为测试**（⚖️ 评审 D10：**静态断不够**）

⇒ ⇒ 照搬 `tests/scripts/test_pytest_pg_gate.py:165-218` 的现成做法（**假 docker** + **真占锁进程**）：

```python
def test_compose_test_stack_fails_when_the_lane_lock_is_held(tmp_path):
    """抢不到锁 ⇒ **非零退出**且说清「另一条车道在跑」⇒ ⇒ 只断文本等于没断。"""
    fake_bin = tmp_path / "bin"; fake_bin.mkdir()
    (fake_bin / "docker").write_text("#!/bin/sh\necho 'fake'\nexit 0\n")
    (fake_bin / "docker").chmod(0o755)
    lock_file = tmp_path / "lane.lock"
    holder = subprocess.Popen(["flock", "-n", str(lock_file), "sleep", "30"],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        r = subprocess.run(["bash", str(SCRIPT)], env={**os.environ,
                           "PATH": f"{fake_bin}:{os.environ['PATH']}",
                           "PCS_PGTEST_LANE_LOCK": str(lock_file)},
                          capture_output=True, text=True, timeout=60)
        assert r.returncode != 0, "锁被占着却跑通了 ⇒ 两条车道不互斥"
        assert "另一条车道" in (r.stdout + r.stderr)
    finally:
        holder.terminate(); holder.wait(timeout=10)
```

⇒ ⇒ ⚠️ 脚本要支持 `PCS_PGTEST_LANE_LOCK` **覆盖**（守门测试不能抢真车道的锁 ⇒ 同
`docs/solutions/testing-issues/guard-test-must-use-its-own-lane-lock.md`）。

- [x] **Step 2: 跑测试确认失败**
- [x] **Step 3: 实现**（`compose_test_stack.sh`）⇒ ⇒ 与 `pytest_pg.sh` **同款**的锁段
（`exec 9>"$LOCK_FILE"` + `flock -n 9` ⇒ 抢不到 ⇒ 退出码 1 + 「另一条车道正在跑」）⇒ ⇒
⚠️ **路径口径必须一致**（`${BACKEND_DIR}/.tmp/lane.lock`）⇒ ⇒ `mkdir -p` 也要有
⇒ ⇒ ⚠️ **支持 `PCS_PGTEST_LANE_LOCK` 覆盖**（Step 1b 要用）。
⇒ ⇒ `docker-compose.yml` 两个服务的注释补一句「**必须**经 `scripts/compose_test_stack.sh` 起（它抢车道锁）⇒ 直接 `docker compose run` 会绕过锁」。
- [x] **Step 4: 跑测试 + 手工验一次**（`bash scripts/compose_test_stack.sh` ⇒ 应正常跑完 ⇒ 且 `pcs-backend/.tmp/lane.lock` 被创建）
⇒ ⇒ ⚠️ **本机 docker registry 拉不动**（实测 `docker manifest inspect` 挂 >120s）⇒ ⇒
**容器侧**的 flock 路线**不可验证** ⇒ ⇒ 本任务选**宿主侧**取锁（零镜像改动）⇒ ⇒
⇒ ⇒ 残留：直接 `docker compose run --rm seed` **仍能绕过锁** ⇒ ⇒ 登记 TODO（P10-C）。
- [x] **Step 5: 提交**（`fix(P10-F): 测试栈起服也进车道锁（评审 #15 第 ① 步）`）
⇒ ⇒ ⚠️ **同时关闭 TODO-163**（在 `TODOS.md` 里标「2026-11-17 关闭 · `<commit>`」）

---

### Task F2-T4: **扩展 repo 级 rowKey 棘轮** ⇒ 禁掉 index 型 rowKey（TODO-162）

> ⚖️ **评审 D8：扩展已有的棘轮，不写页面级测试**
> ⇒ ⇒ 仓里**已有** `pcs-frontend/tests/pages/rowKey_contract.test.ts`（repo 级 ⇒ 扫 `src/pages/**/*.tsx`
> 的 `rowKey="字段"` ⇒ 断言该字段真的在契约里）⇒ ⇒ 它的 docstring **明写**「只取字符串形式 ——
> 函数形式无法静态判定」⇒ ⇒ 回调形式是它**已知且明写**的盲区
> ⇒ ⇒ 全仓 index 型 rowKey **只有 1 处**（`FormulaEditorPage.tsx:241`）⇒ ⇒
> ⇒ ⇒ 修法 = **把棘轮扩到函数形式** ⇒ ⇒ 一处复发即红（而不是一页一断言）

**Files:**
- Modify: `pcs-frontend/tests/pages/rowKey_contract.test.ts`（**扩到函数形式** ⇒ 禁 index 型回调）
- Modify: `pcs-frontend/src/pages/config/FormulaEditorPage.tsx:241`（唯一一处命中 ⇒ 改成稳定 key）
- Modify: `pcs-frontend/e2e/real_backend_route_sweep.spec.ts`（**删掉白名单里那条** ⇒ ⇒ 白名单外必须为空 ⇒ ⇒ 删条目后仍要绿 ⇒ ⇒ **这本身就是验证**）

**Interfaces:**
- Consumes: `rowKey_contract.test.ts` 已有的扫描机制（`readFileSync` + 正则遍历 `src/pages`）
- Produces: 棘轮新增一条断言 —— **全仓不得存在「回调第二参是 `idx`/`index`」的 `rowKey`**

- [x] **Step 1: 写失败测试**（扩棘轮 ⇒ ⇒ **它必须先红**）

```ts
it('⚠️ 不得用 antd 回调的 **index** 参数当 rowKey（antd 5.29 起弃用 · TODO-162）', () => {
  const offenders: string[] = [];
  for (const file of walkTsx(SRC)) {
    const src = readFileSync(file, 'utf-8');
    // 函数形式：rowKey={(...args) => ...} ⇒ 第二参叫 idx/index ⇒ 行身份随排序漂移
    for (const m of src.matchAll(/rowKey=\{[^}]*?\(\s*[^)]*,\s*(idx|index)\b[^}]*\}/g)) {
      offenders.push(`${file.replace(SRC + '/', '')} → ${m[0].slice(0, 80)}`);
    }
  }
  expect(offenders, `这些 rowKey 用了 index 参数：\n${offenders.join('\n')}`).toEqual([]);
});
```

⇒ ⇒ ⚠️ **必须先跑一次确认它红**（现在命中 `FormulaEditorPage.tsx:241`）⇒ ⇒ 这就是 RED。

- [x] **Step 2: 改那一处**（`FormulaEditorPage.tsx:241`）⇒ ⇒ ⚠️ **不能**简单改成 `rowKey={(r) => r.name}`
（参数名**允许空/重复** ⇒ antd 会报 Duplicate row key ⇒ 换成另一种告警）⇒ ⇒ **做法**：
在 `FormulaEditorPage` 的 **draft 之外**维护一份「每行的稳定 key」（`useState<string[]>` ⇒ 新增行 ⇒
`crypto.randomUUID()`）⇒ ⇒ `rowKey` 用那个字符串字段 ⇒ ⇒
⚠️ **key 不得进 `FormulaEditor` 公开形状**（会漏进保存的载荷）⇒ ⇒
⇒ 若实现发现必须改公开类型 ⇒ ⇒ **停下并登记 TODO**（契约面 ⇒ 属另一批）。

- [x] **Step 3: 跑测试确认通过**

Run: `cd pcs-frontend && npm run test -- tests/pages/rowKey_contract.test.ts && npm run typecheck && npm run lint`
Expected: 棘轮 PASS（禁 index 型）· typecheck/lint clean

- [x] **Step 4: 跑真后端通道**（**白名单删条目后仍全绿** ⇒ 这就是「组件修好后删白名单条目」的证据）

Run: `cd pcs-frontend && npm run e2e:real`
Expected: 7+ passed（`/config/formula-editor` 的 antd 弃用告警**不再出现** ⇒ ⇒ 白名单里那条删掉）

- [x] **Step 5: 提交**（`fix(P10-F): rowKey 棘轮扩到函数形式 + 禁 index 型（TODO-162）`）
⇒ ⇒ ⚠️ 顺带在 `TODOS.md` 关闭 **TODO-162**（根因 = 棘轮的盲区 ⇒ 盲区已补 ⇒ 不是「页面改好了」而是「这类写法以后进不来」）。

---

### Task F2-T5: 默认车道的**隔离性** —— 别碰开发库与真 Redis（评审期间新发现）

> 🔎 **2026-11-17 评审期间实测发现**（不在原 8 条里 ⇒ ⇒ 同族但**新**）：
> ⇒ ⇒ 跑默认车道（`uv run pytest`）时，进程 socket 里出现
> **`127.0.0.1:5432`（开发库 pcs）** 与 **`127.0.0.1:6379`（真 Redis）** 的连接
> ⇒ ⇒ 根因：`tests/conftest.py:118-119` 只把**异步**引擎换成 `sqlite+aiosqlite:///:memory:`
> ⇒ ⇒ 而 `app/db/session.py:22-39` 的**同步**引擎 `_sync_engine` 仍按 `settings.database_url`
> 连**开发库**；Redis 侧 `app/services/edit_lock.py:142` 与 `app/services/broadcaster.py:80,144`
> 直接 `aioredis.Redis.from_url(settings.redis_url)`（`config.py:44` 默认 `redis://localhost:6379/0`）
> ⇒ ⇒ 违反 CLAUDE.md「**单测车道绝不碰开发库**」
> ⇒ ⇒ 与 hermes #22 的第三条（`_sync_engine` 是第三个未被覆写的 singleton）**同一形状**，
> 但发生在**默认车道**（⇒ 那一侧从来没被审过）

**Files:**
- Modify: `pcs-backend/tests/conftest.py`（把 `_sync_engine` 覆写成 SQLite 同步引擎 · Redis 指向替身或禁用）
- Test: `pcs-backend/tests/test_lane_isolation.py`（**新建** ⇒ 断「默认车道不连真库/真 Redis」）

**Interfaces:**
- Consumes: `app/db/session.py` 的三个单例（`_sync_engine` · `_async_engine` · `_async_session_factory`）· `app/core/config.py::settings.redis_url`
- Produces: `assert_no_real_backends()` —— 一条**自证**断言：跑测试期间**不得**有到 5432/6379 的连接

- [x] **Step 1: 写失败测试**（**先证伪现状**）

```python
def test_default_lane_never_connects_to_a_real_database_or_redis():
    """默认车道**不得**连开发库（5432）或真 Redis（6379）⇒
    今天的实测：进程 socket 里就挂着这两条连接（且整轮跑挂了 33 分钟）。"""
    # 手段：扫本进程已建立的 socket（/proc/self/net/tcp 或 psutil）⇒ 断没有 5432/6379
    # 备选：在 conftest 里把两个客户端的 URL 改成不可路由的端口 ⇒ 任何真实连接都会抛错
    ...
```

⇒ ⇒ ⚠️ **断法 = 「把 URL 改成不可路由端口」**（与 Step 3 的实现**同一种** ⇒ ⇒
⇒ ⇒ 跨平台、且「连了就炸」比「查到了再判」更硬）⇒ ⇒
⇒ ⇒ ⇒ 测试断言的是「**conftest 把 `settings.redis_url` / `settings.database_url` 改成了
不可路由目标**」⇒ ⇒ **与实现同形** ⇒ ⇒ 不用「扫 socket」（Linux 专有）⇒ ⇒
⇒ ⇒ ⇒ 扫 socket 只作为**额外的手工核验**（Step 4 的 `ss -tnp`）保留 ⇒ ⇒
⇒ ⇒ 但需要把 `settings.redis_url` 与 `settings.database_url` 在 conftest 里**改掉** ⇒ ⇒
⚠️ `settings` 是 **pydantic 缓存实例** ⇒ ⇒ 改法照 `alembic/env.py` 的口径（**进程内**改环境变量 **在 import 之前**）

- [x] **Step 2: 跑测试确认失败**（现状必红 ⇒ ⇒ 证明「默认车道确实连了真库/真 Redis」）
- [x] **Step 3: 实现**
① `tests/conftest.py` 里把 `_sync_engine` 覆写成 **SQLite 同步引擎**（`sqlite:///:memory:`）⇒ ⇒
   ⇒ 与 `_async_engine` 的覆写**成对**（⇒ ⇒ 别再留第三个 singleton 裸奔）
② Redis：把 `settings.redis_url` 指向**不可路由的端口**（如 `redis://127.0.0.1:1/0`）⇒ ⇒
   ⇒ 或用 `fakeredis` 替身（⚠️ 若仓里没有 ⇒ ⇒ **不新增依赖** ⇒ ⇒ 选「不可路由端口」）
③ ⚠️ **副作用要评估**：若有测试**依赖**真 Redis（集成语义）⇒ ⇒ 那类测试应移到
   `scripts/pytest_pg.sh` 那条**真 PG 车道**里 ⇒ ⇒ 登记 TODO，不在本条硬改。
- [x] **Step 4: 跑默认车道**（**必须能跑完、不许挂**）

Run: `cd pcs-backend && uv run pytest -q`
Expected: 全绿且**不挂** ⇒ ⇒ ⚠️ 2026-11-17 那次跑到 22% 卡死 33 分钟 ⇒ ⇒ **这条本身就是判据**

⇒ ⇒ ⚠️ **「要全绿」与「不许连真 Redis」之间的悖论怎么解**（执行者按此判，**不许卡住**）：
若因为 Redis URL 指向不可路由端口而**有测试变红** ⇒ ⇒ **逐条分类**：

| 现象 | 判据 | 处置 |
|---|---|---|
| 该测试**依赖真 Redis 的语义**（编辑锁 / pubsub 的行为） | 它的断言需要真 Redis 才有意义 | ⇒ 在**该测试**上标 `@pytest.mark.skip(reason="依赖真 Redis ⇒ 迁到 scripts/pytest_pg.sh 车道（TODO-165）")` ⇒ ⇒ **并登记 TODO** ⇒ ⇒ F2-T5 **不算失败** |
| 该测试**只是碰巧连了真 Redis**（并不需要它的语义） | 断言与 Redis 无关 | ⇒ ⇒ **修它**（让它用替身/桩）⇒ ⇒ 这是本条要清的**真泄漏** ⇒ ⇒ **不许 skip** |
| 整轮**挂住**（不结束） | 卡在等 Redis/PG | ⇒ ⇒ **本条判失败** ⇒ ⇒ 查是谁在等 ⇒ ⇒ 它的连接必须指向不可路由端口 |

⇒ ⇒ **底线**：F2-T5 的完成判据 = 「默认车道**跑完且绿**」+「跑的过程中**没有**到 5432/6379 的连接」
⇒ ⇒ **允许**为「依赖真 Redis 语义」的测试加 skip（且必须留 TODO）⇒ ⇒ **不允许**整轮挂住。

⇒ ⇒ **同时验**：跑完后 `ss -tnp | grep -E ":5432|:6379"` **不得**出现 pytest 的连接。

- [x] **Step 5: 提交**（`fix(P10-F): 默认车道隔离同步引擎与 Redis（评审期间新发现）`）
⇒ ⇒ 顺带在 `.wolf/buglog.json` 记一条（bug-2181）⇒ ⇒ 在 `TODOS.md` 记「依赖真 Redis 的测试迁到真 PG 车道」

---

# F3 · 守卫覆盖审计（TODO-129）+ 三条越权债复核

> **本批前置**：无（P10-B 的车道与真后端通道已就位 ⇒ 审计有观测面）。
> **本批产出**：**结论**（不是「未审即没问题」）⇒ ⇒ 一份缺口清单（每条带 TODO）+ 一份「已覆盖」清单（带断言位置）。

### Task F3-T1: 划定**审计范围**（用户裁决 Q10 的落地）

⇒ ⇒ 候选模块：`app/api/v1/config.py`（12 端点）· `report_builder.py`（9）· `psychro.py`（13）· 其它
非物流面模块 ⇒ ⇒ **范围由人裁决**（主计划 Q10）⇒ ⇒ **本任务的产出是「范围提案 + 每条候选的初判」**
⇒ ⇒ 提交给人 ⇒ ⇒ **不要**自己把范围定死。

⇒ ⇒ ⚠️ **开工边界**（否则执行者第一步就卡在等人）：
**T1 可以直接开工**（产出范围提案 + 初判 ⇒ 交人）⇒ ⇒
**T2 / T3 等人批了范围再开** ⇒ ⇒ ⇒ 批次地图里「F3 现在能开」指的是 **T1** ⇒ ⇒ 不是整批。

### ✅ 范围裁决（**2026-11-18 · 人**）—— F3-T2/T3 的**开工依据**

⇒ ⇒ 完整提案（含初判 · 三态口径 · 拆表）落**工作区**（gitignored ⇒ 不进仓库）：
`.superpowers/sdd/2026-11-17-p10-batch-f-production-readiness/proposals/guard-coverage-scope-proposal.md`
⇒ ⇒ ⚠️ **`docs/solutions/security-issues/` 是 F3-T5「结论」的位置** ⇒ ⇒ 提案**不放那儿**。

| 裁决项 | 结论 |
|---|---|
| **审计范围** | **A + B + D(敏感)**，**C 档不审**（无项目级数据读写 ⇒ 越权语义不成立）⇒ ⇒ ≈ **63** 端点（AST 实测） |
| **全局资源** | 按**敏感度**分级：审计日志 / 系统参数 **high** · 样式**写 medium** · 样式**读** / 枚举 **不审** |
| **分批** | **4 子批**：`T2a` config+report_builder（**先开**）· `T2b` report+records · `T3a` psychro.results+工作区/身份面 · `T3b` audit+system_settings+meta |
| **工作区 id 令牌** | ① **保留**（改语义动前端消费点 ⇒ 属另一批）· ② **关联项目数据必须审**，独立于 ① |
| **判据** | **照用 D6**（4 问 + 抽样变异 ≥3）⇒ ⇒ 第 3 问补：**项目守卫返 403 = 缺口**（泄露存在性） |

⚠️ **裁决带来的三处「初判口径」修正**（不改裁决本身 ⇒ ⇒ 改的是提案的失真）：

1. **守卫口径改成三态** ⇒ ⇒ `require_roles`（角色闸）/ `current_actor`（只认证）
   **都不是**项目授权闸 ⇒ ⇒ 算成「有守卫」⇒ ⇒ **假阴性**（真缺口被漏掉）。
2. **候选缺口拆表**（无守卫 / 有认证无项目授权 / 本地封装）⇒ ⇒ 口径才不含糊。
3. **端点数以 AST 枚举为准** ⇒ ⇒ **312**（不是 313）⇒ ⇒ 枚举脚本
   `pcs-backend/scripts/audit_list_endpoints.py`（可复跑 ⇒ ⇒ 守卫测试 8 条）。

⚠️ ⚠️ **实测推翻了一条初判**：`config.py` 的 11 个端点 **`authz` = 0**
（全是 `require_roles` + `current_actor`）⇒ ⇒ 原提案写「config 初判已覆盖」是**错的**
⇒ ⇒ 它是 **#5 型越权的头号重灾区** ⇒ ⇒ **T2a 先开它**。

### Task F3-T2 ~ T3: 逐模块**审计**（守卫覆盖面）

⚖️ **评审 D6：判据先写死**（否则「有守卫」不可复核 ⇒ ⇒ 而这正是本仓反复吃过的亏）

⇒ ⇒ **每个端点必答 4 问**（缺任一问 ⇒ 即算缺口）：

| # | 必答问题 | 合格答案的样子 |
|---|---|---|
| ① | 端点从哪个参数拿到**资源 id**（project_id / 设备 id / …）？ | `project_id: UUID`（路径参数/查询参数，写明行号） |
| ② | 该 id 是否**按当前用户/项目**做授权判定？ | `check_project_access_or_404(...)`（行号） |
| ③ | 未授权时**返回什么**？ | 404（与「不存在」同形）/ 403 / **200**（⇒ ⇒ 这是缺口） |
| ④ | 授权判定发生在**哪一行**？ | 文件:行号 |

⇒ ⇒ 输出**一张统一表格**（模块 · 端点 · ①~④ 的答案 · 结论「已覆盖 / 缺口」）
⇒ ⇒ 缺口 ⇒ **逐条登记 TODO**（不许合并成「若干缺口」）⇒ ⇒
已覆盖的 ⇒ **给出断言位置**（哪个测试守着）⇒ ⇒ ⚠️ **「代码里有守卫调用」不等于「有断言」**
⇒ ⇒ ⇒ 两者都要填。

⇒ ⇒ ⚖️ **抽样变异**（D6 的另一半）：从「已覆盖」的端点里**抽样 ≥ 3 个**
⇒ ⇒ 对每个：**临时删掉它的守卫** ⇒ ⇒ 相关断言**必须红** ⇒ ⇒ 还原
⇒ ⇒ ⚠️ 若某个端点**没有对应断言** ⇒ ⇒ 变异后**无人应答** ⇒ ⇒ 那本身就是缺口（登记 TODO）

⇒ ⇒ 范围量（已知）：`config.py` 12 · `report_builder.py` 9 · `psychro.py` 13 = **34 端点**

### Task F3-T4: 三条越权债**复核**（不重做）

⇒ ⇒ TODO-132（禁用用户）· TODO-133（workspace 归属）· TODO-135（mock 旁路）⇒ ⇒ ✅ 已由 P9B-4 闭合
⇒ ⇒ 本批**只复核**：每条找一条**现存**的断言 + 跑一次 ⇒ ⇒ 写「复核结论 + 证据」
⇒ ⇒ ⚠️ 复核的标准与 F3-T2 相同（**断言必须对它命名的缺陷敏感** ⇒ ⇒ 抽一个做变异验证）。

### Task F3-T5: 审计结论**落文档 + 账簿**

⇒ ⇒ 落 `docs/solutions/security-issues/guard-coverage-audit-logistics-adjacent-modules.md`
（**新建** ⇒ frontmatter 照同目录既有条目）⇒ ⇒ 内容 = 范围 · 方法 · 逐端点表格（①~④）· 抽样变异记录 · 缺口 TODO 清单 ⇒ ⇒
⇒ ⇒ 同时更新 `TODOS.md`（每条缺口一条）⇒ ⇒ **不许**写「未审即没问题」。

---

# F4 · 生产就绪的**技术项**（前置：P10-C 落地）

> **本批前置**：P10-C（部署与可观测性）落地 ⇒ ⇒ 否则没有可扫的镜像、没有部署物、没有告警。
> **SPEC 依据**：§3.2.7 的「安全扫描 / 依赖漏洞 / 容器镜像扫描 / 回滚演练 / 数据迁移演练」。
> ⚖️ **评审 D4：只用已装的工具** ⇒ ⇒ `bandit`（1.9.4 已装）· `uv audit`（**内建于 uv 0.11.2**）· `npm audit`
> ⇒ ⇒ **不新增 pip-audit / trivy 二进制**（除非 P10-C 给出镜像后确实需要）
> ⚠️ **本机事实**：宿主到 npmjs/github/ghcr.io **TCP 可达**；但 **docker registry 拉不动**
> （`docker manifest inspect` 挂 >120s）⇒ ⇒ **容器里装工具**这条路不通。

### 任务清单（开工时把每个任务写成 TDD 步骤）

- **F4-T1 安全扫描**（SAST：`bandit -r app/` ⇒ **判据用「高危为 0」** ⇒
  ⚠️ bandit 的严重度档是 `HIGH/MEDIUM/LOW` ⇒ ⇒ 判据 = `bandit -r app/ -ll`（只报 HIGH 及以上）**退出 0**
  ⇒ ⇒ 工具与基线写进 `scripts/`（一个可复跑的脚本）
- **F4-T2 依赖漏洞**（⚖️ D14：**按可达性分级处置**，不是「一刀切为 0」）
  - 命令：`cd pcs-backend && uv audit --no-dev`（生产依赖）+ `cd pcs-frontend && npm audit --production`
  - **已知基线（2026-11-17 实测）**：

    | 包 | 锁定版本 | 条数 | 修复版本 | 可达性 |
    |---|---|---|---|---|
    | **authlib** | 1.8.0 | **14**（含 JWS/JWT 签名伪造） | 1.9.0 / 1.9.1 | ⚠️ `pyproject` 直接声明，但**全仓零 import** ⇒ ⇒ **删掉这一行即清除** |
    | **pyjwt** | 2.13.0 | **29** | 2.14.0 / 2.15.0 | ✅ 直接依赖 · `app/api/v1/config.py:47` · `app/api/v1/auth.py:13` · `app/core/security.py:11`（签发令牌） |
    | pillow | 12.3.0 | 62 | 13.0.0 | ⚠️ 传递自 **reportlab**（生产 PDF 报表）⇒ ⇒ **大版本升级 ⇒ 需验证 reportlab 兼容性** |
    | pyasn1 | 0.6.4 | 4 | 0.6.5 | 传递自 ldap3（生产 LDAP 认证）⇒ ⇒ 补丁级 |
    | mako | 1.4.1 | 2 | 1.4.2 | 传递自 alembic（生产）⇒ ⇒ 补丁级 |
    | joserfc | 1.7.5 | 1 | — | 传递自 authlib ⇒ ⇒ 删 authlib 后自动消失 |
    | certifi | 2026.7.22 | 2 | 2026.10.18 | 传递 ⇒ 补丁级 |
    | pypdf | 6.19.0 | 18 | 6.20.x–6.21.3 | **dev 组** ⇒ ⇒ 不进生产 |

  - **判据**：**生产依赖** ∧ **可达**（我们的代码真的 import/调用）∧ **有高危** ⇒ ⇒ **必须修**；
    其余逐条给**处置结论**（修 / 豁免+理由 / 不进生产）⇒ ⇒ 产出一张**依赖漏洞处置表**
    （包 · 版本 · 条数 · 可达性 · 处置结论）⇒ ⇒ **不许**只写「已扫描」
  - **立即可做**（本批内）：① 删 `authlib`（零 import ⇒ 零代码风险 ⇒ 清除 14 条）
    ② 升 `pyjwt` 到 2.15.0 ⇒ ⇒ ⚠️ **必须验 bug-091 的加固还在**（`options={'require': ['exp','iat','sub']}`）
    ③ 升 mako / pyasn1 / certifi（补丁级）④ pillow ⇒ ⇒ **先查 reportlab 5.0.1 是否支持 pillow 13**
    ⇒ ⇒ 不支持 ⇒ ⇒ 记「豁免 + 理由 + 上游 issue」，**不硬升**
- **F4-T3 容器镜像扫描**（镜像来自 P10-C ⇒ ⚠️ **P10-C 未落地 ⇒ 本任务不启动**
  ⇒ ⇒ 届时选型：`trivy` 二进制可从 github 下载（可达）⇒ ⇒ 但**容器里跑不行**（registry 拉不动））
- **F4-T4 回滚演练**（版本回滚流程 ⇒ 真的回滚一次 ⇒ 记录命令 + 输出）
- **F4-T5 数据迁移演练**（迁移 + **回滚**的数据兼容性 ⇒ 在**隔离 schema** 上跑 upgrade→downgrade→upgrade）
- **F4-T6 证据落盘**（每项一条「命令 + 输出 + 结论」⇒ 落 `docs/` ⇒ **不许**写「已验证」而没有命令
  ⇒ ⇒ ⚠️ **「跑过」≠「按步骤跑通」** ⇒ ⇒ 两者的措辞必须分开写）

---

# F5 · 生产就绪的**运维项**（前置：P10-C + P10-E 落地）

- **F5-T1 监控告警演练**（告警**触发** / **静默** / **升级**三条路径各留证据 ⇒ ⚠️ 依赖 P10-C 的 exporters 与告警规则）
- **F5-T2 备份恢复演练**（RPO ≤ 30min · RTO ≤ 2h ⇒ 记**模板**与**实测耗时**）
- **F5-T3 应急联系人**（明确到人/角色 ⇒ ⚠️ 涉及真实人员 ⇒ **交人确认**，不代填）
- **F5-T4 上线检查清单**（SPEC §3.2.7 的「上线检查清单」⇒ 逐项带证据链接
  ⇒ ⇒ ⚠️ **不得**写「CI 会跑 E2E」（既有裁决：不新建 CI 流水线 ⇒ D25））
- **F5-T5 Go/No-Go 会议纪要模板**（模板 + 填写指引 ⇒ ⚠️ 模板里的「决策」栏留空 ⇒ 不代签）

---

# F6 · 收口

- **F6-T1 部署前置清单**（⚖️ D5：**就在开发库 `pcs` 上跑一次**）
  - **只读部分**（进发布前闸门，一条**只读**脚本，不写库）：
    `SELECT count(*) FROM users WHERE user_id <> uuid5_derived(username)` = 0
    ⇒ ⇒ 授权行计数（`user_projects` 的行数 vs 期望的环境矩阵）⇒ ⇒ 两条都**只读**
  - **写部分**（**一次性运维动作** ⇒ 在**开发库 `pcs`** 上真跑一次）：
    ① `scripts/seed_user_project_access.py --username <u> --project <uuid>`（幂等 ⇒ 重复跑安全）
    ② TODO-137 的遗留账号迁移（`user_id` → 派生 id）⇒ ⇒ ⚠️ **必须写成幂等**
    （先查后改 ⇒ 已在目标形态的行**跳过**）⇒ ⇒ 否则重跑会把 id 改两次
  - ⚠️ **跑之前**：`SELECT count(*)` 的基线先记下来 ⇒ ⇒ 跑完再查一次 ⇒ ⇒ 两条数对得上才算过
  - ⚠️ **写库的库名必须显式写出来**（`.env` 的 `DATABASE_URL` 指向 `pcs` ⇒ ⇒ **不要**用默认值蒙混）
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
| 13 | ⚖️ ~~**「隔离表清单」没有仓库级真相源**~~ | ✅ **已消解** —— 评审 D3 改成「快照 `public` 的**全部表**」⇒ ⇒ **不再需要任何手抄清单** ⇒ ⇒ 表清单来自 `information_schema` | — |
| 14 | ⚖️ **pillow 62 条要升 13.0.0（大版本）**，但它传递自 **reportlab**（生产 PDF 报表） | 兼容性未验证 ⇒ ⇒ F4-T2 的处置：**先查 reportlab 5.0.1 是否支持 pillow 13** ⇒ ⇒ 不支持 ⇒ ⇒ 记「豁免 + 理由 + 上游 issue」⇒ ⇒ **不硬升** | F4-T2 |
| 15 | ⚖️ **升 pyjwt（29 条）要验 bug-091 的加固还在** | `options={'require': ['exp','iat','sub']}`（`app/core/security.py`）⇒ ⇒ 升级后**必须**有一条断言证明 `require` 仍在 ⇒ ⇒ 否则「修了漏洞、拆了加固」 | F4-T2 |
| 16 | ⚖️ **`docker compose run --rm seed` 仍能绕过锁**（F2-T3 选了宿主侧取锁） | 本机 docker registry 拉不动 ⇒ ⇒ 容器侧装 flock **不可验证** ⇒ ⇒ 残留 ⇒ ⇒ P10-C 处理 | F2-T3 · 残留 |
| 17 | ⚖️ **默认车道不隔离**（`_sync_engine` + 真 Redis）⇒ ⇒ 违反「单测车道绝不碰开发库」 | 🔎 2026-11-17 实测：跑默认车道时进程挂着 **5432** 与 **6379** 的连接 ⇒ ⇒ 且整轮跑到 22% **挂死 33 分钟** ⇒ ⇒ F2-T5 修 | F2-T5 |
| 18 | ⚖️ **依赖真 Redis 的测试**（若存在）该迁到真 PG 车道 | F2-T5 先把 URL 指向不可路由端口 ⇒ ⇒ 若某测试因此红 ⇒ ⇒ 说明它**依赖**真 Redis ⇒ ⇒ 登记 TODO（TODO-165）迁到 `scripts/pytest_pg.sh` 车道 | F2-T5 · TODO |
| 19 | ⚖️ **二维码载荷里的 `record_hash_digest` 是 `sha256('')`**（不是审计端点那个） | `app/services/report/qr.py:84-91`：`digest = sha256("|".join(sorted(record_hashes)))` ⇒ ⇒ 而 `record_hashes` 恒为空（`record_hash` 没进 `datasource_registry` ⇒ qr.py 的 docstring **明写**此事）⇒ ⇒ **审计端点那个已按 A1 裁决读 `content_hash`**（`app/api/v1/report.py:486-495`）⇒ ⇒ ⇒ **本条属 P9（报表）域**，P10 SPEC 未涉及二维码 ⇒ ⇒ **不在 P10-F 范围** ⇒ ⇒ 登记为跨批观察项 | 跨批观察 · 非 P10-F |

---

## 「已存在的东西」—— **复用，不重建**（评审要求：What already exists）

| 需求 | **已有的**（别重建） | 本计划怎么用 |
|---|---|---|
| public 快照 | `tests/e2e_flows/test_lane_smoke.py` 的 `_public_snapshot` + 独立连接写法 | 扩它，不另起一套 |
| 车道锁 | `scripts/pytest_pg.sh` 的锁段（`exec 9>` + `flock -n 9` + `PCS_PGTEST_LANE_LOCK` 覆盖） | `compose_test_stack.sh` **照抄同款**（同一把锁 · 同一覆盖变量） |
| 守门测试的「行为测法」 | `tests/scripts/test_pytest_pg_gate.py:165-218`（**假 docker** + **真占锁进程**） | F1-T4 与 F2-T3 都照这个形状写 |
| 剥注释读脚本 | `tests/scripts/test_pytest_e2e_gate.py::_body()` | 抽成 `lane_script_body.py` 一处真相源，两边 import |
| rowKey 缺陷的守卫 | **`tests/pages/rowKey_contract.test.ts`（repo 级棘轮）** | **扩它**（禁 index 型回调）⇒ 不另写页面测试 |
| 依赖漏洞扫描 | **`uv audit`（内建于 uv 0.11.2）** + `bandit`（1.9.4 已装） | F4 直接用 ⇒ **不装 pip-audit / trivy** |
| 发布前只读检查 | `scripts/check_schema_parity.py`（逐库独立进程 + 与代码 head 比） | F6 的只读部署前置照它的形状写 |
| 一次性授权 | `scripts/seed_user_project_access.py`（幂等 · `--username/--project`） | F6-T1 直接调，不重写 |
| 契约滚动 | `scripts/gate_08_openapi_contract.sh` 的四阶段 | F1-T2 照它滚 baseline |
| 隔离断言 | `docs/solutions/testing-issues/assertion-must-be-sensitive-to-named-defect.md` | 每条新断言都要能抗变异 |
| 报告落盘 | `.gstack/qa-reports/`（gitignored ⇒ 结论必须同步进 `TODOS.md`） | F6-T4 照此 |

---

## **NOT in scope**（**明确不做** —— 评审要求）

| 不做的事 | 为什么 |
|---|---|
| 新建 CI 流水线 | 既有裁决（单人开发）⇒ ⇒ SPEC §3.2.0(2) 的「E2E 进 CI」继续登记偏离（D25） |
| `docker compose` 的**容器侧** flock 改造 | 本机 docker registry 拉不动 ⇒ ⇒ 改完**无法验证** ⇒ ⇒ 宿主侧取锁 + 残留 TODO |
| 前端 `refresh` 通路（`POST /auth/refresh` 的调用） | 与 #9 的通道问题**不同族** ⇒ ⇒ 登记 TODO，不在本批顺手做 |
| 前端「禁裸 `fetch(`」的静态守卫 | 属另一批（要定守卫范围与白名单）⇒ ⇒ 登记 TODO |
| 「改动 → 该跑哪几个闸」的索引（`tests/scripts/README.md`） | 独立于本批的小改进 ⇒ ⇒ 登记 TODO |
| pillow 13 的大版本升级（若 reportlab 不兼容） | ⇒ ⇒ 记「豁免 + 理由 + 上游 issue」⇒ ⇒ **不硬升** |
| PgBouncer 的引入评估 | 主计划 Q1 未裁 ⇒ ⇒ 属 P10-D |
| F3 审计的**结论**由 agent 代签 | 审计范围（Q10）与「公司管级列表要不要出现种子行」等**产品决定** ⇒ ⇒ 交人裁决 |

---

## 失败模式（每个新代码路径一条）

| 新路径 | 可能怎么坏 | 有测试吗 | 有错误处理吗 | 用户看到什么 | 判定 |
|---|---|---|---|---|---|
| `useFetch` 失败态 | 后端 500 ⇒ 页面停在「加载中」 | ✅ F1-T1 | ✅ 失败态 + 重试 | 「加载失败：HTTP 500」 | ✅ |
| `useFetch` 超时 | 后端慢 ⇒ 15s 后才失败 | ✅（fake timers） | ✅ 区分「请求超时」 | 「加载失败：请求超时（15s）」 | ✅ |
| `useFetch` 卸载 | 组件卸载 ⇒ timer 泄漏 / setState on unmounted | ✅（abort + clearTimeout） | ✅ cleanup | 无感（正确） | ✅ |
| `useFetch` 401 | token 过期 ⇒ 静默空页面 | ✅（清会话） | ✅ 跳 `/login` | 跳登录页 | ✅ |
| `handleSessionOver` 抽出 | axios 通道的 401 行为被改坏 | ⚠️ **依赖既有 axios 测试** ⇒ 开工时确认其存在 | — | — | ⚠️ **开工前核** |
| `preview-streams` 加 `response_model` | 老数据（list）⇒ 端点 500 | ✅ F1-T2 Step 3b | — | 500 | ✅ |
| 种子管级改形状 | 已种下的老行没被订正 ⇒ 按 id 查仍 500 | ✅ F1-T3 Step 4b | — | 500 | ✅ |
| `lane_script_body` 剥注释 | 脚本把逻辑写在 `#` 后面 ⇒ 守卫误判 | ✅（变异自证） | — | 假绿 | ✅ |
| public 快照 | 车道写了 public ⇒ 数据污染 | ✅（插/删/**改**三种变异） | — | 无人察觉 | ✅ |
| public 快照 | VACUUM FREEZE ⇒ 误报 | ❌ | ⚠️ 注释说明 | 守卫误红 | ⚠️ **已知取舍**（车道库不会 freeze） |
| compose 锁 | 锁路径与车道不一致 ⇒ 互斥失效 | ✅（静态 + 行为） | — | 「偶发卡住」 | ✅ |
| rowKey 棘轮 | 回调形式的匹配漏了 ⇒ 复发 | ✅（先红后绿） | — | antd 告警 | ✅ |
| `useFetch` 签名变更 | 9 个调用点漏改 ⇒ 渲染 undefined | ✅（3 个代表页） | — | 空页面 | ✅ |
| 仪表盘 | 有 project_id 的工作区面板不渲染 | ✅（正向路径） | — | 面板空白 | ✅ |
| F4 依赖升级（pyjwt） | 升级后 `options.require` 加固被拆 | ⚠️ **必须新增断言**（问题 #15） | — | 令牌校验变松 | ⚠️ **F4-T2 必做** |
| F6-T1 写开发库 | 迁移不幂等 ⇒ 跑两次就坏 | ⚠️ **必须写成幂等**（先查后改） | — | 账号授权错乱 | ⚠️ **F6-T1 必做** |
| **默认车道连了开发库/真 Redis** | 单测写进开发库 ⇒ 数据污染；或等锁 ⇒ **整轮挂 33 分钟** | ✅ F2-T5 | — | 绿灯但库被改了 | ✅ **F2-T5（评审期间新发现）** |

⇒ ⇒ **无测试 + 无错误处理 + 静默**的三条：**0** ⇒ ⇒ 无 critical gap
⇒ ⇒ ⚠️ 三条 **⚠️**（已知取舍或必须补断言）⇒ ⇒ **开工时逐条销掉**。

---

## 并行策略（评审要求：worktree 平行化）

⚠️ **本仓禁止 worktree**（历史事故：worktree 被删 ⇒ 会话永久卡死）⇒ ⇒ **不产出 worktree 方案**
⇒ ⇒ 改以**批次顺序**表达并行度：

| 批 | 触及模块 | 依赖 |
|---|---|---|
| F1 | `pcs-frontend/src/api` · `pcs-frontend/src/pages` · `pcs-backend/app/api/v1` · `pcs-backend/scripts` · `pcs-backend/tests/scripts` | — |
| F2 | `pcs-backend/tests/e2e_flows` · `pcs-frontend/src/pages` · `pcs-frontend/tests/pages` · `pcs-backend/scripts` | **F1**（`useFetch` 新签名） |
| F3 | `pcs-backend/app/api/v1`（**只读**）· `docs/solutions/` | — |
| F4 | `pcs-backend/pyproject.toml` · `pcs-frontend/package.json` · `docs/` | **P10-C** |
| F5 | `docs/` · 部署物 | **P10-C + P10-E** |
| F6 | `spec/` · `TODOS.md` · `.wolf/` | **F1~F5** |

⇒ ⇒ **同批内顺序执行**（同模块目录 ⇒ 顺序更省心）⇒ ⇒ **跨批不并行**（F2 消费 F1 的接口）
⇒ ⇒ **F1 与 F3 是唯一可并行的两批**（模块无交集）⇒ ⇒ 但本仓不建 worktree ⇒ ⇒ ⇒
⇒ ⇒ **实际就是一批一批来**（Native inline）⇒ ⇒ 「一批 = 一个上下文窗口」的容量口径就是这里的并行上限。

---

## 执行方式（**开工前由人定**）

- **Subagent-driven**（每个任务一个全新子代理 + 任务间一次独立评审）⇒ 最彻底 ⇒ 成本 = 每任务一份上下文。
- **Native**（本会话 inline 跑完**一批** ⇒ 批末一次整体评审）⇒ 与本仓现状一致（`.superpowers/sdd/<plan>/progress.md` 账簿制）⇒ ⇒
**推荐 Native**（理由：F1~F3 的任务彼此**接口耦合少**（F1-T1 的 `useFetch` 新签名是唯一跨任务契约）⇒ ⇒ 且**一批 = 一个上下文窗口**⇒ ⇒ 分批执行比逐任务换上下文更省）。
⇒ ⇒ **人已选 Native inline**（2026-11-17）。

---

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | 未跑（P10-F 范围已由 P10 主计划 + SPEC §3.2.7 界定） |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | — | `codex` 未安装 |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | CLEAR (PLAN) | 19 issues · 0 critical gaps · 8 条决策全部落进计划<br>⚠️ **这里的 19 是 eng review 的 findings 数**，与 ce review 的 19 条**可执行项**不是同一批 |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | 未跑（本批无新界面） |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | 未跑 |

- **UNRESOLVED:** 3（#2 #17 产品决定 · #3 #24 产品决定 · #4 F3 审计范围 · 均**交人裁决**，非阻塞）
- **VERDICT:** ENG CLEARED — 计划可执行（Native inline）

### 评审（2026-11-17）落进计划的 8 条决策

| 决策 | 内容 | 落在哪 |
|---|---|---|
| D3 | public 守卫**快照 `public` 全部表**（不再枚举「车道写了哪些表」）⇒ 彻底不需要手抄清单 | F2-T1 |
| D4 | F4 只用**已装的** `bandit` + **内建的** `uv audit`（不新增 pip-audit / trivy） | F4 |
| D5 | 部署前置的**写动作**就在**开发库 `pcs`** 上真跑一次（幂等） | F6-T1 |
| D6 | F3 审计**判据先写死**（每端点必答 4 问）+ 抽样变异 | F3-T2/T3 |
| D7 | preview-streams 的响应模型**放同文件** + **显式 `response_model=`**（与 4 个兄弟同形） | F1-T2 |
| D8 | TODO-162 **扩 repo 级 rowKey 棘轮**（禁 index 型回调），不写页面级测试 | F2-T4 |
| D9 | 「旧数据怎么办」的两条回归钉子**都补**（两种历史形状 + 老行订正） | F1-T2 / F1-T3 |
| D10 | 新守卫**断行为**不只断文本（compose 锁行为测试 + public 基线双快照） | F2-T1 / F2-T3 |
| D11 | `useFetch` 的四个边界**都补**（超时 · 卸载清理 · 9 调用点回归 · 请求头断言） | F1-T1 |
| D12 | public 快照判据用 **`count(*)` + `max(xmin::text::bigint)`**（不物化） | F2-T1 |
| D14 | 依赖漏洞**按可达性分级处置**（不是「一刀切为 0」）⇒ authlib 删除 · pyjwt 升级 | F4-T2 |

### 评审中查到的**即时事实**（已写进计划）

- `uv audit`（已内建）**现在就能跑**，且已报出：生产依赖 **112** 条 / 7 个包 ⇒ 其中
  **authlib 14 条是「声明了但全仓零 import」的依赖**（删一行即清）· **pyjwt 29 条是真在用的令牌库**（bug-091 加固要复验）
- 本机 **docker registry 拉不动**（`docker manifest inspect` 挂 >120s）⇒ ⇒ 容器侧装工具这条路不通
  ⇒ ⇒ 宿主直连 npmjs/github **是通的** ⇒ ⇒ STATUS 里「本机无外网」**只对 docker 成立**
- 仓里**已有** repo 级 `rowKey` 棘轮，其 docstring 明写「函数形式无法静态判定」⇒ 全仓 index 型 rowKey **只有 1 处**

---

# F4 前置批（F4-PRE）—— 清「谁做/何时做」仍未定的那部分 · 2026-11-18

> **为什么有这一批**：F4 的前置是 **P10-C**（没有镜像 / 部署物 / 告警 ⇒ F4 开不了）
> ⇒ ⇒ 与其干等 ⇒ ⇒ 把 **F3 审计查出来的、但「谁做 / 何时做」还没定**的债集中清一遍
> ⇒ ⇒ **F4 开工时台账是干净的**（每条要么已修、要么已裁决关闭、要么已转别的批并写明批号）。
> ⇒ ⇒ **本批不依赖 P10-C ⇒ ⇒ 现在就能开。**
>
> ⚠️ **本批不改产品逻辑**（守卫本身的洞由「守卫补洞批」修）⇒ ⇒ 本批产出 = **裁决 + 台账 + 棘轮/车道这类基础设施件**。

## 任务清单

- **FP-T1 逐条裁决**（本批的主任务）⇒ ⇒ 计划末尾「F3/F4 遗留清单」里**谁做/何时做未定**的
  **14 条**（TODO-164/165/168/171/173/176/177/181/183/187/188/189/190/191）逐条落成**三者之一**：
  ① **本批修**（写清改哪个文件 + 哪条断言）② **转某批**（写明批号 + 为什么排那批）
  ③ **关闭**（写明理由 + 证据 ⇒ 「不是缺陷 / 不存在 / 已由别处覆盖」）
  ⇒ ⇒ ⚠️ **不许留「下一批」这种写法**（那正是今天这批债攒下来的原因）。
- **FP-T2 棘轮抬真**（TODO-189 + ce-code-review 的同族发现）
  ⇒ ⇒ `tests/conftest.py::AUDITED_PROJECT_SCOPED_ENDPOINTS` 现在是 **2**（实际审计面 ≈12）
  ⇒ ⇒ **改成「已审端点清单」而不是计数** ⇒ ⇒ 并在 `tests/test_strict_client_ratchet.py`
  里断言：**清单里每个端点路径**都有对应的 `strict_client` 用例 ⇒ ⇒ 棘轮才真能咬。
  ⇒ ⇒ 另：`scripts/audit_list_endpoints.py` 的 `AUTHZ_GUARDS` **漏了两个新 service 层守卫**
  （`require_project_access_or_404` · `require_workspace_access_or_404`）⇒ ⇒ 补进去
  （否则审计脚本自己把新守卫判成「无守卫」⇒ 假阴性）。
- **FP-T3 车道残留**（TODO-165 / 168 / 164）
  ⇒ ⇒ **165**：依赖真 Redis 语义的用例（编辑锁 · 广播）迁到 `scripts/pytest_pg.sh` 车道
  ⇒ ⇒ **168**：默认车道的漂移守卫**不再连开发库**（只读也算连 ⇒ ⇒ 与「单测车道不碰开发库」冲突）
  ⇒ ⇒ **164**：F2-T5 已做隔离 ⇒ ⇒ **核对后标关闭**（或写清残留是哪几处 ⇒ 拆成新条目）。
- **FP-T4 断言缺口**（TODO-171 / 173 / 183 / 187 / 188）
  ⇒ ⇒ 171（`DefinitionService.update` 的写闸无独立断言）· 173（`config.py` 8 端点角色闸无 403 断言）
  ⇒ ⇒ 183（恒真断言）· 187（两种 404 文案不同 ⇒ 存在性可枚举）· 188（`GET /user-projects/me` 角色清单缺 3 个角色）
  ⇒ ⇒ 逐条：**补断言** 或 **写明「为什么现在不补」+ 登记触发条件**（⇒ 与 FP-T1 的②③同一套口径）。
  ⚠️ **181 / 183 必须与「守卫补洞批」同批**（守卫一改就立刻补断言 ⇒ ⇒ 否则又变成「无人应答」）。
- **FP-T5 台账入账**：`TODOS.md` 逐条标状态（关闭 / 转批 / 修）· 本文件末尾的遗留清单表同步 ·
  `.wolf/STATUS.md` 的「下一批」更新 ⇒ ⇒ **F4 开工前，遗留清单里不许有「未定」的行**。

---

# F3/F4 遗留清单（**本批产出的债的唯一账本** ⇒ 与 `TODOS.md` 对齐）

> ⚠️ **为什么要有这一节**：F3 的缺口按任务定义只写进 `TODOS.md` ⇒ ⇒ **计划文件里一条都没有**
> ⇒ ⇒ 而计划的 checkbox 是 **67 勾 / 0 未勾** ⇒ ⇒ 读计划的人会以为 P10-F 已收口。
> ⇒ ⇒ **这一节就是补那个洞**：F3/F4 的债在这里有一张表，带**谁做 / 何时做**。

| # | 条目 | 严重度 | 现状（2026-11-18） | 谁做 | 何时做 |
|---|---|---|---|---|---|
| **TODO-164** | 默认单测车道连了开发库与真 Redis | 🔴 | F2-T5 已做隔离 ⇒ **该标关闭**（残留拆到 165/168） | FP-T3 | **F4-PRE** |
| **TODO-165** | 依赖真 Redis 语义的测试该迁 PG 车道 | 🟡 | 未迁 | FP-T3 | **F4-PRE** |
| **TODO-168** | 默认车道的漂移守卫仍连开发库（只读） | 🟡 | 未清 | FP-T3 | **F4-PRE** |
| **TODO-171** | `DefinitionService.update` 的写闸无独立断言 | 🟠 | 未补 | 守卫补洞批 | **下一批**（与守卫改动同批） |
| **TODO-173** | `config.py` 8 个端点的角色闸无 403 断言 | 🟠 | 未补 | FP-T4 | **F4-PRE** |
| **TODO-176** | 默认 `client` 把项目守卫 mock 成永远 True | 🟠 | 明确「**不进 P10-F 修复范围**」⇒ 归属待定 | FP-T1 | **F4-PRE**（裁决） |
| **TODO-177** | 公司级模板（`project_id IS NULL`）不可执行 | 🟡 | 属新功能 ⇒ 排期未定 | FP-T1 | **F4-PRE**（裁决） |
| **TODO-181** | `records.py` / `report.py` 的项目守卫零断言 | 🟠 | 未补（守卫已改 ⇒ 断言更该补） | 守卫补洞批 | **下一批**（与守卫同批） |
| **TODO-183** | `test_project_level_uses_project_access_not_admin` 断言恒真 | 🟡 | 未改 | 守卫补洞批 | **下一批**（与守卫同批） |
| **TODO-187** | 两种 404 文案不同 ⇒ 存在性可枚举 | 🟡 | 未改（跨 21+ 端点族） | FP-T4 | **F4-PRE** |
| **TODO-188** | `GET /user-projects/me` 角色清单缺 3 个角色 | 🟡 | 未改（前端无消费者 ⇒ 潜伏） | FP-T4 | **F4-PRE** |
| **TODO-189** | 两个「不 mock 守卫」的 client ⇒ 棘轮看不见其中一个 | 🟢 | 未改 | FP-T2 | **F4-PRE** |
| **TODO-190** | `obsolete` 不查 `created_by` | 🟡 | 产品语义待定（裁决只覆盖 publish） | FP-T1 | **F4-PRE**（裁决） |
| **TODO-191** | 前端「保存并发布」对创建人自己无提示 | 🟢 | 未做 | FP-T1 | **F4-PRE**（裁决） |

⇒ ⇒ **已裁决落地、不在本清单里的**：TODO-166（接受现状）· TODO-169（FORMAL 必有项目）
⇒ ⇒ TODO-170 选项③ · TODO-172/175/178（人裁决已落地）· TODO-174（已修）·
⇒ ⇒ TODO-179/180/182/185/186（已修 · `a2b9889`）。
⇒ ⇒ **已转别的批的**：TODO-156/157/159/160 ⇒ ⇒ **P10-C 前端收口子批**
（`docs/superpowers/plans/2026-11-18-p10-c-frontend-closure.md` · 人裁决 2026-11-18）。
