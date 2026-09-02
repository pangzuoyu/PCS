PCS-DICT-ALL-003 V3.5（equipment_list 字段对齐版）
文件标识	PCS-DICT-ALL-003
当前版本	V3.5
发布日期	2026-09-02
变更来源	V3.4 + P2 Sprint 2 Task 3.1/3.2/3.3 三次 alembic 迁移

第一部分：V3.5 增量变更摘要
1.1 增量分类
类别	内容	来源
🟢 equipment_list 字段扩容	equipment_list 新增 47 列（标识 6 / 类型 5 / 来源 4 / 工程 9 / 采购 12 / 图纸 3 / 交付 5 / 安装 5 / 重量 4 / 实际数据 2）	P2 Sprint 2 Task 3.2/3.3 迁移
🟢 equipment_list 命名修正	equipment_list 修正 7 个命名（vendor_id→vendor 字符串、6 个 rename）	P2 Sprint 2 Task 3.1 迁移
🟡 ORM↔DICT 命名漂移	equipment_list 的 `equipment_status`/`procurement_status` 实为两独立列，非 rename；V3.5 明确裁决	本 V3.5
🟡 ORM↔DICT Schema 漂移	详见第三部分：5 项漂移需后续处理	本 V3.5

1.2 表数量不变：53 表。

第二部分：equipment_list V3.5 增量字段清单（54 项）
2.1 V3.4 → V3.5 新增列（来自 P2 Sprint 2 三次迁移）

迁移 ID	新增列数	迁移描述
p2_sprint2_equipment_naming_fix	7（含 1 个三步走 FK→字符串改造 + 6 个 rename）	命名修正（详见 2.2）
p2_sprint2_equipment_procurement_delivery	30	采购 12 + 图纸 3 + 交付 5 + 安装 5 + 重量 4
p2_sprint2_equipment_engineering	21（实际净增 19，2 个已存在跳过）	工程 9 + 标识 6 + 类型 5 + 来源 4 + 实际数据 2（含已存在）

2.2 V3.5 设备字段总表（93 列 = V3.4 基础 38 列 + 本次新增 55 列）

分组	字段名	类型	必填	说明
**基础（V3.1 既有）**	`equipment_id`	UUID PK	✅	设备主键
	`equipment_name`	String(200)	✅	设备英文名称（V3.5 显式记录）
	`equipment_type_project_id`	UUID nullable	❌	复合 FK 第 1 段（指向 equipment_type_codes.project_id）
	`type_code`	String(5) FK	✅	复合 FK 第 2 段
	`equipment_description`	String(500)	❌	设备英文描述（V3.4 rename: description → equipment_description）
	`source_module`	String(30)	❌	来源模块（PIPING / PUMP / MANUAL）
	`source_record_id`	UUID nullable	❌	多态源记录 PK
	`vendor`	String(200)	❌	供应商名称（V3.5 命名修正：原 vendor_id FK 改造为字符串快照）
	`vendor_model`	String(100)	❌	供应商型号
	`design_parameters_json`	JSONB nullable	❌	设计参数 JSON（设备主数据表）
	`procurement_status`	String(30)	❌	采购状态（V3.5 澄清：与 equipment_status 是两个独立字段，非 rename）
	`equipment_status`	Enum(N/E/D/M/F)	✅	设备生命周期分类（V3.5 澄清：P1 Sprint 3 新增，非 procurement_status rename）
	`calc_status`	Enum	✅	计算状态（ADR-0025）
	`actual_data_status`	Enum	✅	实际数据状态（ADR-0025）
	`deliverable_id`	UUID nullable	❌	关联交付物（无 FK 约束）
	`record_hash`	String(64)	✅	仅设计参数参与哈希（商务/采购字段不参与）
	`tag_number`	String(50)	✅	[UNIQUE: project_id+tag_number]
**V3.4 rename**	`installation_location`	String(200)	❌	（V3.4 rename: install_location → installation_location）
	`net_weight`	Float	❌	净重 kg（V3.4 rename: weight_kg → net_weight）
	`paint`	String(100)	❌	涂漆规格（V3.4 rename: paint_spec → paint）
	`process_engineering_remarks`	Text	❌	工艺工程备注（V3.4 rename: engineering_notes → process_engineering_remarks）
	`flowsheet_drawing_number`	String(100)	❌	流程图号（V3.4 rename: drawing_no → flowsheet_drawing_number）
