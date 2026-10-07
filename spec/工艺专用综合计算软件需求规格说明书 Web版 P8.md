P8 报表与输出开发规格说明书
文件标识	PCS-REQ-2026-002-SPEC-P8
当前版本	V1.2
发布日期	2026-08-27（V1.1 修订 2026-08-28；V1.2 修订 2026-09-03，incorporate SUP-009 V1.0：HEAT 报表字段对齐 heat_results 39 字段 + ache_params JSONB）
编制部门	工艺部 / 信息化联合项目组
适用对象	内部开发团队（后端/前端/测试/数据库）
关联文档	PCS-REQ-2026-002 V2.2 §3.2.12、SUP-001 §3.2.17/§3.2.18、SUP-002 §2.1、SUP-003~007、SUP-009 V1.0、DICT-001、SPEC-P0/P1/P2/P3/P4/P5/P6/P7、REPORT_BUILDER 数据源映射字典、HTRI 输出文件（121-A-101.xls、131-E-102-EOR.xls）
第一部分：引言
1.1 目的
本文档定义P8阶段（报表与输出）的完整需求规格，明确REPORT综合报表引擎和REPORT_BUILDER自定义报表构建器两大模块的详细功能需求、接口规范、模板管理机制和验收标准。P8阶段是系统最终交付物的生成层，将各计算模块的结果转化为标准化的计算书、数据表和委托条件表。

1.2 文档范围
包含：

REPORT：Word模板填充、Excel模板填充、PDF生成、二维码防篡改、假设数据声明页、签署页集成

REPORT_BUILDER：报表定义管理、字段选择器、过滤条件构建器、多数据源JOIN、报表执行与导出

与CONFIG的模板管理集成

与签署流程的关联（最终版生成）

不包含：

CONFIG中模板文件的上传/审批管理（P2已交付）

签署流程前端完整实现（P9阶段）

AI辅助报表生成（P10阶段预留）

1.3 定义、缩略语和术语
术语/缩写	定义
REPORT	综合报表子系统
REPORT_BUILDER	自定义报表构建器
.dotx	Word模板文件格式
.xltx	Excel模板文件格式
占位符	模板中需要被数据填充的标记
二维码	嵌入PDF页脚的防篡改验证码
哈希值	数据完整性校验值
假设数据声明页	列出所有基于假设输入的结果的页面
签署页	包含四级签署人信息的页面
数据源	自定义报表中可选择的字段来源实体
过滤条件	自定义报表中用于筛选记录的条件组合
报表定义	完整的自定义报表配置，包含数据源、字段、过滤条件
1.4 参考文献
HT-REQ-2026-002 V2.2 §3.2.12（综合报表子系统）、§3.4.12（详细规格）

SUP-001 §3.2.17（CONFIG模板管理）、§3.2.18（自定义报表构建器）

SUP-002 §2.1（技术选型：python-docx/openpyxl/ReportLab）

SPEC-P2（CONFIG模板文件管理）

SPEC-P7（EQUIP_LIST设备表，报表主要数据源）

DICT-001 §3.17（配置资产表）、DICT-002（设备表字典）

1.5 文档概述
本文档共四个部分。第一部分说明目的、范围和术语。第二部分描述报表子系统的定位和功能。第三部分详细定义REPORT和REPORT_BUILDER的功能需求、接口和数据需求。第四部分为附录，包含模板占位符示例、报表定义示例和待确定问题。

第二部分：综合描述
2.1 产品前景
P8阶段将系统内存储的结构化工程数据转化为标准化的交付文档。REPORT子系统负责固定格式的正式报表（计算书、数据表、委托条件表），REPORT_BUILDER则提供灵活的数据提取和导出能力，满足项目执行过程中的临时核查和进度跟踪需求。两者互补，共同构成系统的输出层。

2.2 产品功能
模块	核心功能	模板来源
REPORT	Word/Excel模板填充、PDF生成、二维码防篡改、假设数据声明、签署页	CONFIG CATEGORY_4
REPORT_BUILDER	自定义报表定义、字段选择、过滤条件、多数据源、执行导出	无固定模板，结构化JSON定义
2.3 用户类和特征
用户类	特征	P8阶段相关需求
工艺设计人员	生成计算书和设备数据表	REPORT日常使用
校核/审核/审定	查看签署页和最终版	REPORT签署页
工艺负责人	创建自定义报表定义	REPORT_BUILDER定义管理
项目管理人员	生成进度跟踪报表	REPORT_BUILDER执行
系统管理员	管理报表模板	CONFIG中维护（P2已交付）
2.4 运行环境
同SPEC-P0 §2.4。

2.5 设计和实现上的限制
模板统一管理：所有正式报表模板在CONFIG中管理，REPORT仅调用当前有效版本。

文件不可变性：已生成的PDF/Word文件不可修改，如需更正必须基于新数据版本重新生成。

二维码强制：所有正式交付的PDF计算书必须包含数据来源二维码。

假设数据透明：存在非VERIFIED输入项时，报表必须包含假设数据声明页。

REPORT_BUILDER非BI工具：不支持复杂聚合、枢轴和图表，聚焦于数据提取。

REPORT_BUILDER执行审计：每次执行均记录日志。

2.6 假设和依赖
依赖P2：CONFIG中的模板文件管理和审批发布功能已可用。

依赖P7：EQUIP_LIST等数据表的**录入能力**已交付（表 + API）。P8 测试需自备数据种子（seed 脚本或 fixture），不假设真库有数据。

