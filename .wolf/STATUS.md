---
description: session handoff, regenerate with /handoff when a quest finishes
budget_tokens: 1500
---
# STATUS — PCS

> Read this FIRST when starting a session. Last updated: 2026-09-27.

---

## ✅ Done（按时间序，仅保留仍值得记住的）

**P6-4 五项必做（merge `849a1bb`）**：C-06 热值 / C-08 分离器 / C-12 冻结契约 / C-17 饱和水 / C-24 Masonelian fl + 4 alembic。

**P6-5+ 13 项工艺计算（merge `f530daa`，16 task 全 APPROVED）**：
- Batch A PIPE（C-03/05/15）+ PIPE_NET（C-13）；Batch B VESSEL/CV/PSV/RESTRICTION（C-09/10/19/20/21）；Batch C FLARE/PSYCHRO（C-16/18/22/23）
- C5 收口：4 张 compound_* CONFIG 表 + alembic + seed + 5-min TTL 缓存（`_compound_config_cache.py`，Q3 fix `e35064b`）
- 架构组 Q1/Q2/Q3 裁决全部闭环

**P6-5+ follow-up 收官（2026-09-26）**：
- TTL-TEST-001~003 正式单元测试（merge `63d8e1a`）
- P5 历史 SPEC 主文档入库 ×2（`96f5fe2`）
- CI-P6-5-SEED：pcs_test 对齐（alembic head + 4 seed 17 行）→ 首次全量回归暴露 24 failed → **6 项修复**（merge `e999591`）：①a5f9360 枚举成员误删（19 测试）②审计三件套 drift（p6_5_005，5 表，**HIGH 生产缺陷** bug-101）③p6_2_001 downgrade 还原 stub（roundtrip 首次全链可逆）④table_count 88 ⑤lineage calc_type ⑥G-07 workspace_id
- pcs 开发库对齐 p6_3_002→head + seed + **p6_5_006 终扫**（3 表 6 列，bug-102）（`e683fed`）
- **双库 ORM↔DB drift 清零**；全量 3173 passed / 5 skipped / 0 failed
- SPEC V1.10 冻结（`d3e9e60`）：Q2 增补并入 §3.9.1.1/§3.9.3.1 + ATT-02 改名 + §0.1 实施终态；CHANGELOG 同步（`3bc9f3f`）

**P6-6A Worley 24 XLS 对账批完成（2026-09-27）**：
- 15 commits (`27910a7..fddeae4`) in worktree `feature/p6-6a-worley`
- T0 工具 + T1~T13 implementer + T10 fix-up (`bdbcea3`) + T14 closure report
- 11 Rulings 已登记（含 Ruling 9 双 surface：C-17 working fluid defect + C-21 AS 1210 vs API 521 hardcode）
- 3 CLEAN tasks (T11+T12+T13, 0 findings each)；T9+T10 共 2 MEDIUM + 6 LOW（all resolved）
- **0 service 改动**（Ruling 1 honored across 13 tasks）
- 全量 3242 passed / 74 skipped / 0 failed（baseline +69 tests）
- T14 closure report: `.superpowers/sdd/.../task-14-report.md` (182 lines)
- 批 B 计划立项：`docs/superpowers/plans/2026-09-27-p6-6b-data-source-replacement.md`
- **merge 入 main**：`09eb037 merge(p6-6a): Worley 24 XLS 算例对账批 (15 commits)`（2026-09-27）
- post-merge spot-check：T1 C-03 + T9 C-17 + T0 extract 56 tests PASS，0 regression

**OPEN-P6-6A-3 关闭（K scale F→F fix，2026-09-27）**：commit `e0d91a6`
- Hammerschmidt 1934 K scale mis-interpretation：原 `delta_t_c = K·X/(M·(1-X))` 把 K_F=2335 当 °C 处理，导致 d_F=38.88°F（1.8× over-prediction vs XLS literature 21.6°F）
- 修：公式 swap → `delta_t_f = K·X/(M·(1-X))`（K °F scale per paper, raw °F output），`delta_t_c = delta_t_f × 5/9`
- 4 fixture 字段重命名 `_d_C_algebra` → `_d_F_algebra` + 黄金 fixture 增 _f/_c 双轨 + worley_c18 fixture 删 `xls_hammerschmidt_K_scale_F_to_C_conversion` out_of_scope + 标 `xls_k_scale_F_vs_pcs_treats_C` root_cause CLOSED
- `test_k_scale_cross_check_xls_F_vs_pcs_C`（defect 文档）→ `test_k_scale_post_fix_xls_F_eq_pcs_F_bit_for_bit`（fix 验证）；PCS d_F=21.6°F = XLS d_F=21.6°F bit-for-bit rel=1e-12
- bug-103 logged with full root_cause/fix; 全量 2418 passed / 32 skipped / 0 failures
- **Ruling 11 K scale CLOSED**

**OPEN-P6-6A-4 关闭（drain orifice Cd/Y_cr^0.5 Ruling 12 fix，2026-09-28）**：commit `c34d3f4`
- PCS `calc_drain_orifice` mass_flow_capacity 公式原仅 A×Ftp×ρ×v_max，假设 Cd=1.0 + Y_cr^0.5=1.0 implicit，导致 1.74× over-prediction vs XLS PR-023 在 d=15.204 mm 处计算（Cd=0.83932 × Y_cr^0.5=0.68717 = 0.5768 → reduction 1.734×）
- 修：给 `DrainOrificeInput` 加 2 optional 字段 `discharge_coefficient` (Cd) + `expansion_factor` (Y_cr^0.5)，默认 1.0 保持向后兼容；formula 改为 m_max = A × Cd × Y_cr^0.5 × Ftp × ρ × v_max；新增 _validate_input 越界校验 Cd/Y_cr ∈ (0, 1]；formula_ref 加 3 键（Ruling 12 + XLS PR-023 字串）
- Fixture `worley_c19_drain_orifice.json`: service_inputs 加 Cd=0.83932 + Y_cr^0.5=0.6871656312856262；expected 加 `mass_max_kg_s_post_fix_with_cd_y_cr=2.656 kg/s`；root_cause_notes 中 `xls_cd_discharge_coefficient_out_of_scope` + `xls_y_cr_expansion_factor_out_of_scope` 状态标 CLOSED in OPEN-P6-6A-4；out_of_scope 移除这 2 项（11→9）
- Test `worley_c19.py`: _build_input 传 Cd/Y_cr；test_mass_flow_capacity_choked_branch_and_is_capacity_ok 改 post-fix 期望（mass_max ≈ 2.656 kg/s, capacity_ratio ≈ 0.71）；新增 test_cd_y_cr_default_one_backward_compat（默认 1.0 零回归）+ test_cd_y_cr_post_fix_1p74x_reduction（reduction ratio ≈ 1.734）+ test_formula_ref_includes_cd_y_cr_ruling_12 + test_worley_c19_root_cause_notes_cd_y_cr_status_closed
- 验证：66/66 restriction tests PASS（含 11 个 worley_c19 测试）；全量 3258 passed / 74 skipped / 0 failures；post-fix mass_max 2.656 kg/s = XLS PR-023 在 d=15.204 mm 处（Ruling 7 family mismatch 0.2% 容差内）
- bug-104 logged with full root_cause/fix
- **Ruling 12 Cd/Y_cr CLOSED**

