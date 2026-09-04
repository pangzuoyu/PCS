PCS-DICT-007 增补文件六
文件标识	PCS-DICT-007-SUP-006
当前版本	V1.6
发布日期	2026-08-29
增补基准	PCS-DICT-007 V2.0 + SUP-004（阀门）+ SUP-005（起重机）
新增参考	离心泵/液力透平数据表实例（PR-01/D702，项目1216B132，液力透平132-P-101-T，API 610 BB5型）
1. 增补说明
1.1 新增素材价值
本素材是液力透平（Hydraulic Power Recovery Turbine）的完整数据表实例，作为泵的驱动机使用（132-P-101A的驱动机）。这是转动设备中结构最复杂的数据表类型：

维度	已有设备类型	本增补（透平）
设备类型	容器/塔/球罐/阀门/起重机	液力透平（API 610 BB5）
工况定义	单工况/多工况	三工况：初期SOR/末期EOR/最大MAX
特有字段	—	NPSHa/NPSHr、轴功率、效率、优先工作区
密封系统	—	API 682机械密封+Plan 23/53B冲洗方案
轴承润滑	—	API 610压力润滑系统
联轴器	—	API 671
振动监测	—	API 670非接触式
防爆分类	简单	Class IIC / Group T4 / Div 2完整三级
材料等级	普通	A-7级（高合金：321SS/347SS）
供货范围	无	15项完整清单
试验检验	简单	6项试验+4种NDE+锻铸件检查
2. 透平数据表完整JSON结构（turbine_data_sheet_json）
2.1 顶层结构
json
{
  "general": {},                 // 概况
  "operating_conditions": {},    // 操作条件（三工况）
  "site_utility": {},            // 现场及公用工程条件
  "construction": {},            // 结构
  "impeller_shaft": {},          // 叶轮/轴
  "coupling": {},                // 联轴器
  "bearings_lubrication": {},    // 轴承及润滑
  "mechanical_seal": {},         // 机械密封
  "instrumentation": {},         // 仪表
  "cooling_steam_piping": {},    // 冷却水和蒸汽管路
  "driver": {},                  // 驱动机
  "performance": {},             // 泵性能
  "test_inspection": {},         // 试验和检验
  "materials": {},               // 材料
  "scope_of_supply": {},         // 供货范围
  "weight_contour": {},          // 质量及外形
  "notes": [],                   // 备注
  "field_annotations": {}        // 字段来源标记
}
2.2 general（概况）
字段名	类型	必填	说明
item_number	string	✅	设备编号（如132-P-101-T）
service	string	✅	设备名称（如液力透平）
model	string	❌	型号
quantity	int	✅	数量（1台）
quantity_operating	int	❌	操作数（1）
quantity_spare	int	❌	备用数（0）
pid_no	string	❌	流程图图号
inlet_pipeline_no	string	❌	入口管道号
operating_mode	enum	❌	CONTINUOUS/INTERMITTENT
parallel_operation_required	bool	❌	需要并联运行
pumps_in_parallel	int	❌	泵并联运行台数
series_operation	bool	❌	泵串联运行
pump_item_no	string	❌	泵位号
gear_item_no	string	❌	齿轮装置位号
motor_item_no	string	❌	电动机位号
turbine_item_no	string	❌	汽轮机位号
gear_provided_by	string	❌	齿轮装置供货商
motor_provided_by	string	❌	电动机供货商
turbine_provided_by	string	❌	汽轮机供货商
gear_mounted_by	string	❌	齿轮装置安装者
motor_mounted_by	string	❌	电动机安装者
turbine_mounted_by	string	❌	汽轮机安装者
gear_data_sheet_no	string	❌	齿轮装置数据表编号
motor_data_sheet_no	string	❌	电动机数据表编号
turbine_data_sheet_no	string	❌	汽轮机数据表编号
2.3 operating_conditions（操作条件）
json
{
  "operating_conditions": {
    "fluid_name": "碳氢化合物",
    "fluid_characteristic": {
      "flammable": "INFLAMMABLE",
      "hazardous": "MIDDLE",
      "specific_heat_kj_kg_c": null,
      "rigid_granules_ppmw": null,
      "max_h2_mg_l": null,
      "max_h2s_mg_l": null,
      "max_chloride_ppmw": null,
      "other_corrosive_agent_mol_pct": null
    },
    "cases": [
      {
        "case_name": "SOR",
        "is_governing": false,
        "pumping_temp_c": 286,
        "vapor_pressure_mpaa": null,
        "density_kg_m3": 600,
        "viscosity_mpa_s": 0.14,
        "flow_rate_m3h": 436.9,
        "suction_pressure_mpag": 13.36,
        "discharge_pressure_mpag": 2.99,
        "efficiency_pct": null,
        "diff_head_m": null,
        "npsha_m": null,
        "shaft_power_kw": 1629
      },
      {
        "case_name": "EOR",
        "is_governing": true,
        "pumping_temp_c": 287,
        "vapor_pressure_mpaa": null,
        "density_kg_m3": 600,
        "viscosity_mpa_s": 0.14,
        "flow_rate_m3h": 432.7,
        "suction_pressure_mpag": 13.37,
        "discharge_pressure_mpag": 2.99,
        "efficiency_pct": null,
        "diff_head_m": null,
        "npsha_m": null,
        "shaft_power_kw": 1614.7
      },
      {
        "case_name": "MAX",
        "is_governing": false,
        "pumping_temp_c": null,
        "vapor_pressure_mpaa": null,
        "density_kg_m3": null,
        "viscosity_mpa_s": null,
        "flow_rate_m3h": null,
        "suction_pressure_mpag": null,
        "discharge_pressure_mpag": null,
        "efficiency_pct": null,
        "diff_head_m": null,
        "npsha_m": null,
        "shaft_power_kw": null
      }
    ],
    "max_suction_temp_c": 300,
    "max_suction_pressure_mpag": 13.37,
    "starting_conditions": null
  }
}
2.4 site_utility（现场及公用工程条件）
字段名	类型	必填	说明
installation_location	object	❌	安装位置（室内/室外/有棚/双层等）
electric_area_classification	object	✅	防爆区分类
winterization_required	bool	❌	要求防冻
tropicalization_required	bool	❌	要求防潮湿
elevation_m	float	❌	海拔高度
ambient_temp	object	✅	{min_c, max_c}
barometer_kpaa	float	❌	大气压
relative_humidity	object	❌	{min_pct, max_pct}
unusual_conditions	object	❌	特殊条件（粉尘/烟雾/其他）
utilities	object	❌	公用工程
electric_area_classification子结构：

