---
description: session handoff, regenerate with /handoff when a quest finishes
budget_tokens: 1200
---
# STATUS — PCS

> Read this FIRST when starting a session. Last updated: 2026-11-02（第 23 轮：**P9B-3 计划吸收委员会复审**）。
> 保持 <2k tokens。历史细节查 `git log` / `docs/` / `TODOS.md` / `.wolf/memory.md`。

---

## ✅ Done（第 23 轮：P9B-3 计划）

**计划**：`docs/PCS-PLAN-P9B-3-系统参数与SIM物流前端.md`（1740 行）· commit **`ac09ad8`**
委员会复审判定 **CLEARED TO START**，本轮把**全部**意见落地进计划（此前 Pass 1+2 未提交，本次补完 Pass 3 一次提交）：
**3 P1**（T4 的 7 项默认键 seed 含 `app/main.py` 启动钩子 + `test_seed_is_idempotent` · T0 的
「收集到 0 个」测试改用**假 docker shim**（否则测的是「PG 没起」）· T2 改 **✅/⏳/❌ 状态标记**
—— SPEC 不该知道批次概念）· **5 P2**（空 composition 区分 `None`/`{}` · TODO-104 · 「只能改不能增」
写进 docstring · TODO-103 拆两 commit · T9「两库 + 一条车道」表）· **5 条用户裁决**
（1a source 列 → **新增 T2.5** · 1b PRO/II 归 `SIM_IMPORT` · 2 T7 顺序（估算失败不阻塞）·
3 SPEC 状态标记 · 4 T4 默认键 7 项）。

**新增 Task T2.5**：`streams.source` 列（VARCHAR(20) NOT NULL DEFAULT 'MANUAL' + CHECK
`ck_streams_source_valid` + 复合索引 `ix_streams_project_source`）+ 迁移 **`p9_015`** +
`StreamSource` 4 值枚举（MANUAL / SIM_IMPORT / EXCEL / LAB）+ 后端 `?source=` 筛选。

**三处实测新事实**（裁决前提未覆盖，已写进计划）：**`streams.source_type` 已存在**
（VARCHAR(30) NOT NULL + CHECK，**13 值** = 3 人工/导入 + 10 个 `*_CALCULATED` 设备计算出口流；
`pcs_test` 202 行实测）⇒ 与新列**语义正交**（产出方式 vs 录入通道）但**取值重叠 3 处**
⇒ 用「同一写入点成对赋值 + 一致性断言」防漂移（#9）· **Excel 导入把 `source_type` 也写成
`SIM_IMPORT`** ⇒ 新列写 `EXCEL`，两列不同是**有意的**（#10）· **10 个 `*_CALCULATED`
出口流在 4 值里无对应** ⇒ 本批规则：**继承上游的 `source`**（#11）。
另修一处**计划自洽性**：T6 断言四项筛选都带 query 参数，但后端只支持 `case_type`
⇒ T2.5 一并补 `phase` / `sign_status`（否则前端 query 被静默忽略 ⇒ 断言必红）；`streams.phase`
无索引 ⇒ #12。

**环境修复（不在仓库内）**：claude-mem 的 observer 凭据被拒 ⇒ `/login` 后读写实测正常；
`code-review-graph` MCP 因 `uvx` 每次要下 wheel 而 **`files.pythonhosted.org` 在本机被重置**
⇒ 卡到 30s MCP 超时、**进程压根没起来**（旁证：`~/.cache/uv/` 930 个 `.tmp*` 孤儿目录）
⇒ 改 `/home/pangzy/code_project/.mcp.json` 直指
`/home/pangzy/miniconda3/bin/code-review-graph`（备份 `/tmp/mcp.json.bak`）⇒ 握手 6.5s。

