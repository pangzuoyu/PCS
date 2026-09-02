PCS 本体论与语义关系研究说明（V1.6）
项目	内容
文件标识	PCS-RESEARCH-001
当前版本	V1.6
状态	✅ 已批准
批准日期	2026-09-03
编制部门	工艺部 / 信息化联合项目组
适用对象	P3–P8 开发者、架构决策者
关联文档	DICT-ALL-003 V3.4、ADR 系列、DF-001、SPEC-P1/P2/P3/P4
变更来源	V1.5 + grilling 9 项裁决（2026-09-03）
1. 执行摘要
核心结论：

不引入 OWL 推理机和 RDF 三元组。 吸收本体论的"结构化思维"——把领域知识从代码中显式化、关系化、可查询化，但完全基于 PostgreSQL + Python 原生能力实现，不增加新依赖、不引入双存储、不引入运行时推理。

经多轮对抗性评估与评审（V1.0 → V1.1 → V1.2 → V1.3 → V1.4 → V1.5），本说明已锁定全部设计决策。V1.5 整合了三项独立意见的裁决（元数据驱动表单立即做、领域模型改形态做、规则清单暂不做），可作为 P3–P8 开发的正式约束输入。

V1.5 的核心增量：

变更项	裁决	落地位置
4.3 元数据驱动表单生成	✅ 立即做，提前到 P3	§2.5（已裁决）+ §5.3（P3 实施要点）
4.1 领域模型文档化	✅ 做，改为 CI 生成视图	§5.1（P4 Task 0-Design 交付物）+ §6（规则 8）
4.2 规则清单显式化	⏸️ 暂不做，P7 评估	§3.5（决策规则细化）
2. 已裁决事项（约束输入）
2.1 完整 OWL / RDF / SWRL——不引入
理由	说明
表达力不匹配	SWRL 无法表达 PCS 核心的状态机转移（9态 × 13事件）
技术栈冲突	推理引擎生态（Java）与 Python + FastAPI 栈不匹配
运行时不可接受	推理会拖垮 P4 计算迭代（管径迭代 + 本体一致性检查）
抽象层爆炸	"字典-模型-代码"三层漂移已消耗大量精力，不可引入第四层
2.2 dependency_type 与 physical_semantics——分离设计，物理语义推迟到 P7
字段	存储	消费方	何时启用
dependency_type	单一字符串：CALCULATION / REFERENCE / MANUAL_OVERRIDE / ESTIMATED	CIA 引擎（P1 已有）	P1-MVP 已启用
physical_semantics	JSONB 数组：候选枚举见 §3.1	P8 报表 / 语义查询	P7 评估后裁定
关键约束（V1.5 正式裁决）：

P4 Task 0 仅在 data_lineage 表中预留 physical_semantics JSONB 列（nullable）。

@lineage 装饰器不暴露 physical_semantics 参数。P4–P6 开发者不填写该字段，永远为 NULL。

P7 启动前，基于 P4–P6 积累的审计数据（见 §3.2 的度量指标定义），决策是否启用语义过滤。

CALCULATES 已从物理语义枚举中移除——它与 dependency_type=CALCULATION 语义重叠，保留会造成分类学边界模糊。

§2.2 的枚举为"候选枚举"，激活待 P7 裁定（与 §3.1 保持措辞一致）。

2.3 preconditions 数组（公式前置条件）——采纳，P2 实施
在 formula_definitions.content_json 中增加 preconditions 数组：

json
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
变量来源约束（V1.5 正式裁决）：

域	标识	说明	允许
调用方输入	input.*	调用 FormulaEngine 时传入的参数	✅
公式参数	params.*	formula_definitions.parameters_json 中定义	✅
公式输出	result	仅用于 result >= 0 类后置检查	✅
上下文（DB 查询）	context.*	任何需要访问数据库的变量	❌ 禁止
治理规则（V1.5 定稿）：

