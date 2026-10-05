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

- ❌ 异步事件队列（当前同步 `emit_event` 够用；D8 裁决 9A 说"异步队列仅高峰需求"）
- ❌ 事件重放（replay）—— 与反向恢复是两回事，除非业务提出审计重放需求

---

## 关联

- `docs/superpowers/plans/2026-10-01-p7-complete-sprint.md` — D4 裁决 4A / Task S4-3
- `pcs-backend/app/services/cia_engine.py` — CIA 引擎（无反向能力）
- `pcs-backend/app/models/enums.py:273-276` — CIA 事件枚举
- `pcs-backend/app/models/calc.py:317-320` — CIA 写字段
