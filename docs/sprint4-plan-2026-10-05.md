# Sprint 4 计划：供应商数据闭环 + 事件骨架 + 真实算例验收 (2026-10-05)

> **状态**: 📋 待执行
> **总工时**: ~3–3.5 人周（5 个 Task）
> **上游**: `docs/superpowers/plans/2026-10-01-p7-complete-sprint.md`（P7 总计划，本文档为其 Sprint 4 部分的执行副本 + 2026-10-05 修订）
> **基线**: 后端 3728 passed / 0 failed · alembic head `p7_s3_005` · tag `t5-energy-summary-2026-10-05` → `37806ac`

---

## Context

T5 综合能耗已封版（`docs/PCS-SIGN-T5-2026-10-05.md`），P7-6B 收尾完成（6 张权威表）。
P7 剩余的唯一一段是 Sprint 4：**供应商侧的数据闭环** —— 实际值录入 → 自动比对 →
偏差报告 → 核算确认 → 触发下游更新。

启动前做的三项裁决改变了 Sprint 4 的形状：

| 裁决 | 影响 |
|---|---|
| `catalyst_loading` 取消不建 | UTIL 权威表 5 → **6 张**；BLOCKER-2 整体关闭；工艺室 2026-10-15 签署不再是任何在办项前置 |
| CIA 反向恢复推迟 P8 | S4-3 只做 rollback 三阶段的前两阶段 |
| S4-4 改写定义 | 不再用 XLS 作验收基准（该前提已被推翻） |

**关键前置发现**（2026-10-05 source-verify）：`emit_event()` 与 listener 机制
**在代码库中完全不存在**。D4 裁决 4A 通篇引用它们，读起来像既有设施，实际
`grep -rn "def emit_event" app/` 零命中。`CIAEngine` 三处直接
`await self.fsm.transition(...)` —— 正是 D4 4A 要禁止的模式本身。
→ 故新增 **Task S4-0** 作为 D4 4A 全部落地的前置。

---

## Task 清单

| Task | 内容 | 估时 | 依赖 |
|---|---|---|---|
| **S4-0** 🆕 | 事件骨架 `emit_event()` + listener + `event_idempotency` 表 + `cia_engine` 解耦 | ~0.5–1 人周 | — |
| S4-1 | 供应商实际数据录入（手动 + Excel 批量） | ~0.7 人周 | — |
| S4-2 | 自动比对 + 偏差报告（3 档 + PDF/Excel 导出） | ~0.7 人周 | S4-1 |
| S4-3 | 核算与更新流程（确认 + 校核 + UTIL 实际值 + CIA 触发） | ~0.6 人周 | S4-2, **S4-0** |
| S4-4 | 蜡油加氢真实数据端到端验收（6 表全链路） | ~0.3 人周 | — |

**建议顺序**: S4-0 → S4-1 → S4-2 → S4-3 → S4-4。
S4-0 先行是架构地基；S4-4 无外部依赖，可并行插入。

---

## Task S4-0: 事件骨架 emit_event() + listener + 幂等表

**为什么是独立 Task**: `emit_event()` 缺失是 **D4 4A 全部落地的前置**，
不是 S4-3 的局部前置。不先建骨架，S4-3 只能继续直调 state_machine，
D4 4A 形同虚设。

**Files**:
- Create: `pcs-backend/app/core/events.py`（emit + register_listener + 派发 + 幂等去重）
- Create: `pcs-backend/alembic/versions/p7_s4_001_event_idempotency.py`
- Modify: `pcs-backend/app/services/cia_engine.py`（3 处直调改事件触发）
- Test: `pcs-backend/tests/core/test_events.py`

**Interfaces**:
- Consumes: `app/services/state_machine.py::StateMachineService`（作为 listener 之一）
- Produces: `emit_event(type, event_id, before, after, **payload)` + `event_idempotency` 表

**设计要点**（详见 `docs/PCS-NOTE-CIA-反向恢复-推到P8-2026-10-05.md`）:

1. **幂等表用独立 `event_idempotency`**，不用 `audit_logs`。
   理由：去重是**业务正确性**要求，不能因重启失效；而 `audit_logs` 是只增不改的
   审计流且有保留期清理策略（D8 monthly partition 保留 6 月），
   把幂等闸建在可能被清理的表上是隐患。

   ```sql
   CREATE TABLE event_idempotency (
       event_id      UUID PRIMARY KEY,     -- 反向事件复用原 id → 天然幂等
       event_type    VARCHAR(64) NOT NULL,
       payload_hash  VARCHAR(64) NOT NULL, -- 同 id 不同 payload 视为冲突, 报错
       before_json   JSONB,                -- P8 反向恢复的快照来源
       processed_at  TIMESTAMPTZ NOT NULL DEFAULT now()
   );
   ```

2. **`payload_hash` 不可省**：同一 `event_id` 携带不同 payload 是上游 bug，
   静默按先到者处理会掩盖问题 → 显式报「event_id 冲突」。

3. **事件 payload 必带 `before` 快照**。设计值一旦被覆盖，旧值就**永久丢失**，
   P8 无法回溯。`design_parameters_json` 已核实是 JSONB 整体
   （`app/models/equipment.py:87`），快照成本近零。**用 `copy.deepcopy`**
   （浅拷贝在嵌套结构下会串），docstring 注明快照**只读**。

4. **`before` 不只存 audit_logs**。`/audit-logs` 是 SYSTEM_ADMIN only
   （`app/api/v1/audit.py:58`），写那里无泄露；但 audit_logs 有保留期，
   快照被清理后**无法再做反向恢复** → 至少落一份在 `event_idempotency`，
   `audit_logs.detail_json` 只记 `event_id` 引用与摘要，不重复存设计值全文。

**Steps**:
- [ ] Step 1: 写 failing test — 派发顺序 / 幂等（同 event_id 重投影响 0 行）/
      payload_hash 冲突报错 / before 快照保真（含 deepcopy 嵌套场景）
- [ ] Step 2: 跑 test 验证失败
- [ ] Step 3: 实现 `app/core/events.py`
- [ ] Step 4: migration `p7_s4_001_event_idempotency`
- [ ] Step 5: `cia_engine.py` 3 处直调改走 `emit_event`
      （listener 内仍调 state_machine —— **单一权威不变，只是触发路径事件化**）
- [ ] Step 6: pytest 全量 0 regression
- [ ] Step 7: commit `feat(p7-s4): 事件骨架 emit_event + 幂等表 (S4-0)`

---

## Task S4-1: 供应商实际数据录入（手动 + Excel 批量）

**Files**:
- Modify: `pcs-backend/app/models/equipment.py`（`EquipmentList.actual_data_json` JSONB 字段）
- Create: `pcs-backend/alembic/versions/p7_s4_002_actual_data_jsonb.py`
- Create: `pcs-backend/app/services/supplier/actual_data_service.py`
- Create: `pcs-backend/app/services/supplier/excel_import_service.py`
- Create: `pcs-backend/app/schemas/supplier.py`
- Create: `pcs-backend/app/api/v1/supplier.py`
- Test: `pcs-backend/tests/services/supplier/test_actual_data_service.py`
- Test: `pcs-backend/tests/services/supplier/fixtures/golden_actual_data.json`（≥10 算例）

**⚠️ 与原计划的偏差**（2026-10-05 source-verify）:

| 原计划写 | 实际 |
|---|---|
| `Modify: p7_open_009_008_actual_data_jsonb.py` | 该文件**不存在** → 实际是 Create |
| `Modify: equip_list.py（ActualData JSONB 字段）` | `EquipmentList` 只有 `actual_data_status` 状态字段，**没有 ActualData JSONB** → 实际是 Create |

故 S4-1 估时可能偏乐观。

**Steps**:
- [ ] Step 1: 写 failing test — 手动录入 + Excel 批量导入各 1 例
- [ ] Step 2: 跑 test 验证失败
- [ ] Step 3: 实现 `actual_data_service`（手动 + JSONB 校验）
- [ ] Step 4: 实现 `excel_import_service`（CONFIG 模板 + 字段映射）
- [ ] Step 5: 边界测试 — Excel 字段缺失抛 `ExcelImportError`；
      类型不匹配抛 `ActualDataValidationError`
- [ ] Step 6: pytest 全量 0 regression
- [ ] Step 7: commit `feat(p7-s4): 供应商实际数据录入 + Excel 批量导入 (S4-1)`