**OPEN-P6-6A-7 关闭（C-19 排污孔板 sizing 完整实现，2026-09-28）**：commits `ce8556f→86d3310→f296a61→709c3bf→1644abf→a5fb167→4a75f38→07c4f6e→3250b42`（9 commits；worktree `feature/p6-6a-7-c19-sizing`）
- **背景**：用户 2026-09-28 指出 OPEN-P6-6A-4 只完成 capacity check 公式精度（Cd/Y_cr^0.5 输入参数化），未实现 SPEC §3.7.2 要求的 sizing 完整功能（Ycr 计算 + Ftp 迭代 + 孔板直径迭代求解）。我当初把 SPEC 增补要点错判 OUT_OF_SCOPE，用户纠正后选 A 选项"现在补完 sizing"
- **服务（ce8556f）**：`drain_orifice_service.py` +261 行（纯追加，forward `calc_drain_orifice` 零改动 — Ruling 1 honored）；新增 `DrainOrificeSizeInput` / `DrainOrificeSizeResult` / `DrainOrificeSizingNotConvergedError` / `calc_drain_orifice_size`；Newton 简化版 `d_new = d × sqrt(W/m_max)` + β 越界自动 bisection fallback；非阻塞流显式抛 `DrainOrificeInputError`
- **测试（86d3310）**：黄金 fixture `golden_drain_orifice_size_pr023.json`（XLS PR-023 inputs + expected d）+ 6 单元测试（golden 对账 + forward↔inverse 自洽 + 非阻塞流 + 输入校验 × 3 + 不收敛抛错）
- **物理修正（f296a61 + bug-105）**：`_y_cr_sqrt` 必须用 `r_c` 而非 `p_ratio`（ISO 5167 Y_cr 是 critical flow expansion factor，input 必为 r_c）；bug-105 logged
- **文档修正（1644abf）**：fixture `_doc_xls_vs_pcs_gap` 显式说明 PCS d=12.762 mm vs XLS PR-023 E42 d=15.204 mm 16% gap（Ruling 7 GB/T 308 vs ISO 5167 Ftp family mismatch + Ruling 13 sub-2 XLS oversizing safety margin vs PCS exact W convergence）
- **Fixture 翻转（a5fb167）**：`xls_d_sizing_iteration_out_of_scope` 标 CLOSED in OPEN-P6-6A-7（移除过时 `finding`；新增 `status` + `status_note` 658 chars 解释 PCS-XLS gap）
- **API（4a75f38）**：`POST /api/v1/restriction/drain-orifice/size` + Pydantic schemas + 4 集成测试（happy path + 非阻塞流 + Cd-out-of-range Ruling 12 锁定 + ACL）。沿用 flare.py kod_sizing 模式（current_actor / require_roles / async / 无 DB 持久化）。OpenAPI regen clean（162 paths / 205 schemas）
- **测试增强（07c4f6e）**：增 `test_drain_orifice_size_post_cd_out_of_range_422` 集成测试锁定 Ruling 12 Cd∈(0,1.0] invariant
- **收口（3250b42）**：bug-104 加 follow_up（含完整 9 commit chain）；cerebrum.md 增 OPEN-P6-6A-7 Key Learning（含 4 守则：SPEC 增补要点不 OUT_OF_SCOPE / Ruling + XLS 迭代 ≠ OUT_OF_SCOPE / Forward + Inverse 必备 / Y_cr 必须用 r_c）
- **验证**：72/72 restriction tests PASS（66 baseline + 6 sizing）；12/12 restriction API tests PASS（7 baseline + 4 sizing + 1 Cd-out-of-range）；全量 **3269 passed / 74 skipped / 0 failed**（OPEN-P6-6A-4 baseline 3258 → P6-6A-7 3269，+11 net）；gate_08 G-08 ✅；whole-branch review APPROVE
- **Ruling 13（Y_cr@r_c + d sizing 范围）CLOSED**
- **OPEN-P6-6A-7 关闭**：6 OPEN-P6-6A-* 中 4 项关闭（#3 #4 #7）；剩余 #1（SPEC V1.2 wording formalization）/ #2（brief template）/ #5（T13 ΔH_vap）/ #6（T8 glycol dehydration）

**OPEN-P6-6A-5 关闭（ΔH_vap fluid-specific input，2026-09-28）**：commits `e72e0db` + `628ef4d`
- PCS `calc_as1210_relief_sizing` `_DHVAP_KJ_KG = 2260` hardcoded → 改为 As1210ReliefInput `delta_h_vap_kj_kg: float = _DHVAP_KJ_KG` 默认 2260（back-compat）
- API 521 §3.4.4.3 "latent heat at relieving T/P" fluid-specific 要求满足
- 7 unit tests：default back-compat 2260 / XLS 208 matches G35 within 1%（6761 vs 6766）/ propane 425 / zero raises / negative raises / formula_ref / 黄金 fixture load
- worley_c21 fixture 新增 1 test：XLS PR-025 ΔH_vap=208 case → relief load ≈ G35=6766 kg/hr 经验 1% PASS
- 黄金 fixture `golden_as1210_dhvap.json` 新建
- **Ruling 14 ΔH_vap CLOSED**
- **注**：Ruling 9 C_AS1210=2.457 vs PCS C=43192（39% Q diff）仍残留，独立 OPEN-P6-6A-?（待 ID 分配）
- 366 psv tests passed / 0 failed (baseline 358 + 8 new)

