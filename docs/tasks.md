# tasks.md — PCS 工艺计算 + 代码债务分类跟踪

> 来源：P6-9-PICKUP-4 T3（2026-09-30）
> 上游：`docs/ce-code-review-p5-p6-summary.md` 50 findings（5 batch × 47 commits）
> 中游：`docs/superpowers/plans/2026-11-15-p6-9-pickup-3-debt-cleanup.md` T5 累积登记（`93a1417`）
> 本文件：22 LOW/INFO 项 4 维分类 + 下游 batch 推荐（上游 21 项 + P6-9-PICKUP-5 5B R=1 新立 PROCo-P6-7-4）

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

## P6-9-PICKUP-5 候选跟踪（22 LOW/INFO 4 维分类）

### 工艺计算正确性（需工艺室对账）

编号格式：`PROCo-<batch>-<seq>`

| ID | Batch | 文件 / 范围 | 描述 | 严重性 | 状态 |
|---|---|---|---|---|---|
| PROCo-P6-7-1 | P6-7 | `pcs-backend/app/services/hydrate_inhibition_service.py`（T3 Nielsen 1988） | 工艺室标定 -0.00645 vs PCS 严格 -0.00754（~17% 差异），工艺室后续澄清 | LOW | OPEN-工艺室 |
| PROCo-P6-7-2 | P6-7 | `pcs-backend/data/behr_coefficients.json`（T2 Behr high_acid） | high_acid 系数不自洽（工艺室 2026-11-15 重发） | LOW | 待 OPEN-P6-6A-9.5 |
| PROCo-P6-7-3 | P6-7 | `pcs-backend/tests/services/psychro/test_*_fixtures*.py`（T8 path b） | fixture 3-sig-fig 近似（C3H8 path b 1.81% diff, dual-tolerance 容纳） | LOW/INFO | OPEN-工艺室 |
| PROCo-P6-8-1 | P6-8 | `pcs-backend/app/services/psychro/glycol_dehydration_service.py`（T1 contactor_temperature_f 范围校验） | brief Step 1 `contactor_temperature_f le=300` vs impl `le=200`（工艺室口径差异） | LOW | 待澄清 |
| PROCo-P6-8-3 | P6-8 | `glycol_dehydration_service.py`（T1 SGR 单位混算） | SGR 单位混算（psi vs mmHg），P6-9-PICKUP-2 T2 部分修复（公式结构），**Antoine A=15.30/B=8500 待工艺室校准** | LOW | OPEN-P6-9-PICKUP-2-1（xfail） |
| PROCo-P6-7-4 | P6-7 | `pcs-backend/app/services/psychro/hydrate_inhibition_service.py:257`（Nielsen 1988 path） | **Nielsen 1988 路径 `x` 摩尔/质量口径漂移**：Nielsen 原式 `x` 为液相**摩尔**分数，代码取 `inhibitor_concentration_in_water_wt_pct / 100.0` 即**质量**分数。质量分数数值恒大于同 wt% 对应的摩尔分数（M_wt = 1/(1 + (M_inhib/M_water)(w/w)·(1-w)/w) 量级），致 `NIELSEN_1988` 路径温降系统性高估：MEOH ≈1.8× / MEG ≈3.4× / TEG ≈8.3×。**仅命中 `NIELSEN_1988` 显式 path；默认 `HAMMERSCHMIDT_1934` 不受影响**（该路径用 Hammerschmidt 质量分数式，本就无漂移） | MEDIUM | **OPEN-工艺室**：待 Nielsen 1988 原文复核 + 工艺室裁定口径（按 mol frac 重算 vs 保留 wt% 近似并登记容差）｜**2026-09-30 由 P6-9-PICKUP-5 5B DOC-P6-6B-2 拆出**：该项仅文档化口径漂移（docstring 摩尔→质量），**未修代码**，故不计入 5B 闭环 |

> **dropped PROCo-P6-8-{2,4}**：brief q_total 数值偏差已 P6-9-PICKUP-2 闭环；Fig 20-4 完整曲线 HIGH 范畴同 PICKUP-2 T1 else-branch 部分修复（remaining 工艺室交付走 OPEN-P6-9-PICKUP-2-1，不重复登记 LOW）

