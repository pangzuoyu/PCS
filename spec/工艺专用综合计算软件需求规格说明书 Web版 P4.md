P4 核心计算引擎（第一批）开发规格说明书
文件标识	PCS-REQ-2026-002-SPEC-P4
当前版本	V1.3
发布日期	2026-08-27（V1.2 修订 2026-08-29，incorporate SUP-007 + ADR-0020/0022；V1.3 修订 2026-09-03，对齐 PCS 本体论 V1.6 §5 Task 0 范围）
编制部门	工艺部 / 信息化联合项目组
适用对象	内部开发团队（后端/前端/测试/数据库）
关联文档	PCS-REQ-2026-002 V2.2 §3.2.3/§3.2.4、SUP-003 §3.2.20/§3.2.23、SUP-007、管道一览表数据字典、离心泵计算数据字典、SPEC-P0/P1/P2/P3、DF-001、**PCS 本体论与语义关系研究说明（V1.6）§5（P4 Task 0 正式范围）**
第一部分：引言
1.1 目的
本文档定义P4阶段（核心计算引擎第一批）的完整需求规格，明确FLASH闪蒸与相平衡、PIPE管道计算、PIPE_NET管道网络水力学和PUMP机泵计算四个核心计算模块的详细功能需求、算法规格、输入输出定义和验收标准。

1.2 文档范围
包含：

FLASH：PT/PH/PS闪蒸、泡露点计算、热力学方法选择

PIPE：管径确定、壁厚计算、压降计算（单相/可压缩/两相）、管件阻力

PIPE_NET：Hardy-Cross迭代、节点法求解、网络拓扑管理

PUMP：扬程计算、NPSH计算、功率计算、控制阀压降分配

不包含：

VESSEL/PSV/HEAT（P5阶段）

CV/RESTRICTION/FLARE_SYS等（P6阶段）

EQUIP_LIST/UTIL集成（P7阶段）

报表输出（P8阶段）

1.3 定义、缩略语和术语
术语/缩写	定义
FLASH	闪蒸与相平衡计算
PT_FLASH	恒温恒压闪蒸
PH_FLASH	恒压恒焓闪蒸
PR	Peng-Robinson状态方程
SRK	Soave-Redlich-Kwong状态方程
NRTL	Non-Random Two-Liquid活度系数模型
NPSH	Net Positive Suction Head，汽蚀余量
BHP	Brake Horsepower，轴功率
Colebrook	摩擦因子迭代求解方程
Dukler I	两相流压降计算方法
L-M	Lockhart-Martinelli两相流方法
Hardy-Cross	管网水力迭代求解方法
DN	公称直径
Sch	管壁厚度系列
1.4 参考文献
HT-REQ-2026-002 V2.2 §3.2.3（PIPE）、§3.2.4（PUMP）、§3.4.3/§3.4.4（详细规格）

SUP-003 §3.2.20（FLASH）、§3.2.23（PIPE_NET）

管道一览表数据字典（完整字段定义）

离心泵计算数据字典（完整JSON结构）

SUP-002 §3.2.19（Python计算引擎规范）

ASME B31.3（管道壁厚计算标准）

HG/T 20570.6-95（推荐流速）

HG/T 20570.7-95（可压缩流压降）

IEC 60534-2-1（调节阀Cv，供PUMP控制阀分配参考）

1.5 文档概述
本文档共四个部分。第一部分说明目的、范围和术语。第二部分描述四个计算模块的定位和关系。第三部分详细定义各模块的算法规格、输入输出和验收标准。第四部分为附录。

第二部分：综合描述
2.1 产品前景
P4阶段是系统核心计算能力的第一批交付。FLASH为所有其他计算提供热力学基础；PIPE管道计算是泵和安全阀计算的上游；PIPE_NET扩展了管网级计算能力；PUMP是设备选型的核心模块。

四个模块形成完整的"物性→管道→管网→泵"计算链。

2.2 产品功能
模块	核心功能	主要依赖
FLASH	相平衡、闪蒸、泡露点	Thermo + CoolProp
PIPE	管径/壁厚/压降	fluids.friction/fittings/compressible/two_phase
PIPE_NET	管网水力求解	fluids + SciPy
PUMP	扬程/NPSH/功率/选型	伯努利方程 + 粘度修正
2.3 用户类和特征
用户类	特征	P4阶段相关需求
工艺设计人员	执行管道计算和泵选型	PIPE/PUMP日常使用
工艺负责人	审核计算结果	结果验证和审查
测试工程师	验证算法正确性	Golden Test执行和结果对比
2.4 运行环境
同SPEC-P0 §2.4。