**上一轮（第 22 轮 P9B-2F）**：follow-up 评审 17 条 actionable 全落地（`77e3293..9f08a0d`）·
后端 5405 passed / 前端 989 tests · 三库 `p9_014` + `alembic check` exit 0 · QA 报告
`.gstack/qa-reports/qa-report-pcs-frontend-2026-11-02-p9b2f.md` · 详见 buglog 2111-2120。

---

## 🚀 Next quest

1. **P9B-3 开工 T0**（本地 PG 车道 · TODO-099）：计划里的 `## Task T0`，12 步。
   顺序 **T0 → T1 → T2 → T2.5 → T3 → T4 → T5 → T6 → T7 → T8 → T9**
   （T2.5 在 T2 之后、T3 之前）。**TDD 红灯先行**：先写
   `pcs-backend/tests/scripts/test_pytest_pg_gate.py`，再跑
   `cd pcs-backend && uv run pytest tests/scripts/test_pytest_pg_gate.py -v` ⇒ 预期 FAIL
   （`scripts/pytest_pg.sh` 尚不存在）。⚠️ 本会话这条命令被权限分类器拦过一次，
   下次直接跑（别另跑 collect-only 探输出格式）。
2. **下一轮 ce-code-review**：scope **必须**含 TODO-100 点名的三处未深审部分
   （`test_deliverable_issue.py` + deliverables/record_edits API 改动 + 其余 diff）。
3. 开放 TODO：**091-105**（104/105 本轮由 T2.5/T8 登记）；57 手写类型长期债；ADR-0050「先不做」。
4. **未跟踪的 6 个遗留文件**（`docs/superpowers/plans/2026-09-30-*.md` ×5 +
   `spec/PCS-SPEC-P10 V1.3.1….md`）—— 非本会话产出，处置由用户定。

---

## Context

- main。**不要建 worktree**（历史事故）。`.wolf/*` 由 hook 自动维护，别手工 revert。
- 两库均在 **`p9_014`**（head），`alembic check` exit 0。⇒ **`p9_015` 尚不存在**，作者是 T2.5。
- ⚠️ **验多库必须每库独立进程**（alembic settings 是 pydantic 缓存实例）+ **直查库**
  （`alembic_version` + 列存在性），不能只信命令输出。`alembic check` 退出码 **255** 不是 1。
- ⚠️ **本仓无自动化 PG 测试通道**（CI 的 api-drift job 一条后端 pytest 都不跑）⇒
  `tests/alembic/` 的引擎级测试**必须本地手动跑**；文档里不得写「CI 承担」。
- **全量 pytest 前先 `docker compose up -d redis`**（ws/broadcaster 系列失败 = 环境未起）；
  **别信 `pytest | tail` 的退出码**；`test_todos.py` 的 500ms 墙钟预算测试满负载下会抖（隔离即过）。
- 契约：批末滚 baseline（`cp openapi.json openapi-baseline.json`）后跑 G-08 `--check-baseline`。
- 提交约定：conventional commits，**无 attribution 行**；长消息写文件后 `git commit -F`。
- ⚠️ API 测试 `client` fixture mock 掉项目授权；StaticPool 共连接 ⇒ 真并发测试不可表达
  （行锁只能**方言级**钉）。
- ⚠️ 前端 e2e：`browse goto` 清 zustand ⇒ 路由可达性检查走 **SPA 菜单点击**。

---

## 教训（已进 cerebrum）

- 「CI 在验」之前必须**读那个 workflow 的 steps**（本仓已两次假委托）。
- `finally` 里的 assert 会**顶掉**原始异常 ⇒ 清理判定放 try/finally **之后**。
- 方言级断言必须**抽生产代码出来**，否则测试只能照抄 ⇒ 删了锁照样绿。
- 评审的「全绿」结论：**先变异实测再转述**（推断 ≠ 实测）。
- 从审计流水反推「当前轮次的执行者」⇒ 取**最后**一条（构造多轮测试 + 时间戳显式设值）。
- **裁决的前提可能不成立** ⇒ 落地前先核事实（本轮就发现 `source_type` 已存在）。
