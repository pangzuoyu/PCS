# ce-code-review P5+P6 全范围 Summary

**执行日期**: 2026-10-31
**执行方式**: 5 batch focused review（sonnet 双 persona correctness + project-standards）
**审查范围**: main HEAD = `2b27e00`，47 commits 跨 9 batches

---

## 已审查批次汇总

| # | 批次 | commits | 范围 (BASE..HEAD) | 关键发现 |
|---|---|---|---|---|
| 1 | **P5-0** | 5 | `40b0c69..20a7b60` | 2 HIGH + 1 MEDIUM + 3 LOW |
| 2 | **P5-123** | 5 | `fbea0a4..ba4e0de` | 2 HIGH + 3 MEDIUM + 4 LOW/INFO |
| 3 | **P6-6B** | 16 | `dc124f7..cd86949` | 2 HIGH + 3 MEDIUM + 4 LOW/INFO |
| 4 | **P6-7** | 10 | `eb824eb..6ed6a50` | 1 CRITICAL + 2 HIGH + 3 MEDIUM + 4 LOW/INFO |
| 5 | **P6-8+P6-9** | 11 | `c89d091..2b27e00` | **3 CRITICAL** + 1 HIGH + 6 MEDIUM/LOW |

**总计**: **47 commits** 跨 **5 batches**。

---

## 严重性分类统计

| 等级 | P5-0 | P5-123 | P6-6B | P6-7 | P6-8+P6-9 | 总计 |
|---|---|---|---|---|---|---|
| **CRITICAL** | 0 | 0 | 0 | 1 | 3 | **4** |
| **HIGH** | 2 | 2 | 2 | 2 | 1 | **9** |
| MEDIUM | 1 | 3 | 3 | 3 | 2 | 12 |
| LOW/INFO | 3 | 4 | 4 | 4 | 6 | 21 |

---

## 测试基线（5 batches 累计）

```
pytest:        3501 passed / 5 skipped / 3 failed (pre-existing CV 模块, 与 review 范围无关)
ruff check:    18 errors (全部 pre-existing, 0 new errors 引入)
G-08 phase 1-4: 全过 drift=0
```

---

## P6-8+P6-9 关键阻塞项（最高优先级）

### 🔴 CRITICAL F1 — `_calc_lean_glycol_concentration_wt_pct` else-branch bug

**文件**: `pcs-backend/app/services/psychro/glycol_dehydration_service.py:1326-1339`

**Evidence**: T∈(380,400)°F 段 line 1333 正确插值后，line 1339 `return _GPSA_FIG_20_4_DATA_POINTS[0].lean_glycol_concentration_wt_pct, warnings` 总是返回 `98.8`，**插值结果被丢弃**。

```python
def _calc_lean_glycol_concentration_wt_pct(...) -> tuple[float, list[str]]:
    # ... (T∈(380,400)°F 段插值)
    lean_at_380 = _GPSA_FIG_20_4_DATA_POINTS[0].lean_glycol_concentration_wt_pct
    lean_at_400 = _GPSA_FIG_20_4_DATA_POINTS[1].lean_glycol_concentration_wt_pct
    lean_glycol = lean_at_380 + (T - 380.0) * (lean_at_400 - lean_at_380) / (400.0 - 380.0)
    warnings.append("LEAN_GLYCOL_INTERPOLATION_PARTIAL: ...")
    # ❌ line 1339 return 应改为 return lean_glycol, warnings
    return _GPSA_FIG_20_4_DATA_POINTS[0].lean_glycol_concentration_wt_pct, warnings
```

**实测**:
```bash
python -c "_calc_lean_glycol_concentration_wt_pct(390.0, 0.0)"
# 返回: 98.8  (应为 ~99.05)
python -c "_calc_lean_glycol_concentration_wt_pct(395.0, 1.5)"
# 返回: 98.8  (应为 ~99.5)
```

**建议修复**:
- Line 1339 改为 `return lean_glycol, warnings`
- 添加 regression test 断言插值（不仅断言 warnings）
- 例: `test_lean_glycol_interpolation_in_band_values()` 验证 T=390, 0 scf/gal → ~99.05