2.5 设计和实现上的限制
公式版本记录：所有计算必须记录使用的公式版本号（FormulaVersion）到DataLineage。

浮点确定性：所有数值计算使用numpy.float64，保证跨平台一致性。

单位制支持：所有模块必须响应PMS中的单位制设置。

数据血缘：每次计算自动记录输入来源和公式版本，以及来源/目标记录哈希（V1.1 哈希锚定）。

输入完备性：计算前检查输入项状态，缺失或假设数据需强制标识。

记录生命周期（V1.1，SUP-007）：各模块计算结果为计算记录——9 态门禁（批准深度按 record_approval_config，默认 PIPE/PUMP 2~3 级）、record_hash（数值规范化舍入 6 位有效数字后计算）、无 version 字段；计算完成自动写 record_hash 并随计算追加血缘；引用物流须为 CHECKED 状态（DRAFT 物流 403）；模块 UI 提供"弃用"操作（未绑定免凭证，位号终身锁定）；管道一览表/泵数据表作为交付物由 P1 交付物机制发布，不在模块内自行签署。

2.6 假设和依赖
依赖P3：SIM物流数据、PIPE_CLASS管道等级、COMMON物性数据可用。

依赖P2：CONFIG中的公式和系数已配置。

假设：有标准算例（手算/商业软件结果）用于验证。

假设：fluids库版本经Golden Test验证。

第三部分：具体需求
3.1 外部接口需求
3.1.1 用户界面
界面	规格
FLASH计算	选择物流、选择热力学方法、选择计算类型（PT/PH/PS/泡露点）、显示结果表格
PIPE计算	管段配置表单（物流选择、管道长度、管件配置）、管径/壁厚/压降结果展示、管道一览表输出
PIPE_NET计算	网络拓扑编辑器（节点+管段图）、收敛日志、流量分配结果
PUMP计算	吸入/排出侧配置、等效长度计算器、NPSH/扬程/功率结果、泵数据表输出
3.1.2 软件接口
接口组	端点	说明
FLASH	POST /api/v1/flash/calculate	执行闪蒸计算
POST /api/v1/flash/bubble	泡点计算
POST /api/v1/flash/dew	露点计算
PIPE	POST /api/v1/pipe/sizing	管径计算
POST /api/v1/pipe/wall-thickness	壁厚计算
POST /api/v1/pipe/pressure-drop	压降计算
POST /api/v1/pipe/calculate-all	完整计算链
PIPE_NET	POST /api/v1/pipe-net/solve	管网求解
GET /api/v1/pipe-net/{net_id}/results	获取结果
PUMP	POST /api/v1/pump/calculate	完整泵计算
POST /api/v1/pump/equivalent-length	等效长度计算
POST /api/v1/pump/control-valve-dp	控制阀压降分配
3.2 功能需求
3.2.1 FLASH闪蒸与相平衡
需求编号：P4-FLASH-001

功能描述：基于Thermo库实现物流的相态判定、闪蒸计算、泡露点计算和焓熵计算。

计算类型：

计算类型	输入	输出	方法
PT_FLASH	P, T, 组成	汽化分率、气液相组成、焓	Rachford-Rice
PH_FLASH	P, H, 组成	T, 汽化分率、相态	能量+相平衡联立
PS_FLASH	P, S, 组成	T, 汽化分率、相态	熵+相平衡联立
BUBBLE_P	T, 液相组成	泡点压力、气相组成	Wilson初始化
BUBBLE_T	P, 液相组成	泡点温度、气相组成	迭代
DEW_P	T, 气相组成	露点压力、液相组成	迭代
DEW_T	P, 气相组成	露点温度、液相组成	迭代
SATURATION	T或P	纯物质饱和压力/温度	CoolProp
热力学方法映射：

体系类型	推荐方法	Thermo实现
轻烃/气体	Peng-Robinson	PRMIX
天然气处理	SRK	SRKMIX
极性体系	NRTL	NRTL
纯水/蒸汽	IAPWS-IF97	CoolProp
与SIM集成：计算结果可反向写入SIM物流的扩展属性（焓、熵、汽化分率），标记来源"FLASH计算"。

