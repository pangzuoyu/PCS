---
status: accepted
date: 2026-09-01
supersedes:
  - ADR-0010 § 进入 STALE 时自动保存变更前快照
  - ADR-0012 § 双层批准带来的快照时机
---

# 快照仅在"数据即将被修改"瞬间创建，移除 STALE 自动存盘

P1 计划 v3 引用 ADR-0010 / ADR-0012 的隐含规则："进入 STALE / CHANGE_PENDING 时系统自动保存变更前快照"。P1-MVP 实施审阅（2026-09-01）发现 STALE 期间数据未修改——仅标记存疑、源记录哈希待重算——此时存盘快照是浪费存储，且撤销恢复时快照内容与 STALE 前完全相同，无信息增益。

决定：调整快照创建时机为**仅在数据即将偏离 CHECKED 基线时创建**。具体三种触发：

- **CHECKED → CHANGE_PENDING**（主动发起变更）：保存 CHECKED 基线
- **STALE → CHANGE_PENDING**（确认重算哈希变化）：保存 STALE 前基线（数据仍等于 CHECKED 基线，记录 STALE 期 record_hash）
- **CHECKED → DRAFT**（未绑定记录回退）：保存 CHECKED 基线

**CHECKED → STALE 不再写快照**（STALE 期间数据未修改）。撤销批准时读 `snapshot_status=ACTIVE` 的快照，同事务恢复记录字段 + 标记 `CONSUMED`。**STALE → CHECKED（哈希不变）路径不需要快照**（数据从未偏离基线）。

新增 `record_change_snapshots.snapshot_status String(20)` 字段（ACTIVE/CONSUMED/ABANDONED，默认 ACTIVE），支撑撤销逻辑显式区分可用快照与已用快照。`snapshot_reason` 枚举实际使用 BEFORE_CHANGE / BEFORE_DRAFT；BEFORE_STALE 保留枚举值不删（兼容未来扩展）。

P4 计算模块"数据即将被修改"的判断通过 `StateMachineService.transition` 一站式触发，caller 不复制副作用逻辑。撤销时需校验快照 `record_hash` 与当前记录 `old_record_hash_before_change`（STALE→CHANGE_PENDING 时记录的旧哈希）匹配，否则视为快照过期、拒绝恢复。

## Consequences

- `record_change_snapshots` 表新增 `snapshot_status` 列，Sprint 2 migration 落地；DICT-ALL-003 → V3.2。
- 记录表新增 `old_record_hash_before_change` 字段由快照承载（P1-MVP 不新增列，从快照表读取旧哈希；如需记录上直接暴露则后续 Sprint 加 FK）。
- STALE 存储成本降为 0（原先每条 STALE 记录一份快照，现仅 CHANGE_PENDING 时一份）。
- `StateMachineService.transition` 需在数据即将被修改前创建快照（顺序：守卫 → 快照 → 状态变更 → 审计 → flush）。
- ADR-0010 § "进入 STALE 时系统自动保存变更前快照"作废；ADR-0012 § 状态机快照时机同步。
- SPEC-P1 V1.2 → V1.3，§3.2.2 同步修订。
- SUP-007 §3.1 文字同步。