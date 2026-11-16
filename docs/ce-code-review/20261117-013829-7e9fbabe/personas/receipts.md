# 各 persona 的原始回执（orchestrator 收到的一行式摘要）

> 完整 findings 在同目录 `*.json`（persona 自写）⇒ 这里只留回执，便于人工速览。

## correctness（7）
- P1 `pcs-backend/app/workers/report_tasks.py:118` · `row.data_version = digest` 永不可达（`_finalize` 的 dup 分支先 return）⇒ 审计哈希端点仍返空串 · bug-2165 未修
- P2 `pcs-backend/app/services/pipe/pipe_chain_persist.py:105` · 占位管级裸 SELECT-then-INSERT ⇒ 并发首次调用撞主键 ⇒ 500
- P2 `pcs-backend/app/services/pipe/pipe_chain_persist.py:134` · 占位行以 `source="COMPANY_STD"` 落进共享参考表
- P2 `pcs-backend/scripts/seed_e2e_flows.py:519` · 种子管级三处违反 `PipeClassResponse` ⇒ `GET /pipe-classes/E2E-SEED-CS` 必 500
- P2 `pcs-backend/tests/e2e_flows/test_e2e_schema_parity.py:73` · 两库闸只比彼此、不与代码 head 比 ⇒ 两库一起落后也绿
- P2 `pcs-frontend/src/pages/DashboardPage.tsx:40` · bug-2168 的守卫应是「拿到真 project id」而非「选了工作区」⇒ 选中后仍用占位 id ⇒ 404 照旧
- P2 `pcs-frontend/e2e/real_backend_flows.spec.ts:41` · 断的 `DEFAULT_RECORD_3_LEVEL` 是内置全局模板 · 不是种子的 `E2E_FLOWS_RECORD_3_LEVEL`

## project-standards（4）
- P2 `pcs-frontend/e2e/real_backend_route_sweep.spec.ts:63` · 违反 CLAUDE.md《Per-Batch QA Gate》步骤 2/4：扫描跑出 6 个不达标页面却把判据降级为只打印
- P2 `spec/P10 AI预留与测试部署开发规格说明书.md:666` · 违反「与 SPEC 冲突时以 OpenAPI 为准并登记 SPEC 修订」：D23~D38 写进非权威的 V1.0 文件（其 §3.2.2 只有 14 场景）
- P2 `.wolf/STATUS.md:88` · 违反「新增解法后回写一份」：STATUS 自称教训「已进 docs/solutions」但本批无 docs/solutions 改动
- P2 `.wolf/STATUS.md:51` · 违反《Per-Batch QA Gate》：本批改了前端却「本轮还没跑」批末 QA

## security（5）
- P2 `pcs-backend/app/services/pipe/pipe_chain_persist.py:260` · 计算端点运行时把占位管级插进**全局** `pipe_classes`（`source="COMPANY_STD"`）⇒ 越权写公司级标准目录
- P2 `pcs-backend/scripts/seed_e2e_flows.py:751` · 新种子脚本无目标库白名单 ⇒ 按文档那条命令会灌进**开发库 `pcs`**
- P2 `pcs-backend/tests/e2e_flows/conftest.py:93` · 车道只靠 `PCS_E2E_LANE` 一个护栏 · `_lane_url()` 只验协议
- P2 `pcs-backend/tests/e2e_flows/test_lane_smoke.py:240` · 「不写 public」守卫只快照 4 张表（且只有 count(*)）
- P3 `pcs-backend/scripts/pytest_pg.sh:57` · 车道锁用可预测 `/tmp/...lock` 且 `exec 9>` 跟随符号链接截断

## adversarial（10）
- P1 `pcs-frontend/e2e/real_backend_flows.spec.ts:144` · 越权 UI 断言恒等（bob=CHECKER 在角色闸被挡 · 项目守卫从未执行 ⇒ 删掉守卫照样绿）
- P1 `pcs-frontend/e2e/real_backend_route_sweep.spec.ts:56` · 「路由渲染出来了」断言恒真（`#root` 是 index.html 的静态 div）
- P1 `pcs-frontend/e2e/real_backend_flows.spec.ts:41` · 签署矩阵 UI 流断的是内置矩阵不是种子那张
- P1 `pcs-backend/tests/e2e_flows/test_e2e_report.py:91` · 命令式 `pytest.xfail` 中止用例 ⇒ 修复回归时车道仍全绿
- P2 `pcs-backend/tests/e2e_flows/conftest.py:96` · 车道只校验 URL 协议 ⇒ 打到开发库 `pcs` 也照跑
- P2 `pcs-backend/tests/e2e_flows/conftest.py:289` · 隔离只覆盖 `get_db` · `ws.py:77`/`errors.py:51` 的全局 session factory 仍指 public
- P2 `pcs-backend/app/core/errors.py:45` · `PYTEST_CURRENT_TEST` 早退 ⇒ 车道里每次 403 都不写审计行
- P2 `pcs-backend/app/services/pipe/pipe_chain_persist.py:95` · 占位管级 get-or-create 无 savepoint ⇒ 并发首算撞唯一约束 500
- P2 `pcs-backend/tests/e2e_flows/test_lane_smoke.py:132` · 「不写 public」守卫只数 4 张表 · 只在种子后取基线
- P2 `pcs-backend/scripts/pytest_pg.sh:83` · 闸门③只要求「≥1 passed」⇒ 29/30 场景被 skip 也算绿

