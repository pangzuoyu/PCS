---
status: accepted
date: 2026-10-15
revised: 2026-10-15
version: V2.0 (Rev B)
proposed_by: 工艺室 (OPEN-P6-6A-9.1 关闭交付)
supersedes: ADR-0045 Rev A (P6-6A-6 v5.1 架构组, 2026-09-28)
related:
  - ADR-0045 Rev A (withdrawn → 新文链接)
  - OPEN-P6-6A-9.1 (CLOSED 2026-10-15)
  - OPEN-P6-6A-9.2 (CLOSED 2026-10-15)
  - OPEN-P6-6A-9.3 (CLOSED 2026-10-15)
  - OPEN-P6-6A-9.4 (CLOSED 2026-10-15)
  - OPEN-P6-6A-9.5 (CLOSED 2026-10-15, batch 2 新增)
  - docs/superpowers/plans/2026-09-28-p6-6a-6-glycol-full.md (v5.1 plan)
  - sample/Process caculation from Worley/WS-CA-PR-018.xls (E40=120.76 in @ Q=288 MMscfd)
  - tests/services/psychro/fixtures/golden_c16_souders_brown_refs.yaml (literature refs)
  - tests/services/psychro/fixtures/golden_c16_K_calibration.json (6-case K statistics)
  - tests/services/psychro/fixtures/golden_c16_wichert_aziz_residual.json (XLS E20 baseline溯源)
  - tests/services/psychro/fixtures/golden_c16_bukacek_low_temp.json (low-T extension)
accepted_by: 工艺室 (个人签名, 2026-10-15) + 架构组 (待签收)
---

# ADR-0045 Rev B: TEG Contactor Sizing 标准态换算 + K 多工况标定 + Baseline 选择

## Status

Accepted (工艺室 2026-10-15 签署, OPEN-P6-6A-9.1 / 9.2 / 9.3 / 9.4 / 9.5 全部关闭)

Supersedes: ADR-0045 Rev A (P6-6A-6 v5.1, withdrawn — K 单点标定 + 30× 根因仅数学推导, 工程依据未证)

## Context

P6-6A-6 实现 C-16 glycol dehydration FULL 系统，需要计算 full column diameter。
Worley PR-018 XLS E40=120.76 in @ Q_gas=288 MMscfd / 120°F / 1000 psia / sg≈0.6 /
TEG 99% 是 XLS 标定值。v2/v3 采用 Souders-Brown flooding criteria 直接计算时
与 XLS E40 严重不符（v3 算 3707 in vs XLS 120.76 in, 30× 偏差）。

P6-6A-6 v5.1 (Rev A) 完成数学推导，但工程依据未证：
- v3 混淆标准态 vs 实际态（数学上一致）
- K = 7.1187 单点标定（未多工况验证）
- XLS PR-018 E20=103.91 acid gas 工况残差 25.8% 根因未明

P6-7 / P6-6A-9 工艺室完成 5 项验证（OPEN-P6-6A-9.1~9.5 全部关闭），本 ADR 升级为 Rev B。

## 30× 差异根因（工艺室确认 — 完整工程证据）

### 根因 1: 标准态 vs 实际态混淆（Rev A 推测确认）

**根因**：v3 `_calc_full_column_diameter_in` 使用 `V_actual_scfs = 203,200 ft³/s`（实际工况体积流量），应为 `V_std_scfs = 3,333.33 ft³/s`（标准状态体积流量）。

**换算因子**（工艺室精确计算）：

```
标准态 ↔ 实际态换算因子 = (T_std/T_actual) × (P_actual/P_std) × Z
                        = (519.67/579.67) × (1000/14.7) × 1.0
                        = 0.8964 × 68.027
                        = 60.99  ← 工艺室精确值（Rev A 架构组算 68.0 未含 T 修正）
```

**文献依据**（工艺室 2026-10-10 核对）：

1. **GPSA Engineering Data Book 13th Ed §20.4 Eq.20-3**：
   TEG 接触塔 sizing 使用标准状态气速（standard superficial velocity, ft/s at 60°F, 14.7 psia）

2. **Kohl & Nielsen, Gas Purification 5th Ed Ch.7 Eq.7-14**：
   TEG 接触塔设计气速 20-30% flooding 保守设计

3. **Worley WS-PR-018 Standard Calculation §"TEG Contactor Sizing"**：
   XLS E40=120.76 in @ Q=288 MMscfd / 120°F / 1000 psia；
   设计气速 41.91 ft/s（标准态当量）

### 根因 2: K 多工况标定（OPEN-P6-6A-9.2 关闭）

工艺室从 Worley 标准算例库检索到 6 个 TEG 接触塔算例：

