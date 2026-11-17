# PCS ce-code-review - P10-B 批（全流程 E2E）

- **Scope**: base `d73d1ac` -> head `f3b35e5`（branch `main`）, 49 个代码文件 + 文档 , 8659 行改动 , 可执行非测试 974 行 -> `size_band=large` -> **depth=full**
- **Intent**: 给 PCS 后端建一条真 PG 隔离 schema 的端到端车道，把 SPEC §3.2.2 的 18 个场景 + 5 条工作流路径 + 权限矩阵在真 app + 真库上跑起来；并把真后端通道的 5 条前端 UI 流跑起来
- **Plan（规格依据）**: `docs/superpowers/plans/2026-11-13-p10-batch-b-fullflow-e2e.md`（**explicit**：本批照它实施）
- **Criteria**: 仓库根 `CLAUDE.md`（治理全部改动文件）
- **Mode**: `markdown report-only`（未授权本地 apply）
- **Reviewers（9，全部已收集）**: correctness , project-standards , testing , maintainability , learnings , security , api-contract , adversarial , reliability
- **跨模型 peer**: **未启动** - 本机没有技能允许的 peer provider CLI（codex / grok / composer / cursor-agent 均不在 PATH，`CROSS_MODEL_PEERS` 未设）-> 对抗性视角由进程内 `adversarial` persona 承担
- **校验器（Stage 5b）**: **未运行** - merge leaf 未产出 `synthesized-findings.json`，且 `validator-batch` 未派发 -> 本报告所有发现 `validation_status: unverified`，请当**线索**而非定论；标 `75` 的条目尤其需要人工复核
- **原始产物**: `personas/*.json`（9 份）, `scope-facts.json` , `shared/`（intent + review-context）, `full.diff` , `files.txt` , `stages.jsonl`
- **日期**: 2026-11-17

---

## 结论摘要

本批的交付物不是功能，而是**一套验证机制**（一条真 PG 隔离 schema 的 E2E 车道 + 三道 fail-closed 闸门 + 真后端 Playwright 通道）。验证机制的失败模式是**假绿**，不是报错。本次评审在 9 份 persona 产物里找到 **40 条主发现**，其中 10 条 P1，核心是三件事：

1. **多处守卫是恒真式或从未被执行**（#3 #4 #5 #14 #35 #36 #37 #38）。真后端通道的「越权可见性」用例比较两个状态码，而两个请求都被**角色闸**挡在 403 上 -> 项目守卫的 404 分支一次都没跑到；路由扫描断的是 `#root` 这个静态 div（恒存在）；签署矩阵用例断的是迁移种下的**全局内置矩阵**，不是本批种子那张。**把被守卫的机制整段删掉，这些用例照样绿。**
2. **本批自称修好的 bug-2165 其实是空操作**（#1 #2）。`report_tasks.py:118` 的 `row.data_version = digest` 位于 `dup` 守卫的 `return` 之后，永不可达；活下来的那一行由 `report_service._upsert_report_file` 构造、根本没有 `data_version` 字段。E2E-009 又用**命令式** `pytest.xfail()` 把整条用例中止，于是「报表可下载且非空」这两段断言也从不执行，而闸门只 grep `N passed` -> **修复被回退，车道仍全绿**。
3. **目标库身份没有被任何一处断言**（#6）。车道 `_lane_url()` 只验 URL 协议，种子脚本完全没有库名护栏，而 `.env` 的 `DATABASE_URL` 指向开发库 `pcs`。`uv run python scripts/seed_e2e_flows.py`（脚本自己文档化的调用）就会往开发库写 E2E 项目 + `alice` 的用户行与授权行。

=> 结论：**不是「这批不能合」，而是「这批的绿灯还不能当证据」**。P1-1..P1-10 修完之后，车道才具备「能证明」的资格。

---

## Actionable Findings

处置口径：`gated_auto` = 有具体改法，调用方判断后可落；`manual` = 需要先做一次设计/口径裁决；owner 一律 `downstream-resolver`（调用方/我来修），`human` 表示必须先有人拍板。

