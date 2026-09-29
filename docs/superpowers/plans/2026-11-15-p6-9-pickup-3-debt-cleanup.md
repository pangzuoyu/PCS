# P6-9-PICKUP-3 — Debt cleanup (DB orphan + schema drift + ruff 18 + 21 LOW/INFO)

## Context

P6-9-PICKUP-2 批闭环（7 commits `cf51fdf..173b42d`），但发现累积债需清理：
- 5 处 DB orphan（`compound_nielsen_1988_params` CONFIG 表 + 关联 artifacts）
- G-07 schema drift（`psychro_id` vs `psychro_calc_id`）
- ruff 18 pre-existing errors（多文件累积）
- 21 LOW/INFO 项（来自 ce-code-review 5 batch）

## 锚定版本

PCS backend main @ `173b42d`（P6-9-PICKUP-2 闭环）

baseline: pytest 3430+ passed / 3513 brief spirit

## 任务清单（5 tasks / ~1.5 天）

### T1. DB orphan 清理 - `compound_nielsen_1988_params` CONFIG 表删除

- **当前**：T5 service 代码层 dead code 已清（commit `b599420`），但 DB 层 6 artifacts 残留：model + alembic 迁移 + downgrade + seed + cache reader + schema test
- **目标**：
  1. Alembic 降级迁移 `pcs-backend/alembic/versions/p5_6_xxx_drop_nielsen_1988_params.py` 删除 CONFIG 表
  2. 删除 model `CompoundNielsen1988Params`
  3. 删除 cache reader `get_nielsen_1988_params` from `_compound_config_cache.py`
  4. 删除 seed 脚本
  5. 删除对应 schema test
  6. 完整 alembic upgrade head + downgrade 验证
- **commit**：1
- **验收**：alembic upgrade head PASS / downgrade PASS
- **工时**：0.5 天

### T2. G-07 schema drift 修复

- **当前**：`tests/services/psychro/test_*_persist*.py` 引用 `psychro_id`，但 pcs_test DB 实际列名是 `psychro_calc_id`（迁移回填历史差异）
- **目标**：
  1. grep 所有 `psychro_id` 引用
  2. 修复 ORM 引用或 DB column rename（视 cost）
  3. 添加 schema drift 守护测试（CI 检测）
- **commit**：1
- **验收**：3 个 pre-existing psychro persist tests PASS
- **工时**：0.3 天

### T3. Ruff 18 pre-existing 修复

- **当前**：`ruff check .` 18 errors 跨 `test_worley_c19.py` / `test_worley_c16.py` / `test_worley_c18.py` / `test_glycol_dehydration_api.py` / `test_restriction_api.py` / `app/services/psychro/glycol_dehydration_service.py` 等
- **目标**：
  1. 分批 `ruff check --fix` 修复
  2. 按文件分组 commit
- **commit**：3-5
- **验收**：`ruff check .` 0 errors
- **工时**：0.4 天

### T4. docs/superpowers/plans/ + sample/ untracked 长期清理

- **当前**：13 plans + sample/Process caculation from Worley/ 长期 untracked
- **目标**：
  1. 决定 plans/ 是否应纳入 git（推荐：纳入 `.superpowers/plans/`）
  2. 决定 sample/ 保留方案
- **commit**：1
- **验收**：untracked files 减少
- **工时**：0.1 天

### T5. 21 LOW/INFO 项累积登记

- **当前**：ce-code-review 5 batch 报告累积 21 项 LOW/INFO
- **目标**：在 .wolf/STATUS.md 累积登记
- **commit**：1（docs）
- **验收**：21 项已登记
- **工时**：0.1 天

## 验收矩阵

- [ ] T1 alembic upgrade + downgrade PASS
- [ ] T2 3 个 pre-existing psychro persist tests PASS
- [ ] T3 `ruff check .` 0 errors
- [ ] T4 untracked files 减少
- [ ] T5 21 项 LOW/INFO 登记
- [ ] pytest 全量 0 break（除 pre-existing env）
- [ ] G-08 phase 1-4 drift=0
- [ ] push 至 origin/main

## 风险 + 缓解

| 风险 | 等级 | 缓解 |
|---|---|---|
| R-1 alembic 降级失败 | 中 | 备份 DB + 显式 transaction |
| R-2 schema drift 改坏其他测试 | 中 | 单独 commit + 测试覆盖 |
| R-3 ruff --fix 改坏代码 | 低 | 仅 whitespace / line length，避危险 fix |

## 后续

P6-9-PICKUP-3 完成后 → P6-9-PICKUP-4 处理 21 LOW/INFO 项细节 + 工艺室 2026-11-15 校准交付
- k_strip calibration（OPEN-P6-9-PICKUP-2-1）
- fixture re-issue（OPEN-P6-9-PICKUP-2-2 / OPEN-P6-4-4）