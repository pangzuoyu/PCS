PCS 53表紧凑对照表（DICT版）
来源：DICT-ALL-003 V3.5（V3.5 equipment_list 字段对齐版，2026-09-02）| 用途：Schema审计+快速查字段 | 共53表

项目与物流（3表）
projects
text
project_id|UUID PK|NOT NULL
project_no|str50|NOT NULL [UNIQUE]
project_name|str200|NOT NULL
project_name_cn|str200
owner_company|str200|NOT NULL
contractor_company|str200
engineer_name|str200
dd_contractor_name|str200
feed_contractor_name|str200
location|str500|NOT NULL
site_address|str500
project_type|str30|NOT NULL
design_phase|str30|NOT NULL
total_capacity|float
total_capacity_unit|str20
plant_count|int
single_plant_capacity|float
single_plant_capacity_unit|str20
reference_plant|str200
unit_system|str20|NOT NULL
bedd_json|jsonb
workspace_id|UUID FK|NOT NULL
status|str20|NOT NULL
created_by|UUID
created_at|dt|NOT NULL
updated_at|dt
streams
text
stream_id|UUID PK|NOT NULL
project_id|UUID FK|NOT NULL
workspace_id|UUID FK|NOT NULL
stream_name|str100|NOT NULL [UNIQUE:project_id+stream_name]
description|str500
phase|str20
temp|float
press|float
mass_flow|float
molar_flow|float
volumetric_flow|float
std_gas_flow|float
composition_json|jsonb
vapor_composition_json|jsonb
liquid_composition_json|jsonb
density|float
viscosity_dynamic|float
viscosity_kinematic|float
thermal_conductivity|float
specific_heat|float
molecular_weight|float
compressibility_factor|float
vapor_fraction|float
enthalpy|float
entropy|float
bulk_density_min|float
bulk_density_max|float
true_density|float
particle_size_avg|float
particle_size_range|str100
particle_shape|str100
repose_angle|float
vessel_cone_angle|float
distillation_json|jsonb
sara_json|jsonb
elemental_json|jsonb
metals_json|jsonb
feedstock_specs_json|jsonb
product_specs_json|jsonb
data_mode|str20|NOT NULL
property_estimation_json|jsonb
pseudo_components_json|jsonb
lab_report_ref|str200
upstream_stream_id|UUID FK
upstream_equipment_type|str30
upstream_equipment_id|UUID
change_type|str30
source_type|str30|NOT NULL
source_file|str200
sign_status|enum(streamsignstatus)|NOT NULL
approval_step|int
approval_depth|int|NOT NULL
checked_by|UUID
checked_at|dt
record_hash|str64|NOT NULL
last_change_reason|str30
last_change_note|str500
last_changed_by|UUID
last_changed_at|dt
created_by|UUID
created_at|dt|NOT NULL
updated_at|dt
stream_state_points
text
state_point_id|UUID PK|NOT NULL
stream_id|UUID FK|NOT NULL
state_label|str50|NOT NULL
case_type|str20|NOT NULL
temp|float|NOT NULL
press|float|NOT NULL
phase|str20|NOT NULL
vapor_fraction|float
mass_flow|float|NOT NULL
composition_json|jsonb|NOT NULL
vapor_composition_json|jsonb
liquid_composition_json|jsonb
density|float
viscosity_dynamic|float
enthalpy|float
entropy|float
record_hash|str64|NOT NULL
estimated_flags_json|jsonb
profile_json|jsonb
source_type|str30|NOT NULL
created_at|dt|NOT NULL
配置层（11表）
config_assets
text
asset_id|UUID PK|NOT NULL
category|str30|NOT NULL
name|str200|NOT NULL
description|str500
current_version|str50|NOT NULL
status|str20|NOT NULL
content_json|jsonb
created_by|UUID
created_at|dt|NOT NULL
updated_at|dt
config_versions
text
version_id|UUID PK|NOT NULL
asset_id|UUID FK|NOT NULL
version_code|str50|NOT NULL
parent_version_id|UUID FK [Step 0 补：版本链自链]
change_note|text [Step 0 补]
content_json|jsonb|NOT NULL
status|str20|NOT NULL
created_by|UUID
created_at|dt|NOT NULL
updated_at|dt
config_approvals
text
approval_id|UUID PK|NOT NULL
version_id|UUID FK|NOT NULL
approver_role|str30|NOT NULL
approver_id|UUID [P2 Step 0 补充]
decision|str20|NOT NULL
comment|str500 [P2 Step 0 rename: comments → comment]
created_by|UUID [TimestampMixin]
created_at|dt|NOT NULL [TimestampMixin, 原 timestamp 列已重命名为 created_at]
updated_at|dt [TimestampMixin]
formula_definitions
text
formula_id|UUID PK|NOT NULL
asset_id|UUID FK [P2 Step 0 补充]
module|str30|NOT NULL
category|str30 [Step 0 补：公式分类]
name|str200|NOT NULL
expression|text|NOT NULL
parameters_json|jsonb|NOT NULL [P2 Step 0 rename]
std_source|str200 [P2 Step 0 补充]
unit_tests_json|jsonb|NOT NULL
version|str50 [Step 0 补：版本号]
status|str20|NOT NULL [Step 0 补：公式状态]
created_by|UUID [TimestampMixin]
created_at|dt|NOT NULL [TimestampMixin]
updated_at|dt [TimestampMixin]
coefficient_tables
text
table_id|UUID PK|NOT NULL
asset_id|UUID FK [P2 Step 0 补充]
name|str200|NOT NULL
data_json|jsonb|NOT NULL
applicable_range|str200 [P2 Step 0 rename: domain → applicable_range]
std_source|str200 [P2 Step 0 补充]
version|str50 [Step 0 补]
status|str20|NOT NULL [Step 0 补]
created_by|UUID [TimestampMixin]
created_at|dt|NOT NULL [TimestampMixin]
updated_at|dt [TimestampMixin]
template_files
text
template_id|UUID PK|NOT NULL
asset_id|UUID FK [P2 Step 0 补充]
name|str200|NOT NULL [Step 0 补]
file_type|str10|NOT NULL
file_path|str500|NOT NULL
placeholders_json|jsonb|NOT NULL
version|str50 [Step 0 补]
status|str20|NOT NULL [Step 0 补]
created_by|UUID [TimestampMixin]
created_at|dt|NOT NULL [TimestampMixin]
updated_at|dt [TimestampMixin]
project_templates
text
template_id|UUID PK|NOT NULL
asset_id|UUID FK [P2 Step 0 补充]
name|str200|NOT NULL
industry|str50 [Step 0 补]
checklist_json|jsonb [P2 Step 0 补充]
default_config_json|jsonb|NOT NULL
version|str50 [Step 0 补]
status|str20|NOT NULL [Step 0 补]
created_by|UUID [TimestampMixin]
created_at|dt|NOT NULL [TimestampMixin]
updated_at|dt [TimestampMixin]
pipe_classes
text
class_id|str20 PK|NOT NULL
class_name|str200|NOT NULL
material_standard|str100|NOT NULL
corrosion_allowance|float|NOT NULL
design_pressure|float|NOT NULL
design_temperature|float|NOT NULL
fluid_service|str100
allowable_stress_json|jsonb|NOT NULL
dn_series_json|jsonb|NOT NULL
sch_series_json|jsonb|NOT NULL
flange_class|str20|NOT NULL
fitting_type|str50
branch_table_json|jsonb
source|str20|NOT NULL
version|str50|NOT NULL
status|str20|NOT NULL
created_by|UUID
created_at|dt|NOT NULL
updated_at|dt
project_pipe_classes
text
project_id|UUID PK/FK|NOT NULL
class_id|str20 PK/FK|NOT NULL
enabled|bool|NOT NULL [P2 Sprint 1 补：是否启用]
custom_override_json|jsonb [P2 Sprint 1 补：项目级覆写]
created_by|UUID [TimestampMixin, 原 assigned_by]
created_at|dt|NOT NULL [TimestampMixin, 原 assigned_at]
updated_at|dt [TimestampMixin]
numbering_templates
text
template_id|UUID PK|NOT NULL
template_name|str200|NOT NULL
description|str500
segments_json|jsonb|NOT NULL
separator|str10|NOT NULL
revision_separate|bool|NOT NULL
deliverable_mappings_json|jsonb|NOT NULL
status|str20|NOT NULL
created_by|UUID
created_at|dt|NOT NULL
updated_at|dt
doc_no_sequences
text
sequence_id|UUID PK|NOT NULL
project_id|UUID FK|NOT NULL [UNIQUE:project_id+template_id+scope_key]
template_id|UUID FK|NOT NULL
scope_key|str100|NOT NULL
current_value|int|NOT NULL
created_by|UUID [TimestampMixin]
created_at|dt|NOT NULL [TimestampMixin]
updated_at|dt [TimestampMixin]
计算模块（16表）
RecordMixin通用字段（以下16表均包含，+piping_results特殊）：
project_id|UUID FK! · workspace_id|UUID FK! · sign_status|enum(recordsignstatus)! · record_hash|str64! · approval_step|int · approval_depth|int! · approval_role|str30 · locked_by_deliverable|bool! · change_pending_since|dt · change_resolved_by|str64 · change_resolved_at|dt · change_abandoned_at|dt · change_abandoned_reason|str500 · obsoleted_reason|str200 · obsoleted_by|UUID · obsoleted_at|dt · obsoleted_via_deliverable_id|UUID · reversal_requested_at|dt · reversal_requested_by|UUID · reversal_reason|str500 · reversal_approved_by|UUID · reversal_approved_at|dt · created_by|UUID · created_at|dt! · updated_at|dt

