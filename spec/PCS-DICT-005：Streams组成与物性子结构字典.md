PCS-DICT-005：Streams组成与物性子结构字典
文件标识	PCS-DICT-005
当前版本	V1.0
发布日期	2026-08-29
关联文档	PCS-DICT-ALL-003 V3.0（表2 streams、表3 stream_state_points）、ADR-0019/0020/0022
1. 目的
定义streams表和stream_state_points表中所有JSON字段的内部结构，包括组成、物性估算、虚拟组分、馏程、SARA、元素分析、金属含量、原料/产品规格。为SIM模块（P3）和FLASH模块（P4）的表单生成和数据校验提供权威依据。

2. Composition_JSON（组成）
2.1 结构定义
json
{
  "basis": "molar",                // molar | mass | volume
  "normalized": true,              // 是否已归一化
  "estimated": false,              // 是否为估算组成
  "components": [
    {
      "material_id": null,         // UUID 引COMMON物性库
      "component_name": null,      // 物质名称（如n-Hexane）
      "formula": null,             // 分子式（如C6H14）
      "mol_fraction": null,        // 摩尔分率
      "mass_fraction": null,       // 质量分率
      "vol_fraction": null         // 体积分率
    }
  ]
}
2.2 校验规则
规则	说明
归一化	所选basis的分率合计=100±0.5%
组分唯一性	同一组分不重复出现
material_id与名称一致性	若填写material_id，系统自动关联物性
虚拟组分标识	若为虚拟组分，component_name以""结尾（如C7）
3. 虚拟组分结构（pseudo_components_json）
json
[
  {
    "name": "C7*",
    "boiling_point_c": 92.2,
    "molecular_weight": 96,
    "liquid_density_kg_m3": 728.1,
    "critical_temp_c": 273.2,
    "critical_pressure_bara": 30.78,
    "critical_volume_m3_kgmole": 0.389,
    "acentricity": 0.3026,
    "boiling_range": {"start_c": null, "end_c": null},
    "source": "USER_INPUT"       // USER_INPUT | AUTO_CUT
  }
]
字段名	类型	必填	单位	说明
name	string	✅	—	虚拟组分名称
boiling_point_c	float	❌	°C	平均沸点
molecular_weight	float	❌	g/mol	分子量
liquid_density_kg_m3	float	❌	kg/m³	液相密度
critical_temp_c	float	❌	°C	临界温度
critical_pressure_bara	float	❌	bara	临界压力
critical_volume_m3_kgmole	float	❌	m³/kgmole	临界体积
acentricity	float	❌	—	偏心因子
boiling_range	object	❌	°C	沸程范围
source	enum	❌	—	USER_INPUT/AUTO_CUT
4. Distillation_JSON（馏程）
json
{
  "unit": "°C",
  "ibp": null,       // 初馏点
  "p5": null,        // 5%
  "p10": null,
  "p20": null,
  "p30": null,
  "p40": null,
  "p50": null,
  "p55": null,
  "fbp": null        // 终馏点
}
5. SARA_JSON（四组分分析）
json
{
  "unit": "wt%",
  "saturates": null,      // 饱和分
  "aromatics": null,      // 芳香分
  "resins": null,         // 胶质
  "asphaltenes": null     // 沥青质
}
6. Elemental_JSON（元素分析）
json
{
  "unit": "wt%",
  "sulfur": null,     // S
  "nitrogen": null,   // N
  "carbon": null,     // C
  "hydrogen": null    // H
}
7. Metals_JSON（金属含量）
json
{
  "unit": "ppm",
  "nickel": null,     // Ni
  "copper": null,     // Cu
  "iron": null,       // Fe
  "nacl": null,       // NaCl
  "vanadium": null    // V
}
8. property_estimation_json（物性估算详情）
json
{
  "density": {"estimated": true, "method": "PR_EOS", "value": 750.5},
  "viscosity_dynamic": {"estimated": true, "method": "MIXING_RULE", "value": 1.23},
  "molecular_weight": {"estimated": false, "method": null, "value": 112.3}
}
字段名	类型	说明
estimated	bool	是否估算
method	string	估算方法（PR_EOS/SRK_EOS/MIXING_RULE/RIAZI_DAUBERT/USER_INPUT等）
value	float	物性值
9. Feedstock/Product Specs JSON
json
{
  "spec_type": "PTA",      // PTA/IPA/VAM/Butene1/Generic
  "specs": [
    {
      "parameter": "AcidValue",
      "value": 675,
      "tolerance": "±2",
      "unit": "mg KOH/g",
      "note": null
    }
  ]
}
10. 两相流约束
约束	说明
气液组成必填	TWO_PHASE时，vapor_composition_json和liquid_composition_json必填
分率范围	vapor_fraction ∈ (0,1)
一致性	气相×分率 + 液相×(1-分率) ≈ 总组成
估算标记	FLASH计算的气液组成标记estimated=true
PCS-DICT-006：签署矩阵与编号模板字典
文件标识	PCS-DICT-006
当前版本	V1.0
发布日期	2026-08-29
关联文档	PCS-DICT-ALL-003 V3.0（表34 signature_matrices、表13 numbering_templates、表10 project_templates）、SUP-005、ADR-0008/0015
1. steps_json（签署矩阵步骤配置）
1.1 结构定义
json
[
  {
    "step_order": 1,
    "sign_role": "CHECKER",
    "step_name": "校核",
    "required": true,
    "can_self_check": false,
    "can_skip": false,
    "action": "CHECK"
  }
]
字段名	类型	必填	默认值	说明
step_order	int	✅	—	步骤序号（从1开始）
sign_role	enum	✅	—	CHECKER/REVIEWER/APPROVER/CUSTOMER/DRAFT_CHECKER/DESIGNED/ENG_CHECKER
step_name	string	❌	role默认名	步骤显示名称
required	bool	✅	true	是否必选步骤
can_self_check	bool	❌	false	是否允许设计人兼任此角色
can_skip	bool	❌	false	是否有审批时可跳过
action	enum	✅	由role推断	CHECK/REVIEW/APPROVE/CUSTOMER_APPROVE
1.2 典型模板
模板	steps_json
2级（Check+Approve）	[{"step_order":1,"sign_role":"CHECKER","required":true},{"step_order":2,"sign_role":"APPROVER","required":true}]
3级（标准）	[{"step_order":1,"sign_role":"CHECKER","required":true},{"step_order":2,"sign_role":"REVIEWER","required":true},{"step_order":3,"sign_role":"APPROVER","required":true}]
4级+客户	3级基础上追加{"step_order":4,"sign_role":"CUSTOMER","required":true,"can_skip":true}
变更单3级	与标准3级相同，doc_type=CHANGE_NOTICE
2. segments_json（编号模板段定义）
2.1 结构定义
json
[
  {
    "key": "project_no",
    "type": "PROJECT_FIELD",
    "field": "project_no",
    "label": "项目编号",
    "required": true,
    "width": null,
    "padding": null,
    "default": null,
    "format": null,
    "scope_keys": null
  }
]
字段名	类型	必填	说明
key	string	✅	段标识（唯一）
type	enum	✅	PROJECT_FIELD/DELIVERABLE_FIELD/SEQUENCE/FIXED/MANUAL/DATE
field	string	❌	PROJECT_FIELD或DELIVERABLE_FIELD类型时的源字段名
label	string	✅	段显示名称
required	bool	✅	是否必填段
width	int	❌	仅SEQUENCE：位数（4→0001）
padding	string	❌	仅SEQUENCE：填充字符（"0"）
default	string	❌	默认值（PROJECT_FIELD/FIXED）
format	string	❌	仅DATE：格式（"YYYY"/"YYYYMM"）
scope_keys	array	❌	仅SEQUENCE：按哪些段的组合独立计数
2.2 SEQUENCE段的scope配置示例
scope_keys	行为
["discipline", "doc_id"]	每个discipline+doc_id组合独立从0001开始
["year", "discipline"]	按年度+专业独立计数
null	全项目统一顺序计数
3. deliverable_mappings_json（交付物类型→段字段映射）
json
{
  "PIPE_LIST":       {"discipline_code": "PE", "doc_identifier_code": "LST"},
  "PIPE_CALC":       {"discipline_code": "PE", "doc_identifier_code": "CAL"},
  "PUMP_DATASHEET":  {"discipline_code": "ME", "doc_identifier_code": "DAS"},
  "PUMP_CALC":       {"discipline_code": "ME", "doc_identifier_code": "CAL"},
  "PSV_LIST":        {"discipline_code": "SR", "doc_identifier_code": "LST"},
  "PSV_DATASHEET":   {"discipline_code": "SR", "doc_identifier_code": "DAS"},
  "EQUIP_LIST":      {"discipline_code": "ME", "doc_identifier_code": "LST"},
  "UTIL_SUMMARY":    {"discipline_code": "MU", "doc_identifier_code": "REP"},
  "CHANGE_NOTICE":   {"discipline_code": "PR", "doc_identifier_code": "KDC"},
  "CUSTOM_REPORT":   {"discipline_code": "PR", "doc_identifier_code": "REP"}
}
4. default_config_json（项目模板默认配置完整结构）
json
{
  "record_approval_config": {
    "PIPE_RESULT": {"depth": 2, "steps": [{"step_order":1,"sign_role":"CHECKER","required":true},{"step_order":2,"sign_role":"APPROVER","required":true}]},
    "PUMP_RESULT": {"depth": 3, "steps": [{"step_order":1,"sign_role":"CHECKER","required":true},{"step_order":2,"sign_role":"REVIEWER","required":true},{"step_order":3,"sign_role":"APPROVER","required":true}]},
    "PSV_RESULT": {"depth": 4, "steps": [{"step_order":1,"sign_role":"CHECKER","required":true},{"step_order":2,"sign_role":"REVIEWER","required":true},{"step_order":3,"sign_role":"APPROVER","required":true},{"step_order":4,"sign_role":"CUSTOMER","required":true}]}
  },
  "stream_approval_config": {"depth": 1, "steps": [{"step_order":1,"sign_role":"CHECKER","required":true}]},
  "signature_matrices": [
    {"matrix_name": "STANDARD_CALC_3_LEVEL", "module": "*", "steps_json": []},
    {"matrix_name": "CHANGE_NOTICE_3_LEVEL", "module": "CHANGE_NOTICE", "steps_json": []}
  ],
  "numbering_config": {
    "template_name": "WORLEY_STD",
    "segments": [],
    "separator": "-",
    "deliverable_mappings": {}
  },
  "customer_approval_config": {
    "proxy_mode": "INTERNAL_PROXY",
    "allowed_proxy_roles": ["PROJECT_MANAGER", "DOC_CONTROLLER", "APPROVER"],
    "require_attachment": true,
    "require_second_auth": true,
    "attachment_types_allowed": ["PDF", "JPG", "PNG", "EML"],
    "max_attachment_size_mb": 20
  },
  "doc_no_config": {"mode": "WORLEY_STD"}
}
PCS-DICT-007：计算模块输入输出JSON字典
文件标识	PCS-DICT-007
当前版本	V1.0
发布日期	2026-08-29
关联文档	PCS-DICT-ALL-003 V3.0（计算模块16表）、SPEC-P4/P5/P6
1. flash_results（表15）
1.1 input_json（按calc_type变化）
json
// PT_FLASH
{"temperature_c": 300, "pressure_mpaa": 1.0, "composition": {"basis":"molar","components":[]}, "method": "PR"}

