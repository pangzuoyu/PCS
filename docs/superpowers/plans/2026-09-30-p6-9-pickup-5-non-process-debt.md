# P6-9-PICKUP-5 计划 — HYG-2 + DOC-4 + REF-2 非 docs 范围闭环

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal**: 闭环 P6-9-PICKUP-6 R=1 revert 的 8 项无效 closure（HYG-2 + DOC-6 撤回 2 项 → 4 项 + REF-2）+ 工艺室 2026-11-15/30 触发项（5D，不在本计划）。

**Architecture**: 3 子批顺序执行，每子批独立 SDD workspace。HYG-2 改 ruff 配置 + pre-commit（meta-config + infra），DOC-4 改 PCS-UI-SPEC + PCS-PLAN-P5 + service docstring（docs/spec），REF-2 拆 glycol_dehydration 子模块（重构）。所有 commit 必须满足 file-level diff 证据（R=1 教训）。

**Tech Stack**: ruff 0.4+ / pre-commit 3.x / Python 3.12 / FastAPI 0.115 / SQLAlchemy 2.0 / Pydantic 2.7

**Spec**: `docs/tasks.md`（21 LOW/INFO 4 维分类 + 本计划覆盖 8 项 reverted）

## Global Constraints

- **R=1 教训（已写入 `.wolf/cerebrum.md`）**: 每个 commit 必须能指向 file-level diff；任何 closure 状态回填不可指向讨论 finding 的文档
- **docs-only 边界**: 5A 改 ruff config + pre-commit（非 docs）；5B 改 SPEC/plan/service docstring（非 docs）；5C 拆 service 子模块（非 docs）— 三子批均非 docs-only，每子批 SDD workspace 独立
- **3 OPEN 跟踪位不变**: OPEN-P6-6A-10 / OPEN-P6-9-PICKUP-2-1 / OPEN-P6-9-PICKUP-2-2
- **5 PROCo + 2 REF 保留 OPEN**（等待工艺室 2026-11-15/30 交付后启动 5D）
- **pytest baseline**: 3515 passed (P6-9-PICKUP-6 R=1 后)；CI/CD 不做（单人开发裁决）
- **SPEC V1.0 冻结**: 5B 中 PCS-UI-SPEC 修订需登记 V1.13（沿用 P6-6B V1.11→V1.12 模式，docs-only micro-revision）
- **PcsError 子类 + frozen dataclass + formula_ref dict** 模式不可破（项目级 service 模式）
- **ChEDL 包装层不可破**: 业务代码禁直接 `import fluids.*`（ADR-0030）

## Review Focus

5 个最可能咬人的输入类 / 失败模式，spec 未明示但 spec reviewer 会盯：

1. **HYG-P6-6B-1 D 规则全量修复** — 508 errors 全清？4 项原描述 vs 全量 fix 范围确认（用户已选「全量」）；autofix 20 项后剩余 488 需手改是否都做了
2. **HYG-P6-8-1 pre-commit end-of-file-fixer 实际启用** — `.pre-commit-config.yaml` 写完后是否真在 `pre-commit run --all-files` 跑过并对 1 个缺末尾换行的 fixture（`golden_c16_stripping_gas_rate.json`）生效
3. **DOC-P6-8-1 PCS-UI-SPEC V1.13 micro-revision** — §3.9.1.1 C-16 12 result fields 真落到 SPEC（不是只 changelog 一行）；P6-8 glycol dehydration 完整数据流
4. **DOC-P6-6B-2 hydrate_inhibition spec deviation 数学修正** — Line 50-53「摩尔分数」docstring vs Line 257 `wt_pct / 100.0` 代码实为 wt% 粗换；修改需同步测试 fixture 期望
5. **REF-P6-8-2 子模块拆分后 public API 兼容** — `ReboilerStrippingInput/Result` 在拆分后保持 public（P6-7 计划依赖）；`__init__.py` 重导出不可漏

---

## Sub-batch 5A: HYG-2 — ruff D 规则 + pre-commit

**Files**:
- Modify: `pcs-backend/pyproject.toml`（line 55-63 [tool.ruff] + line 60 [tool.ruff.lint]）
- Create: `.pre-commit-config.yaml`（项目根目录）
- Modify: `pcs-backend/alembic/versions/*.py`（47 文件，508 D errors → 0；autofix 20 + 手动 488）
- Modify: `pcs-backend/tests/services/psychro/fixtures/golden_c16_stripping_gas_rate.json`（缺末尾 `\n`）

