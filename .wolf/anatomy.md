# anatomy.md

> Auto-maintained by OpenWolf. Last scanned: 2026-10-06T15:36:05.534Z
> Files: 665 tracked | Anatomy hits: 0 | Misses: 0

## ./

- `.gitattributes` — Git attributes (~43 tok)
- `.gitignore` — Git ignore rules (~46 tok)
- `CHANGELOG.md` — Change log (~4191 tok)
- `CLAUDE.md` — OpenWolf (~175 tok)
- `CONTEXT.md` — PCS（工艺专用综合计算软件） (~1524 tok)
- `docker-compose.yml` — Docker Compose services (~309 tok)
- `pcs-p5-start-baseline.txt` — PCS P5 启动基线快照（2026-09-16） (~371 tok)
- `README.md` — Project documentation (~3547 tok)
- `TODOS.md` — TODOS.md — PCS 延后工作清单 (~2890 tok)

## .claude/worktrees/s4-0-events/

- `CLAUDE.md` — OpenWolf (~286 tok)

## .claude/worktrees/s4-0-events/.superpowers/sdd/sprint4-plan-2026-10-05/

- `progress.md` — SDD ledger — plan: docs/sprint4-plan-2026-10-05.md (~3137 tok)

## .claude/worktrees/s4-0-events/docs/

- `PCS-NOTE-SPEC-3.2.4-电机功率规则修订-2026-10-06.md` — PCS-NOTE — SPEC §3.2.4(2) 电机额定功率判定规则修订 (~1040 tok)
- `PCS-NOTE-SPEC-3.2.4(3)-结论档数修订-2026-10-06.md` — PCS-NOTE — SPEC §3.2.4(3) 结论档数修订（3 档 → 4 档，新增「不可判」） (~691 tok)
- `PCS-SIGN-T5-2026-10-05.md` — T5 综合能耗验收 — 正式封版 (2026-10-05) (~2017 tok)
- `sprint4-plan-2026-10-05.md` — Sprint 4 计划：供应商数据闭环 + 事件骨架 + 真实算例验收 (2026-10-05) (~3331 tok)

## .claude/worktrees/s4-0-events/docs/ce-code-review/20261006-sprint4/

- `metadata.json` (~957 tok)

## .claude/worktrees/s4-0-events/pcs-backend/

- `.bench_report.py` (~131 tok)

## .claude/worktrees/s4-0-events/pcs-backend/alembic/versions/

- `p7_s4_001_event_idempotency.py` — p7_s4_001: event_idempotency 表（事件幂等凭据 / D4 裁决 4A 落地前置）. (~521 tok)
- `p7_s4_002_actual_data_jsonb.py` — p7_s4_002: equipment_list.actual_data_json (供应商实测值本体). (~333 tok)

## .claude/worktrees/s4-0-events/pcs-backend/app/api/v1/

- `__init__.py` (~1443 tok)
- `supplier.py` — 供应商实际数据录入 API (P7 Sprint 4 S4-1 / ADR-0025). (~2480 tok)

## .claude/worktrees/s4-0-events/pcs-backend/app/core/

- `events.py` — 事件骨架 — emit_event / register_listener / 幂等去重。 (~1711 tok)

## .claude/worktrees/s4-0-events/pcs-backend/app/schemas/

- `supplier.py` — 供应商实际数据录入 API schemas (P7 Sprint 4 S4-1 / ADR-0025). (~1080 tok)

## .claude/worktrees/s4-0-events/pcs-backend/app/services/

- `cia_engine.py` — CIA 变更影响分析引擎（Sprint 3）。 (~4767 tok)
- `events.py` — 事件骨架 — emit_event / register_listener / 幂等去重。 (~3040 tok)

## .claude/worktrees/s4-0-events/pcs-backend/app/services/equip_list/

- `pump_design_data.py` — 泵设计参数（P7 Sprint 4 · S4-2 设计值缺口收口）. (~1878 tok)

## .claude/worktrees/s4-0-events/pcs-backend/app/services/supplier/

- `__init__.py` — 供应商侧服务（P7 Sprint 4）。 (~97 tok)
- `actual_data_service.py` — 供应商实际数据录入（手动）— P7 Sprint 4 S4-1 / ADR-0025. (~1101 tok)
- `confirmation_service.py` — 供应商核算与更新流程 (P7 Sprint 4 Task S4-3 / SPEC V1.4 §3.2.4(4)(5)(6)). (~1882 tok)
- `deviation_report.py` — 偏差报告组装 + 确认门禁 + 导出 (P7 Sprint 4 S4-2 / SPEC V1.4 §3.2.4). (~3899 tok)
- `deviation_service.py` — 供应商偏差判定引擎 (P7 Sprint 4 S4-2 / SPEC V1.4 §3.2.4(2)). (~2901 tok)
- `excel_import_service.py` — 供应商实际数据 Excel 批量导入 — P7 Sprint 4 S4-1. (~1384 tok)

## .claude/worktrees/s4-0-events/pcs-backend/scripts/

- `_tmp_base_probe.py` — 临时探查: 基础设计表数据质量 (不入 git, 用完即删). (~455 tok)
- `_tmp_cerebrum.py` — 把本次 fix pass 学到的 pytest 坑与裁决写进 cerebrum Do-Not-Repeat。 (~447 tok)
- `_tmp_check10.py` — 临时：验证 #10 的测试可失败（撤掉 savepoint 包裹 -> 跑 -> 还原）. (~289 tok)
- `_tmp_check9.py` — 临时：#9 的 RED 测试 —— 转移中途失败不得把半应用状态提交。 (~595 tok)
- `_tmp_detailed_probe.py` — 临时探查: 详细设计表列结构 (不入 git, 用完即删). (~220 tok)
- `_tmp_falsifiability_check.py` — 临时：验证 #22 的 AST 守卫确实可失败（注入 → 跑 → 还原）. (~384 tok)
- `_tmp_fix_spec11.py` — #11: SPEC 公开 API 表的供应商数据面端点路径与实际发布不一致 —— 登记修订。 (~591 tok)
- `_tmp_fix_stale_gap.py` — One-shot: 修正被本分支自己推翻的「设计值无写入方」过期注释（审查 #18）. (~773 tok)
- `_tmp_fix_uispec.py` — 不可判**\n" (~432 tok)
- `_tmp_pump_ratio_probe.py` — 临时探查: 机泵选型两张表的轴功率/电机功率关系 (不入 git, 用完即删). (~424 tok)
- `_tmp_reg2.py` — 登记: 测试编码缺陷的判据 + buglog 重号导致 max+1 算错号。 (~467 tok)
- `check_migration_idempotency.py` — 检查 alembic migrations 是否用 if_exists / if_not_exists (F-P3-002 fix). (~778 tok)
- `p7_open_012_t5_r1_verification.py` — P7 Sprint 2 T5 ≤2% 验收脚本（蜡油加氢 XLS R1 重算对比）。 (~7056 tok)
- `p7_s4_003_seed_pump_design.py` — 把泵设计参数写入 `EquipmentList.design_parameters_json`（P7 Sprint 4 S4-2 配套）. (~1573 tok)

## .claude/worktrees/s4-0-events/pcs-backend/tests/

- `test_cia_event_decoupling.py` — CIAEngine 3 处直调 state_machine 改走事件触发 (P7 Sprint 4 S4-0 Step 5). (~2281 tok)
- `test_errors.py` — 全局异常信封测试：404 / 405 / 422 均走 ErrorResponse 信封（code/trace_id 字段断言）。 (~512 tok)

## .claude/worktrees/s4-0-events/pcs-backend/tests/api/v1/

- `test_actual_data_confirmation_api.py` — 核算与更新流程 API (P7 Sprint 4 Task S4-3). (~2526 tok)
- `test_deviation_report_api.py` — 偏差报告 API (P7 Sprint 4 Task S4-2). (~1592 tok)
- `test_supplier_actual_data_api.py` — 供应商实际数据录入 API — 手工 UI 路径 (P7 Sprint 4 Task S4-1). (~2024 tok)

## .claude/worktrees/s4-0-events/pcs-backend/tests/core/

- `test_events.py` — 事件骨架 emit_event / listener / 幂等去重 (P7 Sprint 4 Task S4-0). (~2425 tok)

## .claude/worktrees/s4-0-events/pcs-backend/tests/scripts/

- `test_t5_case4_gas_media.py` — T5 Case 4 扩类 — 氮气 / 净化压缩空气 / 低温余热走真实子表 (P7 Sprint 4 Task S4-4). (~1197 tok)

## .claude/worktrees/s4-0-events/pcs-backend/tests/services/equip_list/

- `test_pump_design_data.py` — 泵设计参数接线 (P7 Sprint 4 · S4-2 设计值缺口收口). (~2724 tok)

## .claude/worktrees/s4-0-events/pcs-backend/tests/services/supplier/

- `test_actual_data_service.py` — 供应商实际数据录入 — 手工 UI 路径 (P7 Sprint 4 Task S4-1). (~1788 tok)
- `test_confirmation_service.py` — 供应商核算与更新流程 (P7 Sprint 4 Task S4-3 / SPEC V1.4 §3.2.4(4)(5)(6)). (~4738 tok)
- `test_deviation_report.py` — 偏差报告组装 + 确认门禁 + 导出 (P7 Sprint 4 Task S4-2). (~3230 tok)
- `test_deviation_service.py` — 供应商偏差报告引擎 (P7 Sprint 4 Task S4-2 / SPEC V1.4 §3.2.4). (~1946 tok)
- `test_error_code_registry.py` — 供应商域错误码必须出现在 meta 错误码注册表里（审查 #4）. (~410 tok)
- `test_motor_tier_rule.py` — 电机功率判定改为「对轴功率卡分档下限」 (P7 Sprint 4 S4-2 规则修订). (~1331 tok)

## .code-review-graph/

- `.gitignore` — Git ignore rules (~38 tok)

## .githooks/

- `pre-commit` — A-08 G-08 OpenAPI 契约自动化门禁（pre-commit hook） (~306 tok)
- `README.md` — Project documentation (~332 tok)

## .github/workflows/

- `check-api-drift.yml` — F-P3-002 集成: check-api-drift.sh + check_migration_idempotency.sh CI (~565 tok)

## .gstack/

