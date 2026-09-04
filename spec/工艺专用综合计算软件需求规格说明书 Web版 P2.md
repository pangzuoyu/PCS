
P2 CONFIG配置中枢开发规格说明书
文件标识	PCS-REQ-2026-002-SPEC-P2
当前版本	V1.4
发布日期	2026-08-27（V1.2 修订 2026-08-29；V1.3 修订 2026-09-03，对齐本体论 V1.6 §2.3；V1.4 修订 2026-09-03，incorporate SUP-008 V1.1 + SUP-010 V1.1：CONFIG CATEGORY_3 新增折标煤系数组 + CATEGORY_4 描述扩展 DETAIL 模板与 HTRI 解析模板）
编制部门	工艺部 / 信息化联合项目组
适用对象	内部开发团队（后端/前端/测试/数据库）
关联文档	PCS-REQ-2026-002 V2.2、SUP-001 §3.2.17、SUP-002 §3.2.19、SUP-003~007、SUP-008 V1.1、SUP-010 V1.1、SPEC-P0、SPEC-P1、SPEC-P5、SPEC-P7、SPEC-P8、**PCS 本体论与语义关系研究说明（V1.6）§2.3**
第一部分：引言
1.1 目的
本文档定义P2阶段（CONFIG配置中枢）的完整需求规格，明确公式管理、经验系数管理、模板管理、标准数据库管理、复用设备库管理和项目模板管理六大类配置资产的详细功能需求、审批流程、版本规则和调用方式。

1.2 文档范围
包含：

配置资产基础框架（ConfigAssets + ConfigVersions）

公式管理（CATEGORY_2）——公式存储、解析、热更新

经验系数管理（CATEGORY_3）

报表与导入模板管理（CATEGORY_4）

标准数据库管理（CATEGORY_5）——含管道等级库

复用设备库管理（CATEGORY_6）

项目模板管理（CATEGORY_1）

配置审批流程

不包含：

各计算模块的具体公式实现（P4–P6阶段）

报表生成引擎（P8阶段）

EQUIP_LIB的检索推荐前端（P7阶段）

1.3 定义、缩略语和术语
术语/缩写	定义
CONFIG	配置管理子系统，统一管理公式、系数、模板、标准库
配置资产	需要版本管理和审批的配置数据，分六类
热更新	新版本配置生效后无需重启服务
CATEGORY_1~6	六类配置资产：项目模板、计算公式、经验系数、报表模板、标准数据库、复用设备库
双重审批	公式修改需工艺负责人+系统管理员双重审批
SymPy	Python符号计算库，用于公式解析
受限执行	通过AST白名单限制公式执行环境
Golden Test	固定输入对比固定输出的基准测试
1.4 参考文献
SUP-001 §3.2.17（模板与配置管理子系统）

SUP-002 §3.2.19（Python计算引擎规范）

SUP-003 §6（CONFIG扩展）

SPEC-P0（数据库Schema）

SPEC-P1（状态机/版本管理）

1.5 文档概述
本文档共四个部分。第一部分说明目的、范围和术语。第二部分描述CONFIG子系统的定位和约束。第三部分详细定义六类配置资产的功能需求和审批流程。第四部分为附录。

第二部分：综合描述
2.1 产品前景
CONFIG子系统是系统的"大脑"和"知识库"。它不参与日常项目的具体计算，而是为其他所有子系统提供经过审批的配置数据。通过CONFIG，公司将计算公式、经验系数、模板文件和标准数据库从个人Excel表中沉淀为可控、可追溯、版本化的企业级知识资产。

核心价值：

知识资产化：核心计算公式和工程经验从个人知识转变为公司资产

变更可控：任何配置变更必须走审批流程，全程留痕

版本可追溯：任何历史计算记录都能追溯到其使用的公式版本

热更新：新配置生效无需重启服务，用户下次计算自动使用最新版本

