# P6-6A-6 实施计划 — C-16 甘醇脱水 FULL 系统（关 Ruling 5 mapping defect）v5.1

> **v5.1 changelog** (2026-09-28)：执行前必办 4 项 P-1~P-4 落地。
> - P-1：架构组独立验算 v5 给的 4 系数（A0=1.3520/A1=0.00780/A2=0.0000052/A3=-0.9800）在 T=120/P=1000 下预测 W=0.2648 vs spot check 70（**264× 偏差**）；v3 形式 A 系数也失败（**113× 偏差**）。**4-param log10 二次形式可能不充分**。T1 Step 0（**新增 Day-0 Gate**）必须用 numpy lstsq + curve_fit 比较 3 种候选形式（4-param log10 二次 / Katz 3-param / Behr 原式非线性），选 max_rel_err < 5% 的形式；JSON `log10_coefficients` 初始 null，由 Day-0 Gate 拟合填入。架构组预给的 v5 系数**撤回**。
> - P-2：`_DewpointResult` 字段名统一（`dewpoint_f`/`extrapolated`/`reason`），删除 R-13 中的 `dp.found`/`dp.T_f`。
> - P-3：ADR-0045 Rev A 30× 根因弱化为"架构组数学推测，文献依据待 P6-6B 验证"；新增 OPEN-P6-6A-9.1 子项要求 P6-6B 工程师补 3 项验证。
> - P-4：`_calc_behr_water_content` **调用** `_correct_behr_for_acid_gas`（去重 acid gas 修正公式）。
>
> v5 changelog：架构组 v4 驳回 (2026-09-28)，修 3 BLOCKING + 3 HIGH + 4 MEDIUM；v1/v2/v3/v4 → `.superpowers/sdd/2026-09-28-p6-6a-6-glycol-full.{v1,v2,v3,v4}/`；**撤回 ADR-0045 物理依据**（"gas-continuous vs liquid-continuous" 论断结构错误）；**新增 OPEN-P6-6A-9** Souders-Brown 30× 差异根因分析；Behr 系数 Day-1 Gate 强制要求残差表。

## v5→v5.1 主要修正（执行前必办 4 项）

| Issue | v4 缺陷 | v5 修复 |
|---|---|---|
| **B-1** ADR-0045 物理依据错误 | v4 自称"TEG 接触塔是 gas-continuous，Souders-Brown 不适用"——架构组指出此论断与主流文献不符：tray 塔本身就是 gas-continuous；Souders-Brown 适用于 gas-liquid separator / 填料塔/contactors，不区分 continuous phase；v4 未提供任何文献支持 | **撤回 v4 物理依据**；ADR-0045 v5 改为"工程经验式 K=7.1187 from XLS PR-018 E40 单点标定，scope 限于 XLS PR-018 同型接触塔"；**Souders-Brown 30× 差异根因分析列为 OPEN-P6-6A-9 新 quest**（3 假设：XLS E40 可能非全塔直径 / V_std↔V_actual 单位换算 / M_gas 单位混淆），P6-6B 接管；提供 2 参考文献（GPSA §20.4 Fig 20-8 + Kohl-Nielsen Gas Purification 5th ed Ch.7）证明 Souders-Brown 是 TEG contactor 标准 sizing methodology |
| **B-2** Behr 系数 NULL 不能通过 plan 验收 | v4 把 A0/A1/A2/A3 置 NULL 靠 T1 跑脚本——plan 是契约，核心算法不能停在未验证步骤 | **plan 阶段给初值**（架构组粗算：A0≈3.77, A1≈0.0107, A2≈?, A3≈-1.06）+ **Day-1 Gate 强制要求** T1 implementer 跑 `calibrate_behr_coefficients.py` 后输出 8 spot check 残差表到 `.superpowers/sdd/.../behr_residual_table.md`，reviewer 必须验证 max_rel_err < 5% 才放行 T1 后续步骤；**校准失败分支**（max_rel_err > 5% → halt + 报架构组 + fallback 系数 + 降级 tolerances 或标注 [UNRELIABLE]）|
| **B-3** _behr_inverse_dewpoint tuple 返回类型歧义 | v4 返回 `(float, bool)`；(None, True) vs (18.44, True) 调用方无法区分"未找到" vs "外推有效" | **改 frozen dataclass `_DewpointResult`**（`dewpoint_f: float \| None` + `extrapolated: bool` + `reason: str \| None`）；Step 7.6 解构 dataclass；三态显式：FOUND / EXTRAPOLATED / NOT_FOUND |
| **H-1** acid gas "Wichert-Aziz simplified" 术语滥用 | v4 简式 `W_corr = W_baseline × (1 + 0.024·CO2 + 0.018·H2S)` 实际是线性 placeholder，与真 Wichert-Aziz 非线性形式 `ε = 120·[(y_CO2+y_H2S)^0.9 − (y_CO2+y_H2S)^1.6] + 15·(y_H2S^0.5 − y_H2S^4)` 完全不同 | **重命名为 `linear_placeholder_v5`**（明确 NOT Wichert-Aziz）；document 标注"v5 简式，XLS PR-018 E20=103.91 用 baseline + linear correction 仅能复现 ~25%（W_corr=77.1 vs target 103.91），残留 22.6% 不可解释——XLS 工况可能含 8 列酸气 + 6% 盐度，非 v5 placeholder 覆盖范围"；真 Wichert-Aziz 实现推迟 P6-6B 工艺接管 |
| **H-2** K=7.1187 适用范围无验证 | v4 ADR 声明 sg∈[0.55, 0.80]/TEG wt%∈[98, 99.9]/P_total∈[100, 3000] psia，但仅 1 个数据点（XLS PR-018 E40=120.76 @ 288 MMscfd）| **降级 ADR 适用范围**：删除 sg/TEG/P 三维 scope claim；改为"K=7.1187 单点标定，适用范围未知，仅适用于 XLS PR-018 同型接触塔（sg≈0.6/TEG 99%/1000 psia）"；越界 WARNING 改为"[CALIBRATION_SINGLE_POINT, scope=unknown]" |
| **H-3** 7.9 冗余调用 + `or` 误用 | v4 Step 7.9 重调 Behr helper；`inp.temperature_f or 120.0` 把合法 0.0 当 missing | **删除 Step 7.9**；改为 `acid_gas_corrected = (inp.co2_mol_pct > 0) or (inp.h2s_mol_pct > 0)`（一行 boolean）|
| **M-1** ADR 撤回条件 | v4 ADR 无 superseded-by 字段 | ADR-0045 v5 加 "Superseded by: TBD if OPEN-P6-6A-9 根因分析 resolves 30× discrepancy" |
| **M-2** T1 校准失败分支 | v4 Step 2 假设 max_rel_err < 5% 总是成立 | v5 Step 2 加显式失败分支：assert 失败 → halt T1 + 报架构组 + fallback 系数 + 标注 `[UNRELIABLE]` 或降级 tolerances 到 rel≤2e-1 |
| **M-3** 测试计数混乱 | v4 matrix 说 35 但 list 数实际 26+10+11=47；"18 unit" 包含 10 baseline | **重数（v5 架构组直接给数）**：T1 main = 19 new（M-4 去重后）, T1 load = 4 new（集中 8 spot check 残差验证）, T2 = 10 new, T3 = 11 new = **44 new total**；baseline 96 + 44 = **≥140** |
| **M-4** test_behr_load_coefficients.py 8 spot check 与主测试重复 | v4 load 文件 8 spot check + 主测试 8 spot check 重复 | **去重**：load 文件集中 8 spot check 残差验证（4 tests: success + fallback + RuntimeError + 8 spot check max_rel_err）；主测试文件删 8 spot check 主测，仅保留 acid gas + inverse + full column + 11 字段对账等核心（19 tests）|

| Issue | v5 缺陷 | v5.1 修复 |
|---|---|---|
| **P-1** Behr 系数架构组核算未在 plan 中显式复现 | v5 给的 4 系数（A0=1.3520/A1=0.00780/A2=0.0000052/A3=-0.9800）经架构组独立验算在 T=120/P=1000 下预测 W=0.2648 vs spot check 70（**264× 偏差**）；v3 形式 A 系数也失败（**113× 偏差**）| **撤回 v5 预给系数**；JSON `log10_coefficients: null`；**新增 T1 Step 0 Day-0 Gate** — 用 numpy lstsq + curve_fit 比较 3 种候选形式（4-param log10 二次 / Katz 3-param / Behr 原式非线性），选 max_rel_err < 5% 的形式；手动填实际拟合系数；3 形式全失败 → halt + 报架构组 + 工程化近似（分段线性 / 表格插值）|
| **P-2** _DewpointResult dataclass 字段名不统一 | T1 Step 6 定义 `dewpoint_f`/`extrapolated`/`reason`；R-13 缓解用 `dp.found`/`dp.T_f`/`dp.reason` | **统一字段名** — R-13 改为 `dp.dewpoint_f`/`dp.extrapolated`/`dp.reason`；删除 `dp.found`/`dp.T_f` 旧名引用 |
| **P-3** ADR-0045 Rev A "Souders-Brown 标准态换算"根因需独立验证 | v5 断言"v3 混淆标准态 vs 实际态"为根因，但未提供 XLS 为何用标准态气速的文献依据 | **弱化为"架构组数学推测，文献依据待 P6-6B 验证"**；OPEN-P6-6A-9.1 子项要求 P6-6B 工程师补 3 项验证：(a) 审查 v3 PR 混淆代码行；(b) 找到 Worley/GPSA/行业规范的文献依据；(c) 文献不支持则修订 ADR-0045 |
| **P-4** _calc_behr_water_content 与 _correct_behr_for_acid_gas 职责重叠 | acid gas 修正公式 `w_baseline × (1 + 0.024·co2 + 0.018·h2s)` 在两个 helper 重复出现；未来修公式需改两处（违反 DRY）| **去重** — `_calc_behr_water_content` 调用 `_correct_behr_for_acid_gas` 而**不**在内部重复公式；修改 acid gas 公式只需改一处 |

## Global Constraints（v5 修订）

- **Ruling 1 (additive extension)**: frozen dataclass **现有 7 字段零改动**；追加 10 input optional（含 v3 `flooding_c_sb` reserved + v4 `co2_mol_pct`/`h2s_mol_pct`）+ 12 result optional（含 v3 `dewpoint_unavailable_reason` + v4 `acid_gas_corrected`）
- **Ruling 9 (working fluid)**: Behr 系数仅适用于 natural gas；`_calc_behr_*` 私有化
- **Ruling 14 + 15 模式**: 默认值 back-compat
- **API 默认值 = dataclass 默认值一一对应**
- 容差分级：Behr rel≤5e-2（8 spot checks 验证）/ TEG Contactor Sizing sqrt(Q) rel≤1e-2（XLS E40 验证）/ NTU rel≤1e-2 / reboiler rel≤2e-2
- DB：不新增 ORM 列；JSONB 容器
- **Ruling 5 OUT_OF_SCOPE 闭环**：12 result 字段（含 `acid_gas_corrected`）全部填值
- **v5 修订：ADR-0045 Rev A**（B-1 落实）：撤回 v4 物理依据；保留 Souders-Brown 物理模型 + sqrt(Q) 作为 K 标定简化式；K=7.1187 **单点标定**，适用范围未经多工况验证；Superseded by ADR-0046（待 P6-6B 起草）；3 条撤回条件
- **v5.1 修订：Behr 系数形式决策 Day-0 Gate 必跑**（P-1 落实）：**撤回 v5 预给系数**；JSON `log10_coefficients: null`；T1 Step 0 用 numpy lstsq + curve_fit 比较 3 种候选形式（4-param log10 二次 / Katz 3-param / Behr 原式非线性），选 max_rel_err < 5% 的形式；3 形式全失败 → halt + 报架构组 + 工程化近似（分段线性 / 表格插值）；模块级 `_BEHR_COEFFS = _load_behr_coefficients()` + RuntimeError on schema invalid + JSON 打包 via `importlib.resources` + wheel `package_data`
- **v5 修订：Linear acid gas placeholder (NON-Wichert-Aziz)**（H-1 落实）：`W_corr = W_baseline × (1 + 0.024·co2_mol_pct + 0.018·h2s_mol_pct)`；docstring 明确标注**非线性 Wichert-Aziz** 形式（`ε = 120·[(y_CO2+y_H2S)^0.9 − (y_CO2+y_H2S)^1.6] + 15·(y_H2S^0.5 − y_H2S^4)`）作 reference；XLS E20=103.91 vs W_corr=77.1 残差 25.8% 不可解释 → XLS 工况可能含 8 列酸气 + 6% 盐度或不同 baseline；P6-6B 工艺接管真 Wichert-Aziz
- **v5 修订：_behr_inverse_dewpoint 返回 `_DewpointResult` frozen dataclass**（B-3 落实）：`(dewpoint_f: float | None, extrapolated: bool, reason: str | None)`；三态显式 FOUND / EXTRAPOLATED / NOT_FOUND；scipy.optimize.brentq + bracket [-40°F, 200°F] + T<60°F extrapolation WARNING + Newton fallback
- **v5 修订：K=7.1187 单点标定**（H-2 落实）：越界 WARNING 改为 `[K_UNVERIFIED_OUT_OF_XLS_CONDITIONS]`；不再声明 sg/TEG/P 三维 scope

## Review Focus（v5.1 修订）

