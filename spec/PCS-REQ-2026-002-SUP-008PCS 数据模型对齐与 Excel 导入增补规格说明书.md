PCS 数据模型对齐与 Excel 导入增补规格说明书
项目	内容
文件标识	PCS-REQ-2026-002-SUP-008
当前版本	V1.1
发布日期	2026-09-03
增补基准	PCS-REQ-2026-002 V2.2、SPEC-P0~P10、ADR-0019/0020/0022
编制部门	工艺部 / 信息化联合项目组
适用对象	P3–P8 开发团队
参考附件	PROII-Cal柴油液相加氢1217B131.xls（炼油装置完整工艺计算模板）
　　　　1216D132惠州蜡油加氢装置计算14.7.17计算-没校核.xlsx（V1.1 增补实例）
第一部分：引言
1.1 增补目的
本增补文件基于一份完整的炼油装置工艺计算 Excel 模板（PROII-Cal柴油液相加氢1217B131.xls），对 PCS 系统的数据模型、输出能力和导入功能进行系统性对齐。该 Excel 工作簿涵盖 30+ Sheet，是工艺专业交付物的典型形态。

核心目标：

输出对齐：确保 PCS 各计算模块的输出字段能完整填充该 Excel 模板的对应表格。

导入补充：为 P3 SIM 模块增加 Excel 导入能力，使物流数据可从化验报告、历史数据表直接读取。

数据模型扩展：识别并补充 PCS 当前缺失但 Excel 模板中存在的关键字段和表格。

1.2 适用范围
P3 SIM 模块：Excel 导入能力 + 物流物性字段扩展

P4 PIPE/PUMP 模块：管径/泵选型输出字段增补

P5 VESSEL/PSV/HEAT 模块：设备数据表输出字段增补

P7 UTIL 模块：能耗/水耗/汽耗数据模型（按 Excel 模板设计）

P5 新模块：反应器计算（reactor_results）

1.3 参考 Sheet 映射
Excel Sheet	对应 PCS 模块	优先级
streams, 物流参数, 摩尔组成, PFD参数	P3 SIM	最高
核算问题, 管径核算	P4 PIPE	高
机泵选型	P4 PUMP	高
气液分离罐核算, 缓冲罐核算	P5 VESSEL	中
安全阀选型	P5 PSV	中
电耗, 汽耗, 水耗, 能耗	P7 UTIL	中
反应器选型	P5 新增（reactor_results）	中
物流参数1, 摩尔组成0(末期)	P3 SIM（多案例）	低
蒸汽发生器两相流管径计算	P5 HEAT	低
第二部分：差异化分析（Gap Analysis）
2.1 P3 SIM 模块差距
当前 PCS streams 表：包含基础物流参数（T/P/流量/组成/基础物性）。

Excel 模板含有的额外字段（物流参数 sheet）：

字段	单位	说明	PCS 当前状态
surface_tension	dyne/cm	表面张力	❌ 缺失
api_gravity	°API	API 比重	❌ 缺失
critical_temp	°C	临界温度	❌ 缺失
critical_press	MPa	临界压力	❌ 缺失
enthalpy	kJ/kg	焓值	❌ 缺失
entropy	kJ/kg·K	熵值	❌ 缺失
vapor_density	kg/m³	气相密度	❌ 缺失
vapor_viscosity	cP	气相粘度	❌ 缺失
vapor_thermal_cond	W/(m·K)	气相热导率	❌ 缺失
vapor_mw	g/mol	气相分子量	❌ 缺失
liquid_mw	g/mol	液相分子量	❌ 缺失
vapor_cp_cv_ratio	—	气相绝热指数	❌ 缺失
vapor_z_factor	—	气相压缩系数	❌ 缺失
vapor_pressure	MPa(a)	蒸汽压	❌ 缺失
std_gas_flow	Nm³/h	标准状态气体流量	✅ 已有
actual_vol_flow	m³/h	实际体积流量	⚠️ 建议新增
多案例支持：

Excel 包含“末期”工况（摩尔组成0(末期)），当前 PCS 无“设计案例”概念。

需新增：stream_cases 表或 stream_case_type 枚举（NORMAL / END_OF_RUN / START_OF_RUN / TURN_DOWN）。

2.2 P4 PIPE 模块差距
当前 piping_results 表：已有基础字段，但 Excel 管径核算 sheet 含更多工程输出。

字段	单位	说明	PCS 当前状态
line_description	—	管线说明（如“进装置”）	❌ 缺失
pipe_type	—	管道类型（泵入口/泵出口/自流/两相等）	❌ 缺失
max_flow_factor	—	介质最大流量系数（1.1/1.2/1.3）	❌ 缺失
selected_diameter	m	管径选型（初始选择）	❌ 缺失
inner_diameter	m	内径	✅ 已有
liquid_velocity_max	m/s	管径选型后液体最大流速	❌ 缺失
gas_velocity_max	m/s	管径选型后气体最大流速	❌ 缺失
pressure_drop_per_100m	kPa	100米管线压力降	❌ 缺失
selected_pipe_size	string	选用管径（如“DN250”）	❌ 缺失
recommended_pipe_size	string	建议管径（改大/改小）	❌ 缺失
check_result	enum	核算检查（通过/未通过）	❌ 缺失
velocity_range_reference	string	一般流速范围（0.5～2 m/s）	❌ 缺失
2.3 P4 PUMP 模块差距
当前 pump_results 表：已有详细的 JSON 结构，但缺少选型结果字段。

