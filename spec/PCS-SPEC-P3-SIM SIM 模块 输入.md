PCS-SPEC-P3-SIM
文档编号： PCS-SPEC-P3-SIM
版本： V1.2（完整版）
日期： 2026-09-08
状态： 已定稿（V1.2 增量：整合 ADD-001 手工输入完整字段清单 + ADD-002 校核/引用/冲突分类与处理策略；基于 V1.1 PRO/II 8.x 炼油版基线）
依赖： SPEC-P2 V1.4、开发计划 V1.2 §3.2、D29–D34 裁决
范围： 物流数据的四种输入方式（手工输入、Excel 批量导入、PRO/II 双文件解析、HYSYS/Aspen/HTRI 解析预留）+ 统一校验 + PCS 数据映射 + 扩展单元操作与反应数据解析 + 完整字段清单 + 校核状态/引用追踪/冲突解决
说明： 本文档整合了实际 PRO/II 项目（含反应器、压缩机、简捷塔、计算器等）的解析需求，作为 P3.2 SIM 模块的最终实施依据。

目录
第 0 部分：定位与输入方式总览

第一部分：手工输入

第二部分：Excel 批量导入

第三部分：PRO/II 双文件解析

第四部分：统一校验规则

第五部分：PCS 数据模型映射

第六部分：API 设计

第七部分：实施计划

第八部分：测试策略

附录 A：Excel 模板格式

附录 B：物流数据字段清单

附录 C：PRO/II 四样例覆盖矩阵

附录 D：PRO/II 单位制对照

附录 E：PRO/II 扩展单元操作支持

第 0 部分：定位与输入方式总览
0.1 P3.2 SIM 模块目标
SIM 模块是 P3 基础数据层的核心子系统之一，负责工艺模拟数据的导入、存储、校验和物性补全。它是 P4+ 所有计算模块的物流数据来源，同时为后续设备计算与反应模块提供单元操作和反应数据。

0.2 四种输入方式
输入方式	适用场景	优先级	对应章节
手工输入	少量物流、无模拟文件	P3 交付	第一部分
Excel 批量导入	物流数据已在 Excel 中整理	P3 交付	第二部分
PRO/II 双文件解析	有 PRO/II 模拟文件（.inp + .out）	P3 交付	第三部分
HYSYS/Aspen/HTRI 解析	其他模拟软件	P3/P4 补	预留（本 spec 仅定义接口）
0.3 统一数据模型
四种输入方式最终写入同一张 Streams 表，共享同一套校验规则（第四部分）和数据模型（第五部分）。扩展单元操作数据则写入相应的单元结果表。

text
手工输入 ────┐
             │
Excel 导入 ──┼─→ 统一校验引擎（第四部分）→ Streams 表（第五部分）
             │                                ↓
PRO/II 解析 ─┘                        （P4+ 计算模块消费）
             │
             └─→ 扩展单元操作表（第五部分 §5.5）→ P4/P5 设备模块
             └─→ 反应数据表（第五部分 §5.5）   → P4/P5 反应器模块
0.4 关键设计决策
决策	内容
内部单位制	温度 °C、压力 kPa、质量流量 kg/h、摩尔流量 kmol/h
组成存储	composition_json 为 {标准组分名: 摩尔分数}，归一化到 1.0
组分标识	优先 chemicals 库标准名称（WATER、METHANE），支持别名映射
物性补全	COMMON 库查询；缺失时估算，estimated=True 标记
来源标记	source 字段：MANUAL / EXCEL / PROII / HYSYS / ASPEN / HTRI
收敛状态	PRO/II 自动标记；其他来源默认 CONVERGED
单元操作存储	扩展单元操作结果存入专用结果表，不在 Streams 表中冗余
反应数据存储	反应器数据存入 sim_reactor_results，反应定义存入 sim_reaction_defs
解析范围	PRO/II 解析除物流外，全面覆盖实际项目中出现的所有单元操作类型
第一部分：手工输入
1.1 适用场景
项目初期少量关键物流（原料、产品、公用工程）、无模拟软件的项目、对已有物流进行补充或修正。

1.2 输入字段
1.2.1 基本属性（必填）
字段	类型	约束	说明
stream_name	varchar(50)	项目内唯一	物流名称
temperature	numeric(8,2)	-273 ~ 1000	°C
pressure	numeric(10,3)	0 ~ 100000	kPa
phase	enum	VAPOR / LIQUID / MIXED	相态
total_mass_flow	numeric(14,4)	≥ 0，与摩尔流量二选一	kg/h
total_molar_flow	numeric(14,4)	≥ 0，与质量流量二选一	kmol/h
1.2.2 组成输入（必填）
模式 A：摩尔分数

json
{"composition_json": {"WATER": 0.30, "METHANE": 0.50, "ETHANOL": 0.20}}
模式 B：质量流量（自动换算）

json
{"composition_mass": {"WATER": 5400, "METHANE": 8000, "ETHANOL": 9200}}
1.2.3 可选字段
字段	类型	说明
stream_no	varchar(20)	物流编号（如 P-001-L）
description	varchar(200)	描述
stream_properties_json	json	附加物性手工覆写
1.3 前端交互
text
物流列表页
├── 新建物流 → 表单（基本属性 + 组分选择器 + 组成输入）
│   ├── 组分搜索（chemicals 库）
│   ├── 模式切换（摩尔分数 ↔ 质量流量）
│   └── 实时校验反馈
├── 查看/编辑/删除
└── Excel 导入入口
第二部分：Excel 批量导入
2.1 适用场景
已有 Excel 整理的物流数据表、批量导入 10~100 条物流、从其他软件导出的物流数据。

2.2 Excel 模板格式
双 Sheet 结构：

Sheet 1: 物流列表

Stream Name	Stream No	Temp (°C)	Pressure (kPa)	Phase	Total Mass Flow (kg/h)	Total Molar Flow (kmol/h)	Description
FEED	P-001-L	25.0	101.325	LIQUID	10000.0		原料进料
RECYCLE	P-002-L	80.5	500.0	LIQUID	3500.0		循环物流
Sheet 2: 组分组成

Stream Name	Component Name	Mole Fraction	Mass Flow (kg/h)
FEED	WATER	0.25	
FEED	METHANOL	0.75	
RECYCLE	WATER	0.90	
RECYCLE	AMMONIA	0.10	
规则：

Mole Fraction 和 Mass Flow 至少填一列

两者都填时以 Mole Fraction 为准，Mass Flow 交叉验证

组分名称支持别名（H₂O→WATER 等，见附录 A）

2.3 导入流程
text
上传 Excel → 双 Sheet 解析 → 行级校验 → 预览（正确/错误/警告分组）
→ 用户确认 → 事务写入（任一行失败全量回滚）
第三部分：PRO/II 双文件解析
3.1 解析目标
从 PRO/II Keyword 输入文件（.inp）和输出报告（.out）中提取组分、物流、单元操作数据，以及反应器与动力学数据。解析范围覆盖实际化工流程中出现的常见单元操作和反应系统。

3.2 样例基准
样例	流程	组分	单元操作	收敛	关键特征
1	石油分馏（2 塔 + 3 泵）	34（24+10 PETRO）	COLUMN×2, PUMP×3	✅	完整物流组分、塔盘数据、物流闪蒸曲线
2	NH3/H2O 吸收（未收敛）	2	COLUMN×2, HX×3, PUMP	❌ 20 ERRORS	CALCULATION HISTORY、RECYCLE LOOPS
3	混合+换热+精馏（含侧线）	38（24+14 PETRO）	MIXER, HX, COLUMN	✅	MIXER SUMMARY、侧线、塔盘全套物性
4	酸性水汽提	4	FLASH×2, VALVE×4, PUMP, HX×3, COLUMN	✅ 3 WARNINGS	FLASH/VALVE SUMMARY、HCURVE、零流量物流
5	DMC 反应精馏流程	14	REACTOR, CSTR, COMPRESSOR, SPLITTER, STCA, HX, MIXER, FLASH, PUMP, COLUMN, CALCULATOR	✅	反应动力学、压缩机、简捷塔、计算器输出
3.3 .inp Keyword 解析
3.3.1 文件特征
特征	说明
关键字驱动	Section 以大写关键字开头
行继续符	& 结尾表示续行
数据分隔	/ 分隔数据组
注释	$ 开头
异常容错	输入中可能混入 ** WARNING ** 等输出信息行，解析时须跳过
数据污染	$ 后可能出现非注释数据（如 NORMALIZE$158.344,），需正确截断
3.3.2 Section 清单
Section	必填	提取目标
TITLE	是	Project 元数据
PRINT	否	忽略
TOLERANCE	否	存档
DIMENSION	是	单位制基准
SEQUENCE	否	存档
CALCULATION	否	存档
COMPONENT DATA	是	组分列表（LIBID + PETRO）
THERMODYNAMIC DATA	是	物性方法标记
STREAM DATA	是	进料物流
UNIT OPERATIONS	是	单元操作结构（含 REACTOR, CSTR, COMPRESSOR, SPLITTER, STCA, CALCULATOR 等）
RECYCLE DATA	否	存档
RXDATA	否	反应集定义（RXSET、REACTION）
END	是	结束
3.3.3 提取数据结构
python
@dataclass
class PROIIComponent:
    lib_id: int
    name: str
    is_petroleum: bool = False
    nbp: float | None = None      # PETRO
    api: float | None = None
    molwt: float | None = None

@dataclass
class PROIIStreamInput:
    name: str
    temperature: float
    pressure: float
    phase: str
    rate: float | None
    rate_basis: str               # WT / M
    rate_unit: str | None
    composition: list[tuple[int, float]]
    composition_basis: str
    normalized: bool = False

@dataclass
class PROIIUnitOp:
    uid: str
    name: str
    type: str                     # COLUMN/PUMP/HX/MIXER/FLASH/VALVE/REACTOR/CSTR/COMPRESSOR/SPLITTER/STCA/CALCULATOR
    parameters: dict              # 具体参数依类型而定

@dataclass
class PROIIReactionSet:
    rxset_id: str
    reactions: list[PROIIReaction]

@dataclass
class PROIIReaction:
    id: str
    stoichiometry: list[tuple[int, float]]  # (lib_id, coefficient)
    horx_heat: float | None
    ref_component: int | None
    ref_temp: float | None
    ref_phase: str | None
    kinetics: dict | None         # 动力学参数（PEXP, ACTIVATION, TEXPONENT, KORDER等）
