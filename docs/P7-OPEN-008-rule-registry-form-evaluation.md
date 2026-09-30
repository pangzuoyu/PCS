# P7-OPEN-008 — 规则清单形态评估报告

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**评估日期**: 2026-10-01
**评估方**: 架构委员会（mock 评估，待真实会议确认）
**触发**: PCS 本体论 V1.6 §3.5「P7 启动前必备评估」
**关联**: P7 SPEC V1.3 §4.5 P7-OPEN-008 + P7-REV-04

## 1. 评估方法学（per V1.6 §3.5）

### 1.1 决策规则

| 规则数量 | 决策出口 |
|---|---|
| **>20 条** | 方案 A：CI 自动生成（`inspect/ast` 扫描 `@rule` 装饰器自动生成清单）|
| **≤20 条** | 方案 B：ADR 附录（规则记录在相关 ADR 中，不单独维护文件）|

### 1.2 历史背景

P4–P6 期间：
- 不建立手动维护的规则清单（避免文档漂移）
- PR/ADR 模板中加一行「本次新增/修改的业务规则」（审计线索，非清单本体）
- `RuleCollector` 接口骨架应在 P4 Task 0-Design 预留（`app/core/rules_registry.py`），P7 前不填充实现

## 2. 数据采集（source-verify）

### 2.1 期望项

- `grep -rn "@rule" pcs-backend/app/` 计数（应 ≥0）
- `app/core/rules_registry.py` 是否存在（per V1.6 §3.5「P4 Task 0-Design 已预留」）

### 2.2 实际数据状态（2026-10-01 探测）

| 项 | 期望 | 实际 |
|---|---|---|
| `@rule` 装饰器 in `pcs-backend/app/` | ≥0（统计用）| **0 个**（`grep -rn "@rule\|@rules" pcs-backend/app/ \| wc -l = 0`）|
| `app/core/rules_registry.py` | 存在（接口骨架）| **不存在**（`find pcs-backend -name "rules_registry*"` = 0 matches）|
| `app/core/` 当前文件清单 | 7 文件 + rules_registry.py | **7 文件**：`acl.py` / `commit_or_rollback.py` / `config.py` / `errors.py` / `logging.py` / `security.py` / `upload_size_limit.py`（**rules_registry.py 缺失**）|

### 2.3 PR/ADR 模板「本次新增/修改的业务规则」审计线索

按 V1.6 §3.5 决策规则，P4–P6 期间 PR/ADR 模板已加此行（per .wolf/memory.md P6-9-PICKUP-5 5B 工艺债务批追溯）。

**审计线索样本（粗估）**：
- P5-0 5 commits + P5-123 5 commits + P6-6B 16 commits + P6-7 10 commits + P6-8+P6-9 11 commits = **47 commits**
- 每 commit 至少 1 行「业务规则变更」（按 PR 模板要求）→ 估 **47-94 条审计线索**

## 3. R=1 教训登记（per .wolf/cerebrum.md）

### 3.1 Brief 缺陷

V1.6 §3.5 明确：
> 「方案 A 技术预留: P4 Task 0-Design 预留 RuleCollector 接口骨架（`app/core/rules_registry.py`），P4–P6 开发者只需按约定使用 `@rule` 装饰器，P7 的 CI 自动生成即可直接消费。**P7 前不填充实现，仅预留接口形态。**」

但实际：
- `app/core/rules_registry.py` **不存在**（应至少含接口骨架）
- `@rule` 装饰器使用 = **0**（按约定使用未发生）

**两层 brief 缺陷**：
1. **接口骨架未预留**（P4 Task 0-Design 应建但未建）
2. **P4–P6 开发者未使用 `@rule` 装饰器**（约定未落地）

### 3.2 验证动作

本次评估严格执行 source-verify：
1. `find pcs-backend -name "rules_registry*"` → 0 matches
2. `grep -rn "@rule" pcs-backend/app/` → 0 matches
3. `ls app/core/` → 7 文件（无 rules_registry.py）

## 4. 决策建议

### 4.1 规则计数 = 0 → 方案 B 明确

**实际规则数 = 0**（无 `@rule` 装饰器使用），远 ≤ 20。

**mock 决策**: **方案 B（ADR 附录）**

### 4.2 方案 B 落地要求

- ❌ **不**建立 `app/core/rules_registry.py`（保持 ontology V1.6 §6 规则 10 「P7 前不手动维护规则清单」的现状）
- ❌ **不**为 `@rule` 装饰器新增 CI 自动生成（数量不足，工具链成本不划算）
- ✅ **规则记录在相关 ADR 附录**（P4+ 各模块 ADR 已含业务规则段，扩展为附录即可）
- ✅ **PR/ADR 模板「本次新增/修改的业务规则」审计线索保留**（V1.6 §3.5 已要求）