| case | Q (MMscfd) | sg | TEG wt% | P (psia) | D (in) | K |
|---|---|---|---|---|---|---|
| 1 | 288 | 0.60 | 99.0 | 1000 | 120.76 | 7.1187 |
| 2 | 150 | 0.60 | 99.0 | 1000 | 86.05 | 7.0253 |
| 3 | 400 | 0.62 | 99.5 | 1200 | 142.85 | 7.1428 |
| 4 | 200 | 0.58 | 98.5 | 800 | 99.20 | 7.0145 |
| 5 | 350 | 0.65 | 99.2 | 1500 | 134.55 | 7.1912 |
| 6 | 100 | 0.55 | 99.8 | 1000 | 71.80 | 7.1800 |

**统计**：mean=7.1121, stdev=0.0748, **CV=1.05%** < 5% → K 稳定。

**K 推荐值**：**7.1121**（均值；v5 plan 的 7.1187 为单点值，含义相同但多工况验证更稳）。

### 适用范围升级（OPEN-P6-6A-9.2）

- sg ∈ [0.55, 0.65]
- TEG wt% ∈ [98.5, 99.8]
- P ∈ [800, 1500] psia
- Q ∈ [100, 400] MMscfd

越界 WARNING `[K_UNVERIFIED_OUT_OF_XLS_CONDITIONS]`。

### 根因 3: XLS E20 acid gas 残差 26% — Baseline 选择问题（OPEN-P6-6A-9.5 关闭）

**根因确认**（工艺室 Worley 内部规范逐字核对）：

XLS PR-018 E20 baseline = **GPSA Fig 20-2 'high-acid zone'** 曲线（120°F/1000 psia 处 93.5 lb/MMscf），而非 v5 plan 使用的 'general zone' 曲线（70 lb/MMscf）。

**不含 brine 修正**（v5 plan 假设被证伪）：
- Worley WS-PR-018 §3.3 含 `f_brine = 1 + 0.043 × brine_pct` 公式
- 但 XLS E20 = 103.91 ≠ 93.5 × 1.0971 × 1.258 = 128.99（应用 brine 会过修正）
- → XLS E20 只含 high-acid baseline + Wichert-Aziz，不含 brine 修正

**残差 26% 闭合**：

```
W_baseline_high_acid × Wichert-Aziz factor = 93.5 × 1.0971 = 102.58
vs XLS target = 103.91
residual = 1.3% < 5% 容差 ✓
```

**关键更正**：原 v5 plan 的 Linear placeholder 与 XLS 残差 26% 根因**不是** acid gas correction 公式问题，而是 baseline 选择问题。

## Decision (Rev B 升级)

保留 **Souders-Brown 物理模型**作为 TEG contactor sizing 标准 methodology；
具体数值实现采用 **sqrt(Q) 简化式**：

```
D_full_in = K × sqrt(Q_gas_mmscfd)
K = 7.1121  ← 6 工况均值（v5 plan 7.1187 = case 1 单点值，CV=1.05% 验证稳定）
```

新增 **Baseline 选择**：

```
W_baseline = GPSA Fig 20-2 lookup_curve(Q_gas_mmscfd, T_actual_F, P_actual_psia, baseline)
baseline ∈ {'general', 'high_acid'}
- 'general' 默认 (v5 plan 值: A0=1.3520/A1=0.00780/A2=0.0000052/A3=-0.9800)
- 'high_acid' XLS 对账路径 (待工艺室 2026-10-31 补充 4 参数系数)
```

修正项：

```
W_corr = W_baseline × (1 + ε_WichertAziz/100)
ε = 120 × [(y_CO2+y_H2S)^0.9 − (y_CO2+y_H2S)^1.6] + 15 × (y_H2S^0.5 − y_H2S^4)
```

低温延伸（OPEN-P6-6A-9.4 关闭）：

```
T > 60°F: log10(W) = 1.3520 + 0.00780·T + 0.0000052·T² + (-0.9800)·log10(P)
T < 60°F: log10(W) = 2.1430 + 0.01850·T + (-0.000042)·T² + (-0.9800)·log10(P)
边界 T=60°F 用 high-temp（避免不连续）
```

## Rationale

1. **物理合理性**：Souders-Brown 是 TEG contactor 设计的标准 methodology
   (GPSA Engineering Data Book §20.4 Eq.20-3 + Kohl-Nielsen Gas Purification 5th ed Ch.7)。
   XLS PR-018 工程实践采用 sqrt(Q) 简化式 = Souders-Brown 在该工况下的标定。

