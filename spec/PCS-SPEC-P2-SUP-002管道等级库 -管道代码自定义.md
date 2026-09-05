P2 增补 Spec——管道等级库 + 管道代码自定义（合并版）
文档编号：PCS-SPEC-P2-SUP-002
版本：V1.2（2026-09-05 定稿：七项待裁决全部落定——PC-OPEN-06/07、SYM/FMT/INT-OPEN，见 §0.5；V1.1 为实施对齐版，V1.0 为初稿）
日期：2026-09-05
状态：已定稿（作为 P2 追加 Sprint 实施依据）
依赖：SPEC-P2 V1.4、Plan Design 主文档、D29–D34 裁决、P2 Sprint 1.9 计划（docs/superpowers/plans/2026-09-04-p2-sprint-1.9.md）、三源种子（pcs-backend/app/seeds/pipe_classes_*.json）
范围：管道等级库（CATEGORY_5 子集）+ 管道代码（物流符号表 + 格式模板）项目级自定义

目录
第 0 部分：实施对齐（V1.1 新增）

第一部分：管道等级库

第二部分：物流符号表（STREAM SYMBOLS）

第三部分：管道代码格式模板

第四部分：实施计划

第五部分：测试策略

第六部分：待裁决问题

附录 A：管道等级索引总表

附录 B：物流符号表初始数据

第 0 部分：实施对齐（V1.1 新增）

0.1 绑定语义裁决（用户，2026-09-05）

管道计算选等级时**按项目绑定**：每个项目从 project_pipe_classes 启用清单中选等级；项目可自建管道库（source=PROJECT）；等级编码**不跨项目归一**（各项目沿用自身编码体系，如 BEP 的 A1B、Kaimen 的 150C10F01RF、PPG 的 U4 并存）；公司级 class_id 全局唯一。本 SUP §2.2 的项目级独立命名空间模型（项目内 class_name 唯一、不占公司级码空间）与该裁决兼容。

0.2 已落地现状（截至 2026-09-05）

- **三源种子 71 等级已入库** `pcs-backend/app/seeds/`（JSON 源 + 导入用 xlsx + kaimen 重生成脚本 `scripts/extract_pipe_classes_kaimen.py`）：
  - Worley BEP 4.3 Rev 0 → 6 等级 COMPANY_STD（A1B/A1E/A2B/G1E/A1F/A2F）
  - INEOS Kaimen ABS IFC（SPC-0004-C1 + PSI 索引）→ 54 等级 PROJECT（含 12 夹套组合，core Design Condition 为等级上限）
  - Worley PPG 反应器 MRQ-0001（CC07121065B-SPC-0002-0）→ 11 等级 PROJECT（U1-U8/P1-P3）
- **P2 Sprint 1.9**（进行中）已/将落地本 SUP 的薄层子集：1.9.1 service（CRUD + 作废单向 + 在用不可删）≈ PC-3 子集；1.9.2 API（5 端点 + 分配 + DELETE 保护）≈ PC-6 子集；1.9.6 Excel 导入（单 Sheet 12 列模板）+ 三源导入验证 ≈ PC-5 子集。**3 态（DRAFT/ACTIVE/OBSOLETE）**为 1.9 现状，5 态接入是本 SUP 增量。
- 附录 A 的 PPG 样表已按源文档核对修正（U4 大口径 DN350-900 壁厚为 **STD**，材料 API 5L Gr.B；V1.0 误记 "10"）。

0.3 现状 vs 目标态 schema 差异表（PC-1 迁移依据）

| 项 | P0 已入库（现状） | 本 SUP 目标态（§2） | 处置建议 |
|---|---|---|---|
| 公司级 PK | `class_id String(20)` 自然码（字典表11；piping_results.material_class FK 引用；三源种子按码入库） | UUID PK + class_name 全局唯一 | **建议保留自然码 PK**，class_name 加全局唯一索引（PC-OPEN-07） |
| base_material | 无（material_standard str100 承载） | 独立列 | 增列迁移，种子回填 |
| allowable_stress | `allowable_stress_json` JSONB | varchar 引用 COMMON 表名 | **建议保留 JSONB**（可内嵌引用表名 + 覆写值，信息量更大），SUP §2.1 相应放宽 |
| branch_table | `branch_table_json` JSONB | varchar 引用 | 同上，保留 JSONB |
| version | str50 | int | 增列 version_seq int 或保留 str50（PC-1 定） |
| status | 3 态 | 5 态 | 接入方式待裁决（PC-OPEN-06） |
| 项目级表 | `project_pipe_classes` 复合 PK(project_id,class_id) + enabled + custom_override_json，轻量关联 | 独立 UUID PK + source_class_id FK 可空 + 项目内 class_name 唯一 + override/snapshot 双 JSON + 项目级 5 态 | 结构迁移：扩列（class_name/snapshot_json/status）+ 现复合 PK 行回填（source_class_id=原 class_id，override 迁自 custom_override_json）；`enabled` 语义并入 status |
| 项目创建 fork | 无（1.9.2 仅手工 assign） | 模板默认列表自动 fork + 快照 | PC-4 + INT-1 |

