---
status: accepted
date: 2026-08-28
---

# 演示版模块限制按活记录计数（OBSOLETE 不计），交付物与变更单不限量

SUP-006 定义演示版每模块 ≤3 条记录，但记录层现有 8 态（含 OBSOLETE 弃用终点），计数口径未定；交付物/变更单是否限量也未明确。

决定：计数 = sign_status ≠ OBSOLETE 的记录总数（DRAFT / CHECKED / CHECK_REJECTED / STALE / CHANGE_PENDING / CHANGED / REVERSAL_PENDING 全计入）。弃用即返还配额，演示用户可在配额内"创建→弃用→再创建"循环，不会因配额耗尽卡死演示。交付物与变更单不限量——签署流程与变更闭环是演示核心价值；报表定义独立限 3、EQUIP_LIB 沉淀禁用维持 SUP-006 原文；设备表记录无独立限制，跟随来源模块活记录计数。

## Consequences

- count_records_in_module 查询统一排除 OBSOLETE；配额提示展示"X/3 条活记录"并引导弃用腾配额。
- SUP-006 新增 §3.3.16.10 计数口径；P1 计数服务、P7 联动、P8 报表定义限制、P9 配额 UI 相应更新。
