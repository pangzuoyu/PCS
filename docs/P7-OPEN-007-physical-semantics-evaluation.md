# P7-OPEN-007 — physical_semantics 三元决策评估报告

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**评估日期**: 2026-10-01
**评估方**: 架构委员会（mock 评估，待真实会议确认）
**触发**: PCS 本体论 V1.6 §3.2b「P7 启动前必备评估」
**关联**: P7 SPEC V1.3 §4.5 P7-OPEN-007 + P7-REV-03

## 1. 评估方法学（per V1.6 §3.2b）

### 1.1 度量指标定义（成因编号 A/B/C）

| 编号 | 成因 | physical_semantics 能否缓解 |
|---|---|---|
| A | 元数据字段干扰（record_hash 覆盖备注/说明 → 假阳性，hash 粒度过粗） | ❌ 不能 |
| B | 下游不消费该字段（血缘边语义过宽 → 假阳性） | ✅ 能（语义谓词过滤）|
| C | dependency_type 分类过粗（REFERENCE 边当 CALCULATION 处理） | ❌ 不能（需修 dependency_type 本身） |

### 1.2 决策规则（三元出口）

| 主导成因 | 决策出口 |
|---|---|
| 成因 B > 50% | ✅ 启用 physical_semantics 语义过滤 |
| 成因 A 主导 | 🔧 修正 record_hash 范围（不动 physical_semantics）|
| 成因 C 主导 | 🔧 审计并修正 dependency_type 分类（不动 physical_semantics）|
| 三者均 < 50% | ⏸️ 默认不启用，连续 6 个月超阈值则重新评估 |

**阈值**: >50% 为**默认建议值，非硬约束**。架构委员会可基于实测数据调整。

## 2. 数据采集（source-verify）

### 2.1 期望数据源

- `audit_logs.detail_json` 中的 `stale_resolution_path` / `hash_changed` / `changed_fields` 三字段（per V1.6 §3.2b）
- 由 `StateMachineService` 在 STALE 解除时强制写入

### 2.2 实际数据状态（2026-10-01 探测）

| 项 | 期望 | 实际 |
|---|---|---|
| `audit_logs` 表行数 | ≥30（决策有效样本下限）| **0 行**（pcs_test DB 真空）|
| `audit_logs.detail_json ? 'stale_resolution_path'` | ≥30 | **0 行** |
| `audit_logs.detail_json ? 'hash_changed'` | ≥30 | **0 行** |
| `audit_logs.detail_json ? 'changed_fields'` | ≥30 | **0 行** |
| `state_machine.py` 写入 `stale_resolution_path` | ≥1 | **0 matches**（grep `app/services/state_machine.py`）|
| `state_machine.py` 写入 `hash_changed` | ≥1 | **0 matches** |
| `state_machine.py` 写入 `changed_fields` | ≥1 | **0 matches** |

### 2.3 ORM 列定义（source-verify）

虽 ontology V1.6 §3.2b 标注 `hash_changed` 「当前未强制记录」+ `changed_fields`「未覆盖」，但实际列已在 RecordMixin 中预留：

| ORM 模型 | 行号 | 字段 |
|---|---|---|
| `app/models/calc.py` | 310 | `stale_resolution_path: Mapped[str \| None]` |
| `app/models/calc.py` | 313 | `hash_changed: Mapped[bool \| None]` |
| `app/models/calc.py` | 319 | `changed_fields: Mapped[dict \| None]`（JSONB）|
| `app/models/mixins.py` | 105/108/113 | 同上 3 字段（RecordMixin）|
| `app/models/project.py` | 443/446/451 | 同上 3 字段 |

**结论**: ORM 层列定义完整；但 **StateMachineService 未触发写入**（V1.6 §3.2b「强制写入」未实际落地）。

## 3. R=1 教训登记（per .wolf/cerebrum.md）

### 3.1 Brief 缺陷

V1.6 §3.2b 描述「P4 Task 0-Code 强制 StateMachineService 写入」，但实际：
- 列已加（calc_lineage.py:132 / mixins.py:105-113 注释提及）
- **写入路径未实现**（state_machine.py 0 matches）

### 3.2 验证动作

本次评估严格执行 source-verify：
1. `grep -rn "stale_resolution_path\|hash_changed\|changed_fields" pcs-backend/app/services/state_machine.py` → 0 matches
2. `psql -c "SELECT count(*) FROM audit_logs"` → 0
3. ORM 列存在 ≠ 业务写入触发（本次发现的核心 R=1 lesson）

## 4. 决策建议

### 4.1 当前样本不足 → 推迟决策

**数据样本 = 0**，无法计算 A/B/C 占比。直接套用「三者均 < 50% → 默认不启用」会基于「无证据」，而非「真证据」。

**建议**: 推迟三元决策出口，登记为「数据待补采」。

### 4.2 触发条件（建议）

**P7 Sprint 1 部署后 30 天采集 ≥30 条 STALE 解除审计样本**：

