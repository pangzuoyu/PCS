# T5 综合能耗验收 — 电折标口径违反 GB 30251-2024，待工艺室裁决 (2026-10-05)

**状态**: ⚠️ **BLOCKER — 需工艺室裁决后才能封版**  
**关联**: T5 综合能耗 ≤2% 出厂验收 / F-P2-004 P0 / F-P0-001 R1 / GB 30251-2024 §6.1.5 + 附录A

---

## 一句话结论

查证 GB/T 2589-2020 与 GB 30251-2024 原文后确认：**蜡油加氢属炼油，按 GB 30251-2024
§6.1.5 与附录 A 注，电折标系数必须用「等价值」；PCS 当前默认 `EQUIVALENT`（当量值）选错了。**
同时 XLS 侧存在第二处问题：脚本里的三个"XLS 参考值"在原始 XLS 中**均不存在**，是自证循环产物。

---

## 问题 1：PCS 用了当量值，GB 30251 要求炼油用等价值

### 标准原文

**GB 30251-2024 §6.1.5**（PDF 第 5 页，炼油化工生产装置计算通则）：
> 炼油、乙烯能耗计算中电折标系数采用**等价值**，其余产品电折标系数采用当量值。

**GB 30251-2024 附录 A 表 A.2**（第 1201 行）：
> 电力(当量值) 0.1229 kgce/(kW·h)
> 电力(等价值) **按上年电厂发电标准煤耗计算**
> 电力(等价值) **按供热煤耗计算**（热力）
> 注: 炼油、乙烯能耗计算中电力折标准煤系数选择等价值、其余产品电力折标准煤系数选择当量值。

**GB/T 2589-2020 §3.2**（能量当量值定义）：
> 不同形式的能量相互转换时的相当量。按照能量的法定计量单位焦耳，热能、电能、机械能等
> 不同形式的能量，其相互之间的换算系数均为 1。

### 系数换算验证（已自洽，无需修正）

| 口径 | 系数 | 换算 | 验证 |
|------|------|------|------|
| GB/T 2589 表 A.2 当量值 | 0.1229 kgce/kWh | × 29.3076 MJ/kgce | = **3.6019 MJ/kWh** ≈ 3.6 ✅ |
| PCS R1 `EQUIVALENT` | 0.086 kg**标油**/kWh | × 1.4286 kgce/kg标油 | = **0.1229 kgce/kWh** ✅ 与标准**完全一致**（偏差 0.0%） |
| PCS R1 `EQUIVALENT_VALUE` | 0.21 kg标油/kWh | = 0.30 kgce/kWh | 等价值，合理区间 0.26–0.33 kgce/kWh ✅ |
| XLS `能耗!F26` | 10.89 MJ/kWh | = 0.26 kg标油/kWh = 0.3716 kgce/kWh | 等价值，但比供电煤耗 0.30 高 24% ⚠️ |

→ **PCS 的两个系数本身都正确，问题是默认值选错**。`EQUIVALENT` 用于非炼油产品才合规。

### 对 T5 结果的影响

| 项 | 当量值 EQUIVALENT | 等价值 EQUIVALENT_VALUE |
|----|-------------------|------------------------|
| 电 toe | 3,419.8 t | 8,350.7 t（+4,930.9 t） |
| 电 MJ（PCS 现逻辑 `kWh × 3.6`） | 143,154,133 | 143,154,133（**不变**） |

**发现第二个缺陷**：`utility_energy_summary_service.py:441` 的
`electricity_mj = agg.electricity_kwh_yr * KWH_TO_MJ` **恒用 SI 3.6 MJ/kWh，
与 `electricity_value_type` 无关**。

这在当量值下自洽（3.6 ≈ 0.086 × 41.868 = 3.60），但在等价值下**自相矛盾**：
toe 用了 0.21（隐含 8.79 MJ/kWh），MJ 却仍是 3.6 → 同一份数据里 toe 与 MJ 差 2.44 倍。

`iso_self_consistent_pct = 0.0033%`（当前 PASS 这个诊断）只在当量值下成立，
**换成等价值后该诊断会失效**。

