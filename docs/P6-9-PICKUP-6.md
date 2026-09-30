# P6-9-PICKUP-5 工艺债务批 archive

> 来源：P6-9-PICKUP-6 docs-only 批（2026-09-30）
> 上游：`docs/tasks.md` 22 项 findings（21 + P6-7-4 Nielsen x 口径漂移，5B R=1 新立）
> 本文档：P6-9-PICKUP-5 全 7 commits SHA + 14 CLOSED / 8 OPEN 详情 + R=1 lessons + 5D 触发 plan
> 锚定版本：PCS main @ `9df10cc`（P6-9-PICKUP-5 5C R=1 落点）

## Context

`docs/tasks.md` 记录 `docs/ce-code-review-p5-p6-summary.md`（50 findings）的 LOW/INFO 分级台账。P6-9-PICKUP-4 收口时留下 21 项 LOW/INFO 未处理，分 4 维：

| 维度 | 总数 | 含义 | 处置方式 |
|---|---|---|---|
| HYG | 8 | 代码卫生（ruff / whitespace）| `ruff --fix` 或 config 变更 |
| DOC | 6 | 文档/spec 漂移 | 人工 review + SPEC 修订 |
| PROCo | 6 | 工艺计算正确性 | 工艺室对账（外部依赖）|
| REF | 2 | 重构（glycol dehydration 单文件膨胀）| 拆子模块 |
| **合计** | **22** | | |

P6-9-PICKUP-5 分 3 子批落地（5A / 5B / 5C，共 7 commits）：HYG 8 全清 + DOC 4 闭环 + REF 2 闭环；PROCo 6 与 DOC 2 保留 OPEN。P6-9-PICKUP-6（docs-only）做 5D 工艺室触发 schedule 文档化 + 本 archive 落地。

---

## 来源 + 分布

21 → 22 findings（5B R=1 新立 PROCo-P6-7-4，从 DOC-P6-6B-2 spec deviation 拆出）。最终 4 维分布：

| 维度 | 总数 | CLOSED | OPEN |
|---|---|---|---|
| HYG | 8 | **8** | 0 |
| DOC | 6 | 4 | 2（撤回） |
| PROCo | 6 | 0 | **6**（工艺室对账）|
| REF | 2 | **2** | 0 |
| **合计** | **22** | **14** | **8** |

**测试基线**：pytest 3515 passed / 5 skipped / 1 xfailed / 0 failed；ruff `All checks passed!`；G-08 phase 1-4 drift=0。

---

## HYG-2 ruff D + .gitattributes（5A `60444e5`）

**规模**：85 files, +268/-243。

| 改动 | 内容 |
|---|---|
| `pcs-backend/pyproject.toml` | `extend-exclude` 移除 `**/alembic/versions/**`（`["**/fixtures/**","**/alembic/versions/**","**/migrations/**"]` → `["**/fixtures/**","**/migrations/**"]`）；`select` 由 `["E","F","I","UP","B"]` 增补 `"D"`；新增 `[tool.ruff.lint.extend-per-file-ignores]` 豁免 `app/**` `tests/**` `scripts/**` |
| `alembic/versions/*.py` | 15 个 `p6_*.py` + `p1_*` / `p2_*` 全量清 D 规则，共 508 errors：autofix 20 + 手工 488（D400/D415 218 处 docstring 首行句号、D103 8 处补 docstring、D205 4 处补 summary 空行）|
| `.gitattributes`（新增）| `* text=auto eol=lf`，替代 pre-commit `end-of-file-fixer` |
| `tests/.../fixtures/golden_c16_stripping_gas_rate.json` | 补末尾换行（`-}` / *No newline at end of file* → `+}`）|

**闭环对应**：HYG-P6-6B-1（alembic doc-string D 规则）+ HYG-P6-8-1（fixture JSON 缺末尾换行）。

**关键判断**：中文 docstring 以 `。` 收尾 ruff 不认，统一替换为 ASCII `.` 且单一句号不重复标点。

---

## DOC-4 SPEC V1.13 + service docstring（5B 4 commits）

### `fd56fa8` — DOC-4 闭环 3/4（4 files, +39/-16）

