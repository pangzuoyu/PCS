工艺专用综合计算软件——Claude Code分步开发计划
文档版本：V1.3（V1.2 incorporate SUP-007 两层签署与变更管理，2026-08-28；V1.3 align SUP-002 V1.4 管道等级库/物流符号/管道代码 + P3-SIM V1.1 五样例与炼油扩展单元，2026-09-06）
编制日期：2026-08-27（V1.3 增量更新 2026-09-06）
开发工具：Claude Code（Anthropic）
人类职责：架构决策、公式验证、代码审查、验收

总览：开发阶段划分
阶段	名称	周期	核心产出	依赖
P0	项目初始化与基础设施	第1-3周	项目骨架、数据库模型、认证、CI/CD	—
P1	横切关注点框架	第3-5周	状态机、版本管理、血缘、输入清单、工作区	P0
P2	CONFIG配置中枢	第4-6周	公式引擎、系数库、模板管理、审批流	P0, P1
P3	基础数据层	第6-8周	PMS、SIM、COMMON、PIPE_CLASS	P0, P2
P4	核心计算引擎（第一批）	第8-12周	FLASH、PIPE、PIPE_NET、PUMP	P3
P5	设备计算模块（第二批）	第12-16周	VESSEL、SEP_EQUIP、PSV、HEAT	P4
P6	高级计算模块（第三批）	第16-19周	CV、RESTRICTION、FLARE_SYS、COOL_TOWER、PSYCHRO、OPEN_CHANNEL	P4, P5
P7	集成模块	第19-21周	EQUIP_LIST、UTIL、EQUIP_LIB、供应商数据	P4, P5, P6
P8	报表与输出	第21-23周	REPORT、REPORT_BUILDER	P7
P9	工作流与权限	第23-25周	签署流程、变更影响分析、ADMIN	P1, P7
P10	AI预留与测试部署	第25-28周	AI接口预留、全流程测试、部署文档	全部
P0：项目初始化与基础设施（第1-3周）
目标
建立可运行的前后端骨架、数据库Schema、认证集成、CI/CD配置，定义AI辅助开发规范。

任务分解
0.1 SPEC解析与架构确认
输入：将全部SPEC文档（主文档 + 3份增补 + 2份数据字典 + 5份模块数据字典）喂给Claude Code

Claude Code动作：

提取所有实体、关系、状态机定义

生成模块依赖图（Mermaid格式）

生成REST API端点清单初稿

生成数据库表清单及字段类型建议

人工审查：确认技术栈（Python 3.12 + FastAPI + PostgreSQL 16）、验证模块依赖关系正确性

0.2 项目结构生成
前端：

bash
npm create vite@latest frontend -- --template react-ts
# 安装：antd, zustand, react-router-dom, @ant-design/icons
后端：

bash
# 使用uv创建Python项目
uv init backend
# 核心依赖：fastapi, uvicorn, sqlalchemy, alembic, pydantic
# 计算依赖：chemicals, thermo, coolprop, scipy, sympy, fluids
# 工具：ruff, mypy, pytest, arq, redis
0.3 数据库模型生成
数据源：DICT-001（数据字典总则）+ DICT-002（设备表字典）+ 附加模块数据字典（管道、泵、换热器、空冷器）

Claude Code生成：所有SQLAlchemy模型类（V1.2 按 SUP-007：业务表无 version 字段、含 sign_status 9 态 + record_hash + 批准/变更/弃用字段组；不创建 xxx_History）

基础表：Projects, Streams（含 StreamSignStatus 门禁字段）, DataLineage（哈希锚定）, Workspaces, ProjectInputChecklist

配置表：ConfigAssets, ConfigVersions, FormulaDefinitions, CoefficientTables, TemplateFiles, ProjectTemplates, PipeClasses, ProjectPipeClasses, EquipmentTypeCodes

业务表：PipingResults, PumpResults, PSVResults, VesselResults, HeatResults, CVResults, EquipmentList, FlashResults, PipeNetworkResults, RestrictionResults, FlareSystemResults, CoolingTowerResults, PsychroResults, SepEquipResults, FiltrationResults, CostEstResults, OpenChannelResults

交付物与变更（SUP-007 新增）：Deliverables, DeliverableVersions, DeliverableRecordBindings, ChangeNoticeDetails, NumberingTemplates, DocNoSequences, CustomerApprovalAttachments, RecordChangeSnapshots, SignatureMatrices, ProjectSignatureMatrixBindings, VersionSequenceConfigs, LicenseConfigs

流程表：SignRecords, AuditLogs, AiAuditLog, DocumentChunks, ReportDefinitions, ReportExecutionLogs

人工审查：

JSONB字段使用是否合理

外键约束和索引设计

版本快照表（xxx_History）的生成策略

0.4 认证集成
Claude Code生成：

Authlib + LDAP集成代码

