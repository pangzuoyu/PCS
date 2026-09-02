P7 集成模块开发规格说明书
文件标识	PCS-REQ-2026-002-SPEC-P7
当前版本	V1.3
发布日期	2026-08-27（V1.1 修订 2026-08-28；V1.2 修订 2026-09-03；V1.3 修订 2026-09-03，incorporate SUP-008 V1.1 + SUP-010 V1.1：UTIL 能耗 5 表 + 催化剂装填量 + auxiliary_consumption 4 字段）
编制部门	工艺部 / 信息化联合项目组
适用对象	内部开发团队（后端/前端/测试/数据库）
关联文档	PCS-REQ-2026-002 V2.2 §3.2.9/§3.2.11/§3.2.16、SUP-001 §3.2.16/§3.3.12、SUP-002 §3.2.19、SUP-007、SUP-008 V1.1、SUP-010 V1.1、DICT-002、SPEC-P0/P1/P2/P3/P4/P5/P6、**PCS 本体论与语义关系研究说明（V1.6）§3.1 / §3.2b / §3.5**
第一部分：引言
1.1 目的
本文档定义P7阶段（集成模块）的完整需求规格，明确EQUIP_LIST设备表、UTIL公用工程及能耗、EQUIP_LIB复用设备库和供应商数据录入与核算四个集成模块的详细功能需求、接口规范和验收标准。P7阶段是各计算模块输出结果的汇聚层，也是报表生成和签署流程的数据基础。

1.2 文档范围
包含：

EQUIP_LIST：设备表汇总、计算模块结果同步、设备状态管理、设备类型代码管理

UTIL：公用工程消耗汇总、装置综合能耗计算、水平衡

EQUIP_LIB：复用设备检索、设备沉淀、相似度计算

供应商数据录入：实际数据录入、设计值与实际值比对、偏差报告、校核流程

不包含：

报表生成（P8阶段REPORT）

签署流程前端UI完整实现（P9阶段）

AI辅助功能（P10阶段）

各计算模块的算法（P4–P6阶段已交付）

1.3 定义、缩略语和术语
术语/缩写	定义
EQUIP_LIST	设备表子系统，项目内所有设备数据的汇总中心
UTIL	公用工程及能耗子系统
EQUIP_LIB	标准化与复用设备库
SourceModule	设备记录来源计算模块标识（PUMP/VESSEL/HEAT/PSV/CV/MANUAL）
SourceRecordID	来源模块中的记录ID，用于溯源
设备位号	设备在项目中的唯一标识（如P-101A）
TypeCode	设备类型代码（如P/E/T/V/C/A等）
GB/T 50441	石油化工企业能耗计算标准
折标系数	各种能源折算为标准煤/标准油的系数
沉淀	将项目设备记录标准化后收录进复用设备库的操作
供应商数据	设备供应商报价或实际到货的技术参数
偏差报告	设计值与实际值的自动比对报告
GPE	General Purpose Equipment，通用设备规格书
1.4 参考文献
HT-REQ-2026-002 V2.2 §3.2.9（UTIL）、§3.2.11（EQUIP_LIB）、§3.4.9/§3.4.11

SUP-001 §3.2.16（EQUIP_LIST）、§3.3.12（供应商数据录入与核算）

SUP-001 §3.2.17（CONFIG中复用设备库管理）

HT-REQ-2026-DICT-002（设备表数据字典——完整字段定义）

HT-REQ-2026-DICT-001 §3.18（Suppliers表）、§3.19（EquipmentList表）

SPEC-P4（PUMP结果）、SPEC-P5（VESSEL/PSV/HEAT结果）、SPEC-P6（CV等结果）

GB/T 50441《石油化工企业能耗计算标准》

1.5 文档概述
本文档共四个部分。第一部分说明目的、范围和术语。第二部分描述四个集成模块的定位和关系。第三部分详细定义各模块的功能需求、接口和数据需求。第四部分为附录，包含数据流图、待确定问题和工作量估算。

第二部分：综合描述
2.1 产品前景
P7阶段将P4–P6阶段交付的各计算模块输出汇聚为统一的设备数据视图。EQUIP_LIST是系统数据流的中枢——它是所有设备计算结果的汇聚点、UTIL能耗汇总的数据源、REPORT设备一览表的基础、EQUIP_LIB沉淀的来源。供应商数据录入功能则将理论设计数据与实际采购数据打通，确保最终交付数据与实际工程一致。

