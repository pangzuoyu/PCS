# P6-9-PICKUP-2 — 4 CRITICAL + 2 HIGH 修复批

## Context

架构组（2026-10-31）接受 P5+P6 Review 的 "NOT READY TO MERGE" 结论；批准启动 P6-9-PICKUP-2 批。

## 锚定版本

PCS backend main @ `cf51fdf`（ce-code-review summary doc + 之前所有 commits）

baseline: pytest 3501 passed / vitest 548 passed

## 任务清单（8 tasks / ~2.5 天）

### T1. CRITICAL F1 — `_calc_lean_glycol_concentration_wt_pct` else-branch bug patch

- **当前**：line 1339 `return _GPSA_FIG_20_4_DATA_POINTS[0].lean_glycol_concentration_wt_pct, warnings` 总是返回 98.8（插值结果被丢弃）
- **目标**：
  1. 修复 line 1339 为 `return lean_glycol, warnings`
  2. 添加 3 regression tests：
     - `test_lean_glycol_interp_at_390F_0scf` → assert ~99.05
     - `test_lean_glycol_interp_at_395F_1p5scf` → assert ~99.5
     - `test_lean_glycol_interp_at_385F_0p5scf` → assert 边界值
  3. 删除 `test_glycol_dehydration_pv_consistency`（任何只断言"输出 = 内部变量"的自洽测试）
  4. 对账基准：GPSA Fig 20-4 原文（工艺室 2026-10-15 已交付）逐点对照
- **commit**：1
- **OPEN 影响**：OPEN-P6-6A-11（关联 dead code 删除）
- **工时**：0.3 天

### T2. CRITICAL F2 — `_calc_stripping_gas_rate_scf_gal_teg` 公式反转 patch

- **当前**：公式反向 `sgr = k_strip * (p_total_mmhg / p_sat_te_mmhg) * x_frac / (1.0 - x_frac)` 残差 4e12%
- **目标**：
  1. 修复为 GPSA §20.4 Eq.20-5 形式：`sgr = k_strip * (p_sat_te_mmhg / p_total_mmhg) * (1.0 - x_frac) / x_frac`
  2. 删除 `test_glycol_dehydration_stripping_gas.py:97` 公式自洽测试
  3. 恢复 XLS PR-018 E32=0.4220 对账测试（real-value tolerance check）
  4. 更新 fixture `expected.sgr_scf_gal_teg` 实际值
  5. 工艺室提交 F2 复盘报告（OPEN-P6-9-PICKUP-2-1 跟踪）
- **commit**：1
- **验收**：XLS E32 对账残差 < 5%
- **工时**：0.5 天

### T3. CRITICAL F3 — C-24 reconciliation fixture + service + test

- **当前**：3/3 测试 FAIL（fixture inputs.x vs P1/P2 内部不一致）
- **目标**：
  1. 工艺室重发 verified fixture（x 与 P1/P2/Pv 自洽）
  2. CvEngine.calculate 显式接受 `x: float` 参数（不内部推断 x_p = ΔP/P1）
  3. 添加 `_validate_flash_consistency(x, T, P1, P2, Pv)` 校验在 CvEngine 入口强制调用
  4. 工艺室 deliverable: 3 verified fixture + 1 OPEN-P6-4-4 partial 复盘
- **commit**：1
- **OPEN 影响**：OPEN-P6-4-4 已关闭 → **回退 partial closure**（F3 修复后重新关闭）
- **验收**：3/3 回归全部 PASS
- **工时**：0.5 天

### T4. CRITICAL t_wall_mm → t_wall_m 单位歧义修复

- **当前**：字段名 mm 暗示毫米，公式按米处理（100× 误差风险）
- **目标**：
  1. 重命名 `t_wall_mm` → `t_wall_m`（全 7 处 call sites：line 321/336/358/377/406 + 2 处）
  2. 添加单位测试：
     - `test_t_wall_units_meters`：输入 t=0.020 m → Y_p=4.27e-4
     - `test_t_wall_units_from_mm_conversion`：输入 t_mm=20 自动转换
  3. Pydantic schema 字段明确单位
  4. 工艺室提供 HYSYS 对账算例（2026-11-15 前）验证 Y_p 匹配