0.4 已完成阶段修补评估（结论）

- **P0（schema）**：不回修。上述差异统一由本 SUP Sprint 的 PC-1 一次迁移收口（含 TimestampMixin 三列纪律，见 .wolf/cerebrum Do-Not-Repeat）。
- **P2 Sprint 1.9（进行中）**：不返工。其 3 态 + assign 模型是 PC-3/PC-4/PC-6 的薄实现；SUP Sprint 到位后将 assign 语义升级为 fork/快照、3 态并入 5 态（迁移兼容：DRAFT/ACTIVE→DRAFT、OBSOLETE→OBSOLETE，PENDING/APPROVED 新增）。
- **P1（状态机框架）**：无涉，可直接复用 ConfigStateMachine。

0.5 裁决落定（V1.2，用户 2026-09-05）

| 编号 | 裁决 | 要点 |
|---|---|---|
| PC-OPEN-06 | **5 态接入选 a：pipe_classes 挂 ConfigAsset** | 复用 ConfigStateMachine 与 submit/approve/publish/obsolete 端点（CATEGORY_5）；审计枚举复用 CONFIG_ASSET_*，前版草案的 PIPE_CLASS_CREATED/IMPORTED 两枚取消 |
| PC-OPEN-07 | **保留 class_id 自然码 + 新增 asset_id UUID FK → config_assets** | piping_results FK 不破坏；ConfigAsset.name 存 class_name（或 class_id - class_name）；**pipe_classes.status 为镜像列**——ConfigStateMachine 在 transition 落库时同事务同步写，保证免 join 直查；class_id 放宽为 varchar(50) |
| 3 态→5 态迁移 | PC-1 一次收口 | 薄层实际 3 态 DRAFT/ACTIVE/OBSOLETE → DRAFT/PUBLISHED/OBSOLETE（PENDING/APPROVED 迁移后为空集）；ACTIVE→PUBLISHED |
| SYM-OPEN-01 | 符号表走 5 态审批（挂 ConfigAsset，CATEGORY_5） | 项目级符号表亦 5 态，审批链为项目内角色 |
| FMT-OPEN-01 | auto_increment 默认 scope = project_id + stream_symbol | 同项目同介质独立递增（P 从 001、WA 也从 001，互不干扰） |
| FMT-OPEN-02 | 管道代码格式变更触发下游 STALE（data_lineage 传播） | 影响所有已生成代码的解释，必须标记 |
| INT-OPEN-01 | 符号表 + 格式模板均归 CATEGORY_5 | ConfigAsset 增 asset_subtype 区分（PIPE_CLASS / STREAM_SYMBOL / PIPE_CODE_TEMPLATE；若不增列则用 name 前缀） |

第一部分：管道等级库（Pipe Classes）
1. 范围与定位
管道等级库是 CATEGORY_5 标准数据库的首个落地子集。本部分定义其两层结构（公司级标准库 + 项目级覆写）、输入方式、验证引擎和审批流程。

1.1 两层结构
text
公司级 pipe_classes（标准库）
    ↓ fork（项目创建时或运行中）
项目级 project_pipe_classes（可覆写）
1.2 三种模式
模式	场景	存储
完全继承	项目使用公司标准等级，不做修改	不创建项目级行，直接引用公司级 ID
基于公司级 fork	项目修改个别字段	override_json 仅存被覆写字段 + snapshot_json 快照
项目全新创建	特殊介质/工况	override_json 存全部字段，source_class_id=NULL
1.3 快照绑定（D29）
项目 fork 时完整复制公司级 PUBLISHED 字段到 snapshot_json。公司级后续变更不影响已 fork 的项目。完全继承模式始终引用公司级当前 PUBLISHED 版本。

