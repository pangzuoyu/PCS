# PCS ce-code-review — P10-B 批（全流程 E2E）

- **范围**：`d73a760`..`f3b35e5` 之间的 P10-B 全批（base `d73d1ac` · head `f3b35e5` · branch `main`）
- **规模**：55 文件 · 8659 行改动 · 可执行非测试 974 行 => `size_band=large` => **depth=full**
- **评审者**：9 个 persona（correctness · project-standards · testing · maintainability · learnings · security · api-contract · adversarial · reliability）
- **跨模型 peer**：**未启动** —— 本机没有技能允许的 peer provider CLI（codex / grok / composer / cursor-agent 均不在 PATH；`CROSS_MODEL_PEERS` 未设）=> 对抗性视角由进程内 `adversarial` persona 承担
- **原始产物**：`personas/*.json`（9 份）+ `personas/receipts.md` + `scope-facts.json` + `shared/` + `full.diff`
- **校验器**：**未运行**（merge leaf 未在收口时限内产出 `synthesized-findings.json`）=> 本报告的发现**未经独立校验**，`validation_status` 一律标 `unverified`；请把每条当**线索**而不是**定论**
- **日期**：2026-11-17

---

## Verdict: **Not ready**

理由（**按"人用这个软件会拿到什么"重新分级**，不是按 persona 的标签）：

1. **本批的核心交付物是"验证机制"** —— 一条真 PG 隔离 schema 的 E2E 车道 + 三道 fail-closed 闸门 + 真后端 Playwright 通道。**验证机制的失败模式是"假绿"**，不是"报错"。本次评审找到 **6 处"守卫恒真/守卫从未执行"**（见 P1-1..P1-6）⇒ **车道目前无法证明它想证明的东西**。
2. **本批自称修掉的 bug-2165 其实没修好** —— `report_tasks.py` 里那行赋值在 `dup` 守卫早退之后**永不可达**，而 E2E-009 用命令式 `pytest.xfail` 把用例**中止**了 ⇒ 车道对这条**恒绿** ⇒ "修好了"这个结论**没有任何证据**。
3. **车道本身没有目标库护栏** —— `_lane_url()` 只验 URL 协议，`PCS_E2E_LANE=1` 打到**开发库 `pcs`** 也会照跑（建 schema + 跑 alembic + 灌种子）；种子脚本同样没有白名单 ⇒ **一个环境变量就能把开发库变成测试库**。

⇒ 结论：**不是"这批不能合"，而是"这批的绿灯不能当证据"**。修完 P1-1..P1-6 之后，车道才具备"能证明"的资格。

---

## Actionable Findings（可执行的那部分）