- `docs/PCS-PLAN-P5-DEVICE-EQUIPMENT.md` 12 行 nit
- `app/services/psychro/glycol_dehydration_service.py` docstring
- `app/services/psychro/hydrate_inhibition_service.py`：L21「`x` 摩尔分数」→「质量分数（wt% / 100 粗换，非摩尔分数）」，与 `_calculate_nielsen_depression_full` L257 实际算法（`wt_pct / 100.0`，无摩尔质量换算）对齐 + 新增行内注释。**零数值改动，零 fixture 改动**

### `2f2e80a` — DOC-P6-8-1 闭环（2 files, +18/-4）

`spec/PCS-SPEC-ADD-001 计算覆盖增补规格说明书.md` V1.12 → V1.13：§3.9.1 C-16 `GlycolDehydrationResult` 字段清单 12 → 23 项（7 + 12 + 4，新增 P6-8 T5 的 `reboiler_duty_kw` / `stripping_gas_rate_scf_gal` / `lean_glycol_concentration_wt_pct` / `warnings`，与 `dataclasses.fields` 实测一致）；§3.9.1 实现落点行号 `:294` → `:365`；§9 changelog 增 V1.13 row。V1.10 实施基线保持冻结。

### `ae91e75` — 5B R=1 fix（4 files, +42/-23）

`docs/tasks.md` 状态流转 + 顶部 docstring + Task 1 表数；**新立 PROCo-P6-7-4**（Nielsen 1988 路径 `x` 摩尔/质量口径漂移，MEDIUM，从 DOC-P6-6B-2 拆出）；`glycol_dehydration_service.py` 补「术语约定（中文 → 英文，全文统一）」7 条。

### `dbdd6a1` — 5B R=2 fix（3 files, +7/-7）

`CHANGELOG.md` 死 SHA 修正 + 标点方向勘误 + 行号 356 → 365。

**闭环对应**：DOC-P6-6B-1 / DOC-P6-6B-2 / DOC-P6-8-1 / DOC-P5-0-1。

---

## REF-2 子模块拆分（5C `d8f97dd` + `9df10cc`）

### `d8f97dd`（12 files, +840/-712）

新增私有子包 `pcs-backend/app/services/psychro/_glycol_dehydration/` 4 文件：

| 文件 | LOC | 内容 |
|---|---|---|
| `__init__.py` | 43 | public 三件套重导出 |
| `behr.py` | 267 | `BehrBaseline` L32 / `_BEHR_GRID_PATH` L38 / `BehrGrid` L56 / `_load_behr_grids` L72 / `_BEHR_GRIDS` L106 / `_bilinear_interp_behr` L109 / `_correct_behr_for_acid_gas` L150 / `_calc_behr_water_content_lb_per_mmscf` L184 |
| `dewpoint.py` | 128 | `_DewpointResult` L31 / `_behr_inverse_dewpoint` L47 |
| `reboilers.py` | 312 | `ReboilerStrippingInput` L46 / `ReboilerStrippingResult` L71 / `_calc_reboiler_duty_btu_hr` L94 / `_calc_stripping_gas_rate_scf_gal_teg` L156 / `LeanGlycolDataPoint` L199 / `_calc_lean_glycol_concentration_wt_pct` L217 / `calc_reboiler_stripping` L267 |

`glycol_dehydration_service.py` **1423 → 791 LOC**（< 800 ✓），子模块各 < 400 ✓。依赖方向单向无环：`dewpoint → behr`，`reboilers` / `behr` 仅 stdlib。

REF-P6-8-1（字段去冗余）：移除 v5.1 简式 `_calc_reboiler_duty_simple_btu_hr`（原 L773-800）及其 L1000-1006 唯一调用点；`reboiler_duty_btu_hr` 现唯一来源为 `reboiler_duty_btu_hr = reb_strip_result.q_total_btu_hr`；连带移除 4 个 orphan 常量（`_REBOILER_CP_TEG_BTU_PER_LB_F` / `_REBOILER_CP_WATER_BTU_PER_LB_F` / `_REBOILER_DT_F` / `_REBOILER_DH_VAP_BTU_PER_LB`）。字段名 + 语义（= 完整负荷含 +10% 裕度）不变，public API 0 改动。

### `9df10cc` — 5C R=1 fix（1 file, +34/-14）