> 2026-10-07 修订：原文「已填充数据」把「能力」误写成「数据」。P7 交付的是录入工具
> （record_actual_data / confirm_actual_data + API），真实数据不存在（没有真实项目的
> 设备录入过）。按原文读会得出「P8 无法启动」的结论，而实际缺口只是缺 seed。
> 详见 `docs/PCS-NOTE-P8前置清单与3项修订-2026-10-07.md`。

依赖P1：签署状态和版本管理框架可用。

假设：已有标准Word/Excel模板文件（.dotx/.xltx）可供测试。

假设：python-docx/openpyxl/ReportLab库版本已锁定并通过Golden Test。

第三部分：具体需求
3.1 外部接口需求
3.1.1 用户界面
界面	规格
报表生成中心	按报表类型分类（计算书/数据表/委托条件表），选择设备或模块，点击生成
模板选择	下拉选择当前有效版本的模板，显示模板版本和更新日期
生成预览	生成前预览数据填充结果（支持分页预览）
报表下载	生成完成后提供PDF/Word/Excel下载
报表定义编辑器（REPORT_BUILDER）	左侧数据源字段树，中间已选字段列表，右侧过滤条件构建器，底部预览
报表执行面板	选择已发布报表定义，显示过滤条件摘要，执行并导出
报表定义管理列表	展示定义名称、版本、状态、创建人、共享范围
3.1.2 软件接口
接口组	端点	说明
REPORT	POST /api/v1/report/generate	生成报表（传入模板ID、数据记录ID列表、输出格式）
GET /api/v1/report/{report_id}/status	查询生成任务状态
GET /api/v1/report/{report_id}/download	下载生成的文件
GET /api/v1/report/templates?category=	获取可用模板列表
GET /api/v1/report/templates/{template_id}/placeholders	获取模板占位符
REPORT_BUILDER	POST /api/v1/report-builder/definitions	创建报表定义
GET /api/v1/report-builder/definitions	列出报表定义
GET /api/v1/report-builder/definitions/{def_id}	获取定义详情
PUT /api/v1/report-builder/definitions/{def_id}	更新定义
POST /api/v1/report-builder/definitions/{def_id}/publish	发布定义（需审批）
POST /api/v1/report-builder/definitions/{def_id}/execute	执行报表
GET /api/v1/report-builder/datasources	获取可用数据源和字段树
3.2 功能需求
3.2.1 REPORT综合报表引擎
需求编号：P8-RPT-001

功能描述：实现基于模板的自动化报表填充和生成。

（1）模板调用机制

步骤	说明
1. 获取模板	从CONFIG API获取当前有效版本的模板文件（.dotx/.xltx）
2. 解析占位符	解析模板中的占位符，与数据字典字段映射
3. 数据收集	根据占位符从各数据表收集数据
4. 填充生成	使用python-docx/openpyxl填充占位符
5. 格式转换	转换为PDF（如需），嵌入二维码
6. 版本关联	记录文件版本与数据版本关联
（2）支持的报表类型

报表类型	模板格式	数据来源
管道计算书	.dotx	PipingResults
泵数据表	.dotx/.xltx	PumpResults
安全阀数据表	.dotx	PSVResults
容器数据表	.dotx	VesselResults
换热器规格书	.dotx	HeatResults
设备一览表	.xltx	EquipmentList
公用工程平衡表	.xltx	UTIL汇总
综合能耗计算书	.dotx	UTIL + GB/T 50441
委托条件表（用电/用水/用气）	.xltx	各模块汇总
管道一览表	.xltx	PipingResults

V1.1 注（SUP-007）：上表中的正式交付文档（管道一览表、设备一览表、各类计算书/数据表）生成时创建 deliverables 记录（对应 deliverable_type），走交付物签署矩阵发布并快照绑定 record_hash；交付物创建 UI 集成编号模板预览（自动/手动 doc_no，项目内唯一校验），同类型可按装置等拆分范围创建多份。
（3）二维码防篡改

需求项	规格
嵌入位置	PDF文件每页页脚
内容	doc_no + Rev、版本目的、生成时间、绑定记录哈希摘要（deliverable_record_bindings）
哈希算法	SHA-256
验证方式	扫描二维码可查看数据库中的原始数据哈希值比对
防篡改机制	文件生成后锁定关联输入数据（快照绑定，SUP-007）
（4）假设数据声明页

触发条件	行为
存在ASSUMED或NOT_STARTED输入项	报表中自动加入"假设与参考数据清单"页
声明页内容	列出所有假设输入项名称、值、来源、假设理由
标识传播	受影响字段在表格中带橙色三角标记
签署约束	签署人必须勾选"已知悉并接受上述假设数据"
（5）签署页集成（V1.1：面向交付物层）

需求项	规格
生成时机	交付物签署矩阵走完（APPROVED）后生成最终版
签署页内容	按签署矩阵动态列（Rev / Description / Orig / Check / Review / Appr / Cust / Date，SUP-005 格式）；CUSTOMER 栏显示"客户姓名（代录：X）"（ADR-0007）
电子签名	与交付物签署矩阵集成，从签署记录/代录凭证读取
最终版限制	存在REQUIRED未完成输入项时禁止发布最终版；绑定记录须全部 CHECKED（SUP-007 绑定准入）
假设数据声明	签署人须勾选"已知悉并接受上述假设数据"（与（4）联动）
（6）生成任务管理

