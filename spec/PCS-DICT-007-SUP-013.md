PCS-DICT-007 增补文件十三
文件标识	PCS-DICT-007-SUP-013
当前版本	V1.13
发布日期	2026-08-29
增补基准	PCS-DICT-007 V3.0 + SUP-012（冷却塔）
新增参考	限流孔板仪表数据表（CC0913D1353-10-IN-DAS-0010）+ 文丘里洗涤器数据表（PR-01/D4001，0204-MI-302）
1. 增补说明
1.1 新增素材价值
两份素材填补了restriction_results.data_sheet_json（限流孔板最终数据表）和sep_equip_results中VENTURI_SCRUBBER类型的缺口：

维度	已有结构	本增补新增
限流孔板	仅设计条件（restriction_design_condition_json）	✅ 完整仪表数据表（ISO 5167计算标准）
文丘里洗涤器	仅通用旋风分离器示例	✅ 完整数据表（含4股物流+50组分+粒径分布）
多股物流	单物流	✅ 4股物流（Flexigas In/Out + Slurry In/Out）
液气比L/G	❌	✅ 1.75~2.7×10⁻³ m³/m³设计参数
喉管速度	❌	✅ 61~122 m/s设计范围
焦粉粒径分布	❌	✅ 9级粒径+wt%累积
2. 限流孔板仪表数据表JSON结构（restriction_orifice_datasheet_json）
2.1 顶层结构
json
{
  "general": {},                // 概要
  "process_conditions": {},     // 操作条件
  "orifice_plate": {},          // 孔板规格
  "meter_run": {},              // 测量直管段
  "options": {},                // 选项
  "purchase": {},               // 采购
  "notes": []                   // 备注
}
2.2 general（概要）
字段名	类型	必填	说明
tag_number	string	✅	位号
service	string	✅	用途（如Restricting Pressure To R1111）
pid_no	string	✅	PID号
location	string	❌	位置（Field/Control Room）
line_no	string	✅	管线号
line_size_dn	int	✅	管线尺寸DN
pipe_material	string	✅	材质（如304LSS）
pipe_schedule	string	✅	管线等级（如SCH40S(HG20553)）
area_classification	string	❌	区域划分
2.3 process_conditions（操作条件）
字段名	类型	必填	单位	说明
fluid_name	string	✅	—	介质（如Nitrox）
phase	enum	✅	—	相态（GAS/LIQUID/STEAM）
flow_min_nm3h	float	❌	Nm³/h	最小流量
flow_normal_nm3h	float	✅	Nm³/h	正常流量
flow_max_nm3h	float	✅	Nm³/h	最大流量
pressure_at_flow_barg	object	✅	Barg	{min, nor, max}
temperature_at_flow_c	string	❌	°C	温度（如AMB）
viscosity_cp	float	❌	cP	操作粘度
density_kg_m3	float	✅	kg/m³	操作密度
compressibility_factor	float	❌	—	压缩系数
specific_heat_ratio_cp_cv	float	❌	—	流体比热比
allowable_pressure_drop	string	❌	—	允许压力降（如4Barg）
crystallizable	string	❌	—	可结晶
conductivity	float	❌	—	导电率
2.4 orifice_plate（孔板规格）
字段名	类型	必填	说明
element_type	enum	✅	元件类型（RESTRICTION_ORIFICE/ORIFICE_PLATE/VENTURI/NOZZLE）
nominal_diameter_dn	int	✅	公称直径DN
calculation_standard	string	✅	计算标准（ISO5167/GB2624/ASME MFC-3M）
material	string	✅	材质（如304LSS）
thickness_mm	string	❌	厚度（By MFR）
bore_diameter_20c_mm	string	❌	孔径@20°C（By MFR）
beta_ratio	string	❌	β值(0.2~0.7)（By MFR）
drain_vent_hole	string	❌	排污/放空口（N/A）
flow_full_scale	string	❌	流量刻度（By MFR）
diff_press_full_scale	string	❌	满量程差压（By MFR）
pressure_loss_max_flow	string	❌	最大流量压损（By MFR）
process_connection	string	✅	过程连接（FLANGE_SUPPLY_BY_BUYER）
flange_std_rating	string	✅	法兰标准及等级（如DIN PN1.6 RF）
2.5 meter_run（测量直管段）
字段名	类型	必填	说明
straight_line_material	string	❌	直管段材质（N/A）
upstream_length	string	❌	上游直管段（按标准要求）
downstream_length	string	❌	下游直管段（按标准要求）
process_connection	string	❌	过程连接
2.6 purchase（采购）
字段名	类型	必填	说明
manufacturer	string	❌	制造商
model	string	❌	型号（By MFR）
requisition_no	string	❌	请购单号
purchase_order_no	string	❌	采购编号
item_no	string	❌	项目号
2.7 完整示例数据
json
{
  "general": {
    "tag_number": null,
    "service": "Restricting Pressure To R1111",
    "pid_no": "10-PR-PID-1101",
    "location": "Field",
    "line_no": "NIO-20-11002-F2F5K",
    "line_size_dn": 20,
    "pipe_material": "304LSS",
    "pipe_schedule": "SCH40S(HG20553)"
  },
  "process_conditions": {
    "fluid_name": "Nitrox",
    "phase": "GAS",
    "flow_normal_nm3h": 100,
    "pressure_at_flow_barg": {"min": 4, "nor": 5},
    "temperature_at_flow_c": "AMB",
    "viscosity_cp": 0.013,
    "density_kg_m3": 5,
    "allowable_pressure_drop": "4Barg"
  },
  "orifice_plate": {
    "element_type": "RESTRICTION_ORIFICE",
    "nominal_diameter_dn": 20,
    "calculation_standard": "ISO5167",
    "material": "304LSS",
    "thickness_mm": "By MFR",
    "bore_diameter_20c_mm": "By MFR",
    "beta_ratio": "By MFR",
    "drain_vent_hole": "N/A",
    "process_connection": "FLANGE_SUPPLY_BY_BUYER",
    "flange_std_rating": "DIN PN1.6 RF"
  },
  "purchase": {
    "model": "By MFR",
    "item_no": "CC0913D1353"
  }
}
3. 文丘里洗涤器数据表JSON结构（venturi_scrubber_data_sheet_json）
3.1 顶层结构
json
{
  "general": {},                // 概况
  "site_utilities": {},         // 现场及公用工程条件
  "process_conditions": {},     // 工艺条件（多股物流）
  "construction": {},           // 结构参数
  "nozzles": [],                // 开口说明
  "materials": {},              // 材料
  "weights": {},                // 质量
  "notes": [],                  // 说明（含液气比/喉管速度）
  "stream_composition": [],     // 附表1：物流组成
  "particle_size_distribution": {}, // 附表2：焦粉粒径分布
  "sketch_ref": null
}
3.2 general（概况）
字段名	类型	必填	说明
item_number	string	✅	设备编号（如0204-MI-302）
service	string	✅	设备名称（如文丘里洗涤器Venturi Scrubber）
quantity	int	✅	数量
quantity_operating	int	❌	操作数
quantity_spare	int	❌	备用数
location	string	❌	安装地点
pid_no	string	✅	流程图图号
pipeline_no	string	❌	所在管道号
operating_mode	enum	❌	操作方式
applicable_to	enum[]	❌	用于（询价/采购/设计/施工/竣工）
doc_no	string	✅	文表号
rev	string	✅	版次
3.3 site_utilities（现场及公用工程条件）
字段名	类型	必填	单位	说明
elevation_m	float	❌	m	海拔
atmospheric_pressure_kpaa	float	✅	kPaA	气压（101.39）
wind_pressure_pa	float	❌	Pa	风压（650）
min_ambient_temp_c	float	✅	°C	最低温度（-31.6）
max_ambient_temp_c	float	✅	°C	最高温度（36.6）
min_relative_humidity_pct	float	❌	%	最低相对湿度
max_relative_humidity_pct	float	❌	%	最高相对湿度
electrical_region	string	✅	—	电气区域（2区IIC T4；22区IIIC T300°C）
3.4 process_conditions（工艺条件——多股物流）
json
{
  "process_conditions": {
    "streams": [
      {
        "stream_name": "灵活气进口",
        "stream_name_en": "Flexigas Inlet",
        "fluid_state": "GAS",
        "toxicity_level": "中度危害",
        "explosive_fluid": true,
        "molecular_weight_g_mol": 22.80,
        "operating_temp_c": 213,
        "operating_pressure_mpag": 0.184,
        "density_kg_m3": 1.6,
        "viscosity_mpa_s": 0.024,
        "max_flow_rate_m_s": null,
        "surface_tension_dyne_cm": null,
        "flow_rate_kg_h": {"design": 555838, "turndown": 268276},
        "concentration": {"component": "焦粉Flexicoke", "value": "0.16wt%"},
        "allowable_pressure_drop_mpa": "0.022~0.026 / 注Note 9"
      }
    ]
  }
}
streams元素字段定义：