| # | 严重度 | 位置 | 一句话 | 建议修法 |
|---|---|---|---|---|
| A1 | **P1** | `pcs-backend/app/workers/report_tasks.py:118` | `row.data_version = digest` 在 `dup` 守卫早退之后**永不可达** ⇒ 审计哈希端点仍恒返空串 | 赋值挪到**早退之前**（或给存活的那行补写）⇒ 同时把 E2E-009 的 `pytest.xfail` 换成**真断言**（先红后绿） |
| A2 | **P1** | `pcs-backend/tests/e2e_flows/test_e2e_report.py:91` | 命令式 `pytest.xfail()` **中止**整个用例 ⇒ 修复回归时车道仍全绿 ⇒ 修复是空操作 | 改成**只标记那一条断言**（`pytest.xfail` 放在断言点，不在用例顶层）⇒ 或先修 A1 再去掉 xfail |
| A3 | **P1** | `pcs-frontend/e2e/real_backend_flows.spec.ts:144` | 越权 UI 断言**恒等**：bob=CHECKER 在**角色闸**就被挡 ⇒ 项目守卫 404 分支**从未执行** ⇒ 删掉守卫照样绿 | 换一个**能过角色闸**的局外人账号（全局角色 DESIGNER/PROCESS_CONTROLLER/SYSTEM_ADMIN 且**无授权行**）⇒ 再断 404/同形 |
| A4 | **P1** | `pcs-frontend/e2e/real_backend_route_sweep.spec.ts:56` | 「路由渲染出来了」断言**恒真**（`#root` 是 index.html 的静态 div）⇒ 抓不到"渲染了但拿不到数据" | 断**具体页面特征**（标题/表格行）或至少断"无 console error 且无 4xx"（把已知的 TODO-159/160 列成白名单） |
| A5 | **P1** | `pcs-frontend/e2e/real_backend_flows.spec.ts:41` | 签署矩阵流断的是**内置全局矩阵** `DEFAULT_RECORD_3_LEVEL` ⇒ 种子那张 `E2E_FLOWS_RECORD_3_LEVEL` 没灌也绿 | 断**种子那张**矩阵名（从种子常量派生，不手抄） |
| A6 | **P1** | `pcs-backend/tests/e2e_flows/conftest.py:93` + `scripts/seed_e2e_flows.py:763` | 车道与种子**没有目标库护栏** ⇒ `PCS_E2E_LANE=1` + 指向 `pcs` 的 `DATABASE_URL` ⇒ 在**开发库**建 schema + 灌种子 | 车道与种子都加**库名白名单**（只允许 `pcs_pgtest`/`pcs_test`）⇒ 不匹配 ⇒ **非零退出**（fail-closed） |
| A7 | **P1** | `pcs-backend/app/services/pipe/pipe_chain_persist.py:112` | 占位管级"先查后插"无 savepoint/`IntegrityError` 兜底 ⇒ 并发首算撞主键 ⇒ `IntegrityError` **逃过** `PcsError` 兜底 ⇒ 整条链计算 500 | 改用仓内 house pattern（savepoint + 重读赢家）**或** `ON CONFLICT DO NOTHING` |
| A8 | **P1** | `pcs-frontend/src/pages/routeWrappers.tsx:92` | `useFetch` 把非 2xx 与网络异常**一起吞掉**，且裸 fetch **绕过 axios 的 401 拦截器** ⇒ token 过期后页面永久「加载中…」，不报错也不回登录页，且**无超时** | 走 `src/api/client.ts` 的 axios（统一 401/超时/baseURL）⇒ 或至少区分 401/其他错误并暴露错误态 |
| A9 | **P2** | `pcs-backend/app/services/pipe/pipe_chain_persist.py:134` | 计算端点运行时把占位管级插进**全局** `pipe_classes`（`source="COMPANY_STD"`）⇒ 越权写公司级标准目录 ⇒ 每次链计算都往公司管架列表塞一行 | 别在计算路径写配置表 ⇒ 改由**迁移/配置流程**提供该行（或标 `source="SYSTEM_PLACEHOLDER"` 并从公司列表过滤） |
| A10 | **P2** | `pcs-backend/tests/e2e_flows/test_lane_smoke.py:132,240` | 「不写 public」守卫只快照 **4 张表**、只在种子后取基线、只跑一条写路径 ⇒ 漏检（`pipe_classes`/`piping_results`/`audit_logs`…）不可见 | 快照**所有**本批写的表 + 种子**前**取基线 + 覆盖每条写路径 |
| A11 | **P2** | `pcs-backend/tests/e2e_flows/conftest.py:289` | 隔离只覆盖 `get_db` ⇒ `ws.py:77` / `errors.py:51` 的**全局 session factory** 仍指 public schema | 把隔离 session factory 也注入到那两处 ⇒ 或在车道里 monkeypatch 全局 engine |
| A12 | **P2** | `pcs-backend/app/core/errors.py:45` | `PYTEST_CURRENT_TEST` 早退 ⇒ 车道里**每次 403 都不写审计行** ⇒ 合规语义空跑 | 车道里**不要**早退（或把审计写库放到测试之后断言） |
| A13 | **P2** | `pcs-backend/scripts/pytest_pg.sh:83` | 闸门③只要求「≥1 passed」⇒ 29/30 场景被 skip 也算绿 | 断「**没有 skip**」或「passed ≥ 场景数」 |
| A14 | **P2** | `pcs-backend/tests/e2e_flows/test_e2e_schema_parity.py:65` | 两库闸只比彼此、**不与代码 head 比** ⇒ 两库一起落后也绿；且把车道绑在开发机状态上 | 加「与 alembic head 比」这一条 ⇒ 并把它移出 E2E 车道（它是**发布前检查**，不是场景） |
| A15 | **P2** | `pcs-frontend/src/pages/DashboardPage.tsx:40` | bug-2168 的守卫应是「拿到**真** project id」而非「选了工作区」⇒ 工作区 `project_id` 可空 ⇒ 选中后仍用**占位 id** ⇒ 404 照旧 | 守卫条件改成「拿到了非占位 project_id」 |
| A16 | **P2** | `pcs-backend/scripts/seed_e2e_flows.py:516` + `pcs-backend/app/services/pipe/pipe_chain_persist.py:134` | 种子管级与运行时占位**两套互斥定义**；种子那行还**违反** `PipeClassResponse` 契约（`source` 不在 Literal · dn 缺 `{min,max}` · sch 是 float）⇒ 按 id 取必 500 | 种子行按契约改（并在快车道加一条"按 id 取不 500"的断言）⇒ 两处**共用一个定义** |
| A17 | **P2** | `pcs-backend/tests/e2e_flows/conftest.py:191` | `DROP CASCADE` 只挂在 fixture `finally` ⇒ 进程被杀就**永久留下** `e2e_<随机>` schema；`finally` 里 DROP 抛错会**顶替**真正的失败原因 | 加 janitor（启动时清旧 schema）+ 把 DROP 的异常与测试失败**分开**报 |
| A18 | **P2** | `pcs-backend/tests/e2e_flows/conftest.py:272` | 注释称 `e2e_seed` 已补 lifespan 的两处启动 seed ⇒ **实测 0 处调用** ⇒ 隔离 schema 缺系数表与系统参数（车道上下文 ≠ 生产） | 补上（或删掉那句注释）⇒ 并加一条断言钉住 |
| A19 | **P2** | `pcs-backend/scripts/seed_e2e_flows.py:243` | `_get_or_create` 等**逐字复制** `seed_e2e_data.py:108` 的 house pattern ⇒ 两份真相源 ⇒ 竞态修复只改得了一边 | 抽成共享 helper（`scripts/` 下）⇒ 两个种子共用 |
| A20 | **P2** | `pcs-backend/tests/e2e_flows/helpers.py:206` + `test_e2e_record_workflow.py:48` | `CHAIN_ROLES` 是 `FLOW_MATRIX_STEPS` 的**未钉住副本**；`_bump_record` 与 `helpers.bump_record` **逐字重复** | `CHAIN_ROLES` 从种子派生（加一条比对断言）⇒ `_bump_record` 删掉改 import |
| A21 | **P2** | `pcs-backend/app/api/v1/sim_imports_query.py:325` | preview-streams **无 response_model** ⇒ 统一后的 `{"streams":[…]}` **未进契约**；注释称「SIM/Excel 存 dict」与事实相反（496/612 两个写入点都存 list） | 补 response_model（进 OpenAPI）⇒ 修注释 ⇒ 影响面比注释说的大 |
| A22 | **P2** | `pcs-backend/app/workers/report_tasks.py:118` + `app/api/v1/report.py:494` | 把文件 sha256 写进 `data_version` ⇒ `record_hash_digest` 与 `data_version` **塌成同一个值**；且 `_expected_digest` 只读 `data_version` ⇒ 老行仍返空串 | 两者**语义分开**（`data_version` = 数据版本号 · `record_hash_digest` = 内容哈希）⇒ 或明确写进契约 |
| A23 | **P2** | `pcs-backend/docs/openapi-baseline.json` | 已核实基线漂移**主体**是上一批 AI 端点契约（`6292ca2` 改了 openapi.json 未改基线）；但基线只是"与当前一致"的同步锁 ⇒ 本批的**破坏性变更**（`case_type` 必填→可空）**无版本/弃用/迁移说明** | 破坏性契约变更走**版本或弃用**流程 ⇒ 不只是滚基线 |
| A24 | **P2** | `spec/P10 AI预留与测试部署开发规格说明书.md:666` | D23~D38 **写进了非权威的 V1.0 文件**（其 §3.2.2 只有 14 场景）⇒ 权威 SPEC（计划称 V1.3.1）**一条未修订**；且该文件 D20 仍称「V1.3.1 不存在」，与 master-plan「以 V1.3.1 为准」**直接矛盾** | 先裁「哪份 SPEC 为准」⇒ 把偏离登记写进**权威那份**（或把 V1.0 升版后写进去） |
| A25 | **P2** | `.wolf/STATUS.md:51,88` | 违反 CLAUDE.md《Per-Batch QA Gate》与「解法回写 docs/solutions」：STATUS 自称教训「已进 docs/solutions」但本批**无** `docs/solutions/**` 改动；且把「批末还没跑 QA」写进 STATUS | 本批的 4 条可复用解法**回写 `docs/solutions/`**（车道驱动须与生产一致 · 契约与 DB 可空性对齐 · 前端两条取数通道 · 守门测试隔离） |
| A26 | **P2** | `pcs-frontend/package.json:20` | 真后端 5 条 UI 流依赖 **4 个仓库里没写出的环境变量**（`VITE_PROJECT_ID` / 后端库 / 端口 / `PCS_ENABLE_MOCK_LOGIN`）⇒ 仓库**无法复现** ⇒ 新克隆机器上跑不出来 | 把跑法写进 `pcs-frontend/README` 或 `package.json` 的 script（带默认值）⇒ 报告里也写 |
| A27 | **P2** | `pcs-backend/scripts/pytest_pg.sh:56` + `tests/scripts/test_pytest_e2e_gate.py:95` + `test_pytest_pg_gate.py:111` | 车道锁只约束两条 pytest 车道 ⇒ compose 的 migrate/seed 在同库**裸奔**；守卫测试对**含注释的原文**做子串匹配 ⇒ 删掉 flock 只留注释也能过；「唯一入口」守卫只数一个字面量 | 锁也覆盖 compose 任务（或给 compose 加同一把锁）⇒ 守卫**剥注释**后再匹配（同文件另一处已正确剥）⇒ 入口守卫按**命令形状**匹配 |
| A28 | **P3** | `pcs-backend/scripts/pytest_pg.sh:57` | 车道锁用可预测 `/tmp/pcs-pgtest-lane.lock` 且 `exec 9>` **跟随符号链接截断** ⇒ 共享主机上可被诱导截断任意文件 | 用 `mktemp`/私有目录 + `O_NOFOLLOW` 语义（`flock` 到受控路径） |
| A29 | **P3** | `pcs-backend/tests/e2e_flows/conftest.py:84` | 跳过闸门只随 `tests/e2e_flows/` **目录**注册 ⇒ 用例挪出该目录后默认车道会打开发库而守卫照样绿 | 闸门按**marker**而非目录注册（`pytest_collection_modifyitems` 全局） |
| A30 | **P3** | `pcs-backend/tests/e2e_flows/test_lane_smoke.py:194` | 默认车道 skip 闸门只有「**假 item** 动作断言」⇒ 新增一条漏 `@pytest.mark.e2e` 的用例会直接跑开发库而守卫仍绿 | 守卫**真的收集一次**并断言「e2e 用例数 > 0 且都被标记」 |
| A31 | **P3** | `pcs-backend/tests/e2e_flows/test_e2e_permission_matrix.py:147` | 「逐字同形」只比 status+code ⇒ message 模板改措辞仍绿；且两次请求用**不同 uuid** | 同一 uuid 测两次 + 比 body **逐字**（cerebrum A 的原话） |
| A32 | **P3** | `pcs-backend/app/schemas/stream.py:318` | 响应 `case_type` 可空但请求侧 `StreamBase` 仍必填 ⇒ 读写不对称；且该改动**只有** Playwright 覆盖，车道零回归 | 快车道 + 车道各加一条「case_type 为 NULL 的物流不炸列表端点」的回归 |

