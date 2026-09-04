PCS-DICT-009：PSV/安全阀数据表字典（完整版）
文件标识	PCS-DICT-009
当前版本	V2.0（完整整合版）
发布日期	2026-08-29
关联文档	PCS-DICT-ALL-003 V3.0（表19 psv_results）、SPEC-P5 §3.2.3、ADR-0003
数据来源	MEC PSV Sizing标准、PVRV计算表（1169-20-B-35A）、安全阀数据表（PR-01/D1002）、安全阀计算书（PR-01/D1004/HL13181）、Mod.2510/E泄放汇总表
第一部分：概述
1.1 目的
定义psv_results表的完整字段结构，以及PSV计算全链路（泄放量→泄放面积→选型→核算→数据表→汇总）的输入输出JSON结构。覆盖两种标准体系：

国际标准：API 520/521/526 + ASME

中国标准：GB 150 附录B + HG/T 20592

1.2 数据来源标注约定
来源标识	文档	体系
{MEC}	MEC PSV Sizing标准	API/ASME
{PVRV}	呼吸阀计算表	API 2000
{DAS}	安全阀数据表（加氢反应器）	API
{CAL}	安全阀计算书（C-601A）	GB 150附录B
1.3 颜色/来源标记约定
颜色	含义	PCS source_type
🟢 绿色	人工输入	MANUAL_ENTRY
🔵 蓝色	与计算书关联数据（自动计算）	CALCULATED
🔴 红色	不确定数据（待确认）	ASSUMED
🩷 粉色	配管专业填写/可选手工输入	EXTERNAL_INPUT
⚪ 无色	自动计算结果	CALCULATED
第二部分：psv_results主表字段（V3.0表19完整定义）
字段名	类型	必填	说明	来源
psv_id	UUID	✅	PK	—
project_id	FK→projects	✅		—
workspace_id	FK→workspaces	✅		—
tag_number	string(50)	✅	安全阀位号	—
set_pressure	float	✅	整定压力MPaG	CAL
relief_capacity	float	✅	泄放量kg/h	CAL
orifice_area	float	✅	孔口面积mm²	CAL
orifice_designation	string	✅	D~T	CAL
inlet_size	string	✅	入口尺寸	CAL
outlet_size	string	✅	出口尺寸	CAL
blowdown	float	✅	回座压差%	CAL
relief_scenario	enum[]	✅	多工况	CAL
valve_type	enum	❌	安全阀型式	DAS
model	string	❌	型号	DAS
governing_scenario	enum	❌	选择的泄压工况	CAL
fluid_state	enum	❌	GAS/LIQUID/GAS_LIQUID_MIXED	DAS
calculated_area_mm2	float	❌	计算泄放面积	CAL
selected_area_mm2	float	❌	选用泄放面积	CAL
area_overdesign_pct	float	❌	面积余量%	CAL
data_sheet_json	JSON	❌	完整数据表	DAS
calc_sheet_json	JSON	❌	完整计算书	CAL
+ 统一字段模板			RecordMixin 9态+哈希+变更组	—
第三部分：psv_results.data_sheet_json（安全阀数据表结构）
3.1 顶层结构
json
{
  "general": {},            // 概况
  "process_conditions": {}, // 工艺条件
  "relief_conditions": {},  // 泄放工况计算
  "calculation": {},        // 计算结果/选型
  "construction": {},       // 安全阀结构
  "connections": {},        // 连接
  "materials": {},          // 材料
  "accessories": {},        // 附件
  "remarks": [],            // 备注
  "field_annotations": {}   // 字段来源标记
}
3.2 general（概况）
字段名	类型	必填	说明	来源
item_numbers	array	✅	设备编号（含A/B备阀）	DAS
service	string	✅	设备名称	DAS
quantity_required	int	✅	数量	DAS
quantity_online	int	❌	运行数	DAS
quantity_spare	int	❌	备用数	DAS
location	string	✅	安装地点	DAS
model	string	❌	型号	DAS
max_relief_temp_c	float	✅	最高泄放温度	CAL
pid_no	string	✅	PID图号	DAS
pipeline_no	string	✅	所在管道号	DAS
operating_mode	enum	✅	CONTINUOUS/INTERMITTENT/SPARE	DAS
atmospheric_pressure_kpaa	float	✅	大气压	CAL
min_ambient_temp_c	float	✅	最低环境温度	CAL
doc_no	string	✅	文表号	DAS
rev	string	✅	版次	DAS
3.3 process_conditions（工艺条件）
字段名	类型	必填	说明	来源
fluid_name	string	✅	介质名称	CAL
fluid_category	enum	✅	工艺介质/蒸汽/液化气/空气	CAL
max_h2_conc_mol_pct	float	❌	最高H₂浓度（抗氢）	DAS
max_h2s_conc_mol_pct	float	❌	最高H₂S浓度（抗硫）	DAS
fluid_state	enum	✅	GAS/LIQUID/GAS_LIQUID_MIXED	DAS
toxicity_level	enum	❌	毒性危害程度	DAS
explosive_fluid	bool	❌	易爆介质	DAS
operating_pressure_mpag	float	✅	最高操作压力	CAL
operating_temp_c	float	✅	最高操作温度	CAL
vessel_design_pressure_mpag	float	✅	容器设计压力	CAL
3.4 relief_conditions（泄放工况计算）
json
{
  "relief_conditions": {
    "max_accumulation_pct": 10,
    "max_allowable_inlet_loss_mpa": null,
    "cases": [
      {
        "case_no": 1,
        "governing": true,
        "scenario": "POWER_FAILURE",
        "has_this_scenario": true,
        "max_accumulation_pct": 10,
        "accumulated_pressure_mpa": 0.166,
        "max_relieving_pressure_mpaa": 1.926,
        "relief_temp_c": 175.0,
        "inlet_temp_k": 448.15,
        "fluid_state": "LIQUID",
        "vapor": {
          "mass_rate_kg_h": null, "molecular_weight": null,
          "k_cp_cv": null, "c_factor": null,
          "critical_flow_pressure_mpaa": null, "compressibility_factor": null
        },
        "liquid": {
          "mass_rate_kg_h": 458028.0, "density_kg_m3": 720.0,
          "viscosity_mpa_s": 0.25, "max_flow_coefficient": 1.0,
          "kf": 0.4, "kb": 1.0, "kv": 1.0
        },
        "required_area_mm2": 6829.301,
        "back_pressure_mpag": 0.16
      }
    ],
    "governing_case_no": 1,
    "discharge_to": "FLARE_HEADER",
    "pilot_discharge_to": null,
    "constant_back_pressure_mpag": 0.16,
    "total_back_pressure_mpag": null,
    "correction_factors": {
      "kd": 0.980, "kb_vapor": 1.0, "kw_liquid": null,
      "kv_viscosity": 1.0, "ksh_superheat": null
    }
  }
}
3.5 calculation（计算结果/选型）
json
{
  "calculation": {
    "main_valve_set_pressure_mpag": 1.66,
    "pilot_valve_set_pressure_mpag": null,
    "main_valve_set_grade_mpag": null,
    "reseating_pressure_mpag": null,
    "blowdown_pct": null,
    "required_orifice_area_mm2": 6829.301,
    "suggested_orifice": "Q",
    "required_throat_diameter_mm": 93.3,
    "selected_orifice": "R",
    "selected_throat_diameter_mm": 114.7,
    "selected_area_mm2": 10322.6,
    "area_overdesign_pct": 51,
    "valve_count": 1,
    "selected_model": "6R10-HTO-L DN150XDN250",
    "selected_inlet_dn": 150,
    "selected_outlet_dn": 250,
    "back_pressure_ratio": 0.10,
    "valve_type": "普通安全阀",
    "rated_liquid_kg_h": 148137.665,
    "liquid_reynolds": 1827.805,
    "liquid_kv_corrected": 0.900,
    "actual_liquid_kg_h_after_viscosity": 623085.157,
    "verification": "PASS"
  }
}
3.6 construction（安全阀结构）
字段名	类型	必填	说明
valve_type	enum	✅	安全阀型式（见§5枚举）
design_temp_c	float	❌	设计温度
design_pressure_mpag	float	❌	设计压力
orifice_designation	string	✅	喉径代号
caps_type	string	❌	保护罩型式
required_test_gag	bool	✅	带试验杆
bonnet_type	enum	❌	OPEN/CLOSED
required_lever	bool	✅	带扳手
required_radiator	bool	✅	带散热片
3.7 connections（连接）
json
{
  "inlet": {"class": "2500", "size_dn": 80, "flange_type": "WN/RJ",
             "connection_type": "FLANGE", "flange_std": "ANSIB16.5"},
  "outlet": {"class": "600", "size_dn": 100, "flange_type": "WN/RF",
              "connection_type": "FLANGE", "flange_std": "HG/T20615"}
}
3.8 materials（材料）
json
{
  "main_valve": {"body": null, "bonnet": null, "nozzle": null, "disk": null,
                  "gasket": null, "spindle": null, "seals": null, "internals": null},
  "pilot_valve": {"body": null, "bonnet": null, "nozzle": null, "disk": null,
                   "gasket": null, "spindle": null, "seals": null, "internals": null},
  "soft_goods_main": {"resilient_seat": null, "spring": null, "cap": null,
                       "bellows": null, "guide": null, "seat": null},
  "soft_goods_pilot": {"resilient_seat": null, "spring": null, "cap": null,
                        "bellows": null, "guide": null, "seat": null},
  "pilot_tubing_fittings": null
}
3.9 accessories（附件）
json
{
  "pilot_filter": {"included": null, "material": null},
  "backflow_preventer": {"included": null, "material": null},
  "remote_pressure_sensor": {"included": null},
  "field_test_unit": {"included": null, "material": null},
  "pressure_spike_snubber": {"included": null, "material": null}
}
3.10 remarks（备注）
标准备注模板：

