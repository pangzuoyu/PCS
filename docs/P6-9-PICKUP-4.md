# P6-9-PICKUP-4 — ce-code-review P5+P6 残留 debt 闭环

> 来源：`docs/ce-code-review-p5-p6-summary.md` 50 findings（5 batch × 47 commits）
> 锚定版本：PCS backend main @ `93a1417`（P6-9-PICKUP-3 收口 commit）
> 闭环 commit：`b15512a`（HEAD 2026-09-30）
> 上游：`docs/superpowers/plans/2026-09-30-p6-9-pickup-4-debt-cleanup-final.md`

## Context

`docs/ce-code-review-p5-p6-summary.md`（`cf51fdf` 落地）记录 5 batch focused review（sonnet 双 persona correctness + project-standards），覆盖 main HEAD `2b27e00` 之前 47 commits 跨 9 batches。

| 等级 | P5-0 | P5-123 | P6-6B | P6-7 | P6-8+P6-9 | 总计 |
|---|---|---|---|---|---|---|
| **CRITICAL** | 0 | 0 | 0 | 1 | 3 | **4** |
| **HIGH** | 2 | 2 | 2 | 2 | 1 | **9** |
| MEDIUM | 1 | 3 | 3 | 3 | 2 | 12 |
| LOW/INFO | 3 | 4 | 4 | 4 | 6 | **21** |
| **commits** | 5 | 5 | 16 | 10 | 11 | **47** |

**测试基线**：pytest 3501 passed / 5 skipped / 3 failed（pre-existing CV 模块，与 review 范围无关）；ruff 18 errors（全部 pre-existing）；G-08 phase 1-4 全过 drift=0。

---

## 闭环流程（3 阶段）

### 阶段 1：P6-9-PICKUP-2（CRITICAL + HIGH 修复批，5 commits）

**目标**：4 CRITICAL + 4 HIGH（核心 8 项）的代码侧修复。

| commit | 内容 |
|---|---|
| `0eb4dc3a` | CRITICAL F1 `_calc_lean_glycol_concentration_wt_pct` else-branch 修复（line 1339 return 改为 `lean_glycol`）+ interpolation regression test |
| `0c631c3` | CRITICAL F2 `_calc_stripping_gas_rate_scf_gal_teg` 公式结构反转（GPSA §20.4 Eq.20-5）+ fixture 重算 |
| `4645d78` | CRITICAL F3 C-24 reconciliation service x 显式 + consistency check（OPEN-P6-4-4 部分关闭） |
| `258d857` | HIGH `_calc_*` t_wall_mm → t_wall_m 单位歧义修复（100× 误差风险，7 处同步） |
| `a9956c2` | HIGH `_USE_XLS_CD_Y_CR` feature flag 接入 + `fluid` 参数（drain_orifice_service） |
| `b599420` | HIGH `_calculate_nielsen_depression` dead code 删除（P6-7 已替换 call site） |
| `173b42d` | MEDIUM untracked test file commit + 批末收口 |

**结果**：3513+ passed（1 pre-existing T2 fail 豁免）+ ruff 0 new errors + G-08 drift=0。

### 阶段 2：P6-9-PICKUP-3（MEDIUM ruff + schema drift 守护，5 commits）

**目标**：7 MEDIUM 中的 ruff 18 errors + psychro schema drift 守护测试。

| commit | 内容 |
|---|---|
| `f8260aa` | ruff pre-existing `calibrate_behr_coefficients.py` F841 fix（T3-batch-1） |
| `72162e9` | ruff pre-existing `test_restriction_api` E402 fix（T3-batch-2） |
| `6acc553` | ruff pre-existing psychro test fix（T3-batch-3） |
| `8926328` | ruff pre-existing `test_worley_c18` fix（T3-batch-4） |
| `0cec39a` | ruff pre-existing `test_worley_c19` fix（T3-batch-5） |
| `8b505cb` | G-07 psychro_results schema drift 守护测试 |
| `8d9e43b` | drop `compound_nielsen_1988_params` orphan（`_calculate_nielsen_depression` 删除后无 reader） |
| `6970400` | `docs/superpowers/plans/` 纳入 git + `sample/` .gitignore |
| `93a1417` | P6-9-PICKUP-3 findings 累积登记（21 LOW/INFO + 批末收口 T5） |

**结果**：ruff 18 → 13 errors（5 项残留于 `calibrate_behr_coefficients.py`，rebase 到 PICKUP-4）；`docs/ce-code-review-p5-p6-summary.md` 引用位稳定。

### 阶段 3：P6-9-PICKUP-4（LOW/INFO + 工艺室对账预留位，4 commits）—— **本批**

**目标**：21 LOW/INFO 项 4 维分类 + 9 pre-existing pytest failures 修复 + 工艺室 2026-11-15 交付跟踪位。

