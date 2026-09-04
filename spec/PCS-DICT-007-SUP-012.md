PCS-DICT-007 增补文件十二
文件标识	PCS-DICT-007-SUP-012
当前版本	V1.12
发布日期	2026-08-29
增补基准	PCS-DICT-007 V3.0
新增参考	冷却塔数据表实例（CC0913D1353-20-PR-DAS-2101，常熟高泰助剂C2101-1/2，机械通风逆流冷却塔，2格×500m³/h）
1. 增补说明
1.1 新增素材价值
本素材填补了cooling_tower_results.data_sheet_json的高优先级缺口：

维度	V3.0已有（平铺字段）	本增补新增
cooling_tower_results	duty/water_flow/makeup_water/fan_power/tower_type 5个平铺字段	✅ 完整冷却塔数据表JSON结构
冷却塔类型	简单枚举	✅ 机械通风逆流（MECHANICAL_DRAFT_COUNTERFLOW）
结构材料	❌	✅ 15种部件材质（镀锌碳钢/FRP/PVC/不锈钢/ABS）
风机系统	仅fan_power	✅ 风机/驱动机/减速器/联轴器完整参数
填料	❌	✅ 类型/尺寸/体积/压降
噪声/试验	❌	✅ GB7190.1-2008标准
备注	❌	✅ 16条详细技术要求
2. 冷却塔数据表完整JSON结构（cooling_tower_data_sheet_json）
2.1 顶层结构
json
{
  "general": {},                // 概况
  "performance": {},            // 性能参数
  "construction": {},           // 结构材料
  "structure_details": {},      // 结构尺寸
  "fan_driver": {},             // 风机驱动机
  "fan_data": {},               // 风机数据
  "speed_reducer": {},          // 减速器
  "coupling": {},               // 联轴器
  "filling": {},                // 填料
  "piping_connection": {},      // 管道连接
  "sound": {},                  // 噪声
  "test_inspection": {},        // 试验与检验
  "remarks": [],                // 备注
  "sketch_ref": null            // 简图引用
}
2.2 general（概况）
字段名	类型	必填	说明
item_number	string	✅	设备编号（如C2101-1/2）
service	string	✅	服务名称（如Cooling Water System）
quantity_total	int	✅	总数量（2台）
quantity_working	int	✅	运行数（2）
quantity_standby	int	❌	备用数（0）
doc_no	string	✅	文件号
rev	string	✅	版次
phase	enum	❌	阶段（DETAIL_DESIGN详细设计）
unit_name	string	❌	装置/工区名称
project_name	string	❌	项目名称
2.3 performance（性能参数）
字段名	类型	必填	单位	说明
tower_type	enum	✅	—	冷却塔类型
manufacturer	string	❌	—	制造商（*厂家填）
model	string	❌	—	型号（*厂家填）
total_flow_rate_m3h	float	✅	m³/h	总流量（1000）
flow_per_cell_m3h	float	✅	m³/h	单格循环水量（500）
number_of_cells	int	✅	—	格数（2）
hot_water_temp_c	float	✅	°C	进水（热水）温度（42）
cold_water_temp_c	float	✅	°C	出水（冷水）温度（32）
design_wet_bulb_temp_c	float	✅	°C	设计湿球温度（28.2）
design_dry_bulb_temp_c	float	❌	°C	设计干球温度（38.5）
design_heat_duty_per_cell_kw	float	❌	kW	单格设计热负荷
water_supply_pressure_mpa	float	✅	MPa	供水压力（泵出口）（0.50）
water_return_pressure_mpa	float	✅	MPa	回水压力（0.2）
elevation_above_sea_level_m	float	❌	m	海拔高度（2.30）
min_atmospheric_temp_c	float	✅	°C	最低大气温度（-11.53）
drift_loss_kg_hr_per_cell	float	❌	kg/hr	飘水损失
evaporation_loss_kg_hr_per_cell	float	❌	kg/hr	蒸发损失
blowdown_flow_kg_hr	float	❌	kg/hr	排污流量
makeup_water_kg_hr_per_cell	float	❌	kg/hr	补水流量
max_static_head_spray_m	float	❌	m	喷头最大静压头
max_wind_velocity_10min_10m_30yr_m_s	float	✅	m/s	30年一遇10分钟最大风速（21）
tower_site	enum	❌	—	塔位置（AT_GROUND地面）
2.4 construction（结构材料）
字段名	类型	必填	说明
tower_frame	string	✅	塔体框架（GALVANIZED_CARBON_STEEL镀锌碳钢）
casing	string	✅	塔壁板（FRP）
cold_water_basin	string	✅	冷水池（CONCRETE混凝土）
drift_eliminators_spacers	string	✅	收水器/填料间隔（PVC/FRP）
filling_material	string	✅	填料（PVC）
filling_support	string	❌	填料支撑（镀锌碳钢）
sliding	string	❌	滑动件（FRP）
inlet_louvers	string	❌	进风百叶窗（FRP）
hardware_joint_connectors	string	❌	紧固件/连接件（不锈钢）
drive_shaft_coupling	string	❌	传动轴/联轴器（不锈钢）
distribution_header_nozzles	string	❌	布水总管/喷头（PVC/ABS）
anchor_castings	string	❌	地脚螺栓（不锈钢）
motor_gear_support	string	❌	电机/减速器支撑（热镀锌碳钢）
fan_stack	string	❌	风机风筒（FRP）
fan_guard	string	❌	风机防护罩（NA）
shaft	string	❌	轴（不锈钢或厂家定）
nozzle	string	❌	喷头（ABS）
ladder_handrail	string	❌	梯子/栏杆（热镀锌碳钢）
2.5 structure_details（结构尺寸）
字段名	类型	必填	单位	说明
number_of_cells	int	✅	—	格数（2）
overall_dimensions_lxwxh_mm	string	❌	mm	总尺寸（长×宽×高）
outline_per_cell_lxw_mm	string	❌	mm	单格外形尺寸
basin_dimensions_lxw_mm	string	❌	mm	水池尺寸
basin_depth_mm	float	❌	mm	水池深度
fan_deck_height_above_curb_m	float	❌	m	风机平台高于池沿高度
fan_stack_height_mm	float	❌	mm	风机风筒高度
total_dynamic_head_m	float	❌	m	总动压头
stairway_per_tower	int	❌	—	楼梯数量
ladder_per_tower	int	❌	—	梯子数量
safety_cage_required	bool	❌	—	安全笼
safety_cage_material	string	❌	—	安全笼材质
dry_weight_per_cell_kg	float	❌	kg	单格干重
operating_weight_per_cell_kg	float	❌	kg	单格操作重
total_operating_weight_kg	float	❌	kg	总操作重
shipping_weight_kg	float	❌	kg	运输重量
shipping_cubage_m3	float	❌	m³	运输体积
2.6 fan_driver（风机驱动机）
字段名	类型	必填	说明
manufacturer	string	❌	制造商
model	string	❌	型号
number_of_units	int	✅	数量（2）
power_source	string	✅	电源（380V/3Ph/50Hz）
rated_power_per_unit_kw	float	❌	额定功率kW
speed_control	enum	✅	速度控制（TWO_SPEED/ONE_SPEED/VFD）
first_speed_rpm	float	❌	第一转速rpm
second_speed_rpm	float	❌	第二转速rpm
motor_type	enum	✅	电机类型（OPEN/TEFC/XP防爆）
protection_class	string	✅	防护等级（IP55）
insulation_class	string	✅	绝缘等级（F）
explosion_proof_grade	string	❌	防爆等级（Ex-d ⅡB T3）
vibration_switch_type_model_qty	string	❌	振动开关型号/数量
vibration_switch_manufacturer	string	❌	振动开关制造商
vibration_switch_location	string	❌	振动开关位置（减速器处）
2.7 fan_data（风机数据）
字段名	类型	必填	说明
number_per_cell	int	✅	每格数量（2）
manufacturer	string	❌	制造商
type	enum	✅	类型（AXIAL轴流）
model	string	❌	型号
blades_per_fan	int	❌	每台叶片数
diameter_m	float	❌	叶轮直径m
blade_material	string	✅	叶片材质（AI铝合金）
hub_material	string	❌	轮毂材质（铸钢）
speed_control	enum	❌	转速控制
first_second_speed_rpm	string	❌	第一/第二转速rpm
tip_speed_m_s	float	❌	叶尖速度m/s
air_volume_m3_min_cell	float	❌	风量m³/min/cell
design_exit_air_temp_c	float	❌	设计出口气温°C
design_static_press_mmh2o	float	❌	设计静压mmH₂O
design_velocity_press_mmh2o	float	❌	设计动压mmH₂O
power_per_fan_kw	float	❌	单台功率kW
total_power_kw	float	❌	总功率kW
efficiency_pct	float	❌	效率%
2.8 speed_reducer（减速器）
字段名	类型	必填	说明
number_per_cell	int	✅	每格数量（2）
manufacturer	string	❌	制造商
type_model	string	❌	类型/型号
reduction_ratio	float	❌	减速比
case_material	string	❌	箱体材质
efficiency_pct	float	❌	效率%
oil_temp_indicator_alarm	string	❌	油温指示和报警型号
oil_temp_mfr	string	❌	油温制造商
oil_lubrication_system	string	❌	润滑系统类型
oil_level_indication	string	❌	油位指示类型和位置
2.9 coupling（联轴器）
字段名	类型	必填	说明
manufacturer	string	❌	制造商
model	string	❌	型号
type	string	❌	类型
guard_type_material	string	✅	防护罩类型/材质（全封闭/镀锌碳钢）
furnished_installed_by	string	✅	供货方/安装方（SUPPLIER供应商）
2.10 filling（填料）
字段名	类型	必填	说明
type	string	❌	填料类型
film_pack_size_lxwxh_m	string	❌	膜片尺寸（长×宽×高）m
air_travel_m	float	❌	空气行程m（横流）
total_volume_m3	float	❌	总体积m³
vertical_spacing_mm	float	❌	垂直间距mm
horizontal_spacing_mm	float	❌	水平间距mm
material_dimensions_lxwxh_mm	string	❌	材料尺寸mm
pressure_drop_pa	float	❌	填料压降Pa
2.11 piping_connection（管道连接）
字段名	类型	必填	说明
piping_rating	string	✅	管道等级（1.6MPa）
standard_code	string	✅	标准（HG20592）
nozzles	array	✅	管口列表
nozzles子结构：