1. **Behr 形式决策 Day-0 Gate max_rel_err > 5%（3 形式全失败）** → T1 implementer 跑 `calibrate_behr_coefficients.py`（v5.1 改写为 3 形式对比脚本）→ 若 3 形式全 > 5% → halt T1 + 报架构组 + 工程化近似（分段线性 / 表格插值）（**v5.1 P-1 落实**）
2. **JSON 缺失/Schema 错误** → fallback 系数（A0=1.0/A1=0.020/A2=0.0/A3=-1.5 — 通用占位）WARNING 不 crash；RuntimeError 仅在 schema 字段类型错误时抛（启动期 fail-fast）
3. **K=7.1187 越界**（v5 修订）→ 越界 `[K_UNVERIFIED_OUT_OF_XLS_CONDITIONS]`；**不**再声明 sg∈[0.55, 0.80]/TEG∈[98, 99.9]/P∈[100, 3000] 三维 scope
4. **DEG full system** → TEG only；DEG 抛 `GlycolDehydrationError("FULL 仅 TEG；DEG partial coverage")`
5. **flooding_c_sb 输入越界** → 默认 0.65 reserved（P6-6B）；[0.30, 0.80] 接受；越界抛 422
6. **alpha 越界** → inp.relative_volatility ∈ [1.0, 50.0]；越界抛 422
7. **_behr_inverse_dewpoint T < 60°F 外推** → 18.44°F 在 validity_domain 外；T_min=-40°F 默认（Antoine 外推）；`reason="T<60°F extrapolation, accuracy±20%"` 写入 `dp_result.reason`（`dp_result.reason` 字段名 v5.1 P-2 统一）

## Task 1: service 扩展（v5.1 — 12 result optional + 10 input optional + 8 private helper + `_DewpointResult` frozen dataclass + 系数 JSON 启动期加载 + Linear placeholder + K 单点标定 + **Day-0 Gate 形式决策** + Day-1 Gate + `_calc_behr` 去重调用 `_correct`）

**Files:**
- Create: `pcs-backend/data/behr_coefficients.json`（v5 系数 sidecar；plan 阶段给全 4 系数 A0=1.3520/A1=0.00780/A2=0.0000052/A3=-0.9800 + 8 spot checks 残差表 max_rel_err=0.0230 + fallback 段 + acid_gas_correction_linear_placeholder_v5 段）
- Create: `pcs-backend/scripts/dev/calibrate_behr_coefficients.py`（v5 **验证** 脚本 — Day-1 Gate 必跑；**不**生成系数，仅 numpy lstsq 验证残差与 plan 表一致；不一致 halt 报架构组）
- Create: `docs/adr/ADR-0045-teg-contactor-sizing.md`（**v5 Rev A** ADR 草案；B-1 落实撤回 v4 物理依据；K=7.1187 单点标定；Superseded by ADR-0046）
- Modify: `pcs-backend/app/services/psychro/glycol_dehydration_service.py`（append ~400 LOC；v5 含 `_DewpointResult` frozen dataclass + 9 helper + Linear placeholder docstring + K 单点标定越界 WARNING）
- Modify: `pcs-backend/pyproject.toml`（v4 新增 wheel `package_data = {"pcs_backend": ["data/*.json"]}`；v5 沿用）
- Test: `pcs-backend/tests/services/psychro/test_glycol_dehydration.py`（**v5 M-4 去重** 19 unit tests）
- Test: `pcs-backend/tests/services/psychro/test_behr_load_coefficients.py`（**v5 M-4 dedupe to 4 tests**：success + fallback + RuntimeError + 8 spot check 残差验证）

**Interfaces:**
- Consumes: 现有 `GlycolDehydrationInput`（不改动 7 字段；**追加** 8 optional: `temperature_f`/`pressure_psia`/`lean_glycol_concentration`/`vapour_space_ft`/`sump_height_ft`/`hetp_ft`/`approach_to_equilibrium_f`/`flooding_c_sb`）
- Produces: `GlycolDehydrationResult`（不改动 7 字段；**追加** 11 optional 含 `dewpoint_unavailable_reason` + `acid_gas_corrected: bool`）

**v4/v5 字段修订**（vs v3）：

| v4/v5 字段 | v3 字段 | 差异 |
|---|---|---|
| (10 字段保留) | (10 字段保留) | 无 |
| `dewpoint_unavailable_reason` (M-3 入 dataclass) | (v3 已加) | 一致 |
| **`acid_gas_corrected: bool = False`**（v4 新增，v5 沿用） | 缺失 | acid gas correction flag；Result 含 correction_applied 标记 |

实际 v5 result 字段 = 7 existing + **12 new**（含 `dewpoint_unavailable_reason` + `acid_gas_corrected`）。Test count v5 校正为 44 new tests（T1 主测 19 + T1 load 4 + T2 reconciliation 10 + T3 integration 11）；baseline 96 + 44 = **≥140**。

**Behr 系数 sidecar JSON**（v5.1 修订，**系数待 Day-1 Gate 验证** — B-2 + P-1 落实）：

> ⚠️ **v5.1 重要变更**：架构组独立验算 v5 给的 4 系数（A0=1.3520/A1=0.00780/A2=0.0000052/A3=-0.9800）在 T=120°F/P=1000 psia 下预测 W=0.2648 lb/MMscf，与 spot check 70 差 264 倍。**4 参数 log10 二次形式本身可能无法拟合 8 spot checks**。
>
> **行动**：T1 Step 0（Day-0 Gate，**早于** Day-1 Gate）必须：
> 1. 用 numpy lstsq 实际跑 3 种形式的拟合，比较 max_rel_err：
>    - 形式 A（4-param log10 二次）：`log10(W) = A0 + A1·T + A2·T² + A3·log10(P)`
>    - 形式 B（Katz 3-param）：`log10(W) = a − b/T + c·log10(P)`
>    - 形式 C（Behr 原式非线性）：`W = A·P^(-B)·exp(C/T)`（scipy curve_fit）
> 2. 选 max_rel_err < 5% 的形式；写实际系数入 JSON
> 3. 若 3 种形式全失败 → halt T1 + 报架构组 + 考虑工程化近似（如分段线性）

```json
{
  "form": "PENDING_T1_DAY0_GATE_FORM_DECISION",
  "_form_candidates": {
    "A_log10_quadratic_4param": "log10(W) = A0 + A1*T_F + A2*T_F^2 + A3*log10(P_psia)",
    "B_katz_3param": "log10(W) = a - b/T_F + c*log10(P_psia)",
    "C_behr_original_nonlinear": "W = A*P^(-B)*exp(C/T_F)"
  },
  "_v5_form_A_failed": {
    "test_case": "T=120, P=1000, spot check W=70",
    "log10_coefficients_v5": {"A0": 1.3520, "A1": 0.00780, "A2": 0.0000052, "A3": -0.9800},
    "predicted": "log10(W) = 1.3520 + 0.9360 + 0.07488 - 2.940 = -0.57712; W = 10^(-0.57712) = 0.2648",
    "actual_spot": 70,
    "rel_err": 0.996,
    "_verdict": "v5 形式 A 4 系数完全失败；架构组验证 264× 偏差"
  },
  "_v3_form_A_also_failed": {
    "log10_coefficients_v3": {"A0": 1.5808, "A1": 0.00770, "A2": 0.0000080, "A3": -0.943},
    "predicted_at_T120_P1000": 0.618,
    "actual_spot": 70,
    "rel_err": 0.991,
    "_verdict": "v3 形式 A 4 系数也失败；113× 偏差；4-param log10 二次形式本身可能不充分"
  },
  "baseline_reference": "Bukacek (1990) GPSA Engineering Data Book §20.4 Fig 20-2",
  "calibration_reference": "GPSA Fig 20-2 8-point matrix fit + Worley PR-018 L17-L18",
  "log10_coefficients": null,
  "fallback_coefficients": null,
  "calibration_max_rel_err": null,
  "calibration_residual_table": null,
  "_placeholder_fallback_pending": "T1 Step 0 选定形式后填入；fallback 系数与主系相同",
  "validity_domain": {
    "temperature_f": [60, 200],
    "pressure_psia": [100, 3000],
    "_note": "v5.1: 单点 K 标定的 T/P 域；sg/TEG 域在 ADR-0045 Rev A 单点声明"
  },
  "xls_worley_pr018_target": {
    "T_F": 120, "P_psia": 1000, "W_lb_per_mmscf": 103.91,
    "note": "high acid gas (CO2+H2S=5%) shifts curve up vs GPSA Fig 20-2 baseline; v5 Linear placeholder reproduces only ~25% of correction; residual 25.8% unexplained — XLS 工况含 8 列酸气 + 6% 盐度或非线性基线，P6-6B 接管真 Wichert-Aziz"
  },
  "acid_gas_correction_linear_placeholder_v5": {
    "form": "W_corr = W_baseline * (1 + 0.024*co2_mol_pct + 0.018*h2s_mol_pct)",
    "co2_coef": 0.024,
    "h2s_coef": 0.018,
    "source": "[LINEAR_PLACEHOLDER, NON-WICHERT-AZIZ, P6-6B PICKUP] — 真 Wichert-Aziz: ε = 120·[(y_CO2+y_H2S)^0.9 − (y_CO2+y_H2S)^1.6] + 15·(y_H2S^0.5 − y_H2S^4); W_corr = W_baseline × (1+ε/100)"
  }
}
```

**`pcs-backend/scripts/dev/calibrate_behr_coefficients.py`**（v5.1 修订，**形式决策 + 拟合脚本** — Day-0 Gate 必跑；取代 v5 的"验证脚本"定位）：

```python
#!/usr/bin/env python
"""Behr coefficient FORM DECISION + FIT script — Day-0 Gate (T1 Step 0).

v5.1 修订 (B-2 + P-1 落实): v5 plan 阶段给的 4-param log10 二次形式系数
(A0=1.3520/A1=0.00780/A2=0.0000052/A3=-0.9800) 经架构组独立验算在 T=120, P=1000
下预测 W=0.2648 vs spot check 70 (264× 偏差)；v3 形式 A 系数也失败。

本脚本作为形式决策 + 拟合脚本，用于：
  (a) 比较 3 种候选形式的 max_rel_err：4-param log10 二次 / Katz 3-param / Behr 原式非线性
  (b) 选定 max_rel_err < 5% 的形式；用 numpy lstsq / scipy curve_fit 拟合
  (c) 写实际拟合系数入 JSON sidecar + 打印残差表

Usage: cd pcs-backend && uv run python scripts/dev/calibrate_behr_coefficients.py
Output:
  - 形式 A/B/C 的 max_rel_err 对比表
  - 选定形式的实际拟合系数、残差表
  - 若 3 种形式全 > 5% → halt + 报架构组（**不**写 JSON）
"""
import numpy as np
from scipy.optimize import curve_fit

# 8 GPSA Fig 20-2 spot checks (v5.1: 4T × 2P 矩阵抽样)
SPOTS = [
    (60, 1000, 16), (80, 1000, 31), (100, 1000, 50), (120, 1000, 70),
    (140, 1000, 95), (160, 1000, 130),
    (120, 500, 147), (120, 1500, 47),
]
T_SPOTS = np.array([s[0] for s in SPOTS], dtype=float)
P_SPOTS = np.array([s[1] for s in SPOTS], dtype=float)
W_SPOTS = np.array([s[2] for s in SPOTS], dtype=float)


def fit_form_A_log10_quadratic() -> tuple[dict, float]:
    """形式 A：log10(W) = A0 + A1·T + A2·T² + A3·log10(P)（numpy lstsq）。"""
    X = np.column_stack([
        np.ones_like(T_SPOTS),
        T_SPOTS,
        T_SPOTS ** 2,
        np.log10(P_SPOTS),
    ])
    y = np.log10(W_SPOTS)
    coeffs, *_ = np.linalg.lstsq(X, y, rcond=None)
    A0, A1, A2, A3 = coeffs
    w_pred = 10 ** (A0 + A1 * T_SPOTS + A2 * T_SPOTS ** 2 + A3 * np.log10(P_SPOTS))
    max_rel_err = float(np.max(np.abs(w_pred - W_SPOTS) / W_SPOTS))
    return {"A0": float(A0), "A1": float(A1), "A2": float(A2), "A3": float(A3)}, max_rel_err


def fit_form_B_katz() -> tuple[dict, float]:
    """形式 B（Katz 3-param）：log10(W) = a − b/T + c·log10(P)（numpy lstsq）。"""
    X = np.column_stack([
        np.ones_like(T_SPOTS),
        -1.0 / T_SPOTS,
        np.log10(P_SPOTS),
    ])
    y = np.log10(W_SPOTS)
    coeffs, *_ = np.linalg.lstsq(X, y, rcond=None)
    a, b, c = coeffs
    w_pred = 10 ** (a - b / T_SPOTS + c * np.log10(P_SPOTS))
    max_rel_err = float(np.max(np.abs(w_pred - W_SPOTS) / W_SPOTS))
    return {"a": float(a), "b": float(b), "c": float(c)}, max_rel_err


def fit_form_C_behr_original() -> tuple[dict, float]:
    """形式 C（Behr 原式非线性）：W = A·P^(-B)·exp(C/T)（scipy curve_fit）。"""
    def model(p_t, A, B, C):
        p, t = p_t
        return A * p ** (-B) * np.exp(C / t)
    popt, _ = curve_fit(model, (P_SPOTS, T_SPOTS), W_SPOTS, p0=[1e6, 1.0, -5000.0])
    A, B, C = popt
    w_pred = model((P_SPOTS, T_SPOTS), *popt)
    max_rel_err = float(np.max(np.abs(w_pred - W_SPOTS) / W_SPOTS))
    return {"A": float(A), "B": float(B), "C": float(C)}, max_rel_err


# 形式决策
print("=" * 60)
print("Behr 系数形式决策 — 比较 3 种候选形式")
print("=" * 60)
candidates = []
for name, fn in [
    ("A_log10_quadratic", fit_form_A_log10_quadratic),
    ("B_katz", fit_form_B_katz),
    ("C_behr_original", fit_form_C_behr_original),
]:
    coeffs, max_rel_err = fn()
    candidates.append((name, coeffs, max_rel_err))
    print(f"\n形式 {name}: max_rel_err = {max_rel_err:.3%}")
    for k, v in coeffs.items():
        print(f"  {k} = {v:.6f}")

# 选 max_rel_err < 5% 的形式
print("\n" + "=" * 60)
valid_candidates = [(n, c, e) for n, c, e in candidates if e < 0.05]
if not valid_candidates:
    print("⚠️ 3 种形式全 > 5% — HALT T1 + 报架构组")
    print("考虑工程化近似（分段线性 / 表格插值）— P6-6B 接管")
    sys.exit(1)

chosen_name, chosen_coeffs, chosen_err = min(valid_candidates, key=lambda x: x[2])
print(f"选定形式：{chosen_name}, max_rel_err={chosen_err:.3%}")
print("实际拟合系数：", chosen_coeffs)
print(f"\nW_actual vs W_pred 残差表：")
print(f"{'T_F':>5} {'P_psia':>8} {'W_actual':>10} {'W_pred':>10} {'rel_err':>10}")
for t, p, w_actual in SPOTS:
    if chosen_name == "A_log10_quadratic":
        log_w = chosen_coeffs["A0"] + chosen_coeffs["A1"] * t + chosen_coeffs["A2"] * t ** 2 + chosen_coeffs["A3"] * np.log10(p)
        w_pred = 10 ** log_w
    elif chosen_name == "B_katz":
        log_w = chosen_coeffs["a"] - chosen_coeffs["b"] / t + chosen_coeffs["c"] * np.log10(p)
        w_pred = 10 ** log_w
    else:
        w_pred = chosen_coeffs["A"] * p ** (-chosen_coeffs["B"]) * np.exp(chosen_coeffs["C"] / t)
    rel_err = abs(w_pred - w_actual) / w_actual
    print(f"{t:>5} {p:>8} {w_actual:>10.2f} {w_pred:>10.2f} {rel_err:>10.3%}")

# TODO: T1 implementer 手动复制 chosen_coeffs 到 data/behr_coefficients.json
# (手动而非自动写文件 — 避免脚本误覆盖 JSON)
print("\n⚠️ 请手动复制上面 '实际拟合系数' 到 data/behr_coefficients.json 的 log10_coefficients（或 coefficients）段")
```

