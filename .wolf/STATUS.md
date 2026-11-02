---
description: session handoff, regenerate with /handoff when a quest finishes
budget_tokens: 1200
---
# STATUS — PCS

> Read this FIRST when starting a session. Last updated: 2026-11-03（第 24 轮：**P9B-3 整批落地** T0→T9）。
> 保持 <2k tokens。历史细节查 `git log` / `docs/` / `TODOS.md` / `.wolf/memory.md`。

---

## ✅ Done（第 24 轮：P9B-3 整批 · `8b6d9ef..100ab91` 16 commit）

计划 `docs/PCS-PLAN-P9B-3-系统参数与SIM物流前端.md`，用 **superpowers:executing-plans**（inline）
执行，ledger 在 `.superpowers/sdd/PCS-PLAN-P9B-3-系统参数与SIM物流前端/progress.md`（含全部 `Ruling:`）。

- **T0 本地 PG 车道**（`b127495` · TODO-099 关闭）：`scripts/pytest_pg.sh` = **唯一入口**，
  fail-closed 三闸（PG 未起 / 收集到 0 个 / 无 `N passed` ⇒ exit 1）+ `postgres-pgtest` 服务
  （⚠️ 卷挂 `/var/lib/postgresql`，PG-18 拒绝 `/var/lib/postgresql/data`）+ `pg` marker。
- **T1 三处修正**（`51657ac`/`909bc3a`/`0a0efd5`+`b948044`/`72f20be` · TODO-101/102/103 关闭）：
  StateBadge 交付物 4 态 / 409 收窄到 `uq_projects_project_no` / compact ORM **生成器**。
- **T2 SPEC V2.6**（`3ba9587`）+ **T2.5 `streams.source`**（`baa916d` · 迁移 `p9_015`）：4 值录入通道
  （MANUAL/SIM_IMPORT/EXCEL/LAB）+ `?source=` 筛选；**与既有 `source_type`（13 值）正交** ⇒ 前后端只消费 `source`。
- **T3 组成合计门禁**（`d9937bc`）：送审前置 100±0.5%（`SIM_STREAM_COMPOSITION_OUT_OF_RANGE`）。
  ⚠️ 计划说该校验「根本不存在」—— **实测存在**（`SIM-V09` 创建时 0.1%）⇒ 真正缺口是**送审这一关没有门禁**。
- **T4 系统参数后端**（`a5d5229`）：批量**原子** PUT + `SYSTEM_SETTINGS_UPDATED` 审计 + 幂等 seed 7 键
  （启动钩子）。⚠️ 计划的 `settings: dict[str, Any]` 会让裸载荷闸门 71→72 ⇒ 套 `RootModel`（JSON 形状不变）。
- **T5 系统参数页**（`b5b6616`）：`/admin/system-settings`，**一次保存 = 一个 PUT**，JSON 文本 + `JSON.parse`。
- **T6 物流列表页**（`a6cc93c`）：工具栏（导入/新建/导出，**无**批量提交校对）+ 四项筛选（重新请求后端）
  + 单条「校对」+ 「变更」。⚠️ 未改 `listByProject` 的返回类型（会打破 4 个计算页）⇒ 另开 `streamApi.list`（TODO-109）。
