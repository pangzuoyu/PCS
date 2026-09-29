# P6-8 批 — Glycol Dehydration Service 扩展（OPEN-P6-6A-6 关闭）

## Context

P6-6A-6 v4 + P6-7 工艺交付 + ADR-0045 Rev B 工艺室签署（2026-10-15），P6-7 闭环 OPEN-P6-6A-9.x 系列但 OPEN-P6-6A-6（T8 full glycol dehydration system as new PCS service）仍 OPEN。

P6-8 范围：glycol dehydration service 4 子模块（reboiler / stripping / full column / lean glycol）从 OUT_OF_SCOPE → 落地。

**Path A1A1 决议**（用户 2026-10-31）：
- Reboiler Duty：完整焓平衡 + WARNING（TEG 循环量待对账）
- Antoine系数：v5 plan 原值 `A=15.30/B=8500`
- Lean Glycol：现有 4 数据点插值

## 锚定版本

PCS backend main @ `36de95e`（P6-7 服务集成批 14 commits active + 工艺室 3 批交付物 + 9 OPEN 关闭登记）

baseline: pytest 3458+ passed / vitest 548+ passed

---

## 任务清单（8 tasks / 4-5 天）

### T1. Reboiler Duty service path（OPEN-P6-6A-6 子任务 1）

- **当前**：`glycol_dehydration_service.py` 无 reboiler duty 计算
- **目标**：
  1. 加 `_calc_reboiler_duty_btu_hr` 函数（完整焓平衡 `Q_total = Q_evap + Q_cond + Q_TEG + 10% 设计裕度`）
  2. 加 `_calc_stripping_gas_rate_scf_gal_teg` 函数（GPSA §20.4 Eq.20-5 + v5 plan Antoine `A=15.30/B=8500`）
  3. 加 `ReboilerStrippingInput` Pydantic model
  4. 加 `ReboilerStrippingResult` dataclass（含 WARNING 字段：TEG 循环量待对账）
  5. **warning 字段**：`te_circulation_rate_gal_lb_unverified: bool = True`（提示工艺室对账未完成）
- **commit**：1
- **验收**：
  - pytest 1+ PASS
  - 黄金 fixture 对账（v5 plan 原值）
- **OPEN 关闭**：OPEN-P6-6A-6 子任务 1
- **依赖**：v5 plan Antoine 系数（A=15.30/B=8500）已就位
- **工时**：0.5 天

### T2. Stripping Gas Rate service path（OPEN-P6-6A-6 子任务 2）

- **当前**：T1 已加 `_calc_stripping_gas_rate_scf_gal_teg`；本任务扩展 fixture + 测试
- **目标**：
  1. fixture `golden_c16_stripping_gas_rate.json`：3 算例（T=120/180/250°F × P=1000 psia × X=0.9938/0.9970/0.9990）
  2. 测试验证 `SGR` 与 XLS E32=0.4220 scf/gal 残差 < 5%
- **commit**：1
- **验收**：3 算例 PASS（rel ≤ 5e-2）
- **OPEN 关闭**：OPEN-P6-6A-6 子任务 2
- **依赖**：T1 已落
- **工时**：0.3 天

### T3. Full Column Diameter service path（OPEN-P6-6A-6 子任务 3）

- **当前**：P6-7 T9 已加 `_get_behr_coefficients(T)` + Bukacek low-temp 系数；`D_full = K × √(Q_gas_mmscfd)` 简化式已有
- **目标**：
  1. fixture `golden_c16_full_column_diameter.json`：6 算例（Worley 6 接触塔算例 + ADR-0045 Rev B K=7.1121）
  2. 测试验证 K=7.1121 CV=1.05% < 5%
- **commit**：1
- **验收**：6 算例 PASS（rel ≤ 5e-3）
- **OPEN 关闭**：OPEN-P6-6A-6 子任务 3
- **依赖**：T9 已落
- **工时**：0.2 天

### T4. Lean Glycol Concentration service path（OPEN-P6-6A-6 子任务 4）

- **当前**：`glycol_dehydration_service.py` 无 lean glycol 计算
- **目标**：
  1. 加 `_calc_lean_glycol_concentration_wt_pct` 函数（GPSA Fig 20-4 数据点 + 插值）
  2. fixture `golden_c16_lean_glycol.json`：3 算例（再沸器 380/400/400°F × 汽提气 0/0/3 scf/gal）
  3. 测试验证 lean glycol vs XLS E29=0.9938 残差 < 1%
- **commit**：1
- **验收**：3 算例 PASS（rel ≤ 1e-2）
- **OPEN 关闭**：OPEN-P6-6A-6 子任务 4
- **依赖**：GPSA Fig 20-4 数据点（4 个）已就位
- **工时**：0.5 天

