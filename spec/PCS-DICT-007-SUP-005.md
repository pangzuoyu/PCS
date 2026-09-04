PCS-DICT-007 增补文件五
文件标识	PCS-DICT-007-SUP-005
当前版本	V1.5
发布日期	2026-08-29
增补基准	PCS-DICT-007 V2.0 + SUP-004（阀门数据表）
新增参考	起重设备数据表实例（ME-02/D4101，项目1216B132，电动双梁起重机132-X-501）
1. 增补说明
1.1 新增素材价值
本素材是起重设备（电动双梁桥式起重机）的完整数据表实例，补充了EQUIP_LIST中TypeCode=CR（Crane）类型的结构：

维度	已有设备类型	本增补（起重机）
设备类型	容器/塔/球罐/过滤器/阀门	起重设备（CR）
特有字段	工艺/机械/材质	主钩/副钩参数、大车/小车参数、跨度/轮压/轨面标高、防爆等级
现场条件	温度/压力	海拔/风压/电气区域/防爆/电源
几何尺寸	直径/长度	跨度Lk/宽度B/高度H/H2/距离b
2. 起重机数据表完整JSON结构（crane_data_sheet_json）
2.1 顶层结构
json
{
  "general": {},              // 概况
  "site_utilities": {},       // 现场及公用工程条件
  "technical_requirements": {}, // 技术要求
  "hooks": {},                // 主钩/副钩参数
  "cart_trolley": {},         // 大车/小车参数
  "geometric": {},            // 几何尺寸
  "electrical_requirements": {}, // 电气要求
  "weights": {},              // 质量
  "others": {},               // 执行标准/制造商
  "notes": [],                // 说明
  "sketch_ref": null          // 简图引用
}
2.2 general（概况）
字段名	类型	必填	说明
item_number	string	✅	设备编号（如132-X-501）
service	string	✅	设备名称（如电动双梁起重机）
used_for	string	✅	用途（如补充氢压缩机组检修用）
location	string	✅	安装地点（如补充氢压缩机棚内）
quantity_required	int	✅	数量（1台）
quantity_online	int	❌	操作数
operating_mode	enum	❌	CONTINUOUS/INTERMITTENT/SPARE
2.3 site_utilities（现场及公用工程条件）
字段名	类型	必填	单位	说明
elevation_m	float	❌	m	海拔
atmospheric_pressure_kpaa	float	✅	kPaA	气压（100.31）
wind_pressure_pa	float	❌	Pa	风压（714）
min_ambient_temp_c	float	✅	°C	最低温度（0.5）
max_ambient_temp_c	float	✅	°C	最高温度（38.9）
min_relative_humidity_pct	float	❌	%	最低相对湿度（8）
max_relative_humidity_pct	float	❌	%	最高相对湿度（82）
electrical_region	string	✅	—	电气区域（dIIBT4/2区）
explosion_flammable_condition	bool	✅	—	易燃易爆气体环境（是）
power_supply	object	✅	—	电源条件
power_supply子结构：

json
{
  "voltage_v": 380,
  "frequency_hz": 50,
  "phase": 3
}
2.4 technical_requirements（技术要求）
字段名	类型	必填	说明
crane_model	string	✅	起重设备型号（BQG）
crane_type	enum	✅	起重设备型式（电动双梁桥式）
operating_grade	enum	❌	工作制度（A3）
2.5 hooks（主钩/副钩参数）
字段名	类型	必填	单位	说明
main_hook	object	❌	—	主钩参数
sub_hook	object	❌	—	副钩参数
main_hook子结构：

json
{
  "lifting_weight_t": 32,
  "lifting_height_m": 12.5,
  "lifting_velocity_m_min": null,
  "motor_power_kw": 15
}
sub_hook子结构：

json
{
  "lifting_weight_t": 5,
  "lifting_height_m": null,
  "lifting_velocity_m_min": null,
  "motor_power_kw": 4
}
2.6 cart_trolley（大车/小车参数）
字段名	类型	必填	单位	说明
cart	object	❌	—	大车参数
trolley	object	❌	—	小车参数
cart子结构：