需求项	规格
异步生成	复杂报表使用ARQ后台任务
状态查询	提供任务状态查询接口
失败重试	生成失败可重试，保留错误日志
文件存储	生成文件存储于文件系统，数据库记录元数据
验收标准：

各类型报表生成正确，格式符合模板

二维码嵌入且哈希值正确

假设数据声明页在存在假设时自动加入

签署页信息完整

异步生成和状态查询正常

生成文件与数据版本关联正确

3.2.2 REPORT_BUILDER自定义报表构建器
需求编号：P8-RPB-001

功能描述：实现灵活的数据提取和导出，支持管理员和工艺负责人创建自定义报表定义。

（1）可用数据源清单

数据源标识	数据源名称	核心字段
EQUIP_LIST	设备表	TypeCode, TagNumber, Description, Vendor, VendorModel, EquipmentStatus, DesignParameters_JSON, ActualDataStatus
PIPING_RESULTS	管道一览表	LineNo, LineSize, MaterialClass, FluidCode, DesignPress, DesignTemp, NormOperPress
STREAMS	物流数据	StreamName, Phase, Temp, Press, MassFlow, Composition_JSON
PSV_RESULTS	安全阀结果	TagNumber, SetPressure, ReliefCapacity, OrificeArea
PUMP_RESULTS	泵结果	TagNumber, Flow, Head, NPSHa, Power
VESSEL_RESULTS	容器结果	TagNumber, Volume, Diameter, Length
HEAT_RESULTS	换热器结果	TagNumber, Area, HeatDuty, OverallU
UTIL_RESULTS	能耗汇总	EquipmentID, Power, HeatLoad, SteamConsumption
INPUT_CHECKLIST	输入清单	InputName, Module, Status, SourceType
DATALINEAGE	血缘关系	SourceType, SourceID, TargetType, TargetID
PROJECTS	项目信息	ProjectNo, ProjectName, Location
SUPPLIERS	供应商信息	SupplierName, Type, Rating, Contact_JSON
CONFIG_ASSETS	配置资产	AssetID, Category, Name, CurrentVersion, Status
（2）报表定义结构（ReportDefinition）

字段	类型	说明
ReportDefID	GUID	报表定义ID
ReportName	string	报表名称
ReportCategory	enum	设备类/管道类/物流类/综合类/管理类
Description	string	描述
DataSources	JSON[]	数据源列表（可多源JOIN）
SelectedFields	JSON[]	选中字段列表，每项含source/field/alias/order/visible
FilterConditions	JSON[]	过滤条件，支持AND/OR组合
SortBy	JSON[]	排序字段
MaxRows	int	最大行数限制（默认10000）
OutputFormat	enum	Excel/CSV/PDF/Word
OutputTemplateID	FK nullable	关联CONFIG中的输出模板
CreatedBy	UserID	创建人
CreatedAt	datetime	创建时间
Status	enum	草稿/已发布/已作废
Version	string	版本号
SharedWith	enum	全部用户/指定角色/仅创建人
ProjectScope	enum	跨项目通用/指定项目/当前工作区
（3）字段选择器

需求项	规格
字段树	基于数据字典动态生成左侧树形列表
拖拽排序	已选字段支持拖拽调整顺序
别名设置	支持为字段设置显示别名
显示/隐藏	支持字段显示和隐藏切换
（4）过滤条件构建器

支持的操作符：

操作符	说明	适用字段类型
EQ	等于	string/number/date/enum
NEQ	不等于	string/number/date/enum
GT	大于	number/date
GTE	大于等于	number/date
LT	小于	number/date
LTE	小于等于	number/date
IN	在列表中	string/number/enum
NOT_IN	不在列表中	string/number/enum
CONTAINS	包含文本	string
STARTS_WITH	以...开头	string
ENDS_WITH	以...结尾	string
IS_NULL	为空	all
IS_NOT_NULL	不为空	all
BETWEEN	在范围内	number/date
LIKE	模糊匹配	string
支持AND/OR分组，条件可嵌套。

（5）报表执行

需求项	规格
执行权限	所有用户可执行已发布报表
临时调整	执行时允许临时调整过滤条件（不修改定义本身）
结果展示	表格形式展示前N条
导出	支持Excel/CSV/PDF导出
审计	每次执行记录日志（执行人、时间、定义版本、条件快照、行数）
（6）版本管理与审批

需求项	规格
创建后状态	DRAFT，仅创建人可见和使用
发布审批	需审核角色审批通过
发布后可见	按SharedWith范围对他人可见
修改	已发布定义修改时自动创建新版本
版本规则	遵循V主.次.修订
（7）典型使用场景示例

场景一：筛选所有没有输入厂商资料的设备

json
{
  "reportName": "未录入厂商资料的设备清单",
  "dataSources": ["EQUIP_LIST"],
  "selectedFields": [
    {"source": "EQUIP_LIST", "field": "TagNumber", "alias": "设备位号"},
    {"source": "EQUIP_LIST", "field": "TypeCode", "alias": "类型"},
    {"source": "EQUIP_LIST", "field": "Vendor", "alias": "供应商"},
    {"source": "EQUIP_LIST", "field": "VendorModel", "alias": "型号"}
  ],
  "filterConditions": {
    "operator": "AND",
    "conditions": [
      {"source": "EQUIP_LIST", "field": "Vendor", "operator": "IS_NULL"},
      {"source": "EQUIP_LIST", "field": "SourceModule", "operator": "IN", 
       "value": ["PUMP", "VESSEL", "HEAT", "PSV"]}
    ]
  },
  "sortBy": [{"field": "TagNumber", "direction": "ASC"}],
  "outputFormat": "Excel"
}
场景二：筛选所有假设数据（输入完备性）