字段	说明	PCS 当前状态
selected_pump_model	选定的泵型号	❌ 缺失
selected_motor_model	选定电机型号	❌ 缺失
selected_motor_power	选定电机功率（kW）	❌ 缺失
pump_operation	泵运行方式（正常/备用/停用）	❌ 缺失
vendor_name	供应商名称	✅ vendor 字段已有
purchase_order_number	采购订单号	✅ 已有
2.4 P5 VESSEL 模块差距
字段	单位	说明	PCS 当前状态
vessel_type	—	容器形式（立式/卧式）	❌ 缺失
vessel_specification	—	容器规格（Φ1600×5000 T-T）	❌ 缺失
water_boot_spec	—	分水包规格	❌ 缺失
liquid_holdup_time	min	液体产品停留时间	❌ 缺失
min_holdup_time	min	要求的最小停留时间	❌ 缺失
fill_factor	—	装满系数	❌ 缺失
check_result	enum	核算检查	❌ 缺失
2.5 P5 PSV 模块差距
字段	说明	PCS 当前状态
installation_location	安装部位（如“原料缓冲罐顶”）	❌ 缺失
relief_case	最大安全阀工况（火灾/出口阀关闭等）	❌ 缺失
selected_throat_diameter	选型喉径（mm）	❌ 缺失
selected_valve_model	安全阀型号（如“2J3-WFO-15JC”）	❌ 缺失
valve_inlet_size	入口公称直径	❌ 缺失
valve_outlet_size	出口公称直径	❌ 缺失
2.6 新模块：反应器计算
Excel 反应器选型 sheet 包含完整的反应器工艺参数，当前 PCS 无对应表。

需新增 reactor_results 表：

字段	类型	说明
reactor_id	UUID PK	主键
tag_number	string	反应器编号（R-101）
reactor_name	string	名称
catalyst_volume	float	催化剂体积（m³）
catalyst_height	float	催化剂高度（m）
catalyst_bed_count	int	床层数
reactor_diameter	float	反应器直径（m）
reactor_total_height	float	反应器总高（m）
space_velocity	float	空速（h⁻¹）
protector_volume	float	保护剂体积（m³）
guard_bed_count	int	保护剂床层数
gas_hourly_space_velocity	float	气时空速
+ RecordMixin 字段	—	sign_status/record_hash/等
2.7 新模块：能耗/公用工程
Excel 电耗、汽耗、水耗、能耗 sheet 需 P7 UTIL 模块覆盖。

需新增表：

utility_consumption：

字段	类型	说明
util_id	UUID PK	主键
project_id	UUID FK	项目
consumption_type	enum	ELECTRICITY / STEAM / WATER / FUEL_GAS / NITROGEN / AIR
pressure_level	string	压力等级（MPa）
normal_flow	float	正常用量
max_flow	float	最大用量
is_continuous	bool	是否连续
flow_unit	string	单位（kg/h/Nm³/h/kW）
+ TimestampMixin	—	时间戳
utility_energy_summary（能耗计算）：

字段	类型	说明
summary_id	UUID PK	主键
project_id	UUID FK	项目
energy_item	string	项目名称（电/燃料/蒸汽/水/气体）
consumption	float	消耗量
consumption_unit	string	单位
conversion_factor	float	折算值（kg标准油/单位）
energy_oil_kg	float	折合标准油（kg/h）
specific_energy	float	单位能耗（kg标准油/t）
第三部分：功能需求
3.1 Excel 导入功能（P3 扩展）
3.1.1 导入流程
text
用户上传 Excel 文件
    → 系统解析各 Sheet 结构
    → 识别可导入的 Sheet（物流参数/管径核算/机泵选型等）
    → 用户选择目标 Sheet → 列映射确认
    → 数据预览 → 用户确认
    → 系统写入 PCS 数据库（记录状态=DRAFT）
    → 走校对流程（StreamSignStatus/RecordSignStatus 门禁）
3.1.2 解析能力
Sheet 类型	解析策略	目标表
streams / 物流参数	按表头关键词（Temperature、Pressure、Mass Flow）识别列	streams
摩尔组成	识别组分列（H2、H2S、C1、C2、C3、IC4、NBP*）	streams.composition_json
管径核算	识别管线编号、介质、流量、温度、压力、汽化率、选型管径	piping_results
机泵选型	识别泵编号、流量、扬程、NPSH、功率、电机型号	pump_results
电耗 / 汽耗	识别设备名称、功率/用量、年工作时数	utility_consumption
3.1.3 API 端点（新增）
端点	方法	说明
/api/v1/projects/{project_id}/streams/import-excel	POST	上传 Excel，导入物流数据
/api/v1/projects/{project_id}/pipe/import-excel	POST	导入管径核算数据
/api/v1/projects/{project_id}/pump/import-excel	POST	导入机泵选型数据
/api/v1/projects/{project_id}/utility/import-excel	POST	导入能耗/公用工程数据
/api/v1/import/excel/preview	POST	预览 Excel 解析结果（不写入）
/api/v1/import/excel/mapping	GET	获取列映射模板
3.1.4 映射配置
系统内置 列映射模板库，用户也可自定义映射：