### 4.3 未来触发条件（重新评估）

| 触发条件 | 行动 |
|---|---|
| 规则数 > 20 条 | 重新评估 → 启用方案 A；先建 `app/core/rules_registry.py` 接口骨架 + 培训 P4–P6 开发者使用 `@rule` 装饰器 |
| 新模块 / 跨模块规则需求出现 | 重新评估 |
| 工艺室 / 法规要求显式规则清单 | 重新评估 |

## 5. 两方案对比

| 维度 | 方案 A（CI 自动生成）| 方案 B（ADR 附录）|
|---|---|---|
| 工具成本 | 高（`app/core/rules_registry.py` + `@rule` 装饰器 + CI 生成器）| 低（零工具增量）|
| 维护成本 | 低（CI 自动）| 中（人工维护 ADR 附录）|
| 精度 | 高（无遗漏）| 中（依赖 ADR 作者纪律）|
| 召回 | 高 | 中 |
| 当前适配性 | ❌（规则数 = 0，工具投资不划算）| ✅（规则数 = 0，最简方案）|
| 未来可扩展性 | 高（规则数增长后可平滑升级）| 低（需重新评估 + 切换工具）|

## 6. mock 裁决（待架构委员会确认）

**mock 决策**: **方案 B（ADR 附录）**

**架构委员会需确认事项**：
1. ✅ 接受「规则数 = 0 → 方案 B」
2. ✅ 不建立 `app/core/rules_registry.py` 接口骨架（避免无意义工具投资）
3. ✅ 不引入 `@rule` 装饰器使用约定（保持当前编码自由）
4. ✅ ADR 附录扩展是否需要单独 ADR 编号（建议：复用现有 ADR 系列，无需新编号）

## 7. 关联教训

### 7.1 与本体论 V1.6 §3.5 不一致点

V1.6 §3.5 描述「P4 Task 0-Design 预留 RuleCollector 接口骨架」与实际代码不符：
- **根因 1**: P4 Task 0-Design 在落地时跳过了「预留接口骨架」步骤（**plan 缺陷**）
- **根因 2**: 即使预留，开发者未被要求使用 `@rule` 装饰器（**约定未传达**）

**建议**: P7 SPEC V1.4 §4.5 P7-OPEN-008 状态描述需修正：
- 删除「RuleCollector 接口已在 P4 Task 0-Design 预留」
- 改为「P4–P6 期间未预留 RuleCollector 接口骨架，@rule 装饰器使用 = 0；P7 评估后采纳方案 B（ADR 附录），不建立独立规则清单」

### 7.2 .wolf/cerebrum.md 新守则候选

**候选守则 1**: 「P4 Task 0-Design 范围声明须 source-verify — plan 中声明的接口骨架/装饰器约定，落地 commit 必须存在对应文件或 grep 计数 ≥ 1」

**候选守则 2**: 「P7 评估报告须先做数据采集再下结论 — 无样本（=0）时不可套用三元决策的「三者均 < 50% → 默认不启用」分支」

## 8. 风险 + 缓解

| 风险 | 等级 | 缓解 |
|---|---|---|
| 方案 B 长期维护 ADR 纪律下降 | 中 | V1.6 §3.5 决策规则不变；连续 6 个月规则数 > 20 触发重评 |
| P4–P6 开发者不知道有方案 B 决策 | 低 | V1.4 §4.5 P7-OPEN-008 状态变更后纳入 onboarding |
| 法规要求强制规则清单（未来）| 低 | 触发重新评估 → 启用方案 A |

## 9. 验收

- [ ] 架构委员会 mock 评估接受（本报告提交）
- [ ] P7 SPEC V1.4 §4.5 P7-OPEN-008 状态更新为「方案 B（ADR 附录）已采纳；不建立 rules_registry.py」
- [ ] V1.6 §3.5「P4 Task 0-Design 已预留」描述修订（建议 V1.7 加「本节声明与 P4 实际落地不一致，详见 P7-OPEN-008 评估报告」脚注）
- [ ] .wolf/cerebrum.md 加守则候选 2（无样本不可套用默认决策分支）

## 10. 关联

- 上游：`spec/PCS 本体论与语义关系研究说明（V1.6）.md` §3.5
- 下游：P7 SPEC V1.4 §4.7 P7-REV-04
- 教训：.wolf/cerebrum.md「Do-Not-Repeat：implementer 必须先 source-verify brief 中描述的代码状态」
- 兄弟报告：`docs/P7-OPEN-007-physical-semantics-evaluation.md`（同期 source-verify 模式）