---

## 问题 2：三个"XLS 参考值"在原始 XLS 中不存在

脚本 `p7_open_012_t5_r1_verification.py:181-185` 的 `xls_reference`：

| 参考值 | 在 XLS 中搜索结果 |
|--------|------------------|
| `annual_total_energy_mj = 1,242,159,527.8` | ❌ **不存在**（全表 273 个 >1e8 数值中无匹配） |
| `total_toe_tonne = 28,532.8967` | ❌ 不存在（最接近 `物流参数!F41=28857`，差 1.1%） |
| `total_standard_coal_kg = 40,761,279.4` | ❌ 不存在（最接近 `安全阀数据源!CF99=-40,100,000`，差 1.6%） |

### 证据：参考值 = 旧代码输出的反抄

git 二分结果（`xls_reference` 在 9887ad9 前后未变，但 computed 变了）：

| commit | 代码状态 | computed MJ | xls_reference | 偏差 |
|--------|---------|------------|---------------|------|
| `6d74fdd` | R0 硬编码 38/2778 | 1,242,159,517.0 | 1,242,159,527.8 | **0.000 %**（差 10.8 MJ） |
| `94c1e55` | F-P2-004 P0（ISO 41.868） | 1,194,575,469.2 | 1,242,159,527.8 | 3.831 % |

**参考值与旧代码输出只差 10.8 MJ（相对 8.7e-7 %）** —— 是把旧代码的输出抄成了"参考值"。

### XLS 自己的能耗 sheet 也是坏的

`能耗` sheet 公式（原始 `.xlsx`，非 `.xlsm`）：
```
G21..G32 = D(消耗) × F(折算因子) / 125        ← 单位 MJ/t原料，125 = 原料 t/h
G33 = SUM(G21:G32)                            ← 实测值 #VALUE!
G34 = G33 / 41.868                            ← XLS 自己用 ISO 41.868 ✅ 与 PCS 一致
D32 = 燃料消耗校核!D15 / 1000                  ← 标准燃料量，实测值 #VALUE!
```

`G33` 因 `D32` 是 `#VALUE!` 而**无法算出年总能耗**。

XLS 折算因子（`能耗!F21:F32`）：

| 项 | 因子 | PCS 对应 | 一致? |
|----|------|---------|-------|
| 标准燃料 | 41868 MJ/t | 41.868 MJ/kg标油 | ✅ |
| 1.0MPa 蒸汽 | 3182 MJ/t | 76.0 toe/t × 41.868 = 3182 | ✅ |
| 0.3MPa 蒸汽 | 2763 MJ/t | — | — |
| **电** | **10.89 MJ/kWh**（等价值 0.3716 kgce/kWh） | — | ⚠️ 见问题 1 |
| 循环水 | 4.19 MJ/t | PCS 计 0（水非能源载体） | ❌ 口径不同 |
| 除氧水 | 385.19 MJ/t | 同上 | ❌ |
| 净化空气 | 1.59 MJ/Nm³ | PCS 仪表空气 0.038 toe | 量级差 |
| 氮气 | 0.15 MJ/Nm³ | PCS 0.15 toe/Nm³? | 需核对 |

→ XLS 口径含**耗能工质折算**（水/空气按 MJ/t 计入），PCS 口径不计（水/气体 MJ = 0）。
**这是第三处口径差异**。

---

## 三处口径差异汇总

| # | 项 | PCS | XLS | GB 标准 | 判定 |
|---|---|-----|-----|--------|------|
| 1 | 电折标 | 默认当量值 0.086 | 等价值 0.3716 kgce/kWh | 炼油必须等价值 | ❌ **PCS 违约** |
| 2 | 耗能工质（水/空气/氮气）MJ | 0 | 计入（4.19 / 1.59 / 0.15 等） | GB 30251 未强制 | ⚠️ 需裁决 |
| 3 | 电的 MJ 表达 | 恒 `kWh × 3.6` | `kWh × 折算因子` | — | ❌ **PCS 内部矛盾**（等价值下） |