2. 数据模型
（V1.2 注：下表已按 §0.5 裁决修订——class_id 保留自然码 PK、新增 asset_id FK 挂 ConfigAsset、status 为 5 态镜像列；allowable_stress/branch_table 按 §0.3 建议保留 JSONB。与 P0 已入库 schema 的差异迁移见 §0.3。）
2.1 公司级 pipe_classes
字段	类型	约束	说明
class_id	varchar(50) PK	—	等级自然码（U1、A1B、150C10F01RF），piping_results.material_class FK 引用
asset_id	UUID FK → config_assets	新增（PC-OPEN-07）	状态机挂靠：category=CATEGORY_5，asset_subtype=PIPE_CLASS（INT-OPEN-01）；ConfigAsset.name 存 class_name
class_name	varchar(100)	UNIQUE（全局）	等级名称，如 A1A、U4
material_standard	varchar(50)	NOT NULL	设计标准，如 ASME B31.3
base_material	varchar(100)	NOT NULL	材料牌号，如 A106 Gr.B，支持斜杠分隔组合
corrosion_allowance	numeric(4,2)	≥ 0，≤ 6.5，NOT NULL	腐蚀裕量 mm，0 = 工程判断无腐蚀
design_pressure	numeric(8,2)	> 0，≤ 42	设计压力 MPa
design_temperature	numeric(8,2)	-196 ~ 650	设计温度 °C
allowable_stress_table	varchar(100)	引用 COMMON	许用应力表名
dn_series_json	json	NOT NULL	{"min":15, "max":900, "series":[...]}
sch_series_json	json	NOT NULL	{"DN15":[40,80,160], ...}
flange_class	varchar(20)	枚举	150#~2500#
fitting_type	varchar(200)	自由文本	斜杠分隔枚举组合
branch_table	varchar(100)	引用 COMMON	分支表名
source	varchar(200)	—	来源说明
version	int	—	版本号
status	varchar(20)	5 态镜像列	DRAFT→PENDING→APPROVED→PUBLISHED→OBSOLETE；与 config_assets.status 同事务同步（ConfigStateMachine transition 落库时写）
created_by/at	—	—	审计字段
2.2 项目级 project_pipe_classes
字段	类型	约束	说明
project_class_id	UUID PK	—	项目级唯一标识
project_id	FK → projects	NOT NULL	所属项目
source_class_id	FK → pipe_classes	可空	公司级来源（NULL = 全新创建）
class_name	varchar(100)	UNIQUE(project_id, class_name)	项目内等级名
override_json	json	NOT NULL	仅存被覆写字段
snapshot_json	json	fork 时 NOT NULL	完整公司级字段快照
status	varchar(20)	5 态	项目级审批状态
2.3 JSON 结构
override_json（仅存与快照不同的字段）：

json
{
  "corrosion_allowance": 3.2,
  "flange_class": "300#"
}
snapshot_json（fork 时完整复制）：

json
{
  "class_name": "A1A",
  "material_standard": "ASME B31.3",
  "base_material": "A106 Gr.B",
  "corrosion_allowance": 1.6,
  "design_pressure": 4.0,
  "design_temperature": 200,
  "dn_series_json": {"min":15, "max":600, "series":[...]},
  "sch_series_json": {"DN15":[40,80,160], ...},
  "flange_class": "150#",
  "fitting_type": "对焊",
  "branch_table": "COMMON_BRANCH_TABLE_01"
}
2.4 有效值解析
text
项目级有效值 = snapshot_json ⊕ override_json 顶层键覆写 ⊕ JSON 字段逐键深合并
3. 输入方式
3.1 结构化表单
新建：空白表单，全部字段可编辑

Fork：表单预填公司级值，仅修改需覆写字段，后端自动计算 override_json 和 snapshot_json

实时校验：字段失焦触发 PC-V 系列

3.2 Excel 批量导入
模板结构：

text
Sheet 1: 等级列表
ClassID | ClassName | MaterialStandard | BaseMaterial | DesignPressure | DesignTemp | CorrosionAllowance | FlangeClass | FittingType | AllowableStressTable | BranchTable

Sheet 2: Sch 系列（长表）
ClassID | DN | Sch列表（逗号分隔）
流程：上传 → 行级校验 → 预览（正确/错误/警告分组）→ 确认 → 事务写入（任一行失败全量回滚）

