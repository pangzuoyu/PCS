# P6-6B 数据源替换批 — 9 CONFIG 表 + 4 内联常量

## Context

P6-6A 对账批（commit `258b6d5`..`fddeae4`，13 implementer tasks + 15 commits）已完成，零服务改动，11 Rulings 已登记。现在要替换 9 张 CONFIG 表的 SYNTHETIC 标记数据 + 4 个内联工程常量，转为真实工程数据来源。

P6-6B 是 P6-6A 后续数据源升级（OPEN-P6-4-* 4 项 + P6-6A 新增 6 项 deferred concerns 中可由数据源解决的项）。

## 锚定版本

PCS backend `feature/p6-6a-worley` @ `fddeae4`（worktree `PCS-worktrees/p6-6a-worley`），合并后 main HEAD。

baseline：3242 passed + 74 skipped。

---

## 9 CONFIG 表数据源替换

### T1. `compound_heating_values`（C-06 配置表）
- **当前**：64 种化合物 GPSA FIG. 23-2 + API 5B6 抄录，`source='SYNTHETIC_TEST_DATA'`，`confirmed_by='PLACEHOLDER'`
- **目标**：工艺工程师核对 GPSA FIG. 23-2（2022 ed.）原版 + API 5B6；更新 `confirmed_by=<engineer_name>` + `confirmed_at=YYYY-MM-DD`；`source='GPSA FIG. 23-2 (2022) + API 5B6'`
- **commit**：1
- **验收**：`pytest tests/services/common/test_heating_value_calc.py`；64 行 `source` 字段去 SYNTHETIC 标记；`confirmed_by` 非 PLACEHOLDER
- **OPEN-P6-4-1** 关闭

### T2. `_VALVE_LIBRARY` 真实 Kb 厂商数据（C-24 阀门厂库）
- **当前**：24 组合合成（`SYNTHETIC_TEST_DATA`）；默认 FL/FF/Cf 圆整值
- **目标**：LESER / Consolidated / AG / Farris / Anderson Greenwood 5 厂商 × 4 阀型（GLOBE/BALL/BUTTERFLY/DIAPHRAGM）= 20 组合；真实厂商数据手册 PDF 抄录
- **commit**：2（vendor catalog extract + library dict 替换）
- **验收**：`pytest tests/services/cv/test_flashing_correction.py -k valve_library`；20 组合 `source='<vendor_name> catalog'`；OPEN-P6-4-2 关闭
- **风险**：厂商手册 PDF 不可下载 → 工艺室调取纸质件

### T3. `pipe_E_modulus`（C-13 Joukowsky 输入）
- **当前**：T6 测试 fixture 内联 5 等级硬编码（无 CONFIG 表）
- **目标**：CONFIG 表 `pipe_E_modulus`（grade → E_psi）；API 5L X42/X52/X65/X70/X80 + ASTM A106-B/A335-P11/P22 共 8 等级；`source='API 5L (2018) + ASTM A106/A335'`
- **commit**：2（ORM + seed + C-13 service 集成）
- **验收**：`pytest tests/services/pipe/test_worley_c13.py`；0 break

### T4. `pasquill_sigma`（P6-5+ C-22/C-23 大气扩散）
- **当前**：service 内部 hardcoded σ 系数
- **目标**：CONFIG 表 `pasquill_sigma`（stability class A-F × downwind distance bins）；`source='EPA ISC3 (1995) User's Guide + Briggs (1973)'`
- **commit**：1
- **验收**：P6-5+ 大气扩散测试回归 0 break
- **依赖**：需 P6-5+ service 已落地（2026-09-26 已交付）

### T5. `api521_thresholds`（C-21 fire case 阈值）
- **当前**：PCS service 硬编码 fire coefficient 43192 + ΔH_vap 2260 kJ/kg
- **目标**：CONFIG 表 `api521_thresholds`（wetted area / vessel type → coefficient mapping）；`source='API 521 (2020) §3.4 + AS 1210 §4.4'`
- **commit**：1
- **验收**：T13 C-21 测试 fire_case coefficient 来源标记；OPEN-P6-6A-5 部分关闭（ΔH_vap 口径仍待定）

### T6. `iso9613`（P6-5+ C-22/C-23 噪声衰减）
- **当前**：无 CONFIG 表
- **目标**：CONFIG 表 `iso9613_attenuation_coefficients`（frequency × atmospheric condition）；`source='ISO 9613-2 (1996)'`
- **commit**：1
- **依赖**：P6-5+ 噪声模块已交付

### T7. `hammerschmidt_K`（C-18 hydrate inhibitor K scale）
- **当前**：PCS 硬编码 K=2335 °F 文献值（实际是 °F scale）
- **目标**：CONFIG 表 `hammerschmidt_K`（inhibitor → K_F + K_C + notes）；Hammerschmidt 1934 + Nielsen 1988 + Caroll 2003 三代 K 值；`source='Hammerschmidt 1934 OG / Nielsen 1988 / GPSA Fig. 20-XX'`
- **commit**：2（CONFIG 表 + service 集成 K_F→K_C 转换 OR 文档化字段名）
- **验收**：T10 C-18 测试 K_SCALE 字段引用 CONFIG；OPEN-P6-6A-3 关闭（K_F→K_C conversion decision）

