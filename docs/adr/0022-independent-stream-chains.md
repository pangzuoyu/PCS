---
status: accepted
date: 2026-08-29
supersedes: ADR-0021
---

# 物流与设备的连接模型：独立物流链——一条物流=一个管段，设备是物流间的转换函数

物流号是管段的标识：经过设备后物流号更换（S-101→泵 P-101→S-102→阀→S-103→管道→S-104）。ADR-0021 的"一条物流贯穿多设备"模型（被否决）与 P&ID/PFD 的实际编号做法不符。

决定：设备是物流之间的转换函数，连接记录在 streams 表（upstream_stream_id + upstream_equipment_type + upstream_equipment_id + change_type：ISOENTHALPIC / FRICTION_PRESSURE_DROP / HEAT_EXCHANGE / PUMP_WORK）。**位置变化用不同物流表达；工况变化用同一物流的状态点表达**（case_type 移除 POSITION，仅 NORMAL/MIN/MAX/ALTERNATE）。设备计算完成后自动创建出口物流：source_type=DEVICE_CALCULATED、sign_status=DRAFT、需走校对流程。血缘记录 {S-101} --[PUMP-101]--> {S-102} 形态的转换边；CIA 沿链式传播：物流→设备→物流→设备→物流。

## Consequences

- stream_state_points 删除 upstream_state_point_id / equipment_type / equipment_id / change_type 字段（移至 streams 表）。
- streams 表新增 upstream_stream_id / upstream_equipment_type / upstream_equipment_id / change_type。
- 适用设备：PUMP / CV / PIPE / HEAT / RESTRICTION / FLASH（计算完成自动创建出口物流，P4~P6 各模块落实）。
- data_lineage 支持物流→设备→物流连接类型；P1 CIA 链式传播。