json
{
  "template_name": "柴油加氢物流模板",
  "mappings": [
    {"excel_column": "Stream Name", "pcs_field": "stream_name"},
    {"excel_column": "Temperature C", "pcs_field": "temp"},
    {"excel_column": "Pressure KG/CM2", "pcs_field": "press"},
    {"excel_column": "Total Mass Rate KG/HR", "pcs_field": "mass_flow"},
    {"excel_column": "Vapor Mole Fraction", "pcs_field": "vapor_fraction"},
    {"excel_column": "Molecular Weight", "pcs_field": "molecular_weight"},
    {"excel_column": "Liquid Act. Density KG/M3", "pcs_field": "density"},
    {"excel_column": "Liquid Viscosity CP", "pcs_field": "viscosity_dynamic"},
    {"excel_column": "Surface Tension DYNE/CM", "pcs_field": "surface_tension"},
    {"excel_column": "Enthalpy KCAL/KG", "pcs_field": "enthalpy"}
  ]
}
3.2 数据模型扩展（Schema 更新）
3.2.1 streams 表扩展字段（V3.5 → V3.6）
sql
ALTER TABLE streams ADD COLUMN surface_tension FLOAT;
ALTER TABLE streams ADD COLUMN api_gravity FLOAT;
ALTER TABLE streams ADD COLUMN critical_temp FLOAT;
ALTER TABLE streams ADD COLUMN critical_press FLOAT;
ALTER TABLE streams ADD COLUMN enthalpy FLOAT;
ALTER TABLE streams ADD COLUMN entropy FLOAT;
ALTER TABLE streams ADD COLUMN vapor_density FLOAT;
ALTER TABLE streams ADD COLUMN vapor_viscosity FLOAT;
ALTER TABLE streams ADD COLUMN vapor_thermal_cond FLOAT;
ALTER TABLE streams ADD COLUMN vapor_mw FLOAT;
ALTER TABLE streams ADD COLUMN liquid_mw FLOAT;
ALTER TABLE streams ADD COLUMN vapor_cp_cv_ratio FLOAT;
ALTER TABLE streams ADD COLUMN vapor_z_factor FLOAT;
ALTER TABLE streams ADD COLUMN vapor_pressure FLOAT;
ALTER TABLE streams ADD COLUMN actual_vol_flow FLOAT;
ALTER TABLE streams ADD COLUMN case_type VARCHAR(20) DEFAULT 'NORMAL';  -- NORMAL/END_OF_RUN/START/TURN_DOWN
ALTER TABLE streams ADD COLUMN import_source_type VARCHAR(30) DEFAULT 'MANUAL_ENTRY'; -- SIM/MANUAL/EXCEL/LAB
ALTER TABLE streams ADD COLUMN import_original_row JSONB;
3.2.2 piping_results 表扩展字段
sql
ALTER TABLE piping_results ADD COLUMN line_description VARCHAR(200);
ALTER TABLE piping_results ADD COLUMN pipe_type VARCHAR(30);  -- PUMP_SUCTION/PUMP_DISCHARGE/SELF_FLOW/HEATING_STEAM/TWO_PHASE
ALTER TABLE piping_results ADD COLUMN max_flow_factor FLOAT;
ALTER TABLE piping_results ADD COLUMN selected_diameter FLOAT;
ALTER TABLE piping_results ADD COLUMN liquid_velocity_max FLOAT;
ALTER TABLE piping_results ADD COLUMN gas_velocity_max FLOAT;
ALTER TABLE piping_results ADD COLUMN pressure_drop_per_100m FLOAT;
ALTER TABLE piping_results ADD COLUMN selected_pipe_size VARCHAR(50);
ALTER TABLE piping_results ADD COLUMN recommended_pipe_size VARCHAR(50);
ALTER TABLE piping_results ADD COLUMN velocity_range_reference VARCHAR(100);
ALTER TABLE piping_results ADD COLUMN check_result VARCHAR(20);  -- PASS/FAIL/WARNING
3.2.3 pump_results 表扩展字段
sql
ALTER TABLE pump_results ADD COLUMN selected_pump_model VARCHAR(100);
ALTER TABLE pump_results ADD COLUMN selected_motor_model VARCHAR(100);
ALTER TABLE pump_results ADD COLUMN selected_motor_power FLOAT;
ALTER TABLE pump_results ADD COLUMN pump_operation VARCHAR(20);  -- NORMAL/STANDBY/OFF
3.2.4 vessel_results 表扩展字段
sql
ALTER TABLE vessel_results ADD COLUMN vessel_type VARCHAR(20);  -- VERTICAL/HORIZONTAL
ALTER TABLE vessel_results ADD COLUMN vessel_specification VARCHAR(100);
ALTER TABLE vessel_results ADD COLUMN water_boot_spec VARCHAR(100);
ALTER TABLE vessel_results ADD COLUMN liquid_holdup_time FLOAT;
ALTER TABLE vessel_results ADD COLUMN min_holdup_time FLOAT;
ALTER TABLE vessel_results ADD COLUMN fill_factor FLOAT;
ALTER TABLE vessel_results ADD COLUMN check_result VARCHAR(20);
3.2.5 psv_results 表扩展字段
sql
ALTER TABLE psv_results ADD COLUMN installation_location VARCHAR(200);
ALTER TABLE psv_results ADD COLUMN relief_case VARCHAR(100);
ALTER TABLE psv_results ADD COLUMN selected_throat_diameter FLOAT;
ALTER TABLE psv_results ADD COLUMN selected_valve_model VARCHAR(100);
ALTER TABLE psv_results ADD COLUMN valve_inlet_size VARCHAR(20);
ALTER TABLE psv_results ADD COLUMN valve_outlet_size VARCHAR(20);
3.2.6 新增 reactor_results 表
sql
CREATE TABLE reactor_results (
    reactor_id UUID PRIMARY KEY,
    project_id UUID NOT NULL REFERENCES projects(project_id),
    workspace_id UUID NOT NULL REFERENCES workspaces(workspace_id),
    tag_number VARCHAR(50) NOT NULL,
    reactor_name VARCHAR(200),
    reactor_type VARCHAR(30),  -- FIXED_BED/FLUIDIZED_BED/TUBULAR
    catalyst_volume FLOAT,
    catalyst_height FLOAT,
    catalyst_bed_count INT,
    reactor_diameter FLOAT,
    reactor_total_height FLOAT,
    space_velocity FLOAT,
    protector_volume FLOAT,
    guard_bed_count INT,
    gas_hourly_space_velocity FLOAT,
    -- RecordMixin 字段
    sign_status VARCHAR(30) NOT NULL,
    record_hash VARCHAR(64) NOT NULL,
    approval_step INT,
    approval_depth INT,
    approval_role VARCHAR(30),
    locked_by_deliverable BOOLEAN DEFAULT FALSE,
    created_by UUID,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP,
    -- 唯一约束
    UNIQUE(project_id, tag_number)
);
3.2.7 新增 utility_consumption 表
sql
CREATE TABLE utility_consumption (
    util_id UUID PRIMARY KEY,
    project_id UUID NOT NULL REFERENCES projects(project_id),
    consumption_type VARCHAR(30) NOT NULL,  -- ELECTRICITY/STEAM/WATER/FUEL_GAS/NITROGEN/AIR
    pressure_level VARCHAR(20),
    normal_flow FLOAT,
    max_flow FLOAT,
    is_continuous BOOLEAN DEFAULT TRUE,
    flow_unit VARCHAR(20),
    description VARCHAR(200),
    created_by UUID,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP
);
3.2.8 新增 utility_energy_summary 表
sql
CREATE TABLE utility_energy_summary (
    summary_id UUID PRIMARY KEY,
    project_id UUID NOT NULL REFERENCES projects(project_id),
    energy_item VARCHAR(50) NOT NULL,
    consumption FLOAT NOT NULL,
    consumption_unit VARCHAR(20) NOT NULL,
    conversion_factor FLOAT NOT NULL,
    energy_oil_kg FLOAT NOT NULL,
    specific_energy FLOAT,  -- 单位能耗 kg标准油/t
    calculation_date DATE DEFAULT CURRENT_DATE,
    created_by UUID,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP
);
3.3 输出物生成能力
3.3.1 P4 PIPE 输出要求
PIPE 模块必须能够生成与 Excel 管径核算 sheet 完全对应的数据视图，包含：