规则	说明
常量治理	condition 中的数值常量（如 425）必须来自 params.*，且 params.* 可溯源到 CoefficientTables（系数库），不得硬编码在 condition 字符串中
求值顺序	input.* 和 params.* 在计算前检查；result 在计算后检查（用于 result >= 0 类断言）
违反策略	V1 冻结为 REJECT-only（WARN 作为未来扩展，V1 不支持）
表达式语言	condition 必须复用 FormulaEngine 的受限 AST 解析器——不引入第二套表达式语言，不增加新的安全面
表达力边界声明（V1.5 定稿）：

preconditions 支持：数值比较（<=, >=, ==, !=）、枚举判断（material == 'CS'）、范围判断（velocity BETWEEN 5 AND 30）、AND/OR 组合

暂不支持：跨字段算术约束（design_press - operating_press >= 0.5）、循环/迭代、DB 查询

若 P2 Sprint 1.2 发现跨字段约束是刚需：P2 Sprint 1.2 发现刚需时，先**记录需求到需求文档**（含路径、约束、示例）；P2 期间调用方临时检查代码须标注 `@legacy-P4`；P4 Task 0 启动守卫函数落地。守卫函数可访问完整记录对象，preconditions 保持纯函数约束。

2.4 全局属性字典表 attribute_definitions——不采纳
原提议	裁决	替代方案
新建 attribute_definitions 表，运行时查 DB	否决	P8 报表引擎使用 Pydantic model_json_schema() 从 ORM 模型生成元数据（见 §3.4 的约束条件）
2.5 元数据驱动表单生成（V1.5 新增）——采纳，P3 实施
属性	说明
裁决	✅ 立即做，提前到 P3
实施方案	P3 表单使用 Pydantic model_json_schema() 从 ORM 模型生成标准 JSON Schema，前端据此渲染表单。字段定义一次，验证、表单、报表三处消费。
事实来源锁定	源必须是 Pydantic Schema，不是 DICT Markdown。与 V1.3 §3.4 的报表元数据方案保持一致——model_json_schema() 从代码生成，DICT 是文档视图而非主源。
布局层配合	纯 JSON Schema 不含布局信息。需增加一层 UI Schema（如 x-rjsf-* 扩展或自定义 ui: 字段）表达字段分组、显隐联动、布局顺序。P3 设计阶段需预留此层。
条件显示逻辑	若涉及"phase==GAS 时显示压缩因子"类条件显示：① 优先方案：在 P3 前端组件中按业务模块硬编码（条件显示数量少、变化慢时，硬编码比配置文件更易维护）；② 若条件显示数量 > 10 个，再评估是否引入声明式配置（如复用 preconditions 机制扩展 ui_constraints）。不做先验抽象。
实施要点：

P3 开发期间，每个需要表单的 ORM 模型（streams、equipment_list 等）必须有对应的 Pydantic Schema，且该 Schema 包含 Field(description=...) 注解。

前端表单组件接收 schema + uiSchema 两个 props，根据 uiSchema 控制布局。

禁止从前端硬编码字段名列表（除非字段数 ≤ 3 且永不变化）。

2.6 领域模型文档化（V1.5 新增）——采纳，以"CI 生成视图"形态落地
属性	说明
裁决	✅ 做，但形态改"代码生成视图"，而非手写文档
落地时机	P4 Task 0-Design
生成源	SQLAlchemy metadata（实体/字段）+ data_lineage 表（关系）+ RECORD_TYPE_REGISTRY（模块映射）
产出	docs/domain_model.md，含 Mermaid ERD + 领域约束清单 + 禁止关系清单
维护方式	CI 自动生成。每次 PR 重新生成 domain_model.md，diff 直接可见，零维护成本。
内容要求：

实体关系图（Mermaid ERD） ：展示 16 个核心实体（Stream → StatePoint → PipingResult → PumpResult → EquipmentList → Deliverable）及其关系

领域约束清单：列出关键约束（如"泵的 NPSHa ≥ NPSHr + 0.5m"），每个约束标注代码位置引用

