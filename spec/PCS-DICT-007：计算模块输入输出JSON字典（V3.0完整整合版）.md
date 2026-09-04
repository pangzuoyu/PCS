PCS-DICT-007：计算模块输入输出JSON字典（V3.0完整整合版）
文件标识	PCS-DICT-007
当前版本	V3.0（完整整合版）
发布日期	2026-08-29
关联文档	PCS-DICT-ALL-003 V3.0（计算模块16表）、SPEC-P4/P5/P6
整合范围	V2.0 + SUP-001~011全部增补
第一部分：概述
1.1 目的
定义计算模块（P4-P6）各结果表中JSON字段的内部结构，为各模块的输入表单、计算引擎输出、数据表生成和交付物提供权威依据。

1.2 覆盖模块全景
模块	结果表	本字典章节
VESSEL（容器/塔/球罐/反应器）	vessel_results	第二部分
HEAT（空冷器）	heat_results	第三部分
FLASH（闪蒸）	flash_results	第四部分
PIPE_NET（管网）	pipe_network_results	第五部分
FLARE_SYS（火炬）	flare_system_results	第六部分
PSYCHRO（湿空气）	psychro_results	第七部分
OPEN_CHANNEL（明渠）	open_channel_results	第八部分
SEP_EQUIP（分离设备）	sep_equip_results	第九部分
FILTRATION（过滤）	filtration_results	第十部分
CV/RESTRICTION（阀门/节流/流量计）	cv_results/restriction_results	第十一部分
PUMP（泵/透平）	pump_results	第十二部分
起重设备	equipment_list(type_code=CR)	第十三部分
SIM（HYSYS物流物性）	streams	第十四部分
1.3 数据来源标注
来源标识	文档
{MEC}	MEC PSV Sizing标准
{PVRV}	呼吸阀计算表
{DAS}	安全阀数据表
{CAL}	安全阀计算书
{V-106}	卧式容器数据表（剩余C4罐）
{C-301}	板式塔数据表（低分气脱硫塔）
{TK-01}	球罐数据表（催化液化气）
{R1002}	反应器数据表（氧化锌反应器）
{A-101}	空冷器数据表（催化蒸馏塔）
{SR-106}	过滤器数据表（蜡油过滤器）
{X-501}	起重设备数据表
{P-101T}	液力透平数据表
{PV4702}	调节阀计算+规格合并表
{TV-00803}	调节阀仪表规格书
{PCV-04101}	自力式调节阀仪表规格书
{XMV}	批量控制阀工艺条件表
{FE}	流量计工艺条件表
{HYSYS}	HYSYS物流物性输出
第二部分：VESSEL模块（vessel_results.data_sheet_json）
2.1 设备类型枚举
枚举值	设备类型	data_sheet_json结构
HORIZONTAL_VESSEL	卧式容器	vessel_data_sheet_json
VERTICAL_VESSEL	立式容器	vessel_data_sheet_json
TRAY_COLUMN	板式塔	tray_column_data_sheet_json
PACKED_COLUMN	填料塔	packed_column_data_sheet_json
SPHERICAL_TANK	球罐	spherical_tank_data_sheet_json
REACTOR	反应器	reactor_data_sheet_json
2.2 vessel_data_sheet_json（卧式/立式容器）
（完整结构已在V2.0定义，含general/process_design/mechanical_design/materials/fabrication_inspection/weights/nozzles/remarks，来源{V-106}）

2.3 tray_column_data_sheet_json（板式塔）
（完整结构已在V2.0定义，含tray_operating[]/hydraulics[]/tray_structure[]/internals_specs[]/tray_layout/mechanical_design/materials/weights/nozzles[]，来源{C-301}）

2.4 spherical_tank_data_sheet_json（球罐）
（完整结构已在V2.0定义，含process_design/fire_protection/mechanical_design/materials/nozzles[]，来源{TK-01}）

2.5 reactor_data_sheet_json（反应器）
（完整结构已在V2.0定义，含process_operating/catalyst_beds/construction/safety_valve/mechanical_design/insulation，来源{R1002}）