json
{
  "reportName": "假设数据清单",
  "dataSources": ["INPUT_CHECKLIST"],
  "selectedFields": [
    {"source": "INPUT_CHECKLIST", "field": "Module", "alias": "关联模块"},
    {"source": "INPUT_CHECKLIST", "field": "InputName", "alias": "输入项名称"},
    {"source": "INPUT_CHECKLIST", "field": "Status", "alias": "状态"},
    {"source": "INPUT_CHECKLIST", "field": "AssumptionReason", "alias": "假设理由"}
  ],
  "filterConditions": {
    "operator": "AND",
    "conditions": [
      {"source": "INPUT_CHECKLIST", "field": "Status", "operator": "EQ", "value": "ASSUMED"}
    ]
  }
}
场景三：设备表+供应商信息联合查询

json
{
  "reportName": "设备采购状态一览",
  "dataSources": ["EQUIP_LIST", "SUPPLIERS"],
  "selectedFields": [
    {"source": "EQUIP_LIST", "field": "TagNumber", "alias": "位号"},
    {"source": "EQUIP_LIST", "field": "TypeCode", "alias": "类型"},
    {"source": "SUPPLIERS", "field": "SupplierName", "alias": "供应商"},
    {"source": "EQUIP_LIST", "field": "OrderDate", "alias": "下单日期"},
    {"source": "EQUIP_LIST", "field": "DeliveryDate", "alias": "交付日期"}
  ],
  "filterConditions": {
    "operator": "OR",
    "conditions": [
      {"source": "EQUIP_LIST", "field": "EquipmentStatus", "operator": "EQ", "value": "N"},
      {"source": "EQUIP_LIST", "field": "EquipmentStatus", "operator": "EQ", "value": "M"}
    ]
  }
}
（8）即席导出与固化（V1.1，SUP-007）

需求项	规格
即席导出件	非交付物：无 Rev、无签署，文件带"非发布件"时间戳水印
固化交付物	提供"固化为交付物"动作：定义+当前过滤快照 → deliverable_type=CUSTOM_REPORT 交付物，走签署矩阵发布
演示版	导出自动叠加 DEMO 水印（SUP-006）；报表定义数量限 3 个

验收标准：

报表定义CRUD正常

字段选择器基于数据字典动态生成

过滤条件支持所有操作符

多数据源JOIN正确

执行和导出正常

审计日志完整

权限控制正确

即席导出带非发布件水印；固化交付物走签署并快照

3.3 非功能需求
3.3.1 性能需求
指标	要求
简单报表生成（单设备数据表）	≤5秒
复杂报表生成（全项目设备一览表）	≤15秒
报表定义执行（10000行）	≤10秒
模板列表查询	≤500ms
生成任务状态查询	≤200ms
3.3.2 安全性与合规
指标	要求
文件下载权限	仅项目相关角色可下载
二维码哈希	SHA-256
最终版不可修改	已生成文件不可覆盖
审计日志	生成和下载操作记录日志
3.4 数据需求
P8阶段使用以下表：

report_definitions（自定义报表定义）

report_execution_logs（报表执行审计日志）

以及各业务数据表（作为报表数据源）

第四部分：附录
4.1 模板占位符示例
Word模板占位符格式（示例）：

text
{{Project.ProjectNo}} - 项目编号
{{Project.ProjectName}} - 项目名称
{{PipingResults.LineNo}} - 管道号
{{PipingResults.LineSize}} - 管道尺寸
{{PipingResults.MaterialClass}} - 材料等级
{{PipingResults.DesignPress}} - 设计压力
{{PumpResults.TagNumber}} - 泵位号
{{PumpResults.Flow}} - 流量
{{PumpResults.Head}} - 扬程
{{EquipmentList.TagNumber}} - 设备位号
{{EquipmentList.Vendor}} - 供应商
4.2 自定义报表定义与执行流程
text
┌─────────────────────────────────────────────────────────┐
│          REPORT_BUILDER 报表定义与执行流程               │
└─────────────────────────────────────────────────────────┘

  创建报表定义
      │
      ▼
