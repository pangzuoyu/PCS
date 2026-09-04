---
status: accepted
date: 2026-08-28
---

# 血缘以 record_id + 哈希锚定，删除全部 xxx_History 快照流水表

data_lineage 的 source_version / target_version 在两层模型下语义悬空（记录无版本）；各业务表配套 xxx_History 快照流水与"变更前快照 / 交付物版本 / 审计日志"三处历史职责重叠。

决定：data_lineage 删除两个 version 字段，改为 source_record_hash / target_record_hash（计算时刻哈希），保留 formula_version 并新增 config_version（引用的管道等级等配置版本）；血缘仍只追加。删除全部 xxx_History 表。历史三处承载、职责单一：record_change_snapshots 存完整设计参数（进 STALE/CHANGE_PENDING 前写、撤销/放弃时回滚）、deliverable_record_bindings 只存哈希（发布固化）、audit_logs 存行为流水。CIA 检测改为哈希不匹配：变更记录的新哈希 vs 血缘中 source_record_hash，命中即下游 STALE；级联影响在下游重算（自身哈希变化）时逐级传播，不做预先递归遍历。

## Consequences

- P0 表清单：data_lineage 字段改造；约 10+ 张 xxx_history 表不再创建；record_change_snapshots 为正式表。
- P1：版本管理模块删除（版本仅存于交付物层）；CIA 从递归 CTE 改为哈希不匹配定位 + 状态联动（ADR-0005）。
- 追溯矩阵：Rev 发布时数据 → bindings 哈希；变更前数据 → 变更前快照；行为 → 审计日志，全覆盖无死角。