**OPEN-P6-6A-8 关闭（fire_case_coefficient + fire_case_exponent fluid-specific，2026-09-28）**：commits `bc95487` + `f1c2be1`
- PCS `_FIRE_COEFF_W = 43192.0` hardcoded → As1210ReliefInput 加 fire_case_coefficient + fire_case_exponent 双字段（默认 43192 + 0.82 back-compat）
- 7 unit tests + 1 golden fixture loader + 1 worley_c21 扩展 = 10 new psv tests（366 → 376）
- XLS PR-025 AS 1210 path (a) 验证：coefficient=71866 + exponent=0.82 + ΔH_vap=208 → G54=649808 W within 0.029% + G55=11253 kg/hr within 0.029%（整合 Ruling 14 ΔH_vap + Ruling 15 coeff/exp）
- 黄金 fixture `golden_as1210_fire_coeff.json` 新建（XLS G54 EXACT + G55 within 容差）
- 默认 back-compat 验证：coeff=43192 + exp=0.82 保持 API 521 §3.4 行为（worley_c21 sanity guard 防 silent fallthrough）
- **Ruling 15 fire_case 双字段 CLOSED**
- **注**：AS 1210 §4.4 path (b) gas/vapor (m·Y_p) + jet fire 110,000 W/m² 不在本批（结构差异），独立 OPEN-P6-6A-9（待 ID）
- **merge 入 main @ d636337（fast-forward, 2026-09-28）**：post-merge spot-check 376 psv tests PASS, 0 regression

**OPEN-P6-6A-1 关闭（Ruling 9 wording formalization，2026-09-28）**：commit `8b2e1c2` docs(spec)
- SPEC V1.10 → V1.11 docs-only micro-revision（V1.10 实施基线保持冻结）
- §3.5.2 C-21 加"火灾泄放公式口径"sub-section（API 521 §3.4 default 43192 / AS 1210 §4.4 path (a) 7.2×10⁴ 液化 / path (b) m·Y_p 气体 / Jet fire 110,000 W/m²）+ "流体特定输入"子段（Ruling 14 ΔH_vap + Ruling 15 fire_case coeff/exp）
- §3.9.2 C-17 加"working fluid 口径澄清"（XLS WS-CA-PR-019 natural gas vs PCS humid air 范围边界 + worley_c17 fixture mapping_defect OoM ≥ 10 引用）
- §0.1 加 V1.11 wording 注记（Ruling 9 双 surface 闭环链 cfdbe2d + fddeae4 + e72e0db + bc95487）；§9 changelog V1.11 row
- 26+/2- diff 单文件 docs-only，0 测试影响
- bug-108 logged; cerebrum Key Learning appended
- **Ruling 9 docs CLOSED**

**G-08 OpenAPI baseline drift 收口（2026-09-28）**：commit `68daa60` chore(g-08)
- baseline `384d8c7` (P6-5+ 终态, 850.1K) → 当前 `68daa60` (873.9K)；delta +23.8K
- 纯增量：+2 paths / +4 schemas / 0 removed
- 新增 paths：
  - `/api/v1/psychro/glycol-dehydration/calculate` (P6-6A-6 `5cced07`, Ruling 5 closure v4)
  - `/api/v1/restriction/drain-orifice/size` (P6-6A-7 `3250b42`, Ruling 12/13 closure)
- 新增 schemas：`GlycolDehydrationRequest/Response` + `DrainOrificeSizeRequest/Response`
- 全部 ACL 正确（psychro: DESIGNER/PROCESS_CONTROLLER/SYSTEM_ADMIN；restriction: DESIGNER/PROCESS_CONTROLLER）
- phase 1-4 全过：regen backend → regen frontend snapshot+types → drift=0 → baseline 一致

**SPEC V1.11 → V1.12 wording-only micro-revision（2026-09-28）**：commit `2c2d5b9` docs(spec)
- 6 修订 + ATT-02 同步，2 files +39/-8（主 SPEC +37/-7, ATT-02 +2/-1），docs-only zero code/schema/test 改动
- Fix 1 §3.9.2 C-17 OPEN-P6-6A-2 → OPEN-P6-6A-9.x（typo fix，1 行）
- Fix 2 §3.9.1 C-16 列 12 result fields 全名 + 类型 + Ruling 5 + ADR-0045 Rev A ref（10~15 行大段）
- Fix 3 §3.7.2 C-19 Ruling 12/13 闭环链补全（c34d3f4 + ce8556f→3250b42），不补 POST 路由
- Fix 4 §8 "V1.7 未解决" 2 项 → P6-6B 解决中 + 引 plan `2026-09-27-p6-6b-data-source-replacement.md`
- Fix 5 §3.5.2 C-21 AS 1210 path (b) + Jet fire OPEN-P6-6A-9 → OPEN-P6-6A-10 新立（PSV C-21 主题预留）
- Fix 6 §9 V1.12 row + ATT-02 标题 V1.10 → V1.12 + §7.2 changelog 同步
- reviewer（haiku）PASS：6 fix 全部按用户裁决落实
- 4 deferred candidates（OPEN-P6-4-2/3/4 + OPEN-P6-6A-9.x 4 子项）保留至 P6-6B 工程团队接管

**OPEN-P6-6A-2 关闭（Brief template `brief.id == plan_table_row.id` assert，2026-09-27）**：commit `955d25a` feat(tools)
- 工具 `pcs-backend/scripts/validate_brief.py`（96 行）：controller dispatch 前断言 brief 含 expected-ids 且无 foreign-ids，防止 brief template 复制粘贴残留（如 T9 brief 误标 C-18 vs PR-019，实为 C-17）
- CLI 接口：`--plan <plan> --task-n <N> --brief <brief.md> --expected-ids <ids...> --foreign-ids <ids...>`
- 退出码：0=OK / 1=brief 内容不符 / 2=文件缺失
- 7 unit tests：PASS / MISSING-id / FOREIGN-id / plan 缺失 / brief 缺失 / id 顺序无关（parametrize ×2）
- 245+ insertions 单次提交；已 merge 入 main @ 955d25a
- **OPEN-P6-6A-2 CLOSED**（brief template copy-paste typo guard 已落地）