3.4 .out 输出报告解析
3.4.1 文件特征
特征	说明
页头	PAGE P-nn / PAGE H-nn / PAGE R-nn
固定宽度表格	列宽固定，右对齐
续页标记	(CONT)
未收敛横幅	** WARNING - PROBLEM SOLUTION NOT REACHED **
单元操作 Summary 标题	如 REACTOR SUMMARY、COMPRESSOR SUMMARY 等，直接指示章节内容
3.4.2 Section 清单与提取器
Section	P3 交付	P5 交付
COMPONENT DATA	✅	
PLANT MATERIAL BALANCE	✅	
PUMP SUMMARY	✅	
HEAT EXCHANGER SUMMARY	✅	
MIXER SUMMARY	✅	
FLASH DRUM SUMMARY	✅	
VALVE SUMMARY	✅	
COLUMN SUMMARY（基础+侧线+规格+回流比）	✅	
STREAM COMPONENT RATES/FRACTIONS/PERCENTS	✅	
STREAM SUMMARY（完整物性）	✅	
HEATING/COOLING CURVE	✅	
CALCULATION HISTORY	✅	
RECYCLE LOOPS	✅	
RUN STATISTICS（收敛检测）	✅	
零流量物流检测	✅	
REACTOR SUMMARY	✅	
CSTR SUMMARY	✅	
SPLITTER SUMMARY	✅	
COMPRESSOR SUMMARY	✅	
STREAM CALCULATOR SUMMARY（STCA输出）	✅	
CALCULATOR SUMMARY	✅	
TRAY COMPOSITIONS		✅
TRAY LOADING		✅
TRAY NET RATES/DENSITIES		✅
TRAY STD LIQ DENSITIES		✅
TRAY TRANSPORT PROPERTIES		✅
TRAY ENTHALPIES		✅
TRAY RATING		✅
3.5 收敛状态与分层导入
python
class ConvergenceStatus(str, Enum):
    CONVERGED = "CONVERGED"
    CONVERGED_WITH_WARNINGS = "WARNINGS"
    NOT_CONVERGED = "NOT_CONVERGED"
    ABORTED = "ABORTED"

def detect_convergence(text: str) -> ConvergenceStatus:
    ...
物流来源	CONVERGED	WARNINGS	NOT_CONVERGED	ABORTED
进料物流	✅ 导入	✅ 导入	✅ 导入	✅ 导入
SOLVED 单元产品	✅ 导入	✅ 导入	⚠️ unreliable=True	⚠️ 仅存档
NOT SOLVED 单元物流	—	—	⚠️ 仅存档	⚠️ 仅存档
循环撕裂物流	✅ 导入	✅ 导入	⚠️ tear_stream=True	⚠️ 仅存档
对于新增单元操作类型，产品物流同样遵循上述规则；单元操作结果本身按单元状态存储，并保留 simulation_status 标记。

第四部分：统一校验规则
4.1 结构完整性（SIM-V 系列）
ID	规则	严重度	适用入口
SIM-V01	stream_name 非空且项目内唯一	ERROR	手工/Excel/PROII
SIM-V02	temperature 在 -273~1000°C	ERROR	手工/Excel/PROII
SIM-V03	pressure 在 0~100000 kPa	ERROR	手工/Excel/PROII
SIM-V04	phase 在枚举内	ERROR	手工/Excel/PROII
SIM-V05	质量流量或摩尔流量至少一项 > 0	ERROR	手工/Excel/PROII
SIM-V06	组成非空且至少 1 个组分	ERROR	手工/Excel/PROII
SIM-V07	组分名称可解析	ERROR	手工/Excel/PROII
SIM-V08	同物流内组分不重复	ERROR	手工/Excel/PROII
SIM-V09	组成加和 = 1.0（容差 0.001）	ERROR	提交
SIM-V10	组成加和偏差 > 1%	WARN	输入
4.2 工程一致性（SIM-E 系列）
ID	规则	严重度
SIM-E01	纯液相物流温度 > 临界温度	WARN
SIM-E02	纯气相物流温度 < 泡点（估算）	WARN
SIM-E03	质量流量与摩尔流量换算分子量不一致（容差 1%）	WARN
SIM-E04	物流被计算模块引用后不可删除	ERROR
4.3 PRO/II 结构验证（PR-V 系列）
ID	规则	严重度
PR-V01	.inp 以有效关键字开头	ERROR
PR-V02	必须有 COMPONENT DATA	ERROR
PR-V03	必须有 STREAM DATA 且至少一个 STREAM=	ERROR
PR-V04	必须有 UNIT OPERATIONS	ERROR
PR-V05	组分 ID 在 COMPONENT DATA 中定义	ERROR
PR-V06	PETRO 组分有 NBP/API/MW 三元组	ERROR
PR-V07	物流组成加和 ≈ 1.0（容差 1%）	WARN
PR-V08	NORMALIZE 标志存在时组成已归一化	INFO
PR-V09	行继续符 & 后无内容	ERROR
PR-V10	温度/压力在合理范围	WARN
PR-V11	.out 若存在，可检测到 RUN STATISTICS	WARN
PR-V12	RXDATA 段若存在，反应集 ID 唯一，反应定义完整	ERROR
PR-V13	STCA 的 FOVH 三元组格式正确（组分ID, 位置, 数值）	ERROR
PR-V14	COMPRESSOR/REACTOR 等单元的必填参数存在	ERROR
4.4 双文件交叉验证（PRX-V 系列）
ID	规则	严重度
PRX-V01	.inp 组分与 .out COMPONENT DATA 一致	ERROR
PRX-V02	.inp 进料设定与 .out 物料平衡一致（容差 1%）	WARN
PRX-V03	.inp 单元操作与 .out UNIT SUMMARY 一致	WARN
PRX-V04	.out 物料平衡偏差 ≤ 0.1%	ERROR
PRX-V05	.out 中每个物流有温度/压力/流量	ERROR
PRX-V06	零流量物流标记 zero_flow=True	INFO
PRX-V07	.inp 中定义的单元操作类型在 .out 中有对应 Summary（若已求解）	WARN
PRX-V08	反应器进料/产品物流与物料平衡数据一致（容差 1%）	WARN
第五部分：PCS 数据模型映射
5.1 Streams 表扩展
python
class Stream(Base):
    __tablename__ = "streams"
    stream_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.project_id"))
    stream_name: Mapped[str] = mapped_column(String(50))
    stream_no: Mapped[str | None] = mapped_column(String(20), nullable=True)
    temperature: Mapped[float]
    pressure: Mapped[float]          # kPa
    phase: Mapped[str]               # VAPOR/LIQUID/MIXED
    total_mass_flow: Mapped[float | None]     # kg/h
    total_molar_flow: Mapped[float | None]    # kmol/h
    composition_json: Mapped[dict]   # {标准组分名: 摩尔分数}
    description: Mapped[str | None]
    source: Mapped[str]              # MANUAL/EXCEL/PROII/HYSYS/ASPEN/HTRI
    estimated: Mapped[bool] = mapped_column(Boolean, default=False)
    simulation_status: Mapped[str] = mapped_column(String(20), default="CONVERGED")
    unreliable: Mapped[bool] = mapped_column(Boolean, default=False)
    tear_stream: Mapped[bool] = mapped_column(Boolean, default=False)
    zero_flow: Mapped[bool] = mapped_column(Boolean, default=False)
    stream_properties_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
5.2 组分映射
来源	映射规则
手工/Excel	别名解析 → chemicals 库标准名称
PRO/II LIBID	直接映射（H2O→WATER、NC5→N-PENTANE）
PRO/II PETRO	虚拟组分：{name, NBP, API, MW} 三元组 + .out 临界性质
python
PROII_COMPONENT_ALIASES = {
    "H2O": "WATER",
    "NC5": "N-PENTANE",
    "NC6": "N-HEXANE",
    "NC7": "N-HEPTANE",
    "NC8": "N-OCTANE",
    "NC9": "N-NONANE",
    "NC10": "N-DECANE",
    "ISOOCTAN": "ISOOCTANE",
    "PXYLENE": "P-XYLENE",
    "C1": "METHANE",
    "C2": "ETHANE",
    "C3": "PROPANE",
    "NC4": "N-BUTANE",
    "H2S": "HYDROGEN_SULFIDE",
    "NH3": "AMMONIA",
    "CO2": "CARBON_DIOXIDE",
    "H2": "HYDROGEN",
}
5.3 单位换算
PRO/II METRIC	PCS 内部	转换
°C	°C	1:1
KG/CM²	kPa	× 98.0665
KG/H	kg/h	1:1
KG-MOL/H	kmol/h	1:1
M*KCAL/HR	MJ/h	× 4.1868
KCAL/KG	kJ/kg	× 4.1868
KCAL/HR-M-C	W/(m·K)	× 1.163
CP	mPa·s	1:1
DYNE/CM	mN/m	1:1
5.4 单元操作映射
PRO/II 单元	PCS 目标	预填字段
PUMP	P4.4 PumpResults	inlet/outlet P/T、head、work、efficiency
HX	P5.4 HeatResults	duty、LMTD、U*A、双侧工况
COLUMN	SimTowerResult（存档）	逐板数据、规格、回流比
FLASH	P4.1 FlashResults	T/P、气液分率、闪蒸类型
VALVE	P6.1 CVResults	压降、进出口 P/T
MIXER	存档	混合后 T/P
REACTOR	SimReactorResult	反应器类型、温度/压力、反应热、组分变化、转化率
CSTR	SimCstrResult	体积、空时/空速、反应动力学、热平衡
COMPRESSOR	SimCompressorResult	进出口工况、效率、功、压头、后冷器数据
SPLITTER	SimSplitterResult	分流比、产品流量、温度/压力
STCA	SimStcaResult	塔顶/塔底产品、回收率规格、温度/压力
CALCULATOR	SimCalculatorResult	变量值、名称、单位
5.5 新增表
python
class SimImport(Base):
    __tablename__ = "sim_imports"
    import_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.project_id"))
    source_file: Mapped[str]
    output_file: Mapped[str | None]
    convergence_status: Mapped[str]
    sim_software: Mapped[str] = mapped_column(String(20), default="PROII")
    sim_version: Mapped[str | None]
    imported_at: Mapped[datetime]
    imported_by: Mapped[UUID]

class SimImportWarning(Base):
    __tablename__ = "sim_import_warnings"
    warning_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    import_id: Mapped[UUID] = mapped_column(ForeignKey("sim_imports.import_id"))
    severity: Mapped[str]
    unit_id: Mapped[str | None]
    message: Mapped[str]

class SimTowerResult(Base):
    __tablename__ = "sim_tower_results"
    tower_result_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    import_id: Mapped[UUID] = mapped_column(ForeignKey("sim_imports.import_id"))
    unit_id: Mapped[str]
    tray_data_json: Mapped[dict]
    compositions_json: Mapped[dict | None]
    loading_json: Mapped[dict | None]
    rating_json: Mapped[dict | None]

# 反应定义表
class SimReactionDef(Base):
    __tablename__ = "sim_reaction_defs"
    reaction_def_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    import_id: Mapped[UUID] = mapped_column(ForeignKey("sim_imports.import_id"))
    rxset_id: Mapped[str]
    reaction_id: Mapped[str]
    stoichiometry_json: Mapped[dict]          # {lib_id: coefficient}
    horx_heat: Mapped[float | None]
    ref_component: Mapped[int | None]
    ref_temp: Mapped[float | None]
    ref_phase: Mapped[str | None]
    kinetics_json: Mapped[dict | None]

# 通用单元操作结果基表
class SimUnitOpResult(Base):
    __tablename__ = "sim_unit_op_results"
    unit_result_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    import_id: Mapped[UUID] = mapped_column(ForeignKey("sim_imports.import_id"))
    unit_id: Mapped[str]
    unit_type: Mapped[str]                    # REACTOR/CSTR/COMPRESSOR/SPLITTER/STCA/CALCULATOR
    name: Mapped[str | None]
    temperature_in: Mapped[float | None]
    temperature_out: Mapped[float | None]
    pressure_in: Mapped[float | None]
    pressure_out: Mapped[float | None]
    status: Mapped[str | None]

