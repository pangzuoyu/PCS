# P6-9-PICKUP-6 — Docs / 代码卫生 14 项批

## Context

P6-9-PICKUP-4 已闭环（4 commits + wolf updates）。next 推荐 P6-9-PICKUP-6（HYG 8 + DOC 6 = 14 项）。

来源：`docs/tasks.md` 已分类的 21 项 LOW/INFO 中 HYG + DOC 子集（14 项）。

## 锚定版本

PCS backend main @ `b15512a`

baseline: pytest 3515 passed / ruff 0 errors

## 任务清单（5 tasks / ~1.0 天）

### T1. HYG-P6-008/P6-6B-001 ruff whitespace class sweep（~0.3 天）

- **范围**：
  - `HYG-P6-6B-1`：test fixture docstring
  - `HYG-P6-6B-2`：测试 helper unused import
- **目标**：ruff 检查零 warning + 单 commit
- **commit**：1
- **验收**：3 ruff warning 减至 0
- **工时**：0.3 天

### T2. HYG-P6-007 ruff multi-line docstring reflow（~0.2 天）

- **范围**：PYLINT-convention 类的 E501 行长超限
- **目标**：全 0 warnings + ruff E501 = 0
- **commit**：1
- **验收**：pcs-backend/ ruff errors 0
- **工时**：0.2 天

### T3. DOC-P6-008/P6-6B/P6-7 docs/tasks 增量（P6-9-PICKUP-4 已记录补充）（~0.2 天）

- **范围**：CHANGELOG entries + README 更新 + docs/P6-9-PICKUP-4.md 创建
- **目标**：3 docs commit
- **验收**：CHANGELOG 反映 P6-9-PICKUP-4 + P6-9-PICKUP-3 + P6-9-PICKUP-2 + P6-8
- **工时**：0.2 天

### T4. HYG-P6-008/P6-008/P5-008 unused variable cleanup（~0.1 天）

- **范围**：grep 未使用变量 / 函数 / import
- **目标**：ruff F401/F841 全 0
- **commit**：1
- **验收**：pcs-backend/ ruff errors 0
- **工时**：0.1 天

### T5. 批末收口 + push（~0.2 天）

- **范围**：G-08 phase 1-4 drift=0 验证 + ruff 全 0 + pytest 回归
- **目标**：docs/tasks.md 关闭 14 项 + push origin/main
- **commit**：1（docs + tests）
- **验收**：3 OPEN 跟踪位不变；21 LOW/INFO 中 14 项状态更新为"已修复"
- **工时**：0.2 天

## 验收矩阵

- [ ] T1 ruff 3 warnings → 0
- [ ] T2 ruff E501 全 0
- [ ] T3 CHANGELOG/README/P6-9-PICKUP-4.md 完整
- [ ] T4 F401/F841 全 0
- [ ] T5 pytest 全量 3515+ passed / ruff 0 / G-08 drift=0 / push origin/main
- [ ] docs/tasks.md 中 14 项状态更新为「已修复」

## 风险 + 缓解

| 风险 | 等级 | 缓解 |
|---|---|---|
| ruff 修复引入新语法 error | 中 | T1/T2 后 `ruff check` 验证，单 commit 隔离 |
| CHANGELOG 重复 | 低 | 引用 commit SHA 而非完整内容 |

## 后续

P6-9-PICKUP-6 完成后 → P6-9-PICKUP-5（待工艺室 2026-11-15 交付触发）

## OPEN 状态变化

| OPEN | 变化 |
|---|---|
| （无 OPEN 项关闭，docs-only 批） | docs/tasks 14 项状态更新 |

## 未解决问题

1. OPEN-P6-4-2（Kb 厂商真实数据，部署后批）
2. OPEN-P6-6A-10（AS 1210 PDF 2026-11-15 到位）
3. OPEN-P6-9-PICKUP-2-1/2（工艺室校准报告）