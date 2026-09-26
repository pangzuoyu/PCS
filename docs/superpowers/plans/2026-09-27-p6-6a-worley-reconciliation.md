# P6-6A 实施计划 — Worley XLS 算例对账批（24 个真实工程算例）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用 `sample/Process caculation from Worley/` 的 24 个真实工程算例（WS-CA-PR-*.xls）对 PCS 全部已实现计算模块做首次真实数据对账，产出 `worley_*.json` 真实基准 fixture + 对账报告。

**Architecture:** ① XLS→JSON 提取工具（xlrd≥2.0）→ ② 人工审阅定位输入/输出区 → ③ 逐模块真实 fixture + 对账测试（容差按 SPEC §5 三级：强公式 0.1% / 经验拟合 1% / 图版查表 3~5% + 手算舍入放宽）→ ④ 失败分类处置（代码 bug 修 / 算法变体登记 / 舍入放宽）。

**Tech Stack:** Python + xlrd（.xls OLE2）+ pytest + 现有 frozen dataclass service 层（零改动为默认，bug 修复为例外）。

**Spec:** `spec/PCS-SPEC-ADD-001 计算覆盖增补规格说明书.md` V1.10（§0.1 XLS↔C-XX 映射表 + §5 验收分级）

**用户裁决（2026-09-27 brainstorm）：**
- 分两批：**本批 A = XLS 对账**（全自动可闭环）；批 B = CONFIG/常量数据源替换（文献精录 + 期号，独立立项）
- Kb 库：批 B 用 API 520 Fig.30 标准值替换，厂商细分（LESER/Consolidated）后置待用户样本
- Nielsen 缺口：**Task 0 顺带核实** WS-CA-PR-020 是否含 >25wt% 甲醇工况；有则补实现（~0.5 天），无则登记不补

## Global Constraints

- service 层 frozen dataclass / PcsError / formula_ref 契约**零改动**（对账批只读 + fixture；bug 修复走独立 commit 且需 root-cause）
- 容差分级（SPEC §5）：强公式 rel≤1e-3 / 经验拟合 rel≤1e-2 / 图版查表 rel≤5e-2；对 XLS 手算舍入可再放宽一档（登记理由）
- `sample/` 目录 gitignored——提取产物 JSON 入 `pcs-backend/tests/services/**/fixtures/worley_*.json`
- XLS 文件名含尾随空格（`WS-CA-PR-010 .xls` / `WS-CA-PR-014 .xls`）——工具需容错
- 双库已对齐 head `p6_5_006`；schema 敏感测试前置 alembic 检查（CLAUDE.md 规则）

## Review Focus（最可能咬人的 5 类输入/失败模式）

1. **XLS 单位口径**（Worley 算例可能英制输入 vs PCS SI 基准）→ 每 fixture 记录单位换算链
2. **算法变体**（XLS 手算用了 PCS 未实现的变体，如不同 K 表版本）→ 失败分类登记，不硬凑容差
3. **XLS 嵌入对象/图表**（部分值在图里不在单元格）→ 提取工具标注"缺失"，人工转录
4. **手算舍入**（Worley 工程师 3 位有效数字）→ 断言用 tolerance 而非精确相等
5. **多工况 sheet**（一个 XLS 多个 case）→ fixture 用 list 支持多 case

---

## Task 0: XLS 提取工具 + 全量 dump + Nielsen 核实

**Files:**
- Modify: `pcs-backend/pyproject.toml`（+`xlrd>=2.0`）
- Create: `pcs-backend/scripts/p6_6_extract_worley.py`（24 XLS → `.superpowers/sdd/2026-09-27-p6-6a-worley/worley_dump/*.json`，gitignored 工作区）
- Create: `pcs-backend/tests/services/test_worley_extract.py`（提取工具单测：尾随空格容错 + 非空 sheet 数 + 数字单元格提取）

**Steps:**
- [ ] `uv add xlrd`；工具读 24 XLS 全 sheet → JSON（cell 坐标 + 原始值 + 公式结果值）
- [ ] 跑全量 dump；统计：每 XLS sheet 数 / 数字 cell 数 / 空 XLS（若有）
- [ ] **Nielsen 核实**：读 `WS-CA-PR-020.xls` dump，grep 甲醇浓度；>25 wt% 工况存在 → 登记"补 Nielsen"为本批 Task N+1；不存在 → ledger 记"不补"
- [ ] Commit: `feat(p6-6a): xlrd 依赖 + Worley 24 XLS 提取工具 + Nielsen 工况核实`