2.2 产品功能
模块	核心功能	数据来源	数据去向
EQUIP_LIST	设备汇总、状态管理、类型代码管理	PUMP/VESSEL/HEAT/PSV/CV/手动录入	UTIL、REPORT、EQUIP_LIB、采购清单
UTIL	电耗/热负荷汇总、能耗计算、水平衡	PUMP、HEAT、COOL_TOWER、OPEN_CHANNEL、PMS	REPORT
EQUIP_LIB	设备检索、相似度匹配、沉淀管理	EQUIP_LIST（沉淀）、CONFIG（编辑维护）	VESSEL/PUMP/HEAT（选型参考）
供应商数据	实际数据录入、自动比对、偏差报告	手动录入/Excel导入/PDF解析（预留）	EQUIP_LIST、UTIL（实际值更新）
2.3 用户类和特征
用户类	特征	P7阶段相关需求
工艺设计人员	执行各模块计算，录入供应商数据	EQUIP_LIST日常使用、供应商数据录入
校核人员	校核设备数据	供应商数据校核、设备表审核
工艺负责人	审核设备数据、提交沉淀申请	EQUIP_LIB沉淀申请
公用工程工程师	能耗汇总和水平衡分析	UTIL使用
采购工程师	查看设备采购状态	EQUIP_LIST采购字段查询
2.4 运行环境
同SPEC-P0 §2.4。

2.5 设计和实现上的限制
设备表同步规则（V1.1，SUP-007/ADR-0005）：计算记录到达 CHECKED 才自动创建/更新对应设备记录（DRAFT 试算不进设备表）；来源记录 STALE / CHANGE_PENDING / CHANGED / 变更关闭时设备记录联动进入相同状态。设备记录哈希仅覆盖设计参数（tag_number + type_code + design_parameters_json + source_module + source_record_id），商务/采购字段不进门禁、可直接编辑。

溯源完整性：EQUIP_LIST中的记录通过SourceRecordID引用各子系统中的原始计算结果，实现双向溯源。

实际数据分离存储：实际采购数据与设计数据分离存储（实际数据不参与门禁哈希，已确认实际数据的修改需校核人退回）。

沉淀审核：从EQUIP_LIST沉淀到EQUIP_LIB需审核通过。

能耗汇总优先采用实际值：当设备存在已确认的实际数据时，UTIL优先采用实际值参与汇总。

折标系数来源：从PMS或CONFIG读取，遵循GB/T 50441。

位号终身唯一：(project_id, tag_number) 唯一约束覆盖含 OBSOLETE 的设备记录，弃用不复用。

2.6 假设和依赖
依赖P4–P6：各计算模块的结果表结构已定义并可用。

依赖P2：CONFIG中的复用设备库管理功能（沉淀审批）已就绪。

依赖P1：数据血缘、版本管理、状态机框架可用。

假设：有实际项目的设备清单数据可供测试。

假设：WORLEY标准设备类型代码表（DICT-002 §2.2）已导入CONFIG。