备注键	内容
HIGH_TEMP_SEAL	"为适应高温工况，密封面应采用硬密封形式。Seating material shall be metal to metal due to high operating temperature."
FIRE_CASE_NOTE	"火灾工况温度基于较低操作温度 Fire case temperature is based on lower operating temperature."
WEATHER_HOOD	"安全阀须有防雨设施 PRV shall be furnished with a weather hood."
DRAIN_PORT	"非密闭安全阀出口低点开设½''放净口以防止雨水、凝液在安全阀出口积聚。"
CV_ESTIMATE	"安全阀泄放量按调节阀入口Cv估算，设计方根据实际选择的调节阀规格确定安全阀规格。"
第四部分：psv_results.calc_sheet_json（安全阀计算书结构）
4.1 顶层结构
json
{
  "standard": "GB150_APPENDIX_B",
  "cases": [],           // 各工况计算
  "selection": {},       // 选型结果
  "verification": {}     // 核算
}
4.2 cases[]（工况计算数组）
每个元素结构：

json
{
  "scenario": "POWER_FAILURE",       // 工况类型
  "has_scenario": true,              // 是否有此工况
  "max_accumulation_pct": 10,        // 最大积聚压力%
  "accumulated_pressure_mpa": 0.166, // Pa积聚压力
  "max_relieving_pressure_mpaa": 1.926, // Pm最高泄放压力
  "relief_temp_c": 175.0,            // 介质泄放温度
  "inlet_temp_k": 448.15,            // T1进口温度
  "fluid_state": "LIQUID",           // 泄放状态
  "vapor": {
    "mass_rate_kg_h": null,
    "molecular_weight": null,
    "k_cp_cv": null,
    "c_factor": null,
    "critical_flow_pressure_mpaa": null,
    "compressibility_factor": null,
    "flow_coefficient": null,
    "kb": null
  },
  "liquid": {
    "mass_rate_kg_h": 458028.0,
    "density_kg_m3": 720.0,
    "viscosity_mpa_s": 0.25,
    "max_flow_coefficient": 1.0,
    "kf": 0.40,
    "kb": 1.0,
    "kv": 1.0
  },
  "fire_specific": {                 // 仅火灾工况
    "vessel_type": null,             // 立式/卧式/球型
    "vessel_diameter_m": null,
    "vessel_length_m": null,
    "installation_height_m": null,
    "insulation_thickness_m": null,
    "insulation_conductivity_w_mk": null,
    "saturation_temp_c": null,
    "heat_absorbed_w": null,
    "wet_area_m2": null,
    "latent_heat_kj_kg": null,
    "coefficient_f": null
  },
  "tube_rupture_specific": {         // 仅换热管破裂
    "delta_p_mpa": null,
    "tube_id_m": null,
    "tube_length_m": null,
    "hp_lp_phase": null
  },
  "liquid_expansion_specific": {     // 仅液体膨胀
    "heat_input_w": null,
    "specific_heat_kj_kg_c": null,
    "expansion_coefficient": null,
    "relative_density": null,
    "liquid_relief_m3_h": null
  },
  "required_area_mm2": 6829.301
}
4.3 selection（选型结果）
json
{
  "governing_scenario": "POWER_FAILURE",
  "governing_fluid_state": "LIQUID",
  "required_area_mm2": 6829.301,
  "suggested_orifice": "Q",
  "required_throat_mm": 93.3,
  "selected_orifice": "R",
  "selected_throat_mm": 114.7,
  "selected_area_mm2": 10322.6,
  "area_overdesign_pct": 51,
  "valve_count": 1,
  "model": "6R10-HTO-L DN150XDN250",
  "inlet_dn": 150,
  "outlet_dn": 250,
  "back_pressure_ratio": 0.10,
  "valve_type": "CONVENTIONAL"
}
4.4 verification（核算）
json
{
  "rated_liquid_kg_h": 148137.665,
  "liquid_reynolds": 1827.805,
  "liquid_kv": 0.900,
  "actual_liquid_kg_h": 623085.157,
  "verification_result": "PASS"
}
第五部分：内置查询表（Lookup Tables）
5.1 API 526流道面积表
流道代号	API面积mm²	Actual面积mm²	喉径DN	IN/OUT
D	71.0	86.6	20	32/40
E	126.4	153.9	25	40/50
F	198.1	227.0	32	50/65
G	324.5	380.1	40	65/80
H	506.4	572.6	50	80/100
J	830.3	934.8	65	100/150
K	1185.8	1352.7	100	150/200
L	1840.6	2083.1	—	—
M	2322.6	2642.1	—	—
N	2800.0	—	—	—
P	4116.1	—	—	—
Q	7129.0	8171.3	—	—
R	10322.6	11689.9	—	—
T	16774.2	19113.4	—	—
5.2 Kv粘度修正系数表（液体）
Re	Kv	Re	Kv
0	0.3	400	0.85
30	0.3	500	0.86
40	0.35	600	0.875
50	0.4	700	0.88
60	0.45	800	0.88
70	0.5	900	0.89
80	0.54	1000	0.9
90	0.56	2000	0.93
100	0.6	4000	0.95
150	0.67	10000	0.96
200	0.75	20000	0.97
300	0.81	70000	1.0
5.3 波纹管式安全阀Kb值（液体）
P2/Pm	Kb
0.15	1
0.20	0.97
0.25	0.92
0.30	0.87
0.35	0.82
0.40	0.77
0.45	0.72
0.50	0.67
5.4 波纹管安全阀Kb值（气体）
P2/Ps(表压)	Kb(过压10%)	Kb(过压20%)
0.31	1	1
0.34	0.99	0.96
0.37	0.98	0.90
0.40	0.97	0.86
0.43	0.96	0.81
0.46	0.945	0.76
0.49	0.93	0.70
5.5 液体膨胀系数ω（15.6°C）
°API范围	密度范围	ω
3~34.9	1.052~0.8504	0.00072
35~50.9	0.8498~0.7758	0.0009
51~63.9	0.7753~0.7242	0.00108
64~78.9	0.7238~0.6725	0.00126
79~88.9	0.6722~0.6420	0.00144
89~93.9	0.6417~0.6279	0.00153
94~100	0.6275~0.6112	0.00162
水	—	0.00018
5.6 蒸汽过热修正系数KSH
（蒸汽压力MPa绝×温度°C矩阵，详见CAL素材）