JWT token生成与验证中间件

前端登录页面（Ant Design Form）

角色映射（AD安全组 → 系统角色）

人工审查：验证与公司AD域的兼容性，MFA支持

0.5 CI/CD配置
生成：GitHub Actions或Azure DevOps Pipeline

yaml
stages:
  - lint: ruff + mypy
  - test: pytest + coverage
  - build: docker build
  - deploy: 部署到测试环境
包含：代码覆盖率阈值（≥80%）、Golden Test基准测试

0.6 CLAUDE.md规范文件
内容：

项目架构约定

编码规范（Ruff规则）

常用命令

数据库迁移流程

模块开发模板

P1：横切关注点框架（第3-5周）
目标
实现所有模块共用的横切能力：状态机、版本管理、数据血缘、输入清单、工作区管理。

任务分解
1.1 状态机引擎（V1.2：两层）
SPEC参考：SUP-007 §3（SUP-005 矩阵仅交付物层）

Claude Code生成：

记录层状态枚举：DRAFT, IN_APPROVAL, CHECKED, CHECK_REJECTED, STALE, CHANGE_PENDING, CHANGED, REVERSAL_PENDING, OBSOLETE（9 态）+ StreamSignStatus（4 态）

批准深度引擎（record_approval_config 逐步推进，approval_step/depth/role）

状态迁移函数（含 STALE 哈希判定、变更闭环、分级撤销、弃用）

状态机单元测试（覆盖所有迁移路径）

状态变更审计日志记录器

人工审查：逐条对照SUP-007验证迁移规则，特别是"STALE→哈希判定→凭证关闭"链路

1.2 交付物与变更单管理（V1.2：替代原版本管理系统）
SPEC参考：SUP-004（序列）+ SUP-007 §4/§5

Claude Code生成：

Rev 生成器（版本序列配置驱动）+ 序列内校验

doc_no 编号模板引擎（段解析、scope 原子序号分配）

交付物快照绑定（仅 CHECKED 可绑定、record_hash 固化、AFFECTED 判定）

变更单（deliverable_type=CHANGE_NOTICE）创建/签署/自动关闭绑定记录

变更前快照服务（进入 STALE/CHANGE_PENDING 时保存、放弃/撤销时恢复）

版本历史查询API、Rev 对比（快照哈希 diff）
1.3 数据血缘框架
SPEC参考：3.3.5节

Claude Code生成：

DataLineage表CRUD操作

血缘记录自动写入装饰器

血缘查询API（向上追溯/向下追溯）

血缘图数据格式转换（供前端可视化）

前端：React Flow血缘图组件骨架

1.4 输入清单管理
SPEC参考：3.3.14节

Claude Code生成：

ProjectInputChecklist模型和API

输入项状态管理（NOT_STARTED/IN_PROGRESS/VERIFIED/ASSUMED/NOT_APPLICABLE）

完备性检查引擎

假设数据标识与传播逻辑

前端：输入清单仪表盘组件

1.5 工作区管理
SPEC参考：3.3.15节

Claude Code生成：

Workspaces模型和API

工作区类型（FORMAL/PERSONAL/TEMPORARY）隔离逻辑

数据导入正式项目流程

自动归档/清理任务（ARQ定时任务）

1.6 变更影响分析引擎（V1.2：哈希不匹配检测）
SPEC参考：3.3.9节 + SUP-007 §8（ADR-0003/0005）

Claude Code生成：

基于 data_lineage 的哈希不匹配定位（source_record_hash ≠ 变更记录新哈希 → target 即受影响下游；级联在下游重算时逐级传播）

已绑定/未绑定记录分流：STALE 路径（自动快照、只读）vs 直接回 DRAFT

设备记录状态联动执行器（来源→设备记录传导）

STALE 确认重算流程 API（哈希判定分流：恢复 / CHANGE_PENDING）

关键SQL：

sql
SELECT DISTINCT dl.target_type, dl.target_id
FROM data_lineage dl
WHERE dl.source_id = :changed_id
  AND dl.source_record_hash <> :new_hash;
P2：CONFIG配置中枢（第4-6周）
目标
实现公式、系数、模板、标准数据库的统一管理，提供审批流和热更新能力。

任务分解
2.1 配置资产基础框架
SPEC参考：3.2.17节

Claude Code生成：

ConfigAssets + ConfigVersions模型

六类资产（CATEGORY_1~6）的CRUD API

统一版本管理

审批流程（提交→审核→审定→发布）

2.2 公式管理（CATEGORY_2）
核心功能：

公式存储（LaTeX显示 + SymPy解析表达式）

公式编辑器后端API

公式解析与执行引擎（SymPy + 受限AST执行）

单元测试运行器

公式版本对比

热更新机制

安全约束：