- **commit**：1
- **OPEN 影响**：OPEN-P6-6A-10（关联 AS 1210 path 修复）
- **OPEN 影响**：新增 OPEN-P6-9-PICKUP-2-2 t_wall_mm 复盘
- **验收**：Y_p 残差 < 5% vs 工件基准
- **工时**：0.4 天

### T5. HIGH F1 — `_calculate_nielsen_depression` dead code 删除

- **当前**：line 258-296 函数全代码库零 caller
- **目标**：
  1. grep 全代码库 + test 确认无外部调用
  2. 删除 `_calculate_nielsen_depression`（line 258-296）
  3. 评估 `_NIELSEN_1988_PARAMS` 与 `compound_nielsen_1988_params` CONFIG 表：
     - 若 P6-9-PICKUP-3 计划接入 reader → 只删 dead code，保留数据
     - 若无 reader 计划 → 同步删
- **commit**：1
- **验收**：grep 确认零 caller
- **工时**：0.2 天

### T6. HIGH F2 — `_USE_XLS_CD_Y_CR` feature flag 接入

- **当前**：flag 默认 False，无 caller
- **目标**：
  1. `calc_drain_orifice` / `calc_drain_orifice_size` 入口加 `fluid: str | None = None` 参数
  2. 当 `flag=True` 且 `fluid` 非 None → 自动调 `_resolve_cd_y_cr(fluid)` 覆盖 Cd/Y_cr
  3. 保留 back-compat：`fluid=None` 时走 `inp.discharge_coefficient` / `inp.expansion_factor`
  4. 添加测试：
     - `test_drain_orifice_xls_cd_y_cr_lookup`（flag=True, fluid='WATER'）
     - `test_drain_orifice_back_compat_default`（fluid=None）
- **commit**：1
- **OPEN 影响**：OPEN-P6-6A-4（关联 drain_orifice C-19 重启）
- **工时**：0.4 天

### T7. MEDIUM F3 — untracked test file commit

- **当前**：`test_glycol_dehydration_fixtures_integration.py` untracked `??`
- **目标**：
  1. `git status --porcelain` 列出所有 untracked files
  2. `git add` test 文件
  3. commit as part of T7 文档化
- **commit**：1（与 T8 docs 合并或单独 commit）
- **验收**：所有 P6-8/P6-9 测试文件纳入版本控制
- **工时**：0.1 天

### T8. 批末收口（验证 + docs + push）

- **当前**：8 task 已完成
- **目标**：
  1. pytest psychro 100% pass（含新 regression tests）
  2. pytest cv 100% pass（含 F3 reconciliation 3/3）
  3. ruff 0 new errors
  4. G-08 phase 1-4 drift=0
  5. `.wolf/STATUS.md` 闭环登记（P6-9-PICKUP-2 批落地 + OPEN 队列更新）
  6. `.wolf/cerebrum.md` 更新（F2 + t_wall 复盘记录）
  7. `README.md` 同步
  8. push 至 origin/main
- **commit**：1（docs + wolf/STATUS）
- **验收**：8 项验收标准全部通过
- **工时**：0.3 天

---

## 工时表

| Task | 工时 |
|---|---|
| T1 | 0.3 |
| T2 | 0.5 |
| T3 | 0.5 |
| T4 | 0.4 |
| T5 | 0.2 |
| T6 | 0.4 |
| T7 | 0.1 |
| T8 | 0.3 |
| **总计** | **~2.7 天** |

---

## 验收矩阵（15 项）

