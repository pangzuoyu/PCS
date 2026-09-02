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

依赖P7：EQUIP_LIST等数据表已填充数据。

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