| # | Sev | Route | File | Issue | Fix |
|---|-----|-------|------|-------|-----|
| 1 | P1 | `gated_auto -> downstream-resolver` | `pcs-backend/app/workers/report_tasks.py:118` | `row.data_version = digest` 在 `dup` 守卫 `return` 之后 -> 永不可达，审计哈希端点仍恒返空串 | 在 `report_service._upsert_report_file` 造 `ReportFile` 时补 `data_version=kw["content_hash"]`；`_finalize` 的 dup 分支在 `return` 前补 `dup.data_version = digest`；删掉 :118 那行 |
| 2 | P1 | `gated_auto -> downstream-resolver` | `pcs-backend/tests/e2e_flows/test_e2e_report.py:91` | 命令式 `pytest.xfail()` 中止整条用例 -> 剩余断言从不执行；闸门③ 只 grep `N passed` -> 修复回退也不红 | 修完 #1 后去掉 xfail 改硬断言；并让 `pytest_pg.sh` 闸门③ 把 `xfailed` 也判失败 |
| 3 | P1 | `gated_auto -> downstream-resolver` | `pcs-frontend/e2e/real_backend_flows.spec.ts:144` | 越权 UI 断言恒等（bob=CHECKER 在角色闸就被挡）-> 项目守卫 404 分支从未执行 | 改用无角色闸的 `GET /api/v1/projects/{id}` 断 404；另用 streams 列表端点断 403 |
| 4 | P1 | `manual -> downstream-resolver` | `pcs-frontend/e2e/real_backend_route_sweep.spec.ts:56` | 「路由渲染出来了」断的是静态 `#root` -> 恒真；且 4xx / console error 被降级为只打印 | 先定「已知缺口白名单」口径，再断每条路由的特征元素 + 断言 4xx 只出现在白名单里 |
| 5 | P1 | `gated_auto -> downstream-resolver` | `pcs-frontend/e2e/real_backend_flows.spec.ts:41` | 断的是内置全局矩阵 `DEFAULT_RECORD_3_LEVEL`，不是种子那张 `E2E_FLOWS_RECORD_3_LEVEL` | 断种子那张矩阵名，并把断言收窄到「项目绑定」那张表（加 testid） |
| 6 | P1 | `gated_auto -> downstream-resolver` | `pcs-backend/tests/e2e_flows/conftest.py:93` + `pcs-backend/scripts/seed_e2e_flows.py:763` | 车道与种子都没有目标库护栏 -> 指向 `pcs` 的 `DATABASE_URL` 也会照跑 | 两处都加库名白名单（`pcs_pgtest` / `pcs_test` / 名字含 `e2e`），不匹配即非零退出 |
| 7 | P1 | `gated_auto -> downstream-resolver` | `pcs-backend/app/services/pipe/pipe_chain_persist.py:112` | 占位管级「先查后插」无 savepoint / `IntegrityError` 兜底 -> 并发首算撞主键 -> `IntegrityError` 逃过 `PcsError` -> 整条链计算 500 | 照本仓 house pattern 改成 `begin_nested()` + 撞约束后重读赢家，或 `ON CONFLICT DO NOTHING` |
| 8 | P1 | `manual -> human` | `pcs-backend/app/services/pipe/pipe_chain_persist.py:95` | 计算端点在运行时往**全局** `pipe_classes` 写一行 `source="COMPANY_STD"` 的假公司标准 | 先裁「配置数据由迁移提供 还是 运行时兜底」；若留运行时兜底则必须走 `PipeClassService.create` |
| 9 | P1 | `gated_auto -> downstream-resolver` | `pcs-frontend/src/pages/routeWrappers.tsx:92` | `useFetch` 把非 2xx 与网络异常一起吞掉，且绕过 axios 的 401 拦截器 -> token 30 分钟过期后页面永久「加载中…」 | 改走 `src/api/client.ts` 的 axios 实例（统一 token / 401 / baseURL / 超时），或至少加显式 error 态 + `AbortController` |
| 10 | P1 | `manual -> human` | `pcs-frontend/package.json:20` | 真后端 5 条 UI 流依赖 4 个仓库里没写出的环境变量 -> 干净克隆跑不出来 | 把四个变量 + flows 项目 id 写进 `playwright.config.ts` / `package.json` script，并加「非占位 `VITE_PROJECT_ID`」的 fail-fast 守卫 |
| 11 | P2 | `gated_auto -> downstream-resolver` | `pcs-backend/tests/e2e_flows/test_lane_smoke.py:240` | 「不写 public」守卫只快照 4 张表、只在种子后取基线、只跑一条写路径 | 枚举 public 下所有表取 `count(*)` + `max(id)`，并在种子**前**取基线 |
| 12 | P2 | `manual -> downstream-resolver` | `pcs-backend/tests/e2e_flows/conftest.py:289` | 隔离只覆盖 `get_db` -> `ws.py:77` / `errors.py:51` 的全局 session factory 仍指 public schema | 把隔离 engine 注入那两处，或在车道里 monkeypatch 全局 engine |
| 13 | P2 | `gated_auto -> downstream-resolver` | `pcs-backend/app/core/errors.py:45` | `PYTEST_CURRENT_TEST` 早退 -> 车道里每次 403 都不写审计行 -> 「越权必留痕」空跑 | 车道环境下不要早退；并在权限矩阵里加一条「403 之后 `audit_logs` 多了一行」的断言 |
| 14 | P2 | `gated_auto -> downstream-resolver` | `pcs-backend/scripts/pytest_pg.sh:83` | 闸门③ 只要求「至少 1 passed」-> 几乎全 skip 也是绿的 | 断言 `passed` 数量接近场景总数，且 `xfailed` / `skipped` 判失败 |
| 15 | P2 | `gated_auto -> downstream-resolver` | `pcs-backend/tests/e2e_flows/test_e2e_schema_parity.py:65` | 两库闸只比彼此、不与代码 head 比 -> 两库一起落后也绿；且把车道绑在开发机状态上 | 加「与 `alembic heads` 比」这一条 + 补目标列存在性；并把它移出 E2E 车道（它是发布前检查） |
| 16 | P2 | `gated_auto -> downstream-resolver` | `pcs-frontend/src/pages/DashboardPage.tsx:40` | bug-2168 的守卫应是「拿到真 project id」，而不是「选了工作区」-> 工作区 `project_id` 可空 -> 选中后仍用占位 id -> 404 照旧 | 渲染条件改成「`project_id` 非占位值」；并给种子工作区补 `project_id` |
| 17 | P2 | `gated_auto -> downstream-resolver` | `pcs-backend/scripts/seed_e2e_flows.py:516` | 种子管级违反 `PipeClassResponse` 契约（`source` 不在 Literal / dn 缺 `{min,max}` / sch 是 float）-> 按 id 取必 500 | 改成契约内形状；并加一条「种子行能通过 `PipeClassResponse.model_validate`」的断言 |
| 18 | P2 | `manual -> human` | `pcs-backend/scripts/seed_e2e_flows.py:101` | 同一张 `pipe_classes` 有两套互斥行定义，`sch_series_json` 有三份互相矛盾的真相 | 先定唯一形状（改 ORM 注解或改 schema），再让两个写入方共用一个构造器 |
| 19 | P2 | `gated_auto -> downstream-resolver` | `pcs-backend/tests/e2e_flows/conftest.py:272` | 注释称 `e2e_seed` 已补 lifespan 的两处启动 seed -> 实测 0 处调用 -> 隔离 schema 缺系数表与系统参数 | 补上（或删掉那句注释）并加断言钉住行数 |
| 20 | P2 | `gated_auto -> downstream-resolver` | `pcs-backend/tests/e2e_flows/conftest.py:191` | `DROP CASCADE` 只挂在 fixture `finally` -> 进程被杀就永久留下 `e2e_<随机>` schema；`finally` 里的异常会顶替真正的失败原因 | 加 janitor（启动时清历史 `e2e_%` 残留）+ 把清理异常与测试失败分开报 |
| 21 | P2 | `manual -> human` | `pcs-backend/scripts/pytest_pg.sh:56` | 互斥锁只约束两条 pytest 车道 -> compose 的 `migrate` / `seed` 在同一个 `pcs_pgtest` 上裸奔 | 把互斥提升到库级（compose 也走同一把锁，或由 `pytest_pg.sh` 负责迁移） |
| 22 | P2 | `gated_auto -> downstream-resolver` | `pcs-backend/scripts/seed_e2e_flows.py:243` | `_get_or_create` 与 `_delete_own_rows` 把 house pattern 逐字复制成两份 -> 竞态修复只改得了一边 | 抽共享 helper（`scripts/seed_common.py`），两个种子脚本共用 |
| 23 | P2 | `gated_auto -> downstream-resolver` | `pcs-backend/tests/e2e_flows/helpers.py:206` | `CHAIN_ROLES` 是种子 `FLOW_MATRIX_STEPS` 的**未钉住副本** -> 矩阵一改，批准链就卡在 403 | 从种子派生 `CHAIN_ROLES` + 加一条比对断言（同仓 `ALLOWED_ROLES` 已有正确样板） |
| 24 | P2 | `gated_auto -> downstream-resolver` | `pcs-backend/tests/e2e_flows/test_e2e_record_workflow.py:48` | `_bump_record` 把 `helpers.bump_record` 逐字重写 -> 哈希判据两处 | 删掉本地副本，改 import helpers 的版本 |
| 25 | P2 | `gated_auto -> downstream-resolver` | `pcs-backend/tests/e2e_flows/conftest.py:294` | session factory 挂在 HTTP client 的私有属性上 -> 14 处 `# type: ignore` + helpers 拿到 client 却只要 session | 提成独立 fixture `e2e_session_factory`，helpers 签名改成收 factory |
| 26 | P2 | `gated_auto -> downstream-resolver` | `pcs-backend/app/api/v1/sim_imports_query.py:325` | preview-streams 无 `response_model` -> 本批统一的 `{"streams":[...]}` 没进契约；且注释称「SIM/Excel 存 dict」与事实相反（两个写入点都存 list） | 加 `response_model` + 改注释 + 重跑 `gate_08_openapi_contract.sh` |
| 27 | P2 | `manual -> human` | `pcs-backend/app/workers/report_tasks.py:118` + `pcs-backend/app/api/v1/report.py:494` | 把文件 sha256 写进 `data_version` -> `record_hash_digest` 与 `data_version` 塌成同一个值；`_expected_digest` 只读 `data_version` -> 老行仍返空串 | 两字段语义分开（`data_version` = 数据版本，`record_hash_digest` = 内容指纹）；修 #1 时一起裁 |
| 28 | P2 | `gated_auto -> downstream-resolver` | `spec/P10 AI预留与测试部署开发规格说明书.md:666` | D23~D38 写进了**非权威**的 V1.0 文件（其 §3.2.2 只有 14 场景）；该文件 D20 仍称「V1.3.1 不存在」，与 master-plan「以 V1.3.1 为准」直接矛盾 | 把偏离登记搬到权威那份（计划 :956 指定的就是它），并把 V1.0 的 D20 改成「本文件是 V1.0，P10-B 起以 V1.3.1 为准」 |
| 29 | P2 | `manual -> human` | `.wolf/STATUS.md:50` + `docs/solutions/` | QA 报告实际已产出（`qa-report-pcs-frontend-2026-11-17-p10b.md`），但 STATUS 指向 `2026-11-16-p10b.md` 且写「本轮还没跑」；同时 STATUS 自称三条教训「已进 docs/solutions」，本批却**没有任何** `docs/solutions/**` 改动 | 改 STATUS 的文件名与状态；把 4 条可复用解法回写 `docs/solutions/`（CLAUDE.md 知识库条要求） |
| 30 | P2 | `gated_auto -> downstream-resolver` | `pcs-frontend/e2e/real_backend_flows.spec.ts:32` | 跨语言种子常量靠**手抄**（`FLOW_PROJECT_ID` / `STREAM_NAME` / `DELIVERABLE_TITLE` / `MATRIX_NAME`）-> 矩阵名已经因此漂了 | 让种子产出机器可读 id 文件，前端 spec import 那份 |
| 31 | P2 | `manual -> human` | `pcs-backend/tests/e2e_flows/helpers.py:228` | 测试夹具的真相源住在 CLI 脚本里（`scripts/seed_e2e_flows.py` 的 `__all__` 已膨胀到 20 个常量）-> 依赖方向反了 | 把种子常量抽到中立模块，脚本与测试共同 import |
| 32 | P2 | `manual -> human` | `pcs-backend/app/schemas/stream.py:318` | 响应 `case_type` 可空但请求侧 `StreamBase` 仍必填 -> 读写不对称，「拿响应当入参」的客户端会 422 | 请求侧也允许省略，或在契约里明确登记「响应可空 => 入参必填」 |
| 33 | P3 | `gated_auto -> downstream-resolver` | `pcs-backend/scripts/pytest_pg.sh:57` | 锁路径可预测（`/tmp/pcs-pgtest-lane.lock`）且 `exec 9>` 跟随符号链接截断 -> 共享主机上可被诱导截断任意文件 | 用私有目录 + `O_NOFOLLOW` 语义，或 `>>` 加符号链接拒绝 |
| 34 | P3 | `gated_auto -> downstream-resolver` | `pcs-backend/tests/e2e_flows/conftest.py:84` | 跳过闸门只在 `tests/e2e_flows/` **目录**注册 -> 用例挪出该目录后默认车道会打开发库而守卫照样绿 | 把闸门上移到 `tests/conftest.py`，并断言所有 `@pytest.mark.e2e` 都在被注册的目录里 |
| 35 | P3 | `gated_auto -> downstream-resolver` | `pcs-backend/tests/e2e_flows/test_lane_smoke.py:194` | skip 闸门只有「假 item 动作断言」-> 新增一条漏 `@pytest.mark.e2e` 的用例会真跑开发库 | 改成后果级守卫：默认车道收集一次并断言 e2e 用例全部带 skip |
| 36 | P3 | `gated_auto -> downstream-resolver` | `pcs-backend/tests/scripts/test_pytest_e2e_gate.py:95` | flock 守卫对**含注释的原文**做子串匹配 -> 删掉 flock 只留注释也能过 | 用同文件已有的 `_body()` 剥注释，断 `flock -n` 与 `exec 9>` |
| 37 | P3 | `gated_auto -> downstream-resolver` | `pcs-backend/tests/scripts/test_pytest_pg_gate.py:111` | 「唯一入口」守卫只数 `uv run pytest` 一个字面量 -> `uv run python -m pytest` 等分叉进不来 | 改成按命令形状的正则匹配，并断两处分别是「收集」与「执行」 |
| 38 | P3 | `gated_auto -> downstream-resolver` | `pcs-backend/tests/e2e_flows/test_e2e_permission_matrix.py:147` | 「逐字同形」只比 status + code，且两次请求用**不同 uuid** -> 无权分支改 message 措辞仍绿 | 同一 uuid 测两次 + body 归一化后逐字比较 |
| 39 | P3 | `gated_auto -> downstream-resolver` | `pcs-backend/app/schemas/stream.py:318` | `case_type` 可空这条生产修复**零后端回归覆盖**（车道里根本没有 `GET /projects/{id}/streams` 用例） | 车道加一条该端点的用例；快车道加一条 `case_type` 可选性断言 |
| 40 | P3 | `gated_auto -> downstream-resolver` | `pcs-backend/tests/e2e_flows/test_lane_smoke.py:247` | `text_()` 死代码 | 删掉 |

