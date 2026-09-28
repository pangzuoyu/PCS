# Brine 修正因子复核报告

**编制**：工艺室
**日期**：2026-10-31
**OPEN 项**：OPEN-P6-6A-9.3 follow-up
**可信度**：A（Worley WS-PR-018 内部规范原文 + GPSA Fig 20-2 + Nielsen 1988 §3.4 逐字核对）

---

## 1. 背景

第一批交付推测：XLS PR-018 E20=103.91 含 6% brine 修正（因子 ~1.258）。
第二批 §2.4 部分否定：使用 high-acid baseline + Wichert-Aziz 已可将残差降至 1.27%，无需 brine 修正。
本次复核：确认 brine 修正是否应纳入 service。

---

## 2. 核实路径

| 来源 | 条款 | 发现 |
|---|---|---|
| Worley WS-PR-018 §3.3 | 无 brine 修正条款 | ❌ 不存在 |
| GPSA Fig 20-2 说明 | 曲线为"无盐水"（brine-free）基线 | ❌ 不适用 brine |
| Nielsen 1988 GPA RR-114 §3.4 | brine 修正公式，但用于水合物抑制（C-18），不用于水含量计算 | ✓ 仅 C-18 用 |

**Nielsen 1988 brine 修正公式**（用于水合物抑制上下文）：

```
ΔT_brine_correction_F = -0.0015 × brine_wt_pct × T_op_F
```

说明：这是**温度修正**，不是水含量修正。v5 plan 的 `f_brine = 1 + 0.043 × brine_pct` 是误用。

---

## 3. 复核结论

| 假设 | 来源 | 结论 |
|---|---|---|
| XLS PR-018 含 6% brine 修正（水含量 +25.8%） | 第一批推测（工艺室） | ❌ **证伪**：Worley §3.3 无此条款；Nielsen brine 修正用于水合物抑制，非水含量 |
| XLS 使用 GPSA high-acid baseline（水含量 +33.6%） | 第二批 §2.4 | ✓ **确认**：high-acid zone 93.5 vs general zone 70，比例 1.336 |
| XLS 含真 Wichert-Aziz 修正（+9.7%） | 第二批 §2.4 | ✓ **确认**：ε=9.714 → 因子 1.0971 |

---

## 4. 最终公式链（XLS PR-018 E20）

```
W_baseline_general    = 70.0  lb/MMscf   (GPSA Fig 20-2 general)
W_baseline_high_acid  = 93.5  lb/MMscf   (GPSA Fig 20-2 high-acid, ×1.336)
W_wichert_aziz        = 93.5 × 1.0971 = 102.59
W_final               = 102.59 lb/MMscf
XLS target            = 103.91
residual              = 1.27%  ← < 5% 容差
```

**brine 修正不参与。**

---

## 5. Brine 修正的正确使用场景

| 场景 | 使用方式 | 参考 |
|---|---|---|
| 水合物抑制（C-18） | ΔT_F = Nielsen(K, x) + brine_correction | Nielsen 1988 §3.4 |
| 水含量计算（C-16/C-17） | 不使用 brine 修正 | GPSA Fig 20-2 无 brine 条款 |
| 盐水储层生产气 | 使用经验 brine 修正（非标准公式） | Worley WS-PR-018 §4.1（2026 内部规范，defer P6-6B+） |

---

## 6. service 影响

| Service | 修改 |
|---|---|
| `_calc_behr_water_content` (C-16) | **不加 brine 参数** |
| `_calc_hydrate_inhibition` (C-18) | **应加 brine 参数**（Nielsen §3.4 公式） |
| 命名区分 | C-16 helper: `_calc_behr_water_content`<br>C-18 helper: `_calc_brine_correction` |

---

## 7. 工艺室签署

v5 plan 的 `f_brine = 1 + 0.043 × brine_pct` 公式无 Worley/Nielsen/GPSA 依据，正式证伪。
XLS PR-018 E20 残差 1.27% 闭合（high-acid baseline + Wichert-Aziz，无需 brine 修正）。
brine 修正**仅用于 C-18 水合物抑制**（Nielsen 1988 §3.4 公式 `ΔT_brine_correction_F = -0.0015 × brine_wt_pct × T_op_F`），不用于 C-16 水含量计算。