json
{
  "class": "IIC",
  "group": "T4",
  "division": 2
}
utilities子结构：

json
{
  "steam": {"hs": null, "ms": null, "ls": null, "lls": null},
  "electricity": {"voltage_v": 10000, "frequency_hz": 50, "phase": 3},
  "cooling_water": {
    "supply_temp_c": 33,
    "max_return_temp_c": 43,
    "normal_pressure_mpag": 0.4,
    "design_pressure_mpag": null,
    "max_allowable_dp_mpa": null,
    "min_return_pressure_mpag": 0.2,
    "water_source": "CW",
    "chloride_ppmw": null
  },
  "instrument_air_pressure_mpag": 0.7,
  "nitrogen_pressure_mpag": 0.85,
  "flare_back_pressure_mpag": 0.15
}
2.5 construction（结构）
字段名	类型	必填	说明
applicable_standard	string	✅	应用标准（API 610 11th Ed.）
pump_type	enum	✅	泵型（BB5）
nozzles	array	✅	管口接头
flange_joint_std	string	❌	法兰连接标准
cylindrical_threads_required	bool	❌	要求圆柱螺纹
casing_mounting	enum	❌	安装方式（CENTERLINE中心线）
casing_position	enum	❌	卧式/立式
casing_split	enum	❌	剖分型式（RADIAL径向）
casing_type	enum	❌	泵壳型式（BETWEEN_BEARINGS两端支撑式）
rotation	enum	❌	转向（CW/CCW，从联轴器端看）
impellers_individually_secured	bool	❌	叶轮分别独立固定
max_allowable_working_pressure_mpag	float	❌	最大允许工作压力
maap_temp_c	float	❌	MAWP对应温度
hydrotest_pressure_mpag	float	❌	水压试验压力
suction_pressure_regions_mawp	bool	❌	吸入压力区按MAWP设计
drive_mode	enum	❌	传动方式（STRAIGHT直联）
nozzles子结构：

