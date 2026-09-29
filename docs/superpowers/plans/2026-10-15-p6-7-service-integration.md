# P6-7 服务集成批 — 工艺室 4 批交付物集成

## Context

工艺室 2026-09-28 / 2026-10-15 / 2026-10-31 三批交付物落库完成：

- 第一批（2026-09-28）：8 文件 fixtures（OPEN-P6-4-3 / 4-4 / 6A-9.1~9.4 / 6A-10 / 6A-11 + ADR-0045 Rev A 引用）
- 第二批（2026-10-15）：7 文件 fixture + ADR-0045 Rev B（OPEN-P6-4-3 / 4-4 / 6A-9.3 / 9.4 / 9.5 / 11 工艺侧闭环）
- 第二批补充（2026-10-31）：`behr_coefficients.json` (general + high-acid) + `brine_correction_review.md`

P6-7 = 服务代码集成工艺室交付物 + 测试 0 break + ADR-0045 Rev B 实施 + 工艺 OPEN 代码侧全部闭环。

## 锚定版本

PCS backend main @ `89bbf14`（P6-6B 数据源替换批 13 commits active + 工艺室 3 批交付物落库）

baseline: pytest 3269 passed / vitest 548 passed

---

## 任务清单（10 tasks / 5.0 天）

### T1. `psychro.py` HydrateGasComposition schema v2（OPEN-P6-6A-11 代码侧）

- **当前**：`pcs-backend/app/schemas/psychro.py` 无 `gas_composition` 字段
- **目标**：加 `HydrateGasComposition` Pydantic model（7 组分：CH4/C2H6/C3H8/i_C4H10/N2/CO2/H2S）+ `_validate_sum_to_one` + `HydrateInhibitionInputV2.gas_composition` 字段（default 纯 CH4）
- **commit**：1
- **验收**：`pytest tests/schemas/ -q`；向后兼容（默认纯 CH4 行为不变）
- **OPEN 关闭**：OPEN-P6-6A-11 代码侧
- **依赖**：Nielsen constants 已落库（`pcs-backend/data/nielsen_1988_constants.json`）
- **工时**：0.3 天

### T2. C-16 Behr service `_calc_behr_water_content` 加 baseline 参数（OPEN-P6-6A-9.3 + 9.5 代码侧）

- **当前**：`glycol_dehydration_service.py` 用 general baseline（v5 plan 默认）
- **目标**：加 `baseline: Literal['general', 'high_acid'] = 'general'` 参数；high_acid 路径从 `pcs-backend/data/behr_coefficients.json` 读取；worley_c16 fixture 加高酸气 + 含 acid gas 算例；xls 对账路径测试（残差 < 5%）
- **commit**：1
- **验收**：worley_c16 fixture 0 break；新算例 `test_behr_high_acid_baseline_xls_reconciliation` PASS（残差 < 5%）
- **OPEN 关闭**：OPEN-P6-6A-9.3 + 9.5 代码侧
- **依赖**：T1（gas_composition schema）；`behr_coefficients.json` 已落库
- **工时**：0.7 天

### T3. C-18 hydrate_inhibition service Nielsen 完整方程组 + gas_composition + brine（OPEN-P6-6A-11 代码侧）

- **当前**：P6-6B T8 已落 InhibitorModel + 双模型分支，但 A/B/C 估算值 + 简化 `ΔT_F = A + B·x`
- **目标**：
  - 升级 `_calculate_nielsen_depression` 为完整方程组 `ΔT_F = A + B·x + C·x²` + 气组分加权 `ΔT_F_weighted = Σ(y_i · ΔT_F_i)`
  - 加 `gas_composition` 参数（默认纯 CH4）
  - 加 `_calc_brine_correction` 分支（Nielsen §3.4 `ΔT_brine_correction_F = -0.0015 × brine_wt_pct × T_op_F`）
  - 加 `brine_wt_pct` 输入字段
  - worley_c18 fixture 加 2 算例（纯甲烷 + 富 C2H6/C3H8 气田）
- **commit**：1
- **验收**：worley_c18 fixture 0 break；新算例 `test_nielsen_full_equation_ch4` + `test_nielsen_gas_composition_weighted` + `test_brine_correction` PASS
- **OPEN 关闭**：OPEN-P6-6A-11 代码侧（已部分闭环，再补 brine / gas_composition）
- **依赖**：T1（schema）；`nielsen_1988_constants.json` 已落库
- **工时**：0.8 天