---

## 完整发现表（按严重度）

### P1（11 条 · 全部列在 Actionable Findings 里：A1-A8 及其在其它 persona 的重复报告）

| 位置 | 一句话 | 提出者 |
|---|---|---|
| `app/workers/report_tasks.py:118` | `data_version` 赋值永不可达 ⇒ 审计哈希恒空（**对象没脱钩，是分支写错了**） | correctness · reliability |
| `tests/e2e_flows/test_e2e_report.py:91` | 命令式 `xfail` 中止用例 ⇒ 修复回归时车道恒绿 | testing · adversarial |
| `pcs-frontend/e2e/real_backend_flows.spec.ts:144` | 越权 UI 断言恒等（角色闸短路 ⇒ 项目守卫从未执行） | adversarial · learnings |
| `pcs-frontend/e2e/real_backend_route_sweep.spec.ts:56` | 「路由渲染出来了」断言恒真 | adversarial · testing · learnings |
| `pcs-frontend/e2e/real_backend_flows.spec.ts:41` | 断的是内置矩阵而非种子那张 | adversarial · correctness · maintainability |
| `pcs-frontend/src/pages/routeWrappers.tsx:92` | `useFetch` 吞非 2xx + 绕过 axios 401 ⇒ token 过期后永久「加载中…」 | reliability |
| `app/services/pipe/pipe_chain_persist.py:112` | 占位管级先查后插无 savepoint ⇒ 并发撞主键 ⇒ 500 | reliability · correctness · adversarial |
| `app/services/pipe/pipe_chain_persist.py:95` | 计算端点运行时往**配置主表**写占位行（绕过 `PipeClassService.create`） | maintainability |
| `pcs-backend/tests/e2e_flows/conftest.py:93` / `scripts/seed_e2e_flows.py:763` | 车道与种子**无目标库护栏** | security · adversarial · testing · reliability |
| `pcs-frontend/package.json:20` | 真后端 UI 流依赖 4 个仓库外环境变量 ⇒ 无法复现 | testing |