第三部分：HEAT模块空冷器（heat_results.ache_data_sheet_json）
3.1 顶层结构
含general/process_design（tube_side+air_side）/heat_transfer/controls_air_side/construction（tube_bundle_header+bay+louver+fan+driver+speed_reducer）/mechanical_design/materials（16部件）/fabrication_inspection/weights（12项）/nozzles/condensation_curve/remarks，来源{A-101}。

3.2 冷凝曲线（condensation_curve）
6点完整冷凝曲线数据，每点含温度/气相分率/焓/潜热/气相物性/液相物性/表面张力，来源{A-101} Page 5。

第四部分：FLASH模块（flash_results）
（V2.0原有内容，8种计算类型input_json/output_json）

第五部分：PIPE_NET模块（pipe_network_results）
（V2.0原有内容：topology_json/convergence_log_json/flow_distribution_json）

第六部分：FLARE_SYS模块（flare_system_results）
（V2.0原有内容：radiation_check_json）

第七部分：PSYCHRO模块（psychro_results）
（V2.0原有内容：6种计算类型）

第八部分：OPEN_CHANNEL模块（open_channel_results）
（V2.0原有内容：3种断面cross_section_json）

第九部分：SEP_EQUIP模块（sep_equip_results）
（V2.0原有内容：equip_type/dimensions/efficiency/pressure_drop/cut_diameter/method）

第十部分：FILTRATION模块（filtration_results）
10.1 data_sheet_json
含general/process_conditions/construction/screen_mesh_table/nozzles/materials/notes，来源{SR-106}。筛网结构参数表（7行：网孔宽度/丝径/目数/孔数/开孔面积百分数）。

第十一部分：CV/RESTRICTION模块
11.1 文档格式全景
文档	JSON结构	适用阀门类型	来源
设计条件表	cv_design_condition_json	调节阀	SUP-007
批量开关阀汇总	cv_batch_condition_table_json（简化）	开关阀XMV	SUP-010
批量调节阀汇总	cv_batch_condition_table_json（扩展）	调节阀LV/FV/HV/TV/PV	SUP-011
批量流量计汇总	flowmeter_condition_table_json	流量计FE/FT	SUP-011
计算+规格合并表	cv_calc_spec_json	调节阀	SUP-009
仪表规格书	control_valve_spec_json	调节阀	SUP-008
自力式调节阀	regulator_valve_spec_json	自力式调节阀	SUP-008
阀门数据表	valve_data_sheet_json	通用阀门	SUP-004
FF总线设备数据表	fieldbus_data	FF现场总线定位器	SUP-008
11.2 节流装置设计条件（restriction_design_condition_json）
（SUP-007完整定义：pid_no/fluid_name/流量三工况/密度/K/Z/管道参数/允许压损）

第十二部分：PUMP模块（pump_results.turbine_data_sheet_json）
12.1 液力透平数据表
含general（含供货商/安装者/数据表编号）/operating_conditions（三工况SOR/EOR/MAX）/site_utility（防爆三级）/construction（API 610 BB5）/impeller_shaft/coupling（API 671）/bearings_lubrication/mechanical_seal（API 682+Plan 23/53B）/instrumentation（API 670）/cooling_steam_piping/driver/performance/test_inspection/materials（A-7等级）/scope_of_supply/weight_contour/notes，来源{P-101T}。

第十三部分：起重设备（equipment_list.design_parameters_json）
13.1 crane_data_sheet_json
含general/site_utilities/technical_requirements/hooks（主钩/副钩）/cart_trolley（大车/小车）/geometric（Lk/B/H/H2/b）/electrical_requirements/weights/others/notes，来源{X-501}。

13.2 内置球罐/储罐选型表
（球罐容积-内径-支柱高度表；固定顶/内浮顶/浮顶储罐选型表）

