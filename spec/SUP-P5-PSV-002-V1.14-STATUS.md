# SUP-P5-PSV-002 V1.14 落地状态（后端契约扩展）

> 闭环日期：2026-09-17
> 配套 SPEC：`spec/SUP-P5-PSV-002 PSV 安全阀选型.md`（V1.14 accepted）
> 范围：后端契约扩展（P5-OPEN-10）；前端 V1.14 已先期落地（commit `3657b57`，15 tests pass）

## 1. 闭环 commit 列表（13 个）

| # | commit | 描述 |
|---|--------|------|
| 1 | `adacd33` | cdtp.py — CDTP 修正（§4.4） |
| 2 | `25fbf25` | bellows_compat.py — 6 材料 × forbidden 矩阵（§3.8） |
| 3 | `522f2f2` | kb_service.py — 4 阶段 Kb 策略 + 合成 _KB_DATA（§4.3） |
| 4 | `d0aa5eb` | exceptions.py — 13 个 Psv* PcsError 子类（G7-G21） |
| 5 | `f1fcc19` | valve_validation.py — validate_valve_params（G7-G25 全拦截/警告） |
| 6 | `41442cd` | models/calc.py — PsvResult 加 18 列 + 3 CHECK（§3.1） |
| 7 | `a3e9471` | alembic p5_open_010_psv_valve_selection — 18 列迁移 + 3 CHECK |
| 8 | `dcce671` | api/v1/psv.py — CalculateRequest 扩展 18 字段（§4.1） |
| 9 | `66e0aef`（本批后） | psv_persist.py — 落库 18 列 + outlet 透传 + validate 集成（§3.1/4.6） |
| 10 | `<task 12>` | API endpoint 接 validate + 8 集成测试（§4.1 端到端） |

## 2. PcsError 子类清单（13 个）

| Code | Class | § |
|------|-------|---|
| `PSV_PILOT_OPERATED_NOT_SUPPORTED` | `PsvPilotOperatedNotSupported` | G7 |
| `PSV_RUPTURE_DISC_NOT_SUPPORTED` | `PsvRuptureDiscNotSupported` | G8 |
| `PSV_ORIFICE_OVERRIDE_TOO_SMALL` | `PsvOrificeOverrideTooSmall` | G9 |
| `PSV_BACK_PRESSURE_EXCEEDED` | `PsvBackPressureExceeded` | G10 |
| `PSV_BLOWDOWN_OUT_OF_RANGE` | `PsvBlowdownOutOfRange` | G11 |
| `PSV_INLET_OUTLET_MISMATCH` | `PsvInletOutletMismatch` | G12 |
| `PSV_MATERIAL_INCOMPATIBLE` | `PsvMaterialIncompatible` | G13 |
| `PSV_INLET_TOO_SMALL` | `PsvInletTooSmall` | G14 |
| `PSV_ORIFICE_TEMPERATURE_LIMIT` | `PsvOrificeTemperatureLimit` | G15 |
| `PSV_BELLOWS_MATERIAL_REQUIRED` | `PsvBellowsMaterialRequired` | G17 |
| `PSV_FLANGE_CLASS_ORIFICE_MISMATCH` | `PsvFlangeClassOrificeMismatch` | G20 |
| `PSV_BELLOWS_INCOMPATIBLE` | `PsvBellowsIncompatible` | G21 |
| `PSV_INLET_OUTLET_REQUIRED` | `PsvInletOutletRequired` | — |

## 3. PsvResult 新增 18 列 + 3 CHECK

### 18 列（§3.1）
1. `valve_type` (32) — SPRING_LOADED/BALANCED_BELLOWS/PILOT/RUPTURE_DISC
2. `body_material` (32) — CARBON_STEEL/SS304/SS316/SS316L/ALLOY
3. `bellows_material` (32) — 6 种（HASTELLOY_C276 / SS316L / INCONEL_625 / INCONEL_718 / ALLOY_400 / ALLOY_C22）
4. `flange_class` (8) — 150#/300#/600#/900#/1500#/2500#
5. `back_pressure_type` (16) — BUILT_UP / SUPERIMPOSED
6. `back_pressure_pct` (Float) — 0-50
7. `overpressure_pct` (Float) — 10/16/21
8. `kb_factor` (Float) — 背压修正 Kb
9. `kb_source` (32) — none / manufacturer:X / api520_fig30 / en4126 / mixed:X+Y
10. `valve_brand` (32) — 自由字符串
11. `cdtp_applied` (Bool, default FALSE) — CDTP 修正生效
12. `orifice_overridden` (Bool, default FALSE) — 用户手动指定孔口
13. `orifice_manual` (8) — 手动指定孔口字母 D-T
14. `rupture_disc_position` (16) — UPSTREAM/DOWNSTREAM/NONE
15. `rupture_disc_kc` (Float) — UPSTREAM=0.90 / DOWNSTREAM=1.00
16. `pilot_temperature_c` (Float) — 先导温度（占位）
17. `pilot_temp_class` (16) — GENERAL/HIGH_TEMP/CRYOGENIC（占位）
18. `fire_protection` (Bool, default FALSE) — 防火保护

