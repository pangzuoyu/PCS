PCS-DICT-007 增补文件四
文件标识	PCS-DICT-007-SUP-004
当前版本	V1.4
发布日期	2026-08-29
增补基准	PCS-DICT-007 V2.0
新增参考	阀门数据表模板（VALVE DATA SHEET，含球阀/蝶阀/闸阀通用格式）
1. 增补说明
1.1 新增素材价值
本素材是通用阀门数据表模板，适用于CV模块（调节阀）以及EQUIP_LIST中的手动阀门录入：

维度	DICT-007已有CV	本增补新增
cv_results平铺字段	✅ cv_value/flow_rate/pressure_drop/choked_flow/noise	—
data_sheet_json	❌ 无	✅ 完整阀门数据表结构
材料子结构	❌ 无	✅ 阀体/阀盖/阀芯/阀杆/阀座/盘根6部件
结构/操作方式	❌ 无	✅ CONSTRUCTURE/OPERATION
2. 阀门数据表完整JSON结构（valve_data_sheet_json）
2.1 顶层结构
json
{
  "item_no": null,             // 序号
  "tag_no": null,              // 编号
  "application": null,         // 应用
  "valve_type": null,          // 阀门类型
  "quantity": null,            // 数量
  "fluid_media": null,         // 流体介质
  "design_pressure_temp": {    // 设计压力/温度
    "pressure_mpag": null,
    "temp_c": null
  },
  "flow_rating": null,         // 流量特性（等百分比/线性/快开等）
  "end_connection": null,      // 连接方式（法兰/对夹/焊接/螺纹）
  "design_code": null,         // 设计标准（ASME B16.34/API 6D等）
  "size": null,                // 公称尺寸（DN/NPS）
  "figure_no": null,           // 阀门编号
  "ansi_rating": null,         // 压力等级（150#/300#/600#等）
  "seat_leakage": null,        // 泄漏等级（ANSI Class I~VI）
  "materials": {               // 材料
    "body": null,              // 阀体
    "bonnet": null,            // 阀盖
    "disc": null,              // 阀瓣/阀芯
    "stem": null,              // 阀杆
    "seat": null,              // 阀座
    "packing": null            // 盘根
  },
  "constructure": null,        // 结构形式（直通/角式/三通等）
  "operation": null,           // 操作方式（手动/电动/气动/液动）
  "remarks": null,             // 备注
  "data_source": null          // 数据来源标记
}
2.2 字段定义
字段名	类型	必填	说明
item_no	int	✅	序号
tag_no	string	✅	阀门位号
application	string	✅	应用说明
valve_type	enum	✅	GLOBE/BALL/BUTTERFLY/GATE/CHECK/PLUG/DIAPHRAGM
quantity	int	✅	数量
fluid_media	string	✅	流体介质
design_pressure_mpag	float	✅	设计压力
design_temp_c	float	✅	设计温度
flow_rating	enum	❌	EQUAL_PERCENT/LINEAR/QUICK_OPEN
end_connection	enum	✅	FLANGE/WAFER/WELD/THREAD
design_code	string	❌	ASME B16.34/API 6D/GB/T 12224等
size	string	✅	公称尺寸（DN80/NPS 3"）
figure_no	string	❌	阀门编号（制造商图号）
ansi_rating	string	✅	压力等级（150#/300#/600#/900#）
seat_leakage	enum	❌	CLASS_I/II/III/IV/V/VI（ANSI FCI 70-2）
materials.body	string	❌	阀体材质
materials.bonnet	string	❌	阀盖材质
materials.disc	string	❌	阀瓣/阀芯材质
materials.stem	string	❌	阀杆材质
materials.seat	string	❌	阀座材质
materials.packing	string	❌	盘根/填料
constructure	string	❌	结构形式
operation	string	❌	操作方式
remarks	string	❌	备注
3. 枚举定义
3.1 ValveType（阀门类型）
枚举值	中文
GLOBE	截止阀/调节阀
BALL	球阀
BUTTERFLY	蝶阀
GATE	闸阀
CHECK	止回阀
PLUG	旋塞阀
DIAPHRAGM	隔膜阀
NEEDLE	针阀
3.2 FlowRating（流量特性）
枚举值	中文
EQUAL_PERCENT	等百分比
LINEAR	线性
QUICK_OPEN	快开
3.3 EndConnection（连接方式）
枚举值	中文
FLANGE	法兰
WAFER	对夹
WELD	焊接
THREAD	螺纹
3.4 SeatLeakage（泄漏等级，ANSI FCI 70-2）
枚举值	说明
CLASS_I	I级（不要求严密）
CLASS_II	II级
CLASS_III	III级
CLASS_IV	IV级（金属阀座标准）
CLASS_V	V级
CLASS_VI	VI级（软阀座严密关断）
4. 与cv_results平铺字段的映射
cv_results字段	valve_data_sheet_json字段
tag_number	tag_no
cv_value	由计算得出，不直接在数据表中
flow_rate	由流体介质+设计条件推算
pressure_drop	由设计压力推算
choked_flow	由计算得出
noise	由计算得出
5. 与EQUIP_LIST的关系
当equipment_list.type_code = CV（调节阀）或手动录入阀门时，design_parameters_json可采用valve_data_sheet_json结构。

equipment_list字段	valve_data_sheet_json
type_code	valve_type
tag_number	tag_no
equipment_description	application
design_parameters_json	完整valve_data_sheet_json
6. 版本历史
版本	日期	修改内容
V1.0~V1.3	2026-08-29	初始+容器+塔+球罐增补
V2.0	2026-08-29	完整整合版
V1.4	2026-08-29	增补阀门数据表结构（SUP-004），新增valve_data_sheet_json
增补完成。 PCS-DICT-007现覆盖CV模块的阀门数据表结构（valve_data_sheet_json），含8种阀门类型、4种流量特性、4种连接方式、6级泄漏等级枚举。P6阶段CV模块和P7阶段EQUIP_LIST阀门录入以此为准。