┌─────────────────┐
│ 选择数据源       │ ← 从可用数据源列表选择
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 选择字段         │ ← 从字段树选择，设置别名和顺序
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 设置过滤条件     │ ← 构建AND/OR条件组合
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 设置排序和限制   │ ← 排序字段、最大行数
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 保存为草稿       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 发布审批         │ ← 审核角色审批
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 已发布           │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 执行报表         │ ← 用户选择定义，可临时调整条件
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 导出结果         │ ← Excel/CSV/PDF
└─────────────────┘
4.3 待确定问题列表
编号	问题	影响	建议解决方案	状态
P8-OPEN-001	正式报表模板（.dotx/.xltx）由谁提供？	模板准备	需工艺负责人提供标准模板	待确认
P8-OPEN-002	PDF生成的字体要求（中文字体嵌入）？	生成效果	需确认公司标准字体	待确认
P8-OPEN-003	REPORT_BUILDER是否需要支持图表？	功能范围	SPEC明确不支持，仅数据提取	已确认
P8-OPEN-004	委托条件表的格式是否已有标准？	模板设计	需各专业提供标准格式	待确认
P8-OPEN-005	多数据源JOIN时的关联键如何定义？	实现复杂度	通过外键自动关联，需定义JOIN规则	待确认
P8-OPEN-006	[HEAT 报表字段对齐 heat_results] 详见 SUP-009 V1.0 §3.1 + §4：REPORT_BUILDER 数据源 HEAT_EXCEL 需要适配 heat_results 新表 39 字段（基础/热工/壳程管程 JSONB/几何/热阻分布）+ ache_params JSONB（风机/空气侧/翅片/管嘴/空气侧阻力分布）。原9 字段保留向后兼容（detail_level=BASIC 仍可生成简化报表）；扩展字段（detail_level=DETAIL）需要 121-A-101.xls（HTRI 空冷器 33 列）+ 131-E-102-EOR.xls（TEMA 管壳式 23 列）两个模板源均覆盖。建议新建 ADR-0028 记录 HEAT 报表双 detail_level 模板裁决。验收：detail_level=DETAIL 报表字段覆盖率 ≥ 95%。	P8 REPORT_BUILDER 数据源适配	HEAT 数据源字段映射配置 + ADR-0028 起草 + HTRI 输出文件兼容性测试	待启动
4.4 工作量估算
模块	自研内容	估算工作量
REPORT引擎	模板填充、PDF生成、二维码、假设声明页	2-2.5人周
REPORT_BUILDER	定义管理、字段选择器、过滤构建器、执行引擎	2-3人周
模板集成	与CONFIG API对接、占位符解析	0.5-1人周
合计		约4.5-6.5人周

## 版本历史

| 版本 | 日期 | 修改内容 | 编制人 |
|---|---|---|---|
| V1.0 | 2026-08-27 | 初始版本 | 联合项目组 |
| V1.1 | 2026-08-28 | incorporate SUP-004/007：正式报表生成即创建交付物（编号模板预览、快照绑定、绑定准入仅 CHECKED）；签署页按矩阵动态列+客户代录标注；二维码内容改 doc_no+Rev+哈希摘要；REPORT_BUILDER 新增即席导出非交付物/固化交付物/演示水印；文件标识改 PCS 前缀 | 联合项目组 |
| V1.2 | 2026-09-03 | incorporate SUP-009 V1.0：关联文档加 SUP-009；新增 P8-OPEN-006（HEAT 报表字段对齐 heat_results 39 字段 + ache_params JSONB + detail_level=BASIC/DETAIL 双模板 + ADR-0028）；主体报表引擎不变，仅扩 HEAT 数据源字段映射 | 联合项目组 |


P8 报表与输出开发计划（修订版 V2.0）
修订日期：2026-10-07
修订人：首席架构师 / 工艺专家
基于：SPEC-P8 V1.2、开发计划 V1.3、TODOS.md 2026-10-07 全量核销
核心变更：重写任务分解、确定 PDF 转换技术路线、设计模板自定义机制、裁决交付物写面归属

一、P0 裁决与冻结（开工前置，第 1 周）
1.1 交付物写面裁决
裁决：P8-MVP 不含正式交付物写面（create / issue / customer-approval-proxy / 签署矩阵 / 最终版）。

依据：TODOS.md 已明确 D 模块写面改判到 P9，SignatureMatrix.steps_json 的消费方（SUP-005）未落地。ChangeNoticeService.create_change_notice 写死 matrix_id=None 而 Deliverable.matrix_id 是 NOT NULL 带 FK，真库上必 500 —— **该函数已于 2026-10-08 改为显式 `raise NotImplementedError`（P9A-DLV-009），不再留哑雷；功能本身待 P9A-DLV-007 的矩阵消费方。**

P8 只交付：

文件生成（Word / Excel / PDF）

二维码嵌入（指向验证 URL，哈希比对）

假设数据声明页

即席导出 + 非发布件水印 + DEMO 水印

REPORT_BUILDER 定义管理、执行、导出

下载权限与审计

以下内容延后 P9：生成即创建 deliverables 记录、签署矩阵集成、签署页 PDF、固化交付物（CUSTOM_REPORT）、绑定 record_hash 快照、最终版发布。P8 生成的即席导出件不是交付物，无 Rev、无签署。

1.2 模板与字体
P8-OPEN-001 关闭：初始报表样式由用户单独提供 .dotx / .xltx 模板文件。P8 开发期间使用用户提供的模板作为唯一初始模板源，不再等待工艺负责人。

P8-OPEN-002 关闭：中文字体统一使用 Noto Sans CJK（思源黑体）/ Noto Serif CJK（思源宋体），嵌入 PDF。字体文件随项目仓库管理或通过 font_dir 参数指定。

P8-OPEN-004 关闭：委托条件表格式随用户提供的模板确定。

1.3 数据源与 JOIN
P8-OPEN-005 关闭：多数据源 JOIN 仅支持显式声明的关联键。关联键必须在数据源注册表中预定义，格式为 {source}.{field} = {target}.{field}，禁止按名称文本模糊 JOIN。P8 首批只开放以下 JOIN 对：

EQUIP_LIST.tag_number = PUMP_RESULTS.tag_number

EQUIP_LIST.tag_number = VESSEL_RESULTS.tag_number

EQUIP_LIST.tag_number = HEAT_RESULTS.tag_number

EQUIP_LIST.tag_number = PSV_RESULTS.tag_number

EQUIP_LIST.vendor_id = SUPPLIERS.supplier_id（需 SUPPLIERS 表有 vendor_id 列；若不存在则降级为 EQUIP_LIST.vendor = SUPPLIERS.supplier_name，WARN 级提示）