3.3 JSON/API 导入（P3 延后）
与 Excel 共用验证引擎。

4. 验证引擎
4.1 结构完整性（PC-V 系列）
ID	规则	严重度	时机
PC-V01	必填字段非空	ERROR	输入/提交/发布
PC-V02	dn_series 非空且 min ≤ max	ERROR	输入/提交/发布
PC-V03	sch_series 中每个 DN 存在于 dn_series	ERROR	输入/提交/发布
PC-V04	Sch 值 > 0	ERROR	输入/提交/发布
PC-V05	design_pressure 0~42 MPa	ERROR	输入/提交/发布
PC-V06	design_temperature -196~650°C	WARN	输入/提交/发布
PC-V07	corrosion_allowance ≥ 0 且 ≤ 6.5，不允许 NULL	ERROR	输入/提交/发布
PC-V08	flange_class 在枚举内	ERROR	输入/提交/发布
PC-V09	项目级 class_name 项目内唯一	ERROR	输入/提交/发布
PC-V10	source_class_id 有效	ERROR	提交/发布
PC-V11	fitting_type 各分段在枚举内	ERROR	输入/提交/发布
4.2 工程一致性（PC-E 系列）
ID	规则	严重度	时机
PC-E01	碳钢且温度 > 400°C	WARN	提交/发布
PC-E02	150# 且压力 > 1.96 MPa	WARN	提交/发布
PC-E03	压力 > 法兰等级最大允许压力	ERROR	提交/发布
PC-E04	引用表不存在于 COMMON	ERROR	发布
PC-E05	DN > 600	WARN	提交/发布
PC-E06	fork 时覆写压力但未覆写法兰等级	WARN	输入/提交/发布
PC-E07	Sch 系列空但 DN 非空	ERROR	输入/提交/发布
法兰等级-压力对照表（38°C 基准）：

等级	最大允许压力 (MPa)
150#	1.96
300#	5.11
400#	6.81
600#	10.21
900#	15.32
1500#	25.53
2500#	42.55
4.3 项目上下文（PC-C 系列）
ID	规则	严重度	时机
PC-C01	项目级设计压力 ≤ 项目上限（若定义）	WARN	提交/发布
PC-C02	材料在项目允许列表内（若定义）	WARN	提交/发布
PC-C03	同名不同 source 的等级不可并存	ERROR	输入/提交/发布
PC-C04	被设备引用后不可删除	ERROR	发布
5. API
公司级
text
GET    /api/v1/pipe-classes
POST   /api/v1/pipe-classes
PUT    /api/v1/pipe-classes/{class_id}
POST   /api/v1/pipe-classes/import
POST   /api/v1/pipe-classes/validate
POST   /api/v1/pipe-classes/{class_id}/submit
POST   /api/v1/pipe-classes/{class_id}/approve
POST   /api/v1/pipe-classes/{class_id}/publish
POST   /api/v1/pipe-classes/{class_id}/obsolete
项目级
text
GET    /api/v1/projects/{project_id}/pipe-classes
POST   /api/v1/projects/{project_id}/pipe-classes
PUT    /api/v1/projects/{project_id}/pipe-classes/{id}
POST   /api/v1/projects/{project_id}/pipe-classes/validate
DELETE /api/v1/projects/{project_id}/pipe-classes/{id}
POST   /api/v1/projects/{project_id}/pipe-classes/{id}/submit
POST   /api/v1/projects/{project_id}/pipe-classes/{id}/approve
POST   /api/v1/projects/{project_id}/pipe-classes/{id}/publish
POST   /api/v1/projects/{project_id}/pipe-classes/{id}/obsolete
GET    /api/v1/projects/{project_id}/pipe-classes/effective/{class_name}
第二部分：物流符号表（STREAM SYMBOLS）
6. 范围与定位
物流符号（Stream Symbol）是管道代码中标识介质类型的短码前缀，如 P = PROCESS FLUID、WA = WASTE WATER HARMLESS。不同项目的介质体系不同，符号表必须允许项目级覆写。