与状态点联动（V1.2，ADR-0020/0022）：给定状态点的 T/P/总组成 → FLASH 自动计算气液分率与气液相组成并写回该状态点（estimated 标记）；FLASH 本身作为设备转换也创建出口物流（source_type=FLASH_CALCULATED/DEVICE_CALCULATED，DRAFT 待校对）。

出口物流规则（V1.2，ADR-0022）：PIPE / PIPE_NET / PUMP / CV 计算完成后自动创建出口物流——物流是管段的标识，经过设备后物流号更换；出口物流 source_type=DEVICE_CALCULATED、sign_status=DRAFT、change_type 按设备性质取值（PUMP_WORK / FRICTION_PRESSURE_DROP 等），血缘记录 {上游物流}--[设备]-->{出口物流}。

验收标准：

纯物质饱和性质与CoolProp偏差<0.5%

混合物闪蒸结果与Aspen HYSYS偏差<1%

泡露点与HYSYS偏差<0.5°C

3.2.2 PIPE管道计算
需求编号：P4-PIPE-001

功能描述：实现管径确定、壁厚计算和压降计算的完整计算链。

（1）管径确定

方法	公式	说明
预定流速法	D = 1000×√(V/(0.785×v))	V=体积流量m³/s, v=流速m/s
设定压力降法	迭代求满足压降约束的最小管径	每100m压降控制值
流速参考来自CONFIG配置的推荐流速表（HG/T 20570.6-95）。

圆整规则：向上圆整至标准DN系列（从PIPE_CLASS读取）。

（2）壁厚计算

无缝钢管：t = P×D / (2×(S×E + P×Y))
焊接钢管：t = P×D / (2×(S×E×W + P×Y))

S = 材料许用应力（从PIPE_CLASS/COMMON读取，按设计温度插值）

E = 质量系数

Y = 壁厚温度系数

W = 焊缝接头强度降低系数

c = 腐蚀裕量（从PIPE_CLASS读取）

选用壁厚：t_nom = t + c，向上圆整至标准Sch系列。

（3）压降计算

工况	方法
单相不可压缩	Darcy-Weisbach + Colebrook + 管件K值（fluids.fittings）
单相可压缩（ΔP/P₁<10%）	不可压缩近似
单相可压缩（ΔP/P₁≥10%）	fluids.compressible等温/绝热流
两相流	首选Dukler I，备选Lockhart-Martinelli
管件阻力计算（fluids.fittings）：

管件类型	fluids函数	K值来源
90°弯头	bend_rounded	Crane TP-410
45°弯头	bend_rounded	Crane TP-410
三通	T_sharp/T_round	Crane TP-410
阀门	K_gate_valve_Crane等	Crane TP-410
变径	contraction_round/diffuser_round	Crane TP-410
入口/出口	entrance_sharp/exit_normal	Crane TP-410
输出：管道一览表（PipingResults表完整字段），包括管道号、尺寸、材料等级、介质信息、绝热涂漆、操作工况、设计工况、试验检验、清洗应力分析等。

验收标准：

单相压降与商业软件偏差<0.1%

壁厚计算与手算一致

管件K值与Crane TP-410偏差<2%

综合压降与手算偏差<5%

3.2.3 PIPE_NET管道网络水力学
需求编号：P4-PNET-001

功能描述：实现多管道网络的水力学求解。

求解方法：

方法	适用场景	SciPy实现
Hardy-Cross迭代	环形管网	scipy.optimize.fsolve
节点法	复杂网络	线性化迭代
环路法	多环路系统	Newton-Raphson
串联求解	简单支状网络	逐个管段
拓扑输入：

节点：设备/分支点

管段：管道号、管径、管长、管件

与PIPE集成：PIPE计算单管压降→作为管段阻力特性输入→PIPE_NET求解→反馈流量至PIPE更新流速→迭代至收敛。

验收标准：

简单并联网络与手算偏差<1%

环形管网与Hardy-Cross标准算例偏差<2%

3.2.4 PUMP机泵计算
需求编号：P4-PUMP-001

功能描述：实现泵的完整计算链，包括扬程、NPSH、功率和选型辅助。

计算步骤：

