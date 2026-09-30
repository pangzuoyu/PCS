"""S1-4 EQUIP_LIST 同步服务包（P7-Sprint 1 T2）。

包含：
- ``type_code_map``: source_module → type_code 常量映射
- ``source_resolver``: source_module + source_record_id → ORM 记录 dispatcher
- ``sync_service``: sync_from_source 主入口（CHECKED 触发 → EquipmentList 同步）
"""