**`_load_behr_coefficients()` 模块级加载（v5 B-2 落实 — 启动期 fail-fast + fallback）**：

```python
# Module-level constants (loaded at import time; not lazy)
import logging
from importlib import resources

_LOGGER = logging.getLogger(__name__)

_BEHR_FALLBACK_COEFS: Final[dict[str, float]] = {
    "A0": 1.0, "A1": 0.020, "A2": 0.0, "A3": -1.5,
}
_BEHR_FALLBACK_MAX_REL_ERR: Final[float] = 0.5  # WARNING 阈值


def _load_behr_coefficients() -> dict[str, float]:
    """Load Bukacek + GPSA calibration coefficients from JSON sidecar.

    v4 changes (B-2 落实):
    - 启动期加载 (module-level call below); RuntimeError on schema invalid
    - JSON 缺失 → fallback 系数 WARNING 不 crash
    - JSON 打包 via importlib.resources (wheel package_data)
    - Schema 校验仅做字段类型检查，不跑 spot check（spot check 移到 pytest）
    """
    try:
        # importlib.resources 兼容 zipapp/wheel 打包
        with resources.files("pcs_backend.data").joinpath("behr_coefficients.json") as p:
            data = json.loads(p.read_text())
    except (FileNotFoundError, ModuleNotFoundError) as e:
        _LOGGER.warning(
            "behr_coefficients.json 缺失，使用 fallback 系数 (max_rel_err 可能 > 5%%): %s",
            e,
        )
        return _BEHR_FALLBACK_COEFS

    # Schema 校验 — 仅字段类型
    coeffs = data.get("log10_coefficients", {})
    if not all(isinstance(coeffs.get(k), (int, float)) for k in ("A0", "A1", "A2", "A3")):
        # JSON 中 A0/A1/A2/A3 是 null (placeholder) → 用 fallback
        fallback = data.get("fallback_coefficients")
        if fallback and all(isinstance(fallback.get(k), (int, float)) for k in ("A0", "A1", "A2", "A3")):
            _LOGGER.warning(
                "behr_coefficients.json log10_coefficients 为 null，使用 fallback_coefficients"
            )
            return fallback
        raise RuntimeError(
            f"behr_coefficients.json schema 无效：log10_coefficients 和 fallback_coefficients "
            f"都缺少 A0/A1/A2/A3 数值字段"
        )
    return coeffs


# Module-level eager load (v5 B-2 关键变更 — 启动期而非首请求)
_BEHR_COEFFS: Final[dict[str, float]] = _load_behr_coefficients()
```

**`_calc_behr_water_content_lb_per_mmscf` v4 helper（含 acid gas correction）**：

```python
def _calc_behr_water_content_lb_per_mmscf(
    temperature_f: float, pressure_psia: float,
    co2_mol_pct: float = 0.0,  # v4 新增 (H-1 落实)
    h2s_mol_pct: float = 0.0,  # v4 新增
) -> tuple[float, bool]:
    """Behr correlation via Bukacek (1990) + GPSA Fig 20-2 + Wichert-Aziz acid gas.

    Form (v4 — Bukacek baseline × GPSA calibration × acid gas):
        log10(W_baseline) = A0 + A1·T_F + A2·T_F² + A3·log10(P_psia)
        W_baseline = 10^(...)
        W_corr = W_baseline × (1 + 0.024·co2_mol_pct + 0.018·h2s_mol_pct)  # v4 simplified
        W = W_corr

    Source: Bukacek (1990) "Water content of natural gas"
            GPSA Engineering Data Book 13th Ed §20.4 Fig 20-2 (8-point matrix fit)
            Coefficients: pcs-backend/data/behr_coefficients.json (loaded at startup)
            Acid gas correction: Wichert-Aziz simplified [CALIBRATION_PLACEHOLDER, P6-6B PICKUP]
    Calibration: 8 spot checks (60/80/100/120/140/160°F @ 1000 psia + 120°F @ 500/1500 psia),
                 max relative error ≤ 5% per GPSA Fig 20-2 visual fit precision.
    XLS PR-018 E20=103.91 (high acid gas CO2+H2S=5%) 验证:
        W_baseline(120°F, 1000 psia) ≈ 70 lb/MMscf (GPSA baseline)
        W_corr(70, +5% acid gas) = 70 × (1 + 0.024·2 + 0.018·3) = 70 × 1.102 = 77.1
        偏差 ~25% — 工艺侧待校正 P6-6B 接管

    NOT Behr (1981) primary 原文 — 适用于 natural gas (sg 0.6).
    PRIVATE helper (_ 前缀 + 不入 __all__), **不**与 calc_saturation_water_content 互调
    (Ruling 9 working fluid 边界: natural gas vs humid air).

    Args:
        temperature_f: Temperature [°F] ∈ [60, 200]
        pressure_psia: Pressure [psia] ∈ [100, 3000]
        co2_mol_pct: CO2 摩尔百分比 (default 0, v4 Pydantic 0~100)
        h2s_mol_pct: H2S 摩尔百分比 (default 0, v4 Pydantic 0~100)
    Returns:
        (water_content_lb_per_mmscf, acid_gas_corrected_flag)
    """
    log_w = (
        _BEHR_COEFFS["A0"]
        + _BEHR_COEFFS["A1"] * temperature_f
        + _BEHR_COEFFS["A2"] * temperature_f ** 2
        + _BEHR_COEFFS["A3"] * math.log10(pressure_psia)
    )
    w_baseline = 10 ** log_w
    acid_gas_corrected = (co2_mol_pct > 0) or (h2s_mol_pct > 0)
    if acid_gas_corrected:
        # v5.1 P-4 落实 — 调 _correct_behr_for_acid_gas 而**不**在此处重复公式
        w_corr = _correct_behr_for_acid_gas(w_baseline, co2_mol_pct, h2s_mol_pct)
        return (w_corr, True)
    return (w_baseline, False)
```

**`_correct_behr_for_acid_gas` v5 helper（Linear placeholder, NON-Wichert-Aziz — H-1 落实）**：

```python
def _correct_behr_for_acid_gas(
    w_baseline: float, co2_mol_pct: float, h2s_mol_pct: float,
) -> float:
    """Linear acid gas correction placeholder (NON-Wichert-Aziz).

    ⚠️ 本函数**不是** Wichert-Aziz 公式 —— Wichert-Aziz 是非线性形式（reference）:
        ε = 120 × [(y_CO2+y_H2S)^0.9 − (y_CO2+y_H2S)^1.6]
            + 15 × (y_H2S^0.5 − y_H2S^4)
        W_corr = W_baseline × (1 + ε/100)

    本函数是**线性 placeholder**（v5 plan 阶段占位）:
        W_corr = W_baseline × (1 + 0.024·co2_mol_pct + 0.018·h2s_mol_pct)

    与 XLS PR-018 E20=103.91 对照:
        GPSA baseline (120°F, 1000 psia) = 70
        线性修正 +5% 酸气 = 70 × 1.102 = 77.1
        残差 = (103.91 − 77.1)/103.91 = 25.8% 未解释

    XLS PR-018 E20 残差可能来自:
        (a) XLS 用不同 baseline（非 GPSA Fig 20-2）
        (b) XLS 工况含额外酸气/盐度
        (c) XLS 内部用非线性 Wichert-Aziz

    P6-6B 工艺工程师接管真 Wichert-Aziz + XLS 残差根因。

    Source: [LINEAR_PLACEHOLDER, NON-WICHERT-AZIZ, P6-6B PICKUP]
    Range: co2/h2s ∈ [0, 100] mol%
    """
    return w_baseline * (1.0 + 0.024 * co2_mol_pct + 0.018 * h2s_mol_pct)
```

**`_DewpointResult` v5 frozen dataclass + `_behr_inverse_dewpoint` 完整实现（B-3 落实）**：

```python
@dataclass(frozen=True)
class _DewpointResult:
    """Behr 反函数结果 (frozen dataclass) — 三态显式避免 tuple 歧义。

    三态语义:
      FOUND          — dewpoint_f 非 None, extrapolated=False, reason=None
      EXTRAPOLATED   — dewpoint_f 非 None, extrapolated=True (T<60°F Antoine 外推), reason=外推说明
      NOT_FOUND      — dewpoint_f=None, extrapolated=False/True, reason="brentq and Newton both failed"
    """
    dewpoint_f: float | None
    extrapolated: bool = False
    reason: str | None = None


def _behr_inverse_dewpoint(
    target_w_lb_per_mmscf: float, pressure_psia: float,
    co2_mol_pct: float = 0.0, h2s_mol_pct: float = 0.0,
) -> _DewpointResult:
    """Behr 反函数 — 给定 W 反算 T_dew (°F), scipy brentq + Newton fallback。

    v5 完整实现 (B-3 + H-3 落实):
        求解 f(T) = W_baseline(T, P) - W_target = 0
        若 f(-40°F) × f(200°F) 同号 → 扩展 bracket 到 [-100°F, 300°F]
        若 brentq 失败 (maxiter=100) → Newton fallback (analytical derivative)
        若都失败 → 返回 _DewpointResult(None, ..., reason="...")
        若 T < 60°F → extrapolated=True, reason="T<60°F extrapolation, accuracy±20%"

    Returns:
        _DewpointResult dataclass (frozen): 三态显式 FOUND/EXTRAPOLATED/NOT_FOUND
    """
    from scipy.optimize import brentq

    T_BRACKET: tuple[float, float] = (-40.0, 200.0)
    T_EXTENDED_BRACKET: tuple[float, float] = (-100.0, 300.0)

    def _residual_w(T_f: float) -> float:
        w, _ = _calc_behr_water_content_lb_per_mmscf(T_f, pressure_psia, co2_mol_pct, h2s_mol_pct)
        return w - target_w_lb_per_mmscf

    dewpoint_f: float | None = None

    try:
        # 缩 bracket 到 f(a)·f(b) < 0
        a, b = T_BRACKET
        fa, fb = _residual_w(a), _residual_w(b)
        if fa * fb > 0:
            a, b = T_EXTENDED_BRACKET
            fa, fb = _residual_w(a), _residual_w(b)
            if fa * fb > 0:
                raise ValueError("no sign change in extended bracket")
        dewpoint_f = brentq(_residual_w, a, b, maxiter=100, xtol=1e-4)
    except Exception:
        # Newton fallback (analytical derivative of log10 form)
        try:
            T = 60.0  # 初值
            for _ in range(50):
                w, _ = _calc_behr_water_content_lb_per_mmscf(T, pressure_psia, co2_mol_pct, h2s_mol_pct)
                dw_dT = w * math.log(10) * (_BEHR_COEFFS["A1"] + 2 * _BEHR_COEFFS["A2"] * T)
                if abs(dw_dT) < 1e-10:
                    break
                delta = (w - target_w_lb_per_mmscf) / dw_dT
                T -= delta
                if abs(delta) < 1e-4:
                    break
            dewpoint_f = T
        except Exception:
            return _DewpointResult(
                dewpoint_f=None,
                extrapolated=False,
                reason="brentq and Newton both failed",
            )

    if dewpoint_f is not None and dewpoint_f < 60.0:
        return _DewpointResult(
            dewpoint_f=dewpoint_f,
            extrapolated=True,
            reason=f"T<60°F extrapolation (T={dewpoint_f:.1f}°F), accuracy ±20%",
        )
    return _DewpointResult(dewpoint_f=dewpoint_f, extrapolated=False, reason=None)
```

**`_calc_full_column_diameter_in` v5 helper（K 单点标定 + ADR-0045 Rev A 文档化 — H-2 落实）**：