**Interfaces**:
- Consumes: HYG-P6-6B-1 / HYG-P6-8-1 reverted findings (P6-9-PICKUP-6 R=1)
- Produces: ruff `pcs-backend/ --select D,all --no-cache` = 0；`pre-commit run --all-files` exit 0

**Steps**:

- [ ] **Step 1**: 修改 `pyproject.toml` — `select` 加 `"D"`；`extend-exclude` 移除 `"**/alembic/versions/**"`（保留 fixtures/migrations 排除）
- [ ] **Step 2**: 跑 `cd pcs-backend && uv run ruff check --select D alembic/versions/ 2>&1 | wc -l` 确认 508 errors
- [ ] **Step 3**: 跑 `cd pcs-backend && uv run ruff check --select D --fix alembic/versions/ 2>&1 | tail -5`（autofix 20 项）
- [ ] **Step 4**: 手动 fix 剩余 488 D errors（docstring 格式：首行大写、结尾标点、`"""` 闭合、indent 4-space、参数/返回值行首字母大写）
- [ ] **Step 5**: 跑 `cd pcs-backend && uv run ruff check . 2>&1 | tail -3` 确认 0
- [ ] **Step 6**: 创建 `.pre-commit-config.yaml` — `repos: [{repo: pre-commit/pre-commit-hooks, rev: v4.6.0, hooks: [id: end-of-file-fixer]}]`
- [ ] **Step 7**: `pre-commit install`（仓库根）+ `pre-commit run --all-files` 验证 fixture `golden_c16_stripping_gas_rate.json` 末尾补 `\n`
- [ ] **Step 8**: pytest 回归 `cd pcs-backend && DATABASE_URL=... uv run pytest tests/ -q` 期望 3515+ passed
- [ ] **Step 9**: 单 commit — `style(p6-9-pickup-5): HYG ruff D 规则全量 + pre-commit end-of-file-fixer (5A)`

## Sub-batch 5B: DOC-4 — PCS-UI-SPEC + PCS-PLAN-P5 + service docstring + CHANGELOG

**Files**:
- Modify: `docs/PCS-UI-SPEC.md`（V1.0 → V1.13 micro-revision，加 §3.9.1.1 C-16 + 12 result fields）
- Modify: `docs/PCS-PLAN-P5-DEVICE-EQUIPMENT.md`（P5-0 / P5-123 章节 nit）
- Modify: `pcs-backend/app/services/psychro/glycol_dehydration_service.py`（顶部 docstring 中文标点/RST 混排 + `_DewpointResult` 列表符号 + 常量注释）
- Modify: `pcs-backend/app/services/psychro/hydrate_inhibition_service.py`（Line 50-53「摩尔分数」vs Line 257 `wt_pct/100.0` 数学漂移）
- Modify: `CHANGELOG.md`（顶部新增 P6-9-PICKUP-5 行）

**Interfaces**:
- Consumes: DOC-P6-6B-1 / DOC-P6-6B-2 / DOC-P6-8-1 / DOC-P5-0-1（4 项；P5-123-1/2 已 drop）
- Produces: 4 项 finding 状态从 OPEN → CLOSED（file-level diff 证据：具体行号 + 改动内容）
- **DO NOT touch**（保持显式撤回）: 任何 P5-123 引用（0 matches，finding 已 drop）

**Steps**:

- [ ] **Step 1**: 修改 `docs/PCS-UI-SPEC.md` — V1.0 → V1.13（沿用 V1.11→V1.12 wording-only 模式）；加 §3.9.1.1 C-16「TEG dehydration full system 12 result fields」子节；§9 changelog V1.13 row
- [ ] **Step 2**: 修改 `docs/PCS-PLAN-P5-DEVICE-EQUIPMENT.md` P5-0 章节 nit（对照具体 P5-0 commit diff 定位 nit）
- [ ] **Step 3**: 修改 `glycol_dehydration_service.py` 顶部 docstring — 统一全角标点 + RST 风格 + 中文术语表
- [ ] **Step 4**: 修改 `glycol_dehydration_service.py` `_DewpointResult` 列表符号 — 三态显式 FOUND/EXTRAPOLATED/NOT_FOUND 描述
- [ ] **Step 5**: 修改 `hydrate_inhibition_service.py` Line 50-53 — 修正为「质量分数粗换」（spec deviation 修复）；同步 Line 257 代码注释
- [ ] **Step 6**: 修改 `hydrate_inhibition_service.py` 测试 fixture 期望（如有数学漂移连带影响）
- [ ] **Step 7**: `CHANGELOG.md` 顶部新增「P6-9-PICKUP-5 4 项 DOC 闭环」行
- [ ] **Step 8**: 跑 `cd pcs-backend && uv run pytest tests/services/psychro/test_hydrate_inhibition_service.py -q` 确认 spec deviation 修复无回归
- [ ] **Step 9**: 单 commit — `docs(p6-9-pickup-5): DOC-4 闭环（SPEC V1.13 + PCS-PLAN-P5 + 2 service docstring）(5B)`

## Sub-batch 5C: REF-2 — glycol dehydration 子模块拆分 + 字段去冗余

**Files**:
- Create: `pcs-backend/app/services/psychro/_glycol_dehydration/__init__.py`（重导出）
- Create: `pcs-backend/app/services/psychro/_glycol_dehydration/reboilers.py`（`_calc_reboiler_duty_btu_hr` + `_calc_stripping_gas_rate_scf_gal_teg` + `ReboilerStrippingInput/Result` + `calc_reboiler_stripping` + `LeanGlycolDataPoint` + `_GPSA_FIG_20_4_DATA_POINTS` + `_calc_lean_glycol_concentration_wt_pct`）
- Create: `pcs-backend/app/services/psychro/_glycol_dehydration/dewpoint.py`（`_DewpointResult` + `_behr_inverse_dewpoint`）
- Create: `pcs-backend/app/services/psychro/_glycol_dehydration/behr.py`（`_BEHR_GRIDS` + `_bilinear_interp_behr` + `_calc_behr_water_content_lb_per_mmscf` + `_correct_behr_for_acid_gas` + `BehrGrid` + `BehrBaseline` + `_load_behr_grids`）
- Modify: `pcs-backend/app/services/psychro/glycol_dehydration_service.py`（缩减至 ~600 LOC，移除上述 4 _calc_*；保留 `GlycolDehydrationInput/Result/Error` + `calc_glycol_dehydration`）
- Modify: `pcs-backend/app/services/psychro/__init__.py`（保持现有 public API：`calc_glycol_dehydration`, `GlycolDehydrationInput`, `GlycolDehydrationResult`, `ReboilerStrippingInput`, `ReboilerStrippingResult`, `calc_reboiler_stripping`）

**Interfaces**:
- Consumes: REF-P6-8-1（字段去冗余 `reboiler_duty_btu_hr` 双源）+ REF-P6-8-2（`_glycol_dehydration/` 子模块拆分）
- Produces: `glycol_dehydration_service.py` 缩至 < 800 LOC（P6-PLAN 文件上限）；子模块各 < 400 LOC；public API 保持；所有现有测试 0 regression

**Reusable patterns**:
- cool_tower 子模块结构（`cool_tower/{merkel.py, tower_curve.py, water_balance.py, ...}`）— 7 文件结构；每模块 `{Input, Result, InputError, calc_*}` 四元组
- `__init__.py` 分章节注释 + 完整 `__all__` 重导出

**Steps**:

- [ ] **Step 1**: 创建 `pcs-backend/app/services/psychro/_glycol_dehydration/` 子包
- [ ] **Step 2**: 移 `_calc_reboiler_duty_btu_hr` (line 1172) + `_calc_stripping_gas_rate_scf_gal_teg` (line 1234) + `_calc_lean_glycol_concentration_wt_pct` (line 1295) + `ReboilerStrippingInput/Result` + `calc_reboiler_stripping` + `LeanGlycolDataPoint` + `_GPSA_FIG_20_4_DATA_POINTS` 到 `reboilers.py`
- [ ] **Step 3**: 移 `_DewpointResult` (line 282-296) + `_behr_inverse_dewpoint` 到 `dewpoint.py`
- [ ] **Step 4**: 移 `_BEHR_GRIDS` + `_bilinear_interp_behr` + `_calc_behr_water_content_lb_per_mmscf` + `_correct_behr_for_acid_gas` + `BehrGrid` + `BehrBaseline` + `_load_behr_grids` 到 `behr.py`
- [ ] **Step 5**: 解决跨子模块 import（`glycol_dehydration_service.py` 主入口调 `reboilers.calc_reboiler_stripping` + `dewpoint._behr_inverse_dewpoint` + `behr._calc_behr_water_content_lb_per_mmscf`）
- [ ] **Step 6**: 处理双字段冗余 — `GlycolDehydrationResult.reboiler_duty_btu_hr` 简式来源（line 1106 vs line 398），保留 `reboiler_duty_kw` (P6-8 T5) 作为权威；移除冗余字段
- [ ] **Step 7**: 子包 `__init__.py` 重导出（4 元组 `Input, Result, InputError, calc_*` 模式仿 cool_tower）
- [ ] **Step 8**: 顶层 `pcs-backend/app/services/psychro/__init__.py` 重导出（保持 public API 0 改动）
- [ ] **Step 9**: pytest 全量 `cd pcs-backend && DATABASE_URL=... uv run pytest tests/ -q` 期望 3515+ passed, 0 regression
- [ ] **Step 10**: ruff check 全 0 + `wc -l pcs-backend/app/services/psychro/glycol_dehydration_service.py` < 800 LOC
- [ ] **Step 11**: 单 commit — `refactor(p6-9-pickup-5): glycol dehydration 拆 _glycol_dehydration/ 子模块 (5C)`

## 收口

- [ ] **Step 收 1**: `docs/tasks.md` 更新 8 项状态（HYG 2 + DOC 4 + REF 2）从 OPEN → CLOSED via P6-9-PICKUP-5 file-level diff
- [ ] **Step 收 2**: `.wolf/STATUS.md` 新增 P6-9-PICKUP-5 收口 entry
- [ ] **Step 收 3**: G-08 phase 1-4 drift=0 + ruff 全 0 + pytest 3515+ passed + push origin/main
- [ ] **Step 收 4**: SDD workspace 清理（3 子批各自 workspace）

## 关键文件路径

- `pcs-backend/pyproject.toml`（HYG 配置改点）
- `.pre-commit-config.yaml`（HYG-P6-8-1 新建）
- `pcs-backend/alembic/versions/*.py`（508 D errors → 0）
- `docs/PCS-UI-SPEC.md`（V1.13 micro-revision）
- `docs/PCS-PLAN-P5-DEVICE-EQUIPMENT.md`（P5-0 nit）
- `pcs-backend/app/services/psychro/glycol_dehydration_service.py`（DOC + REF 改点）
- `pcs-backend/app/services/psychro/hydrate_inhibition_service.py`（DOC spec deviation 改点）
- `pcs-backend/app/services/psychro/_glycol_dehydration/`（REF 新建子包）

## 复用清单

| 现有 | 路径 | 复用任务 | 用法 |
|---|---|---|---|
| `cool_tower/{merkel,tower_curve,water_balance,heat_aggregator,fan_power,cool_tower_persist_service}.py` | `pcs-backend/app/services/cool_tower/` | 5C | 子模块拆分模板（7 文件 + 四元组 `Input/Result/InputError/calc_*`）|
| `cool_tower/__init__.py` 分章节注释 + `__all__` 重导出 | 同上 | 5C | 子包 `__init__.py` 模式 |
| ADR-0030 ChEDL 包装层 | `pcs-backend/app/services/chedl_wrapper.py` | 全部 | 业务代码禁 `import fluids.*` 强化 |
| `_calc_behr_water_content_lb_per_mmscf` Behr grid v3 | 5C 拆出后 `behr.py` | 5C | P6-8 T9r 工艺室 2026-09-29 v3 grid 闭环 |
| `ReboilerStrippingInput/Result` Pydantic BaseModel + frozen | `glycol_dehydration_service.py:1124/1148` | 5C 拆出 | 拆分后保持 public（P6-7 依赖）|

## 端到端验证矩阵

