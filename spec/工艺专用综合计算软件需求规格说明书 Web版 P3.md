P3 基础数据层开发规格说明书
文件标识	PCS-REQ-2026-002-SPEC-P3
当前版本	V1.5
发布日期	2026-08-27（V1.2 修订 2026-08-29，incorporate SUP-007 + ADR-0019~0022；V1.3 修订 2026-09-03，对齐 PCS 本体论 V1.6 §2.5 / §5.3；V1.4 修订 2026-09-03，incorporate SUP-008 V1.1 + SUP-010 V1.1：SIM Excel 导入 + streams 16 字段 + viscosity_temperature_curve + 多案例支持；**V1.5 修订 2026-09-08，对齐 P2 close 现状：SUP-002 V1.4 全部落地 + PCS-SPEC-P3-SIM V1.2 已合并 ADD-001/002 + TODOS.md TODO-024~033 + 代码现状 §第五部分 实施遗漏清单**）
编制部门	工艺部 / 信息化联合项目组
适用对象	内部开发团队（后端/前端/测试/数据库）
关联文档	PCS-REQ-2026-002 V2.2 §3.2.1/§3.2.2/§3.2.10/§3.2.15、SUP-001~007、SUP-008 V1.1、SUP-010 V1.1、**PCS 本体论与语义关系研究说明（V1.6）§2.5 / §5.3、PCS-SPEC-P3-SIM V1.2（2026-09-08 已合并 ADD-001 完整字段清单 + ADD-002 校核/引用/冲突）、PCS-SPEC-P2-SUP-002 V1.4（2026-09-06 定稿，PC-1~6/SYM-1~3/FMT-1~4 全部落地）、主开发计划 V1.3、TODOS.md**
第一部分：引言
1.1 目的
本文档定义P3阶段（基础数据层）的完整需求规格，明确PMS项目基本信息、SIM工艺模拟数据、COMMON工艺常用数据库和PIPE_CLASS管道等级库四个基础数据子系统的详细功能需求、接口规范和验收标准。

1.2 文档范围
包含：

PMS：项目创建向导、BEDD数据管理、单位制联动

SIM：模拟文件解析、物流数据管理、物性补全

COMMON：物性数据库、材料数据、介质安全数据

PIPE_CLASS：管道等级库管理、项目级分配

不包含：

管道计算（P4阶段PIPE模块）

泵计算（P4阶段PUMP模块）

闪蒸计算（P4阶段FLASH模块）

设备计算（P5-P6阶段）

1.3 定义、缩略语和术语
术语/缩写	定义
BEDD	Basic Engineering Design Data，基础工程设计数据
SIM	工艺模拟数据子系统
PMS	项目基本信息子系统
COMMON	工艺常用数据库
PIPE_CLASS	管道等级库子系统
HYSYS	Aspen HYSYS流程模拟软件
物流号	模拟软件中物料流股的唯一标识
IAPWS-IF97	水蒸气性质国际标准
DN	公称直径
Sch	管壁厚度系列
1.4 参考文献
HT-REQ-2026-002 V2.2 §3.2.1-3.2.2、§3.2.10、§3.2.15

SUP-001 §3.2.15（管道等级库）

DICT-001 §3.1-3.13（BEDD/Stream/物性数据结构）

管道一览表数据字典（PipingResults表完整字段）

SPEC-P2（CONFIG配置中枢）

1.5 文档概述
本文档共四个部分。第一部分说明目的、范围和术语。第二部分描述基础数据层四个子系统的定位和关系。第三部分详细定义各子系统的功能需求。第四部分为附录。

第二部分：综合描述
2.1 产品前景
P3阶段的四个子系统构成了整个系统的"数据底座"。PMS提供项目级设计条件，SIM提供物流级工艺数据，COMMON提供物质级物性数据，PIPE_CLASS提供管道等级工程化组合数据。所有后续计算模块（P4-P6）都依赖这四个子系统提供的数据。

三层数据分离原则：

项目级（BEDD）：气象、地质、公用工程、排放限值等

物流级（Stream）：物流物性、组成、规格

物质级（Material）：纯物质固有物性

2.2 产品功能
子系统	核心功能
PMS	项目创建向导、BEDD录入/导入、单位制联动、项目复制
SIM	模拟文件解析、物流表格展示、物性补全、手动修改
COMMON	物性查询、材料许用应力、毒性/爆炸极限
PIPE_CLASS	等级定义管理、项目分配、版本管理
2.3 用户类和特征
用户类	特征	P3阶段相关需求
工艺设计人员	创建项目、导入模拟数据、查询物性	PMS/SIM日常操作
工艺负责人	管理管道等级分配	PIPE_CLASS项目级管理
数据管理员	维护COMMON数据库	物性数据导入
系统管理员	维护管道等级库（公司级）	PIPE_CLASS公司级管理
2.4 运行环境
同SPEC-P0 §2.4。

2.5 设计和实现上的限制
数据来源标记：所有数据必须标记来源类型（SIM导入/手动录入/标准库/假设/默认值/估算）。

物性数据分层：COMMON提供基础数据，PIPE_CLASS工程化组合，不得混淆。

管道等级版本：已用于计算的等级不可删除（仅可标记作废）。

