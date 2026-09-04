---
status: accepted
date: 2026-08-28
---

# 交付物 doc_no 由项目模板级可配置的编号模板生成，不硬编码编码规则

deliverables.doc_no 的产生规则在规格中空白；不同公司/客户的文控编号规则差异大（Worley 多段式、简化式、带日期式、按装置式）。硬编码任一种都会限制跨客户复用，纯手动录入则失去序号防冲突与自动分配。

决定：编号系统作为 CONFIG CATEGORY_1 项目模板中的编号模板（Numbering Template）——段类型 6 种（PROJECT_FIELD / DELIVERABLE_FIELD / SEQUENCE / FIXED / MANUAL / DATE）+ 分隔符 + 交付物类型→段字段映射；SEQUENCE 段按 scope（如 discipline+doc_id 组合、按项目/按拆分范围/按年重置）通过数据库原子 UPSERT 分配，已分配序号不回收、允许手动指定跳号。同类型交付物可按装置等拆分范围创建多份，各自独立 Rev 序列；Rev 不进 doc_no。创建交付物时可选自动编号（预览）或手动录入，系统校验项目内唯一。P2 内置 3–5 套标准模板。

## Consequences

- 新增 numbering_templates、doc_no_sequences 两表；deliverables 增加 numbering_template_id / segment_values_json / manual_doc_no 字段。
- 变更单编号（CN-xxx）同样走编号模板（deliverable_mappings 含 CHANGE_NOTICE）。
- 编号模板编辑器进 P2 项目模板编辑器；交付物创建 UI（P8）与变更单创建 UI（P9）集成编号预览。
