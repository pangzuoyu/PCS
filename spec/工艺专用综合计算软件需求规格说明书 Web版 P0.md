工艺专用综合计算软件——分阶段开发规格说明书
以下为各阶段（P0–P10）开发SPEC，每份均遵循标准软件需求规格说明书结构，作为该阶段编码、测试与验收的独立依据。

P0 项目初始化与基础设施开发规格说明书
文件标识	PCS-REQ-2026-002-SPEC-P0
当前版本	V1.2
发布日期	2026-08-27（V1.2 修订 2026-08-29，incorporate SUP-007 + ADR-0019~0022）
编制部门	工艺部 / 信息化联合项目组
适用对象	内部开发团队（后端/前端/测试/数据库）
关联文档	PCS-REQ-2026-002 V2.2（主SPEC）、SUP-001~007、DICT-001/002
第一部分：引言
1.1 目的
本文档定义P0阶段（项目初始化与基础设施）的完整需求规格，明确该阶段必须交付的软件组件、接口、数据模型和质量标准。本文档是P0阶段设计、编码、测试和验收的唯一依据。

1.2 文档范围
包含：

前后端项目骨架的搭建规范

数据库Schema的完整定义

AD认证集成要求

CI/CD流水线配置

AI辅助开发规范文件（CLAUDE.md）

开发环境与工具链标准

不包含：

任何业务计算逻辑

状态机与工作流实现

报表生成功能

AI推理能力

1.3 定义、缩略语和术语
术语/缩写	定义
SPEC	Software Requirements Specification，软件需求规格说明书
P0	Phase 0，第零阶段（初始化阶段）
AD	Active Directory，公司域控服务
CI/CD	Continuous Integration / Continuous Deployment，持续集成/持续部署
MFA	Multi-Factor Authentication，多因素认证
ORM	Object-Relational Mapping，对象关系映射
JSONB	PostgreSQL中的二进制JSON存储类型
Golden Test	基准测试，固定输入对比固定输出的回归测试
CLAUDE.md	Claude Code的项目级配置文件，定义编码规范和AI辅助开发约定
计算记录	单条工程计算数据（一条管道、一台泵）。9 态数据门禁，无 Rev（SUP-007）
交付物	面向发布的文档单元（管道一览表、计算书、变更单）。独占 Rev/版本目的/签署矩阵（SUP-007）
1.4 参考文献
HT-REQ-2026-002 V2.2《工艺专用综合计算软件需求规格说明书（Web版·完整版）》

HT-REQ-2026-002-SUP-001《增补文件一：数据管理与协同功能》

HT-REQ-2026-002-SUP-002《增补文件二：Python技术栈调整》

HT-REQ-2026-002-SUP-003《增补文件三：计算模块补充》

HT-REQ-2026-DICT-001《数据字典总则》

HT-REQ-2026-DICT-002《设备表数据字典》

管道一览表数据字典、换热器规格书数据字典、离心泵计算数据字典、空冷器规格书数据字典

1.5 文档概述
本文档共四个部分。第一部分为引言，说明文档目的、范围和术语。第二部分为综合描述，从宏观视角描述P0阶段产品的背景、用户、环境和约束。第三部分为具体需求，详细定义外部接口、功能需求、非功能需求和数据需求。第四部分为附录，包含系统模型图和待确定问题列表。

第二部分：综合描述
2.1 产品前景
P0阶段是整个《工艺专用综合计算软件》的地基工程。本阶段不交付任何面向工艺工程师的业务功能，而是建立可运行的技术骨架、完整的数据存储层、统一的认证体系和标准化的开发工具链。后续所有阶段（P1–P10）均在此基础上进行增量开发。

本产品定位为内部研发项目，目标是替代工艺室当前依赖的Excel散表工作模式，实现从模拟数据读取→工艺计算→校审签章→计算书自动生成的闭环。

2.2 产品功能
P0阶段交付的功能概述：

