---
status: accepted
date: 2026-08-28
---

# 设备记录在来源 CHECKED 时同步创建，状态随来源联动；哈希只覆盖设计参数

P7 原文按旧模型写：计算保存即同步（DRAFT 数据进设备表）、equipment_list 自带 CHECKING~APPROVED 签署、来源变更仅"提示用户确认更新"。设备记录还是混合体：设计参数来自计算模块，采购/图纸/交付/安装/重量/工程字段由采购、施工等角色直接编辑。

决定：计算记录到达 CHECKED 才自动创建/更新设备记录（DRAFT 试算不进设备表）；来源记录 STALE / CHANGE_PENDING / CHANGED / 变更关闭时设备记录联动进入相同状态。设备记录本身是普通计算记录（7 态门禁、无 Rev），设备一览表（EQUIP_LIST）、单台设备数据表（EQUIP_DATASHEET）、采购清单（PURCHASE_LIST）是交付物类型。record_hash 仅覆盖 tag_number + type_code + design_parameters_json + source_module + source_record_id——采购工程师改供应商、交付日期、安装备注不触发任何变更流程（运营数据 ≠ 设计数据）。

## Considered Options

- 保存即同步（P7 原文）——设备表充满未校核数据，位号被试算数据占坑，否决。
- 纯手动同步——设备表永远滞后，遗漏风险高，否决。

## Consequences

- 设备记录 CHANGED 的关闭凭证三选一：来源记录关闭连带、自身变更单、设备一览表升 Rev。
- 商务字段变更不产生 AFFECTED（哈希不覆盖）；PURCHASE_LIST 类交付物发布时对商务字段做整体快照固化。
- P7 新增 P7-EQL-010~015；原"重新计算后提示用户确认更新"改为自动联动。