| 触发条件 | 状态 |
|---|---|
| pcs_test DB 预填测试数据 ≥30 行 STALE 解除审计 | 待 P7 Sprint 1 落地 |
| `StateMachineService` 落地三字段强制写入 | **P7 Sprint 0 前置 — 必须落地**（否则 P7 Sprint 1 部署后仍无数据）|
| 30 天后重新跑此评估脚本 | 待触发 |

### 4.3 前置落地项（必须 P7 Sprint 0 内完成）

**T0（架构组执行前必办）**：`StateMachineService` 强制写入 3 字段：

```python
# 伪代码 — 待 implementer source-verify state_machine.py 实际写入点
def resolve_stale(record, ...):
    audit_detail = {
        "stale_resolution_path": "RESOLVE_NO_CHANGE",  # or "RESOLVE_CHANGED"
        "hash_changed": new_hash != old_hash,
        "changed_fields": list(diff.keys()),
    }
    audit_service.write(
        action="STALE_RESOLVED",
        resource_type=record.__tablename__,
        resource_id=record.id,
        detail_json=audit_detail,
    )
```

**T1（数据预填）**：在 pcs_test DB 写入 ≥30 行 STALE 解除审计 fixture（已知 A/B/C 分布）。

### 4.4 并列评估：字段级血缘（per V1.6 §3.2b(5)）

字段级血缘是模块级语义的替代方案：
- 不需要本体词汇表
- 直接命中「下游不消费该字段」的假阳性
- 数据工程成熟方案，成本可控

**建议**: 即使未来启用 physical_semantics，字段级血缘应作为补充方案并列考虑。

## 5. 三方案成本-收益-精度-召回分析（per V1.6 §3.2b(4)）

| 方案 | 说明 | 成本 | 精度 | 召回 | 建议 |
|---|---|---|---|---|---|
| A 自动推断 | 基于 source_type → target_type 映射表自动打标签 | 低 | 中（与模块级语义同样粗）| 中（字段级假阳可能把真实传播滤掉）| 主推 |
| B 人工标注 | 开发标注工具/API 手动补标签 | 高 | 高 | 高 | 不主推（人工成本不可持续）|
| C 放弃 | physical_semantics 列保持空置 | 零 | n/a | n/a | 当前默认 |

## 6. 风险 + 缓解

| 风险 | 等级 | 缓解 |
|---|---|---|
| T0 落地后仍无真实 STALE 解除事件（生产环境未触发）| 中 | 同步登记「pcs_test 模拟触发」路径，30 天评估窗口前预生成样本 |
| T1 数据预填 A/B/C 分布偏离真实 | 高 | 工艺工程师 2026-11-15 后对账（如 OPEN-P6-6A-10 AS 1210 PDF 同步） |
| 字段级血缘被推迟到 P7+ 评估 | 中 | P7-REV-03 决议附带「字段级血缘前置调研」建议（不主推，但保留接口）|

## 7. mock 裁决（待架构委员会确认）

**mock 决策**: 推迟三元决策 → 登记「数据待补采」→ 触发条件 T0+T1 落地后 30 天重评。

**架构委员会需确认事项**：
1. ✅ 接受「数据不足 → 推迟决策」vs「默认不启用」
2. ✅ T0 StateMachineService 强制写入是否纳入 P7 Sprint 0 任务（建议：是，否则 P7 Sprint 1 部署后仍无样本）
3. ✅ T1 pcs_test DB 预填 fixture 是否需要工艺室签署（建议：是，按 PROCo 标记）
4. ✅ 字段级血缘是否纳入 P7-REV-03 并列评估（建议：是）

## 8. 未解决问题

1. T0 落地工时估算（未在 P7 SPEC §4.6 计入；建议 +0.5-1 人日）
2. T1 pcs_test fixture 工艺室签署时间窗（与 P6-9-PICKUP-6 5D-2 时间窗 2026-11-15 重叠）
3. 三元决策推迟到 P7 Sprint 1 部署后 30 天，对 P7 SPEC V1.4 §4.5 状态字段影响（「待裁决」→「待补采」）

## 9. 验收

- [ ] 架构委员会 mock 评估接受（本报告提交）
- [ ] T0 StateMachineService 强制写入纳入 P7 Sprint 0 任务（决议待 P7-REV-03 落地）
- [ ] pcs_test fixture 工艺室签署 schedule 排定（待 OPEN-P6-6A-10 2026-11-15 后）
- [ ] P7 SPEC V1.4 §4.5 P7-OPEN-007 状态更新为「待补采 — 触发：pcs_test ≥30 行 + StateMachineService 写入」

## 10. 关联

- 上游：`spec/PCS 本体论与语义关系研究说明（V1.6）.md` §3.2b
- 下游：P7 SPEC V1.4 §4.7 P7-REV-03
- 教训：.wolf/cerebrum.md「Do-Not-Repeat：implementer 必须先 source-verify brief 中描述的代码状态」
- 关联 OPEN：OPEN-P6-6A-10（AS 1210 PDF 2026-11-15 交付 — 可能影响 STALE 触发频次）