// PH_FLASH
{"pressure_mpaa": 1.0, "enthalpy_kj_kg": 500.0, "composition": {...}, "method": "PR"}

// BUBBLE_T
{"pressure_mpaa": 1.0, "liquid_composition": {...}, "method": "PR"}

// DEW_T
{"pressure_mpaa": 1.0, "vapor_composition": {...}, "method": "PR"}

// SATURATION
{"temperature_c": 100.0, "fluid": "Water"}
1.2 output_json
json
{
  "vapor_fraction": 0.35,
  "vapor_composition": {"basis":"molar","components":[]},
  "liquid_composition": {"basis":"molar","components":[]},
  "enthalpy_kj_kg": null,
  "entropy_kj_kg_k": null,
  "k_values": [{"component":"C6H14","k": 1.5}],
  "converged": true,
  "iterations": 15,
  "method_used": "PR"
}
2. pipe_network_results（表17）
2.1 topology_json
json
{
  "nodes": [
    {"node_id": "N1", "label": "泵出口", "type": "JUNCTION"}
  ],
  "pipes": [
    {
      "pipe_id": "P1",
      "from_node": "N1",
      "to_node": "N2",
      "length_m": 100,
      "diameter_mm": 100,
      "roughness_mm": 0.046,
      "fittings_count": 3
    }
  ]
}
2.2 convergence_log_json
json
{
  "solver": "Hardy-Cross",
  "max_iterations": 100,
  "tolerance": 1e-6,
  "iterations_used": 25,
  "converged": true,
  "residual_history": [0.5, 0.1, 0.02, 0.004, 0.0005]
}
2.3 flow_distribution_json
json
[
  {"pipe_id": "P1", "flow_kg_h": 50000, "velocity_m_s": 1.77, "pressure_drop_kpa": 31.2}
]
3. flare_system_results（表20）
3.1 radiation_check_json
json
{
  "total_relief_load_kg_h": null,
  "header_size_inch": null,
  "header_mach": null,
  "kod_diameter_mm": null,
  "stack_height_m": null,
  "radiation_at_grade_kw_m2": null,
  "radiation_limit_kw_m2": null,
  "pass": true,
  "flare_type": null,
  "steam_for_smokeless_kg_h": null
}
4. psychro_results（表27）
4.1 input_json / output_json（按calc_type）
calc_type	input_json	output_json
HUMIDITY_RATIO	{"temp_c":30,"rh_pct":60,"pressure_kpa":101.325}	{"humidity_ratio_kg_kg":null}
DEW_POINT	{"temp_c":30,"rh_pct":60}	{"dew_point_c":null}
WET_BULB	{"temp_c":30,"rh_pct":60}	{"wet_bulb_c":null}
ENTHALPY	{"temp_c":30,"rh_pct":60}	{"enthalpy_kj_kg":null}
COOLING_COIL	{"inlet":{"temp_c":35,"rh_pct":70},"outlet":{"temp_c":15,"rh_pct":90}}	{"sensible_kw":null,"latent_kw":null}
5. open_channel_results（表28）
5.1 cross_section_json
json
// 梯形
{"type":"TRAPEZOIDAL","bottom_width_m":1.0,"side_slope_h_v":2.0,"depth_m":0.5}

