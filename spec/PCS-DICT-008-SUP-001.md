PCS-DICT-008 增补文件
文件标识	PCS-DICT-008-SUP-001
当前版本	V1.1
发布日期	2026-08-29
增补基准	PCS-DICT-008 V1.0
新增参考	Piping Prefabrication施工进度表（INEOS ABS项目）+ 设备表详细行（分液罐SEPARATOR实例）
1. 增补说明
1.1 新增素材价值
两份素材填补了equipment_list施工进度字段组和design_parameters_json按TypeCode展开的缺口：

维度	DICT-008已有	本增补新增
施工进度	仅TagIn3D/TagInESR/L4_ID/L4_C_Start/ROS平铺字段	✅ 6个Gate完整施工进度跟踪JSON
design_parameters_json	仅5种TypeCode（泵/换热器/容器/PSV/压缩机）	✅ SEPARATOR分液罐完整实例
按Unit汇总	❌	✅ Unit级Mhr/EA(Tag)汇总结构
采购交付跟踪	仅DeliveryDate平铺	✅ Delivery Plan/Actual/Forecast三值跟踪
2. 施工进度跟踪JSON结构（construction_progress_json）
2.1 按Unit汇总结构（unit_summary）
json
{
  "unit_summary": [
    {
      "unit_no": "5000",
      "unit_name": "ABS 5 Plant (incl. Zeppelin)",
      "total_mhr": 51807,
      "total_ea_tag": 496,
      "completion_pct": 0.7,
      "actual_installed_ea": 0
    },
    {
      "unit_no": "6000",
      "unit_name": "ABS 6 Plant",
      "total_mhr": 54975,
      "total_ea_tag": 579,
      "completion_pct": 0.0,
      "actual_installed_ea": 0
    }
  ],
  "report_date": "2022/2/12"
}
2.2 单台设备施工进度结构（equipment_construction_progress）
json
{
  "tag_no": "A31513A",
  "equipment_description": "FIXED & MOVEABLE BELT CONVEYORS SYSTEM",
  "equipment_name_cn": "固定和移动式带式输送机",
  "equipment_type": "动设备",
  "package_no": "MH-003",
  "sub_project": "ISBL",
  "unit_no": "3100",
  "detail_group_code": "1931",
  "mhr": 11,
  "unit_name": "Finished Products Logistics",
  "location": "3151",
  "pid_number": "C3100XFEQ1040",
  "dimensions": "~25240(total length)*600*700",
  "net_weight_kg": 2450,
  "installation": "MEI",
  "ros_to_mei": "2022/8/31",
  "anchor_bolt": null,
  "l4_id": "C3100XFEQ1040",
  "l4_c_start": "2022-10-31",
  "l4_c_finish": "2022-11-29",
  "tag_in_3d": true,
  "loading_by": "MEI",
  "in_package": "A31511",
  "aligned_ros": "2022-10-26",
  "delivery": {
    "actual": "2022-5-31",
    "forecast": null,
    "type": "Type 3"
  },
  "gates": [
    {
      "gate_no": 1,
      "gate_name": "基础支撑验收",
      "progress_pct": 0,
      "weight_factor": 5,
      "plan": "2022-10-21",
      "actual": null,
      "forecast": null
    },
    {
      "gate_no": 2,
      "gate_name": "安装就位",
      "progress_pct": 40,
      "weight_factor": 40,
      "plan": "2022-10-31",
      "actual": null,
      "forecast": null
    },
    {
      "gate_no": 3,
      "gate_name": "找平找正",
      "progress_pct": 20,
      "weight_factor": 20,
      "plan": "2022-11-14",
      "actual": null,
      "forecast": null
    },
    {
      "gate_no": 4,
      "gate_name": "一次灌浆",
      "progress_pct": 5,
      "weight_factor": 5,
      "plan": "2022-11-29",
      "actual": null,
      "forecast": "精平/垫铁隐蔽"
    },
    {
      "gate_no": 5,
      "gate_name": "调整步骤1",
      "progress_pct": 25,
      "weight_factor": 25,
      "plan": "2022-12-9",
      "actual": null,
      "forecast": "二次灌浆"
    },
    {
      "gate_no": 6,
      "gate_name": "调整步骤2",
      "progress_pct": 5,
      "weight_factor": 5,
      "plan": "2022-12-19",
      "actual": null,
      "forecast": null
    }
  ],
  "total_weight_factor": 100,
  "earned_hours": 0,
  "count_actual_tag": 0
}
2.3 6个Gate定义
Gate	名称	典型W.F.	说明
Gate 1	基础支撑验收	5%	基础验收合格后设备方可安装
Gate 2	安装就位	40%	设备吊装至基础上就位
Gate 3	找平找正	20%	设备水平度和位置调整
Gate 4	一次灌浆	5%	地脚螺栓一次灌浆
Gate 5	调整步骤1（精平/垫铁隐蔽）	25%	最终精平调整
Gate 6	调整步骤2（二次灌浆）	5%	二次灌浆完成
进度计算公式：

text
整体进度% = Σ(每个Gate的progress_pct × W.F.) / 100
Earned Hours = 整体进度% × Mhr
2.4 采购交付跟踪字段
字段名	类型	必填	说明
aligned_ros	date	❌	调整后的ROS（Required On Site）
delivery.actual	date	❌	实际交付日期
delivery.forecast	date	❌	预计交付日期
delivery.type	enum	❌	交付类型（Type 1~4）
Delivery Type枚举：