**OPEN-P6-6A-6 关闭（glycol dehydration v5.1 — Ruling 5 OUT_OF_SCOPE 12 fields + ADR-0045 Rev A + Day-0 Gate 形式决策，2026-09-28）**：commits `95bb442` → `8aaa68d` → `ee3c40e` → `1391a5a` → `5cced07`（5 commits；worktree `feature/p6-6a-6-glycol-full`）
- **背景**：P6-6A Worley 批登记的 Ruling 5 要求 C-16 glycol dehydration 服务实现 11 OUT_OF_SCOPE outputs + acid_gas_corrected 共 12 fields 闭环（含 ADR-0045 TEG Contactor Sizing K 标定 + brentq 逆 dewpoint + acid gas placeholder + JSON 启动期加载三铁律）。v5 plan 阶段架构组预给 Behr 系数 (A0=1.3520/A1=0.00780/A2=0.0000052/A3=-0.9800) 独立验算失败（T=120/P=1000 预测 W=0.2648 vs spot 70，264× 偏差）+ v3 形式 A 也失败（113× 偏差），用户裁决 v5.1 必须 Day-0 Gate 形式决策 + 实际拟合系数 + 30× 根因弱化为推测待 P6-6B 验证
- **v5.1 plan P-1~P-4 修正（95bb442）**：执行前必办 4 项——P-1 Day-0 Gate 形式决策必跑（numpy lstsq + scipy curve_fit 比较 3 形式）+ JSON log10_coefficients null；P-2 _DewpointResult 字段名统一（dewpoint_f/extrapolated/reason）；P-3 30× 根因弱化为推测待 P6-6B 验证（OPEN-P6-6A-9.1）；P-4 _calc_behr_water_content 调用 _correct_behr_for_acid_gas 去重
- **T1 service v5.1（8aaa68d）**：glycol_dehydration_service.py 扩 12 result fields + 8 helper（_calc_behr_water_content / _correct_behr_for_acid_gas / _calculate_full_column_diameter / _calculate_ntu / _calculate_column_height / _calculate_reboiler_duty / _calculate_dewpoint_inverse / _validate_input）+ _DewpointResult frozen dataclass + 模块级 `_BEHR_COEFFS = load_behr_coefficients()` 启动期加载 + K=7.1187 from Worley PR-018 E40 单点标定 + 越界 WARNING `[K_UNVERIFIED_OUT_OF_XLS_CONDITIONS]` + Linear placeholder (NON-Wichert-Aziz) 术语正名 + acid_gas_corrected 纯逻辑判断 `(co2 > 0) or (h2s > 0)` + α=inp.relative_volatility 显式声明 + _validate_input 422 校验 7 字段（co2/h2s/lean_glycol/flooding_c_sb/relative_volatility）
- **T1 fix REQUEST_CHANGES（ee3c40e）**：4 reviewer fixes — vap/sump column_height + 3 test rename + Python 3.13 forward-compat（dict[str, float] | None 显式声明）
- **T2 fixture v4（1391a5a）**：worley_c16_glycol_dehydration.json 扩 11 OUT_OF_SCOPE outputs（acid_gas_corrected + co2/h2s inputs + dewpoint_unavailable_reason + flooding_c_sb 等）+ 10 parameterized tests（Ruling 5 closure 状态 v4）
- **T3 API v4（5cced07）**：`/psychro/glycol-dehydration/calculate` v4 API + Pydantic schemas（GlycolDehydrationInput/Output）+ 11 集成测试（happy path TEGS / happy path acid gas / DEG 422 / T/P 缺 → None + reason / co2/h2s 422 / ACL designer-only 等）+ OpenAPI/frontend types regen
- **docs 收口（本批 T4）**：bug-109/110/111/112/113 entries（id/timestamp/error_message/file/root_cause/fix/fix_commit/tags/occurrences/last_seen + fix_commit 必填）+ cerebrum.md 9 守则 v5.1（#3 Behr Day-0 Gate + #4 30× 根因弱化推测 + #8 Linear placeholder 三铁律）+ OPEN-P6-6A-6 v5.1 关闭 entry
- **bug-109 fix_commit**: `5cced07`（Ruling 5 OUT_OF_SCOPE 12 fields API 暴露闭环）
- **bug-110 fix_commit**: `8aaa68d`（Behr 系数 v5.1 Day-0 Gate 实际拟合 + K=7.1187）
- **bug-111 fix_commit**: `8aaa68d`（v4 ADR-0045 + acid gas placeholder + brentq inverse + JSON 启动期加载三铁律）
- **bug-112 fix_commit**: `8aaa68d`（v5 ADR-0045 Rev A 撤回 v4 物理依据 + _DewpointResult dataclass + Linear placeholder 正名）
- **bug-113 fix_commit**: `95bb442`（v5.1 plan P-1~P-4 落实 + 30× 根因弱化推测 + Day-0 Gate 形式决策必跑）
- **验收**：(a) ruff 0 errors；(c) `vitest run` ≥ 525 baseline PASS（v3 M-5 frontend 验收）；(d) 36 项端到端验证全过，含 worley_c16 fixture `ruling_5_closure_status_v4`；(e) console 无 antd/React/TS error；OpenAPI drift=0 + frontend tsc 0 errors
- **OPEN-P6-6A-9 立项（4 子项 quest）**：OPEN-P6-6A-9.1 30× 差异根因完整验证（P6-6B 工程师 3 项：V_actual_scfs 混淆代码行定位 + XLS 标况气速文献依据 + 修订 ADR-0045 Rev A）；OPEN-P6-6A-9.2 K=7.1187 多工况标定（Q∈[144,432] MMscfd + sg sweep + TEG wt% sweep）；OPEN-P6-6A-9.3 真 Wichert-Aziz 非线性形式（接管 v5 Linear placeholder ~25% 偏差）；OPEN-P6-6A-9.4 brentq inverse T<60°F Bukacek 1990 low-temp extension
- **OPEN-P6-6A-11 立项（C-18 Nielsen 方程覆盖缺口，2026-09-28）**：核实发现 SPEC §3.9.3 要求 BOTH Hammerschmidt (MeOH ≤25 wt%) + Nielsen (MeOH ≤50 wt%)，P6-5 仅落 Hammerschmidt；MeOH > 25 wt% 工况无对应方程静默外推，超出 Hammerschmidt 验证域（验收线 <3%）。范围：Nielsen 1991 方程分支（按 GPSA §20.3 Fig 20-13 拟合）+ MeOH > 25 wt% 自动切换 + WARNING [NIELSEN_AUTO_SWITCH] + 黄金 fixture 3 点对账（Nielsen 1991 paper Fig 5 vs Hammerschmidt 切点）。预估 ~1.0 天；P6-6B 工程团队接管
- **Ruling 5 OUT_OF_SCOPE 12 fields CLOSED**（11 OUT_OF_SCOPE + acid_gas_corrected，alpha 显式 + dewpoint_unavailable_reason + acid_gas_corrected 一致性 + TEG Contactor Sizing ADR-0045 Rev A 单点标定 + 30× 根因弱化为推测 + brentq inverse → _DewpointResult frozen dataclass 字段名统一 + Linear placeholder 术语正名 + JSON 启动期加载三铁律 + Day-0 Gate 形式决策 + Day-1 Gate 验证 + _calc_behr 去重调用 _correct）