2.2 产品功能
功能模块	核心能力
配置资产框架	统一CRUD、版本管理、审批流、状态管理
公式管理	公式编辑器、SymPy解析、单元测试运行、热更新
经验系数管理	条件分行表格编辑、批量修改
模板管理	文件上传、占位符解析、版本替换
标准数据库	Excel批量导入、数据编辑、来源标注
管道等级库	公司级/项目级混合管理
复用设备库	设备沉淀、标准化信息补全
项目模板	输入清单模板定义、默认配置
2.3 用户类和特征
用户类	特征	CONFIG相关权限
系统管理员	系统维护，不参与工程签署	编辑公式、导入标准库、管理模板
工艺负责人	工艺专业负责人	编辑公式/系数/模板、提交沉淀申请
数据管理员	负责标准数据维护	批量导入标准数据库
审核角色	CONFIG专属审批	审批配置修改（审核级）
审定角色	CONFIG专属审批	审批配置修改（审定级）
设计/校核（普通用户）	使用配置数据进行计算	仅查看已发布的配置
2.4 运行环境
同SPEC-P0 §2.4。

2.5 设计和实现上的限制
公式安全约束：公式表达式仅允许白名单函数，禁止import、文件读写、网络访问。

双重审批：公式修改必须经工艺负责人+系统管理员双重审批。

版本不可变：已发布版本不可修改，变更必须创建新版本。

热更新：配置新版本发布后，计算引擎下次调用自动使用最新版本。

缓存策略：前端可缓存配置数据，但版本号变化时强制刷新。

审计留痕：所有配置修改、审批、发布操作记录审计日志，保留≥10年。

2.6 假设和依赖
依赖P1：状态机和版本管理框架已就绪。

依赖P0：ConfigAssets、ConfigVersions、FormulaDefinitions等表已创建。

假设：SymPy可满足所有当前公式的解析需求。

假设：公司级管道等级库初始数据可由工艺负责人提供。

第三部分：具体需求
3.1 外部接口需求
3.1.1 用户界面
界面	规格
配置资产管理列表	按六类资产分类展示，支持筛选、搜索、状态过滤
公式编辑器	代码编辑器风格，语法高亮，参数自动补全，实时预览计算结果
系数表格编辑器	表格编辑，支持条件分行和批量修改
模板文件管理	文件上传/替换，占位符自动解析和缺失映射提示
标准数据管理	Excel导入向导，数据预览，来源标注
管道等级管理	等级列表、详情编辑、项目分配
复用设备库管理	设备录入/编辑、沉淀审批列表
配置审批面板	待审批列表、版本对比、审批意见
版本历史	版本时间线、diff视图（公式数学表达式diff/表格行列diff）
3.1.2 软件接口
接口组	端点	说明
配置资产通用	GET /api/v1/config/assets?category=	列出配置资产
POST /api/v1/config/assets	创建配置资产
GET /api/v1/config/assets/{asset_id}	获取详情
GET /api/v1/config/assets/{asset_id}/versions	版本历史
GET /api/v1/config/assets/{asset_id}/versions/{version}	获取指定版本
POST /api/v1/config/assets/{asset_id}/versions/{version}/approve	审批
公式管理	POST /api/v1/config/formulas/{formula_id}/test	执行单元测试
POST /api/v1/config/formulas/{formula_id}/preview	预览计算结果
配置调用	GET /api/v1/config/effective/{asset_id}	获取当前有效版本
GET /api/v1/config/effective?category=CATEGORY_2&module=PIPE	按模块获取公式
管道等级	GET /api/v1/pipe-classes	公司级等级列表
GET /api/v1/pipe-classes/{class_id}	等级详情
POST /api/v1/pipe-classes	新建等级
PUT /api/v1/pipe-classes/{class_id}	修改等级
GET /api/v1/projects/{project_id}/pipe-classes	项目级等级列表
复用设备	GET /api/v1/equip-lib/search?params=	检索设备
POST /api/v1/equip-lib/settle	沉淀申请
3.2 功能需求
3.2.1 配置资产基础框架
需求编号：P2-CFG-001

功能描述：实现六类配置资产的统一CRUD、版本管理和审批流。

资产类别：

