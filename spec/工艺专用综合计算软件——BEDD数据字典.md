工艺专用综合计算软件——BEDD数据字典
文件标识	PCS-DICT-004
当前版本	V1.0
发布日期	2026-08-29
编制部门	工艺部 / 信息化联合项目组
关联文档	PCS-DICT-ALL-003 V3.0（表级字段）、PCS-REQ-2026-002 V2.2 §3.2.1
数据来源	合同技术附件二（项目1239）、INEOS KAIMEN BEDD（20048A-0000-EM-REF-0001）、浙石化炼化一体化设计基础（1193E-00-0000-01-111-0001）、DICT-001 §3.2~3.9
第一部分：概述
1.1 目的
本文档定义 projects.bedd_json 的完整JSON结构字典，为PMS子系统（P3阶段）的表单动态生成、数据校验和项目输入清单提供唯一权威依据。BEDD采用JSONB存储于projects表，不同项目间差异通过JSON结构灵活承载。

1.2 数据来源说明
来源标识	文档	特点
{1239}	合同技术附件二（项目1239）	俄式格式，水质参数极其详细（10种水系统）
{KAIMEN}	INEOS KAIMEN BEDD	Worley格式，结构规范，含设计寿命/法规/IGGN
{ZPC}	浙石化设计基础	中国炼化一体化项目，含原油来源/燃料煤/空气质量/运输限界
{DICT-001}	原数据字典总则	原始BEDD结构定义
1.3 顶层结构总览
json
{
  "project_info": {},         // 项目基本信息
  "site_conditions": {        // 现场条件（气象/水文/地质/地震/运输限界）
    "meteorology": {},
    "hydrogeology": {},
    "transport_limits": {}
  },
  "feedstock": {},            // 原料来源和组成（炼化项目特有）
  "utilities": {},            // 公用工程条件
  "design_life": {},          // 设计寿命
  "operation": {},            // 操作时间与检修周期
  "regulatory": {},           // 法规/标准/规范
  "battery_limits": [],       // 界区条件
  "units": {},                // 单位制约定
  "discipline_criteria": {}   // 各专业设计准则文档引用
}
1.4 字段标注约定
标注	含义
✅	必填（项目创建时至少填默认值或"待确认"）
❌	可选
🔵	炼化项目特有（非炼化项目可忽略）
{来源}	字段来源标注
第二部分：完整字段定义
2.1 project_info（项目基本信息）
字段名	类型	必填	说明	来源
company_name	string	✅	业主公司名称	KAIMEN §1.2
project_name	string	✅	项目名称	KAIMEN §1.2
project_name_cn	string	❌	项目中文名称	KAIMEN §1.2
project_code	string	✅	项目代号（如ZLH1）	ZPC §1.1
project_no	string	✅	项目编号（文档系统编号）	KAIMEN
nameplate_capacity	string	✅	额定产能描述	KAIMEN §1.2
location	string	✅	建设地点	KAIMEN §1.2
site_address	string	❌	详细地址	KAIMEN §1.2
site_description	string	❌	场地描述	KAIMEN §1.3
project_type	enum	✅	REFINERY/CHEMICAL/STORAGE/UTILITY/FINE_CHEM/OTHER	DICT-001
design_phase	enum	✅	FEASIBILITY/FEED/BASIC_DESIGN/DETAIL_DESIGN/EPCM	DICT-001
unit_system	enum	✅	SI/METRIC/IMPERIAL	KAIMEN §2.1
language	string	✅	工程语言约定	KAIMEN §2.2
definitions	object	❌	项目术语定义	KAIMEN §2.3
maintenance_cycle	object	❌	检修周期	ZPC §1.2
phases	array	❌	项目分期信息	ZPC §1.1
maintenance_cycle子结构：

json
{
  "cycle_years": 4,
  "description": "四年一修"
}
phases子结构：

json
[
  {
    "phase": "I",
    "capacity": "20 MTPA refinery + 1.4 MTPA ethylene",
    "description": "一期工程"
  }
]
2.2 site_conditions（现场条件）
2.2.1 site_conditions.general（一般信息）
字段名	类型	必填	说明	来源
plant_location	string	❌	工厂位置描述	ZPC §2.1.1
geographical_conditions	string	❌	自然地形	ZPC §2.1.2
site_elevation	object	❌	场地标高	ZPC §2.1.3
site_elevation子结构：