禁止关系清单：**唯一允许人工编辑的小节**，附于 CI 生成内容之后。明确列出"不允许的关系"（如 piping_results 不可直接引用 streams——必须通过 stream_state_points；physical_semantics 在 P4–P6 不可写入等）。声明性知识的价值不仅在于"可以做什么"，更在于"明确不能做什么"。理由：CI 无法表达负向关系（SQLAlchemy 没有"禁止 FK"原生概念），需独立维护。

认知负荷检查点（P4 Task 0-Design 软建议，**非硬验收项**）：

domain_model.md 产出后，找一位未参与 P4 开发的开发者（如 P5 负责人），仅凭该文档理解"一条物流从 SIM 导入到被 PIPE 引用，需要经过哪些状态转换和校验"。若 10 分钟内无法讲清，则文档需迭代。本检查点为**软建议**：架构委员会评审时关注总量可读性，不作为 P4 Task 0-Design 的硬验收项；硬验收项保留"架构委员会批准"。

3. 待研究事项（已锁定触发时机）
3.1 physical_semantics 完整枚举设计
属性	说明
性质	设计决策
触发时机	P7 启动前（不作为 P4 前置条件）
候选枚举（V1.5 定稿）	PRESSURIZES / HEATS / SEPARATES / RESTRICTS / TRANSPORTS / CONTROLS（CALCULATES 已移除）
待研究内容	16 个模块的典型物理语义映射表；与 EQUIP_LIST 同步关系的语义表达；以及 "字段级血缘"是否比"模块级语义"更适合解决 CIA 过传播问题（见 §3.2b）
定稿约束	若 P7 评估决定不做语义过滤，则本枚举设计可取消，physical_semantics 列永久留空
备注	若 P7 决定启用 physical_semantics，届时同步建立"语义标签注册表"（semantic_labels 枚举或配置表）作为 DataLineage.physical_semantics 的值域权威来源。当前阶段不预设统一语义模型。
3.2 物理语义在 CIA 传播中的应用——决策机制
拆分说明：

子项	性质	触发时机	状态
3.2a CIA API 形状预留	设计决策	P4 Task 0-Design	✅ 已定稿（见 §5）
3.2b 语义过滤功能实现	功能实现 + 数据驱动决策	P7 启动前	待评估（决策规则见下方）
3.2b 的决策机制与度量指标（V1.5 正式裁决）：

（1）度量指标定义（成因编号 A/B/C）

编号	成因	说明	physical_semantics 能否缓解
A	元数据字段干扰	上游改动的是备注、说明等字段，但 record_hash 覆盖了它们——假阳性，hash 粒度过粗	❌ 不能
B	下游不消费该字段	上游改了工程数据，但下游计算不消费该字段——假阳性，血缘边语义过宽	✅ 能（通过语义谓词过滤）
C	dependency_type 分类过粗	REFERENCE 边被当作 CALCULATION 处理	❌ 不能（需修正 dependency_type 本身）
（2）审计数据要求（P4 Task 0-Code 强制执行）

P4 开发期间，StateMachineService 在每次 STALE 解除时，必须向 audit_logs.detail_json 写入以下三项字段：

字段	类型	说明	当前状态
stale_resolution_path	string	"RESOLVE_NO_CHANGE" 或 "RESOLVE_CHANGED"	✅ StateMachineService 已通过 transition 参数区分
hash_changed	boolean	重算前后 record_hash 是否变化（系统计算，用户不可覆盖）——权威信号	⚠️ 当前未强制记录，需在 P4 Task 0-Code 中规范
changed_fields	array[string]	上游变更涉及哪些字段组（如 ["design_pressure", "design_temp"]）	❌ 未覆盖，需在 P4 Task 0-Code 中新增（数据流见 §5.1）
审计字段一致性约束：

若 hash_changed=true 但 stale_resolution_path="RESOLVE_NO_CHANGE" → 审计告警（用户动作与系统事实矛盾）

若 hash_changed=false 但 stale_resolution_path="RESOLVE_CHANGED" → 审计告警

两条信息均保留（不删除任何一方），供 P7 评估时分析"用户误判率"

（3）决策规则（V1.5 修正：三元决策出口）

