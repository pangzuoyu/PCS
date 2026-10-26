---
status: accepted
date: 2026-08-28
---

# 已发布记录的修改走 CHANGED 生命周期 + 变更单机制，不回退 DRAFT、不写时复制

被交付物快照绑定的 CHECKED 记录需要修改时（场景：管道一览表 Rev 0 已发布，第 5 条管径算错），存在三条路：原地回退 DRAFT、写时复制新记录、交付物驱动解锁。三条都有缺陷——回退 DRAFT 丢失"修改已发布数据"与"新建"的语义区分；写时复制使位号唯一性、设备表同步、血缘追溯都要处理双记录并存；交付物驱动解锁让数据正确性问题被发布流程卡住。

决定：记录层增加 CHANGE_PENDING（获准修改、正在改+重校核）与 CHANGED（校核完成、等待关闭）两态。变更通过两种凭证关闭：新版交付物发布（大变更，升 Rev）或**变更单（Change Notice）**发布（小变更，独立签署矩阵，版本目的 ISSUED_FOR_CHANGE，与工程 DCN/ECN 实践一致）。变更单驳回则记录回 CHANGE_PENDING 重改。被绑定的旧 Rev 永久标记 AFFECTED（快照与当前数据不一致是既成事实）。

## Consequences

- RecordSignStatus 扩展为 6 值；业务记录表新增 change_pending_since / change_resolved_by / change_resolved_at / old_record_hash_before_change 四字段。
- 新增 change_notices、change_notice_record_bindings 两张表；变更单复用 SUP-004 版本目的与 SUP-005 签署矩阵机制（新增 CHANGE_NOTICE 文档类型、ISSUED_FOR_CHANGE 目的）。
- 每次对已发布数据的修改都有可追溯的关闭凭证（谁、为什么、凭什么关闭），防止无声修改。
- SUP-005 §3.2"上游变更回退规则"需与 CHANGED 机制对齐（见后续 ADR）。

## 修订记录

### 2026-10-26 · 「变更单驳回则记录回 CHANGE_PENDING 重改」一句**被 ADR-0008 取代**

**本 ADR 的决定正文一字未改**（ADR 记录历史，不重写历史）；这里登记一次
**范围收窄**。

**冲突**：本 ADR 说「变更单驳回则记录回 CHANGE_PENDING 重改」；ADR-0008 说
「被驳回则回 DRAFT，**绑定记录保持 CHANGED**」—— 两句都写「变更单驳回」，
字面互斥（2026-10-26 评审发现，长期未登记 ⇒ TODO-084 第 4 条）。

**裁决**：**ADR-0008 管辖「变更单被驳回」这一事件**，本 ADR 那半句**不适用**于
变更单驳回（它描述的是**变更被放弃**，见下）。理由三条：

1. **对象不同**。ADR-0008 讲的是**变更单（交付物）**的状态机（回 DRAFT）；
   本 ADR 讲的是**记录**的状态机。两者可以同时成立 —— 驳回时
   *单据*回 DRAFT（ADR-0008）＋ *记录*回 CHANGE_PENDING（本 ADR）。
2. **本 ADR 那半句没有机制**。9 态状态机里 `CHANGED` 的出边只有
   `REQUEST_REVERSAL` 与 `OBSOLETE` —— **没有** `CHANGED → CHANGE_PENDING`
   ⇒ 「回 CHANGE_PENDING」今天**无法执行**。
3. **照字面实现会断掉哈希链**。变更单与记录的关联行
   （`deliverable_record_bindings`）带 `record_hash` / `old_record_hash_before_change`
   —— 那是**建单那一刻**的哈希。若驳回后记录直接回 CHANGE_PENDING（**可编辑**），
   记录内容一改，单据上的哈希就与记录**脱节** ⇒ 关闭凭证说的不是被关的那条数据。

**「重改」的落地路径**（已实现、可测）—— 不是「记录回 CHANGE_PENDING」，而是
**撤销 → 重来**：

```
变更单被驳回（单据 → DRAFT，记录保持 CHANGED）
  → 数据本身要改？走撤销：request-reversal（CHANGED → REVERSAL_PENDING）
    → approve-reversal（→ CHECKED）
  → initiate-change（CHECKED → CHANGE_PENDING，可编辑）→ 改 → apply-change（→ CHANGED）
  → 重新签发同一张变更单（DRAFT → PENDING，R-5 已允许）→ 3 级签署 → 自动关记录（→ CHECKED）
```

⇒ 「重改」**能走通**，只是路径是「撤销 + 重来」而不是「原地回退」。

⚠️ **2026-10-26 二次更正**：本记录最初写的是「approve-reversal ⇒ **恢复快照**
⇒ 回到变更前的数据」—— **那句话说早了**：快照的 `data_snapshot_json`
**恒为 `{}`**（`state_machine._create_snapshot` 写的是空 dict ⇒ 没有任何代码
往里放数据）⇒ 恢复循环**空转** ⇒ **撤销并不真的恢复数据/哈希**，记录带着
改动回到 CHECKED。⇒ 「撤销」目前只回**状态**，不回**数据**（缺陷已登记
**TODO-087** + bug-2070，有 xfail 用例钉着）。⇒ 上面的「重改」路径成立，
但它**不依赖**撤销恢复数据（改数据是在**第二次** CHANGE_PENDING 里做的）。

⚠️ **遗留**（已登记 TODOS.md）：重走时那张变更单的 binding 哈希是**建单时**的，
而记录的数据已被撤销/重做过 ⇒ 哈希链需要**刷新**（另立一轮，不在本裁决范围）。