字段名	类型	必填	单位	说明
stream_name	string	✅	—	物流名称
stream_name_en	string	❌	—	英文名称
fluid_state	enum	✅	—	相态
toxicity_level	enum	❌	—	毒性危害程度
explosive_fluid	bool	❌	—	易爆介质
molecular_weight_g_mol	float	❌	g/mol	分子量
operating_temp_c	float	✅	°C	操作温度
operating_pressure_mpag	float	✅	MPaG	操作压力
density_kg_m3	float	❌	kg/m³	操作密度
viscosity_mpa_s	float	❌	mPa·s	操作粘度
max_flow_rate_m_s	float	❌	m/s	最大流速
surface_tension_dyne_cm	float	❌	dyne/cm	表面张力
flow_rate_kg_h	object	✅	kg/h	{design, turndown}
concentration	object	❌	—	{component, value}
allowable_pressure_drop_mpa	string	❌	MPa	允许压降
3.5 construction（结构参数）
字段名	类型	必填	说明
position	enum	✅	安装方位（VERTICAL垂直）
flow_direction	string	❌	流动方向
operation_type	enum	❌	混合类型
model	string	❌	混合器型号
mixer_type	enum	✅	混合器类型（VENTURI_SCRUBBER文丘里洗涤器）
specifications	string	❌	混合器规格（L=mm, DN=mm）
design_temp_c	float	✅	设计温度（343°C）
design_pressure_mpag	float	✅	设计压力（0.48 MPaG）
mixing_elements_removable	bool	❌	内件是否可拆
outlet_sound_pressure_dba	float	❌	出口声压级dB(A)
drain	string	❌	排液
lightning_arrest	string	❌	避雷
max_allowed_mixer_length_mm	float	❌	最大允许混合长度L
3.6 nozzles（开口说明）
json
[
  {"mark":"N1","service":"灵活气进口","service_en":"Flexigas Inlet","quantity":1,"pressure_class":150,"size_dn":1800,"mating_flange":null,"flange_std":null,"remark":null},
  {"mark":"N2","service":"N2循环浆液进口","service_en":"Slurry Inlet","quantity":1,"pressure_class":150,"size_dn":350,"mating_flange":null,"flange_std":null,"remark":null},
  {"mark":"N3","service":"混合物流出口","service_en":"Mixed fluid Outlet","quantity":1,"pressure_class":null,"size_dn":null,"mating_flange":null,"flange_std":null,"remark":"长方形管嘴"},
  {"mark":"N4","service":"压差变送器口","service_en":"Differential Pressure Transmitter","quantity":2,"pressure_class":null,"size_dn":25,"mating_flange":"socket weld","flange_std":"PN63","remark":"取压口配带承插焊闸阀"}
]
3.7 materials（材料）
json
{
  "shell": "焊接 Q245R",
  "elements": "CS + 3mm min. Alloy 20 Cb-3 SS clad",
  "nozzle_line": "20#",
  "flange": "20# WN/RF"
}
3.8 weights（质量）
字段名	类型	必填	单位	说明
weight_kg	float	❌	kg	设备净重
operating_fluid_weight_kg	float	❌	kg	操作介质质量
filled_water_weight_kg	float	❌	kg	充水质量
manufacturer	string	❌	—	制造商
code_for_manufacture	string	❌	—	制造标准
3.9 notes（说明——含核心设计参数）
备注键	内容
TYPE	"文丘里洗涤器类型：固定喉嘴高能文丘里。Fixed Throat High Energy Venturi"
SERVICE	"脱除灵活气中的固体焦粉。Remove Coke Fines from Flexigas"
EFFICIENCY	"焦粉脱除率>99wt%"
LG_RATIO	"液气比L/G：最小1.75×10⁻³，正常2.0×10⁻³，最大2.7×10⁻³ m³/m³"
THROAT_VELOCITY	"喉管流速：61~122 m/s"
MAX_AIR_GAP	"喉管内部湿壁间最大气体间隙<254mm"
EXTERNAL_DESIGN_PRESSURE	"设计外压：全真空@150°C"
WETTED_WALL	"湿壁设计：收缩段内壁完全均匀被液体覆盖"
DIVERGING_SECTION	"扩散段从喉管截面延伸至出口管道截面"
MECHANICAL_FEATURES	"所有外部加强构件连续全方位焊接"
3.10 stream_composition（附表1：物流组成，约50组分）
json
{
  "stream_composition": {
    "unit": "kg/h",
    "components": [
      {"name": "METHANE", "cn": "甲烷", "flexigas_inlet": null, "flexigas_outlet": null, "slurry_inlet": null, "slurry_outlet": null},
      {"name": "H2S", "cn": "硫化氢", "flexigas_inlet": 4587, "flexigas_outlet": 4617.3, "slurry_inlet": 146.3, "slurry_outlet": 116.1},
      {"name": "H2", "cn": "氢气", "flexigas_inlet": 8191.5, "flexigas_outlet": 8191.5, "slurry_inlet": 0.4, "slurry_outlet": 0.4},
      {"name": "NH3", "cn": "氨", "flexigas_inlet": 254.2, "flexigas_outlet": 405.7, "slurry_inlet": 635.6, "slurry_outlet": 484.1},
      {"name": "H2O", "cn": "水", "flexigas_inlet": 76118.5, "flexigas_outlet": 116085.8, "slurry_inlet": 666637.7, "slurry_outlet": 626670.4},
      {"name": "CO2", "cn": "二氧化碳", "flexigas_inlet": 63211.8, "flexigas_outlet": 63446.5, "slurry_inlet": 882.4, "slurry_outlet": 647.7},
      {"name": "Flexicoke", "cn": "焦粉", "flexigas_inlet": 914, "flexigas_outlet": null, "slurry_inlet": 12155, "slurry_outlet": 13069}
    ],
    "total": {"flexigas_inlet": 555837.9, "flexigas_outlet": 595299.9, "slurry_inlet": 680623.9, "slurry_outlet": 641161.1}
  }
}
3.11 particle_size_distribution（附表2：焦粉粒径分布）
json
{
  "particle_size_distribution": {
    "dust_type": "Flexicoke",
    "particle_density_kg_m3": 1858,
    "distribution": [
      {"diameter_range": "<1.0", "wt_pct": 12},
      {"diameter_range": "1~2", "wt_pct": 28},
      {"diameter_range": "2~3", "wt_pct": 42},
      {"diameter_range": "3~4", "wt_pct": 52},
      {"diameter_range": "4~6", "wt_pct": 70},
      {"diameter_range": "6~8", "wt_pct": 81},
      {"diameter_range": "8~10", "wt_pct": 88},
      {"diameter_range": "10~13", "wt_pct": 94},
      {"diameter_range": ">13", "wt_pct": 99}
    ]
  }
}
4. 枚举定义
4.1 RestrictionElementType（节流元件类型）
枚举值	中文
RESTRICTION_ORIFICE	限流孔板
ORIFICE_PLATE	标准孔板
VENTURI_TUBE	文丘里管
NOZZLE	喷嘴
4.2 ScrubberType（洗涤器类型）
枚举值	中文
FIXED_THROAT_HIGH_ENERGY_VENTURI	固定喉嘴高能文丘里
ADJUSTABLE_THROAT_VENTURI	可调喉管文丘里
SPRAY_TOWER	喷淋塔
PACKED_SCRUBBER	填料洗涤塔
TRAY_SCRUBBER	板式洗涤塔
4.3 OperationType（混合器操作类型）
枚举值	中文
MIXING	混合
SCRUBBING	洗涤
ATTEMPERATING	减温
EJECTING	喷射
5. 与已有结构的映射
5.1 与restriction_results的映射
restriction_results字段	restriction_orifice_datasheet_json
tag_number	general.tag_number
restriction_type	orifice_plate.element_type
bore_diameter	orifice_plate.bore_diameter_20c_mm
perm_pressure_drop	orifice_plate.pressure_loss_max_flow
choked_flow	由临界压比判定（不在数据表中直接显示）
5.2 与sep_equip_results的映射
sep_equip_results字段	venturi_scrubber_data_sheet_json
tag_number	general.item_number
equip_type	VENTURI_SCRUBBER
dimensions	construction.specifications
efficiency	notes中EFFICIENCY（>99wt%）
pressure_drop	process_conditions.streams[].allowable_pressure_drop_mpa
6. 版本历史
版本	日期	修改内容
V1.0~V1.11	2026-08-29	初始+10次增补
V2.0	2026-08-29	完整整合版
V3.0	2026-08-29	V2.0+SUP-001~011完整合并
V1.12	2026-08-29	增补冷却塔数据表（SUP-012）
V1.13	2026-08-29	增补限流孔板+文丘里洗涤器数据表（SUP-013）