P7 评估时，从审计日志中提取三项数据，分别统计 A/B/C 三种成因的贡献度：

主导成因	决策出口	说明
成因 B 贡献 > 50%	✅ 启用 physical_semantics 语义过滤	语义谓词可精准过滤"下游不消费该字段"的假阳性
成因 A 主导	🔧 修正 record_hash 范围	排除纯元数据字段（备注、说明），不动 physical_semantics
成因 C 主导	🔧 审计并修正 dependency_type 分类	REFERENCE 边不应触发 CIA 全传播，不动 physical_semantics
三者均 < 50%	⏸️ 默认不启用，触发重评条件	连续 6 个月比例超阈值则重新评估
决策出口与 §3.2b(5) 的"字段级血缘并列评估"闭环：若成因 B 由字段级假阳性主导，字段级血缘可能比模块级语义更优，评估时应并列考虑。

阈值说明：>50% 为**默认建议值**，不是硬约束。架构委员会可基于 P7 实测数据调整阈值（如降为 30%）或偏离决策规则作出裁决。连续 6 个月超阈值触发重评。

（4）启用成本（V1.5 定稿）

即使 P7 决定启用语义过滤，physical_semantics 数据的获取方式必须同时评估：

方案	说明	粒度局限与风险
方案 A（自动推断）	基于 source_type → target_type 映射表自动打标签	⚠️ 与模块级语义同样粗。若主导成因是字段级假阳性，存在"把真实传播也滤掉"的召回风险。成本-收益分析必须包含精度/召回评估，并与 §3.2b(5) 的"字段级血缘"方案形成闭环
方案 B（人工标注）	开发标注工具或通过 API 手动补标签	人工成本高，但精度可控
方案 C（放弃）	若 A/B 皆不可行，则 physical_semantics 列保持空置	零成本，放弃语义过滤
P7 评估报告必须包含上述三个方案的成本-收益-精度-召回分析。

（5）"字段级血缘"作为替代方案并列评估

模块级语义（PRESSURIZES / HEATS）是粗粒度标签，可能无法精准命中字段级假阳性。P7 评估时应将字段级血缘（下游消费了上游哪些字段）作为替代/补充方案并列评估。字段级血缘的优点：

不需要本体词汇表

直接命中"下游不消费该字段"导致的假阳性

在数据工程中是成熟方案，实现成本可控