单位制联动：PMS单位制切换时，所有已填数值必须实时转换并提示转换基准。

BEDD动态结构：BEDD_JSON采用灵活JSON结构，支持项目间差异。

2.6 假设和依赖
依赖P2：CONFIG中的项目模板、管道等级库（公司级）已就绪。

依赖P1：输入清单框架、工作区管理已就绪。

假设：有实际HYSYS/Aspen Plus输出文件可用于解析器测试。

假设：公司现有管道等级数据可整理为标准格式导入。

第三部分：具体需求
3.1 外部接口需求
3.1.1 用户界面
界面	规格
项目创建向导	四步：模板选择→基本信息→BEDD导入→单位制确认
BEDD数据编辑	分组Tab（气象/水文/公用工程/排放/设计寿命/安全消防/火炬/界面条件）
物流数据表格	表格展示，支持筛选/排序/手动新增/修改
模拟文件导入	文件上传向导，解析预览，确认导入
物性查询	搜索框输入物质名称/CAS号，显示物性详情
管道等级管理	等级列表、详情编辑、项目分配面板
3.1.2 软件接口
接口组	端点	说明
PMS	POST /api/v1/projects	创建项目
GET /api/v1/projects/{project_id}	获取项目详情
PUT /api/v1/projects/{project_id}	更新项目信息
PUT /api/v1/projects/{project_id}/bedd	更新BEDD数据
POST /api/v1/projects/{project_id}/copy	复制项目
SIM	POST /api/v1/projects/{project_id}/streams/import	导入模拟文件
GET /api/v1/projects/{project_id}/streams	获取物流列表
POST /api/v1/projects/{project_id}/streams	手动创建物流（V1.2：三模式向导+物性估算+虚拟组分）
PUT /api/v1/projects/{project_id}/streams/{stream_id}	修改物流（V1.2：限权+原因+影响预览）
GET /api/v1/streams/{stream_id}/state-points	状态点列表（V1.2）
POST /api/v1/streams/{stream_id}/state-points	新建状态点（T/P 变化派生新快照，V1.2）
GET /api/v1/streams/{stream_id}/chain	物流链视图（上游物流+设备→本物流，V1.2）
COMMON	GET /api/v1/common/materials/{material_id}	查询物性
GET /api/v1/common/materials/search?q=	搜索物质
GET /api/v1/common/allowable-stress?material=&temp=	查询许用应力
PIPE_CLASS	GET /api/v1/pipe-classes	公司级等级列表
GET /api/v1/projects/{project_id}/pipe-classes	项目级等级
POST /api/v1/projects/{project_id}/pipe-classes/assign	分配等级到项目
3.2 功能需求
3.2.1 PMS项目创建向导
需求编号：P3-PMS-001

功能描述：实现四步项目创建向导。

步骤详情：

步骤	内容	规格
Step 1	模板选择	从CONFIG CATEGORY_1获取可用项目模板列表，展示模板描述和默认配置摘要
Step 2	基本信息	项目编号（唯一校验）、名称、业主、建设地点、项目类型、设计阶段、单位制
Step 3	BEDD录入/导入	根据模板生成BEDD表单骨架，支持Excel导入和在线填写
Step 4	确认	展示配置摘要，确认后创建项目并自动生成输入清单
项目复制功能：

复制时自动生成新项目编号

可选择复制BEDD、物流数据、计算结果

复制后所有计算结果标记为"未重新计算"

单位制联动：

支持SI/Metric/Imperial三种

切换时所有已填数值自动转换

提示转换基准和转换公式

验收标准：

四步向导完整可用

项目模板正确加载

项目创建后自动生成输入清单

单位制切换正常转换

项目复制功能正常

3.2.2 SIM模拟文件解析
需求编号：P3-SIM-001

功能描述：实现多格式模拟文件的解析和物流数据管理。

支持格式：

格式	扩展名	解析方式
HYSYS XML	.xml	XML解析
HYSYS CSV	.csv	CSV解析
Aspen Plus报告	.inp/.txt	正则表达式
PRO/II	.txt	正则表达式
HTRI	.dat	专用解析器
解析规则：

以物流号为主键识别

自动单位转换（匹配PMS单位制）

组成归一化校核（100±0.5%）

物性缺失时调用COMMON或FLASH估算并标记

物流校对门禁（V1.1，SUP-007/ADR-0014）：导入/创建的物流初始为 DRAFT（StreamSignStatus：DRAFT/IN_APPROVAL/CHECKED/OBSOLETE），须提交校对（默认 1 级校对人，项目模板 stream_approval_config 可配 2 级）后方可被计算记录引用——校对项含来源一致性、组成归一化、单位、完整性、数值合理性；DRAFT/IN_APPROVAL/OBSOLETE 状态被引用时返回 403

CHECKED 物流的后续修改不重新校对：限权（DESIGNER+项目负责人）+ 强制修改原因 + 影响预览（展示下游波及清单后确认），状态保持 CHECKED 并触发 CIA（下游记录 STALE）

物流手动创建（V1.2，ADR-0019/0020/0022）：