**采购字段组**	`alternate_vendor`	String(200)	❌	备选供应商
	`order_date`	Date	❌	下单日期
	`purchase_order_number`	String(100)	❌	采购订单号
	`cost`	Numeric(18,2)	❌	成本
	`cost_currency`	String(10)	❌	币种
	`cost_source`	String(200)	❌	成本来源
	`cost_year`	Integer	❌	成本年份
	`gpe_spec_number`	String(100)	❌	GPE 规格书编号
	`gpe_spec_status`	String(20)	❌	GPE 规格书状态
	`specification_priority`	String(100)	❌	规格书优先级
**图纸字段组**	`approval_drawing_received_date`	Date	❌	审批图收到日期
	`approval_drawing_return_date`	Date	❌	审批图返回日期
	`certified_drawing_received_date`	Date	❌	认证图收到日期
**交付字段组**	`delivery_date`	Date	❌	交付日期
	`actual_received_date`	Date	❌	实际收到日期
	`forecast_on_site`	Date	❌	预计到场日期
	`actual_on_site`	Date	❌	实际到场日期
	`storage_location`	String(200)	❌	存放位置
**安装字段组**	`installation_contract_number`	String(100)	❌	安装合同号
	`installation_notes`	String(500)	❌	安装备注
	`installation`	String(50)	❌	安装方式（MEI/吊装/现场组装）
	`unloading`	String(200)	❌	卸车方式
	`loading_by`	String(100)	❌	装车负责人
**重量字段组**	`empty_weight`	Float	❌	空重 kg
	`full_weight`	Float	❌	满重 kg
	`weigh_cells`	Boolean	❌	称重传感器
**来源字段组**	`in_package`	Boolean	❌	是否成套设备内
	`data_sources`	String(200)	❌	数据来源（PREL/ESR/PID Rule）
	`tag_in_3d`	Boolean	❌	是否已 3D 建模
	`tag_in_esr`	Boolean	❌	是否在 ESR 中
**标识字段组**	`equipment_name_cn`	String(100)	❌	设备中文名称
	`package_no`	String(50)	❌	成套包号（如 RE-002）
	`sub_project`	String(20)	❌	子项目（ISBL/OSBL）
	`unit_no`	String(20)	❌	单元号（如 5000）
	`unit_name`	String(100)	❌	单元名称
**类型字段组**	`equipment_sub_type`	String(50)	❌	设备子类型（如 Shell&Tube）
	`equipment_category`	String(30)	❌	设备大类（静设备/转动/成套等）
	`is_pressure_vessel`	Boolean	❌	是否压力容器
	`pressure_vessel_category`	String(10)	❌	压力容器类别（Ⅰ/Ⅱ/Ⅲ）
**工程字段组**	`process_engineer`	String(100)	❌	工艺工程师
	`detail_engineer`	String(100)	❌	详细设计工程师
	`pid_drawing_number`	String(100)	❌	P&ID 图号
	`pid_status`	String(10)	❌	P&ID 状态
	`dimensions`	String(100)	❌	外形尺寸
	`registration_number`	String(100)	❌	压力容器注册号
	`emts_number`	String(100)	❌	设备物料跟踪系统号
	`mst_number`	String(100)	❌	材料规格跟踪号
**RecordMixin 通用字段**（+ equipment_status/calc_status/actual_data_status 已列出）	`sign_status`	Enum	✅	签名状态
	`approval_step`	Integer	❌	当前审批步
	`approval_depth`	Integer	✅	审批深度
	`approval_role`	String(30)	❌	当前审批角色
	`locked_by_deliverable`	Boolean	✅	被交付物锁定
	`change_pending_since`	datetime	❌	变更挂起起始时间
	`change_resolved_by`	String(64)	❌	变更解决人
	`change_resolved_at`	datetime	❌	变更解决时间
	`change_abandoned_at`	datetime	❌	变更放弃时间
	`change_abandoned_reason`	String(500)	❌	变更放弃原因
	`obsoleted_reason`	String(200)	❌	作废原因
	`obsoleted_by`	UUID	❌	作废人
	`obsoleted_at`	datetime	❌	作废时间
	`obsoleted_via_deliverable_id`	UUID	❌	通过交付物作废
	`reversal_requested_at`	datetime	❌	撤销请求时间
	`reversal_requested_by`	UUID	❌	撤销请求人
	`reversal_reason`	String(500)	❌	撤销原因
	`reversal_approved_by`	UUID	❌	撤销批准人
	`reversal_approved_at`	datetime	❌	撤销批准时间
	`project_id`	UUID FK	✅	项目主键
	`workspace_id`	UUID FK	✅	工作区主键
	`created_by`	UUID	❌	创建人
	`created_at`	datetime	✅	创建时间
	`updated_at`	datetime	❌	更新时间