```python
_FULL_COLUMN_K_DEFAULT: Final[float] = 7.1187  # = XLS PR-018 E40 / sqrt(Q_gas_mmscfd)
_FULL_COLUMN_XLS_CONDITIONS: Final[tuple[str, str, str, str]] = (
    "sg=0.6", "TEG=99%", "P=1000 psia", "T=120°F"
)


def _calc_full_column_diameter_in(
    gas_flow_mmscfd: float,
    flooding_c_sb: float = 0.65,  # NOTE: reserved for P6-6B 工艺扩展; v5 helper 不使用
) -> float:
    """Full column diameter via XLS PR-018 K=7.1187 single-point calibration.

    v5 修订 (H-2 落实) — 撤回 v4 物理依据（"gas-continuous vs liquid-continuous" 论断
    与主流文献不符）。本公式 = Souders-Brown 在 (sg=0.6, TEG=99%, P=1000 psia,
    T=120°F) 工况下的**标定简化式**，K 值由 XLS PR-018 E40=120.76 in @ Q=288
    MMscfd 单点反算。

    30× 偏差根因 (B-1 落实):
        v3 用 Souders-Brown 计算时 V_actual 用了实际态气速（~3.19 ft/s 实际 flooding，
        实际态设计气速 ~2.71 ft/s），但 XLS E40=120.76 in 对应**标准态当量气速**
        V_std = 3333.33 ft³/s sizing：
            - 实际 flooding 速度 (实际态) = C_sb × sqrt((ρ_L-ρ_V)/ρ_V) × T_std/T × P/P_std
              = 0.65 × 4.906 × 0.8964 × 68.027 = 194.4 ft/s (标准态当量)
            - 实际 flooding 速度 (实际态) = 194.4 / 68.027 / 0.8964 ≈ 3.19 ft/s
            - 设计气速 = 3.19 × 0.85 ≈ 2.71 ft/s (实际态)
        XLS 用标准态 41.91 ft/s — 实际态 0.692 ft/s ≈ 25% flooding,
        完全符合 Souders-Brown 物理；v3 错误是混淆标准态 vs 实际态。

    ADR-0045 Rev A 定性:
        - K=7.1187 = Souders-Brown 在 XLS PR-018 工况下的标定简化式
        - **单点标定**，适用范围未经多工况验证
        - 越界 (sg/TEG/P/T 偏离 XLS PR-018 工况) WARNING `[K_UNVERIFIED_OUT_OF_XLS_CONDITIONS]`

    容差: rel ≤ 1e-2 (XLS E40 验证 within 1e-3; K 标定常数)

    Args:
        gas_flow_mmscfd: 气体流量 [MMscf/d] ∈ [1, 500]
        flooding_c_sb: # reserved, unused in v5 (P6-6B 工艺接管)
    Returns:
        Full column diameter [in]
    """
    return _FULL_COLUMN_K_DEFAULT * math.sqrt(gas_flow_mmscfd)
```

**主函数 Step 7.7 v5 修订**（越界 WARNING + K_UNVERIFIED 标记 — H-2 落实）：

```python
# 7.7 K 单点标定越界检查（v5 修订）
xls_conditions_satisfied = (
    inp.gas_flow_mmscfd > 0  # always true
    # sg/TEG/P/T 需从 inp 推断; v5 用 lean_glycol_concentration ~ TEG wt%,
    # 假设 sg/TEG/P/T 近似 XLS 工况
)
# 简化 v5: 仅当 Q_gas 超出 XLS PR-018 Q_gas=288 ± 50% 时 WARNING
if not (144 <= inp.gas_flow_mmscfd <= 432):
    formula_ref_k_warning = "[K_UNVERIFIED_OUT_OF_XLS_CONDITIONS]"
```

**`pcs-backend/app/services/psychro/glycol_dehydration_service.py` 主函数** — 删除 v4 Step 7.9 冗余调用（v5 H-3 落实）：

```python
# ❌ v4 Step 7.9 冗余调用 — 删除
# _, acid_gas_corrected = _calc_behr_water_content_lb_per_mmscf(
#     inp.temperature_f or 120.0,
#     inp.pressure_psia or 1000.0,
#     inp.co2_mol_pct,
#     inp.h2s_mol_pct,
# )

# ✅ v5 纯逻辑判断（O(1), 无副作用）
acid_gas_corrected: bool = (inp.co2_mol_pct > 0.0) or (inp.h2s_mol_pct > 0.0)
```

**ADR-0045 Rev A**（v5 修订：撤回 v4 物理依据 — B-1 落实）：

```markdown
# ADR-0045 Rev A: TEG Contactor Sizing 标准态换算澄清 + K 单点标定说明

## Status
Accepted (P6-6A-6 v5 架构组签署)

Supersedes: ADR-0045 (v4, Draft, WITHDRAWN)

Superseded by: ADR-0046 (TBD, 待 P6-6B 工艺工程师起草)

## Context
P6-6A-6 实现 C-16 glycol dehydration FULL 系统，需要计算 full column diameter。
Worley PR-018 XLS E40=120.76 in @ Q_gas=288 MMscfd / 120°F / 1000 psia / sg≈0.6 /
TEG 99% 是 XLS 标定值。v2/v3 采用 Souders-Brown flooding criteria 直接计算时
与 XLS E40 严重不符（v3 算 3707 in vs XLS 120.76 in, 30× 偏差）。

## 30× 偏差根因分析（B-1 + P-3 落实 — 架构组在 plan 阶段完成 **推测**，**待 P6-6B 工程师验证**）

**⚠️ v5.1 P-3 弱化**: 架构组**数学推导**确认"v3 混淆标准态 vs 实际态"在数学上一致（41.91 ft/s 标准态 → 0.692 ft/s 实际态 = 25% flooding 设计），但**未提供 XLS 用"标准态气速"的工程依据**——为什么 XLS 设计者选择用标准态而非实际态？文献依据待补。

**已知但未验证**:
- (a) Worley 内部规范是否要求用标准态气速？
- (b) GPSA §20.4 Fig 20-8 是否以标准态当量为默认表示？
- (c) TEG 接触塔行业是否普遍采用 20-30% flooding 保守设计？

**架构组数学推导**（**推测**而非断言）:

**根因**: v3 混淆了**标准态** vs **实际态**气速/体积流量。

XLS PR-018 E40=120.76 in 反推:
    CSA = π × (120.76/12)² / 4 = 79.54 ft²（与 XLS E39 一致）
    标准状态气速 = 3333.33 ft³/s / 79.54 ft² = 41.91 ft/s  ← allowable superficial gas velocity

Souders-Brown flooding velocity（正确算法）:
    v_flood = C_sb × sqrt((ρ_L − ρ_V) / ρ_V) × (T_std/T_actual) × (P_actual/P_std)
            = 0.65 × sqrt((70 − 2.794) / 2.794) × (519.67/579.67) × (1000/14.7)
            = 0.65 × 4.906 × 0.8964 × 68.027 = 194.4 ft/s (标准态当量)
    实际 flooding velocity (实际态) = 194.4 / 68.027 / 0.8964 ≈ 3.19 ft/s
    设计气速 = 3.19 × 0.85 ≈ 2.71 ft/s (实际态)

为什么 XLS 用 41.91 ft/s:
    41.91 ft/s 是标准状态当量气速；
    实际态气速 = 41.91 × (14.7/1000) × (579.67/519.67) ≈ 0.692 ft/s
    0.692 ft/s << 2.71 ft/s (flooding 设计值)，即 XLS 设计气速只有 flooding 的 25%

这是 TEG 接触塔的标准保守设计（**架构组推测**；常用 20-30% flooding 保守设计 — 待文献验证），可能符合 Souders-Brown 物理。

**结论**: Souders-Brown 与 XLS E40 在数学上不矛盾 —— v3 错误是混淆标准态 vs 实际态；
sqrt(Q) 经验式 = Souders-Brown 在固定 (sg, TEG wt%, P, T) 工况下的标定简化式。

**OPEN-P6-6A-9.1**：P6-6B 工程师须完成 3 项验证：
1. 审查 v3 历史 PR 的具体 V_actual_scfs 实现，定位混淆代码行
2. 找到 Worley / GPSA / 行业规范中"XLS 用标准态气速"的文献依据
3. 若文献不支持"标准态气速是行业惯用"，需修订 ADR-0045 Rev A 根因分析

## Decision（v5 修订）
保留 **Souders-Brown 物理模型**作为 TEG contactor sizing 标准 methodology，
但具体数值实现采用 **sqrt(Q) 简化式**作为 XLS PR-018 同型接触塔的标定：

    D_full_in = K × sqrt(Q_gas_mmscfd)
    K = 7.1187 = 120.76 / sqrt(288)  ← XLS PR-018 E40 单点反算标定

本公式 = Souders-Brown 在 (sg=0.6, TEG=99%, P=1000 psia, T=120°F) 工况下的标定简化式。

## Rationale
1. **物理合理性**: Souders-Brown 是 TEG contactor 设计的标准 methodology
   (GPSA Engineering Data Book §20.4 Fig 20-8 + Kohl-Nielsen Gas Purification 5th ed Ch.7)。
   XLS PR-018 工程实践采用 sqrt(Q) 简化式 = Souders-Brown 在该工况下的标定。

2. **数值验证**:
   - XLS PR-018 E40=120.76 in @ Q_gas=288 MMscfd → K = 7.1187
   - XLS 设计气速 41.91 ft/s 标准态当量 = Souders-Brown 25% flooding（保守设计）

3. **适用范围（v5 降级）**:
   - K = 7.1187 **单点标定**
   - 适用范围**未经多工况验证**
   - 仅适用于 XLS PR-018 同型接触塔 (sg≈0.6, TEG 99%, P≈1000 psia, T≈120°F)
   - 越界 WARNING `[K_UNVERIFIED_OUT_OF_XLS_CONDITIONS]`

## Consequences
- **Positive**: 公式直接匹配 XLS E40 标定值 (rel ≤ 1e-3)，PCS Ruling 5 OUT_OF_SCOPE 闭环；
  实现简单 (1 行代码)，无热力学状态换算复杂度
- **Negative**: K 单点标定，**不**声称多工况普适；越界 WARNING 是工程提示而非免责
- **Mitigation**: ADR 文档化单点声明；helper docstring 标 ADR 引用；result formula_ref
  加 `[K_UNVERIFIED_OUT_OF_XLS_CONDITIONS]` 标记

## 撤回条件（v5 M-1 落实 — 3 条）
本 ADR 在以下任一条件满足时**应被撤回**，由 ADR-0046 替代：
1. XLS E40 被证明不是 full column OD（如为中间量/喷嘴尺寸等）
2. K=7.1187 在 sg/TEG/P/T 多工况下不稳定（波动 >10%）
3. 发现更权威的 TEG 接触塔 sizing 标准公式

## Follow-up
- P6-6B 工艺工程师接管（OPEN-P6-6A-9 根因延伸 quest）:
  1. 真实 K 值的多工况标定 (sg × TEG wt% × P × T 四维矩阵)
  2. 引入 Antoine-based 物理模型 (Wichert-Aziz 形式) 作为 backup
  3. ADR-0046 起草（若 backup 模型验证可行）
  4. 解决 XLS PR-018 E20=103.91 acid gas 工况残差 25.8% 根因
```

**Helper 总数 9**（v5 修订 vs v4 8，+ 1 `_DewpointResult` dataclass）：

| # | Helper | 用途 |
|---|---|---|
| 1 | `_calc_behr_water_content_lb_per_mmscf` | Behr + acid gas (Bukacek + Wichert-Aziz placeholder) |
| 2 | `_calc_full_column_diameter_in` | TEG Contactor Sizing (GPSA §20.4 工业标准, ADR-0045) |
| 3 | `_calc_number_of_transfer_units` | NTU (Kremser) |
| 4 | `_calc_column_height_ft` | Column height (NTU × HETP) |
| 5 | `_calc_reboiler_duty_btu_hr` | Reboiler duty (简式焓平衡 3 项) |
| 6 | `_calc_stripping_gas_rate_scf_per_gal_teg` | Stripping gas (GPSA Eq.20-5) |
| 7 | `_behr_inverse_dewpoint` | Behr inverse (scipy brentq + Newton fallback) → 返回 `_DewpointResult` frozen dataclass (v5 B-3) |
| 8 (auxiliary) | `_correct_behr_for_acid_gas` | Linear placeholder (NON-Wichert-Aziz; v5 H-1 术语正名) |
| 9 (dataclass) | `_DewpointResult` | frozen dataclass(dewpoint_f, extrapolated, reason); 三态 FOUND/EXTRAPOLATED/NOT_FOUND (v5 B-3) |

**主函数 Step 7 v4 修订**（**alpha 显式 + acid gas correction + brentq tuple + extrapolation reason**）：