json
{
  "description": "开山吹砂填海，堆载预压+强夯后",
  "min_m": 3.4,
  "max_m": 4.5,
  "datum": "85国家高程"
}
2.2.2 site_conditions.meteorology（气象条件）
2.2.2.1 temperature（气温）
字段名	类型	必填	单位	说明	来源
annual_avg	float	✅	°C	年平均温度	三份文档均有
monthly_avg_max	float	❌	°C	最热月份平均温度	KAIMEN/ZPC
monthly_avg_min	float	❌	°C	最冷月份平均气温	KAIMEN/ZPC
hottest_month_avg_max	float	❌	°C	历年最热月平均最高温度	ZPC
hottest_month_avg_min	float	❌	°C	历年最热月平均最低温度	ZPC
coldest_month_avg	float	❌	°C	最冷月平均气温	1239/KAIMEN
coldest_month_avg_min	float	❌	°C	最冷月平均最低气温	1239
monthly_avg_min_lowest	float	❌	°C	历年月平均最低气温最低值	ZPC
past10yr_min_daily_avg	float	❌	°C	过去10年最低日平均气温	ZPC
past10yr_min_monthly_avg	float	❌	°C	过去10年最低月平均气温	ZPC
extreme_high	float	✅	°C	极端最高气温	三份文档均有
extreme_low	float	✅	°C	极端最低气温	三份文档均有
daily_max_diff	float	❌	°C	一天内最大温差	ZPC
hottest_10yr_dry_bulb_daily_avg	float	❌	°C	10年内最热月日平均干球温度	ZPC
hottest_10yr_wet_bulb_daily_avg	float	❌	°C	10年内最热月日平均湿球温度	ZPC
daily_avg_dry_bulb	float	❌	°C	日平均干球温度	ZPC
daily_avg_wet_bulb	float	❌	°C	日平均湿球温度	ZPC
hottest_month_5day_exceed	float	❌	°C	最热月不保证5天平均温度	1239
ac_dry_bulb_winter	float	❌	°C	空调干球温度（冬季）	1239/ZPC
ac_dry_bulb_summer	float	❌	°C	空调干球温度（夏季）	1239/ZPC
ac_wet_bulb_winter	float	❌	°C	空调湿球温度（冬季）	1239
ac_wet_bulb_summer	float	❌	°C	空调湿球温度（夏季）	1239/ZPC
ac_daily_avg_summer	float	❌	°C	空调日平均温度（夏季）	ZPC
ventilation_winter	float	❌	°C	通风温度（冬季）	1239/ZPC
ventilation_summer	float	❌	°C	通风温度（夏季）	1239/ZPC
heating_winter	float	❌	°C	冬季供暖温度	1239
heating_days_winter	int	❌	d	冬季供暖日数	1239
mdht	object	❌	—	最高设计温度分组	1239
mdht子结构：

json
{
  "pressure_vessels": -55,
  "non_pressure_vessels": -39,
  "steel_structures": -37,
  "unit": "°C"
}
2.2.2.2 pressure（气压）
字段名	类型	必填	单位	说明	来源
annual_avg	float	✅	kPaA	全年平均气压	三份文档均有
monthly_avg_max	float	❌	kPaA	月平均最大气压	1239/ZPC
monthly_avg_min	float	❌	kPaA	月平均最小气压	1239/ZPC
extreme_max	float	❌	kPaA	最高气压	KAIMEN/ZPC
extreme_min	float	❌	kPaA	最低气压	KAIMEN/ZPC
summer_avg	float	❌	kPaA	夏季平均气压	1239/KAIMEN
winter_avg	float	❌	kPaA	冬季平均气压	1239/KAIMEN
2.2.2.3 humidity（湿度）
字段名	类型	必填	单位	说明	来源
annual_avg	float	✅	%	年平均相对湿度	三份文档均有
monthly_avg_max	float	❌	%	月平均最高相对湿度	1239/KAIMEN/ZPC
monthly_avg_min	float	❌	%	月平均最低相对湿度	1239/KAIMEN/ZPC
coldest_month_avg	float	❌	%	最冷月平均相对湿度	1239/ZPC
hottest_month_avg	float	❌	%	最热月平均相对湿度	1239/KAIMEN/ZPC
daily_avg	float	❌	%	日平均相对湿度	ZPC
summer_hottest_day_max	float	❌	%	夏日最大日平均相对湿度	ZPC
winter_coldest_day_max	float	❌	%	冬天最大日平均相对湿度	ZPC
winter_avg	float	❌	%	冬季相对湿度	ZPC
db_28_6c_humidity_jul	float	❌	%	干球28.6°C时湿度（7月）	KAIMEN
db_28_6c_humidity_jan	float	❌	%	干球28.6°C时湿度（1月）	KAIMEN
2.2.2.4 wind（风）
字段名	类型	必填	单位	说明	来源
prevailing_direction	string	✅	—	主导风向	KAIMEN/ZPC
prevailing_frequency	float	❌	%	主导风向频率	KAIMEN
secondary_directions	array	❌	—	次主导风向	KAIMEN/ZPC
summer_prevailing	string	❌	—	夏季主导风向	KAIMEN/ZPC
winter_prevailing	string	❌	—	冬季主导风向	KAIMEN/ZPC
annual_avg_speed	float	❌	m/s	年平均风速	1239/ZPC
ten_min_max_speed	float	✅	m/s	最高风速（10分钟平均）	KAIMEN/ZPC
instant_max_speed	float	❌	m/s	瞬时最大风速	1239/ZPC
max_30yr_speed	float	❌	m/s	30年一遇最高风速	ZPC
max_50yr_speed	float	❌	m/s	50年一遇最高风速	ZPC
max_100yr_speed	float	❌	m/s	100年一遇最高风速	ZPC
basic_pressure	float	✅	kN/m²	基本风压	三份文档均有
design_pressure	float	❌	Pa	设计风压值	1239
terrain_roughness_category	string	❌	—	地面粗糙度类别（A/B/C/D）	KAIMEN/ZPC
annual_strong_wind_days	float	❌	d	年均大风天数	ZPC
wind_rose_ref	string	❌	—	风玫瑰图附件引用	1239/ZPC
wind_pressure_analysis_ref	string	❌	—	风压分析报告引用	ZPC
2.2.2.5 typhoon（台风）
字段名	类型	必填	单位	说明	来源
typhoon_numbers_recorded	int	❌	次	台风次数	ZPC §2.2.5
max_typhoon_10min_avg_speed	float	❌	m/s	最大台风十分钟平均风速	ZPC §2.2.5
typhoon_events	array	❌	—	台风事件记录	KAIMEN §4.2.13
typhoon_events子结构：

