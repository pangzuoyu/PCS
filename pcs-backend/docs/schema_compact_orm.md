# PCS 53表紧凑对照表（ORM版）
> 生成时间：2026-09-02 | 来源：app/models/*.py
> 表数量：53

## 项目与物流(3)
### projects
  project_id|CHARPK!, project_no|str!, project_name|str!, project_name_cn|str, owner_company|str!, contractor_company|str, engineer_name|str, dd_contractor_name|str, feed_contractor_name|str, location|str!, site_address|str, project_type|str!, design_phase|str!, total_capacity|float, total_capacity_unit|str, plant_count|int, single_plant_capacity|float, single_plant_capacity_unit|str, reference_plant|str, unit_system|str!, bedd_json|jsonb, workspace_id|CHARFK!, status|str!, created_by|CHAR, created_at|dt!, updated_at|dt  [UNIQUE: project_no]
### streams
  stream_id|CHARPK!, project_id|CHARFK!, workspace_id|CHARFK!, stream_name|str!, description|str, phase|str, temp|float, press|float, mass_flow|float, molar_flow|float, volumetric_flow|float, std_gas_flow|float, composition_json|jsonb, vapor_composition_json|jsonb, liquid_composition_json|jsonb, density|float, viscosity_dynamic|float, viscosity_kinematic|float, thermal_conductivity|float, specific_heat|float, molecular_weight|float, compressibility_factor|float, vapor_fraction|float, enthalpy|float, entropy|float, bulk_density_min|float, bulk_density_max|float, true_density|float, particle_size_avg|float, particle_size_range|str, particle_shape|str, repose_angle|float, vessel_cone_angle|float, distillation_json|jsonb, sara_json|jsonb, elemental_json|jsonb, metals_json|jsonb, feedstock_specs_json|jsonb, product_specs_json|jsonb, data_mode|str!, property_estimation_json|jsonb, pseudo_components_json|jsonb, lab_report_ref|str, upstream_stream_id|CHARFK, upstream_equipment_type|str, upstream_equipment_id|CHAR, change_type|str, source_type|str!, source_file|str, sign_status|str!, approval_step|int, approval_depth|int!, checked_by|CHAR, checked_at|dt, record_hash|str!, last_change_reason|str, last_change_note|str, last_changed_by|CHAR, last_changed_at|dt, created_by|CHAR, created_at|dt!, updated_at|dt  [UNIQUE: project_id+stream_name]
### stream_state_points
  state_point_id|CHARPK!, stream_id|CHARFK!, state_label|str!, case_type|str!, temp|float!, press|float!, phase|str!, vapor_fraction|float, mass_flow|float!, composition_json|jsonb!, vapor_composition_json|jsonb, liquid_composition_json|jsonb, density|float, viscosity_dynamic|float, enthalpy|float, entropy|float, record_hash|str!, estimated_flags_json|jsonb, profile_json|jsonb, source_type|str!, created_at|dt!

## 配置层(11)
### config_assets
  asset_id|CHARPK!, category|str!, name|str!, description|str, current_version|str!, status|str!, content_json|jsonb, created_by|CHAR, created_at|dt!, updated_at|dt
### config_versions
  version_id|CHARPK!, asset_id|CHARFK!, version_code|str!, parent_version_id|CHARFK, change_note|text, content_json|jsonb, status|str!, created_by|CHAR, created_at|dt!, updated_at|dt
### config_approvals
  approval_id|CHARPK!, version_id|CHARFK!, approver_role|str!, approver_id|CHAR, decision|str!, comment|text, created_by|CHAR, created_at|dt!, updated_at|dt
### formula_definitions
  formula_id|CHARPK!, asset_id|CHARFK, name|str!, module|str!, category|str!, expression|text!, parameters_json|jsonb!, unit_tests_json|jsonb, std_source|str, version|str!, status|str!, created_by|CHAR, created_at|dt!, updated_at|dt
### coefficient_tables
  table_id|CHARPK!, asset_id|CHARFK, name|str!, applicable_range|str!, data_json|jsonb!, std_source|str, version|str!, status|str!, created_by|CHAR, created_at|dt!, updated_at|dt
### template_files
  template_id|CHARPK!, asset_id|CHARFK, name|str!, file_type|str!, file_path|str!, placeholders_json|jsonb!, version|str!, status|str!, created_by|CHAR, created_at|dt!, updated_at|dt
### project_templates
  template_id|CHARPK!, asset_id|CHARFK, name|str!, industry|str, checklist_json|jsonb, default_config_json|jsonb!, version|str!, status|str!, created_by|CHAR, created_at|dt!, updated_at|dt
### pipe_classes
  class_id|strPK!, class_name|str!, material_standard|str!, corrosion_allowance|float!, design_pressure|float!, design_temperature|float!, fluid_service|str, allowable_stress_json|jsonb!, dn_series_json|jsonb!, sch_series_json|jsonb!, flange_class|str!, fitting_type|str, branch_table_json|jsonb, source|str!, version|str!, status|str!, created_by|CHAR, created_at|dt!, updated_at|dt
### project_pipe_classes
  project_id|CHARPKFK!, class_id|strPKFK!, enabled|bool!, custom_override_json|jsonb, created_by|CHAR, created_at|dt!, updated_at|dt
### numbering_templates
  template_id|CHARPK!, template_name|str!, description|str!, segments_json|jsonb!, separator|str!, revision_separate|bool!, deliverable_mappings_json|jsonb, status|str!, created_by|CHAR, created_at|dt!, updated_at|dt
### doc_no_sequences
  sequence_id|CHARPK!, project_id|CHARFK!, template_id|CHARFK!, scope_key|str!, current_value|int!, created_by|CHAR, created_at|dt!, updated_at|dt  [UNIQUE: project_id+template_id+scope_key]

## 计算模块(16)
### piping_results
  pipe_id|CHARPK!, seq_no|int!, line_no|str!, line_size|str!, material_class|strFK!, fluid_code|str!, fluid_name|str!, fluid_phase|str!, fluid_category|str!, toxic_class|str, pipe_grade|str, insulation_code|str, insulation_thickness|float, paint_code|str, tracing_type|str, holding_temp|float, source_pid|str!, line_from|str!, line_to|str!, norm_oper_press|float!, max_oper_press|float!, norm_oper_temp|float!, max_oper_temp|float!, alt_norm_oper_press|float, alt_max_oper_press|float, alt_norm_oper_temp|float, alt_max_oper_temp|float, design_press|float!, design_vacuum|float, design_temp|float!, design_min_temp|float, piping_category|str!, pressure_test_medium|str!, pressure_test_press|float!, ndt_method|str, ndt_ratio|float, ndt_tech_level|str, leak_test_medium|str, leak_test_press|float, check_class|str!, cleaning_method|jsonb, stress_analysis_level|str, remark|str, tag_number|str, sign_status|str!, record_hash|str!, approval_step|int, approval_depth|int!, approval_role|str, locked_by_deliverable|bool!, change_pending_since|dt, change_resolved_by|str, change_resolved_at|dt, change_abandoned_at|dt, change_abandoned_reason|str, obsoleted_reason|str, obsoleted_by|CHAR, obsoleted_at|dt, obsoleted_via_deliverable_id|CHAR, reversal_requested_at|dt, reversal_requested_by|CHAR, reversal_reason|str, reversal_approved_by|CHAR, reversal_approved_at|dt, project_id|CHARFK!, workspace_id|CHARFK!, created_by|CHAR, created_at|dt!, updated_at|dt
### pump_results
  pump_id|CHARPK!, basic_info_json|jsonb!, fluid_properties_json|jsonb!, flow_rates_json|jsonb!, suction_calculation_json|jsonb!, discharge_calculation_json|jsonb!, differential_pressure_json|jsonb!, design_pressure_json|jsonb!, power_consumption_json|jsonb!, control_valve_json|jsonb, equivalent_length_json|jsonb, pressure_drop_details_json|jsonb, line_references_json|jsonb, actual_head|float, actual_efficiency|float, actual_motor_power|float, actual_npshr|float, vendor_model|str, actual_data_confirmed|bool!, tag_number|str!, sign_status|str!, record_hash|str!, approval_step|int, approval_depth|int!, approval_role|str, locked_by_deliverable|bool!, change_pending_since|dt, change_resolved_by|str, change_resolved_at|dt, change_abandoned_at|dt, change_abandoned_reason|str, obsoleted_reason|str, obsoleted_by|CHAR, obsoleted_at|dt, obsoleted_via_deliverable_id|CHAR, reversal_requested_at|dt, reversal_requested_by|CHAR, reversal_reason|str, reversal_approved_by|CHAR, reversal_approved_at|dt, project_id|CHARFK!, workspace_id|CHARFK!, created_by|CHAR, created_at|dt!, updated_at|dt
### psv_results
  psv_id|CHARPK!, set_pressure|float!, relief_capacity|float!, orifice_area|float!, blowdown|float!, orifice_designation|str!, inlet_size|str!, outlet_size|str!, relief_scenario|jsonb!, tag_number|str!, sign_status|str!, record_hash|str!, approval_step|int, approval_depth|int!, approval_role|str, locked_by_deliverable|bool!, change_pending_since|dt, change_resolved_by|str, change_resolved_at|dt, change_abandoned_at|dt, change_abandoned_reason|str, obsoleted_reason|str, obsoleted_by|CHAR, obsoleted_at|dt, obsoleted_via_deliverable_id|CHAR, reversal_requested_at|dt, reversal_requested_by|CHAR, reversal_reason|str, reversal_approved_by|CHAR, reversal_approved_at|dt, project_id|CHARFK!, workspace_id|CHARFK!, created_by|CHAR, created_at|dt!, updated_at|dt
### vessel_results
  vessel_calc_id|CHARPK!, input_json|jsonb!, output_json|jsonb!, tag_number|str!, sign_status|str!, record_hash|str!, approval_step|int, approval_depth|int!, approval_role|str, locked_by_deliverable|bool!, change_pending_since|dt, change_resolved_by|str, change_resolved_at|dt, change_abandoned_at|dt, change_abandoned_reason|str, obsoleted_reason|str, obsoleted_by|CHAR, obsoleted_at|dt, obsoleted_via_deliverable_id|CHAR, reversal_requested_at|dt, reversal_requested_by|CHAR, reversal_reason|str, reversal_approved_by|CHAR, reversal_approved_at|dt, project_id|CHARFK!, workspace_id|CHARFK!, created_by|CHAR, created_at|dt!, updated_at|dt
### heat_results
  heat_calc_id|CHARPK!, exchanger_category|str!, air_side_json|jsonb, design_conditions_json|jsonb!, enthalpy_table_json|jsonb, input_json|jsonb!, output_json|jsonb!, tag_number|str!, sign_status|str!, record_hash|str!, approval_step|int, approval_depth|int!, approval_role|str, locked_by_deliverable|bool!, change_pending_since|dt, change_resolved_by|str, change_resolved_at|dt, change_abandoned_at|dt, change_abandoned_reason|str, obsoleted_reason|str, obsoleted_by|CHAR, obsoleted_at|dt, obsoleted_via_deliverable_id|CHAR, reversal_requested_at|dt, reversal_requested_by|CHAR, reversal_reason|str, reversal_approved_by|CHAR, reversal_approved_at|dt, project_id|CHARFK!, workspace_id|CHARFK!, created_by|CHAR, created_at|dt!, updated_at|dt
### cv_results
  cv_calc_id|CHARPK!, cv_value|float!, flow_rate|float!, pressure_drop|float!, choked_flow|bool!, input_json|jsonb!, output_json|jsonb!, tag_number|str!, sign_status|str!, record_hash|str!, approval_step|int, approval_depth|int!, approval_role|str, locked_by_deliverable|bool!, change_pending_since|dt, change_resolved_by|str, change_resolved_at|dt, change_abandoned_at|dt, change_abandoned_reason|str, obsoleted_reason|str, obsoleted_by|CHAR, obsoleted_at|dt, obsoleted_via_deliverable_id|CHAR, reversal_requested_at|dt, reversal_requested_by|CHAR, reversal_reason|str, reversal_approved_by|CHAR, reversal_approved_at|dt, project_id|CHARFK!, workspace_id|CHARFK!, created_by|CHAR, created_at|dt!, updated_at|dt
### flash_results
  flash_id|CHARPK!, stream_id|CHARFK!, calc_type|str!, method|str!, input_json|jsonb!, output_json|jsonb!, tag_number|str!, sign_status|str!, record_hash|str!, approval_step|int, approval_depth|int!, approval_role|str, locked_by_deliverable|bool!, change_pending_since|dt, change_resolved_by|str, change_resolved_at|dt, change_abandoned_at|dt, change_abandoned_reason|str, obsoleted_reason|str, obsoleted_by|CHAR, obsoleted_at|dt, obsoleted_via_deliverable_id|CHAR, reversal_requested_at|dt, reversal_requested_by|CHAR, reversal_reason|str, reversal_approved_by|CHAR, reversal_approved_at|dt, project_id|CHARFK!, workspace_id|CHARFK!, created_by|CHAR, created_at|dt!, updated_at|dt
### pipe_network_results
  network_id|CHARPK!, input_json|jsonb!, output_json|jsonb!, tag_number|str!, sign_status|str!, record_hash|str!, approval_step|int, approval_depth|int!, approval_role|str, locked_by_deliverable|bool!, change_pending_since|dt, change_resolved_by|str, change_resolved_at|dt, change_abandoned_at|dt, change_abandoned_reason|str, obsoleted_reason|str, obsoleted_by|CHAR, obsoleted_at|dt, obsoleted_via_deliverable_id|CHAR, reversal_requested_at|dt, reversal_requested_by|CHAR, reversal_reason|str, reversal_approved_by|CHAR, reversal_approved_at|dt, project_id|CHARFK!, workspace_id|CHARFK!, created_by|CHAR, created_at|dt!, updated_at|dt
### restriction_results
  orifice_calc_id|CHARPK!, restriction_type|str!, input_json|jsonb!, output_json|jsonb!, tag_number|str!, sign_status|str!, record_hash|str!, approval_step|int, approval_depth|int!, approval_role|str, locked_by_deliverable|bool!, change_pending_since|dt, change_resolved_by|str, change_resolved_at|dt, change_abandoned_at|dt, change_abandoned_reason|str, obsoleted_reason|str, obsoleted_by|CHAR, obsoleted_at|dt, obsoleted_via_deliverable_id|CHAR, reversal_requested_at|dt, reversal_requested_by|CHAR, reversal_reason|str, reversal_approved_by|CHAR, reversal_approved_at|dt, project_id|CHARFK!, workspace_id|CHARFK!, created_by|CHAR, created_at|dt!, updated_at|dt
### flare_system_results
  flare_id|CHARPK!, input_json|jsonb!, output_json|jsonb!, tag_number|str!, sign_status|str!, record_hash|str!, approval_step|int, approval_depth|int!, approval_role|str, locked_by_deliverable|bool!, change_pending_since|dt, change_resolved_by|str, change_resolved_at|dt, change_abandoned_at|dt, change_abandoned_reason|str, obsoleted_reason|str, obsoleted_by|CHAR, obsoleted_at|dt, obsoleted_via_deliverable_id|CHAR, reversal_requested_at|dt, reversal_requested_by|CHAR, reversal_reason|str, reversal_approved_by|CHAR, reversal_approved_at|dt, project_id|CHARFK!, workspace_id|CHARFK!, created_by|CHAR, created_at|dt!, updated_at|dt
### cooling_tower_results
  ct_calc_id|CHARPK!, input_json|jsonb!, output_json|jsonb!, tag_number|str!, sign_status|str!, record_hash|str!, approval_step|int, approval_depth|int!, approval_role|str, locked_by_deliverable|bool!, change_pending_since|dt, change_resolved_by|str, change_resolved_at|dt, change_abandoned_at|dt, change_abandoned_reason|str, obsoleted_reason|str, obsoleted_by|CHAR, obsoleted_at|dt, obsoleted_via_deliverable_id|CHAR, reversal_requested_at|dt, reversal_requested_by|CHAR, reversal_reason|str, reversal_approved_by|CHAR, reversal_approved_at|dt, project_id|CHARFK!, workspace_id|CHARFK!, created_by|CHAR, created_at|dt!, updated_at|dt
### psychro_results
  psychro_calc_id|CHARPK!, calc_type|str!, input_json|jsonb!, output_json|jsonb!, tag_number|str!, sign_status|str!, record_hash|str!, approval_step|int, approval_depth|int!, approval_role|str, locked_by_deliverable|bool!, change_pending_since|dt, change_resolved_by|str, change_resolved_at|dt, change_abandoned_at|dt, change_abandoned_reason|str, obsoleted_reason|str, obsoleted_by|CHAR, obsoleted_at|dt, obsoleted_via_deliverable_id|CHAR, reversal_requested_at|dt, reversal_requested_by|CHAR, reversal_reason|str, reversal_approved_by|CHAR, reversal_approved_at|dt, project_id|CHARFK!, workspace_id|CHARFK!, created_by|CHAR, created_at|dt!, updated_at|dt
### sep_equip_results
  sep_calc_id|CHARPK!, input_json|jsonb!, output_json|jsonb!, tag_number|str!, sign_status|str!, record_hash|str!, approval_step|int, approval_depth|int!, approval_role|str, locked_by_deliverable|bool!, change_pending_since|dt, change_resolved_by|str, change_resolved_at|dt, change_abandoned_at|dt, change_abandoned_reason|str, obsoleted_reason|str, obsoleted_by|CHAR, obsoleted_at|dt, obsoleted_via_deliverable_id|CHAR, reversal_requested_at|dt, reversal_requested_by|CHAR, reversal_reason|str, reversal_approved_by|CHAR, reversal_approved_at|dt, project_id|CHARFK!, workspace_id|CHARFK!, created_by|CHAR, created_at|dt!, updated_at|dt
### filtration_results
  filter_calc_id|CHARPK!, filter_type|str!, area|float!, cycle_time|float!, pressure_drop|float!, tag_number|str!, sign_status|str!, record_hash|str!, approval_step|int, approval_depth|int!, approval_role|str, locked_by_deliverable|bool!, change_pending_since|dt, change_resolved_by|str, change_resolved_at|dt, change_abandoned_at|dt, change_abandoned_reason|str, obsoleted_reason|str, obsoleted_by|CHAR, obsoleted_at|dt, obsoleted_via_deliverable_id|CHAR, reversal_requested_at|dt, reversal_requested_by|CHAR, reversal_reason|str, reversal_approved_by|CHAR, reversal_approved_at|dt, project_id|CHARFK!, workspace_id|CHARFK!, created_by|CHAR, created_at|dt!, updated_at|dt
### cost_est_results
  cost_est_id|CHARPK!, equipment_id|CHARFK!, estimated_cost|dec!, currency|str!, cost_index_year|int!, created_at|dt  [UNIQUE: equipment_id]
### open_channel_results
  channel_calc_id|CHARPK!, channel_type|str!, cross_section_json|jsonb!, flow_rate|float!, depth|float!, velocity|float!, slope|float!, tag_number|str!, sign_status|str!, record_hash|str!, approval_step|int, approval_depth|int!, approval_role|str, locked_by_deliverable|bool!, change_pending_since|dt, change_resolved_by|str, change_resolved_at|dt, change_abandoned_at|dt, change_abandoned_reason|str, obsoleted_reason|str, obsoleted_by|CHAR, obsoleted_at|dt, obsoleted_via_deliverable_id|CHAR, reversal_requested_at|dt, reversal_requested_by|CHAR, reversal_reason|str, reversal_approved_by|CHAR, reversal_approved_at|dt, project_id|CHARFK!, workspace_id|CHARFK!, created_by|CHAR, created_at|dt!, updated_at|dt

## 交付物层(6)
### deliverables
  deliverable_id|CHARPK!, project_id|CHARFK!, deliverable_type|str!, scope_type|str!, scope_value|str!, parent_deliverable_id|CHARFK, doc_no|str!, doc_no_mode|str!, numbering_template_id|CHARFK, segment_values_json|jsonb, discipline_code|str, doc_identifier_code|str, sequence_no|int, title|str!, current_rev|str!, version_purpose|str!, sign_status|str!, matrix_id|CHARFK!, customer_approval_date|date, customer_approver_name|str, customer_approval_method|str, customer_approval_proxy_by|CHAR, customer_approval_proxy_at|dt, customer_approval_attachment_id|CHAR, customer_approval_is_proxy|bool, created_by|CHAR, created_at|dt!, updated_at|dt  [UNIQUE: project_id+doc_no; project_id+deliverable_type+scope_type+scope_value]
### deliverable_versions
  version_id|CHARPK!, deliverable_id|CHARFK!, rev|str!, version_purpose|str!, description|text!, record_snapshot_json|jsonb!, signature_summary_json|jsonb!, customer_approval_date|date, pdf_file_path|str, affected_status|str, created_at|dt!, created_by|CHAR, updated_at|dt
### deliverable_record_bindings
  binding_id|CHARPK!, deliverable_version_id|CHARFK!, record_type|str!, record_id|CHAR!, record_hash|str!, old_record_hash_before_change|str
### signature_matrices
  matrix_id|CHARPK!, matrix_name|str!, module|str!, doc_type|str!, version_purpose|str!, steps_json|jsonb!, status|str!, created_by|CHAR, created_at|dt!, updated_at|dt
### project_signature_matrix_bindings
  binding_id|CHARPK!, project_id|CHARFK!, module|str!, matrix_id|CHARFK!, created_by|CHAR, created_at|dt!, updated_at|dt
### customer_approval_attachments
  attachment_id|CHARPK!, deliverable_version_id|CHARFK!, file_path|str!, file_name|str!, file_type|str!, file_size|int!, uploaded_by|CHAR!, uploaded_at|dt!, file_hash|str!

## 变更管理(2)
### change_notice_details
  detail_id|CHARPK!, deliverable_id|CHARFK!, change_type|str!, reason|text!, triggered_by|str!, source_record_type|str, created_by|CHAR, created_at|dt!, updated_at|dt  [UNIQUE: deliverable_id]
### record_change_snapshots
  snapshot_id|CHARPK!, record_type|str!, record_id|CHAR!, record_hash|str!, data_snapshot_json|jsonb!, snapshot_reason|str!, snapshot_source|str!, created_at|dt!, created_by|CHAR, snapshot_status|str

## 集成层(4)
### equipment_list
  equipment_id|CHARPK!, equipment_type_project_id|CHARFK, type_code|strFK!, equipment_name|str!, equipment_description|str, source_record_id|CHAR, source_module|str, vendor|str, vendor_model|str, design_parameters_json|jsonb, procurement_status|str, flowsheet_drawing_number|str, deliverable_id|CHAR, installation_location|str, net_weight|float, paint|str, process_engineering_remarks|text, alternate_vendor|str, order_date|date, purchase_order_number|str, cost|dec, cost_currency|str, cost_source|str, cost_year|int, gpe_spec_number|str, gpe_spec_status|str, specification_priority|str, approval_drawing_received_date|date, approval_drawing_return_date|date, certified_drawing_received_date|date, delivery_date|date, actual_received_date|date, forecast_on_site|date, actual_on_site|date, storage_location|str, installation_contract_number|str, installation_notes|str, installation|str, unloading|str, loading_by|str, empty_weight|float, full_weight|float, weigh_cells|bool, in_package|bool, data_sources|str, tag_in_3d|bool, tag_in_esr|bool, equipment_name_cn|str, package_no|str, sub_project|str, unit_no|str, unit_name|str, equipment_sub_type|str, equipment_category|str, is_pressure_vessel|bool, pressure_vessel_category|str, process_engineer|str, detail_engineer|str, pid_drawing_number|str, pid_status|str, dimensions|str, registration_number|str, emts_number|str, mst_number|str, equipment_status|str!, calc_status|str!, actual_data_status|str!, tag_number|str!, sign_status|str!, record_hash|str!, approval_step|int, approval_depth|int!, approval_role|str, locked_by_deliverable|bool!, change_pending_since|dt, change_resolved_by|str, change_resolved_at|dt, change_abandoned_at|dt, change_abandoned_reason|str, obsoleted_reason|str, obsoleted_by|CHAR, obsoleted_at|dt, obsoleted_via_deliverable_id|CHAR, reversal_requested_at|dt, reversal_requested_by|CHAR, reversal_reason|str, reversal_approved_by|CHAR, reversal_approved_at|dt, project_id|CHARFK!, workspace_id|CHARFK!, created_by|CHAR, created_at|dt!, updated_at|dt
### equipment_type_codes
  project_id|CHARPKFK, type_code|strPK!, equipment_description|str!, description_cn|str, category|str!, is_process_equipment|bool!, is_pressure_vessel|bool!, source|str, status|str!  [UNIQUE: project_id+type_code]
### equipment_lib
  equip_id|CHARPK!, type_code|str!, size|str, weight|float, material|str, standard_drawing_no|str, process_description|text, cost|dec, cost_currency|str, cost_year|int, status|str!, created_by|CHAR, created_at|dt!, updated_at|dt
### suppliers
  supplier_id|CHARPK!, supplier_name|str!, supplier_type|str!, contact_json|jsonb, qualification_json|jsonb, rating|str!, approved_by|CHAR, approved_date|date, created_by|CHAR, created_at|dt!, updated_at|dt

## 流程横切(6)
### data_lineage
  lineage_id|CHARPK!, record_type|str!, record_id|CHAR!, parent_lineage_id|CHARFK, source|str!, source_ref_type|str, source_ref_id|CHAR, actor_user_id|CHAR, actor_ai_agent_id|CHAR, change_summary|text, change_diff_json|jsonb, occurred_at|dt!
### project_input_checklist
  checklist_id|CHARPK!, project_id|CHARFK!, item_key|str!, item_label|str!, required|bool!, note|text, module|str, input_category|str, input_value_json|jsonb, source_type|str, status|str!, verified_by|CHAR, verified_at|dt, assumption_reason|text, created_by|CHAR, created_at|dt!, updated_at|dt
### workspaces
  workspace_id|CHARPK!, workspace_type|str!, owner_id|CHAR, project_id|CHARFK, name|str!, created_at|dt!, last_active_at|dt, retention_days|int
### audit_logs
  audit_id|CHARPK!, user_id|CHAR, action|str!, resource_type|str, resource_id|str, ip|INET, user_agent|str, request_id|str, detail_json|jsonb, occurred_at|dt!
### users
  user_id|CHARPK!, username|str!, display_name|str!, email|str, department|str, roles|jsonb!, ad_groups|jsonb!, status|str!, last_login_at|dt  [UNIQUE: username]
### system_settings
  setting_key|strPK!, setting_value_json|jsonb!, description|text, updated_at|dt!

## 报表层(2)
### report_definitions
  report_id|CHARPK!, project_id|CHARFK, report_name|str!, report_type|str!, query_json|jsonb!, template_id|CHARFK, enabled|bool!, created_by|CHAR, created_at|dt!, updated_at|dt
### report_execution_logs
  exec_id|CHARPK!, report_id|CHARFK!, executed_by|CHAR!, started_at|dt!, finished_at|dt, row_count|int, status|str!, error_message|text

## AI预留(2)
### document_chunks
  chunk_id|CHARPK!, source_type|str!, source_id|CHAR!, project_id|CHARFK, chunk_text|text!, embedding_vector|jsonb, token_count|int, created_at|dt!
### ai_audit_log
  ai_log_id|CHARPK!, agent_id|CHAR!, session_id|CHAR, user_id|CHAR, operation|str!, prompt_text|text, response_text|text, prompt_tokens|int, response_tokens|int, model|str, cost_usd|float, decision_ref_type|str, decision_ref_id|CHAR, human_approved|bool, human_approver_id|CHAR, occurred_at|dt!

## 许可(1)
### license_configs
  license_id|CHARPK!, license_key|str!, modules_json|jsonb!, issued_at|dt!, expires_at|dt, status|str!  [UNIQUE: license_key]