### P2（42 条）

去重后的主题（同一处多人报已合并，括号内为提出者）：占位管级写全局配置表并以 `COMPANY_STD` 进公司列表（A9，correctness·security·api-contract·adversarial）· 种子无库白名单（security·reliability）· `_lane_url()` 只验协议（adversarial·testing）· 「不写 public」守卫只覆盖 4 张表/只取一次基线（security·adversarial·testing）· 隔离只覆盖 `get_db`（adversarial）· `PYTEST_CURRENT_TEST` 早退 ⇒ 403 不写审计行（adversarial）· 闸门③只要求 ≥1 passed（adversarial）· 两库闸只比彼此且绑开发机（testing·correctness）· bug-2168 守卫条件错（correctness）· 种子管级违反契约（correctness·learnings）· 种子管级与运行时占位两套定义（maintainability）· `_get_or_create` 两份真相源（maintainability）· `CHAIN_ROLES` 未钉住副本 + `_bump_record` 重复（maintainability）· `useFetch` 第二套 HTTP 通道（maintainability）· 手抄种子常量（maintainability）· preview-streams 无 response_model + 注释与事实相反（api-contract）· `data_version` 与 `record_hash_digest` 塌同值 + 老行仍空（api-contract）· 占位管级与契约同形不可区分（api-contract）· 基线漂移主体是上一批 + 破坏性变更无版本说明（api-contract）· D23~D38 写进非权威 SPEC（api-contract·project-standards）· 路线扫描把判据降级为只打印（project-standards·learnings）· STATUS 违反 QA Gate 与「回写 docs/solutions」（project-standards）· `report_tasks` 赋值与 `dup` 早退（api-contract）· DROP CASCADE 只挂 finally + 无 janitor + 异常顶替失败原因（reliability）· 车道锁只管 pytest 车道，compose 裸奔（reliability）· 注释称已补 lifespan seed 实测 0 处调用（reliability）· 隔离 schema 缺系数表/系统参数 ⇒ 上下文 ≠ 生产（reliability）· `case_type` 读写不对称（api-contract）· 契约与 DB 可空性未对齐的回归缺测（testing）· 「逐字同形」只比 status+code（learnings）

