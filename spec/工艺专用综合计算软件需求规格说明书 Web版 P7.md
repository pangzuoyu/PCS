P7 集成模块开发规格说明书
文件标识	PCS-REQ-2026-002-SPEC-P7
当前版本	V1.4
发布日期	2026-10-01（V1.1 修订 2026-08-28；V1.2/V1.3 修订 2026-09-03；V1.4 修订 2026-10-01，incorporate PCS-SPEC-ADD-001 V1.13 + P7 启动前 mock 裁决报告 P7-REV-01~04：R-01 接受 / R-02 方案 A / R-03 待补采 / R-04 方案 B；9 处修订 + §4.7 启动前裁决清单新增）
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

来源模块	记录类型	TypeCode	触发时机
PUMP（P4）	泵设备记录	P	泵计算完成并保存时
VESSEL（P5）	容器设备记录	D/V/T/R	容器计算完成并保存时
VESSEL（P5）· C-08	两相分离器 sizing 记录	D/V/T	`two_phase_separator_sizing_service` 完成并保存时（SPEC-ADD-001 V1.13 §3.4.2）
VESSEL（P5）· C-07	立式两相分离器记录	D/V/T	`two_phase_separator_service` 完成并保存时
VESSEL（P5）· C-10	三相分离器记录	D/V/T	`three_phase_separator_service` 完成并保存时
HEAT（P5）	换热器/空冷器记录	E	HTRI 导入/重量估算完成时
PSV（P5）· C-21	安全阀/火灾泄放记录	PSV/PRD	PSV 计算完成并保存时
PSV（P5）· C-20	储罐通风（呼吸阀）记录	PVRV	`breathing_valve_service` 火灾热输入分支完成时
CV（P6）· C-24	调节阀记录	CV	CV 计算完成时（含 Masonelian fl 三模型输出）
COOL_TOWER（P6）	冷却塔记录	CT	冷却塔计算完成并保存时
PSYCHRO（P6.5）· C-16	甘醇脱水塔记录	T/V	甘醇脱水计算完成并保存时；**默认不进设备表，需手动"同步"触发**（见下方注记）
OPEN_CHANNEL（P6）	明渠流记录	—	**不进设备表**，仅 UTIL 汇总引用
手动录入	其他设备	任意	用户手动添加

> **C-16 甘醇脱水塔同步注记（P7-REV-01）**：PSYCHRO C-16 计算结果默认不自动进设备表（甘醇脱水塔多属成套包 ARU/MRU，非单台设备）。如需进设备表，由设计人在设备详情页手动"从 PSYCHRO 同步"触发，TypeCode 按实际选 T（塔）或 V（储罐）。COOL_TOWER（CT）与 OPEN_CHANNEL 的同步规则见上表。

- C-08/C-07/C-10 三个 VESSEL 子服务的设备记录共用 TypeCode 组 D/V/T/R，由 `source_service` 字段区分（`two_phase_separator_sizing_service` / `two_phase_separator_service` / `three_phase_separator_service`）
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
EQUIP_LIST 是 P4–P6 阶段交付的各计算模块输出结果的汇聚中枢，所有计算记录（CHECKED 状态）自动同步至 EQUIP_LIST，并支持手动录入。数据流：P4:PUMP / P5:VESSEL / P5:HEAT / P5:PSV / P6:CV / 手动录入 → 同步操作（SourceModule + SourceRecordID）→ EQUIP_LIST → UTIL（能耗汇总）/ REPORT（设备一览）/ EQUIP_LIB（沉淀）。

4.2 供应商数据流程图
供应商数据通过手动录入 / Excel 导入 / PDF 解析（预留）进入"实际数据录入"（ActualData_JSON），经自动比对（设计值 vs 实际值）得到合格 / 警告 / 不合格结论，设计人确认 + 校核人校核后标记"已确认"，最终更新下游（UTIL 自动引用实际值 + 触发影响分析）。

4.3 设备同步触发规则（V1.1：CHECKED 触发 + 状态联动）
触发方式	场景	行为
自动同步	来源计算记录到达 CHECKED	自动创建/更新对应设备记录（继承批准深度）
状态联动	来源记录 STALE/CHANGE_PENDING/CHANGED/关闭	设备记录自动进入相同状态，无需手动确认
联动恢复	STALE 重算哈希不变	设备记录联动恢复 CHECKED
手动同步	用户在设备表点击"同步"	列出 CHECKED 记录供选择（DRAFT 不出现）
批量同步	用户在设备表批量操作	一次性同步多个模块的 CHECKED 结果
弃用联动	来源记录 OBSOLETE	设备记录 sign_status 跟随、EquipmentStatus=D
| C-08 两相分离器 | `two_phase_separator_sizing_service` 到达 CHECKED | 自动创建设备记录（TypeCode=D/V/T），`source_service=two_phase_separator_sizing_service` |
| C-16 甘醇脱水塔 | 默认不自动进设备表 | 设计人手动词"从 PSYCHRO 同步"，TypeCode=T/V |
| C-24 调节阀 | `cv_engine` + `flashing_correction` 到达 CHECKED | 自动创建设备记录（TypeCode=CV），`masonelian_model` 写入设计参数 |
| COOL_TOWER | 冷却塔计算到达 CHECKED | 自动创建设备记录（TypeCode=CT） |

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