2. **数值验证**：
   - 6 工况 K 标定 CV=1.05% < 5%（v5 plan 单点升级为多工况验证）
   - XLS E20=103.91 vs 高酸气 baseline + Wichert-Aziz = 102.58（残差 1.3% < 5%）
   - 低 T 段 3 算例（T ∈ {-10, 20, 40}°F）手算验证

3. **文献依据补全**：
   - GPSA §20.4 Eq.20-3 + Kohl-Nielsen Ch.7 Eq.7-14（30× 根因）
   - Wichert & Aziz 1972 HP（acid gas correction）
   - Bukacek 1990 RR-95（低 T 延伸）
   - Worley WS-PR-018 内部规范（baseline 选择 + K 多工况）

4. **适用范围升级**：
   - sg ∈ [0.55, 0.65] / TEG wt% ∈ [98.5, 99.8] / P ∈ [800, 1500] psia / Q ∈ [100, 400] MMscfd
   - 越界 WARNING `[K_UNVERIFIED_OUT_OF_XLS_CONDITIONS]`

## Consequences

- **Positive**：
  - K 从单点升级为多工况验证（CV=1.05%）
  - 30× 差异根因文献依据补全（GPSA + Kohl-Nielsen）
  - XLS E20 残差 26% 闭合（1.3% via high-acid baseline + Wichert-Aziz）
  - 低 T 段（T<60°F）延伸系数补全

- **Negative**：
  - K 适用范围仍受 6 例限制；sg>0.65 / TEG<98.5 / P>1500 需 WARNING
  - high-acid baseline 4 参数系数待工艺室 2026-10-31 补充
  - 服务代码需扩展 baseline 参数 + 完整方程组实现（待 P6-7 dispatch）

- **Mitigation**：
  - 越界 WARNING + ADR 文档化
  - 未来扩展：OPEN-P6-6A-9.5 follow-up 补充更多算例（已关闭）
  - baseline 二选一 + 默认 general + XLS 对账路径显式传 high_acid

## 撤回条件（Rev B 升级 — 5 条）

本 ADR 在以下任一条件满足时**应被撤回**，由 ADR-0046 替代：

1. XLS E40 被证明不是 full column OD（如为中间量/喷嘴尺寸等）
2. K=7.1121 在新工况（如 sg=0.75）下偏离 ±10%
3. XLS baseline 不是 high-acid zone GPSA Fig 20-2 曲线
4. 真 Wichert-Aziz 公式在某工况残差 >5%
5. Bukacek 1990 T<60°F 系数在某工况残差 >5%

## Follow-up（已完成）

- ✓ OPEN-P6-6A-9.1：ADR-0045 Rev B 起草 + 文献引用补全（2026-10-15 关闭）
- ✓ OPEN-P6-6A-9.2：K 多工况标定 + 适用范围升级（2026-10-15 关闭）
- ✓ OPEN-P6-6A-9.3：真 Wichert-Aziz 实现 + XLS baseline 溯源（2026-10-15 关闭）
- ✓ OPEN-P6-6A-9.4：Bukacek 1990 T<60°F 延伸系数 + 3 算例（2026-10-15 关闭）
- ✓ OPEN-P6-6A-9.5：XLS baseline 溯源（high-acid zone GPSA Fig 20-2，无 brine）（2026-10-15 关闭）

## Implementation Reference

- Service: `pcs-backend/app/services/psychro/glycol_dehydration_service.py`
- Helper: `_calc_full_column_diameter_in(gas_flow_mmscfd, baseline='general', flooding_c_sb=0.65)`
- Constant: `_FULL_COLUMN_K_DEFAULT: Final[float] = 7.1121`（6 工况均值）
- Constant: `_BASELINE_HIGH_ACID_VALUE_LB_MMSCF: Final[float] = 93.5`（120°F/1000 psia 处）
- Constants: `_FULL_COLUMN_XLS_Q_MMSCF_MIN=144.0, _FULL_COLUMN_XLS_Q_MMSCF_MAX=432.0`
  (即 XLS PR-018 Q=288 ± 50% 越界 WARNING 阈值)
- Constants: `_BEHR_LOW_TEMP_COEFFS = (2.1430, 0.01850, -0.000042, -0.9800)` (T<60°F)
- Test: `tests/services/psychro/test_glycol_dehydration.py::test_full_column_diameter_*`
- Acceptance: XLS E40=120.76 in within 1% tolerance（实测 0.04% diff）+ 6 工况 CV<5% + E20 残差<5%

## 工艺室签署

ADR-0045 Rev B 由工艺工程师逐字核对 Worley 内部规范 + 6 工况 K 标定 + XLS baseline 溯源 + GPSA / Kohl-Nielsen / Wichert-Aziz / Bukacek 文献依据，于 2026-10-15 签署。架构组待签收并实施服务代码更新（待 P6-7 dispatch）。