7. 数据模型
7.1 公司级 stream_symbols
字段	类型	约束	说明
symbol_id	UUID PK	—	唯一标识
asset_id	UUID FK → config_assets	新增（SYM-OPEN-01/INT-OPEN-01）	状态机挂靠：CATEGORY_5，asset_subtype=STREAM_SYMBOL
symbol	varchar(10)	UNIQUE（全局）	符号，如 P、WA、WRr
name	varchar(200)	NOT NULL	含义，如 PROCESS FLUID
category	varchar(50)	—	分类（PROCESS/UTILITY/WASTE/VENT/...）
is_active	boolean	DEFAULT true	是否启用
status	varchar(20)	5 态	审批状态
version	int	—	版本号
created_by/at	—	—	审计字段
7.2 项目级 project_stream_symbols
字段	类型	约束	说明
project_symbol_id	UUID PK	—	唯一标识
project_id	FK → projects	NOT NULL	所属项目
source_symbol_id	FK → stream_symbols	可空	公司级来源（NULL = 项目自建）
symbol	varchar(10)	UNIQUE(project_id, symbol)	项目内符号
name	varchar(200)	NOT NULL	项目内含义
category	varchar(50)	—	分类
is_active	boolean	DEFAULT true	是否启用
snapshot_json	json	fork 时	快照公司级原始值
status	varchar(20)	5 态	项目级审批状态
7.3 覆写规则
项目可增删符号、改含义、改符号本身

同一项目内 symbol 唯一

完全继承：直接使用公司级当前 PUBLISHED 符号表

Fork：复制公司级符号表到项目级，快照绑定，随后自由修改

8. 验证规则（SYM 系列）
ID	规则	严重度
SYM-V01	symbol 非空且长度 1~10	ERROR
SYM-V02	name 非空且长度 ≤ 200	ERROR
SYM-V03	项目内 symbol 唯一	ERROR
SYM-V04	category 若填写必须在预定义枚举内	WARN
SYM-V05	项目级 fork 后，snapshot_json 不可为空	ERROR
SYM-V06	符号被管道代码格式模板引用后，不可删除（仅可 is_active=false）	ERROR
9. API
text
# 公司级
GET    /api/v1/stream-symbols
POST   /api/v1/stream-symbols
PUT    /api/v1/stream-symbols/{symbol_id}
POST   /api/v1/stream-symbols/{symbol_id}/submit
POST   /api/v1/stream-symbols/{symbol_id}/approve
POST   /api/v1/stream-symbols/{symbol_id}/publish
POST   /api/v1/stream-symbols/{symbol_id}/obsolete

# 项目级
GET    /api/v1/projects/{project_id}/stream-symbols
POST   /api/v1/projects/{project_id}/stream-symbols
PUT    /api/v1/projects/{project_id}/stream-symbols/{id}
DELETE /api/v1/projects/{project_id}/stream-symbols/{id}
POST   /api/v1/projects/{project_id}/stream-symbols/{id}/submit
POST   /api/v1/projects/{project_id}/stream-symbols/{id}/approve
POST   /api/v1/projects/{project_id}/stream-symbols/{id}/publish
POST   /api/v1/projects/{project_id}/stream-symbols/{id}/obsolete
第三部分：管道代码格式模板
10. 范围与定位
管道代码（Pipe Code / Line Number）是管线在图纸和计算书中的唯一标识。其格式（分段结构、顺序、分隔符、每段规则）在不同项目间有显著差异，必须允许项目级自定义。