python
ALLOWED_FUNCTIONS = {'sin','cos','tan','exp','log','sqrt','pow', ...}
# 禁止import、文件读写、网络访问
2.3 经验系数管理（CATEGORY_3）
Claude Code生成：

CoefficientTables模型

表格编辑器API（支持条件分行）

Souders-Brown K因子、推荐流速表等初始数据导入

2.4 模板文件管理（CATEGORY_4）
Claude Code生成：

TemplateFiles模型（.dotx, .xltx文件存储）

占位符自动解析

版本管理

2.5 标准数据库管理（CATEGORY_5）
包含：管道等级库、材料许用应力、物性数据

Claude Code生成：

PipeClasses模型和API

材料许用应力表（ASME B31.3 Table A-1数据导入）

Excel批量导入接口

（2026-09-06 增补 V1.3：管道等级库深化实施依据 = PCS-SPEC-P2-SUP-002 V1.4（追加 Sprint 17.5 天，约 3.5 周，详见 docs/PCS-PLAN-SUP-002-SPRINT）。

**已落地**（P2 Sprint 1.9 薄层）：pipe_classes service + 5 端点 + Excel 12 列模板导入 + 三源 71 等级种子（BEP 6 COMPANY_STD / Kaimen 54 PROJECT 含 12 夹套 / PPG 11 PROJECT，app/seeds/pipe_classes_*.json + xlsx + scripts/extract_pipe_classes_kaimen.py）。

**增量**（SUP Sprint）：
- 数据模型：pipe_classes 保留自然码 class_id varchar(50) PK + 新增 asset_id FK → config_assets（CATEGORY_5，asset_subtype=PIPE_CLASS），status 5 态镜像列同事务同步；新增 base_material varchar(100) NOT NULL；version 保留 str50 不迁 int（V1.4 修正）；project_pipe_classes 重构为 UUID PK + source_class_id + class_name UNIQUE(project_id, class_name) + override_json + snapshot_json + status 5 态
- 验证引擎：22 条规则（PC-V11 + PC-E7 + PC-C4），PC-E04 注入 common_tables 校验表名、PC-E06 fork 时 override 压力未覆写法兰 WARN、PC-V10 source_class_id 有效性（service 层）、PC-C04 is_in_use classmethod（查 piping_results.material_class FK）
- 5 态接入：公司级 pipe_classes 挂 ConfigAsset 复用 ConfigStateMachine + submit/approve/publish/obsolete 端点（审计复用 CONFIG_ASSET_*，PIPE_CLASS_* 两枚取消）；项目级不挂 ConfigAsset，使用轻量状态列 + ProjectPipeClassStateMachine + config_approvals.project_class_id 可空列写入审批记录
- 三种模式：完全继承（不建项目级行，直接引用公司级 PUBLISHED）/ 基于公司级 fork（snapshot_json + override_json 双 JSON 深层覆写）/ 项目全新创建（source_class_id=NULL，override_json 含全部字段）
- 物流符号表（第二部分）：公司级 stream_symbols + 项目级 project_stream_symbols（symbol_id UUID + asset_id FK，UNIQUE(project_id, symbol)，override_json 与等级对齐），6 条 SYM 验证规则
- 管道代码格式模板（第三部分）：公司级 pipe_code_templates + 项目级 project_pipe_code_configs，format_definition_json 含 segments（enum/stream_symbol/auto_increment/free_text/constant/delimiter 六型），9 条 FMT 验证规则
- 格式代码生成器（FMT-3）：auto_increment 段 scope 默认 project+symbol（同介质独立递增），事务内 SELECT FOR UPDATE 行锁 + UNIQUE(project_id, pipe_code) 兜底，FMT-SEQ-01 复用既有 NumberingService/DocNoSequence（不新建序列表）
- CATEGORY_1 项目模板集成（INT-1）：项目模板新增 pipe_code_template_id FK + project_template_pipe_classes 关联表（template_id, class_id）替换 default_pipe_class_ids FK[]
- 实施约束（V1.4 §0.6 裁决）：PC-FMT-01 dn_series_json.series 可选键；PC-FMT-02 sch_series_json 键=裸 DN 数字串+SchEntry；PC-FMT-03 flange_class 接受 150#/150Lb/PN25 三形式（PN 系合法但跳过 E02/E03 评估）；PC-FMT-04 列宽保持现状不收窄；EXCEL-01 Excel Sheet1 沿用 1.9.6 十二列模板（base_material 可选第 13 列）；INT-DROP-01 项目模板不增 stream_symbol_table_id 列（公司符号表无聚合实体，项目级走完全继承+按需 fork）
- 等级绑定语义（用户 2026-09-05 裁决）：管道计算选等级按项目绑定；项目可自建 PROJECT 级库；等级编码不跨项目归一，class_id 全局唯一 PK
- 三态→五态迁移（PC-1 一次收口）：DRAFT→DRAFT、ACTIVE→PUBLISHED、OBSOLETE→OBSOLETE，PENDING/APPROVED 迁移后为空集；新表迁移含 TimestampMixin 三列（created_by/created_at/updated_at）——见 .wolf/cerebrum Do-Not-Repeat
- 前端：INT-2 3.5 天（管道等级表单 + 符号表管理 + 拖拽式格式设计器），与 P2 Sprint 2 前端波合并

