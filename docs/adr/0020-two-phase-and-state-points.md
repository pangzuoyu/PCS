---
status: accepted
date: 2026-08-29
---

# 两相流必须同时保存总组成与气液相组成；T/P 变化通过新建状态点表达，不修改原值

仅存总组成（被否决）会让下游两相流计算无法精确处理；直接修改物流 T/P（被否决）不可追溯且无法支持多工况对比。物流的物理状态是快照——改变条件应派生新快照。

决定：两相流物流同时保存总组成、气液分率（vapor_fraction）、气相组成、液相组成；气液组成可由 FLASH 模块计算填充（标记 estimated）。一条物流可有多个状态点（StatePoint，新表 stream_state_points），每个状态点独立保存 T/P/相态/气液分率/组成/物性/record_hash；状态点表达不同工况（NORMAL/MIN/MAX/ALTERNATE）。位置变化不建状态点——按 ADR-0022 用不同物流表达（本 ADR 初稿含 POSITION 工况，被 ADR-0022 修正移除；状态点间的设备连接字段亦随 ADR-0022 移至 streams 表）。

## Consequences

- streams 表新增 vapor_composition_json / liquid_composition_json；新增 stream_state_points 表。
- FLASH 与状态点联动：给定 T/P/总组成自动计算气液组成并写回状态点。
- 状态点的 record_hash 纳入血缘锚定（P1）。
