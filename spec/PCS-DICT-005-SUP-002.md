PCS-DICT-005 增补文件
文件标识	PCS-DICT-005-SUP-002
当前版本	V1.2
发布日期	2026-08-29
增补基准	PCS-DICT-005 V1.1（含SUP-001介质特性数据）
新增参考	空冷器数据表实例×2（PR-01/D501，1222-A-101AB催化蒸馏塔塔顶复合式空冷器；PR-01/D502，1222-A-102甲醇回收塔复合式空冷器）
1. 增补说明
1.1 新增素材价值
两份素材是复合式空冷器（引风式）的完整数据表实例，补充了heat_results表中空冷器类型（exchanger_category=AIR_COOLED）的详细数据表结构。此前V3.0已定义了空冷器的JSON子结构框架（air_side_json/design_conditions_json/enthalpy_table_json等），本增补将其扩展为完整的工程数据表JSON：

维度	V3.0已定义	本增补新增
空冷器类型	AIR_COOLED枚举	复合式空冷/引风式具体型式
工艺条件	管程参数框架	气液混相完整参数（总流量/气液相分流量/进出口条件）
传热性能	heat_transfer_json	光管/翅片管双口径传热速率+EMTD+Ft
冷凝曲线	enthalpy_table_json	✅ 6点完整冷凝曲线数据（温度/分率/焓/潜热/气液物性）
空气侧控制	❌	✅ 出口温度控制精度/风机角度/百叶窗/气源气压
结构参数	框架	✅ 管束/构架/风机/驱动机/减速器完整参数
材料	material_json	✅ 16部件完整材料清单
制造检验	❌	✅ 焊接规程/NDE/热处理/硬度检查/酸洗钝化
质量	weights_json	✅ 12项质量分类
开口	connections_json	✅ 管束入口/出口（含配对法兰）
1.2 两份实例对比
参数	1222-A-101AB	1222-A-102
设备名称	催化蒸馏塔塔顶复合式空冷器	甲醇回收塔复合式空冷器
数量	2台	1台
总流量	36149 kg/h	2093 kg/h
进口温度	59°C	74°C
出口温度	40°C	40°C
进口压力	0.50 MPaG	0.03 MPaG
气相分率(进/出)	97.5/0 wt%	100/0.5 wt%
介质相态	气液混相	气液混相
2. 空冷器数据表完整JSON结构（ache_data_sheet_json）
2.1 顶层结构
json
{
  "general": {},                    // 概况
  "process_design": {},            // 工艺设计条件
  "heat_transfer": {},             // 传热性能
  "controls_air_side": {},         // 空气侧控制要求
  "construction": {},              // 结构参数（管束/构架/风机/驱动机/减速器）
  "mechanical_design": {},         // 机械设计条件
  "materials": {},                 // 材料
  "fabrication_inspection": {},    // 制造与检验
  "weights": {},                   // 质量
  "nozzles": [],                   // 开口说明
  "condensation_curve": {},        // 介质冷凝曲线数据
  "remarks": [],                   // 备注
  "sketch_ref": null               // 平台简图引用
}
2.2 general（概况）
字段名	类型	必填	说明
item_number	string	✅	设备编号（如1222-A-101AB）
service	string	✅	设备名称
quantity	int	✅	数量
model_spec	string	❌	型号/规格
draft_type	enum	✅	INDUCED_DRAFT（引风式）/FORCED_DRAFT（鼓风式）
exchanger_type	enum	✅	COMPOSITE_AIR_COOLED（复合式空冷）
pid_no	string	✅	流程图图号
position	enum	✅	HORIZONTAL/VERTICAL
operating_mode	enum	❌	CONTINUOUS/INTERMITTENT/SPARE
doc_no	string	✅	文表号
rev	string	✅	版次
applicable_to	enum[]	❌	PROPOSAL/PURCHASE/DESIGN/CONSTRUCTION/AS_BUILT
2.3 process_design（工艺设计条件）
json
{
  "process_design": {
    "tube_side": {
      "fluid_name": "塔顶油气",
      "toxicity_level": "轻度危害",
      "explosive_fluid": true,
      "fluid_state": "GAS_LIQUID_MIXED",
      "total_flow_kg_h": 36149,
      "liquid_flow_in_out_kg_h": {"in": 35245, "out": 0},
      "vapor_flow_in_out_kg_h": {"in": 904, "out": 36149},
      "inlet_temp_c": {"max": 59, "normal": null, "min": null},
      "outlet_temp_c": {"max": 40, "normal": null, "min": null},
      "inlet_pressure_mpag": {"max": 0.50, "normal": null, "min": null},
      "pressure_drop_kpa": {"allowable": 50, "calculated": null},
      "velocity_m_s": {"allowable": null, "calculated": null},
      "film_coefficient_w_m2k": null,
      "fouling_resistance_m2k_w": 0.000180,
      "vapor": {
        "molecular_weight": null,
        "density_in_out_kg_m3": {"in": 13.835, "out": 14.198},
        "viscosity_in_out_mpa_s": {"in": 0.0089, "out": 0.0088},
        "specific_heat_in_out_kj_kg_c": {"in": 1.799, "out": 1.794},
        "thermal_conductivity_in_out_w_mc": {"in": 0.0187, "out": 0.0183}
      },
      "liquid": {
        "density_in_out_kg_m3": {"in": 561.19, "out": 569.88},
        "viscosity_in_out_mpa_s": {"in": 0.147, "out": 0.15},
        "specific_heat_in_out_kj_kg_c": {"in": 2.7227, "out": 2.5526},
        "thermal_conductivity_in_out_w_mc": {"in": 0.0961, "out": 0.1002}
      },
      "enthalpy_in_out_kj_kg": {"in": 97.5, "out": 0},
      "vapor_fraction_in_out_wt_pct": {"in": 97.5, "out": 0},
      "max_h2_partial_pressure_mpaa": null,
      "max_h2s_partial_pressure_mpaa": null,
      "dew_point_c": null,
      "pour_point_c": null,
      "bubble_point_c": null,
      "freeze_point_c": null,
      "condensation_curve_ref": "See Page 5"
    },
    "air_side": {
      "fluid_name": "空气",
      "inlet_temp_c": 40,
      "design_ambient_temp_c": null,
      "altitude_m": null
    }
  }
}
管侧/空气侧字段统一：

