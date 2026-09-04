PCS-DICT-ALL-003 V3.4（Schema 审计同步版）
文件标识	PCS-DICT-ALL-003
当前版本	V3.4
发布日期	2026-09-02
变更来源	V3.3 + P2 Sprint 1 Step 0 Schema 审计（D13 裁决）

第一部分：V3.4 增量变更摘要
1.1 增量分类
类别	内容	来源
🟠 DICT→ORM 现实	`data_lineage` / `audit_logs` 重写对齐 ORM 实际列	P2 Sprint 1 Step 0（Schema 审计 §2.1/2.2）
🟢 配置层 ORM 修正	`config_approvals` / `formula_definitions` / `coefficient_tables` / `template_files` / `project_templates` / `numbering_templates` / `doc_no_sequences` 7 表 ORM 修正落地	D13 裁决 + alembic `p2_sprint1_config_layer_fix`
🟢 命名偏差声明	21 处 ORM↔DICT 命名漂移的官方裁决（DICT 为准，ORM 逐步修正）	Schema 审计 §5
🟢 V3.3 内容保留	ADR-0023/0024/0025 + SUP-001~014 整合不变	—

1.2 表数量不变：53 表。

第二部分：DICT→ORM 现实（2 表，P1 已深度消费）
2.1 `data_lineage` V3.4 定义（取代 V3.3 旧定义）

字段名	类型	必填	说明
`lineage_id`	UUID	✅	PK
`record_type`	str(30)	✅	记录类型（PipingResult / PumpResult 等）
`record_id`	UUID	✅	记录 PK
`parent_lineage_id`	UUID FK nullable	❌	自链指向（版本链传播），nullable=无父血缘
`source`	str(50)	✅	来源标签（P1-MVP 抽象源标签：CALCULATION / CIA / MANUAL / SEED 等）
`source_ref_type`	str(30)	❌	P4 扩展：FK 引用模式下的源类型（用于 FK 反查传播）
`source_ref_id`	UUID nullable	❌	P4 扩展：FK 引用模式下的源记录 PK
`actor_user_id`	UUID nullable	❌	触发该血缘的用户（P1-MVP：手动签名者；P2+：审批人）
`actor_ai_agent_id`	UUID nullable	❌	AI agent 触发时填写
`change_summary`	text nullable	❌	变更摘要
`change_diff_json`	JSONB nullable	❌	变更差异 JSON（含旧/新 record_hash）
`occurred_at`	datetime	✅	发生时间

V3.4 相对 V3.3 的变化：
- V3.3 的 `source_type/source_id/source_record_hash/target_type/target_id/target_record_hash/dependency_type/field_name/formula_version/config_version/timestamp` 全部移除
- V3.4 引入 P4 双模式：版本链（`parent_lineage_id`）+ FK 引用（`source_ref_type/source_ref_id`）
- V3.4 的 `record_hash` 存于 `change_diff_json` 内（不再单独成列）

2.2 `audit_logs` V3.4 定义（取代 V3.3 旧定义）

字段名	类型	必填	说明
`audit_id`	UUID	✅	PK
`user_id`	UUID nullable	❌	触发用户（CIA/SYSADMIN 触发时为 NULL）
`action`	str(50)	✅	AuditAction 枚举（~40 值）
`resource_type`	str(50)	❌	资源类型（equipment_list / piping_results 等）
`resource_id`	str(64)	❌	资源 PK（UUID 字符串）
`ip`	INET nullable	❌	客户端 IP（PG INET 类型）
`user_agent`	str(500) nullable	❌	客户端 UA
`request_id`	str(64) nullable	❌	请求链路 ID（用于跨服务追踪）
`detail_json`	JSONB nullable	❌	审计详情（V3.3 的 old_value/new_value/remarks 合并到此）
`occurred_at`	datetime	✅	发生时间

V3.4 相对 V3.3 的变化：
- V3.3 的 `log_id/module/object_id/old_value/new_value/remarks/timestamp/hash/sign_role/sign_step` 全部移除或合并
- V3.4 引入 `ip/user_agent/request_id` 用于现代 web 审计
- V3.4 的旧值/新值合并为 `detail_json`（保留扩展性）

第三部分：配置层 7 表 ORM 修正落地（V3.4 与 ORM 已对齐）
3.1 修正列表

表	ORM 修正	DICT V3.4 确认
`config_approvals`	rename `comments` → `comment`；add `approver_id UUID nullable`	✅
`formula_definitions`	add `asset_id UUID FK nullable`；add `std_source str(200) nullable`；rename `variables_json` → `parameters_json`	✅
`coefficient_tables`	add `asset_id UUID FK nullable`；add `std_source str(200) nullable`；rename `domain` → `applicable_range`	✅
`template_files`	add `asset_id UUID FK nullable`	✅
`project_templates`	add `asset_id UUID FK nullable`；add `checklist_json JSONB nullable`	✅
`numbering_templates`	rename `name` → `template_name`；rename `scope` → `description`	✅
`doc_no_sequences`	add `project_id UUID FK`（DB 列已存在）；声明 UQ(`project_id`+`template_id`+`scope_key`)	✅