# 反应器专用结果
class SimReactorResult(Base):
    __tablename__ = "sim_reactor_results"
    reactor_result_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    unit_result_id: Mapped[UUID] = mapped_column(ForeignKey("sim_unit_op_results.unit_result_id"))
    reactor_type: Mapped[str]                 # ADIABATIC/ISOTHERMAL/...
    duty: Mapped[float | None]
    heat_of_reaction: Mapped[float | None]
    component_changes_json: Mapped[dict | None]  # 组分变化数据
    conversion_json: Mapped[dict | None]      # 转化率

# CSTR 专用结果
class SimCstrResult(Base):
    __tablename__ = "sim_cstr_results"
    cstr_result_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    unit_result_id: Mapped[UUID] = mapped_column(ForeignKey("sim_unit_op_results.unit_result_id"))
    volume: Mapped[float | None]
    space_time: Mapped[float | None]
    space_velocity: Mapped[float | None]
    kinetics_json: Mapped[dict | None]

# 压缩机专用结果
class SimCompressorResult(Base):
    __tablename__ = "sim_compressor_results"
    compressor_result_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    unit_result_id: Mapped[UUID] = mapped_column(ForeignKey("sim_unit_op_results.unit_result_id"))
    adiabatic_efficiency: Mapped[float | None]
    polytropic_efficiency: Mapped[float | None]
    work_kw: Mapped[float | None]
    head_m: Mapped[float | None]
    aftercooler_duty: Mapped[float | None]
    aftercooler_temp: Mapped[float | None]

# 分流器专用结果
class SimSplitterResult(Base):
    __tablename__ = "sim_splitter_results"
    splitter_result_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    unit_result_id: Mapped[UUID] = mapped_column(ForeignKey("sim_unit_op_results.unit_result_id"))
    split_fraction: Mapped[float | None]

# 简捷塔专用结果
class SimStcaResult(Base):
    __tablename__ = "sim_stca_results"
    stca_result_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    unit_result_id: Mapped[UUID] = mapped_column(ForeignKey("sim_unit_op_results.unit_result_id"))
    overhead_stream: Mapped[str | None]
    bottoms_stream: Mapped[str | None]
    recovery_specs_json: Mapped[dict | None]

# 计算器专用结果
class SimCalculatorResult(Base):
    __tablename__ = "sim_calculator_results"
    calculator_result_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    unit_result_id: Mapped[UUID] = mapped_column(ForeignKey("sim_unit_op_results.unit_result_id"))
    variables_json: Mapped[dict | None]       # {name: value}
5.6 物性自动补全
物性	来源	估算方法
分子量	COMMON 库	—
临界温度/压力	COMMON 库	Joback 基团贡献法
偏心因子	COMMON 库	Lee-Kesler 关联式
标准密度	COMMON 库	Rackett 方程
焓值	CoolProp	理想气体焓 + 状态方程校正
粘度	CoolProp	对应态法
导热系数	CoolProp	对应态法
估算标记：任何物性使用估算值时，estimated=True。

第六部分：API 设计
6.1 手工输入
text
POST   /api/v1/streams
GET    /api/v1/streams/{stream_id}
PUT    /api/v1/streams/{stream_id}
DELETE /api/v1/streams/{stream_id}
POST   /api/v1/streams/validate
6.2 Excel 导入
text
POST   /api/v1/streams/import/excel                     # 上传 + 预览
POST   /api/v1/streams/import/excel/{preview_id}/confirm  # 确认导入
GET    /api/v1/streams/import/excel/template            # 下载模板
6.3 PRO/II 导入
text
POST   /api/v1/sim/imports/proii                        # 上传 .inp + .out
POST   /api/v1/sim/imports/proii/preview                # 仅预览
POST   /api/v1/sim/imports/proii/{import_id}/confirm    # 确认导入
GET    /api/v1/sim/imports/{import_id}                  # 导入详情
GET    /api/v1/sim/imports/{import_id}/warnings         # 警告列表
GET    /api/v1/sim/imports/{import_id}/towers/{unit_id} # 塔存档数据
V1.0 新增（扩展单元操作查询）：

text
GET    /api/v1/sim/imports/{import_id}/unit-results              # 所有单元操作结果
GET    /api/v1/sim/imports/{import_id}/unit-results/{unit_id}    # 指定单元结果
GET    /api/v1/sim/imports/{import_id}/reactions                 # 反应定义
GET    /api/v1/sim/imports/{import_id}/reactors/{unit_id}        # 反应器结果
GET    /api/v1/sim/imports/{import_id}/compressors/{unit_id}     # 压缩机结果
GET    /api/v1/sim/imports/{import_id}/splitters/{unit_id}       # 分流器结果
GET    /api/v1/sim/imports/{import_id}/stcas/{unit_id}           # 简捷塔结果
GET    /api/v1/sim/imports/{import_id}/calculators/{unit_id}     # 计算器结果
6.4 物性查询
text
GET    /api/v1/streams/{stream_id}/properties           # 完整物性
POST   /api/v1/streams/{stream_id}/properties/estimate  # 估算
6.5 其他模拟软件（预留接口）
text
POST   /api/v1/sim/imports/hysys      # P3/P4 补
POST   /api/v1/sim/imports/aspen      # P3/P4 补
POST   /api/v1/sim/imports/htri       # P3/P4 补
第七部分：实施计划
任务	内容	工时	依赖
SIM-1	Streams 表扩展（estimated/simulation_status/unreliable/tear_stream/zero_flow/stream_properties_json）	0.5 天	无
SIM-2	统一校验引擎（SIM-V 10 条 + SIM-E 4 条 + PR-V 14 条 + PRX-V 8 条）	1 天	SIM-1
SIM-3	手工输入 API + 物性自动补全	1.5 天	SIM-2
SIM-4	Excel 模板生成 + 双 Sheet 解析 + 导入 API	2 天	SIM-2
PR-1	PRO/II .inp 词法分析 + Section 解析（含 RXDATA）	1.5 天	无
PR-2	PRO/II .inp 组分/物流/单元操作提取（含新增类型）	2 天	PR-1
PR-3	PRO/II .out 固定宽度表格解析器	1.5 天	无
PR-4	PRO/II .out 组分数据提取	0.5 天	PR-3
PR-5	PRO/II .out 物流组分提取（RATES/FRACTIONS/PERCENTS）	1 天	PR-3
PR-6	PRO/II .out 物料平衡 + 单元汇总（PUMP/HX/MIXER/FLASH/VALVE）	1.5 天	PR-3
PR-7	PRO/II .out 塔基础汇总（含侧线/规格/回流比）	1 天	PR-3
PR-8	PRO/II .out HCURVE 提取	1 天	PR-3
PR-9	PRO/II 收敛检测 + CALCULATION HISTORY	0.5 天	PR-3
PR-10	PRO/II RECYCLE LOOPS + 零流量检测	0.5 天	PR-3
PR-11	PRO/II 交叉验证 + PCS 映射 + SimImport 表	1 天	PR-1~10, SIM-1
PR-12	PRO/II API + 集成测试	1 天	PR-11
PR-13	扩展单元操作解析（REACTOR/CSTR/COMPRESSOR/SPLITTER/STCA/CALCULATOR）	3 天	PR-6, PR-7
PR-14	反应数据解析与存储（RXDATA + REACTOR SUMMARY + CSTR SUMMARY）	2 天	PR-13
PR-15	扩展单元操作 API + 测试	1.5 天	PR-13, PR-14
SIM-9	前端物流表格 + 手工输入表单 + Excel 上传向导	2.5 天	SIM-3, SIM-4
INT-1	三入口统一集成测试 + 扩展单元操作测试	1.5 天	全部
合计		26.5 天（约 5.5 周）	
注：塔盘详细数据提取（TRAY COMPOSITIONS/LOADING/RATING）延后到 P5，约 1.5 天。

第八部分：测试策略
8.1 单元测试
测试类	覆盖
Validator	SIM-V 10 条 + SIM-E 4 条 + PR-V 14 条 + PRX-V 8 条 = 36 条规则
Property Estimation	已知物性查询 / 缺失物性估算 / estimated 标记
Excel Parser	双 Sheet 解析 / 组分别名 / 缺列处理
Composition Conversion	质量→摩尔换算 / 归一化
PROII Lexer	5 样例 + 边界（空文件/缺 END）
PROII FixedWidth Parser	列宽变化 / 科学计数法 / N/A 处理
PROII Convergence Detector	4 种状态
PROII UnitOp Parser	新增单元类型解析（REACTOR/CSTR/COMPRESSOR/SPLITTER/STCA/CALCULATOR）
RXDATA Parser	反应集、反应定义、动力学参数
Calculator Parser	变量输出、UNDEFINED 处理
8.2 集成测试（Golden Test）
python
# 手工输入
def test_manual_stream_crud_roundtrip(): ...

# Excel 导入
def test_excel_import_preview_confirm(): ...
def test_excel_import_rejects_invalid_composition(): ...

# PRO/II 样例 1（石油分馏）
def test_proii_sample1_components_34():
    assert len(result.components) == 34
    assert result.convergence_status == "CONVERGED"
    assert len(result.streams) == 21

# PRO/II 样例 2（未收敛）
def test_proii_sample2_not_converged():
    assert result.convergence_status == "NOT_CONVERGED"
    assert result.streams["S1"].unreliable == True

# PRO/II 样例 3（含侧线）
def test_proii_sample3_side_draw():
    assert result.streams["F"].is_side_draw == True
    assert len(result.components) == 38

# PRO/II 样例 4（酸性水汽提）
def test_proii_sample4_flash_valve():
    assert result.unit_ops["V01"].type == "FLASH"
    assert result.zero_flow_streams == ["FG1", "FG2"]

# PRO/II 样例 5（DMC 反应精馏）
def test_proii_sample5_reactor_extraction():
    assert result.unit_ops["R101"].type == "REACTOR"
    assert len(result.reactions) == 4
    assert result.unit_ops["C1"].type == "COMPRESSOR"
    assert result.unit_ops["SP1"].type == "SPLITTER"
    assert result.unit_ops["S2"].type == "STCA"
    assert result.unit_ops["CA2"].type == "CALCULATOR"

# 三入口一致性
def test_three_entry_points_consistency():
    """手工 + Excel + PRO/II 写入的数据格式一致"""
8.3 验收标准
标准	阈值
校验规则覆盖	36/36
手工输入 CRUD	100%
Excel 导入成功率（有效文件）	100%
PRO/II 5 样例解析成功率	100%
组分解析准确率	100%
物流 T/P/流量解析准确率	100%（容差 0.001）
收敛状态判定准确率	100%
物性补全成功率（常见组分）	≥ 95%
组分别名解析	≥ 50 个常见别名
扩展单元操作解析准确率	100%（容差 0.001）
反应数据解析准确率	100%
附录 A：Excel 模板格式
Sheet 1: 物流列表

