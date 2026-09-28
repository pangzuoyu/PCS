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
- 6 unit tests：default back-compat / XLS G54 EXACT (71866×0.82=649810 W) / AS 1210 path with ΔH_vap=208 matches G55 within 0.06% / linear exponent 1.0 / coefficient zero raises / exponent zero raises / formula_ref
- 黄金 fixture `golden_as1210_fire_coeff.json` 新建（XLS G54 EXACT + G55 within 1%）
- worley_c21 fixture 扩展 1 test：AS 1210 path G54/G55 within 容差
- **Ruling 15 fire_case 双字段 CLOSED**
- **注**：AS 1210 §4.4 path (b) gas/vapor (m·Y_p) + jet fire 110,000 W/m² 不在本批（结构差异），独立 OPEN-P6-6A-9（待 ID）

---

## 🚀 Next quest

**P6-6B 数据源替换批启动（2026-09-27，Subagent-driven 待工程团队开工）**：
- Plan: `docs/superpowers/plans/2026-09-27-p6-6b-data-source-replacement.md`
- 范围：9 CONFIG 表替换 SYNTHETIC 标记 + 4 内联常量替换
- 触发：T14 closure report sign-off + 工程团队接管真实 GPSA / Vendor / ISO / API 数据
- 预计 5-7 工作日（Phase 1 CONFIG 并行 3-4 天 + Phase 2 service 集成 1-2 天 + ETL 1 天）
- 解决 OPEN-P6-4-1/2 + OPEN-P6-6A-5（6 OPEN-P6-6A-* 中 4 项关闭）— **OPEN-P6-6A-3 已 e0d91a6 关闭**（Ruling 11 K scale）+ **OPEN-P6-6A-4 已 c34d3f4 关闭**（Ruling 12 Cd/Y_cr^0.5）+ **OPEN-P6-6A-7 已 3250b42 关闭**（Ruling 13 Y_cr@r_c + sizing 完整实现）

**P6-6A 已完成（merged to main @ `09eb037`）**：worktree `PCS-worktrees/p6-6a-worley` @ `fddeae4`，15 commits，0 service 改动，11 Rulings 已登记，post-merge 56/56 spot-check PASS。

**OPEN-P6-6A-3 已关闭（commit `e0d91a6`）**：Hammerschmidt 1934 K scale fix（Ruling 11）。

**后续（待用户裁决）**：
1. ~~P6-6A merge 到 main~~ ✓ done `09eb037`
2. ~~OPEN-P6-6A-3 K scale fix~~ ✓ done `e0d91a6`
3. P6-6B 启动确认（工程团队接管厂商数据采集）
4. SPEC V1.2 修订（10 项 deferred candidates 中 6 项 wording 决议）
5. G-08 OpenAPI baseline drift 收口（P6-2/3/4 累积，Task 16/28）
6. 前端 wrapper 3 页（heating-value / saturation-water-content / cv，P6-4 裁决推迟项）

**未解决问题**：
- OPEN-P6-4-2（Kb 厂商真实数据 LESER/Consolidated/AG，部署前）
- OPEN-P6-4-3（C-08 Imperial 单位支持范围）
- OPEN-P6-4-4（C-24 Chapman-Jans / Tong 模型与商业软件对账，部署前）
- OPEN-P6-6A-1（Ruling 9 wording formalization，SPEC V1.2 决议）
- OPEN-P6-6A-2（Brief template `brief.id == plan_table_row.id` assert，批 B brief template 实现）
- OPEN-P6-6A-5（T13 ΔH_vap 2260 vs 208 kJ/kg, 18× diff, medium effort）
- OPEN-P6-6A-6（T8 full glycol dehydration system as new PCS service，CONFIG 占位 T9 关闭；service 扩展待 P6-7）

**验收**：P6-6B 后 source 字段去 SYNTHETIC 标记 + gate 报告签字 + 黄金 fixture 重对账。
**待用户裁决**：是否先核实 C-18 Nielsen 方程覆盖缺口（SPEC §3.9.3 要点含 Nielsen，P6-5 只落了 Hammerschmidt）。

**次优先（B 批剩余）**：G-08 OpenAPI baseline drift 收口（P6-2/3/4 累积，Task 16/28）→ 前端 wrapper 3 页（heating-value / saturation-water-content / cv，P6-4 裁决推迟项）。

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