json
[
  {
    "name": "Maisha",
    "year": 2005,
    "landfall_date": "2005-08-06",
    "central_pressure_hpa": 950,
    "max_wind_speed": 45,
    "areal_rainfall_mm": 464.2
  }
]
2.2.2.6 rainfall（降雨）
字段名	类型	必填	单位	说明	来源
annual_avg	float	✅	mm	年平均降雨量	三份文档均有
annual_max	float	❌	mm	年最大降雨量	KAIMEN/ZPC
annual_min	float	❌	mm	年最小降雨量	KAIMEN/ZPC
monthly_max	float	❌	mm	月最大降雨量	1239
daily_max_24h	float	❌	mm	24小时最大降雨量	1239
daily_max	float	❌	mm	最大日降雨量	KAIMEN/ZPC
hourly_max_30yr	float	❌	mm	每小时最大(30年一遇)	ZPC
hourly_max_35yr	float	❌	mm	每小时最大(35年一遇)	ZPC
hourly_max_50yr	float	❌	mm	每小时最大(50年一遇)	ZPC
hourly_max_100yr	float	❌	mm	每小时最大(100年一遇)	ZPC
min10_max_40yr	float	❌	mm	10分钟最大降雨量(40年)	ZPC
min5_max_40yr	float	❌	mm	5分钟最大降雨量(40年)	ZPC
min30_max	float	❌	mm	30分钟最大降雨量	KAIMEN
min20_max	float	❌	mm	20分钟最大降雨量	KAIMEN
min10_max	float	❌	mm	10分钟最大降雨量	KAIMEN
five_day_max	float	❌	mm	连续5天最大降雨量	KAIMEN
annual_avg_days	float	❌	d	年平均降雨日数	1239/KAIMEN/ZPC
annual_avg_storm_days_50mm	float	❌	d	年平均暴雨天数(>50mm)	ZPC
annual_avg_heavy_rain_days_25mm	float	❌	d	年平均大雨天数(>25mm)	ZPC
continuous_max_days	int	❌	d	最大连续降雨日数	KAIMEN
intensity_formula	string	❌	—	雨强公式	KAIMEN/ZPC
seawater_level	object	❌	—	海水平稳水位	1239
seawater_level子结构：

json
{
  "highest": 236,
  "lowest": 229.7,
  "unit": "mm"
}
2.2.2.7 evaporation / snowfall / thunderstorm / fog / sunshine / frost / soil_temperature / frozen_soil / soil / dust / altitude / air_quality
字段组	字段名	类型	必填	单位	说明	来源
evaporation	annual_avg	float	❌	mm	年平均蒸发量	KAIMEN/ZPC
annual_max	float	❌	mm	最大年蒸发量	ZPC
annual_min	float	❌	mm	最小年蒸发量	ZPC
monthly_max	float	❌	mm	月最大蒸发量	KAIMEN
monthly_min	float	❌	mm	月最小蒸发量	KAIMEN
snowfall	monthly_max	float	❌	mm	月最大降雪量	1239
annual_max	float	❌	mm	年最大降雪量	1239
max_depth_30yr	float	❌	mm	最大积雪深度(30年一遇)	KAIMEN
max_depth_50yr	float	❌	cm	最大积雪深度(50年一遇)	ZPC
max_snow_pressure_50yr	float	❌	kN/m²	最大积雪压力(50年)	ZPC
basic_snow_pressure_50yr	float	❌	kN/m²	基本雪压(n=50)	KAIMEN/ZPC
basic_snow_pressure_100yr	float	❌	kN/m²	基本雪压(n=100)	KAIMEN
avg_days	float	❌	d	平均降雪日数	KAIMEN
max_days	int	❌	d	最大降雪日数	KAIMEN
icing_thickness	float	❌	mm	覆冰厚度	1239
thunderstorm	annual_avg_days	float	❌	d	年平均雷暴日数	1239/KAIMEN/ZPC
max_days	int	❌	d	年最多雷暴日数	1239/KAIMEN
min_days	int	❌	d	年最少雷暴日数	KAIMEN
fog	avg_days	float	❌	d	年平均雾日数	KAIMEN/ZPC
max_days	int	❌	d	年最多雾日数	KAIMEN/ZPC
sunshine	annual_avg_hours	float	❌	h	年平均日照时数	KAIMEN/ZPC
annual_max_hours	float	❌	h	年最大日照时数	KAIMEN
frost	annual_avg_days	float	❌	d	年平均霜日数	KAIMEN
frozen_soil	max_depth	float	❌	m/cm	最大冻土深度	1239/ZPC
soil	resistivity	float	❌	Ω·m	土壤电阻率	1239
thermal_resistance	float	❌	°C·cm/W	土壤热阻系数	1239
temp_hottest_month_0_8m	float	❌	°C	最热月土壤温度(0.8m)	1239
temp_coldest_month_surface	float	❌	°C	最冷月地表温度	KAIMEN
temp_hottest_month_surface	float	❌	°C	最热月地表温度	KAIMEN
temp_coldest_month_5m	float	❌	°C	最冷月地下5m温度	KAIMEN
temp_hottest_month_5m	float	❌	°C	最热月地下5m温度	KAIMEN
temp_coldest_month_10m	float	❌	°C	最冷月地下10m温度	KAIMEN
temp_hottest_month_10m	float	❌	°C	最热月地下10m温度	KAIMEN
dust	types	array	❌	—	["浮尘","扬沙","沙尘暴","强沙尘暴"]	1239
altitude	type	enum	❌	—	PLATEAU/NON_PLATEAU	1239
value	float	❌	m	海拔高度	1239/ZPC
air_quality	components	object	❌	mg/m³	空气成分	ZPC §2.2.16
air_quality.components子结构：