### T5. API 端点扩展（OPEN-P6-6A-6 集成）

- **当前**：`/psychro/glycol-dehydration/calculate` v4 API（P6-6A-6 T3）已支持 12 OUT_OF_SCOPE fields
- **目标**：
  1. API response 增 4 outputs：
     - `reboiler_duty_btu_hr: float`
     - `reboiler_duty_kw: float`
     - `stripping_gas_rate_scf_gal: float`
     - `lean_glycol_concentration_wt_pct: float`
     - `full_column_diameter_in: float`（T3 已有，但 Pydantic schema 可能需补）
  2. **WARNING 字段**：`warnings: list[str]`（含 `TEG_CIRCULATION_RATE_UNVERIFIED`）
  3. `GoldenGlycolDehydrationResult` schema 扩展
- **commit**：1
- **验收**：
  - OpenAPI regen 成功（drift=0）
  - 前端 types regen 成功（drift=0）
  - API 集成测试 PASS
- **OPEN 关闭**：OPEN-P6-6A-6 集成
- **依赖**：T1+T2+T3+T4 已落
- **工时**：0.5 天

### T6. 黄金 fixtures 4 子模块

- **当前**：P6-7 T9 + 本批 T1+T2+T3+T4 已加 fixture 文件；本任务整合
- **目标**：
  1. fixture 完整性 check（所有 4 子模块黄金值）
  2. 文档化每个 fixture 的 source_note（工艺室 2026-10-31 提供）
- **commit**：0（fixture 已在 T1-T4 内 commit，不重复 commit）
- **验收**：4 子模块 fixture 齐全
- **OPEN 关闭**：—
- **依赖**：T1-T4 已落
- **工时**：0.2 天

### T7. pytest + OpenAPI regen + frontend types 同步

- **当前**：T5 之前已 OpenAPI regen + frontend types 同步；本任务仅 verify
- **目标**：
  1. pytest 全模块 0 break（baseline ≥ 3458）
  2. OpenAPI regen + G-08 phase 1-4 全过
  3. 前端 types regen
- **commit**：0（verify only）
- **验收**：G-08 ✅ + pytest ✅ + types regen ✅
- **OPEN 关闭**：—
- **依赖**：T1-T6 已落
- **工时**：0.3 天

### T8. 批末收口（G-08 + STATUS + README + wolf 登记 + push）

- **当前**：8 task 全部完成
- **目标**：
  1. G-08 phase 1-4 全过
  2. pytest 各模块 0 break
  3. vitest 0 break
  4. `.wolf/STATUS.md` 闭环登记（P6-8 批落地 entry + OPEN-P6-6A-6 关闭）
  5. `.wolf/cerebrum.md` 更新（4 子模块 service 落地 + ADR-0045 Rev B 实施）
  6. `README.md` 同步 P6-8 已闭环批次
  7. push 全部 commits 至 origin/main
- **commit**：1（docs(wolf): P6-8 批落地登记 + README 同步）
- **验收**：batch-end G-08 ✅ + 测试基线不退化
- **工时**：0.3 天

---

## 依赖图

```
T1 (Reboiler Duty + Stripping Gas helpers)
  ├─→ T2 (Stripping Gas fixture)
  └─→ T4 (Lean Glycol)

T3 (Full Column)        依赖 T9 (P6-7)
T5 (API 集成)           依赖 T1+T2+T3+T4
T7 (verify)             依赖 T1-T6
T8 (收口)               依赖所有 APPROVE
```

**Phase 1 并行**：T1, T3（独立）
**Phase 2 并行**：T2, T4（依赖 T1）
**Phase 3**：T5（依赖 T1+T2+T3+T4）
**Phase 4**：T6, T7
**Phase 5**：T8

---

## 工时表

| Phase | Tasks | 工作日 |
|---|---|---|
| Phase 1 并行 | T1, T3 | 0.5（max T1=0.5） |
| Phase 2 并行 | T2, T4 | 0.5（max T4=0.5） |
| Phase 3 | T5 | 0.5 |
| Phase 4 | T6, T7 | 0.5（并行） |
| Phase 5 | T8 | 0.3 |
| **总计** | | **~2.3 工作日** |

---

## 验收矩阵（15 项）