5.7 容器受热面积计算
容器形式	受热面积A计算
半球型封头卧式	按公式计算
椭圆型封头卧式	按公式计算
立式	按公式计算
球型	按公式计算
5.8 火灾工况泄放量（按介质类别）
泄放介质	火灾工况泄放量计算方法
非易爆液化气体且无火灾危险环境	简化公式
液化气体（有火灾危险）	详细公式
饱和水蒸气<10MPa	查表
饱和水蒸气>10MPa<22MPa	查表
工艺介质	GB150附录B
第六部分：relief_scenario枚举（最终完整版）
枚举值	说明	标准来源
BLOCKED_OUTLET	出口堵塞	API 521 / GB150
OPEN_INLET	入口全开	API 521
EXTERNAL_FIRE	外部火灾	API 521 / GB150附录B
COOLING_FAILURE	冷却失效	API 521
REFLUX_FAILURE	回流失效	API 521
TUBE_RUPTURE	换热管破裂	API 521 / SEI
POWER_FAILURE	动力故障	API 521 / GB150
STEAM_FAILURE	蒸汽失效	API 521
INSTRUMENT_AIR_FAILURE	仪表风失效	API 521
THERMAL_EXPANSION	液体热膨胀	API 521 / SEI
VAPOR_BLOWBY	汽相窜入	API 521
CV_FAILURE	调节阀失效	API 521
EXCESSIVE_HEAT_INPUT	过量热输入	API 521
CHECK_VALVE_FAILURE	止回阀失效	API 521
REVERSE_FLOW	反向流	—
BACK_OVERFILL	回流超装	—
SPILL_OVERFILL	溢出超装	—
第七部分：安全阀型式枚举（最终完整版）
枚举值	中文名
SPRING_FULL_LIFT	弹簧全启式安全阀
SPRING_LOW_LIFT	弹簧微启式安全阀
BELLOWS_SPRING	波纹管弹簧式安全阀
SPRING_CLOSED	弹簧封闭式安全阀
SPRING_CLOSED_ANTI_SULFUR	弹簧封闭式抗硫安全阀
CLOSED_LOW_TEMP	弹簧微启封闭式低温安全阀
BALANCED_PRESSURE	平衡式安全阀
PILOT_OPERATED	先导式安全阀
CONVENTIONAL	普通安全阀
第八部分：PVRV呼吸阀计算（V1.0保留）
8.1 PVRV输入
json
{
  "valve_type": "PVRV",
  "tank_no": "TF-D-03",
  "rate_inflow_m3_hr": 50,
  "rate_outflow_m3_hr": 12,
  "set_vacuum_mpag": -0.00025,
  "set_pressure_mpag": 0.00098,
  "standard": "API_2000",
  "flame_arrester": false,
  "flash_point_c": -18
}
8.2 PVRV输出
json
{
  "normal_venting": {
    "outbreathing_total_nm3_hr": 299.7,
    "inbreathing_total_nm3_hr": 204.8
  },
  "emergency_venting": {
    "fire_wet_area_m2": 301.5,
    "heat_absorbed_kcal_hr": 4007276,
    "vent_flow_kg_hr": 39019.2
  }
}
8.3 API 2000热呼吸量表
（保留V1.0完整表，含26行罐容-吸气-呼气数据）