与模拟导入并列，支持三种数据模式——CHEMICAL（组成+T/P+流量）、PETROLEUM（馏程/SARA 四组分/元素分析/金属含量/API + 虚拟组分：手动输入或按 25°C 沸程自动切割）、SOLID（堆积密度/粒径/休止角/真密度）。用户填关键字段后其余物性由 chemicals/thermo 自动估算并标记 estimated=true；手动创建走与导入完全相同的校对流程（DRAFT→校对→CHECKED），source_type=MANUAL_ENTRY/LAB_REPORT

状态点管理（V1.2）：一条物流按工况（NORMAL/MIN/MAX/ALTERNATE）维护多个状态点（stream_state_points），T/P 变化新建状态点、不修改原状态点；两相流须保存气液分率与气液相组成（可由 FLASH 计算填充）

设备连接（V1.2，ADR-0022）：物流是管段的标识，经过设备后物流号更换。streams 表携带 upstream_stream_id / upstream_equipment_type / upstream_equipment_id / change_type；设备计算完成后系统自动创建出口物流（source_type=DEVICE_CALCULATED，sign_status=DRAFT，需校对）

物流数据字段（完整Streams表字段）：
包括但不限于：温度、压力、质量流量、摩尔流量、体积流量、标准状态气体流量、密度、粘度、导热系数、比热容、分子量、压缩因子、汽化分率、组成（摩尔/质量/体积分率）、堆积密度、真密度、粒径、休止角、馏程、四组分分析、元素分析、金属含量、原料/产品规格。

验收标准：

各格式文件解析正确

单位转换正确

组成归一化校验

物性缺失自动标记

3.2.3 COMMON物性数据库
需求编号：P3-COM-001

功能描述：实现纯物质物性、材料数据和介质安全数据的查询和管理。

数据来源：

数据类型	来源库	说明
纯物质物性	chemicals + CoolProp	分子量、临界参数、沸点、饱和蒸气压等
高精度物性	CoolProp IAPWS-IF97	水蒸气精确物性
材料许用应力	ASME B31.3 Table A-1	按温度插值
毒性数据	内置数据库	剧毒/高毒/中毒/低毒分类
爆炸极限	内置数据库	上限/下限
查询规格：

按物质名称/CAS号/分子式搜索

按材料牌号+温度查询许用应力（支持插值）

返回结果包含数据来源标记（实验值/估算值/标准值）

验收标准：

物性查询正常

许用应力插值正确

数据来源标记完整

3.2.4 PIPE_CLASS管道等级库
需求编号：P3-PCL-001

功能描述：实现管道等级的定义管理、项目分配和版本控制。

公司级/项目级混合结构：

公司级：由管理员在CONFIG中维护

项目级：项目创建时从公司级选取，或创建项目专属等级（需审核）

等级数据结构（完整PipeClasses表字段）：
等级代码、名称、材料标准、腐蚀裕量、设计压力/温度上下限、适用介质、许用应力表引用、DN系列、Sch系列、法兰等级、管件类型、支管表、来源、版本、状态。

项目分配：

项目创建时从公司标准库选取适用等级

项目级创建需审核通过

已用于计算的等级不可删除

验收标准：

等级CRUD正常

项目分配正常

版本管理正确

引用PIPE计算正常

3.2.5 元数据驱动表单（V1.3，对齐本体论 V1.6 §2.5 / §5.3）
需求编号：P3-META-FORM-001

功能描述：P3 表单由 Pydantic Schema 驱动，不手动维护字段列表。前端从 `model_json_schema()` 获取字段定义，UI 布局由独立的 `uiSchema` 控制，不侵入业务模型。事实来源锁定 Pydantic Schema（不是 DICT Markdown）。

实施要点：

要点	说明
Pydantic Schema 覆盖	P3 开发期间，每个需要表单的 ORM 模型（streams、equipment_list、projects 等）必须有对应的 Pydantic Schema，且该 Schema 包含 `Field(description=...)` 注解
UI Schema 层预留	前端表单组件接收 `schema` + `uiSchema` 两个 props；`uiSchema` 包含字段分组、显隐联动、布局顺序；P3 设计阶段确定 `uiSchema` 格式（如 x-rjsf-* 扩展或自定义 `ui:` 字段）
条件显示策略	若涉及 `phase=='GAS'` 类条件显示：① 优先在 P3 前端组件中按业务模块硬编码（条件显示数量少、变化慢时，硬编码比配置文件更易维护）；② 条件显示数量 > 10 个时再评估是否引入声明式配置（如复用 preconditions 机制扩展 `ui_constraints`）。不做先验抽象
禁止事项	前端不得硬编码字段名列表（除非字段数 ≤ 3 且永不变化）

CI 硬性项（V1.6 §6 规则 11 / §5.3 增补）：

```
表单 ↔ Schema 静态对比 CI：
- 前端表单组件产出的 JSON Schema
- 后端 Pydantic Schema model_json_schema() 输出
必须 CI 静态对比，漂移即 fail
```

验收标准：

P3 表单字段列表与 Pydantic Schema 保持一致（CI 自动校验）

无硬编码字段名（除 ≤ 3 且永不变化的例外）

每个需表单的 ORM 模型都有对应 Pydantic Schema + `Field(description=...)` 注解