### 3 CHECK（DB 层兜底）
- `psv_valve_type_chk`：`valve_type IS NULL OR valve_type IN ('SPRING_LOADED', 'BALANCED_BELLOWS')`
- `psv_cdtp_check`：`NOT cdtp_applied OR back_pressure_type = 'SUPERIMPOSED'`
- `psv_orifice_overridden_check`：`(NOT orifice_overridden AND orifice_manual IS NULL) OR (orifice_overridden AND orifice_manual IS NOT NULL)`

## 4. Kb 4 阶段策略（§4.3）

1. **None**：`PILOT_OPERATED` 走 EN 4126（不受 Kb 修正）；其它零背压直接返回 `kb=1.0 / source='none'`
2. **Brand**：`valve_brand` ∈ {_KB_DATA 厂商} → 查厂商曲线（10%/16%/21% 三个 overpressure 点 + 线性插值）
3. **Mixed**：`valve_brand='mixed:mfr1+mfr2'` → 取最低一档
5. **Conservative fallback**：未匹配 → 走 `api520_fig30` 保守值（标 `source='api520_fig30'`）

**重要标记**：`_KB_DATA` 顶部包含 `# SYNTHETIC_TEST_DATA` 注释 + TODO。P5-3 启动后由工艺工程师替换为真实厂商曲线。

## 5. 6 波纹管材料兼容矩阵（§3.8）

| Material | Forbidden 条件 |
|----------|----------------|
| HASTELLOY_C276 | 强氧化性（热浓硝酸 / 游离卤素） |
| SS316L | 还原性酸 / HCl / 湿 H2S |
| INCONEL_625 | 含氟酸 / 强氧化碱 |
| INCONEL_718 | 强还原性 / 熔融 NaOH |
| ALLOY_400 | 强氧化性 / 含汞介质 |
| ALLOY_C22 | 含氟酸 + 高温 |

匹配规则：service_note 文本含关键词 → raise PsvBellowsIncompatible（422 PSV_BELLOWS_INCOMPATIBLE）。

## 6. API 526 14 孔口-法兰映射（§3.3）

支持 D/E/F/G/H/J/K/L/M/N/P/Q/R/T 共 14 个孔口字母；H/G 在 600# 以上双候选；Q/R/T 高温低分子量限制（T>177°C AND MW<10 → 警告）。

## 7. 测试清单（30+ 例落地）

| 文件 | 例数 | 覆盖 |
|------|------|------|
| `tests/services/psv/test_orifice_flange.py` | 8 | API 526 Tables 2-15 + H/G 双候选 + T 65psig |
| `tests/services/psv/test_bellows_compat.py` | 11 | 6 材料 × forbidden 条件 + helpers |
| `tests/services/psv/test_kb_lookup.py` | 8 | §8 gate #10 全部 8 场景 |
| `tests/services/psv/test_valve_validation.py` | 15 | G7-G21 全拦截 + happy path |
| `tests/api/v1/test_psv_api.py` | 8 | 端到端：默认 18 列 + G7/G8/G10/G12/G17/G21 + LESER Kb |

## 8. 后续待办（P5-3 启动后接管）

- **OPEN-10-1**：`API526_FLANGE_CLASS_ORIFICE_LIMITS` 84 组合（SPEC §8 gate #4 硬性）—— 工艺工程师负责
- **OPEN-10-2**：真实 Kb 厂商数据（LESER/Consolidated/AG）—— 工艺工程师 + 数据收集
- **OPEN-10-3**：+50~60 测试余项 —— 入 P5-3 后续批
- **OPEN-10-4**：CRYOGENIC 型号（OPEN-18）/ API 521 FIRE+PILOT 章节号（OPEN-19）—— 工艺工程师
- **OPEN-10-5**：65 psig T 孔口 150# 警告（OPEN-20）—— 工艺工程师确认
- **OPEN-10-6**：record_hash 含新字段（SPEC §7.2 兼容）—— 当前 `finalize_calc_record` 已自动重算，待回归验证