// 矩形
{"type":"RECTANGULAR","width_m":1.5,"depth_m":0.6}

// 圆形
{"type":"CIRCULAR","diameter_m":0.8}
6. sep_equip_results（表22）
json
{
  "equip_type": "CYCLONE",
  "dimensions": {"diameter_mm": 800, "height_mm": 2400, "inlet_w_mm": 200, "inlet_h_mm": 400},
  "efficiency_pct": 95.5,
  "pressure_drop_kpa": 1.2,
  "cut_diameter_micron": 10,
  "method": "Lapple"
}
7. filtration_results（表29）
json
{
  "filter_type": "PLATE_FRAME",
  "area_m2": 25.0,
  "cycle_time_min": 60,
  "pressure_drop_kpa": 180,
  "cake_thickness_mm": 15,
  "filtration_medium": null
}
8. 已合并的模块（参考V3.0表定义）
模块	已有JSON定义位置
piping_results	V3.0表16（完整字段）
pump_results	V3.0表18（12个JSON子结构）
psv_results	V3.0表19（平铺字段）
vessel_results	V3.0表21（平铺字段）
heat_results	V3.0表23（管壳式+空冷器JSON子结构）
cv_results	V3.0表24（平铺字段）
restriction_results	V3.0表25（平铺字段）
cooling_tower_results	V3.0表26（平铺字段）
PCS-DICT-008：集成与配置JSON字典
文件标识	PCS-DICT-008
当前版本	V1.0
发布日期	2026-08-29
关联文档	PCS-DICT-ALL-003 V3.0（表39 equipment_list、表37 change_notice_details、表38 record_change_snapshots、表44 project_input_checklist）
1. equipment_list.design_parameters_json
1.1 按TypeCode定义
TypeCode	设计参数字段
P（泵）	flow_m3h, head_m, npshr_m, efficiency_pct, power_kw, speed_rpm, seal_type, model, vendor
E（换热器）	area_m2, duty_kw, shell_dia_mm, tube_len_m, tube_count, passes, u_value_w_m2k, fouling_m2k_w, tema_type
D/V/T/R（容器/塔）	volume_m3, diameter_mm, length_mm, design_press_mpag, design_temp_c, operating_press_mpag, operating_temp_c, moc, corrosion_allowance_mm
PSV	set_pressure_mpag, relief_capacity_kgh, orifice_area_cm2, orifice, inlet_size, outlet_size, blowdown_pct
C（压缩机）	flow_m3min, discharge_press_mpag, power_kw, speed_rpm, type, model
1.2 泵设计参数示例
json
{
  "flow_m3h": 50,
  "head_m": 120,
  "npshr_m": 2.5,
  "efficiency_pct": 75,
  "power_kw": 28,
  "speed_rpm": 2950,
  "seal_type": "MECHANICAL",
  "model": null,
  "vendor": null
}
2. equipment_list.actual_key_parameter_json
json
{
  "actual_head_m": 118,
  "actual_efficiency_pct": 73,
  "actual_motor_power_kw": 30,
  "actual_npshr_m": 2.8,
  "vendor_model": "XYZ-123",
  "deviation_details": {
    "head_deviation_pct": -1.7,
    "efficiency_deviation_pct": -2.7,
    "motor_power_deviation_pct": +7.1
  },
  "confirmed": false
}
3. change_notice_details扩展
字段名	类型	说明
change_type	enum	DATA_CORRECTION/PROCESS_CHANGE/UPSTREAM_CHANGE/CLIENT_COMMENT/RECORD_CANCELLATION/CHANGE_REVERSAL/OTHER
reason	string	变更原因（必填）
triggered_by	enum	MANUAL/UPSTREAM_CHANGE
source_record_type	enum	PIPE_RESULT/PUMP_RESULT等
4. record_change_snapshots.data_snapshot_json
4.1 快照内容范围
仅参与哈希的设计参数，不包括：

