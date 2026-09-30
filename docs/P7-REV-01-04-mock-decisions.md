# P7-REV-01~04 — 启动前裁决清单 mock 决议

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**裁决日期**: 2026-10-01
**裁决方**: 架构委员会 + 工艺负责人（mock 裁决，待真实会议确认）
**触发**: P7 SPEC V1.3 §4.5 + §4.7 启动前必备裁决清单
**关联**: P7 SPEC V1.4 §4.7

---

## R-01 — §3.2.1 设备来源表遗漏

**问题**（V1.4 patch 修订 1）：P7 SPEC V1.3 §3.2.1（1）设备记录来源与同步表只列了 PUMP / VESSEL / HEAT / PSV / CV / 手动录入 6 类，遗漏了 P5-0-1b 后的 PSYCHRO（C-16）+ P6-5+ 后的 COOL_TOWER + P6 OPEN_CHANNEL。

**V1.4 修补方案**（已在 L595+ patch）：替换原表，11 行（新增 VESSEL·C-08/C-07/C-10 三子服务 + PSV·C-20 储罐通风 + CV·C-24 + COOL_TOWER + PSYCHRO·C-16 + OPEN_CHANNEL）+ C-16 甘醇脱水塔同步注记（默认不自动进设备表，需手动触发）。

**mock 决议**: ✅ **接受 V1.4 修订 1**（工艺负责人 2026-10-01 签收）

**责任方**: 工艺负责人
**截止**: V1.4 发布即闭环
**无需用户裁决**（V1.4 patch 自行闭环；如不接受可走 V1.4.1 micro-revision）

---

## R-02 — P7-OPEN-009（UTIL 5 表）方案 A/B（需用户裁决）

**问题**：P7-OPEN-009 描述 SUP-010 V1.1 §3.2.3 + §3.3.4 落地的 6 项（5 表 + 4 字段）：
1. `utility_power_items`（电耗设备清单）
2. `utility_fuel_gas`（燃料气）
3. `utility_heat_exchange`（蒸汽/冷凝水）
4. `utility_energy_summary`（综合能耗汇总 + 折标煤系数 from CONFIG）
5. `catalyst_loading`（催化剂装填量）
6. `auxiliary_consumption` 表新增 4 字段（electrical_power / fuel_gas_consumption / steam_consumption / cooling_water_consumption）

**验收**: 综合能耗汇总与 Excel 偏差 ≤ 2%（数据来源：蜡油加氢—综合能耗.xlsx）

### 两方案对比

| 维度 | 方案 A（纳入 P7 基线）| 方案 B（延后 P7.5）|
|---|---|---|
| 工时 | +2~3 人周（数据模型 + service + alembic + fixture + 工艺室签署）| 0（保持 V1.3 util_results 单表 + consumption_json JSONB 容器）|
| P7 总工时 | 10-13 人周 | 8-10 人周 |
| 综合能耗精度 | 5 表规范化 + 折标煤系数 CONFIG 化，精度高 | util_results 单表 JSONB 容器，精度中 |
| P7 主线聚焦 | UTIL 基线 + 5 表迁移并行，工时压力大 | UTIL 基线（V1.3）独立交付，5 表迁移推到 P7.5 |
| 工艺室依赖 | 强依赖（5D-2 2026-11-15 后 AS 1210 PDF + 工艺室校准） | 不强依赖（P7 主线可先交付骨架，P7.5 等工艺室签署）|
| 数据源 | 蜡油加氢—综合能耗.xlsx（已在 sample/） + 工艺室签署 | 同左（P7.5 再启）|
| 单人开发适配性 | ❌（10-13 人周超负荷）| ✅（8-10 人周主线可控）|

### 我的推荐

**方案 B（延后 P7.5）** — 推荐理由：

1. **单人开发负荷现实**（per memory 「CI/CD 不做」+ P7-9-PICKUP-6 5D schedule 已排定 8.5 人日/批）：10-13 人周超负荷；P7 主线 8-10 人周已含 EQUIP_LIST(2.5-3) + UTIL 基线(1.5-2) + EQUIP_LIB(1-1.5) + 供应商数据(2-2.5)
2. **P7 V1.3 基线已含 UTIL 综合能耗骨架**（util_results 单表 + consumption_json JSONB 容器 + 13 类公用工程枚举 §4.4）：可临时承载验收 ≤2% 偏差（粗估 1.5-2% 边界）
3. **P7.5 排期与 P6-9-PICKUP-6 5D-2 自然衔接**（2026-11-15 后 AS 1210 PDF 等 OPEN 关闭时启动）
4. **降低工艺室签署 schedule 风险**（方案 A 强行要求工艺室 10 月签署 6 项；方案 B 仅需 5D-2 时间窗）

### mock 决议（待用户裁决）

- ⏸️ **方案 B（延后 P7.5）** — 推荐
- ⏸️ 方案 A（纳入 P7 基线） — 备选

**请用户在 Phase 2 末裁决。**

---

## R-03 — P7-OPEN-007（physical_semantics）三元决策

**问题**（per V1.6 §3.2b）：是否启用 physical_semantics 语义过滤？决策出口为三元：
- 方案 1（成因 B > 50%）：启用语义过滤
- 方案 2（成因 A 主导）：修正 record_hash 范围
- 方案 3（成因 C 主导）：审计并修正 dependency_type 分类
- 三者均 < 50%：默认不启用