## Task 1~13: 逐模块对账（P6-4/P6-5 新落地 13 项，最高优先）

每 task 同构（以 Task 1 = C-03/WS-CA-PR-003 为模板）：

**Files:**
- Create: `pcs-backend/tests/services/<mod>/fixtures/worley_c03_erosion.json`（XLS 真实输入/输出 + 单位换算链 + 容差字段）
- Create: `pcs-backend/tests/services/<mod>/test_worley_c03.py`（fixture 参数化 → 调 service → 三级容差断言）

**Steps（每 task）：**
- [ ] 读该 XLS dump → 人工定位输入区/输出区 → 转录 fixture（含 case 描述 + Worley 原始单位）
- [ ] 写对账测试（容差按该算法 SPEC §5 分级，注明级别 + 放宽理由若有）
- [ ] 跑测试：全过 → task 完成；失败 → 按 4 类处置（代码 bug → 独立 fix commit + root-cause / 变体 → ledger 登记 + fixture 标 variant / 舍入 → 放宽登记 / XLS 数据错 → 登记）
- [ ] Commit: `test(p6-6a): C-XX vs WS-CA-PR-NNN 真实算例对账（N case）`

**13 项映射（XLS 有算例的 P6-4/P6-5 项）：**

| Task | C-XX | XLS | service 模块 | SPEC §5 级别 |
|---|---|---|---|---|
| 1 | C-03 | 003 | pipe/two_phase_erosion | 经验 1% |
| 2 | C-05 | 005 | pipe/two_phase_sizing | 经验 1% |
| 3 | C-06 | 006 | common_service.calculate_gas_heating_value | 强公式 0.1% |
| 4 | C-09 | 007 | cv/（AS 2360 d<1in） | 经验 1% |
| 5 | C-10 | 011 | vessel/three_phase_separator | 经验 1% |
| 6 | C-13 | 014 | pipe_net/surge_pressure | 强公式 0.1% |
| 7 | C-15 | 016 | pipe/holdup_correlation | 图版 5% |
| 8 | C-16 | 018 | psychro/glycol_dehydration | 经验 1% |
| 9 | C-17 | 019 | psychro/saturation_water_content | 强公式 0.1% |
| 10 | C-18 | 020 | psychro/hydrate_inhibition | 经验 1% |
| 11 | C-19 | 023 | restriction/drain_orifice | 强公式 0.1% |
| 12 | C-20 | 024 | psv/（API 2000 breathing） | 经验 1% |
| 13 | C-21 | 025 | psv/（AS 1210 fire/rupture） | 经验 1% |

（C-22/026 + C-23/027 FLARE、C-24/028 CV fl——P6-5 已落，XLS 有算例则并入 Task 14 补充组）

## Task 14: 补充组 + 收口

- [ ] C-22（026 dispersion）/ C-23（027 noise）/ C-24（028 masonelian fl）同构对账（图版 5% / 经验 1%）
- [ ] 若 Task 0 判定补 Nielsen：`psychro/hydrate_inhibition_service` + Nielsen 方程（甲醇 ≤50 wt%）+ 测试 + 对 020 高浓 case
- [ ] 对账总报告 `.superpowers/sdd/.../reconciliation-report.md`（24 XLS × 通过/变体/失败矩阵 + 处置记录）
- [ ] CHANGELOG P6-6A 段 + SPEC V1.10 无需改（对账不改变规格；发现的规格偏差登记 SPEC 修订项）
- [ ] 批 B 立项文档（数据源替换：9 CONFIG 表 + 4 内联常量 + API 520 Fig.30 Kb + 文献精录清单）

## 验收

```bash
cd pcs-backend && uv run pytest tests/services/ -q          # 全绿（含新 worley_*.py）
uv run ruff check .                                          # 0 errors
# 对账矩阵：24 XLS 全覆盖（通过 / 变体登记 / 失败修复 三态，无"未对账"）
```

## 未解决问题

1. XLS 嵌入图表中的值无法机器提取——遇到即人工转录（Task 内处置）
2. C-08（010）两相分离器 sizing 属 P6-4 重写项、XLS 有算例——**未列入 13 项**（属 VESSEL 老模块对账，如需并入 Task 14 顺带）
3. 批 B 的文献精录依赖我在知识库中的 GPSA/API 公开值准确度——用户抽检机制在批 B 计划中定义