| # | 项 | 命令 | 期望 |
|---|---|---|---|
| 1 | ruff | `cd pcs-backend && uv run ruff check .` | 0 errors |
| 2 | pytest | `uv run pytest -q` | ≥ 3458 passed + 0 break |
| 3 | vitest | `cd pcs-frontend && npx vitest run` | ≥ 548 passed |
| 4 | tsc | `npx tsc --noEmit` | 0 errors |
| 5 | eslint | `npx eslint src/ tests/` | 0 errors |
| 6 | gate_08 | `bash pcs-backend/scripts/gate_08_openapi_contract.sh` | drift=0 |
| **T1** | 7 | 完整焓平衡 Q_total = Q_evap + Q_cond + Q_TEG + 10% 设计裕度 | PASS |
| **T1** | 8 | WARNING `TEG_CIRCULATION_RATE_UNVERIFIED` 字段 | PASS |
| **T2** | 9 | SGR 3 算例 vs XLS E32 残差 < 5% | PASS |
| **T3** | 10 | Full Column 6 算例 K=7.1121 残差 < 5e-3 | PASS |
| **T4** | 11 | Lean Glycol 3 算例 vs XLS E29 残差 < 1% | PASS |
| **T5** | 12 | API 集成 4 outputs + WARNING 字段 | PASS |
| **T6** | 13 | 4 子模块 fixture 齐全 | PASS |
| **T7** | 14 | OpenAPI regen + frontend types 同步 | PASS |
| **T8** | 15 | push 至 origin/main + remote HEAD 一致 | PASS |

---

## 风险 + 缓解

| 风险 | 等级 | 缓解 |
|---|---|---|
| **R-1** Reboiler Duty TEG 循环量假设（3 gal/lb vs XLS 实际 1.5 gal/lb） | 中 | WARNING `TEG_CIRCULATION_RATE_UNVERIFIED` + 工艺室 2026-11-15 对账后回归 |
| **R-2** Antoine系数 v5 plan 原值 vs DIPPR NIST | 中 | 工艺室 2026-11-15 DIPPR / NIST 验证后回归 |
| **R-3** Lean Glycol GPSA Fig 20-4 完整曲线待抄录 | 低 | 当前 4 数据点插值足够覆盖典型工况；工艺室 2026-11-15 完整曲线后回归 |
| **R-4** 4 子模块 API 集成回归（worley_c16 fixture 扩 4 case） | 低 | T5 测试覆盖；OpenAPI drift=0 |
| **R-5** OpenAPI / frontend types regen 兼容 | 低 | pre-commit hook 自动触发；regen 后跑测试 |

---

## 关键文件路径

- `pcs-backend/app/services/psychro/glycol_dehydration_service.py` — T1/T3/T4 service path
- `pcs-backend/app/schemas/psychro.py` — T5 4 outputs Pydantic schema 增量
- `pcs-backend/tests/services/psychro/fixtures/golden_c16_stripping_gas_rate.json` — T2 fixture
- `pcs-backend/tests/services/psychro/fixtures/golden_c16_full_column_diameter.json` — T3 fixture
- `pcs-backend/tests/services/psychro/fixtures/golden_c16_lean_glycol.json` — T4 fixture
- `pcs-backend/app/services/psychro/_compound_config_cache.py` — T5 (optional)
- `pcs-backend/tests/services/psychro/test_glycol_dehydration.py` — T1/T2/T3/T4 测试
- `pcs-backend/docs/adr/ADR-0045-teg-contactor-sizing.md` — Rev B 实施确认（T3）

---

## OPEN 关闭清单（P6-8 批内）

| OPEN | T8 关闭 | 备注 |
|---|---|---|
| OPEN-P6-6A-6 | ✅ | 4 子模块 service path 全落地 |

**剩余 OPEN 队列**（P6-8 之后）：
- OPEN-P6-4-2（上线后）
- OPEN-P6-4-4（部分关闭 — 3-model fixture 待修复）
- OPEN-P6-6A-9.5（待 fixture 重发 2026-11-15）
- OPEN-P6-6A-10（工艺 PDF 2026-11-15 升级 confidence）

---

## 后续（P6-9 / 上线）

P6-8 完成后触发：
- 工程团队接管厂商数据采集 + ETL 重新对账
- 工艺室 2026-11-15 交付物到位后回归（T2 fixture 修复 + Antoine 系数更新 + Lean Glycol 完整曲线）
- 上线部署 + SPEC V1.2 修订（OPEN-P6-6A-1 Ruling 9 wording final + C-17/C-19 文档化）

---

## 未解决问题

1. **OPEN-P6-4-2**（上线后批）— 不阻塞 P6-8
2. **OPEN-P6-4-4 fixture 修复** — T5 fixture 待工艺室对账
3. **OPEN-P6-6A-9.5 工艺室 fixture 重发** — T2 fixture coefficients.json 待 2026-11-15
4. **OPEN-P6-6A-10 工艺 PDF** — T8 待 AS 1210-2010 PDF 到位
5. **T1 Reboiler Duty TEG 循环量** — 工艺室与 Worley 对账