字段组	字段名	类型	必填	单位	说明
管侧基础	fluid_name	string	✅	—	介质名称
toxicity_level	enum	❌	—	毒性程度
explosive_fluid	bool	❌	—	易爆介质
fluid_state	enum	✅	—	GAS/LIQUID/GAS_LIQUID_MIXED
total_flow_kg_h	float	✅	kg/h	总流量
liquid_flow_in_out_kg_h	object	❌	kg/h	{in, out}
vapor_flow_in_out_kg_h	object	❌	kg/h	{in, out}
温度压力	inlet_temp_c	object	✅	°C	{max, normal, min}
outlet_temp_c	object	✅	°C	{max, normal, min}
inlet_pressure_mpag	object	✅	MPaG	{max, normal, min}
pressure_drop_kpa	object	❌	kPa	{allowable, calculated}
气相物性	vapor.molecular_weight	float	❌	g/mol	分子量
vapor.density_in_out_kg_m3	object	❌	kg/m³	{in, out}
vapor.viscosity_in_out_mpa_s	object	❌	mPa·s	{in, out}
vapor.specific_heat_in_out_kj_kg_c	object	❌	kJ/kg·°C	{in, out}
vapor.thermal_conductivity_in_out_w_mc	object	❌	W/m·°C	{in, out}
液相物性	liquid.density_in_out_kg_m3	object	❌	kg/m³	{in, out}
liquid.viscosity_in_out_mpa_s	object	❌	mPa·s	{in, out}
liquid.specific_heat_in_out_kj_kg_c	object	❌	kJ/kg·°C	{in, out}
liquid.thermal_conductivity_in_out_w_mc	object	❌	W/m·°C	{in, out}
焓/分率	enthalpy_in_out_kj_kg	object	❌	kJ/kg	{in, out}
vapor_fraction_in_out_wt_pct	object	❌	wt%	{in, out}
腐蚀	max_h2_partial_pressure_mpaa	float	❌	MPaA	
max_h2s_partial_pressure_mpaa	float	❌	MPaA	
other_corrosive_agent_mol_pct	float	❌	mol%	
相变	dew_point_c	float	❌	°C	露点
pour_point_c	float	❌	°C	倾点
bubble_point_c	float	❌	°C	泡点
freeze_point_c	float	❌	°C	凝点
2.4 heat_transfer（传热性能）
字段名	类型	必填	单位	说明
transfer_rate_bare_fin_w_m2k	float	❌	W/m²·K	光管/翅片管传热速率
static_press_drop_kpa	float	❌	kPa	空气侧静压降
mass_velocity_air_kg_s_m2	float	❌	kg/s·m²	空气侧质量流速
overall_heat_duty_kw	float	❌	kW	总热负荷
emtd_c	float	❌	°C	有效传热温差
correction_factor_ft	float	❌	—	温差校正系数
overall_htc_w_m2k	object	❌	W/m²·K	{clean, fouled}（基于翅片管总面积）
calc_area_m2	object	❌	m²	{bare_tube, finned_tube}
employed_area_m2	object	❌	m²	{bare_tube, finned_tube}
area_per_bundle_m2	object	❌	m²	{bare_tube, finned_tube}
total_bundles	int	❌	—	总片数
overdesign_pct	float	❌	%	面积余量
face_velocity_m_s	float	❌	m/s	迎风面风速
2.5 controls_air_side（空气侧控制要求）
json
{
  "outlet_temp_control": {
    "degree_control_c": null,        // 控制精度 ±°C
    "max_cooling_c": null            // 最大冷却
  },
  "action_on_signal_failure": null,  // 控制信号失败时动作
  "fan_pitch": {
    "type": null,                    // 自动/手动
    "angle_degrees": null
  },
  "louvers": {
    "installed": null,
    "location": null,
    "action_control": null,
    "action_type": null,
    "positioner": null
  },
  "actuator_air_supply": {
    "max_mpag": null,
    "min_mpag": null
  },
  "signal_air_range": {
    "max_mpag": null,
    "min_mpag": null
  },
  "air_recirculation": null
}
2.6 construction（结构参数）
json
{
  "tube_bundle_header": {
    "bundle_size_lxw_m": null,
    "bundle_thickness_mm": null,
    "bundles_per_bay": null,
    "rows_passes": null,
    "series_parallels": null,
    "tube_layout": null,
    "tube_type": null,
    "tube_count_per_bundle": null,
    "bare_tube_od_mm": null,
    "pitch_mm": null,
    "tube_length_m": null,
    "fin_od_mm": null,
    "fin_height_mm": null,
    "fin_type": null,
    "fin_thickness_mm": null,
    "fin_bare_ratio": null,
    "fin_spacing_mm": null,
    "fins_per_m": null,
    "header_type": null,
    "header_slope_mm_m": null
  },
  "bay": {
    "bay_type": null,
    "bay_size_lxw_m": null,
    "bay_model": null,
    "bay_count": null,
    "pipereck_beams_cc_m": null,
    "structure_mounting": null
  },
  "louver": {
    "size_m": null,
    "qty": null
  },
  "fan": {
    "type": null,
    "qty": null,
    "per_bay": null,
    "speed_rpm": null,
    "shaft_power_kw": null,
    "pitch_adjustment": null,
    "blade_angle_deg": null,
    "blade_count": null,
    "diameter_m": null,
    "max_tip_speed_m_s": null,
    "air_flow_per_fan_m3": null,
    "noise_dba": {"allowable": null, "calculated": null}
  },
  "driver": {
    "type": null,
    "qty": null,
    "per_bay": null,
    "speed_rpm": null,
    "power_kw": null,
    "service_factor": null,
    "explosion_proof_grade": "dIIBT4",
    "guard_insulation": "IP55/F",
    "variable_speed_motor": true,
    "on_stream_factor_h_a": 8000,
    "voltage_v": 380,
    "phase": 3,
    "frequency_hz": 50
  },
  "speed_reducer": {
    "type": null,
    "qty": null,
    "speed_ratio": null,
    "service_factor": null,
    "per_bay": null,
    "support": null,
    "enclosure": null,
    "vibration_switch": null
  }
}
2.7 mechanical_design（机械设计条件）
字段名	类型	必填	单位	说明
codes_specs	string	❌	—	执行标准（GB150 NB/T47007）
design_wind_pressure_pa	float	❌	Pa	基本风压（850）
exposure_category	string	❌	—	地面粗糙度类别
seismic_intensity_degree	int	❌	度	抗震设防烈度（7）
earthquake_response_accel_g	float	❌	g	基本加速度（0.1）
site_class	string	❌	—	场地土类别（Ⅱ类）
seismic_group	string	❌	—	设计地震分组（第一组）
design_pressure_mpa	float	❌	MPa	设计压力
design_temp_c	float	❌	°C	设计温度
fin_tube_design_temp_c	float	❌	°C	翅片管设计温度
mdmt_c	float	❌	°C	金属最低设计温度
corrosion_allowance_mm	float	❌	mm	腐蚀裕量
joint_efficiency	float	❌	—	焊接接头系数
tube_tubesheet_joint	string	❌	—	管子与管板连接
2.8 materials（材料，16部件）
json
{
  "header": {"material": null, "std": null},
  "tubesheet": {"material": null, "std": null},
  "partition": {"material": null, "std": null},
  "tube": {"material": null, "std": null},
  "fin": {"material": null, "std": null},
  "cover_plate": {"material": null, "std": null},
  "plug": {"material": null, "std": null},
  "gasket": {"material": null, "std": null},
  "bay": {"material": null, "std": null},
  "nozzle": {"material": null, "std": null},
  "nozzle_flange": {"material": null, "std": null},
  "louver": {"material": null, "std": null},
  "fan_blade": {"material": null, "std": null},
  "hub": {"material": null, "std": null},
  "bolt_external": {"material": null, "std": null},
  "nut_external": {"material": null, "std": null},
  "platform": {"material": null, "std": null},
  "steel_plate_application": null,
  "steel_plate_ut": null
}
2.9 fabrication_inspection（制造与检验）
字段名	类型	必填	说明
welding_specification	string	❌	焊接规程
nde_joints	object	❌	{rt: bool, ut: bool, mt: bool, pt: bool}
nde_tube_tubesheet	string	❌	管头无损检测
postweld_heat_treatment	bool	❌	焊后热处理
hardness_test	bool	❌	焊缝硬度检查
pickling_passivation	bool	❌	管箱酸洗钝化
hydro_test_pressure_mpa	float	❌	液压试验压力
gas_leak_test_pressure_mpa	float	❌	气密性试验压力
coating_packing_transport	string	❌	涂敷与运输包装
drawing_language	string	❌	图纸使用语言
nameplate_language	string	❌	铭牌使用语言
nameplate_location	string	❌	铭牌位置
2.10 weights（质量，12项）
字段名	类型	必填	单位	说明
tube_bundles_kg	float	❌	kg	管束质量
operating_fluid_kg	float	❌	kg	操作介质重
water_kg	float	❌	kg	充水质量
bays_kg	float	❌	kg	构架质量
louvers_kg	float	❌	kg	百叶窗质量
heating_coils_kg	float	❌	kg	加热盘管质量
spray_equipment_kg	float	❌	kg	喷淋装置质量
fans_kg	float	❌	kg	风机质量
motors_kg	float	❌	kg	电机质量
reductors_kg	float	❌	kg	减速器质量
platforms_ladders_kg	float	❌	kg	平台梯子重
system_total_kg	float	❌	kg	空冷器系统总重
plot_area_lxw_m	string	❌	m×m	设备占地面积
2.11 nozzles（开口说明）
数组格式：