Sprint 执行顺序：PC-1 → PC-2 → PC-3 → PC-4 → PC-6 → SYM-1 → SYM-2 → SYM-3 → FMT-1 → FMT-2 → FMT-3 → FMT-4 → INT-1 → INT-3；INT-2 可后置；写作计划见 docs/PCS-PLAN-SUP-002-SPRINT。）

2.6 复用设备库管理（CATEGORY_6）
关联：EQUIP_LIB子系统（沉淀、审批、检索）

Claude Code生成：基础CRUD和检索API

P3：基础数据层（第6-8周）
目标
实现PMS、SIM、COMMON、PIPE_CLASS四个基础数据子系统。

任务分解
3.1 PMS项目基本信息
SPEC参考：3.2.1节 + BEDD数据结构（气象、地质、公用工程、排放、设计寿命等）

Claude Code生成：

BEDD_JSON的Pydantic模型（完整的BEDD数据结构，包括气象、水文、公用工程、排放限值、设计条件、安全消防、火炬、界面条件）

项目创建向导（4步）

项目模板调用（从CONFIG获取）

单位制联动逻辑

前端：项目创建表单、BEDD数据录入界面

3.2 SIM工艺模拟数据
SPEC参考：3.2.2节 + Streams表完整字段 + PCS-SPEC-P3-SIM V1.1（2026-09-06 五样例 + PRO/II 8.x 炼油版）

Claude Code生成：

PRO/II 双文件解析器（.inp 关键字驱动 + .out 固定宽度表格）

HYSYS/Aspen Plus/HTRI 解析器（P3/P4 补，仅预留路由）

物流数据表 API（Streams + composition_json + estimated/simulation_status/unreliable/tear_stream/zero_flow 标志位）

统一校验引擎（SIM-V 10 条 + SIM-E 4 条 + PR-V 14 条 + PRX-V 8 条 = 36 条；含 PRO/II 结构验证、双文件交叉验证、收敛状态分层导入）

组成归一化校核（容差 0.001）+ 物性缺失自动估算（COMMON 库：MW、临界 Tc/Pc、ω、标准密度；CoolProp：焓/粘度/导热系数；缺失估算 estimated=True 标记）

手动修改记录（user_provided_properties_json + calculated_properties_json + effective_properties_json 三 JSON，user 优先于 calculated；CALCULATED_PRIORITY_FIELDS 例外：molecular_weight/total_mass_flow/total_molar_flow 始终取 calculated）

反应数据存储（sim_reactions_defs 集 + REACTOR/CSTR SUMMARY）+ 扩展单元操作结果（REACTOR/CSTR/COMPRESSOR/SPLITTER/STCA/CALCULATOR 各自结果表 + sim_unit_op_results 基表）

冲突解决引擎（ConflictSeverity BLOCK/WARN/INFO + PropertyConflictResolver：硬冲突阻止保存、用户值优先物性类、计算值优先派生类）

物流校核状态（sign_status 5 态：DRAFT→PENDING→APPROVED→PUBLISHED→OBSOLETE）+ 引用追踪（DataLineage 反向查询）+ CIA 联动（上游 PUBLISHED 修改触发下游 STALE）

前端：物流数据表格、Excel 双 Sheet 上传向导、PRO/II 文件上传向导、物性对比展示、冲突展示组件、状态标记（🟢/🔵/🟡/⚪/⚫）、引用面板（📎×N）

（2026-09-06 增补 V1.3：

**已落地**（P2 Sprint 1.9 薄层）：石油分馏/NH3吸收/混合精馏/酸性水汽提四样例 PRO/II 解析基座、Streams 基础字段。