列名	必填	类型
Stream Name	✅	文本
Stream No	❌	文本
Temperature (°C)	✅	数字
Pressure (kPa)	✅	数字
Phase	✅	VAPOR/LIQUID/MIXED
Total Mass Flow (kg/h)	⚠️ 二选一	数字
Total Molar Flow (kmol/h)	⚠️ 二选一	数字
Description	❌	文本
Sheet 2: 组分组成

列名	必填	类型
Stream Name	✅	文本
Component Name	✅	文本（支持别名）
Mole Fraction	⚠️ 二选一	数字
Mass Flow (kg/h)	⚠️ 二选一	数字
组分别名

别名	标准名称
H2O	WATER
CH4	METHANE
C2H5OH	ETHANOL
NH3	AMMONIA
H2S	HYDROGEN_SULFIDE
CO2	CARBON_DIOXIDE
N2	NITROGEN
O2	OXYGEN
NC5	N-PENTANE
NC6	N-HEXANE
...	...
附录 B：物流数据字段清单
字段	手工	Excel	PROII	必填	类型
stream_name	✅	✅	✅	✅	varchar(50)
stream_no	✅	✅	❌	❌	varchar(20)
temperature	✅	✅	✅	✅	numeric(8,2)
pressure	✅	✅	✅	✅	numeric(10,3)
phase	✅	✅	✅	✅	enum
total_mass_flow	✅	✅	✅	⚠️	numeric(14,4)
total_molar_flow	✅	✅	✅	⚠️	numeric(14,4)
composition_json	✅	✅	✅	✅	json
description	✅	✅	❌	❌	varchar(200)
source	自动	自动	自动	✅	varchar(20)
estimated	自动	自动	自动	✅	boolean
simulation_status	—	—	✅	❌	varchar(20)
unreliable	—	—	✅	❌	boolean
tear_stream	—	—	✅	❌	boolean
zero_flow	—	—	✅	❌	boolean
stream_properties_json	✅	❌	✅	❌	json
附录 C：PRO/II 样例覆盖矩阵
解析能力	样例 1	样例 2	样例 3	样例 4	样例 5	交付
.inp 词法分析	✅	✅	✅	✅	✅	P3
.inp 组分	✅	✅	✅	✅	✅	P3
.inp 物流	✅	✅	✅	✅	✅	P3
.inp COLUMN/PUMP/HX	✅	✅	✅	✅	✅	P3
.inp MIXER/FLASH/VALVE	—	—	✅	✅	✅	P3
.inp REACTOR/CSTR	—	—	—	—	✅	P3
.inp COMPRESSOR/SPLITTER	—	—	—	—	✅	P3
.inp STCA/CALCULATOR	—	—	—	—	✅	P3
.inp RXDATA	—	—	—	—	✅	P3
.out COMPONENT DATA	✅	✅	✅	✅	✅	P3
.out PLANT MATERIAL BALANCE	✅	✅	—	✅	✅	P3
.out PUMP/HX SUMMARY	✅	✅	✅	✅	✅	P3
.out MIXER/FLASH/VALVE SUMMARY	—	—	✅	✅	✅	P3
.out REACTOR SUMMARY	—	—	—	—	✅	P3
.out CSTR SUMMARY	—	—	—	—	✅	P3
.out COMPRESSOR SUMMARY	—	—	—	—	✅	P3
.out SPLITTER SUMMARY	—	—	—	—	✅	P3
.out STREAM CALCULATOR SUMMARY (STCA)	—	—	—	—	✅	P3
.out CALCULATOR SUMMARY	—	—	—	—	✅	P3
.out COLUMN SUMMARY（基础+侧线）	✅	✅	✅	✅	✅	P3
.out STREAM COMPONENT RATES/FRACTIONS/PERCENTS	✅	✅	✅	✅	✅	P3
.out STREAM SUMMARY	✅	✅	✅	✅	✅	P3
.out HEATING/COOLING CURVE	✅	—	—	✅	—	P3
.out CALCULATION HISTORY	—	✅	✅	✅	✅	P3
.out RECYCLE LOOPS	—	✅	✅	—	✅	P3
.out RUN STATISTICS	✅	✅	✅	✅	✅	P3
.out 零流量物流	—	—	—	✅	—	P3
.out TRAY COMPOSITIONS	✅	—	✅	—	—	P5
.out TRAY LOADING	✅	—	✅	—	—	P5
.out TRAY NET RATES/DENSITIES	—	—	✅	✅	—	P5
.out TRAY STD LIQ DENSITIES	—	—	✅	✅	—	P5
.out TRAY TRANSPORT PROPERTIES	—	—	✅	✅	—	P5
.out TRAY ENTHALPIES	—	—	✅	✅	—	P5
.out TRAY RATING	—	—	—	✅	—	P5
附录 D：PRO/II 单位制对照
PRO/II METRIC	符号	PCS 内部	转换
温度	°C	°C	1:1
压力	KG/CM²	kPa	× 98.0665
质量流量	KG/H	kg/h	1:1
摩尔流量	KG-MOL/H	kmol/h	1:1
密度	KG/M³	kg/m³	1:1
焓（总量）	M*KCAL/HR	MJ/h	× 4.1868
焓（比）	KCAL/KG	kJ/kg	× 4.1868
导热系数	KCAL/HR-M-C	W/(m·K)	× 1.163
粘度	CP	mPa·s	1:1
表面张力	DYNE/CM	mN/m	1:1
标准气体体积	K*M³/HR（0°C, 1atm）	Nm³/h	× 1000
附录 E：PRO/II 扩展单元操作支持
本附录详细描述新增单元操作类型在 .inp 和 .out 中的关键字与数据结构。

E.1 REACTOR（绝热/等温反应器）
输入文件关键字：

REACTOR UID=...

FEED / PRODUCT

OPERATION ADIABATIC 或 OPERATION ISOTHERMAL

RXCALCULATION MODEL=STOIC,CONVERSION

RXSTOIC RXSET=...

REACTION / STOICHIOMETRY / BASE COMPONENT / CONVERSION

输出 Summary：

REACTOR SUMMARY

操作条件：类型、热负荷、反应热、进出口温度/压力

反应数据：各组分进料/变化/产品摩尔流量、转化率

质量平衡表

E.2 CSTR（连续搅拌釜反应器）
输入文件关键字：

CSTR UID=...

FEED / PRODUCT

OPERATION PHASE=L,VOLUME=...,ADIABATIC

RXSTOIC RXSET=...

REACTION / BASE COMPONENT / KINETICS

输出 Summary：

CSTR SUMMARY

操作条件：体积、空时、空速、进出口温度/压力

反应数据：组分变化、转化率、动力学参数

热平衡表

E.3 COMPRESSOR（压缩机）
输入文件关键字：

COMPRESSOR UID=...

FEED / PRODUCT

OPERATION CALCULATION=ASME, PRES=...

COOLER ACDP=..., ACTEMP=...

输出 Summary：

COMPRESSOR SUMMARY

进出口条件：温度、压力、焓、熵、相态

效率（绝热/多变）、压头、功、后冷器数据

E.4 SPLITTER（分流器）
输入文件关键字：

SPLITTER UID=...

FEED / PRODUCT

OPERATION OPTION=FILL

SPEC STREAM=...,RATE(...),DIVIDE,...

输出 Summary：

SPLITTER SUMMARY

进料流率、产品流率、分流比、温度/压力

E.5 STCA（简捷塔）
输入文件关键字：

STCA UID=...

FEED / OVHD STRM=... / BTMS STRM=...

FOVH（组分回收率规格）

输出 Summary：

STREAM CALCULATOR SUMMARY

进料工况、塔顶/塔底产品工况（流率、温度、压力、焓等）

E.6 CALCULATOR（计算器）
输入文件关键字：

CALCULATOR UID=...,NAME=...

SEQUENCE STREAM=...

PROCEDURE 块

输出 Summary：

CALCULATOR SUMMARY

变量编号、名称、值（可能为 UNDEFINED）

解析时需注意：

计算器输出中可能出现 UNDEFINED，解析为 None。

变量值可能以科学计数法表示。

PCS-SPEC-P3-SIM V1.1 → V1.2 增量 Diff（2026-09-08）

合并 ADD-001：手工输入完整字段清单（§第二部分附录 A — 字段三级分类 R/O/C）
合并 ADD-002：物流校核状态 / 引用追踪 / 冲突分类与处理（§第二部分附录 B — 校核状态 / §附录 C — 引用追踪 / §附录 D — 冲突解决引擎）
数据库增量（ADD-002 §3.6）：streams 表增加 sign_status / user_provided_properties_json / calculated_properties_json / effective_properties_json / conflict_resolutions_json 五列（参见 §校核/引用/冲突章节）
状态机：SIM 物流走标准 5 态 DRAFT/PENDING/APPROVED/PUBLISHED/OBSOLETE（参见 §校核状态）

PCS-SPEC-P3-SIM V1.0 → V1.1 增量 Diff
变更摘要：新增 5 类 .out 提取器（SPLITTER/COMPRESSOR/TRAY SIZING/REFINERY PROPERTIES/TBP-ASTM）+ 9 类 .inp 新语法（ASSAY/D86/TBP/LIGHTEND/REFSTREAM/NAME/SIDESTRIPPER/COMPRESSOR/SPLITTER/CONTROLLER）+ 总工时 21.5→24.5 天

变更 1：§0.2 四样例基准 → 五样例基准
diff
-### 0.2 四样例基准
-本 spec 基于四个真实 PRO/II 4.17 样例文件：
+### 0.2 五样例基准
+本 spec 基于五个真实 PRO/II 样例文件（4 个 4.17 版 + 1 个 8.1.3 版）：

 | 样例 | 流程 | 组分 | 单元操作 | 收敛 | 关键特征 |
 |---|---|---|---|---|---|
 | 1 | 石油分馏（2 塔 + 3 泵） | 34（24+10 PETRO） | COLUMN×2, PUMP×3 | ✅ | 完整物流组分、塔盘数据、物流闪蒸曲线 |
 | 2 | NH3/H2O 吸收（未收敛） | 2 | COLUMN×2, HX×3, PUMP | ❌ 20 ERRORS | CALCULATION HISTORY、RECYCLE LOOPS |
 | 3 | 混合+换热+精馏（含侧线） | 38（24+14 PETRO） | MIXER, HX, COLUMN | ✅ | MIXER SUMMARY、侧线、塔盘全套物性 |
 | 4 | 酸性水汽提 | 4 | FLASH×2, VALVE×4, PUMP, HX×3, COLUMN | ✅ 3 WARNINGS | FLASH/VALVE SUMMARY、HCURVE、零流量物流 |
+| 5 | **FCC 催化裂化装置** | **41（26+15 PETRO）** | **COLUMN×4, SIDESTRIPPER, COMPRESSOR×2, PUMP×7, HX×25, SPLITTER×7, FLASH×4, MIXER×3, VALVE, CONTROLLER** | ✅ | **ASSAY 蒸馏曲线、REFSTREAM、SPLITTER/COMPRESSOR SUMMARY、TRAY SIZING、REFINERY PROPERTIES、TBP/ASTM 曲线** |
变更 2：§0.3 分层交付策略更新
diff
 | 层级 | 内容 | 交付阶段 |
 |---|---|---|
 | **P0（最小可行）** | .inp 词法分析、组分/物流/进料设定、.out 组分数据、物料平衡、物流组分（RATES/FRACTIONS/PERCENTS）、STREAM SUMMARY、泵/换热器汇总、收敛检测 | P3 |