字段名	类型	必填	说明
mark	string	✅	管口编号
service	string	✅	名称（管束入口/管束出口）
quantity	int	✅	数量
pressure_class	string	❌	公称压力Class
size_dn	string	❌	公称直径DN（厂家定/计算）
mating_flange_required	bool	❌	配对法兰要求（带Yes）
flange_std	string	❌	法兰标准（HG/T20615）
remark	string	❌	备注
2.12 condensation_curve（介质冷凝曲线数据）——空冷器特有
来源：数据表Page 5 "介质冷凝曲线数据 FLUID PROPERTIES"

json
{
  "condensation_curve": {
    "points": [
      {
        "point_no": 1,
        "position": "INLET",
        "temperature_c": 58.875,
        "vapor_weight_fraction": 0.975,
        "enthalpy_kj_kg": 0.0,
        "latent_heat": 357.53,
        "vapor": {
          "density_kg_m3": 13.835,
          "viscosity_mpa_s": 0.0089,
          "specific_heat_kj_kg_c": 1.799,
          "thermal_conductivity_w_mc": 0.0187
        },
        "liquid": {
          "density_kg_m3": 561.19,
          "viscosity_mpa_s": 0.147,
          "specific_heat_kj_kg_c": 2.7227,
          "thermal_conductivity_w_mc": 0.0961
        },
        "surface_tension_mn_m": 10.568
      }
    ],
    "molecular_weight": null,
    "critical_temp_c": null,
    "critical_pressure_mpaa": null
  }
}
冷凝曲线point字段定义：