**处置建议的读法**：#8 / #18 / #21 / #27 / #29 / #31 / #32 这 7 条需要**人先拍一次口径**，其余 33 条是机械工作（补断言、加护栏、删死代码），可一次性做完。

---

## Triage Groups

| Group | Findings | Context | Preferred Resolution | Why |
|-------|----------|---------|----------------------|-----|
| 守卫恒真 / 从未执行 | #3, #4, #5, #14, #35, #36, #37 | 本批把「验证机制」当交付物，但多处守卫断的是**动作**或**恒真量**，不是**后果** | 先定一次口径（#4 的「已知缺口白名单」与 #3 的观测点），再把其余 5 条一次性改掉 | 这 7 条是同一种病的不同器官：断言与被断言对象脱钩。口径不定，改一条还会再冒一条 |
| 目标库身份没有被断言 | #6, #11, #12, #20 | 车道的全部安全属性（「不碰开发库」「不写 public」）都建立在**没人检查目标库**之上 | 先落 #6 的库名白名单（一个 fail-closed 守卫），再补 #11 的全表快照与 #20 的 janitor | 白名单是前提：库里可能有残留 schema 时，后两条的断言读数本身不可信 |
| 本批自称修好的生产修复是空操作 | #1, #2, #27 | bug-2165 的修复写在会被删掉的行上，守卫它的断言又被 `xfail` 中止 | 先修 #1（赋值落到存活行），再把 #2 的 xfail 换成硬断言；#27 的语义裁剪与 #1 一起做 | 三条是同一处代码的三个面：赋值位置、断言形状、字段语义。分开修会各留一半 |
| 运行时写全局配置表（占位管级） | #7, #8, #17, #18 | 一次链计算会往**公司级**标准目录插一行没有版本、没有审批的假标准；种子那一侧还违反响应契约 | 先裁 #8 的口径（配置数据归迁移 还是 归运行时兜底），再统一 #17 / #18 的行定义，最后用 #7 的 savepoint 收并发 | 口径一变，#17 / #18 的具体形状与 #7 的实现方式都跟着变，所以 #8 必须先做 |
| 前端取数通道与跨语言常量 | #9, #10, #30 | 前端有两条 HTTP 通道（axios vs 裸 fetch），跨语言常量靠手抄 | 先做 #9（统一到 axios），再做 #30（生成 id 文件），最后用 #10 把复现条件写进仓库 | #10 的 fail-fast 守卫依赖 #30 产出的真实 id；#9 决定 UI 流失败时能不能被看见 |
| 治理与文档闭环 | #22, #23, #24, #25, #28, #29, #31 | 本批的解法没有回写 `docs/solutions/`，偏离登记写进了非权威 SPEC，守卫测试大量复制 | #28 / #29 先落（口径与事实），#22-#25 / #31 作为一次「去重复」的清扫一起做 | 都是「两份真相源」的同一族，单独清一条只会让另一条更显眼 |

---

## 完整发现表

置信度列给的是证据锚点（50 / 75 / 100）。**同进程 persona 的互相印证不抬锚点**（同一模型服务），所以多人报的那几条也只反映单人给出的强度。

### P1 -- Critical / High

| # | File | Issue | Reviewer | Confidence |
|---|------|-------|----------|------------|
| 1 | `pcs-backend/app/workers/report_tasks.py:118` | `data_version` 赋值在 `dup` 早退之后 -> 永不可达，审计哈希端点仍恒返空串 | correctness, reliability | 100 |
| 2 | `pcs-backend/tests/e2e_flows/test_e2e_report.py:91` | 命令式 `xfail` 中止整条用例 -> 修复无回归保护 | testing, adversarial | 100 |
| 3 | `pcs-frontend/e2e/real_backend_flows.spec.ts:144` | 越权 UI 断言恒等（角色闸短路）-> 404 分支从未执行 | adversarial, learnings | 100 |
| 4 | `pcs-frontend/e2e/real_backend_route_sweep.spec.ts:56` | 「渲染出来了」断的是静态 `#root` -> 恒真 | adversarial, testing, learnings, project-standards | 100 |
| 5 | `pcs-frontend/e2e/real_backend_flows.spec.ts:41` | 断的是全局内置矩阵，不是种子那张 | adversarial, correctness, maintainability | 100 |
| 6 | `pcs-backend/tests/e2e_flows/conftest.py:93` + `pcs-backend/scripts/seed_e2e_flows.py:763` | 车道与种子都没有目标库护栏 | security, adversarial, testing, reliability | 75 |
| 7 | `pcs-backend/app/services/pipe/pipe_chain_persist.py:112` | 占位管级先查后插无 savepoint -> 并发撞主键 -> 500 | reliability, correctness, adversarial | 75 |
| 8 | `pcs-backend/app/services/pipe/pipe_chain_persist.py:95` | 计算端点运行时往全局配置主表写占位管级 | maintainability, security, correctness, api-contract | 75 |
| 9 | `pcs-frontend/src/pages/routeWrappers.tsx:92` | `useFetch` 吞错 + 绕过 axios 401 -> token 过期后永久「加载中…」 | reliability, maintainability | 75 |
| 10 | `pcs-frontend/package.json:20` | 真后端 UI 车道无法从仓库复现（4 个环境变量没写出来） | testing | 75 |

- **#1** - `report_tasks._finalize` 先 `await db.delete(row)` 再 `return str(dup.report_file_id)`（`:107-111`），而 `row.data_version = digest` 在 `:118`，位于那个 `return` 之后。`dup` **必然命中**：`report_service.generate` -> `store_rendered` -> `_upsert_report_file`（`report_service.py:612-618`）已经建了一行 `content_hash == digest` 的 `ReportFile`，且它**没有** `data_version` 字段。于是占位行被删，活下来的那行 `data_version` 仍是 NULL，`report.py:494` 的 `return row.data_version or ""` 继续返空串。证据：`report_tasks.py:107-111`、`:118`、`report_service.py:606-618`、`report.py:494`。修法见 Actionable 表。
- **#2** - `pytest.xfail()` 是**命令式**的，抛异常中止整个测试函数，所以紧跟其后的「下载 200 + 字节数 > 0」两段断言一次都不执行（`test_e2e_report.py:96-100`）。而 `pytest_pg.sh:83-86` 的闸门只 grep `[1-9][0-9]* passed`，`xfailed` 不算失败 -> **#1 的修复被回退，车道依旧全绿**。修法：修完 #1 后改成硬断言，并让闸门把 `xfailed` 判失败。
- **#3** - 用例比较 `unauthorized.status()` 与 `nonexistent.status()`，但观测点 `GET /projects/{id}/streams` 先跑 `require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")`（`streams.py:407`），`bob` 在 mock 登录里是 CHECKER（`mock_auth.py:16`）-> 两个请求都在 `:407` 返回 403，`check_project_access_or_404`（`streams.py:410`）**一次都没执行** -> 断言退化成 `403 === 403`。把 `streams.py:410` 整段删掉，这条用例照样绿。mock 登录的 4 个用户里**没有一个**能表达「角色够但没授权行」（dan 走 SYSTEM_ADMIN bypass）-> 需要显式造一个这样的身份。
- **#4** - `const root = (await realPage.locator('#root').count()) > 0`（`:56`）断的是 `index.html:9` 的静态容器 div，count 恒为 1 -> 白屏、渲染异常、错误边界、懒加载失败都绿。再叠加 `:64-69` 自陈「控制台无 error / 无 4xx-5xx **不作为断言**」，CLAUDE.md《Per-Batch QA Gate》里的三条浏览器判据（路由可达 / 控制台无 error / 网络无 404）在本批之后**没有任何自动断言在守**。修法：先维护一份「已知缺口路由白名单」（对应 TODO-159 的 3 个 404 与 TODO-160 的 3 个 422），断言 4xx 只出现在白名单里。
- **#5** - `MATRIX_NAME = 'DEFAULT_RECORD_3_LEVEL'`（`:41`）是迁移 `p9_013` 在任何已迁移库里都插的**全局内置矩阵**（`signature_matrix_service.py:124`），而本批种子那张叫 `E2E_FLOWS_RECORD_3_LEVEL`（`seed_e2e_flows.py:583`）且只绑在 flows 项目上 -> 种子没灌 / 名字漂了 / 项目绑定没生效，这条用例照样绿。修法：断种子那张，并把断言收窄到「项目绑定」那张表（加 testid）。
- **#6** - `_lane_url()` 只断 `url.startswith("postgres")`（`conftest.py:93-101`），库名从不检查；而拿到 URL 就 `CREATE SCHEMA` + 子进程 `alembic upgrade head`（`conftest.py:164-187`）。种子脚本更彻底：`_main` 直接 `get_async_session_factory()`（`seed_e2e_flows.py:751`），`session.py:66` 解析 `settings.database_url` -> 落到 `.env` 的**开发库 `pcs`**。脚本自己文档化的调用（`seed_e2e_flows.py:3729`）就会往开发库写 E2E 项目、`alice` 的 `users` 行与 `user_projects` 授权行。症状是「跑得挺快、全绿」。修法：库名白名单 + 不匹配即非零退出。
- **#7** - `_ensure_placeholder_pipe_class` 是裸的 SELECT-then-INSERT（`:105-111` 查、`:112-138` 插），无 `begin_nested()`、无 `IntegrityError` 分支。两个并发的 `POST /api/v1/pipe/calc-chain` 都看到「不存在」-> 都 INSERT -> 输家撞 `pipe_classes.class_id` 主键（`config_domain.py:237`）-> `IntegrityError` 逃过 `pipe.py:213-216` 的 `except PcsError` -> **端点 500 且事务被 abort**。本仓的 house pattern 就在同批的 `seed_e2e_flows.py:257-269`（savepoint + 重读赢家），产品代码这段没照抄。
- **#8** - 落库层从「只写业务结果」变成「写业务结果 + 写主数据」。`source="COMPANY_STD"`（`:134`）+ `pipe_class_service.py:149` 的 `where(PipeClass.source == "COMPANY_STD")` -> 这行必然出现在**公司级管架列表**里，名字叫「碳钢标准（链计算占位）」，`asset_id=None`、无版本、无 5 态审批，也不在 `PipeClassService.create`（`pipe_class_service.py:173`）的创建路径上。任何人在任何项目跑一次链计算，就往**共享参考数据**里永久插入一行假的公司标准，并出现在所有人的管架下拉里（还能被 fork 成项目级管级）。
- **#9** - 本批把 `useFetch` 的 `headers` 从写死的 `DEV_BEARER` 改成会话里的真 token（diff 中的改动行）。但这条通道用的是裸 `fetch`：`r.ok ? r.json() : null` 把非 2xx 折成 `null`，`.catch(() => {})`（`:92`）把网络异常吞掉 -> `data` 永远停在 `initial` -> `StreamDetailRoute` 永久渲染「加载中…」（`:159-160`）。同时它**绕过 axios 的响应拦截器**（`client.ts:51-66`：401 -> `clearSession()` + 跳 `/login`），而 `access_token_expire_minutes: int = 30`（`config.py:46`）意味着过期是必然事件 -> 用户既不被踢回登录页、也看不到任何报错，裸 `fetch` 还没有超时。注：`.catch` 与 `r.ok ? null` 本身是本批未改的上下文行，本批的改动让「过期」从边缘情况变成必然事件。
- **#10** - 后端 `DATABASE_URL` 必须指向 `pcs_pgtest`（:5433）+ `PCS_ENABLE_MOCK_LOGIN=true`，前端 `VITE_PROJECT_ID` 必须是 flows 项目 id + `VITE_API_PROXY_TARGET` 必须指向那个后端。`npm run e2e:real`（`package.json:20`）只设了后两个里的一个（且默认指向 **:8000 的开发后端**），`playwright.config.ts` 的真后端 webServer 只设了 `VITE_ENABLE_MOCK=false`。而 `src/constants/env.ts:13` 的 `PROJECT_ID` 默认值是占位 id -> 不注入时物流/交付物/签署矩阵三页查的是**另一个项目** -> 空表。完整复现步骤只写在 `.gstack/qa-reports/qa-report-pcs-frontend-2026-11-17-p10b.md`，而 `.gstack/` 已 gitignore -> 换机器就再也跑不起来这条验收。更糟：项目 id 错掉时「路由扫描」与「越权可见性」这两条**照样绿**。