### T4. C-08 vessel Imperial 测试（OPEN-P6-4-3 代码侧）

- **当前**：`vessel_weight_estimate_service.py` 仅 SI 单位；`golden_c08_imperial.json` 已 3 算例
- **目标**：测试用例加载 fixture + 验证 SI 输入/输出 + Imperial 转换（lb/ft³ 等）；3 fixture 落地（卧式 + 立式 + 球罐）
- **commit**：1
- **验收**：3 fixture 测试 PASS（rel ≤ 1e-2 容差）
- **OPEN 关闭**：OPEN-P6-4-3 代码侧
- **依赖**：`golden_c08_imperial.json` 已落库
- **工时**：0.3 天

### T5. C-24 CV Masonelian 3-model 对账测试（OPEN-P6-4-4 代码侧）

- **当前**：`cv_engine.py` 已 3 model；`golden_c24_valve_library.json` 24 组合 + `golden_c24_model_reconciliation.json` 3 算例
- **目标**：测试用例加载 fixtures + 验证 Masonelian_1973 / CHAPMAN_JANS / TONG 3 模型 vs 商业软件（容差 rel ≤ 1e-2 / TONG ≤ 5e-2）
- **commit**：1
- **验收**：3 算例 + 24 厂商库测试 0 break
- **OPEN 关闭**：OPEN-P6-4-4 代码侧
- **依赖**：`golden_c24_valve_library.json` + `golden_c24_model_reconciliation.json` 已落库
- **工时**：0.4 天

### T6. T10 路径 A：hydrate_inhibition 字段名 `_c` → `_f`（OPEN-P6-6A-3 真正关闭）

- **当前**：`hydrate_inhibition_service.py` 输出字段名 `hydrate_depression_c`（语义 Bug，实际输出 °F 值）；P6-6A-3 公式层 fix 已闭环
- **目标**：
  - 输出字段名修正 `hydrate_depression_c` → `hydrate_depression_f`（K_F=2335 °F scale per paper）
  - 新增 `hydrate_depression_c: float = _f × 5/9` 派生字段
  - 保留 `hydrate_depression_c_legacy: float = _f` deprecated 向后兼容
  - worley_c18 fixture 期望值更新（字段名 _c → _f + 新增 _c 派生）
  - CHANGELOG 标注 breaking change
- **commit**：1
- **验收**：worley_c18 fixture 0 break；新测试 `test_hydrate_depression_field_rename` PASS；旧 fixture 期望值迁移完成
- **OPEN 关闭**：OPEN-P6-6A-3 真正关闭（公式 + 字段名 + CONFIG 全闭环）
- **依赖**：`hammerschmidt_K` CONFIG 表已就位（P6-6B T7）
- **工时**：0.5 天

### T7. T11 分 path 并存：fire_case_standard 枚举（OPEN-P6-6A-5 真正关闭）

- **当前**：`as1210_overpressure_service.py` 硬编码 `_FIRE_COEFF_W = 43192`（API 521 §3.4）；P6-6A-5 加 `fire_case` 双字段（API 521 + AS 1210 path (a)）；P6-6B T5 `compound_api521_thresholds` CONFIG 表 2 行 metadata 闭环
- **目标**：
  - 加 `fire_case_standard: Literal["API_521", "AS_1210"] = "API_521"` 枚举
  - service 启动时从 `compound_api521_thresholds` CONFIG 读取 API 521 coefficient
  - 同时加载 AS 1210 path (a) `7.2e4`（已有）+ path (b)（OPEN-P6-6A-10 工艺 2026-11-15 关闭）
  - **放弃 2.457 系数**（工艺室追溯来源不明）
  - worley_c21 fixture 加 AS_1210 path (a) 算例
- **commit**：1
- **验收**：worley_c21 fixture 0 break；新测试 `test_fire_case_standard_api_521_default` + `test_fire_case_standard_as_1210_path_a` PASS
- **OPEN 关闭**：OPEN-P6-6A-5 真正关闭
- **依赖**：`compound_api521_thresholds` CONFIG 表已就位
- **工时**：0.5 天

### T8. AS 1210 §4.4 path (b) + Jet fire110,000 W/m² service path 分支（OPEN-P6-6A-10 代码侧）