11. 数据模型
11.1 公司级 pipe_code_templates
字段	类型	约束	说明
template_id	UUID PK	—	唯一标识
asset_id	UUID FK → config_assets	新增（INT-OPEN-01）	状态机挂靠：CATEGORY_5，asset_subtype=PIPE_CODE_TEMPLATE；格式变更经 data_lineage 触发下游 STALE（FMT-OPEN-02）
template_name	varchar(100)	UNIQUE	模板名称
description	varchar(500)	—	说明
format_definition_json	json	NOT NULL	分段定义（见 §11.3）
status	varchar(20)	5 态	审批状态
version	int	—	版本号
created_by/at	—	—	审计字段
11.2 项目级 project_pipe_code_configs
字段	类型	约束	说明
config_id	UUID PK	—	唯一标识
project_id	FK → projects	NOT NULL	所属项目
source_template_id	FK → pipe_code_templates	可空	公司级模板（NULL = 全新创建）
config_name	varchar(100)	UNIQUE(project_id, config_name)	项目内配置名
format_definition_json	json	NOT NULL	分段定义（全量替换）
snapshot_json	json	fork 时	公司级模板快照
status	varchar(20)	5 态	项目级审批状态
11.3 format_definition_json 结构
json
{
  "separator": "-",
  "segments": [
    {
      "key": "unit",
      "label": "单元号",
      "type": "enum",
      "values": ["100", "200", "300", "400"],
      "length": 3,
      "required": true,
      "position": 1
    },
    {
      "key": "stream_symbol",
      "label": "介质符号",
      "type": "stream_symbol",
      "length": 10,
      "required": true,
      "position": 2
    },
    {
      "key": "sequence",
      "label": "序列号",
      "type": "auto_increment",
      "length": 3,
      "start_value": 1,
      "step": 1,
      "padding": "zero",
      "required": true,
      "position": 3
    },
    {
      "key": "phase",
      "label": "相态",
      "type": "enum",
      "values": ["L", "G", "V", "S", "M"],
      "length": 1,
      "required": false,
      "position": 4
    }
  ]
}
11.4 段类型
type	说明	配置参数
stream_symbol	引用物流符号表（项目级优先）	length
enum	枚举	values, length
auto_increment	自动递增	start_value, step, padding
free_text	自由文本	length, regex
constant	固定值	value
delimiter	分隔符	separator
11.5 格式示例
模板	格式	示例
标准四段式	{unit}-{stream_symbol}-{sequence}-{phase}	100-P-001-L
五段式	{project}-{unit}-{stream_symbol}-{sequence}-{phase}	PX-100-P-001-L
简化三段式	{stream_symbol}-{sequence}-{phase}	P-001-L
12. 验证规则（FMT 系列）
ID	规则	严重度
FMT-V01	必须有且仅有一个 auto_increment 段	ERROR
FMT-V02	必须有且仅有一个 stream_symbol 段	ERROR
FMT-V03	分段 key 唯一	ERROR
FMT-V04	相邻两段不能均无分隔符	ERROR
FMT-V05	总长度 ≤ 50 字符	ERROR
FMT-V06	枚举段 values 非空	ERROR
FMT-V07	stream_symbol 段引用符号在项目有效符号表内	ERROR
FMT-V08	项目级配置名唯一	ERROR
FMT-V09	auto_increment 段建议位于末位或靠近末位	WARN
13. 代码生成与验证
13.1 生成逻辑
text
1. 解析项目级 format_definition_json（若无则用公司级）
2. 按 position 顺序拼接各段
3. stream_symbol 段：从项目级符号表（或公司级）取值验证
4. auto_increment 段：默认 scope = project_id + stream_symbol（FMT-OPEN-01 裁决），可配置
5. 返回完整代码 + 各段解析结果
13.2 并发保障
auto_increment 段在事务内 SELECT ... FOR UPDATE 行锁，保证同一项目内不重复。UNIQUE(project_id, pipe_code) 兜底。

14. API
text
# 公司级模板
GET    /api/v1/pipe-code-templates
POST   /api/v1/pipe-code-templates
PUT    /api/v1/pipe-code-templates/{template_id}
POST   /api/v1/pipe-code-templates/{template_id}/submit
POST   /api/v1/pipe-code-templates/{template_id}/approve
POST   /api/v1/pipe-code-templates/{template_id}/publish
POST   /api/v1/pipe-code-templates/{template_id}/obsolete

# 项目级配置
GET    /api/v1/projects/{project_id}/pipe-code-configs
POST   /api/v1/projects/{project_id}/pipe-code-configs
PUT    /api/v1/projects/{project_id}/pipe-code-configs/{id}
POST   /api/v1/projects/{project_id}/pipe-code-configs/{id}/submit
POST   /api/v1/projects/{project_id}/pipe-code-configs/{id}/approve
POST   /api/v1/projects/{project_id}/pipe-code-configs/{id}/publish
POST   /api/v1/projects/{project_id}/pipe-code-configs/{id}/obsolete

# 生成与验证
POST   /api/v1/projects/{project_id}/pipe-codes/generate
       # body: {"stream_symbol": "P", "unit": "100", "phase": "L"}
POST   /api/v1/projects/{project_id}/pipe-codes/validate
       # body: {"pipe_code": "100-P-001-L"}
15. 与 CATEGORY_1 项目模板的集成
项目模板新增字段：

text
pipe_code_template_id       FK → pipe_code_templates
stream_symbol_table_id      FK → stream_symbols
default_pipe_class_ids      FK[] → pipe_classes
项目创建流程：

