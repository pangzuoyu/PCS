文件标识批量更新——ProcessCalc Suite（PCS）
以下为所有已产出文档的文件标识映射表及更新后的完整标识体系。

一、文件标识映射总表
原文件标识	新文件标识	文档名称
HT-REQ-2026-002 V2.2	PCS-REQ-2026-002 V2.2	工艺专用综合计算软件需求规格说明书（Web版·完整版）
HT-REQ-2026-002-SUP-001 V1.0	PCS-REQ-2026-002-SUP-001 V1.0	增补文件一：数据管理与协同功能
HT-REQ-2026-002-SUP-002 V1.0	PCS-REQ-2026-002-SUP-002 V1.0	增补文件二：Python技术栈调整
HT-REQ-2026-002-SUP-003 V1.2	PCS-REQ-2026-002-SUP-003 V1.2	增补文件三：计算模块补充
HT-REQ-2026-002-SUP-004 V1.0	PCS-REQ-2026-002-SUP-004 V1.1	增补文件四：版本与版次管理
HT-REQ-2026-002-SUP-005 V1.0	PCS-REQ-2026-002-SUP-005 V1.1	增补文件五：校审层级可配置化
无（新编）	PCS-REQ-2026-002-SUP-006 V1.1	增补文件六：演示版许可模式
无（新编）	PCS-REQ-2026-002-SUP-007 V1.0	增补文件七：两层签署与变更管理
HT-REQ-2026-DICT-001 V1.0	PCS-DICT-001 V1.0	数据字典总则
HT-REQ-2026-DICT-002 V1.0	PCS-DICT-002 V1.0	设备表数据字典
HT-REQ-2026-DICT-ALL-002 V2.0	PCS-DICT-ALL-002 V2.0	合并数据字典（更新版）
HT-REQ-2026-002-SPEC-P0 V1.0	PCS-SPEC-P0 V1.2	P0 项目初始化与基础设施开发规格说明书
HT-REQ-2026-002-SPEC-P1 V1.0	PCS-SPEC-P1 V1.2	P1 横切关注点框架开发规格说明书
HT-REQ-2026-002-SPEC-P2 V1.0	PCS-SPEC-P2 V1.2	P2 CONFIG配置中枢开发规格说明书
HT-REQ-2026-002-SPEC-P3 V1.0	PCS-SPEC-P3 V1.2	P3 基础数据层开发规格说明书
HT-REQ-2026-002-SPEC-P4 V1.0	PCS-SPEC-P4 V1.2	P4 核心计算引擎（第一批）开发规格说明书
HT-REQ-2026-002-SPEC-P5 V1.0	PCS-SPEC-P5 V1.2	P5 设备计算模块（第二批）开发规格说明书
HT-REQ-2026-002-SPEC-P6 V1.0	PCS-SPEC-P6 V1.2	P6 高级计算模块（第三批）开发规格说明书
HT-REQ-2026-002-SPEC-P7 V1.0	PCS-SPEC-P7 V1.1	P7 集成模块开发规格说明书
HT-REQ-2026-002-SPEC-P8 V1.0	PCS-SPEC-P8 V1.1	P8 报表与输出开发规格说明书
HT-REQ-2026-002-SPEC-P9 V1.0	PCS-SPEC-P9 V1.2	P9 工作流与权限开发规格说明书
HT-REQ-2026-002-SPEC-P10 V1.0	PCS-SPEC-P10 V1.1	P10 AI预留与测试部署开发规格说明书
无独立编号（管道字典）	PCS-DICT-003 V1.0	管道一览表数据字典
无独立编号（泵字典）	PCS-DICT-004 V1.0	离心泵计算数据字典
无独立编号（换热器字典）	PCS-DICT-005 V1.0	换热器规格书数据字典
无独立编号（空冷器字典）	PCS-DICT-006 V1.0	空冷器规格书数据字典
无独立编号（开发计划）	PCS-PLAN-2026-001 V1.2	Claude Code分步开发计划
二、系统命名使用规范
2.1 正式名称
项目	内容
英文全称	ProcessCalc Suite
英文简称	PCS
中文名称	工艺专用综合计算软件
副标题（可选）	Integrated Process Engineering Calculation & Data Management Platform
2.2 各场景使用约定
场景	用法
正式文档标题	ProcessCalc Suite（PCS）——工艺专用综合计算软件
文档编号	PCS-<类别>-<年份>-<序号>
数据库名	pcs_db
数据库Schema	pcs
API前缀	/api/v1/...（保持不引入品牌前缀）
Docker镜像	pcs-backend:latest、pcs-frontend:latest、pcs-worker:latest
Git仓库	pcs-backend、pcs-frontend、pcs-docs
Python包名	pcs_backend
前端npm包	pcs-frontend
内部称呼	PCS系统 / ProcessCalc
登录页标题	ProcessCalc Suite
Logo方案	文字Logo：PCS + 副标题“ProcessCalc Suite”
版本号格式	PCS V2.2
2.3 文档编号规则
text
PCS-<类别>-<年份>-<序号>-<后缀>