**P6-6B 数据源替换批落地（2026-09-28，13 commits active，T2 跳过 OPEN-P6-4-2 上线后）**：commits `287ea9c`..`af0a054`
- **范围**：9 张 CONFIG 表 metadata 闭环 + 4 个内联常量替换（service 集成）；T10/T11 决策点路径 A/B 推迟到工程团队
- **T1** `compound_heating_values` 64 行 metadata 闭环（OPEN-P6-4-1 关闭）
- **T2** `_VALVE_LIBRARY` 真实 Kb 厂商数据 — **跳过**（OPEN-P6-4-2 上线后推迟，commit `dc124f7`）
- **T3** `pipe_e_modulus` CONFIG 表 + ORM + 8 行 seed + C-13 service 集成（CARBON_STEEL 等旧 5 材质枚举彻底移除）
- **T4** `compound_pasquill_sigma` 6 行 metadata 闭环（EPA ISC3 + Briggs 1973）
- **T5** `compound_api521_thresholds` 2 行 metadata 闭环（API 521 §3.4 + AS 1210 §4.4）
- **T6** `compound_iso9613_atmospheric_absorption` 4 行 metadata 闭环（ISO 9613-2 1996）
- **T7** `compound_hammerschmidt_K` 5 行 metadata 闭环（Hammerschmidt 1934 + Nielsen 1988 + GPSA Fig. 20-XX）
- **T8** `compound_nielsen_1988_params` 新建 CONFIG 表 + 7 行 seed + hydrate_inhibition service Nielsen 1988 备选 path（InhibitorModel 枚举 + 双模型分支 + 默认向后兼容 Hammerschmidt）；A/B/C 估算值待工艺工程师二次核对
- **T9** `glycol_dehydration_full_system` 10 行典型工况范围（CONFIG 占位）+ glycol_dehydration_service docstring 加 OUT_OF_SCOPE 引用 4 子模块（reboiler/stripping/full column/lean glycol 待 P6-7 service 扩展）
- **T10** Hammerschmidt K_F=2335 → K_C=1297.22 service 集成 — **路径待工程团队**
- **T11** API 521 fire coeff 43192 → AS 1210 2.457 service 集成 — **路径待工程团队**
- **T12** `delta_h_vap_natural_gas` 2 行 metadata 闭环 + service 双字段切换（`use_xls_convention` 默认 False，2260 保留向后兼容，XLS 208 字段可选；OPEN-P6-6A-5 形式关闭）
- **T13** `drain_orifice_Cd_Y_cr` 6 行 metadata + service feature flag `_USE_XLS_CD_Y_CR` 默认 False + `_resolved_cd_y_cr` 内部 override 参数集成（R=1 fix 闭环；OPEN-P6-6A-4 形式关闭；CONFIG + 双轨方案就位，待 ETL 对账后启用 XLS convention）
- **验收**：G-08 phase 1-3 全过（0 OPENAPI drift，metadata-only 改动无新路径）；pytest 各模块 0 break；ruff 0 errors on touched files；pcs_test head `p6_6b_013_drain_orifice_Cd_Y_cr`
- **Parked findings (跨批 LOW/INFO 11 项，batch-end 清理)**：T3 4 项 doc-style nit + T8 4 项 spec deviation + T12 3 项 ruff/seed 偏差

**P6-6B 工艺工程师对 OPEN 队列的决策（2026-09-28，工艺室签署）**：全部 11 项（OPEN-P6-4-3 / 4-4 / 6A-9 9.1~9.4 + 新增 9.5 / 6A-10 / 6A-11 + T10 / T11）已锁定输入与决策，详见 `.wolf/cerebrum.md` §"P6-6B 工艺工程师对 OPEN 队列的决策"
- **关键决策摘要**：
  - **T10 路径 A**（推翻 progress.md 旧 docs-only 裁决）：service 改 + 字段名修正（`_c` → `_f`，语义 Bug）+ CONFIG 表闭环 + `hydrate_depression_c = _f × 5/9` 派生 + `_c_legacy` deprecated；OPEN-P6-6A-3 真正关闭
  - **T11 放弃 2.457**：工艺室追溯来源不明（XLS PR-025 内部 BTU/hr basis 转换或不同 ΔH_vap 假设）；改分 path 并存（API_521 默认 + AS_1210 path (a) 7.2×10⁴ + path (b) OPEN-P6-6A-10）
  - **OPEN-P6-6A-9.2 K 范围升级**：单点 K=7.1187 实测 6 工况 CV=1.05% < 5%；适用范围 [sg ∈ 0.55-0.65, TEG wt% ∈ 98.5-99.8, P ∈ 800-1500 psia, Q ∈ 100-400 MMscfd]；ADR-0045 Rev B 更新
  - **OPEN-P6-6A-9.5 新增**：XLS PR-018 E20=103.91 baseline 残差 26% 归因 XLS baseline（≠ GPSA 70 lb/MMscf）+ 6% brine 盐度修正 +15~25%
  - **OPEN-P6-6A-9.3 残差归因**：真 Wichert-Aziz 实现后与 v5 Linear placeholder 几乎相同（差 0.4%）；XLS E20 残差 26% 不在 acid gas correction
  - **OPEN-P6-6A-11 Nielsen 精确常数**：Nielsen 1988 (GPA RR-114) Table 2-3 A/B/C 完整常数 7 组（CH4/C2H6/C3H8/i-C4H10/N2/CO2/H2S）；v5 简化（C=0.0）升级为完整 Table 2-3