### P2 -- Moderate

| # | File | Issue | Reviewer | Confidence |
|---|------|-------|----------|------------|
| 11 | `pcs-backend/tests/e2e_flows/test_lane_smoke.py:240` | 「不写 public」守卫只快照 4 张表、只在种子后取基线、只跑一条写路径 | security, testing, adversarial | 75 |
| 12 | `pcs-backend/tests/e2e_flows/conftest.py:289` | 隔离只覆盖 `get_db` -> 全局 session factory 仍指 public schema | adversarial | 75 |
| 13 | `pcs-backend/app/core/errors.py:45` | `PYTEST_CURRENT_TEST` 早退 -> 车道里每次 403 都不写审计行 | adversarial | 100 |
| 14 | `pcs-backend/scripts/pytest_pg.sh:83` | 闸门③ 只要求「至少 1 passed」-> 几乎全 skip 也绿 | adversarial | 75 |
| 15 | `pcs-backend/tests/e2e_flows/test_e2e_schema_parity.py:65` | 两库闸只比彼此、不与代码 head 比，且把车道绑在开发机状态上 | correctness, testing, maintainability | 75 |
| 16 | `pcs-frontend/src/pages/DashboardPage.tsx:40` | bug-2168 守卫条件不严（工作区 `project_id` 可空 -> 仍用占位 id） | correctness | 75 |
| 17 | `pcs-backend/scripts/seed_e2e_flows.py:516` | 种子管级违反 `PipeClassResponse` 契约 -> 按 id 取必 500 | correctness, learnings | 75 |
| 18 | `pcs-backend/scripts/seed_e2e_flows.py:101` | `pipe_classes` 两套互斥行定义 + `sch_series_json` 三份真相 | maintainability | 100 |
| 19 | `pcs-backend/tests/e2e_flows/conftest.py:272` | 车道不跑 lifespan，注释谎称已补启动 seed -> 缺系数表与系统参数 | reliability | 75 |
| 20 | `pcs-backend/tests/e2e_flows/conftest.py:191` | 隔离 schema 清理只挂 `finally` -> 永久残留 + 异常顶替失败原因 | reliability | 75 |
| 21 | `pcs-backend/scripts/pytest_pg.sh:56` | 互斥锁只覆盖两条 pytest 车道 -> compose 的 migrate/seed 在同库裸奔 | reliability | 75 |
| 22 | `pcs-backend/scripts/seed_e2e_flows.py:243` | house pattern 被逐字复制成两份（`_get_or_create` + `_delete_own_rows`） | maintainability | 100 |
| 23 | `pcs-backend/tests/e2e_flows/helpers.py:206` | `CHAIN_ROLES` 是种子 `FLOW_MATRIX_STEPS` 的未钉住副本 | maintainability | 100 |
| 24 | `pcs-backend/tests/e2e_flows/test_e2e_record_workflow.py:48` | `_bump_record` 把 `helpers.bump_record` 逐字重写 | maintainability | 100 |
| 25 | `pcs-backend/tests/e2e_flows/conftest.py:294` | session factory 挂在 HTTP client 私有属性 -> 14 处 `type: ignore` + Feature Envy | maintainability | 75 |
| 26 | `pcs-backend/app/api/v1/sim_imports_query.py:325` | preview-streams 无 `response_model` + 注释与事实相反 | api-contract, maintainability | 75 |
| 27 | `pcs-backend/app/workers/report_tasks.py:118` + `pcs-backend/app/api/v1/report.py:494` | `data_version` 被文件 sha256 占死 -> 两字段语义塌陷 + 老行仍返空串 | api-contract | 75 |
| 28 | `spec/P10 AI预留与测试部署开发规格说明书.md:666` | D23~D38 写进非权威 SPEC，D20 与 master-plan 直接矛盾 | api-contract, project-standards | 75 |
| 29 | `.wolf/STATUS.md:50` + `docs/solutions/` | QA 报告口径不一致 + 4 条可复用解法未回写 `docs/solutions/` | project-standards | 75 |
| 30 | `pcs-frontend/e2e/real_backend_flows.spec.ts:32` | 跨语言种子常量靠手抄，无生成/校验机制 | maintainability | 100 |
| 31 | `pcs-backend/tests/e2e_flows/helpers.py:228` | `scripts/` 被当成测试 fixture 的公共库（依赖方向反了） | maintainability | 75 |
| 32 | `pcs-backend/app/schemas/stream.py:318` | 响应可空 / 请求必填 -> 读写不对称 | api-contract | 75 |