第三部分：具体需求
3.1 外部接口需求
3.1.1 用户界面
界面	规格
设备表汇总	表格展示所有设备，支持按类型/状态/来源筛选，行内编辑设计参数
设备详情页	展示完整设计参数、采购数据、实际数据、版本历史、溯源面板
设备同步面板	显示待同步的计算结果，支持单选/批量同步
供应商数据录入	"实际数据"标签页，逐项填写，支持Excel批量导入
偏差报告	设计值vs实际值对比表格，合格/警告/不合格标识
UTIL汇总	公用工程消耗平衡表，按介质类型分组
能耗计算书	综合能耗计算结果（GB/T 50441格式）
EQUIP_LIB检索	按工艺条件模糊搜索匹配设备
沉淀申请	从设备表选择设备提交沉淀，填写标准化信息
3.1.2 软件接口
接口组	端点	说明
EQUIP_LIST	GET /api/v1/equipment-list?project_id=	获取项目设备列表
GET /api/v1/equipment-list/{equipment_id}	获取设备详情
PUT /api/v1/equipment-list/{equipment_id}	更新设备信息
POST /api/v1/equipment-list/sync	同步计算模块结果
POST /api/v1/equipment-list/manual	手动添加设备
DELETE /api/v1/equipment-list/{equipment_id}	删除设备（仅DRAFT且未使用）
设备类型代码	GET /api/v1/equipment-type-codes	获取全部类型代码
GET /api/v1/equipment-type-codes/{type_code}	获取类型详情
UTIL	GET /api/v1/util/summary?project_id=	获取公用工程汇总
POST /api/v1/util/recalculate	重新计算能耗汇总
GET /api/v1/util/energy-consumption	获取综合能耗
GET /api/v1/util/water-balance	获取水平衡
EQUIP_LIB	GET /api/v1/equip-lib/search?params=	检索复用设备
GET /api/v1/equip-lib/{equip_id}	获取设备详情
POST /api/v1/equip-lib/settle	提交沉淀申请
GET /api/v1/equip-lib/settle/pending	待审批沉淀列表
供应商数据	POST /api/v1/equipment-list/{equipment_id}/actual-data	录入实际数据
POST /api/v1/equipment-list/{equipment_id}/actual-data/import	Excel批量导入
GET /api/v1/equipment-list/{equipment_id}/deviation-report	获取偏差报告
POST /api/v1/equipment-list/{equipment_id}/actual-data/confirm	确认实际数据
POST /api/v1/equipment-list/{equipment_id}/actual-data/check	校核实际数据
3.2 功能需求
3.2.1 EQUIP_LIST设备表
需求编号：P7-EQL-001

功能描述：实现项目设备表的汇总、同步和状态管理。

（1）设备记录来源与同步

来源模块	记录类型	触发时机
PUMP（P4）	泵设备记录（TypeCode=P）	泵计算完成并保存时
VESSEL（P5）	容器设备记录（TypeCode=D/V/T/R）	容器计算完成并保存时
HEAT（P5）	换热器/空冷器记录（TypeCode=E）	HTRI导入/重量估算完成时
PSV（P5）	安全阀记录（TypeCode=PSV/PRD/PVRV）	PSV计算完成并保存时
CV（P6）	调节阀记录（TypeCode=CV）	CV计算完成时
手动录入	其他设备（TypeCode=任意）	用户手动添加
同步规则（V1.1：CHECKED 触发 + 状态联动）：

计算模块保存结果（DRAFT）不写入EQUIP_LIST

来源记录到达 CHECKED 时系统自动创建/更新设备记录；手动"同步"按钮仅列出 CHECKED 记录可选

来源记录状态变化自动联动设备记录：STALE→STALE、CHANGE_PENDING→CHANGE_PENDING、CHANGED→CHANGED、变更关闭→CHECKED；来源 OBSOLETE→设备记录 sign_status 跟随 OBSOLETE 且 EquipmentStatus=D

设备记录从来源同步时继承来源的批准深度（来源已 CHECKED 则设备记录设计参数部分自动 CHECKED，无需重复批准）

通过SourceRecordID关联来源记录，实现双向溯源

同步时自动填充：设备位号、类型代码、设计参数、来源模块

设备记录自身为普通计算记录（9 态门禁、无 Rev）；设备一览表（EQUIP_LIST）、单台设备数据表（EQUIP_DATASHEET）、采购清单（PURCHASE_LIST）为交付物类型，经交付物机制签署发布

设备记录 CHANGED 的关闭凭证三选一：来源记录关闭连带、自身变更单、设备一览表升 Rev

（2）设备表完整字段

EQUIP_LIST表完整字段见DICT-002 §3.1–§3.5，包含以下字段组：

字段组	主要字段
标识	TagNumber, EquipmentDescription, EquipmentNameCN, PackageNo, SubProject, UnitNo
类型	TypeCode, EquipmentSubType, EquipmentCategory, IsPressureVessel
来源	SourceModule, SourceRecordID, InPackage, DataSources
状态	EquipmentStatus(N/E/D/M/F), CalcStatus, SignStatus（RecordSignStatus 9 态门禁，与来源记录联动）, ActualDataStatus
设计参数	DesignParameters_JSON（按设备类型动态定义）
采购	Vendor, AlternateVendor, OrderDate, PO Number, Cost, GPE规格
图纸	审批图/认证图收发日期
交付	DeliveryDate, ActualReceivedDate, ForecastOnSite, StorageLocation
安装	InstallationLocation, InstallationContractNumber, InstallationNotes
重量	EmptyWeight, FullWeight, WeighCells, NetWeight
工程	ProcessEngineer, DetailEngineer, FlowsheetDrawingNumber, PID_DrawingNumber
版本	RecordHash（仅设计参数参与）, SignStatus（9 态门禁）, CreatedBy, CreatedAt, UpdatedAt（V1.1：无 Version 字段，商务字段组不参与哈希）
（3）设备类型代码管理