3.3 非功能需求
3.3.1 性能需求
指标	要求
项目创建（含输入清单生成）	≤3秒
HYSYS文件解析（100条物流）	≤10秒
物性查询	≤300ms
管道等级查询	≤300ms
BEDD保存	≤500ms
3.3.2 数据完整性需求
约束	要求
项目编号	全局唯一
物流名称	项目内唯一
组成归一化	100±0.5%
管道等级代码	公司内唯一
数据来源标记	所有数据必须有来源标记
物流状态约束	仅 CHECKED 物流可被计算记录引用（V1.1）
3.4 数据需求
P3阶段使用P0创建的表：

projects（含BEDD_JSON）

streams（含Composition_JSON和扩展字段）

pipe_classes

project_pipe_classes

以及P1阶段的project_input_checklist、workspaces

第四部分：附录
4.1 BEDD_JSON结构概览
text
BEDD_JSON
├── Temperature（温度）
│   ├── annualAvg（年平均）
│   ├── extremeHigh/Low（极端高/低）
│   ├── MDHT（最高设计温度）
│   └── designTemps（各设计温度）
├── Humidity（湿度）
├── Pressure（气压）
├── Wind（风）
├── Rainfall（降雨）
├── Snow（雪）
├── Evaporation（蒸发）
├── Thunderstorm（雷暴）
├── Fog（雾）
├── Sunshine（日照）
├── SolarRadiation（太阳辐射）
├── Soil（土壤）
├── Dust（粉尘）
├── Altitude（海拔）
├── Hydrogeology（水文地质）
├── Seismic（地震）
├── Utilities（公用工程）
│   ├── SteamGrades（蒸汽等级）
│   ├── WaterSystems（水系统）
│   ├── AirSystems（空气系统）
│   ├── Nitrogen（氮气）
│   ├── GasFuel（气体燃料）
│   ├── FuelOil（燃料油）
│   ├── Hydrogen（氢气）
│   ├── Chemicals（化学品）
│   ├── HotOil（导热油）
│   ├── Condensate（凝液）
│   └── Electrical（电气）
├── EmissionLimits（排放限值）
├── DesignCriteria（设计准则）
├── Safety（安全消防）
├── Flare（火炬）
└── BatteryLimits（界面条件）
4.2 待确定问题列表
编号	问题	影响	建议解决方案	状态
P3-OPEN-001	HYSYS XML格式的具体版本？	解析器兼容性	收集实际项目中的多种HYSYS版本文件进行测试	待确认
P3-OPEN-002	公司现有管道等级数据格式？	PIPE_CLASS初始数据导入	需工艺负责人提供现有等级表	待确认
P3-OPEN-003	BEDD中是否有新增的特定业主格式要求？	BEDD结构	基于DICT-001定义的结构，后续可按需扩展JSON字段	已确认
P3-OPEN-004	[Pydantic Schema 覆盖核对] 详见 PCS 本体论 V1.6 §5.3：P3 开发期间需确认每个需表单的 ORM 模型（streams、equipment_list、projects 等）均有对应 Pydantic Schema，且包含 `Field(description=...)` 注解。需同步确定 `uiSchema` 格式（x-rjsf-* 扩展 or 自定义 `ui:` 字段）。表单 ↔ Pydantic Schema 静态对比 CI 漂移即 fail（V1.6 §6 规则 11）。	P3 开发期间必备	逐模型核对 + 配置前端 CI	待启动
P3-OPEN-005	[SIM Excel 导入] 详见 SUP-008 V1.1 §3.1：P3 SIM 增加 Excel 导入能力（流程序列：上传 → Sheet 识别 → 列映射确认 → 预览 → 写入 DRAFT → 走 StreamSignStatus 门禁）。覆盖 streams / 摩尔组成 / 管径核算 / 机泵选型 / 能耗 5 类 Sheet；列映射模板库支持用户自定义；新增 API 端点 6 个。streams 表扩展 16 字段（surface_tension / api_gravity / critical_temp / critical_press / enthalpy / entropy / vapor_* / actual_vol_flow）+ import_source_type 枚举（SIM/MANUAL/EXCEL/LAB）+ import_original_row JSONB。验收：30 条物流 ≤ 5 秒导入 + 物性字段完整度 ≥ 90% + 组成归一化 100±0.5%。	P3 开发期间必备	按 SUP-008 §3.1.2 解析策略 + §3.1.4 映射配置实现	待启动
P3-OPEN-006	[viscosity_temperature_curve] 详见 SUP-008 V1.1 §8.3.7：streams 表新增 `viscosity_temperature_curve` JSONB 字段，存储原料油常压下温度-粘度对应表（如 `{"50": 213.2, "80": 56.8, "100": 28.4, ...}`），用于蜡油加氢实例原料油粘度。	P3 数据模型迁移	新增字段 nullable；现有物流历史数据不受影响	待启动
P3-OPEN-007	[多案例 stream_case_type] 详见 SUP-008 V1.1 §2.1：streams 表新增 `case_type` 字段（NORMAL/END_OF_RUN/START_OF_RUN/TURN_DOWN），Excel 包含"末期"工况（摩尔组成0(末期)）需多案例切换支持。	P3 数据模型迁移 + SIM 切换功能	按枚举值实现 SIM 案例切换 UI	待启动
P3-OPEN-008	[PMS 项目管理服务/API 全部 0%] 详见 §第五部分 5.1：P3 §3.1.2 PMS 5 端点（POST/GET/PUT /projects、PUT /bedd、POST /copy）+ §3.2.1 项目创建向导（4 步）+ §3.2.1 项目复制功能 + §3.2.1 单位制联动（SI/Metric/Imperial 实时转换）**后端实现率 0%**。Project 模型字段（含 bedd_json）已就位；缺 `app/services/project_service.py` + `app/api/v1/projects.py` + `app/schemas/project.py`。	P3 启动必备	按 §3.1.2 + §3.2.1 落地；Pydantic Schema 同步覆盖（P3-OPEN-004）	待启动
P3-OPEN-009	[SIM 物流管理服务/API 全部 0%] 详见 §第五部分 5.2：P3 §3.1.2 SIM 9 端点（import/streams×3/state-points×2/chain/composition）+ §3.2.2 三模式手动创建（CHEMICAL/PETROLEUM/SOLID）+ §3.2.2 物流校对门禁（StreamSignStatus 状态机）+ §3.2.2 设备连接字段 + §3.2.2 物性补全（chemicals/thermo 自动估算）**后端实现率约 5%**（Stream 模型 + StreamStatePoint + StreamSignStatus enum + V3.1 migration 已落）。缺 `app/services/stream_service.py` + `app/api/v1/streams.py` + `app/schemas/stream.py` + 全部解析器（HYSYS XML/CSV、Aspen Plus、PRO/II、HTRI）+ Excel 导入（P3-OPEN-005）+ 物性补全服务 + PropertyConflictResolver（P3-SIM V1.2 §3）。	P3 启动必备	按 PCS-SPEC-P3-SIM V1.2 落地	待启动
P3-OPEN-010	[COMMON 物性数据库服务/API 全部 0%] 详见 §第五部分 5.3：P3 §3.1.2 COMMON 3 端点（materials/{id}/search/allowable-stress）+ §3.2.3 物性查询（chemicals + CoolProp IAPWS-IF97）+ §3.2.3 许用应力（ASME B31.3 Table A-1 插值）+ §3.2.3 毒性/爆炸极限**后端实现率 0%**。缺 `app/services/common_service.py` + `app/api/v1/common.py` + `app/schemas/common.py`。chemicals/fluids/thermo vendor 三件已接线（Task 1.9.0）。	P3 启动必备	按 §3.2.3 落地；Pydantic Schema 同步覆盖（P3-OPEN-004）	待启动
P3-OPEN-011	[Pydantic Schema 覆盖 + 表单 CI 漂移校验 — §3.2.5 实施现状] PCS 本体论 V1.6 §5.3 / §6 规则 11 要求「表单 ↔ Pydantic Schema 静态对比 CI」。当前已实现 schemas：checklist / config / equip_lib / formula / pipe_class / project_template / records / workspace（共 8 个）。**待补 schemas（与未实现 ORM/服务同步）**：project（P3-OPEN-008）、stream + state_point + composition（P3-OPEN-009）、common.material + allowable_stress（P3-OPEN-010）。	阻塞 §3.2.5 验收	先建 Pydantic Schema，再建前端 CI 漂移校验；与 P3-OPEN-008/009/010 同窗口落地	待启动