第十四部分：SIM模块（streams关联）
14.1 stream_hysys_property_json（HYSYS物流物性输出）
含30物流物性：name/vapor_fraction/temperature/pressure/mass_flow/mass_density/liquid_phase{}（6项）/vapor_phase{}（6项）/heat_of_vaporization/bubble_point_pressure，来源{HYSYS}。

14.2 与streams表的映射
HYSYS字段	streams表字段
name	stream_name
vapor_fraction	vapor_fraction
temperature_c	temp
pressure_mpag	press
mass_flow_kg_h	mass_flow
mass_density_kg_m3	density
liquid_phase.viscosity_cp	viscosity_dynamic
liquid_phase.kinematic_viscosity_cst	viscosity_kinematic
liquid_phase.molecular_weight	molecular_weight
liquid_phase.z_factor	compressibility_factor
vapor_phase.molecular_weight	气相组成相关
heat_of_vaporization_kj_kgmole	焓值相关
bubble_point_pressure_bar	泡点数据
第十五部分：枚举定义汇总（V3.0完整版）
15.1 VesselPosition
HORIZONTAL/VERTICAL

15.2 StructuralType（球罐）
MIXED/ORANGE_PEEL/FOOTBALL

15.3 TrayType
FLOATING_VALVE/SIEVE/BUBBLE_CAP/BAFFLE

15.4 HeadType
ELLIPSOIDAL/HEMISPHERICAL/TORISPHERICAL/FLAT

15.5 SupportType
SADDLE/SKIRT/LEG/RING

15.6 VesselClass
CLASS_I/CLASS_II/CLASS_III/NON_CLASSIFIED

15.7 DraftType（空冷器通风方式）
INDUCED_DRAFT/FORCED_DRAFT

15.8 ACHEType（空冷器型式）
COMPOSITE_AIR_COOLED/SINGLE_AIR_COOLED

15.9 TubeType（换热管类型）
PLAIN/LOW_FIN/HIGH_FIN

15.10 FinType（翅片型式）
L_FIN/LL_FIN/KL_FIN/G_FIN/EXTRUDED_FIN

15.11 ValveType（阀门类型）
GLOBE/BALL/BUTTERFLY/GATE/CHECK/PLUG/DIAPHRAGM/NEEDLE

15.12 BodyType（调节阀类型）
SINGLE_SEAT/DOUBLE_SEAT/SLEEVE_GUIDED/HIGH_PRESSURE_SLEEVE_GUIDED/CAGE_GUIDED/ECCENTRIC_ROTARY/CAGE_DOUBLE_SEAT

15.13 FlowRating（流量特性）
EQUAL_PERCENT/LINEAR/QUICK_OPEN

15.14 EndConnection（连接方式）
FLANGE/WAFER/WELD/THREAD

15.15 SeatLeakage（泄漏等级）
CLASS_I/II/III/IV/V/VI

15.16 ActuatorType（执行机构）
PNEUMATIC_DIAPHRAGM/PNEUMATIC_PISTON/ELECTRIC/HYDRAULIC/SELF_OPERATED

15.17 Action（作用形式）
DIRECT/REVERSE/SINGLE_ACTING/DOUBLE_ACTING

15.18 FailPosition（开关阀故障状态）
OPEN/CLOSE/LOCK

15.19 FailAction（调节阀故障状态）
FC/FO

15.20 ControlMode（自力式调节方式）
PRESSURE_REGULATING/PRESSURE_REDUCING/PRESSURE_RELIEF/DIFFERENTIAL_PRESSURE/TEMPERATURE_REGULATING

15.21 TrimType（阀芯型式）
SINGLE_SEAT_V/SLEEVE/CAGE/PARABOLIC

15.22 BonnetType（阀盖类型）
STANDARD/RADIATION_FIN/BELLOWS_SEALED/EXTENDED/BOLTED_P_TYPE

15.23 FlowDirection（流体流向）
FLOW_TO_OPEN/FLOW_TO_CLOSE

15.24 ConversionFunction（转换特性）
LINEAR/EQUAL_PERCENT/CUSTOM