管线编号/说明/介质/管道类型

温度/压力/汽化率

介质操作流量（正常/最大）

管径选型（初选/内径/选用管径）

流速（液体最大/气体最大/一般流速范围）

100米管线压力降

核算检查 + 建议管径

3.3.2 P5 VESSEL 输出要求
VESSEL 模块必须能够生成与 Excel 气液分离罐核算 / 缓冲罐核算 对应的数据视图，包含：

容器编号/名称/形式/规格

介质/温度/压力

正常液体质量流率/装满系数

液体停留时间（计算值 vs 要求最小值）

分水包规格/停留时间

核算检查（通过/未通过）

3.3.3 P5 PSV 输出要求
PSV 模块必须能够生成与 Excel 安全阀选型 对应的数据视图，包含：

安全阀编号/名称/安装部位

操作介质/设计压力/最高操作压力

定压值/安全泄放量

喷嘴面积/选型喉径/选型型号

入口/出口公称直径

核算检查

3.3.4 P4 PUMP 输出要求
PUMP 模块必须能够生成与 Excel 机泵选型 对应的数据视图，包含：

泵编号/名称/介质

正常/额定/最小流量（质量/体积）

温度/密度/粘度

入口/出口压力（含设备压力、管线压降）

计算扬程/选型扬程

NPSHa/NPSHr

轴功率/电机功率/选定电机

效率/转速

3.3.5 P7 UTIL 输出要求
UTIL 模块必须能够生成与 Excel 能耗 sheet 对应的汇总视图：

电耗汇总（设备名称/电压/操作台数/备用台数/轴功率/年工作时数/年用电量）

汽耗汇总（压力等级/正常用量/最大用量/自产汽量）

水耗汇总（新鲜水/循环冷水/除盐水/凝结水/排水）

能耗计算（电/燃料/蒸汽/水/气体 → 折合标准油）

第四部分：验收标准
4.1 P3 SIM Excel 导入
验收项	标准
物流参数导入	30 条物流数据可在 5 秒内完成导入，物性字段完整度 ≥ 90%
组成导入	组分摩尔分数归一化至 100% ± 0.5%
列映射	支持用户手动拖拽匹配，支持保存为自定义模板
状态流	导入后物流为 DRAFT，提交校对后变为 IN_APPROVAL，通过后 CHECKED
多案例	支持 NORMAL / END_OF_RUN 案例切换
4.2 数据模型对齐
模块	新增字段数	对齐度（相对 Excel 模板）
P3 SIM	16	≥ 95%
P4 PIPE	12	≥ 90%
P4 PUMP	4	≥ 95%
P5 VESSEL	7	≥ 90%
P5 PSV	6	≥ 90%
新增反应器	1 表（14 字段）	100%
新增能耗	2 表	100%
4.3 输出验证
给定 Excel 模板中的输入数据，PCS 各模块的计算结果（管径/压降/扬程/NPSH/泄放量/停留时间）与 Excel 偏差 ≤ 5%。