sign_status/approval_step等状态字段

created_by/created_at等审计字段

record_hash本身

4.2 示例（piping_results的快照）
json
{
  "line_no": "100-P001-DN100-1F",
  "line_size": "DN100",
  "material_class": "2180",
  "design_press_mpag": 1.0,
  "design_temp_c": 65,
  "norm_oper_press_mpag": 0.4,
  "norm_oper_temp_c": 30,
  "record_hash_at_snapshot": "abc123..."
}
5. project_input_checklist.input_value_json
5.1 按输入项类型
输入项类型	value格式
文本	{"type":"string","value":"xxx"}
数值	{"type":"number","value":17.2,"unit":"°C"}
布尔	{"type":"bool","value":true}
枚举	{"type":"enum","value":"SI","options":["SI","METRIC","IMPERIAL"]}
文件引用	{"type":"file_ref","value":"attachments/xxx.pdf"}
对象	{"type":"object","value":{...}}
5.2 示例
json
{
  "type": "number",
  "value": 17.2,
  "unit": "°C",
  "source": "BEDD §2.2.1",
  "verified": true
}
四份字典完成。 至此，PCS字典体系完整覆盖：

字典	内容	状态
PCS-DICT-ALL-003 V3.0	53表完整字段定义	✅
PCS-DICT-004	BEDD完整JSON结构（+2增补）	✅
PCS-DICT-005	Streams组成与物性子结构	✅
PCS-DICT-006	签署矩阵与编号模板	✅
PCS-DICT-007	计算模块JSON结构	✅
PCS-DICT-008	集成与配置JSON结构	✅
PCS-DICT-005 增补文件
文件标识	PCS-DICT-005-SUP-001
当前版本	V1.1
发布日期	2026-08-29
增补基准	PCS-DICT-005 V1.0（Streams组成与物性子结构）
新增参考	物料介质特性数据表（Material Property List，DOC. NO. 21A/28/162K）
1. 增补说明
1.1 新增素材价值
本素材是项目级物料介质特性数据表，定义了物流（Streams）引用的介质代码（Fluid Code）对应的安全与物性属性：