15.25 FlowUnit（流量单位）
KG_H/NM3_H/M3_H

15.26 PumpType（泵型，API 610）
OH1/OH2/BB1/BB2/BB3/BB4/BB5/VS1/VS4

15.27 CasingType（泵壳型式）
BETWEEN_BEARINGS/OVERHUNG

15.28 DriveMode（传动方式）
STRAIGHT/BELT/GEAR

15.29 Rotation（转向）
CW/CCW

15.30 ImpellerType（叶轮型式）
CLOSED/SEMI_OPEN/OPEN

15.31 CasingMounting（安装方式）
CENTERLINE/FOOT

15.32 CasingSplit（剖分型式）
AXIAL/RADIAL

15.33 SealFlushPlan（密封冲洗方案）
PLAN_11/PLAN_21/PLAN_23/PLAN_32/PLAN_52/PLAN_53A/PLAN_53B/PLAN_54

15.34 LubricationMethod（润滑方式）
GREASE/OIL_BATH/RING_OIL/FLINGER/PURGE_OIL_MIST/PURE_OIL_MIST

15.35 CraneType（起重机类型）
ELECTRIC_DOUBLE_GIRDER_BRIDGE/ELECTRIC_SINGLE_GIRDER_BRIDGE/GANTRY/JIB/MONORAIL/HOIST/OVERHEAD_CRANE

15.36 OperatingGrade（工作制度）
A1~A8

15.37 PowerIntroductionMethod（电源引入）
CABLE/SLIDING_CONTACT_LINE/CABLE_REEL

15.38 OperatingMethod（操纵方式）
GROUND/CAB/REMOTE/AUTO

15.39 FlowmeterType（流量计类型）
FE/FT/FQ

15.40 FilterType（过滤器类型）
Y_TYPE/T_TYPE/BASKET_OFFSET/PLATE_FRAME/ROTARY_DRUM/BELT/DEEP_BED

15.41 MaterialGrade（泵材料等级）
S-1/S-2/A-1/A-2/A-3/A-4/A-5/A-6/A-7

第十六部分：版本历史
版本	日期	修改内容
V1.0	2026-08-29	初始版本（FLASH/PIPE_NET/FLARE_SYS/PSYCHRO/OPEN_CHANNEL/SEP_EQUIP/FILTRATION）
V1.1	2026-08-29	增补容器数据表（SUP-001）
V1.2	2026-08-29	增补板式塔数据表（SUP-002）
V1.3	2026-08-29	增补球罐+反应器数据表（SUP-003）
V1.4	2026-08-29	增补阀门数据表（SUP-004）
V1.5	2026-08-29	增补起重设备数据表（SUP-005）
V1.6	2026-08-29	增补液力透平数据表（SUP-006）
V1.7	2026-08-29	增补节流装置/调节阀设计条件（SUP-007）
V2.0	2026-08-29	完整整合版
V1.8	2026-08-29	增补仪表规格书+FF总线（SUP-008）
V1.9	2026-08-29	增补计算+规格合并表（SUP-009）
V1.10	2026-08-29	增补批量开关阀汇总（SUP-010）
V1.11	2026-08-29	增补流量计批量表+调节阀批量扩展+HYSYS物性（SUP-011）
V3.0	2026-08-29	完整整合版：V2.0+SUP-001~011全部合并，40组枚举汇总
PCS-DICT-007 V3.0完。 本文档作为计算模块JSON结构的唯一权威字典，覆盖：

内容	章节
VESSEL模块（4种设备类型）	第二部分
HEAT空冷器	第三部分
FLASH/PIPE_NET/FLARE_SYS/PSYCHRO/OPEN_CHANNEL/SEP_EQUIP/FILTRATION	第四~十部分
CV/RESTRICTION/流量计（9种文档格式）	第十一部分
PUMP液力透平	第十二部分
起重设备	第十三部分
SIM/HYSYS物性	第十四部分
40组枚举	第十五部分
P4-P6阶段各计算模块开发严格以此为准。
