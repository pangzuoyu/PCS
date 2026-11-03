---
description: session handoff, regenerate with /handoff when a quest finishes
budget_tokens: 1200
---
# STATUS — PCS

> Read this FIRST when starting a session. Last updated: 2026-11-03（第 25 轮：**P9B-3b 整批落地** T1→T6，8 commit `252f25a..9558d72`）。
> 保持 <2k tokens。历史细节查 `git log` / `docs/` / `TODOS.md` / `.wolf/memory.md`。

---

## ✅ Done（第 25 轮：P9B-3b 批量「提交校对」）

计划 `docs/superpowers/plans/2026-11-03-p9b-3b-batch-submit.md`（3600+ 行，含 GSTACK REVIEW REPORT），
**superpowers:executing-plans**（inline）+ gstack `plan-eng-review` 审查 ⇒ 委员会 D1~D12 全部写进计划。
ledger：`.superpowers/sdd/2026-11-03-p9b-3b-batch-submit/progress.md`（含全部 `Ruling:`）。

- **T1 地基**（`252f25a`）：组成口径单一来源 `composition_mole_fraction_total`（router 侧副本删除）+
  `get_setting_value` + `AuditAction.STREAM_BATCH_SUBMITTED` + **加锁读唯一入口**
  `build_stream_for_update_stmt` / `select_stream_for_update`（`populate_existing=True`）⇒
  `StreamService.transition` 也改走它（唯一入口）。
- **T2 批次 service**（`5778117`）：`app/services/stream_batch_service.py` —— 去重 / 幂等
  （已 IN_APPROVAL 记成功 + `note=already_in_approval`）/ 部分成功 / `dry_run` / 上限 /
  **逐条独立 commit** / 批次审计（`resource_type=STREAM_BATCH`，`resource_id == batch_id`）。
  ⚠️ **实测推翻原假设**：savepoint 内调 **session 级** `rollback()` 会关掉整个外层事务 ⇒ 逐条 commit 是唯一可行解。
- **T3 端点**（`593020b`）：`POST /streams/batch-submit`，**207 Multi-Status**（路径两段 ⇒ 不与
  `/streams/{id}/submit` 抢路由）+ ACL（DESIGNER/PROCESS_CONTROLLER/SYSTEM_ADMIN）+ 422 上限 +
  **具名**契约 schema（裸载荷未涨）。
- **T4 行锁**（`7e53be0`）：方言级 `FOR UPDATE` 断言 + `populate_existing` 断言 + **接线断言**
  （spy 批次模块自己的引用 ⇒ 变异实测抓到过**假闸门**）+ PG 车道真并发（一胜一拒 / 审计恰好 1 条）。
- **T5 前端**（`728df02`）：`rowSelection` + 工具栏「批量提交校对」+ 结果弹窗（成功 N · 失败 M +
  每条原因 + 批次 warning + **失败清单关闭提示**）+ dev mock（`buildBatchSubmitResponse` 导出 ⇒
  棘轮清单同步 + ajv 校验 207 形状）。
- **T5b e2e**（`450a177`）：Playwright 断言**报文**（不是只断言 UI）⇒ 变异实测：只发第一个 id ⇒ 变红 ✓。
- **T6 收口**（`9558d72`）：SPEC §7.7.1 → **V2.10** + §12.4 修订行；债项 **TODO-116/118/119/120/121**；
  OpenAPI baseline 滚动（G-08 `--check-baseline` ✅）。

**批末实测**：后端 **5474 passed / 77 skipped RC=0**（基线 5439 + 35）· PG 车道 5 passed RC=0 ·
前端 **1017 passed**（111 files）· typecheck + lint clean · 裸载荷 **71**（未涨）· G-08 4/4 ✅ ·
e2e 2 passed · 浏览器 QA 全过（0 error / 0×404）⇒ **CRITICAL 0 · HIGH 0**。
报告：`.gstack/qa-reports/qa-report-pcs-frontend-2026-11-03-p9b3b.md`（gitignored，只落本地）。

---

## 🚀 Next quest