功能	说明
项目骨架	前端React+TypeScript项目、后端FastAPI项目可运行
数据库Schema	所有核心表结构通过Alembic迁移创建
AD认证	用户可通过公司域账号登录，获取JWT令牌
CI/CD	代码提交自动触发lint、test、build流水线
开发规范	CLAUDE.md定义AI辅助开发的编码标准和命令约定
2.3 用户类和特征
用户类	特征	P0阶段相关需求
后端开发工程师	熟悉Python/FastAPI/SQLAlchemy，负责业务逻辑实现	项目骨架可用性、数据库迁移顺畅
前端开发工程师	熟悉React/TypeScript/Ant Design，负责UI实现	前端项目启动正常、路由可用
测试工程师	熟悉pytest/Playwright，负责质量保障	CI流水线中测试可执行
系统管理员	负责部署、监控、运维	Docker配置、环境变量文档完整
工艺工程师（最终用户）	不直接参与P0阶段开发	P0阶段无直接交互
2.4 运行环境
开发环境：

层级	规格
操作系统	Windows 11 / macOS / Ubuntu 22.04
Python	3.12.x（通过uv管理）
Node.js	20.x LTS
数据库	PostgreSQL 16（本地Docker容器）
Redis	7.x（本地Docker容器，用于缓存和任务队列）
浏览器	Chrome 90+ / Edge 90+ / Firefox 88+
生产环境（预留）：

层级	规格
操作系统	Ubuntu 22.04 LTS / Rocky Linux 9
服务器	32核/64GB RAM/1TB SSD
部署方式	Docker + Docker Compose
数据库	PostgreSQL 16主从复制
反向代理	Nginx
2.5 设计和实现上的限制
技术栈锁定：后端必须使用Python 3.12 + FastAPI + SQLAlchemy 2.0 + Alembic。前端必须使用React 18 + TypeScript + Ant Design。技术栈已在SUP-002中确定，本阶段不得引入替代框架。

数据库版本锁定：PostgreSQL 16（推荐）或SQL Server 2022（备选）。生产环境优先使用PostgreSQL以利用JSONB和pgvector特性。

依赖锁定：Python依赖通过uv.lock完全锁定。任何依赖变更需走变更流程。

代码规范：必须通过Ruff和mypy检查，无error级别警告方可合并。

浮点确定性：所有数值计算使用numpy.float64，禁止使用float32或Python原生float参与核心计算。

安全合规：禁止调用任何外部云AI服务。所有API必须经过认证中间件。

2.6 假设和依赖
假设：公司AD域控支持LDAP协议认证，且网络可达。

假设：开发团队具备Python和TypeScript的基础能力，Claude Code作为辅助工具。

依赖：内部Git服务器（Azure DevOps）可用。

依赖：Docker运行环境已安装并配置。

依赖：PostgreSQL 16 Docker镜像可在内网拉取。

第三部分：具体需求
3.1 外部接口需求
3.1.1 用户界面
P0阶段交付以下最小UI：

界面	规格
登录页	Ant Design Form布局，包含用户名/密码输入框、登录按钮、错误提示。支持AD域认证。
主布局	左侧导航栏（空菜单占位）+ 顶部工具栏（项目切换占位、用户信息、退出按钮）+ 内容区（空状态提示）
路由配置	/login（登录）、/（主布局，默认重定向到首页占位）
界面风格：遵循Ant Design默认主题，明亮模式。

3.1.2 软件接口
接口	规格
认证API	POST /api/v1/auth/login — 接收用户名/密码，返回JWT令牌
认证API	POST /api/v1/auth/refresh — 刷新JWT令牌
健康检查	GET /api/v1/health — 返回服务状态、数据库连通性
Swagger文档	GET /docs — FastAPI自动生成的OpenAPI文档
3.1.3 通信接口
协议	规格
HTTPS	TLS 1.3，开发环境可使用自签名证书
WebSocket	预留支持（不在P0阶段实现具体功能）
数据库连接	PostgreSQL TCP 5432，连接池最小5/最大50
3.2 功能需求
3.2.1 前端项目骨架
需求编号：P0-FE-001
功能描述：创建可运行的React + TypeScript前端项目。

详细规格：

需求项	规格
项目初始化	使用Vite创建react-ts模板
UI库	Ant Design 5.x，按需引入
状态管理	Zustand，初始化store结构
路由	React Router v6，定义基础路由
目录结构	src/{pages,components,services,stores,types,utils,hooks}
环境变量	.env.development、.env.production配置API基础URL
代理配置	Vite dev server代理/api到后端
验收标准：

npm run dev启动正常，无控制台错误

npm run build构建成功

访问/login显示登录页面

