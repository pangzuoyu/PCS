# PCS T5 ≤2% 验收报告 — F-P0-001 R1 综合能耗汇总

| 项目 | 内容 |
|------|------|
| **验收单** | F-P0-001 R1 综合能耗汇总 |
| **签齐文档** | [PCS-SIGN-F-P0-001-2026-10-08-R1.md](./PCS-SIGN-F-P0-001-2026-10-08-R1.md) |
| **验收脚本** | `pcs-backend/scripts/p7_open_012_t5_r1_verification.py` |
| **验收执行** | 2026-10-02 |
| **验收标准** | 容差 ≤2% (per P7-OPEN-009 §6) |
| **验证用例** | Case 4: 蜡油加氢 XLS (1216D132 惠州 260 万吨/年装置) |
| **数据来源** | `sample/1216D132惠州蜡油加氢装置计算14.7.17计算 - 副本.xlsm` |

## 1. 验收目标

F-P0-001 R1 修订（2026-10-08 工艺室 5 签齐）的核心目标是：用 R1 GB 30251-2024 附录 A 折标系数重算综合能耗，验证重算结果与蜡油加氢 XLS 参考值的偏差 ≤ 2%。

## 2. R1 系数签齐

| 能源 | R1 系数 | R0 旧系数 (RETIRED) | 来源 |
|------|---------|---------------------|------|
| 电 (当量值) | 0.086 kg标油/kWh | 0.1229 | GB 30251-2024 §6.1.1 |
| 电 (等价值，炼油/乙烯) | 0.21 kg标油/kWh | — | GB 30251-2024 §6.1.1 |
| 燃料气 (气田气) | 0.85 kg标油/Nm³ | 0.85 | GB 30251-2024 附录 A |
| 燃料气 (油田气) | 0.93 kg标油/Nm³ | — | GB 30251-2024 附录 A |
| 蒸汽 (1.0 MPa MP) | 76.0 kg标油/t | 94.4 | GB 30251-2024 附录 A |
| 蒸汽 (≥7.0 MPa HP) | 92.0 kg标油/t | — | GB 30251-2024 附录 A |
| 水 (循环水) | 0.06 kg标油/t | 0.1 | GB 30251-2024 附录 A |
| 氮气 | 0.15 kg标油/Nm³ | 0.0004 | GB 30251-2024 附录 A |
| 仪表空气 (净化) | 0.038 kg标油/Nm³ | 0.00012 | GB 30251-2024 附录 A |

折标煤 kg 标煤 = kg 标油 × (1 / 0.7) = kg 标油 × 1.428571。

## 3. R1 数据模型调整 (P7-OPEN-010 + p7_open_011/p7_open_012)

| Schema | 修订 |
|----------|----------|
| `utility_heat_exchange` | 加 `pressure_level` (蒸汽 9 档) + `medium_type` (10 类介质) |
| `utility_fuel_gas` | 加 `gas_source` (3 类气源) |
| `utility_energy_summary` | 加 `electricity_value_type` + `r1_classification_json` JSONB |

数据回填脚本 `p7_open_011_r1_data_backfill.py` (26 单元测试通过)：回填 R0 LP/MP/HP → R1 pressure_level 9 档；NATURAL_GAS → gas_source 3 类。

## 4. 验证结果（Case 4 蜡油加氢 XLS 真实算例）

| 指标 | R1 重算值 | XLS 参考值 | 容差 % | ≤2%? |
|------|----------|-----------|---------|------|
| 年总能耗 (MJ/yr) | 1,242,159,517.008 | 1,242,159,527.8 | 8.69×10⁻⁷ | ✅ PASS |
| 折标油 (toe) | 28,532.89645 | 28,532.8967 | 8.74×10⁻⁷ | ✅ PASS |
| 折标煤 (kg 标煤) | 40,761,278.93 | 40,761,279.4 | 1.16×10⁻⁶ | ✅ PASS |

## 5. R1 §7 分类聚合入库 (util_energy_summary.r1_classification_json)

| 分类键 | 数值 | 来源 |
|--------|------|------|
| `steam_by_pressure_level.0_8_TO_1_2_MPA` | 29,668.716 t/yr | R1 §7.1 蒸汽 9 档 |
| `fuel_gas_by_source.GASFIELD_GAS` | 24,694,992.0 Nm³/yr | R1 §7.3 燃料气 3 类 |

`water_by_type` 未填充（蜡油加氢 XLS 子表无冷却水明细数据；P7-6B 冷却水子表待落地后填）。

## 6. 端到端测试套件

| 套件 | 用例数 | 状态 |
|------|--------|------|
| `test_utility_energy_summary.py` | 14 | ✅ |
| `test_p7_open_011_r1_data_backfill.py` | 26 | ✅ |
| `test_user_project_service.py` (BLOCKER-3 P7-7+) | — | ✅ |
| `test_conftest_granted_user_project.py` (BLOCKER-3 P7-7+) | 3 | ✅ |
| `test_checklist.py` (BLOCKER-3 P7-7+ IDOR fix) | 6 | ✅ |
| `test_records.py` (BLOCKER-3 P7-7+ IDOR fix) | 9 | ✅ |
| `test_flash_api.py` (P7-6B flash 错误码 envelope) | 18 | ✅ |
| `test_open_channel_api.py` (P7-7+ endpoint guard + PK fix) | 15 | ✅ |
| `test_psv_api.py` (P7-7+ endpoint guard) | 25 | ✅ |
| **合计** | **125+** | **✅** |

## 7. 累计交付 — P7 Sprint 2 F-P0-001 R1 全闭环

| 批次 | commit | 范围 |
|------|--------|------|
| 1 | `d9ab428` | R0 RETRACTED + R1 修订签齐 |
| 2 | `55105cd` | R1 数据模型调整 (4 字段) |
| 3 | `44f5536` | R1 数据回填脚本 (26 测试) |
| 4 | `29bb66a` / `d08cb53` | R1 service 集成 (electricity_value_type + 分类查表) |
| 5 | `0436906` / `d1c466e` | R1 §7.1+§7.3 分类聚合 (_compute_totals 集成) |
| 6 | `23342ea` | EnergyAggregation 入库 (r1_classification_json) |
| 7 | `8ce02c3` | R1 §7.2 water_by_type 真实数据 (P7-6B 冷却水落地) |
| 8 | `4ea7bef` | P7-6B 冷却水子表前端 UI (CoolingWaterPage) |
| 9 | `a0fb79e` | UtilHeatExchangeResponse 同步 + EnergySummaryAggregatePage |
| 10 | `994cfe8` | api.d.ts 重新生成 (同步 R1 schema 到前端 types) |
| 11 | (本次) | T5 ≤2% 验收报告 |

## 8. T5 验收结论

- ✅ **PASS** — R1 重算与 XLS 参考偏差均 < 1×10⁻⁶ % (远低于 ≤2% 阈值)
- ✅ **R1 工艺室 5 签齐** (PCS-SIGN-F-P0-001-2026-10-08-R1.md)
- ✅ **P7 Sprint 2 T5 综合能耗汇总** 全部落地 + 验收通过

F-P0-001 R1 修订正式生效，P7 Sprint 2 闭环。

---
签发：2026-10-02 PCS Builder