不支持的 JOIN 对返回 REPORT_BUILDER_JOIN_NOT_SUPPORTED。

1.4 P8-OPEN-006 HEAT 独立工作流
P8-OPEN-006（HEAT 报表字段对齐 39 字段 + ache_params JSONB + BASIC/DETAIL 双模板 + ADR-0028 + HTRI 兼容测试 + DETAIL 覆盖率 ≥95%）单独立项为 P8c，不并入 8.1。

1.5 测试数据 seed
P8 测试不依赖真库数据。P8a 交付前需完成：

tests/fixtures/report/ 下 10 类报表各 2–3 组 seed（管道计算书 / 泵数据表 / PSV 数据表 / 容器数据表 / 换热器规格书 / 设备一览表 / 公用工程平衡表 / 综合能耗计算书 / 委托条件表 / 管道一览表）

seed 通过 make_report_seed() fixture 注入 SQLite 测试库

Golden 文件（模板渲染后的期望输出）纳入 tests/golden/report/

二、PDF 转换技术路线
2.1 候选方案评估
方案	原理	中文支持	保真度	运行时依赖	容器友好	许可
LibreOffice headless	调用 soffice --convert-to pdf	需安装中文字体包	极高（接近 Word 导出）	系统安装 LibreOffice（~500MB）	需 unoserver 保持常驻	MPL-2.0
pydocx-pdf	解压 DOCX XML，用 fpdf2 直接渲染	需 font_dir 提供 TTF	中低（复杂排版丢失）	纯 Python，零系统依赖	极好	MIT
Aspose.Words FOSS	纯 Python DOCX→PDF	需验证	中高（宣称接近原生）	纯 Python	好	MIT
mtdxpdf / dxpdf	Rust + Skia 渲染	需验证	高（宣称保留格式）	Rust 二进制	好	开源
WeasyPrint	HTML/CSS → PDF	需 @font-face 指定 CJK	高（CSS Paged Media）	Python + Pango/Cairo	需系统库	BSD-3
ReportLab	编程式 PDF 生成	需注册 TTF	高（数据表/图表强）	Python	好	BSD-3
2.2 推荐路线：LibreOffice headless（主路径）+ pydocx-pdf（降级路径）
理由：

保真度优先。P8 正式报表（计算书、数据表、规格书）必须与用户提供的 .dotx 模板视觉一致——页眉页脚、表格边框、合并单元格、字体、页码、章节编号。LibreOffice headless 是目前唯一能可靠实现这一点的开源方案，pydocx-pdf 对复杂表格和分页的支持有限。

用户模板直接复用。用户提供的 .dotx 模板用 Word 设计，LibreOffice 对 OOXML 的兼容性是开源方案中最成熟的。填好数据的 .docx 直接交给 LibreOffice 转换即可，无需重排。

二维码叠加独立于转换引擎。PDF 生成后，用 pypdf 或 reportlab 在每页页脚叠加二维码图片和文本，与转换引擎解耦。

容器化方案成熟。通过 unoserver 保持 LibreOffice 常驻进程，避免每次冷启动 2–3 秒的开销，CPU 负载降低 50–75%，可同时转换的文档量提升 2–4 倍。

降级路径：若部署环境无法安装 LibreOffice（如极小容器、只读文件系统），降级到 pydocx-pdf + fpdf2，功能受限但可用。降级模式在配置项 REPORT_PDF_ENGINE=libreoffice|pydocx 中切换。

实施细节：

python
# app/services/report/pdf_engine.py

class PdfEngine(Protocol):
    def convert(self, docx_bytes: bytes) -> bytes: ...

class LibreOfficeEngine:
    """通过 unoserver 常驻进程转换，超时 60s"""
    def __init__(self, host: str = "localhost", port: int = 2002):
        ...
    def convert(self, docx_bytes: bytes) -> bytes:
        # HTTP POST 到 unoserver 的 /convert 端点
        ...

class PydocxEngine:
    """零依赖降级引擎"""
    def convert(self, docx_bytes: bytes) -> bytes:
        from pydocx_pdf import convert
        return convert(docx_bytes, font_dir="/app/fonts")
性能预算：简单计算书（单设备，2–5 页）目标 ≤5s（含填模板、转 PDF、二维码、审计）；复杂报表（设备一览表，50–200 行）目标 ≤15s。LibreOffice 常驻进程下，单文档转换约 1–3s；pydocx-pdf 约 0.5–2s。

三、模板自定义机制
用户提供的 .dotx / .xltx 是初始模板。系统必须支持在不改代码的前提下，让非开发人员（工艺负责人、系统管理员）自定义报表样式。

3.1 三层模板模型
层级	载体	谁维护	变更方式
L1 模板文件	.dotx / .xltx 上传到 CONFIG CATEGORY_4	系统管理员	上传新版本，版本号递增
L2 占位符映射	模板中的 {{...}} 占位符 ↔ 数据源字段的绑定关系	工艺负责人（通过 UI）	在模板管理界面拖拽/选择字段绑定
L3 填充规则	循环、条件、格式化规则	工艺负责人	在占位符编辑器中配置
3.2 占位符 DSL
基于 docxtpl（Jinja2 in DOCX），占位符语法与 SPEC 附录 4.1 兼容并扩展：

