# P6-9-PICKUP-4 — Debt Cleanup Final

## Context

P6-9-PICKUP-3 closed：5 task APPROVE（8d9e43b nielsen DB drop, 8b505cb schema drift guard, f8260aa/72162e9/6acc553/8926328/0cec39a ruff 18 fixes in 5 batches, 6970400 docs/sample untracked, 93a1417 batch closeout + 21 LOW/INFO registry）。

残留债务：
- 9 pre-existing pytest failures（pcs_test DB schema drift in untouched files）
- 5 ruff errors pre-existing in `scripts/dev/calibrate_behr_coefficients.py`
- 21 LOW/INFO 项 detail processing
- 工艺室 2026-11-15 交付后 OPEN-P6-6A-10 / OPEN-P6-9-PICKUP-2-1/2 重新对账预留位

## 锚定版本

PCS backend main @ `93a141780122ac1cf5c93b5ebf40c6773c3188dc`

baseline: pytest 3507 passed / vitest 548 passed

## 任务清单（4 tasks / ~2 天）

### T1. 9 pre-existing pytest failures 修复

- **当前**：`tests/services/{psychro,cv,test_schema_drift}.py` 3 文件引用的 `psychro_id` 与 pcs_test DB 实际 `psychro_calc_id` 列名不一致（schema drift 历史差异）
- **目标**：
  1. grep `psychro_id` 所有引用
  2. 修复实际运行量（按最小 diff 路径：rename ORM field `id → calc_id` 或 DB column rename）
  4. 验证测试通过
- **commit**：1（ps_test + schema drift 守护一并）
- **验收**：9 个 pre-existing pytest failures PASS
- **依赖**：pcs_test DB 实际状态需检查
- **工时**：0.5 天

### T2. 5 ruff errors pre-existing 修复（calibrate_behr_coefficients.py）

- **当前**：`pcs-backend/scripts/dev/calibrate_behr_coefficients.py` 5 ruff errors pre-existing
- **目标**：`ruff check scripts/dev/` 全 0 errors
- **验收**：`ruff check .` 全局 0 errors
- **commit**：1
- **依赖**：不动 core algorithm
- **工时**：0.2 天

### T3. 21 LOW/INFO 项 detail processing

- **当前**：`docs/ce-code-review-p5-p6-summary.md` 50 findings 完整登记；21 LOW/INFO 累积登记但 detail 未分类
- **目标**：21 项按 4 维分类（工艺计算正确性 / 代码卫生 / 文档 / 重构）→ 推 P7-0 或推 docs/tasks
- **commit**：1（仅 docs/tasks.md 更新）
- **依赖**：无
- **工时**：0.5 天

### T4. 工艺室 2026-11-15 交付后重新对账预留位

- **当前**：OPEN-P6-6A-10 / OPEN-P6-9-PICKUP-2-1/2 待工艺室交付
- **目标**：预留跟踪位（不写代码）
- **验收**：批末 docs/tasks.md 含交付前置条件 + 状态字段
- **commit**：1（docs only）
- **依赖**：工艺室 2026-11-15 交付（不可控）
- **工时**：0.1 天

## 验收矩阵

- [ ] T1 pytest 0 regression（9 pre-existing 修复）
- [ ] T2 ruff check 全 0 errors
- [ ] T3 docs/tasks.md 21 项 detail 分类
- [ ] T4 docs/tasks.md 工艺室 2026-11-15 跟踪位
- [ ] pytest 全量 3507+ passed
- [ ] vitest 全量 548 passed
- [ ] ruff 全 0 errors
- [ ] G-08 phase 1-4 drift=0
- [ ] push 至 origin/main

## 风险 + 缓解

| 风险 | 等级 | 缓解 |
|---|---|---|
| pcs_test DB 状态未知 | 中 | T1 实施前 `pcs_test env` 状态探测 + 备份 |
| 工艺室 2026-11-15 交付延期 | P1 | T4 仅 docs 预留位，零阻塞 |

## 后续

P6-9-PICKUP-4 完成后：
- 启动 P7-0（OPEN-P6-6A-10 / OPEN-P6-9-PICKUP-2-1/2 工艺室交付接入）
- 或部署批触发 OPEN-P6-4-2（Kb 厂商真实数据）
- 或暂时 idle 等工艺室 11-15 交付

## OPEN 状态变化（预期）

| OPEN | 变化 |
|---|---|
| OPEN-P6-6A-10 | 关联（待工艺室 PDF）|
| OPEN-P6-9-PICKUP-2-1 | 关联（待工艺室 k_strip 校准）|
| OPEN-P6-9-PICKUP-2-2 | 关联（待工艺室 HYSYS 对账）|
| OPEN-P6-9-PICKUP-4 | 新增（T4 跟踪） |
| OPEN-P6-4-2 | 不变（部署后批）|

## 未解决问题

1. OPEN-P6-4-2 厂商真实数据（部署后批）
2. OPEN-P6-6A-9.5 N2 公式校准（已闭环 T1-P6-9-PICKUP-2）
3. 9 pre-existing pytest failures 根因分析（schema drift vs 业务逻辑）