json
[
  {
    "mark": "SUCTION",
    "service": "吸入口",
    "size_dn": null,
    "rating_class": null,
    "mating_flange": "WN/RTJ",
    "position": "VERTICAL"
  },
  {
    "mark": "DISCHARGE",
    "service": "排出口",
    "size_dn": null,
    "rating_class": null,
    "mating_flange": "WN/RTJ",
    "position": "VERTICAL"
  },
  {
    "mark": "BALANCE_DRUM",
    "service": "平衡鼓",
    "position": "VERTICAL"
  }
]
2.6 impeller_shaft（叶轮/轴）
字段名	类型	必填	说明
impeller_od_mm	object	❌	{max, rated}
impeller_type	enum	❌	CLOSED（闭式）
impeller_suction	string	❌	吸入方式
shaft_dia_coupling_mm	float	❌	联轴器处轴径
shaft_dia_between_bearings_mm	float	❌	轴承轴径
span_between_bearings_mm	float	❌	轴承中心间跨距
span_bearings_to_impeller_mm	float	❌	轴承与叶轮间跨距
2.7 coupling（联轴器）
字段名	类型	必填	说明
make	string	❌	结构型式
model	string	❌	型号
limited_end_float_required	bool	❌	要求端面有限浮动
drive_half_mounted_by	enum	❌	PUMP_MFR/DRIVER_MFR/PURCHASER
rating_kw_per_100rpm	float	❌	联轴器等级
lubrication	string	❌	润滑
spacer_length_mm	float	❌	加长段长度
service_factor	float	❌	使用系数
per_api_671	bool	✅	联轴器按API 671
2.8 bearings_lubrication（轴承及润滑）
字段名	类型	必填	说明
radial_bearing_type	string	❌	径向轴承（型式/代号）
thrust_bearing_type	string	❌	止推轴承（型式/代号）
lubrication_method	enum	❌	润滑方式
constant_level_oiler_preferred	bool	❌	恒油位注油器优选
pressure_lube_system	object	❌	强制润滑系统
oil_viscosity_iso_grade	int	❌	润滑油ISO粘度等级
oil_heater	enum[]	❌	加热器（ELECTRIC/STEAM）
oil_pressure_greater_than_coolant	bool	❌	要求油压大于冷却剂压力
pressure_lube_system子结构：

json
{
  "required": null,
  "api_610": null,
  "api_614": null
}
lubrication_method枚举：

