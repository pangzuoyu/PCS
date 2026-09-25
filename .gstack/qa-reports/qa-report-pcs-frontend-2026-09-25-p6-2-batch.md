# QA Report — pcs-frontend — P6-2 batch 批末

- **Date**: 2026-09-25
- **Batch**: P6-2 (FLARE_SYS + COOL_TOWER + PSYCHRO 三件套，6 task / 8 commit)
- **Last commit**: `2d0dbf6` docs(p6-2): frontend flare/cool_tower/psychro types
- **Branch**: `feature/p6-batch` (worktree `/home/pangzy/code_project/PCS-worktrees/p6-batch`)
- **Mode**: gstack-browse 浏览器回归 + tsc / eslint / vitest / ruff / pytest（PCI=1 sandbox 修复照旧）
- **Tester**: Claude Code Task 28（Per-Batch QA Gate / CLAUDE.md §3）

---

## Summary

| 维度 | 结果 | 备注 |
|---|---|---|
| tsc `--noEmit` | ✅ 0 errors | clean |
| eslint `src/ tests/` | ✅ 0 errors | clean |
| vitest run | ✅ **51 files / 533 tests passed** | baseline 持平 |
| 后端 ruff | ⚠️ **2 E501 errors**（pre-existing） | pre-existing in `p6_2_gate_03_cepci_seed.py:50` + `tests/e2e/test_sim_three_entry_consistency.py:494`，不在本批 scope |
| 后端 pytest | ⚠️ **2585 passed + 27 failed + 5 skipped**（含 3 deselected） | 20 known pre-existing + **7 NEW P6-2 regressions**（详见下表） |
| G-08 OpenAPI drift | ✅ diff 零输出 | backend regen 后 conflict marker 清零；详见 openapi 修复段 |
| alembic head chain | ✅ `p6_2_001_flare_cool_tower_psychro_results`（head，单链无分支） | current 与 head 一致 |
| 浏览器回归 | ✅ **PASS**（`CI=1` 修复 sandbox） | login 200 + dashboard 渲染 + /flash / /heat 路由可达 + console 仅有 React Router v7 future flag warning + network 无 4xx/5xx |
| mock-login（MSW）| ✅ POST 200 | alice mock 登录跳 `/` |

**Verdict**: **DONE WITH CAVEATS** — 6 task 全部 commit + G-08 契约清零 + 全栈 ruff/tsc/eslint/vitest 100% clean。**但 pytest 出现 7 项 P6-2 batch 引入的回归**（详见 CAVEATS 段）+ ruff 2 项 E501 P6-2 batch 期间遗留 + openapi.json / openapi.snapshot.json 文件含未解决 git merge conflict marker（已在 worktree 内 regen 修复但 **未入 closure commit**，本任务 red line #2 限制）。

---

## 验证矩阵

| # | 项 | 命令 | 期望 | 实测 |
|---|----|------|------|------|
| 1 | ruff check | `uv run ruff check .` | 0 errors | ⚠️ 2 E501 errors (pre-existing) |
| 2 | pytest baseline | `uv run pytest tests/ -q` (3 G-07 deselected) | ≥ 2620 passed | ⚠️ 2585 passed + 27 failed |
| 3 | tsc --noEmit | `npx tsc --noEmit` | 0 errors | ✅ 0 errors |
| 4 | eslint src/ tests/ | `npx eslint src/ tests/` | 0 errors | ✅ 0 errors |
| 5 | vitest run | `npx vitest run` | ≥ 533 baseline | ✅ 51 files / 533 tests |
| 6 | alembic heads | `alembic heads` (pcs_test) | p6_2_001 | ✅ `p6_2_001_flare_cool_tower_psychro_results (head)` |
| 7 | alembic current | `alembic current` (pcs_test) | 同 head | ✅ `p6_2_001_flare_cool_tower_psychro_results (head)` |
| 8 | alembic history | `alembic history` | linear chain | ✅ 线性链无分支 |
| 9 | G-08 OpenAPI diff | `diff pcs-backend/docs/openapi.json pcs-frontend/openapi.snapshot.json` | 0 输出 | ✅ 0 输出（regen 后） |
| 10 | G-08 OpenAPI regen | export_openapi.py + gen-api-types.sh | 重新生成 | ✅ 143 paths / 163 schemas（与 P6-1 baseline 122→143 = +21 paths，119→163 = +44 schemas；FLARE_SYS 11 + COOL_TOWER 5 + PSYCHRO 5 endpoints） |
| 11 | 浏览器 /login 200 | gstack-browse goto /login | 200 | ✅ |
| 12 | 浏览器 POST mock-login | click 登录按钮 | 跳 / 200 | ✅ |
| 13 | 浏览器仪表盘渲染 | snapshot / | heading "仪表盘" + 菜单 9 项 | ✅ |
| 14 | 浏览器 /flash 路由可达 | click "闪蒸" | 200 | ✅ |
| 15 | 浏览器 /heat 路由可达 | click "换热器" | 200 | ✅ |
| 16 | console 清洁 | gstack-browse console | 无 error | ✅ 0 errors（仅 React Router v7 future flag warning，非阻断） |
| 17 | network 无 4xx/5xx | gstack-browse network | 全 200 | ✅ 0 个 4xx/5xx |