-| **P1（完整）** | FLASH/VALVE/MIXER 汇总、HCURVE、CALCULATION HISTORY、RECYCLE LOOPS、零流量物流检测、塔基础汇总（含侧线） | P3 |
-| **P2（塔详细）** | TRAY COMPOSITIONS/LOADING/NET RATES/DENSITIES/TRANSPORT/ENTHALPIES/RATING | P5（存档供塔计算） |
+| **P1（完整）** | FLASH/VALVE/MIXER 汇总、HCURVE、CALCULATION HISTORY、RECYCLE LOOPS、零流量物流检测、塔基础汇总（含侧线）、**SPLITTER/COMPRESSOR 汇总、ASSAY/D86/TBP 蒸馏曲线、REFSTREAM 引用解析、NAME 重命名、SIDESTRIPPER/SPLITTER/CONTROLLER 单元提取** | P3 |
+| **P2（塔详细）** | TRAY COMPOSITIONS/LOADING/NET RATES/DENSITIES/TRANSPORT/ENTHALPIES/RATING、**TRAY SIZING** | P5（存档供塔计算） |
+| **P2b（炼油物性）** | **REFINERY PROCESSOR PROPERTIES SET、STREAM TBP/ASTM CURVES** | P5（物性验证基准） |
变更 3：§1.2 Section 清单（.inp）新增语法
在 §第三部分 PRO/II 双文件解析的 .inp Section 清单后追加：

diff
 ### 3.3.3 提取数据结构
 （保持原内容）

+### 3.3.4 PRO/II 8.x 新增语法
+
+#### ASSAY 石油评价数据
+
+```python
+@dataclass
+class PROIIAssayConfig:
+    conversion: str            # API94
+    curvefit: str              # IMPROVED
+    kvreconcile: str           # TAILS
+    tbp_cuts: tuple[int, int, int]  # (30, 650, 23) = 起始°C, 终止°C, 切割数
+    cutpoint_default: str      # DEFAULT
+```
+
+#### D86 / TBP 蒸馏曲线数据
+
+```python
+@dataclass
+class PROIIDistillationInput:
+    stream_name: str
+    curve_type: str            # D86 / TBP
+    points: dict[int, float]   # {体积%: 温度°C}
+    api_average: float | None  # API 重度（可选）
+
+@dataclass
+class PROIILightEnd:
+    stream_name: str
+    composition: list[tuple[int, float]]  # (组分ID, 质量分数)
+    percent: float             # 轻端占总物流的质量%
+    normalized: bool = False
+```
+
+#### REFSTREAM 引用物流
+
+```python
+@dataclass
+class PROIIRefStream:
+    stream_name: str           # 5R
+    ref_stream: str            # 5
+    temperature_override: float | None
+    rate_override: float | None
+    rate_basis: str | None     # M / WT
+```
+
+#### NAME 物流重命名
+
+```python
+def extract_stream_names(text: str) -> dict[str, str]:
+    """从 NAME 1G,FLUE/1DY,Dry Gas/1B,LPG 提取映射"""
+    ...
+```
+
+#### 新单元操作类型
+
+```python
+UNIT_TYPE_KEYWORDS = {
+    "COLUMN", "PUMP", "HX", "MIXER", "FLASH", "VALVE", "HCURVE",
+    "SIDESTRIPPER", "COMPRESSOR", "SPLITTER", "CONTROLLER",  # 8.x 新增
+}
+```
变更 4：§第三部分新增 SPLITTER SUMMARY 提取器
在 §2.4.3 单元操作汇总后追加：

diff
 @dataclass
 class PROIIValveResult:
     ...

+@dataclass
+class PROIISplitterResult:
+    """分流器汇总（PRO/II 8.x 新增）"""
+    unit_id: str               # FL1
+    unit_name: str             # 'LCO PROD SPLITTER'
+    feeds: list[str]
+    feed_molar_rate: float     # KG-MOL/HR
+    feed_mass_rate: float      # KG/HR
+    products: list[PROIISplitterProduct]
+    temperature: float
+    pressure: float
+    pressure_drop: float
+    mole_frac_vapor: float
+    mole_frac_total_liquid: float
+    mole_frac_hc_liquid: float      # 烃类液相分数
+    mole_frac_free_water: float     # 自由水分数
+    mole_frac_mw_solid: float       # 分子量固体分数
+
+@dataclass
+class PROIISplitterProduct:
+    stream: str
+    fraction: float            # 分配比例
+    molar_rate: float
+    mass_rate: float
变更 5：§第三部分新增 COMPRESSOR SUMMARY 提取器
diff
+@dataclass
+class PROIICompressorResult:
+    """压缩机汇总（PRO/II 8.x 新增）"""
+    unit_id: str               # STG1
+    unit_name: str
+    feeds: list[str]
+    vapor_products: list[str]
+    liquid_products: list[str]  # 可空
+    water_products: list[str]   # 可空
+    # 三段数据
+    inlet_temp: float
+    inlet_pressure: float
+    inlet_enthalpy: float
+    inlet_entropy: float
+    inlet_cp: float
+    inlet_cv: float
+    inlet_cp_cpr: float        # CP/(CP-R)
+    inlet_cp_cv: float         # CP/CV
+    isentropic_temp: float
+    isentropic_pressure: float
+    isentropic_enthalpy: float
+    isentropic_entropy: float
+    outlet_temp: float
+    outlet_pressure: float
+    outlet_enthalpy: float
+    outlet_entropy: float
+    outlet_cp: float
+    outlet_cv: float
+    outlet_cp_cpr: float
+    outlet_cp_cv: float
+    act_vap_rate: float        # M3/SEC
+    adiabatic_eff: float       # %
+    polytropic_eff: float      # %
+    isentropic_coefficient_k: float
+    polytropic_coefficient_n: float
+    asme_f_factor: float
+    head_adiabatic: float      # m
+    head_polytropic: float     # m
+    head_actual: float         # m
+    work_theoretical: float    # kW
+    work_polytropic: float     # kW
+    work_actual: float         # kW
+    aftercooler_duty: float | None
+    aftercooler_temp: float | None
+    aftercooler_pressure: float | None
变更 6：§第三部分新增 TRAY SIZING 提取器（P5 交付）
diff
+@dataclass
+class PROIITraySizingMechanicalData:
+    """塔盘尺寸设计机械数据（PRO/II 8.x）"""
+    section: int
+    tray_numbers: tuple[int, int]
+    tray_passes: int | None    # N/A = 未指定
+    tray_spacing: float        # mm
+    system_factor: float
+    tray_type: str             # VALVE
+    min_diameter: float        # mm
+
+@dataclass
+class PROIITraySizingResult:
+    tray_no: int
+    vapor_m3s: float           # M3/S
+    liquid_m3s: float          # M3/S
+    vload_m3s: float           # M3/S
+    design_diameter: float     # mm
+    design_ff: float           # %
+    next_smaller_diameter: float
+    next_smaller_ff: float
+    next_larger_diameter: float
+    next_larger_ff: float
+    n_passes: int
+
+@dataclass
+class PROIITraySizingDowncomer:
+    tray_no: int
+    next_larger_diameter: float
+    side_dc: float | None      # mm
+    center_dc: float | None    # mm
+    off_center_dc: float | None  # mm
+
+def extract_tray_sizing(pages: list[PROIIPage]) -> PROIITraySizing:
+    """从 TRAY SIZING MECHANICAL DATA + TRAY SIZING RESULTS + DOWNCOMER WIDTH 提取"""
+    ...
变更 7：§第三部分新增 REFINERY PROCESSOR PROPERTIES SET 提取器
diff
+@dataclass
+class PROIIRefineryStreamProperties:
+    """炼油处理器物性组（PRO/II 8.x 新增，替代部分 STREAM SUMMARY 功能）"""
+    stream_id: str
+    name: str
+    phase: str                 # WATER / DRY LIQUID / WET VAPOR
+    thermo_id: int
+    # Total Stream - WET BASIS
+    temperature: float
+    pressure: float
+    molar_rate: float
+    mass_rate: float
+    enthalpy_total: float
+    enthalpy_mass: float
+    molecular_weight: float
+    rvp: float | None          # PSI（Reid 蒸气压）
+    tvp: float | None          # KG/CM2（真实蒸气压）
+    # Liquid Phase - WET BASIS
+    liquid_mass_rate: float
+    liquid_act_rate: float     # LIT/SEC
+    liquid_std_lv_rate: float  # M3/HR
+    liquid_std_lv_rate_day: float  # M3/DAY
+    liquid_cp: float
+    liquid_mw: float
+    liquid_act_density: float
+    liquid_density: float      # 标准密度
+    liquid_viscosity: float    # CP
+    # Total Stream - DRY BASIS
+    dry_mass_rate: float | None
+    dry_mw: float | None
+    watson_k: float | None     # UOPK
+    flash_point: float | None  # °C
+    dry_rvp: float | None
+    dry_tvp: float | None
+    dry_density: float | None
+
+def extract_refinery_properties(pages: list[PROIIPage]) -> list[PROIIRefineryStreamProperties]:
+    """从 REFINERY PROCESSOR PROPERTIES SET 提取（注意 4 列并排格式）"""
+    ...
变更 8：§第三部分新增 STREAM TBP/ASTM CURVES 提取器
diff
+@dataclass
+class PROIIDistillationCurve:
+    curve_type: str            # TBP / D86 / D86_CRACKING / D1160 / D2887
+    pressure: str              # "760 MM HG" / "10 MM HG"
+    basis: str                 # LV PERCENT / WT PERCENT
+    points: dict[int, float]   # {1: temp, 5: temp, 10: temp, ..., 98: temp}
+
+@dataclass
+class PROIIStreamDistillationCurves:
+    stream_id: str
+    phase: str
+    thermo_id: int
+    curves: list[PROIIDistillationCurve]  # 最多 8 种曲线
+
+# 标准切割点
+STANDARD_CUT_POINTS = [1, 5, 10, 30, 50, 70, 90, 95, 98]
+
+# 8 种曲线组合
+CURVE_TYPES = [
+    ("TBP", "760 MM HG", "LV PERCENT"),
+    ("TBP", "10 MM HG", "LV PERCENT"),
+    ("TBP", "760 MM HG", "WT PERCENT"),
+    ("ASTM D86", "760 MM HG", "LV PERCENT"),
+    ("ASTM D86 WITH CRACKING", "760 MM HG", "LV PERCENT"),
+    ("ASTM D1160", "760 MM HG", "LV PERCENT"),
+    ("ASTM D1160", "10 MM HG", "LV PERCENT"),
+    ("ASTM D2887", "760 MM HG", "WT PERCENT"),
+]
+
+def extract_distillation_curves(pages: list[PROIIPage]) -> list[PROIIStreamDistillationCurves]:
+    """从 STREAM TBP/ASTM CURVES 提取（注意多曲线+多物流并排格式）"""
+    ...
变更 9：§第五部分 PCS 数据模型映射扩展
diff
 ### 5.4 单元操作映射
 
 | PRO/II 单元 | PCS 目标 | 预填字段 |
 |---|---|---|
 | PUMP | P4.4 PumpResults | inlet/outlet P/T、head、work、efficiency |
 | HX | P5.4 HeatResults | duty、LMTD、U*A、双侧工况 |
 | COLUMN | SimTowerResult（存档） | 逐板数据、规格、回流比 |
 | FLASH | P4.1 FlashResults | T/P、气液分率、闪蒸类型 |
 | VALVE | P6.1 CVResults | 压降、进出口 P/T |
 | MIXER | 存档 | 混合后 T/P |