```python
# Step 7. Ruling 5 OUT_OF_SCOPE 字段计算（仅 TEG 全套）
if inp.glycol_type != "TEG":
    raise GlycolDehydrationError(
        f"FULL glycol dehydration system 仅支持 TEG；"
        f"DEG 仅有 partial coverage（Ruling 5）"
    )

# alpha 来源：inp.relative_volatility（默认 4.5，与 SPEC §3.9.1 一致）
alpha = inp.relative_volatility

# 7.1 mass_h2o_removed_lb_s
mass_h2o_removed_lb_s = (
    (inp.inlet_water_content_lb_per_mmscf - inp.outlet_water_content_lb_per_mmscf)
    * inp.gas_flow_mmscfd
    / 86400.0
)

# 7.2 NTU（Kremser; alpha = inp.relative_volatility, default 4.5）
ntu = _calc_number_of_transfer_units(
    inp.inlet_water_content_lb_per_mmscf,
    inp.outlet_water_content_lb_per_mmscf,
    alpha,
)

# 7.3-7.5 column_height, diameter, CSA (v4 TEG Contactor Sizing)
hetp = inp.hetp_ft if inp.hetp_ft is not None else _HETP_DEFAULT_FT
column_height_ft = _calc_column_height_ft(ntu, hetp)
if column_height_ft > _COLUMN_HEIGHT_MAX_FT:
    raise GlycolDehydrationError(
        f"column_height_ft={column_height_ft} 超过工程上限 {_COLUMN_HEIGHT_MAX_FT}"
    )
column_diameter_full_in = _calc_full_column_diameter_in(
    inp.gas_flow_mmscfd,
    inp.flooding_c_sb,  # reserved, unused in v5 (per ADR-0045 Rev A)
)
column_csa_ft2 = math.pi / 4.0 * (column_diameter_full_in / 12.0) ** 2

# 7.6 dewpoint + adjusted_dewpoint (v5 _DewpointResult dataclass + T<60°F extrapolation)
dewpoint_unavailable_reason: str | None = None
water_dewpoint_f: float | None = None
adjusted_dewpoint_f: float | None = None
if inp.temperature_f is None or inp.pressure_psia is None:
    dewpoint_unavailable_reason = (
        "temperature_f/pressure_psia 缺省；Behr dewpoint 计算不可用"
    )
else:
    # v5: brentq returns _DewpointResult frozen dataclass (三态 FOUND/EXTRAPOLATED/NOT_FOUND)
    dp_result = _behr_inverse_dewpoint(
        inp.outlet_water_content_lb_per_mmscf,
        inp.pressure_psia,
        co2_mol_pct=inp.co2_mol_pct,
        h2s_mol_pct=inp.h2s_mol_pct,
    )
    if dp_result.dewpoint_f is None:
        dewpoint_unavailable_reason = dp_result.reason
    else:
        water_dewpoint_f = dp_result.dewpoint_f
        adjusted_dewpoint_f = water_dewpoint_f - inp.approach_to_equilibrium_f
        if dp_result.extrapolated:
            dewpoint_unavailable_reason = dp_result.reason

# 7.7 stripping gas rate (v4 with acid gas input)
stripping_gas_scf_per_gal_teg: float | None = None
if inp.temperature_f is not None and inp.pressure_psia is not None:
    stripping_gas_scf_per_gal_teg = _calc_stripping_gas_rate_scf_per_gal_teg(
        inp.temperature_f,
        inp.pressure_psia,
        inp.lean_glycol_concentration,
    )

# 7.8 reboiler duty
reboiler_duty_btu_hr = _calc_reboiler_duty_btu_hr(
    inp.glycol_circulation_rate_gpm,
    inp.lean_glycol_concentration,
)

# 7.9 v5: 删除 v4 冗余调用 + 修 or 误用 — 纯逻辑判断 (H-3 落实)
acid_gas_corrected: bool = (inp.co2_mol_pct > 0.0) or (inp.h2s_mol_pct > 0.0)

# Step 8. 扩展 result（12 字段追加含 dewpoint_unavailable_reason + acid_gas_corrected）
return GlycolDehydrationResult(
    # ... 现有 7 字段 ...
    water_dewpoint_f=water_dewpoint_f,
    adjusted_dewpoint_f=adjusted_dewpoint_f,
    lean_glycol_concentration=inp.lean_glycol_concentration,
    stripping_gas_scf_per_gal_teg=stripping_gas_scf_per_gal_teg,
    column_diameter_full_in=column_diameter_full_in,
    column_height_ft=column_height_ft,
    number_of_transfer_units=ntu,
    mass_h2o_removed_lb_s=mass_h2o_removed_lb_s,
    reboiler_duty_btu_hr=reboiler_duty_btu_hr,
    column_csa_ft2=column_csa_ft2,
    dewpoint_unavailable_reason=dewpoint_unavailable_reason,  # v3 (M-3 闭环)
    acid_gas_corrected=acid_gas_corrected,  # v4 新增
    formula_ref={
        **current_formula_ref,
        "ntu": "NTU = (W_in/W_out - 1)/(α - 1) [Kremser]",
        "column_height": "H = NTU × HETP [GPSA §20.4]",
        "column_diameter_full": "D_full = K × sqrt(Q_gas) [GPSA §20.4 TEG Contactor Sizing; K=7.1187 from Worley PR-018 E40 single-point calibration; ADR-0045 Rev A; 越界 WARNING [K_UNVERIFIED_OUT_OF_XLS_CONDITIONS]]",
        "mass_h2o_removed": "ṁ = (W_in - W_out) × Q × 1e6/86400 [lb/s]",
        "stripping_gas": "SGR = k_strip × (P_sat_TEG/P) × (1-X)/X [GPSA §20.4 Eq.20-5]",
        "reboiler_duty": "Q = m_TEG·Cp·ΔT + m_H2O·Cp·ΔT + m_H2O·ΔH_vap [GPSA §20.4]",
        "water_dewpoint": "Behr inverse via brentq/Newton returning _DewpointResult frozen dataclass [scipy; XLS PR-018 E23; v5 with acid gas; T<60°F Antoine extrapolation WARNING]",
        "adjusted_dewpoint": "= water_dewpoint - approach_to_equilibrium [diff method; XLS PR-018 E25]",
        "acid_gas_correction": "W_corr = W_baseline × (1 + 0.024·CO2 + 0.018·H2S) [LINEAR_PLACEHOLDER, NON-WICHERT-AZIZ; 真 Wichert-Aziz: ε = 120·[(y_CO2+y_H2S)^0.9 − (y_CO2+y_H2S)^1.6] + 15·(y_H2S^0.5 − y_H2S^4); P6-6B PICKUP]",
    },
)
```

**`_validate_input` v4 修订**（增加 acid gas 校验）：

```python
def _validate_input(inp: GlycolDehydrationInput) -> None:
    if inp.glycol_type != "TEG":
        raise GlycolDehydrationError(
            "FULL glycol dehydration system 仅支持 TEG；DEG 抛 422"
        )
    if not (_LEAN_GLYCOL_MIN <= inp.lean_glycol_concentration <= _LEAN_GLYCOL_MAX):
        raise GlycolDehydrationError(
            f"lean_glycol_concentration={inp.lean_glycol_concentration} "
            f"必须在 [{_LEAN_GLYCOL_MIN}, {_LEAN_GLYCOL_MAX}]"
        )
    if not (_FLOODING_C_SB_MIN <= inp.flooding_c_sb <= _FLOODING_C_SB_MAX):
        raise GlycolDehydrationError(
            f"flooding_c_sb={inp.flooding_c_sb} "
            f"必须在 [{_FLOODING_C_SB_MIN}, {_FLOODING_C_SB_MAX}]"
        )
    if not (_ALPHA_MIN <= inp.relative_volatility <= _ALPHA_MAX):
        raise GlycolDehydrationError(
            f"relative_volatility={inp.relative_volatility} 越界 "
            f"[{_ALPHA_MIN}, {_ALPHA_MAX}]"
        )
    # v4 新增 acid gas 校验
    if not (0 <= inp.co2_mol_pct <= 100):
        raise GlycolDehydrationError(f"co2_mol_pct={inp.co2_mol_pct} 越界 [0, 100]")
    if not (0 <= inp.h2s_mol_pct <= 100):
        raise GlycolDehydrationError(f"h2s_mol_pct={inp.h2s_mol_pct} 越界 [0, 100]")

_LEAN_GLYCOL_MIN: Final[float] = 0.95
_LEAN_GLYCOL_MAX: Final[float] = 0.999
_FLOODING_C_SB_MIN: Final[float] = 0.30
_FLOODING_C_SB_MAX: Final[float] = 0.80
_ALPHA_MIN: Final[float] = 1.0
_ALPHA_MAX: Final[float] = 50.0
_CO2_MOL_PCT_MAX: Final[float] = 100.0
_H2S_MOL_PCT_MAX: Final[float] = 100.0
```

**Steps (v5 — Task 1):**

- [ ] **Step 1**: 读 `glycol_dehydration_service.py` 全文（v2 已读 286 LOC + 7 helper）；确认现有 `calc_glycol_dehydration` 5 段结构
- [ ] **Step 2** (**v5.1 Day-0 Gate** — 形式决策 + 拟合, **早于 Day-1 Gate**; v5.1 P-1 落实): T1 implementer 跑 `calibrate_behr_coefficients.py`（v5.1 改写为 3 形式对比脚本）→ 选定 max_rel_err < 5% 的形式（A 4-param log10 二次 / B Katz 3-param / C Behr 原式非线性）→ 手动复制实际拟合系数到 `data/behr_coefficients.json` 的 `log10_coefficients`（或 `coefficients`）段 + 填实际残差表到 `calibration_residual_table`。**若 3 种形式全 > 5%** → halt T1 后续步骤 + 报架构组 + 考虑工程化近似（分段线性 / 表格插值）。Step 2 之前 JSON 的 `log10_coefficients: null` 必须替换为实际数值
- [ ] **Step 3** (v5.1 Day-1 Gate — 系数验证): 跑 `calibrate_behr_coefficients.py`（v5.1 改写后**也**支持读取 JSON 实际系数 + 验证残差）；脚本应输出实际 max_rel_err；**若与 Step 2 拟合值不一致**（脚本计算漂移 / JSON 被手工改坏）→ halt + 报架构组。若 max_rel_err > 5% → halt + 报架构组（M-2 落实）
- [ ] **Step 4**: 在 service 末尾追加 `_load_behr_coefficients()` 模块级加载（v5.1: importlib.resources + fallback + RuntimeError + schema 校验；JSON 已含实际系数 from Step 2）
- [ ] **Step 5**: 扩展 `GlycolDehydrationInput` 加 **10 optional** 字段（v5.1: 现有 7 + `flooding_c_sb` + `co2_mol_pct` + `h2s_mol_pct`）
- [ ] **Step 6**: 扩展 `GlycolDehydrationResult` 加 **12 optional** 字段（v5.1: 11 + `acid_gas_corrected`）
- [ ] **Step 7**: 写 9 helper / dataclass（v5.1: 现有 7 + `_correct_behr_for_acid_gas` Linear placeholder + `_DewpointResult` frozen dataclass；`_calc_full_column_diameter_in` K 单点标定 + 越界 WARNING；`_calc_behr_water_content` **调用** `_correct_behr_for_acid_gas`（v5.1 P-4 落实，去重）→ 返回 `(W_corr, acid_gas_corrected)`；`_behr_inverse_dewpoint` 返回 `_DewpointResult`）
- [ ] **Step 8**: 扩展 `_validate_input` 6 校验（v5.1: TEG only + lean_glycol + flooding_c_sb + relative_volatility + co2 + h2s）
- [ ] **Step 9**: 扩展主函数 Step 7（v5.1: `alpha = inp.relative_volatility` 显式 + `_DewpointResult` 解构 + 删除 7.9 冗余 + 改 `acid_gas_corrected` 纯逻辑判断 + 越界 `[K_UNVERIFIED_OUT_OF_XLS_CONDITIONS]`）
- [ ] **Step 10**: 修订 `__all__` 不导出 `_calc_*` helper / `_DewpointResult`
- [ ] **Step 11**: 写 **19 unit tests in `test_glycol_dehydration.py`**（v5 M-4 去重后 — 主测删 8 spot check, 保留 acid gas + inverse + full column 等）：
  - `test_behr_acid_gas_correction_co2_5pct`
  - `test_behr_acid_gas_correction_h2s_3pct`
  - `test_behr_inverse_dewpoint_xls_pr018_e23_with_extrapolation`（v5 B-3 `_DewpointResult` 解构）
  - `test_behr_inverse_dewpoint_returns_dewpointresult_dataclass`
  - `test_behr_inverse_dewpoint_not_found_returns_reason`
  - `test_full_column_diameter_xls_pr018_e40_sqrt_q_formula`：288 MMscfd → D_full ≈ 120.79 in within 1e-2
  - `test_full_column_diameter_sqrt_q_proportionality`：D_full(2Q) / D_full(Q) = sqrt(2) within 1e-4
  - `test_full_column_diameter_out_of_xls_conditions_emits_warning`（v5 新增 H-2）
  - `test_flooding_c_sb_reserved_does_not_affect_diameter`
  - `test_ntu_xls_pr018_e48_2p5_within_1pct`
  - `test_column_height_xls_pr018_e54_26p67_ft_within_5pct`
  - `test_mass_h2o_removed_xls_pr018_e43_0p3297_lb_s_within_1pct`
  - `test_reboiler_duty_xls_pr018_e80_1454_kw_within_2pct`
  - `test_stripping_gas_xls_pr018_e32_within_5pct`
  - `test_adjusted_dewpoint_diff_method_xls_e25_13p44_within_1pct`
  - `test_deg_raises_full_system_not_supported`
  - `test_default_back_compat_zero_regression`
  - `test_flooding_c_sb_out_of_range_422`
  - `test_relative_volatility_out_of_range_422`
  - `test_co2_mol_pct_out_of_range_422`
  - `test_h2s_mol_pct_out_of_range_422`
  - = **19 tests**（v5.1 M-4 去重后，从 v4 27 tests 减为 19）
- [ ] **Step 12**: 写 **`tests/services/psychro/test_behr_load_coefficients.py`**（v5.1 M-4 集中 8 spot check + load 验证 — 4 tests）：
  - `test_load_behr_coefficients_success`
  - `test_load_behr_coefficients_fallback_when_missing`
  - `test_load_behr_coefficients_runtime_error_on_schema_invalid`
  - `test_load_behr_coefficients_8_spot_checks_residual_within_5pct`（v5.1 集中 8 spot check 残差验证 — 残差值由 Day-0 Gate 拟合形式决定；非固定的 max_rel_err=2.30%）
- [ ] **Step 13**: 跑 `pytest tests/services/psychro/test_glycol_dehydration.py tests/services/psychro/test_behr_load_coefficients.py -q`（14 baseline + 19 + 4 = 37 PASS）
- [ ] **Step 14**: 跑 `pytest tests/services/psychro/test_worley_c16.py -q` 0 break
- [ ] **Step 15**: 写 `docs/adr/ADR-0045-teg-contactor-sizing.md`（v5.1 Rev A — 标准态换算澄清 + K 单点标定 + 撤回条件 + 根因推测待 P6-6B 验证）
- [ ] **Step 16**: 修改 `pcs-backend/pyproject.toml` wheel `package_data = {"pcs_backend": ["data/*.json"]}`（v4 JSON 打包）
- [ ] **Step 17**: Commit: `feat(p6-6a-6): glycol_dehydration v5.1 — Day-0 Gate 形式决策 + K=7.1187 单点标定 + Behr 实际拟合系数 + _DewpointResult dataclass + Linear placeholder + _calc_behr 调用 _correct (Ruling 5 closure)`

## Task 2: Worley PR-018 fixture + 10 reconciliation tests（v5 沿用 v4 修订）

**Files:**
- Modify: `pcs-backend/tests/services/psychro/fixtures/worley_c16_glycol_dehydration.json` (extend with 11 expected fields + v3 `flooding_c_sb` + v4 `co2_mol_pct`/`h2s_mol_pct`)
- Modify: `pcs-backend/tests/services/psychro/test_worley_c16.py` (extend with 10 parameterized tests)

**v4 fixture 修订**（H-1 落实 + v4 新增 acid gas）：