TaggedRecordMixin额外（除piping外15表）：tag_number|str50! [UNIQUE:project_id+tag_number]

flash_results（RecordMixin，无tag_number）
text
flash_id|UUID PK|NOT NULL
stream_id|UUID FK|NOT NULL
calc_type|str30|NOT NULL
method|str20|NOT NULL
input_json|jsonb|NOT NULL
output_json|jsonb|NOT NULL
+ RecordMixin
piping_results（RecordMixin，无tag_number）
text
pipe_id|UUID PK|NOT NULL
line_no|str50|NOT NULL [UNIQUE:project_id+line_no]
seq_no|int|NOT NULL
line_size|str20|NOT NULL
material_class|str20 FK|NOT NULL
fluid_code|str10|NOT NULL
fluid_name|str100|NOT NULL
fluid_phase|str20|NOT NULL
fluid_category|str10|NOT NULL
toxic_class|str30
pipe_grade|str30
insulation_code|str20
insulation_thickness|float
paint_code|str20
tracing_type|str10
holding_temp|float
source_pid|str50|NOT NULL
line_from|str100|NOT NULL
line_to|str100|NOT NULL
norm_oper_press|float|NOT NULL
max_oper_press|float|NOT NULL
norm_oper_temp|float|NOT NULL
max_oper_temp|float|NOT NULL
alt_norm_oper_press|float
alt_max_oper_press|float
alt_norm_oper_temp|float
alt_max_oper_temp|float
design_press|float|NOT NULL
design_vacuum|float
design_temp|float|NOT NULL
design_min_temp|float
piping_category|str10|NOT NULL
pressure_test_medium|str10|NOT NULL
pressure_test_press|float|NOT NULL
ndt_method|str10
ndt_ratio|float
ndt_tech_level|str10
leak_test_medium|str10
leak_test_press|float
check_class|str5|NOT NULL
cleaning_method|jsonb
stress_analysis_level|str10
remark|str500
+ RecordMixin
pipe_network_results（RecordMixin，无tag_number）
text
net_id|UUID PK|NOT NULL
topology_json|jsonb|NOT NULL
convergence_log_json|jsonb|NOT NULL
flow_distribution_json|jsonb|NOT NULL
+ RecordMixin
pump_results（TaggedRecordMixin）
text
pump_id|UUID PK|NOT NULL
tag_number|str50! [UNIQUE:project_id+tag_number]
basic_info_json|jsonb|NOT NULL
fluid_properties_json|jsonb|NOT NULL
flow_rates_json|jsonb|NOT NULL
dependencies_json|jsonb [D2裁决新增]
suction_calculation_json|jsonb|NOT NULL
discharge_calculation_json|jsonb|NOT NULL
differential_pressure_json|jsonb|NOT NULL
design_pressure_json|jsonb|NOT NULL
power_consumption_json|jsonb|NOT NULL
control_valve_json|jsonb|NOT NULL
equivalent_length_json|jsonb|NOT NULL
pressure_drop_details_json|jsonb|NOT NULL
line_references_json|jsonb|NOT NULL
performance_curve_json|jsonb [D10补]
seal_bearing_json|jsonb [D10补]
instrumentation_json|jsonb [D10补]
test_inspection_json|jsonb [D10补]
remark|text [D10补]
vendor_data_json|jsonb
actual_head|float
actual_efficiency|float
actual_motor_power|float
actual_npshr|float
vendor_model|str200
actual_data_confirmed|bool
+ RecordMixin
psv_results（TaggedRecordMixin）
text
psv_id|UUID PK|NOT NULL
tag_number|str50! [UNIQUE:project_id+tag_number]
set_pressure|float|NOT NULL
relief_capacity|float|NOT NULL
orifice_area|float|NOT NULL
orifice_designation|str10|NOT NULL
inlet_size|str20|NOT NULL
outlet_size|str20|NOT NULL
blowdown|float|NOT NULL
relief_scenario|jsonb|NOT NULL
data_sheet_json|jsonb
calc_sheet_json|jsonb
+ RecordMixin
flare_system_results（TaggedRecordMixin）
text
flare_id|UUID PK|NOT NULL
tag_number|str50! [UNIQUE:project_id+tag_number]
total_relief_load|float|NOT NULL
header_size|str50
kod_size|str50
stack_height|float
radiation_check_json|jsonb
+ RecordMixin
vessel_results（TaggedRecordMixin）
text
vessel_id|UUID PK|NOT NULL
tag_number|str50! [UNIQUE:project_id+tag_number]
volume|float
diameter|float
length_height|float
design_pressure|float
design_temp|float
operating_pressure|float
operating_temp|float
moc|str100
corrosion_allowance|float
insulation|str50
tracing|str10
tower_type|str10
packing_height|float
tray_count|int
data_sheet_json|jsonb
+ RecordMixin
sep_equip_results（TaggedRecordMixin）
text
sep_equip_id|UUID PK|NOT NULL
tag_number|str50! [UNIQUE:project_id+tag_number]
equip_type|str30|NOT NULL
dimensions|str200
efficiency|float
pressure_drop|float
data_sheet_json|jsonb
+ RecordMixin
heat_results（TaggedRecordMixin）
text
heat_exchanger_id|UUID PK|NOT NULL
tag_number|str50! [UNIQUE:project_id+tag_number]
exchanger_category|str20|NOT NULL
general_parameters_json|jsonb|NOT NULL
performance_data_json|jsonb|NOT NULL
heat_transfer_json|jsonb|NOT NULL
construction_json|jsonb|NOT NULL
tube_bundle_json|jsonb
shell_internals_json|jsonb
weights_json|jsonb
air_side_json|jsonb
design_conditions_json|jsonb
material_json|jsonb
connections_json|jsonb|NOT NULL
enthalpy_table_json|jsonb
notes_json|jsonb
ache_data_sheet_json|jsonb
remark|str500
+ RecordMixin
cv_results（TaggedRecordMixin）
text
cv_id|UUID PK|NOT NULL
tag_number|str50! [UNIQUE:project_id+tag_number]
cv_value|float|NOT NULL
flow_rate|float|NOT NULL
pressure_drop|float|NOT NULL
choked_flow|bool|NOT NULL
noise|float
design_condition_json|jsonb
calc_spec_json|jsonb
control_valve_spec_json|jsonb
+ RecordMixin
restriction_results（TaggedRecordMixin）
text
restriction_id|UUID PK|NOT NULL
tag_number|str50! [UNIQUE:project_id+tag_number]
restriction_type|str30|NOT NULL
bore_diameter|float|NOT NULL
perm_pressure_drop|float|NOT NULL
choked_flow|bool|NOT NULL
noise|float
design_condition_json|jsonb
orifice_datasheet_json|jsonb
+ RecordMixin
cooling_tower_results（TaggedRecordMixin）
text
ct_id|UUID PK|NOT NULL
tag_number|str50! [UNIQUE:project_id+tag_number]
duty|float|NOT NULL
water_flow|float|NOT NULL
makeup_water|float|NOT NULL
fan_power|float|NOT NULL
tower_type|str30|NOT NULL
data_sheet_json|jsonb
+ RecordMixin
psychro_results（TaggedRecordMixin）
text
psychro_id|UUID PK|NOT NULL
tag_number|str50! [UNIQUE:project_id+tag_number]
calc_type|str30|NOT NULL
input_json|jsonb|NOT NULL
output_json|jsonb|NOT NULL
+ RecordMixin
open_channel_results（TaggedRecordMixin）
text
channel_id|UUID PK|NOT NULL
tag_number|str50! [UNIQUE:project_id+tag_number]
channel_type|str30|NOT NULL
cross_section_json|jsonb|NOT NULL
flow_rate|float|NOT NULL
depth|float|NOT NULL
velocity|float|NOT NULL
slope|float|NOT NULL
+ RecordMixin
filtration_results（TaggedRecordMixin）
text
filter_id|UUID PK|NOT NULL
tag_number|str50! [UNIQUE:project_id+tag_number]
filter_type|str30|NOT NULL
area|float|NOT NULL
cycle_time|float
pressure_drop|float|NOT NULL
data_sheet_json|jsonb
+ RecordMixin
cost_est_results（TaggedRecordMixin）
text
cost_est_id|UUID PK|NOT NULL
tag_number|str50! [UNIQUE:project_id+tag_number]
equipment_id|UUID FK|NOT NULL
estimated_cost|dec18_2|NOT NULL
currency|str10|NOT NULL
cost_index_year|int|NOT NULL
cost_estimate_json|jsonb
+ RecordMixin
交付物层（6表）
deliverables
text
deliverable_id|UUID PK|NOT NULL
project_id|UUID FK|NOT NULL
deliverable_type|str30|NOT NULL
scope_type|str20|NOT NULL
scope_value|str100|NOT NULL
parent_deliverable_id|UUID FK
doc_no|str200|NOT NULL
doc_no_mode|str20|NOT NULL
numbering_template_id|UUID FK
segment_values_json|jsonb
discipline_code|str2
doc_identifier_code|str3
sequence_no|int
title|str500|NOT NULL
current_rev|str20|NOT NULL
version_purpose|str40|NOT NULL
sign_status|enum(deliverablesignstatus)|NOT NULL
matrix_id|UUID FK|NOT NULL
customer_approval_date|date
customer_approver_name|str100
customer_approval_method|str20
customer_approval_proxy_by|UUID
customer_approval_proxy_at|dt
customer_approval_attachment_id|UUID
customer_approval_is_proxy|bool
created_by|UUID
created_at|dt|NOT NULL
updated_at|dt
[UNIQUE:project_id+deliverable_type+scope_type+scope_value]
[UNIQUE:project_id+doc_no]
deliverable_versions
text
version_id|UUID PK|NOT NULL
deliverable_id|UUID FK|NOT NULL
rev|str20|NOT NULL
version_purpose|str40|NOT NULL
description|text|NOT NULL
record_snapshot_json|jsonb|NOT NULL
signature_summary_json|jsonb|NOT NULL
customer_approval_date|date
pdf_file_path|str500
affected_status|str10
created_by|UUID
created_at|dt|NOT NULL
updated_at|dt
deliverable_record_bindings
text
binding_id|UUID PK|NOT NULL
deliverable_version_id|UUID FK|NOT NULL
record_type|str30|NOT NULL
record_id|UUID|NOT NULL
record_hash|str64|NOT NULL
old_record_hash_before_change|str64
signature_matrices
text
matrix_id|UUID PK|NOT NULL
matrix_name|str200|NOT NULL
module|str30|NOT NULL
doc_type|str30|NOT NULL
version_purpose|str40|NOT NULL
steps_json|jsonb|NOT NULL
status|str20|NOT NULL
created_by|UUID
created_at|dt|NOT NULL
updated_at|dt
project_signature_matrix_bindings
text
binding_id|UUID PK|NOT NULL
project_id|UUID FK|NOT NULL
module|str30|NOT NULL
matrix_id|UUID FK|NOT NULL
created_by|UUID
created_at|dt|NOT NULL
updated_at|dt
customer_approval_attachments
text
attachment_id|UUID PK|NOT NULL
deliverable_version_id|UUID FK|NOT NULL
file_path|str500|NOT NULL
file_name|str200|NOT NULL
file_type|str10|NOT NULL
file_size|int|NOT NULL
uploaded_by|UUID|NOT NULL
uploaded_at|dt|NOT NULL
file_hash|str64|NOT NULL
变更管理（2表）
change_notice_details
text
detail_id|UUID PK|NOT NULL
deliverable_id|UUID FK|NOT NULL [UNIQUE]
change_type|str30|NOT NULL
reason|text|NOT NULL
triggered_by|str20|NOT NULL
source_record_type|str30
created_by|UUID
created_at|dt|NOT NULL
updated_at|dt
record_change_snapshots
text
snapshot_id|UUID PK|NOT NULL
record_type|str30|NOT NULL
record_id|UUID|NOT NULL
record_hash|str64|NOT NULL
data_snapshot_json|jsonb|NOT NULL
snapshot_reason|str20|NOT NULL
snapshot_source|str20|NOT NULL
snapshot_status|str20|NOT NULL [ADR-0024新增]
created_by|UUID
created_at|dt|NOT NULL
集成层（4表）
equipment_list（TaggedRecordMixin）— V3.5 字段对齐（93 列）
text
equipment_id|UUID PK|NOT NULL
equipment_name|str200 [V3.5 显式记录，V3.1 既有]
equipment_type_project_id|UUID [复合 FK 第 1 段，nullable]
type_code|str5 FK|NOT NULL [复合FK:equipment_type_project_id+type_code]
tag_number|str50! [UNIQUE:project_id+tag_number]
equipment_description|str200|NOT NULL [V3.4 rename: description → equipment_description]
equipment_name_cn|str100
package_no|str50
sub_project|str20
unit_no|str20
unit_name|str100
equipment_sub_type|str50
equipment_category|str30
is_pressure_vessel|bool|NOT NULL
pressure_vessel_category|str10
source_module|str30|NOT NULL
source_record_id|UUID
in_package|bool
data_sources|str200
equipment_status|str1|NOT NULL [V3.5 澄清：P1 Sprint 3 新增 enum(N/E/D/M/F)，非 procurement_status rename]
procurement_status|str30|nullable [V3.5 澄清：V3.1 既有采购状态列，与 equipment_status 独立共存]
calc_status|str20|NOT NULL [ADR-0025]
actual_data_status|str20|NOT NULL [ADR-0025]
tag_in_3d|bool
tag_in_esr|bool
design_parameters_json|jsonb
vendor|str200 [V3.5 命名修正：原 vendor_id FK 改造为字符串快照，P2 Sprint 2 Task 3.1 三步走迁移]
alternate_vendor|str200
order_date|date
purchase_order_number|str100
cost|dec18_2
cost_currency|str10
cost_source|str200
cost_year|int
gpe_spec_number|str100
gpe_spec_status|str20
specification_priority|str100
approval_drawing_received_date|date
approval_drawing_return_date|date
certified_drawing_received_date|date
delivery_date|date
actual_received_date|date
forecast_on_site|date
actual_on_site|date
storage_location|str200
installation_location|str200 [V3.4 rename: install_location → installation_location]
installation_contract_number|str100
installation_notes|str500
installation|str50
unloading|str200
loading_by|str100
empty_weight|float
full_weight|float
weigh_cells|bool
net_weight|float [V3.4 rename: weight_kg → net_weight]
paint|str100 [V3.4 rename: paint_spec → paint]
process_engineer|str100
detail_engineer|str100
flowsheet_drawing_number|str100 [V3.4 rename: drawing_no → flowsheet_drawing_number]
pid_drawing_number|str100
pid_status|str10
dimensions|str100
registration_number|str100
emts_number|str100
mst_number|str100
process_engineering_remarks|str500 [V3.4 rename: engineering_notes → process_engineering_remarks]
actual_key_parameter_json|jsonb [V3.5 漂移：spec 已定义但 ORM 未实现，待 Sprint 3 跟进]
vendor_model|str200
deliverable_id|UUID [保留，暂无FK]
+ RecordMixin
equipment_type_codes（ADR-0023复合）
text
project_id|UUID FK [nullable, PK复合]
type_code|str5 PK|NOT NULL
equipment_description|str200|NOT NULL
description_cn|str100
category|str30|NOT NULL
is_process_equipment|bool|NOT NULL
is_pressure_vessel|bool|NOT NULL
source|str200
status|str20|NOT NULL
[UNIQUE:project_id+type_code]
equipment_lib
text
equip_id|UUID PK|NOT NULL
type_code|str5|NOT NULL
size|str200
weight|float
material|str100
standard_drawing_no|str100
process_description|str500
cost|dec18_2
cost_currency|str10
cost_year|int
status|str20|NOT NULL
created_by|UUID
created_at|dt|NOT NULL
updated_at|dt
suppliers
text
supplier_id|UUID PK|NOT NULL
supplier_name|str200|NOT NULL
supplier_type|str30|NOT NULL
contact_json|jsonb
qualification_json|jsonb
rating|str10
approved_by|UUID
approved_date|date
流程横切（6表）
data_lineage（V3.4 重写：DICT→ORM 现实）
text
lineage_id|UUID PK|NOT NULL
record_type|str30|NOT NULL
record_id|UUID|NOT NULL
parent_lineage_id|UUID FK
source|str50|NOT NULL
source_ref_type|str30 [P4 扩展]
source_ref_id|UUID [P4 扩展]
actor_user_id|UUID
actor_ai_agent_id|UUID
change_summary|text
change_diff_json|jsonb
occurred_at|dt|NOT NULL
project_input_checklist（Sprint 1已对齐）
text
input_id|UUID PK|NOT NULL
project_id|UUID FK|NOT NULL
module|str30|NOT NULL
input_name|str200|NOT NULL
input_category|str30|NOT NULL
input_value_json|jsonb
source_type|str30|NOT NULL
status|str30|NOT NULL
verified_by|UUID
verified_at|dt
assumption_reason|str500
last_updated|dt|NOT NULL
workspaces
text
workspace_id|UUID PK|NOT NULL
workspace_type|str20|NOT NULL
owner_id|UUID
project_id|UUID FK
name|str200|NOT NULL
created_at|dt|NOT NULL
last_active_at|dt
retention_days|int
audit_logs（V3.4 重写：DICT→ORM 现实）
text
audit_id|UUID PK|NOT NULL
user_id|UUID
action|str50|NOT NULL [AuditAction ~40 项]
resource_type|str50
resource_id|str64
ip|INET
user_agent|str500
request_id|str64
detail_json|jsonb
occurred_at|dt|NOT NULL
users
text
user_id|UUID PK|NOT NULL
username|str100|NOT NULL [UNIQUE]
display_name|str200|NOT NULL
email|str200
department|str200
roles|jsonb|NOT NULL
ad_groups|jsonb
status|str20|NOT NULL
last_login_at|dt
system_settings
text
setting_id|UUID PK|NOT NULL
setting_key|str100|NOT NULL [UNIQUE]
setting_value|jsonb|NOT NULL
updated_by|UUID
updated_at|dt|NOT NULL
报表层（2表）
report_definitions
text
report_def_id|UUID PK|NOT NULL
report_name|str200|NOT NULL
report_category|str30|NOT NULL
description|str500
data_sources_json|jsonb|NOT NULL
selected_fields_json|jsonb|NOT NULL
filter_conditions_json|jsonb
sort_by_json|jsonb
max_rows|int
output_format|str20|NOT NULL
output_template_id|UUID FK
created_by|UUID
created_at|dt|NOT NULL
status|str20|NOT NULL
version|str50|NOT NULL [配置类版本保留]
shared_with|str30|NOT NULL
project_scope|str30|NOT NULL
report_execution_logs
text
log_id|UUID PK|NOT NULL
report_def_id|UUID FK|NOT NULL
report_def_version|str50|NOT NULL
executed_by|UUID|NOT NULL
executed_at|dt|NOT NULL
filter_snapshot_json|jsonb
row_count|int|NOT NULL
export_format|str20|NOT NULL
AI预留（2表）
document_chunks
text
chunk_id|UUID PK|NOT NULL
document_id|str64|NOT NULL
content|text|NOT NULL
vector_id|str64
source|str200
created_at|dt|NOT NULL
[embedding列：P10加，P0-P1无]
ai_audit_log
text
log_id|UUID PK|NOT NULL
user_id|UUID|NOT NULL
timestamp|dt|NOT NULL
request_summary|str500|NOT NULL
response_summary|str500
model_version|str50
许可（1表）
license_configs
text
license_id|UUID PK|NOT NULL
license_type|str10|NOT NULL
max_projects|int|NOT NULL
module_limits_json|jsonb|NOT NULL
watermark_enabled|bool|NOT NULL
watermark_text|str200|NOT NULL
config_readonly|bool|NOT NULL
equip_lib_settle_disabled|bool|NOT NULL
workspace_types_allowed|jsonb|NOT NULL
ai_enabled|bool|NOT NULL
trial_start_date|date
trial_end_date|date
created_at|dt|NOT NULL
updated_at|dt|NOT NULL
汇总
域	表数	字段数（约）
项目与物流	3	~100
配置层	11	~120
计算模块	16	~400（含Mixin）
交付物层	6	~90
变更管理	2	~25
集成层	4	~110
流程横切	6	~70
报表层	2	~30
AI预留	2	~15
许可	1	~15
合计	53	~975

