"""供应商侧服务（P7 Sprint 4）。

- `actual_data_service`: 手工 UI 录入供应商实测值并落 `actual_data_json`
- `deviation_service`: SPEC §3.2.4(2) 异构允许偏差判定引擎
- `deviation_report`: 偏差报告组装 + 确认门禁 + xlsx/PDF 导出
- `confirmation_service`: 设计人确认 → 校核人校核 → 发 `actual_data_replaces_design`

⚠️ 录入入口是**手工 UI 页面**（S4-1 裁决）：要求供应商填统一 Excel 不现实，
故**无** Excel 批量导入模块，勿再加。
"""