类别	标识	说明
项目模板	CATEGORY_1	项目创建向导模板
计算公式	CATEGORY_2	核心算法公式
经验系数	CATEGORY_3	工程经验值
报表模板	CATEGORY_4	Word/Excel模板
标准数据库	CATEGORY_5	物性/管道等级/材料数据
复用设备库	CATEGORY_6	标准化设备数据
版本规则：遵循V主.次.修订统一规则。修改已发布版本时主版本号+1（公式）或按变更类型递增。

审批流程：

资产类别	提交人	审核	审定
CATEGORY_1	工艺负责人	审核角色	审定角色
CATEGORY_2	系统管理员/工艺负责人	工艺负责人+系统管理员（双重）	—
CATEGORY_3	工艺负责人	审核角色	—
CATEGORY_4	系统管理员/工艺负责人	工艺负责人	—
CATEGORY_5	数据管理员	工艺负责人	—
CATEGORY_6	工艺负责人	审核角色	—
验收标准：

六类资产CRUD正常

版本规则正确

审批流程按角色执行

所有操作记录审计日志

3.2.2 公式管理（CATEGORY_2）
需求编号：P2-FRM-001

功能描述：实现公式的存储、解析、测试和热更新。

公式存储结构（FormulaDefinitions表Content_JSON）：

json
{
  "name": "管道压降_Darcy_Weisbach",
  "module": "PIPE",
  "expression": "f * L / D * rho * v**2 / 2",
  "parameters": [
    {"name": "f", "unit": "dimensionless", "description": "达西摩擦因子"},
    {"name": "L", "unit": "m", "description": "管长"},
    {"name": "D", "unit": "m", "description": "管道内径"},
    {"name": "rho", "unit": "kg/m3", "description": "密度"},
    {"name": "v", "unit": "m/s", "description": "流速"}
  ],
  "stdSource": "Darcy-Weisbach Equation",
  "unitTests": [
    {"inputs": {"f": 0.02, "L": 100, "D": 0.1, "rho": 800, "v": 2},
     "expected": 16000, "tolerance": 0.01}
  ]
}
公式热更新流程：

text
CONFIG审批通过新版本公式
    → 后端加载公式表达式
    → SymPy解析为AST（语法校验）
    → 自动执行单元测试用例
    → 全部通过后新公式生效
    → 计算引擎下次调用使用新版本
    → DataLineage记录FormulaVersion
安全约束：

约束	规格
白名单函数	sin, cos, tan, exp, log, sqrt, pow, abs, min, max
禁止操作	import, open, eval, exec, import
执行环境	受限AST执行，__builtins__白名单
审批要求	双重审批
验收标准：

公式存储和检索正常

SymPy解析正确

单元测试自动执行

非法公式被拒绝

热更新生效（无需重启）

3.2.2a 公式前置条件 preconditions（V1.3，对齐本体论 V1.6 §2.3）
需求编号：P2-FORMULA-PRECOND-001

功能描述：在 `formula_definitions.content_json` 中新增 `preconditions` 数组，用于在公式执行前对输入/参数做声明式前置检查。

存储格式：

```json
{
  "expression": "...",
  "parameters": [...],
  "preconditions": [
    {
      "id": "PRECOND-001",
      "description": "CS材料温度上限",
      "condition": "input.material == 'CS' AND input.design_temp <= params.cs_max_temp",
      "variables": [
        {"name": "input.material", "source": "CALLER_INPUT", "required": true},
        {"name": "input.design_temp", "source": "CALLER_INPUT", "required": true},
        {"name": "params.cs_max_temp", "source": "FORMULA_PARAM", "required": true, "trace": "CoefficientTables:CT-001"}
      ],
      "on_violation": "REJECT"
    }
  ]
}
```

治理条款（V1.6 §2.3 定稿）：

