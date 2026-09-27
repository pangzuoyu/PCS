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

---

## 🚀 Next quest

**P6-6B 数据源替换批启动（2026-09-27，Subagent-driven 待工程团队开工）**：
- Plan: `docs/superpowers/plans/2026-09-27-p6-6b-data-source-replacement.md`
- 范围：9 CONFIG 表替换 SYNTHETIC 标记 + 4 内联常量替换
- 触发：T14 closure report sign-off + 工程团队接管真实 GPSA / Vendor / ISO / API 数据
- 预计 5-7 工作日（Phase 1 CONFIG 并行 3-4 天 + Phase 2 service 集成 1-2 天 + ETL 1 天）
- 解决 OPEN-P6-4-1/2 + OPEN-P6-6A-5（6 OPEN-P6-6A-* 中 3 项关闭）— **OPEN-P6-6A-3 已 e0d91a6 关闭**（Ruling 11 K scale）+ **OPEN-P6-6A-4 已关闭**（Ruling 12 Cd/Y_cr^0.5）

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
- **双库已对齐 head `p6_5_006`**：跑 schema 敏感测试前 `DATABASE_URL=postgresql+psycopg://pcs:pcs_dev@localhost:5432/pcs_test uv run alembic upgrade head`（CLAUDE.md 规则仍适用）
- 全量回归基线：**3258 passed / 74 skipped**（OPEN-P6-6A-4 commit 后；增量 +840 vs OPEN-P6-6A-3 baseline 2418 = P6-6A Task 11 fixture-driven 测试 +3 新 worley_c19 test + 837 P6-6A 其他任务测试）
- buglog 最新 bug-101/102/103/104（审计三件套 drift / 手写清单教训 / OPEN-P6-6A-3 K scale / **OPEN-P6-6A-4 Cd/Y_cr^0.5 1.74× over-prediction**）
- 无 CI/CD（单人开发裁决，勿再建议）；SPEC V1.10 已冻结为实施基线，后续改 SPEC 需新版本号
- P6-6A 11 Rulings 已登记：Ruling 1 零改动 / Ruling 2 表格化 / Ruling 3-8 mapping defects / Ruling 9 双 surface / Ruling 10 brief template / **Ruling 11 K scale CLOSED in OPEN-P6-6A-3 (e0d91a6)** / **Ruling 12 Cd/Y_cr CLOSED in OPEN-P6-6A-4 (c34d3f4)**