维度	DICT-005已有	本增补新增
组成	✅ Composition_JSON	—
物性	✅ 密度/粘度/分子量等	—
馏程/SARA	✅	—
介质安全属性	❌	✅ 闪点/爆炸极限/引燃温度/燃烧性
火灾危险等级	❌	✅ 甲/乙/丙类
毒性数据	❌	✅ LD50/LC50/MAC/PC-TWA/PC-STEL
危害程度分级	❌	✅ GBZ230-2010分级
危规号/UN编号	❌	✅
外观特性	❌	✅
静电接地要求	❌	✅
1.2 在PCS体系中的位置
介质特性数据属于COMMON物性数据库 + 项目级介质代码表的交叉：

text
streams.fluid_code（物流引用介质代码）
    │
    ▼
fluid_properties（介质特性数据——本增补定义）
    ├── 物性数据：熔点/沸点/密度（来自chemicals/CoolProp）
    ├── 安全数据：闪点/爆炸极限/引燃温度/燃烧性
    ├── 火灾等级：甲A/甲B/乙A/乙B/丙A/丙B/丁/戊
    ├── 毒性数据：LD50/LC50/MAC/PC-TWA/PC-STEL
    ├── 危害分级：Ⅰ/Ⅱ/Ⅲ/Ⅳ（GBZ230-2010）
    ├── 静电接地：Y/N
    └── 运输信息：危规号/UN编号