**小计**：6 项（3 OPEN-工艺室 + 1 待 OPEN-P6-6A-9.5 + 1 待澄清 + 1 OPEN-P6-9-PICKUP-2-1）→ **全部保留 OPEN（P6-9-PICKUP-5/6 范围外）**。其中 PROCo-P6-7-4 为 P6-9-PICKUP-5 5B 新增登记。

### 代码卫生（自动化工具可修）

编号格式：`HYG-<batch>-<seq>`

| ID | Batch | 文件 / 范围 | 描述 | 严重性 | 工具 |
|---|---|---|---|---|---|
| HYG-P6-6B-1 | P6-6B | `pcs-backend/alembic/versions/*` (T3 4 项) | doc-string 格式 nit（4 项 ruff D规则） | LOW | `ruff --fix` — **CLOSED** via P6-9-PICKUP-5 5A commit `60444e5`（file-level diff）：`pyproject.toml` `extend-exclude` 移除 `**/alembic/versions/**`（原 `["**/fixtures/**","**/alembic/versions/**","**/migrations/**"]` → `["**/fixtures/**","**/migrations/**"]`），`select` 由 `["E","F","I","UP","B"]` 增补 `"D"`；同 commit 15 个 `alembic/versions/p6_*.py` 全量清 D 规则。D 规则对 `app/**` / `tests/**` / `scripts/**` 采用 `extend-per-file-ignores` 分批推进（staged adoption，pyproject 内已注明理由：全局启用将暴露 12263 errors，超出 5A 授权范围），非永久豁免 |
| HYG-P6-6B-2 | P6-6B | `pcs-backend/app/services/psychro/*` (T12 3 项) | ruff/seed 偏差（3 项 E501/F841） | LOW | `ruff --fix` — **CLOSED** via P6-9-PICKUP-3 ruff 18 fixes |
| HYG-P6-7-1 | P6-7 | `app/services/psychro/glycol_dehydration_service.py` lines 352 / 676 | 2 ruff errors pre-existing（E501 长行 + F841 unused `T_LOW`） | LOW | `ruff --fix`（P6-9-PICKUP-3 已分 5 批修过同批类似文件，本项残留）— **CLOSED** via P6-9-PICKUP-3 ruff 18 fixes |
| HYG-P6-8-1 | P6-8 | `pcs-backend/tests/services/psychro/fixtures/*.json` | fixture JSON 末尾缺换行符（T2 O-T2-1） | INFO | `pre-commit end-of-file-fixer` — **CLOSED** via P6-9-PICKUP-5 5A commit `60444e5`（file-level diff，`golden_c16_stripping_gas_rate.json`：`-}` / *No newline at end of file* → `+}`，末字节 0x0a 已核）；根因（仓库无 `.pre-commit-config.yaml`）以 `.gitattributes`（`* text=auto eol=lf`）替代闭环 —— user ruling 2026-09-30 跳过 pre-commit 外部集成，**非**引入 pre-commit config |
| HYG-P5-0-1 | P5-0 | `pcs-backend/app/services/psv/*` | pre-existing ruff/whitespace 类（与 P5-3 ruff 18 累积同类） | LOW | `ruff --fix` — **CLOSED** via P6-9-PICKUP-3 ruff 18 fixes |
| HYG-P5-0-2 | P5-0 | `pcs-backend/tests/services/psv/*` | pre-existing ruff nit（待沉淀） | LOW | `ruff --fix` — **CLOSED** via P6-9-PICKUP-3 ruff 18 fixes |
| HYG-P5-123-1 | P5-123 | `pcs-backend/app/services/heat_exchanger/*` | pre-existing whitespace / unused imports | LOW | `ruff --fix` — **CLOSED** via P6-9-PICKUP-3 ruff 18 fixes |
| HYG-P5-123-2 | P5-123 | `pcs-backend/tests/services/cv/*` | pre-existing long-line / f-string nit | INFO | `ruff --fix` — **CLOSED** via P6-9-PICKUP-3 ruff 18 fixes |

