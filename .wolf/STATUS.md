---
description: session handoff, regenerate with /handoff when a quest finishes
budget_tokens: 1200
---
# STATUS — PCS

> Read this FIRST when starting a session. Last updated: 2026-10-26（P9A-DLV-007 + TODO-057 落地）。
> 保持 <2k tokens。历史细节查 `git log` / `docs/` / `TODOS.md` / `.wolf/memory.md`。

---

## ✅ Done

### 第 12 轮：**P9A-DLV-007 + TODO-057**（签署矩阵的取得 + 变更单的观测写入点）

计划 `docs/PCS-PLAN-P9A-DLV-007-签署矩阵与变更单观测.md`（含执行结果段）。commit
`56e91ae` → `2bb7e81`。

产出：**后端**
- `SignatureMatrixService`（新）—— `parse_steps` 是 `steps_json` 的**唯一**解析口
  （排序 / 坏项跳过+日志 / 缺省补齐 / 全非法 ⇒ 422 `SIGNATURE_MATRIX_INVALID`）；
  `ensure_change_notice_matrix` **惰性建**内置模板 `CHANGE_NOTICE_3_LEVEL`（3 级
  校核/审核/审定）+ 项目绑定 ⇒ `signature_matrices` 不再恒 0 行。
- `DeliverableService._matrix_steps` 改为调它（消除第二份解析 ⇒ bug-2050）。
- `ChangeNoticeService.create_change_notice` **落地**（不再 `NotImplementedError`）：
  绑矩阵 + `deliverables`(matrix_id 非空) + `change_notice_details` + 审计 +
  **观测写入点 2a**（CHANGE_NOTICE / PENDING，`workflow_id` = 变更单的 deliverable_id）。
- `approve_change_notice` 写**观测写入点 2b**（APPROVED ⇒ COMPLETED + completed_at）；
  审批失败不写观测。观测写与业务变更**同一事务**。

**测试**：3 个「断言 NotImplementedError」的假 DB 用例**改写成真库用例**（内存 SQLite）
+ 新增 `tests/services/test_change_notice_observation.py`（4 例，含同事务回滚断言）。
后端全量 **5188 passed / 77 skipped**（基线 5168）；`alembic check`（pcs）exit 0；
`gate_08_openapi_contract.sh --check-baseline` exit 0（baseline 顺带滚了 P9B-1 的
遗留漂移 `current_version_id`）。

**登记**：SPEC **V2.2**（§7.2.1「三工作流写入」部分 2/3 ⇒ **通过 3/3** + DLV-007
实现偏离注记）· `TODOS.md` TODO-057 **闭环** + 新增 **TODO-068~072** ·
`.wolf/buglog.json` bug-145 收尾 + 新增 bug-2050/2051/2052 ·
cerebrum 新增「假 DB 看不见 DB 层约束」「同一份配置只能有一份解析实现」。

### 上一轮：**P9B-1**（结果记录页 + 编辑锁前端）—— 已完成

见 `docs/PCS-PLAN-P9B-1-…` 与 git log；deferred minor 记在 TODO-067。

---

## 🚀 Next quest

1. **P9B-2**：签署流程前端（操作栏 / 批注 / 状态时间线）+ ADMIN 前端（用户管理 /
   审计日志）+ **两个后端前置**（**TODO-065** 聚合端点 `GET /deliverables/{id}/progress`、
   **TODO-066** 按项目守卫的编辑审计读端点）。
   ⚠️ 计划 `docs/PCS-PLAN-P9B-2-签署流程与ADMIN前端.md` **尚未过 `/plan-eng-review`**。
2. **P9B-3**：系统参数前端 + 物流手动创建向导 + 校对 UI。
3. **P9A-DLV-007 的遗留**（本批新登记）：
   TODO-068 变更申请**无 HTTP 入口** · TODO-069「一条记录一张变更单」待 SPEC 确认
   · TODO-070 矩阵**无管理面** · TODO-071 bindings 缺唯一约束（bug-2052，改迁移
   ⇒ 全新库验）· TODO-072 `steps_json` 校验器。
4. **ADR-0050**：用户 2026-10-20 裁决「先不做」⇒ 再开工按 P1~P6。
5. **P9A-1 遗留**（未变）：access token 不带 `tv`；AD 同步需运维服务账号。

---

## Context

- main，工作区干净（`.wolf/*` 由钩子持续更新）。**不要建 worktree**（历史事故）。
- 两库均在 `p9_007`（head）。本批**未改迁移** ⇒ 无漂移风险。
  改迁移的纪律见 CLAUDE.md（退出码 **255**；先 `current` vs `heads`；
  `pcs_test` 的跑法：URL 从 `.env` 派生，**不要把口令写在命令行**）。
- ⚠️ **CI 现在是活的**（`.github/workflows/check-api-drift.yml`）⇒ 改了迁移必须
  在**全新库**上验（bug-2041 就是 dev 库看不见、只有 CI 全新库炸）。
- **Redis**：跨进程/锁的测试需要真 Redis —— `docker compose up -d redis`
  （本会话已起；没起时那批测试**红**而不是 skip）。
- 契约产物由 G-08 钩子在 commit **之后**重生成，而 `git add` 在钩子之前
  ⇒ 偶尔漏提交，commit 后要 `git add -A && git commit --amend --no-edit` 补。
- 提交约定：conventional commits，**无 attribution 行**（本仓全局禁用）。
  ⚠️ commit message 里用 `!` `（）` 会被 shell 吃掉 —— 长消息写文件后
  `git commit -F <file>`。
- 无 CI/CD 的历史裁决已**部分过期**（CI 存在且会跑）；但**不要新增流水线**。

---

## 教训（本会话新增 2 条，已进 cerebrum）

- **假 DB 看不见 DB 层约束**：`_FakeSession` 断言内存对象 ⇒ NOT NULL / 唯一约束
  / 外键**一条都观察不到** ⇒ bug-145 的 5 个用例测出来是绿的。⇒ 验「DB 层拒绝」
  必须用**真库**（内存 SQLite，注意它**不强制外键**）。
- **同一份配置只能有一份解析实现**：`steps_json` 曾有两份解析（签署路径 + 变更单
  路径）⇒ 坏数据处理不同 ⇒ 「谁该签这一步」在不同入口不一致。⇒ 解析收敛到
  唯一入口；配置数据要**显式排序** + **坏数据不静默**。