---

## Task S4-2: 自动比对 + 偏差报告

**Files**:
- Create: `pcs-backend/app/services/supplier/deviation_service.py`
- Create: `pcs-backend/app/api/v1/supplier.py`（`GET /equipment-list/{id}/deviation-report`）
- Test: `pcs-backend/tests/services/supplier/test_deviation_service.py`
- Test: `pcs-backend/tests/services/supplier/fixtures/golden_deviation_report.json`
  （≥5 算例，含合格/警告/不合格 3 档）

**Steps**:
- [ ] Step 1: 写 failing test — 3 档判定 + 颜色标识
- [ ] Step 2: 跑 test 验证失败
- [ ] Step 3: 实现 `deviation_service`（按 SPEC V1.4 §3.2.4（2）允许偏差表）
- [ ] Step 4: PDF/Excel 导出（reportlab + openpyxl）
- [ ] Step 5: 边界测试 — 不合格项必拒绝确认 + 通知供应商
- [ ] Step 6: pytest 全量 0 regression
- [ ] Step 7: commit `feat(p7-s4): 供应商偏差报告 3 档判定 (S4-2)`

---

## Task S4-3: 核算与更新流程

**Files**:
- Create: `pcs-backend/app/services/supplier/confirmation_service.py`
- Create: `pcs-backend/app/api/v1/supplier.py`
  （`POST /equipment-list/{id}/actual-data/confirm` + `/check`）

**Steps**:
- [ ] Step 1: 写 failing test — 不合格项禁止确认
- [ ] Step 2: 跑 test 验证失败
- [ ] Step 3: 实现 `confirmation_service`（设计人 + 校核人流程）
- [ ] Step 4: UTIL 实际值优先触发（Sprint 1 Task S1-5 boundary）——
      **改走 `emit_event`，不直接调 state_machine**（依赖 S4-0）
- [ ] Step 5: CIA 触发（实际值替换设计值 → CHANGED 流程）——
      `emit_event('actual_data_replaces_design', equipment_id, event_id=uuid4(),
      before={...}, after={...})`
      - ⚠️ payload **必带 `before`**（P8 反向恢复的前提）
      - ℹ️ **CIA 反向恢复不在本 Task 范围** —— 已裁决推迟 P8
- [ ] Step 6: pytest 全量 0 regression
- [ ] Step 7: commit `feat(p7-s4): 供应商核算 + UTIL 实际值更新 (S4-3)`

---

## Task S4-4: 蜡油加氢真实数据端到端验收（6 表全链路）

> 🔄 **2026-10-05 改写**。原定义「用蜡油加氢—综合能耗.xlsx 验收偏差 ≤2%」
> 的前提已被推翻（用户裁决「XLS 不作为最终依据」），三重问题：
> 1. 三个「XLS 参考值」在 XLS 全表**不存在**（旧代码输出反抄，自证循环）
> 2. XLS 自身 `能耗!G33` 因 `D32=#VALUE!` 算不出年总能耗
> 3. XLS 折标系数偏离国标：电 +23.8% / 循环水 +67% / 除氧水 +41.5%

**新定义**: T5 的**验收判据**已由 `docs/PCS-SIGN-T5-2026-10-05.md` 完成封版
（基准 = GB 30251-2024 附录A 表A.1 独立重算）。本 Task 不再重复算同一个数，
而是补上封版时**缺的那块证据**：

> 至今所有 T5 验证都基于**合成 fixture**（仅电/燃料气/蒸汽三类）。XLS 里存在的
> **氮气、净化压缩空气、低温余热从未走过 P7-6B 收尾新建的 2 张表**。
> 没有任何真实算例走过它们。

**关键区别**: 只从 XLS 取**消耗量作为输入**，不取其折标结果。

**Files**:
- Modify: `pcs-backend/scripts/p7_open_012_t5_r1_verification.py`
  （`_inject_case_4` 补 `UtilityGasMedia` / `UtilityLowTempHeat` seed；
  `_gb30251_reference()` 同步补对应类别）
- Modify: `pcs-backend/tests/services/util/test_utility_energy_summary.py`