json
{
  "moving_velocity_m_min": null,
  "motor_power_kw": 4,
  "travel_m": null,
  "railway_type": "QU70",
  "max_wheel_pressure_kn": 259
}
trolley子结构：

json
{
  "moving_velocity_m_min": null,
  "motor_power_kw": 3
}
2.7 geometric（几何尺寸）
字段名	类型	必填	单位	说明
span_lk_m	float	✅	m	跨度Lk（16.5）
railway_surface_level_m	float	❌	m	轨道表面标高（13）
length_railway_to_crane_top_h_mm	float	❌	mm	轨面至起重机顶端距离H（2681）
crane_max_width_b_mm	float	❌	mm	起重机最大宽度B（6560）
length_railway_center_to_crane_end_b_mm	float	❌	mm	轨道中心至起重机外端距离b（250）
length_main_hook_to_railway_h2_mm	float	❌	mm	主钩顶面至轨面距离H2（424）
2.8 electrical_requirements（电气要求）
json
{
  "power_introduction_method": "CABLE",
  "lead_junction_boxes": true,
  "sliding_contact_line": {
    "type": "四线式安全滑触线",
    "load_current_a": "≥150A",
    "protection_grade": "≥IP23",
    "current_collector": "双组集电器，80A",
    "installation_std": "90D401-1"
  },
  "traction_manual_kn": null
}
2.9 weights（质量）
字段名	类型	必填	单位	说明
total_weight_kg	float	✅	kg	设备总质量（31000）
cart_total_weight_kg	float	❌	kg	大车总质量
trolley_total_weight_kg	float	❌	kg	小车总质量
2.10 others（其他）
字段名	类型	必填	说明
codes_specs	string	❌	执行标准
manufacturer	string	❌	制造厂商
2.11 notes（说明）
备注键	内容
MOTOR_SPEC	"电机选用户外、湿热型，防爆等级为dⅡCT4"
PRELIMINARY_ONLY	"本数据表仅作为基础设计使用，不作为订货依据"
3. 枚举定义
3.1 CraneType（起重机类型）
枚举值	中文
ELECTRIC_DOUBLE_GIRDER_BRIDGE	电动双梁桥式起重机
ELECTRIC_SINGLE_GIRDER_BRIDGE	电动单梁桥式起重机
GANTRY	门式起重机
JIB	悬臂起重机
MONORAIL	单轨吊
HOIST	电动葫芦
OVERHEAD_CRANE	桥式起重机（通用）
3.2 OperatingGrade（工作制度，GB/T 3811）
枚举值	说明
A1	轻级（很少使用）
A2	轻级
A3	中级（间歇使用，本实例）
A4	中级
A5	重级
A6	重级
A7	超重级
A8	超重级（连续使用）
3.3 PowerIntroductionMethod（电源引入方式）
枚举值	中文
CABLE	电缆
SLIDING_CONTACT_LINE	滑触线
CABLE_REEL	电缆卷筒
3.4 OperatingMethod（操纵方式）
枚举值	中文
GROUND	地面操作
CAB	司机室操作
REMOTE	遥控
AUTO	自动
4. 与EQUIP_LIST的映射
equipment_list字段	crane_data_sheet_json
type_code	CR（Crane）
tag_number	general.item_number
equipment_description	general.service
equipment_category	ROTATING_EQUIPMENT（转动设备）
design_parameters_json	完整crane_data_sheet_json
5. 版本历史
版本	日期	修改内容
V1.0~V1.4	2026-08-29	初始+容器+塔+球罐+阀门
V2.0	2026-08-29	完整整合版
V1.5	2026-08-29	增补起重设备数据表（SUP-005），新增crane_data_sheet_json
增补完成。 PCS-DICT-007现覆盖起重设备（CR）数据表结构，含7种起重机类型、8级工作制度（A1-A8）、4种操纵方式枚举。P7阶段EQUIP_LIST起重机类型录入以此为准