> **dropped HYG-P6-8-2**：`pyproject.toml ruff B018` extend-exclude 配置 out of scope（属 P6-9-PICKUP-6 之外的 meta-config 范畴）

**小计**：8 项 → **P6-9-PICKUP-6 闭环 6 项**（HYG-P6-6B-2 / P6-7-1 / P5-0-1 / P5-0-2 / P5-123-1 / P5-123-2，均在 ruff 全局检查覆盖范围内）；**保留 OPEN 2 项**（HYG-P6-6B-1 需改 `pyproject.toml` 配置、HYG-P6-8-1 需引入 pre-commit config — 均超出 docs-only 批范围）

### Documentation（人工 review + 文档更新）

编号格式：`DOC-<batch>-<seq>`

| ID | Batch | 文件 / 范围 | 描述 | 严重性 | 行动 |
|---|---|---|---|---|---|
| DOC-P6-6B-1 | P6-6B | `pcs-backend/app/services/psychro/glycol_dehydration_service.py` docstring (T3 4 项) | docstring nit（4 项 doc-style + 中文标点 + rst格式） | LOW | 人工 review — **CLOSED** via P6-9-PICKUP-5 5B commit `fd56fa8` + 本 commit（5B R=1 fix）（file-level diff，行号为 5B R=1 fix commit 落地后终态）：顶部模块 docstring L16-23 ASCII 标点→全角 CJK 标点（`Linear placeholder, `→`Linear placeholder；`；`diff method, `→`diff method，`）+ 中英术语补全（`Stripping gas rate`→`汽提气率 stripping gas rate` / `Reboiler duty`→`再沸器负荷 reboiler duty` 等）；L27-28 公式列对齐；L58 全角冒号 `：`→半角 `: `；L78-79 悬空折行收敛（`lean glycol）` 不再断行）；L81-88 新增「术语约定（中文 → 英文，全文统一）」7 条；`_DewpointResult` L296-300 三态改 RST 列表；`GlycolDehydrationInput` L335 补 P6-8 T5 的 2 字段；`GlycolDehydrationResult` L391 补 P6-8 T5 的 4 输出 + `warnings`；常量 L115 `gal H2O`→`lb H2O`） |
| DOC-P6-6B-2 | P6-6B | `pcs-backend/app/services/psychro/hydrate_inhibition_service.py` (T8 4 项) | spec deviation（4 项 spec 与实现小幅漂移） | LOW | SPEC V1.13 修订预留 — **CLOSED** via P6-9-PICKUP-5 5B commit `fd56fa8`（file-level diff：L21 摩尔分数→质量分数（wt%/100 粗换）；L51-52 模块 docstring 尾段同步；L257 新增行内注释说明不做摩尔质量换算。零数值改动，零 fixture 改动。**遗留量级偏差见 PROCo-P6-7-4**） |
| DOC-P6-8-1 | P6-8 | `spec/PCS-SPEC-ADD-001 计算覆盖增补规格说明书.md` §3.9.1 C-16 | P6-8 实施后 12 result fields 文档同步（部分含 OUT_OF_SCOPE 引用） | INFO | **CLOSED** via P6-9-PICKUP-5 5B commit `2f2e80a`（file-level diff：版本头 L3 V1.12→V1.13；§3.9.1 L883-896 新增 V1.13 段登记 P6-8 T5 的 4 字段，L896 字段总数对账 7+12+4=23（`dataclasses.fields` 实测一致）；§3.9.1 实现落点行号 `:294`→`:365`（`ae91e75` 顶部 docstring 增 9 行后再校准）；§9 变更记录 L1182 增 V1.13 row。V1.10 实施基线冻结声明保留。**注：原行动列误指 `docs/PCS-UI-SPEC.md`，user ruling 2026-09-30 更正为 ADD-001**） |
| DOC-P5-0-1 | P5-0 | `docs/PCS-PLAN-P5-DEVICE-EQUIPMENT.md` | P5-0 实施后 5 commits 部分内容与计划文档 nit（待沉淀） | LOW | 人工 review — **CLOSED** via P6-9-PICKUP-5 5B commit `fd56fa8` + 本 commit（5B R=1 fix）（file-level diff，行号为 5B R=1 fix commit 落地后终态）：L41 P5-0 章节头补 P5-0-4a 标注；L54 registry 12 类→8 类（落地 `40b0c69`）+ 注明累加至 20 类；L57 RED 步同步；L60 Task 1 commit 行 7 tables→3 tables；L112 Task 4 commit 行 `p5-0-4`→`p5-0-4a`（落地 `34ab33e`）；L520 前置任务章节头 `Task 24/25`→`Task 24/25/26`；**M1** Task 1 表数 4/7/7/3 → 统一落地口径 3 表（L45 新增说明块记录 4 蒸汽表至今未落地、推迟为 P5-0-1b，scope 保留） |
| DOC-P5-123-1 | P5-123 | `docs/PCS-PLAN-P5-DEVICE-EQUIPMENT.md` | P5-123 实施后 5 commits 部分内容与计划文档 nit（待沉淀） | LOW | 人工 review — **OPEN（撤回）**：user ruling 2026-09-30 撤回；`grep -c "P5-123"` = 0（全仓无对应 finding 可溯），无证据支撑，不予闭环 |
| DOC-P5-123-2 | P5-123 | `README.md` / `CHANGELOG.md` | P5-123 commit message 格式 nit（待沉淀） | INFO | 人工 review — **OPEN（撤回）**：user ruling 2026-09-30 撤回；同 DOC-P5-123-1，0 matches 无证据，不予闭环 |

