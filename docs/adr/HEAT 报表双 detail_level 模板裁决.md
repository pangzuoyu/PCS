HEAT 报表双 detail_level 模板裁决
状态：已接受（Accepted）· **2026-12-12 修订：放弃「DETAIL 字段覆盖率 ≥ 95%」验收目标**（见文末「修订记录」）
日期：2026-10-07（修订 2026-12-12）
决策者：首席架构师 / 工艺专家
关联：ADR-P8-001（全直接生成模式）、SUP-009 V1.0、SPEC-P8 V1.2 §4.3 P8-OPEN-006

背景
SPEC-P8 V1.2 在 P8-OPEN-006 中提出：REPORT_BUILDER 数据源 HEAT_EXCEL 需适配 heat_results 新表的 39 个字段 + ache_params JSONB。原 9 字段保留向后兼容（detail_level=BASIC 仍可生成简化报表）；扩展字段（detail_level=DETAIL）需要覆盖 HTRI 空冷器模板源 `A-101.xls`（原写 121-A-101.xls，实际文件名无 `121-` 前缀）和 TEMA 管壳式模板源 131-E-102-EOR.xls 两个来源。原验收标准为 detail_level=DETAIL 报表字段覆盖率 ≥ 95%，**该目标已于 2026-12-12 放弃**（修订记录见文末）。

该问题在 SPEC 中仅以“待确定问题”形式登记，未给出具体裁决。P8 开发前必须明确：detail_level 的分级标准、两类换热器（空冷器/管壳式）的字段映射规则、以及双模板在 REPORT_BUILDER 中的呈现方式。

关键约束：ADR-P8-001 已裁决 P8 报表全部采用直接生成模式，不再使用模板填充 + 格式转换链路。因此本 ADR 的“双模板”应理解为双套 ReportStyle + 字段映射配置，而非两个 .dotx / .xltx 文件。

决策
P8 REPORT_BUILDER 的 HEAT 数据源采用 detail_level 双级分级：BASIC（9 字段简化报表）与 DETAIL（39 字段完整报表）。两类报表均通过直接生成模式输出，DETAIL 级需覆盖 HTRI 空冷器和 TEMA 管壳式两种模板源的字段映射。

分级标准
级别	字段来源	字段数	适用场景	输出样式
BASIC	原 9 字段（向后兼容）	9	快速预览、设备一览表汇总行、即席查询	简化表格，无几何/热阻明细
DETAIL	heat_results 39 字段 + ache_params JSONB	39+	正式计算书、规格书、交付物	完整表格，含壳程管程 JSONB 展开、几何、热阻分布
字段映射配置
BASIC 级（9 字段）
原 9 字段保持不变，确保向后兼容：

#	字段	说明
1	TagNumber	设备位号
2	Area	换热面积
3	HeatDuty	热负荷
4	OverallU	总传热系数
5	ShellInletTemp	壳程进口温度
6	ShellOutletTemp	壳程出口温度
7	TubeInletTemp	管程进口温度
8	TubeOutletTemp	管程出口温度
9	PressureDrop	压降
DETAIL 级（39 字段 + JSONB）
DETAIL 级字段分为基础字段和扩展字段两组，扩展字段按换热器类型分叉。

基础字段（全类型适用，与 BASIC 共 9 字段 + 热工字段） ：

类别	字段	说明
标识	TagNumber, Service, Type	位号、用途、类型（空冷器/管壳式）
热工	HeatDuty, Area, OverallU, LMTD, MTD_Correction	热负荷、面积、总传热系数、对数平均温差、温差修正系数
温度	ShellInletTemp, ShellOutletTemp, TubeInletTemp, TubeOutletTemp	壳程/管程进出口温度
流量	ShellFlowRate, TubeFlowRate	壳程/管程流量
压降	ShellPressureDrop, TubePressureDrop	壳程/管程压降
壳程/管程 JSONB 扩展字段：

JSONB 键	内容
shell_side_json	壳程物性（密度、粘度、导热系数、比热）、雷诺数、普朗特数、传热系数、污垢热阻
tube_side_json	管程物性、雷诺数、普朗特数、传热系数、污垢热阻
几何字段：