---

### 🔴 CRITICAL F2 — SGR 公式结构反转

**文件**: `pcs-backend/app/services/psychro/glycol_dehydration_service.py:1234-1269` (with `2b27e00` PICKUP scope)

**Evidence**: GPSA §20.4 Eq.20-5 应为：

```
SGR = k × (P_sat,TEG / P_total) × (1-X) / X
```

实际实现：

```python
# ❌ line 1267: ratio 和 X-fraction 都反了
sgr = k_strip * (p_total_mmhg / p_sat_te_mmhg) * x_frac / (1.0 - x_frac)
```

**实测残差**: default case (T_reb=400°F, P=1000 psia, X=0.9938) SGR = **1.694e10 scf/gal** vs XLS E32 = **0.4220 scf/gal** → 残差 **4.015e12%**。

**根因分析**: 2b27e00 PICKUP 修复单位但未触及公式反转（声称 "SGR 单位修复" 但根因结构反转遗漏）。

**建议修复**:
```python
# 恢复 GPSA Eq.20-5 形式
sgr = k_strip * (p_sat_te_mmhg / p_total_mmhg) * (1.0 - x_frac) / x_frac
```
- 更新 fixture `expected.sgr_scf_gal_teg` 实际值
- 移除 `test_glycol_dehydration_stripping_gas.py:97` 公式自洽测试（递归套娃锁 bug）
- 恢复 real-value tolerance check vs XLS E32=0.4220

---

### 🔴 CRITICAL F3 (high side) — P6-7 3/3 C-24 model reconciliation 测试 FAIL

**文件**: `pcs-backend/tests/services/cv/test_c24_model_reconciliation.py:119`

**Evidence**:

| Case | Actual | Golden | Residual % |
|---|---|---|---|
| MASONELIAN_1973 | 0.6495 | 0.7638 | **14.96%** > tol 1% |
| CHAPMAN_JANS | 0.0944 | 0.2656 | **64.44%** > tol 1% |
| TONG | 0.5091 | 0.6026 | **15.51%** > tol 5% |

**根因**: fixture `inputs.x` 描述"闪蒸分率"(x=0.2/0.6/0.3)，但测试代码 IGNORE fixture.x 用内部 `x_p = ΔP/P1` 代替。

**影响**: **OPEN-P6-4-4 关闭无效**（3/3 测试 FAIL）。

**建议修复**: 三选一：
- (a) pass fixture.x 显式作为 pressure ratio 给 CvEngine
- (b) regenerate fixture golden fl 值匹配实际 service 代码
- (c) 删除失败测试直到工艺室提供 verified fixture 值

---

### 🟠 HIGH F1 — `_calculate_nielsen_depression` dead code（P6-123 + P6-6B）

**文件**: `pcs-backend/app/services/psychro/hydrate_inhibition_service.py:258-296`

**Evidence**: P6-7 T3 替换 call site (line 391) 为 `_calculate_nielsen_depression_full` — 旧 `_calculate_nielsen_depression` 函数**全代码库零 caller**。P6-6B T8 落地的 `_NIELSEN_1988_PARAMS` 和 `compound_nielsen_1988_params` CONFIG 表同样**无 reader**。

**建议修复**: 删除整个 dead code 函数 + 重构 fallback `_calculate_nielsen_depression_full` 优先读 DB 表

---

### 🟠 HIGH F2 — `_USE_XLS_CD_Y_CR` feature flag dead code（P6-6B）

**文件**: `pcs-backend/app/services/restriction/drain_orifice_service.py:44, 128-148`

