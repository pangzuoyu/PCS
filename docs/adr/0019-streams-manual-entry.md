---
status: accepted
date: 2026-08-29
---

# Streams 必须支持手动创建（含炼油油品特殊输入），与模拟导入并列且走同一校对流程

不是所有项目都有模拟软件输出：小项目、改造项目、炼油局部设计的物流数据常来自化验报告而非 HYSYS/Aspen。仅支持模拟文件导入（被否决）会让这些场景无法使用；手动创建不走校对（被否决）则数据质量无保障。

决定：手动创建与导入并列，支持三种数据模式——CHEMICAL（常规化工：组成+T/P+流量）、PETROLEUM（炼油油品：馏程/SARA 四组分/元素分析/金属含量/虚拟组分）、SOLID（固体颗粒：堆积密度/粒径/休止角/真密度）。手动创建走与导入完全相同的校对流程（ADR-0014/用户编号 ADR-0018：DRAFT→校对→CHECKED）。物性自动估算：用户填组成+T/P+流量，其余物性由 chemicals/thermo 估算并标记 estimated=true。炼油虚拟组分按沸程切割，支持手动输入或系统自动切割（每 25°C 一段）；CONFIG 增加炼油关联式（Riazi-Daubert 等）。

## Consequences

- streams 表新增 data_mode / property_estimation_json / pseudo_components_json / lab_report_ref 字段。
- StreamSourceType 枚举扩展：MANUAL_ENTRY、LAB_REPORT。
- P2 CONFIG 增加炼油关联式与物性估算参数；P3 手动创建向导；P9 校对流程 UI。