- **总工时 ~8.5 天**，按关闭日期分 4 批：
  - **2026-10-15**：OPEN-P6-4-3 + 9.1 + 9.2 + T10 + T11（3.5 天）
  - **2026-10-31**：OPEN-P6-4-4 + 9.3 + 9.4（3.0 天）
  - **2026-11-15**：OPEN-P6-6A-10（1.0 天）
  - **2026-11-30**：OPEN-P6-6A-11 + 9.5（2.0 天）
- **OPEN-P6-6A-3 / OPEN-P6-6A-5 真正关闭**：T10 路径 A 后 OPEN-P6-6A-3 全闭环；T11 fire_case 双 path 注册后 OPEN-P6-6A-5 全闭环
- **P6-7 启动前置**：2026-10-15 批 OPEN 闭环后即可启动 P6-7 glycol service 扩展 + 工艺室 4 批 fixture 集成

**P6-7 服务集成批落地（2026-10-31，10 commits active，T5 partial + T2 partial）**：commits `eb824eb`..`6ed6a50`
- **范围**：工艺室 3 批交付物（OPEN 队列 6 项）服务代码集成 + ADR-0045 Rev B 实施 + OPEN 关闭登记
- **T1 (eb824eb)**：`psychro.py` `HydrateGasComposition` schema v2（OPEN-P6-6A-11 代码侧 schema 部分）
- **T3 (c6caacb)**：C-18 Nielsen 1988 完整方程组 + gas_composition + brine（OPEN-P6-6A-11 代码侧闭环，工艺 + 代码双闭环）
- **T4 (f58d9e4 + 0aec803)**：C-08 两相分离器 sizing imperial 测试（OPEN-P6-4-3 Path A 决议代码侧重定义闭环）
- **T5 (8acf6c6 + ea5ec30)**：C-24 CV Masonelian 3-model + 24 厂商库（OPEN-P6-4-4 部分关闭：24 厂商库 PASS + 3-model 待 fixture 修复后重跑）
- **T6 (dfd702b)**：T10 hydrate_inhibition 字段名 `_c` → `_f` + 派生 `_c` + `_c_legacy` deprecated（OPEN-P6-6A-3 真正关闭）
- **T7 (5dbd09e)**：T11 fire_case 分 path 并存 + 放弃 2.457 系数（OPEN-P6-6A-5 真正关闭）
- **T9 (29048f9)**：Bukacek 1990 T<60°F 延伸 `_behr_inverse_dewpoint` 分 T 段（OPEN-P6-6A-9.4 代码侧闭环）
- **T2 (6f6ca9d)**：C-16 Behr baseline 选择 general/high_acid（OPEN-P6-6A-9.3 + 9.5 部分关闭：code 正确 + general OK；high_acid 待 fixture 修复后重跑）
- **T8 (6ed6a50)**：AS 1210 §4.4 path (b) + Jet fire service path（OPEN-P6-6A-10 代码侧就位，工艺侧 confidence B → A 升级待 2026-11-15）
- **验收**：G-08 phase 1-4 全过；pytest 386+ psv + psychro 各模块 0 break；ruff 各 touched 文件 0 errors；vitest 548/548 PASS（前端不动）
- **Schema sync**：tests/test_schema.py table_count 88 → 93（P6-6B 净新增 5 张 CONFIG 表：pipe_e_modulus / compound_nielsen_1988_params / glycol_dehydration_full_system / compound_delta_h_vap_natural_gas / drain_orifice_Cd_Y_cr）
- **Parked findings（cross-task, non-blocking, batch-end 清理候选）**：
  - T3 工艺室标定 -0.00645 vs PCS 严格 -0.00754 (~17% 差异，工艺室后续澄清)
  - T2 `pcs-backend/data/behr_coefficients.json` high_acid 系数不自洽（工艺室 2026-11-15 重发）
  - T8 fixture 3-sig-fig 近似（C3H8 path b 1.81% diff，dual-tolerance 容纳）
  - T9 brief 模板高温系数 vs v5.1 JSON fit 不一致（implementer 沿用 JSON）
  - 2 ruff errors pre-existing in `app/services/psychro/glycol_dehydration_service.py` (lines 352 E501 / 676 F841 T_LOW unused, both from P6-6A-6 8aaa68d)

**P6-8 glycol dehydration service 集成批落地（2026-11-15，5 commits active）**：commits `c89d091`..`1e85dc4`
- **范围**：工艺室 2026-10-31 4 子模块计算逻辑服务集成 + ADR-0045 Rev B 实施确认 + OPEN-P6-6A-6 代码侧闭环
- **T1 (c89d091)**：Reboiler Duty + Stripping Gas Rate service path（OPEN-P6-6A-6 子任务 1+2）+ WARNING 字段 `TEG_CIRCULATION_RATE_UNVERIFIED`
- **T2 (6506796)**：Stripping Gas Rate fixture 3 算例 + 测试（XLS E32 + 380°F + 250→300°F 钳制）
- **T3 (9497b5f)**：Full Column Diameter fixture K=7.1121 6 工况 + K-CV 验证（OPEN-P6-6A-6 子任务 3）
- **T4 (21eb943)**：Lean Glycol Concentration service path + GPSA Fig 20-4 4 数据点插值（OPEN-P6-6A-6 子任务 4）
- **T5 (1e85dc4)**：API 端点扩展 4 outputs + WARNING 字段 + OpenAPI regen drift=0
- **T6+T7**：verify only（fixtures 完整性 + pytest/vitest/OpenAPI/G-08/ruff 全过）
- **验收**：pytest 各模块 0 break（5 pre-existing failures 属 OPEN-P6-4-4 / OPEN-P6-6A-9 待工艺室 fixture 重发）；vitest 548/548；G-08 phase 1-4 全过（baseline 滚动）；ruff 各 touched files 0 new errors
- **OPEN-P6-6A-6 代码侧闭环**（4 子模块 + API 集成 + WARNING）
- **Parked findings (跨 task LOW/MEDIUM/non-blocking)**：
  - T1 F1: brief Step 1 `contactor_temperature_f le=300` vs impl `le=200`
  - T1 F3: brief q_total 16.18M vs impl 10.40M（brief 数值有误）
  - T1 F4: SGR 单位混算（psi vs mmHg），待 P6-9 PICKUP 修复
  - T2 O-T2-1: fixture JSON 末尾缺换行符
  - T3 F1 (MEDIUM): ruff B018 false-positive on fixtures/ JSON（pyproject.toml extend-exclude out of scope）
  - T4 F2: 返回值单位约定（wt% vs 质量分率），P6-9 PICKUP 必统一
  - T5 F5/F6: 双字段冗余同源 + reboiler_duty_btu_hr 字段名不变但实现被 T1 覆盖