3.2.2 后端项目骨架
需求编号：P0-BE-001
功能描述：创建可运行的FastAPI后端项目。

详细规格：

需求项	规格
项目初始化	使用uv创建Python 3.12项目
框架	FastAPI + Pydantic v2
ORM	SQLAlchemy 2.0 + Alembic
目录结构	backend/{app/{api,models,services,core,schemas},tests,alembic}
配置管理	Pydantic Settings，支持环境变量覆盖
日志	结构化日志（JSON格式），输出到stdout
异常处理	全局异常处理器，返回统一JSON错误格式
验收标准：

uv run uvicorn app.main:app --reload启动正常

GET /docs可访问Swagger UI

GET /api/v1/health返回200

3.2.3 数据库Schema创建
需求编号：P0-DB-001
功能描述：创建完整的数据库Schema，覆盖所有业务表。

表清单（按域分组）。

V1.1 注（SUP-007）：业务计算记录表（piping_results、pump_results、equipment_list 等）**不含 version / version_purpose / version_description / customer_approval_date 字段**——Rev 与版本目的仅存在于交付物层。业务记录表统一含：sign_status（RecordSignStatus 9 态）、record_hash、approval_step / approval_depth / approval_role、locked_by_deliverable、stale_* / change_* / reversal_* / obsoleted_* 字段组、imported_from_workspace_id。xxx_History 快照流水表全部不创建（历史由变更前快照 / 交付物版本 / 审计日志三处承载）。