+| SPLITTER | sim_splitter_results（存档） | 分配比例、各产品流量 |
+| COMPRESSOR | P6.3 FLARE_SYS / P7 UTIL | 功耗、压比、效率、级间冷却 |
+| SIDESTRIPPER | SimTowerResult（存档） | 同 COLUMN |
+| CONTROLLER | 存档（spec/vary 配置） | 控制逻辑 |
+
+### 5.6 炼油物性映射（PRO/II 8.x 新增）
+
+| PRO/II 数据 | PCS 目标 | 说明 |
+|---|---|---|
+| ASSAY 配置 | sim_imports.assay_config_json | TBPCUTS 等 |
+| D86/TBP 蒸馏曲线 | stream_properties_json.distillation_curves | 8 种曲线 |
+| LIGHTEND 轻端 | composition_json | 与虚拟组分分开存储 |
+| RVP/TVP | stream_properties_json | 炼油专用 |
+| WATSON K | stream_properties_json | 特性因数 |
+| FLASH POINT | stream_properties_json | 闪点 |
变更 10：§第七部分实施计划更新
diff
 | 任务 | 内容 | 工时 | 交付层级 |
 |---|---|---|---|
 | PR-1 | .inp 词法分析 + Section 解析 | 1 天 | P0 |
 | PR-2 | .inp 组分/物流/单元操作提取 | 1.5 天 | P0 |
+| PR-2b | .inp ASSAY/D86/TBP/LIGHTEND/REFSTREAM/NAME 提取 | 1 天 | P1 |
 | PR-3 | .out 固定宽度表格解析器 | 1.5 天 | P0 |
 | PR-4 | .out 组分数据提取 | 0.5 天 | P0 |
 | PR-5 | .out 物流组分提取（RATES/FRACTIONS/PERCENTS） | 1 天 | P0 |
 | PR-6 | .out 物料平衡 + 单元汇总（PUMP/HX/MIXER/FLASH/VALVE） | 1.5 天 | P0+P1 |
 | PR-7 | .out 塔基础汇总（含侧线/规格/回流比） | 1 天 | P1 |
 | PR-8 | .out HCURVE 提取 | 1 天 | P1 |
+| PR-8b | .out SPLITTER/COMPRESSOR SUMMARY 提取 | 1 天 | P1 |
 | PR-9 | 收敛检测 + CALCULATION HISTORY | 0.5 天 | P1 |
 | PR-10 | RECYCLE LOOPS + 零流量检测 | 0.5 天 | P1 |
 | PR-11 | 交叉验证 + PCS 映射 + SimImport 表 | 1 天 | P0 |
 | PR-12 | API + 集成测试（5 样例端到端） | 1 天 | P0+P1 |
 | PR-13 | 塔盘详细数据（TRAY COMPOSITIONS/LOADING/RATING） | 1.5 天 | P5 |
+| PR-14 | TRAY SIZING 提取 | 0.5 天 | P5 |
+| PR-15 | REFINERY PROCESSOR PROPERTIES SET 提取 | 1 天 | P5 |
+| PR-16 | STREAM TBP/ASTM CURVES 提取 | 0.5 天 | P5 |
 | SIM-1~9 | 手工输入 + Excel 导入 + 前端 | 10 天 | — |
 | INT-1 | 三入口统一集成测试 | 1 天 | — |
-| **合计** | | **21.5 天（约 4.5 周）** | |
+| **合计** | | **24.5 天（约 5 周）** | |
变更 11：§第八部分测试策略更新
diff
 ### 8.2 集成测试（Golden Test）
 
 （保留原有 4 样例测试）
 
+# PRO/II 样例 5（FCC 催化裂化）
+def test_proii_sample5_fcc():
+    result = parse_proii_files(sample5_inp, sample5_out)
+    assert result.convergence_status == "CONVERGED"
+    assert len(result.components) == 41  # 26 LIBID + 15 PETRO
+    assert result.unit_ops["STG1"].type == "COMPRESSOR"
+    assert result.unit_ops["FL1"].type == "SPLITTER"
+    assert result.unit_ops["T202"].type == "SIDESTRIPPER"
+    assert "ASSAY" in result.assay_configs
+    assert "FO1" in result.distillation_curves
+    assert len(result.distillation_curves["FO1"].curves) == 8
+
+def test_proii_sample5_splitter():
+    splitter = result.unit_ops["FL1"]
+    assert splitter.products[0].fraction == 0.4621
+    assert splitter.products[1].fraction == 0.5379
+
+def test_proii_sample5_compressor():
+    comp = result.unit_ops["STG1"]
+    assert comp.work_actual == 1455.84
+    assert comp.polytropic_eff == 76.0
+    assert comp.aftercooler_temp == 42.0
+
+def test_proii_sample5_tbp_curves():
+    curves = result.distillation_curves["FO1"]
+    tbp = curves.get("TBP_760_LV")
+    assert tbp.points[50] == 462.915
+    d86 = curves.get("D86_760_LV")
+    assert d86.points[50] == 445.754
变更 12：附录 C 覆盖矩阵更新
diff
 | 解析能力 | 样例 1 | 样例 2 | 样例 3 | 样例 4 | 样例 5 | 交付 |
 |---|---|---|---|---|---|---|
 | .inp 词法分析 | ✅ | ✅ | ✅ | ✅ | ✅ | P3 |
 | .inp 组分 | ✅ | ✅ | ✅ | ✅ | ✅ | P3 |
 | .inp 物流 | ✅ | ✅ | ✅ | ✅ | ✅ | P3 |
-| .inp COLUMN/PUMP/HX | ✅ | ✅ | ✅ | ✅ | — | P3 |
-| .inp MIXER/FLASH/VALVE | — | — | ✅ | ✅ | — | P3 |
-| .inp HCURVE/DEFINE/TOLERANCE | — | — | — | ✅ | — | P3 |
+| .inp COLUMN/PUMP/HX | ✅ | ✅ | ✅ | ✅ | ✅ | P3 |
+| .inp MIXER/FLASH/VALVE | — | — | ✅ | ✅ | ✅ | P3 |
+| .inp HCURVE/DEFINE/TOLERANCE | — | — | — | ✅ | ✅ | P3 |
+| .inp ASSAY/D86/TBP/LIGHTEND | — | — | — | — | ✅ | P3 |
+| .inp REFSTREAM/NAME | — | — | — | — | ✅ | P3 |
+| .inp SIDESTRIPPER/COMPRESSOR/SPLITTER/CONTROLLER | — | — | — | — | ✅ | P3 |
 | .out COMPONENT DATA | ✅ | ✅ | ✅ | ✅ | ✅ | P3 |
 | .out PLANT MATERIAL BALANCE | ✅ | ✅ | — | ✅ | ✅ | P3 |
 | .out PUMP/HX SUMMARY | ✅ | ✅ | ✅ | ✅ | ✅ | P3 |
 | .out MIXER/FLASH/VALVE SUMMARY | — | — | ✅ | ✅ | ✅ | P3 |
+| .out SPLITTER SUMMARY | — | — | — | — | ✅ | P3 |
+| .out COMPRESSOR SUMMARY | — | — | — | — | ✅ | P3 |
 | .out COLUMN SUMMARY（基础+侧线） | ✅ | ✅ | ✅ | ✅ | ✅ | P3 |
 | .out STREAM COMPONENT RATES/FRACTIONS/PERCENTS | ✅ | ✅ | ✅ | ✅ | ✅ | P3 |
 | .out STREAM SUMMARY | ✅ | ✅ | ✅ | ✅ | — | P3 |
 | .out HEATING/COOLING CURVE | ✅ | — | — | ✅ | ✅ | P3 |
 | .out CALCULATION HISTORY | — | ✅ | ✅ | ✅ | ✅ | P3 |
 | .out RECYCLE LOOPS | — | ✅ | ✅ | — | ✅ | P3 |
 | .out RUN STATISTICS | ✅ | ✅ | ✅ | ✅ | ✅ | P3 |
 | .out 零流量物流 | — | — | — | ✅ | — | P3 |
 | .out TRAY COMPOSITIONS | ✅ | — | ✅ | — | — | P5 |
 | .out TRAY LOADING | ✅ | — | ✅ | — | — | P5 |
 | .out TRAY NET RATES/DENSITIES | — | — | ✅ | ✅ | ✅ | P5 |
 | .out TRAY STD LIQ DENSITIES | — | — | ✅ | ✅ | ✅ | P5 |
 | .out TRAY TRANSPORT PROPERTIES | — | — | ✅ | ✅ | ✅ | P5 |
 | .out TRAY ENTHALPIES | — | — | ✅ | ✅ | — | P5 |
 | .out TRAY RATING | — | — | — | ✅ | ✅ | P5 |
+| .out TRAY SIZING | — | — | — | — | ✅ | P5 |
+| .out REFINERY PROCESSOR PROPERTIES SET | — | — | — | — | ✅ | P5 |
+| .out STREAM TBP/ASTM CURVES | — | — | — | — | ✅ | P5 |
变更 13：版本信息更新
diff
-# PCS-SPEC-P3-SIM
+# PCS-SPEC-P3-SIM
 
-**版本**：V1.0
+**版本**：V1.1
 **日期**：2026-09-06
-**状态**：已定稿（P3.2 SIM 工艺模拟数据模块完整实施依据）
+**状态**：已定稿（V1.1 增量：PRO/II 8.x 炼油版 SPLITTER/COMPRESSOR/TRAY SIZING/REFINERY PROPERTIES/TBP-ASTM）
PCS-SPEC-P3-SIM 增补——手工输入字段完整清单（基于 PRO/II 字段对齐）
文档编号：PCS-SPEC-P3-SIM-ADD-001
关联：PCS-SPEC-P3-SIM V1.2 §第一部分（手工输入）
状态：已合并入 V1.2（2026-09-08）
日期：2026-09-06

1. 目标
手工输入表单的字段设计对齐 PRO/II STREAM SUMMARY 和 REFINERY PROCESSOR PROPERTIES SET 的全部字段。用户能填多少填多少，空白字段由物性补全服务或后续计算模块（P4+ FLASH）自动填充。