**增量**（P3.2 SIM Sprint）：
- PRO/II 五样例基线：①石油分馏 34 组分（24+10 PETRO）、②NH3/H2O 未收敛 20 ERRORS、③混合精馏 38 组分含侧线、④酸性水汽提含 FLASH/VALVE/HX、⑤FCC 催化裂化 41 组分（26+15 PETRO）含 SIDESTRIPPER/COMPRESSOR×2/SPLITTER×7/FLASH×4/VALVE/CONTROLLER/HX×25
- PRO/II 8.x 新语法：ASSAY/D86/TBP/LIGHTEND/REFSTREAM/NAME/SIDESTRIPPER/COMPRESSOR/SPLITTER/CONTROLLER 九类 .inp 段；ASSAY 切割点 (30, 650, 23)、D86/TBP 蒸馏曲线 8 种组合、NAME 物流重命名映射
- .out 新增提取器：SPLITTER SUMMARY（含烃类液相/自由水/分子量固体分数）、COMPRESSOR SUMMARY（绝热/多变效率、压头、功、后冷器三段数据）、TRAY SIZING（P5 延后）、REFINERY PROCESSOR PROPERTIES SET（P5 延后含 RVP/TVP/Watson K/Flash Point/LIQUID-DRY BASIS 双套）、STREAM TBP/ASTM CURVES（P5 延后 8 种曲线）
- PCS 数据模型：Streams 表扩展 6 字段（estimated/simulation_status/unreliable/tear_stream/zero_flow/stream_properties_json）；新增 9 表（sim_imports/sim_import_warnings/sim_tower_results/sim_reaction_defs/sim_unit_op_results 基表 + sim_reactor_results/sim_cstr_results/sim_compressor_results/sim_splitter_results/sim_stca_results/sim_calculator_results）
- 收敛分层导入：CONVERGED/WARNINGS 全量导入；NOT_CONVERGED/ABORTED SOLVED 单元产品 unreliable=True 仅存档；循环撕裂 tear_stream=True
- 增补 Spec（待评审）：PCS-SPEC-P3-SIM-ADD-001 手工输入字段完整清单（PRO/II STREAM SUMMARY + REFINERY PROPERTIES SET 全字段对齐，三级分类 R/O/C）；PCS-SPEC-P3-SIM-ADD-002 校核状态 + 引用追踪 + 冲突分类（BLOCK/WARN/INFO 三级，硬冲突阻止保存）
- 工时：基线 26.5 天 + ADD-001 增量 2.5 天 + ADD-002 增量 6.5 天 = 35.5 天，约 7 周；V1.1 炼油增量 24.5 天（独立 Sprint）；P5 延后项（TRAY 详细 + TRAY SIZING + REFINERY PROPERTIES + TBP/ASTM）约 4 天
- 实施顺序：SIM-1~9 + PR-1~16 + INT-1 + ADD-001（SIM-2b/4b/7b）+ ADD-002（SIM-S1~5 + SIM-C1~3）

P3 阶段的 SIM 子系统是 P4+ 计算模块的物流数据来源，需在 FLASH/PIPE/PUMP 等计算前完成交付。）

3.3 COMMON工艺常用数据库
包含：

chemicals库物性数据（纯物质）

CoolProp高精度物性（水蒸气IAPWS-IF97等）

材料许用应力表

介质毒性/爆炸极限数据

Claude Code生成：

物性查询API

数据批量导入接口

版本管理

3.4 PIPE_CLASS管道等级库
SPEC参考：3.2.15节 + PCS-SPEC-P2-SUP-002 V1.4（§0.6 实施裁决 + 第一部分）

Claude Code生成：

PipeClasses模型（含DNSeries_JSON, SchSeries_JSON, AllowableStress_JSON, BranchTable_JSON, asset_id FK → config_assets，5 态 status 镜像列）

ProjectPipeClasses模型（UUID PK + source_class_id FK + class_name UNIQUE(project_id) + override_json + snapshot_json + 5 态 status）

公司级/项目级数据混合读取（get_effective：snapshot ⊕ override 递归深合并；JSON 字段逐键合并，标量字段直接覆写）

与COMMON的许用应力/branch table 引用关系（PC-E04 校验引用的表名存在于 COMMON 库）

项目模板集成（project_template_pipe_classes 关联表，template_id + class_id 复合 PK）

（2026-09-06 增补 V1.3：本节交付依赖 SUP-002 追加 Sprint 先完成 PIPE_CLASS 库本体（PC-1~PC-6）+ 物流符号表（SYM-1~SYM-3）+ 管道代码格式模板（FMT-1~FMT-4）；P4.2 PIPE 计算读取 pipe_classes 时直接消费 project_pipe_classes 的 effective 值；项目模板创建时（INT-1）从 project_template_pipe_classes 拷贝默认等级 + fork 模板格式配置 → project_pipe_code_configs。阻塞关系：SUP Sprint 全部后端就绪 + INT-2 前端契约冻结后，P3.4 视为完全解锁。）

P4：核心计算引擎（第一批）（第8-12周）
目标
实现FLASH、PIPE、PIPE_NET、PUMP四个核心计算模块。

任务分解
4.1 FLASH闪蒸与相平衡
SPEC参考：3.2.20节（SUP-003）

Claude Code生成：

基于Thermo库的PT/PH/PS闪蒸计算

泡露点计算

热力学方法选择接口（PR/SRK/NRTL等）

与SIM集成（物性补全）

验收：与Aspen HYSYS偏差<1%

4.2 PIPE管道计算
SPEC参考：3.2.3节 + 管道一览表数据字典

核心算法：

