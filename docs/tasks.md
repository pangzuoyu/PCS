# tasks.md — PCS 工艺计算 + 代码债务分类跟踪

> 来源：P6-9-PICKUP-4 T3（2026-09-30）
> 上游：`docs/ce-code-review-p5-p6-summary.md` 50 findings（5 batch × 47 commits）
> 中游：`docs/superpowers/plans/2026-11-15-p6-9-pickup-3-debt-cleanup.md` T5 累积登记（`93a1417`）
> 本文件：21 LOW/INFO 项 4 维分类 + 下游 batch 推荐

## 来源 + 分布

| Batch | Commits | CRITICAL | HIGH | MEDIUM | LOW/INFO |
|---|---|---|---|---|---|
| P5-0 | `40b0c69..20a7b60` (5) | 0 | 2 | 1 | **3** |
| P5-123 | `fbea0a4..ba4e0de` (5) | 0 | 2 | 3 | **4** |
| P6-6B | `dc124f7..cd86949` (16) | 0 | 2 | 3 | **4** |
| P6-7 | `eb824eb..6ed6a50` (10) | 1 | 2 | 3 | **4** |
| P6-8+P6-9 | `c89d091..2b27e00` (11) | 3 | 1 | 2 | **6** |
| **总计** | | 4 | 9 | 12 | **21** |

21 LOW/INFO 项 = P5-0(3) + P5-123(4) + P6-6B(4) + P6-7(4) + P6-8+P6-9(6)

---

## P6-9-PICKUP-5 候选跟踪（21 LOW/INFO 4 维分类）

### 工艺计算正确性（需工艺室对账）

编号格式：`PROCo-<batch>-<seq>`

| ID | Batch | 文件 / 范围 | 描述 | 严重性 | 状态 |
|---|---|---|---|---|---|
| PROCo-P6-7-1 | P6-7 | `pcs-backend/app/services/hydrate_inhibition_service.py`（T3 Nielsen 1988） | 工艺室标定 -0.00645 vs PCS 严格 -0.00754（~17% 差异），工艺室后续澄清 | LOW | OPEN-工艺室 |
| PROCo-P6-7-2 | P6-7 | `pcs-backend/data/behr_coefficients.json`（T2 Behr high_acid） | high_acid 系数不自洽（工艺室 2026-11-15 重发） | LOW | 待 OPEN-P6-6A-9.5 |
| PROCo-P6-7-3 | P6-7 | `pcs-backend/tests/services/psychro/test_*_fixtures*.py`（T8 path b） | fixture 3-sig-fig 近似（C3H8 path b 1.81% diff, dual-tolerance 容纳） | LOW/INFO | OPEN-工艺室 |
| PROCo-P6-8-1 | P6-8 | `pcs-backend/app/services/psychro/glycol_dehydration_service.py`（T1 contactor_temperature_f 范围校验） | brief Step 1 `contactor_temperature_f le=300` vs impl `le=200`（工艺室口径差异） | LOW | 待澄清 |
| PROCo-P6-8-3 | P6-8 | `glycol_dehydration_service.py`（T1 SGR 单位混算） | SGR 单位混算（psi vs mmHg），P6-9-PICKUP-2 T2 部分修复（公式结构），**Antoine A=15.30/B=8500 待工艺室校准** | LOW | OPEN-P6-9-PICKUP-2-1（xfail） |

> **dropped PROCo-P6-8-{2,4}**：brief q_total 数值偏差已 P6-9-PICKUP-2 闭环；Fig 20-4 完整曲线 HIGH 范畴同 PICKUP-2 T1 else-branch 部分修复（remaining 工艺室交付走 OPEN-P6-9-PICKUP-2-1，不重复登记 LOW）

**小计**：5 项（2 OPEN-工艺室 + 1 待 OPEN-P6-6A-9.5 + 1 待澄清 + 1 OPEN-P6-9-PICKUP-2-1）

### 代码卫生（自动化工具可修）

编号格式：`HYG-<batch>-<seq>`