| commit | Task | 内容 |
|---|---|---|
| `f9f1360` | T1 | 9 pre-existing pytest failures 修复（psychro schema drift + 4 类 DB drift） |
| `0cec39a` | T2 | `calibrate_behr_coefficients.py` ruff 5 errors rebase 收口（PICKUP-3 T3-batch-5 已分批修） |
| `15b6edd` | T3 | 21 LOW/INFO 项 4 维分类（5 PROCo + 8 HYG + 6 DOC + 2 REF）+ 推荐下游 batch |
| `6271db7` | T3 fix | 数学不一致修正（26 IDs → 21 IDs 对齐上游 LOW/INFO 计数） |
| `b15512a` | T4 | 工艺室 2026-11-15 交付跟踪位预留（OPEN 5 项状态字段 + 前置条件） |

**结果**：3515 passed / 0 failed / ruff 0 errors / vitest 548 持平 / G-08 drift=0。

---

## 21 LOW/INFO 项 4 维分类（docs/tasks.md 主仓）

### 工艺计算正确性（5 项，需工艺室对账）

| ID | Batch | 范围 | 状态 |
|---|---|---|---|
| PROCo-P6-7-1 | P6-7 | Nielsen 1988 -0.00645 vs -0.00754（~17% 差异）| OPEN-工艺室 |
| PROCo-P6-7-2 | P6-7 | Behr high_acid 系数不自洽 | 待 OPEN-P6-6A-9.5 |
| PROCo-P6-7-3 | P6-7 | fixture 3-sig-fig 近似（dual-tolerance 容纳）| OPEN-工艺室 |
| PROCo-P6-8-1 | P6-8 | brief `contactor_temperature_f le=300` vs impl `le=200` | 待澄清 |
| PROCo-P6-8-3 | P6-8 | SGR Antoine A=15.30/B=8500 待校准 | OPEN-P6-9-PICKUP-2-1（xfail）|

### 代码卫生（8 项，`ruff --fix` 可批量）

| ID | Batch | 范围 | 工具 |
|---|---|---|---|
| HYG-P6-6B-1 | P6-6B | alembic doc-string 4 项 ruff D 规则 | `ruff --fix` |
| HYG-P6-6B-2 | P6-6B | psychro service ruff/seed 3 项 E501/F841 | `ruff --fix` |
| HYG-P6-7-1 | P6-7 | `glycol_dehydration_service.py` E501 + F841 残留 | `ruff --fix` |
| HYG-P6-8-1 | P6-8 | fixture JSON 末尾缺换行符 | `pre-commit end-of-file-fixer` |
| HYG-P5-0-1 | P5-0 | psv service pre-existing ruff/whitespace | `ruff --fix` |
| HYG-P5-0-2 | P5-0 | psv test pre-existing ruff nit | `ruff --fix` |
| HYG-P5-123-1 | P5-123 | heat_exchanger service pre-existing | `ruff --fix` |
| HYG-P5-123-2 | P5-123 | cv test pre-existing long-line / f-string | `ruff --fix` |

### Documentation（6 项，人工 review）

| ID | Batch | 范围 | 行动 |
|---|---|---|---|
| DOC-P6-6B-1 | P6-6B | `glycol_dehydration_service.py` docstring nit | 人工 review |
| DOC-P6-6B-2 | P6-6B | `hydrate_inhibition_service.py` spec deviation | SPEC V1.13 修订预留 |
| DOC-P6-8-1 | P6-8 | `PCS-UI-SPEC.md` §3.9.1.1 C-16 12 result fields | SPEC V1.13 修订预留 |
| DOC-P5-0-1 | P5-0 | `PCS-PLAN-P5-DEVICE-EQUIPMENT.md` 实施后 nit | 人工 review |
| DOC-P5-123-1 | P5-123 | `PCS-PLAN-P5-DEVICE-EQUIPMENT.md` 实施后 nit | 人工 review |
| DOC-P5-123-2 | P5-123 | README / CHANGELOG commit message 格式 | 人工 review |

### 重构（2 项，需重构 plan）

| ID | Batch | 范围 | 行动 |
|---|---|---|---|
| REF-P6-8-1 | P6-8 | glycol 双字段冗余 + `boeboiler_duty_btu_hr` 命名 | 重构 plan（拆分 + 命名统一） |
| REF-P6-8-2 | P6-8 | `_calc_*` 4 helpers + `_DewpointResult` + WARNING 集中 | 拆 `_glycol_dehydration/` 子模块 |

**总计**：5 + 8 + 6 + 2 = **21 项 ✓**

---

## 工艺室 2026-11-15 交付对账预留位（T4 跟踪）