外加：三个参考值本身不来自 XLS（问题 2）。

---

## 待工艺室裁决

### Q1（最关键）：电的口径

GB 30251-2024 明确规定炼油用等价值。需确认：

1. PCS 的 `electricity_value_type` 默认值是否应从 `EQUIVALENT` 改为 `EQUIVALENT_VALUE`，
   或在炼油项目类型下强制 `EQUIVALENT_VALUE`？
2. 等价值系数取多少？GB 说"按上年电厂发电标准煤耗计算"：
   - PCS R1 现用 0.21 kg标油/kWh = 0.30 kgce/kWh
   - XLS 用 10.89 MJ/kWh = 0.3716 kgce/kWh
   - 两者差 24%，需统一到同一份"上年发电煤耗"依据
3. `annual_total_energy` 的电 MJ 应改为 `kWh × toe_factor × 41.868`（跟随 value_type），
   还是保持 `kWh × 3.6`（纯物理能量，与折标口径解耦）？
   **若保持 3.6，toe 与 MJ 在等价值下会差 2.44 倍，验收脚本的 `iso_self_consistent_pct` 诊断失效。**

### Q2：耗能工质是否计 MJ

XLS 把循环水 4.19 MJ/t、除氧水 385.19 MJ/t、净化空气 1.59 MJ/Nm³ 等计入年总能耗；
PCS 全部计 0。GB 30251-2024 对此无强制规定（只规定折标准煤系数）。

需确认：PCS 是否应增加耗能工质 MJ 折算？若需要，`ConfigEnergyConversionFactor`
需新增 `unit_to_mj` 列（不能复用 `toe_factor × 41.868`，因为水 toe 0.06 但 MJ 是 4.19）。

### Q3：XLS 基准值重出

三个参考值不来自 XLS，且 XLS 的 `G33` 合计因 `D32=#VALUE!` 算不出来。
需工艺室：
- 修复 `燃料消耗校核!D15`（或提供直接的标准燃料量）
- 重新导出年总能耗基准
- 或书面确认"XLS 不作为 MJ 基准，PCS 内部自洽即可"

---

## 建议路径

### ✅ 已完成（代码侧，GB 30251 强制项，无需等待裁决）

1. **T5 脚本显式用等价值** — `p7_open_012_t5_r1_verification.py:176-180`
   加 `electricity_value_type="EQUIVALENT_VALUE"`（蜡油加氢 = 炼油，GB 30251 §6.1.5 强制）。
2. **修电 MJ 口径 bug** — `utility_energy_summary_service.py:441`
   `electricity_mj` 从恒 `kWh × 3.6` 改为跟随 `value_type`：
   - `EQUIVALENT`（当量值，GB/T 2589 §3.2 物理当量）→ `kWh × 3.6`
   - `EQUIVALENT_VALUE`（等价值，炼油强制）→ `kWh × toe_factor × 41.868`

   **修正前** 等价值下 `iso_self_consistent_pct = 21.09%`（toe 与 MJ 差 2.44 倍）；
   **修正后** `iso_self_consistent_pct = 0.0%`（严格自洽）。
3. **回归测试** — `test_utility_energy_summary.py` 的
   `test_electricity_value_type_persisted` 追加两条自洽性断言
   （两口径下 `annual_total_energy == total_toe × 1000 × 41.868`）。

**验证**：后端 3716 passed（零新增 regression）、util energy 16/16 passed。

### ⏳ 待裁决（Q1 等价值系数取值 / Q2 耗能工质 MJ / Q3 XLS 基准重出）

4. **Q1**：等价值系数取多少？PCS R1 用 0.21 kg标油/kWh（0.30 kgce/kWh），
   XLS 用 10.89 MJ/kWh（0.3716 kgce/kWh）—— **两者差 24%**，需统一到同一份
   "上年电厂发电标准煤耗"依据。这是剩余偏差的主要来源。
5. **Q2**：耗能工质（水/空气/氮气）是否计 MJ（XLS 计，PCS 计 0）。
   若需要，CONFIG 需新增 `unit_to_mj` 列（不能复用 `toe_factor × 41.868`）。