`docs/tasks.md` 全局统计口径失效修正：总计 22 = 6 PROCo + 8 HYG + 6 DOC + 2 REF；14 CLOSED / 8 OPEN 逐批归属回填。

---

## R=1 教训

### 3 条 implementer judgment call（全部成立，均为拒 brief 错指令）

| # | 子批 | brief 指令 | 实施方判断 | 依据 |
|---|---|---|---|---|
| 1 | 5A | 直接全量开 ruff `D` | 改用 `extend-per-file-ignores` 豁免 `app/**` `tests/**` `scripts/**` | 全局启用 D 一次性暴露 **12263 errors**，超出 5A「不动 service code / tests」授权范围；pyproject 内注释明记为 staged adoption、非永久豁免，后续批次逐目录解除 |
| 2 | 5B | DOC-P6-8-1 改 `docs/PCS-UI-SPEC.md` | 更正为 `spec/PCS-SPEC-ADD-001 计算覆盖增补规格说明书.md` | user ruling 2026-09-30；SPEC V1.12 → V1.13 |
| 3 | 5C | 去重 `_calc_stripping_gas_rate_scf_per_gal_teg` | **拒绝执行** | 它填 result 字段 `stripping_gas_scf_per_gal_teg`（占位 k=1.5），与 `stripping_gas_rate_scf_gal`（Antoine 真 P_sat, k=6.5）是**两个不同字段 + 两个不同公式**，非冗余；`app/schemas/psychro.py:749` + `app/api/v1/psychro.py:480` 依赖前者，移除即破坏 API |

### ledger accuracy 修复模式

R=1 / R=2 两轮共 4 commits（`ae91e75` / `dbdd6a1` / `9df10cc`）全部是**台账准确性**修复，非功能改动：状态列 OPEN → CLOSED 附 file-level diff 行号证据、CHANGELOG 死 SHA、标点方向、行号漂移（356 → 365）、全局统计口径重算。**任何 closure 状态回填必须指向 file-level diff**（不指分类 / 路由文档）—— `docs/P6-9-PICKUP-4.md` 系分类/路由文档，不构成 finding 的实际修复证据。

### self-referential SHA 死锁

5C R=1（`9df10cc`）修改的正是记录自身 commit 的台账（`docs/tasks.md`），commit SHA 在写入时尚不存在。规避方式：台账中该行引用「5C 本 commit」而非硬编码 SHA，SHA 由 archive（本文档）事后补全。

---

## 5D 工艺室触发 schedule

> 权威来源：`.wolf/STATUS.md:174-177`「P6-6B 工艺工程师对 OPEN 队列的决策」（工艺室 2026-09-28 签署，11 项 OPEN，总工时 ~8.5 天）。
> 完整表格见 `docs/tasks.md` §5D 工艺室触发 schedule。

| 触发日期 | 工艺室交付 OPEN items | 本批 PROCo 触发 | 5D 子批 | 工时估算 |
|---|---|---|---|---|
| 2026-10-15 | OPEN-P6-4-3 + OPEN-P6-6A-9.{1,2} + T10 + T11 | （本批无 PROCo 触发） | 5D-0 — 其他模块消化 | n/a |
| 2026-10-31 | OPEN-P6-4-4 + OPEN-P6-6A-9.{3,4}（真 Wichert-Aziz + Bukacek low-T） | （本批无 PROCo 触发） | 5D-1 — 其他模块消化 | n/a |
| 2026-11-15 | OPEN-P6-6A-10（AS 1210 PDF）+ OPEN-P6-9-PICKUP-2-{1,2}（F2 SGR + t_wall HYSYS） | PROCo-P6-8-{1,3} | 5D-2 综合工艺室交付 | ~2.5 天 |
| 2026-11-30 | OPEN-P6-6A-11（Nielsen Table 2-3）+ OPEN-P6-6A-9.5（XLS E20 baseline + 6% brine） | PROCo-P6-7-{1,2,3,4} | 5D-3 Nielsen + Behr 综合交付 | ~2.0 天 |
| 上线后 | OPEN-P6-4-2（Kb 厂商数据） | （无 PROCo 触发） | 5D-5 上线后批 | 推迟 |