> **数据模型版本注记（V1.4 新增，P7-REV-07）**：
> - **V1.3 基线**：`util_results` 单表 + `consumption_json` JSONB 容器（13 类公用工程枚举见 §4.4）
> - **SUP-010 增量（P7-OPEN-009 裁决后）**：5 表规范化（`utility_power_items` / `utility_fuel_gas` / `utility_heat_exchange` / `utility_energy_summary` / `catalyst_loading`）+ `auxiliary_consumption` 4 字段（`electrical_power` / `fuel_gas_consumption` / `steam_consumption` / `cooling_water_consumption`）
> - **裁决出口**：P7 启动前由架构委员会裁决 P7-OPEN-009 走方案 A（纳入 P7 基线，+2~3 人周）或方案 B（延后 P7.5 增量）。本 SPEC V1.4 默认描述 V1.3 基线；**V1.4 mock 决议（2026-10-01）= 方案 A**：5 表迁移排期详见 `docs/P7-OPEN-009-SUP-010-5table-migration-schedule.md`。

4.5 待确定问题列表
（V1.4 mock 决议后状态更新，详见上表 P7-OPEN-007/008/009 行）

4.6 工作量估算（V1.4 mock 决议 = 方案 A）
模块	自研内容	估算工作量
EQUIP_LIST	同步服务、设备管理 API、类型代码管理、C-08/C-16/C-24 多源适配	2.5–3 人周
UTIL	能耗汇总、水平衡、折标系数集成	1.5–2 人周（V1.3 基线）+ 2–3 人周（SUP-010 增量，方案 A 已采纳）
EQUIP_LIB	检索服务、相似度计算、沉淀流程	1–1.5 人周
供应商数据	实际数据录入、自动比对、偏差报告、校核流程	2–2.5 人周
| **小计（不含 SUP-010，方案 B 备选）** | | **7–9 人周** |
| **小计（含 SUP-010，方案 A）** | | **9–12 人周** |
| **P7 总工时（V1.4 mock 决议）** | | **10–13 人周** |

> **P7 启动前必备评估（不计入上表）**：
> - P7-OPEN-007 physical_semantics 评估：3–5 人日 → **mock 决议 2026-10-01 = 待补采**（详见 §4.7 P7-REV-03）
> - P7-OPEN-008 规则清单形态评估：1–2 人日 → **mock 决议 2026-10-01 = 方案 B**（详见 §4.7 P7-REV-04）
> - **合计 4–7 人日（约 1 人周）**

4.7 P7 启动前裁决清单（V1.4 新增）

| 编号 | 问题 | 裁决出口 | mock 决议（2026-10-01） | 责任方 | 截止 |
|---|---|---|---|---|---|
| P7-REV-01 | P7 SPEC §3.2.1 设备来源表遗漏 PSYCHRO（C-16）/COOL_TOWER/OPEN_CHANNEL | **已在本 V1.4 补来源行 + 注记** | ✅ **接受 V1.4 修订 1**（工艺负责人 2026-10-01 mock 签收）| 工艺负责人 | V1.4 发布即闭环 |
| P7-REV-02 | P7-OPEN-009（UTIL 5 表）是否纳入 P7 基线 | 方案 A（纳入，+2–3 人周）/ 方案 B（延后 P7.5） | ✅ **方案 A（纳入 P7 基线）**（mock 决议 2026-10-01，用户裁决确认；详见 `docs/P7-OPEN-009-SUP-010-5table-migration-schedule.md`）| 架构委员会 + 工艺负责人 | P7 Sprint 0 |
| P7-REV-03 | P7-OPEN-007（physical_semantics）是否启用 | 三元决策（启用语义过滤 / 修正 record_hash / 默认不启用），50% 软阈值 | ⏸️ **推迟三元决策 → 待补采**（mock 决议 2026-10-01；无样本不可套用「三者均 < 50% → 默认不启用」分支；触发条件 T0+T1+30 天；详见 `docs/P7-OPEN-007-physical-semantics-evaluation.md`）| 架构委员会 | P7 Sprint 0 |
| P7-REV-04 | P7-OPEN-008（规则清单形态）方案 A/B | >20 条 → 方案 A（CI 自动生成）；≤20 条 → 方案 B（ADR 附录） | ✅ **方案 B（ADR 附录）**（mock 决议 2026-10-01；@rule = 0 远 ≤ 20；详见 `docs/P7-OPEN-008-rule-registry-form-evaluation.md`）| 架构委员会 | P7 Sprint 0 |

> **mock 决议说明**：上表 4 项裁决为 2026-10-01 架构委员会 + 工艺负责人 mock 决议，落地于 `docs/P7-REV-01-04-mock-decisions.md`。真实会议召开后，如 mock 决议被否决，按 V1.4.1 micro-revision 修订（沿用 P6-9-PICKUP-5 5B V1.0→V1.13 模式）。

P7 SPEC V1.4 完。 本文档与 SPEC-P0 至 SPEC-P6 合并构成完整的《工艺专用综合计算软件》分阶段开发规格说明书体系。后续 P8（报表）、P9（工作流与权限）、P10（AI 预留与测试部署）的 SPEC 可继续按此格式编写。V1.4 mock 裁决报告详见 `docs/P7-REV-01-04-mock-decisions.md`；评估报告详见 `docs/P7-OPEN-007-physical-semantics-evaluation.md` + `docs/P7-OPEN-008-rule-registry-form-evaluation.md` + `docs/P7-OPEN-009-SUP-010-5table-migration-schedule.md`。R=1 教训（bug-114 + bug-115）已登记于 `.wolf/buglog.json`。