条款	说明
变量来源白名单	仅允许 `input.*`（调用方输入）、`params.*`（公式参数）、`result`（仅 result >= 0 类后置检查）；禁止 `context.*`（不访问 DB）
常量溯源	condition 中的数值常量（如 425）必须来自 `params.*`，且 `params.*` 可溯源至 `CoefficientTables`（系数库），不得硬编码在 condition 字符串中
求值顺序	`input.*` 和 `params.*` 在计算前检查（pre）；`result` 在计算后检查（post）
违反策略	V1 冻结为 REJECT-only（WARN 作为未来扩展，V1 不支持）
表达式语言	condition 必须复用 FormulaEngine 的受限 AST 解析器——不引入第二套表达式语言，不增加新的安全面
表达力边界	支持：数值比较（<=, >=, ==, !=）、枚举判断、范围判断（BETWEEN）、AND/OR 组合；不支持：跨字段算术约束、循环/迭代、DB 查询
跨字段约束 fallback	若 P2 Sprint 1.2 发现跨字段约束是刚需：先记录需求到需求文档；P2 期间调用方临时检查代码须标注 `@legacy-P4`；P4 Task 0 启动守卫函数落地

验收标准：

`preconditions` 数组随公式一起版本化、审批、Unit Test 回归

受限 AST 复用——preconditions 与 expression 共用同一解析器，无新安全面

违反时抛 `PcsError`（REJECT-only）

`CoefficientTables` 溯源校验：所有 `params.*` 必须能溯源到系数库

3.2.3 经验系数管理（CATEGORY_3）
需求编号：P2-COEF-001

功能描述：实现工程经验系数的表格化管理和批量修改。

系数类型（初始）：

系数名称	适用模块	数据来源
Souders-Brown K因子	VESSEL	附录F
推荐流速表	PIPE	HG/T 20570.6-95
泵功率安全系数	PUMP	API 610
管道粗糙度默认值	PIPE	工程经验
换热器重量估算系数	HEAT	工程经验
管件阻力系数映射表	PIPE	fluids.fittings映射
炼油物性关联式（V1.2，ADR-0019）	PETROLEUM 数据模式	Riazi-Daubert 等：馏程/比重→分子量/临界参数/粘度/蒸汽压
物性估算参数（V1.2，ADR-0019）	手动创建物流	估算方法选择、默认基团贡献法、estimated 标记规则
虚拟组分切割规则（V1.2，ADR-0019）	PETROLEUM 数据模式	自动切割沸程宽度（默认 25°C）、馏程边界约定
表格编辑规格：支持按条件分行（如"立式分离器 + 无除沫器 → K=0.03~0.06"），单次可批量修改多个系数。

验收标准：

系数表CRUD正常

批量修改功能可用

版本管理正确

3.2.4 模板文件管理（CATEGORY_4）
需求编号：P2-TPL-001

功能描述：实现报表模板和导入模板的文件管理。

支持格式：.dotx（Word模板）、.xltx（Excel模板）

占位符解析：模板上传后自动解析占位符，与数据字典字段映射，提示缺失映射。

验收标准：

模板文件上传/替换正常

占位符自动解析

版本替换生效

3.2.5 标准数据库管理（CATEGORY_5）
需求编号：P2-STD-001

功能描述：实现物性数据、材料数据、管道等级的标准库管理。

覆盖范围：

chemicals库物性数据（纯物质）

CoolProp高精度物性（水蒸气等）

材料许用应力表（ASME B31.3 Table A-1）

介质毒性/爆炸极限数据

管道等级库（PipeClasses）

管道等级库（重点）：

字段组	字段	说明
基本信息	ClassID, ClassName, MaterialStandard	等级标识
腐蚀	CorrosionAllowance	腐蚀裕量mm
设计条件	DesignPressure, DesignTemperature	等级设计上限
许用应力	AllowableStressTable	引用COMMON，可覆写
DN系列	DNSeries_JSON	{min: 15, max: 600}
Sch系列	SchSeries_JSON	各DN对应Sch
法兰管件	FlangeClass, FittingType, BranchTable	连接标准
版本	Source, Version, Status	公司级/项目级
Excel批量导入规格：提供标准化模板下载，支持批量导入，附来源说明。

验收标准：

Excel导入正常

管道等级库CRUD正常

项目级等级分配正常

已用等级不可删除（仅可作废）

3.2.6 复用设备库管理（CATEGORY_6）
需求编号：P2-EQL-001

功能描述：实现复用设备的沉淀申请、审批和标准化管理。