类型	字段
空冷器	TubeOD, TubeWallThickness, TubeLength, TubePitch, TubeRows, TubePasses, FinHeight, FinDensity, FinThickness, BundleWidth, BundleLength, FanDiameter, FanPower, NumberOfFans, AirFlowRate
管壳式	ShellID, TubeOD, TubeWallThickness, TubeLength, TubePitch, TubePasses, TubeCount, BaffleSpacing, BaffleCut, BaffleType, TEMA_Type, NozzleSizes
热阻分布字段：

字段	说明
ShellSideResistance	壳程热阻
TubeSideResistance	管程热阻
WallResistance	壁面热阻
FoulingResistance	污垢热阻
TotalResistance	总热阻
ache_params JSONB（仅空冷器） ：

键	内容
fan_params	风机参数（类型、直径、功率、数量、转速）
air_side_params	空气侧参数（进口温度、出口温度、流量、流速）
fin_params	翅片参数（高度、密度、厚度、材质）
nozzle_params	管嘴参数（尺寸、等级、方向）
air_side_resistance	空气侧阻力分布
模板源与输出样式
模板源	对应换热器类型	适用报表	ReportStyle 关键配置
HTRI 空冷器（121-A-101.xls）	空冷器（ACHE）	空冷器规格书、计算书	横向布局，翅片/风机参数表，空气侧阻力分布表
TEMA 管壳式（131-E-102-EOR.xls）	管壳式换热器	换热器规格书、计算书	纵向布局，壳程/管程分栏表，TEMA 类型标识，热阻分布表
两类模板源均通过 ReportStyle 配置实现，不涉及文件模板。ReportStyle 中通过 heat_exchanger_type 字段区分 AIR_COOLER / SHELL_TUBE，渲染器据此选择对应的表格结构、列宽、字段布局。

REPORT_BUILDER 呈现
数据源注册表：HEAT_EXCEL 数据源暴露全部 39 字段 + JSONB 展开键。

detail_level 选择：报表定义中增加 detailLevel 字段（枚举 BASIC / DETAIL），执行时按级别过滤字段树。

字段树动态生成：BASIC 级只展示 9 个基础字段；DETAIL 级展示全部字段，并按换热器类型分组（通用 / 空冷器专属 / 管壳式专属）。

JOIN 支持：EQUIP_LIST.tag_number = HEAT_RESULTS.tag_number（已在 ADR-P8-001 §1.3 中声明）。

选型理由
向后兼容。BASIC 级保留原 9 字段，现有报表定义和即席查询不受影响。

分级合理。BASIC 满足快速预览和设备一览表汇总需求；DETAIL 满足正式计算书和规格书的完整字段需求。两级之间无重叠，切换成本低。

与全直接生成模式一致。双模板通过 ReportStyle 配置实现，不引入 .xls 模板文件，符合 ADR-P8-001 裁决。

HTRI 兼容性有据。HTRI 空冷器输出（Xace）和 TEMA 管壳式输出（Xist）是行业标准格式，DETAIL 级字段映射以其为基准，可确保与商业软件输出一致。

验收标准明确。DETAIL 字段覆盖率 ≥ 95% 可通过自动化比对验证，不依赖人工目视。

影响
正面
REPORT_BUILDER 的 HEAT 数据源可用。P8 可正式启动 HEAT 报表开发。

正式计算书和规格书有完整字段支撑。DETAIL 级覆盖 HTRI 和 TEMA 输出格式，满足交付物要求。

双级切换灵活。用户可根据报表用途选择 BASIC 或 DETAIL，无需修改数据模型。

~~测试目标明确。覆盖率 ≥ 95% 是量化验收标准。~~ **（2026-12-12 作废 —— 该数字从未被复现，见修订记录）**

负面
字段映射需一次性核对。39 个字段 + ache_params JSONB 与两个 HTRI 模板源的映射需人工核对，工作量大。