PCS 生成的报表结构可直接复制到 Excel 模板对应 Sheet，无需手工调整列顺序。

第五部分：实施计划
阶段	任务	负责模块	预估工作量
Sprint 1	streams 表扩展（16 字段）+ Alembic 迁移	P3	2 天
Sprint 2	Excel 导入引擎（列识别 + 映射 + 解析）	P3	3 天
Sprint 3	管径/泵/容器/安全阀字段扩展 + 迁移	P4/P5	2 天
Sprint 4	反应器表 + 能耗表 + 迁移	P5/P7	2 天
Sprint 5	导入 API 端点 + 前端导入向导	P3/P9	2 天
Sprint 6	输出物验证 + Excel 导出模板	P8	1 天
合计	—	—	~12 天（2.5 周）
第六部分：与现有 ADR/SPEC 的关系
文档	影响	说明
ADR-0019	扩展	import_source_type 增加 EXCEL_IMPORT 枚举值
ADR-0020	扩展	状态点（StatePoint）的物性字段同步扩展
ADR-0022	无影响	物流链模型不变，Excel 导入仅填充数据
SPEC-P3 V1.2	增补	新增 Excel 导入章节（§3.2.4）
SPEC-P4 V1.2	增补	PIPE/PUMP 输出字段同步
SPEC-P5 V1.2	增补	VESSEL/PSV 输出字段同步 + 新增反应器模块
SPEC-P7 V1.1	增补	UTIL 模块按此增补设计
DICT-ALL-003	升级至 V3.6	新增 30+ 字段 + 3 张新表

第七部分：版本历史
版本	日期	修改内容
V1.0	2026-09-02	初始版本：基于 PROII-Cal柴油液相加氢模板的完整增补规格
V1.1	2026-09-03	基于 1216D132 蜡油加氢实例的增补规格：34 sheet 映射 + 12 字段 + 5 表（relief_results / column_sizing / two_phase_results / mixer_results / workflow_progress / auxiliary_consumption）+ 双阶段设计模板
本增补文件与 PCS-REQ-2026-002 及 SPEC-P0~P10 合并使用，构成 PCS 系统开发的完整依据。