json
{
  "o2": null, "n2": null, "ar": null,
  "co2": null, "ch4": null, "c2h2": null,
  "c2h4": null, "c2h6": null, "c3h3": null,
  "c3h8": null, "c4_plus": null, "co": null,
  "h2": null, "nh3": null, "so2_so3": null,
  "hcl": null, "cl2": null, "n2o": null,
  "no_nox": null, "h2s": null,
  "tsp": null, "pm10": null, "pm2_5": null
}
2.2.2.8 cooling_tower_design_parameters（冷却塔设计气象参数）
字段名	类型	必填	单位	说明	来源
wet_bulb_temp	float	❌	°C	对应的湿球温度	ZPC §2.2.15
dry_bulb_temp_range	string	❌	°C	对应的干球温度范围	ZPC §2.2.15
design_atm_pressure_range	string	❌	hPa	对应的设计大气压力范围	ZPC §2.2.15
max_pressure	float	❌	hPa	对应的最高气压	ZPC §2.2.15
min_pressure	float	❌	hPa	对应的最低气压	ZPC §2.2.15
relative_humidity_range	string	❌	%	对应的相对湿度范围	ZPC §2.2.15
wind_speed_range	string	❌	m/s	对应风速范围	ZPC §2.2.15
status	enum	❌	—	HOLD/CONFIRMED（待定/确认）	ZPC
2.2.2.9 ocean_hydrology（海洋水文）
字段名	类型	必填	单位	说明	来源
max_tidal_stage	float	❌	cm	最高潮位	ZPC §2.2.11
min_tidal_stage	float	❌	cm	最低潮位	ZPC
avg_high_tidal_stage	float	❌	cm	平均高潮位	ZPC
avg_low_tidal_stage	float	❌	cm	平均低潮位	ZPC
avg_tidal_stage	float	❌	cm	平均潮位	ZPC
max_tidal_range	float	❌	cm	最大潮差	ZPC
min_tidal_range	float	❌	cm	最小潮差	ZPC
avg_tidal_range	float	❌	cm	平均潮差	ZPC
avg_flood_duration	string	❌	—	平均涨潮历时	ZPC
avg_ebb_duration	string	❌	—	平均落潮历时	ZPC
freq_0_1pct_high_tide	float	❌	cm	频率0.1%最高潮位	ZPC
freq_1pct_high_tide	float	❌	cm	频率1%高潮位	ZPC
guarantee_99pct_low_tide	float	❌	cm	保证率99%最低潮位	ZPC
guarantee_97pct_low_tide	float	❌	cm	保证率97%低潮位	ZPC
water_temp	object	❌	°C	海水温度	ZPC
water_temp子结构：

json
{
  "hot_5yr_freq10pct_daily_avg": 27.3,
  "annual_avg": 17.4,
  "hottest_month_avg": 26.6,
  "coldest_month_avg": 7.9,
  "max": 27.8,
  "min": 5.6
}
2.2.3 site_conditions.hydrogeology（水文/地质/地震）
2.2.3.1 tide（潮位—— 河口/近海项目）
字段名	类型	必填	单位	说明	来源
annual_avg_differential	float	❌	m	年平均潮差	KAIMEN §4.3
max_differential	float	❌	m	最大潮差	KAIMEN
annual_avg_high	float	❌	m	年平均高潮位	1239/KAIMEN
annual_avg_low	float	❌	m	年平均低潮位	1239/KAIMEN
avg_level	float	❌	m	平均潮位	KAIMEN
max_recorded	float	❌	m	历史最高潮位	KAIMEN
min_recorded	float	❌	m	历史最低潮位	KAIMEN
avg_flood_duration	float	❌	h	年平均涨潮历时	KAIMEN
avg_ebb_duration	float	❌	h	年平均落潮历时	KAIMEN
design_max_0yr	float	❌	m	设计最高潮位(0年一遇)	KAIMEN
design_max_100yr	float	❌	m	设计最高潮位(100年一遇)	KAIMEN
design_max_200yr	float	❌	m	设计最高潮位(200年一遇)	KAIMEN
freq_high	float	❌	m	频率分析高潮位	1239
freq_low	float	❌	m	频率分析低潮位	1239
max_wave_height	float	❌	m	最大海浪高度	1239
flow_direction_velocity	string	❌	—	流向和流速	1239
2.2.3.2 river（河流）
字段名	类型	必填	单位	说明	来源
flood_level	float	❌	m	洪水位	1239
flood_std_reference	string	❌	—	防洪标准引用	1239
flood_std_table	array	❌	—	企业等级-防洪标准表	1239
low_water_level	float	❌	m	枯水位	1239
2.2.3.3 geology（地质）
字段名	类型	必填	单位	说明	来源
groundwater_depth	float	❌	m	场地地下水深度	1239
site_class	enum	❌	—	场地类别（Ⅰ/Ⅱ/Ⅲ/Ⅳ）	1239/KAIMEN
terrain_roughness	enum	❌	—	地面粗糙度（A/B/C/D）	1239/KAIMEN/ZPC
corrosion_evaluation_ref	string	❌	—	水土腐蚀性评价附件	1239
geotechnical_report_ref	string	❌	—	岩土勘察报告附件	1239/KAIMEN
2.2.3.4 seismic（地震）
字段名	类型	必填	单位	说明	来源
fortification_intensity	int	✅	度	抗震设防烈度	三份文档均有
basic_acceleration	float	✅	g	设计基本地震加速度	KAIMEN/ZPC
design_group	enum	❌	—	设计地震分组（Ⅰ/Ⅱ/Ⅲ）	三份文档均有
site_category	string	❌	—	场地类别	ZPC
characteristic_period	string	❌	—	设计特征周期	ZPC
load_spec	string	❌	—	抗震设计规范引用	DICT-001
2.2.4 site_conditions.transport_limits（运输限界）
字段名	类型	必填	说明	来源
max_size_weight_equipment	array	❌	设备最大尺寸和重量限制	ZPC §2.4
note	string	❌	运输注意事项	ZPC
max_size_weight_equipment子结构：

