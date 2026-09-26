# P6-5 前端补课：3 计算页（heating-value / saturation-water-content / cv）

依据：UI SPEC §7.12 设备计算统一页面模式（PageHeader + SchemaForm 输入 + 计算按钮 + 结果卡片区）+ OpenAPI（G-08 baseline 已滚至 161 paths / 203 schemas，types 已 regen）。P6-4 DECISION 推迟项，独立前端批。

范式：VesselComputePage（Card 输入 + Card 结果 + NumberRow）+ pages/routeWrappers.tsx + api/<mod>.ts 薄 wrapper + mocks handler + tests/pages/<mod>/。

- T1 api 层：`api/common.ts`（heating-value）+ `api/psychro.ts` + `api/cv.ts`，types 从 `types/api`（生成）re-export 薄层
- T2 HeatingValuePage：动态组分行（compound/concentration）+ excess_air + 结果（HHV/LHV 双单位 + 烟气组成 + MW）
- T3 SaturationWaterContentPage：T/P/单位 + 结果（kg/kg + mg/Sm³ + lb/MMscf + SI/Imperial）
- T4 CvComputePage：phase 分支（LIQUID/GAS/STEAM）条件字段 + 结果（Cv + fl + flash_steam_rate + masonelian_model）
- T5 路由（App.tsx + routeWrappers）+ MSW handlers + vitest ×3 + tsc/eslint/vitest 全绿

未解决问题：无