json
[
  {"mark": "WATER_INLET", "service": "进水口", "size": "*", "quantity": 1, "facing": "RF"},
  {"mark": "WATER_OUTLET", "service": "出水口", "size": "NA", "quantity": null, "facing": null},
  {"mark": "AUTO_FILL", "service": "自动补水", "size": "NA", "quantity": null, "facing": null},
  {"mark": "QUICK_FILL", "service": "快速补水", "size": "NA", "quantity": null, "facing": null},
  {"mark": "OVERFLOW", "service": "溢流", "size": "NA", "quantity": null, "facing": null},
  {"mark": "DRAIN", "service": "排水", "size": "NA", "quantity": null, "facing": null}
]
2.12 sound（噪声）
字段名	类型	必填	说明
measurement_distance	string	✅	测量距离（1m from any part of perimeter）
max_sound_level_dba	float	✅	最大噪声（78 dB(A)）
standard	string	✅	标准（GB 7190.1-2008）
2.13 test_inspection（试验与检验）
json
{
  "test_inspection": {
    "performance_test": "GB7190.1",
    "vibration_test": null,
    "balance_test": null,
    "blade_casting_test": null,
    "sound_level_test": "GB7190.1",
    "max_allow_sound_level": "GB7190.1",
    "certified_test_reports": "GB7190.1",
    "material_certificates": null
  }
}
2.14 remarks（备注，16条）
序号	内容
1	本地气象条件，供应商需根据项目现场条件确定，包括冷却塔格间相互影响
2	进水口应在冷却塔侧面
3	遵循GB7190.1-2008和CECS118-2000
4	必须使用齿轮减速器，皮带传动不可接受
5	FRP和PVC填料的氧指数不低于30
6	必须设置笼式梯子，梯子延伸至地面或混凝土平台
7	必须提供检修通道，电机四周至少700mm风机平台，风机风筒外侧至少1000mm
8	格宽≤7.310m时，风机风筒至侧壁距离可减至760mm
9	电机端传动轴和联轴器必须设置可拆卸防护罩
10	每个风机风筒内必须设置永久检修平台
11	平台和走道最小宽度900mm
12	外部梯子必须热镀锌
13	每根传动轴必须进行静动平衡，不平衡力不超过传动轴自重的5%
14	整个风机组件必须静平衡，允许业主见证试验
15	设备振动限值Veff=2.8 mm/s
16	必须提供三方向振动检测系统
3. 枚举定义
3.1 CoolingTowerType（冷却塔类型）
枚举值	中文
MECHANICAL_DRAFT_COUNTERFLOW	机械通风逆流冷却塔
MECHANICAL_DRAFT_CROSSFLOW	机械通风横流冷却塔
NATURAL_DRAFT	自然通风冷却塔
3.2 MotorType（电机类型）
枚举值	中文
OPEN	开启式
TEFC	全封闭风冷式
XP	防爆式（Explosion Proof）
3.3 SpeedControl（速度控制）
枚举值	中文
TWO_SPEED	双速
ONE_SPEED	单速
VFD	变频调速
3.4 TowerSite（塔位置）
枚举值	中文
AT_GROUND	地面安装
ON_ROOF	屋面安装
3.5 FanType（风机类型）
枚举值	中文
AXIAL	轴流式
CENTRIFUGAL	离心式
4. 与cooling_tower_results平铺字段的映射
cooling_tower_results字段	cooling_tower_data_sheet_json字段
duty	performance.design_heat_duty_per_cell_kw × number_of_cells
water_flow	performance.total_flow_rate_m3h
makeup_water	performance.makeup_water_kg_hr_per_cell × number_of_cells
fan_power	fan_data.total_power_kw
tower_type	performance.tower_type
tag_number	general.item_number
5. 版本历史
版本	日期	修改内容
V1.0~V1.11	2026-08-29	初始+10次增补
V2.0	2026-08-29	完整整合版
V3.0	2026-08-29	V2.0+SUP-001~011完整合并
V1.12	2026-08-29	增补冷却塔数据表（SUP-012），新增cooling_tower_data_sheet_json + 5组枚举
增补完成。 PCS-DICT-007 SUP-012填补了cooling_tower_results.data_sheet_json的高优先级缺口：

结构	内容
cooling_tower_data_sheet_json	14个子结构（性能/结构材料/结构尺寸/风机/减速器/联轴器/填料/管道/噪声/试验/备注）
5组新枚举	CoolingTowerType/MotorType/SpeedControl/TowerSite/FanType