3.2 不变项
- `config_versions.asset_id`：ORM 已存在，无需迁移
- `numbering_templates.revision_separate`：ORM 已存在，无需迁移

3.3 迁移 alembic
- 迁移 ID：`p2_sprint1_config_layer_fix`
- down_revision：`p1_sprint3_equipment_status_columns`
- 验证：`alembic upgrade head` ✅（2026-09-02）

第四部分：命名偏差 21 处裁决
4.1 计算模块主键命名（10 处）
DICT 字段	ORM 实际	V3.4 裁决
`vessel_id`	`vessel_calc_id`	DICT 为准，ORM 在 P5 vessel 模块开发时统一 rename
`heat_exchanger_id`	`heat_calc_id`	DICT 为准，ORM 在 P5 heat 模块开发时统一 rename
`cv_id`	`cv_calc_id`	DICT 为准，ORM 在 P5 cv 模块开发时统一 rename
`net_id` (pipe_network)	`network_id`	DICT 为准，ORM 在 P5 pipe_network 模块开发时统一 rename
`restriction_id`	`orifice_calc_id`	DICT 为准，ORM 在 P5 restriction 模块开发时统一 rename
`ct_id` (cooling_tower)	`ct_calc_id`	DICT 为准，ORM 在 P5 cooling_tower 模块开发时统一 rename
`psychro_id`	`psychro_calc_id`	DICT 为准，ORM 在 P5 psychro 模块开发时统一 rename
`sep_equip_id`	`sep_calc_id`	DICT 为准，ORM 在 P5 sep_equip 模块开发时统一 rename
`filter_id` (filtration)	`filter_calc_id`	DICT 为准，ORM 在 P5 filtration 模块开发时统一 rename
`channel_id` (open_channel)	`channel_calc_id`	DICT 为准，ORM 在 P5 open_channel 模块开发时统一 rename

4.2 equipment_list 字段命名（6 处）
DICT 字段	ORM 实际	V3.4 裁决
`equipment_description`	`description`	已在 `p1_sprint3_nullable_equipment_type_codes` 后处理，ORM P3 集成层统一 rename
`installation_location`	`install_location`	同上
`net_weight`	`weight_kg`	同上
`paint`	`paint_spec`	同上
`process_engineering_remarks`	`engineering_notes`	同上
`flowsheet_drawing_number`	`drawing_no`	同上

4.3 其他命名偏差（5 处）
表	DICT	ORM	V3.4 裁决
`numbering_templates`	`template_name`	`name`	本 V3.4 已修正（迁移落地）
`numbering_templates`	`description`	`scope`	本 V3.4 已修正
`coefficient_tables`	`applicable_range`	`domain`	本 V3.4 已修正
`formula_definitions`	`parameters_json`	`variables_json`	本 V3.4 已修正
`config_approvals`	`comment`	`comments`	本 V3.4 已修正

第五部分：保留的 V3.3 内容
5.1 ADR-0023：equipment_type_codes 复合 PK
保留，参见 V3.3 §2.1。

5.2 ADR-0024：record_change_snapshots.snapshot_status
保留，参见 V3.3 §2.2。

5.3 ADR-0025：equipment_list.actual_data_status 语义扩展
保留，参见 V3.3 §2.4。

5.4 SUP-001~014 整合
保留，参见 V3.3 第三部分。

5.5 枚举定义
保留，参见 V3.3 第四部分（SnapshotStatus / AuditAction / RestrictionElementType / ScrubberType / CraneType / OperatingGrade / InsulationType / DeliveryType）。

第六部分：分阶段修正路线图
阶段	内容	表数	预计
✅ P2 Sprint 1 Step 0（本次）	配置层 7 表 ORM 修正 + DICT V3.4 发布（data_lineage / audit_logs 反向更新）	7 + 2	~4h（完成）
⏭️ P2 Sprint 2	`equipment_list` 完整对齐 DICT V3.3 字段组	1	~3h
⏭️ P4 Task 0	`pump_results` 补 6 列（dependencies + performance_curve + seal_bearing + instrumentation + test_inspection + remark）	1	~3h
⏭️ P5 各模块开发时	vessel / heat / cv / restriction / flare / cooling / sep / filtration / open_channel 逐个展开平铺字段或 data_sheet_json	9	各模块开发时顺带
⏭️ P7 开发时	`cost_est_results` 补 RecordMixin	1	P7 启动时

第七部分：版本历史
版本	日期	修改内容
V3.0	2026-08-29	初始 53 表
V3.1	2026-08-29	ADR-0023
V3.2	2026-09-01	ADR-0024
V3.3	2026-09-01	ADR-0025 + AuditAction 完整枚举 + PCS-DICT-007-SUP-001~014 全部整合
V3.4	2026-09-02	DICT→ORM 现实（data_lineage / audit_logs）+ 配置层 7 表 ORM 修正 + 21 处命名偏差裁决

V3.4 完。