ReportStyle 配置复杂。空冷器和管壳式的表格结构差异大，heat_exchanger_type 分支逻辑增加渲染器复杂度。

JSONB 展开需处理。shell_side_json / tube_side_json / ache_params 需在渲染前展开为平铺字段，增加数据预处理步骤。

实施细节
数据源注册表条目
python
# app/services/report/datasources/heat.py

HEAT_DATASOURCE = DataSource(
    source_id="HEAT_EXCEL",
    name="换热器结果",
    fields=[
        # 基础字段（BASIC + DETAIL 共用）
        Field("TagNumber", "string", level="BASIC"),
        Field("Area", "number", level="BASIC"),
        Field("HeatDuty", "number", level="BASIC"),
        Field("OverallU", "number", level="BASIC"),
        # ... 其余 5 个 BASIC 字段
        # DETAIL 专属字段
        Field("LMTD", "number", level="DETAIL"),
        Field("MTD_Correction", "number", level="DETAIL"),
        Field("ShellFlowRate", "number", level="DETAIL"),
        Field("TubeFlowRate", "number", level="DETAIL"),
        Field("ShellPressureDrop", "number", level="DETAIL"),
        Field("TubePressureDrop", "number", level="DETAIL"),
        # 几何字段（按类型分叉）
        Field("TubeOD", "number", level="DETAIL", exchanger_type="SHELL_TUBE"),
        Field("BundleWidth", "number", level="DETAIL", exchanger_type="AIR_COOLER"),
        # ... 其余几何字段
        # 热阻字段
        Field("ShellSideResistance", "number", level="DETAIL"),
        Field("TubeSideResistance", "number", level="DETAIL"),
        # ... 其余热阻字段
        # JSONB 展开字段
        Field("shell_side_json.density", "number", level="DETAIL"),
        Field("tube_side_json.reynolds", "number", level="DETAIL"),
        Field("ache_params.fan_params.power", "number", level="DETAIL", exchanger_type="AIR_COOLER"),
    ],
)
ReportStyle 配置
python
# app/seeds/report_styles/heat_default.json

{
  "report_type": "HEAT",
  "detail_level": "DETAIL",
  "heat_exchanger_type": "SHELL_TUBE",
  "table_layout": {
    "columns": [
      {"field": "TagNumber", "alias": "位号", "width": 80},
      {"field": "HeatDuty", "alias": "热负荷", "width": 100},
      {"field": "ShellInletTemp", "alias": "壳程进口", "width": 80},
      {"field": "TubeInletTemp", "alias": "管程进口", "width": 80}
    ],
    "sections": [
      {"title": "基础信息", "fields": ["TagNumber", "Service", "Type"]},
      {"title": "热工参数", "fields": ["HeatDuty", "Area", "OverallU", "LMTD"]},
      {"title": "壳程", "fields": ["ShellInletTemp", "ShellOutletTemp", "ShellFlowRate", "ShellPressureDrop"]},
      {"title": "管程", "fields": ["TubeInletTemp", "TubeOutletTemp", "TubeFlowRate", "TubePressureDrop"]},
      {"title": "几何参数", "fields": ["ShellID", "TubeOD", "TubeLength", "BaffleSpacing"]},
      {"title": "热阻分布", "fields": ["ShellSideResistance", "TubeSideResistance", "WallResistance", "FoulingResistance"]}
    ]
  }
}
覆盖率验证
text
# pcs-backend/scripts/report_heat_coverage.py
# 用法：uv run python scripts/report_heat_coverage.py sample/A-101.xls sample/131-E-102-EOR.xls
# 退出码：0 未回归 / 1 已回归 / 2 缺输入

⚠️ **这里没有 95% 的断言**，也**不能**改成断言 0。
覆盖率工具恒绿比没有工具更坏 —— 它让人以为还在守着。
现为**基线 + 回归容差**：涨随便涨（补字段/修映射），跌超 2pp 才报。

  实测基线（--scope main，即每个文件的主输出表）：
    模板口径 64.9%（48/74 条标签）
    注册口径 53.0%（44/83 个已登记字段）