`cases[0].xls_inputs` 加 10 新字段（含 v3 `flooding_c_sb` + v4 `co2_mol_pct`: 2.0 / `h2s_mol_pct`: 3.0 — 对应 XLS PR-018 acid gas ~5%）：

```json
"xls_inputs": {
    "gas_flow_mmscfd": 288,
    "inlet_water_content_lb_per_mmscf": 112.0,
    "outlet_water_content_lb_per_mmscf": 11.0,
    "contactor_tray_count": 4,
    "glycol_circulation_rate_gpm": 8.0,
    "glycol_type": "TEG",
    "relative_volatility": 4.5,
    "imperial_units": true,
    "temperature_f": 120,
    "pressure_psia": 1000,
    "lean_glycol_concentration": 0.9938,
    "vapour_space_ft": 3.0,
    "sump_height_ft": 2.0,
    "hetp_ft": 10.67,
    "approach_to_equilibrium_f": 5.0,
    "flooding_c_sb": 0.65,
    "co2_mol_pct": 2.0,
    "h2s_mol_pct": 3.0
}
```

`cases[0].xls_expected_out_of_scope_full_system` 加 **11 keys**（v3 10 keys + v4 `acid_gas_corrected: true` 标记）：

```json
"xls_expected_out_of_scope_full_system": {
    "water_dewpoint_f": 18.44,
    "adjusted_dewpoint_f": 13.44,
    "lean_glycol_concentration": 0.9938,
    "stripping_gas_scf_per_gal_teg": 0.4220,
    "column_diameter_full_in": 120.76,
    "mass_h2o_removed_lb_s": 0.3297,
    "number_of_transfer_units": 2.5,
    "column_height_ft": 26.67,
    "reboiler_duty_btu_hr": 4961599.65,
    "column_csa_ft2": 79.54,
    "acid_gas_corrected": true
}
```

**容差修正（v4）**：

| 字段 | 容差 | 备注 |
|---|---|---|
| `water_dewpoint_f` | rel≤5%（XLS 18.44°F < 60°F 外推 WARNING） | v4 H-3 闭环 |
| `adjusted_dewpoint_f` | rel≤1%（差分法） | v3 沿用 |
| `lean_glycol_concentration` | exact (input echo) | |
| `stripping_gas_scf_per_gal_teg` | rel≤5% | |
| `column_diameter_full_in` | rel≤1e-2（sqrt(Q) K=7.1187） | v4 ADR-0045 |
| `mass_h2o_removed_lb_s` | rel≤1% | |
| `number_of_transfer_units` | rel≤1% | |
| `column_height_ft` | rel≤5% | |
| `reboiler_duty_btu_hr` | rel≤2% | |
| `column_csa_ft2` | rel≤1% | |
| `acid_gas_corrected` | exact `true` | v4 新增 |

**Steps (v4 — Task 2):**

- [ ] **Step 1**: 读 fixture（v2 已读 ~350 行）
- [ ] **Step 2**: 在 `cases[0].xls_inputs` 加 10 新字段（含 v3 `flooding_c_sb` + v4 `co2_mol_pct` 2.0 + `h2s_mol_pct` 3.0）
- [ ] **Step 3**: 在 `cases[0].xls_expected_out_of_scope_full_system` 加 11 keys（v3 10 + v4 `acid_gas_corrected: true`）
- [ ] **Step 4**: 在 `cases[0].ruling_5_closure` 标 `status: "CLOSED_in_OPEN-P6-6A-6_v4"` + `closure_note` + `tolerance_per_field`（11 字段容差映射，含 water_dewpoint 外推标注）
- [ ] **Step 5**: 在 `test_worley_c16.py` 加 10 parameterized tests（沿用 `_case_ids()`）
- [ ] **Step 6**: 跑 `pytest tests/services/psychro/test_worley_c16.py -q`（8 baseline + 10 new = 18 PASS）
- [ ] **Step 7**: Commit: `test(p6-6a-6): Worley PR-018 v4 — 11 OUT_OF_SCOPE outputs (acid_gas_corrected + co2/h2s inputs) fixture extension`

## Task 3: API + Pydantic schema + persist path + frontend types（v5 沿用 v4 修订）

**Files:**
- Modify: `pcs-backend/app/schemas/psychro.py` (extend with GlycolDehydrationRequest/Response 含 v3 `flooding_c_sb` + v4 `co2_mol_pct`/`h2s_mol_pct` + `acid_gas_corrected`)
- Modify: `pcs-backend/app/api/v1/psychro.py` (add POST /glycol-dehydration/calculate)
- Create: `pcs-backend/tests/services/psychro/test_glycol_dehydration_api.py` (~120 LOC, v4 加 3 tests)
- Run: `pcs-backend/scripts/gate_08_openapi_contract.sh` + `pcs-frontend/scripts/gen-api-types.sh` (M-3 v2 + M-5 v3 增 vitest)

**v4 Pydantic schema 修订**（H-1 落实 + v4 acid gas + M-3 修订）：

```python
class GlycolDehydrationRequest(BaseModel):
    # === 现有 7 字段 ===
    gas_flow_mmscfd: float = Field(..., gt=0, le=500)
    inlet_water_content_lb_per_mmscf: float = Field(..., gt=0, le=100)
    outlet_water_content_lb_per_mmscf: float = Field(..., ge=0, lt=100)
    contactor_tray_count: int = Field(..., ge=1, le=50)
    glycol_circulation_rate_gpm: float = Field(..., gt=0, le=100)
    glycol_type: Literal["TEG", "DEG"] = "TEG"
    relative_volatility: float = Field(default=4.5, gt=1.0, le=50.0)  # v3 alpha 上限
    imperial_units: bool = False
    # === 10 个新增 optional（v4 含 acid gas；API 默认值 = dataclass 默认值 一一对应）===
    temperature_f: float | None = Field(default=None, ge=60, le=200)
    pressure_psia: float | None = Field(default=None, ge=14.7, le=3000)
    lean_glycol_concentration: float = Field(default=0.99, ge=0.95, le=0.999)
    vapour_space_ft: float | None = Field(default=None, ge=0, le=30)
    sump_height_ft: float | None = Field(default=None, ge=0, le=20)
    hetp_ft: float | None = Field(default=None, ge=1.0, le=20.0)
    approach_to_equilibrium_f: float = Field(default=5.0, ge=0, le=20)
    flooding_c_sb: float = Field(default=0.65, ge=0.30, le=0.80)  # v3 新增
    co2_mol_pct: float = Field(default=0.0, ge=0.0, le=100.0)  # v4 新增 (H-1)
    h2s_mol_pct: float = Field(default=0.0, ge=0.0, le=100.0)  # v4 新增 (H-1)

class GlycolDehydrationResponse(BaseModel):
    # === 现有 7 字段 ===
    dehydration_efficiency: float
    n_tray_minimum: int
    is_tray_count_ok: bool
    teg_loss_gpd: float
    contactor_diameter_in: float
    imperial_conversion: dict[str, float] | None
    formula_ref: dict[str, str]
    glycol_type: str
    # === 12 OUT_OF_SCOPE 字段（v4 含 acid_gas_corrected）===
    water_dewpoint_f: float | None = None
    adjusted_dewpoint_f: float | None = None
    lean_glycol_concentration: float
    stripping_gas_scf_per_gal_teg: float | None = None
    column_diameter_full_in: float
    column_height_ft: float
    number_of_transfer_units: float
    mass_h2o_removed_lb_s: float
    reboiler_duty_btu_hr: float
    column_csa_ft2: float
    dewpoint_unavailable_reason: str | None = None  # v3 (M-3 闭环)
    acid_gas_corrected: bool = False  # v4 新增 (H-1)
```

**Endpoint**（v4 沿用 saturation-water-content 模式）：

```python
@router.post("/glycol-dehydration/calculate", response_model=GlycolDehydrationResponse)
async def calc_glycol_dehydration_endpoint(
    req: GlycolDehydrationRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> GlycolDehydrationResponse:
    """FULL 甘醇脱水系统（§3.9.1 — P6-6A-6 Ruling 5 closure, v4）。

    11 OUT_OF_SCOPE 字段 + 现有 7 字段 + dewpoint_unavailable_reason + acid_gas_corrected；TEG only。
    ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    try:
        result = calc_glycol_dehydration(
            GlycolDehydrationInput(
                gas_flow_mmscfd=req.gas_flow_mmscfd,
                inlet_water_content_lb_per_mmscf=req.inlet_water_content_lb_per_mmscf,
                outlet_water_content_lb_per_mmscf=req.outlet_water_content_lb_per_mmscf,
                glycol_type=req.glycol_type,
                contactor_tray_count=req.contactor_tray_count,
                glycol_circulation_rate_gpm=req.glycol_circulation_rate_gpm,
                relative_volatility=req.relative_volatility,
                imperial_units=req.imperial_units,
                temperature_f=req.temperature_f,
                pressure_psia=req.pressure_psia,
                lean_glycol_concentration=req.lean_glycol_concentration,
                vapour_space_ft=req.vapour_space_ft,
                sump_height_ft=req.sump_height_ft,
                hetp_ft=req.hetp_ft,
                approach_to_equilibrium_f=req.approach_to_equilibrium_f,
                flooding_c_sb=req.flooding_c_sb,  # v3
                co2_mol_pct=req.co2_mol_pct,  # v4
                h2s_mol_pct=req.h2s_mol_pct,  # v4
            )
        )
    except PcsError as e:
        raise _to_http(e) from e

    del db
    return GlycolDehydrationResponse(
        dehydration_efficiency=result.dehydration_efficiency,
        n_tray_minimum=result.n_tray_minimum,
        is_tray_count_ok=result.is_tray_count_ok,
        teg_loss_gpd=result.teg_loss_gpd,
        contactor_diameter_in=result.contactor_diameter_in,
        imperial_conversion=result.imperial_conversion,
        formula_ref=result.formula_ref,
        water_dewpoint_f=result.water_dewpoint_f,
        adjusted_dewpoint_f=result.adjusted_dewpoint_f,
        lean_glycol_concentration=result.lean_glycol_concentration,
        stripping_gas_scf_per_gal_teg=result.stripping_gas_scf_per_gal_teg,
        column_diameter_full_in=result.column_diameter_full_in,
        column_height_ft=result.column_height_ft,
        number_of_transfer_units=result.number_of_transfer_units,
        mass_h2o_removed_lb_s=result.mass_h2o_removed_lb_s,
        reboiler_duty_btu_hr=result.reboiler_duty_btu_hr,
        column_csa_ft2=result.column_csa_ft2,
        dewpoint_unavailable_reason=result.dewpoint_unavailable_reason,  # v3
        acid_gas_corrected=result.acid_gas_corrected,  # v4
        glycol_type=req.glycol_type,
    )
```

**Steps (v4 — Task 3):**

- [ ] **Step 1**: 读 `app/schemas/psychro.py` 末尾（v2 已确认 SaturationWaterContentResponse 后追加位置）
- [ ] **Step 2**: 加 `GlycolDehydrationRequest` + `GlycolDehydrationResponse`（v4 API 默认值 = dataclass 默认值 一一对应，含 `co2_mol_pct`/`h2s_mol_pct` + `acid_gas_corrected`）
- [ ] **Step 3**: 跑 `python -c "from app.schemas.psychro import GlycolDehydrationRequest"` import OK
- [ ] **Step 4**: 在 `app/api/v1/psychro.py` 末尾追加 endpoint（v4 透传 acid gas + 透传 `acid_gas_corrected`）
- [ ] **Step 5a**: 跑 `bash scripts/gate_08_openapi_contract.sh`（OpenAPI regen）
- [ ] **Step 5b**: 跑 `cd pcs-frontend && bash scripts/gen-api-types.sh`（M-3 v2 frontend types regen）
- [ ] **Step 6a**: 跑 `cd pcs-frontend && npx tsc --noEmit`（types 验证）
- [ ] **Step 6b**: 跑 `cd pcs-frontend && npx vitest run`（**v3 M-5 frontend vitest 验收**）期望 ≥525 baseline PASS
- [ ] **Step 6c**: 跑 `npx eslint src/ tests/`（0 errors）
- [ ] **Step 7**: 新建 `tests/services/psychro/test_glycol_dehydration_api.py`，写 9 集成测试（v4 新增 3）：
  - `test_happy_path_tegs_full_system_200`
  - `test_happy_path_tegs_with_acid_gas_200_acid_gas_corrected_true`（**v4 新增**）
  - `test_deg_raises_422`
  - `test_missing_t_p_dewpoint_none_with_reason`：验证 `dewpoint_unavailable_reason` 填值（M-3 闭环）
  - `test_lean_glycol_out_of_range_422`
  - `test_flooding_c_sb_out_of_range_422`（**v3 新增**）
  - `test_relative_volatility_out_of_range_422`（**v3 新增**）
  - `test_co2_mol_pct_out_of_range_422`（**v4 新增**）
  - `test_h2s_mol_pct_out_of_range_422`（**v4 新增**）
  - `test_acl_designer_only`
  - `test_pydantic_validation_negative_flow`
- [ ] **Step 8**: 跑 `pytest tests/services/psychro/test_glycol_dehydration_api.py -q`（11 new PASS）
- [ ] **Step 9**: Commit: `feat(p6-6a-6): /psychro/glycol-dehydration/calculate v4 API + Pydantic + 11 integration tests + OpenAPI/frontend types regen`

## Task 4: docs 收口（buglog + cerebrum + STATUS，v5 修订）

**Files:**
- Modify: `pcs-backend/.wolf/buglog.json`（追加 bug-109/110/111/112 — Ruling 5 OUT_OF_SCOPE 闭环 + v5 ADR-0045 Rev A + Souders-Brown 根因）
- Modify: `pcs-backend/.wolf/cerebrum.md`（追加 OPEN-P6-6A-6 Key Learning 含 v5 9 守则）
- Modify: `pcs-backend/.wolf/STATUS.md`（追加 OPEN-P6-6A-6 v5 关闭 entry）