枚举值	说明
TYPE_1	常规交付
TYPE_2	特殊交付
TYPE_3	设备类（需吊装）
TYPE_4	超限设备
3. design_parameters_json——SEPARATOR分液罐实例
3.1 完整JSON结构（equipment_list.design_parameters_json中TypeCode=SEPARATOR的展开）
json
{
  "area_no": "5000",
  "pid_no": "5610",
  "tag_no": "B56106",
  "equipment_type": "SEPARATOR",
  "equipment_name_cn": "分液罐",
  "quantity": 1,
  "package_no": null,
  "design_capacity": {
    "value": "23(Working V=20)",
    "unit": "m3"
  },
  "rated_power_kw": null,
  "voltage_v": null,
  "position": "H",
  "dimensions": {
    "id_mm": 2600,
    "height_length_mm": 3480,
    "format": "ID x H (TL-TL)"
  },
  "materials": {
    "shell": "Q345R",
    "internal": "Coil:Q345D"
  },
  "pressure_conditions": {
    "shell_side": {"operating_mpag": "0.01/0.1", "design_mpag": "0.73"},
    "internal": {"operating_mpag": "FV/0.6", "design_mpag": "1.2"}
  },
  "temperature_conditions": {
    "shell_side": {"operating_c": "70/250", "design_c": "75.0"},
    "internal": {"operating_c": "250", "design_c": "105"}
  },
  "shell_type": "Eillp",
  "net_weight_kg": 7495,
  "filling_weight_kg": 31405,
  "insulation_type": "W",
  "insulation_thickness_mm": 70,
  "pressure_vessel_category": "II",
  "mr_no": "SE-04",
  "remark": "Normal empty",
  "package_skid": {
    "in_package_skid": "Y2",
    "in_equipment_skid": "Y2"
  },
  "mds_doc_no": {
    "ifq_new": "5000-SE-DAS-0113",
    "ifq_old": "5000-SE-DAS-0113"
  }
}
3.2 字段定义
字段名	类型	必填	说明
area_no	string	✅	区域编号（Unit_No）
pid_no	string	✅	PID图号
tag_no	string	✅	设备位号
equipment_type	string	✅	设备类型代码（SEPARATOR等）
equipment_name_cn	string	❌	中文名称
quantity	int	✅	数量
package_no	string	❌	成套包号
design_capacity	object	❌	设计能力（{value, unit}）
rated_power_kw	float	❌	额定功率
voltage_v	float	❌	电压
position	enum	❌	H（卧式）/V（立式）
dimensions	object	✅	尺寸（{id_mm, height_length_mm, format}）
materials.shell	string	✅	壳体材质
materials.internal	string	❌	内件材质
pressure_conditions.shell_side	object	❌	壳程压力（{operating, design}）
pressure_conditions.internal	object	❌	内件压力
temperature_conditions.shell_side	object	❌	壳程温度
temperature_conditions.internal	object	❌	内件温度
shell_type	string	❌	封头型式（Eillp椭圆等）
net_weight_kg	float	❌	净重
filling_weight_kg	float	❌	充水重量
insulation_type	string	❌	保温类型（B/K/W/G/M/H）
insulation_thickness_mm	float	❌	保温厚度
pressure_vessel_category	enum	❌	压力容器类别（I/II/III）
mr_no	string	❌	MR编号
remark	string	❌	备注
package_skid.in_package_skid	enum	❌	Y1/N1——是否在成套包内
package_skid.in_equipment_skid	enum	❌	Y2/N2——是否在设备橇内
mds_doc_no.ifq_new	string	❌	MDS新文档号
mds_doc_no.ifq_old	string	❌	MDS旧文档号
4. 保温类型枚举（InsulationType）
枚举值	中文	说明
B	保冷	Cold Insulation
K	保冷（低温）	Cryogenic Insulation
W	保温	Heat Insulation
G	防烫	Personnel Protection
M	隔音	Acoustic Insulation
H	防冻	Frost Protection
5. 与V3.0 equipment_list的映射
5.1 construction_progress_json与平铺字段
equipment_list平铺字段	construction_progress_json字段
tag_in_3d	tag_in_3d
l4_id	l4_id
l4_c_start	l4_c_start
ros	ros_to_mei
forecast_on_site	aligned_ros或delivery.forecast
actual_on_site	delivery.actual
installation	installation
installation_notes	gates[].forecast（Gate名称）
5.2 design_parameters_json与平铺字段
equipment_list平铺字段	design_parameters_json（SEPARATOR）
tag_number	tag_no
type_code	equipment_type
package_no	package_no
unit_no	area_no
design_parameters_json	完整JSON
6. 版本历史
版本	日期	修改内容
V1.0	2026-08-29	初始版本（design_parameters_json 5种TypeCode/change_notice详情/快照/输入清单）
V1.1	2026-08-29	增补施工进度跟踪（SUP-001），新增construction_progress_json+SEPARATOR实例+保温枚举+Delivery Type
增补完成。 PCS-DICT-008-SUP-001填补了EQUIP_LIST的两个缺口：

结构	内容
construction_progress_json	6个Gate施工进度跟踪（含W.F./Plan/Actual/Forecast）+采购交付三值跟踪+按Unit汇总
design_parameters_json（SEPARATOR实例）	分液罐完整参数（尺寸/材质/压力温度/保温/压力容器类别/MR/MDS文档）
2组新枚举	InsulationType（B/K/W/G/M/H）+ DeliveryType（Type 1~4）