> **dropped DOC-P6-7-1**：brief 模板高温系数 nit（LOW 范畴，P6-9-PICKUP-6 brief 模板批改时一并 sweep）
> **dropped DOC-P6-8-2**：brief Step 1 `contactor_temperature_f le=300` 文字与 impl `le=200` 偏差（PROCo-P6-8-1 已登记同源 finding，避免重复）

**小计**：6 项 → **P6-9-PICKUP-5 5B 闭环 4 项**（DOC-P6-6B-1 / DOC-P6-6B-2 / DOC-P6-8-1 / DOC-P5-0-1，均有 file-level diff 证据）；**保留 OPEN 2 项**（DOC-P5-123-1 / DOC-P5-123-2 — user ruling 2026-09-30 撤回，0 matches 无证据）

### 重构（需要重构 plan）

编号格式：`REF-<batch>-<seq>`

| ID | Batch | 文件 / 范围 | 描述 | 严重性 | 行动 |
|---|---|---|---|---|---|
| REF-P6-8-1 | P6-8 | `glycol_dehydration_service.py`（T5 F5/F6） | 双字段冗余同源 + `boeboiler_duty_btu_hr` 字段名不变但实现被 T1 覆盖 | LOW | **CLOSED** via P6-9-PICKUP-5 5C 本 commit（file-level diff，行号为 5C 落地后终态）：`glycol_dehydration_service.py` 移除 v5.1 简式 `_calc_reboiler_duty_simple_btu_hr`（原 L773-800）及其 L1000-1006 唯一调用点；L694 现为 `reboiler_duty_btu_hr = reb_strip_result.q_total_btu_hr` **唯一**来源（L665 注释标注）；连带 orphan 常量 `_REBOILER_CP_TEG_BTU_PER_LB_F` / `_REBOILER_CP_WATER_BTU_PER_LB_F` / `_REBOILER_DT_F` / `_REBOILER_DH_VAP_BTU_PER_LB` 同步移除。`reboiler_duty_btu_hr` 字段名 + 语义（= 完整负荷含 +10% 裕度）不变，public API 0 改动。**未**移除 `_calc_stripping_gas_rate_scf_per_gal_teg`（现 L463 docstring / L648 调用点）：它填 result 字段 `stripping_gas_scf_per_gal_teg`（占位 k=1.5），与 reboilers 的 `stripping_gas_rate_scf_gal`（Antoine 真 P_sat, k=6.5）是**两个不同字段 + 两个不同公式**，非冗余；`app/schemas/psychro.py:749` + `app/api/v1/psychro.py:480` 依赖前者，移除即破坏 API |
| REF-P6-8-2 | P6-8 | `glycol_dehydration_service.py` + `_calc_*` helpers（4 子模块） | P6-8 落地后 `_calc_reboiler_duty` / `_calc_stripping_gas_rate` / `_calc_full_column_diameter` / `_calc_lean_glycol_concentration_wt_pct` 4 函数 + `_DewpointResult` + WARNING 字段集中管理 → 可拆为 `_glycol_dehydration/reboilers.py` 子模块 | INFO | **CLOSED** via P6-9-PICKUP-5 5C 本 commit（file-level diff，行号为 5C 落地后终态）：新增私有子包 `pcs-backend/app/services/psychro/_glycol_dehydration/` 4 文件 —— `__init__.py`（43 LOC，public 三件套重导出）/ `behr.py`（267 LOC；`BehrBaseline` L32、`_BEHR_GRID_PATH` L38、`BehrGrid` L56、`_load_behr_grids` L72、`_BEHR_GRIDS` L106、`_bilinear_interp_behr` L109、`_correct_behr_for_acid_gas` L150、`_calc_behr_water_content_lb_per_mmscf` L184）/ `dewpoint.py`（128 LOC；`_DewpointResult` L31、`_behr_inverse_dewpoint` L47）/ `reboilers.py`（312 LOC；`ReboilerStrippingInput` L46、`ReboilerStrippingResult` L71、`_calc_reboiler_duty_btu_hr` L94、`_calc_stripping_gas_rate_scf_gal_teg` L156、`LeanGlycolDataPoint` L199、`_calc_lean_glycol_concentration_wt_pct` L217、`calc_reboiler_stripping` L267）。`glycol_dehydration_service.py` 1423 → 791 LOC（< 800 ✓），子模块各 < 400 ✓。依赖方向单向无环：`dewpoint → behr`，`reboilers` / `behr` 仅 stdlib |