完整的标准类型代码表见DICT-002 §2.2（约80种类型），包括：

大类	典型代码
转动设备	P（泵）、C（压缩机）、B（鼓风机）、A（搅拌器）、M（电机）、ST（汽轮机）、GT（燃气轮机）
静设备	E（换热器）、D（压力容器）、V（储罐/球罐）、T（塔）、R（反应器）、S（分离器）
安全设备	PSV、PRD、PVRV、ERV、FA（阻火器）
成套设备	ARU、MRU、LOS（润滑油系统）、SOS（密封油系统）
其他	H（料斗）、F（加热炉）、CT（冷却塔）、X（离子交换器）
类型代码存储在CONFIG CATEGORY_5标准数据库中，各项目不得自定义。允许扩展但需在CONFIG中登记审批。

（4）设备状态管理

状态字段	值	说明
EquipmentStatus	N（新建）/E（已有）/D（删除）/M（修改）/F（预留）	设备生命周期状态
CalcStatus	未计算/计算中/已完成/需重算	计算状态
SignStatus	DRAFT/CHECKING/.../APPROVED	签署状态（与状态机一致）
ActualDataStatus	未录入/待确认/已确认	实际数据状态
（5）设备弃用/删除规则（V1.1 对齐 SUP-007/ADR-0009）

未绑定交付物的设备记录：设计人填写弃用原因后直接 OBSOLETE，免凭证

已被交付物绑定的设备记录：须创建变更单（change_type=RECORD_CANCELLATION），APPROVED 后 OBSOLETE，绑定 Rev 标 AFFECTED

位号终身唯一：OBSOLETE 设备位号不释放、永不复用，替代设备分配新位号

来源计算记录 OBSOLETE 时设备记录 sign_status 联动 OBSOLETE、EquipmentStatus 置 D

设备状态字段 EquipmentStatus(N/E/D/M/F) 表述生命周期（D=取消），与 sign_status 并存、前者优先表述

验收标准：

各计算模块结果可正确同步至设备表

双向溯源可用（设备表→来源记录→设备表）

类型代码完整（≥80种标准类型）

设备状态管理正确

删除规则正确执行

3.2.2 UTIL公用工程及能耗
需求编号：P7-UTIL-001

功能描述：实现公用工程消耗汇总和装置综合能耗计算。

（1）数据来源

消耗类型	来源模块	说明
电耗	PUMP（设计值或实际值）	从PumpResults.AbsorbedPower读取
电耗	COOL_TOWER（风机功率）	从CoolingTowerResults.FanPower读取
热负荷	HEAT（换热器/空冷器）	从HeatResults.HeatExchanged读取
蒸汽消耗	HEAT（蒸汽加热器）	从HeatResults读取
补充水	COOL_TOWER	从CoolingTowerResults.MakeupWater读取
燃料气	PMS/SIM	从BEDD或用户录入
其他	手动录入	用户补充
（2）实际值优先规则：

当设备存在"已确认"的实际数据（ActualDataStatus=已确认）时，UTIL优先使用实际值

数据血缘中标记来源为"实际采购数据"

实际值替换设计值后，如导致下游结果变化，触发3.3.9变更影响分析

（3）能耗计算（GB/T 50441）

计算项	说明
装置综合能耗	各种能源消耗×折标系数之和
折标系数	从PMS或CONFIG读取，遵循GB/T 50441
能耗单位	kg标油/t产品 或 kg标煤/t产品
输出格式	按GB/T 50441标准表格
（4）水平衡

输入	输出
循环水量（COOL_TOWER）、冷却水消耗（HEAT）、补充水（COOL_TOWER）	全厂水平衡表
（5）UTIL汇总表结构