json
[
  {
    "equipment_name": "Hydrogenation reactor",
    "specification": "φ5500×44000(T.L.)",
    "weight_ton": 1400
  },
  {
    "equipment_name": "Vacuum tower",
    "specification": "Φ5600/8600/12000/5600×48060(T.L.)",
    "weight_ton": 530
  }
]
2.3 feedstock（原料来源和组成）🔵
字段名	类型	必填	说明	来源
crude_oil	object	❌	原油来源和组成	ZPC §3.1
fuel_coal	object	❌	燃料煤规格	ZPC §3.2
coal_for_h2	object	❌	煤焦制氢煤质要求	ZPC §3.3
crude_oil子结构：

json
{
  "procurement_regions": ["Middle East", "Africa", "Southeast Asia", "South America(long term)"],
  "phase_i": {
    "train_i": {"description": "50% Saudi medium + 50% Iran light", "type": "high sulfur medium"},
    "train_ii": {"description": "70% Iran heavy + 30% Brazil Frade", "type": "high sulfur acidic"}
  },
  "phase_ii": {
    "description": "50% Saudi light + 50% Saudi heavy",
    "type": "high sulfur medium"
  }
}
fuel_coal子结构：

json
{
  "total_sulfur_pct": 1.2,
  "ash_pct": "25.0~30",
  "total_moisture_pct": 12,
  "volatile_matter_pct": "20~25",
  "net_heating_value_mj_kg": "20000~21000"
}
coal_for_h2子结构：

json
{
  "ash_fusion_temp_c": 1350,
  "coal_water_slurry_concentration_pct": 60
}
2.4 utilities（公用工程条件）
2.4.1 utilities.water_systems（水系统）
水系统类型清单：

水系统	字段名	来源
生产给水	process_water	1239 §2.1.1
工业水	industrial_water	KAIMEN §6.3
生产水（海水淡化）	production_water	ZPC §4.6
开式循环冷却水	cooling_water_open	ZPC §4.1
闭式循环冷却水	cooling_water_closed	ZPC §4.1
海水冷却水	seawater_cooling	ZPC §4.1
一次冷却水	primary_cooling_water	KAIMEN §6.6
二次冷却水	secondary_cooling_water	KAIMEN §6.7
冷冻水	chilled_water	KAIMEN §6.8
热水	hot_water	KAIMEN §6.9 / ZPC §4.9
生活给水	domestic_water	1239 §2.1.3 / KAIMEN §6.5 / ZPC §4.5
消防给水	fire_water	1239 §2.1.4 / KAIMEN §6.10 / ZPC §4.7
回用水	reused_water	ZPC §4.8
凝结水	condensate	1239 §2.1.7 / KAIMEN §6.2 / ZPC §4.3
除盐水	demineralized_water	1239 §2.1.8 / KAIMEN §6.4 / ZPC §4.4
除氧水	deoxygenated_water	1239 §2.1.9
生产污水	polluted_drainage	1239 §2.1.5 / ZPC §4.19
雨水	rain_drainage	1239 §2.1.6
每种水系统的通用结构：

json
{
  "bl_condition": {
    "p_min": null, "p_nor": null, "p_max": null, "p_design": null,
    "t_oper": null, "t_design": null, "rating_class": null,
    "line_size": null, "max_flow": null, "nor_flow": null,
    "boundary_isolation": null, "test_method": null, "cleaning_method": null
  },
  "quality": {}
}
各水系统的quality参数集：