步骤	公式/方法	说明
扬程	H = ΔP/(ρg) + ΔZ + Σhf	伯努利方程
NPSHa	(Ps - Pv)/(ρg) + v²/(2g) - h损失	有效汽蚀余量
粘度修正	HI标准方法	影响扬程/流量/效率
轴功率	BHP = Q×H×ρ×g/(3600×η)	泵效率来自选型
电机功率	BHP/电机效率×安全系数	安全系数来自CONFIG
泵设计压力	MaxSuctionPressure + 1.25×DP	125%差压
控制阀压降	分设计/正常/最小三工况	从CONFIG获取分配规则
泵计算数据字典（完整JSON结构）：

BasicInfo：服务描述、位号、项目编号、环路号

FluidProperties：介质名称、温度、密度、蒸气压、粘度

FlowRates：正常/最小/设计流量

SuctionCalculation：吸入侧压力、液位、压降、NPSHa

DischargeCalculation：排出侧压力、静压头、压降

DifferentialPressure：差压、扬程

DesignPressure：最大吸入压力、泵设计压力

PowerConsumption：效率、BHP、电机功率

ControlValve：控制阀压降分配

EquivalentLength：管件等效长度

PressureDropDetails：压降明细

LineReferences：管线引用

等效长度计算：管件类型枚举（TUBE/BENDS/VALVES/TEE/CHECK_VALVE/REDUCER），每项记录数量和等效长度。

验收标准：

扬程计算与手算偏差<1%

NPSH计算正确

功率计算正确

控制阀压降分配合理

泵数据表输出完整

3.3 非功能需求
3.3.1 性能需求
指标	要求
FLASH单次计算	≤2秒
PIPE完整计算链（单管段）	≤3秒
PIPE_NET求解（10节点网络）	≤5秒
PUMP完整计算	≤2秒
收敛迭代次数上限	≤100次（超限返回警告）
3.3.2 精度需求
指标	要求
FLASH与HYSYS偏差	<1%
PIPE压降与商业软件偏差	<0.1%
壁厚计算	与手算完全一致
PUMP计算	与手算偏差<1%
浮点一致性	Golden Test偏差≤1e-12
3.4 数据需求
P4阶段使用P0创建的表：

piping_results（管道一览表完整字段）

pump_results（泵计算完整JSON结构）

flash_results（闪蒸计算结果）

pipe_network_results（管网计算结果）

data_lineage（血缘记录）

第四部分：附录
4.1 PIPE计算流程图
text
┌─────────────────────────────────────────────────────────┐
│                   PIPE计算链                            │
└─────────────────────────────────────────────────────────┘
                        │
                        ▼
              ┌─────────────────┐
              │  物性准备        │ ← SIM物流 + COMMON物性
              │  (密度/粘度)     │
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────────┐
              │  相态判断        │ ← FLASH模块调用
              │  (液/气/两相)   │
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────────┐
              │  管径初算        │ ← 预定流速法 + 设定压力降法
              │                 │ ← 圆整至标准DN
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────────┐
              │  壁厚计算        │ ← ASME B31.3
              │                 │ ← 圆整至标准Sch
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────────┐
              │  压降计算        │ ← Darcy-Weisbach + Colebrook
              │                 │ ← 管件K值(fluids.fittings)
              │                 │ ← 可压缩流/两相流
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────────┐
              │  流速与流型校核  │ ← 流速范围验证
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────────┐
              │  输出管道一览表   │ → PipingResults表
              └─────────────────┘
4.2 PUMP计算数据流
text
┌─────────────────────────────────────────────────────────┐
│                   PUMP计算链                            │
└─────────────────────────────────────────────────────────┘
                        │
         ┌──────────────┼──────────────┐
         ▼              ▼              ▼
   ┌──────────┐  ┌──────────┐  ┌──────────┐
   │ SIM物流  │  │PIPE压降  │  │PMS设计条件│
   │(流量物性)│  │(管线阻力)│  │(压力温度)│
   └────┬─────┘  └────┬─────┘  └────┬─────┘
        │             │             │
        └─────────────┼─────────────┘
                      ▼
             ┌─────────────────┐
             │   扬程计算       │ ← 伯努利方程
             └────────┬────────┘
                      │
                      ▼
             ┌─────────────────┐
             │   NPSH计算      │ ← NPSHa vs NPSHr
             └────────┬────────┘
                      │
                      ▼
             ┌─────────────────┐
             │   粘度修正       │ ← HI标准
             └────────┬────────┘
                      │
                      ▼
             ┌─────────────────┐
             │   功率计算       │ ← BHP + 电机功率
             └────────┬────────┘
                      │
                      ▼
             ┌─────────────────┐
             │  控制阀压降分配  │ ← 设计/正常/最小
             └────────┬────────┘
                      │
                      ▼
             ┌─────────────────┐
             │  泵数据表输出    │ → PumpResults表
             └─────────────────┘