## 第五部分：实施现状与遗漏（V1.5 新增，2026-09-08 P2 close 同步）

> 本部分基于 P2 close 后仓库代码现状（`pcs-backend/` + `pcs-frontend/`），与本文档 §3 需求规格逐项核对。
> 用于 P3 启动时识别具体缺口。

### 5.1 P3.1 PMS 项目管理

**规格来源**：§3.1.2 PMS 端点（POST/GET/PUT /projects、PUT /bedd、POST /copy）+ §3.2.1 项目创建向导 4 步 + §3.2.1 项目复制 + §3.2.1 单位制联动 + §3.2.4 引用 PIPE 计算 + §3.3.1 性能 ≤3 秒。

**已实现**（代码层）：
- `app/models/project.py` Project 模型（含 `project_no`/`project_name`/`owner_company`/`location`/`project_type`/`design_phase`/`unit_system`/`bedd_json`/`workspace_id` 等）；V3.1 full_schema migration 已建表
- `app/models/project.py` Workspace 模型 + `app/services/workspace_service.py` + `app/api/v1/workspaces.py`（3 端点 POST/GET/GET by id）
- `app/services/checklist_service.py` + `app/api/v1/checklist.py`（项目输入清单生成 + GET/POST/PUT 端点）
- `app/services/project_template_service.py`（项目模板创建 fork default_config_json → INT-1 落地）

**遗漏**：
1. ❌ `app/services/project_service.py` 不存在 — 缺 create/get/update/copy/bedd_update 业务方法
2. ❌ `app/api/v1/projects.py` 路由不存在 — 缺 §3.1.2 PMS 全部 5 端点
3. ❌ `app/schemas/project.py` 不存在 — P3-OPEN-004 Pydantic Schema 覆盖阻塞
4. ❌ §3.2.1 项目创建向导 4 步（模板选择 / 基本信息 / BEDD 录入 / 确认）业务逻辑无 service 层
5. ❌ §3.2.1 项目复制功能（POST /copy + 复制 BEDD/物流/计算结果 + 计算结果标「未重新计算」）无实现
6. ❌ §3.2.1 单位制联动（SI/Metric/Imperial 实时转换 + 转换基准提示）无实现
7. ❌ §3.2.4 「已用于计算的等级不可删除」业务规则（已在 PIPE_CLASS §3.2.4 落地，本项 OK）