- `browse-audit.jsonl` (~37227 tok)
- `browse.json` (~66 tok)
- `scan-p6-6a-6-spec-v12-candidates.md` — P6-6A-6 SPEC V1.12 修订前置扫描报告 (~1549 tok)
- `spec-v12-implementer-report.md` — P6-6A-6 SPEC V1.12 修订实施报告 (~662 tok)
- `spec-v12-review-report.md` — V1.12 wording-only micro-revision 评审报告 (~508 tok)

## .gstack/qa-reports/

- `_dashboard-snapshot.txt` — - BEGIN UNTRUSTED EXTERNAL CONTENT (source: http://localhost:5173/) --- (~536 tok)
- `qa-report-pcs-frontend-2026-09-16.md` — PCS Frontend QA Report (~1153 tok)
- `qa-report-pcs-frontend-2026-09-17-p5-4-frontend.md` — QA Report — pcs-frontend — P5-4 HEAT frontend UI 闭环 (~2385 tok)
- `qa-report-pcs-frontend-2026-09-25-p6-2-batch.md` — QA Report — pcs-frontend — P6-2 batch 批末 (~2123 tok)
- `qa-report-pcs-frontend-2026-10-01-sprint2.md` — Sprint 2 batch-end QA report (~1214 tok)
- `qa-report-pcs-frontend-2026-10-02-sprint2-batch.md` — QA Report: pcs-frontend 2026-10-02 Sprint 2 批末 (~1014 tok)
- `qa-report-pcs-frontend-per-batch-2026-09-16.md` — PCS Frontend Per-Batch QA Report (~1293 tok)

## .superpowers/sdd/

- `.gitignore` — Git ignore rules (~1 tok)

## .superpowers/sdd/2026-09-30-p5-0-1b-5-tables/

- `progress.md` — SDD ledger — plan: docs/superpowers/plans/2026-09-30-p5-0-1b-5-tables.md (~398 tok)
- `task-1-brief.md` — Task 1 Brief: thermosiphon_circulation_results 表实现 (T1) (~1340 tok)
- `task-1-report.md` — Task 1 Report: thermosiphon_circulation_results (P5-0-1b T1) (~2441 tok)

## .superpowers/sdd/2026-10-01-p7-complete-sprint/

- `plan-path` (~15 tok)
- `progress.md` — SDD ledger — plan: docs/superpowers/plans/2026-10-01-p7-complete-sprint.md (~6260 tok)
- `review-496b84d..92b4478.diff` — Review package: 496b84d..HEAD (~3855 tok)
- `task-1-brief.md` (~0 tok)
- `task-4-brief.md` (~0 tok)
- `task-s1-2-brief.md` — Task S1-2: EquipmentList ORM model（含 SourceService V1.4 新字段） (~1128 tok)
- `task-s1-2-report.md` — Task S1-2 Report — EquipmentList ORM model（含 SourceService V1.4 字段） (~3504 tok)
- `task-s1-3-brief.md` — ## Task S1-3: EquipmentTypeCodes CONFIG seed（CATEGORY_5，不建独立 ORM） (~232 tok)
- `task-s1-4-brief.md` — pcs-backend/app/services/equip_list/sync_service.py (~939 tok)
- `task-s1-5-brief.md` — tests/services/util/test_summary_service.py (~506 tok)

## .superpowers/sdd/2026-11-15-p6-8-glycol-dehydration-extensions/

- `plan-path` (~20 tok)
- `review-3b881d8..2b27e00.diff` — Review package: 3b881d8..2b27e00 (~10117 tok)

## .superpowers/sdd/PCS-PLAN-P4-CORE-ENGINE/

- `p2-bug-fix-report.md` — P2 Bug Fix Report — allowable_stress 邻接节点方向取反 (~788 tok)
- `p4-2-3-r1-fix-report.md` — P4-2-3 R1 fix 报告 (~1250 tok)
- `p4-2-5-r2-report.md` — P4-2-5 R2 修复报告 (~618 tok)
- `p4-2-5-r3-report.md` — P4-2-5 R3 修复报告 — test_sup008 fixture 同源 bug (~520 tok)
- `p4-3-3-r1-report.md` — P4-3-3 r1 修复报告 (~174 tok)
- `p4-4-1-r1-report.md` — P4-4-1 R1 Fix Report (~165 tok)
- `progress.md` — SDD ledger — plan: docs/PCS-PLAN-P4-CORE-ENGINE.md (~5930 tok)
- `review-882f581..e72116f.diff` — Review package: 882f581..HEAD (~5491 tok)
- `task-1-brief.md` — Task P4-0-1 Brief: 审计字段迁移 + lineage helper (~876 tok)
- `task-1-fix-r1-report.md` — P4-0-1 R1 修复报告 (~376 tok)
- `task-1-report.md` — Task P4-0-1 Report: 审计字段迁移 + lineage helper (~847 tok)
- `task-10-report.md` — Task 10 Report — P4-2-3 single phase pressure drop (~1386 tok)
- `task-11-report.md` — Task 11 Report: P4-2-4 两相压降（Lockhart-Martinelli-Baker + 流型判定 + 落库） (~1663 tok)
- `task-11-review-report.md` — Task 11 审查报告：P4-2-4 两相压降 (~903 tok)
- `task-12-report.md` — Task-12 Report: P4-2-5 链式管道 + 出口物流 (~3890 tok)
- `task-13-report.md` — Task 13 — P4-3-1 管网拓扑模型 报告 (~858 tok)
- `task-13-review-report.md` — Task 13 审查报告：P4-3-1 管网拓扑模型 (~1580 tok)
- `task-14-report.md` — Task 14 — P4-3-2 管网 Hardy-Cross 求解器 报告 (~1868 tok)
- `task-14-review-report.md` — Task 14 审查报告：P4-3-2 管网 Hardy-Cross 求解器 (~1888 tok)
- `task-15-report.md` — Task 15 — P4-3-3 管网 API + 落库 + outlet_stream Literal 扩展 报告 (~934 tok)
- `task-15-review-report.md` — Task 15 审查报告：P4-3-3 管网 API + 落库 + outlet_stream Literal 扩展 (~2184 tok)
- `task-16-report.md` — P4-4-1 PUMP 泵选型 — 任务报告 (~290 tok)
- `task-16-review-report.md` — Task-16 Review Report — P4-4-1 PUMP 泵选型 (~734 tok)
- `task-17-report.md` — task-17 P4-4-2 NPSHa 计算 R1 报告 (~291 tok)
- `task-17-review-report.md` — Task-17 Review Report — P4-4-2 NPSHa 计算 (~1000 tok)
- `task-18-report.md` — P4-4-3 泵曲线插值 实施报告 (~158 tok)
- `task-18-review-report.md` — P4-4-3 泵曲线插值 审查报告 (~751 tok)
- `task-19-report.md` — Task P4-4-4 报告 (~70 tok)
- `task-19-review-report.md` — Task-19 Review Report — P4-4-4 PUMP 链 + 出口物流 (~500 tok)
- `task-2-report.md` — Task P4-0-2 Report: OPEN-008 表扩展（SUP-008 V1.1） (~1555 tok)
- `task-20-report.md` — Task-20 P4-TASK0 本体论落地报告 (~611 tok)
- `task-20-review-report.md` — P4-TASK0 Ontology Closure Review (~418 tok)
- `task-3-report.md` — Task P4-0-3 Report: 计算入口守卫接线（CHECKED + unreliable） (~1031 tok)
- `task-4-report.md` — Task P4-1-1 Report: Thermo 封装层（thermo_factory） (~814 tok)
- `task-5-step1-report.md` — P4-1-2 Step 1 Report (~599 tok)
- `task-5-step2-report.md` — P4-1-2 step 2 报告 (~866 tok)
- `task-5-step3-report.md` — P4-1-2 step 3 报告 (~1015 tok)
- `task-6-report.md` — Task 6 Report — P4-1-3 flash api + persistence + outlet stream (~309 tok)
- `task-7-report.md` — Task 7 Report — P4-1-4 flash writeback to stream (~751 tok)
- `task-8-report.md` — Task 8 Report — P4-2-1 pipe sizing (velocity + dp methods) (~1141 tok)
- `task-9-report.md` — Task 9 Report — P4-2-2 wall thickness (ASME B31.3) (~1491 tok)

## .vite/vitest/

- `results.json` (~39 tok)

## docs/

- `ce-code-review-p5-p6-summary.md` — ce-code-review P5+P6 全范围 Summary (~1831 tok)
- `P45-BATCH3-TYPE-MIGRATION.md` — P45 BATCH3 前端类型手动迁移登记 (~248 tok)
- `P6-9-PICKUP-4.md` — P6-9-PICKUP-4 — ce-code-review P5+P6 残留 debt 闭环 (~2054 tok)
- `P6-9-PICKUP-6.md` — P6-9-PICKUP-5 工艺债务批 archive (~2281 tok)
- `P7-OPEN-007-physical-semantics-evaluation.md` — P7-OPEN-007 — physical_semantics 三元决策评估报告 (~1381 tok)
- `P7-OPEN-008-rule-registry-form-evaluation.md` — P7-OPEN-008 — 规则清单形态评估报告 (~1175 tok)
- `P7-OPEN-009-SUP-010-5table-migration-schedule.md` — P7-OPEN-009 — SUP-010 5 表 + catalyst_loading + auxiliary_consumption 4 字段 迁移排期 (~2011 tok)
- `P7-REV-01-04-mock-decisions.md` — P7-REV-01~04 — 启动前裁决清单 mock 决议 (~1290 tok)
- `PCS-CALC-BLOCKER-2-RECALC-2026-10-01.md` — PCS BLOCKER-2 重算结果 — 蜡油加氢 XLS 独立计算 (~803 tok)
- `PCS-NOTE-BLOCKER-2-2026-10-01.md` — PCS BLOCKER-2 状态登记 — 蜡油加氢 XLS 提取 (~710 tok)
- `PCS-NOTE-catalyst_loading-取消-2026-10-05.md` — catalyst_loading 功能取消 — 该表不建，此功能先不做 (2026-10-05) (~925 tok)
- `PCS-NOTE-CIA-反向恢复-推到P8-2026-10-05.md` — CIA 反向恢复推迟到 P8 — 落地路径 (2026-10-05) (~933 tok)
- `PCS-NOTE-equipment_lib-废弃-2026-10-06.md` — PCS-NOTE: `equipment_lib` 表废弃裁决（2026-10-06） (~782 tok)
- `PCS-NOTE-T5-MJ-基准口径裁决-2026-10-05.md` — T5 综合能耗验收 — 电折标口径按 GB 30251-2024 修正，基准重建 (2026-10-05) (~3938 tok)
- `PCS-P2-CLOSE-REPORT.md` — PCS P2 Sprint Close Report（2026-09-08） (~2039 tok)
- `PCS-P3.2-SIM-AUDIT-REPORT.md` — PCS P3.2 SIM 全量审计报告 V1.0 (~1983 tok)
- `PCS-P3.2-SIM-AUDIT-V2.md` — PCS P3.2 SIM 全量审计报告 V2.0（Post-SIM-13 闭环） (~5875 tok)
- `PCS-P3.2-SIM-CLOSE-REPORT.md` — PCS P3.2 SIM Sprint 收口报告 V1.1 (~2145 tok)
- `PCS-P3.2-SIM-P3X-CLOSE-REPORT.md` — PCS P3.x SIM 收口报告 V1.0 (~1489 tok)
- `PCS-P3.3-COMMON-CLOSE-REPORT.md` — PCS P3.3 COMMON 平 收口报告（2026-09-08） (~790 tok)
- `PCS-P4-CLOSE-REPORT.md` — PCS-P4 验收报告（核心引擎） (~1106 tok)
- `PCS-P5-PLAN.md` — PCS P5 批计划锚点（2026-09-16 / 末次修订 2026-09-17） (~2208 tok)
- `PCS-P5-START-CHECKLIST.md` — PCS P5 启动前检查清单（12 项） (~2491 tok)
- `PCS-PLAN-P3.2-SIM-P3X.md` — PCS P3.2 SIM P3.x 续推计划 V1.1 (~2629 tok)
- `PCS-PLAN-P3.2-SIM.md` — PCS P3.2 SIM 实施 Writing-Plan（V1.0，2026-09-08） (~7883 tok)
- `PCS-PLAN-P4-CORE-ENGINE.md` — P4 核心计算引擎（第一批）实施计划 V1.1 (~2992 tok)
- `PCS-PLAN-P5-DEVICE-EQUIPMENT.md` — P5 设备计算模块（第二批）实施计划 V1.10 (~20491 tok)
- `PCS-PLAN-SUP-002-SPRINT SUP-002 Sprint Writing-Plan.md` — p2_sup_sprint_pc1_pipe_class_upgrade.py (~17953 tok)
- `PCS-SIGN-F-P0-001-2026-10-08-R1.md` — PCS 折标系数正式签字确认书（修订版） (~1470 tok)
- `PCS-SIGN-F-P0-001-2026-10-08.md` — PCS 折标系数正式签字确认书 (~1611 tok)
- `PCS-SIGN-T5-2026-10-05.md` — T5 综合能耗验收 — 正式封版 (2026-10-05) (~1431 tok)
- `PCS-T5-R1-ACCEPTANCE-2026-10-02.md` — PCS T5 ≤2% 验收报告 — F-P0-001 R1 综合能耗汇总 (~978 tok)
- `PCS-UI-SPEC.md` (~9161 tok)
- `PROD-CHECKLIST-F-P3-001-2026-10-02.md` — F-P3-001 Production 前置 Checklist (~1321 tok)
- `sprint3-plan-2026-10-02.md` — Sprint 3 计划: Production 前置 + Audit 可观测性 (~5668 tok)
- `sprint4-plan-2026-10-05.md` — Sprint 4 计划：供应商数据闭环 + 事件骨架 + 真实算例验收 (2026-10-05) (~2408 tok)
- `tasks.md` — tasks.md — PCS 工艺计算 + 代码债务分类跟踪 (~4357 tok)

## docs/adr/

- `0001-two-layer-signing-model.md` — 签署与版本采用两层模型：计算记录无 Rev，交付物承载全部发布语义 (~248 tok)
- `0002-changed-lifecycle-and-change-notice.md` — 已发布记录的修改走 CHANGED 生命周期 + 变更单机制，不回退 DRAFT、不写时复制 (~224 tok)
- `0003-upstream-change-stale-and-hash.md` — 上游变更命中锁定记录走 STALE 标记 + 哈希判定，替换 P1 的作废重建规则 (~237 tok)
- `0004-gate-formal-workspace-only.md` — 校核门禁与交付物仅存在于正式工作区，个人/临时区记录永远 DRAFT (~158 tok)
- `0005-equipment-sync-on-checked.md` — 设备记录在来源 CHECKED 时同步创建，状态随来源联动；哈希只覆盖设计参数 (~211 tok)
- `0006-configurable-deliverable-numbering.md` — 交付物 doc_no 由项目模板级可配置的编号模板生成，不硬编码编码规则 (~200 tok)
- `0007-customer-approval-proxy-recording.md` — 客户批准采用凭证代录：客户在系统外批准，内部授权人在系统内代录闭环 CUSTOMER 签署步骤 (~199 tok)
- `0008-change-notice-as-deliverable-subtype.md` — 变更单是交付物的子类型（deliverable_type=CHANGE_NOTICE），不是平行实体 (~233 tok)
- `0009-obsolete-and-tag-lifetime-uniqueness.md` — OBSOLETE = 人工弃用（分级凭证）；位号终身唯一，弃用不复用 (~232 tok)
- `0010-graded-change-reversal.md` — 变更撤销以"是否已对外生效"为界分级处理，新增 REVERSAL_PENDING 状态 (~211 tok)
- `0011-demo-license-active-record-counting.md` — 演示版模块限制按活记录计数（OBSOLETE 不计），交付物与变更单不限量 (~145 tok)
- `0012-configurable-record-approval-depth.md` — 记录层批准深度可配置；CHECKED = 全部配置步骤通过，是交付物绑定的唯一准入状态 (~218 tok)
- `0013-lineage-hash-anchor-drop-history.md` — 血缘以 record_id + 哈希锚定，删除全部 xxx_History 快照流水表 (~208 tok)
- `0014-stream-lightweight-gate.md` — 物流（streams）采用简化门禁：初次引入须校对，后续修改知情管理不重校对 (~208 tok)
- `0019-streams-manual-entry.md` — Streams 必须支持手动创建（含炼油油品特殊输入），与模拟导入并列且走同一校对流程 (~181 tok)
- `0020-two-phase-and-state-points.md` — 两相流必须同时保存总组成与气液相组成；T/P 变化通过新建状态点表达，不修改原值 (~165 tok)
- `0021-state-point-equipment-links.md` — （已被替代）状态点之间通过设备关联，设备计算自动产生下游状态点 (~106 tok)
- `0022-independent-stream-chains.md` — 物流与设备的连接模型：独立物流链——一条物流=一个管段，设备是物流间的转换函数 (~244 tok)
- `0024-snapshot-only-before-data-modification.md` — 快照仅在"数据即将被修改"瞬间创建，移除 STALE 自动存盘 (~394 tok)
- `0025-equipment-eventual-consistency-window.md` — 设备联动最终一致性窗口 ≤ 5 分钟（CIA 异步传播） (~353 tok)
- `0027-heat-results-dual-track.md` — P5-4 实施状态：duty 双轨字段已就位（决策 5 跟踪项闭环） (~1794 tok)
- `0028-psv-multi-standard-engine.md` — PSV 多标准引擎：项目级显式配置 + 双路径隔离 + 公式溯源 (~2827 tok)
- `0029-toe-conversion-and-detail-htri-templates.md` — ADR-0029：折标煤系数组与 DETAIL/HTRI 模板入库 (~361 tok)
- `0030-chedl-version-lock.md` — ChEDL 版本锁定：pyproject.toml 单一来源 + 包装层隔离 + dir() 前置核验 (~4861 tok)
- `0031-p4-task0-exemption.md` — P4 计算链条件启动：本体论 Task 0 全量后置 (~315 tok)
- `0032-vessel-process-calculation.md` — VESSEL 工艺计算架构（P5-1 容器计算） (~2158 tok)
- `0040-c-12-vessel-geometry-service-interface-freeze.md` — ADR-0040：C-12 vessel_service 公共接口 6 个月冻结 (~3027 tok)
- `0041-c-12-vessel-6-path-coverage.md` — ADR-0041：C-12 vessel_service 12 路径覆盖补全（Q4 2026） (~6559 tok)
- `ADR-0023：EquipmentTypeCode项目级可配置.md` (~927 tok)
- `README.md` — Project documentation (~242 tok)

## docs/adr/signatures/

- `0028-acceptance-resolution.md` — ADR-0028 V1.1 评审委员会决议（接受） (~1218 tok)
- `0028-v1.1-标准对比分析.md` — 标准对比分析：API 521 vs GB/T 150.1 附录 B 火灾工况 (~1694 tok)
- `0030-acceptance-resolution.md` — ADR-0030 V1.1 评审委员会决议（接受） (~1589 tok)
- `0030-v1.2-coolprop-extension.md` — ADR-0030 V1.2 修订说明：CoolProp 纳入锁定（D3 反向决议） (~1346 tok)
- `dba-btree-gist-install-confirmation.md` — DBA 执行确认：btree_gist 扩展预装（两库） (~563 tok)
- `dba-btree-gist-install-request.md` — DBA 执行请求：预装 btree_gist 扩展（两库） (~794 tok)
- `psv-gas-area-independent-verification.md` — PSV 气体泄放面积独立工程复算（C6 关闭报告） (~2360 tok)

## docs/ce-code-review/

- `CLOSURE-P2-P3-2026-10-02.md` — ce-code-review P2/P3 收口报告 v2 (2026-10-02 修订) (~1123 tok)

## docs/ce-code-review/20261001-174422-16a356de/

- `adversarial.json` — Declares is (~9747 tok)
- `correctness.json` (~5662 tok)
- `data-migration.json` — Declares column (~6834 tok)
- `files.txt` (~394 tok)
- `finish-input.json` (~1148 tok)
- `metadata.json` (~112 tok)
- `raw-returns.json` (~139 tok)
- `report.md` — P7 Sprint 2 — ce-code-review Report (~1951 tok)
- `security.json` — Declares PMS (~4035 tok)
- `stages.jsonl` (~43 tok)
- `synthesized-findings.json` (~5396 tok)

## docs/ce-code-review/20261001-sprint1-d8f67f72/

- `adversarial.json` — Declares output (~9060 tok)
- `api-contract.json` — Declares safety (~2612 tok)
- `correctness.json` — Declares match (~7458 tok)
- `data-migration.json` — Declares mismatch (~5284 tok)
- `files.txt` (~436 tok)
- `full.diff` (~105444 tok)
- `metadata.json` (~113 tok)
- `raw-returns.json` (~194 tok)
- `report.md` — P7 Sprint 1 — ce-code-review Report (~2211 tok)
- `security.json` (~11141 tok)
- `stages.jsonl` (~68 tok)
- `synthesized-findings.json` (~4946 tok)

## docs/contracts/

- `p45-contract-reconciliation-2026-09-16.md` — 后端 ↔ PCS-UI-SPEC 契约对账报告 (~1285 tok)

## docs/p6-gate-reports/

- `gate-01-open-channel-api.json` (~179 tok)
- `gate-03-cepci-confirmation.md` — G-03 CEPCI 数据确认（占位；工艺室签字待补） (~588 tok)
- `gate-04-cooling-tower-curves-confirmation.md` — G-04 冷却塔特性曲线数据确认（占位；工艺室签字待补） (~771 tok)
- `gate-04-cv-deviation.md` — G-04: CV/RESTRICTION 偏差验收报告（2026-09-24） (~1049 tok)
- `gate-05-filtration-media-library-confirmation.md` — G-05 过滤介质物性数据确认（占位；工艺室签字待补） (~877 tok)
- `gate-06-flare-radiation-limits-confirmation.md` — G-06 火炬地面辐射热通量 BEDD 限值数据确认（占位；工艺室签字待补） (~771 tok)
- `p6-open-001-decision.md` — P6-OPEN-001 裁决：OPEN_CHANNEL 模块自研兜底（fluids.open_channel API 缺失） (~620 tok)

## docs/superpowers/plans/

- `2026-08-29-p0-skeleton-schema.md` — P0 骨架 + Schema 实施计划 (~24883 tok)
- `2026-09-01-p1-cross-cutting-framework.md` — P1 横切关注点框架 实施计划 (~6155 tok)
- `2026-09-02-p2-implementation-plan.md` — P2 Implementation Plan (~20209 tok)
- `2026-09-03-p2-sprint-1.8-and-1.10.md` — P2 Sprint 1.8 闭环 + Sprint 1.10 V1.4 收敛实施计划 (~16448 tok)
- `2026-09-04-p2-sprint-1.9.md` — P2 Sprint 1.9（配置层收尾）Implementation Plan (~13285 tok)
- `2026-09-16-p45-frontend-sprint-batch3.md` — P4.5 批 3：P3/P4 计算页面 实施计划 (~5231 tok)
- `2026-09-16-p45-frontend-sprint.md` — P4.5 前端补课 Sprint 实施计划 (~6176 tok)
- `2026-09-17-p5-4-frontend-heat-ui.md` — P5-4 HEAT 前端 UI 实施计划（V1.3 对齐） (~13441 tok)
- `2026-09-19-p6-batch.md` — P6 高级计算模块（第三批）8 模块实施计划 (~6661 tok)
- `2026-09-25-p6-4-batch.md` — P6-4 单批实施计划 — C-06 / C-08 / C-12 / C-17 / C-24 五项 🔴 必做（V1.2） (~8272 tok)
- `2026-09-25-p6-4-batch.v0.md` — P6-4 单批实施计划 — C-06 / C-08 / C-12 / C-17 / C-24 五项 🔴 必做 (~7937 tok)
- `2026-09-25-p6-4-batch.v1.1.md` — P6-4 单批实施计划 — C-06 / C-08 / C-12 / C-17 / C-24 五项 🔴 必做（V1.2） (~8027 tok)
- `2026-09-26-p6-5-batch.md` — P6-5+ 13 项工艺计算增补 — 三批并行实施计划 (~32314 tok)
- `2026-09-26-p6-5-frontend-3pages.md` — P6-5 前端补课：3 计算页（heating-value / saturation-water-content / cv） (~213 tok)
- `2026-09-27-p6-6a-worley-reconciliation.md` — P6-6A 实施计划 — Worley XLS 算例对账批（24 个真实工程算例） (~1227 tok)
- `2026-09-27-p6-6b-data-source-replacement.md` — P6-6B 数据源替换批 — 9 CONFIG 表 + 4 内联常量 (~2415 tok)
- `2026-09-28-p6-6a-5-dhvap.md` — OPEN-P6-6A-5 Implementation Plan — ΔH_vap as input field (~1641 tok)
- `2026-09-28-p6-6a-6-glycol-full.md` — P6-6A-6 实施计划 — C-16 甘醇脱水 FULL 系统（关 Ruling 5 mapping defect）v5.1 (~18644 tok)
- `2026-09-28-p6-6a-6-glycol-full.v1.md` — P6-6A-6 实施计划 — C-16 甘醇脱水 FULL 系统（关 Ruling 5 mapping defect） (~7680 tok)
- `2026-09-28-p6-6a-7-c19-sizing.md` — P6-6A-7 C-19 排污孔板 Sizing 完整实现 — 单批计划 (~5961 tok)
- `2026-09-28-p6-6a-8-fire-coeff.md` — OPEN-P6-6A-8 Implementation Plan — fire_case_coefficient + fire_case_exponent (~1751 tok)
- `2026-10-01-p7-complete-sprint.md` — P7 Complete Implementation Plan (~12688 tok)
- `2026-10-15-p6-7-service-integration.md` — P6-7 服务集成批 — 工艺室 4 批交付物集成 (~3166 tok)
- `2026-10-31-p6-9-pickup-2-critical-fixes.md` — P6-9-PICKUP-2 — 4 CRITICAL + 2 HIGH 修复批 (~1794 tok)
- `2026-11-15-p6-8-glycol-dehydration-extensions.md` — P6-8 批 — Glycol Dehydration Service 扩展（OPEN-P6-6A-6 关闭） (~2024 tok)
- `2026-11-15-p6-9-pickup-3-debt-cleanup.md` — P6-9-PICKUP-3 — Debt cleanup (DB orphan + schema drift + ruff 18 + 21 LOW/INFO) (~736 tok)

## docs/superpowers/specs/

- `2026-09-02-p2-plan-design.md` — P2 Plan Design (~2715 tok)

## infra/ldap/

- `seed.ldif` (~328 tok)

## neqsim/

- `.cursorrules` — Cursor Rules for NeqSim (~303 tok)
- `.dockerignore` — Docker ignore rules (~183 tok)
- `.gitattributes` — Git attributes (~180 tok)
- `.gitignore` — Git ignore rules (~715 tok)
- `.pre-commit-config.yaml` (~300 tok)
- `.windsurfrules` — Windsurf Rules for NeqSim (~304 tok)
- `AGENTS.md` — NeqSim — Agent Instructions (~33899 tok)
- `azure-pipelines.yml` — Build your Java project and run tests with Apache Maven. (~235 tok)
- `CHANGELOG_AGENT_NOTES.md` — NeqSim API Changelog — Agent Notes (~90450 tok)
- `CITATION.cff` (~240 tok)
- `CLAUDE.md` — Claude Code Instructions for NeqSim (~99 tok)
- `CODE_OF_CONDUCT.md` — Contributor Covenant Code of Conduct (~1301 tok)
- `CODEOWNERS` — Merging to this repo requires approval from (~18 tok)
- `community-agents.yaml` — /*.agent.md", "agents/**/AGENT.md"] (~932 tok)
- `community-skills.yaml` — /SKILL.md"  # fallback when no catalog is found (~544 tok)
- `CONTEXT.md` — NeqSim — Industrial Agentic Engineering (~4481 tok)
- `CONTRIBUTING.md` — Contributing (~2505 tok)
- `Dockerfile` — Docker container definition (~651 tok)
- `GOVERNANCE.md` — NeqSim Governance (~845 tok)
- `install.cmd` (~1377 tok)
- `install.ps1` — install.ps1 - Bootstrap the NeqSim devtools package on Windows. (~3655 tok)
- `install.sh` — install.sh - Bootstrap the NeqSim devtools package on macOS/Linux. (~2810 tok)
- `LICENSE` — Project license (~3023 tok)
- `MAINTAINERS.md` — NeqSim Maintainers (~522 tok)
- `mvnw` — or more contributor license agreements.  See the NOTICE file (~3144 tok)
- `mvnw.cmd` — Declares Directory (~2262 tok)
- `pom.xml` — Maven project configuration (~4209 tok)
- `pomJava8.xml` — Declares execution (~3250 tok)
- `README.md` — Project documentation (~8231 tok)
- `SECURITY.md` (~232 tok)
- `VISION_AGENTS.md` — NeqSim Agent & Skill Vision (~1485 tok)

## neqsim/.config/

- `checkstyle_neqsim.xml` — Declares name (~5285 tok)
- `eclipse-java-google-style.xml` (~10287 tok)
- `neqsim_formatter.xml` (~10976 tok)

## neqsim/.devcontainer/

- `devcontainer-lock.json` (~181 tok)
- `devcontainer.json` — NeqSim Development Container Configuration (~1035 tok)
- `Dockerfile` — Docker container definition (~265 tok)

## neqsim/.github/

- `CODEOWNERS` — NeqSim repository ownership (~485 tok)
- `copilot-instructions.md` — Quick Orientation (~14581 tok)
- `dependabot.yml` (~237 tok)
- `external-skill-refs.txt` — Skills referenced from neqsim agent/instruction markdown that live in a (~157 tok)
- `neqsim-septic.code-workspace` (~55 tok)
- `pull_request_template.md` — Pull Request (~166 tok)

## neqsim/.github/ISSUE_TEMPLATE/

- `agent_bug.md` — Which agent or skill? (~267 tok)
- `bug_report.md` — Python example (~232 tok)
- `config.yml` (~100 tok)
- `feature_request.md` (~149 tok)
- `good_first_issue.md` — Summary (~271 tok)
- `newrelease.md` (~38 tok)
- `skill_contribution.md` — Skill / Agent name (~316 tok)

## neqsim/.github/agents/

- `capability.scout.agent.md` — When to Use This Agent (~4976 tok)
- `ccs.hydrogen.agent.md` — Primary Objective (~2695 tok)
- `consequence.analysis.agent.md` — Loaded skills (~1929 tok)
- `control.system.agent.md` — Skills to Load (~1912 tok)
- `documentation.agent.md` — Primary Objective (~2068 tok)
- `dynamic.equipment.agent.md` — Mission (~1105 tok)
- `emissions.environmental.agent.md` — Skills to Load (~3461 tok)
- `engineering.deliverables.agent.md` — Core Functionality (~4566 tok)
- `extract.process.agent.md` — Core Principle (~4043 tok)
- `field.development.agent.md` — Core Expertise (~4703 tok)
- `flow.assurance.agent.md` — Primary Objective (~3661 tok)
- `gas.quality.agent.md` — Primary Objective (~1965 tok)
- `literature.scout.agent.md` — When to Use (~2068 tok)
- `mechanical.design.agent.md` — Primary Objective (~4247 tok)
- `neqsim.test.agent.md` — Primary Objective (~2959 tok)
- `notebook.example.agent.md` — Primary Objective (~2238 tok)
- `optimize.agent.md` — Skills to Load (~1260 tok)
- `optimize.processmodel.agent.md` — Loaded skills (~2100 tok)
- `paperlab.agent.md` — Primary Objective (~1274 tok)
- `plant.data.agent.md` — Primary Objective (~2973 tok)
- `process.model.agent.md` — Primary Objective (~4060 tok)
- `pvt.simulation.agent.md` — Primary Objective (~1363 tok)
- `reaction.engineering.agent.md` — Skills to Load (~1356 tok)
- `README.md` — Project documentation (~5839 tok)
- `review.agent.md` — When to Use (~1651 tok)
- `root.cause.agent.md` — Skills to Load (~2746 tok)
- `router.agent.md` — Routing Decision Table (~3749 tok)
- `safety.depressuring.agent.md` — Primary Objective (~3917 tok)
- `solve.process.agent.md` — 1 ── WORKFLOW (follow this exactly) (~2091 tok)
- `solve.task.agent.md` — ⚠️ MANDATORY FIRST ACTION — CREATE TASK FOLDER (DO NOT SKIP) (~33742 tok)
- `standards.review.agent.md` — Primary Objective (~2580 tok)
- `technical.reader.agent.md` — Core Principle (~4060 tok)
- `thermo.fluid.agent.md` — Primary Objective (~1886 tok)
- `unisim.reader.agent.md` — MANDATORY: Load Skill First (~5814 tok)
- `utility.design.agent.md` — Skills to Load (~1282 tok)

## neqsim/.github/instructions/

- `thermodynamic-initialization.instructions.md` — Minimal thermodynamic initialization level (~520 tok)

## neqsim/.github/metrics/

- `dependabot-metrics.json` (~24 tok)
- `security-metrics.json` (~29 tok)

## neqsim/.github/skills/

- `README.md` — Project documentation (~5776 tok)
- `skill-index.json` (~10495 tok)

## neqsim/.github/skills/analyze_convergence/

- `SKILL.md` — Skill: Analyze Convergence (~1892 tok)

## neqsim/.github/skills/analyze_gibbs_convergence/

- `SKILL.md` — Skill: Analyze Gibbs Convergence (~2551 tok)

## neqsim/.github/skills/book_creation/

- `SKILL.md` — Skill: Book Creation in PaperLab (~6595 tok)

## neqsim/.github/skills/design_flash_benchmark/

- `SKILL.md` — Skill: Design Flash Benchmark (~1392 tok)

## neqsim/.github/skills/design_reactor_benchmark/

- `SKILL.md` — Skill: Design Reactor / Chemical Equilibrium Benchmark (~2298 tok)

## neqsim/.github/skills/figure-discussion/

- `SKILL.md` — Skill: Figure Discussion (observation → mechanism → implication → recommendation) (~2073 tok)

## neqsim/.github/skills/generate_publication_figures/

- `SKILL.md` — Skill: Generate Publication-Quality Figures (~4530 tok)

## neqsim/.github/skills/journal_formatting/

- `SKILL.md` — Skill: Journal Formatting (~4107 tok)

## neqsim/.github/skills/neqsim-agent-handoff/

- `SKILL.md` — NeqSim Agent Handoff Schema (~2219 tok)

## neqsim/.github/skills/neqsim-agentic-process-optimization/

- `SKILL.md` — Agentic Process-Model Optimization (~7678 tok)

## neqsim/.github/skills/neqsim-api-patterns/

- `SKILL.md` — NeqSim API Patterns (~13818 tok)

## neqsim/.github/skills/neqsim-autonomous-investigation/

- `SKILL.md` — NeqSim Autonomous Investigation Skill (~2715 tok)

## neqsim/.github/skills/neqsim-capability-map/

- `SKILL.md` — NeqSim Capability Map (~11291 tok)

## neqsim/.github/skills/neqsim-ccs-hydrogen/

- `SKILL.md` — CCS and Hydrogen Systems with NeqSim (~3845 tok)

## neqsim/.github/skills/neqsim-compressor-antisurge-recycle/

- `SKILL.md` — NeqSim Compressor Anti-Surge & Minimum-Speed Recycle Control Skill (~1810 tok)

## neqsim/.github/skills/neqsim-consequence-analysis/

- `SKILL.md` — NeqSim Consequence Analysis Skill (~2808 tok)

## neqsim/.github/skills/neqsim-controllability-operability/

- `SKILL.md` — NeqSim Controllability & Operability Skill (~2801 tok)

## neqsim/.github/skills/neqsim-depressurization-mdmt/

- `SKILL.md` — NeqSim Depressurization & MDMT Skill (~4209 tok)

## neqsim/.github/skills/neqsim-distillation-design/

- `SKILL.md` — Distillation Design Rules (~3257 tok)

## neqsim/.github/skills/neqsim-document-intelligence-extraction/

- `SKILL.md` — Document Intelligence Extraction (~2162 tok)

## neqsim/.github/skills/neqsim-dynamic-equipment-implementation/

- `SKILL.md` — Dynamic Equipment Implementation (~2219 tok)

## neqsim/.github/skills/neqsim-dynamic-simulation/

- `SKILL.md` — Dynamic Simulation Guidance (~9177 tok)

## neqsim/.github/skills/neqsim-electrolyte-systems/

- `SKILL.md` — Electrolyte Systems Guide (~3253 tok)

## neqsim/.github/skills/neqsim-eos-regression/

- `SKILL.md` — EOS Parameter Regression Workflow (~2444 tok)

## neqsim/.github/skills/neqsim-equipment-cost-estimation/

- `SKILL.md` — NeqSim Equipment Cost Estimation Skill (~3483 tok)

## neqsim/.github/skills/neqsim-field-development/

- `SKILL.md` — NeqSim Field Development Skill (~4551 tok)

## neqsim/.github/skills/neqsim-field-economics/

- `SKILL.md` — NeqSim Field Economics Skill (~2664 tok)

## neqsim/.github/skills/neqsim-flow-accelerated-corrosion/

- `SKILL.md` — NeqSim Flow-Accelerated Corrosion and High-Temperature pH Skill (~4007 tok)

## neqsim/.github/skills/neqsim-flow-assurance/

- `SKILL.md` — Flow Assurance Analysis with NeqSim (~17575 tok)

## neqsim/.github/skills/neqsim-hazid-fmea-eta-fta/

- `SKILL.md` — NeqSim HAZID / FMEA / ETA / FTA Skill (~3895 tok)

## neqsim/.github/skills/neqsim-heat-integration/

- `SKILL.md` — NeqSim Heat Integration Skill (~1541 tok)

## neqsim/.github/skills/neqsim-hydrogen-production/

- `SKILL.md` — Hydrogen Production with NeqSim (~4916 tok)

## neqsim/.github/skills/neqsim-input-validation/

- `SKILL.md` — NeqSim Input Validation Rules (~1732 tok)

## neqsim/.github/skills/neqsim-java8-rules/

- `SKILL.md` — Java 8 Compatibility Rules for NeqSim (~1285 tok)

## neqsim/.github/skills/neqsim-literature-search/

- `SKILL.md` — Literature & Web Search for Engineering Tasks (~1964 tok)

## neqsim/.github/skills/neqsim-model-calibration-and-data-reconciliation/

- `SKILL.md` — Model Calibration and Data Reconciliation (~2003 tok)

## neqsim/.github/skills/neqsim-notebook-patterns/

- `SKILL.md` — Jupyter Notebook Patterns for NeqSim (~5717 tok)

## neqsim/.github/skills/neqsim-optimization-and-doe/

- `SKILL.md` — NeqSim Process Optimization & DoE Skill (~4833 tok)

## neqsim/.github/skills/neqsim-pdf-ocr/

- `SKILL.md` — NeqSim PDF OCR Skill (~2673 tok)

## neqsim/.github/skills/neqsim-phase-envelope/

- `neqsim-phase-envelope-readme.md` — NeqSim PT Phase Envelopes (~497 tok)
- `SKILL.md` — NeqSim PT Phase Envelopes (~2996 tok)

## neqsim/.github/skills/neqsim-physics-explanations/

- `SKILL.md` — NeqSim Physics Explanations (~2759 tok)

## neqsim/.github/skills/neqsim-pid-process-operations/

- `SKILL.md` — P&ID to Process Operations (~7438 tok)

## neqsim/.github/skills/neqsim-pipeline-survey-processing/

- `SKILL.md` — Pipeline Survey Processing (~3678 tok)

## neqsim/.github/skills/neqsim-plant-data/

- `SKILL.md` — Plant Data Integration with Tagreader (~8821 tok)

## neqsim/.github/skills/neqsim-platform-modeling/

- `SKILL.md` — NeqSim Production Platform Modeling (~11844 tok)

## neqsim/.github/skills/neqsim-power-generation/

- `SKILL.md` — Power Generation with NeqSim (~7168 tok)

## neqsim/.github/skills/neqsim-process-extraction/

- `SKILL.md` — NeqSim Process Extraction Skill (~22492 tok)

## neqsim/.github/skills/neqsim-process-modeling/

- `SKILL.md` — NeqSim Process Modeling Skill (~4562 tok)

## neqsim/.github/skills/neqsim-process-safety/

- `SKILL.md` — NeqSim Process Safety Skill (~7819 tok)

## neqsim/.github/skills/neqsim-production-optimization/

- `SKILL.md` — NeqSim Production Optimization Skill (~7444 tok)

## neqsim/.github/skills/neqsim-professional-reporting/

- `SKILL.md` — NeqSim Professional Reporting Skill (~6269 tok)

## neqsim/.github/skills/neqsim-reaction-engineering/

- `SKILL.md` — Reaction Engineering Patterns (~2992 tok)

## neqsim/.github/skills/neqsim-regression-baselines/

- `SKILL.md` — NeqSim Regression Baseline Management (~1695 tok)

## neqsim/.github/skills/neqsim-relief-flare-network/

- `SKILL.md` — NeqSim Relief & Flare Network Skill (~3533 tok)

## neqsim/.github/skills/neqsim-root-cause-analysis/

- `SKILL.md` — NeqSim Root Cause Analysis Skill (~6200 tok)

## neqsim/.github/skills/neqsim-self-heating-ignition/

- `SKILL.md` — NeqSim Self-Heating and Spontaneous Ignition Skill (~2517 tok)

## neqsim/.github/skills/neqsim-standards-lookup/

- `SKILL.md` — NeqSim Standards Lookup (~6826 tok)

## neqsim/.github/skills/neqsim-stid-retriever/

- `SKILL.md` — Document Retrieval Skill for Engineering Tasks (~5942 tok)

## neqsim/.github/skills/neqsim-subsea-and-wells/

- `SKILL.md` — NeqSim Subsea & Wells Skill (~5444 tok)

## neqsim/.github/skills/neqsim-technical-document-reading/

- `SKILL.md` — Technical Document Reading Skill (~14372 tok)

## neqsim/.github/skills/neqsim-thermodynamic-initialization/

- `SKILL.md` — NeqSim thermodynamic initialization (~932 tok)

## neqsim/.github/skills/neqsim-trapped-liquid-fire-rupture/

- `SKILL.md` — Fire Rupture Study (~5978 tok)

## neqsim/.github/skills/neqsim-troubleshooting/

- `SKILL.md` — NeqSim Troubleshooting Playbook (~6907 tok)

## neqsim/.github/skills/neqsim-unisim-reader/

- `SKILL.md` — UniSim Design / HYSYS → NeqSim Conversion Skill (~19140 tok)

## neqsim/.github/skills/neqsim-utilities-specification/

- `SKILL.md` — NeqSim Utilities Specification Skill (~2407 tok)

## neqsim/.github/skills/neqsim-utility-design/

- `SKILL.md` — NeqSim Utility Design Skill (~2078 tok)

## neqsim/.github/skills/neqsim-water-hammer/

- `SKILL.md` — Water Hammer and Liquid Hammer Screening (~1296 tok)

## neqsim/.github/skills/neqsim-wax-calculations/

- `SKILL.md` — NeqSim Wax Calculations (~2882 tok)

## neqsim/.github/skills/neqsim_in_writing/

- `SKILL.md` — NeqSim integration for scientific writing (~2445 tok)

## neqsim/.github/skills/neqsim_standard_requirement_extraction/

- `SKILL.md` — Skill: NeqSim Standard Requirement Extraction (~606 tok)

## neqsim/.github/skills/paperlab_book_release_orchestration/

- `SKILL.md` — PaperLab Book Release Orchestration (~468 tok)

## neqsim/.github/skills/paperlab_book_to_paper_extraction/

- `SKILL.md` — PaperLab Book to Paper Extraction (~350 tok)

## neqsim/.github/skills/paperlab_journal_positioning/

- `SKILL.md` — PaperLab Journal Positioning (~338 tok)

## neqsim/.github/skills/paperlab_neqsim_api_claim_verification/

- `SKILL.md` — PaperLab NeqSim API Claim Verification (~581 tok)

## neqsim/.github/skills/paperlab_notebook_regression_baselines/

- `SKILL.md` — PaperLab Notebook Regression Baselines (~525 tok)

## neqsim/.github/skills/paperlab_paper_to_book_chapter/

- `SKILL.md` — PaperLab Paper to Book Chapter (~386 tok)

## neqsim/.github/skills/paperlab_publication_opportunity_mining/

- `SKILL.md` — PaperLab Publication Opportunity Mining (~530 tok)

## neqsim/.github/skills/paperlab_reproducibility_capsule/

- `SKILL.md` — PaperLab Reproducibility Capsule (~331 tok)

## neqsim/.github/skills/paperlab_scientific_traceability_audit/

- `SKILL.md` — PaperLab Scientific Traceability Audit (~911 tok)

## neqsim/.github/skills/paperlab_student_readability/

- `SKILL.md` — PaperLab Student Readability (~948 tok)

## neqsim/.github/skills/run_flash_experiments/

- `SKILL.md` — Skill: Run Flash Experiments (~1858 tok)

## neqsim/.github/skills/write_methods_section/

- `SKILL.md` — Skill: Write Methods Section (~1760 tok)

## neqsim/.github/workflows/

- `codeql.yml` — /*.sarif (~534 tok)
- `convert_notebooks.yml` — CI: Convert Notebooks to Markdown (~706 tok)
- `devcontainer_prebuild.yml` — CI: Prebuild Dev Container (~497 tok)
- `devtools_tests.yml` — CI: Devtools tests (~392 tok)
- `documentation-search.yml` — CI: Documentation search coverage (~413 tok)
- `energy-notebook-execution.yml` — CI: Execute Energy Network Notebooks (~1480 tok)
- `engineering-diagram-performance.yml` — CI: Engineering diagram performance (~535 tok)
- `execute-complete-pid-notebook.yml` — CI: Execute complete P&ID synthesis notebook (~1024 tok)
- `execute-ncs-hazop-safety-notebook.yml` — CI: Execute NCS HAZOP and safety engineering notebook (~1891 tok)
- `execute-offshore-engineering-notebook.yml` — CI: Execute complete offshore engineering notebook (~2004 tok)
- `execute-process-to-engineering-simulator.yml` — CI: Execute process-to-engineering simulator notebook (~1134 tok)
- `install_smoke_test.yml` — CI: Install smoke test (~1607 tok)
- `mcp_protocol_qualification.yml` — CI: MCP protocol qualification (~1176 tok)
- `mcp_server_release.yml` — CI: Build MCP Server Release (~1141 tok)
- `paperlab_replication_gate.yml` — or books/<slug>/**. Performs: (~1853 tok)
- `precommit.yml` — CI: Pre-commit checks (~515 tok)
- `publish_javadoc.yml` — CI: Deploy Javadoc (~175 tok)
- `publish_neqsim_image.yml` — CI: Publish NeqSim Image (~565 tok)
- `publish_to_maven_central.yml` — CI: Publish package to the Maven Central Repository (~749 tok)
- `release_with_jars.yml` — CI: Create release (draft) (~2725 tok)
- `research-scan.yml` — CI: Daily Research Scan (~1069 tok)
- `security-metrics.yml` — CI: Security Metrics Badge (~1028 tok)
- `skills_agents_lint.yml` — CI: Skills and agents lint (~572 tok)
- `spotless-format-patch.yml` — CI: Spotless format patch (~166 tok)
- `task_nip_issues.yml` — /neqsim_improvements.md" (~1228 tok)
- `task_quality_gate.yml` — CI: Task quality gate (~917 tok)
- `verify_build.yml` — CI: Run build, test and javadoc (~2089 tok)

## neqsim/.mvn/

- `maven.config` (~63 tok)

## neqsim/.mvn/wrapper/

- `maven-wrapper.properties` (~45 tok)

## neqsim/.openapi/

- `codex.yaml` (~132 tok)

## neqsim/devtools/

- `agent_search.py` — URL configuration (~3690 tok)
- `audit_report.py` — Audit Word and HTML report consistency after generation. (~1048 tok)
- `check_agent_skill_catalogs.py` — Check NeqSim agent and skill catalogs across sibling repositories. (~1473 tok)
- `check_documentation_search.py` — Validate NeqSim documentation sources and generated site-search coverage. (~4975 tok)
- `consistency_checker.py` — class: run (~7436 tok)
- `ensure_on_path.py` — Ensure the directory containing the installed ``neqsim`` console script is on (~3876 tok)
- `explore_unisim_com.py` — safe_get, safe_getvalue, explore_components, explore_stream + 3 more (~3680 tok)
- `generate_agent_skill_map.py` — Generate ``docs/development/AGENT_SKILL_MAP.md`` from agent files. (~1466 tok)
- `generate_equipment_documentation_catalog.py` — Generate the source-backed process-equipment documentation catalog. (~3633 tok)
- `generate_skill_index.py` — Generate the shared skill-id index consumed by the agent manifest validators. (~1337 tok)
- `generate_sources_md.py` — Organize collected task documents into per-source folders and generate a (~5392 tok)
- `industrial_sm_benchmark.py` — Run, aggregate, and validate the industrial S/M optimization benchmark. (~5976 tok)
- `install_agent.py` — /*.agent.md", (~31465 tok)
- `install_skill.py` — /SKILL.md" (~28925 tok)
- `neqsim_cli.py` — URL configuration (~1159 tok)
- `neqsim_contribute.py` — /*.md for dead links)") (~2438 tok)
- `neqsim_dev_setup.py` — URL configuration (~4966 tok)
- `neqsim_doctor.py` — URL configuration (~5741 tok)
- `neqsim_try.py` — URL configuration (~2584 tok)
- `new_skill.py` — URL configuration (~2067 tok)
- `new_task.py` — URL configuration (~45637 tok)
- `onboard.py` — URL configuration (~5179 tok)
- `paperlab_install.py` — Install PaperLab agents and skills for VS Code Chat. (~3233 tok)
- `pdf_ocr.py` — URL configuration (~3630 tok)
- `pdf_to_figures.py` — pdf_to_pngs, pdf_folder_to_pngs, main (~1783 tok)
- `pyproject.toml` — Python project configuration (~172 tok)
- `README.md` — Project documentation (~3844 tok)
- `run_spotless.py` — Cross-platform Spotless runner for pre-commit hooks. (~327 tok)
- `run_spotless.sh` — Cross-platform Maven wrapper selector for spotless (~72 tok)
- `skill_search.py` — search, main (~3067 tok)
- `stid_download.py` — URL configuration (~3220 tok)
- `task_audit.py` — find_task_folders, check_results_json, check_notes, check_notebooks + 7 more (~3176 tok)
- `task_search.py` — Cross-task keyword search across all task_solve/ folders. (~2204 tok)
- `test_agent_search.py` — Regression tests for devtools/agent_search.py semantic agent discovery. (~1441 tok)
- `test_check_documentation_search.py` — Unit tests for the documentation notebook-link audit. (~932 tok)
- `test_complete_offshore_engineering_study.py` — Contract and committed-execution checks for the offshore engineering study. (~1318 tok)
- `test_engineering_documentation.py` — Contract checks for the process-to-engineering documentation bundle. (~629 tok)
- `test_industrial_sm_benchmark.py` — Unit tests for industrial S/M benchmark aggregation and validation. (~1847 tok)
- `test_install_agent.py` — /*.agent.md", "agents/**/AGENT.md"] (~19900 tok)
- `test_install_skill.py` — /SKILL.md", (~11642 tok)
- `test_neqsim_studio.py` — Pure-Python tests for the NeqSim Studio package. (~2886 tok)
- `test_onboard.py` — Regression tests for the onboarding wizard. (~264 tok)
- `test_paperlab_install.py` — Tests: iter_paperlab_assets_find_definitions, iter_paperlab_assets_include_internal_when_requested, cmd_install_exports_to_explicit_vscode_dirs, cm... (~1130 tok)
- `test_render_engineering_pid.py` — Tests for the dependency-light DEXPI documentation renderer. (~905 tok)
- `test_report_gen.py` — Quick integration test for the generate_report.py template in new_task.py. (~4656 tok)
- `test_report_workflow.py` — Regression tests for the Solution Workflow report section. (~1059 tok)
- `test_skill_search.py` — Regression tests for devtools/skill_search.py sibling-repo skill indexing. (~813 tok)
- `test_unisim_outputs.py` — Test all UniSimToNeqSim output modes with a synthetic model. (~18720 tok)
- `test_validate_dexpi_interoperability.py` — Tests: csv_findings_are_typed_and_deterministically_sorted, run_requires_exact_checkout_and_retains_findings, baseline_comparison_checks_provenance... (~1836 tok)
- `test_validate_engineering_diagram_performance.py` — Contracts for engineering-diagram performance evidence validation. (~838 tok)
- `test_verify_agent_skill_refs.py` — Regression tests for the combined cross-repo skill-ref check in (~1113 tok)
- `test_verify_skills_agents.py` — Focused tests for the skill and agent verifier. (~474 tok)
- `unisim_neqsim_bridge.py` — class: max_deviation_pct, has_significant_deviation, to_dict, to_json + 4 more (~4206 tok)
- `unisim_reader.py` — class: component_names, has_critical_properties, write_e300 (~99636 tok)
- `unisim_writer.py` — class: warnings, parse (~18327 tok)
- `update_liquid_conductivity.py` — URL configuration (~1958 tok)
- `validate_dexpi_interoperability.py` — Validate a generated NeqSim DEXPI package with optional external importers. (~3653 tok)
- `validate_engineering_diagram_performance.py` — Validate deterministic engineering-diagram benchmark evidence and CI budgets. (~1864 tok)
- `validate_task_results.py` — /results.json. (~4551 tok)
- `verify_agent_schema_sync.py` — Guard the shared agent- and skill-manifest schemas against cross-repo drift. (~1058 tok)
- `verify_agent_skill_refs.py` — URL configuration (~4978 tok)
- `verify_mcp_tool_references.py` — Verify that MCP tool names referenced by skills and agents actually exist. (~1905 tok)
- `verify_notebooks.py` — Verify Jupyter notebooks are executed and error-free. (~1986 tok)
- `verify_skill_mirror.py` — Detect drift between the core ``.github/skills`` mirror and the source repos. (~1476 tok)
- `verify_skills_agents.py` — Lint .github/skills/ and .github/agents/ for structural integrity. (~2916 tok)

## neqsim/devtools/baselines/

- `engineering_diagram_performance.json` (~133 tok)

## neqsim/devtools/neqsim_dev_setup.egg-info/

- `entry_points.txt` (~11 tok)
- `PKG-INFO` (~123 tok)

## neqsim/devtools/neqsim_runner/

- `__init__.py` — submit_job, run_supervisor, job_status, list_jobs (~1078 tok)
- `__main__.py` — Entry point for: python -m neqsim_runner (~26 tok)
- `agent_bridge.py` — AgentBridge: submit_notebook, submit_script, submit_parametric_sweep, run_all + 6 more (~6145 tok)
- `cli.py` — cmd_submit, cmd_run, cmd_go, cmd_status + 3 more (~2084 tok)
- `job_helpers.py` — get_args, get_output_dir, save_checkpoint, load_checkpoint + 3 more (~1152 tok)
- `models.py` — JobStatus: to_dict, from_dict, is_retryable, set_status + 4 more (~1981 tok)
- `progress.py` — TaskProgress: is_resuming, current_phase, next_action, completed_milestones + 13 more (~3260 tok)
- `README.md` — Project documentation (~2921 tok)
- `store.py` — JobStore: save_job, get_job, list_jobs, get_pending_jobs + 5 more (~1985 tok)
- `supervisor.py` — Supervisor: run, stop (~2708 tok)
- `worker.py` — URL configuration (~2808 tok)

## neqsim/devtools/neqsim_runner/bootstrap/

- `__init__.py` (~0 tok)
- `notebook_executor.py` — Notebook executor - runs a .ipynb in a Jupyter kernel subprocess. (~2241 tok)
- `script_executor.py` — Worker bootstrap - runs inside the isolated subprocess. (~1442 tok)

## neqsim/devtools/neqsim_runner/examples/

- `_test_job.py` — Minimal test job that doesn't require NeqSim — tests the runner machinery. (~202 tok)
- `example_monte_carlo.py` — run_single_simulation, main (~1740 tok)
- `example_pipeline.py` — main (~563 tok)
- `example_simple.py` — main (~588 tok)

## neqsim/devtools/neqsim_runner/tests/

- `__init__.py` (~0 tok)
- `test_runner.py` — Tests for neqsim_runner package — covers critical fixes and core logic. (~5265 tok)

## neqsim/devtools/neqsim_studio/

- `__init__.py` — NeqSim Studio — a Python-first, newcomer-friendly way to build process models. (~926 tok)
- `build.py` — JSON build bridge for NeqSim Studio. (~856 tok)
- `core.py` — Core objects for NeqSim Studio. (~6295 tok)
- `edit.py` — Edit-by-chat helpers for NeqSim Studio (Proposal #4). (~3282 tok)
- `fluids.py` — Fluid helpers for NeqSim Studio. (~1540 tok)
- `gallery.py` — Recipe gallery / cookbook for NeqSim Studio (Proposal #5). (~1690 tok)
- `jsonspec.py` — Pure-Python flowsheet JSON spec builder for NeqSim Studio. (~3423 tok)
- `README.md` — Project documentation (~2642 tok)
- `templates.py` — Template recipes for NeqSim Studio (Proposal #2). (~3410 tok)
- `text.py` — Natural-language flowsheet builder for NeqSim Studio (Proposal #1). (~2750 tok)
- `wizard.py` — Guided wizard for NeqSim Studio (Proposal #3). (~1517 tok)

## neqsim/devtools/presentations/

- `generate_agent_skill_overview.py` — Generate a PowerPoint overview of the NeqSim agent and skill ecosystem. (~9142 tok)

## neqsim/devtools/task_template/

- `README.md` — Project documentation (~350 tok)
- `study_config.yaml` — Study configuration for NeqSim task solver. (~795 tok)
- `user_input.md` — User Input Log (~635 tok)

## neqsim/devtools/task_template/step1_scope_and_research/

- `analysis.md` — Deep Analysis & Solution Design (~721 tok)
- `capability_assessment.md` — Capability Assessment & Implementation Plan (~1245 tok)
- `neqsim_improvements.md` — NeqSim Improvement Proposals (NIPs) (~353 tok)

## neqsim/devtools/task_template/step2_analysis/starters/

- `README.md` — Project documentation (~381 tok)
- `starter_field_economics.ipynb` (~3016 tok)
- `starter_flow_assurance.ipynb` (~2198 tok)
- `starter_process_sim.ipynb` (~2760 tok)
- `starter_pvt_study.ipynb` (~2489 tok)

## neqsim/devtools/task_template/step3_report/

- `generate_report.py` — URL configuration (~40824 tok)

## pcs-backend/alembic/versions/

- `p7_s3_001_workspace_status.py` — F-P3-003 Sprint 3: workspaces.status 列 + 索引 (2-state ACTIVE/ARCHIVED). (~394 tok)
- `p7_s3_002_project_product_category.py` — p7_s3_002: projects.product_category — GB 30251-2024 §6.1.5 电折标口径判据. (~526 tok)
- `p7_s3_003_energy_config_classification_cols.py` — p7_s3_003: config_energy_conversion_factors 补 R1 分类列 (从未迁移的 schema drift). (~1788 tok)
- `p7_s3_003_energy_config_gb30251_a1.py` — p7_s3_003: 折标系数对齐 GB 30251-2024 附录A 表A.1. (~1360 tok)
- `p7_s3_005_gas_media_and_low_temp_heat.py` — p7_s3_005: utility_gas_media + utility_low_temp_heat (P7-6B 收尾). (~1833 tok)
- `p7_s5_001_drop_equipment_lib.py` — p7_s5_001: 删除 `equipment_lib` 死表（设备库实际由 ConfigAsset CATEGORY_6 承载）. (~775 tok)

## pcs-backend/app/api/v1/

- `__init__.py` (~1404 tok)
- `_guard.py` — API endpoint 守卫 helper（BLOCKER-3 修复共享函数）。 (~602 tok)
- `audit.py` — Audit Query API (F-P2-009 Sprint 3 / Issue 7 混合 RBAC). (~2535 tok)
- `config.py` — Config API — 7 端点（Task 2.8 / P2 Sprint 1.7）。 (~5196 tok)
- `equip_lib.py` — equip-lib 端点（Task 1.9.5 / P2-EQL-001）。 (~724 tok)
- `filtration.py` — P6-3 FILTRATION API（SPEC §3.2.7 + Task 34）。 (~5529 tok)
- `flare.py` — P6-2 FLARE_SYS API：Task 20 header_sizing + Task 21 kod_sizing + (~5836 tok)
- `mock_auth.py` — Mock 登录：仅 env != production 时挂载。固定 4 个角色账号，无 LDAP 依赖。 (~560 tok)
- `pipe_classes.py` — 管道等级端点（Task 1.9.2 / P2-STD-001）。 (~6127 tok)
- `pipe_codes.py` — 管道代码 API（FMT-4 / SUP-002 §11.5/§12）。 (~7377 tok)
- `pipe_net.py` — P4-3-3 管网 Hardy-Cross 计算 + 落库 + outlet_stream API。 (~3646 tok)
- `pipe.py` — P4-2-5 PIPE 计算链 API。 (~2299 tok)
- `projects.py` — 项目产品类别 API (product_category — GB 30251-2024 §6.1.5 电折标口径判据). (~1184 tok)
- `psychro.py` — P6-2 PSYCHRO API：Task 26 6 calc endpoints + psychro_persist CRUD endpoints。 (~7320 tok)
- `pump.py` — P4-4-4 PUMP 链 API。 (~2574 tok)
- `records.py` — Records API（Sprint 2）。 (~3276 tok)
- `sep_equip.py` — P5-2-4 SEP_EQUIP API：POST /calculate 端点契约。 (~1773 tok)
- `sim_imports_query.py` — P3.x SIM-27：sim_imports 9 类查询端点（spec §5.5）。 (~4193 tok)
- `stream_symbols.py` — 物流符号表端点（SYM-3 / SUP-002 §8）。 (~4194 tok)
- `streams.py` — P3.2 SIM-6 + SIM-8 + SIM-24：物流 / 状态点手工表单 API（spec V1.6 §3.2）。 (~6705 tok)
- `util.py` — S1-5b UTIL API endpoints。 (~8191 tok)
- `workspaces.py` — Workspace API（Sprint 1）。 (~1513 tok)

## pcs-backend/app/core/

- `config.py` — 应用全局配置（pydantic-settings + 环境变量 + .env 兜底）。 (~1084 tok)
- `errors.py` — FastAPI 全局异常处理器 + 统一 PcsError 信封。 (~2419 tok)
- `security.py` — JWT 编解码 + 密码哈希 + JTI 吊销。HS256，密钥由 Settings.secret_key 提供。 (~1249 tok)

## pcs-backend/app/models/

- `config.py` — 成本指数 / 元数据型 CONFIG 表（与 config_domain 的业务配置域区分）。 (~11272 tok)
- `enums.py` — 业务枚举（项目/角色/状态等数据库可空字符串字段的 Python 枚举映射）。 (~3800 tok)
- `equipment.py` — 设备/器材库 ORM 模型（P5-2-4 / P5-3 选型库）。 (~3186 tok)
- `project.py` — 项目/工作区/成员 ORM 模型（核心租户隔离维度）。 (~7227 tok)
- `util.py` — S1-5 R1: UtilResults ORM (util_results 单表) + jsonb_deprecated marker。 (~8014 tok)

## pcs-backend/app/schemas/

- `audit.py` — Audit Query Pydantic schemas (F-P2-009 Sprint 3 / Issue 5). (~769 tok)
- `project.py` — 项目产品类别 schema (GB 30251-2024 §6.1.5 电折标口径判据). (~297 tok)
- `util.py` — S1-5b UTIL API schemas。 (~3550 tok)
- `workspace.py` — Workspace Pydantic schemas（Sprint 1）。 (~711 tok)

## pcs-backend/app/services/

- `advisory_lock.py` — Postgres advisory lock（事务级）防止并发状态转移。 (~862 tok)
- `audit_service.py` — AuditService：审计统一入口（Issue 6 锁定）。 (~610 tok)
- `ldap_client.py` — LDAP 简易封装。Task 9 用，Task 10 引入 mock 旁路。 (~1011 tok)
- `stream_service.py` — P3.2 SIM-4 + SIM-8 + SIM-13：StreamService 物流 / 状态点 CRUD + 状态机（spec V1.6 §3.2.3）。 (~6322 tok)

## pcs-backend/app/services/util/

- `utility_energy_summary_service.py` — P7 Sprint 2 T5: 综合能耗汇总 service (utility_energy_summary). (~10715 tok)

## pcs-backend/scripts/

- `check_migration_idempotency.py` — 检查 alembic migrations 是否用 if_exists / if_not_exists (F-P3-002 fix). (~706 tok)
- `p7_open_009_t0_seed_energy_conversion_factors.py` — t**) GB 30251-2024 附录A 序号4 — " (~3764 tok)
- `p7_open_012_t5_r1_verification.py` — P7 Sprint 2 T5 ≤2% 验收脚本（蜡油加氢 XLS R1 重算对比）。 (~4491 tok)
- `p7_open_016_config_conformance_audit.py` — PCS 折标系数 vs GB 30251-2024 附录A 表A.1 一致性审计. (~3146 tok)
- `p7_s3_003_backfill_config_audit.py` — F-P0-001 R1 audit backfill (P7 Sprint 3 / Issue 6). (~1249 tok)

## pcs-backend/tests/

- `conftest.py` — Sprint 1 + P2 共享测试 fixtures。 (~4455 tok)
- `test_audit_guard.py` — P7-7+ BLOCKER-3 guard 集成测试 — /equipment-deletion-audit 端点. (~1256 tok)
- `test_audit_query.py` — F-P2-009 Sprint 3: Audit Query 后端测试 (Issue 5 错误路径 + Issue 7 混合 RBAC). (~3389 tok)
- `test_jwt_production.py` — F-P3-001 Sprint 3: JWT production hardening + LDAP fail-closed 测试. (~2042 tok)
- `test_rbac_audit.py` — F-P3-001 checklist #5: RBAC 401/403 audit log + per-IP rate limit 测试. (~1861 tok)
- `test_schema.py` — V3.1 Schema 层契约：表数量、关键约束、ADR-0023 复合键。 (~2523 tok)
- `test_workspace_archive.py` — F-P3-003 Sprint 3: Workspace archive PATCH 端点测试. (~1272 tok)

## pcs-backend/tests/api/v1/

- `test_gas_media_and_low_temp_heat_api.py` — 工艺气体 / 低温热 CRUD API 测试 (P7-6B 收尾). (~2562 tok)
- `test_meta.py` — Meta API 测试（P4.5 P45-0-4 / P45-0-4.5 V1.1）。 (~3030 tok)
- `test_project_product_category.py` — 项目产品类别 API (product_category, GB 30251-2024 §6.1.5 电折标口径判据). (~2174 tok)
- `test_subtable_duplicate_conflict.py` — 既有子表 POST 端点的 UNIQUE 冲突处理 (2026-10-05). (~1507 tok)

## pcs-backend/tests/services/

- `test_stream_transition.py` — P3.2 SIM-13：StreamService.transition() 状态机集成测试（闭环审计 D-1）。 (~2982 tok)

## pcs-backend/tests/services/util/

- `test_electricity_value_type_policy.py` — 电折标口径按项目产品类别强制 (用户裁决 2026-10-05「按 project 产品类型强制」). (~2934 tok)
- `test_energy_mj_from_config.py` — 耗能工质 MJ 从 CONFIG 推导 (Q2, 用户裁决 2026-10-05). (~1419 tok)
- `test_gas_media_and_low_temp_heat.py` — 工艺气体 / 低温热子表聚合 (P7-6B 收尾). (~2512 tok)
- `test_gb30251_config_conformance.py` — GB 30251-2024 附录A 表A.1 折标系数一致性回归 (2026-10-05). (~1427 tok)
- `test_utility_energy_summary.py` — P7 Sprint 2 T5: utility_energy_summary service 测试. (~9769 tok)

## pcs-frontend/.gstack/qa-reports/

- `qa-report-pcs-frontend-2026-10-03-sprint3-batch2.md` — PCS Frontend QA Report — Sprint 3 Batch 2 (2026-10-03) (~1424 tok)

## pcs-frontend/e2e/

- `audit_log.spec.ts` — AuditLogPage e2e (F-P2-009 Sprint 3 / Issue 7). (~864 tok)
- `cooling_water.spec.ts` — P7-6B CoolingWaterPage 端到端测试 (Playwright / R1 §7.2 9 类水). (~966 tok)
- `energy_summary.spec.ts` — P7 Sprint 2 T5 EnergySummaryAggregatePage 端到端测试 (Playwright / R1 §7). (~1139 tok)
- `fixtures.ts` — Playwright e2e fixtures (F-P2-009 Sprint 3 / Issue 7). (~306 tok)

## pcs-frontend/src/

- `App.tsx` — router — renders form (~1070 tok)

## pcs-frontend/src/api/

- `audit.ts` — Audit Query API 客户端 (F-P2-009 Sprint 3 / Issue 7). (~720 tok)

## pcs-frontend/src/layouts/

- `MainLayout.tsx` — 在 MENU_ITEMS 中找 path 命中的条目（含父 group）。找不到返回 []。 (~1538 tok)

## pcs-frontend/src/mocks/

- `handlers.ts` — MSW handlers — 离线 mock server（P45-0-5 + QA 2026-09-16） (~8100 tok)

## pcs-frontend/src/pages/

- `routeWrappers.tsx` — 路由层默认 fixtures 包装器（QA fix / ISSUE-002 + 11 组件实例化） (~2937 tok)

## pcs-frontend/src/pages/audit/

- `AuditLogPage.tsx` — AuditLogPage — Audit Query viewer (F-P2-009 Sprint 3 / Issue 7). (~2271 tok)

## pcs-frontend/src/pages/util/

- `EnergySummaryAggregatePage.tsx` — EnergySummaryAggregatePage — 综合能耗聚合 UI（P7 Sprint 2 T5 / R1 §7）。 (~3359 tok)

## pcs-frontend/tests/api/

- `audit_api.test.ts` — Audit API 客户端测试 (F-P2-009 Sprint 3 / Issue 7). (~512 tok)

## pcs-frontend/tests/mocks/

- `handlers.test.ts` — MSW seed + handler shape 验证 — 防 MSW ↔ OpenAPI drift (P45-0-5) (~1807 tok)

## pcs-frontend/tests/pages/audit/

- `AuditLogPage.test.tsx` — AuditLogPage 组件测试 (F-P2-009 Sprint 3). (~598 tok)