3.3 preconditions 完整表达力
属性	说明
性质	设计决策 + 功能实现
触发时机	P2 Sprint 1.2（同步完成）
已定稿约束	变量来源仅限 input.* / params.* / result（见 §2.3）；常量必须走 params.* 且可溯源至系数库；求值顺序明确（pre + post）；V1 违反策略冻结为 REJECT-only；表达式语言复用 FormulaEngine 的受限 AST；表达力边界声明已定稿（见 §2.3）
待研究	AND/OR 组合的语法细节、违反时的 PcsError 格式（在已定稿约束的框架内细化）
3.4 从 ORM 模型自动生成报表元数据
属性	说明
性质	功能实现
触发时机	P8 启动前
实施方案	Pydantic model_json_schema() 从 ORM 模型生成 JSON Schema（含 description 字段，来源于 ORM Column 注释）
约束条件（V1.5 定稿 + V1.6 增补）	① 每个 *_result 表的 JSONB 载荷，必须有对应的嵌套 Pydantic 模型（如 HeatResults.design_parameters → HeatDesignParametersSchema），且该模型必须包含 Field(description=...) 注解；② P4 Task 0-Code 起加 ORM Column comment ↔ Pydantic Field description 静态对比 CI 测试（漂移即 fail），同步规则——单一事实来源为 Pydantic Schema（它是 JSONB 子结构的唯一载体），ORM 模型的 comment 需与之一致但非主源；③ P8 前评审现有 JSONB 字段的 Pydantic Schema 覆盖情况
不实施方案	从 DICT-ALL-003 Markdown 解析（已否决）
3.5 规则注册表（V1.5 更新）
属性	说明
性质	文档 + 评估
触发时机	P7 启动前（与 V1.3 §3.5 一致）
决策规则（V1.5 补充 + V1.6 增补）	① P4–P6 期间，不建立手动维护的规则清单（避免文档漂移）；② 仅在 PR/ADR 模板中加一行"本次新增/修改的业务规则"，作为**轻量级意图记录（审计线索，非规则清单本体）**——规则清单本体（CI 自动生成）由 P7 评估后决定方案 A 或 B；③ P7 评估规则数量：若规则数量 > 20 条，启用 方案 A（CI 自动生成） ——通过 inspect/ast 扫描 @rule 装饰器自动生成清单；若规则数量 ≤ 20 条，启用 方案 B（ADR 附录） ——规则记录在相关 ADR 中，不单独维护文件
方案 A 技术预留	P4 Task 0-Design 预留 RuleCollector 接口骨架（app/core/rules_registry.py），P4–P6 开发者只需按约定使用 @rule 装饰器，P7 的 CI 自动生成即可直接消费。P7 前不填充实现，仅预留接口形态。
4. 明确不研究事项（排除清单）
主题	排除理由
Neo4j / 图数据库	破坏 PostgreSQL 单库事务（commit_or_rollback）
HermiT / Pellet 推理机	运行时推理拖垮 P4 计算
Protégé 本体编辑器	PCS 的语义层仅为轻量级枚举与 JSON Schema，通过 Git PR + 代码审查即可完成协作定义，无需引入独立的图形化工具链及 .owl 文件管理负担
RDF 三元组存储	53 表 Schema 已覆盖
SWRL 规则语言	表达不了过程性规则
描述逻辑（SROIQ）	工艺工程师不可读
手动维护的规则清单	与 V1.5 §3.5 决策规则一致——P7 前不建立手动清单，避免文档漂移
5. P4 Task 0 正式范围（V1.5 定稿 + V1.6 修订）
5.1 P4 Task 0-Design（设计阶段）
触发时机：P3 完成、P4 编码开始前。

产出	内容
CIA 传播 API 形状	propagate_from_source(source_type, source_id, dependency_type=None) 签名确定
@lineage 最终签名	语法扩展（D4）+ source_hash 抓取（D5）—— 不包含 physical_semantics 参数
RECORD_TYPE_REGISTRY	完整映射表，覆盖 P4–P6 全部计算模块（漂移防护见 §5.2 三方比对 CI 测试）
physical_semantics 列声明	data_lineage 表预留 JSONB nullable 列，但装饰器不暴露、P4 不写入
审计日志字段规范	定义 audit_logs.detail_json 中 stale_resolution_path、hash_changed、changed_fields 的 JSON Schema（见 §3.2b）
diff 采集与传递链路设计	明确 changed_fields 的采集点（源记录变更批准时）、传递载体（CIA 扫描任务携带的 payload）、落库时机（下游 STALE 标记时）。评估方案 A（源批准时 diff + CIA 载荷携带）与方案 B（源快照保留 + 解除时 diff），在 ADR 中记录裁决结果
RuleCollector 接口预留	app/core/rules_registry.py 骨架，预留 @rule 装饰器接口形态（P7 前不填充实现）
ADR 记录	输出新 ADR 或更新现有 ADR，记录上述 API 形状和约束
验收：设计文档经架构委员会批准，方可进入 Code 阶段。**注**：原 §2.6 "10 分钟陌生人理解" 列为**软建议**，不作为本节硬验收项。