### P3（15 条）

车道锁可预测路径 / 符号链接截断（security）· 跳过闸门按目录注册（testing）· skip 闸门只测假 item（testing·learnings）· flock 守卫子串匹配（testing·learnings）· 「唯一入口」守卫只数一个字面量（testing）· 路由扫描只打印不断言（testing·learnings）· 种子脚本没有库护栏（reliability）· `case_type` 只有 Playwright 覆盖（testing）· `data_version` 语义占死（api-contract）

---

## Requirements Completeness（对照计划 `docs/superpowers/plans/2026-11-13-p10-batch-b-fullflow-e2e.md`）

| 计划项 | 达成 | 说明 |
|---|---|---|
| E2E 车道（隔离 schema + 真 PG + 真 app） | ⚠️ **部分** | 车道能跑（28 passed + 1 xfailed）⇒ 但 **A6/A10/A11/A13/A29/A30** ⇒ 「隔离」与「fail-closed」目前**不可证** |
| 18 个 SPEC 场景 | ✅ **覆盖** | E2E-001~018 都有对应用例（车道 28 passed + 1 xfailed） |
| WF-PATH 五类路径（01A/01B/01C/01D/01E/02/03 等） | ✅ **覆盖** | 但 01C 的链式传播断言只断到 `propagated >= 1` + 状态（**未**断血缘行的具体内容） |
| 权限矩阵 + 跨项目 404 | ⚠️ **部分** | 后端矩阵 ✅（E2E-016 断 404/同形）⇒ **前端越权流恒等**（A3） |
| AI 审计（E2E-017） | ✅ **覆盖** | 两段式（入队 spy + 直调写库） |
| 两库 schema 一致（E2E-018） | ⚠️ **部分** | 断的是「两库彼此相等」⇒ 不与代码 head 比（A14）⇒ 且不该在场景车道里 |
| 真后端 5 条 UI 流 | ⚠️ **部分** | 5 条都存在且跑通 ⇒ 但 **A4/A5/A3** ⇒ 其中三条的断言**恒真或断错对象** ⇒ 数字绿、内容空 |
| 批末 QA 报告 | ✅ **有** | `.gstack/qa-reports/qa-report-pcs-frontend-2026-11-17-p10b.md`（但 STATUS 自称「本轮还没跑」⇒ **状态文案不一致**，A25） |
| SPEC 偏离登记 | ⚠️ **落错文件** | D23~D38 写进非权威的 V1.0（**权威 SPEC 一条未修订**）⇒ A24 |
| 「E2E 进 CI」 | ❌ **刻意未做** | 既有裁决「不新建流水线」⇒ 登记 D25 ⇒ **延到 P10-F**（非本批缺陷） |