**工时估算**：项目 CRUD + BEDD JSON 写入 + 复制 + 单位制联动 + 5 端点 + Schema = **约 5 天**。

### 5.2 P3.2 SIM 工艺模拟数据

**规格来源**：§3.1.2 SIM 端点（POST /streams/import、GET/POST/PUT /streams、GET/POST /state-points、GET /chain）+ §3.2.2 多格式解析（HYSYS XML/CSV、Aspen Plus、PRO/II、HTRI）+ §3.2.2 三模式手动创建（CHEMICAL/PETROLEUM/SOLID）+ §3.2.2 物流校对门禁（4 态）+ §3.2.2 设备连接字段 + §3.2.2 物性补全 + P3-SIM V1.2 §3 PropertyConflictResolver + P3-OPEN-005/006/007 字段扩展。

**已实现**（代码层）：
- `app/models/project.py` Stream 模型（含 ADR-0019 全部 16 字段 + sign_status + approval_step + approval_depth + checked_by/at + record_hash + last_change_reason/note/changed_by/at + upstream_* 设备连接字段 + data_mode + source_type）
- `app/models/project.py` StreamStatePoint 模型（含 case_type NORMAL/MIN/MAX/ALTERNATE + T/P/phase/组成/vapor_composition/liquid_composition + record_hash + profile_json）
- `app/models/enums.py` StreamSignStatus 枚举（DRAFT/IN_APPROVAL/CHECKED/OBSOLETE — 4 态）
- V3.1 full_schema migration 已建 streams + stream_state_points 两表
- `app/schemas/project_template.py` StreamApprovalConfig（stream_approval_depth 1~2 配置）

**遗漏**：
1. ❌ `app/services/stream_service.py` 不存在 — 缺 create/get/update/import/state_point CRUD/chain/校核状态机/物性补全全部业务方法
2. ❌ `app/api/v1/streams.py` 路由不存在 — 缺 §3.1.2 SIM 全部 9 端点
3. ❌ `app/schemas/stream.py` 不存在 — P3-OPEN-004 阻塞
4. ❌ §3.2.2 多格式解析器全部缺失（HYSYS XML / HYSYS CSV / Aspen Plus / PRO/II / HTRI） — 须按 P3-SIM V1.2 §第二部分落地
5. ❌ §3.2.2 Excel 导入（P3-OPEN-005） — 6 个新 API + 列映射模板库
6. ❌ P3-OPEN-006 `viscosity_temperature_curve JSONB` 字段未加 streams 表
7. ❌ P3-OPEN-007 streams.case_type 字段未加（与 state_point.case_type 语义不同）
8. ❌ P3-OPEN-005 16 字段扩展部分缺失：`surface_tension` / `api_gravity` / `critical_temp` / `critical_press` / `vapor_*` / `actual_vol_flow`（`enthalpy` / `entropy` 已存在）
9. ❌ P3-OPEN-005 `import_source_type` 枚举 + `import_original_row` JSONB 字段未加（现有 `source_type` 复用 SIM_IMPORT/MANUAL_ENTRY 等 5 枚举，需扩展到 SIM/MANUAL/EXCEL/LAB 4 值并加 `import_original_row`）
10. ❌ §3.2.2 §3.2.2 三模式手动创建（CHEMICAL/PETROLEUM/SOLID）业务逻辑未实现（数据模式 enum 已定义）
11. ❌ §3.2.2 物流校对门禁状态机（StreamSignStatus 4 态 DRAFT/IN_APPROVAL/CHECKED/OBSOLETE 转移表 + 限权 + 引用保护）未实现
12. ❌ §3.2.2 设备连接字段生效（设备计算完成后自动创建出口物流 source_type=DEVICE_CALCULATED，sign_status=DRAFT）未接线
13. ❌ §3.2.2 物性补全服务（chemicals/thermo/petroleum 自动估算 + estimated=true 标记）未实现
14. ❌ P3-SIM V1.2 §3 PropertyConflictResolver（硬冲突 BLOCK / 软冲突 WARN / 蒸馏曲线冲突 / 第一/二/三类分类）未实现
15. ⚠️ StreamSignStatus 4 态 vs 5 态对齐：本 spec §3.2.2 写 4 态 DRAFT/IN_APPROVAL/CHECKED/OBSOLETE；P3-SIM V1.2 §1.2 写 5 态 DRAFT/PENDING/APPROVED/PUBLISHED/OBSOLETE；代码 = 4 态 — **两 spec 内部矛盾，待 P3 启动时对齐裁决**
16. ❌ P3-OPEN-005 验收指标（30 条物流 ≤ 5 秒 + 物性完整度 ≥ 90% + 组成归一化 100±0.5%）性能基线未测
17. ❌ §3.3.1 性能 HYSYS 文件解析 100 条 ≤ 10 秒 / 物性查询 ≤ 300ms 未测

