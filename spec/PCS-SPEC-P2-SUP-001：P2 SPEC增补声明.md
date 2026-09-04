PCS-SPEC-P2-SUP-001：P2 SPEC增补声明
文件标识	PCS-SPEC-P2-SUP-001
当前版本	V1.0
发布日期	2026-09-02
增补基准	PCS-SPEC-P2 V1.0（早期发布）、PCS-DICT-ALL-003 V3.4、ADR-0023~0025、P1-MVP交付报告
适用对象	内部开发团队（后端/前端/测试）
1. 增补目的
P2 SPEC（早期发布）基于DICT V3.0的配置层字段定义。在P0/P1实际执行中，配置层ORM模型经D13全量Schema审计后已对齐至DICT V3.4。本增补声明锁定P2开发使用的实际字段定义、可复用组件清单和配置资产状态机语义，避免Claude Code按旧SPEC执行产生新漂移。

2. 配置层8表字段对齐确认（D13 Step 0结果）
以下为P2开发中实际使用的配置层字段定义（ORM已对齐）：

2.1 config_versions
text
version_id | UUID PK
asset_id | UUID FK→config_assets         ← Step 0修正（ORM已有，无迁移）
version_code | str50
parent_version_id | UUID FK nullable     ← 增强保留（版本链）
change_note | text nullable              ← 增强保留
content_json | jsonb
status | str20
created_by | UUID
created_at | dt
updated_at | dt
2.2 config_approvals
text
approval_id | UUID PK
version_id | UUID FK→config_versions
approver_role | str30                    ← Step 0修正
approver_id | UUID                        ← Step 0修正
decision | str20
comment | str500                         ← Step 0修正（原comments改名）
created_by | UUID
created_at | dt
updated_at | dt
2.3 formula_definitions
text
formula_id | UUID PK
asset_id | UUID FK→config_assets         ← Step 0修正
module | str30
name | str200
expression | text
parameters_json | jsonb                  ← Step 0修正（原variables_json改名）
std_source | str200 nullable             ← Step 0修正
unit_tests_json | jsonb
category | str30 nullable                ← 增强保留
version | str50
status | str20
created_by | UUID
created_at | dt
updated_at | dt
注意：version和status字段是ORM自含的快照字段，实际版本管理通过config_versions表进行。P2公式引擎开发时，formula_definitions保存当前有效版本，config_versions保存历史版本。

2.4 coefficient_tables
text
table_id | UUID PK
asset_id | UUID FK→config_assets         ← Step 0修正
name | str200
applicable_range | str200 nullable       ← Step 0修正（原domain改名）
data_json | jsonb
std_source | str200 nullable             ← Step 0修正
version | str50
status | str20
created_by | UUID
created_at | dt
updated_at | dt
2.5 template_files
text
template_id | UUID PK
asset_id | UUID FK→config_assets         ← Step 0修正
name | str200
file_type | str10
file_path | str500
placeholders_json | jsonb
version | str50
status | str20
created_by | UUID
created_at | dt
updated_at | dt
2.6 project_templates
text
template_id | UUID PK
asset_id | UUID FK→config_assets         ← Step 0修正
name | str200
industry | str30 nullable                ← 增强保留
default_config_json | jsonb
checklist_json | jsonb nullable          ← Step 0修正
version | str50
status | str20
created_by | UUID
created_at | dt
updated_at | dt
2.7 numbering_templates
text
template_id | UUID PK
template_name | str200                   ← Step 0修正（原name改名）
description | str500 nullable            ← Step 0修正（原scope改名）
segments_json | jsonb
separator | str10
revision_separate | bool                 ← ORM已有，无迁移
deliverable_mappings_json | jsonb
status | str20
created_by | UUID
created_at | dt
updated_at | dt
2.8 doc_no_sequences
text
sequence_id | UUID PK
project_id | UUID FK→projects            ← ORM模型已更新（P1迁移已建DB列）
template_id | UUID FK→numbering_templates
scope_key | str100
current_value | int
created_by | UUID
created_at | dt
updated_at | dt
[UNIQUE: project_id + template_id + scope_key]
3. 配置资产状态机（独立于记录层9态）
3.1 状态定义
状态	标识	说明
DRAFT	DRAFT	草稿
PENDING	PENDING	提交审批
APPROVED	APPROVED	审核通过
PUBLISHED	PUBLISHED	发布生效
OBSOLETE	OBSOLETE	作废
3.2 状态流转
text
DRAFT ──提交审批──► PENDING ──审核通过──► APPROVED ──发布──► PUBLISHED
  ▲                     │                │                 │
  │◄────驳回─────────────┘                │                 │
  │                                      │                 │
  │              创建新版本（修改已发布）  │                 │
  │◄─────────────────────────────────────┘                 │
  │                                                        │
  └────────────────────────── 作废 ◄───────────────────────┘