管径确定（预定流速法 + 设定压力降法）

壁厚计算（ASME B31.3无缝管/焊接管公式）

压降计算（Darcy-Weisbach + Colebrook + 管件K值）

可压缩流计算（fluids.compressible）

两相流计算（Dukler I / Lockhart-Martinelli）

管件压降（fluids.fittings）

Claude Code生成：

PipeSizingService、WallThicknessService、PressureDropService

与PIPE_CLASS集成（读取腐蚀裕量、许用应力）

管道一览表输出（PipingResults表）

验收：与商业软件偏差<0.1%

4.3 PIPE_NET管道网络水力学
SPEC参考：3.2.23节（SUP-003）

Claude Code生成：

Hardy-Cross迭代求解器

节点法/环路法求解器

网络拓扑输入接口

与PIPE单管计算集成

验收：与手算偏差<1-2%

4.4 PUMP机泵计算
SPEC参考：3.2.4节 + 离心泵计算数据字典

核心算法：

扬程计算（伯努利方程）

NPSHa计算

粘度修正

轴功率/电机功率计算

泵设计压力计算

控制阀压降分配

Claude Code生成：

PumpCalculationService（完整计算链）

等效长度计算

泵数据表输出

前端：泵计算表单（吸入侧/排出侧/压降明细）

验收：与手算偏差<1%

P5：设备计算模块（第二批）（第12-16周）
目标
实现VESSEL、SEP_EQUIP、PSV、HEAT四个设备计算模块。

任务分解
5.1 VESSEL容器计算
SPEC参考：3.2.6节 + 容器/塔数据字段

核心算法：

Souders-Brown气速计算

最小直径计算

液体停留时间核算

容器流体力学校核（fluids.tanks）

Claude Code生成：

VesselCalculationService

容器数据表输出

EQUIP_LIB复用推荐接口

5.2 SEP_EQUIP气固/气液分离设备
SPEC参考：3.2.28节（SUP-003）

核心算法：

旋风分离器（Lapple/Swift/Barth）

丝网除沫器（York法）

重力沉降器（Stokes定律）

颗粒沉降计算（fluids.particle_size）

Claude Code生成：各类型分离设备计算服务

5.3 PSV安全阀计算
SPEC参考：3.2.5节 + API 520/521

核心算法：

泄放量计算（火灾/阀门关闭/反应失控）

泄放面积计算（气体/液体/两相流）

API 526孔口尺寸圆整

呼吸阀计算（API 2000）

Claude Code生成：

PSVCalculationService

安全阀数据表输出

与FLARE_SYS的泄放量汇总接口

5.4 HEAT换热器计算
SPEC参考：3.2.7节 + 换热器规格书数据字典 + 空冷器规格书数据字典

核心功能：

HTRI文件解析

换热器规格书数据存储（管壳式 + 空冷器）

重量估算

焓值表存储（空冷器）

Claude Code生成：

HTRI解析器

HeatResults模型完整实现（含所有JSON子结构）

冷换设备汇总表输出

P6：高级计算模块（第三批）（第16-19周）
目标
实现CV、RESTRICTION、FLARE_SYS、COOL_TOWER、PSYCHRO、OPEN_CHANNEL六个高级计算模块。

任务分解
6.1 CV调节阀计算
核心算法：

Cv值计算（IEC 60534-2-1，不可压缩/可压缩流体）

阻塞流校核

孔板计算（ISO 5167）

Claude Code生成：CVCalculationService

6.2 RESTRICTION节流装置
核心算法：

限流孔板（ISO 5167-2）

文丘里管/喷嘴计算

多级降压装置

临界流判定

Claude Code生成：RestrictionCalculationService

6.3 FLARE_SYS火炬系统
核心算法：

泄放量汇总（从PSV读取）

火炬总管尺寸计算（Mach数法）

分液罐尺寸计算

火炬筒体高度（辐射计算）

辐射校验

Claude Code生成：FlareSystemCalculationService（自研为主）

6.4 COOL_TOWER冷却塔
核心算法：Merkel方法、循环水量、补充水量、风机功率

Claude Code生成：CoolingTowerCalculationService（自研）

6.5 PSYCHRO湿空气计算
核心算法：CoolProp HumidAir模块直接调用

Claude Code生成：PsychroCalculationService

6.6 OPEN_CHANNEL明渠流
核心算法：Manning公式、临界水深、水跃、最优断面（fluids.open_channel）

Claude Code生成：OpenChannelCalculationService

P7：集成模块（第19-21周）
目标
实现EQUIP_LIST、UTIL、EQUIP_LIB、供应商数据录入四个集成模块。

任务分解
7.1 EQUIP_LIST设备表
SPEC参考：3.2.16节 + DICT-002设备表数据字典

核心功能：

各计算模块结果自动同步

设备状态管理（N/E/D/M/F）