- **当前**：PSV C-21 仅 API 521 §3.4 + AS 1210 path (a) 7.2×10⁴ 液化；AS 1210 path (b) gas/vapor + Jet fire 未实现
- **目标**：
  - `as1210_overpressure_service.py` 加 `_path_b_gas_vapor` 计算（`m' = m·Y_p + m'_p`，`Y_p = 10,000 / (C_w·t·T_o)`）
  - 加 `_jet_fire` 计算（`m' = m·Y_t + m'_p`，`Y_t = 110,000 / (C_w·t·T_r)`，vs pool fire 10,000）
  - fire_case 加 `Jet fire` 选项
  - `golden_as1210_path_b_jet_fire.json` 4 算例落地测试
- **commit**：1
- **验收**：4 算例测试 PASS（rel ≤ 1e-2 容差）
- **OPEN 关闭**：OPEN-P6-6A-10 代码侧（工艺 2026-11-15 关闭）
- **依赖**：`golden_as1210_path_b_jet_fire.json` 已落库
- **工时**：1.0 天

### T9. Bukacek 1990 T<60°F 延伸 `_behr_inverse_dewpoint` 分 T 段（OPEN-P6-6A-9.4 代码侧）

- **当前**：`glycol_dehydration_service.py` `_behr_inverse_dewpoint` 仅 T>60°F 系数（A0=1.3520/A1=0.00780/A2=0.0000052/A3=-0.9800）
- **目标**：
  - 加 Bukacek 1990 T<60°F 系数（A0'=2.1430/A1'=0.01850/A2'=-0.000042/A3'=-0.9800）
  - `_behr_inverse_dewpoint` 分 T 段：T>60°F 用 high-temp coeffs；T<60°F 用 low-temp coeffs；边界 T=60°F 用 high-temp（避免不连续）
  - worley_c16 fixture 加 3 低 T 算例（T ∈ {-10, 20, 40}°F）
  - `golden_c16_bukacek_low_temp.json` 3 算例落地测试
- **commit**：1
- **验收**：3 算例测试 PASS（rel ≤ 2e-2 容差）
- **OPEN 关闭**：OPEN-P6-6A-9.4 代码侧
- **依赖**：`golden_c16_bukacek_low_temp.json` 已落库
- **工时**：0.3 天

### T10. 批末收口：G-08 + STATUS + README + ADR-0045 Rev B 实施 + wolf 登记

- **当前**：10 task 全部 APPROVE
- **目标**：
  - G-08 phase 1-4 全过（0 OPENAPI drift）
  - pytest 各模块 0 break
  - vitest 0 break
  - `.wolf/STATUS.md` 闭环登记（P6-7 批落地 entry）
  - `.wolf/cerebrum.md` 更新（ADR-0045 Rev B 实施 + T10/T11 决策）
  - `README.md` 同步 P6-7 已闭环批次
  - push 全部 commits
- **commit**：1（docs(wolf): P6-7 批落地登记）
- **验收**：batch-end G-08 ✅ + 测试基线不退化
- **工时**：0.2 天

---

## 依赖图

```
T1 (psychro schema v2)
  ├─→ T2 (C-16 Behr baseline)
  └─→ T3 (C-18 Nielsen + brine)

T2 + T3 独立可并行（不同 service）

T4 (C-08 Imperial)        独立
T5 (C-24 CV 3-model)       独立
T6 (T10 字段名 _c → _f)    独立
T7 (T11 fire_case 分 path)   独立

T8 (AS 1210 path b + Jet fire) 依赖 T7 (fire_case 枚举扩展)
T9 (Bukacek T<60°F)        独立

T10 (批末收口) 依赖所有 T1~T9 APPROVE
```

**Phase 1 并行**：T1, T4, T5, T6, T7, T9（6 tasks 独立）
**Phase 2 并行**：T2, T3, T8（3 tasks 依赖 T1 + T7）
**Phase 3**：T10（批末收口）

---

## 工时表

| Phase | Tasks | 工作日 |
|---|---|---|
| Phase 1 并行 | T1, T4, T5, T6, T7, T9 | 2.0（并行 6 task，最长 0.5 天）|
| Phase 2 并行 | T2, T3, T8 | 1.5（并行 3 task，最长 0.8 天）|
| Phase 3 批末 | T10 | 0.2 |
| ETL 重新对账 + 全栈基线 | G-08 + pytest + vitest | 0.3 |
| **总计** | | **~4.0 工作日** |

---

## 验收矩阵（33 项）