3.3 审批流差异
配置类别	审批层级
公式（CATEGORY_2）	双重审批（工艺负责人+系统管理员）
系数（CATEGORY_3）	单层审批（工艺负责人）
模板（CATEGORY_4）	单层审批（工艺负责人）
项目模板（CATEGORY_1）	单层审批（工艺负责人）
标准数据库（CATEGORY_5）	单层审批（工艺负责人）
复用设备库（CATEGORY_6）	单层审批（工艺负责人）
4. P1-MVP可复用组件
组件	P2使用场景	说明
AuditService(session).write()	公式/系数/模板修改审计	直接复用，action使用CONFIG相关枚举
AuditAction枚举	新增CONFIG动作	需追加：CONFIG_ASSET_CREATED/CONFIG_VERSION_CREATED/CONFIG_ASSET_PUBLISHED
StateMachineService	配置资产DRAFT→PUBLISHED流转	需适配配置状态机（5态），不复用记录层9态
双引擎（sync+async）	配置API全部async	复用P1基础设施
commit_or_rollback	配置写操作	复用P1端点模板
require_formal_workspace	不适用	CONFIG是全局配置，非项目级
5. P2 Sprint 1核心开发范围（基于本增补声明）
模块	内容	关键约定
公式引擎	SymPy解析+AST受限执行+热更新+单元测试运行器	公式表达式使用parameters_json定义参数
系数库	表格编辑+批量修改	data_json存储条件分行数据
模板管理	文件上传+占位符解析	placeholders_json自动解析
审批流	DRAFT→PENDING→APPROVED→PUBLISHED	公式走双重审批
编号模板	segments_json+deliverable_mappings_json	P1.2编号分配消费
6. 需新增的AuditAction枚举
P2开发时在app/models/enums.py的AuditAction中追加：

python
# === CONFIG（P2新增） ===
CONFIG_ASSET_CREATED = "CONFIG_ASSET_CREATED"
CONFIG_VERSION_CREATED = "CONFIG_VERSION_CREATED"
CONFIG_ASSET_SUBMITTED = "CONFIG_ASSET_SUBMITTED"      # DRAFT→PENDING
CONFIG_ASSET_APPROVED = "CONFIG_ASSET_APPROVED"        # PENDING→APPROVED
CONFIG_ASSET_PUBLISHED = "CONFIG_ASSET_PUBLISHED"      # APPROVED→PUBLISHED
CONFIG_ASSET_OBSOLETED = "CONFIG_ASSET_OBSOLETED"      # →OBSOLETE
CONFIG_ASSET_REJECTED = "CONFIG_ASSET_REJECTED"        # PENDING→DRAFT
CONFIG_VERSION_DIFF_VIEWED = "CONFIG_VERSION_DIFF_VIEWED"  # 版本对比查看
7. 版本历史
版本	日期	修改内容
V1.0	2026-09-02	P2 SPEC增补声明：配置层字段对齐+P1复用组件+配置状态机
P2 SPEC增补声明完。 本文档与PCS-SPEC-P2 V1.0合并使用，构成P2开发的完整依据。P2 Sprint 1核心开发以此为准。