公用工程类型	消耗量	单位	来源
电	总计	kW	各设备汇总
蒸汽（HP/MP/LP）	分等级	t/h	HEAT汇总
循环水	总量	m³/h	HEAT汇总
补充水	总量	m³/h	COOL_TOWER
燃料气	总量	Nm³/h	PMS/手动
氮气（HP/LP）	分等级	Nm³/h	手动
仪表空气	总量	Nm³/h	手动
...			
验收标准：

电耗/热负荷汇总正确

实际值优先规则生效

综合能耗计算符合GB/T 50441

水平衡闭合

汇总表输出正确

3.2.3 EQUIP_LIB复用设备库
需求编号：P7-EQB-001

功能描述：实现复用设备的检索、相似度匹配和沉淀管理。

（1）设备检索

检索方式	说明
按类型代码	TypeCode筛选
按工艺条件	压力/温度/腐蚀裕量/介质参数区间匹配
按尺寸参数	直径/容积/换热面积/流量/扬程范围
按关键词	设备描述关键词搜索
语义检索	预留AI接口（P10阶段启用）
（2）相似度计算

相似度	推荐规则
≥90%	直接推荐
80%–90%	提示需校核
<80%	仅展示，不推荐
相似度计算采用加权欧几里得距离或余弦相似度，权重在CONFIG中配置。

（3）沉淀流程

text
EQUIP_LIST中选择设备 → 提交沉淀申请
    → 填写标准化信息（标准图号、适用条件范围、材质、重量、关键尺寸、原项目位号）
    → 审核审批（CONFIG）
    → 审批通过后入库
    → 沉淀后的记录与源项目解耦
（4）沉淀数据标准化要求：

字段	要求
标准图号	如有则必填
适用工艺条件范围	压力/温度/介质范围
材质	必填
重量	必填（如有）
关键尺寸	必填
原项目位号	必填
投用日期	必填
验收标准：

检索功能正常

相似度计算合理

沉淀流程完整

标准化信息校验生效

3.2.4 供应商数据录入与核算
需求编号：P7-SUP-001

功能描述：实现供应商实际数据的录入、自动比对和校核流程。

（1）数据录入方式

方式	说明
手动录入	设备详情页"实际数据"标签页逐项填写
Excel批量导入	标准化模板（CONFIG管理），批量导入多个设备
PDF技术规格书解析	预留AI接口（P10阶段），P7阶段支持复制粘贴辅助匹配
（2）实际数据字段（以泵为例）

实际数据字段	设计对应字段	允许偏差
实际流量-扬程曲线	设计工况点（Q, H）	额定点扬程+5%/-0%
实际效率曲线	设计效率η	设计流量下实际效率≥95%设计值
实际NPSHr	设计NPSHr	实际值不得超过设计值
实际电机额定功率	设计电机功率	偏差±10%
实际转速、叶轮直径	设计选型值	允许差异，需重新校核性能
厂家型号、材质	设计选型要求	材质不得低于设计要求
（3）自动比对与偏差报告

结论	颜色	说明
合格	绿色	在允许范围内
警告	黄色	超出允许范围但可接受
不合格	红色	不满足工艺要求
偏差报告包含：对比项、设计值、实际值、偏差、结论。可导出PDF/Excel。

（4）核算与更新流程

text
设计人录入实际数据
    → 系统自动比对，生成偏差报告
    → 设计人确认：
        全部合格/仅警告 → 勾选"确认实际数据满足工艺要求" → 提交校核
        存在不合格项 → 与供应商沟通或修改工艺条件 → 重新录入
    → 校核人校核 → 通过后标记"已确认"
    → 系统更新：
        - 实际关键参数写入对应设备结果记录
        - UTIL自动引用实际值
        - 触发变更影响分析（如有必要）
（5）版本管理与审计（V1.1 修订）

实际数据与设计数据分离存储；实际数据不参与设备记录门禁哈希，无独立版本号（变更留审计痕迹）

所有操作记录审计日志

已确认的实际数据修改需校核人退回

（6）对已发布数据的影响（V1.1 对齐两层模型）