6. **Q3**：换掉伪造的参考值（XLS 的 `G33` 因 `D32=#VALUE!` 算不出年总能耗）。
7. 三项全 PASS 后 T5 正式封板 + git tag。

**注意**：在 Q1/Q2/Q3 裁决完成前，**不得**为了让验收变绿而修改 PCS 折标系数或编造新的参考值
——F-P2-004 P0 拆穿假 PASS 已经证明这条路走不通。

---

## 修正后的当前 T5 结果（等价值）

```
annual_total_energy   : 偏差 21.87%   FAIL
total_toe             : 偏差 26.72%   FAIL
total_standard_coal_kg: 偏差 26.72%   FAIL
iso_self_consistent   : 0.0%         ← PCS 内部完全自洽 ✅
```

三项偏差 21-27% **全部来自 Q1（等价值系数 0.21 vs XLS 0.3716 kgce/kWh，差 24%）**。
PCS 侧已无可修正项——继续改 PCS 只会重演"为绿而改"的覆辙。

---

## 复现方式

```bash
cd pcs-backend
DATABASE_URL="postgresql+psycopg://pcs:pcs_dev@localhost:5432/pcs_test" \
  uv run python scripts/p7_open_012_t5_r1_verification.py
```

XLS 原始口径核对（`sample/1216D132惠州蜡油加氢装置计算14.7.17计算 - 副本.xlsx`）：
```python
import openpyxl
wb = openpyxl.load_workbook('.../1216D132....xlsx', data_only=False)
ws = wb['能耗']
for r in range(21, 35):
    print([ws.cell(r, c).value for c in (2, 4, 6, 7)])
```

标准原文定位：
```bash
pdftotext -layout sample/GB+30251-2024.pdf - | grep -n "等价值"   # §6.1.5 + 附录A 表 A.2
pdftotext -layout sample/综合能耗计算通则.pdf - | grep -n "0.1229" # GB/T 2589 表 A.2
```

---

## 关联

- **标准原文**: `sample/GB+30251-2024.pdf`（§6.1.5 第 5 页 / 附录 A 表 A.2 第 1201 行）、
  `sample/综合能耗计算通则.pdf`（GB/T 2589-2020，§3.2 / 附录 A 表 A.1+A.2 第 245 行）
- **T5 PASS 原始报告**: commit `9887ad9`（2026-10-02 09:48）
- **F-P2-004 P0 修正**: commit `94c1e55`（2026-10-02 17:55，删 `NM3_FUEL_GAS_TO_MJ=38` /
  `T_STEAM_TO_MJ=2778`，改 CONFIG `toe_factor × TOE_TO_MJ(41.868)`）
- **R1 签署**: `docs/PCS-SIGN-F-P0-001-2026-10-08-R1.md`（工艺室 5 签齐）
- **黄金 fixture 的旧口径**: `pcs-backend/tests/services/util/fixtures/golden_utility_energy_summary.json`
  `_meta.notes` 写明 `unit_to_mj: 1kWh=3.6MJ / 1Nm³=38MJ / 1t=2778MJ`（R0 残留，已被 P0 作废）
- **BLOCKER-2 背景**: `docs/PCS-NOTE-BLOCKER-2-2026-10-01.md`
- **XLS 源**: `sample/1216D132惠州蜡油加氢装置计算14.7.17计算 - 副本.xlsm` / `.xlsx`

---

## 待办

- [ ] Q1 电口径裁决（炼油用等价值 — GB 30251 强制；等价值系数取值；电 MJ 是否跟随 value_type）
- [ ] Q2 耗能工质（水/空气/氮气）是否计 MJ
- [ ] Q3 XLS 基准值重出（修复 `燃料消耗校核!D15` 或书面确认不作为基准）
- [ ] 按裁决修 `utility_energy_summary_service.py:441` + CONFIG 表
- [ ] 重跑验收确认三项全 PASS
- [ ] T5 正式封板 + git tag
- [ ] T6 catalyst_loading fixture（独立 BLOCKER-2 残余）
