# CIA 反向恢复推迟到 P8 — 落地路径 (2026-10-05)

**状态**: 🔜 **推迟到 P8** — P7 Sprint 4 只做 rollback 三阶段的前两阶段
**裁决人**: 用户（2026-10-05）
**关联**: `docs/superpowers/plans/2026-10-01-p7-complete-sprint.md` D4 裁决 4A

---

## 一句话结论

用户裁决：**CIA 反向恢复推到 P8 落地；P8 启动时按 D4 4A 事件模式扩展。**

P7 Sprint 4 的 Task S4-3（核算与更新流程）实现 rollback 三阶段中的
**① 事件撤回 + ② 门禁回滚**，**③ CIA 反向恢复留到 P8**。

---

## D4 裁决 4A 原文（三阶段 rollback）

> 状态机统一所有门禁迁移；业务模块（Supplier / UtilResults / EquipmentList）通过
> `emit_event()` 发事件，不直接触发门禁迁移；事件需幂等性（event_id 去重）；
> rollback 分阶段（**事件撤回 / 门禁回滚 / CIA 反向恢复**）

S4-3 Step 5 原文：
> CIA 触发（实际值导致设计值被替换 → CHANGED 流程）— D4 裁决 4A: Supplier 调
> `emit_event('actual_data_replaces_design', equipment_id, diff, event_id=uuid4())`；
> **不直接调 state_machine**；state_machine listener 走 EquipmentList.CHANGED +
> UtilResults.recalculate（不进门禁）+ CIA.evaluate

---

## ⚠️ 落地前的两个前置事实核查（2026-10-05 source-verify）

按 `.wolf/cerebrum.md` 的 R=1 教训（implementer 必须先 source-verify brief 描述的
代码状态），核查后发现 **D4 4A 引用的机制有一半还不存在**：

| D4 4A 假定 | 实际 | 影响 |
|---|---|---|
| `emit_event()` | ❌ **不存在** —— `grep -rn "def emit_event" app/` 零命中 | S4-3 Step 4/5 要新建 |
| listener / subscribe 机制 | ❌ **不存在** —— `app/core/` 下无 event 基础设施 | 同上 |
| `CIAEngine` | ✅ 存在（`app/services/cia_engine.py`，456 行） | — |
| `CIAEngine.propagate()` / `propagate_to_equipment()` | ✅ 存在（`mark_stale_then_propagate` 封装） | — |
| CIA 事件枚举 | ✅ `CIA_SCAN_STARTED` / `CIA_SCAN_COMPLETED` / `CIA_NOTIFIED` / `CIA_NO_IMPACT`（`app/models/enums.py:273-276`） | — |
| CIA 写字段 | ✅ `record_hash` / `changed_fields`（`app/models/calc.py:317-320`，注释「CIA 引擎写；业务模块禁直写」） | — |
| **CIA 反向恢复基础** | ❌ **完全没有** —— `grep "snapshot|reverse|rollback|prev_\|old_value" cia_engine.py` 零命中 | **P8 的真正工作量** |

**结论**：CIA 反向恢复推迟的代价不大 —— 它连基础都没有，推迟反而避免在 P7 仓促
造一套半成品。但 **P7 的 S4-3 仍需先建 `emit_event()` + listener 骨架**，
否则 D4 4A 的「不直接调 state_machine」根本无从遵守（现在只有 `state_machine`
可调，绕不开）。

---

## 影响范围：emit_event() 不存在不只是 S4-3 的前置（2026-10-05 复审补充）

原文档只说影响 S4-3，**低估了**。实际核查后，D4 4A 未落地的真实影响面：

| 受影响项 | 实际状态 | 影响 |
|---|---|---|
| **D4 4A 全部落地** | `emit_event()` / listener 均不存在 | 「单一权威 + 事件解耦」架构原则**整体未落地** |
| **`CIAEngine` 3 处直调** | `cia_engine.py:133,187,254` 直接 `await self.fsm.transition(...)` | ⚠️ **这正是 D4 4A 要禁止的模式本身** —— 事件源与状态机耦合 |
| `records.py` / `stream_service.py` / `meta_service.py` | 直接 import `StateMachineService` | API/service 层直调，非事件驱动 |
| **未来所有跨模块变更** | 无事件骨架 | 一律直调 state_machine，无解耦点 |
| Sprint 4 S4-3 Step 4/5 | 需新建 `emit_event()` + listener | — |