水系统	quality参数
process_water	pH, turbidity, Ca²⁺, Fe²⁺, temp_range, pressure, total_hardness, nitrate, chloride, sulfate, solid_residue, nitrite, oil, surfactant, phenol_index, ammonia
industrial_water	pH, turbidity, TSS, TDS, chloride, free_chlorine, CODcr
production_water	pH, TDS, conductivity, total_iron, sodium, potassium, chloride, sulfate, calcium, phosphate, silica, manganese, TOC, TSS, turbidity
cooling_water_open	pH, turbidity, chloride, oil, fouling_factor
cooling_water_closed	pH, conductivity, fouling_factor
seawater_cooling	TSS, salinity
primary_cooling_water	pH, turbidity, fouling_factor, Cu²⁺, Cl⁻, SiO₂, NH₃-N, free_chlorine, oil, Fe, hardness_alkalinity, SO₄²⁻+Cl⁻, COD
secondary_cooling_water	pH, conductivity, total_hardness, silica, Fe, DOC, SO₄²⁻, Cl⁻, oil, CFU
chilled_water	glycol_content
hot_water	pH, conductivity, silica, Fe, DOC, SO₄²⁻, Cl⁻, fouling_factor
domestic_water	pH, chroma, turbidity, Al, Fe, Mn, Cu, Zn, chloride, sulfate, TDS, total_hardness, oxygen_utilization, bacteria, As, Cd, Cr⁶⁺, Pb, Hg, cyanide, nitrate_N, chloroform, CCl₄
fire_water	pH, turbidity, Ca²⁺, Fe²⁺, temp, pressure
reused_water	pH, temp, oil, NH₃-N, phosphate, conductivity, CODcr, TDS, total_alkalinity, total_hardness, Cl⁻, turbidity, free_Cl₂
condensate	pH, conductivity, silica, Na/K, Fe, Cu, ammonia, oil, hardness
demineralized_water	pH, conductivity, silica, Fe, Cu, Na, TDS, Cl⁻, carbonate, turbidity, TOC
deoxygenated_water	hardness, dissolved_O₂, pH, Fe, Cu, oil, SiO₂, conductivity, temp, steam_pressure
polluted_drainage	pH, CODcr, BOD₅, SS, oil, sulphide, NH₃-N, volatile_phenol, temp, pressure, TDS, CN⁻, Cr⁶⁺, Cr, Zn, Cu, Pb, As, Hg, Cd, Ni, Mn, Fe, anionics, chloride
rain_drainage	pH, CODcr, oil, temp, pressure
2.4.2 utilities.steam_grades（蒸汽等级）
字段名	类型	必填	单位	说明	来源
grade	string	✅	—	等级名称（SS/HS/MS/LS）	KAIMEN/ZPC
source	string	❌	—	蒸汽来源	KAIMEN
oper_press	object	❌	MPaG	{min, nor, max}	三份文档均有
oper_temp	object	❌	°C	{min, nor, max}	三份文档均有
design_press	float	✅	MPaG	设计压力	三份文档均有
design_temp	float	✅	°C	设计温度	三份文档均有
rating_class	int	❌	—	法兰等级	KAIMEN
bl_line_size	string	❌	—	界区管线尺寸	KAIMEN
max_flow	float	❌	t/h	最大流量	KAIMEN
nor_flow	float	❌	t/h	正常流量	KAIMEN
boundary_isolation	string	❌	—	界区隔离要求	KAIMEN
test_method	string	❌	—	试验方法	KAIMEN
cleaning_method	string	❌	—	清洗方法	KAIMEN
quality	object	❌	—	蒸汽品质	KAIMEN/ZPC
quality子结构：

json
{
  "ph": null, "conductivity": null, "tc": null,
  "silica": null, "sodium": null, "potassium": null,
  "iron": null, "copper": null, "ammonia": null
}
2.4.3 utilities.air_systems（空气系统）
系统	字段名	来源
工厂空气	plant_air	KAIMEN §6.11 / ZPC §4.11
仪表空气	instrument_air	KAIMEN §6.11 / ZPC §4.12
呼吸空气	breathing_air	KAIMEN §6.12
每个空气系统子结构：

json
{
  "supply_capacity": null,
  "dew_point": null,
  "min_press": null, "nor_press": null, "max_press": null, "design_press": null,
  "oil_content": null, "dust_content": null, "dust_diameter": null,
  "temp_oper": null, "temp_design": null,
  "note": null
}
2.4.4 utilities.nitrogen（氮气）
字段名	类型	必填	说明
grades	array	✅	氮气等级数组
grades子结构：

json
[
  {
    "grade": "LP",
    "bl_condition": {"p_min": null, "p_nor": null, "p_max": null, "p_design": null,
                      "t_oper": null, "t_design": null},
    "quality": {"purity": null, "o2": null, "co2": null, "co": null, "dew_point": null}
  }
]
2.4.5 utilities.fuel_gas（燃料气）🔵
字段名	类型	必填	说明	来源
source	string	❌	燃料气来源描述	ZPC §4.10
header_pressure	string	❌	管网压力维持值	ZPC
h2s_max_ppm	float	❌	H₂S最大含量	ZPC
composition	object	❌	组成（Vol%，nor/min/max三列）	1239
heat_tracing	enum	❌	伴热要求	1239
net_heating_value	float	❌	净热值 kJ/kg	1239
specific_gravity	float	❌	比重	1239
2.4.6 utilities.natural_gas（天然气）
字段名	类型	必填	说明	来源
bl_condition	object	❌	界区条件	KAIMEN §6.14
composition	object	❌	组成	1239 §2.6.2
quality_std	string	❌	气质标准（如12T）	KAIMEN
line_size	string	❌	管线尺寸	KAIMEN
max_flow	float	❌	最大流量 Nm³/h	KAIMEN
nor_flow	float	❌	正常流量 Nm³/h	KAIMEN
boundary_isolation	string	❌	界区隔离	KAIMEN
test_method	string	❌	试验方法	KAIMEN
cleaning_method	string	❌	清洗方法	KAIMEN
2.4.7 utilities.fuel_oil（燃料油）🔵
字段名	类型	必填	单位	说明	来源
supply_press	float	❌	MPaG	供应总管操作压力	1239
return_press	float	❌	MPaG	返回管操作压力	1239
supply_temp	object	❌	°C	{max, nor, min}	1239
design_press	float	❌	MPa	设计压力	1239
design_temp	float	❌	°C	设计温度	1239
properties	object	❌	—	燃料油性质	1239
properties子结构：