| # | 项 | 命令 | 期望 |
|---|---|---|---|
| 1 | ruff | `cd pcs-backend && uv run ruff check .` | 0 errors |
| 2 | pytest | `uv run pytest -q` | ≥ baseline 3269 + 0 break |
| 3 | vitest | `cd pcs-frontend && npx vitest run` | ≥ baseline 548 + 0 break |
| 4 | tsc | `npx tsc --noEmit` | 0 errors |
| 5 | eslint | `npx eslint src/ tests/` | 0 errors |
| 6 | gate_08 | `bash pcs-backend/scripts/gate_08_openapi_contract.sh` | drift=0 |
| **T1** | 7 | schema v2 落地 + HydrateGasComposition sum_to_one validator | PASS |
| **T2** | 8 | Behr high_acid baseline vs XLS E20 残差 < 5% | PASS |
| **T2** | 9 | `golden_c16_high_acid_xls_e20.json` fixture 加载 | PASS |
| **T3** | 10 | Nielsen 完整方程组 `ΔT_F = A + B·x + C·x²` 验证 | PASS |
| **T3** | 11 | 气组分加权 `ΔT_F_weighted = Σ(y_i · ΔT_F_i)` 验证 | PASS |
| **T3** | 12 | `_calc_brine_correction` (Nielsen §3.4) 验证 | PASS |
| **T4** | 13 | C-08 vessel Imperial 3 算例（卧式 + 立式 + 球罐）rel ≤ 1e-2 | PASS |
| **T5** | 14 | C-24 CV Masonelian 1973 + CHAPMAN_JANS + TONG 3 模型对账 | PASS |
| **T5** | 15 | 24 厂商库 FL/FF/Cf 测试 0 break | PASS |
| **T6** | 16 | hydrate_depression_f 字段输出 vs XLS bit-for-bit | PASS |
| **T6** | 17 | `hydrate_depression_c = _f × 5/9` 派生字段 | PASS |
| **T6** | 18 | `hydrate_depression_c_legacy` deprecated 向后兼容 | PASS |
| **T7** | 19 | `fire_case_standard='API_521'` 默认路径 | PASS |
| **T7** | 20 | `fire_case_standard='AS_1210'` path (a) 7.2e4 | PASS |
| **T8** | 21 | AS 1210 path (b) gas/vapor `m' = m·Y_p + m'_p` 验证 | PASS |
| **T8** | 22 | Jet fire `m' = m·Y_t + m'_p` (110,000 W/m²) 验证 | PASS |
| **T8** | 23 | 4 算例（CH4/C3 × path b/jet fire）rel ≤ 1e-2 | PASS |
| **T9** | 24 | Bukacek T<60°F 分支 vs 手算 3 算例（rel ≤ 2e-2） | PASS |
| **T9** | 25 | T=60°F 边界不连续性验证（用 high-temp） | PASS |
| **T10** | 26 | G-08 phase 1-4 全过 | PASS |
| **T10** | 27 | `.wolf/STATUS.md` P6-7 落地 entry | DONE |
| **T10** | 28 | `.wolf/cerebrum.md` ADR-0045 Rev B + T10/T11 决策更新 | DONE |
| **T10** | 29 | `README.md` P6-7 已闭环批次同步 | DONE |
| **T10** | 30 | push 全部 commits 至 origin/main | DONE |

---

## 风险 + 缓解

| 风险 | 等级 | 缓解 |
|---|---|---|
| **R-1** ADR-0045 Rev B 落地时 K=7.1121 与 v5 plan K=7.1187 兼容性 | 低 | 6 工况 CV=1.05% < 5%，新值更稳定；worley_c16 fixture 期望值更新（rel ≤ 1e-3） |
| **R-2** T6 breaking change `_c` → `_f` 影响下游消费方 | 中 | `_c_legacy` deprecated 保留向后兼容；CHANGELOG 标注；worley_c18 fixture 期望值迁移 + 新测试覆盖 |
| **R-3** T8 AS 1210 path (b) + Jet fire 工艺 2026-11-15 才闭环 | 低 | 代码 + 测试已就位；工艺 PDF 到位后 confidence B 升级 A；worley_c21 fixture 同步 |
| **R-4** T3 Nielsen 完整方程组 + 气组分加权 + brine 3 项叠加变更 | 中 | 3 个独立子测试覆盖；worley_c18 fixture 扩 4 算例；CHANGELOG 标注 |
| **R-5** T1 schema v2 默认纯 CH4 与 P6-6B T8 实现交互 | 中 | 默认 CH4 不触发气组分加权；T2/T3 测试覆盖 |
| **R-6** T7 `fire_case_standard` 枚举与 P6-6A-5 双字段交互 | 低 | 双字段保留（`fire_case coeff/exp` 旧字段）；新枚举为辅 |
| **R-7** P6-7 与 P6-6B 后续 OPEN-P6-4-2 / 6-6A-10 工艺依赖 | 低 | OPEN-P6-4-2 上线后；OPEN-P6-6A-10 工艺 2026-11-15 闭环，T8 代码侧已就位 |