- **#11** - `_public_snapshot` 只数 `users / projects / streams / user_projects` 四张表的 `count(*)`（`:240`），而车道写的表远不止这四张（`piping_results` / `deliverables` / `workspaces` / `signature_matrices` / `equipment_list` / `pipe_classes` / `report_definitions` / `ai_audit_log` …），且基线取在种子**之后**（`:132`）-> 种子阶段的泄漏已被吸收进基线。docstring 宣称「E2E 的行**不能**出现在 public schema」-> 断言范围与宣称范围不一致。修法：枚举 `information_schema` 里 public 的所有表取 `count(*)` + `max(id)`，并在种子**前**取基线。
- **#12** - `app.dependency_overrides[get_db]` 只改写依赖注入层；`app/db/session.py::get_async_session_factory()` 是**进程级单例**，engine 来自 `settings.database_url` -> 车道里那是 `pcs_pgtest` 的 **public**。`app/api/v1/ws.py:77`（WS 握手鉴权）与 `app/core/errors.py:51`（RBAC 拒绝审计）都走它 -> 这两条路径在车道里读/写的是另一个房间，与生产（同一个库）行为不同，而 #11 的守卫看不见它们。
- **#13** - `_write_rbac_audit_row` 在 `PYTEST_CURRENT_TEST` 存在时直接 `return`（`errors.py:45-46`）-> 真后端车道里**每一次 403 都不写审计行** -> 权限矩阵里 5 条 403 用例验的是「无副作用」的版本，生产上「越权必留痕」这条合规语义在车道里是空跑。早退的理由（防测试写真实 DB）在隔离 schema 车道里已不成立。
- **#14** - 闸门③ 是 `echo "$out" | grep -qE '[1-9][0-9]* passed'`（`pytest_pg.sh:83-86`）-> 只要有一条真跑过就算过。若某次改动让绝大多数场景被静默跳过，车道照样全绿。修法：断 `passed` 数量接近场景总数，并把 `xfailed` / `skipped` 也判失败。
- **#15** - 用例只断言 `pcs_rev == pcs_test_rev`（`:70-76`），**从不与代码 head 比** -> 两库一起停在同一个旧 revision（CLAUDE.md 记过 `pcs_test` 停在 `p7_s4_001` / `p9_006` 这类事故）时照样通过。同时它从 `.env` 取**开发库** URL（`:65-68`）-> 车道红绿绑在开发机本地库状态上；而且「两库一致性」是**发布前检查**（CLAUDE.md 第 1 条），不是端到端场景，放在 `@pytest.mark.e2e` 里等于「批末跑一次的检查」占了车道一个名额。
- **#16** - 修 bug-2168 的守卫是 `{selected ? <InputChecklistPanel projectId={projectId} /> : null}`（`:40`），但真正的触发条件是「拿到的 projectId 是占位值」：`workspaceProjectId(ws)`（`:8-10`）在 `ws.project_id` 为 null 时**仍然**返回占位 id，而 `Workspace.project_id` 可空（`models/project.py:118`），两个种子脚本造的工作区都**没填** `project_id`（`seed_e2e_flows.py:338-343`）-> 选中它们之后面板照旧用占位 id 取数 -> 404 与控制台 error 照旧出现。
- **#17** - 种子造的 `pipe_classes` 行三处违反出参契约：`source="E2E_SEED"` 不在 `Literal["COMPANY_STD","PROJECT"]`（`schemas/pipe_class.py:77`）；`dn_series_json={"DN150": 1.0}` 缺 `{min,max}` -> `_check_dn` 抛 ValueError（`:91-93`）；`sch_series_json={"DN150": 40.0}` 的值是 float，而契约是 `dict[str, str]`（`:62-63`，pydantic v2 不把数字转字符串）。`GET /pipe-classes/{class_id}` 用 `PipeClassResponse`（`api/v1/pipe_classes.py:168`）-> 必然 500。它现在不可见，只因为 `source="E2E_SEED"` 不在 `list_company` 的过滤范围内。
- **#18** - `sch_series_json` 这一列有**三份互相矛盾**的真相：ORM 声明 `Mapped[list]`（`models/config_domain.py:249`）、Pydantic 响应声明 `dict[str, str]`（`schemas/pipe_class.py:61`）、两个写入方各写各的（运行时的 `{min,max}` 与种子的 `{DN150: 40.0}`）。而 `dn_series_json` / `sch_series_json` 的**键**在两处也不同（`min`/`max` vs `DN150`）。
- **#19** - conftest:271-272 写「『只有 lifespan 才会做的那两处 seed』由 `e2e_seed` 显式补」，但实测 `coefficient|system_setting|Coefficient|SystemSetting|seed_default` 在 `seed_e2e_flows.py` / `seed_e2e_data.py` / `conftest.py` 上**0 命中**。生产在 `app/main.py:157-160` 的 lifespan 里 seed `CoefficientService.seed_default_tables` 与 `seed_system_setting_defaults` -> 隔离 schema 里这两处是空的 -> 依赖它们的场景看到的是「空的生产默认集」-> 车道可以在与生产形状不同的上下文上绿过去。注释主动掩盖了这个缺口。
- **#20** - 清理只挂在 fixture 的 `finally`（`conftest.py:189-192`）-> SIGKILL / 容器被杀 / DB 断连时不跑 -> 隔离 schema 永久留在共享库里，而 schema 名是随机的 `e2e_<8hex>`（`:164`）-> 下轮的「起手 DROP」只针对本轮那个名字，**旧残留一个都清不掉**。且 `finally` 里的 DROP 自己也可能抛（连接已断）-> **顶替掉真正的失败原因**。
- **#21** - 锁放在共享脚本里是对的（两条 pytest 车道都生效，`flock -n` 快速失败，fd 9 被子进程继承），但**同一个 `pcs_pgtest` 库还有别的写者没进锁**：compose 的 `migrate` 服务（`docker-compose.yml:113`，`alembic upgrade head` 写 public schema）与 `seed` 服务（`:140-145`）都在这个库上跑 DDL/DML -> 开发者 `docker compose --profile test up` 时，隔离 schema 的 DDL 与 public schema 的 DDL 并发 -> 表现是 catalog 锁互等（脚本注释自己写的「偶发卡住」）。
- **#22** - `seed_e2e_flows.py:243-270` 的 `_get_or_create`（`begin_nested()` + `flush()` + 捕获 `IntegrityError` 后重读赢家）与 `seed_e2e_data.py:108-140` **逐字相同**（含同一段注释）；`_delete_own_rows` 也是两份（FK 删序清单一份 9 张表、一份 4 张表）-> 竞态处理被修好时只改得了一边；新增实体时两份清单都要记得改，漏一份 -> `--reset` 撞 FK。
- **#23** - `CHAIN_ROLES = ("CHECKER","REVIEWER","APPROVER")` 是种子里 `FLOW_MATRIX_STEPS` 的 `sign_role` 序列的**第二份副本**，注释还明说「与种子的签署矩阵一致」，但一致性**没有任何机制保证**：全仓 `FLOW_MATRIX_STEPS` 只出现在种子脚本里，`CHAIN_ROLES` 只出现在 helpers 与一个断言里，两边没有一处比对 -> 矩阵一改，`approve_record_steps` 仍按旧角色发请求 -> 403 `APPROVAL_ROLE_MISMATCH` -> 症状看着像「端点坏了」。同仓已有正确样板：`ALLOWED_ROLES` 那份 copy 被 `test_lane_smoke.py:172-191` 逐个比对钉住。
- **#24** - `helpers.py:353-369` 的 `bump_record`（`design_press + 0.1` -> flush -> `compute_record_hash` -> commit）已在 `test_e2e_change_impact.py` 使用；`test_e2e_record_workflow.py:48-61` 又把它逐字抄了一份（该文件的 import 列表里**没有** `bump_record`）-> 「哈希怎么算、什么时候算」这条规则有两处，将来 CIA 的哈希判据变了，改了 helpers 那份，另一条用例仍按旧规则绿着。
- **#25** - 车道把 `session_factory` 藏进 `httpx.AsyncClient` 实例的私有属性 `_e2e_session_factory`（`conftest.py:294`），于是「直查隔离 schema」在 14 处靠 `# type: ignore[attr-defined]` 维持；更根本的是**「要一个 DB session」被迫先造一个 HTTP client** -> `make_record` / `bump_record` / `link_lineage` 都只需要 session 却都得接一个 client 参数（Feature Envy）。
- **#26** - 端点只有 `-> dict` 注解、没有 `response_model`（`:325-330`）-> OpenAPI 里 200 仍是 `{"type": "object"}`（前端生成类型是 `{[key: string]: unknown}`）-> 消费者无法从契约得知必须读 `.streams`。同时新增的注释说「SIM/Excel 导入存 **dict**（`{"streams": [...]}`）」，与事实相反：`import_service.py:496`（PRO/II）与 `:612`（EXCEL）两个写入点都存 **list** -> 归一的影响面比注释写的大。同一处注释问题也出现在 `models/sim_import.py:95` 的 `Mapped[dict]` 注解上。
- **#27** - `row.data_version = digest` 写的是**文件** sha256，而 `data_version` 列原义是「登记时冻结的数据版本」（`report.py:487-494`）-> `GET /report/{id}/hash` 的 `record_hash_digest` 与 `data_version` 现在返回同一个值，审计方无法区分「源数据版本」与「文件内容摘要」。且 `_expected_digest` 只读 `data_version` -> 本批之前登记的行恒返空串；`_finalize` 的 dup 分支直接 `return`，被复用的行也永远没写过。
- **#28** - 计划 :956 明确写 `Modify: spec/PCS-SPEC-P10 V1.3.1 …md`（第五部分「偏离登记」），本批却把 D23~D38 追加进了 **V1.0** 那份（其 §3.2.2 只有 14 场景，而 D23~D38 每条都引用 §3.2.2 的 18 场景口径）-> 权威那份**一条都没被修订**，下一个按权威文件读 SPEC 的人拿到的是过期口径。该文件 D20 仍写着「PCS-SPEC-P10 V1.3.1 在仓库中不存在 => 以 V1.0 为准」，与 master-plan :216-220 的新裁决「以 V1.3.1 为准」**直接冲突**。
- **#29** - 两件事：(a) `.wolf/STATUS.md:50-51` 指向 `qa-report-pcs-frontend-2026-11-16-p10b.md` 且写「**本轮还没跑**」，而实际产出的是 `qa-report-pcs-frontend-2026-11-17-p10b.md`（7.1K，2026-11-17 01:33）-> 状态文案与事实不一致；`project-standards` persona 据 STATUS 断言「报告尚未产出」，这一条**已被证伪**（报告存在），真实问题只是口径。(b) STATUS:86-92 自称三条教训「已进 cerebrum / docs/solutions」，但本批的改动文件清单里**没有任何** `docs/solutions/**` 条目 -> 那句断言不成立，而 CLAUDE.md 知识库条明确要求「新增解法后回写一份，别只留在提交信息里」。
- **#30** - `FLOW_PROJECT_ID`（种子里是 `uuid5(NAMESPACE_DNS, "pcs-e2e-flows-project")` 的结果）、`STREAM_NAME`、`DELIVERABLE_TITLE`、`MATRIX_NAME` 四个值在 Python 与 TS 各存一份，没有任何生成或校验机制 -> **已经有一份对不上**：spec 注释写「种子签署矩阵名（`_ensure_matrix`）」，值却是 `DEFAULT_RECORD_3_LEVEL`，而种子写的是 `E2E_FLOWS_RECORD_3_LEVEL`。修 #30 可一并消掉 #5 的复发路径。
- **#31** - 测试层的 fixture 数据住在 **CLI 脚本**里：`helpers.py` 从 `scripts.seed_e2e_flows` 取 `PIPING_RECORD_PAYLOAD`（造记录的 21 字段模板），`conftest.py` 从同一个脚本取全部 id 与角色映射。`scripts/` 靠 namespace package 被 import 进来，`__all__` 已膨胀到 20 个常量名（`seed_e2e_flows.py:773-794`）纯粹是为了让这个脚本可当库用。分层上生产/运维脚本是上层、测试夹具是下层 -> 依赖方向反了。
- **#32** - `StreamResponse.case_type` 改成可空（对齐 DB 的 `Mapped[str | None]`），但请求侧 `StreamBase.case_type` 仍必填 -> 读到的 null 值无法原样写回（GET->POST 回写会 422）。前端既有消费点（`StreamListPage.tsx:175`、`StreamBasicTab.tsx:71`）已全部加空值保护，本批不破坏任何现有消费者，契约侧只是同一字段读写要求不一致。