| ID | Batch | 文件 / 范围 | 描述 | 严重性 | 工具 |
|---|---|---|---|---|---|
| HYG-P6-6B-1 | P6-6B | `pcs-backend/alembic/versions/*` (T3 4 项) | doc-string 格式 nit（4 项 ruff D规则） | LOW | `ruff --fix` |
| HYG-P6-6B-2 | P6-6B | `pcs-backend/app/services/psychro/*` (T12 3 项) | ruff/seed 偏差（3 项 E501/F841） | LOW | `ruff --fix` |
| HYG-P6-7-1 | P6-7 | `app/services/psychro/glycol_dehydration_service.py` lines 352 / 676 | 2 ruff errors pre-existing（E501 长行 + F841 unused `T_LOW`） | LOW | `ruff --fix`（P6-9-PICKUP-3 已分 5 批修过同批类似文件，本项残留） |
| HYG-P6-8-1 | P6-8 | `pcs-backend/tests/services/psychro/fixtures/*.json` | fixture JSON 末尾缺换行符（T2 O-T2-1） | INFO | `pre-commit end-of-file-fixer` |
| HYG-P5-0-1 | P5-0 | `pcs-backend/app/services/psv/*` | pre-existing ruff/whitespace 类（与 P5-3 ruff 18 累积同类） | LOW | `ruff --fix` |
| HYG-P5-0-2 | P5-0 | `pcs-backend/tests/services/psv/*` | pre-existing ruff nit（待沉淀） | LOW | `ruff --fix` |
| HYG-P5-123-1 | P5-123 | `pcs-backend/app/services/heat_exchanger/*` | pre-existing whitespace / unused imports | LOW | `ruff --fix` |
| HYG-P5-123-2 | P5-123 | `pcs-backend/tests/services/cv/*` | pre-existing long-line / f-string nit | INFO | `ruff --fix` |

> **dropped HYG-P6-8-2**：`pyproject.toml ruff B018` extend-exclude 配置 out of scope（属 P6-9-PICKUP-6 之外的 meta-config 范畴）

**小计**：8 项（ruff 18 中 8 项残留于未触碰文件，需单文件 + `-20` ruff 规则套件）

### Documentation（人工 review + 文档更新）

编号格式：`DOC-<batch>-<seq>`

| ID | Batch | 文件 / 范围 | 描述 | 严重性 | 行动 |
|---|---|---|---|---|---|
| DOC-P6-6B-1 | P6-6B | `pcs-backend/app/services/psychro/glycol_dehydration_service.py` docstring (T3 4 项) | docstring nit（4 项 doc-style + 中文标点 + rst格式） | LOW | 人工 review |
| DOC-P6-6B-2 | P6-6B | `pcs-backend/app/services/hydrate_inhibition_service.py` (T8 4 项) | spec deviation（4 项 spec 与实现小幅漂移） | LOW | SPEC V1.13 修订预留 |
| DOC-P6-8-1 | P6-8 | `docs/PCS-UI-SPEC.md` §3.9.1.1 C-16 | P6-8 实施后 12 result fields 文档同步（部分含 OUT_OF_SCOPE 引用） | INFO | SPEC V1.13 修订预留 |
| DOC-P5-0-1 | P5-0 | `docs/PCS-PLAN-P5-DEVICE-EQUIPMENT.md` | P5-0 实施后 5 commits 部分内容与计划文档 nit（待沉淀） | LOW | 人工 review |
| DOC-P5-123-1 | P5-123 | `docs/PCS-PLAN-P5-DEVICE-EQUIPMENT.md` | P5-123 实施后 5 commits 部分内容与计划文档 nit（待沉淀） | LOW | 人工 review |
| DOC-P5-123-2 | P5-123 | `README.md` / `CHANGELOG.md` | P5-123 commit message 格式 nit（待沉淀） | INFO | 人工 review |

> **dropped DOC-P6-7-1**：brief 模板高温系数 nit（LOW 范畴，P6-9-PICKUP-6 brief 模板批改时一并 sweep）
> **dropped DOC-P6-8-2**：brief Step 1 `contactor_temperature_f le=300` 文字与 impl `le=200` 偏差（PROCo-P6-8-1 已登记同源 finding，避免重复）

**小计**：6 项（3 类：SPEC 修订预留 + brief 模板 sweep + commit message 格式）

### 重构（需要重构 plan）

编号格式：`REF-<batch>-<seq>`

| ID | Batch | 文件 / 范围 | 描述 | 严重性 | 行动 |
|---|---|---|---|---|---|
| REF-P6-8-1 | P6-8 | `glycol_dehydration_service.py`（T5 F5/F6） | 双字段冗余同源 + `boeboiler_duty_btu_hr` 字段名不变但实现被 T1 覆盖 | LOW | 重构 plan（拆分 + 字段命名统一） |
| REF-P6-8-2 | P6-8 | `glycol_dehydration_service.py` + `_calc_*` helpers（4 子模块） | P6-8 落地后 `_calc_reboiler_duty` / `_calc_stripping_gas_rate` / `_calc_full_column_diameter` / `_calc_lean_glycol_concentration_wt_pct` 4 函数 + `_DewpointResult` + WARNING 字段集中管理 → 可拆为 `_glycol_dehydration/reboilers.py` 子模块 | INFO | 重构 plan（建议 P7-0） |