### T8. `nielsen_1988_params`（C-18 modern hydrate inhibition）
- **当前**：无；PCS 仅有 Hammerschmidt 1934 path
- **目标**：CONFIG 表 `nielsen_1988_params`（CH4/C2H6/C3H8/I-C4H6/N2/CO2/H2S × A/B/C constants）；Nielsen 1988 论文 Table 1-3 抄录
- **commit**：2（ORM + seed + Hammerschmidt service 备选 path）
- **验收**：T10 C-18 测试 dual-model 注册
- **依赖**：工艺工程师从 Nielsen 1988 paper PDF 抄录 12 组 constants

### T9. `glycol_dehydration_full_system`（C-16 full system）
- **当前**：PCS 仅 algebraic EXACT contact tower diameter；reboiler / stripping / full column / lean glycol 4 子模块 OUT_OF_SCOPE
- **目标**：CONFIG 表 `glycol_dehydration_full_system`（TEG 浓度 / reboiler temperature / stripping gas rate 等典型工况范围）；`source='GPSA Fig. 20-XX + McKetta-Wehe'`
- **commit**：1
- **范围**：仅 CONFIG 表占位 + 文档化 OUT_OF_SCOPE；service 扩展不在 P6-6B scope
- **验收**：T8 C-16 测试 OUT_OF_SCOPE ledger 加 CONFIG 引用；OPEN-P6-6A-6 部分关闭

---

## 4 内联常量替换

### T10. Hammerschmidt K_F=2335 → K_C=1297.22（**Ruling 11 关闭**）
- **当前**：`app/services/restriction/drain_orifice_service.py` 或 hydrate 关联 service 硬编码 `K=2335`
- **目标**：service 启动时载入 `hammerschmidt_K` CONFIG 表 → K_F→K_C 转换（1297.22）；或 docs 明确 `hydrate_depression_c` 字段名改为 `_f`
- **commit**：1
- **决议路径**：A) service 改（preferred — 关闭 OPEN-P6-6A-3）；B) docs-only（less invasive，carry OPEN-P6-6A-3）
- **决策待工程团队**

### T11. API 521 fire coefficient 43192 → AS 1210 coefficient 2.457（**Ruling 9 2nd surface 部分关闭**）
- **当前**：`app/services/psv/as1210_overpressure_service.py` 硬编码 43192
- **目标**：service 从 `api521_thresholds` CONFIG 表读取；同时加载 AS 1210 路径（2.457）备选
- **commit**：1
- **验收**：T13 C-21 测试 fire_case 双 path 注册；OPEN-P6-6A-5 部分关闭（ΔH_vap 口径仍 18× diff）

### T12. ΔH_vap 2260 kJ/kg（**OPEN-P6-6A-5 关闭**）
- **当前**：PCS hardcoded 2260 kJ/kg；XLS PR-025 implicit 208 kJ/kg（差距 18×）
- **目标**：CONFIG 表 `delta_h_vap_natural_gas`（typical = 2260；XLS-convention = 208）；service 切换
- **commit**：1
- **决策**：A) PCS 改 2260→208（breaks existing api2000 calculations）；B) XLS 口径文档化为特殊情况（preserves backward compat）；C) 双字段 `delta_h_vap_default` + `delta_h_vap_xls_convention`
- **决策待工程团队**

### T13. Cd=1.0 / Y_cr=1.0 → XLS Cd=0.839 / Y_cr=0.687（**OPEN-P6-6A-4 关闭**）
- **当前**：`app/services/restriction/drain_orifice_service.py` implicit Cd=1.0 / Y_cr=1.0
- **目标**：CONFIG 表 `drain_orifice_Cd_Y_cr`（介质 / β range → Cd / Y_cr lookup）；service 集成
- **commit**：1
- **风险**：1.74× capacity over-prediction 修正 → 影响所有现有 drain_orifice 计算结果；需 ETL 重新对账

---

## 依赖图

```
T1 compound_heating_values ──────┐
T3 pipe_E_modulus ───────────────┤
T4 pasquill_sigma ───────────────┤── Phase 1 (并行)
T6 iso9613 ──────────────────────┤
T7 hammerschmidt_K ───┐          │
                      ├── T10 ──→┤
T8 nielsen_1988_params ┘         │
T9 glycol_dehydration_full_system┤
T2 _VALVE_LIBRARY ───────────────┤
T5 api521_thresholds ──┐         │
                      ├── T11 ──→┤
T12 ΔH_vap ────────────┘         │
T13 Cd/Y_cr ─────────────────────┘

Phase 1：T1+T3+T4+T6+T7+T8+T9+T2+T5+T12+T13 (11 tasks, 可并行)
Phase 2：T10+T11 (依赖 Phase 1 CONFIG 表)
```

---

## 工时表