设备类型代码管理（完整TypeCode清单）

设备采购数据字段

与EQUIP_LIB沉淀关系

Claude Code生成：

EquipmentList完整模型

同步服务（从PumpResults/VesselResults等自动创建/更新设备记录）

设备表查询API

7.2 UTIL公用工程及能耗
核心功能：

电耗汇总（从PUMP读取）

热负荷汇总（从HEAT读取）

公用工程消耗平衡

装置综合能耗计算（GB/T 50441）

冷却塔补充水量

排水系统汇总

Claude Code生成：UtilSummaryService

7.3 EQUIP_LIB复用设备库
核心功能：

设备检索（按工艺条件模糊搜索）

设备沉淀（从EQUIP_LIST审核后入库）

相似度计算

Claude Code生成：EquipmentLibService

7.4 供应商数据录入与核算
SPEC参考：3.3.12节

核心功能：

实际数据录入（手动/Excel批量导入）

自动比对设计值vs实际值

偏差报告生成

校核流程

下游数据更新

Claude Code生成：SupplierDataService

P8：报表与输出（第21-23周）
目标
实现REPORT和REPORT_BUILDER。

任务分解
8.1 REPORT综合报表引擎
核心功能：

Word模板填充（python-docx）

Excel模板填充（openpyxl）

PDF生成（ReportLab）

二维码嵌入（哈希验证）

假设数据声明页

Claude Code生成：ReportGenerationService

8.2 REPORT_BUILDER自定义报表
SPEC参考：3.2.18节

核心功能：

报表定义管理

字段选择器

过滤条件构建器（支持AND/OR/IS_NULL/IN等操作符）

多数据源JOIN

报表执行与导出

Claude Code生成：

ReportDefinitions模型

报表执行引擎

前端报表定义编辑界面

P9：工作流与权限（第23-25周）
目标
实现签署流程、变更影响分析前端、ADMIN模块。

任务分解
9.1 签署工作流前端（V1.2：两层）
前端页面：

记录层：提交批准按钮（按批准深度显示 Step n/N）、弃用、变更申请、放弃/撤销操作

交付物层：版本目的选择→Rev 生成、签署矩阵动态渲染（按钮/签署栏列数随矩阵）、变更单审批界面（新旧哈希对比）

代录客户批准弹窗（凭证附件上传+二次认证+客户栏"（代录：X）"标注）

签署意见批注面板

状态流转可视化（记录状态时间线 + 交付物 Rev 时间线）

待办列表（含撤销审批、STALE 确认）

通知中心

后端：

两层状态机API（与P1集成）

电子签名验证（AD二次认证，代录同强）

签名页PDF生成（矩阵动态列）

9.2 变更影响分析前端
核心UI：

受影响记录橙色高亮

通知中心变更清单

变更详情对比面板

确认与重新计算操作

9.3 ADMIN系统管理
核心功能：

用户管理（AD同步）

角色分配

审计日志查询

AI功能开关

系统参数设置

P10：AI预留与测试部署（第25-28周）
目标
实现AI接口预留、全流程测试、部署文档。

任务分解
10.1 AI预留接口
SPEC参考：3.3.13节（SUP-001/002）

Claude Code生成：