风险与缓解风险与缓解
风险	概率	影响	缓解
39 字段与 HTRI 模板源映射不完整	中	覆盖率不达标	开发期做逐字段核对，生成映射对照表；缺失字段补入注册表
ache_params JSONB 键未定义完整	中	空冷器 DETAIL 报表缺字段	以 HTRI Xace 输出为基准定义 ache_params 键清单
空冷器与管壳式字段命名冲突	低	ReportStyle 分支混乱	使用 exchanger_type 元数据标记字段，渲染器按类型过滤
ReportStyle 配置过于复杂，用户难维护	中	用户不愿用	P8c 交付样式管理 UI，按换热器类型预置模板，用户只需微调
覆盖率测试只比名字不比语义	低	假通过	覆盖率测试同时校验字段类型和单位，name + type + unit 三元组比对
待验证事项
□ heat_results 39 字段的完整清单（需从 ORM 模型确认）
□ ache_params JSONB 的完整键清单（需从 SUP-009 或 HTRI Xace 输出确认）
□ HTRI 121-A-101.xls 的 33 列字段清单（空冷器模板源）
□ HTRI 131-E-102-EOR.xls 的 23 列字段清单（TEMA 管壳式模板源）
□ 空冷器与管壳式的 ReportStyle 差异字段清单
□ 覆盖率测试的自动化实现
与相关 ADR 的关系
ADR	关系
ADR-P8-001	双模板通过 ReportStyle 配置实现，符合全直接生成模式裁决
SUP-009 V1.0	本 ADR 是 SUP-009 在 REPORT_BUILDER 数据源层面的落地裁决
SPEC-P8 V1.2 P8-OPEN-006	本 ADR 关闭该待确定问题

## 修订记录

### 2026-12-12 — 放弃「DETAIL 字段覆盖率 ≥ 95%」验收目标

**决策者**：用户（明确指令「放弃95%这个目标」）

**为什么放弃**。P8c c5 用真实参考文件实测（`sample/A-101.xls` +
`sample/131-E-102-EOR.xls`，均可由 `scripts/report_heat_coverage.py`
复现）：

| 口径 | 数值 |
|---|---|
| 模板口径（认得几项，主表） | **64.9%**（48/74 条标签）|
| 注册口径（覆盖几项） | **53.0%**（44/83 个已登记字段）|

即便把 11 条已知缺口**全部**补进数据模型，模板口径也只到 **73%**。

原目标的 95% 有三处对不上，**没有一处能被复现**：

1. **数量级对不上**：计划写「33 列 / 23 列」，而提取到的主表标签是
   50 / 25、合并 74。差的不是几个字段，是**分母定义本身**。
2. **分母口径从未写明**：是「模板字段数」还是「我们已登记字段数」？
   两者在同一份文件上差 11.9 个百分点。
3. **HTRI/TEMA 模板里相当一部分内容不属于规格书字段**：壁温分布、
   两相含量、翅片面积比、风机几何校核比 —— 客户不需要，
   把它们算进分母就注定了达不到 95%。

换句话说：95% 大概是在一个**更窄的定义**下达成的，而那个定义没有被记录。
追一个无法复现的数字，等于让人去改数据模型去凑分母。

**改成什么**。不再是「追覆盖率」，而是**防回归**：

- 记录两条实测基线（模板 64.9% / 注册 53.0%），各留 2pp 容差
- 覆盖率**上涨永远不报失败**（补字段、修映射都是好事）
- 下跌超容差才报 —— 抓的是「有人改坏了」
- ⚠️ **不是**把目标改成 0：那会让工具恒绿

**本 ADR 的其余决策全部不变**：detail_level 双分级（BASIC 9 /
DETAIL 全量）、双套 ReportStyle、字段用真实 ORM 列名、
`heat_exchanger_type` 分组。这些都已实现且有测试。

**仍然待办**（不因放弃目标而消失）：11 条缺口的分类见 `TODOS.md`
TODO-058（其中 A 类 6 条是真实的数据模型缺口）、
ACHE 翅片几何缺失见 TODO-056。