2. 字段三级分类
分类	含义	说明
R（必填）	用户必须输入	无此数据物流不完整，无法导入
O（可选）	有数据就填	留空则自动补全或估算
C（计算填）	用户不填，计算模块填	表单中只读展示，由 P4+ 计算后回填
3. 完整字段清单
3.1 基本属性
字段	类型	分类	PRO/II 对应	说明
stream_name	varchar(50)	R	STREAM ID	物流名称，项目内唯一
stream_no	varchar(20)	O	—	物流编号（管道代码）
temperature	numeric(8,2)	R	TEMPERATURE, C	°C
pressure	numeric(10,3)	R	PRESSURE, KG/CM2	kPa（内部）
phase	enum	R	PHASE	VAPOR / LIQUID / MIXED
total_mass_flow	numeric(14,4)	R*	RATE, KG/HR	kg/h（与摩尔流量二选一）
total_molar_flow	numeric(14,4)	R*	RATE, KG-MOL/HR	kmol/h（与质量流量二选一）
description	varchar(200)	O	—	描述
*二选一必填。

3.2 组成
字段	类型	分类	说明
composition_json	json	R	{标准组分名: 摩尔分数}，加和=1.0
或 composition_mass	json	R*	{标准组分名: 质量流量}，自动换算
3.3 热力学基础物性（有数据就填，留空自动计算）
字段	类型	分类	PRO/II 对应	由谁补全
molecular_weight	numeric(10,4)	O	MOLECULAR WEIGHT	组成自动计算（精确）
std_liq_density	numeric(10,4)	O	STD LIQ DENSITY, KG/M3	COMMON 库查询
specific_gravity	numeric(8,4)	O	SPECIFIC GRAVITY	= std_liq_density / 1000
api_gravity	numeric(8,4)	O	API GRAVITY	= 141.5/SG - 131.5
3.4 相态物性（可选）
字段	类型	分类	PRO/II 对应	由谁补全
vapor_fraction	numeric(6,4)	O	MOLE FRAC VAPOR	FLASH 计算（P4.1）
liquid_fraction	numeric(6,4)	O	MOLE FRAC LIQUID	= 1 - vapor_fraction
3.5 气相物性（仅气相或混合相物流）
字段	类型	分类	PRO/II 对应	由谁补全
vapor_mass_rate	numeric(14,4)	O	VAPOR K*KG/HR	= total × vapor_fraction
vapor_actual_m3hr	numeric(14,4)	O	VAPOR M3/HR	状态方程
vapor_normal_m3hr	numeric(14,4)	O	NORM VAP RATE, K*M3/HR	理想气体定律
vapor_mw	numeric(10,4)	C	VAPOR MW	FLASH 计算
vapor_density	numeric(10,4)	C	VAPOR DENSITY, KG/M3	状态方程
vapor_z	numeric(8,4)	C	Z (FROM DENSITY)	状态方程
vapor_cp	numeric(10,4)	C	VAPOR CP, KCAL/KG-C	热力学模型
vapor_viscosity	numeric(10,4)	C	VAPOR VISCOSITY, CP	关联式
vapor_thermal_cond	numeric(10,4)	C	VAPOR TH COND	关联式
3.6 液相物性
字段	类型	分类	PRO/II 对应	由谁补全
liquid_mass_rate	numeric(14,4)	O	LIQUID K*KG/HR	= total × liquid_fraction
liquid_actual_m3hr	numeric(14,4)	O	LIQUID M3/HR	状态方程
liquid_gpm	numeric(12,4)	O	LIQUID GAL/MIN	单位换算
liquid_std_liq_rate	numeric(12,4)	O	STD LIQ RATE, M3/HR	标准密度换算
liquid_mw	numeric(10,4)	C	LIQUID MW	FLASH 计算
liquid_density	numeric(10,4)	O	LIQUID DENSITY, KG/M3	有实测数据优先填
liquid_z	numeric(8,4)	C	LIQUID Z	状态方程
liquid_cp	numeric(10,4)	C	LIQUID CP	热力学模型
liquid_viscosity	numeric(10,4)	O	LIQUID VISCOSITY, CP	有实测数据优先填
liquid_surface_tension	numeric(10,4)	O	SURFACE TENSION, DYNE/CM	关联式
liquid_thermal_cond	numeric(10,4)	C	LIQUID TH COND	关联式
3.7 焓值（可选，有实验数据时填）
字段	类型	分类	PRO/II 对应	由谁补全
enthalpy_total	numeric(14,6)	O	ENTHALPY, M*KCAL/HR	热力学模型
enthalpy_mass	numeric(10,4)	O	ENTHALPY, KCAL/KG	= total / mass_flow
3.8 炼油专用（可选，炼油项目填）
字段	类型	分类	PRO/II 对应	由谁补全
rvp	numeric(8,4)	O	RVP, PSI	FLASH 计算（P4.1）
tvp	numeric(8,4)	O	TVP, KG/CM2	FLASH 计算（P4.1）
watson_k	numeric(8,4)	O	WATSON K (UOPK)	组成计算
flash_point	numeric(8,2)	O	FLASH POINT, C	关联式（P3.3 COMMON）
distillation_curves	json	O	TBP/D86/D1160/D2887	有实测数据优先填
3.9 蒸馏曲线（炼油项目重点）
json
{
  "distillation_curves": {
    "D86_760_LV": {
      "points": {"0": 45, "10": 65, "50": 115, "90": 180, "100": 205}
    },
    "TBP_760_LV": {
      "points": {"5": 322, "10": 352, "30": 402, "50": 453}
    },
    "API_AVERAGE": 67.8
  }
}
用户可填任意一种或多种曲线。留空时由 ASSAY 切割虚拟组分后自动生成（P4.1 FLASH 的前置步骤）。

4. 输入优先级规则
当用户填写了某个物性字段时，用户值优先于计算值。具体规则：

冲突情况	处理
用户填了 liquid_density，FLASH 计算出不同值	用户值优先，FLASH 结果仅展示对比
用户填了 molecular_weight，组成计算不同	组成计算优先（分子量与组成强相关）
用户填了 enthalpy，热力学模型不同	用户值优先，模型结果展示对比
用户填了蒸馏曲线，ASSAY 切割不同	用户曲线优先
标记机制：用户手动填写的字段存入 user_provided_properties_json，自动计算的存入 calculated_properties_json。前端可展示「用户值 vs 计算值」对比。

5. 前端表单设计
text
┌─────────────────────────────────────────────┐
│ 物流手工输入                                 │
├─────────────────────────────────────────────┤
│ 基本属性（必填）                              │
│  名称 [________] 温度 [____] °C 压力 [____] kPa │
│  相态 [MIXED ▼]                              │
│  流量 [____] kg/h 或 [____] kmol/h           │
├─────────────────────────────────────────────┤
│ 组成（必填）                                  │
│  [WATER    ] [0.30]  [+ 添加组分]            │
│  [METHANOL ] [0.70]                         │
│  模式: ●摩尔分数 ○质量流量                    │
│  加和: ✓ 1.0000                              │
├─────────────────────────────────────────────┤
│ 热力学基础物性（可选，留空自动计算）            │
│  分子量 [____] 标准密度 [____] API [____]    │
├─────────────────────────────────────────────┤
│ 液相物性（可选）                              │
│  密度 [____] kg/m³  粘度 [____] cP          │
│  [展开更多] 表面张力 [____]                  │
├─────────────────────────────────────────────┤
│ 气相物性（仅气相/混合相）                     │
│  [展开更多]                                  │
├─────────────────────────────────────────────┤
│ 焓值（可选）                                 │
│  总焓 [________] MJ/h                        │
├─────────────────────────────────────────────┤
│ 炼油专用（可选，炼油项目展开）                 │
│  [展开更多] RVP [____] TVP [____]           │
│  D86 蒸馏曲线: [0,45] [10,65] [50,115] ...  │
├─────────────────────────────────────────────┤
│ [保存] [保存并触发物性补全]                   │
└─────────────────────────────────────────────┘
设计原则：

必填字段始终可见

可选字段按类别折叠，「展开更多」才显示

炼油专用字段仅当项目类型含「炼油」时显示

保存后立即展示「已填/待计算」状态指示

6. 与计算模块的接口
6.1 物性补全（P3.3 COMMON）
text
POST /api/v1/streams/{stream_id}/properties/complete
→ 补全：molecular_weight、std_liq_density、api_gravity
6.2 FLASH 计算（P4.1）
text
POST /api/v1/streams/{stream_id}/flash
→ 补全：vapor_fraction、liquid/vapor 各相物性、RVP/TVP
→ 写入 calculated_properties_json
6.3 蒸馏曲线生成（P4.1 前置）
text
POST /api/v1/streams/{stream_id}/distillation/generate
→ 从组成 + ASSAY 切割生成 TBP/D86 曲线
→ 写入 stream_properties_json.distillation_curves
7. 数据模型增量
python
class Stream(Base):
    # ... 既有字段
    user_provided_properties_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    calculated_properties_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # stream_properties_json 保留：最终有效值 = user_provided ⊕ calculated（user 优先）
三 JSON 字段关系：

text
stream_properties_json = calculated_properties_json ⊕ user_provided_properties_json
                         （user_provided 顶层键覆写 calculated）
8. 实施增量
任务	内容	工时
SIM-2b	手工输入 schema 扩展（完整字段清单）	1 天
SIM-4b	物性补全服务区分 user/calculated 来源	0.5 天
SIM-7b	前端完整表单（折叠式分组）	1 天
总增量		2.5 天
PCS-SPEC-P3-SIM 增补——物流校核状态、引用追踪与冲突解决
文档编号：PCS-SPEC-P3-SIM-ADD-002
版本：V1.2（在 V1.1 校核+引用基础上，整合冲突分类与处理策略；已合并入主文档 §校核/引用/冲突）
关联：PCS-SPEC-P3-SIM V1.2
状态：已合并入 V1.2（2026-09-08）
日期：2026-09-06

目录
第 1 部分：物流校核状态

第 2 部分：引用追踪

第 3 部分：冲突分类与处理策略

第 4 部分：实施计划汇总

第 1 部分：物流校核状态
1.1 需求
物流列表中每条物流需显示校核状态。SIM 物流作为记录层实体，走标准 5 态：

text
DRAFT → PENDING → APPROVED → PUBLISHED → OBSOLETE
         ↑ 驳回                    │
         └────────────────────────┘
1.2 状态定义
状态	含义	可见操作
DRAFT	新建/导入，未提交校核	编辑、删除、提交
PENDING	已提交，等待校核	撤回、校核通过/驳回
APPROVED	校核通过	发布、编辑（触发新版本）
PUBLISHED	已发布，计算模块可使用	作废、fork 新版本
OBSOLETE	已作废	仅查看
1.3 修改限制
状态	可编辑？	可删除？
DRAFT	✅	✅
PENDING	❌（需撤回）	❌
APPROVED	❌（需 fork）	❌
PUBLISHED	❌（需 fork）	❌
OBSOLETE	❌	❌
1.4 校核通过条件
条件	说明
组成加和 = 1.0（容差 0.001）	SIM-V09
无 BLOCK 级冲突	见第 3 部分
无 ERROR 级校验问题	SIM-V 系列无 ERROR
物性完整度 ≥ 阈值	必填字段 + 基础物性已补全
第 2 部分：引用追踪
2.1 需求
每条物流需显示是否已被设备计算引用，以及引用的具体来源。

