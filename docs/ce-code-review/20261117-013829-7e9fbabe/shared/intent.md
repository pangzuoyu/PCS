# Intent（本批 P10-B：全流程 E2E）

给 PCS 后端建一条**真 PG 隔离 schema**的端到端车道，把 SPEC 的 18 个场景 +
5 条工作流路径 + 权限矩阵在**真 app + 真库**上跑起来；并把「真后端通道」的
5 条前端 UI 流跑起来（此前该通道从未真正跑过 ⇒ 抓到 5 个缺陷）。

关键约束（审查时按这些当规格）：
- 车道用**隔离 schema**（`CREATE SCHEMA` → `alembic upgrade head` → `DROP CASCADE`），
  默认车道必须**跳过** e2e 用例（否则会打到开发库 `pcs`）。
- 两条车道（PG / E2E）**共用一个库** ⇒ 必须**互斥**（flock）。
- 车道要能抓住「单测（SQLite）绿、真库炸」那一类缺陷 ⇒ 驱动必须与生产一致。
- 权限语义：**跨项目 ⇒ 404（与「不存在」同形）**；**角色不够 ⇒ 403**。
- 本批改过的产品代码只有 8 处（其余是测试/文档）：
  `app/schemas/stream.py`（case_type 可空）· `app/api/v1/sim_imports_query.py`（list→dict 归一）·
  `app/services/pipe/pipe_chain_persist.py`（占位管级）· `app/workers/report_tasks.py`（data_version）·
  `app/api/v1/report.py`（docstring）· `scripts/seed_e2e_flows.py`（version 类型）·
  `docker-compose.yml`（seed 串两个脚本）· 前端 `DashboardPage.tsx` + `routeWrappers.tsx`。

计划（规格依据）：`docs/superpowers/plans/2026-11-13-p10-batch-b-fullflow-e2e.md`