**小计**：2 项 → **P6-9-PICKUP-5 5C 闭环 2 项**（REF-P6-8-1 字段去冗余 + REF-P6-8-2 子模块拆分，均有 file-level diff 证据）；**0 项保留 OPEN**

### 总计：22 项 = 6 + 8 + 6 + 2 ✓

**闭环状态：as of 2026-09-30**（P6-9-PICKUP-5 5C + R=1 修正后）

| 维度 | 总数 | CLOSED | OPEN |
|---|---|---|---|
| HYG（hygiene） | 8 | **8** | 0 |
| DOC（文档） | 6 | 4 | 2 |
| PROCo（工艺正确性） | 6 | 0 | **6** |
| REF（重构） | 2 | **2** | 0 |
| **合计** | **22** | **14** | **8** |

**14 项 CLOSED**，逐批 file-level diff 证据来源：
- P6-9-PICKUP-6 R=1 闭环 **6 项**（HYG-P6-6B-2 / HYG-P6-7-1 / HYG-P5-0-1 / HYG-P5-0-2 / HYG-P5-123-1 / HYG-P5-123-2，均在 ruff 全局检查覆盖范围内）
- P6-9-PICKUP-5 5A（`60444e5`）闭环 **2 项**（HYG-P6-6B-1 / HYG-P6-8-1）
- P6-9-PICKUP-5 5B 闭环 **4 项**（DOC-P6-6B-1 / DOC-P6-6B-2 / DOC-P6-8-1 / DOC-P5-0-1）
- P6-9-PICKUP-5 5C 本 commit 闭环 **2 项**（REF-P6-8-1 字段去冗余 + REF-P6-8-2 `_glycol_dehydration/` 子模块拆分）