**6 PROCo OPEN items 全部归属 5D-2 / 5D-3 两批**（2026-11-15 + 2026-11-30）。2026-10-15 与 2026-10-31 两批的签署 OPEN（C-08 Imperial 单位、contactor sizing 9.1~9.4、T10 / T11 路径）不落在本 22 项台账，对本批零触发。

**DOC-P5-123-{1,2} 不计入 5D 触发**：user ruling 2026-09-30 撤回，`grep -c "P5-123"` = 0，无证据可溯，保留 OPEN 跟踪位但无工艺室交付依赖。

### 3 OPEN 跟踪位（不变）

| OPEN ID | 主题 | 前置条件 | 状态 |
|---|---|---|---|
| OPEN-P6-6A-10 | AS 1210 PDF 到位 | 工艺室 PDF delivery（2026-11-15）| 待交付 |
| OPEN-P6-9-PICKUP-2-1 | F2 SGR 公式校准 | 工艺室校准报告（2026-11-15）| pytest xfail 重测 |
| OPEN-P6-9-PICKUP-2-2 | t_wall HYSYS 对账 | 工艺室 HYSYS 验证（2026-11-15）| fixture 数值重算 |

---

## 验证矩阵

| 项 | 结果 |
|---|---|
| pytest 全量 | 3515 passed / 5 skipped / 1 xfailed / 0 failed |
| ruff check | All checks passed! |
| G-08 phase 1-4 | 全过 drift=0 |
| `glycol_dehydration_service.py` LOC | 1423 → 791（< 800 ✓）|
| 子模块各 LOC | 43 / 267 / 128 / 312（各 < 400 ✓）|
| ADD-001 C-16 字段数 | 12 → 23（7 + 12 + 4，`dataclasses.fields` 实测一致）|
| docs/tasks.md 总计 | 22 = 6 + 8 + 6 + 2 ✓；14 CLOSED / 8 OPEN |

---

## 未解决问题

### 8 OPEN items

1. **PROCo-P6-7-1**（Nielsen 标定 ~17% 差异）→ 5D-3，待 OPEN-P6-6A-11
2. **PROCo-P6-7-2**（Behr high_acid 系数不自洽）→ 5D-3，待 OPEN-P6-6A-9.5
3. **PROCo-P6-7-3**（psychro fixture 3-sig-fig 近似）→ 5D-3，待 OPEN-P6-6A-11
4. **PROCo-P6-7-4**（Nielsen 1988 `x` 摩尔/质量口径漂移，MEDIUM）→ 5D-3，待 Nielsen 1988 原文复核
5. **PROCo-P6-8-1**（`contactor_temperature_f` `le=300` vs `le=200`）→ 5D-2，**无独立签署 OPEN**，随 OPEN-P6-6A-10 后 glycol dehydration 精度复核一并对账
6. **PROCo-P6-8-3**（SGR Antoine A=15.30 / B=8500）→ 5D-2，待 OPEN-P6-9-PICKUP-2-1
7. **DOC-P5-123-1**（撤回，0 matches 无证据）→ 不计入 5D
8. **DOC-P5-123-2**（撤回，0 matches 无证据）→ 不计入 5D

### R=1 教训应用

- 任何后续 closure 回填必须附 file-level diff 证据（commit SHA + 行号），分类 / 路由文档不构成修复证据
- 5A 的 `extend-per-file-ignores` 是 **staged adoption**，`app/**` / `tests/**` / `scripts/**` 的 D 规则豁免待后续批次逐目录解除
- 新立 finding（如 PROCo-P6-7-4 从 DOC 项拆出）时，总计数字需同步重算，避免全局统计口径失效

---

## 参考

- 主仓台账：`docs/tasks.md`（22 项 4 维分类 + §5D 工艺室触发 schedule）
- 上游 summary：`docs/ce-code-review-p5-p6-summary.md`（50 findings）
- 前序批 archive：`docs/P6-9-PICKUP-4.md`（21 项分类 + 工艺室对账预留位）
- 工艺室签署排期：`.wolf/STATUS.md:165-195`（P6-6B 工艺工程师对 OPEN 队列的决策）
- 实施 plan：`docs/superpowers/plans/2026-09-30-p6-9-pickup-6-process-debt-tracking.md`