### P3 -- Low

| # | File | Issue | Reviewer | Confidence |
|---|------|-------|----------|------------|
| 33 | `pcs-backend/scripts/pytest_pg.sh:57` | 锁路径可预测 + `exec 9>` 跟随符号链接截断 | security | 50 |
| 34 | `pcs-backend/tests/e2e_flows/conftest.py:84` | 跳过闸门只随 `tests/e2e_flows/` 目录注册 | testing | 75 |
| 35 | `pcs-backend/tests/e2e_flows/test_lane_smoke.py:194` | skip 闸门只有「假 item」动作断言 | learnings | 50 |
| 36 | `pcs-backend/tests/scripts/test_pytest_e2e_gate.py:95` | flock 守卫对含注释原文做子串匹配 | testing, learnings | 75 |
| 37 | `pcs-backend/tests/scripts/test_pytest_pg_gate.py:111` | 「唯一入口」守卫只数一个字面量 | testing | 75 |
| 38 | `pcs-backend/tests/e2e_flows/test_e2e_permission_matrix.py:147` | 「逐字同形」只比 status + code，且用不同 uuid | learnings | 75 |
| 39 | `pcs-backend/app/schemas/stream.py:318` | `case_type` 可空这条修复零后端回归覆盖 | testing | 75 |
| 40 | `pcs-backend/tests/e2e_flows/test_lane_smoke.py:247` | `text_()` 死代码 | maintainability | 100 |

- **#33** - `exec 9>"$LOCK_FILE"` 会**截断**目标路径，默认是 `/tmp/pcs-pgtest-lane.lock`（固定、位于 world-writable 目录）-> 共享主机上另一个本地用户可以把它预置成指向任意可写文件的符号链接，下一次车道运行就把那个文件截断（shell 重定向跟随符号链接），而车道继续跑、仿佛拿到了锁。`PCS_PGTEST_LANE_LOCK` 还能让调用方把截断指向任意路径。影响限于开发机、需要一个本地低权用户，修法一行。
- **#34** - `pytest_collection_modifyitems` 定义在 `tests/e2e_flows/conftest.py` 里 -> 只有 pytest 真的收集了 `tests/e2e_flows/` 时才注册。目前所有 `@pytest.mark.e2e` 用例都在该目录（已核对），所以默认车道安全，但这个保证是**巧合式的**。守门测试 `test_e2e_items_are_skipped_without_the_lane_flag` 只用一个自造 `_FakeItem` 调闸门**函数**，既不验证 hook 真被 pytest 调用，也不验证「所有 e2e 用例都在被注册的目录里」。
- **#35** - 守卫断的是**动作**（`add_marker` 被调过）而不是**后果**（「默认车道里一个 e2e 用例都没被执行」）。只要有人加一条忘了 `@pytest.mark.e2e` 的用例，它就会在默认车道真的连上开发库跑隔离 schema + alembic + 种子，而当前守卫仍然绿。
- **#36** - 断言的是「`pytest_pg.sh` 全文里出现过 `flock` 这个词」，而且读的是**未剥注释**的原文（同文件里给薄封装用的 `_body()` 恰恰会剥注释，两处口径不一致）-> 把 `flock -n 9` 改成阻塞的 `flock 9`（并发时变成挂死而不是报错）守卫照样绿；把整段锁删掉只留一句「TODO: 用 flock」的注释守卫也照样绿。
- **#37** - 守卫意图是「脚本里不得出现第二条不经脚本的 pytest 调用路径」，实现是 `body.count("uv run pytest") == 2` -> `uv run python -m pytest`、裸 `pytest`、写成变量再展开都不会被计数。反过来，任何一次合法的新增 pytest 调用都会把这个 count 断言顶红 -> 守卫同时也是脆的。文档里已经写着「不得在 README/CLAUDE.md 里教『也可以直接 DATABASE_URL=... pytest』」，说明这条分叉是真实存在的诱惑。
- **#38** - 两条同形断言都停在「状态码 + code」：后端比 `missing.json().get("code") == resp.json().get("code")`，而且两个请求用的是**不同** uuid（一个是种子项目 id，一个是 `uuid.uuid4()`）-> 只要有人把无权分支的 message 改成不同措辞，两条用例都仍绿，而枚举向量已经打开。仓库已记录的死法是「无权」与「不存在」必须**逐字同形」（含 code 与 message），且「同形测试必须用同一个 uuid 测两次」。
- **#39** - `case_type` 可空这条生产修复的**唯一**覆盖在 Playwright 真后端通道。后端两侧都没有：快车道 `tests/schemas/test_stream_vocabulary.py` 只断言词表四项与 `raw_phase`；E2E 车道的隔离 schema 里**正好躺着会触发这个 bug 的数据**（`seed_e2e_flows.py:428-448` 建 Stream 时没给 `case_type` -> NULL），却没有任何一条 e2e 用例去 GET `/projects/{id}/streams` -> 把这次修复回退成必填，两条后端车道都不会红。
- **#40** - `text_()` 定义后全文件零引用（同文件的 SQL 都在函数体内直接 `from sqlalchemy import text`）-> 新文件里的死代码，读者会以为有一条「统一走 text_ 短别名」的约定。

---

## Requirements Completeness

对照计划 `docs/superpowers/plans/2026-11-13-p10-batch-b-fullflow-e2e.md`（**explicit** 计划，本批照它实施）。已核对：`tests/e2e_flows/` 下 13 个文件、32 个测试函数、30 个 `@pytest.mark.e2e`；SPEC V1.3.1 §3.2.2 的 E2E-001..018 逐条对照。

| 计划项 | 状态 | 说明 |
|---|---|---|
| E2E-001 项目创建 -> BEDD -> 输入清单 | met | `test_e2e_project_config.py`（含 D27：清单靠显式 seed 生成，非自动） |
| E2E-002 SIM 导入 -> 物流验证 | met | `test_e2e_sim_import.py`（两段式，见 D31） |
| E2E-003/004/005/006 管道 / 泵 / 安全阀 / 容器计算链 | met | `test_e2e_calc_chains.py` 4 条 |
| E2E-007 设备表汇总 | met | `test_e2e_equipment_util.py` |
| E2E-008 能耗汇总 | met | 同上（断「汇总 = 明细之和」） |
| E2E-009 报表生成 -> 计算书 | **partially** | 用例在，但 `pytest.xfail` **中止**了它 -> 「计算书生成正确」这条验收今天**没有被真正断言**（#2） |
| E2E-010 记录层审批 | met | `test_e2e_record_workflow.py::test_e2e_010_...` |
| E2E-011 交付物 Rev | met | `test_e2e_deliverable_rev.py::test_wf_path_02_...` |
| E2E-012 签署矩阵与代录 | met | `test_wf_path_03_proxy_customer_approval_records_who_recorded_it` |
| E2E-013 上游变更影响 | met | `test_e2e_change_impact.py`（断 `propagated >= 1`，见 D34） |
| E2E-014 供应商实际值 -> 偏差报告 | met | `test_e2e_supplier.py` |
| E2E-015 自定义报表执行 | met | `test_e2e_report.py` |
| E2E-016 用户权限验证（跨项目 404） | met（后端） | `test_e2e_016_cross_project_access_is_404_not_403`；但只断 status + code（#38），且**前端**对应流恒等（#3） |
| E2E-017 AI 占位与审计 | met | `test_e2e_ai_audit.py`（两段式：入队 spy + 直调写库，见 D6） |
| E2E-018 两库 schema 一致 | **partially** | 只断「两库彼此相等」，不与代码 head 比、不断目标列存在性；且它是发布前检查却放在 E2E 车道（#15） |
| WF-PATH-01A/01B/01D/01E（记录层） | met | `test_e2e_record_workflow.py` 4 条 |
| WF-PATH-01C（变更闭环） | met | `test_e2e_change_impact.py::test_wf_path_01c_...` |
| WF-PATH-02/03（交付物 Rev / 代录） | met | `test_e2e_deliverable_rev.py` 2 条 |
| WF-PATH-04（权限矩阵与签署矩阵一致性） | met | `test_e2e_permission_matrix.py::test_wf_path_04_...` |
| AUTH-E2E-01~10（权限矩阵四元组） | met | `test_permission_matrix` 参数化 10 行（含 AUTH-E2E-05b 拆行，见 D35），逐行断**错误码** |
| AUTH-E2E-11/12（`TEST_VIEWER`） | **not addressed（计划内刻意不做）** | 角色不存在 + 测试报告页属 P10-C => D24 + TODO-153，非本批缺陷 |
| 真后端通道 5 条 UI 流 | **partially** | 5 条都在且跑通，但其中 3 条的断言**恒真或断错对象**（#3 越权 / #4 路由扫描 / #5 矩阵）=> 数字绿、内容空 |
| 车道隔离 schema + 真 PG + 真 app | met（结构） | 结构齐全，但「隔离」「fail-closed」目前**不可证**（#6 #11 #12 #20 #14） |
| 三道 fail-closed 闸门 + flock 互斥 | met（结构） | 闸门在，但守门测试本身可能失效（#36 #37）；锁只覆盖 pytest 车道（#21） |
| 批末 QA 报告 | met | `.gstack/qa-reports/qa-report-pcs-frontend-2026-11-17-p10b.md` 存在（7.1K）；但 STATUS 指向另一个文件名并写「本轮还没跑」（#29） |
| SPEC 偏离登记 D23~D38 | **partially** | 内容写了，但写进了**非权威**的 V1.0 文件；计划 :956 指定的是 V1.3.1（#28） |
| 「E2E 进 CI」 | **not addressed（计划内刻意不做）** | 既有裁决「不新建流水线」=> D25 + TODO-152 => 延到 P10-F，非本批缺陷 |
| 4 条可复用解法回写 `docs/solutions/` | **not addressed** | 计划未显式列，但 CLAUDE.md 知识库条要求；本批无该目录改动（#29） |