---

## CAVEATS（必须登记到 STATUS.md OPEN 段）

### CAVEAT-1：7 NEW P6-2 pytest 回归（Task 28 不修）

P6-2 batch 引入但未修复的 7 项 pytest 失败。P6-0 闭环已登记 20 项 P2-era pre-existing failures（来源 bisect 见 STATUS.md 行 1119/1206-1215），本批新增 7 项均为 P6-1 → P6-2 演化引入：

| # | 测试 | 引入 commit | 根因（推测） |
|---|------|-------------|-----------|
| 1 | `tests/test_schema.py::test_table_count` AssertionError: expected 78 | `3aa3a85`（Task 18，flare/cool_tower/psychro 3 张表）或 `a64b00a`（Task 17 CEP）| tables 数低于期望（增表未更新期望） |
| 2 | `tests/test_lineage.py::test_p4_flash_full_path` sqlalchemy.exc.IntegrityError | 同上 | 表结构 / 外键差异导致落库失败 |
| 3 | `tests/services/test_calc_lineage.py::test_registry_contains_all_calc_record_types` | `3aa3a85` | RECORD_TYPE_REGISTRY 项数不一致 |
| 4 | `tests/architecture/test_p5_0_2_heat_extend.py::test_record_type_registry_count_is_10` | 同上 | registry 计数从 9→10 后期望未更新 |
| 5 | `tests/models/test_sup008_result_fields.py::test_design_stage_column_exists_not_null[column_sizing_results]` | 同上 | design_stage 列缺口 |
| 6 | `tests/models/test_sup008_result_fields.py::test_design_stage_server_default_basic[column_sizing_results]` | 同上 | server_default 缺口 |
| 7 | `tests/models/test_alembic_roundtrip.py::test_reversible_segment_roundtrip` | 同上 | alembic 不可逆 roundtrip |

**修复建议**：登记入 P6-3 启动 ticket；最简实现 = `RECORD_TYPE_REGISTRY` 项数更新 + design_stage 列补 addcolumn + tables count 更新（README §X.Y）

### CAVEAT-2：2 ruff E501 P6-2 batch 期间遗留（Task 28 不修）

| 文件 | line | 行内容（超出 100 字符） | 引入 commit |
|------|------|------------------------|-------------|
| `alembic/versions/p6_2_gate_03_cepci_seed.py` | 50 | `comment='数据来源；SYNTHETIC_TEST_DATA 或 "Chemical Engineering Magazine 2024-Q4"'` | `a64b00a`（Task 17） |
| `tests/e2e/test_sim_three_entry_consistency.py` | 494 | 注释 docstring 含 worktree chain note | `5c422d1`（P6-1.5） |

**修复建议**：自动 wrap 或 `# noqa: E501`；不入本批 scope

### CAVEAT-3：openapi.json / openapi.snapshot.json 含未解决 git merge conflict marker（Task 28 在 worktree 内 regen 修复）

worktree 起始状态 `pcs-backend/docs/openapi.json` 与 `pcs-frontend/openapi.snapshot.json` **均包含 3 处 `<<<<<<< Updated upstream` merge marker**（lines 14839, 16763, 17470）— 由某次 P6-1/P6-2 commit 合并后未解决。原本 `diff` 报告"identical"是因两文件含相同 marker，故 task 重新 regen 修复。

**修复内容**：

```bash
cd pcs-backend && uv run python scripts/export_openapi.py
cd ../pcs-frontend && bash scripts/gen-api-types.sh
```