第八部分：蜡油加氢装置 1216D132 实例增补（V1.1）
8.1 实例背景
参考附件二：1216D132惠州蜡油加氢装置计算14.7.17计算-没校核.xlsx，34 个 Sheet（项目：惠州二期 340 万吨/年柴油加氢装置；输入数据来源：杜邦工艺包 + Htri 5 + Aspen Plus）。
V1.0 基于柴油液相加氢模板（PROII-Cal1217B131），本节基于蜡油加氢实例补充 V1.0 未覆盖的工程模块与字段。
8.2 Sheet ↔ PCS 模块映射（V1.1 新增）
Sheet 名	对应 PCS 模块	状态	说明
说明, 项目信息, 输入	—	元数据	项目规模 260 万吨/年、操作弹性 60~110%、年工作时数 8400h
作业流程	P9 项目管理	新增	专业作业序列 + 进度 + 外部专业条件 + 开始/完成时间
柴油加氢物料平衡(杜邦)	P3 SIM	新增（扩展）	总物料平衡（按氢耗 3w% 调整）+ 产品硫分布
物流参数	P3 SIM	已覆盖，扩列	100~235 路（V1.0 实例为多案例单列），单 sheet 列数 235
反应器选型	P5 REACTOR	已覆盖	131-R-101 加氢反应器（Φ4600×22000 立式 2 台）+ 131-R-102 在线精制反应器
塔径核算	P5 COLUMN	新增	HYSYS 泛点率 → 计算塔径 → 选取塔径 → 参考塔径
高压容器核算	P5 VESSEL	新增	高压闪蒸罐 / 热高压分离器 / 冷高压分离器（高压 vessel 类别）
汽液分离罐核算	P5 VESSEL	已覆盖，扩列	13 路实例（V1.0 仅 2~3 路）
卧式回流罐核算	P5 VESSEL	新增	含分水包规格 + 回流流量 + 水流率（汽提塔顶/分馏塔顶回流罐）
缓冲罐核算	P5 VESSEL	已覆盖	10 路（原料油/加氢进料/除氧水/封油/贫胺液/硫化剂/污油/排污/废胺液）
净化风罐核算	P5 VESSEL	新增	Φ1600×4650 立式（小型压力容器）
泄放量	P5 PSV	新增	反应器总体积计算 + 气密压力 + 安全系数 1.2 + 多档泄放率（0.7/1.4/2.1 MPa/min）
容器选型（详细设计新模板）	P5 VESSEL	新增	双阶段设计模板（基础设计 → 详细设计，含 83 列完整字段）
机泵选型(基础设计)	P4 PUMP	新增（双模板）	14 台泵基本参数（基础设计阶段）
机泵选型（详细设计新模板）	P4 PUMP	新增（双模板）	684 行 × 43 列完整选型 + 运行参数 + 校核
安全阀选型(基础设计)	P5 PSV	新增（双模板）	12 路 PSV 基础设计数据
安全阀选型(详细设计新模板)	P5 PSV	新增（双模板）	88 列完整选型 + 操作介质 + 最高操作温度 + 喉径计算
单相流管径核算	P4 PIPE	已覆盖，扩列	275 列（V1.0 实例 ≤ 50 路）
混相流管径核算	P4 PIPE	新增	370 列混合相管径核算
两相流	P4 PIPE	新增	Bx/By + 流动型式（环状流/雾状流）+ 避开柱状流
辅助剂用量	P7 UTIL	新增	催化剂（型号/供应商/外观/装填量）+ 化学药剂
电耗	P7 UTIL	已覆盖	电压/操作台数/备用台数/设备容量/轴功率/年工作时数/年用电量
其他设备选型	P5 OTHER	新增	混合器（MI-101/MI-201）+ 空冷器 + 换热器
安全阀数据源	P5 PSV	新增	数据源追溯（PSV 选型输入流股 110 列）
水耗	P7 UTIL	已覆盖，扩展	生产给水/循环水/除盐水/除氧水/循环热水/含油污水/含硫污水/凝结水
汽耗	P7 UTIL	已覆盖	蒸汽用量 + 多压力等级（MPa(G)）
燃料消耗	P7 UTIL	新增	反应进料炉 kg/h + Nm³/h；热值 41868 KJ/Kg（标煤）+ 26377 KJ/Nm³（燃料气）
能耗	P7 UTIL	已覆盖	装置能耗汇总（折合标准油）
塔釜物料停留时间	P5 VESSEL	新增	催化蒸馏塔 T-101 等
操作介质重	P5 VESSEL	新增	塔器操作介质重（塔径/塔板数/板间距/集油箱液位高/操作介质密度）
原料油粘度	P3 SIM	新增	常压下温度-粘度对应表（多温度点）
混合器压降	P5 OTHER	新增	MI-101 重芳烃-裂解催化剂混合器 + MI-201 精制进料混合器
8.3 V1.1 新增 Gap（V1.0 未覆盖）
8.3.1 P5 VESSEL：高压 vessel 类别
V1.0 vessel_results 未区分高压 vs 中低压；V1.1 实例新增高压闪蒸罐/热高压分离器/冷高压分离器，需 vessel_category 枚举扩展：
枚举值	对应容器	设计要点
HIGH_PRESSURE_FLASH	高压闪蒸罐	Φ2800×10500 立式，高 H₂ 分压
HIGH_PRESSURE_HOT	热高压分离器	Φ2400×8500 立式
HIGH_PRESSURE_COLD	冷高压分离器	Φ2000×6500 立式
MEDIUM_PRESSURE	中压容器	气液分离罐/缓冲罐（V1.0 既有）
LOW_PRESSURE	低压容器	回流罐/净化风罐（V1.0 既有）
sql
ALTER TABLE vessel_results ADD COLUMN vessel_category VARCHAR(30) DEFAULT 'MEDIUM_PRESSURE';
ALTER TABLE vessel_results ADD COLUMN design_pressure FLOAT;  -- MPa
ALTER TABLE vessel_results ADD COLUMN design_temp FLOAT;       -- ℃
ALTER TABLE vessel_results ADD COLUMN h2_partial_pressure FLOAT; -- MPa（H₂ 分压，高压加氢特有）
8.3.2 P5 PSV：泄放量（relief sizing）
V1.0 PSV 仅含 installation_location/relief_case/喉径；V1.1 实例新增泄放量独立计算模块：
字段	类型	说明
relief_id	UUID PK	主键
project_id	UUID FK	项目
source_equipment_id	UUID FK	源设备（多态：reactor/vessel/heat exchanger）
relief_scenario	enum	FIRE / BLOCKED_OUTLET / COOLING_FAILURE / POWER_FAILURE
reactor_volume	float	反应器总体积 m³
reactor_diameter	float	直径 m
reactor_height	float	高度 m
gas_tight_pressure	float	气密试验压力 Bar
safety_factor	float	安全系数（默认 1.2）
relief_rate_tier_1	float	第一档泄放率 MPa/min（0.7）
relief_rate_tier_2	float	第二档泄放率 MPa/min（1.4）
relief_rate_tier_3	float	第三档泄放率 MPa/min（2.1）
required_relief_area	float	所需泄放面积 cm²（输出）
selected_psv_id	UUID FK	选型 PSV（反查 psv_results）
8.3.3 P5 COLUMN：塔径核算
V1.0 无塔径模块；V1.1 实例汽提塔 T-101 给出 HYSYS 泛点率 33.02% → 计算塔径 1829mm → 选取塔径 2200mm。
字段	类型	说明
column_id	UUID PK	主键
project_id	UUID FK	项目
column_tag	string	塔编号（T-101）
column_name	string	名称（汽提塔）
hysys_flooding_percent	float	HYSYS 泛点率 %
hysys_calc_diameter_mm	float	HYSYS 计算塔径 mm
selected_diameter_mm	float	选取塔径 mm
reference_diameter_mm	float	参考塔径 mm
tray_spacing_mm	float	板间距 mm
tray_count	int	实际塔板数
theoretical_tray_count	int	理论塔板数
overall_efficiency	float	总板效率 %
calc_date	date	计算日期
sql
CREATE TABLE column_sizing (
    column_id UUID PRIMARY KEY,
    project_id UUID NOT NULL REFERENCES projects(project_id),
    workspace_id UUID NOT NULL REFERENCES workspaces(workspace_id),
    column_tag VARCHAR(50) NOT NULL,
    column_name VARCHAR(200),
    hysys_flooding_percent FLOAT,
    hysys_calc_diameter_mm FLOAT,
    selected_diameter_mm FLOAT,
    reference_diameter_mm FLOAT,
    tray_spacing_mm FLOAT,
    tray_count INT,
    theoretical_tray_count INT,
    overall_efficiency FLOAT,
    calc_date DATE,
    -- RecordMixin
    sign_status VARCHAR(30) NOT NULL,
    record_hash VARCHAR(64) NOT NULL,
    approval_step INT,
    approval_depth INT,
    approval_role VARCHAR(30),
    locked_by_deliverable BOOLEAN DEFAULT FALSE,
    created_by UUID,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP,
    UNIQUE(project_id, column_tag)
);
8.3.4 P4 PIPE：两相流管径核算
V1.0 PIPE 仅单相流；V1.1 实例新增两相流（混合相/避免柱状流）：
字段	类型	说明
two_phase_id	UUID PK	主键
project_id	UUID FK	项目
line_number	string	管线编号（112 / 213 / 518 等）
line_description	string	管线说明（混合油 / 出 E-102 / F-201 出口 2 路）
medium_name	string	介质名称
mass_flow	float	流量 kg/h
density	float	密度 kg/m³
viscosity	float	粘度 cP
surface_tension	float	表面张力 dyne/cm
path_count	int	路数
diameter_mm	float	管径 mm
velocity_mps	float	管速 m/s
pressure_drop_100m_kpa	float	100 米压降 kPa
bx	float	Bx（液相动能比）
by	float	By（气相动能比）
flow_pattern	enum	ANNULAR / MIST / BUBBLE / SLUG / STRATIFIED / WAVE
two_phase_check	enum	PASS / WARNING / FAIL
8.3.5 P5 NEW：混合器压降（mixer pressure drop）
V1.1 实例 MI-101（重芳烃-裂解催化剂混合器）+ MI-201（精制进料混合器）：
字段	类型	说明
mixer_id	UUID PK	主键
project_id	UUID FK	项目
mixer_tag	string	混合器编号（MI-101）
mixer_name	string	名称
component_1_name	string	组分 1 名称（重芳烃）
component_1_flow	float	流率 m³/h
component_2_name	string	组分 2 名称（裂解催化剂 / 高压闪蒸气）
component_2_flow	float	流率 m³/h
pressure_drop_kpa	float	压降 kPa
check_result	enum	PASS / WARNING / FAIL
sql
CREATE TABLE mixer_results (
    mixer_id UUID PRIMARY KEY,
    project_id UUID NOT NULL REFERENCES projects(project_id),
    workspace_id UUID NOT NULL REFERENCES workspaces(workspace_id),
    mixer_tag VARCHAR(50) NOT NULL,
    mixer_name VARCHAR(200),
    component_1_name VARCHAR(100),
    component_1_flow FLOAT,
    component_2_name VARCHAR(100),
    component_2_flow FLOAT,
    pressure_drop_kpa FLOAT,
    check_result VARCHAR(20),
    -- RecordMixin
    sign_status VARCHAR(30) NOT NULL,
    record_hash VARCHAR(64) NOT NULL,
    approval_step INT,
    approval_depth INT,
    approval_role VARCHAR(30),
    locked_by_deliverable BOOLEAN DEFAULT FALSE,
    created_by UUID,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP,
    UNIQUE(project_id, mixer_tag)
);
8.3.6 P5 VESSEL：操作介质重
V1.1 实例塔器操作介质重计算（汽提塔 / 分馏塔）：
sql
ALTER TABLE vessel_results ADD COLUMN vessel_weight_calc JSONB;
-- 结构示例：
-- {
--   "vessel_category": "COLUMN",
--   "diameter_mm": 2200,
--   "tray_count": 30,
--   "tray_spacing_mm": 600,
--   "collector_box_level_mm": 200,
--   "operating_medium_density_kgm3": 720,
--   "total_medium_weight_kg": 15234.5
-- }
8.3.7 P3 SIM：原料油粘度表
V1.1 实例原料油粘度（温度-粘度对应）：
sql
ALTER TABLE streams ADD COLUMN viscosity_temperature_curve JSONB;
-- 结构示例：
-- {"50": 213.2, "80": 56.8, "100": 28.4, "150": 9.6, "200": 4.3}
8.3.8 P7 UTIL：燃料消耗 + 双热值换算
V1.0 P7 UTIL 无燃料消耗；V1.1 实例反应进料炉：
sql
ALTER TABLE utility_consumption ADD COLUMN calorific_value_kj_kg FLOAT;    -- 标准煤热值 41868 KJ/Kg
ALTER TABLE utility_consumption ADD COLUMN calorific_value_kj_nm3 FLOAT;   -- 燃料气热值 26377 KJ/Nm³
ALTER TABLE utility_consumption ADD COLUMN heating_value_load_kw FLOAT;    -- 负荷 KW
ALTER TABLE utility_consumption ADD COLUMN furnace_efficiency_percent FLOAT;  -- 效率 %
8.4 V1.1 新增 Gap：双阶段设计模板
V1.1 实例 VESSEL/PUMP/PSV 全部使用「基础设计 + 详细设计」双模板：
基础设计阶段	详细设计阶段
简化表头（≤ 30 列）	完整表头（PUMP 684 行 × 43 列；PSV 88 列；VESSEL 83 列）
仅工艺参数	工艺参数 + 设备规格 + 校核 + 备件 + 运行参数
无运行校核	含轴功率校核 / NPSHa 计算 / 必需汽蚀余量 / 效率 / 转速 / 电机匹配
无签名状态字段	RecordMixin 字段完整（sign_status / record_hash / approval_*）
需新增表 design_stage 标识当前记录处于哪个设计阶段：
sql
ALTER TABLE pump_results ADD COLUMN design_stage VARCHAR(20) DEFAULT 'BASIC';  -- BASIC/DETAIL
ALTER TABLE vessel_results ADD COLUMN design_stage VARCHAR(20) DEFAULT 'BASIC';
ALTER TABLE psv_results ADD COLUMN design_stage VARCHAR(20) DEFAULT 'BASIC';
8.5 V1.1 新增 Gap：项目管理（作业流程）
V1.1 Sheet 2（作业流程）给出专业作业进度模板：
sql
CREATE TABLE workflow_progress (
    progress_id UUID PRIMARY KEY,
    project_id UUID NOT NULL REFERENCES projects(project_id),
    workspace_id UUID NOT NULL REFERENCES workspaces(workspace_id),
    sequence_no INT NOT NULL,
    main_workflow_item VARCHAR(200),        -- 主流程项
    progress_percent FLOAT,                 -- 进度 %
    external_condition_1 VARCHAR(200),      -- 外部专业条件 1
    external_condition_1_progress FLOAT,
    external_condition_2 VARCHAR(200),
    external_condition_2_progress FLOAT,
    external_condition_3 VARCHAR(200),
    external_condition_3_progress FLOAT,
    external_condition_4 VARCHAR(200),
    external_condition_4_progress FLOAT,
    external_condition_5 VARCHAR(200),
    external_condition_5_progress FLOAT,
    start_date DATE,
    completion_date DATE,
    -- TimestampMixin
    created_by UUID,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP,
    UNIQUE(project_id, sequence_no)
);
8.6 V1.1 新增 Gap：辅助剂用量
V1.1 Sheet 23 给出催化剂 + 化学药剂用量：
sql
CREATE TABLE auxiliary_consumption (
    aux_id UUID PRIMARY KEY,
    project_id UUID NOT NULL REFERENCES projects(project_id),
    workspace_id UUID NOT NULL REFERENCES workspaces(workspace_id),
    aux_category VARCHAR(30),       -- CATALYST / CHEMICAL
    model VARCHAR(100),             -- 型号
    vendor VARCHAR(200),            -- 供应商
    appearance VARCHAR(100),        -- 外观
    loading_volume FLOAT,           -- 装填量 m³
    loading_weight_kg FLOAT,        -- 装填重量 kg
    first_fill BOOLEAN DEFAULT TRUE,-- 首次装填
    -- RecordMixin
    sign_status VARCHAR(30) NOT NULL,
    record_hash VARCHAR(64) NOT NULL,
    approval_step INT,
    approval_depth INT,
    approval_role VARCHAR(30),
    locked_by_deliverable BOOLEAN DEFAULT FALSE,
    created_by UUID,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP,
    UNIQUE(project_id, model)
);
8.7 V1.1 验收标准扩展
模块	新增字段数 / 表数	对齐度（相对 1216D132 实例）
P5 VESSEL	+4 字段（vessel_category / design_pressure / design_temp / h2_partial_pressure）+ 1 表（column_sizing）	≥ 92%
P5 PSV	+1 表（relief_results，11 字段）	≥ 95%
P4 PIPE	+1 表（two_phase_results，13 字段）	≥ 90%
P5 NEW	+1 表（mixer_results，9 字段）	≥ 95%
P7 UTIL	+4 字段（calorific_value_kj_kg/nm3 / heating_value_load_kw / furnace_efficiency_percent）+ 1 表（auxiliary_consumption，8 字段）	≥ 93%
P9	+1 表（workflow_progress，14 字段）	100%
设计阶段双模板	+1 字段 design_stage × 3 表	100%
V1.1 合计	+12 字段 / +5 表（relief_results / column_sizing / two_phase_results / mixer_results / auxiliary_consumption / workflow_progress）	—
8.8 V1.1 实施计划扩展
阶段	任务	负责模块	预估工作量
Sprint 7	vessel_category 枚举 + vessel_results 4 字段 + column_sizing 表 + migration	P5	2 天
Sprint 8	relief_results 表 + relief_scenario 枚举 + migration	P5	2 天
Sprint 9	two_phase_results 表 + flow_pattern 枚举 + migration	P4	1.5 天
Sprint 10	mixer_results 表 + auxiliary_consumption 表 + utility_consumption 4 字段 + migration	P5/P7	2 天
Sprint 11	workflow_progress 表 + P9 项目管理前端	P9	1.5 天
Sprint 12	design_stage 字段 × 3 表（PUMP/VESSEL/PSV）+ 双模板导入引擎	P3/P4/P5	2 天
Sprint 13	1216D132 实例验证 + 输出报表对齐	P8	1.5 天
V1.1 合计	—	—	~12.5 天
8.9 V1.1 与现有 ADR/SPEC 的关系
文档	影响	说明
ADR-0019	扩展	import_source_type 增加 EXCEL_IMPORT_WAX_OIL 子类（蜡油加氢模板）
SPEC-P3 V1.2	增补	viscosity_temperature_curve JSONB 字段（原料油温度-粘度对应表）
SPEC-P4 V1.2	增补	two_phase_results 表（两相流管径核算）+ flow_pattern 枚举
SPEC-P5 V1.2	增补	vessel_category 枚举（5 值）+ column_sizing / relief_results / mixer_results 3 表
SPEC-P7 V1.1	增补	utility_consumption 4 字段（calorific_value_*/heating_value_load_kw/furnace_efficiency_percent）+ auxiliary_consumption 表
SPEC-P9 V1.0	新建	P9 项目管理 + workflow_progress 表
DICT-ALL-003	升级至 V3.7	新增 12 字段 + 5 表
ADR-0026	新建（建议）	设计阶段双模板（基础设计 → 详细设计）；design_stage 字段