| # | 项 | 命令 | 期望 |
|---|---|---|---|
| 5A-1 | ruff D 全 0 | `cd pcs-backend && uv run ruff check . 2>&1 \| tail -3` | All checks passed! |
| 5A-2 | pre-commit 启用 | `pre-commit run --all-files 2>&1 \| tail -10` | fixture 末尾换行已修，exit 0 |
| 5A-3 | pytest 0 regression | `cd pcs-backend && DATABASE_URL=... uv run pytest tests/ -q` | 3515+ passed, 0 failed |
| 5B-1 | PCS-UI-SPEC §3.9.1.1 出现 | `grep -c "C-16" docs/PCS-UI-SPEC.md` | ≥ 1（不再是 0）|
| 5B-2 | hydrate_inhibition 测试 | `cd pcs-backend && uv run pytest tests/services/psychro/test_hydrate_inhibition_service.py -q` | 0 regression |
| 5B-3 | CHANGELOG 顶部 P6-9-PICKUP-5 行 | `head -10 CHANGELOG.md` | 含新行 |
| 5C-1 | glycol_dehydration_service.py LOC | `wc -l pcs-backend/app/services/psychro/glycol_dehydration_service.py` | < 800 |
| 5C-2 | 子模块 LOC | `wc -l pcs-backend/app/services/psychro/_glycol_dehydration/*.py` | 各 < 400 |
| 5C-3 | public API 兼容 | `cd pcs-backend && uv run python -c "from app.services.psychro import calc_glycol_dehydration, calc_reboiler_stripping, ReboilerStrippingInput, ReboilerStrippingResult, GlycolDehydrationInput, GlycolDehydrationResult"` | exit 0 |
| 收-1 | G-08 phase 1-4 drift=0 | `bash pcs-backend/scripts/gate_08_openapi_contract.sh --check-baseline` | OK baseline 一致 |
| 收-2 | docs/tasks.md 8 项 CLOSED | `grep -c "CLOSED via P6-9-PICKUP-5" docs/tasks.md` | 8 |

## 风险 + 缓解

| 风险 | 等级 | 缓解 |
|---|---|---|
| R-1 HYG-P6-6B-1 488 手动 fix 漏 | 中 | 逐文件 ruff check + 关窗 0 验证；commit 前 `ruff check .` |
| R-2 pre-commit 不在 CI，dev-only 启用 | 低 | 文档化在 CONTRIBUTING.md；G-08 不依赖 pre-commit |
| R-3 PCS-UI-SPEC V1.13 修订撞 V1.10 冻结基线 | 中 | 沿用 V1.11→V1.12 wording-only micro-revision 模式（保持冻结说明，docs-only 增量）|
| R-4 hydrate_inhibition spec deviation 数学漂移连带测试 | 中 | Step 8 跑 test_hydrate_inhibition_service.py 单独验证 |
| R-5 5C 子模块拆分 import 循环 | 高 | `glycol_dehydration_service.py` 主入口单向导入子模块，子模块间不互引（仿 cool_tower）|
| R-6 5C 拆分后 P6-7 计划依赖破损 | 中 | 保持 public API 0 改动；拆分前 snapshot 跑一次 pytest 验证 baseline |
| R-7 R=1 教训再现 — closure 状态回填不可指文档 | 高 | docs/tasks.md 更新时每项附 file-level diff（commit SHA + 行号）|

## 工时表

| 子批 | 工时 |
|---|---|
| 5A ruff D + pre-commit | 0.8 天（autofix 20 + 手动 488） |
| 5B DOC-4（V1.13 + PCS-PLAN-P5 + 2 service docstring） | 1.2 天 |
| 5C REF-2 子模块拆分 | 1.5 天 |
| 收口 + docs/tasks.md + workspace cleanup | 0.3 天 |
| **总计** | **~3.8 工作日** |

## 后续

P6-9-PICKUP-5 完成后 → 工艺室 2026-10-15 交付触发 OPEN-P6-6A-3 / OPEN-P6-6A-5 / OPEN-P6-6A-9.1 / OPEN-P6-6A-9.2 / OPEN-P6-4-3 收口 → P6-7 glycol dehydration service 扩展（8.5 天）。

## 未解决问题

1. **OPEN-P6-4-2**（Kb 厂商真实数据 LESER/Consolidated/AG）— 推迟到上线后批
2. **5 PROCo 项**（PROCo-P6-7-{1,2,3} / PROCo-P6-8-{1,3}）— 工艺室 2026-11-15/30 交付后启动 5D
3. **5C 子包命名**：`_glycol_dehydration/` 下划线前缀表示私有 vs 公开包？本计划用 `_` 前缀（与 `_DewpointResult` 等同模式）；若 P6-7 需公开访问需调整（待 P6-7 启动时定）