text
{{Scalar.Field}}                          # 标量替换
{{#table_rows}} ... {{/table_rows}}       # 表格行循环（docxtpl 用 {%tr for ... %}）
{{#if condition}} ... {{/if}}              # 条件块
{{@image:field_name}}                     # 图片插入
{{@qr:record_hash}}                       # 二维码占位
{{#dynamic_columns}} ... {{/dynamic_columns}}  # 动态列（签署页矩阵）
docxtpl 支持 {%tr for item in items %} 循环表格行、{%tc for header in headers %} 动态列、{% cellbg var %} 动态背景色、{% colspan var %} 跨列合并。

3.3 占位符解析与绑定
P8 需实现：

占位符扫描：上传 .dotx 后，解析 document.xml，提取所有 {{...}} 和 {%...%}，生成占位符清单。

自动绑定：按占位符命名规则（{{PipingResults.LineNo}}）自动匹配数据源字段。

手动绑定 UI：占位符清单与数据源字段树并排展示，拖拽绑定。

校验：保存前校验所有占位符已绑定、类型匹配（数字字段不能绑到文本占位符）。

3.4 Excel 模板自定义
Excel 模板用 openpyxl 加载 .xltx，遍历单元格查找 {{...}} 占位符并替换。复杂表格（动态行）通过 openpyxl-templates 扩展或自定义行插入逻辑实现。openpyxl 加载模板后另存为 .xlsx，再用 LibreOffice headless 转 PDF（如果用户需要 PDF 输出）。

3.5 模板版本管理
每次上传新模板创建 TemplateFile 新记录，template_version 递增。

生成报表时记录使用的 template_version。

旧模板不删除，保留历史生成能力。

模板与数据源字段的绑定关系存为 JSON，随模板版本冻结。

四、修订后的 P8 任务分解
P8a REPORT 核心（3–4 周）
目标：完成正式报表的生成、转换、二维码、假设页、异步任务、文件存储、下载权限、审计。不涉及交付物写面。

#	任务	产出	验收
a1	模板管理集成	从 CONFIG 获取 .dotx/.xltx；占位符扫描 API；占位符绑定 CRUD	上传模板 → 扫描占位符 → 绑定字段 → 保存绑定
a2	Word 填充引擎	docxtpl 封装；标量/循环/条件/图片/动态列渲染	10 类报表各 1 组 Golden 样例通过
a3	Excel 填充引擎	openpyxl 封装；占位符替换；动态行插入	设备一览表/公用工程平衡表 Golden 通过
a4	PDF 转换引擎	LibreOffice headless（unoserver）+ pydocx-pdf 降级；中文字体嵌入	转换保真度 ≥95%（与 Word 导出目视比对）；降级模式可用
a5	二维码嵌入	pypdf 叠加二维码 + 文本到每页页脚；二维码指向 /api/v1/report/verify/{report_id}	扫描二维码 → 打开验证 URL → 显示哈希比对结果
a6	假设数据声明页	触发条件：存在 ASSUMED 或 NOT_STARTED 输入项 → 插入声明页；受影响字段橙色三角标记	有假设 → 自动插入；无假设 → 不插入；标记正确
a7	异步生成任务	ARQ 任务；状态查询端点；失败重试（max_tries=3）；错误日志	任务提交 → 轮询状态 → 完成/失败；失败可重试
a8	文件存储	内容哈希命名（{sha256[:16]}.pdf）；DB 元数据（report_files 表）；只读	重复生成相同内容 → 同一文件；下载权限校验
a9	下载与权限	下载端点带项目角色校验；短期签名 URL 或 Bearer 校验	无权限用户 403；有权限用户 200
a10	审计	生成/下载/失败均写 audit_logs（REPORT_GENERATED / REPORT_DOWNLOADED / REPORT_FAILED + ip + report_id）	审计行完整；失败也记录
a11	测试 seed	10 类报表各 2–3 组 seed fixture	make_report_seed() 可复用
a12	性能基准	简单报表 ≤5s；复杂报表 ≤15s	pytest-benchmark 记录；CI 阈值告警
P8b REPORT_BUILDER 核心（3–4 周）
#	任务	产出	验收
b1	数据源注册表	13 个数据源的字段清单、类型、权限、项目范围过滤	GET /datasources 返回完整字段树
b2	报表定义 CRUD	ReportDefinitions 模型；创建/读取/更新/删除；DRAFT 状态	CRUD 正常；仅创建人可见 DRAFT
b3	版本与审批	发布审批流；发布后按 SharedWith 可见；修改自动创建新版本	发布 → 他人可见；修改 → 新版本
b4	字段选择器后端	字段树 API；别名设置；排序；显示/隐藏	前端可获取字段树并保存选择
b5	过滤条件引擎	支持 SPEC 全部 16 个操作符；AND/OR 嵌套；参数化查询	每个操作符 1 条测试；注入尝试返回空结果而非报错
b6	JOIN 引擎	显式关联键；支持 1.3 节定义的 JOIN 对	5 对 JOIN 各 1 条测试；不支持的对返回明确错误
b7	执行引擎	构建 SQL（参数化）；执行；返回前 N 行；临时调整过滤条件（不修改定义）	10000 行 ≤10s；条件快照写入审计
b8	导出	Excel / CSV / PDF 导出；即席导出叠加“非发布件”时间戳水印；DEMO 水印；定义数量限 3（DEMO）	水印可见；DEMO 限制生效
b9	审计	每次执行写 report_execution_logs（执行人、时间、定义版本、条件快照、行数）	审计行完整
b10	前端：定义编辑器	左侧数据源字段树 / 中间已选字段 / 右侧过滤条件构建器 / 底部预览	拖拽排序；别名编辑；条件嵌套
b11	前端：执行面板	选择已发布定义；条件摘要；执行；导出	执行结果表格展示；导出文件可下载
b12	前端：管理列表	定义名称、版本、状态、创建人、共享范围	列表可筛选、可排序
P8c HEAT DETAIL + 多源 JOIN 深化 + 模板自定义 UI（2–3 周）
#	任务	产出
c1	HEAT 字段映射	heat_results 39 字段 + ache_params JSONB → HEAT_EXCEL 数据源
c2	BASIC/DETAIL 双模板	detail_level=BASIC 用 9 字段简化报表；DETAIL 用 39 字段 + HTRI 模板源
c3	ADR-0028	HEAT 报表双 detail_level 模板裁决记录
c4	HTRI 兼容测试	121-A-101.xls + 131-E-102-EOR.xls 字段覆盖比对
c5	覆盖率报告	DETAIL 字段覆盖率自动计算，目标 ≥95%
c6	模板自定义 UI 深化	占位符可视化绑定编辑器；拖拽式占位符插入；实时预览
c7	多源 JOIN 扩展	按需开放更多 JOIN 对（需先定义关联键）
五、依赖与风险
依赖	状态	风险	缓解
用户提供初始模板	待用户提供	P8a 阻塞	用户提供前先用 SPEC 附录 4.1 的占位符示例造 dummy 模板推进开发
LibreOffice 容器安装	待验证	镜像体积 + 中文字体包	用 python:3.12-slim + apt install libreoffice-writer libreoffice-calc fonts-noto-cjk；或用 unoserver 官方镜像
Noto CJK 字体	待确认	字体缺失 → PDF 中文乱码	字体文件随项目仓库管理，通过 font_dir 指定
TODO-016 ARQ 失败路径	未做	异步生成失败无重试	P8a 内补 max_tries=3 + DLQ 测试
TODO-032 真库测试文件	27 个未迁	P8 测试打真库	P8a 内同步迁移 report 相关测试到 SQLite fixture
TODO-026 9 张计算表 JSONB	未展开	字段树无平铺字段	P8b 字段树先暴露 input_json 下的已知键；TODO-026 完成后自动获得平铺字段
TODO-039/041 前端契约	逾期	前端类型与 API 不一致	P8b 前端开工前强制完成 types/* → ./api 迁移
P9 写面	未做	固化交付物/签署页阻塞	已裁决延后 P9，P8 不做
六、验收标准（P8 完成定义）
报表生成正确性：10 类报表各至少 2 组 Golden 样例通过；占位符全部正确替换；表格循环行数正确；条件块按数据正确显示/隐藏。

PDF 转换保真度：与 LibreOffice 直接导出的 PDF 目视比对无差异；中文字体正确嵌入（pdffonts 确认 Noto CJK embedded）。

二维码：扫描可打开验证 URL；哈希与 DB 中 record_hash 一致；篡改后验证失败。

假设数据声明页：触发条件正确；橙色三角标记正确；签署约束（延后 P9 的勾选逻辑不计入 P8 验收）。

异步生成：任务提交 → 状态查询 → 完成/失败；失败重试 3 次；审计完整。

REPORT_BUILDER：定义 CRUD / 发布审批 / 字段选择 / 16 操作符 / 5 对 JOIN / 执行导出 / 审计完整。

性能：简单 ≤5s；复杂 ≤15s；10000 行 ≤10s。

安全：下载权限负例通过；二维码验证端点限流；参数化查询无注入。

模板版本：模板不匹配返回 STREAM_TEMPLATE_VERSION_MISMATCH（复用 TODO-034 错误码）。

前端：定义编辑器可用；执行面板可用；管理列表可用。

七、工作量估算
阶段	内容	估算
P0 裁决与冻结	模板/字体/JOIN/写面裁决；seed 准备	0.5 周
P8a REPORT 核心	a1–a12	3–4 周
P8b BUILDER 核心	b1–b12	3–4 周
P8c HEAT + 深化	c1–c7	2–3 周
合计		8.5–11.5 周
单人开发约 2–2.5 个月。若拆为两人并行（P8a + P8b 各一人），约 4–5 周，P8c 在后端合流后启动。

八、与 TODO 清单的联动
TODO	P8 动作
TODO-016 ARQ 失败注入	P8a 内补
TODO-026 9 张计算表平铺字段	P8b 字段树先暴露 JSONB 已知键；TODO-026 完成后自动升级
TODO-032 真库测试迁移	P8a 内同步迁移 report 相关测试
TODO-034 Excel 模板版本	P8 复用 STREAM_TEMPLATE_VERSION_MISMATCH 错误码
TODO-039/041 前端契约	P8b 前端开工前强制完成
TODO-044 QA Gate 项目化	P8 每批交付前跑 .gstack/qa-reports/ 闸门
九、关键设计决策记录（待补 ADR）
ADR	决策	状态
ADR-P8-001	PDF 转换引擎选 LibreOffice headless（unoserver）+ pydocx-pdf 降级	待正式化
ADR-P8-002	占位符 DSL 基于 docxtpl/Jinja2，扩展 @qr: 和 @image:	待正式化
ADR-P8-003	交付物写面延后 P9，P8 只交付即席报表	待正式化
ADR-0028	HEAT 双 detail_level 模板裁决	SPEC 已预留编号，待起草