⇒ **反向检查（计划没要求、diff 却引入的行为规则）**：本批引入了两条**未在计划里的行为规则** ——
① `StreamResponse.case_type` 变可空（对外契约放宽 ⇒ 属行为规则，计划只要求「修好 500」）⇒ 建议按 P3/advisory 走 human 裁决；
② `useFetch` 改用会话 token（前端取数口径变化 ⇒ 计划未提）⇒ 同上。

---

## Coverage

- **depth**：`full`（floor = `size_band=large` · 可执行非测试 974 行）
- **范围**：base `d73d1ac` · head `f3b35e5` · 55 文件 · 8659 行 · `unclassified_lines`：json 1978 · md 1869 · txt 282 · yml 15
- **reviewers（9）**：correctness · project-standards · testing · maintainability · learnings · security · api-contract · adversarial · reliability
- **project-standards**：跑了（criteria = 仓库根 `CLAUDE.md` ⇒ 治理全部改动文件）
- **跨模型 peer**：**未启动** —— 本机无技能允许的 peer provider CLI（codex/grok/composer/cursor-agent 均不在 PATH；`CROSS_MODEL_PEERS` 未设）⇒ **对抗性视角只由进程内 persona 承担** ⇒ 独立性弱于「跨模型 + 本地」双视角
- **校验器**：**未运行** ⇒ 所有发现 `validation_status: unverified`
- **未选人士及理由**：performance（生产改动极小 · 性能面集中在测试种子）· data-migration（diff 内无迁移/模式产物）· agent-native（无 agent 面向面）· julik-frontend-races（React/TS 非 Stimulus/Turbo）· swift-ios（无 Swift 文件）· previous-comments（standalone · 无 PR）· deployment-verification（无高风险迁移）
- **本批自认的债 与 本次发现的关系**：
  - bug-2165「根因未闭环」⇒ **本次给出了根因**（不是对象脱钩 · 是 `dup` 守卫早退 ⇒ A1）⇒ **TODO-158 可直接按 A1 收口**
  - TODO-161「运行时写配置表」⇒ **本次升级为 P1/P2 级**（越权写公司级目录 + 并发 500）⇒ A7 + A9
  - TODO-159/160（前端 3 页 404 / 3 页 422）⇒ **本次指出**：扫描本该抓住它们却只打印（A4）⇒ 把「白名单化断言」加上即可闭环
  - 「E2E 进 CI 延到 P10-F」⇒ 不变