json
{
  "api": null, "net_heating_value": null,
  "viscosity_100c": null, "viscosity_120c": null,
  "vapor_pressure": null, "flash_point": null,
  "pour_point": null, "sulfur": null,
  "nitrogen": null, "vanadium": null,
  "sodium": null, "nickel": null,
  "iron": null, "ash": null, "water": null,
  "particulates": null
}
2.4.8 utilities.hydrogen（氢气）
字段名	类型	必填	说明	来源
supply_press	float	❌	供应压力 MPaG	1239
return_press	float	❌	返回压力 MPaG	1239
supply_temp	object	❌	{max, nor} °C	1239
design_press	float	❌	设计压力 MPa	1239
design_temp	float	❌	设计温度 °C	1239
molecular_weight	float	❌	分子量	1239
composition	object	❌	组成（Vol%）	1239
other_impurities	object	❌	其他杂质	1239
grades	array	❌	多压力等级	ZPC §4.16
grades子结构（ZPC格式）：

json
[
  {"grade": "LP", "pressure_mpag": 2.3, "temperature_c": 40},
  {"grade": "MP", "pressure_mpag": 4.8, "temperature_c": 40}
]
2.4.9 utilities.oxygen（氧气）🔵
字段名	类型	必填	说明	来源
purity	string	❌	纯度 mol%	ZPC §4.13
argon_nitrogen	string	❌	氩+氮 mol%	ZPC
grades	array	❌	压力等级	ZPC
2.4.10 utilities.hot_oil（导热油）
字段名	类型	必填	说明	来源
bl_condition	object	❌	界区条件	KAIMEN §6.15
fluid_type	string	❌	导热油类型	KAIMEN
composition_description	string	❌	组分描述	KAIMEN
properties	object	❌	性质	1239 §2.12.2
properties子结构：

json
{
  "api": null, "specific_gravity": null,
  "viscosity": null, "vapor_pressure": null,
  "flash_point": null, "pour_point": null,
  "auto_ignition": null, "thermal_conductivity": null,
  "thermal_expansion": null
}
2.4.11 utilities.chemicals（化学品）
化学品	字段名	说明	来源
碱液	caustic	{strength, bl_pressure, bl_temp, design_press, design_temp}	1239/KAIMEN
MDEA	mdea	同碱液	KAIMEN
硫酸	sulphuric_acid	{strength, supply_method}	ZPC §4.15
2.4.12 utilities.electrical（电气）
字段名	类型	必填	单位	说明	来源
incoming_voltage	string	✅	kV	进线电源电压	1239/KAIMEN/ZPC
frequency	float	✅	Hz	额定频率	KAIMEN/ZPC
voltage_levels	array	❌	—	电压等级列表	KAIMEN/ZPC
voltage_variation_range	string	❌	—	电压波动范围	KAIMEN/ZPC
freq_variation_range	string	❌	—	频率波动范围	KAIMEN/ZPC
motor_env	enum	❌	—	电机环境	1239
grounding_methods	object	❌	—	各等级接地方式	ZPC
motor_voltage_selection	array	❌	—	电机电压选择	KAIMEN/ZPC
voltage_levels子结构（ZPC格式更详细）：

json
[
  {"voltage_kv": 220, "variation": "±7%", "frequency": "50±0.5Hz", "grounding": "3ph3w neutral solid grounded"},
  {"voltage_kv": 110, "variation": "±7%", "frequency": "50±0.5Hz", "grounding": "3ph3w neutral solid grounded"},
  {"voltage_kv": 35, "variation": "±7%", "frequency": "50±0.5Hz", "grounding": "3ph3w resistor grounded"},
  {"voltage_kv": 10, "variation": "±7%", "frequency": "50±0.5Hz", "grounding": "3ph3w ungrounded/Petersen"},
  {"voltage_kv": 0.38, "variation": "±10%", "frequency": "50±0.5Hz", "grounding": "3ph4w TN-S/TN-C-S"}
]
2.5 design_life（设计寿命）
字段名	类型	必填	单位	说明	来源
equipment	object	❌	年	设备设计寿命分类	KAIMEN §5.1
piping	object	❌	年	管道设计寿命分类	KAIMEN
structure	float	❌	年	结构设计寿命	KAIMEN
equipment子结构：

json
{
  "spherical_tank": 25,
  "column_reactor_spiral_hx": 25,
  "normal_vessel_tubular_hx_plate_hx_tank_silo": 20,
  "rotating_equipment": 20
}
piping子结构：