类别：
  REQ   = Requirements（需求规格说明书）
  SUP   = Supplement（增补文件）
  DICT  = Data Dictionary（数据字典）
  SPEC  = Specification（阶段开发规格）
  PLAN  = Plan（开发计划）
  UM    = User Manual（用户手册）
  AM    = Administrator Manual（管理员手册）

示例：
  PCS-REQ-2026-002          — 主需求规格说明书
  PCS-REQ-2026-002-SUP-001  — 增补文件一
  PCS-DICT-ALL-002          — 合并数据字典
  PCS-SPEC-P0               — P0阶段开发规格
  PCS-PLAN-2026-001         — 开发计划
三、更新后的文档体系总表
3.1 需求规格说明书体系（REQ）
文档编号	版本	文档名称	状态
PCS-REQ-2026-002	V2.2	工艺专用综合计算软件需求规格说明书（Web版·完整版）	已发布
PCS-REQ-2026-002-SUP-001	V1.0	增补一：数据管理与协同功能（含EQUIP_LIST/CONFIG/供应商/大模型预留/输入清单/工作区/自定义报表）	已发布
PCS-REQ-2026-002-SUP-002	V1.0	增补二：Python技术栈调整（FastAPI/ChEDL/CoolProp/SciPy）	已发布
PCS-REQ-2026-002-SUP-003	V1.2	增补三：计算模块补充（FLASH/PIPE_NET/RESTRICTION/FLARE_SYS/COOL_TOWER/PSYCHRO/SEP_EQUIP/FILTRATION/COST_EST/OPEN_CHANNEL）	已发布
PCS-REQ-2026-002-SUP-004	V1.1	增补四：版本与版次管理（可配置版本序列Alpha/数字/As-built/Void）	已发布
PCS-REQ-2026-002-SUP-005	V1.1	增补五：校审层级可配置化（签署矩阵驱动交付物状态机）	已发布
PCS-REQ-2026-002-SUP-006	V1.1	增补六：演示版许可模式（活记录计数）	已发布
PCS-REQ-2026-002-SUP-007	V1.0	增补七：两层签署与变更管理（对应 ADR-0001~0014）	已发布（现行权威）
3.2 数据字典体系（DICT）
文档编号	版本	文档名称	状态
PCS-DICT-ALL-002	V2.0	合并数据字典（统一命名规范/消除歧义/40+表/41+枚举）	最新权威
PCS-DICT-001	V1.0	数据字典总则（BEDD/Streams/流程/横切层）	已合并至ALL
PCS-DICT-002	V1.0	设备表数据字典（EquipmentList/TypeCode）	已合并至ALL
PCS-DICT-003	V1.0	管道一览表数据字典	已合并至ALL
PCS-DICT-004	V1.0	离心泵计算数据字典	已合并至ALL
PCS-DICT-005	V1.0	换热器规格书数据字典	已合并至ALL
PCS-DICT-006	V1.0	空冷器规格书数据字典	已合并至ALL
3.3 分阶段开发规格说明书体系（SPEC）
文档编号	版本	文档名称	状态
PCS-SPEC-P0	V1.2	项目初始化与基础设施（含Mock认证/测试AD）	完整
PCS-SPEC-P1	V1.2	横切关注点框架（状态机/版本/血缘/输入清单/工作区/变更影响）	完整
PCS-SPEC-P2	V1.2	CONFIG配置中枢（公式/系数/模板/标准库/管道等级/项目模板）	完整
PCS-SPEC-P3	V1.2	基础数据层（PMS/SIM/COMMON/PIPE_CLASS）	完整
PCS-SPEC-P4	V1.2	核心计算引擎第一批（FLASH/PIPE/PIPE_NET/PUMP）	完整
PCS-SPEC-P5	V1.2	设备计算模块第二批（VESSEL/SEP_EQUIP/PSV/HEAT）	完整
PCS-SPEC-P6	V1.2	高级计算模块第三批（CV/RESTRICTION/FLARE_SYS/COOL_TOWER/PSYCHRO/OPEN_CHANNEL/FILTRATION/COST_EST）	完整（含补完）
PCS-SPEC-P7	V1.1	集成模块（EQUIP_LIST/UTIL/EQUIP_LIB/供应商数据）	完整
PCS-SPEC-P8	V1.1	报表与输出（REPORT/REPORT_BUILDER）	完整
PCS-SPEC-P9	V1.2	工作流与权限（签署流程/变更影响前端/ADMIN）	完整（需结合SUP-004/005修订）
PCS-SPEC-P10	V1.1	AI预留与测试部署（AI接口/E2E/压测/部署文档/用户文档）	完整
3.4 开发计划体系（PLAN）
文档编号	版本	文档名称	状态
PCS-PLAN-2026-001	V1.2	Claude Code分步开发计划（P0~P10，主干→模块→集成）	已发布
四、全体系文档结构图
text
ProcessCalc Suite（PCS）——工艺专用综合计算软件
│
├── 需求规格说明书体系（REQ）
│   ├── PCS-REQ-2026-002 V2.2（主文档）
│   ├── PCS-REQ-2026-002-SUP-001（增补一）
│   ├── PCS-REQ-2026-002-SUP-002（增补二）
│   ├── PCS-REQ-2026-002-SUP-003（增补三）
│   ├── PCS-REQ-2026-002-SUP-004（增补四：版本序列）
│   ├── PCS-REQ-2026-002-SUP-005（增补五：签署矩阵，仅交付物层）
│   ├── PCS-REQ-2026-002-SUP-006（增补六：演示版许可）
│   └── PCS-REQ-2026-002-SUP-007（增补七：两层签署与变更管理）★现行权威
│
├── 数据字典体系（DICT）
│   ├── PCS-DICT-ALL-002 V2.0（合并权威版）★
│   ├── PCS-DICT-001（总则，已合并）
│   ├── PCS-DICT-002（设备表，已合并）
│   ├── PCS-DICT-003（管道一览表，已合并）
│   ├── PCS-DICT-004（离心泵，已合并）
│   ├── PCS-DICT-005（换热器，已合并）
│   └── PCS-DICT-006（空冷器，已合并）
│
├── 分阶段开发规格体系（SPEC）
│   ├── PCS-SPEC-P0（基础设施）
│   ├── PCS-SPEC-P1（横切框架）
│   ├── PCS-SPEC-P2（CONFIG）
│   ├── PCS-SPEC-P3（基础数据）
│   ├── PCS-SPEC-P4（核心计算一）
│   ├── PCS-SPEC-P5（设备计算二）
│   ├── PCS-SPEC-P6（高级计算三）
│   ├── PCS-SPEC-P7（集成模块）
│   ├── PCS-SPEC-P8（报表输出）
│   ├── PCS-SPEC-P9（工作流权限）
│   └── PCS-SPEC-P10（AI预留与部署）
│
└── 开发计划（PLAN）
    └── PCS-PLAN-2026-001（Claude Code分步计划）
五、版本历史
版本	日期	修改内容
V1.0	2026-08-27	全体系文档标识从HT-REQ统一更新为PCS，建立PCS文档编号规则和命名规范
V1.1	2026-08-28	基线 SPEC 升版 incorporate SUP-007：SPEC-P0~P10 升 V1.1、SUP-004/005/006 升 V1.1、开发计划升 V1.2；登记 SUP-006/SUP-007
V1.2	2026-08-29	物流手动创建与物流链建模（ADR-0019~0022）incorporate：SPEC-P0~P6/P9 升 V1.2（P7/P8/P10 维持 V1.1）；streams 新增 10 字段、新增 stream_state_points 表、4 组枚举