域	表名	核心字段
项目与物流	projects	project_id, project_no, name, location, unit_system, bedd_json
streams	stream_id, project_id, workspace_id, name, phase, temp, press, mass_flow, composition_json, vapor_composition_json, liquid_composition_json, data_mode（CHEMICAL/PETROLEUM/SOLID）, property_estimation_json, pseudo_components_json, lab_report_ref, upstream_stream_id, upstream_equipment_type, upstream_equipment_id, change_type, sign_status（StreamSignStatus：DRAFT/IN_APPROVAL/CHECKED/OBSOLETE）, approval_step, approval_depth, checked_by, checked_at
stream_state_points	state_point_id, stream_id, state_label, case_type（NORMAL/MIN/MAX/ALTERNATE）, temp, press, phase, vapor_fraction, mass_flow, composition_json, vapor_composition_json, liquid_composition_json, density, viscosity_dynamic, enthalpy, entropy, record_hash, estimated_flags_json, profile_json（长输管道沿程剖面）, source_type（SIM_IMPORT/MANUAL_ENTRY/FLASH_CALCULATED/DEVICE_CALCULATED）, created_at
配置层	config_assets	asset_id, category, name, description, current_version, status, content_json
config_versions	version_id, asset_id, version_code, content_json, created_by, created_at, status
config_approvals	approval_id, version_id, approver_role, approver_id, decision, comment, timestamp
formula_definitions	formula_id, asset_id, module, name, expression, parameters_json, std_source, unit_tests_json
coefficient_tables	table_id, asset_id, name, data_json, applicable_range, std_source
template_files	template_id, asset_id, file_type, file_path, placeholders_json
project_templates	template_id, asset_id, name, checklist_json, default_config_json
pipe_classes	class_id, class_name, material_standard, corrosion_allowance, dn_series_json, sch_series_json, flange_class, version, status
project_pipe_classes	project_id, class_id, assigned_by, assigned_at
计算模块	piping_results	pipe_id, project_id, workspace_id, seq_no, line_no, line_size, material_class, fluid_code, fluid_name, fluid_phase, fluid_category, toxic_class, pipe_grade, insulation_code, insulation_thickness, paint_code, tracing_type, holding_temp, source_pid, line_from, line_to, norm_oper_press, max_oper_press, norm_oper_temp, max_oper_temp, alt_norm_oper_press, alt_max_oper_press, alt_norm_oper_temp, alt_max_oper_temp, design_press, design_vacuum, design_temp, design_min_temp, piping_category, pressure_test_medium, pressure_test_press, ndt_method, ndt_ratio, ndt_tech_level, leak_test_medium, leak_test_press, check_class, cleaning_method, stress_analysis_level, remark, sign_status
pump_results	pump_id, project_id, workspace_id, tag_number, equipment_tag, sign_status, basic_info_json, fluid_properties_json, flow_rates_json, suction_calculation_json, discharge_calculation_json, differential_pressure_json, design_pressure_json, power_consumption_json, control_valve_json, equivalent_length_json, pressure_drop_details_json, line_references_json, actual_head, actual_efficiency, actual_motor_power, actual_npshr, vendor_model, actual_data_confirmed
psv_results	psv_id, project_id, workspace_id, tag_number, equipment_tag, sign_status, relief_scenario, relief_capacity, orifice_area, orifice_designation, set_pressure, inlet_size, outlet_size, blowdown
vessel_results	vessel_id, project_id, workspace_id, tag_number, equipment_tag, sign_status, volume, diameter, length_height, design_pressure, design_temp, operating_pressure, operating_temp, moc, corrosion_allowance, insulation, tracing, tower_type, packing_height, tray_count
heat_results	heat_exchanger_id, project_id, workspace_id, equipment_tag, heat_exchanger_type, sign_status, general_parameters_json, performance_data_json, heat_transfer_json, construction_json, tube_bundle_json, shell_internals_json, weights_json, enthalpy_table_json, material_json, connections_json, notes_json, remarks
cv_results	cv_id, project_id, workspace_id, tag_number, equipment_tag, sign_status, cv_value, flow_rate, pressure_drop, choked_flow, noise
flash_results	flash_id, project_id, stream_id, calc_type, method, input_json, output_json
pipe_network_results	net_id, project_id, topology_json, convergence_log_json, flow_distribution_json
restriction_results	restriction_id, project_id, type, bore_diameter, perm_pressure_drop, choked_flow, noise
flare_system_results	flare_id, project_id, total_relief_load, header_size, kod_size, stack_height, radiation_check_json
cooling_tower_results	ct_id, project_id, duty, water_flow, makeup_water, fan_power, tower_type
psychro_results	psychro_id, project_id, calc_type, input_json, output_json
sep_equip_results	sep_equip_id, project_id, equip_type, dimensions, efficiency, pressure_drop
filtration_results	filter_id, project_id, filter_type, area, cycle_time, pressure_drop
cost_est_results	cost_est_id, project_id, equipment_id, estimated_cost, currency, cost_index_year
open_channel_results	channel_id, project_id, type, cross_section_json, flow_rate, depth, velocity, slope
集成层	equipment_list	equipment_id, project_id, workspace_id, tag_number, equipment_description, equipment_name_cn, package_no, sub_project, unit_no, unit_name, type_code, equipment_sub_type, equipment_category, is_pressure_vessel, pressure_vessel_category, source_module, source_record_id, in_package, data_sources, equipment_status, calc_status, sign_status, actual_data_status, tag_in_3d, tag_in_esr, record_hash（仅设计参数参与哈希，商务/采购字段不参与）, design_parameters_json, vendor, alternate_vendor, order_date, purchase_order_number, cost, cost_currency, cost_source, cost_year, gpe_specification_number, gpe_specification_status, specification_priority, approval_drawing_received_date, approval_drawing_return_date, certified_drawing_received_date, delivery_date, actual_received_date, forecast_on_site, actual_on_site, storage_location, installation_location, installation_contract_number, installation_notes, installation, unloading, loading_by, empty_weight, full_weight, weigh_cells, net_weight, paint, process_engineer, subject_matter_expert, detail_engineer, manufacturing_representative, process_engineering_remarks, detail_engineering_remarks, flowsheet_drawing_number, flowsheet_status, pid_drawing_number, pid_status, pid_number, pid_no_from, dimensions, registration_number, emts_number, mst_number, existing_tag_number, l4_id, l4_c_start, ros, ros_to_mei, ros_to_mei_before_loa, actual_key_parameter_json, vendor_model, actual_data_status
equipment_type_codes	type_code, equipment_description, description_cn, category, is_process_equipment, is_pressure_vessel, source, status
equipment_lib	equip_id, type, size, weight, material, standard_drawing_no, process_description, cost, cost_currency, cost_year
交付物与变更	deliverables	deliverable_id, project_id, deliverable_type（PIPE_LIST/EQUIP_LIST/CALC_BOOK/PUMP_DATASHEET/EQUIP_DATASHEET/PURCHASE_LIST/CUSTOM_REPORT/CHANGE_NOTICE/…）, scope_type, scope_value, doc_no, title, current_rev, version_purpose, sign_status, matrix_id, 客户批准字段组（customer_approval_date/name/method/proxy_by/proxy_at/attachment_id）
deliverable_versions	version_id, deliverable_id, rev, version_purpose, description, signature_summary_json, customer_approval_date, pdf_file_path
deliverable_record_bindings	binding_id, deliverable_version_id, record_type, record_id, record_hash, old_record_hash_before_change
change_notice_details	detail_id, deliverable_id（1:1，deliverable_type=CHANGE_NOTICE）, change_type, reason, triggered_by, source_record_type
numbering_templates	template_id, template_name, description, segments_json, separator, revision_separate, deliverable_mappings_json, status
doc_no_sequences	sequence_id, project_id, template_id, scope_key, current_value
customer_approval_attachments	attachment_id, deliverable_version_id, file_path, file_name, file_type, file_size, uploaded_by, uploaded_at, file_hash
record_change_snapshots	变更前快照：进入 STALE/CHANGE_PENDING 前自动保存完整设计参数，供哈希比对与撤销回滚
流程与横切	data_lineage	lineage_id, source_type, source_id, source_record_hash, target_type, target_id, target_record_hash, dependency_type, field_name, formula_version, config_version, timestamp
project_input_checklist	input_id, project_id, module, input_name, input_category, input_value_json, source_type, status, verified_by, verified_at, assumption_reason, last_updated
workspaces	workspace_id, workspace_type, owner_id, project_id, name, created_at, last_active_at, retention_days
calc_logs	log_id, user_id, module, timestamp, old_value, new_value, hash
suppliers	supplier_id, supplier_name, supplier_type, contact_json, qualification_json, rating, approved_by, approved_date
report_definitions	report_def_id, report_name, report_category, description, data_sources_json, selected_fields_json, filter_conditions_json, sort_by_json, max_rows, output_format, output_template_id, created_by, created_at, status, version, shared_with, project_scope
report_execution_logs	log_id, report_def_id, report_def_version, executed_by, executed_at, filter_conditions_snapshot_json, row_count, export_format
AI预留	document_chunks	chunk_id, document_id, content, vector_id, source, created_at
ai_audit_log	log_id, user_id, timestamp, request_summary, response_summary, model_version
验收标准：