**小计**：2 项（P6-8 glycol 子模块拆分 + 字段命名去冗余）

### 总计：21 项 = 5 + 8 + 6 + 2 ✓

---

## 推荐下游 batch

### P6-9-PICKUP-5（建议）：工艺计算正确性 + 重构（7 项）

**范围**：
- PROCo-P6-7-{1,2,3}：工艺室标定对账 3 项（待 OPEN-P6-6A-9.5 / OPEN-P6-6A-11 2026-11-15 / 2026-11-30 交付）
- PROCo-P6-8-{1,3}：glycol dehydration 2 子模块精度校准（待 OPEN-P6-9-PICKUP-2-1 工艺室 k_strip + Antoine A/B 校准交付）
- REF-P6-8-{1,2}：2 项 glycol 重构（拆分 `_glycol_dehydration/` 子模块 + 字段命名去冗余）

**触发**：OPEN-P6-6A-9.5 / OPEN-P6-6A-11 / OPEN-P6-9-PICKUP-2-1 工艺室交付后启动

**预计工时**：~2.0 天（依赖工艺室交付）

### P6-9-PICKUP-6（建议）：代码卫生 + documentation（14 项）

**范围**：
- HYG-*-{1..8}：8 项 ruff/whitespace 类修复（`ruff check --fix` + 手工 `pre-commit` 配置）
- DOC-*-{1..6}：6 项 SPEC/brief/commit message 格式同步

**触发**：与 P6-9-PICKUP-5 并行可启动，无外部依赖

**预计工时**：~1.0 天（单文件分批 commit）

---

## 工艺室 2026-11-15 交付对账预留位（P6-9-PICKUP-4 T4 跟踪）

| OPEN | 关联 LOW/INFO | 状态 |
|---|---|---|
| OPEN-P6-6A-10 | DOC-P6-8-1（partial）/ REF-P6-8-2 | 工艺室 2026-11-15 AS 1210-2010 PDF 升级 confidence B → A |
| OPEN-P6-9-PICKUP-2-1 | PROCo-P6-8-3（SGR Antoine k_strip 校准） | xfail，工艺室 2026-11-15 解除 |
| OPEN-P6-9-PICKUP-2-2 | （t_wall_mm 复盘报告，HIGH 已修） | 已闭环（`258d857`） |
| OPEN-P6-6A-9.5 | PROCo-P6-7-2（high_acid 系数据源） | 工艺室 2026-11-30 重发 |
| OPEN-P6-6A-11 | PROCo-P6-7-{1,3}（Nielsen 精确常数 + 3-sig-fig） | 工艺室 2026-11-30 完整 Table 2-3 |

---

## 上游总仓（archived reference）

- `docs/ce-code-review-p5-p6-summary.md`：50 findings 全范围 review summary（`cf51fdf` 落地）
- `.wolf/STATUS.md` 第 308-331 行：P6-9-PICKUP-3 findings 累积登记（21 LOW/INFO 分级）
- `docs/superpowers/plans/2026-09-30-p6-9-pickup-4-debt-cleanup-final.md` T3：本文档对应 plan

## 工艺室 2026-11-15 交付跟踪位（P6-9-PICKUP-4 闭环后）

| OPEN ID | 主题 | 前置条件 | 状态 | 关联下游 |
|---|---|---|---|---|
| OPEN-P6-6A-10 | AS 1210 PDF 到位 | 工艺室 PDF delivery | 待交付 | P6-9-PICKUP-5 + 5 → A 升级 |
| OPEN-P6-9-PICKUP-2-1 | F2 SGR 公式校准 | 工艺室校准报告 | 待交付 | pytest xfail 重测 |
| OPEN-P6-9-PICKUP-2-2 | t_wall HYSYS 对账 | 工艺室 HYSYS 验证 | 待交付 | fixture 数值重算 |

## 工艺室 2026-11-15 触发条件

- AS 1210 PDF 物理收到 + 数字可查对账
- 校准报告 → STG 模拟值与 GPSA Fig 20-7 实测值一致
- HYSYS 重做校验 → t_wall_m 实测 < 5% rel_err

## 影响范围（OPEN 状态变化）

| OPEN | 交付前 | 交付后 |
|---|---|---|
| OPEN-P6-6A-10 | partial closure | confidence B → A 升级 + partial closure → close |
| OPEN-P6-9-PICKUP-2-1 | partial closure（k_strip 待校准）| 校准后重测 pytest → close |
| OPEN-P6-9-PICKUP-2-2 | partial closure（t_wall HYSYS 待验证）| HYSYS 后 fixture 数值重算 → close |