**工时估算**：stream_service + 9 端点 + schema + 5 解析器 + 状态机 + 物性补全 + 冲突解决 + Excel 导入 + 字段扩展 = **约 30~35 天**（含 P3-SIM V1.2 §1-4 全量）。

### 5.3 P3.3 COMMON 工艺常用数据库

**规格来源**：§3.1.2 COMMON 端点（GET materials/{id}/search/allowable-stress）+ §3.2.3 物性查询（chemicals + CoolProp IAPWS-IF97）+ §3.2.3 许用应力（ASME B31.3 Table A-1 插值）+ §3.2.3 毒性/爆炸极限。

**已实现**（代码层）：
- `pcs-backend/vendor/chemicals/fluids/thermo` vendor 三件接线（Task 1.9.0，commit 337bc30）— 提供纯物质物性查询底层
- CATEGORY_3 seed 13 张系数表（含 Riazi-Daubert 物性估算参数 + 切割规则，P2 Sprint 1.9.4 落地）

**遗漏**：
1. ❌ `app/services/common_service.py` 不存在 — 缺 material_query / allowable_stress_query / toxicity_query / explosion_limit_query 业务方法
2. ❌ `app/api/v1/common.py` 路由不存在 — 缺 §3.1.2 COMMON 全部 3 端点
3. ❌ `app/schemas/common.py` 不存在 — P3-OPEN-004 阻塞
4. ❌ §3.2.3 数据来源标记（实验值/估算值/标准值）业务方法未实现
5. ❌ §3.2.3 ASME B31.3 Table A-1 许用应力按温度插值逻辑未实现
6. ❌ §3.2.3 毒性数据（剧毒/高毒/中毒/低毒分类）+ 爆炸极限（上限/下限）内置数据库未建
7. ❌ §3.3.1 物性查询 ≤ 300ms 性能基线未测

**工时估算**：common_service + 3 端点 + schema + 物性封装 + 应力插值 + 毒性与爆炸数据库 = **约 4~5 天**。

### 5.4 P3.4 PIPE_CLASS 管道等级库 — 已 100% 落地

**规格来源**：§3.2.4 PIPE_CLASS 全部 + D29~D34 裁决 + PC-OPEN-06/07 + SYM-OPEN-01 + FMT-OPEN-01/02 + INT-OPEN-01 + PC-FMT-01~06 + EXCEL-01 + FMT-SEQ-01。

**已实现**（代码层，P2 Sprint 1.9 + SUP-002 后端全部落地，commits ad25700..f59233d）：

| 模块 | 内容 | 提交 |
|------|------|------|
| PC-1 | pipe_classes/project_pipe_classes schema 升级 + ORM | f7778d4 |
| PC-2 | 管道等级验证引擎 22 条规则 + 接口契约 | 6f32a7e |
| PC-3 | 公司级 CRUD 接 ConfigAsset + 5 态审批流 | fc8487c |
| PC-4 | 项目级 fork + 快照 + 5 态轻量状态机 | 453c144 |
| PC-5 | Excel 双 Sheet 导入 + import_id 暂存 | 0b2acb8 |
| PC-6 | 管道等级 API 端到端收口 + 6 集成测试 | 8b1fd20 |
| SYM-1~3 | 物流符号表 migration+ORM+service+API+V01~V06 验证规则 | 40b0415 |
| FMT-1~4 | 管道代码模板 migration+ORM+service+generator+... | 651e2bc |
| INT-1 | 项目模板集成 + INT-3 端到端测试 | ade6111 |
| FMT-OPEN-02 | 模板 PUBLISH 触发 CIAEngine STALE 传播 | f59233d |
| P2 close | 删 assign_to_project + 2 schema + 1 端点（bug-051 收口） | 57f7b0f |

**测试**：463 passed（46 service + 12 API pipe_class + 16 pipe_code_template + 16 stream_symbol + INT-1 + 修复波），ruff 0 新增错误。

**遗漏**（仅 INT-2 前端波延后，非后端）：
- INT-2 前端表单组件（等级编辑 + 符号表管理 + 格式设计器）— 与 P2 Sprint 2 前端波合并，详见 P2 close 报告 §4
- bug-051 已收口；ProjectPipeClassResponse.pipe_class 恒 null（Sprint 2 前端契约遗留）→ P3 兑现
- equip-lib search limit>200 返 422（TODO-033 终审 DEFER）→ P3 兑现

**结论**：P3.4 视为完全解锁（依赖 SUP-002 追加 Sprint 先完成 PIPE_CLASS 库本体 + 物流符号表 + 管道代码格式模板；P4.2 PIPE 计算读取时直接消费 project_pipe_classes effective 值；项目模板创建 fork 模板格式配置 → project_pipe_code_configs — INT-1 已落地）。

### 5.5 P3 实施遗漏总览