情况	处理
实际数据与设计值差异在允许范围内且不影响下游	仅更新实际数据字段（不进门禁哈希），不触发变更流程
实际数据导致设计值被替换	该设备记录走 CHANGED 流程（修改+重新批准）并以变更单或新版设备一览表关闭；UTIL 自动引用实际值并触发 CIA（如有必要）
验收标准：

手动录入和Excel批量导入正常

自动比对规则正确

偏差报告生成正确

校核流程完整

实际值更新UTIL汇总正确

审计日志完整

3.3 非功能需求
3.3.1 性能需求
指标	要求
设备表查询（1000条记录）	≤2秒
设备同步（单条）	≤1秒
UTIL汇总计算（全项目）	≤5秒
EQUIP_LIB检索	≤1秒
偏差报告生成	≤3秒
Excel批量导入（100条）	≤10秒
3.3.2 数据完整性需求
约束	要求
设备位号	项目内唯一
SourceRecordID	来源记录存在性校验
TypeCode	必须在EquipmentTypeCodes表中存在
实际数据版本	独立于设计数据版本
折标系数	必须来自CONFIG或PMS，不允许用户手动输入
3.4 数据需求
P7阶段使用P0创建的以下表：

equipment_list（完整字段见DICT-002）

equipment_type_codes（标准类型代码）

equipment_lib（复用设备库）

suppliers（供应商信息）

util_results（能耗汇总结果，如需要独立存储）

以及P1阶段的：

data_lineage（血缘记录）

workspaces（工作区）

project_input_checklist（输入清单）

第四部分：附录
4.1 EQUIP_LIST数据流图
text
┌─────────────────────────────────────────────────────────┐
│              EQUIP_LIST 数据汇聚图                      │
└─────────────────────────────────────────────────────────┘

    ┌──────────┐    ┌──────────┐    ┌──────────┐
    │ P4:PUMP  │    │ P5:VESSEL│    │ P5:HEAT  │
    │PumpResults│   │VesselRes │    │HeatResults│
    └────┬─────┘    └────┬─────┘    └────┬─────┘
         │               │               │
         │               │               │
    ┌──────────┐    ┌──────────┐    ┌──────────┐
    │ P5:PSV   │    │ P6:CV    │    │ 手动录入  │
    │PSVResults│    │CVResults │    │(MANUAL)  │
    └────┬─────┘    └────┬─────┘    └────┬─────┘
         │               │               │
         └───────────────┼───────────────┘
                         │ 同步操作（SourceModule + SourceRecordID）
                         ▼
               ┌─────────────────┐
               │   EQUIP_LIST    │
               │  （项目设备表）   │
               └────────┬────────┘
                        │
      ┌─────────────────┼─────────────────┐
      ▼                 ▼                 ▼
┌──────────┐    ┌──────────┐    ┌──────────┐
│   UTIL   │    │  REPORT  │    │EQUIP_LIB │
│(能耗汇总)│    │(设备一览)│    │(沉淀)    │
└──────────┘    └──────────┘    └──────────┘
4.2 供应商数据流程图
text
┌─────────────────────────────────────────────────────────┐
│              供应商数据录入与核算流程                     │
└─────────────────────────────────────────────────────────┘

   ┌──────────┐    ┌──────────┐    ┌──────────┐
   │ 手动录入  │    │Excel导入 │    │PDF解析   │
   │          │    │          │    │(P10预留)│
   └────┬─────┘    └────┬─────┘    └────┬─────┘
        │               │               │
        └───────────────┼───────────────┘
                        ▼
              ┌─────────────────┐
              │ 实际数据录入     │
              │(ActualData_JSON)│
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────────┐
              │  自动比对        │ ← 设计值 vs 实际值
              │  (预设允许偏差)  │ ← 逐项对比
              └────────┬────────┘
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
    ┌──────────┐ ┌──────────┐ ┌──────────┐
    │ 合格(绿) │ │ 警告(黄) │ │不合格(红)│
    └────┬─────┘ └────┬─────┘ └────┬─────┘
         │            │            │
         │            │     禁止确认+通知
         │            │            │
         └────────────┼────────────┘
                      ▼
             ┌─────────────────┐
             │  设计人确认      │
             │  提交校核        │
             └────────┬────────┘
                      │
                      ▼
             ┌─────────────────┐
             │  校核人校核      │
             │  通过→已确认     │
             └────────┬────────┘
                      │
                      ▼
             ┌─────────────────┐
             │  更新下游        │ ← UTIL优先采用实际值
             │  触发影响分析    │ ← 如必要
             └─────────────────┘