| Phase | Tasks | 工作日 |
|---|---|---|
| Phase 1 CONFIG 表 | T1~T9 + T12 + T13（11 tasks，部分并行） | 3-4 |
| Phase 2 service 集成 | T10 + T11（2 tasks） | 1-2 |
| ETL 重新对账 + regression | 全套 13 tests + PCS 全栈 baseline 验证 | 1 |
| **总计** | | **5-7 工作日** |

---

## 验收矩阵

| # | 项 | 命令 | 期望 |
|---|---|---|---|
| 1 | ruff | `cd pcs-backend && uv run ruff check .` | 0 errors |
| 2 | pytest | `uv run pytest -q` | ≥ baseline 3242 + 0 break |
| 3 | tsc | `cd pcs-frontend && npx tsc --noEmit` | 0 errors |
| 4 | eslint | `npx eslint src/ tests/` | 0 errors |
| 5 | vitest | `npx vitest run` | ≥ baseline 530 + 0 break |
| 6 | gate_08 | `bash pcs-backend/scripts/gate_08_openapi_contract.sh` | drift=0 |
| 7 | SYNTHETIC 标记扫描 | `grep -r "SYNTHETIC_TEST_DATA" pcs-backend/app/ pcs-backend/scripts/` | 0 matches (excl. config.py SYNTHETIC enum) |
| 8 | `confirmed_by` 字段 | `psql ... -c "SELECT count(*) FROM compound_heating_values WHERE confirmed_by='PLACEHOLDER'"` | 0 |
| 9 | per-task test | `pytest tests/services/<module>/test_worley_<c>.py` | ≥ 13 modules all pass |

---

## 风险 + 缓解

| 风险 | 等级 | 缓解 |
|---|---|---|
| **R-1** 厂商手册 PDF 不可下载（T2） | 高 | 工艺室调取纸质件 / 联系厂商销售 |
| **R-2** GPSA FIG. 23-2 抄录误差（T1） | 中 | 双人交叉核对 + 第二季度复审 |
| **R-3** ΔH_vap 2260→208 破坏向后兼容（T12） | 高 | 双字段（default + xls_convention）；保留原 2260 默认值 |
| **R-4** Cd/Y_cr 修正影响现有计算（T13） | 高 | 双轨（new_field + legacy_field）；feature flag 控制切换 |
| **R-5** P6-5+ service 依赖（T4/T6） | 中 | P6-5+ 已 2026-09-26 交付，但需 merge 到 main 后再开工 |

---

## 关键文件路径

- `pcs-backend/app/models/config.py` — 9 张 CONFIG 表 ORM（仿 `CepciIndexSeries` / `CompoundHeatingValues`）
- `pcs-backend/scripts/p6_6b_seed_*.py` — 9 seed 脚本（GPSA / API / ISO / Vendor 抄录）
- `pcs-backend/alembic/versions/p6_6b_*.py` — 9 alembic 迁移（CREATE TABLE + 索引 + confirmed_by）
- `pcs-backend/app/services/{restriction,psv,pipe,...}/` — 4 内联常量 service 集成（T10~T13）
- `pcs-backend/tests/services/{common,cv,pipe,psv,restriction,...}/test_worley_*.py` — 13 模块测试 0 break 验证

---

## 后续

P6-6B 完成后触发 SPEC V1.2 修订（解决 OPEN-P6-6A-1~6 中剩余 3 项 wording 决议：①Ruling 9 wording final ②C-17 docstring scope clarification ③C-19 Cd/Y_cr 文档化）。

P6-7 / P6-8 由工程团队评估启动时机（建议 P6-6B 验收后立即）。

---

## 未解决问题

1. **OPEN-P6-4-1**：T1 64 种化合物 GPSA FIG. 23-2 抄录（工艺工程师接管）— P6-6B T1 关闭
2. **OPEN-P6-4-2**：T2 真实 Kb 厂商数据（LESER/Consolidated/AG）— P6-6B T2 关闭
3. **OPEN-P6-4-3**：C-08 Imperial 单位支持范围（待 P6-6B 后续批）
4. **OPEN-P6-4-4**：C-24 Chapman-Jans / Tong 模型与商业软件对账（待 P6-6B 后续批）
5. **OPEN-P6-6A-1**：Ruling 9 wording formalization（待 SPEC V1.2 修订）
6. **OPEN-P6-6A-3**：Ruling 11 K_F→K_C conversion OR field rename — P6-6B T10 关闭
7. **OPEN-P6-6A-4**：T11 PCS Cd/Y_cr 默认 1.0 — P6-6B T13 关闭
8. **OPEN-P6-6A-5**：T13 ΔH_vap 2260 vs XLS implicit 208 kJ/kg — P6-6B T12 关闭（部分）
9. **OPEN-P6-6A-6**：T8 full glycol dehydration system as new PCS service — P6-6B T9 部分关闭（CONFIG 占位）；service 扩展待 P6-7
10. **OPEN-P6-6B-1**（新增）：厂商手册 PDF 调取渠道（T2 风险）
11. **OPEN-P6-6B-2**（新增）：ΔH_vap 2260→208 切换策略（T12 决策待工程团队）
12. **OPEN-P6-6B-3**（新增）：Cd/Y_cr feature flag 设计（T13 风险）