1. **整支分支的 fresh-context 评审**（本轮末尾已派 opus，**尚未收结论**）⇒ Critical/Important 进修复批。
2. **下一 quest 待用户定**：P9B-4（批量操作交互收口 · 含 TODO-116 的「只重试失败项」）或 P9B-3c。
   起点线索：`docs/PCS-PLAN-P9B-3-系统参数与SIM物流前端.md` 的「P9B-3b 移交」节已全部落地 ⇒ 该节可标「已完成」。
3. **下一轮 ce-code-review**：scope **必须**含 TODO-100 点名的三处未深审部分
   （`test_deliverable_issue.py` + deliverables/record_edits API 改动 + 其余 diff）。
4. 开放 TODO：**091-115 + 116/118/119/120/121**（099/101/102/103 已关闭）；57 手写类型长期债；ADR-0050「先不做」。
   ⚠️ **TODO-118（🔴）是本批刻意接受的越权缺口**（批次端点与六个写端点同口径，只做角色校验）
   ⇒ 批次把越权成本从「100 次请求」降到「1 次扫荡」；TODO-113/114 是**读面**的同类缺口。
5. **未跟踪的 6 个遗留文件**（`docs/superpowers/plans/2026-09-30-*.md` ×5 +
   `spec/PCS-SPEC-P10 V1.3.1….md`）—— 非本会话产出，处置由用户定。

---

## Context

- main。**不要建 worktree**（历史事故）。`.wolf/*` 由 hook 自动维护，别手工 revert。
- ⚠️ 本批**未改 `alembic/versions/*`** ⇒ 无迁移漂移风险 ⇒ 两库仍在 `p9_015`，本批没碰过。
- ⚠️ **全量 pytest 前先 `docker compose up -d redis`**；**别信 `pytest | tail` 的退出码**；
  `test_notification_list_budget.py` 的 500ms 墙钟预算测试**满负载下会抖**（隔离即过 ⇒ 负载型 flake）。
- ⚠️ **本仓 CI 一条后端 pytest 都不跑**（单人开发裁决）⇒ PG 车道是**本地**闸门，须人工跑。
- 契约：批中只跑 G-08 前三段；**批末**滚 baseline（`cp openapi.json openapi-baseline.json`）后才跑 `--check-baseline`。
- 提交约定：conventional commits，**无 attribution 行**；长消息写文件后 `git commit -F`。
- ⚠️ 前端 e2e / 浏览器 QA：`page.goto` / `browse goto` / `reload` 会清 zustand（内存态）
  ⇒ 路由可达性走 **SPA 菜单点击**。
- ⚠️ gstack `browse click @eN` 对 antd 表格复选框会解析成表头「Select all」（所有行复选框
  `aria-label` 相同）⇒ 勾选改用 `js` 点 DOM + Playwright 交叉验证 ⇒ **别把它当应用 bug**。
- ⚠️ 契约缺口（裸 dict）：`CreateStreamRequest.payload`、state-points body、properties/state-points/
  lineage graph 响应 ⇒ 前端手写本地类型 ⇒ **字段名无编译期约束**（TODO-110/111）。

---

## 教训（已进 cerebrum）

- 「裁决的前提可能不成立」⇒ 落地前先核事实（T3：组成合计校验**存在**）。
- 计划的字段形状**要过契约闸门**再落地（裸载荷数会因「照抄计划」而涨）。
- 计划自相矛盾时按「后一步能走到」那条读（T7：写入后跳走 ⇒ 后两步走不到）。
- 测试辅助函数若假设「每次都从头开始」，第二次调用必假红（T7 `gotoStep`）。
- **savepoint 不能隔离「service 内部自己调 `db.rollback()`」** ⇒ 逐条 commit 是唯一可行解。
- **断言要 spy「被测模块自己的引用」** ⇒ 否则会被别的调用路径满足 ⇒ 假闸门（变异实测抓到的）。
- **工具的 ref 解析 ≠ 应用行为** ⇒ 拿 Playwright 真实事件交叉验证再下结论。