**⚠️ 一条 review 前提被 source-verify 推翻**：review 认为
「`sync_from_source` 若 D4 4A 未落则仍是直调 state_machine」——
**不成立**。`app/services/equip_list/sync_service.py` 全文件
`grep "state_machine|transition|resolve_stale"` **零命中**，
它只走 D2 2A advisory lock + `source_resolver` + `type_code_map`，
**与状态机完全无关**。D2 2A 与 D4 4A 确实是两条线，但 sync 那条线不经过状态机。

**结论**：`emit_event()` 缺失是 **D4 4A 全部落地的前置**，不是 S4-3 的局部前置。
建议在 Sprint 4 计划里登记为 **Task 0**（见文末「对 Sprint 4 计划的建议」）。

---

## before 快照的结构（source-verify 2026-10-05）

review 要求确认 `design_parameters_json` 是 JSONB 整体还是独立列。已核实：

```
pcs-backend/app/models/equipment.py:87
    design_parameters_json: Mapped[dict | None] = mapped_column(JSONB)
```

**是 JSONB 整体**（`EquipmentList` 表）。故 `before` 快照为一行代码：

```python
before = dict(existing.design_parameters_json or {})   # 浅拷贝够用
```

边际成本确实**近零**，review 的判断成立。

⚠️ 但**浅拷贝只对顶层成立** —— 若 JSONB 内部有嵌套 dict/list 且后续有人原地
修改内部对象，浅拷贝会串。安全写法是 `copy.deepcopy()`，或明确只读不改。
建议 P8 落地时统一走 `deepcopy` 并在 docstring 注明快照**只读**。

---

## 幂等键 event_id 的存储位置（review 补充 3）

P8 验收判据第 2 条「同一 event_id 重复投递 → 影响行数为 0」依赖去重机制，
但**原文档未明确存哪里**。三个选项：

| 选项 | 优点 | 缺点 | 评估 |
|---|---|---|---|
| a. `audit_logs.detail_json.event_id` + 索引 | 复用现有表；`p7_s1_002` 已建 JSONB GIN 索引 | 需表达式索引才能按 event_id 查；audit_logs 是**只增不改**的审计流，拿来做去重闸语义不纯 | 🟡 |
| b. 独立 `event_idempotency` 表 | 语义清晰；`event_id` UNIQUE 约束天然去重；可存处理状态 | 新表 + migration | 🟢 **推荐** |
| c. Redis / 内存 | 快 | 重启丢失 → 幂等保证随重启消失 | ❌ |

**推荐 b**，理由：去重是**业务正确性**要求（不能因重启而失效），而 `audit_logs`
是审计流水（只增不改、可能按保留期清理）。把幂等闸建在可能被清理的表上是隐患。