合计：约 93 列（含 V3.1 既有列 + V3.4 rename 6 + V3.5 新增约 47）。

2.3 与 V3.4 差异
V3.4 未覆盖 equipment_list 详细字段列表（仅在 §4.2 列出 6 个命名偏差裁决）。
V3.5 补全 equipment_list 的完整字段清单，并将 P2 Sprint 2 三次迁移新增列全部纳入。

第三部分：Schema 漂移审计（V3.5 发布后）
3.1 ORM↔DICT 漂移明细

本次审计通过手工 diff `pcs-backend/docs/schema_compact_orm.md` 与 `spec/schema_compact_dict.md` 完成。
目标漂移 = 0。实际漂移 = 5 项（详见下表）。

方向	字段	状态	说明
ORM-ahead（不在 DICT）	`equipment_name`	String(200)	🟡 已知偏差	V3.1 既有列，V3.5 已加入 DICT，漂移消除
ORM-ahead（不在 DICT）	`equipment_type_project_id`	UUID	🟡 已知偏差	复合 FK 第 1 段，V3.5 已加入 DICT，漂移消除
ORM-ahead（不在 DICT）	`procurement_status`	String(30)	🟡 已知偏差	V3.1 既有列，V3.5 已加入 DICT 并澄清与 equipment_status 关系
ORM-behind（DICT 列未落 ORM）	`actual_key_parameter_json`	JSONB	🔴 真实漂移	原 spec 已定义，ORM 未实现；列入 P2 Sprint 3 跟进
DICT-stale（DICT 残留但 ORM 已移除）	`vendor_id`	UUID FK	🟢 已处理	P2 Sprint 2 Task 3.1 三步走迁移已删除，schema_compact_dict.md 同步更新

3.2 漂移结论
- **可消除漂移**：3 项 ORM-ahead 字段（equipment_name / equipment_type_project_id / procurement_status）通过 V3.5 显式纳入 DICT 解决。
- **真实遗留漂移**：1 项（`actual_key_parameter_json`）需后续 Sprint 补 ORM 列。
- **已正确处理漂移**：1 项（`vendor_id`）通过迁移删除，DICT 同步。
- **本 V3.5 发布后净漂移 = 1**（`actual_key_parameter_json` 待落地）。

3.3 验证证据
- ORM compact：`pcs-backend/docs/schema_compact_orm.md` 第 92-93 行（equipment_list 93 列）
- DICT compact：`spec/schema_compact_dict.md` 第 626-695 行（equipment_list 字段组）
- 手工 diff 命令：
  ```bash
  awk '/^### equipment_list$/{f=1; next} f && /^### /{exit} f' \
      pcs-backend/docs/schema_compact_orm.md | tr ',' '\n' \
      | awk -F'|' '{print $1}' | sort > /tmp/orm.txt
  # 类似处理 DICT 端（含 RecordMixin 展开）
  comm -23 /tmp/orm.txt /tmp/dict.txt  # ORM-ahead
  comm -13 /tmp/orm.txt /tmp/dict.txt  # DICT-ahead
  ```

第四部分：保留的 V3.4 内容
4.1 ADR-0023：equipment_type_codes 复合 PK
保留，参见 V3.4 §5.1。

4.2 ADR-0024：record_change_snapshots.snapshot_status
保留，参见 V3.4 §5.2。

4.3 ADR-0025：equipment_list.actual_data_status 语义扩展
保留，参见 V3.4 §5.3。V3.5 新增 `equipment_status` 字段澄清（独立于 procurement_status）。

4.4 SUP-001~014 整合
保留，参见 V3.4 §5.4。

4.5 枚举定义
保留，参见 V3.4 §5.5。V3.5 新增：`equipment_status` enum(N/E/D/M/F)。

第五部分：版本历史
版本	日期	修改内容
V3.0	2026-08-29	初始 53 表
V3.1	2026-08-29	ADR-0023
V3.2	2026-09-01	ADR-0024
V3.3	2026-09-01	ADR-0025 + AuditAction 完整枚举 + PCS-DICT-007-SUP-001~014 全部整合
V3.4	2026-09-02	DICT→ORM 现实（data_lineage / audit_logs）+ 配置层 7 表 ORM 修正 + 21 处命名偏差裁决
V3.5	2026-09-02	equipment_list 完整字段对齐（54 项）+ `equipment_status`/`procurement_status` 关系澄清 + Schema 漂移审计

V3.5 完。