Alembic迁移脚本可从头创建所有表

外键约束正确

JSONB字段使用恰当

核心表有适当索引

3.2.4 AD认证集成
需求编号：P0-AUTH-001
功能描述：实现基于公司AD域的用户认证。

详细规格：

需求项	规格
认证方式	LDAP绑定认证
库	Authlib + ldap3
令牌	JWT（HS256或RS256），过期时间30分钟
刷新机制	支持刷新令牌，过期时间7天
角色映射	AD安全组→系统角色（DESIGNER/CHECKER/REVIEWER/APPROVER/SYSADMIN）
MFA预留	接口设计支持MFA，P0阶段不强制启用
前端集成	登录页调用认证API，令牌存储于内存（不存localStorage）
验收标准：

使用有效的AD账号可登录成功

无效凭证返回401

JWT令牌可被后端中间件验证

角色信息包含在令牌中
3.2.4.1 测试认证机制

需求编号：P0-AUTH-002

功能描述：为开发、测试和CI环境提供不依赖生产AD域的认证模拟能力。

（1）Mock认证依赖覆盖

需求项	规格
实现方式	FastAPI dependency_overrides覆盖get_current_user依赖
模拟角色	DESIGNER / CHECKER / REVIEWER / APPROVER / SYSADMIN / 多角色组合
环境控制	仅在ENV=development或ENV=test时启用
生产禁用	ENV=production时代码中强制禁用Mock认证，启动时自检
Mock用户工厂规格：

python
# tests/conftest.py（测试环境）
@pytest.fixture
def mock_designer():
    return User(
        user_id="test-designer-001",
        username="designer01",
        roles=["DESIGNER"],
        ad_groups=["DESIGNER_GROUP"]
    )

# app/core/auth_mock.py（开发环境）
# 开发环境下，登录页提供角色下拉选择，直接生成对应JWT
（2）测试AD域搭建