```sql
CREATE TABLE event_idempotency (
    event_id      UUID PRIMARY KEY,          -- 反向事件复用原 id → 天然幂等
    event_type    VARCHAR(64) NOT NULL,
    payload_hash  VARCHAR(64) NOT NULL,      -- 同 id 不同 payload 视为冲突, 报错
    processed_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

⚠️ **`payload_hash` 不可省**：同一个 `event_id` 携带不同 payload 是上游 bug，
静默按先到者处理会掩盖问题。应显式报「event_id 冲突」。

---

## before 快照的存储位置与访问权限（review 风险项）

**风险**：`before` 含设计值（如 `motor_power_kw`），若落进低权限可查的表 → 设计值泄露。

**audit 权限现状（2026-10-05 source-verify `app/api/v1/audit.py`）**：

| 端点 | 权限 | 行号 |
|---|---|---|
| `/audit-logs` | **SYSTEM_ADMIN only** | :58 |
| `/equipment-deletion-audit` | DESIGNER+ | :118 |
| `/config-audit` | DESIGNER+ | :202 |

**结论**：
- `before` 写入 `audit_logs.detail_json` → SYSTEM_ADMIN 才可查 → **无泄露** ✅
- 但 `audit_logs` 有保留期/清理策略（见「不在 P8 范围」外的 D8 裁决 monthly
  partition，保留 6 月）—— 快照被清理后**无法再做反向恢复**。
- 因此 `before` **不能只存在 audit_logs**，至少要有一份落在
  `event_idempotency`（推荐方案的表）里，与幂等记录同生命周期。

→ **P8 落地路径第 1 步修正为**：`before` 快照存 `event_idempotency.payload`
（或同表的 `before_json` 列），`audit_logs.detail_json` 只记 `event_id` 引用
与摘要，**不重复存设计值全文**。

---

## source-verify 结论：D8 裁决无独立文档

review 要求验证「D8 裁决 9A」是否真实存在。已核实：

- `grep -rn "D8 裁决|裁决 9A" docs/ .wolf/` → **仅命中 plan 自身 + 本文档**，
  `docs/adr/` 下**无 D8 裁决文档**
- 但其引用的工作是**真实落地**的：`alembic/versions/p7_s1_002_audit_logs_jsonb_gin.py` 存在

**判定**：引用**不算伪造**（plan 内部措辞一致，且引用的 migration 真实存在），
但**出处不可追溯** —— 属文档债。本文档的引用已改为标注「D8 裁决（plan 内部引用，
无独立 ADR）」。

---

## 对 Sprint 4 计划的建议

把 `emit_event()` + listener 骨架登记为 **Sprint 4 Task 0**（而非塞进 S4-3）：

| Task | 内容 | 理由 |
|---|---|---|
| **S4-0** | `emit_event()` + listener 注册/派发 + `event_idempotency` 表 + 单测 | 是 D4 4A 全部落地的前置；S4-3 依赖它；独立出来可先验证「CIAEngine 3 处直调」的解耦路径 |

S4-0 落地后，S4-3 Step 4/5 才可能真正遵守 D4 4A 的「不直接调 state_machine」。

---

## P8 落地路径

P8 启动时按 D4 4A 事件模式扩展，具体三步：

### 1. 事件可逆化 —— payload 携带前值快照

`actual_data_replaces_design` 当前只传 `diff`。**没有前值就无法反向恢复。**

```python
# P7 (S4-3) 建的最小形态 —— 补前值快照是 P8 第 1 步
emit_event(
    "actual_data_replaces_design",
    equipment_id=equipment_id,
    event_id=uuid4(),                    # 幂等去重键 (D4 4A 要求)
    before={"motor_power_kw": 100.0, "annual_consumption_kwh": 800000.0},
    after={"motor_power_kw": 112.0, "annual_consumption_kwh": 896000.0},
)
```

> `before` 字段若在 P7 就带上，P8 可省一大步。**建议 S4-3 Step 4 直接加上** ——
> 边际成本近零（dict 多一个 key），却让 P8 的第 1 步变成"读已有数据"而非"补历史数据"
> （后者做不到 —— 设计值一旦被覆盖，旧值就永久丢失）。

### 2. 反向事件 + 幂等补偿

```python
# P8 新增
emit_event(
    "design_restores_actual",             # 方向相反的事件
    equipment_id=equipment_id,
    event_id=original_event_id,          # 复用原事件 id → 天然幂等
    restored=original_event.before,
)
```

CIA listener 需支持**补偿语义**：见到反向事件时，把 `propagate()` 已经写下的
STALE 标记与 `changed_fields` 按 `before` 还原，而非再次向前传播。

### 3. 三阶段 rollback 补齐第三阶段

| 阶段 | P7 (S4-3) | P8 |
|---|---|---|
| ① 事件撤回 | ✅ 撤回 `actual_data_replaces_design` | — |
| ② 门禁回滚 | ✅ EquipmentList.sign_status 回退 | — |
| ③ CIA 反向恢复 | 🔜 | ✅ 按 `before` 还原 `record_hash` / `changed_fields` / STALE 传播结果 |

---

## P8 启动时的验收判据（建议）

1. `design_restores_actual` 走一遍后，CIA 的 `propagate()` 结果与
   `actual_data_replaces_design` 之前**逐字段一致**（用 `_content_hash` 对比）
2. 同一 `event_id` 重复投递 → 影响行数为 0（幂等，D4 4A 要求）
3. `before` 缺失的历史事件（2026-10 之前）→ 明确报"不可逆"，**不静默跳过**
   （宁可报错也不假装回滚成功）

---

## 不在 P8 范围

- ❌ 异步事件队列（当前同步 `emit_event` 够用；plan 内部「D8 裁决 9A」说
  "异步队列仅高峰需求" —— ⚠️ 该裁决**无独立 ADR 文档**，仅 plan 内部引用，
  详见下方「source-verify 结论：D8 裁决无独立文档」）
- ❌ 事件重放（replay）—— 与反向恢复是两回事，除非业务提出审计重放需求

---

## 关联

- `docs/superpowers/plans/2026-10-01-p7-complete-sprint.md` — D4 裁决 4A / Task S4-3
- `pcs-backend/app/services/cia_engine.py` — CIA 引擎（无反向能力）
- `pcs-backend/app/models/enums.py:273-276` — CIA 事件枚举
- `pcs-backend/app/models/calc.py:317-320` — CIA 写字段
