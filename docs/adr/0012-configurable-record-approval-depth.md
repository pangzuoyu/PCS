---
status: accepted
date: 2026-08-28
---

# 记录层批准深度可配置；CHECKED = 全部配置步骤通过，是交付物绑定的唯一准入状态

ADR-0002 的状态表曾写"DRAFT 可被新交付物绑定"，与其自身流程"选择已 CHECKED 的记录创建交付物"矛盾；且用户指正：不同记录类型需要不同批准深度（安全阀要 4 级含客户，标准管道 2 级，FLASH 中间计算 1 级甚至 0 级），固定两级门禁不够。

决定：绑定规则收紧为**仅 CHECKED 可绑定**（其余 8 态一律拒绝，整份拒发）。CHECKED 语义升级：该记录类型配置的全部批准步骤通过。新增复合状态 IN_APPROVAL（内部 approval_step / approval_depth / approval_role 追踪），批准深度存于项目模板 record_approval_config，按模块差异化；深度可含 CUSTOMER 步骤（走 ADR-0007 凭证代录）。设备记录从来源计算记录继承批准深度，同步即 CHECKED，商务字段不受影响。个人/临时工作区记录永远 DRAFT、不得进入 IN_APPROVAL（ADR-0004 不变）。双层批准各司其职：记录层确认"单条数据正确"（≤交付物层深度），交付物层签署矩阵确认"整份文档可发布"。

## Consequences

- RecordSignStatus 最终 9 值；原 CHECKING 概念并入 IN_APPROVAL。
- 业务记录表新增 approval_step / approval_depth / approval_role 字段。
- 本 ADR 修订 ADR-0002（CHECKED 含义）与 ADR-0002 状态表（DRAFT 可绑定条目作废）。
- P1 状态机增加 IN_APPROVAL 复合状态与配置解析；P2 项目模板增加 record_approval_config；P9 按深度渲染批准按钮与进度。