**Evidence**: flag `_USE_XLS_CD_Y_CR: Final = False`。`_resolve_cd_y_cr(fluid)` 是唯一读 flag 函数，但**全代码库零 caller**（包括 `calc_drain_orifice`/`calc_drain_orifice_size`）。af0a054 加了 `_resolved_cd_y_cr` 手动参数 override，但**生产代码默认路径仍走 `inp.discharge_coefficient`/inp.expansion_factor`（back-compat 默认 1.0）**，不会自动 lookup CONFIG 表。

**建议修复**: `calc_drain_orifice` / `calc_drain_orifice_size` 入口加 `fluid: str | None` 参数；当 flag=True 且 fluid 提供时自动调 `_resolve_cd_y_cr(fluid)` 覆盖 Cd/Y_cr

---

### 🟠 HIGH — P6-7 `t_wall_mm` 单位歧义（100× 误差）

**文件**: `pcs-backend/app/services/psv/as1210_overpressure_service.py:321, 336, 358, 377, 406`

**Evidence**: 字段名 `t_wall_mm` 暗示 mm，但公式：

```python
y_p = 10_000 / (c_w_kj_per_m3_k * t_wall_mm * t_o_k)  # denominator 需 meters
```

**量纲检查**: numerator W/m² = kJ/(s·m²); denominator 需 kJ/m² → c_w [kJ/(m³·K)] × t [m] × T [K] = kJ/m²。**t 必须为 m**。t=20 mm 实际 → Y_p 偏离 100×。

**建议修复**: 重命名为 `t_wall_m` + 全 7 处同步更新（或显式 `/1000` 转换）

---

### 🟠 HIGH F3 standards — untracked test file

**文件**: `pcs-backend/tests/services/psychro/test_glycol_dehydration_fixtures_integration.py`（untracked `??`）

**建议修复**: 纳入 version control（commit as part of T6 commit 或 new test commit）

---

## 严重性优先级处理建议

| 优先级 | 项 | 行动 |
|---|---|---|
| **P0 立即** | CRITICAL F1+F2（p6-8+p6-9） | 立刻 patch `2b27e00` follow-up commit 修复 2 处 critical bug + 重跑 psychro 测试 |
| **P0 立即** | CRITICAL F3（p6-7） | 立刻 patch C-24 测试 fixture x vs P1/P2 一致性 + 重跑 CV 测试 |
| **P1 本周** | HIGH t_wall_mm 单位歧义 | 重命名 + 同步更新所有 call sites + 测试 |
| **P1 本周** | HIGH dead code（2 处） | 删除未引用 helper 函数（nielsen_1976 简化 + _USE_XLS_CD_Y_CR 标志） |
| **P2 本批收口** | HIGH F3 standards | commit test_glycol_dehydration_fixtures_integration.py |
| **P3 下批** | 12 MEDIUM 项 | 累积到 p6-9-pickup-2 或 p7-0 批 |
| **P4 下下批** | 21 LOW/INFO 项 | 文档化 / 暂不修 |

---

## 综合 verdict

**NOT READY TO MERGE** — P6-7/P6-8+P6-9 两批共 **4 处 CRITICAL** 必须修复：

1. `_calc_lean_glycol_concentration_wt_pct` else-branch 总是返回 98.8
2. `_calc_stripping_gas_rate_scf_gal_teg` 公式反向残差 4e12%
3. C-24 model reconciliation 3/3 测试 FAIL（OPEN-P6-4-4 关闭无效）
4. 隐含第 4 项：HIGH 单元歧义 t_wall_mm（公式未触及修复路径但 100× 风险）

**建议下批命名**: P6-9-PICKUP-2 (或 P6-10) fix-2-CRITICAL
- 修复 F1+F2（service.py）
- 修复 F3（test_c24_model_reconciliation.py + fixture）
- 修复 F_high（t_wall_mm + 2 dead code）
- 跑全部 psychro + cv 测试 100% pass
- 一次性 push 到 origin/main

---

## Review artifacts

| 文件 | 内容 |
|---|---|
| `docs/ce-code-review-p5-p6-summary.md` | **本文件**（总览 + 优先级建议） |
| `.superpowers/sdd/2026-11-15-p6-8-glycol-dehydration-extensions/` | P6-8 + P6-9 SDD workspace |
| 5 个 review agent runs | distributed review reports（per batch） |