/api/v1/ai/*路由骨架

DocumentChunks表 + pgvector支持

AiAuditLog表

LangChain集成骨架（可选）

数据脱敏中间件

10.2 全流程测试
端到端测试场景：

项目创建 → BEDD录入 → 输入清单生成
SIM导入 → 物流验证
PIPE计算 → 管道一览表输出
PUMP计算 → 泵数据表
PSV计算 → 安全阀数据表
VESSEL计算 → 容器数据表
EQUIP_LIST汇总 → 设备表
REPORT生成 → 计算书
签署流程 → APPROVED
上游变更 → 影响分析 → 重新计算
性能压测：k6脚本，验证响应时间指标

10.3 部署文档
Docker Compose配置

环境变量清单

数据库迁移指南

监控告警配置（ELK/Prometheus）

模块开发依赖图
text
P0 (基础设施)
 ├─► P1 (横切关注点)
 │    ├─► P2 (CONFIG)
 │    │    ├─► P3 (PMS/SIM/COMMON/PIPE_CLASS)
 │    │    │    ├─► P4 (FLASH/PIPE/PIPE_NET/PUMP)
 │    │    │    │    ├─► P5 (VESSEL/SEP_EQUIP/PSV/HEAT)
 │    │    │    │    │    ├─► P6 (CV/RESTRICTION/FLARE_SYS/COOL_TOWER/PSYCHRO/OPEN_CHANNEL)
 │    │    │    │    │    │    ├─► P7 (EQUIP_LIST/UTIL/EQUIP_LIB/供应商)
 │    │    │    │    │    │    │    ├─► P8 (REPORT/REPORT_BUILDER)
 │    │    │    │    │    │    │    │    ├─► P9 (签署/变更影响/ADMIN)
 │    │    │    │    │    │    │    │    │    └─► P10 (AI预留/测试/部署)
各阶段Claude Code使用要点
场景	Claude Code使用方式	人工审查重点
生成新模块	提供SPEC相关章节 + 数据字典 → 生成完整模块代码	公式正确性、边界条件
单元测试	让Claude Code生成边界值测试、随机化测试	测试质量而非覆盖率
Bug修复	提供错误日志+相关代码 → 生成修复补丁	回归影响
数据导入	提供Excel/CSV文件 → 生成解析器	单位转换、异常数据
优化	提供性能分析报告 → 建议优化方案	可读性vs性能权衡
重构	提供重构目标 → 生成重构代码	行为不变性
关键里程碑验收标准
里程碑	验收标准
P0完成	前后端可运行、数据库迁移成功（SUP-007 表清单）、AD认证可用
P1完成	两层状态机全路径测试通过（9 态+STALE 哈希判定+变更单闭环）、交付物 Rev/编号/快照正确、血缘哈希追溯可用
P2完成	公式热更新可用、系数库可配置、审批流工作
P3完成	BEDD完整录入、HYSYS解析正确、物性查询可用
P4完成	FLASH与HYSYS偏差<1%、PIPE与商业软件偏差<0.1%、PUMP计算正确
P5完成	各设备计算与手算/商业软件偏差在SPEC要求范围内
P6完成	高级模块计算功能验证通过
P7完成	设备表正确汇聚各模块结果、UTIL能耗汇总正确
P8完成	报表生成格式正确、自定义报表可用
P9完成	签署流程完整走通、变更影响分析正确触发
P10完成	全流程E2E测试通过、性能达标、部署文档完整

---

## 未解决问题（V1.3 增量）

1. **P3.2 SIM 工时 vs P3 周期（6-8 周）**：基线 26.5 天 + ADD-001 增量 2.5 天 + ADD-002 增量 6.5 天 = 35.5 天已超 P3 整个阶段 14 天窗口。两种处理路径：(a) P3 SIM 只交付 SIM-1~9 + PR-1~12（基线 26.5 天仍超 14 天，需拆分到 P4 早期补完），ADD-001/002 推后；(b) P3 阶段延长或 SIM 拆分两波。需裁决后调整 P3-P4 时间盒。
2. **P5 延后项归属**：TRAY COMPOSITIONS/LOADING/RATING + TRAY SIZING + REFINERY PROPERTIES SET + STREAM TBP/ASTM CURVES 共约 4 天，归入 P5 设备计算模块阶段或单列 P3.5 炼油增强 Sprint？需与 P5 计划主理对齐。
3. **P3-SIM-ADD-001/002 待评审状态**：两个增补 Spec 文档当前「待评审」（2026-09-06），合并入 PCS-SPEC-P3-SIM V1.2 后再实施；用户验收前 SIM-S1~5 + SIM-C1~3 三组任务暂不启动。
4. **PIPE_CLASS Sprint 工期 17.5 天 vs 现状**：Sprint 1.9 已交付 1.9.1~1.9.6 薄层（service + 5 端点 + Excel 导入 + 71 等级种子），SUP Sprint 增量 17.5 天（PC-1~PC-6 + SYM-1~SYM-3 + FMT-1~FMT-4 + INT-1 + INT-3），合计进入 P2.5 增量约 3.5 周。P2 阶段原预算 3 周（4-6 周），需把 SUP Sprint 显式从 P2.5 切出作为 P2.5b 追加 Sprint，或压缩 P2 阶段其他模块（P2.1~P2.4 + P2.6）。
5. **pcs_test 库 schema 漂移**：矫正迁移（PC-1/SIM-1/SYM-1/FMT-1/新增表）历史上只对 pcs 库生效，pcs_test 库需手动 `alembic upgrade head` 对齐再跑 schema 敏感测试（已记 .wolf/cerebrum Do-Not-Repeat）。Sprint 启动前需 CI 步骤加自动 alembic upgrade。
6. **TimestampMixin 三列纪律**（.wolf/cerebrum Do-Not-Repeat）：新表迁移必须含 created_by/created_at/updated_at（created_at timezone+server_default，updated_at nullable）——SUP Sprint 内 PC-1/SYM-1/FMT-1/INT-1 关联表新增时需逐表核对，缺列需在迁移脚本显式补齐。
7. **前端契约已冻结但实施未排期**：ProjectPipeClassResponse.pipe_class 恒 null（Sprint 2 前端契约）；equip-lib limit>200 返 422（TODO-033）。这两个契约在本计划外落定，需 P2 Sprint 2 前端波启动时确认沿用。

本计划供项目组内部使用，具体执行中可根据实际进展和资源情况进行调整。