需求项	规格
工具	Samba 4 AD DC（Docker容器）
用途	集成测试中验证真实LDAP绑定和安全组映射
测试账号	designer01, checker01, reviewer01, approver01, admin01
测试安全组	DESIGNER_GROUP, CHECKER_GROUP, REVIEWER_GROUP, APPROVER_GROUP, ADMIN_GROUP
适用场景	CI集成测试阶段（可选）、本地集成测试
Docker Compose配置（开发环境docker-compose.ad.yml）：

yaml
services:
  samba-ad:
    image: nowsci/samba-domain
    environment:
      DOMAIN: TEST.LOCAL
      ADMIN_PASSWORD: Test@123
    ports:
      - "389:389"
      - "636:636"
    volumes:
      - ad-data:/var/lib/samba
（3）认证测试用例

测试编号	测试用例	预期结果
AUTH-T-001	有效AD账号登录	返回200 + JWT令牌
AUTH-T-002	无效密码登录	返回401
AUTH-T-003	无令牌访问受保护端点	返回401
AUTH-T-004	无效/过期令牌访问	返回401
AUTH-T-005	AD安全组正确映射为系统角色	JWT中包含正确角色
AUTH-T-006	多安全组用户获得多角色	JWT中包含全部角色
AUTH-T-007	Mock认证在生产环境被禁用	启动失败或返回403
AUTH-T-008	令牌过期后刷新流程	刷新令牌可获取新令牌
验收标准：

Mock认证在开发/测试环境可用

生产环境Mock认证完全禁用（启动自检）

测试AD容器可启动并支持LDAP绑定

上述8个测试用例全部通过


3.2.5 CI/CD流水线
需求编号：P0-CICD-001
功能描述：配置自动化构建、测试和部署流水线。

流水线阶段：

阶段	命令	失败条件
Lint（后端）	uv run ruff check .	任何error
Type Check	uv run mypy app/	任何error
单元测试	uv run pytest tests/ --cov=app --cov-report=term-missing	测试失败或覆盖率<80%
Golden Test	uv run pytest tests/golden/	结果偏差>1e-12
Lint（前端）	npm run lint	任何error
前端构建	npm run build	构建失败
Docker镜像构建	docker build -t process-calc:latest .	构建失败
验收标准：

代码提交触发流水线自动执行

所有阶段通过后方可合并到主分支

流水线结果通过Webhook通知到团队

3.2.6 CLAUDE.md开发规范
需求编号：P0-DOC-001
功能描述：创建Claude Code项目级配置文件。

内容要求：

markdown
# CLAUDE.md

## 项目概述
工艺专用综合计算软件——Web版

## 技术栈
- 前端：React 18 + TypeScript + Ant Design + Zustand
- 后端：Python 3.12 + FastAPI + SQLAlchemy 2.0 + Alembic
- 数据库：PostgreSQL 16
- 计算库：chemicals, thermo, coolprop, scipy, sympy, fluids

## 编码规范
- Python：Ruff规则（line-length=100, target-version=py312）
- TypeScript：ESLint + Prettier
- 类型注解：所有Python函数必须有完整类型注解
- 浮点数：使用numpy.float64，禁止float32

## 常用命令
- 后端开发：uv run uvicorn app.main:app --reload
- 数据库迁移：uv run alembic upgrade head
- 单元测试：uv run pytest tests/ -v
- 前端开发：npm run dev
- 前端构建：npm run build

## 架构约定
- API路径：/api/v1/{module}/{resource}
- 数据访问：Repository模式
- 版本管理：V主.次.修订
- 状态机：DRAFT → CHECKING → ... → APPROVED

## 模块开发模板
[各模块开发时的标准模板结构]
验收标准：CLAUDE.md提交至仓库根目录，团队评审通过。