### mock 决议

**数据样本 = 0**（pcs_test audit_logs 表 0 行；state_machine.py grep 三字段 = 0 matches）

**❌ 不可套用「三者均 < 50% → 默认不启用」分支**（per R=1 lesson + P7-OPEN-007 评估报告 §4.1）

**✅ 推迟三元决策 → 登记「数据待补采」**（per P7-OPEN-007 评估报告 §4.2）

**触发条件**:
1. **T0**（架构组执行前必办）：`StateMachineService` 强制写入 `stale_resolution_path` / `hash_changed` / `changed_fields` 三字段
2. **T1**（pcs_test fixture）：预填 ≥30 行 STALE 解除审计 fixture（已知 A/B/C 分布）
3. **30 天窗口**：T0 + T1 落地后 30 天重新跑 P7-OPEN-007 评估脚本

**架构委员会需确认事项**（P7 Sprint 0 内）:
1. ✅ 接受「数据不足 → 推迟决策」
2. ✅ T0 是否纳入 P7 Sprint 0 任务（**建议：是**，否则 P7 Sprint 1 部署后仍无样本）
3. ✅ T1 pcs_test fixture 是否需要工艺室签署（**建议：是**，按 PROCo 标记）

**责任方**: 架构委员会
**截止**: P7 Sprint 0 末（与 P7 SPEC V1.4 同步发布）

---

## R-04 — P7-OPEN-008（规则清单形态）方案 A/B

**问题**（per V1.6 §3.5）：P4–P6 期间 `@rule` 装饰器使用数 > 20 → 方案 A（CI 自动生成）/ ≤ 20 → 方案 B（ADR 附录）

### mock 决议

**规则计数 = 0**（grep `pcs-backend/app/` for `@rule` = 0；`app/core/rules_registry.py` 不存在）

**✅ 方案 B（ADR 附录）采纳**（per P7-OPEN-008 评估报告 §4.1）

**方案 B 落地要求**:
- ❌ 不建立 `app/core/rules_registry.py`（保持 V1.6 §6 规则 10「P7 前不手动维护规则清单」）
- ❌ 不为 `@rule` 装饰器新增 CI 自动生成
- ✅ 规则记录在相关 ADR 附录（P4+ 各模块 ADR 已含业务规则段）
- ✅ PR/ADR 模板「本次新增/修改的业务规则」审计线索保留

**重新评估触发**:
- 规则数 > 20 条
- 新模块 / 跨模块规则需求
- 工艺室 / 法规要求显式规则清单

**建议 V1.7 §3.5 加脚注**：「本节声明与 P4 实际落地不一致（接口骨架未预留 + 装饰器使用 = 0），详见 P7-OPEN-008 评估报告」

**责任方**: 架构委员会
**截止**: P7 Sprint 0 末（与 P7 SPEC V1.4 同步发布）

---

## 裁决清单汇总

| 编号 | 决议 | 状态 | 责任方 | 截止 |
|---|---|---|---|---|
| R-01 | 接受 V1.4 修订 1（设备来源表补 C-08/C-16/C-24/COOL_TOWER/OPEN_CHANNEL）| mock 接受 | 工艺负责人 | V1.4 发布即闭环 |
| R-02 | **待用户裁决**（方案 A vs B）| 待裁决 | 架构委员会 + 工艺负责人 | P7 Sprint 0 |
| R-03 | 推迟 → 待补采（T0 + T1 + 30 天窗口）| mock 接受 | 架构委员会 | P7 Sprint 0 末 |
| R-04 | 方案 B（ADR 附录）采纳 | mock 接受 | 架构委员会 | P7 Sprint 0 末 |

---

## 下游依赖

| 决议 | 下游 SPEC 章节修订 |
|---|---|
| R-01 | V1.4 §3.2.1（1）表替换（已 patch）|
| R-02 (若 B) | V1.4 §3.2.2（5）+ §4.5 P7-OPEN-009 状态更新为「延后 P7.5」+ §4.6 工时表保持 V1.3 |
| R-02 (若 A) | V1.4 §3.2.2（5）表结构 + §4.4 类型清单同步改写为 5 表结构 + §4.6 +2-3 人周 |
| R-03 | V1.4 §4.5 P7-OPEN-007 状态更新为「待补采」+ 新增 T0/T1 跟踪位 |
| R-04 | V1.4 §4.5 P7-OPEN-008 状态更新为「方案 B（ADR 附录）已采纳」+ V1.7 §3.5 加脚注建议 |

---

## 验收

- [ ] 用户裁决 R-02（A 或 B）
- [ ] R-01~04 mock 决议写入 P7 SPEC V1.4 §4.7 裁决清单
- [ ] R-03 触发条件 T0 纳入 P7 Sprint 0 任务（如架构委员会接受）
- [ ] R-02 裁决落地后启动 Phase 4（若 A）或关闭（若 B）

## 关联

- 上游：P7 SPEC V1.3 §4.5 + §4.7
- 下游：P7 SPEC V1.4 §4.7 + 兄弟报告 P7-OPEN-007/008
- 教训：.wolf/cerebrum.md「Do-Not-Repeat：source-verify brief」
- bug：bug-114（state_machine 不写三字段）+ bug-115（rules_registry 未预留 + @rule = 0）