沉淀流程：

工艺负责人从EQUIP_LIST提交沉淀申请

补全标准化信息（标准图号、适用条件范围、材质、重量、关键尺寸、原项目位号）

审核审批

设备入库生效

验收标准：

沉淀申请流程正常

标准化信息校验

审批后入库

3.2.7 项目模板管理（CATEGORY_1）
需求编号：P2-PJT-001

功能描述：实现项目创建向导模板的定义和管理。

模板内容：

默认输入清单（InputChecklist模板）

默认单位制

默认模块启用状态

默认管道等级列表

BEDD_JSON默认结构

版本序列配置 version_sequence_config（SUP-004：Alpha/数字起始、跳过Alpha、清理Alpha、特殊后缀、可用版本目的列表）

签署矩阵绑定（SUP-005：模块/文档类型/版本目的→矩阵；项目级覆写需双重审批）

记录批准深度 record_approval_config（SUP-007/ADR-0012：按记录类型 1~4 级步骤，可含客户代录步骤）

物流校对深度 stream_approval_config（SUP-007/ADR-0014：1~2 级）

编号模板引用 numbering_template（SUP-007/ADR-0006：doc_no 段结构/序号scope/类型映射；内置 3~5 套标准模板）

客户批准代录配置 customer_approval_config（SUP-007/ADR-0007：允许代录角色、附件要求）

撤销批准角色（SUP-007/ADR-0010：CHANGED 撤销由哪一级角色批准）

签署矩阵模板库含 CHANGE_NOTICE_3_LEVEL（变更单默认 3 级矩阵）

验收标准：

模板创建/编辑正常

发布后新项目创建时默认使用最新版本

上述签署/版本/编号/批准深度配置随模板正确加载并生效

3.3 非功能需求
3.3.1 性能需求
指标	要求
配置资产列表查询	≤500ms
公式测试执行（单用例）	≤1秒
管道等级查询	≤300ms
有效版本获取	≤200ms（带缓存）
3.3.2 安全性需求
指标	要求
公式执行环境	完全沙箱化
审批流程	强制走审批，不可绕过
审计日志	所有修改/审批/发布操作留痕
版本不可变	已发布版本不可修改
3.4 数据需求
P2阶段使用P0创建的以下表：

config_assets（资产主表）

config_versions（版本表）

config_approvals（审批记录）

formula_definitions（公式定义）

coefficient_tables（系数表）

template_files（模板文件）

project_templates（项目模板）

pipe_classes（管道等级）

project_pipe_classes（项目-等级关联）

第四部分：附录
4.1 配置资产审批流图
text
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   创建/修改   │────►│   提交审批    │────►│   审核通过    │
│  (DRAFT)     │     │  (PENDING)   │     │  (APPROVED)  │
└──────────────┘     └──────┬───────┘     └──────┬───────┘
      ▲                     │                    │
      │                     │ 驳回                │ 发布
      │                     ▼                    ▼
      │              ┌──────────────┐     ┌──────────────┐
      │              │   REJECTED   │     │  PUBLISHED   │
      │              │  (退回修改)   │     │  (当前有效)   │
      │              └──────────────┘     └──────────────┘
      │                                           │
      │                                    修改已发布版本
      │                                           │
      └───────────────────────────────────────────┘
                    (自动创建新版本)
