PCS-DICT-ALL-003 V3.3（最终整合版·完整）
文件标识	PCS-DICT-ALL-003
当前版本	V3.3
发布日期	2026-09-01
变更来源	ADR-0023~0025 + P1-MVP Issue 1-9 + P1计划v6全部裁决 + **PCS-DICT-007-SUP-001~014全部增补**
第一部分：版本变更摘要
版本	变更
V3.0	初始53表版本
V3.1	ADR-0023：equipment_type_codes增加project_id，支持项目级覆写
V3.2	ADR-0024：record_change_snapshots增加snapshot_status列
V3.3	ADR-0025设备联动语义 + AuditAction完整枚举 + PCS-DICT-007-SUP-001~014全部整合
表数量不变：53表。 SUP-001~014均为JSON结构字典，不新增表。

第二部分：表定义变更详情
2.1 equipment_type_codes（ADR-0023）
字段名	类型	必填	说明
type_code	string(5)	✅	PK（复合，含project_id）
project_id	UUID nullable	❌	项目级覆写；NULL=公司级默认
equipment_description	string(200)	✅	
description_cn	string(100)	❌	
category	enum	✅	
is_process_equipment	bool	✅	
is_pressure_vessel	bool	✅	
source	string	❌	
status	enum	✅	ACTIVE/OBSOLETE
唯一约束：UNIQUE(COALESCE(project_id::text, ''), type_code)

2.2 record_change_snapshots（ADR-0024）
字段名	类型	必填	说明
snapshot_id	UUID	✅	PK
record_type	enum	✅	
record_id	UUID	✅	
record_hash	string(64)	✅	快照时哈希
data_snapshot_json	JSON	✅	完整设计参数
snapshot_reason	enum	✅	BEFORE_CHANGE/BEFORE_DRAFT（BEFORE_STALE保留不写）
snapshot_source	enum	✅	MANUAL_CHANGE/UPSTREAM_CHANGE/MANUAL_ROLLBACK
snapshot_status	string(20)	✅	ACTIVE/CONSUMED/ABANDONED，默认ACTIVE
created_at	datetime	✅	
created_by	UUID	✅	
2.3 audit_logs（P1 Issue 6）
字段名	类型	说明
action	string(50)	完整AuditAction枚举（~40值，应用层定义）
其余字段	不变	见V3.0
2.4 equipment_list（ADR-0025）
actual_data_status语义扩展：NEED_RECALC用于CIA扫描失败标记。不新增cia_status列。

第三部分：PCS-DICT-007-SUP-001~014 完整整合
3.1 设备数据表结构清单（对应各模块JSON字段）
设备类型	data_sheet_json结构	来源SUP	关联表字段
卧式/立式容器	vessel_data_sheet_json	SUP-001	vessel_results.data_sheet_json
板式塔	tray_column_data_sheet_json	SUP-002	vessel_results.data_sheet_json
球罐	spherical_tank_data_sheet_json	SUP-003	vessel_results.data_sheet_json
反应器	reactor_data_sheet_json	SUP-003	vessel_results.data_sheet_json
空冷器	ache_data_sheet_json	DICT-005-SUP-002	heat_results.data_sheet_json
过滤器	filter_data_sheet_json	DICT-010	filtration_results.data_sheet_json
起重设备	crane_data_sheet_json	SUP-005	equipment_list.design_parameters_json
液力透平	turbine_data_sheet_json	SUP-006	pump_results.data_sheet_json
限流孔板	restriction_orifice_datasheet_json	SUP-013	restriction_results.data_sheet_json
文丘里洗涤器	venturi_scrubber_data_sheet_json	SUP-013	sep_equip_results.data_sheet_json
冷却塔	cooling_tower_data_sheet_json	SUP-012	cooling_tower_results.data_sheet_json
安全阀	psv_data_sheet_json + calc_sheet_json	DICT-009	psv_results
调节阀（5格式）	cv_design_condition_json/cv_batch_condition_table_json/cv_calc_spec_json/control_valve_spec_json/valve_data_sheet_json	SUP-004/007/008/009/010/011	cv_results
流量计	flowmeter_condition_table_json	SUP-011	restriction_results
HYSYS物流物性	stream_hysys_property_json	SUP-011	streams
3.2 文档格式全景（CV/RESTRICTION模块）
文档	JSON结构	适用类型	来源
设计条件表	cv_design_condition_json	调节阀	SUP-007
批量开关阀汇总	cv_batch_condition_table_json（简化）	XMV	SUP-010
批量调节阀汇总	cv_batch_condition_table_json（扩展）	LV/FV/HV/TV/PV	SUP-011
批量流量计汇总	flowmeter_condition_table_json	FE/FT	SUP-011
计算+规格合并表	cv_calc_spec_json	调节阀	SUP-009
仪表规格书	control_valve_spec_json	调节阀	SUP-008
自力式调节阀	regulator_valve_spec_json	自力式	SUP-008
阀门数据表	valve_data_sheet_json	通用	SUP-004
FF总线数据	fieldbus_data	定位器	SUP-008
限流孔板数据表	restriction_orifice_datasheet_json	孔板	SUP-013
文丘里洗涤器	venturi_scrubber_data_sheet_json	洗涤器	SUP-013
3.3 成本估算（SUP-014）
cost_estimate_json（7大模块：metadata/cost_summary/cost_categories/risk_factors/monte_carlo_results/contingency_recommendation/validation_checks），对应cost_est_results。

3.4 施工进度（DICT-008-SUP-001）
construction_progress_json（6个Gate+W.F.权重），对应equipment_list施工字段组。

第四部分：新增枚举定义（V3.3完整版）
4.1 SnapshotStatus
值	说明
ACTIVE	可被撤销批准使用
CONSUMED	已消费（凭证关闭/撤销执行）
ABANDONED	已放弃
4.2 AuditAction（完整~40值）
见P1 Issue 6裁决定义。

4.3 RestrictionElementType
值	中文
RESTRICTION_ORIFICE	限流孔板
ORIFICE_PLATE	标准孔板
VENTURI_TUBE	文丘里管
NOZZLE	喷嘴
4.4 ScrubberType
值	中文
FIXED_THROAT_HIGH_ENERGY_VENTURI	固定喉嘴高能文丘里
ADJUSTABLE_THROAT_VENTURI	可调喉管文丘里
SPRAY_TOWER	喷淋塔
PACKED_SCRUBBER	填料洗涤塔
TRAY_SCRUBBER	板式洗涤塔
4.5 CraneType / OperatingGrade / InsulationType / DeliveryType
见DICT-007 SUP-005 / DICT-008 SUP-001。

第五部分：ADR文档引用汇总
ADR	内容	影响表
ADR-0023	TypeCode项目级可配置	equipment_type_codes
ADR-0024	快照时机修正	record_change_snapshots
ADR-0025	设备联动最终一致性	equipment_list（语义）
第六部分：版本历史
版本	日期	修改内容
V3.0	2026-08-29	初始53表
V3.1	2026-08-29	ADR-0023
V3.2	2026-09-01	ADR-0024
V3.3	2026-09-01	ADR-0025 + AuditAction完整枚举 + PCS-DICT-007-SUP-001~014全部整合