- **3 项 limitation 待工艺室 2026-11-15 对账**：Reboiler Duty TEG 循环量（+216% 偏差）/ Antoine 系数（待 DIPPR 验证）/ Leon Glycol 完整 Fig 20-4 曲线
- **OPEN 队列变化**：
  - ✅ OPEN-P6-6A-6 代码侧闭环（4 子模块 service path 全落地）
  - ⚠️ OPEN-P6-4-4 + OPEN-P6-6A-9.5 + OPEN-P6-6A-10 待 fixture 重发 / PDF 升级 / 对账（工艺室 2026-11-15）

**P6-9-PICKUP-2 批落地（2026-11-15，6 commits active）**：commits `258d857`, `b599420`, `a9956c2` 等
- **范围**：4 项 CRITICAL + 2 项 HIGH 修复
- **T1 (eb2e4c9)**：CRITICAL F1 `_calc_lean_glycol_concentration_wt_pct` else-branch patch + 3 regression tests
- **T2 (0c631c3)**：CRITICAL F2 SGR 公式反转 patch (GPSA §20.4 Eq.20-5)
- **T3 (4645d78)**：CRITICAL F3 C-24 reconciliation service x 显式 + consistency check
- **T4 (258d857)**：CRITICAL t_wall_mm → t_wall_m 单位歧义修复
- **T5 (b599420)**：HIGH F1 nielsen dead code 删除
- **T6 (a9956c2)**：HIGH F2 `_USE_XLS_CD_Y_CR` feature flag 接入
- **T7**：MEDIUM F3 untracked test file commit
- **T8**：批末收口（验证 + docs + push）

- **验收**：3513+ passed（1 pre-existing T2 fail 豁免）+ ruff 0 new errors
- **OPEN 队列影响**：
  - OPEN-P6-4-4：已关闭 → ⚠️ partial closure（待工艺室 v2 fixture 签署）
  - OPEN-P6-9-PICKUP-2-1：新增 F2 SGR 公式复盘跟踪
  - OPEN-P6-9-PICKUP-2-2：新增 t_wall_mm 复盘跟踪
  - OPEN-P6-6A-10：关联 t_wall_m 修复（仍待 AS 1210-2010 PDF 升级 confidence B → A）

---

## 🚀 Next quest

**P6-7 glycol dehydration service 扩展（OPEN-P6-6A-6 后续 + OPEN-P6-6A-9.x 4 子项 + OPEN-P6-6A-9.5）**：
- Plan: 待定（**2026-10-15 工艺室承诺 OPEN-P6-6A-9.1/9.2 闭环后启动**，ADR-0045 Rev B 起草 + K 适用范围升级）
- 范围：
  - OPEN-P6-6A-6：4 子模块（reboiler / stripping / full column / lean glycol）从 OUT_OF_SCOPE → 落地
  - OPEN-P6-6A-9.1：ADR-0045 Rev B 起草 + GPSA §20.4 Eq.20-3 + Kohl-Nielsen Ch.7 Eq.7-14 引用补充
  - OPEN-P6-6A-9.2：K=7.1187 6 工况标定 [sg ∈ 0.55-0.65, TEG wt% ∈ 98.5-99.8, P ∈ 800-1500 psia, Q ∈ 100-400 MMscfd]（CV=1.05% < 5%）
  - OPEN-P6-6A-9.3：真 Wichert-Aziz（Wichert & Aziz 1972 HC Processing）
  - OPEN-P6-6A-9.4：Bukacek 1990 Table 3 low-temp T<60°F 系数（A0'=2.1430, A1'=0.01850, A2'=-0.000042, A3'=-0.9800）
  - OPEN-P6-6A-9.5（新增）：XLS PR-018 E20 baseline 溯源 + 6% brine 盐度修正
- 触发：T9 CONFIG `glycol_dehydration_full_system` 10 行典型工况范围已就位 + 工艺工程师 4 批 fixture 集成
- 预计 8.5 工作日（按工艺室 4 批 OPEN 关闭日期分阶段推进）

**P6-6B 已完成（merged to main @ `68daa60` → `af0a054`）**：13 commits active（T2 skipped），OPEN-P6-4-1 关闭 + OPEN-P6-6A-4/5 形式关闭 + OPEN-P6-6A-6 部分关闭（CONFIG 占位 T9）；OPEN-P6-4-2 推迟上线后；T10 路径 A + T11 分 path 并存工艺室 2026-09-28 签署（详见 `.wolf/cerebrum.md`）

**OPEN-P6-6A-3 K scale**：
- 公式层：`e0d91a6`（Ruling 11 K °F scale per paper）已闭环
- 字段名层：**T10 路径 A 待 2026-10-15 闭环**（`_c` → `_f` 修正语义 Bug + `hydrate_depression_c` 派生 + `_c_legacy` deprecated 向后兼容）
- 工艺室签署：T10 路径 A（service 改 + CONFIG 表闭环）；`hammerschmidt_K` CONFIG 表同时含 K_F + K_C 两列

**后续（待用户裁决）**：
1. ~~P6-6A merge 到 main~~ ✓ done `09eb037`
2. ~~OPEN-P6-6A-3 K scale fix~~ ✓ done `e0d91a6`
3. ~~P6-6B 启动确认~~ ✓ done（13 commits `287ea9c`..`af0a054`，OPEN-P6-4-1 关闭，OPEN-P6-4-2/3/4 + OPEN-P6-6A-5/6 部分关闭；OPEN-P6-6A-4/5 形式关闭 — 详见 P6-6B 批落地 entry）
4. ~~SPEC V1.2 修订~~ ✓ done `2c2d5b9`（V1.11 → V1.12 wording-only 6 修订 + OPEN-P6-6A-10 新立）
5. ~~G-08 OpenAPI baseline drift 收口~~ ✓ done `68daa60`（+2 paths / +4 schemas / 0 removed；P6-6A-6/7 全部已 merge main）
6. ~~前端 wrapper 3 页~~ ✓ done P6-5 补课（`HeatingValuePage.tsx:11.4K` + `SaturationWaterContentPage.tsx:9.4K` + `CvComputePage.tsx:12.9K`，路由 `routeWrappers.tsx:48/51/52` + `208/211/215`，vitest 15/15 PASS）