枚举值	中文
GREASE	油脂
OIL_BATH	油浴
RING_OIL	油环
FLINGER	抛油环
PURGE_OIL_MIST	吹洗油雾（湿油池）
PURE_OIL_MIST	完全油雾（干油池）
2.9 mechanical_seal（机械密封或软填料）
json
{
  "mechanical_seal": {
    "seal_data": "SEE_API_682",
    "non_api_682_seal": null,
    "seal_classification_code": "BDTXX",
    "seal_code_note": "波纹管",
    "seal_manufacturer": null,
    "size_type": null,
    "manufacturer_code": null,
    "seal_chamber_data": {
      "pressure_mpag": null,
      "temp_c": null,
      "flowrate_m3h": null,
      "chamber_size": null,
      "total_length_mm": null,
      "clear_length_mm": null
    },
    "seal_construction": {
      "sleeve_material": null,
      "gland_material": null,
      "aux_seal_device": null,
      "jacket_required": false
    },
    "gland_taps": {
      "flush_f": null,
      "drain_d": null,
      "buffer_b": null,
      "quench_q": null,
      "cooling_c": null,
      "lubrication_g": null,
      "heating_h": null,
      "leakage": null,
      "pumped_fluid_p": null,
      "balance_fluid_e": null,
      "external_injection_x": null
    },
    "seal_fluids": {
      "name": null,
      "specific_gravity": null,
      "supply_temp_max_min_c": null,
      "vapor_pressure_kpaa": null,
      "hazardous": null,
      "flow_max_min_m3h": null,
      "pressure_required_max_min_kpag": null,
      "temp_required_max_min_c": null
    },
    "buffer_liquid": {
      "name": null,
      "relative_density": null,
      "supply_temp_max_min_c": null,
      "hazardous": null,
      "vapor_pressure_kpaa": null,
      "flowrate_max_min_m3h": null,
      "pressure_required_max_min_kpag": null,
      "temp_required_max_min_c": null
    },
    "quench_liquid": {
      "name": null,
      "flow_rate_m3h": null
    },
    "seal_flush_piping": {
      "plan": "PLAN_23",
      "tubing": null,
      "pipe": null,
      "aux_plan": "PLAN_53B",
      "aux_tubing": null,
      "aux_pipe": null
    },
    "piping_assembly": {
      "threaded": null,
      "unions": null,
      "socket_welded": null,
      "flanged": null,
      "tube_type_fittings": null
    },
    "instruments": {
      "low_pressure_switch_type": null,
      "pressure_gauge": null,
      "low_level_switch_type": null,
      "level_gauge": null,
      "temp_indicator_type": null,
      "heat_exchanger": null
    }
  }
}
密封分类编码说明：

编码位置	含义	示例值
第1位	密封类型	B=平衡型
第2位	旋转/静止	D=旋转式
第3位	弹簧型式	T=多弹簧
第4-5位	辅助装置	XX=无
Seal Flush Piping Plan枚举：