| 子系统 | 规格需求 | 后端实现率 | 工时估算 | 阻塞项 |
|--------|---------|-----------|---------|--------|
| P3.1 PMS | §3.1.2 5 端点 + §3.2.1 向导/复制/单位制 | 0% | 5 天 | P3-OPEN-008 |
| P3.2 SIM | §3.1.2 9 端点 + §3.2.2 解析/创建/校对/补全 + P3-SIM V1.2 §3 + P3-OPEN-005/006/007 | ~5% | 30~35 天 | P3-OPEN-009 + P3-OPEN-005 + 4 态 vs 5 态对齐 |
| P3.3 COMMON | §3.1.2 3 端点 + §3.2.3 物性/应力/毒性 | 0% | 4~5 天 | P3-OPEN-010 |
| P3.4 PIPE_CLASS | §3.2.4 + D29~D34 + PC-OPEN-06/07 | **100%** | 0 天（已 closed） | 无 |
| P3-OPEN-004 元数据表单 CI | §3.2.5 + V1.6 §5.3 | 0%（需先建 schemas） | 含在 5.1~5.3 内 | 依赖 5.1~5.3 Pydantic Schema |
| P3-OPEN-011 Pydantic Schema 覆盖 | 阻塞 §3.2.5 验收 | 8 schemas 已建 / 缺 3 套 | 含在 5.1~5.3 内 | 同 P3-OPEN-004 |

**P3 启动总工时估算**：约 **40~45 天**（不含 P3.4 已 closed 部分）。

### 5.6 P2 close 后续待办（跨入 P3 / P2 Sprint 2 前端波）

| 编号 | 内容 | 落点 |
|------|------|------|
| P2 close §4 INT-2 | 等级编辑 + 符号表管理 + 格式设计器前端组件 | P2 Sprint 2 前端波 / P3 前端 |
| TODO-024 | equipment_list 补 ~56 列对齐 DICT V3.3 | P3 集成层启动前 |
| TODO-025 | pump_results 补 6 列 | P4 Task 0 |
| TODO-026 | P5 模块平铺字段/data_sheet_json 展开（9 表） | P5 各模块开发期 |
| TODO-027 | cost_est_results 补 RecordMixin + cost_estimate_json | P7 启动时 |
| TODO-028 | 10 张计算表主键 rename 落地 | P5 各模块开发时 |
| TODO-029 | CIA propagation perf budget 测试 | P2 Sprint 4 启动时 |
| TODO-030 | openpyxl 流式导出 | 条件触发 |
| TODO-031 ✅ | preconditions 接入 PUBLISH 门禁 | 已完成 2026-09-04 |
| TODO-032 | 4 个真库测试迁 conftest fixtures | P1.2 |
| TODO-033 | Sprint 1.9 终审 DEFER 清单 | 各自窗口 |

## 版本历史

| 版本 | 日期 | 修改内容 | 编制人 |
|---|---|---|---|
| V1.0 | 2026-08-27 | 初始版本 | 联合项目组 |
| V1.1 | 2026-08-28 | incorporate SUP-007：SIM 增加物流校对门禁（StreamSignStatus 4 态，DRAFT 不可引用，修改走限权+原因+影响预览）；文件标识改 PCS 前缀 | 联合项目组 |
| V1.2 | 2026-08-29 | incorporate ADR-0019~0022：手动创建向导（三模式/虚拟组分/物性估算）；状态点管理（多工况快照、两相流气液组成）；设备连接字段与出口物流（独立物流链）；新增状态点/物流链 API | 联合项目组 |
| V1.3 | 2026-09-03 | 对齐 PCS 本体论 V1.6 §2.5 / §5.3：关联文档加 V1.6；新增 §3.2.5 元数据驱动表单（Pydantic Schema 覆盖、UI Schema 层预留、条件显示策略、表单 ↔ Schema 静态对比 CI）；新增 P3-OPEN-004（Pydantic Schema 覆盖核对 + uiSchema 格式确定）；本版本不修改 PMS/SIM/COMMON/PIPE_CLASS 四大子系统主体需求 | 联合项目组 |
| V1.4 | 2026-09-03 | incorporate SUP-008 V1.1 + SUP-010 V1.1：关联文档加 SUP-008/SUP-010；新增 P3-OPEN-005（SIM Excel 导入引擎 + streams 16 字段扩展 + 多案例 stream_case_type 枚举）；新增 P3-OPEN-006（viscosity_temperature_curve JSONB 字段，蜡油加氢实例）；新增 P3-OPEN-007（case_type NORMAL/END_OF_RUN/START_OF_RUN/TURN_DOWN 案例切换）；主体 PMS/COMMON/PIPE_CLASS 不动 | 联合项目组 |
| V1.5 | 2026-09-08 | 对齐 P2 close 现状：关联文档加 PCS-SPEC-P3-SIM V1.2（ADD-001/002 合并）+ PCS-SPEC-P2-SUP-002 V1.4（PC-1~6/SYM-1~3/FMT-1~4 全部落地）+ 主开发计划 V1.3 + TODOS.md；新增 §第五部分 实施遗漏清单（5.1 PMS 0% / 5.2 SIM ~5% / 5.3 COMMON 0% / 5.4 PIPE_CLASS 100% / 5.5 总览 / 5.6 P2 close 后续待办）；新增 P3-OPEN-008（PMS 全缺）/ P3-OPEN-009（SIM service/API 全缺）/ P3-OPEN-010（COMMON service/API 全缺）/ P3-OPEN-011（Pydantic Schema 覆盖 + 表单 CI 漂移校验现状）；标记 StreamSignStatus 4 态 vs 5 态内部矛盾待 P3 启动时统一裁决；P3 启动总工时估算约 40~45 天 | 联合项目组 |