text
1. 读取项目模板引用
2. 若模板指定了默认管道等级列表，自动 fork 快照
3. 若项目需要自定义管道代码格式/符号表，创建向导提供 fork 入口
4. fork 后创建项目级配置，快照绑定
5. 后续管道代码生成/校验按项目级配置执行；不存在则回退公司级
第四部分：实施计划
16. 任务分解
（V1.1 注：P2 Sprint 1.9 已落地薄层——1.9.1 service（3 态 CRUD/作废/在用保护）≈ PC-3 子集、1.9.2 API ≈ PC-6 子集、1.9.6 Excel 导入（单 Sheet 12 列）+ 三源 71 等级种子 ≈ PC-5 子集；下表为 SUP Sprint 增量口径。）
任务 ID	内容	依赖	工时
PC-1	管道等级差异迁移 + ORM（按 §0.3 差异表：base_material/version 扩列、项目级表重构 + 现有行回填；PC-OPEN-06/07 裁决后定稿）	无	0.5 天
PC-2	管道等级验证引擎（22 条规则）	PC-1	1 天
PC-3	管道等级公司级 CRUD + 5 态接入	PC-1	1 天
PC-4	管道等级项目级 fork + 快照 + 有效值解析	PC-3	1 天
PC-5	管道等级 Excel 批量导入	PC-2, PC-3	1.5 天
PC-6	管道等级 API + 测试	PC-3, PC-4	1 天
SYM-1	物流符号两表 migration + ORM	无	0.5 天
SYM-2	符号表 CRUD + 项目级 fork + 覆写 + 验证	SYM-1	1 天
SYM-3	符号表 API + 测试	SYM-2	0.5 天
FMT-1	管道代码模板两表 migration + ORM	无	0.5 天
FMT-2	格式模板 CRUD + 验证规则（FMT 系列）	FMT-1	1 天
FMT-3	代码生成器 + 验证器 + 并发保障	FMT-1, SYM-2	1.5 天
FMT-4	管道代码 API + 测试	FMT-2, FMT-3	1 天
INT-1	CATEGORY_1 项目模板集成（3 个新字段）	PC-3, SYM-2, FMT-2	0.5 天
INT-2	前端表单组件（等级编辑 + 符号表管理 + 格式设计器）	PC-3, SYM-2, FMT-2	2.5 天
INT-3	端到端集成测试	全部	1 天
合计			15.5 天（约 3 周）
第五部分：测试策略
测试层	内容	目标
单元测试	验证引擎每条规则独立测试	100% 覆盖（PC-V 11 + PC-E 7 + PC-C 4 + SYM-V 6 + FMT-V 9 = 37 条）
单元测试	快照绑定（fork → snapshot → override → 有效值）	管道等级 4 路径 + 符号表 2 路径 + 格式模板 2 路径
API 测试	每端点 happy + failure	≥ 2 用例/端点
集成测试	Excel 导入 → 预览 → 确认 → 事务回滚	全流程
集成测试	管道代码生成并发（10 并发同一项目）	全部唯一
集成测试	等级/符号/模板被引用后不可删除	3 用例
集成测试	项目模板 fork 全链路（等级 + 符号表 + 格式）	1 用例
第六部分：待裁决问题
编号	问题	建议	状态
PC-OPEN-01	法兰等级-压力温度降额曲线	P2 按 38°C 基准，P3 扩充	已裁决 D30
PC-OPEN-02	项目级全新创建双审适用范围	统一双审，后续按规模配置	已裁决 D31
PC-OPEN-03	完全继承模式自动跟随公司级更新	是，始终引用当前 PUBLISHED	已裁决 D32
PC-OPEN-04	等级库与 CATEGORY_1 默认列表联动	项目创建时自动 fork	已裁决 D33
PC-OPEN-05	base_material 多材料存储	varchar 斜杠分隔，P3 结构化	已裁决 D34
PC-OPEN-06	公司级 5 态接入方式	a) pipe_classes 挂 ConfigAsset（CATEGORY_5）复用 ConfigStateMachine 与 submit/approve/publish 端点	已裁决 2026-09-05（选 a；审计复用 CONFIG_ASSET_*，PIPE_CLASS_* 两枚取消）
PC-OPEN-07	公司级 PK 形态	保留 class_id 自然码（varchar(50)），新增 asset_id UUID FK → config_assets；status 为镜像列同事务同步	已裁决 2026-09-05
SYM-OPEN-01	符号表是否需要审批流，还是项目内自由维护	走 5 态审批（挂 ConfigAsset CATEGORY_5；项目级审批链为项目内角色）	已裁决 2026-09-05
FMT-OPEN-01	auto_increment 递增 scope 默认值	默认 scope = project_id + stream_symbol（同介质独立递增）	已裁决 2026-09-05
FMT-OPEN-02	管道代码变更是否触发下游 STALE	是，通过 data_lineage 传播	已裁决 2026-09-05
INT-OPEN-01	管道等级库与物流符号表是否都并入 CATEGORY_5，还是符号表独立成类	均归 CATEGORY_5，ConfigAsset 以 asset_subtype 区分（PIPE_CLASS/STREAM_SYMBOL/PIPE_CODE_TEMPLATE）	已裁决 2026-09-05
附录 A：管道等级索引总表
（V1.1：PPG MRQ-0001 样表，已按源文档核对修正；完整三源 71 等级见 `pcs-backend/app/seeds/pipe_classes_{bep_rev0,kaimen_20048a,ppg}.json`。Status 列为 SUP 目标态语义——种子导入 1.9.6 后初始为 DRAFT。）
Piping Class	Service	Design Press. (MPa)	Design Temp. (°C)	Flange Class	Base Material	Corr. Allow. (mm)	DN 系列	Sch 系列（简写）	Branch Table	Status
U1	Compressor Air	1.0	60	150#	A106 Gr.B / GALV（DN≥80 为 A53 Gr.B/GALV）	0	15~200	DN15~50: XS; DN80~200: STD	Branch 2	PUBLISHED
U4	Cooling Water	1.0	110	150#	A106 Gr.B（DN≥350 为 API 5L Gr.B SAW）	1.6	15~900	DN15~40: XS; DN50~900: STD	Branch 1	PUBLISHED
P2	Vents/Drains	1.0	200	150#	A312 TP304L	0	15~900	DN15~40: 40S; DN50~750: 10S; DN800~900: SCH10（EFW，B36.10）	Branch 1	PUBLISHED
P3	Tempered Water	1.9	200	300#	A312 TP304L	0	15~100	DN15~100: 40S	Branch 1	PUBLISHED
附录 B：物流符号表初始数据
symbol	name	category
P	PROCESS FLUID	PROCESS
AA	AMINO ACID	PROCESS
AF	AMMONIA LIQUID	PROCESS
ATa	ETHANOL	PROCESS
AW	NH4OH	PROCESS
ES	ACETIC ACID	PROCESS
EH	ACETIC ANHYDRIDE	PROCESS
MN	METHANOL	PROCESS
ME	METHIONINE	PROCESS
MU	MOTHER LIQUOR	PROCESS
IPa	ISOPROPANOL	PROCESS
SC	HYDROCHLORIC ACID (31%)	PROCESS
SCr	HYDROCHLORIC ACID (10-14%)	PROCESS
Ssa	SULFURIC ACID 98%	PROCESS
SSd	SULFURIC ACID DILUTED	PROCESS
NA	NaOH	PROCESS
DM	STEAM	UTILITY
GSH	HIGH PRESSURE NITROGEN	UTILITY
GS	NITROGEN	UTILITY
GSD	NITROGEN FOR INERTIZATION	UTILITY
LD	PLANT AIR	UTILITY
LT	INSTRUMENT AIR	UTILITY
LV	COMBUSTION AIR	UTILITY
WD	CONDENSATE	UTILITY
WE	DEMINERALIZED WATER	UTILITY
WF	FIRE FIGHTING WATER	UTILITY
WH	HOT WATER	UTILITY
WG	COLD WATER	UTILITY
WB	CITY WATER	UTILITY
WQb	BOILER FEED WATER	UTILITY
WRr	COOLING WATER RETURN	UTILITY
WRs	COOLING WATER SUPPLY	UTILITY
WU	ULTRAFILTRATED WATER	UTILITY
QS	BRINE	UTILITY
WA	WASTE WATER HARMLESS	WASTE
WC	WASTE WATER SANITARY	WASTE
WS	WASTE WATER CONTAMINATED	WASTE
KR	STORM SEWER	WASTE
LA	VENT	VENT
VA	VACUUM	VENT
FH	FILTER AID	OTHER
KB	ACTIVATED CARBON	OTHER
本增补 Spec 状态：待评审（V1.1）。确认后作为 P2 追加 Sprint（约 3 周）的实施依据；PC-OPEN-06/07 与既有 SYM/FMT/INT-OPEN 各项裁决完成后进入 writing-plans。