4.3 设备同步触发规则（V1.1：CHECKED 触发 + 状态联动）
触发方式	场景	行为
自动同步	来源计算记录到达 CHECKED	自动创建/更新对应设备记录（继承批准深度）
状态联动	来源记录 STALE/CHANGE_PENDING/CHANGED/关闭	设备记录自动进入相同状态，无需手动确认
联动恢复	STALE 重算哈希不变	设备记录联动恢复 CHECKED
手动同步	用户在设备表点击"同步"	列出 CHECKED 记录供选择（DRAFT 不出现）
批量同步	用户在设备表批量操作	一次性同步多个模块的 CHECKED 结果
弃用联动	来源记录 OBSOLETE	设备记录 sign_status 跟随、EquipmentStatus=D
4.4 UTIL汇总类型清单
公用工程类型	枚举值	来源模块	汇总方式
电	ELECTRICITY	PUMP、COOL_TOWER	求和
蒸汽-HP	STEAM_HP	HEAT	求和
蒸汽-MP	STEAM_MP	HEAT	求和
蒸汽-LP	STEAM_LP	HEAT	求和
凝液	CONDENSATE	HEAT	求和
冷却水	COOLING_WATER	HEAT	求和
冷冻水	CHILLED_WATER	HEAT	求和
补充水	MAKEUP_WATER	COOL_TOWER	求和
燃料气	FUEL_GAS	PMS/手动	求和
氮气	NITROGEN	手动	求和
仪表空气	INSTRUMENT_AIR	手动	求和
工厂空气	PLANT_AIR	手动	求和
4.5 待确定问题列表
编号	问题	影响	建议解决方案	状态
P7-OPEN-001	WORLEY标准设备类型代码表的完整清单是否已收集？	类型代码导入	需确认DICT-002 §2.2的清单是否完整	待确认
P7-OPEN-002	折标系数数据来源？	能耗计算精度	建议从GB/T 50441附录获取并导入CONFIG	待确认
P7-OPEN-003	供应商数据Excel导入模板的具体格式？	导入功能实现	需与工艺负责人确认模板格式	待确认
P7-OPEN-004	设备同步是默认自动还是默认手动？	用户体验	建议默认自动同步+可配置关闭	待确认
P7-OPEN-005	EQUIP_LIB相似度计算的权重配置由谁维护？	推荐准确性	由工艺负责人在CONFIG中配置	已确认
P7-OPEN-006	实际数据确认后UTIL自动更新是否需要用户确认？	数据一致性	建议自动更新+通知用户	待确认
P7-OPEN-007	[physical_semantics 评估] 详见 PCS 本体论 V1.6 §3.2b：P7 启动前基于 P4–P6 积累的审计数据（stale_resolution_path / hash_changed / changed_fields），决策是否启用 physical_semantics 语义过滤。决策出口为三元：① 启用语义过滤（成因 B 主导）② 修正 record_hash 范围 / dependency_type 分类（成因 A 或 C 主导）③ 默认不启用（均 < 50%）。**50% 为默认建议值，非硬约束**，架构委员会可基于实测调整阈值或偏离决策规则裁决。	P7 启动前必备评估	按 V1.6 §3.2b 度量指标采集数据，三元决策；评估报告须含方案 A/B/C 成本-收益-精度-召回分析 + 字段级血缘并列评估	待启动
P7-OPEN-008	[规则清单形态评估] 详见 PCS 本体论 V1.6 §3.5：P7 启动前评估 P4–P6 期间 @rule 装饰器累计规则数量。> 20 条 → 启用方案 A（CI 自动生成；P4 Task 0-Design 已预留 `app/core/rules_registry.py` 接口骨架）；≤ 20 条 → 启用方案 B（ADR 附录）。V1.6 §6 规则 10 强调：PR/ADR 模板中"本次新增/修改的业务规则"一行属于审计线索，**非规则清单本体**。	P7 启动前必备评估	按规则数量二选一；RuleCollector 接口已在 P4 Task 0-Design 预留，P7 评估通过后填充实现	待启动
P7-OPEN-009	[UTIL 能耗 5 表 + 催化剂装填量] 详见 SUP-010 V1.1 §3.2.3 + §3.3.4：① 新增 utility_power_items 表（电耗设备清单，含 motor_power/operating_hours/annual_consumption/load_factor）；② 新增 utility_fuel_gas 表（燃料气，含 calorific_value/consumption/annual_consumption）；③ 新增 utility_heat_exchange 表（蒸汽/冷凝水，含 steam_pressure/steam_quality/return_condensate）；④ 新增 utility_energy_summary 表（综合能耗汇总，含 annual_total_energy/toe_conversion_factor/standard_coal_factor）+ 折标煤系数从 CONFIG 取；⑤ 新增 catalyst_loading 表（催化剂装填量，含 volume/weight/density/bed_height）+ 蜡油加氢—综合能耗.xlsx 与惠州汽包实例数据来源；⑥ UTIL 主记录 auxiliary_consumption 表新增 4 字段（electrical_power / fuel_gas_consumption / steam_consumption / cooling_water_consumption，详见 SUP-008 §2.5）。验收：综合能耗汇总与 Excel 偏差 ≤ 2%。	P7 UTIL 数据模型迁移 + 配置项	按 SUP-008 §3.2.5 + SUP-010 §3.2.3 ALTER/CREATE TABLE；CONFIG 新增折标煤系数配置项	待启动