---

## 关键文件路径

- `pcs-backend/app/schemas/psychro.py` — T1 schema v2 增量
- `pcs-backend/app/services/psychro/glycol_dehydration_service.py` — T2 Behr baseline + T9 Bukacek
- `pcs-backend/app/services/psychro/hydrate_inhibition_service.py` — T3 Nielsen + brine + T6 字段名
- `pcs-backend/app/services/vessel/vessel_weight_estimate_service.py` — T4 Imperial 测试
- `pcs-backend/app/services/cv/cv_engine.py` — T5 Masonelian 3-model 测试
- `pcs-backend/app/services/psv/as1210_overpressure_service.py` — T7 fire_case_standard + T8 path (b) + Jet fire
- `pcs-backend/app/services/_compound_config_cache.py` — T7 CONFIG 读取 + T3 brine (optional)
- `pcs-backend/data/behr_coefficients.json` — T2 加载（已落库）
- `pcs-backend/data/nielsen_1988_constants.json` — T3 加载（已落库）
- `pcs-backend/docs/adr/ADR-0045-teg-contactor-sizing.md` — Rev B 已就位（T10 实施确认）
- `pcs-backend/tests/services/psychro/test_glycol_dehydration.py` — T2/T9 测试
- `pcs-backend/tests/services/psychro/test_hydrate_inhibition.py` — T3/T6 测试
- `pcs-backend/tests/services/vessel/test_weight_estimate.py` — T4 测试
- `pcs-backend/tests/services/cv/test_flashing_correction.py` — T5 测试
- `pcs-backend/tests/services/psv/test_as1210_overpressure.py` — T7/T8 测试

---

## OPEN 关闭清单（P6-7 批内）

| OPEN | 工艺侧 | 代码侧 | P6-7 task |
|---|---|---|---|
| OPEN-P6-4-3 | ✓ (2026-10-15) | T4 | C-08 Imperial 测试 |
| OPEN-P6-4-4 | ✓ (2026-10-31) | T5 | C-24 CV 3-model 测试 |
| OPEN-P6-6A-3 | ✓ | T6 | T10 字段名修正 |
| OPEN-P6-6A-4 | ✓ (P6-6B) | — | — |
| OPEN-P6-6A-5 | ✓ | T7 | T11 fire_case 双 path |
| OPEN-P6-6A-6 | partial (P6-6B T9 占位) | P6-7+/P7 | T9 glycol service 扩展 |
| OPEN-P6-6A-9 | ✓ (5 子项全部 2026-10-15) | T2/T9 | C-16 Behr + Bukacek |
| OPEN-P6-6A-10 | 待 (2026-11-15) | T8 | AS 1210 path b + Jet fire |
| OPEN-P6-6A-11 | ✓ (2026-10-15) | T1/T3 | hydrate_inhibition 完整方程组 |

**P6-7 批可关闭 9 项 OPEN**（含代码侧）。

---

## 后续（P6-8 / 上线）

P6-7 完成后触发：
- SPEC V1.2 修订（OPEN-P6-6A-1 Ruling 9 wording final + C-17 docstring scope clarification + C-19 Cd/Y_cr 文档化）
- P6-8 工程团队部署 + ETL 重新对账（OPEN-P6-6A-3 / 4 / 5 / 10 / 11 真实部署；T13 `_USE_XLS_CD_Y_CR` flag 切换）

---

## 未解决问题

1. **OPEN-P6-4-2**（T2 _VALVE_LIBRARY 真实 Kb 厂商数据）— 上线后批；P6-7 不阻塞
2. **OPEN-P6-6A-10 工艺 PDF**（AS 1210-2010 SAI Global 采购）— 2026-11-15 前到位升级 confidence B → A
3. **T8 path (b) + Jet fire 工艺 2026-11-15 闭环确认**— 工艺已给 fixture，但 PDF 标准原文升级待 P6-7 末 QA gate