4.3 待确定问题列表
编号	问题	影响	建议解决方案	状态
P4-OPEN-001	Thermo库PRMIX对哪些体系可能不收敛？	FLASH稳定性	需在测试阶段覆盖典型体系	待测试
P4-OPEN-002	粘度修正的具体HI标准版本？	PUMP精度	建议采用HI 9.6.7-2015	待确认
P4-OPEN-003	两相流Dukler I和L-M方法的选择规则？	PIPE精度	按SPEC：首选Dukler I，L-M交叉验证	已确认
P4-OPEN-004	管道粗糙度默认值来源？	PIPE压降精度	从CONFIG读取，默认0.046mm	已确认
P4-OPEN-005	[P4 Task 0-Design 范围确认] 详见 PCS 本体论 V1.6 §5.1：CIA 传播 API 形状、`@lineage` 最终签名（D4+D5，不暴露 physical_semantics）、RECORD_TYPE_REGISTRY 完整映射、physical_semantics 列声明、审计字段 JSON Schema（stale_resolution_path / hash_changed / changed_fields）、diff 采集与传递链路（A/B 方案）、RuleCollector 接口预留、ADR 记录	Task 0-Design 启动门	架构委员会按 V1.6 §5.1 清单逐项 approve；changed_fields diff 采集方案 A/B 在 ADR 中裁决	待启动
P4-OPEN-006	[P4 Task 0-Code 范围确认] 详见 PCS 本体论 V1.6 §5.2：Alembic 迁移加 physical_semantics 列（含 `@P7-eval-point` 注释）、装饰器 D4/D5 实现、importlinter D8、StateMachineService 审计字段强制写入、**RECORD_TYPE_REGISTRY 三方比对 CI（与 SQLAlchemy metadata + 状态机配置）**、**Pydantic ↔ ORM 同步 CI（V1.6 新增，硬性）**	Task 0-Code 启动门	按 V1.6 §5.2 清单逐项落地；DICT-ALL-003 升至 V4.0 标注 physical_semantics	待启动
P4-OPEN-007	[认知负荷检查] PCS 本体论 V1.6 §2.6 / §5.1 末段提示：domain_model.md 产出后由未参与 P4 开发的开发者（如 P5 负责人）10 分钟理解"物流从 SIM 导入到被 PIPE 引用"的完整状态转换与校验链。**该检查点为软建议**，非硬验收项；硬验收仍为架构委员会批准。	P4 Task 0-Design 软指标	若 10 分钟内讲不清则迭代 domain_model.md；架构委员会评审时关注总量可读性	软建议

## 版本历史

| 版本 | 日期 | 修改内容 | 编制人 |
|---|---|---|---|
| V1.0 | 2026-08-27 | 初始版本 | 联合项目组 |
| V1.1 | 2026-08-28 | incorporate SUP-007：记录生命周期约束（9 态门禁/record_hash/无 version 字段/弃用操作/物流 CHECKED 引用/交付物外置）；文件标识改 PCS 前缀 | 联合项目组 |
| V1.2 | 2026-08-29 | incorporate ADR-0020/0022：FLASH 与状态点联动（自动计算气液组成）；PIPE/PIPE_NET/PUMP/CV 计算完成自动创建出口物流（独立物流链，DEVICE_CALCULATED→DRAFT 待校对） | 联合项目组 |
| V1.3 | 2026-09-03 | 对齐 PCS 本体论 V1.6：关联文档加 V1.6 §5（P4 Task 0 正式范围）+ DF-001；新增 P4-OPEN-005/006/007（Task 0-Design 范围确认、Task 0-Code 范围确认、认知负荷软建议）；本版本不修改 §3.2/§4 等已交付计算模块需求，仅补充前置 Task 0 启动门与 CI 硬性项 | 联合项目组 |