| # | 项 | 命令 | 期望 |
|---|---|---|---|
| 1 | ruff | `uv run ruff check .` | 0 new errors |
| 2 | pytest psychro | `uv run pytest tests/services/psychro/ -q` | 100% pass（含 3 new regression） |
| 3 | pytest cv | `uv run pytest tests/services/cv/ -q` | 100% pass（含 F3 reconciliation 3/3） |
| 4 | pytest total | `uv run pytest -q` | ≥ 3501 passed + 0 break |
| 5 | vitest | `npx vitest run` | ≥ 548 passed |
| 6 | G-08 | `gate_08_openapi_contract.sh` | drift=0 |
| T1 | lean-glycol patch + 3 tests | `pytest tests/services/psychro/test_glycol_dehydration_lean_glycol.py -v` | 3 新测试 PASS |
| T2 | SGR 修复 + XLS E32 对账 | `pytest ... test_glycol_dehydration_stripping_gas.py` | fl_calculated (now GPSA) ≈ XLS E32 0.4220 |
| T3 | C-24 reconciliation | `pytest ... test_c24_model_reconciliation.py -v` | 3/3 PASS |
| T4 | t_wall_m 单位 | `pytest tests/services/psv/` | 新单位测试 PASS |
| T5 | nielsen dead code 删除 | `grep _calculate_nielsen_depression` | 0 result |
| T6 | _USE_XLS_CD_Y_CR 接入 | `pytest test_drain_orifice*` | 2 新测试 PASS |
| T7 | untracked commit | `git status --porcelain` | 0 untracked files |
| T8 | docs + STATUS + push | push origin main | 远端 HEAD = 本地 HEAD |
| 14 | OPEN-P6-4-4 回退 partial closure | `wolf/STATUS.md` | 已登记 |
| 15 | 4 CRITICAL 全部修复 | code review summary 重新审查 | NOT READY → READY |

---

## 风险 + 缓解

| 风险 | 等级 | 缓解 |
|---|---|---|
| **R-1** T3 C-24 fixture 工艺室重发延迟 | 高 | 工艺室 2026-11-15 交付；若延迟，T1/T2/T4/T5/T6 仍可独立完成 |
| **R-2** T2 SGR 修复公式需工艺室确认 | 高 | GPSA §20.4 Eq.20-5 是标准形式，工艺室已签字 T7 commit（commit `5dbd09e`）；修复按已签字方向 |
| **R-3** T4 t_wall_m 单位测试依赖 HYSYS 对账 | 中 | 工程参考值已知（Y_p=4.27e-4 @ t=20mm, T=400°F）；HYSYS 对账后补 |
| **R-4** 工艺室 F2 复盘报告（OPEN-P6-9-PICKUP-2-1） | 中 | 修复完成 + 复盘报告 = 闭环 |
| **R-5** 6 ruff 错误 P5-7（p5-3-fe/p5-med 等） | 中 | 不在本批 scope；累积到 P6-9-PICKUP-3 |

---

## OPEN 队列变化

| OPEN | 修复前 | 修复后 |
|---|---|---|
| OPEN-P6-4-4 | 已关闭 | **⚠️ partial closure**（T3 修复后重新关闭） |
| OPEN-P6-6A-9.5 | partial | pending（F3 不涉及 Behr coefficients） |
| OPEN-P6-6A-10 | 待 AS 1210 PDF | partial closure（T4 t_wall_m 修复关联） |
| OPEN-P6-6A-11 | 已关闭 | 已关闭（T5 dead code 清理关联） |
| **新增 OPEN-P6-9-PICKUP-2-1** | — | F2 SGR 公式复盘报告 |
| **新增 OPEN-P6-9-PICKUP-2-2** | — | t_wall_mm 单位复盘报告 |

---

## 后续

P6-9-PICKUP-2 完成后 → 启动 P6-9-PICKUP-3：
- 12 MEDIUM 项工艺修复
- 21 LOW/INFO 项评估
- OPEN-P6-6A-10 AS 1210 PDF 2026-11-15 升级 confidence B → A
- 工程团队接管厂商数据采集（OPEN-P6-4-2 上线后批）

---

## 未解决问题

1. **OPEN-P6-4-2**（Kb 厂商真实数据，上线后批）- 不阻塞 P6-9-PICKUP-2
2. **OPEN-P6-6A-10**（AS 1210-2010 PDF 采购到位 2026-11-15）- 阻塞 OPEN-P6-6A-10 完全关闭
3. **OPEN-P6-6A-9.5 工艺室系数重发** - 待 2026-11-15 工艺室交付
4. **OPEN-P6-4-4 fixture 重发** - 待 T3 工艺室交付
5. **T3 工艺室 fixture 延迟风险** - T1/T2/T4/T5/T6 仍可独立完成