2. 介质特性数据完整JSON结构（fluid_property_json）
2.1 顶层结构
json
{
  "fluid_code": null,           // 介质代码（如COS/COR、HOS/HOR/HOV/HOD、DCMCS3、M2）
  "fluid_name": null,           // 介质名称（如冷冻硅油、导热硅油）
  "fluid_name_en": null,        // 英文名称（如Chilled oil、Hot oil）
  "appearance": null,           // 外观特性
  "physical": {},               // 物性数据
  "safety": {},                 // 安全数据
  "fire_grade": null,           // 火灾危险等级
  "toxicity": {},               // 毒性数据
  "harm_grade": null,           // 危害程度分级
  "static_grounding": null,     // 静电接地要求
  "transport": {},              // 运输信息
  "source": null                // 数据来源标记
}
2.2 physical（物性数据）
字段名	类型	必填	单位	说明
melt_point_c	float	❌	°C	熔点
boil_point_c	float	❌	°C	沸点
flash_point_c	float	❌	°C	闪点
ignite_temp_c	float	❌	°C	引燃温度/自燃点
relative_density_water	float	❌	—	相对密度（水=1）
relative_density_air	float	❌	—	相对密度（空气=1）
explosion_limit_lower_pct	float	❌	%v	爆炸下限
explosion_limit_upper_pct	float	❌	%v	爆炸上限
2.3 safety（安全数据）
字段名	类型	必填	说明
flammable	enum	❌	燃烧性（FLAMMABLE/INFLAMMABLE/NONFLAMMABLE）
corrosive	enum	❌	腐蚀性（YES/NO/NONE）
static_grounding_required	enum	❌	静电接地（Y/N/-）
2.4 fire_grade（火灾危险等级）
字段名	类型	必填	说明
fire_grade	enum	❌	甲A/甲B/乙A/乙B/丙A/丙B/丁/戊
2.5 toxicity（毒性数据）
字段名	类型	必填	单位	说明
ld50_mg_kg	float	❌	mg/kg	经口LD50
lc50_mg_m3	float	❌	mg/m³	吸入LC50
mac_mg_m3	float	❌	mg/m³	最高容许浓度（MAC）
pc_twa_mg_m3	float	❌	mg/m³	时间加权平均容许浓度（PC-TWA）
pc_stel_mg_m3	float	❌	mg/m³	短时间接触容许浓度（PC-STEL）
standard	string	❌	—	毒性标准（GBZ2.1-2007）
2.6 harm_grade（危害程度分级）
字段名	类型	必填	说明
harm_grade	enum	❌	Ⅰ（极度）/Ⅱ（高度）/Ⅲ（中度）/Ⅳ（轻度）
harm_standard	string	❌	分级标准（GBZ230-2010）
2.7 transport（运输信息）
字段名	类型	必填	说明
dangerous_goods_code	string	❌	危规号
un_no	string	❌	UN编号
2.8 source（数据来源标记）
字段名	类型	说明
source_type	enum	MANUAL_ENTRY / COMMON_DB / CALCULATED
source_ref	string	来源文档/标准编号
3. 完整示例数据（来自素材）
3.1 冷冻硅油（COS/COR）
json
{
  "fluid_code": "COS/COR",
  "fluid_name": "冷冻硅油",
  "fluid_name_en": "Chilled oil",
  "appearance": "清澈的液体 Crystal-clear liquid",
  "physical": {
    "melt_point_c": null,
    "boil_point_c": null,
    "flash_point_c": 42,
    "ignite_temp_c": 350,
    "relative_density_water": 0.85,
    "relative_density_air": null,
    "explosion_limit_upper_pct": 12.5,
    "explosion_limit_lower_pct": 0.7
  },
  "safety": {
    "flammable": "FLAMMABLE",
    "corrosive": "NONE",
    "static_grounding_required": "Y"
  },
  "fire_grade": "乙B类",
  "toxicity": {
    "ld50_mg_kg": null,
    "lc50_mg_m3": null,
    "mac_mg_m3": null,
    "pc_twa_mg_m3": null,
    "pc_stel_mg_m3": null,
    "standard": "GBZ2.1-2007"
  },
  "harm_grade": "轻度危害(Ⅳ)",
  "static_grounding": "Y",
  "transport": {"dangerous_goods_code": null, "un_no": null}
}
3.2 液氨
json
{
  "fluid_code": null,
  "fluid_name": "液氨",
  "fluid_name_en": "Ammonia",
  "appearance": "无色有刺激性，液体",
  "physical": {
    "melt_point_c": -77.7,
    "boil_point_c": -33.4,
    "flash_point_c": null,
    "ignite_temp_c": 651,
    "relative_density_water": 0.7067,
    "explosion_limit_upper_pct": 25,
    "explosion_limit_lower_pct": 16
  },
  "safety": {
    "flammable": "INFLAMMABLE",
    "corrosive": "YES",
    "static_grounding_required": "Y"
  },
  "fire_grade": null,
  "toxicity": {
    "ld50_mg_kg": 350,
    "lc50_mg_m3": 1390,
    "mac_mg_m3": null,
    "pc_twa_mg_m3": null,
    "pc_stel_mg_m3": null,
    "standard": "GBZ2.1-2007"
  },
  "harm_grade": "中度危害",
  "transport": {"dangerous_goods_code": null, "un_no": null}
}
3.3 氮气
json
{
  "fluid_code": null,
  "fluid_name": "氮气",
  "fluid_name_en": "Nitrogen",
  "appearance": "无色无臭气体 Colorless, Odorless Gas",
  "physical": {
    "melt_point_c": -209.8,
    "boil_point_c": -195.6,
    "flash_point_c": null,
    "ignite_temp_c": null,
    "relative_density_air": 0.97,
    "explosion_limit_upper_pct": null,
    "explosion_limit_lower_pct": null
  },
  "safety": {
    "flammable": "NONFLAMMABLE",
    "corrosive": "NONE",
    "static_grounding_required": "-"
  },
  "fire_grade": "丁类",
  "toxicity": {
    "ld50_mg_kg": null,
    "lc50_mg_m3": null,
    "mac_mg_m3": null,
    "pc_twa_mg_m3": null,
    "pc_stel_mg_m3": null
  },
  "harm_grade": null,
  "transport": {"dangerous_goods_code": "22005", "un_no": "1066"}
}
3.4 导热硅油（HOS/HOR/HOV/HOD）
json
{
  "fluid_code": "HOS/HOR/HOV/HOD",
  "fluid_name": "导热硅油",
  "fluid_name_en": "Hot oil",
  "appearance": "澄清黄色液体 Clear Yellow Liquid",
  "physical": {
    "melt_point_c": null,
    "boil_point_c": null,
    "flash_point_c": 160,
    "ignite_temp_c": 385,
    "relative_density_water": 0.935,
    "explosion_limit_upper_pct": 5,
    "explosion_limit_lower_pct": 0.9
  },
  "safety": {
    "flammable": "FLAMMABLE",
    "corrosive": "NONE",
    "static_grounding_required": "Y"
  },
  "fire_grade": "丙B类",
  "toxicity": {"ld50_mg_kg": null, "lc50_mg_m3": null},
  "harm_grade": "轻度危害(Ⅳ)",
  "transport": {"dangerous_goods_code": null, "un_no": null}
}
3.5 甲基氯硅烷混合物（DCMCS3）
json
{
  "fluid_code": "DCMCS3",
  "fluid_name": "甲基氯硅烷混合物",
  "fluid_name_en": "Methylchlorosilane Mixture",
  "appearance": "无色有刺鼻气味液体 Colorless Liquid with a Pungent Odor",
  "physical": {"melt_point_c": null, "boil_point_c": null, "flash_point_c": null, "ignite_temp_c": null},
  "safety": {
    "flammable": "INFLAMMABLE",
    "corrosive": "YES",
    "static_grounding_required": "Y"
  },
  "fire_grade": "甲B类",
  "toxicity": {"ld50_mg_kg": null, "lc50_mg_m3": null},
  "harm_grade": "中度危害(Ⅲ)",
  "transport": {"dangerous_goods_code": null, "un_no": null}
}
3.6 二甲基二氯硅烷（M2）
json
{
  "fluid_code": "M2",
  "fluid_name": "二甲基二氯硅烷",
  "fluid_name_en": "Dimethyldichlorosilane",
  "appearance": "无色有刺鼻气味液体 Colorless Liquid with a Pungent Odor",
  "physical": {
    "melt_point_c": -86,
    "boil_point_c": 70.5,
    "flash_point_c": -16,
    "ignite_temp_c": 380,
    "relative_density_water": 1.07,
    "relative_density_air": 4.45,
    "explosion_limit_upper_pct": 9.5,
    "explosion_limit_lower_pct": 3.4
  },
  "safety": {
    "flammable": "INFLAMMABLE",
    "corrosive": "YES",
    "static_grounding_required": "Y"
  },
  "fire_grade": "甲B类",
  "toxicity": {
    "ld50_mg_kg": null,
    "lc50_mg_m3": 4910,
    "pc_stel_mg_m3": 2,
    "standard": "GBZ2.1-2007"
  },
  "harm_grade": "中度危害(Ⅲ)",
  "transport": {"dangerous_goods_code": "32186", "un_no": "1162"}
}
4. 新增枚举定义
4.1 Flammability（燃烧性）
枚举值	中文
FLAMMABLE	可燃
INFLAMMABLE	易燃
NONFLAMMABLE	不燃
4.2 FireGrade（火灾危险等级）
枚举值	说明
CLASS_IA	甲A类
CLASS_IB	甲B类
CLASS_IIA	乙A类
CLASS_IIB	乙B类
CLASS_IIIA	丙A类
CLASS_IIIB	丙B类
CLASS_IV	丁类
CLASS_V	戊类
4.3 HarmGrade（危害程度分级，GBZ230-2010）
枚举值	中文
GRADE_I	极度危害(Ⅰ)
GRADE_II	高度危害(Ⅱ)
GRADE_III	中度危害(Ⅲ)
GRADE_IV	轻度危害(Ⅳ)
4.4 StaticGrounding（静电接地）
枚举值	说明
Y	需要
N	不需要
-	不适用
4.5 Corrosive（腐蚀性）
枚举值	说明
YES	有腐蚀性
NO	无腐蚀性
NONE	不适用（非接触介质）
5. 与现有PCS结构的关联
PCS组件	关联方式
streams.fluid_code	引用本字典的fluid_code
piping_results.fluid_code	引用本字典的fluid_code
piping_results.toxic_class	映射自harm_grade
piping_results.fluid_category	映射自flammable+fire_grade
COMMON物性库	物性数据（熔点/沸点/密度）可来自chemicals库，本字典为项目级覆写
输入清单	介质特性数据缺失时，作为REQUIRED输入项
5.1 ToxicClass（毒性级别）映射
HarmGrade	ToxicClass（piping_results）
GRADE_I	EXTREMELY_TOXIC
GRADE_II	HIGHLY_TOXIC
GRADE_III	TOXIC
GRADE_IV	LOW_TOXIC
null	NON_TOXIC
5.2 FluidCategory映射
Flammable	FluidCategory（ASME B31.3）
INFLAMMABLE + 甲类	M（高危）
FLAMMABLE	NORMAL
NONFLAMMABLE	D
6. 版本历史
版本	日期	修改内容
V1.0	2026-08-29	初始版本（组成/物性/馏程/SARA/虚拟组分）
V1.1	2026-08-29	增补介质特性数据表结构（SUP-001），新增fluid_property_json/安全数据/火灾等级/毒性/危害分级/运输信息
增补完成。 PCS-DICT-005现覆盖物流数据的完整链路：组成→物性→安全属性→火灾等级→毒性→运输信息。介质特性数据作为项目级配置，与COMMON物性库（物质级）形成两层数据体系，通过fluid_code关联。P3阶段SIM模块的物流创建和介质选择以此为准。