V1.1 新增需求（SUP-007）：

需求编号	内容
P7-EQL-010	设备记录仅在来源记录 CHECKED 时自动创建（DRAFT 试算不进设备表）
P7-EQL-011	来源记录 STALE/CHANGED 等状态变化自动联动设备记录
P7-EQL-012	设备记录哈希仅覆盖设计参数，不覆盖商务/采购字段
P7-EQL-013	采购/商务字段编辑不触发变更流程
P7-EQL-014	设备一览表/设备数据表/采购清单作为交付物类型
P7-EQL-015	设备记录支持独立变更单关闭

## 版本历史

| 版本 | 日期 | 修改内容 | 编制人 |
|---|---|---|---|
| V1.0 | 2026-08-27 | 初始版本 | 联合项目组 |
| V1.1 | 2026-08-28 | incorporate SUP-007：同步改 CHECKED 触发+状态联动；哈希仅盖设计参数；弃用/位号终身唯一；实际数据无独立版本号；供应商数据影响走 CHANGED 流程；新增 P7-EQL-010~015；文件标识改 PCS 前缀 | 联合项目组 |
| V1.2 | 2026-09-03 | 对齐 PCS 本体论 V1.6：关联文档加 V1.6 §3.1/§3.2b/§3.5；新增 P7-OPEN-007（physical_semantics 三元决策评估，50% 阈值软约束）、P7-OPEN-008（规则清单形态评估 A/B 二选一，PR/ADR 行属审计线索非清单本体）；本版本不修改 EQUIP_LIST/UTIL/EQUIP_LIB/SUPPLIER 四大模块主体需求，仅补充 P7 启动前两项必备评估 | 联合项目组 |
| V1.3 | 2026-09-03 | incorporate SUP-008 V1.1 + SUP-010 V1.1：关联文档加 SUP-008 V1.1 + SUP-010 V1.1；新增 P7-OPEN-009（UTIL 能耗 5 表 + 催化剂装填量 + auxiliary_consumption 4 字段扩展）；本版本不修改 EQUIP_LIST/UTIL 主体需求，仅扩展 UTIL 数据模型 | 联合项目组 |
4.6 工作量估算
模块	自研内容	估算工作量
EQUIP_LIST	同步服务、设备管理API、类型代码管理	2-2.5人周
UTIL	能耗汇总、水平衡、折标系数集成	1.5-2人周
EQUIP_LIB	检索服务、相似度计算、沉淀流程	1-1.5人周
供应商数据	实际数据录入、自动比对、偏差报告、校核流程	2-2.5人周
合计		约6.5-8.5人周
P7 SPEC完。 本文档与SPEC-P0至SPEC-P6合并构成完整的《工艺专用综合计算软件》分阶段开发规格说明书体系。后续P8（报表）、P9（工作流与权限）、P10（AI预留与测试部署）的SPEC可继续按此格式编写。