**验收判据**（区别于旧定义的 ≤2%）:
1. 三项指标 vs GB 30251 附录A 独立重算仍 ≤ 2%
2. `iso_self_consistent_pct` 仍 = 0.0%
3. `scripts/p7_open_016_config_conformance_audit.py` 仍 exit 0
4. **新增**：扩类前后的 T5 数字差异必须在 `docs/PCS-SIGN-T5-2026-10-05.md`
   补一节「封版后扩类影响」—— 让「数字因补全采集类别而上升」可追溯，
   而不是悄悄变（此前那部分是**漏算**，不是 PCS 算错）

**Steps**:
- [ ] Step 1: 从 `sample/1216D132*.xlsx` 的 `能耗` sheet 提取氮气 / 净化空气 /
      低温余热的**年消耗量**（原始量，非折标值），标注溯源
- [ ] Step 2: 写 failing test — Case 4 扩展到 5 类介质 + 低温热
- [ ] Step 3: 跑 test 验证失败
- [ ] Step 4: `_inject_case_4` + `_gb30251_reference()` 同步补类别
- [ ] Step 5: 重跑 T5 验收脚本 + 审计脚本
- [ ] Step 6: pytest 全量 0 regression
- [ ] Step 7: 在 `PCS-SIGN-T5-2026-10-05.md` 补「封版后扩类影响」一节
- [ ] Step 8: commit `feat(p7-s4): 蜡油加氢真实数据端到端验收 (S4-4)`

**不做**: 不用 XLS 折标结果作基准 / 不等工艺室签署 / 不改已封版的判据 /
不碰 `auxiliary_consumption` 4 字段

---

## NOT in Scope

| 项 | 理由 |
|---|---|
| `catalyst_loading` 表 | 用户裁决 2026-10-05 取消不建 |
| CIA 反向恢复 | 裁决推迟 P8，S4-3 只做前两阶段 rollback |
| `auxiliary_consumption` 4 字段 | 归属未定；现有 6 张表已能聚合算出，建议不做 |
| 异步事件队列 | 当前同步 `emit_event` 够用 |
| 事件重放（replay） | 与反向恢复是两回事，除非提出审计重放需求 |
| 完整 Project CRUD | T5 封版时刻意留白 |

---

## 验证（全 Sprint）

```bash
cd pcs-backend
uv run pytest tests/ -q                          # 0 failed (基线 3728)
uv run python scripts/check_migration_idempotency.py
uv run alembic -c alembic.ini heads
uv run python scripts/p7_open_012_t5_r1_verification.py   # T5 仍 PASS
uv run python scripts/p7_open_016_config_conformance_audit.py  # exit 0
uv run ruff check app/ tests/                    # 零新增
# G-08 OpenAPI 契约门禁自动触发（pre-commit）
```

## 风险 + 缓解

| 风险 | 缓解 |
|---|---|
| `emit_event` 是新架构，S4-0 做歪会拖累 S4-1~3 | S4-0 独立成 Task + 独立 review |
| S4-1 估时偏乐观（字段要从零建，非 Modify） | 缓冲 +0.2 人周 |
| `before` 快照设计值泄露 | 存 `event_idempotency`（不进 DESIGNER 可查端点）+ audit_logs 只存引用 |
| S4-4 扩类后 T5 数字上升被误读为回归 | 验收判据第 4 条强制留痕 |
| 事件骨架引入后并发行为变化 | 幂等表 + 回归测试；S4-0 单测覆盖派发顺序 |

---

## 关联引用

- `docs/superpowers/plans/2026-10-01-p7-complete-sprint.md` — P7 总计划（Sprint 4 原文）
- `docs/PCS-SIGN-T5-2026-10-05.md` — T5 封版签署
- `docs/PCS-NOTE-T5-MJ-基准口径裁决-2026-10-05.md` — 口径裁决全过程
- `docs/PCS-NOTE-catalyst_loading-取消-2026-10-05.md` — catalyst_loading 取消
- `docs/PCS-NOTE-CIA-反向恢复-推到P8-2026-10-05.md` — CIA 推迟 P8 + 落地路径
- `docs/PCS-UI-SPEC.md` §4.4 修订登记 — 工艺气体/低温热口径
- `docs/sprint3-plan-2026-10-02.md` — Sprint 3 计划（格式参照）