枚举值	说明
PLAN_11	从泵出口经孔板到密封
PLAN_21	从泵出口经冷却器到密封
PLAN_23	闭式循环（泵送环+换热器）
PLAN_32	外供冲洗液
PLAN_52	外部缓冲液储罐（无压）
PLAN_53A	外部隔离液储罐（加压）
PLAN_53B	外部隔离液储罐（气囊加压）
PLAN_54	外供高压隔离液
2.10 instrumentation（仪表）
json
{
  "vibration": {
    "type": "NONCONTACTING_API_670",
    "provision_for_mounting_only": null,
    "see_api_670_data_sheet": null,
    "flat_surface_required": null,
    "transducer": null,
    "monitors_and_cables": null
  }
}
2.11 cooling_steam_piping（冷却水和蒸汽管路）
json
{
  "cooling_water": {
    "piping_plan": "M+支座",
    "seal_jacket_brg_hsg": {"flow_m3h": null, "pressure_mpag": null},
    "seal_heat_exchanger": {"flow_m3h": null, "pressure_mpag": null},
    "quench": {"flow_m3h": null, "pressure_mpag": null},
    "total_flow_m3h": null
  },
  "steam": {
    "type": null,
    "piping": "TUBING",
    "consumption_t_h": null
  }
}
2.12 driver（驱动机）
json
{
  "driver": {
    "motor": {
      "type": null,
      "vvvf_device": null,
      "service_factor": null,
      "on_stream_factor_h_a": null,
      "dcs_display": null,
      "interlock_required": null,
      "starting_voltage_rated_min_v": null,
      "employed_power_kw": null,
      "explosion_proof_grade": null,
      "protection_class": null,
      "insulation_class": null,
      "feeding_in_method": null,
      "no_terminal_boxes": null,
      "speed_rpm": null,
      "restart_batch": null
    },
    "turbine": {
      "type": null,
      "shaft_power_nor_max_kw": null,
      "speed_nor_max_rpm": null,
      "steam_flow_nor_max_kg_h": null,
      "steam_pressure_in_mpag": null,
      "steam_pressure_out_mpag": null,
      "steam_temp_in_c": null,
      "steam_temp_out_c": null,
      "inlet_size_dn": null,
      "outlet_size_dn": null,
      "inlet_pressure_pn": null,
      "outlet_pressure_pn": null,
      "inlet_mating_flange": null,
      "outlet_mating_flange": null,
      "position": null
    }
  }
}
2.13 performance（泵性能）
字段名	类型	必填	单位	说明
proposal_curve_no	string	❌	—	报价单曲线号
rpm	float	❌	r/min	转速
no_stages	int	❌	—	级数
min_continuous_flow_m3h	float	❌	m³/h	最小连续流量
thermal_flow_m3h	float	❌	m³/h	热控流量
stable_flow_m3h	float	❌	m³/h	稳定流量
preferred_operating_region_m3h	object	❌	m³/h	{from, to}
allowable_operating_region_m3h	object	❌	m³/h	{from, to}
npshr_m	float	❌	m	必需汽蚀余量
suction_specific_speed	float	❌	—	汽蚀比转速
est_max_sound_pressure_dba	float	❌	dBA	EST最大声压级
max_sound_pressure_required_dba	float	❌	dBA	要求最大声压级
max_head_rated_impeller_m	float	❌	m	最大扬程
max_power_rated_impeller_kw	float	❌	kW	最大功率
estimated_shutoff_pressure_mpag	float	❌	MPaG	预期关闭压力
2.14 test_inspection（试验和检验）
json
{
  "plant_check": true,
  "complete_machine_test": true,
  "cavitation_test": true,
  "remove_inspect_hydro_bearings": true,
  "performance_test": true,
  "hydraulic_test": true,
  "auxiliary_equipment_test": true,
  "sound_level_test": true,
  "cleanliness_before_final_assembly": true,
  "nde_joints": {
    "rt": true, "ut": true, "mt": true, "pt": true
  },
  "forge_casting_inspection": {
    "rt": true, "ut": true, "mt": true, "pt": true
  }
}
2.15 materials（材料）
json
{
  "material_grade": "A-7",
  "barrel_casing": "321SS/347SS",
  "casing": "321SS/347SS",
  "impeller": "347SS",
  "shaft_shaft_sleeve": "321SS/347SS",
  "abrasion_resistant_ring": null,
  "coupling_spacer_hubs": null,
  "coupling_diaphragms_disks": null,
  "diffusers": null
}
材料等级（Material Grade）说明：