**未解决问题**（工艺室 2026-09-28 签署，详见 `.wolf/cerebrum.md` §"P6-6B 工艺工程师对 OPEN 队列的决策"）：
- OPEN-P6-4-2（Kb 厂商真实数据 LESER/Consolidated/AG，**上线后** P6-6B+ 启动）
- OPEN-P6-4-3（C-08 vessel Imperial 单位白名单；工艺室 2026-10-15 关闭，~1.0 天）
- OPEN-P6-4-4（C-24 CV Masonelian fl 三模型对账；工艺室 2026-10-31 关闭，~1.0 天）
  - ⚠️ **partial closure（2026-10-31 P6-9 PICKUP-2 T3）**：service 端 x 显式 + consistency check + 工艺室 fixture re-issue 已落 `4645d78`；3/3 reconciliation PASS + back-compat 回归 PASS；待工艺室 fixture 重新签署后重新关闭（v2 fixture 用 P1/Pv_kpa/T_c 自洽输入）
- OPEN-P6-6A-6（T8 full glycol dehydration service 扩展待 P6-7）
- OPEN-P6-6A-9.1（30× 差异根因完整验证；工艺室 2026-10-15 关闭，~1.0 天）
- OPEN-P6-6A-9.2（K=7.1187 6 工况 CV=1.05%；工艺室 2026-10-15 关闭，~0.5 天）
- OPEN-P6-6A-9.3（真 Wichert-Aziz 实现；工艺室 2026-10-31 关闭，~1.0 天）
- OPEN-P6-6A-9.4（Bukacek 1990 T<60°F；工艺室 2026-10-31 关闭，~0.5 天）
- **OPEN-P6-6A-9.5（新增，2026-09-28）**：XLS PR-018 E20 baseline 溯源 + 6% brine 盐度修正；工艺室 2026-11-30 关闭，~0.5 天
- OPEN-P6-6A-10（AS 1210 §4.4 path (b) gas/vapor m·Y_p + Jet fire 110,000 W/m²；工艺室 2026-11-15 关闭，~1.0 天）
- OPEN-P6-6A-11（C-18 Nielsen Table 2-3 完整 A/B/C 7 组常数 + gas_composition 输入；工艺室 2026-11-30 关闭，~1.0 天；P6-6B T8 已部分落地 InhibitorModel + 双模型分支，A/B/C 待工艺工程师 PDF 抄录）
- **OPEN-P6-6A-3**（T10 路径 A 真正关闭，~0.5 天，2026-10-15）
- **OPEN-P6-6A-5**（T11 fire_case 双 path 注册关闭，~0.5 天，2026-10-15）

**验收**：P6-6B 后 source 字段去 SYNTHETIC 标记 + gate 报告签字 + 黄金 fixture 重对账。
**Next batch 触发**：2026-10-15 批 OPEN 闭环后 P6-7 启动；全部 11 项关闭后 P6-8（部署 + ETL 重新对账）启动。

---

## Context

- main @ `c34d3f4`（P6-6A merge `09eb037` + OPEN-P6-6A-3 Ruling 11 K scale fix `e0d91a6` + OPEN-P6-6A-4 Ruling 12 Cd/Y_cr^0.5 fix `c34d3f4`）；working tree 仅 .wolf/*（hooks 维护）+ tests/models/test_orm_db_drift.py（**未 commit**——drift 守卫测试，pcs_test-only skipif，已验证 PASS/skip）
- worktree `feature/p6-6a-worley` @ `fddeae4`（P6-6A 完整 15 commits，**已 merge 入 main @ 09eb037**，worktree 可清理）
- **worktree `feature/p6-6a-7-c19-sizing` @ `3250b42`**（P6-6A-7 完整 9 commits，**待 merge 入 main**，whole-branch review APPROVE）
- **双库已对齐 head `p6_5_006`**：跑 schema 敏感测试前 `DATABASE_URL=postgresql+psycopg://pcs:pcs_dev@localhost:5432/pcs_test uv run alembic upgrade head`（CLAUDE.md 规则仍适用）
- 全量回归基线：**3258 passed / 74 skipped**（OPEN-P6-6A-4 commit 后；增量 +840 vs OPEN-P6-6A-3 baseline 2418 = P6-6A Task 11 fixture-driven 测试 +3 新 worley_c19 test + 837 P6-6A 其他任务测试）
- P6-6A-7 增量：**+11 net**（+6 sizing service tests + +4 sizing API tests + +1 Cd-out-of-range 422 test；post-merge 期望 3269 passed / 74 skipped / 0 failed）
- buglog 最新 bug-101/102/103/104/105/106（审计三件套 drift / 手写清单教训 / OPEN-P6-6A-3 K scale / **OPEN-P6-6A-4 Cd/Y_cr^0.5 1.74× over-prediction** / **OPEN-P6-6A-7 Y_cr@r_c 物理修正** / **OPEN-P6-6A-5 ΔH_vap fluid-specific input (e72e0db)**）
- 无 CI/CD（单人开发裁决，勿再建议）；SPEC V1.10 已冻结为实施基线，后续改 SPEC 需新版本号
- P6-6A 11 Rulings + Ruling 13/14 已登记：Ruling 1 零改动 / Ruling 2 表格化 / Ruling 3-8 mapping defects / Ruling 9 双 surface / Ruling 10 brief template / **Ruling 11 K scale CLOSED in OPEN-P6-6A-3 (e0d91a6)** / **Ruling 12 Cd/Y_cr CLOSED in OPEN-P6-6A-4 (c34d3f4)** / **Ruling 13 Y_cr@r_c + d sizing 范围 CLOSED in OPEN-P6-6A-7 (3250b42)** / **Ruling 14 ΔH_vap fluid-specific input CLOSED in OPEN-P6-6A-5 (628ef4d)**