3.3 非功能需求
3.3.1 性能需求
指标	要求
后端API响应时间（健康检查）	≤100ms
数据库迁移执行时间（全量）	≤5分钟
前端首屏加载时间	≤3秒（开发环境）
CI/CD流水线总执行时间	≤15分钟
3.3.2 安全性需求
指标	要求
密码传输	通过HTTPS加密
令牌存储	前端内存存储，不持久化
数据库连接	使用参数化查询，防止SQL注入
API认证	所有/api/v1/*端点（除login和health）必须验证JWT
日志脱敏	日志中不记录密码、令牌
3.3.3 可靠性需求
指标	要求
后端异常处理	所有未捕获异常返回统一500 JSON格式
数据库连接失败	返回503并记录错误日志
前端网络异常	显示友好错误提示
3.3.4 可维护性需求
指标	要求
代码覆盖率	后端核心代码覆盖率≥80%
静态检查	Ruff零error、mypy零error
文档	所有API端点有OpenAPI描述
日志	结构化JSON日志，包含trace_id
3.4 数据需求
P0阶段创建的数据库Schema必须满足以下数据完整性要求：

约束类型	要求
主键	所有表使用UUID主键
外键	所有关联字段建立外键约束
唯一约束	project_no唯一、stream_name+project_id唯一；位号终身唯一——(project_id, tag_number/line_no) 覆盖含 OBSOLETE 的全部记录，弃用不释放、永不复用（SUP-007/ADR-0009）
索引	外键列、常用查询列（project_id、tag_number、sign_status）建立索引
JSONB	复杂数据结构使用JSONB存储，支持索引查询
记录哈希	业务记录表含 record_hash（SHA-256，数值规范化舍入 6 位有效数字后计算，仅计算结果/设计参数字段参与）；版本快照仅存于交付物层（deliverable_versions）与变更前快照（record_change_snapshots）
第四部分：附录
4.1 系统模型图
4.1.1 P0阶段组件架构
text
┌─────────────────────────────────────────────────────────┐
│                     前端（React 18）                     │
│  ┌─────────┐  ┌─────────┐  ┌──────────────────────┐    │
│  │ Login   │  │ Layout  │  │ Router（占位）         │    │
│  │ Page    │  │ Shell   │  │                      │    │
│  └────┬────┘  └────┬────┘  └──────────┬───────────┘    │
│       │            │                  │                 │
│       └────────────┴──────────────────┘                 │
│                    │ HTTPS                              │
└────────────────────┼────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│                  FastAPI 后端                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐      │
│  │ Auth     │  │ Health   │  │ Database         │      │
│  │ Module   │  │ Check    │  │ Session          │      │
│  └────┬─────┘  └────┬─────┘  └────────┬─────────┘      │
│       │             │                 │                 │
│       ▼             ▼                 ▼                 │
│  ┌──────────────────────────────────────────────────┐  │
│  │            SQLAlchemy 2.0 ORM                    │  │
│  └──────────────────────┬───────────────────────────┘  │
│                         │                                │
└─────────────────────────┼────────────────────────────────┘
                          │
┌─────────────────────────▼────────────────────────────────┐
│                  PostgreSQL 16                            │
│  ┌──────────────────────────────────────────────────┐   │
│  │  全部业务表（见3.2.3表清单）                      │   │
│  └──────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────┘
4.2 待确定问题列表
编号	问题	影响	建议解决方案	状态
P0-OPEN-001	公司AD域是否支持LDAP简单绑定？	认证实现方式	需与IT部门确认	待确认
P0-OPEN-002	内网Docker镜像仓库是否可用？	CI/CD部署方式	使用内部Harbor或Azure Container Registry	待确认
P0-OPEN-003	前端令牌刷新策略：静默刷新还是弹窗重新登录？	用户体验	建议采用静默刷新+失败后弹窗	待确认
P0-OPEN-004	Golden Test基准数据由谁提供？	浮点确定性验证	由核心算法开发阶段（P4）补充	待P4阶段解决

## 版本历史

| 版本 | 日期 | 修改内容 | 编制人 |
|---|---|---|---|
| V1.0 | 2026-08-27 | 初始版本 | 联合项目组 |
| V1.1 | 2026-08-28 | incorporate SUP-007：文件标识改 PCS 前缀；表清单重构（业务表移除 version 字段、新增交付物与变更域 8 张表、streams 门禁字段、data_lineage 哈希锚定）；数据需求增加位号终身唯一与记录哈希；不创建 xxx_History 表 | 联合项目组 |
| V1.2 | 2026-08-29 | incorporate ADR-0019~0022：streams 表新增 10 字段（气液组成/数据模式/估算/虚拟组分/化验报告/设备连接 upstream_*+change_type）；新增 stream_state_points 表（工况快照，无设备连接字段）；新增 4 组枚举（StreamDataMode/StreamCaseType/StreamStatePointSourceType/StreamChangeType） | 联合项目组 |