2.2 DataLineage 反向查询
sql
SELECT DISTINCT dl.source_type, dl.source_id
FROM data_lineage dl
WHERE dl.target_type = 'stream'
  AND dl.target_id = :stream_id
2.3 引用来源类型
source_type	对应模块	说明
piping_result	P4.2 PIPE	管道计算引用了该物流
pump_result	P4.4 PUMP	泵计算引用了该物流
flash_result	P4.1 FLASH	闪蒸计算引用了该物流
vessel_result	P5.1 VESSEL	容器计算引用了该物流
heat_result	P5.4 HEAT	换热器计算引用了该物流
psv_result	P5.3 PSV	安全阀计算引用了该物流
equipment_record	P7.1 EQUIP_LIST	设备表引用了该物流
2.4 引用保护规则
规则	处理
in_use=True 且 sign_status=PUBLISHED	禁止修改。需先 fork 新版本
in_use=True 且 sign_status=DRAFT	禁止删除。修改不阻塞但需提醒
上游 PUBLISHED 物流被修改（fork 后发布新版本）	下游引用旧版本的记录经 CIA 传播标 STALE
2.5 API 响应扩展
json
{
  "stream_id": "...",
  "stream_name": "FEED-001",
  "sign_status": "PUBLISHED",
  "reference_count": 3,
  "references": [
    {"source_type": "pump_result", "source_id": "...", "module": "PUMP", "label": "P-101"},
    {"source_type": "heat_result", "source_id": "...", "module": "HEAT", "label": "E-201"}
  ],
  "in_use": true
}
2.6 前端展示
物流列表状态标记：

标记	含义
🟢 已发布	PUBLISHED
🔵 已通过	APPROVED
🟡 待校核	PENDING
⚪ 草稿	DRAFT
⚫ 已作废	OBSOLETE
📎 ×N	被 N 个计算引用
第 3 部分：冲突分类与处理策略
3.1 冲突的本质
手工输入和 Excel 导入的物流数据中，部分物性字段由用户提供，部分由后续计算模块（P4+ FLASH 等）计算。当两者对同一字段给出不同值时，产生冲突。

核心矛盾：用户填写的值可能是实测数据（比计算更准），也可能是估计值（比计算更差）。不能用简单规则一刀切。

3.2 冲突三级分类
第一类：硬冲突（数学上不能共存）
冲突	例子	处理
相态与 T/P/组成矛盾	用户填 phase=LIQUID，但 200°C/1atm/纯水在 FLASH 下必然是 VAPOR	拒绝保存。提示「该 T/P 下相态不可能为 LIQUID」
质量流量 × 组成 → 摩尔流量 ≠ 用户填的摩尔流量	质量流量=10000 kg/h，组成换算摩尔流量=555 kmol/h，但用户填了 400 kmol/h	拒绝保存。偏差 > 1% 时强校验
组成加和 ≠ 1.0	已处理（SIM-V09）	拒绝提交
第二类：物性冲突（可以有偏差，来源优先）
字段	用户填的可能是	计算得到的是	处理
liquid_density	实测值（更准）或估计值（不准）	状态方程/关联式（一般 ±1~5%）	用户值优先，但标记偏差
liquid_viscosity	实测值	关联式（±10~20%）	同上
molecular_weight	一般不填	组成加权平均（几乎无误差）	计算值优先，用户填了也忽略并警告
enthalpy	极少实测	热力学模型	计算值优先，用户填了需声明来源
RVP/TVP	实测值	FLASH 计算	实测优先
第三类：蒸馏曲线冲突
冲突	处理
用户填了 D86 曲线，ASSAY 切割产生不同的虚拟组分	用户曲线优先。ASSAY 只用于补全未提供的曲线类型
用户填了 D86 但没填 TBP	后端用 API94 关联式从 D86 换算 TBP
用户填了 TBP 但没填 D86	同理反向换算
3.3 冲突解决引擎
python
from enum import Enum
from dataclasses import dataclass

class ConflictSeverity(str, Enum):
    BLOCK = "BLOCK"        # 硬冲突，阻止保存
    WARN = "WARN"          # 软冲突，允许保存但标记
    INFO = "INFO"          # 仅提示差异

@dataclass
class ConflictResolution:
    severity: ConflictSeverity
    field: str
    user_value: float | str
    calculated_value: float | str
    resolution: str        # USER_VALUE / CALCULATED_VALUE / USER_MUST_CHANGE
    message: str

class PropertyConflictResolver:
    """物性冲突解决器"""

    def resolve(self, stream: Stream, flash_result: FlashResult | None = None) -> list[ConflictResolution]:
        conflicts = []

        # 第一类：硬冲突
        self._check_phase_consistency(stream, flash_result, conflicts)
        self._check_flow_consistency(stream, conflicts)
        self._check_composition_consistency(stream, conflicts)

        # 第二类：物性冲突
        self._check_property_conflicts(stream, flash_result, conflicts)

        # 第三类：蒸馏曲线
        self._check_distillation_conflicts(stream, conflicts)

        return conflicts
3.4 硬冲突处理
python
def _check_phase_consistency(self, stream, flash_result, conflicts):
    """相态与 T/P/组成矛盾"""
    if flash_result is None:
        return
    predicted_vapor_frac = flash_result.vapor_fraction
    if stream.phase == "LIQUID" and predicted_vapor_frac > 0.05:
        conflicts.append(ConflictResolution(
            severity=ConflictSeverity.BLOCK,
            field="phase",
            user_value="LIQUID",
            calculated_value=f"MIXED (vapor_frac={predicted_vapor_frac:.2f})",
            resolution="USER_MUST_CHANGE",
            message=f"该温度/压力/组成下气相分数为 {predicted_vapor_frac:.1%}，不能标记为纯液相",
        ))
    if stream.phase == "VAPOR" and predicted_vapor_frac < 0.95:
        conflicts.append(ConflictResolution(
            severity=ConflictSeverity.BLOCK,
            field="phase",
            user_value="VAPOR",
            calculated_value=f"MIXED (vapor_frac={predicted_vapor_frac:.2f})",
            resolution="USER_MUST_CHANGE",
            message=f"该温度/压力/组成下液相分数为 {1-predicted_vapor_frac:.1%}，不能标记为纯气相",
        ))
3.5 物性冲突处理
python
def _check_property_conflicts(self, stream, flash_result, conflicts):
    """用户填的物性 vs 计算结果——按字段分类处理"""
    user_props = stream.user_provided_properties_json or {}
    calc_props = flash_result.properties or {}

    # 用户值优先字段
    USER_PRIORITY_FIELDS = {
        "liquid_density": 0.10,      # 偏差阈值 10%
        "liquid_viscosity": 0.20,    # 偏差阈值 20%
        "vapor_density": 0.10,
        "surface_tension": 0.15,
        "rvp": 0.10,
        "tvp": 0.10,
    }

    for field, threshold in USER_PRIORITY_FIELDS.items():
        if field in user_props and field in calc_props:
            user_val = user_props[field]
            calc_val = calc_props[field]
            deviation = abs(user_val - calc_val) / calc_val
            if deviation > threshold:
                conflicts.append(ConflictResolution(
                    severity=ConflictSeverity.WARN,
                    field=field,
                    user_value=user_val,
                    calculated_value=calc_val,
                    resolution="USER_VALUE",
                    message=f"用户 {field}={user_val} 与计算值 {calc_val} 偏差 {deviation:.1%}，请确认是否为实测值",
                ))
            else:
                conflicts.append(ConflictResolution(
                    severity=ConflictSeverity.INFO,
                    field=field,
                    user_value=user_val,
                    calculated_value=calc_val,
                    resolution="USER_VALUE",
                    message=f"偏差 {deviation:.1%}，用户值已采用",
                ))

    # 计算值优先字段
    CALCULATED_PRIORITY_FIELDS = {
        "molecular_weight": "分子量由组成精确计算，用户输入已被忽略",
        "total_molar_flow": "摩尔流量由质量流量÷分子量换算，用户输入已被忽略",
        "total_mass_flow": "质量流量由摩尔流量×分子量换算，用户输入已被忽略",
    }

    for field, msg in CALCULATED_PRIORITY_FIELDS.items():
        if field in user_props:
            calc_val = getattr(stream, f"_calculated_{field}")()
            if abs(user_props[field] - calc_val) / calc_val > 0.01:
                conflicts.append(ConflictResolution(
                    severity=ConflictSeverity.WARN,
                    field=field,
                    user_value=user_props[field],
                    calculated_value=calc_val,
                    resolution="CALCULATED_VALUE",
                    message=msg,
                ))
3.6 数据存储策略
python
class Stream(Base):
    # ... 既有字段
    user_provided_properties_json: Mapped[dict | None]
    calculated_properties_json: Mapped[dict | None]
    effective_properties_json: Mapped[dict | None]
    conflict_resolutions_json: Mapped[list | None]   # 最近一次冲突解决记录
effective 计算规则：

text
effective = calculated ⊕ user（user 顶层键覆写 calculated）
但 CALCULATED_PRIORITY_FIELDS 中的字段始终取 calculated
3.7 冲突解决总原则
优先级	原则
1	数学一致性 > 用户输入——硬冲突阻止保存
2	实测数据 > 模型计算——用户值优先（物性类）
3	精确计算 > 用户估计——计算值优先（分子量、换算流量）
4	冲突必须可见——绝不静默覆盖
5	计算模块只读 effective——不直接读 user 或 calculated
3.8 前端交互
text
┌─────────────────────────────────────────────┐
│ ⚠️ 检测到 2 个数据冲突                      │
├─────────────────────────────────────────────┤
│ ❌ 相态冲突（阻止保存）                       │
│   你标记了 LIQUID，但 FLASH 计算显示          │
│   该条件下气相分数为 62%，应为 MIXED          │
│   [修改相态] [修改温度/压力]                  │
├─────────────────────────────────────────────┤
│ ⚠️ 密度偏差 12%（用户值已采用）               │
│   你输入: 900 kg/m³                          │
│   计算值:  803 kg/m³                         │
│   [确认实测值] [改用计算值]                   │
└─────────────────────────────────────────────┘
第 4 部分：实施计划汇总
任务	内容	工时
SIM-S1	Streams 表增加 sign_status + 状态历史	0.5 天
SIM-S2	物流校核状态机（复用 P1 记录层状态机）	1 天
SIM-S3	引用查询 API（DataLineage 反向查询）	0.5 天
SIM-S4	前端状态标记 + 引用面板	1 天
SIM-S5	CIA 联动（修改触发下游 STALE）	0.5 天
SIM-C1	ConflictResolver 引擎（硬冲突 + 软冲突 + 蒸馏曲线冲突）	1.5 天
SIM-C2	Stream 表增加 effective/conflict JSON 字段	0.5 天
SIM-C3	前端冲突展示组件 + 状态标记	1 天
总增量		6.5 天
增补 Spec 状态：已合并入 PCS-SPEC-P3-SIM V1.2（2026-09-08）。后续如需修订，按 V1.2.x 增量增补（参见 §V1.1→V1.2 Diff）。