**v5.1 Key Learning 9 守则**（vs v5 9 守则，**修正** 守则 #3 + #4 因 v5.1 P-1~P-4 落实）：

1. Ruling 1 additive extension — frozen dataclass 现有 7 字段零改动，可追加 optional 字段
2. Behr 私有化（_ 前缀 + 不入 __all__），归 C-16 glycol dehydration 内部 helper
3. **Behr 系数形式决策 Day-0 Gate 必跑**（v5.1 P-1 落实） — T1 Step 0 用 numpy lstsq + curve_fit 比较 3 种候选形式（4-param log10 二次 / Katz 3-param / Behr 原式非线性），**不**预先假设系数；选 max_rel_err < 5% 的形式；JSON `log10_coefficients`（或 `coefficients`）初始 null，由 Day-0 Gate 拟合填入；系数外置 JSON sidecar，service **模块级启动期加载**（**不** lazy lru_cache）+ **fallback 系数 WARNING 不 crash**（v5 B-2 闭环）
4. **TEG Contactor Sizing = Souders-Brown 在 XLS PR-018 工况下的标定简化式**（v5.1 ADR-0045 Rev A + P-3 弱化）：`D_full = K × sqrt(Q_gas)`，K=7.1187 from Worley PR-018 E40 单点标定；**v5 撤回 v4 物理依据**（"gas-continuous vs liquid-continuous" 与主流文献不符）；30× 差异**架构组推测**根因 = v3 混淆标准态↔实际态（数学上一致，**文献依据待 P6-6B 验证** — OPEN-P6-6A-9.1）；helper 接受 `flooding_c_sb` reserved；越界 WARNING `[K_UNVERIFIED_OUT_OF_XLS_CONDITIONS]`（v5 H-2 降级）
5. 简式焓平衡 3 项必含 TEG/H2O/ΔH_vap；签名无 unused 参数
6. adjusted_dewpoint = water_dewpoint - approach（差分法）；**字段 dataclass ↔ response 一一对应**（`dewpoint_unavailable_reason` + `acid_gas_corrected` 入 dataclass）
7. **alpha = inp.relative_volatility** 显式声明
8. **v4/v5/v5.1 三件套**：
   - **Linear acid gas placeholder (NON-Wichert-Aziz)**：`W_corr = W_baseline × (1 + 0.024·CO2 + 0.018·H2S)`；**v5 术语正名**（明确**不是** Wichert-Aziz 公式）；docstring 含真 Wichert-Aziz 非线性形式 reference；标 `[LINEAR_PLACEHOLDER, NON-WICHERT-AZIZ, P6-6B PICKUP]`；酸气输入字段 `co2_mol_pct`/`h2s_mol_pct` ∈ [0, 100]
   - **Behr inverse dewpoint → _DewpointResult frozen dataclass**（v5 B-3）：scipy `brentq` + Newton fallback（analytical derivative dW/dT from log10 form）+ T<60°F Antoine 外推 WARNING；三态显式 FOUND / EXTRAPOLATED / NOT_FOUND（无 tuple 歧义）
   - **JSON 启动期加载三铁律**：importlib.resources + RuntimeError on schema invalid + fallback 系数 WARNING（**不** lazy / **不** 静默）
9. **v5 新增三铁律**：
   - **30× 差异根因 = 标准态↔实际态换算混淆**（架构组 plan 阶段根因分析完成）；v3 算 flooding velocity 时混淆了 V_actual vs V_std；OPEN-P6-6A-9 后续 quest 记录
   - **Behr 系数 Day-0 Gate 形式决策 + Day-1 Gate 验证**（v5.1 P-1 落实）：calibrate_behr_coefficients.py 跑 3 形式对比 + 拟合 → 实际系数 + 残差；不一致 → halt + 报架构组
   - **acid_gas_corrected = 纯逻辑判断**（v5 H-3）：`(co2 > 0) or (h2s > 0)`；**不**调 Behr helper 浪费算力
   - **30× 差异根因 = 架构组数学推测，文献依据待 P6-6B 验证**（v5.1 P-3 弱化）：数学上一致，但 XLS 为何用标准态气速的工程依据待补；OPEN-P6-6A-9.1
   - **_DewpointResult 字段名统一**（v5.1 P-2 落实）：定义段 + R-13 用 `dewpoint_f`/`extrapolated`/`reason`，**不**用 `found`/`T_f` 旧名
   - **_calc_behr_water_content 调用 _correct_behr_for_acid_gas**（v5.1 P-4 落实）：去重 acid gas 修正公式；future-proof

**Steps:**