4.2 待确定问题列表
编号	问题	影响	建议解决方案	状态
P2-OPEN-001	公司级管道等级库初始数据由谁提供？	P3阶段PIPE计算数据源	用户提供 Worley BEP Template 4.3 Piping Material Classification Rev 0（2026-09-05）；已提取 6 等级（A1B/A1E/A2B/G1E/A1F/A2F）为种子 pcs-backend/app/seeds/pipe_classes_bep_rev0.{json,xlsx}，Sprint 1.9 Task 1.9.6 导入	已确认
P2-OPEN-002	公式版本升级后，历史计算结果是否自动标记？	变更影响分析	是，P1阶段已实现自动标记	已确认
P2-OPEN-003	配置审批是否需要会签（多人同时审批）？	审批流程设计	P2阶段暂不支持会签，单人审批即可	已确认
P2-OPEN-004	[preconditions 范围核对] 详见 PCS 本体论 V1.6 §2.3：是否需要引入跨字段算术约束（如 design_press - operating_press >= 0.5）？V1.6 §2.3 表达力边界声明"暂不支持跨字段约束"。若 P2 Sprint 1.2 实施期间发现刚需，按 fallback：① 记录需求到需求文档（含路径/约束/示例）；② P2 期间调用方临时检查代码须标注 `@legacy-P4`；③ P4 Task 0 启动守卫函数落地。	P2 Sprint 1.2 启动前必备	按 V1.6 §2.3 表达力边界声明核对；刚需时走 fallback 流程	待启动
P2-OPEN-005	[CONFIG 折标煤系数组 + DETAIL/HTRI 模板扩展] 详见 SUP-008 V1.1 §2.5（auxiliary_consumption 4 字段）+ SUP-010 V1.1 §3.3.4（utility_energy_summary）+ 偏差审查结论：① CATEGORY_3 经验系数管理新增"折标煤系数组"配置资产，含 2 项系数（toe_conversion_factor — 吨油当量折算系数；standard_coal_factor — 标煤折算系数），支持按燃料类型/年度调整；CONFIG 端维护入口，UTIL 端读取引用；② CATEGORY_4 报表与导入模板管理描述扩展：明确 DETAIL 设计阶段模板（如 121-A-101.xls、131-E-102-EOR.xls）作为标准模板资产入库；HTRI 输出文件解析模板（121-A-101.xls 空冷器 33 列、131-E-102-EOR.xls 管壳式 23 列）作为导入模板资产入库；模板版本号字段纳入 CONFIG 模板版本序列。建议新建 ADR-0029 记录 CATEGORY_3/4 一次性收敛裁决。验收：UTIL 折标煤计算与蜡油加氢—综合能耗.xlsx 实例偏差 ≤ 2%。	P2 CONFIG 数据模型扩展	CATEGORY_3 新增折标煤系数组；CATEGORY_4 描述扩展 + 模板资产入库；ADR-0029 起草；列入 DICT V3.9	待启动

## 版本历史

| 版本 | 日期 | 修改内容 | 编制人 |
|---|---|---|---|
| V1.0 | 2026-08-27 | 初始版本 | 联合项目组 |
| V1.1 | 2026-08-28 | incorporate SUP-004/005/007：项目模板（CATEGORY_1）扩展版本序列、签署矩阵绑定、记录批准深度、物流校对深度、编号模板、客户代录配置、撤销批准角色；文件标识改 PCS 前缀 | 联合项目组 |
| V1.2 | 2026-08-29 | incorporate ADR-0019：CONFIG（CATEGORY_3/5）新增炼油物性关联式（Riazi-Daubert 等）、物性估算参数配置、虚拟组分切割规则 | 联合项目组 |
| V1.3 | 2026-09-03 | 对齐 PCS 本体论 V1.6 §2.3：关联文档加 V1.6；新增 §3.2.2a 公式前置条件 preconditions（变量白名单 input.*/params.*/result、禁止 context.*、常量溯源 CoefficientTables、pre/post 求值顺序、REJECT-only、复用受限 AST、跨字段约束 fallback 流程）；新增 P2-OPEN-004（preconditions 跨字段约束范围核对）；本版本不修改六类配置资产框架主体需求 | 联合项目组 |
| V1.4 | 2026-09-03 | incorporate SUP-008 V1.1 + SUP-010 V1.1：关联文档加 SUP-008 V1.1 + SUP-010 V1.1；新增 P2-OPEN-005（CATEGORY_3 新增折标煤系数组 toe/standard_coal 配套 auxiliary_consumption 4 字段 + utility_energy_summary；CATEGORY_4 描述扩展 DETAIL 模板 + HTRI 解析模板；ADR-0029 起草）；主体 §3.2.2a/§3.2.3/§3.2.4/§3.2.5 不动，仅扩 CONFIG 数据模型 | 联合项目组 |