字段名	类型	必填	单位	说明
point_no	int	✅	—	序号（1=入口，N=出口）
position	enum	✅	—	INLET/INTERMEDIATE/OUTLET
temperature_c	float	✅	°C	温度
vapor_weight_fraction	float	✅	wt%	气相质量分率
enthalpy_kj_kg	float	✅	kJ/kg	热焓
latent_heat	float	✅	kJ/kg	潜热
vapor.density_kg_m3	float	❌	kg/m³	气相密度
vapor.viscosity_mpa_s	float	❌	mPa·s	气相粘度
vapor.specific_heat_kj_kg_c	float	❌	kJ/kg·°C	气相比热容
vapor.thermal_conductivity_w_mc	float	❌	W/m·°C	气相导热系数
liquid.density_kg_m3	float	❌	kg/m³	液相密度
liquid.viscosity_mpa_s	float	❌	mPa·s	液相粘度
liquid.specific_heat_kj_kg_c	float	❌	kJ/kg·°C	液相比热容
liquid.thermal_conductivity_w_mc	float	❌	W/m·°C	液相导热系数
surface_tension_mn_m	float	❌	mN/m	表面张力
3. 与V3.0 heat_results JSON子结构的映射
V3.0 heat_results字段	ache_data_sheet_json字段
general_parameters_json	general
performance_data_json	process_design.tube_side
heat_transfer_json	heat_transfer
air_side_json	process_design.air_side
design_conditions_json	mechanical_design
material_json	materials
connections_json	nozzles
enthalpy_table_json	condensation_curve
notes_json	remarks
weights_json	weights
4. 完整示例数据（1222-A-101AB）
json
{
  "general": {
    "item_number": "1222-A-101AB",
    "service": "催化蒸馏塔塔顶复合式空冷器",
    "quantity": 2,
    "draft_type": "INDUCED_DRAFT",
    "exchanger_type": "COMPOSITE_AIR_COOLED",
    "pid_no": "PR-02/107",
    "position": "HORIZONTAL",
    "doc_no": "PR-01/D501",
    "rev": "1"
  },
  "process_design": {
    "tube_side": {
      "fluid_name": "塔顶油气",
      "toxicity_level": "轻度危害",
      "explosive_fluid": true,
      "fluid_state": "GAS_LIQUID_MIXED",
      "total_flow_kg_h": 36149,
      "liquid_flow_in_out_kg_h": {"in": 35245, "out": 0},
      "vapor_flow_in_out_kg_h": {"in": 904, "out": 36149},
      "inlet_temp_c": {"max": 59, "normal": null, "min": null},
      "outlet_temp_c": {"max": 40, "normal": null, "min": null},
      "inlet_pressure_mpag": {"max": 0.50, "normal": null, "min": null},
      "pressure_drop_kpa": {"allowable": 50, "calculated": null},
      "fouling_resistance_m2k_w": 0.000180,
      "enthalpy_in_out_kj_kg": {"in": 97.5, "out": 0},
      "vapor_fraction_in_out_wt_pct": {"in": 97.5, "out": 0}
    },
    "air_side": {
      "fluid_name": "空气",
      "inlet_temp_c": 40
    }
  },
  "remarks": [
    "最热月平均气温28.4°C，绝对最高气温36.8°C",
    "操作弹性为70%~120%，要求空冷器在任何工况下设计余量不低于20%",
    "制造厂提供空冷器操作平台(含直梯)"
  ]
}
5. 枚举定义
5.1 DraftType（通风方式）
枚举值	中文
INDUCED_DRAFT	引风式
FORCED_DRAFT	鼓风式
5.2 ACHEType（空冷器型式）
枚举值	中文
COMPOSITE_AIR_COOLED	复合式空冷
SINGLE_AIR_COOLED	单一式空冷
5.3 TubeType（管子类型）
枚举值	中文
PLAIN	光管
LOW_FIN	低翅片管
HIGH_FIN	高翅片管
5.4 HeaderType（管箱型式）
枚举值	中文
PLUG_TYPE	丝堵型
COVER_PLATE_TYPE	盖板型
MANIFOLD_TYPE	集合管型
5.5 FinType（翅片型式）
枚举值	中文
L_FIN	L型缠绕翅片
LL_FIN	LL型缠绕翅片
KL_FIN	KL型滚轧翅片
G_FIN	G型镶嵌翅片
EXTRUDED_FIN	整体挤压翅片
6. 版本历史
版本	日期	修改内容
V1.0	2026-08-29	初始版本（组成/物性/馏程/SARA/虚拟组分）
V1.1	2026-08-29	增补介质特性数据表结构（SUP-001）
V1.2	2026-08-29	增补空冷器数据表结构（SUP-002），新增ache_data_sheet_json 13个子结构+冷凝曲线+5组枚举
增补完成。 PCS-DICT-005现覆盖：

内容	章节
物流组成（Composition_JSON）	V1.0
虚拟组分（Pseudo-Component）	V1.0
馏程/SARA/元素/金属	V1.0
物性估算（PropertyEstimation）	V1.0
介质特性数据表（FluidProperty）	SUP-001
空冷器数据表（ACHE Data Sheet）	SUP-002
P5阶段HEAT模块空冷器数据表生成以此为准。