json
{
  "isbl_osbl_except_jacket": 15,
  "jacket_pipe": 10,
  "offsite_pipeline": 20
}
2.6 operation（操作时间与检修）
字段名	类型	必填	单位	说明	来源
hours_per_year	int	✅	h/yr	年运行小时数	KAIMEN §5.2
design_operating_hours	float	❌	h/yr	设计运行小时数	KAIMEN
operating_rate_pct	float	❌	%	运行率	KAIMEN
maintenance_cycle_years	int	❌	年	检修周期	ZPC §1.2
2.7 regulatory（法规/标准/规范）
字段名	类型	必填	说明	来源
precedence	array	✅	优先级顺序	KAIMEN §3.1
regulations	array	❌	中国EH&S标准规范清单	KAIMEN §3.2 / ZPC §7
owner_requirements	object	❌	业主特殊要求	KAIMEN §3.4
regulations子结构：

json
[
  {
    "code": "GB50160-2008",
    "name": "石油化工企业设计防火规范",
    "name_en": "Fire prevention code of petrochemical enterprise design",
    "category": "FIRE"
  }
]
owner_requirements子结构：

json
{
  "guide_notes": ["Working at Height", "Dropped Objects", "..."],
  "iggn_documents": ["OPS-SHE-01: ...", "..."],
  "ascare_requirements": ["All steelwork galvanized", ">70% AsCare", "..."]
}
2.8 battery_limits（界区条件）
数组格式，每个元素：

字段名	类型	必填	单位	说明	来源
no	int	✅	—	序号	1239/ZPC
medium	string	✅	—	介质名称	三份文档均有
temp_nor	string	❌	°C	正常温度（可含括号设计值）	1239
temp_design	string	❌	°C	设计温度	KAIMEN
press_nor	string	❌	MPaG	正常压力	1239
press_design	string	❌	MPaG	设计压力	1239
startup_shutdown	string	❌	—	开工/停工条件	1239
dn	string	❌	—	管径	1239
max_flow	float	❌	按介质	最大流量	KAIMEN
nor_flow	float	❌	按介质	正常流量	KAIMEN
boundary_isolation	string	❌	—	界区隔离	KAIMEN
test_method	string	❌	—	试验方法	KAIMEN
cleaning_method	string	❌	—	清洗方法	KAIMEN
remark	string	❌	—	备注	1239
2.9 units（单位制约定）
字段名	类型	说明	来源
temperature	string	°C	三份文档均有
pressure_gauge	string	MPa(G)/barg	三份文档均有
pressure_absolute	string	kPa(a)	KAIMEN
differential_pressure	string	kPa	ZPC
flowrate	string	m³/h	KAIMEN
gas_std_flow	string	Nm³/h	三份文档均有
mass_flowrate	string	kg/h	三份文档均有
density	string	kg/m³	三份文档均有
dynamic_viscosity	string	cP/mPa·s	三份文档均有
kinematic_viscosity	string	cSt	KAIMEN
heating_value_gas	string	MJ/Nm³	KAIMEN
heating_value_liquid	string	MJ/kg	KAIMEN
fouling_factor	string	m²·°C/kW	KAIMEN
heat_transfer_coefficient	string	W/m²·°C	KAIMEN/ZPC
specific_heat	string	kJ/kg·°C	KAIMEN/ZPC
thermal_conductivity	string	W/m·°C	KAIMEN/ZPC
velocity	string	m/s	KAIMEN/ZPC
notes	array	附加说明	KAIMEN/ZPC
2.10 discipline_criteria（各专业设计准则文档引用）
字段名	类型	必填	说明	来源
general_plot_plan	string	❌	总图设计准则文档号	KAIMEN §7.1
process	string	❌	工艺设计准则文档号	KAIMEN §7.2
material_handling	string	❌	物料处理准则文档号	KAIMEN §7.3
piping	string	❌	管道设计准则文档号	KAIMEN §7.5
piping_material	object	❌	管道材料相关文档	KAIMEN §7.6
piping_stress	string	❌	管道应力文档号	KAIMEN §7.7
static_equipment	string	❌	静设备设计准则	KAIMEN §7.8
rotating_equipment	string	❌	转动机器设计准则	KAIMEN §7.9
instrument	string	❌	仪表设计准则	KAIMEN §7.10
telecom	string	❌	通信设计准则	KAIMEN §7.11
electrical	string	❌	电气设计准则	KAIMEN §7.12
hvac	string	❌	HVAC设计准则	KAIMEN §7.13
plumbing_firefighting	array	❌	给排水/消防文档列表	KAIMEN §7.14
civil_structure	string	❌	土建结构设计准则	KAIMEN §7.15
architecture	string	❌	建筑设计准则	KAIMEN §7.16
第三部分：关联关系
关系	说明
projects.bedd_json	本文档定义其完整JSON结构
PMS表单生成	P3阶段按本字典动态生成表单
输入清单	BEDD中的必填字段自动成为输入清单REQUIRED项
单位制联动	project_info.unit_system决定数值基准单位
校验规则	字段范围和单位校验在Schema中定义
项目模板	按项目类型（炼化/化工/公用工程）预设不同BEDD结构
第四部分：版本历史
版本	日期	修改内容
V1.0	2026-08-29	初始版本，合并合同技术附件二（1239）、INEOS KAIMEN BEDD、浙石化设计基础（1193E），结合DICT-001 §3.2~3.9
PCS-DICT-004完。 本文档作为projects.bedd_json的完整结构字典，涵盖10组顶层字段，综合三份真实工程文件的气象/水文/地质/公用工程/原料/界区条件的完整字段定义，并标注数据来源。P3阶段PMS开发以此为准。