第九部分：泄放汇总表结构（flare_system_results关联）
json
{
  "summary_entry": {
    "rev": 1,
    "tag_number": "PRV-308A",
    "location": "O-3405",
    "protected_equipment": ["L-3401", "K-3401", "O-3405"],
    "size_type": "2\" J 4\"",
    "set_pressure_barg": 50,
    "discharge_to": "HF",
    "valve_type": "B",
    "scenarios": [
      {"type": "FIRE", "mw": 155, "kg_h": 6792, "temp_c": 455, "phase": "V"},
      {"type": "POWER_FAILURE", "mw": 8.6, "kg_h": 11830, "temp_c": 50, "phase": "V"},
      {"type": "OVERFILL", "density": 841, "kg_m3": 122, "m3_h": 50, "phase": "L"}
    ],
    "spare": true,
    "note": "PRV-308B IN SPARE"
  }
}
第十部分：计算API接口汇总
端点	说明
POST /api/v1/psv/calculate-relief	单工况泄放量计算
POST /api/v1/psv/calculate-all-scenarios	全工况计算（返回最大面积工况）
POST /api/v1/psv/calculate-area	泄放面积计算
POST /api/v1/psv/select-orifice	API 526/GB流道选型
POST /api/v1/psv/verify	核算检查
POST /api/v1/psv/generate-datasheet	生成数据表
POST /api/v1/psv/pvrv-calculate	PVRV呼吸阀计算
GET /api/v1/psv/lookup-tables	查询内置表（Kv/Kb/流道面积/膨胀系数）
GET /api/v1/psv/{psv_id}/summary	泄放汇总查询
第十一部分：版本历史
版本	日期	修改内容
V1.0	2026-08-29	初始版本（MEC标准+PVRV+泄放汇总）
V1.1	2026-08-29	增补安全阀数据表结构（SUP-001，加氢反应器实例）
V2.0	2026-08-29	整合安全阀计算书（GB150附录B），新增calc_sheet_json/内置查询表/完整枚举/计算API
PCS-DICT-009 V2.0完。 本文档覆盖PSV计算全链路的完整数据字典：

覆盖内容	标准体系
泄放量计算	API 520/521 + GB150附录B
泄放面积计算	气体/液体/两相流
选型	API 526 + HG/T 20592
数据表输出	9个JSON子结构
计算书输出	4个JSON子结构
内置查询表	8张（流道面积/Kv/Kb/膨胀系数/过热系数/受热面积）
PVRV呼吸阀	API 2000
泄放汇总	Mod.2510/E格式