---

## Testing Gaps

1. **bug-2167（`case_type` 可空）** 只有 Playwright 覆盖 ⇒ 快车道与 E2E 车道**零回归**（A32）
2. **越权 404 分支**从未在**前端**被执行（A3）⇒ 后端有 E2E-016、前端没有
3. **`report_tasks` 的审计哈希**没有一条**真断言**（A2）⇒ 这条需求今天**实际是空的**
4. **车道隔离**只验 4 张表（A10）+ 只覆盖 `get_db`（A11）⇒ 「不碰开发库/public」这句话目前**不可证**
5. **真后端 UI 流的 4 个环境变量**没有落进仓库（A26）⇒ 新机器上**跑不起来**（⇒ 也意味着这条通道**平时没人跑** ⇒ 它的缺陷容易长期隐形）
6. **`flock` 守卫**用子串匹配 ⇒ 守卫本身**可能失效**（A27）

## Residual Risks

1. **跨模型视角缺席**（peer 未启动）⇒ 本次对抗性审查**只有本地一个视角** ⇒ 「假绿」这类问题**最需要**独立视角 ⇒ 建议修 A1-A6 后**再跑一次**跨模型对抗审查
2. **校验器未运行** ⇒ 68 条发现里有**误报**（尤其是「恒等断言」类结论，依赖对端点闸门顺序的判断）
3. **reliability persona 晚到 70 分钟** ⇒ 它指出的 3 条 P1（`data_version` 早退 / 并发 IntegrityError / `useFetch` 吞错）**没有被 merge leaf 合并**（merge leaf 未产出）⇒ 本报告是**人工汇总**的（我按 9 份 JSON 聚合）⇒ 可能仍有遗漏
4. **`data_version` 语义**被文件 sha256 占死（A22）⇒ 修 A1 时**别把它写成内容哈希** ⇒ 两件事一起裁
5. **SPEC 以哪份为准**这个矛盾（A24）**在本批之前就存在**（D20 vs master-plan）⇒ 不是本批引入 ⇒ 但本批把 16 条偏离写进了**错的那份** ⇒ 修的时候要一次裁清

---

*原始产物见同目录 `personas/`（9 份 JSON + `receipts.md`）、`scope-facts.json`、`shared/`（意图与收口上下文）、`full.diff`、`files.txt`、`stages.jsonl`。*