**反向检查（计划没要求、diff 却引入的行为规则）**：

1. `StreamResponse.case_type` 由必填枚举改为可空 -> 对外契约放宽（`openapi.json` / 基线 / 前端 `api.d.ts` 三处都改了）-> 计划只要求「修好 500」，未要求改契约形状 -> 需按 #32 与 P-1 一起裁决。
2. `useFetch` 改用会话 token -> 前端取数口径变化（无 `DEV_BEARER` 兜底路径的显式失效处理）-> 计划未提 -> 见 #9。
3. 运行时往全局 `pipe_classes` 写 `source="COMPANY_STD"` 的占位行 -> **产品代码写共享主数据**这一行为规则，计划未列（计划的 `Modify/Create` 清单里没有 `pipe_chain_persist.py`）-> 见 #8。
4. 车道内部约定「开发库 pcs / pcs_test」被读进 E2E 车道 -> 引入了一条「E2E 依赖开发机 DB 状态」的规则 -> 见 #15。

---

## Coverage

- **depth**: `full`（floor = `size_band=large`，可执行非测试 974 行）
- **范围**: base `d73d1ac` -> head `f3b35e5`，branch `main`；49 个代码文件 + 文档；`unclassified_lines`: json 1978 , md 1869 , txt 282 , yml 15
- **reviewers（9，全部已收集）**: correctness , project-standards , testing , maintainability , learnings , security , api-contract , adversarial , reliability
  - reliability **晚到**（在 merge leaf 窗口之后落盘），已按其 7 条发现手工并入本报告（#1 #7 #9 #12 #19 #20 #21 + 一条并入 #6）
- **project-standards**: 跑了（criteria = 仓库根 `CLAUDE.md` => 治理全部改动文件）
- **跨模型 peer**: **未启动**  -  本机没有技能允许的 peer provider CLI（codex / grok / composer / cursor-agent 均不在 PATH，`CROSS_MODEL_PEERS` 未设）=> 对抗性视角**只由进程内 `adversarial` persona 承担** => 独立性弱于「跨模型 + 本地」双视角。**「假绿」这类问题恰恰最需要独立视角**，建议修完 P1 后再跑一次跨模型对抗审查
- **merge leaf（Stage 5）**: **未产出** `synthesized-findings.json`（收口时限内未落盘）=> 本报告由 report leaf 手工合并 9 份 persona JSON：按「同一处代码、同一失效模式、同一修法」去重，同族合并保留各 reviewer 名；按后果重定严重度（如 #6 从各家的 P2 提到 P1，理由是种子脚本的**文档化调用**就会写开发库）；每条补齐 `证据 / 为什么重要 / 建议修法 / 提出者`
- **校验器（Stage 5b）**: **未运行**  -  没有派发 `validator-batch` => **全部发现 `validation_status: unverified`**。本报告**没有假装校验过**：`confidence` 只是证据锚点，不是被独立复核过的结论。标 75 的条目请当线索复核后再动手
- **未选人士及理由**: performance（生产代码改动极小，性能面集中在测试种子，无实质资源影响）, data-migration（diff 内**无** `alembic/versions/*` 改动，无 backfill / 迁移脚本）, agent-native（diff 内无 agent 面向的能力或工具面）, julik-frontend-races（前端是 React/TS，非 Stimulus/Turbo）, swift-ios（无 Swift/iOS 文件）, previous-comments（standalone 评审，无 PR 评论）, deployment-verification（无高风险迁移产物，部署面只有 compose 种子服务串接）
- **本批自认的债 与 本次发现的关系**:
  - **bug-2165「根因未闭环」**（TODO-158）-> 本次给出了**根因**：不是「对象与被 flush 的行脱钩」，而是**那行赋值根本走不到**（`dup` 守卫早退，#1）=> TODO-158 可直接按 #1 + #2 收口
  - **TODO-161「计算端点运行时写配置表」** -> 本次把严重度抬到 P1/P2：越权写公司级标准目录（#8）+ 并发首算 500（#7）+ 种子侧违反响应契约（#17）
  - **TODO-159 / 160（前端 3 页 404 / 3 页 422）** -> 本次指出：扫描本该抓住它们，却把判据降级为只打印（#4）=> 把「白名单化断言」加上即可闭环
  - **「E2E 进 CI 延到 P10-F」**（D25 / TODO-152）-> 不变，且本次的发现进一步支持延后是**对的**：车道目前还不能自证（#6 #11 #12 #14）
  - **「E2E 不跑 lifespan」** -> 本次发现这不是设计选择而是**缺口**：注释声称已补启动 seed，实测 0 处调用（#19）
  - **bug-2168（仪表盘 404）/ bug-2169（假 token）** -> 这两个**修对了方向**，但 #16 与 #9 指出各自的收尾条件仍不严（守卫条件 / 失败态）
- **发现数**: 主发现 40 条（P1 10 , P2 22 , P3 8）+ 既有 1 条；9 份 persona 原始条目共 61 条，去重后 40 条

## Testing Gaps

1. **`case_type` 可空（bug-2167）零后端回归覆盖**  -  车道里没有任何用例 GET `/projects/{id}/streams`，快车道也没有可空性断言；把修复回退成必填，两条后端车道都不会红（#39）。
2. **审计哈希没有任何真断言**  -  E2E-009 被 `xfail` 中止，「活下来的 `report_files` 行带非空 `data_version`」这件事全仓没有断言；就算有人把 `data_version` 整段删掉，车道仍然绿（#2）。
3. **跨项目 404 在前端从未被执行**  -  前端那条被角色闸短路，后端 E2E-016 用的是无角色闸的 `GET /projects/{id}`；UI 通道对「跨项目 404」零覆盖（#3）。
4. **「逐字同形」只比 status + code**，且两次请求用不同 uuid -> 无权分支改 message 措辞仍绿（#38）。
5. **车道隔离只验 4 张表 + 只覆盖 `get_db`** -> 「不碰开发库 / 不写 public」这句话目前不可证（#11 #12）。
6. **并发首算无用例**  -  没有一条真 PG 用例证明两个并发的 `POST /pipe/calc-chain`（库里尚无 `CS-STD` 时）不会撞主键 500（#7）。
7. **种子行未做「出参可序列化」守卫**  -  `tests/scripts/test_seed_e2e_flows.py` 只按 ORM metadata 比必填列，不验证种子行能否通过对应 Response 模型（#17）。
8. **车道与种子「拒绝非测试库」无用例**  -  护栏缺失不会被发现（#6）。
9. **「车道里 403 会写审计行」无用例**  -  `errors.py` 的 `PYTEST_CURRENT_TEST` 早退把它掐掉了，权限矩阵的 403 行目前只验状态码与错误码（#13）。
10. **lifespan 播种的 6 张系数表与 7 条系统参数无用例** -> 车道与生产上下文的保真度缺口不可见（#19）。
11. **真实登录路径（签发 / 过期 / `token_version` 失效）从未被触发**  -  车道直接铸造 token，`role_headers` 造出的角色是**自称**的；签发端点坏了不会被发现（adversarial + security 提出）。
12. **批量端点的跨项目「同形」无用例**  -  CLAUDE.md 要求 `POST /streams/batch-submit` 返回 **207** + 失败项 `reason=SIM_STREAM_NOT_FOUND` 与「真不存在」逐字同形；E2E 车道没有对应用例（project-standards 提出）。
13. **同内容复用路径（`_finalize` 的 dup 分支）无用例**  -  被复用的行永远没写 `data_version`（api-contract 提出）。
14. **`flock` 只测了被覆盖过的临时路径**  -  默认锁路径与「两条车道真的互斥」这个行为本身没有被测到（reliability 提出）。

## Residual Risks

1. **跨模型视角缺席**（peer 未启动）=> 本次对抗性审查只有本地一个视角 => 「假绿」这类问题最需要独立视角 => 建议修完 P1-1..P1-10 后**再跑一次**跨模型对抗审查。
2. **校验器未运行** => 40 条发现里**有误报**，尤其是「恒等断言」类结论（依赖对端点闸门顺序的判断）与「死代码」类结论（依赖全仓 grep）。
3. **`reliability` 晚到** => merge leaf 未产出，本报告是**手工合并** 9 份 persona JSON 的结果 => 合并口径（严重度重定、同族归并）是人做的，可能仍有遗漏或误并。
4. **`data_version` 语义被文件 sha256 占死**（#27）=> 修 #1 时**别把它写成内容哈希** => 两件事必须一起裁。
5. **「SPEC 以哪份为准」这个矛盾在本批之前就存在**（D20 vs master-plan :216-220）=> 不是本批引入；但本批把 16 条偏离写进了**错的那份**（#28）=> 修的时候要一次裁清。
6. **隔离不变量没有被机制强制**  -  任何绕过 `Depends(get_db)` 自建 session 的代码路径仍会落到 public schema；当前 E2E 场景没走到这些路径，但「隔离」这句话没有机制背书（correctness 提出）。
7. **E2E 车道没有自动化作业会跑**（既有裁决「不新建 CI 流水线」）=> 车道的绿只在有人手动跑 `scripts/pytest_e2e.sh` 时成立 => 下一个维护者仍可能把「E2E 用例存在」读成「E2E 被验过」（learnings 提出，与 CLAUDE.md 记的「CI 不跑 => 绿灯证明不了它们跑过」同族）。
8. **真后端 UI 通道读的是 `pcs_pgtest` 的 public**，而 E2E 车道读的是隔离 schema => 两套数据互不相通 => UI 通道的绿灯**不证明** E2E 车道的场景在真后端也成立（testing 提出）。
9. **`report_tasks._finalize` 把 `data_version` 写成文件内容 sha256**，而端点把它作为 `record_hash_digest` 返回 => 字段名说的是「记录哈希」、装的是「产物哈希」；已有 ReportFile 行的 `data_version` 仍是 NULL（不迁数据）=> 生产上老行该端点仍返回空串（adversarial 提出，与 #27 同源）。
10. **`alembic upgrade head` 在共享库里执行 `CREATE EXTENSION IF NOT EXISTS btree_gist`**  -  这是**库级** DDL，发生在号称隔离的车道里；若扩展落在隔离 schema 内，teardown 的 `DROP SCHEMA ... CASCADE` 会连带删掉它并级联到依赖它的 public 对象（reliability 提出）。
11. **前端 mock 通道仍总是返回 `case_type: 'NORMAL'`**，与真库可返回 null 的契约不一致 => 只在真后端通道暴露的 null 分支在 mock 通道测不到（api-contract 提出）。
12. **`.gstack/` 已 gitignore** => 本批的 QA 报告不随仓库分发 => 关键结论必须同步进 `TODOS.md` 或提交信息，否则同事与后续会话看不到（CLAUDE.md 自己承认这个取舍）。