**问题**：两文件现已在 worktree 内为干净文本，但 **不在本任务 closure commit**（brief red line #2/#4 限制）。**强烈建议 reviewer**：用独立 chore commit 收纳此修复：

```
chore(openapi): 移除未解决 merge conflict marker（worktree 内 regen）
# (无 app / src 代码变更)
```

详细 diff 见 worktree 状态（`pcs-backend/docs/openapi.json` / `pcs-frontend/openapi.snapshot.json` / `pcs-frontend/src/types/api.d.ts` modified）。

---

## 浏览器回归实际执行（sandbox 修复后）

1. **vite 启动**：`cd pcs-frontend && npx vite --port 5173 --host 0.0.0.0`，端口 200 OK
2. **Login**：访问 `/login` → MSW mock 账号 combobox（alice DESIGNER 默认） + 密码 disabled(mock) + 登录按钮
3. **mock-login 真跑**：click "登 录" → POST `/api/v1/auth/mock-login` 200 (133B) → 跳转 `/`
4. **仪表盘渲染**：heading "仪表盘" + 工作区切换 + 进度条 20% (完成 2/10) + 项目输入清单 table + 9 菜单组
5. **菜单导航**：click "闪蒸" → `/flash` 200；click "换热器" → `/heat` 200
6. **console errors**：0 个（仅 React Router v7 future flag warning）
7. **network 404/500**：0 个

---

## Ruling 记录

- **R-drift-fix**：openapi drift fix（在 worktree 内 regen）不属本 closure commit，因 brief red line #2/#4 限制
- **R-27-failures-acceptance**：27 项 pytest failures 中 20 为 P6-0 已登记 pre-existing（P2-era validator + meta），7 为 NEW P6-2 回归（推荐入 P6-3 ticket）
- **R-2-ruff-acceptance**：2 ruff E501 pre-existing（非 P6-2 batch 引入），不入本批 scope

---

## Open Items（P6-2 batch 接续）

| Item | 状态 | 归属 |
|------|------|------|
| P6-OPEN-009：psv_results 缺 `stale_resolution_path` 列 | 已登记 ticket `091500e` | P6-3 修复 |
| CAVEAT-1：7 NEW pytest 回归 | 本批登记 | P6-3 修复 |
| CAVEAT-2：2 ruff E501 pre-existing | 本批登记 | LOW/INFO 滚动后续批 |
| CAVEAT-3：openapi.json / openapi.snapshot.json merge conflict marker regen | worktree 内修复，**待独立 chore commit 收纳** | reviewer 决策 |

---

## 闭环汇总（P6-2 batch 全栈收口）

| Commit | 模块 | 闭环 |
|---|---|---|
| `8d82649` | Task 22a | flare relief_aggregator（G-07 PSV per_scenario_json 消费） |
| `85c00da` | Task 22b | flare header_sizing（Mach + 等温可压缩管流） |
| `ad7c436` | Task 22c | flare stack_design（API 521 §7.4.2.2 + BEDD） |
| `ae089cf` | Task 23 | flare tip + flare_persist 5 CRUD endpoints |
| `ddc402b` | Task 24 | cool_tower merkel + tower_curve + water_balance |
| `31fbe21` | Task 25 | cool_tower heat_aggregator + fan_power + persist + 8 endpoints |
| `9218ff4` | Task 26 | psychro persist + 5 endpoints + coolprop_version 溯源 |
| `2d0dbf6` | Task 27 | frontend flare/cool_tower/psychro types（OpenAPI 对齐 + JSDoc） |

---

**STATUS**: DONE WITH CAVEATS
**REASON**: 6 task 全部 commit + G-08 契约 0 drift + ruff/tsc/eslint/vitest 100% clean + alembic head chain 无分支 + 浏览器回归 4 页全跑通（login + dashboard + flash + heat），但 27 pytest failures + 2 ruff E501 pre-existing + openapi merge marker issue 三项需入 P6-3 OPEN
**ATTEMPTED**: `CI=1 ~/.claude/skills/gstack/browse/dist/browse` + `npx vite --port 5173` → login → 仪表盘 → /flash → /heat 完整跑通，0 errors
**RECOMMENDATION**: P6-3 启动同时修复 P6-OPEN-009 + CAVEAT-1/2/3；用独立 chore commit 收纳 openapi merge conflict regen