5.2 P4 Task 0-Code（编码阶段）
产出	内容
Alembic 迁移	data_lineage 增加 physical_semantics JSONB nullable 列；列注释标注 @P7-eval-point
装饰器扩展	实现 D4（多 sources 语法）+ D5（source_hash 自动抓取）
importlinter 契约	数据流分层约束（D8）
CIA 传播 API	实现预留的 dependency_type 过滤参数（P4–P6 不传该参数，保持全传播）；在相关代码中预留 # P7: 语义过滤入口 注释锚点
审计日志扩展	StateMachineService 写入 STALE 解除审计时，强制包含 stale_resolution_path、hash_changed、changed_fields 三项字段
三方比对 CI 测试	RECORD_TYPE_REGISTRY 与 SQLAlchemy metadata、状态机配置三方比对，防止三处定义各自演化
Pydantic ↔ ORM 同步 CI（V1.6 增补）	ORM Column comment ↔ Pydantic Field description 静态对比 CI 测试，漂移即 fail（与三方比对 CI 同级硬性）
P7 评估锚点	在 DataLineage 模型 physical_semantics 字段 docstring 中注明"P7 评估语义过滤时启用"
测试	兼容性测试 + 新语法测试 + importlinter 测试 + 三方比对测试 + 审计字段测试 + Pydantic ↔ ORM 同步 CI
验收：ruff check / mypy / pytest 全绿；DICT-ALL-003 更新为 V4.0（标注 physical_semantics 列存在）；三方比对测试与 Pydantic ↔ ORM 同步 CI 通过。

5.3 P3 元数据驱动表单实施要点
触发时机：P3 开发期间（与 §2.5 同步落地）。

产出	内容
Pydantic Schema 覆盖	确认 streams、equipment_list 等需要表单的 ORM 模型有对应的 Pydantic Schema（含 Field(description=...) 注解）
UI Schema 层预留	前端表单组件接收 schema + uiSchema 两个 props，uiSchema 包含字段分组、显隐联动、布局顺序。P3 设计阶段确定 uiSchema 格式（如 x-rjsf-* 扩展或自定义 ui: 字段）
条件显示策略	若涉及 phase=='GAS' 类条件显示：数量少时在 P3 前端组件中硬编码；数量 > 10 个时再评估声明式方案（如复用 preconditions 机制扩展 ui_constraints）
表单 ↔ Schema 静态对比 CI（V1.6 增补）	前端表单组件产出的 JSON Schema 与后端 Pydantic Schema model_json_schema() 输出必须在 CI 静态对比。漂移即 fail
禁止事项	前端不得硬编码字段名列表（除非字段数 ≤ 3 且永不变化）
验收：P3 表单字段列表与 Pydantic Schema 保持一致（CI 自动校验），无硬编码字段名。