## testing（10）
- P1 `tests/e2e_flows/test_e2e_report.py:91` · 命令式 `pytest.xfail()` 把 data_version 修复记成 xfailed ⇒ 车道恒绿
- P1 `pcs-frontend/package.json:20` · 真后端 5 条 UI 流依赖 4 个仓库里没写出的环境变量 ⇒ 仓库无法复现
- P2 `tests/e2e_flows/test_e2e_schema_parity.py:65` · 车道直连开发库 `pcs`/`pcs_test` 读 revision ⇒ 车道绑在开发机状态上
- P2 `tests/e2e_flows/test_lane_smoke.py:240` · 「不写 public」守卫只快照 4 张表
- P2 `tests/e2e_flows/conftest.py:96` · `_lane_url()` 只查协议不查库名
- P3 `tests/e2e_flows/conftest.py:84` · 跳过闸门只随 `tests/e2e_flows/` 注册 ⇒ 挪出该目录后守卫照样绿
- P3 `app/schemas/stream.py:318` · bug-2167（case_type 可空）只有 Playwright 覆盖 · 车道零回归测试
- P3 `pcs-frontend/e2e/real_backend_route_sweep.spec.ts:70` · 唯一实质断言是「#root 还在」
- P3 `tests/scripts/test_pytest_e2e_gate.py:95` · flock 守卫是未剥注释的子串匹配
- P3 `tests/scripts/test_pytest_pg_gate.py:111` · 「唯一入口」守卫只数一个字面量

## maintainability（12）
- P1 `pcs-backend/app/services/pipe/pipe_chain_persist.py:95` · 计算端点运行时往配置主表写占位行 · 绕过 `PipeClassService.create`
- P2 `pcs-backend/scripts/seed_e2e_flows.py:243` · `_get_or_create` 逐字复制 `seed_e2e_data.py:108` ⇒ 两份真相源
- P2 `pcs-backend/scripts/seed_e2e_flows.py:101` · 种子管级 `E2E-SEED-CS` 与运行时占位 `CS-STD` 是两套互斥定义 · `sch_series_json` 四份矛盾真相
- P2 `pcs-backend/tests/e2e_flows/helpers.py:206` · `CHAIN_ROLES` 是 `FLOW_MATRIX_STEPS` 的未钉住副本
- P2 `pcs-backend/tests/e2e_flows/test_e2e_record_workflow.py:48` · `_bump_record` 逐字重写 `helpers.py:353`
- P2 `pcs-frontend/src/pages/routeWrappers.tsx:87` · `useFetch` 裸 fetch 手拼 token ⇒ 绕过 axios 拦截器 ⇒ 第二套 HTTP 通道
- P2 `pcs-frontend/e2e/real_backend_flows.spec.ts:41` · 手抄的种子常量与种子实际值对不上

## learnings（6 findings + 6 learnings）
- P2 `pcs-frontend/e2e/real_backend_flows.spec.ts:136` · UI 越权断言被角色闸短路
- P3 `pcs-backend/tests/e2e_flows/test_e2e_permission_matrix.py:147` · 「逐字同形」只比 status+code
- P3 `pcs-backend/scripts/seed_e2e_flows.py:516` · 种子管级违反 `PipeClassResponse` 契约
- P3 `pcs-backend/tests/e2e_flows/test_lane_smoke.py:194` · 默认车道 skip 闸门只有「假 item 动作断言」
- P3 `pcs-backend/tests/scripts/test_pytest_e2e_gate.py:95` · flock 守卫子串匹配
- P3 `pcs-frontend/e2e/real_backend_route_sweep.spec.ts:70` · 路由扫描把 console error/4xx 降级为打印
- learnings（6，可复用）：真后端第二 Playwright project + `@real-backend` tag · 守卫须与真车道用不同锁 ·
  隔离 schema 车道四校准（asyncpg 同款 / server_settings search_path / 子进程 alembic / 锁放共享脚本）·
  public 前后快照 · 权限四元组 + 分支可达钉子 · 目录级配置落笔先 ls 住客

## api-contract（7）
- P2 `pcs-backend/app/workers/report_tasks.py:118` · 把文件 sha256 写进 `data_version` ⇒ `record_hash_digest` 与 `data_version` 塌成同值
- P2 `pcs-backend/app/api/v1/report.py:494` · `_expected_digest` 只读 data_version ⇒ 老行仍返空串
- P2 `pcs-backend/app/api/v1/sim_imports_query.py:325` · preview-streams 无 response_model ⇒ 统一后的形状未进契约
- P2 `pcs-backend/app/services/pipe/pipe_chain_persist.py:134` · 占位管级以 `source=COMPANY_STD` 进公司级列表
- P2 `pcs-backend/docs/openapi-baseline.json:1` · 已核实基线漂移主体是上一批 AI 端点契约；但破坏性变更（必填→可空）无版本/弃用说明
- P2 `spec/P10 AI预留与测试部署开发规格说明书.md:666` · D23~D38 写进 V1.0 文件 · 权威 SPEC 未修订
- P3 `pcs-backend/app/schemas/stream.py:318` · 响应可空但请求侧仍必填 ⇒ 读写不对称

## reliability
⚠️ 未收集（该 persona 在合并前未落盘）