---

## Pre-existing Issues

| # | File | Issue | Reviewer |
|---|------|-------|----------|
| P-1 | `pcs-backend/docs/openapi-baseline.json` | 基线只是「与当前一致」的同步锁，不是「已发布契约」锚点 -> 本批的破坏性变更（`case_type` 必填 -> 可空）无版本、无弃用期、无迁移说明 | api-contract |

核实结论：基线漂移的主体确实是**上一批**的 AI 端点契约（`6292ca2` 改了 `openapi.json` 未改基线），本批把基线滚到与 `openapi.json` 逐字相同（三个文件 blob 哈希同为 `6663086`）。但 `gate_08` 的第 4 阶段只是 `diff -q baseline openapi.json` => 基线必须永远等于当前规格 => 任何破坏性变更都能无版本进契约。这条**不是本批引入的**，故不计进 verdict；本批的破坏性变更骑在它上面，所以修的时候要一起裁（与 #27 同批）。

---

## Learnings & Past Solutions

`learnings` persona 读到的既有解法与本批的关系（**不是发现**，是「已被遵守的已知模式」）：

- **[Known Pattern]** `docs/solutions/testing-issues/guard-test-fooled-by-lying-comment.md`  -  本批的 `test_pytest_pg_gate.py` 已经用 `_body()` 剥注释（正确样板），但同一个文件里的 flock 守卫没有（#36）=> 「同族教训已在本文件内，但只落了一半」。
- **[Known Pattern]** `docs/solutions/testing-issues/guard-patched-definition-site-consumer-imported-by-value.md`  -  本批的守卫测试用 `PCS_PGTEST_LANE_LOCK` 覆盖成 per-PID 临时文件（bug-2170 的绕法），思路正确；但它同时导致**默认锁路径从未被测过**（#21 的尾巴）。
- **[Known Pattern]** `docs/solutions/testing-issues/sqlite-staticpool-hides-uncommitted.md`  -  「把『测试通过』读成『守卫生效了』，实际是『守卫从未被触发』」：#3（越权断言恒等）、#5（矩阵断错对象）、#35（skip 闸门只测假 item）都属于这一族。
- **[Known Pattern]** `docs/solutions/testing-issues/engine-level-migration-tests-skipif-pg.md`  -  本批的车道在 alembic 上正确沿用了「隔离 schema + 子进程 alembic + 清理要响亮」的形状；但「清理要响亮」这条在 #20 处破功（`finally` 里的 DROP 异常会顶替真正的失败原因）。
- **[Known Pattern]** `docs/solutions/testing-issues/narrow-declaration-is-not-a-constraint.md`  -  本批 8 处产品修补里有 5 处是「响应 schema 与 DB 实际形状对齐」，方向正确；但放宽后的契约**没有对应的负向用例**（#39）。
- **[Known Pattern]** `docs/solutions/security-issues/midflight-config-rebind-defeeds-one-shot-guards.md`  -  权限矩阵场景依赖「提交时冻结判据」，本批**没有**任何「中途重绑」的用例 => 快照类回归仍不可见。
- **[Known Pattern]** `docs/solutions/database-issues/get-or-create-default-row-race-savepoint-reread.md`  -  本仓已把 get-or-create 的竞态处理写成 house pattern；本批**产品代码**（#7）破了自家规矩，而**同批的种子脚本**照着写了。

---

## 尚未解决的问题（需要人裁决）

1. **#8 / #18 / #21 / #27 / #29 / #31 / #32 这 7 条要先拍一次口径**（配置数据归迁移还是运行时兜底 / `sch_series_json` 的唯一形状 / 互斥锁的覆盖面 / `data_version` 的语义 / QA 与 solutions 的回写责任 / 种子常量的归属层 / `case_type` 的读写对称性）。本报告只给了「推荐默认值」，没有替人做这 7 次决定。
2. **跨模型 peer 没有第二次机会**：本机缺 peer provider CLI 是**环境**问题，不是这次运行的选择。要么接受「对抗性视角只有本地一份」，要么先把 peer CLI 装上再复跑一次。
3. **校验器未运行**：40 条发现**一条都没有被独立复核过**。若要把这份报告当作合并闸门，需要先补一次 Stage 5b 校验（尤其对 75 锚点的 22 条）。
4. **P-1 的契约版本策略**没有方案：要不要引入「已发布契约」锚点 + breaking 变更清单，是产品决策，本批只登记了问题。

---

*原始产物见 `docs/ce-code-review/20261117-013829-7e9fbabe/personas/`（9 份 JSON）、`scope-facts.json`、`shared/`（intent 与 review-context）、`full.diff`、`files.txt`、`stages.jsonl`。*

---

### Verdict

> **Verdict: Not ready**
>
> **Reasoning:**
> 1. 本批的核心交付物是**验证机制**（真 PG 隔离 schema 的 E2E 车道 + 三道 fail-closed 闸门 + 真后端 Playwright 通道）。验证机制的失败模式是**假绿**。本次找到 **6 处「守卫恒真 / 守卫从未执行」**（#3 #4 #5 #35 #36 #38），**把被守卫的机制整段删掉，这些用例照样绿**。
> 2. 本批自称修掉的 **bug-2165 其实没修好**（#1）：`report_tasks.py:118` 的赋值位于 `dup` 守卫的 `return` 之后，永不可达；而守着它的 E2E-009 又被**命令式** `pytest.xfail` 中止（#2）=> 车道对这条**恒绿** => 「修好了」这个结论**没有任何证据**。
> 3. 车道与种子都**没有目标库护栏**（#6）：`_lane_url()` 只验 URL 协议，种子脚本完全裸奔，而 `.env` 的 `DATABASE_URL` 指向开发库 `pcs` => **一个环境变量 + 一条文档化的命令**就能把开发库变成测试库。
> 4. 计划（explicit）的验收「E2E-001~018 **全部通过**」在实质上**未达成**：E2E-009 被 `xfail` 中止（#2），其「计算书可下载且非空」两段断言从未执行；真后端 5 条 UI 流里 3 条的断言恒真或断错对象（#3 #4 #5）。
>
> 这不是「这批不能合」，而是「**这批的绿灯还不能当证据**」。修完 #1..#10 之后，车道才具备「能证明」的资格。
>
> **Fix order:**
> #1 + #2（先修赋值，再把 xfail 换成硬断言，两件事一起做）->
> #6（库名白名单，fail-closed 守卫）->
> #3 + #4 + #5（守卫口径一次定完：观测点 / 白名单 / 断种子那张矩阵）->
> #7 + #8（占位管级：先裁口径，再落 savepoint）->
> #9 + #10（前端通道与复现条件）->
> 其余 P2/P3 按 Triage Groups 分批清。

**Actionable Findings 速览（按优先级）**

| # | Sev | File | Issue | Response |
|---|-----|------|-------|----------|
| 1 | P1 | `pcs-backend/app/workers/report_tasks.py:118` | `data_version` 赋值在 `dup` 早退之后 -> 永不可达 | mechanical fix |
| 2 | P1 | `pcs-backend/tests/e2e_flows/test_e2e_report.py:91` | 命令式 `xfail` 中止用例 -> 无回归保护 | mechanical fix |
| 6 | P1 | `pcs-backend/tests/e2e_flows/conftest.py:93` + `pcs-backend/scripts/seed_e2e_flows.py:763` | 车道与种子无目标库护栏 | mechanical fix (fail-closed) |
| 3 | P1 | `pcs-frontend/e2e/real_backend_flows.spec.ts:144` | 越权 UI 断言恒等（角色闸短路） | mechanical fix（换观测点） |
| 5 | P1 | `pcs-frontend/e2e/real_backend_flows.spec.ts:41` | 断的是内置矩阵不是种子那张 | mechanical fix（改常量 + 收窄） |
| 7 | P1 | `pcs-backend/app/services/pipe/pipe_chain_persist.py:112` | 占位管级先查后插无 savepoint -> 500 | mechanical fix（house pattern） |
| 9 | P1 | `pcs-frontend/src/pages/routeWrappers.tsx:92` | `useFetch` 吞错 + 绕过 axios 401 | mechanical fix（走 axios） |
| 4 | P1 | `pcs-frontend/e2e/real_backend_route_sweep.spec.ts:56` | 「渲染出来了」恒真 + 判据降级为打印 | **需要一次口径裁决**（已知缺口白名单） |
| 8 | P1 | `pcs-backend/app/services/pipe/pipe_chain_persist.py:95` | 运行时写全局配置主表 | **需要人拍板**（配置数据归迁移还是运行时） |
| 10 | P1 | `pcs-frontend/package.json:20` | 真后端 UI 车道无法从仓库复现 | **需要人拍板**（复现条件写进仓库） |

完整 40 条见上文「Actionable Findings」与「完整发现表」两节。