- **T7 手动创建向导**（`30f4dfb`）：`/sim/streams/new`，7 步，校验红项 ⇒ 写入禁用，**估算失败不阻塞**提交校对。
- **T8 详情 7 Tab**（`a220cec`）：基本信息/组成/物性/状态点/设备连接/血缘/**校核记录**（前端按
  `detail_json.transition` 过滤）。⚠️ 校核记录端点**限 SYSTEM_ADMIN** ⇒ 非管理员见「无权查看」（TODO-112）。
- **T9 收口**（`614f696`）：QA 报告 `.gstack/qa-reports/qa-report-pcs-frontend-2026-11-03-p9b3.md`
  （Health 97/100；唯一 HIGH 是 antd `rowKey` index 弃用 ⇒ 批内已修并复验）；契约 baseline 已滚（G-08 4/4）。
- **整批评审 + 修复批**（`100ab91`）：fresh context · opus ⇒ **2 Critical + 4 Important + 8 Minor** ⇒
  Critical/Important **全修**：**C-1** 加锁读被 identity map 旧副本遮蔽（**T3 引入的回归** ⇒ 并发提交
  校对两次都成功）⇒ 加锁 select 加 `populate_existing=True`；**C-2** 详情页未知 `sign_status` 整页崩
  （计划 Review Focus #2 的另一半没做）⇒ 共享 `StateBadgeBoundary`；I-1 写路径 ACL 无测试 / I-2 dev
  mock 的批量 PUT 不原子 / I-3 PG 车道第三条闸无测试 / I-4 后端 `?phase=` `?sign_status=` 无测试
  ⇒ 全部补上（**每条都做了变异实测：能红**）。8 条 Minor 记进 ledger 延后。

**批末实测**：后端 5439 passed / PG 车道 4 passed / 前端 1008 passed（111 files）/ typecheck+lint clean /
裸载荷 71（未涨）/ `pcs`+`pcs_test` 均 `p9_015` + `alembic check` exit 0（独立进程 + 直查库）/ 浏览器 0 error 0×404。

---

## 🚀 Next quest

1. **P9B-3b（批量「提交校对」）** —— 委员会裁决 5：**单列计划**，本批**不做**。
   契约决策（D1~D6 / 207 Multi-Status / 新动作 `STREAM_BATCH_SUBMITTED` / 上限取
   `system_settings.stream.batch_submit_limit` / 幂等去重 / `dry_run`）与 12 条边界用例
   已留档在 P9B-3 计划文档的「P9B-3b 移交」节 ⇒ **开工前先把那段抄成新计划**。
   ⚠️ 端点命名待裁决：`POST /streams/batch/submit`（`batch` 会与 `{stream_id}` 抢路由 ⇒ 建议 `/streams/batch-submit`）。
   ⚠️ 最关键的测试：**并发提交同一条 stream ⇒ 一胜一拒**（行锁）⇒ 方言级 SQL 断言 + 接线断言。
2. **下一轮 ce-code-review**：scope **必须**含 TODO-100 点名的三处未深审部分
   （`test_deliverable_issue.py` + deliverables/record_edits API 改动 + 其余 diff）。
3. 开放 TODO：**091-115**（本批新登记 104~115；099/101/102/103 已关闭）；57 手写类型长期债；ADR-0050「先不做」。
   ⚠️ **TODO-113/114** 是**既有**的越权缺口（`GET /streams/{id}` 无项目守卫 · `lineage/graph`
   对 `record_type='streams'` 跳过校验）—— 本批详情页与血缘 Tab 依赖这两条端点。
4. **未跟踪的 6 个遗留文件**（`docs/superpowers/plans/2026-09-30-*.md` ×5 +
   `spec/PCS-SPEC-P10 V1.3.1….md`）—— 非本会话产出，处置由用户定。

---

## Context

- main。**不要建 worktree**（历史事故）。`.wolf/*` 由 hook 自动维护，别手工 revert。
- 两库均在 **`p9_015`**（head），`alembic check` exit 0（每库**独立进程** + **直查库**）。
  ⚠️ `alembic check` 退出码 **255** 不是 1；「Target database is not up to date」= **检查失败**。
- ⚠️ **验多库必须每库独立进程**（alembic `settings` 是 pydantic 缓存实例，第二次改 env 不生效）。
- ⚠️ **全量 pytest 前先 `docker compose up -d redis`**；**别信 `pytest | tail` 的退出码**；
  `test_notification_list_budget.py` 的 500ms 墙钟预算测试**满负载下会抖**（隔离即过 ⇒ 负载型 flake）。
- ⚠️ **本仓 CI 一条后端 pytest 都不跑**（单人开发裁决）⇒ PG 车道是**本地**闸门，须人工跑。
- 契约：批末滚 baseline（`cp openapi.json openapi-baseline.json`）后跑 G-08 `--check-baseline`。
- 提交约定：conventional commits，**无 attribution 行**；长消息写文件后 `git commit -F`。
- ⚠️ 前端 e2e：`browse goto`/`reload` 会清 zustand ⇒ 路由可达性走 **SPA 菜单点击**。
- ⚠️ 契约缺口（裸 dict）：`CreateStreamRequest.payload`、state-points body、properties/state-points/
  lineage graph 响应 ⇒ 前端手写本地类型 ⇒ **字段名无编译期约束**（TODO-110/111）。

---

## 教训（已进 cerebrum）

- 「裁决的前提可能不成立」⇒ 落地前先核事实（T3：组成合计校验**存在**）。
- 计划的字段形状**要过契约闸门**再落地（裸载荷数会因「照抄计划」而涨）。
- 计划自相矛盾时按「后一步能走到」那条读（T7：写入后跳走 ⇒ 后两步走不到）。
- 测试辅助函数若假设「每次都从头开始」，第二次调用必假红（T7 `gotoStep`）。