**8 项保留 OPEN**：
- PROCo-P6-7-{1,2,3,4} + PROCo-P6-8-{1,3} 共 **6 项** —— 全部待工艺室标定对账（OPEN-P6-6A-9.5 / OPEN-P6-6A-11 2026-11-15 / OPEN-P6-9-PICKUP-2-1；PROCo-P6-8-1 为待澄清、PROCo-P6-8-3 为 xfail）
- DOC-P5-123-{1,2} 共 **2 项** —— user ruling 2026-09-30 撤回；`grep -c "P5-123"` = 0（全仓无对应 finding 可溯），无证据支撑，不予闭环

> **注**：本段取代 P6-9-PICKUP-6 单批视角的旧表述（原「仅 6 项 CLOSED / 15 项保留 OPEN」）。该口径在 5A / 5B / 5C 落地后已失效 —— 5A + 5B + 5C 合计再闭环 8 项，HYG 与 REF 两个维度均已归零。

> **本批实际范围**：P6-9-PICKUP-6 为 **docs-only 批**。仅当 finding 落在 ruff 全局检查（`select=["E","F","I","UP","B"]`、排除 `**/fixtures/**` + `**/alembic/versions/**` + `**/migrations/**`）覆盖范围内时方可闭环。**超出该范围者一律保留 OPEN，转后续非 docs 批处理**：`docs/P6-9-PICKUP-4.md` 系分类/路由文档，不构成 finding 的实际修复证据。3 OPEN 跟踪位（OPEN-P6-6A-10 / OPEN-P6-9-PICKUP-2-1 / OPEN-P6-9-PICKUP-2-2）不变。

---

## 推荐下游 batch

### P6-9-PICKUP-5（执行中）：工艺计算正确性 + 重构（8 项登记，2 项已闭环）

**范围**：
- PROCo-P6-7-{1,2,3,4}：工艺室标定对账 4 项（待 OPEN-P6-6A-9.5 / OPEN-P6-6A-11 2026-11-15 / 2026-11-30 交付；PROCo-P6-7-4 待 Nielsen 1988 原文复核 + 工艺室裁定 x 摩尔/质量口径，5B R=1 新立）
- PROCo-P6-8-{1,3}：glycol dehydration 2 子模块精度校准（待 OPEN-P6-9-PICKUP-2-1 工艺室 k_strip + Antoine A/B 校准交付）
- REF-P6-8-{1,2}：2 项 glycol 重构 —— **已闭环**（5A 2 HYG + 5B 4 DOC + 5C 2 REF；REF 2 项见 5C 本 commit）

**触发**：PROCo 6 项待 OPEN-P6-6A-9.5 / OPEN-P6-6A-11 / OPEN-P6-9-PICKUP-2-1 工艺室交付后启动

**预计工时**：~2.0 天（依赖工艺室交付）

### P6-9-PICKUP-6（已执行，docs-only）：6 项闭环

**实际闭环 6 项**（ruff 全局检查覆盖范围内）：HYG-P6-6B-2 / HYG-P6-7-1 / HYG-P5-0-1 / HYG-P5-0-2 / HYG-P5-123-1 / HYG-P5-123-2

**转出 8 项 → 需非 docs 批**（**均已在 P6-9-PICKUP-5 闭环**，本段保留为历史记录）：
- HYG-P6-6B-1：需改 `pyproject.toml`（移除 `**/alembic/versions/**` 排除 + `select` 加 `D`）后 ruff 方可见，属 meta-config 变更 → **CLOSED** via 5A `60444e5`
- HYG-P6-8-1：需引入 `.pre-commit-config.yaml` 并启用 `end-of-file-fixer`（仓库当前无此文件）→ **CLOSED** via 5A `60444e5`（`.gitattributes` 替代方案，user ruling 跳过 pre-commit 外部集成）
- DOC-* 6 项：需实际编辑 service docstring / `docs/PCS-UI-SPEC.md` / `docs/PCS-PLAN-P5-DEVICE-EQUIPMENT.md` / `README.md` / `CHANGELOG.md` → **4 项 CLOSED** via 5B（DOC-P6-6B-1 / DOC-P6-6B-2 / DOC-P6-8-1 / DOC-P5-0-1）；DOC-P5-123-{1,2} 撤回不予闭环

**触发**：转出项随下一非 docs-only 批启动，无外部依赖

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