等级	含义	适用工况
S-1	碳钢	一般
S-2	碳钢+内部涂层	轻度腐蚀
A-1	12Cr	中度腐蚀
A-2	304SS	腐蚀
A-3	316SS	强腐蚀
A-4	317SS/316Ti	强腐蚀+高温
A-5	321SS	高温
A-6	347SS	高温+焊接后不热处理
A-7	321SS/347SS	高温+H₂S（抗氢诱导开裂）
2.16 scope_of_supply（供货范围）
json
{
  "pump": true,
  "driver": true,
  "spare_parts": true,
  "special_tools": true,
  "baseplate": true,
  "anchor_bolt": true,
  "belt_pulley_guard": true,
  "operating_spare_parts_2yr": true,
  "coupling_protecting_bush": true,
  "lubricating_oil_system": true,
  "mechanical_seal": true,
  "gland_seal_system": true,
  "comparison_flange_fastener_inlet_outlet": true
}
2.17 weight_contour（质量及外形）
字段名	类型	必填	单位	说明
weight_kg	object	❌	kg	{pump, driver, transmission, baseplate, subtotal}
contour_size	object	❌	mm	{length, width, height}
2.18 notes（备注）
备注键	内容
TURBINE_AS_DRIVER	"透平泵作为进料泵132-P-101A的驱动机使用。Hydraulic power recovery turbine used for driven charge pump 132-P-101A."
CASE_NOTE	"初期工况作为核算工况，末期工况为主工况。SOR as checking case, EOR as governing case."
DETAIL_REF	"详细设计要求见杜邦泵数据表 IT12019-PMP-003（B版）。"
FLANGE_GASKET_FASTENER	"配套法兰采用ANSI B16.5，配套密封件采用ANSI B16.20，配套紧固件采用ASTM A193/ASTM A194。"
3. 枚举定义
3.1 PumpType（泵型，API 610）
枚举值	说明
OH1	悬臂式底脚安装
OH2	悬臂式中心线安装
BB1	两端支撑式单级
BB2	两端支撑式双级
BB3	两端支撑式多级轴向剖分
BB4	两端支撑式多级径向剖分（筒袋）
BB5	两端支撑式多级径向剖分（高压筒袋，本实例）
VS1	立式湿坑
VS4	立式深井
3.2 CasingType（泵壳型式）
枚举值	中文
BETWEEN_BEARINGS	两端支撑式
OVERHUNG	悬臂式
3.3 CasingSplit（剖分型式）
枚举值	中文
AXIAL	轴向剖分
RADIAL	径向剖分
3.4 DriveMode（传动方式）
枚举值	中文
STRAIGHT	直联
BELT	皮带传动
GEAR	齿轮传动
3.5 Rotation（转向）
枚举值	中文
CW	顺时针（从联轴器端看）
CCW	逆时针（从联轴器端看）
3.6 ImpellerType（叶轮型式）
枚举值	中文
CLOSED	闭式
SEMI_OPEN	半开式
OPEN	开式
3.7 CasingMounting（安装方式）
枚举值	中文
CENTERLINE	中心线安装
FOOT	底脚安装
3.8 OperatingMode（操作方式）
枚举值	中文
CONTINUOUS	连续
INTERMITTENT	间断
4. 与pump_results的映射
pump_results字段	turbine_data_sheet_json字段
tag_number	general.item_number
basic_info_json.service	general.service
fluid_properties_json	operating_conditions.fluid_name + .fluid_characteristic
flow_rates_json.normal_capacity_qn	operating_conditions.cases[EOR].flow_rate_m3h
suction_calculation_json	operating_conditions.cases[].suction_pressure_mpag
discharge_calculation_json	operating_conditions.cases[].discharge_pressure_mpag
differential_pressure_json	operating_conditions.cases[].diff_head_m
power_consumption_json.bhp	operating_conditions.cases[].shaft_power_kw
power_consumption_json.pump_efficiency	operating_conditions.cases[].efficiency_pct
actual_npshr	performance.npshr_m
5. 版本历史
版本	日期	修改内容
V1.0~V1.5	2026-08-29	初始+容器+塔+球罐+阀门+起重机
V2.0	2026-08-29	完整整合版
V1.6	2026-08-29	增补液力透平数据表（SUP-006），新增turbine_data_sheet_json 18个子结构+8组枚举+材料等级表
增补完成。 PCS-DICT-007 SUP-006现完整覆盖液力透平数据表结构：

子结构	内容
2.2 general	设备/供货商/安装者完整信息
2.3 operating_conditions	三工况（SOR/EOR/MAX）
2.4 site_utility	防爆三级/公用工程
2.5 construction	API 610 BB5/管口/法兰
2.6 impeller_shaft	叶轮/轴径/跨距
2.7 coupling	API 671
2.8 bearings_lubrication	API 610压力润滑
2.9 mechanical_seal	API 682+Plan 23/53B
2.10 instrumentation	API 670振动
2.11 cooling_steam_piping	冷却水+蒸汽
2.12 driver	电机/汽轮机
2.13 performance	NPSHr/优先工作区
2.14 test_inspection	6项试验+NDE
2.15 materials	A-7等级（321SS/347SS）
2.16 scope_of_supply	15项清单
2.17 weight_contour	质量/外形
2.18 notes	备注
P4阶段PUMP模块数据表生成以此为准。