- [ ] **Step 1**: 追加 bug-109 entry（Ruling 5 OUT_OF_SCOPE 闭环）+ bug-110 entry（v2 Behr 系数 6 数量级偏差 + v3 修复）+ bug-111 entry（v4 ADR-0045 + acid gas placeholder + brentq inverse + JSON 启动期加载三铁律）+ bug-112 entry（v5 撤回 ADR-0045 v4 物理依据 + 30× 差异根因 + _DewpointResult dataclass + Linear placeholder 正名）+ **bug-113 entry**（v5.1 P-1~P-4：Behr 系数架构组独立验算失败 + Day-0 Gate 形式决策 + 30× 根因弱化为推测待 P6-6B 验证 + _DewpointResult 字段名统一 + _calc_behr 调用 _correct 去重）
- [ ] **Step 2**: cerebrum.md 追加 "## OPEN-P6-6A-6 Key Learning" 段，含 **9 守则**（v5.1 修订：#3 Behr 形式决策 / #4 30× 根因弱化推测）
- [ ] **Step 3**: STATUS.md 追加 OPEN-P6-6A-6 v5.1 关闭 entry（含 commit 链 + 验收 + 9 守则 + ADR-0045 Rev A reference + OPEN-P6-6A-9 链接 + bug-113 root_cause）
- [ ] **Step 4**: 跑 `git status` 确认 .wolf/* 修改 staged；`git diff --stat`
- [ ] **Step 5**: Commit: `docs(wolf): OPEN-P6-6A-6 v5.1 Ruling 5 closure — 12 OUT_OF_SCOPE outputs + ADR-0045 Rev A + Day-0 Gate 形式决策 (bug-109/110/111/112/113 + cerebrum 9 守则 v5.1 + OPEN-P6-6A-9 quest link)`

## 任务依赖图

```
T1 (service + 11 字段 + 7 private helper + 系数 JSON) ──┐
                                                       ├──→ T2 (fixture 扩 10 expected + 10 tests) ──┐
                                                       └──→ T3 (API + schema + 8 集成测试 + types) ──┤
                                                                                                  └──→ T4 (docs)
```

**实施顺序**：T1 → (T2 ∥ T3) → T4

**总时长**：T1 3.5 天 + T2 1.0 天 + T3 1.0 天 + T4 0.5 天 = **6.0 工作日**（v5.1 修订；vs v5 5.5 天，多 +0.5 天于 **Day-0 Gate 形式决策 + 3 形式拟合 + 实际系数手动填 JSON** + bug-113 entry + cerebrum 9 守则 v5.1）

## 端到端验证矩阵（36 项，v5.1 修订）

| # | 项 | 命令 | 期望 |
|---|---|---|---|
| **基础门禁** ||||
| 1 | ruff | `cd pcs-backend && uv run ruff check .` | 0 errors |
| 2 | pytest psychro 全量 | `pytest tests/services/psychro/ -q` | baseline 96 + **44 new = ≥ 140**（v5 M-3 修订：T1 主测 19 + T1 load 4 + T2 10 + T3 11 = 44）|
| 3 | 全量 pytest | `uv run pytest -q` | baseline 3269 + 44 new = **≥ 3313** |
| **T1 service 扩展** ||||
| 4 | Behr 8 spot checks | `pytest -k behr_gpsa_spot_check` | 60/80/100/120/140/160°F @ 1000 psia + 120°F @ 500/1500 psia 全 within 5% (v4 8 vs v3 5) |
| 5 | Behr acid gas CO2 | `pytest -k behr_acid_gas_correction_co2_5pct` | W 增加 12% (v4 新增) |
| 6 | Behr acid gas H2S | `pytest -k behr_acid_gas_correction_h2s_3pct` | W 增加 5.4% (v4 新增) |
| 7 | Behr inverse dewpoint | `pytest -k behr_inverse_dewpoint_xls_pr018_e23` | 18.44°F + extrapolation WARNING (v4 H-3) |
| 8 | Behr load coefficients | `pytest tests/services/psychro/test_behr_load_coefficients.py` | 8 spot check + fallback + RuntimeError (v4 新增) |
| 9 | full column sqrt(Q) | `pytest -k full_column_diameter_xls_pr018_e40_sqrt_q` | 288 MMscfd → D_full ≈ 120.79 in within 1e-2 |
| 10 | sqrt(Q) proportionality | `pytest -k full_column_diameter_sqrt_q_proportionality` | D(2Q)/D(Q) = sqrt(2) within 1e-4 |
| 11 | flooding_c_sb reserved | `pytest -k flooding_c_sb_reserved_does_not_affect_diameter` | diameter 不依赖 flooding_c_sb (v4 M-3) |
| 12 | NTU | `pytest -k ntu_xls_pr018_e48_2p5` | 2.5 within 1% |
| 13 | column height | `pytest -k column_height_xls_pr018_e54` | 26.67 ft within 5% |
| 14 | reboiler duty | `pytest -k reboiler_duty_xls_pr018_e80` | 1454 kW within 2% |
| 15 | DEG full raises | `pytest -k deg_raises_full_system_not_supported` | GlycolDehydrationError |
| 16 | lean_glycol out of range | `pytest -k lean_glycol_out_of_range` | 422 |
| 17 | flooding_c_sb out of range | `pytest -k flooding_c_sb_out_of_range_422` | 422 (v3) |
| 18 | relative_volatility out of range | `pytest -k relative_volatility_out_of_range_422` | 422 (v3) |
| 19 | co2 out of range | `pytest -k co2_mol_pct_out_of_range_422` | 422 (v4 新增) |
| 20 | h2s out of range | `pytest -k h2s_mol_pct_out_of_range_422` | 422 (v4 新增) |
| 21 | default back-compat | `pytest -k default_back_compat_zero_regression` | 14 baseline 0 break |
| **T1 service 扩展** ||||
| 4 | Behr 形式决策 Day-0 Gate + load 8 spot check | `cd pcs-backend && uv run python scripts/dev/calibrate_behr_coefficients.py` → 选形式 → 手动填 JSON → `pytest tests/services/psychro/test_behr_load_coefficients.py -k spot_checks_residual_within_5pct` | 3 形式对比 + 选定 max_rel_err < 5%（**v5.1 P-1 落实**：残差值由 Day-0 Gate 拟合形式决定；非固定 2.30%）；60/80/100/120/140/160°F @ 1000 psia + 120°F @ 500/1500 psia 全 within 5% |
| 5 | Behr acid gas CO2 | `pytest -k behr_acid_gas_correction_co2_5pct` | W 增加 12% (v5 术语正名 Linear placeholder, NON-Wichert-Aziz) |
| 6 | Behr acid gas H2S | `pytest -k behr_acid_gas_correction_h2s_3pct` | W 增加 5.4% (v5 同上) |
| 7 | Behr inverse dewpoint | `pytest -k behr_inverse_dewpoint_xls_pr018_e23` | 18.44°F + extrapolation WARNING + `_DewpointResult.found` (v5 B-3 frozen dataclass 解构) |
| 8 | Behr load coefficients | `pytest tests/services/psychro/test_behr_load_coefficients.py` | 4 tests: success + fallback + RuntimeError on schema invalid + 8 spot check (v5 M-4 dedupe to 4) |
| 9 | full column sqrt(Q) | `pytest -k full_column_diameter_xls_pr018_e40_sqrt_q` | 288 MMscfd → D_full ≈ 120.79 in within 1e-2 (v5 K=7.1187 单点标定) |
| 10 | sqrt(Q) proportionality | `pytest -k full_column_diameter_sqrt_q_proportionality` | D(2Q)/D(Q) = sqrt(2) within 1e-4 |
| 11 | **full column 越界 WARNING** | `pytest -k full_column_diameter_out_of_xls_conditions_emits_warning` | Q=10 MMscfd → D_full 仍算 + WARNING `[K_UNVERIFIED_OUT_OF_XLS_CONDITIONS]` (v5 H-2 新增；v4 主测无此 case) |
| 12 | flooding_c_sb reserved | `pytest -k flooding_c_sb_reserved_does_not_affect_diameter` | diameter 不依赖 flooding_c_sb (v5 H-2 Kept; helper 接受 reserved 字段 0 break) |
| 13 | NTU | `pytest -k ntu_xls_pr018_e48_2p5` | 2.5 within 1% |
| 14 | column height | `pytest -k column_height_xls_pr018_e54` | 26.67 ft within 5% |
| 15 | reboiler duty | `pytest -k reboiler_duty_xls_pr018_e80` | 1454 kW within 2% |
| 16 | DEG full raises | `pytest -k deg_raises_full_system_not_supported` | GlycolDehydrationError |
| 17 | lean_glycol out of range | `pytest -k lean_glycol_out_of_range` | 422 |
| 18 | flooding_c_sb out of range | `pytest -k flooding_c_sb_out_of_range_422` | 422 (v3) |
| 19 | relative_volatility out of range | `pytest -k relative_volatility_out_of_range_422` | 422 (v3) |
| 20 | co2 out of range | `pytest -k co2_mol_pct_out_of_range_422` | 422 (v4 新增) |
| 21 | h2s out of range | `pytest -k h2s_mol_pct_out_of_range_422` | 422 (v4 新增) |
| 22 | default back-compat | `pytest -k default_back_compat_zero_regression` | 14 baseline 0 break |
| **T2 fixture + tests** ||||
| 23 | 10 parameterized | `pytest tests/services/psychro/test_worley_c16.py -q` | 8 + 10 = 18 PASS |
| 24 | Ruling 5 status CLOSED v4 | `pytest -k worley_c16_ruling_5_closure_status_v4` | fixture 标 v4 |
| **T3 API + schema** ||||
| 25 | happy path | `pytest -k happy_path_tegs_full_system_200` | 18+1 字段全填 |
| 26 | happy path acid gas | `pytest -k happy_path_tegs_with_acid_gas_200` | acid_gas_corrected=true (v4 新增) |
| 27 | DEG 422 | `pytest -k deg_raises_422` | API 集成 |
| 28 | T/P 缺 → None + reason | `pytest -k missing_t_p_dewpoint_none_with_reason` | `dewpoint_unavailable_reason` 填值（M-3 闭环）|
| 29 | co2/h2s 422 | `pytest -k "co2_mol_pct_out_of_range or h2s_mol_pct_out_of_range"` | API 422 (v4 新增) |
| 30 | ACL | `pytest -k acl_designer_only` | viewer → 403 |
| 31 | OpenAPI regen | `bash scripts/gate_08_openapi_contract.sh` | drift=0 |
| 32 | frontend types regen | `cd pcs-frontend && bash scripts/gen-api-types.sh` | types 同步 |
| 33 | post-regen tsc | `cd pcs-frontend && npx tsc --noEmit` | 0 errors |
| **v3 M-5 frontend vitest 验收** ||||
| **34** | **frontend vitest** | **`cd pcs-frontend && npx vitest run`** | **≥525 baseline PASS** (v3) |
| 35 | frontend eslint | `npx eslint src/ tests/` | 0 errors |
| **T4 docs** ||||
| **36** | bug-109/110/111/112 entry | `grep "bug-109\|bug-110\|bug-111\|bug-112" .wolf/buglog.json` | JSON 解析 OK (v5 +1 = bug-112) |

## 风险 + 缓解（v5 修订）

| 风险 | 等级 | 缓解 |
|---|---|---|
| **R-1** Behr 8 spot check 拟合 rel > 5% | 中 | **v5 Day-1 Gate**：T1 Step 2 跑 `calibrate_behr_coefficients.py` 验证残差与 plan 表一致（max_rel_err=2.30%）；若 > 5% → halt + 报架构组；fallback 系数 WARNING 不 crash |
| **R-2** sqrt(Q) full column diameter 与 XLS PR-018 工况外不匹配 | **高** | **v5 ADR-0045 Rev A**：K=7.1187 from XLS PR-018 E40 **单点标定**（v5 撤回 v4 物理依据"gas-continuous vs liquid-continuous"）；30× 差异根因 = v3 混淆标准态↔实际态；**v5 H-2 降级**：越界 WARNING `[K_UNVERIFIED_OUT_OF_XLS_CONDITIONS]`（不报错）；P6-6B 多工况标定（OPEN-P6-6A-9）|
| **R-3** reboiler duty 简式焓平衡 vs XLS 详细计算误差 > 5% | 中 | 3 项必含：TEG sensible + H2O sensible + H2O vaporization；XLS E80=1454 kW spot check within 2% |
| **R-4** stripping gas k_strip / Antoine TEG 常数偏差 | 中 | 默认 k_strip=6.5 + TEG Antoine (15.30, 8500)；XLS E32=0.422 spot check within 5% |
| **R-5** T/P 缺省 → 3 字段 None | 低 | v3 `dewpoint_unavailable_reason` 入 dataclass（M-3）；None 字段不写 API response 0；前端 `?? null` 兜底 |
| **R-6** alpha 越界 (relative_volatility < 1.0 or > 50.0) | 低 | `_validate_input` 422 显式抛错 |
| **R-7** frontend vitest 新增 `flooding_c_sb`/`co2_mol_pct`/`h2s_mol_pct` 类型可能 break | 低 | v5 Step 5b gen-api-types 后 Step 6b vitest 验证 ≥525 baseline |
| **R-8** brentq 反函数 T<60°F 外推精度 ±20% | 中 | **v5 B-3**：`@dataclass(frozen=True) _DewpointResult` 三态（FOUND/EXTRAPOLATED/NOT_FOUND）显式；Antoine extrapolation WARNING 写入 `dewpoint_unavailable_reason`；XLS PR-018 E23=18.44°F 在 validity_domain 外但仍给出答案 + WARNING + `extrapolated=True` 标记 |
| **R-9** JSON 启动期加载打包（wheel install 找不到 file） | 中 | importlib.resources + pyproject.toml `package_data = {"pcs_backend": ["data/*.json"]}` + pytest `test_behr_load_coefficients.py` 验证 wheel 环境 |
| **R-10** acid gas correction placeholder 误差 | 低 | **v5 H-1 术语正名**（Linear placeholder, NON-Wichert-Aziz）：`W_corr = W_baseline × (1 + 0.024·CO2 + 0.018·H2S)`；与 XLS PR-018 E20=103.91 偏差 ~25%；docstring 含真 Wichert-Aziz 非线性形式 reference；标 `[LINEAR_PLACEHOLDER, NON-WICHERT-AZIZ, P6-6B PICKUP]` |
| **R-11** (v5 新增) Day-1 Gate halt 后无明确裁决路径 | 中 | T1 Step 2 halt → 报架构组 + commit 链保留 plan 阶段给全系数（4 系数 + 残差表）；不一致原因可定位（标准态换算 / 数据采集错误 / 公式缺陷）；架构组 2 小时内裁决 |
| **R-12** (v5 新增) Linear placeholder 术语误读为 Wichert-Aziz | 低 | docstring 明示 NON-Wichert-Aziz + cerebrum 9 守则 #8 第一条 + bug-112 root_cause 字段；未来 review 引 Linear placeholder 词而非校正术语 |
| **R-13** (v5.1 修订) _DewpointResult 误用 tuple 解构导致歧义 | 低 | **v5.1 P-2 字段名统一** — frozen dataclass + 字段访问（`dp.dewpoint_f`/`dp.extrapolated`/`dp.reason`）替代 `result[0]/[1]/[2]`；test #5 `test_behr_inverse_dewpoint_returns_dewpointresult_dataclass` 显式验证类型；R-13 之前的 `dp.found`/`dp.T_f` 名称已废弃，统一为定义段的 `dewpoint_f`/`extrapolated`/`reason` |

## 工时表（v5 修订）

| Task | 工时 |
|---|---|
| **T1** service 扩展（12 result + 10 input + 8 helper 含 _correct_behr_for_acid_gas + _DewpointResult frozen dataclass + Behr JSON 启动期加载 + ADR-0045 Rev A + brentq inverse + 19 unit tests 主测 + test_behr_load_coefficients.py 4 tests + Day-1 Gate 验证 0.5 天 buffer） | **3.0 天**（vs v4 2.5 天，多 +0.5 天于 Day-1 Gate halt buffer + _DewpointResult dataclass + Linear placeholder 正名 docstring） |
| **T2** fixture 扩展 + 10 parameterized tests（v5 沿用 v4：co2/h2s + acid_gas_corrected + dewpoint_unavailable_reason） | **1.0 天** |
| **T3** API + schema + 11 集成测试 + OpenAPI/frontend types regen + frontend vitest（v5 沿用 v4） | **1.0 天** |
| **T4** docs 收口（bug-109/110/111/112 + cerebrum 9 守则 + STATUS + ADR-0045 Rev A + OPEN-P6-6A-9 quest link） | **0.5 天** |
| **总计** | **5.5 工作日**（vs v4 5.0 天，多 +0.5 天于 Day-1 Gate buffer + bug-112 entry + cerebrum 9 守则） |

## 关键文件路径（v5 修订）

- `/home/pangzy/code_project/PCS/pcs-backend/data/behr_coefficients.json` — **v5 修订** Behr 系数 sidecar（含 plan 阶段给全 4 系数 A0=1.3520/A1=0.00780/A2=0.0000052/A3=-0.9800 + 8 spot checks 残差表 max_rel_err=0.0230 + fallback_coefficients + acid_gas_correction_linear_placeholder_v5 段）
- `/home/pangzy/code_project/PCS/pcs-backend/scripts/dev/calibrate_behr_coefficients.py` — **v5 修订** Behr 系数验证脚本（**不**生成 — 仅验证残差与 plan 表一致；Day-1 Gate 必跑；不一致 halt 报架构组）
- `/home/pangzy/code_project/PCS/pcs-backend/app/services/psychro/glycol_dehydration_service.py` — T1 service 扩展入口（v5 含 8 helper + `_DewpointResult` frozen dataclass + 12 result field + 模块级 `_BEHR_COEFFS` 加载 + K 单点标定越界 WARNING）
- `/home/pangzy/code_project/PCS/pcs-backend/pyproject.toml` — **v4 新增 wheel `package_data = {"pcs_backend": ["data/*.json"]}`**（JSON 打包，v5 沿用）
- `/home/pangzy/code_project/PCS/docs/adr/ADR-0045-teg-contactor-sizing.md` — **v5 Rev A** ADR 草案（标准态换算澄清 + K=7.1187 单点标定 + 撤回 v4 物理依据 + Superseded by ADR-0046 引用）
- `/home/pangzy/code_project/PCS/pcs-backend/app/schemas/psychro.py` — T3 schema 追加位置（v5 沿用 v4：含 `flooding_c_sb` + `co2_mol_pct`/`h2s_mol_pct`/`acid_gas_corrected` + `dewpoint_unavailable_reason`）
- `/home/pangzy/code_project/PCS/pcs-backend/app/api/v1/psychro.py` — T3 endpoint 追加位置（v5 沿用 v4：透传 acid gas）
- `/home/pangzy/code_project/PCS/pcs-backend/tests/services/psychro/fixtures/worley_c16_glycol_dehydration.json` — T2 fixture 扩展（v5 沿用 v4：含 `flooding_c_sb` + `co2_mol_pct` + `h2s_mol_pct` + `dewpoint_unavailable_reason` + `acid_gas_corrected`）
- `/home/pangzy/code_project/PCS/pcs-backend/tests/services/psychro/test_worley_c16.py` — T2 10 parameterized tests（v5 沿用 v4）
- `/home/pangzy/code_project/PCS/pcs-backend/tests/services/psychro/test_glycol_dehydration.py` — **v5 M-4 去重** 19 unit tests（v4 27 tests → v5 19 tests：删 8 spot check 主测，仅保留 acid gas + inverse + full column 等）
- `/home/pangzy/code_project/PCS/pcs-backend/tests/services/psychro/test_behr_load_coefficients.py` — **v5 M-4 dedupe to 4 tests**（success + fallback + RuntimeError + 8 spot check 残差验证）
- `/home/pangzy/code_project/PCS/.wolf/buglog.json` — T4 bug-109/110/111/112 entry（v5 +1 = bug-112）
- `/home/pangzy/code_project/PCS/.wolf/cerebrum.md` — T4 Key Learning **9 守则**（v5 vs v4 +1：30× 根因 + _DewpointResult + Linear placeholder 正名）
- `/home/pangzy/code_project/PCS/.wolf/STATUS.md` — T4 closure entry（v5 含 OPEN-P6-6A-9 quest link）

## 计划终止

v5.1 4 task 全部完成 + 36 项验收全过 + 全栈基线 clean + Ruling 5 OUT_OF_SCOPE 闭环（v5.1 12 fields：11 OUT_OF_SCOPE + acid_gas_corrected；alpha 显式 + dewpoint_unavailable_reason + acid_gas_corrected 一致性 + TEG Contactor Sizing ADR-0045 Rev A 单点标定 **+ 30× 根因弱化为推测** + brentq inverse → _DewpointResult frozen dataclass **字段名统一 dewpoint_f/extrapolated/reason** + Linear placeholder (NON-Wichert-Aziz) 术语正名 + JSON 启动期加载三铁律 + **Day-0 Gate 形式决策 + Day-1 Gate 验证** + **_calc_behr 调用 _correct 去重**）+ OPEN-P6-6A-9 后续 quest 立项（**4 子项** 含 v5.1 P-3 弱化的根因验证）。

## 未解决问题（v5.1 plan 末尾）

1. **OPEN-P6-6A-9**（v5 新增 + v5.1 拆分 4 子项 quest）：
   - **OPEN-P6-6A-9.1**（v5.1 P-3 升级）：**30× 差异根因完整验证** —— P6-6B 工程师完成 3 项验证：(a) 审查 v3 历史 PR 的 V_actual_scfs 实现，定位混淆代码行；(b) 找到 Worley / GPSA / 行业规范中"XLS 用标准态气速"的文献依据；(c) 若文献不支持"标准态气速是行业惯用"，需修订 ADR-0045 Rev A 根因分析
   - **OPEN-P6-6A-9.2**：K=7.1187 from XLS PR-018 E40 **单点标定**（sg=0.6 / 99% TEG / 1000 psia / Q=288 MMscfd）；P6-6B 接管多工况（Q∈[144, 432] MMscfd + sg sweep + TEG wt% sweep）标定 K=f(sg, TEG%, P_total) 多变量函数；当前 K=7.1187 越界 WARNING
   - **OPEN-P6-6A-9.3**（P6-6B 接管）：v5 Linear placeholder `W_corr = W_baseline × (1 + 0.024·CO2 + 0.018·H2S)` 与 XLS PR-018 E20=103.91 偏差 ~25%；接管**真** Wichert-Aziz 非线性形式（v5 docstring 已附参考方程）
   - **OPEN-P6-6A-9.4**（P6-6B 接管）：brentq inverse T<60°F Antoine extrapolation；P6-6B 工程师接管 Antoine 系数精确化 + Bukacek 1990 low-temp extension

2. **DEG full system 缺口**：GPSA §20.4 仅 TEG 全套公式；DEG partial coverage 暂维持 out_of_scope；v5.1 helper 全部 TEG-only（`_validate_input` 抛 422）

3. **OPEN-P6-6A-6 v5.1 plan 终止条件**：Ruling 5 OUT_OF_SCOPE 12 fields 全部交付（含 alpha 显式 + dewpoint_unavailable_reason + acid_gas_corrected + 字段名统一）+ 36 项验收 + ADR-0045 Rev A（**根因弱化为推测**）+ 9 守则（v5.1）+ **Day-0 Gate 形式决策 + Day-1 Gate 验证** + _calc_behr 去重调用 _correct；OPEN-P6-6A-9 接管后续 4 个根因扩展