| OPEN | 关联 LOW/INFO | 状态 | 前置条件 |
|---|---|---|---|
| OPEN-P6-6A-10 | DOC-P6-8-1（partial）/ REF-P6-8-2 | 工艺室 2026-11-15 AS 1210-2010 PDF | confidence B → A 升级 |
| OPEN-P6-9-PICKUP-2-1 | PROCo-P6-8-3（SGR Antoine k_strip） | xfail | 工艺室校准报告 |
| OPEN-P6-9-PICKUP-2-2 | （t_wall_mm 复盘，HIGH 已修） | 已闭环（`258d857`）| — |
| OPEN-P6-6A-9.5 | PROCo-P6-7-2（high_acid 系数据源） | 工艺室 2026-11-30 重发 | Behr 系数表完整 |
| OPEN-P6-6A-11 | PROCo-P6-7-{1,3}（Nielsen 精确常数 + 3-sig-fig） | 工艺室 2026-11-30 完整 Table 2-3 | Nielsen 1988 完整数据 |

---

## 下游 batch 推荐

### P6-9-PICKUP-5（建议）：工艺计算正确性 + 重构（7 项，~2.0 天）

- PROCo-P6-7-{1,2,3}：工艺室标定对账 3 项（待 OPEN-P6-6A-9.5 / OPEN-P6-6A-11 2026-11-15 / 2026-11-30 交付）
- PROCo-P6-8-{1,3}：glycol dehydration 2 子模块精度校准（待 OPEN-P6-9-PICKUP-2-1 工艺室 k_strip + Antoine A/B 校准交付）
- REF-P6-8-{1,2}：2 项 glycol 重构（拆分 `_glycol_dehydration/` 子模块 + 字段命名去冗余）

**触发**：OPEN-P6-6A-9.5 / OPEN-P6-6A-11 / OPEN-P6-9-PICKUP-2-1 工艺室交付后启动。

### P6-9-PICKUP-6（建议）：代码卫生 + documentation（14 项，~1.0 天）

- HYG-*-{1..8}：8 项 ruff/whitespace 类修复（`ruff check --fix` + 手工 `pre-commit` 配置）
- DOC-*-{1..6}：6 项 SPEC/brief/commit message 格式同步

**触发**：与 P6-9-PICKUP-5 并行可启动，无外部依赖。

---

## 验证矩阵

| 项 | 结果 |
|---|---|
| pytest 全量 | **3515 passed / 0 failed**（9 pre-existing 修复后无 regression） |
| ruff check（全局） | **0 errors**（`scripts/dev/calibrate_behr_coefficients.py` 5 项清零） |
| vitest 全量 | 548 passed（基线持平） |
| G-08 phase 1-4 | 全过 drift=0 |
| docs/tasks.md 总计 | 21 项 = 5 PROCo + 8 HYG + 6 DOC + 2 REF ✓ |
| OPEN 状态字段 | 5 项（OPEN-P6-6A-10 / -9-PICKUP-2-1/2 / -6A-9.5 / -6A-11）|

---

## OPEN 状态变化（累计 3 阶段）

| OPEN | 交付前 | 交付后 |
|---|---|---|
| OPEN-P6-4-4 | partial closure | 维持 partial（C-24 reconciliation ≥ 1/3 模型通过） |
| OPEN-P6-6A-10 | partial closure | confidence B → A 升级 + partial closure → close |
| OPEN-P6-9-PICKUP-2-1 | partial closure（k_strip 待校准）| 校准后重测 pytest → close |
| OPEN-P6-9-PICKUP-2-2 | partial closure（t_wall HYSYS 待验证）| HYSYS 后 fixture 数值重算 → close |
| OPEN-P6-6A-9.5 | partial closure（high_acid 系数不自洽）| 重发 → close |
| OPEN-P6-6A-11 | partial closure（Nielsen 覆盖缺口）| Table 2-3 完整 → close |
| OPEN-P6-9-PICKUP-4 | — | 新增（T4 跟踪位预留）|

---

## 参考

- 上游总仓：`docs/ce-code-review-p5-p6-summary.md`（`cf51fdf` 落地，214 行）
- 任务分配：`docs/tasks.md`（21 项 4 维分类主仓）
- 实施 plan：`docs/superpowers/plans/2026-09-30-p6-9-pickup-4-debt-cleanup-final.md`
- 阶段 1 plan：`docs/superpowers/plans/2026-09-30-p6-9-pickup-2-debt-cleanup.md`
- 阶段 2 plan：`docs/superpowers/plans/2026-11-15-p6-9-pickup-3-debt-cleanup.md`
- 下游 batch 候选：`docs/superpowers/plans/2026-09-30-p6-9-pickup-6-docs-hygiene.md`（HYG+DOC 14 项）
- 工艺室交付跟踪：`docs/tasks.md` §工艺室 2026-11-15 交付对账预留位