6. 实施约束（关键规则速查）
规则	说明
规则 1	@lineage 不暴露 physical_semantics 参数。P4–P6 开发者无需知道此字段存在。
规则 2	preconditions 只允许 input.* / params.* / result，禁止 context.*（不访问 DB）。常量必须走 params.* 且可溯源至系数库。
规则 3	dependency_type 与 physical_semantics 职责分离：前者用于 CIA 传播（P1），后者用于语义查询（P7 评估）。CALCULATES 已从物理语义枚举中移除。
规则 4	P8 报表元数据从 Pydantic model_json_schema() 生成。JSONB 嵌套字段必须有对应的嵌套 Pydantic 模型。不查 DB 表，不解析 Markdown。
规则 5	physical_semantics 的启用与否，由 P7 基于审计日志中 分层度量数据（见 §3.2b）决策，不先验假设。决策出口为三元（语义过滤 / 字段级血缘 / 都不做），不设"永久不做"硬边界。
规则 6	P4 Task 0-Code 必须包含三方比对 CI 测试：RECORD_TYPE_REGISTRY 与 SQLAlchemy metadata 和状态机配置一致。
规则 7	P4 Task 0-Code 必须扩展审计日志，确保 STALE 解除时写入 stale_resolution_path、hash_changed、changed_fields。
规则 8（V1.5 新增 + V1.6 增补）	领域模型文档由 CI 生成，不手动维护。docs/domain_model.md 从 SQLAlchemy metadata + data_lineage + RECORD_TYPE_REGISTRY 自动生成。每次 PR 重新生成，diff 可见，零维护成本。**禁止关系清单是 domain_model.md 中唯一允许人工编辑的部分**（CI 无法表达负向关系），其余内容由 CI 生成。
规则 9（V1.5 新增）	P3 表单由 Pydantic Schema 驱动，不手动维护字段列表。前端从 model_json_schema() 获取字段定义。UI 布局由独立的 uiSchema 控制，不侵入业务模型。
规则 10（V1.5 新增）	规则清单 P7 前不手动建立。**PR/ADR 模板中"本次新增/修改的业务规则"一行属于审计线索（非规则清单本体）**。P7 评估规则数量后，再决定启用 CI 自动生成（>20 条）或 ADR 附录（≤20 条）。
规则 11（V1.6 新增）	ORM ↔ Pydantic Schema 漂移 CI 是硬性 CI 项；P3 表单组件 schema 与后端 Pydantic Schema model_json_schema() 输出静态对比 CI，漂移即 fail（与规则 6 同级）。
7. 对其他文档的影响
文档	影响	时机
DICT-ALL-003	升级至 V4.0：data_lineage 增加 physical_semantics 列	P4 Task 0-Code 完成后
ADR 系列	新增或更新 ADR：记录 dependency_type / physical_semantics 分离原则；记录 changed_fields diff 采集与传递链路设计裁决；记录 RuleCollector 接口预留	P4 Task 0-Design 完成后
DF-001	更新数据流约束：physical_semantics 作为语义标签层，不影响数据流拓扑	P4 Task 0-Design 完成后
P2 Plan	需增补 §2.3 的 preconditions 治理条款（常量溯源系数库、pre/post 求值顺序、REJECT-only、复用受限 AST）。P2 Sprint 1.2 启动前完成 scope 核对。	P2 Sprint 1.2 启动前
P3 SPEC	需在 P3 开发期间确认 Pydantic Schema 覆盖情况，并为前端表单预留 UI Schema 接口。	P3 开发期间
CLAUDE.md / 开发者模板	新增"领域模型文档生成"章节，说明 domain_model.md 的生成方式和维护约定。	P4 Task 0-Design 完成后
8. 版本历史
版本	日期	修改内容
V1.0	2026-09-02	初始版本：记录 Ontology 讨论结论 + 待研事项
V1.1	2026-09-02	修正触发时机：P4 Task 0 拆分为 Design + Code 两阶段
V1.2	2026-09-02	回应四项批判性审查
V1.3	2026-09-02	整合七项评审意见
V1.4	2026-09-02	整合三项风险应对 + 七项评审意见最终修编
V1.5	2026-09-02	整合三项独立意见裁决：① 4.3 元数据驱动表单——采纳，提前到 P3（新增 §2.5 + §5.3），事实来源锁定 Pydantic Schema，布局由独立 UI Schema 控制；② 4.1 领域模型文档化——采纳，形态改为"CI 从 metadata/lineage 自动生成"（新增 §2.6 + §6 规则 8），含禁止关系清单 + 认知负荷检查点；③ 4.2 规则清单显式化——暂不做，P7 评估规则数量后再定方案（更新 §3.5），仅 PR/ADR 模板加一行规则记录；④ 新增 §6 规则 9（表单驱动）+ 规则 10（规则清单决策）
V1.6	2026-09-03	grilling 9 项裁决：① §3.5 PR/ADR 行明确为审计线索非规则清单本体；② §3.2b(3) 50% 阈值明确为默认建议值，架构委员会可调；③ §3.4 + §5.2 新增 Pydantic ↔ ORM 静态对比 CI；④ §2.6 + §5.1 认知负荷检查点降级为软建议；⑤ §2.3 跨字段约束 fallback 修订为"P2 记录需求，P4 落地守卫函数，临时检查标 @legacy-P4"；⑥ §2.6 + §6 规则 8 禁止关系清单明确为唯一允许人工编辑的小节；⑦ §2.6 取消"约 200 行"约束；⑧ §5.3 + §6 规则 11 表单 ↔ Pydantic Schema 静态对比 CI；⑨ §5.1/§5.2 取消时间预算表述（~3h / ~1天）
本文件为正式批准版本（V1.6）。P3 开发可据此启动元数据驱动表单方案；P4 Task 0 可据此启动设计阶段。
