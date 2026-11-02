# PCS 紧凑对照表（ORM 版 · **生成物**）
> 生成时间：2026-11-02 | 来源：app/models/*.py（**生成物，勿手改**）
> 重新生成：`cd pcs-backend && uv run python scripts/gen_compact_orm.py`
> 表数量：**107**（= ORM metadata 的全部表）

⚠️ 本文件是 `SA_Base.metadata` 的**派生**产物 ⇒ 表/列不会过期。
完整真值永远 = `app/models/*.py`；本文件只供「快速查一张表的字段」用。

## 项目与物流(3)
### projects
  project_id|CHARPK!, project_no|str!, project_name|str!, project_name_cn|str, owner_company|str!, contractor_company|str, engineer_name|str, dd_contractor_name|str, feed_contractor_name|str, location|str!, site_address|str, project_type|str!, design_phase|str!, total_capacity|float, total_capacity_unit|str, plant_count|int, single_plant_capacity|float, single_plant_capacity_unit|str, reference_plant|str, unit_system|str!, bedd_json|jsonb, workspace_id|CHARFK!, status|str!, product_category|str!, created_by|CHAR, created_at|dt!, updated_at|dt  [UNIQUE: project_no]
### streams
  stream_id|CHARPK!, project_id|CHARFK!, workspace_id|CHARFK!, stream_name|str!, description|str, phase|str, raw_phase|str, temp|float, press|float, mass_flow|float, molar_flow|float, volumetric_flow|float, std_gas_flow|float, composition_json|jsonb, vapor_composition_json|jsonb, liquid_composition_json|jsonb, molecular_weight|float, vapor_fraction|float, liquid_fraction|float, liquid_density|float, liquid_viscosity_dynamic|float, liquid_viscosity_kinematic|float, liquid_thermal_conductivity|float, liquid_specific_heat|float, liquid_surface_tension|float, liquid_compressibility_factor|float, liquid_std_density|float, liquid_mass_rate|float, liquid_actual_m3hr|float, vapor_mass_rate|float, vapor_actual_m3hr|float, vapor_normal_m3hr|float, vapor_mw|float, vapor_density|float, vapor_z|float, vapor_cp|float, vapor_viscosity|float, vapor_thermal_cond|float, enthalpy|float, entropy|float, bulk_density_min|float, bulk_density_max|float, true_density|float, particle_size_avg|float, particle_size_range|str, particle_shape|str, repose_angle|float, vessel_cone_angle|float, distillation_json|jsonb, sara_json|jsonb, elemental_json|jsonb, metals_json|jsonb, feedstock_specs_json|jsonb, product_specs_json|jsonb, data_mode|str!, property_estimation_json|jsonb, pseudo_components_json|jsonb, lab_report_ref|str, upstream_stream_id|CHARFK, upstream_equipment_type|str, upstream_equipment_id|CHAR, change_type|str, source_type|str!, source_file|str, sign_status|str!, approval_step|int, approval_depth|int!, checked_by|CHAR, checked_at|dt, record_hash|str!, last_change_reason|str, last_change_note|str, last_changed_by|CHAR, last_changed_at|dt, case_type|str, api_gravity|float, specific_gravity|float, rvp|float, tvp|float, watson_k|float, flash_point|float, distillation_curves|jsonb, critical_temp|float, critical_press|float, actual_vol_flow|float, viscosity_temperature_curve|jsonb, import_original_row|int, import_source_version|str, is_unreliable|bool, is_mixed_phase|bool, change_pending_since|dt, change_resolved_at|dt, change_resolved_by|str, simulation_status|str, tear_stream|bool, estimated|bool, stream_properties_json|jsonb, user_provided_properties_json|jsonb, calculated_properties_json|jsonb, effective_properties_json|jsonb, conflict_resolutions_json|jsonb, stale_resolution_path|str, hash_changed|bool, changed_fields|jsonb, created_by|CHAR, created_at|dt!, updated_at|dt  [UNIQUE: project_id+stream_name]
### stream_state_points
  state_point_id|CHARPK!, stream_id|CHARFK!, state_label|str!, case_type|str!, temp|float!, press|float!, phase|str!, vapor_fraction|float, mass_flow|float!, composition_json|jsonb!, vapor_composition_json|jsonb, liquid_composition_json|jsonb, density|float, viscosity_dynamic|float, enthalpy|float, entropy|float, record_hash|str!, estimated_flags_json|jsonb, profile_json|jsonb, source_type|str!, created_at|dt!  [UNIQUE: stream_id+case_type+state_label]

## 配置层(11)
### config_assets
  asset_id|CHARPK!, category|str!, name|str!, description|str, current_version|str!, status|str!, content_json|jsonb, asset_subtype|str, created_by|CHAR, created_at|dt!, updated_at|dt
### config_versions
  version_id|CHARPK!, asset_id|CHARFK!, version_code|str!, parent_version_id|CHARFK, change_note|text, content_json|jsonb, status|str!, created_by|CHAR, created_at|dt!, updated_at|dt
### config_approvals
  approval_id|CHARPK!, version_id|CHARFK, approver_role|str!, decision|str!, comment|text, approver_id|CHAR, project_class_id|CHARFK, created_by|CHAR, created_at|dt!, updated_at|dt
### formula_definitions
  formula_id|CHARPK!, name|str!, module|str!, category|str!, expression|text!, parameters_json|jsonb!, unit_tests_json|jsonb, version|str!, status|str!, asset_id|CHARFK, std_source|str, created_by|CHAR, created_at|dt!, updated_at|dt
### coefficient_tables
  table_id|CHARPK!, name|str!, applicable_range|str!, data_json|jsonb!, version|str!, status|str!, asset_id|CHARFK, std_source|str, created_by|CHAR, created_at|dt!, updated_at|dt
### template_files
  template_id|CHARPK!, name|str!, file_type|str!, file_path|str!, placeholders_json|jsonb!, version|str!, template_version_seq|int!, status|str!, asset_id|CHARFK, created_by|CHAR, created_at|dt!, updated_at|dt
### project_templates
  template_id|CHARPK!, name|str!, industry|str, default_config_json|jsonb!, version|str!, status|str!, asset_id|CHARFK, checklist_json|jsonb, pipe_code_template_id|CHARFK, created_by|CHAR, created_at|dt!, updated_at|dt
### pipe_classes
  class_id|strPK!, asset_id|CHARFK, class_name|str!, material_standard|str!, base_material|str, corrosion_allowance|float!, design_pressure|float!, design_temperature|float!, fluid_service|str, allowable_stress_json|jsonb!, dn_series_json|jsonb!, sch_series_json|jsonb!, flange_class|str!, fitting_type|str, branch_table_json|jsonb, source|str!, version|str!, status|str!, created_by|CHAR, created_at|dt!, updated_at|dt
### project_pipe_classes
  project_class_id|CHARPK!, project_id|CHARFK!, source_class_id|str, class_name|str!, override_json|jsonb!, snapshot_json|jsonb, status|str!, created_by|CHAR, created_at|dt!, updated_at|dt  [UNIQUE: project_id+class_name]
### numbering_templates
  template_id|CHARPK!, template_name|str!, description|str!, segments_json|jsonb!, separator|str!, revision_separate|bool!, deliverable_mappings_json|jsonb, status|str!, created_by|CHAR, created_at|dt!, updated_at|dt  [UNIQUE: template_name]
### doc_no_sequences
  sequence_id|CHARPK!, project_id|CHARFK, template_id|CHARFK!, scope_key|str!, current_value|int!, created_by|CHAR, created_at|dt!, updated_at|dt  [UNIQUE: project_id+template_id+scope_key]

## 计算模块(16)
### piping_results
  pipe_id|CHARPK!, seq_no|int!, line_no|str!, line_size|str!, material_class|strFK!, fluid_code|str!, fluid_name|str!, fluid_phase|str!, fluid_category|str!, toxic_class|str, pipe_grade|str, insulation_code|str, insulation_thickness|float, paint_code|str, tracing_type|str, holding_temp|float, source_pid|str!, line_from|str!, line_to|str!, norm_oper_press|float!, max_oper_press|float!, norm_oper_temp|float!, max_oper_temp|float!, alt_norm_oper_press|float, alt_max_oper_press|float, alt_norm_oper_temp|float, alt_max_oper_temp|float, design_press|float!, design_vacuum|float, design_temp|float!, design_min_temp|float, piping_category|str!, pressure_test_medium|str!, pressure_test_press|float!, ndt_method|str, ndt_ratio|float, ndt_tech_level|str, leak_test_medium|str, leak_test_press|float, check_class|str!, cleaning_method|jsonb, stress_analysis_level|str, remark|str, line_description|str, pipe_type|str, max_flow_factor|float, selected_diameter|float, liquid_velocity_max|float, gas_velocity_max|float, pressure_drop_per_100m|float, selected_pipe_size|str, recommended_pipe_size|str, check_result|str, velocity_range_reference|str, tag_number|str, sign_status|str!, record_hash|str!, approval_step|int, approval_depth|int!, approval_role|str, approval_chain_snapshot|jsonb, locked_by_deliverable|bool!, change_pending_since|dt, change_resolved_by|str, change_resolved_at|dt, change_abandoned_at|dt, change_abandoned_reason|str, obsoleted_reason|str, obsoleted_by|CHAR, obsoleted_at|dt, obsoleted_via_deliverable_id|CHAR, reversal_requested_at|dt, reversal_requested_by|CHAR, reversal_reason|str, reversal_approved_by|CHAR, reversal_approved_at|dt, stale_resolution_path|str, hash_changed|bool, changed_fields|jsonb, project_id|CHARFK!, workspace_id|CHARFK!, created_by|CHAR, created_at|dt!, updated_at|dt
### pump_results
  pump_id|CHARPK!, basic_info_json|jsonb!, fluid_properties_json|jsonb!, flow_rates_json|jsonb!, suction_calculation_json|jsonb!, discharge_calculation_json|jsonb!, differential_pressure_json|jsonb!, design_pressure_json|jsonb!, power_consumption_json|jsonb!, control_valve_json|jsonb, equivalent_length_json|jsonb, pressure_drop_details_json|jsonb, line_references_json|jsonb, actual_head|float, actual_efficiency|float, actual_motor_power|float, actual_npshr|float, vendor_model|str, actual_data_confirmed|bool!, selected_pump_model|str, selected_motor_model|str, selected_motor_power|float, pump_operation|str, design_stage|str!, input_json|jsonb, output_json|jsonb, tag_number|str!, sign_status|str!, record_hash|str!, approval_step|int, approval_depth|int!, approval_role|str, approval_chain_snapshot|jsonb, locked_by_deliverable|bool!, change_pending_since|dt, change_resolved_by|str, change_resolved_at|dt, change_abandoned_at|dt, change_abandoned_reason|str, obsoleted_reason|str, obsoleted_by|CHAR, obsoleted_at|dt, obsoleted_via_deliverable_id|CHAR, reversal_requested_at|dt, reversal_requested_by|CHAR, reversal_reason|str, reversal_approved_by|CHAR, reversal_approved_at|dt, stale_resolution_path|str, hash_changed|bool, changed_fields|jsonb, project_id|CHARFK!, workspace_id|CHARFK!, created_by|CHAR, created_at|dt!, updated_at|dt
### psv_results
  psv_id|CHARPK!, set_pressure|float!, relief_capacity|float!, orifice_area|float!, blowdown|float!, orifice_designation|str!, inlet_size|str!, outlet_size|str!, relief_scenario|jsonb!, design_stage|str!, standard_profile_code|str, standard_refs_json|jsonb, formula_ref_json|jsonb, pending_review|bool!, migrated_default|bool!, override_reason|text, override_approval_json|jsonb, valve_type|str, body_material|str, bellows_material|str, flange_class|str, back_pressure_type|str, back_pressure_pct|float, overpressure_pct|float, kb_factor|float, kb_source|str, valve_brand|str, cdtp_applied|bool!, orifice_overridden|bool!, orifice_manual|str, rupture_disc_position|str, rupture_disc_kc|float, pilot_temperature_c|float, pilot_temp_class|str, fire_protection|bool!, stale_resolution_path|text, hash_changed|bool!, changed_fields|jsonb, tag_number|str!, sign_status|str!, record_hash|str!, approval_step|int, approval_depth|int!, approval_role|str, approval_chain_snapshot|jsonb, locked_by_deliverable|bool!, change_pending_since|dt, change_resolved_by|str, change_resolved_at|dt, change_abandoned_at|dt, change_abandoned_reason|str, obsoleted_reason|str, obsoleted_by|CHAR, obsoleted_at|dt, obsoleted_via_deliverable_id|CHAR, reversal_requested_at|dt, reversal_requested_by|CHAR, reversal_reason|str, reversal_approved_by|CHAR, reversal_approved_at|dt, project_id|CHARFK!, workspace_id|CHARFK!, created_by|CHAR, created_at|dt!, updated_at|dt
### vessel_results
  vessel_id|CHARPK!, input_json|jsonb!, output_json|jsonb!, design_stage|str!, vmax_m_s|float, csa_min_m2|float, csa_actual_m2|float, nozzle_min_id_m|float, control_height_m|float, residence_time_s|float, tag_number|str!, sign_status|str!, record_hash|str!, approval_step|int, approval_depth|int!, approval_role|str, approval_chain_snapshot|jsonb, locked_by_deliverable|bool!, change_pending_since|dt, change_resolved_by|str, change_resolved_at|dt, change_abandoned_at|dt, change_abandoned_reason|str, obsoleted_reason|str, obsoleted_by|CHAR, obsoleted_at|dt, obsoleted_via_deliverable_id|CHAR, reversal_requested_at|dt, reversal_requested_by|CHAR, reversal_reason|str, reversal_approved_by|CHAR, reversal_approved_at|dt, stale_resolution_path|str, hash_changed|bool, changed_fields|jsonb, project_id|CHARFK!, workspace_id|CHARFK!, created_by|CHAR, created_at|dt!, updated_at|dt
### heat_results
  heat_exchanger_id|CHARPK!, exchanger_category|str!, air_side_json|jsonb, design_conditions_json|jsonb!, enthalpy_table_json|jsonb, input_json|jsonb!, output_json|jsonb!, equipment_no|str, equipment_name|str, duty|float, duty_legacy|float, duty_calc|float, effective_area|float, hot_inlet_pressure|float, hot_outlet_pressure|float, cold_inlet_pressure|float, cold_outlet_pressure|float, u_overall|float, exchanger_type|str, orientation|str, units_series|int, units_parallel|int, shells_per_unit|int, total_area_gross|float, total_area_eff|float, lmtd|float, mtd_corrected|float, emtd|float, overdesign_percent|float, u_service|float, u_calculated|float, u_clean|float, heat_exchange_area|float, tube_count|int, tube_od|float, tube_id|float, tube_wall_thickness|float, tube_length|float, tube_pitch|float, tube_layout|str, tube_material|str, tube_passes|int, tube_rows|int, skin_temp_min|float, skin_temp_max|float, extended_area_m2|float, bare_area_m2|float, fan_face_area_ratio|float, heat_transfer_safety_factor|float, shell_id|float, shell_design_pressure|float, shell_design_temp|float, baffle_type|str, baffle_cut_percent|float, baffle_spacing|float, baffle_inlet_spacing|float, seal_strip_count|int, passlane_seal_rod_count|int, impingement_plate|str, thermal_resistance_shell|float, thermal_resistance_tube|float, thermal_resistance_fouling|float, thermal_resistance_metal|float, thermal_resistance_bond|float, shell_params|jsonb, tube_params|jsonb, ache_params|jsonb, tag_number|str!, sign_status|str!, record_hash|str!, approval_step|int, approval_depth|int!, approval_role|str, approval_chain_snapshot|jsonb, locked_by_deliverable|bool!, change_pending_since|dt, change_resolved_by|str, change_resolved_at|dt, change_abandoned_at|dt, change_abandoned_reason|str, obsoleted_reason|str, obsoleted_by|CHAR, obsoleted_at|dt, obsoleted_via_deliverable_id|CHAR, reversal_requested_at|dt, reversal_requested_by|CHAR, reversal_reason|str, reversal_approved_by|CHAR, reversal_approved_at|dt, stale_resolution_path|str, hash_changed|bool, changed_fields|jsonb, project_id|CHARFK!, workspace_id|CHARFK!, created_by|CHAR, created_at|dt!, updated_at|dt
### cv_results
  cv_id|CHARPK!, cv_value|float!, flow_rate|float!, pressure_drop|float!, choked_flow|bool!, input_json|jsonb!, output_json|jsonb!, valve_type|str!, fluid_phase|str!, P1_pa|float!, P2_pa|float!, T1_k|float!, Q_m3_per_h|float, rho|float, SG|float, FL|float, xT|float, gamma|float, M|float, Z|float, Cv_calculated|float!, Cv_selected|float, choked|bool!, cavitation|bool!, flashing|bool!, noise_sil_db|float, standard_profile_code|str!, design_stage|str!, masonelian_model|str, tag_number|str!, sign_status|str!, record_hash|str!, approval_step|int, approval_depth|int!, approval_role|str, approval_chain_snapshot|jsonb, locked_by_deliverable|bool!, change_pending_since|dt, change_resolved_by|str, change_resolved_at|dt, change_abandoned_at|dt, change_abandoned_reason|str, obsoleted_reason|str, obsoleted_by|CHAR, obsoleted_at|dt, obsoleted_via_deliverable_id|CHAR, reversal_requested_at|dt, reversal_requested_by|CHAR, reversal_reason|str, reversal_approved_by|CHAR, reversal_approved_at|dt, stale_resolution_path|str, hash_changed|bool, changed_fields|jsonb, project_id|CHARFK!, workspace_id|CHARFK!, created_by|CHAR, created_at|dt!, updated_at|dt
### flash_results
  flash_id|CHARPK!, stream_id|CHARFK!, calc_type|str!, method|str!, input_json|jsonb!, output_json|jsonb!, tag_number|str!, sign_status|str!, record_hash|str!, approval_step|int, approval_depth|int!, approval_role|str, approval_chain_snapshot|jsonb, locked_by_deliverable|bool!, change_pending_since|dt, change_resolved_by|str, change_resolved_at|dt, change_abandoned_at|dt, change_abandoned_reason|str, obsoleted_reason|str, obsoleted_by|CHAR, obsoleted_at|dt, obsoleted_via_deliverable_id|CHAR, reversal_requested_at|dt, reversal_requested_by|CHAR, reversal_reason|str, reversal_approved_by|CHAR, reversal_approved_at|dt, stale_resolution_path|str, hash_changed|bool, changed_fields|jsonb, project_id|CHARFK!, workspace_id|CHARFK!, created_by|CHAR, created_at|dt!, updated_at|dt
### pipe_network_results
  network_id|CHARPK!, input_json|jsonb!, output_json|jsonb!, tag_number|str!, sign_status|str!, record_hash|str!, approval_step|int, approval_depth|int!, approval_role|str, approval_chain_snapshot|jsonb, locked_by_deliverable|bool!, change_pending_since|dt, change_resolved_by|str, change_resolved_at|dt, change_abandoned_at|dt, change_abandoned_reason|str, obsoleted_reason|str, obsoleted_by|CHAR, obsoleted_at|dt, obsoleted_via_deliverable_id|CHAR, reversal_requested_at|dt, reversal_requested_by|CHAR, reversal_reason|str, reversal_approved_by|CHAR, reversal_approved_at|dt, stale_resolution_path|str, hash_changed|bool, changed_fields|jsonb, project_id|CHARFK!, workspace_id|CHARFK!, created_by|CHAR, created_at|dt!, updated_at|dt
### restriction_results
  orifice_id|CHARPK!, restriction_type|str!, input_json|jsonb!, output_json|jsonb!, device_type|str!, D_pipe_m|float!, d_solved_m|float!, beta_ratio|float!, C_discharge|float!, epsilon|float, Re_D|float, delta_P_pa|float!, delta_omega_pa|float, choked|bool!, flashing|bool!, stages|int, design_stage|str!, tag_number|str!, sign_status|str!, record_hash|str!, approval_step|int, approval_depth|int!, approval_role|str, approval_chain_snapshot|jsonb, locked_by_deliverable|bool!, change_pending_since|dt, change_resolved_by|str, change_resolved_at|dt, change_abandoned_at|dt, change_abandoned_reason|str, obsoleted_reason|str, obsoleted_by|CHAR, obsoleted_at|dt, obsoleted_via_deliverable_id|CHAR, reversal_requested_at|dt, reversal_requested_by|CHAR, reversal_reason|str, reversal_approved_by|CHAR, reversal_approved_at|dt, stale_resolution_path|str, hash_changed|bool, changed_fields|jsonb, project_id|CHARFK!, workspace_id|CHARFK!, created_by|CHAR, created_at|dt!, updated_at|dt
### flare_system_results
  flare_id|CHARPK!, standard_profile_code|str!, calc_type|str!, total_relief_load_kg_h|float, header_diameter_mm|float, header_mach|float, header_pressure_drop_kpa|float, kod_diameter_mm|float, water_seal_height_mm|float, stack_height_m|float, stack_diameter_m|float, radiation_at_grade_kw_m2|float, radiation_limit_kw_m2|float, pass|bool, flare_tip_diameter_mm|float, steam_for_smokeless_kg_h|float, radiation_check_json|jsonb, input_json|jsonb, output_json|jsonb, tag_number|str!, sign_status|str!, record_hash|str!, approval_step|int, approval_depth|int!, approval_role|str, approval_chain_snapshot|jsonb, locked_by_deliverable|bool!, change_pending_since|dt, change_resolved_by|str, change_resolved_at|dt, change_abandoned_at|dt, change_abandoned_reason|str, obsoleted_reason|str, obsoleted_by|CHAR, obsoleted_at|dt, obsoleted_via_deliverable_id|CHAR, reversal_requested_at|dt, reversal_requested_by|CHAR, reversal_reason|str, reversal_approved_by|CHAR, reversal_approved_at|dt, stale_resolution_path|str, hash_changed|bool, changed_fields|jsonb, project_id|CHARFK!, workspace_id|CHARFK!, created_by|CHAR, created_at|dt!, updated_at|dt  [UNIQUE: project_id+tag_number]
### cooling_tower_results
  cooling_tower_id|CHARPK!, standard_profile_code|str!, calc_type|str!, tower_type|str, duty_kw|float, water_flow_m3h|float, makeup_water_m3h|float, fan_power_kw|float, merkel_integral|float, data_sheet_json|jsonb, input_json|jsonb, output_json|jsonb, tag_number|str!, sign_status|str!, record_hash|str!, approval_step|int, approval_depth|int!, approval_role|str, approval_chain_snapshot|jsonb, locked_by_deliverable|bool!, change_pending_since|dt, change_resolved_by|str, change_resolved_at|dt, change_abandoned_at|dt, change_abandoned_reason|str, obsoleted_reason|str, obsoleted_by|CHAR, obsoleted_at|dt, obsoleted_via_deliverable_id|CHAR, reversal_requested_at|dt, reversal_requested_by|CHAR, reversal_reason|str, reversal_approved_by|CHAR, reversal_approved_at|dt, stale_resolution_path|str, hash_changed|bool, changed_fields|jsonb, project_id|CHARFK!, workspace_id|CHARFK!, created_by|CHAR, created_at|dt!, updated_at|dt  [UNIQUE: project_id+tag_number]
### psychro_results
  psychro_id|CHARPK!, standard_profile_code|str!, calc_type|str!, coolprop_version|str, humidity_ratio_kg_kg|float, dew_point_c|float, wet_bulb_c|float, enthalpy_kj_kg|float, specific_volume_m3_kg|float, sensible_heat_kw|float, latent_heat_kw|float, saturation_w_kg_kg|float, saturation_w_mg_sm3|float, saturation_w_lb_per_mmscf|float, saturation_T_c|float, input_json|jsonb, output_json|jsonb, tag_number|str!, sign_status|str!, record_hash|str!, approval_step|int, approval_depth|int!, approval_role|str, approval_chain_snapshot|jsonb, locked_by_deliverable|bool!, change_pending_since|dt, change_resolved_by|str, change_resolved_at|dt, change_abandoned_at|dt, change_abandoned_reason|str, obsoleted_reason|str, obsoleted_by|CHAR, obsoleted_at|dt, obsoleted_via_deliverable_id|CHAR, reversal_requested_at|dt, reversal_requested_by|CHAR, reversal_reason|str, reversal_approved_by|CHAR, reversal_approved_at|dt, stale_resolution_path|str, hash_changed|bool, changed_fields|jsonb, project_id|CHARFK!, workspace_id|CHARFK!, created_by|CHAR, created_at|dt!, updated_at|dt  [UNIQUE: project_id+tag_number]
### sep_equip_results
  sep_equip_id|CHARPK!, input_json|jsonb!, output_json|jsonb!, tag_number|str!, sign_status|str!, record_hash|str!, approval_step|int, approval_depth|int!, approval_role|str, approval_chain_snapshot|jsonb, locked_by_deliverable|bool!, change_pending_since|dt, change_resolved_by|str, change_resolved_at|dt, change_abandoned_at|dt, change_abandoned_reason|str, obsoleted_reason|str, obsoleted_by|CHAR, obsoleted_at|dt, obsoleted_via_deliverable_id|CHAR, reversal_requested_at|dt, reversal_requested_by|CHAR, reversal_reason|str, reversal_approved_by|CHAR, reversal_approved_at|dt, stale_resolution_path|str, hash_changed|bool, changed_fields|jsonb, project_id|CHARFK!, workspace_id|CHARFK!, created_by|CHAR, created_at|dt!, updated_at|dt
### filtration_results
  filter_id|CHARPK!, filter_type|str!, area|float!, cycle_time|float!, pressure_drop|float!, media_type|str, cake_resistance_alpha|float, specific_resistance_r0|float, permeability_k|float, porosity_eps|float, filter_velocity|float, tag_number|str!, sign_status|str!, record_hash|str!, approval_step|int, approval_depth|int!, approval_role|str, approval_chain_snapshot|jsonb, locked_by_deliverable|bool!, change_pending_since|dt, change_resolved_by|str, change_resolved_at|dt, change_abandoned_at|dt, change_abandoned_reason|str, obsoleted_reason|str, obsoleted_by|CHAR, obsoleted_at|dt, obsoleted_via_deliverable_id|CHAR, reversal_requested_at|dt, reversal_requested_by|CHAR, reversal_reason|str, reversal_approved_by|CHAR, reversal_approved_at|dt, stale_resolution_path|str, hash_changed|bool, changed_fields|jsonb, project_id|CHARFK!, workspace_id|CHARFK!, created_by|CHAR, created_at|dt!, updated_at|dt
### cost_est_results
  cost_est_id|CHARPK!, equipment_id|CHARFK!, project_id|CHARFK!, estimated_cost|dec!, currency|str!, cost_index_year|int!, base_cost|dec, base_year|int, cepci_index_base|float, cepci_index_target|float, correlation_source|str, scaling_exponent|float, record_hash|str!, created_at|dt  [UNIQUE: equipment_id]
### open_channel_results
  open_channel_id|CHARPK!, channel_type|str!, cross_section_json|jsonb!, flow_rate|float!, depth|float!, velocity|float!, slope|float!, critical_depth|float, froude_number|float, manning_n|float, hydraulic_radius|float, jump_type|str, conjugate_depth|float, energy_loss|float, tag_number|str!, sign_status|str!, record_hash|str!, approval_step|int, approval_depth|int!, approval_role|str, approval_chain_snapshot|jsonb, locked_by_deliverable|bool!, change_pending_since|dt, change_resolved_by|str, change_resolved_at|dt, change_abandoned_at|dt, change_abandoned_reason|str, obsoleted_reason|str, obsoleted_by|CHAR, obsoleted_at|dt, obsoleted_via_deliverable_id|CHAR, reversal_requested_at|dt, reversal_requested_by|CHAR, reversal_reason|str, reversal_approved_by|CHAR, reversal_approved_at|dt, stale_resolution_path|str, hash_changed|bool, changed_fields|jsonb, project_id|CHARFK!, workspace_id|CHARFK!, created_by|CHAR, created_at|dt!, updated_at|dt

## 交付物层(6)
### deliverables
  deliverable_id|CHARPK!, project_id|CHARFK!, deliverable_type|str!, scope_type|str!, scope_value|str!, doc_no|str!, doc_no_mode|str!, numbering_template_id|CHARFK, segment_values_json|jsonb, discipline_code|str, doc_identifier_code|str, sequence_no|int, title|str!, current_rev|str!, version_purpose|str!, sign_status|str!, matrix_id|CHARFK!, customer_approval_date|date, customer_approver_name|str, customer_approval_method|str, customer_approval_proxy_by|CHAR, customer_approval_proxy_at|dt, customer_approval_attachment_id|CHAR, customer_approval_is_proxy|bool, created_by|CHAR, created_at|dt!, updated_at|dt  [UNIQUE: project_id+doc_no; project_id+deliverable_type+scope_type+scope_value]
### deliverable_versions
  version_id|CHARPK!, deliverable_id|CHARFK!, rev|str!, version_purpose|str!, description|text!, record_snapshot_json|jsonb!, signature_summary_json|jsonb!, customer_approval_date|date, pdf_file_path|str, affected_status|str, created_at|dt!, created_by|CHAR, updated_at|dt
### deliverable_record_bindings
  binding_id|CHARPK!, deliverable_version_id|CHARFK!, record_type|str!, record_id|CHAR!, record_hash|str!, old_record_hash_before_change|str
### signature_matrices
  matrix_id|CHARPK!, matrix_name|str!, module|str!, doc_type|str!, version_purpose|str!, steps_json|jsonb!, status|str!, created_by|CHAR, created_at|dt!, updated_at|dt  [UNIQUE: matrix_name+status]
### project_signature_matrix_bindings
  binding_id|CHARPK!, project_id|CHARFK!, module|str!, matrix_id|CHARFK!, created_by|CHAR, created_at|dt!, updated_at|dt  [UNIQUE: project_id+module]
### customer_approval_attachments
  attachment_id|CHARPK!, deliverable_version_id|CHARFK!, file_path|str!, file_name|str!, file_type|str!, file_size|int!, uploaded_by|CHAR!, uploaded_at|dt!, file_hash|str!

## 变更管理(2)
### change_notice_details
  detail_id|CHARPK!, deliverable_id|CHARFK!, change_type|str!, reason|text!, triggered_by|str!, source_record_type|str, created_by|CHAR, created_at|dt!, updated_at|dt  [UNIQUE: deliverable_id]
### record_change_snapshots
  snapshot_id|CHARPK!, record_type|str!, record_id|CHAR!, record_hash|str!, data_snapshot_json|jsonb!, snapshot_reason|str!, snapshot_source|str!, created_at|dt!, created_by|CHAR, snapshot_status|str

## 集成层(3)
### equipment_list
  equipment_id|CHARPK!, equipment_type_project_id|CHARFK, type_code|strFK!, equipment_name|str!, equipment_description|str, source_record_id|CHAR, source_module|str, source_service|str, vendor|str, vendor_model|str, design_parameters_json|jsonb, procurement_status|str, flowsheet_drawing_number|str, deliverable_id|CHAR, installation_location|str, net_weight|float, paint|str, process_engineering_remarks|text, alternate_vendor|str, order_date|date, purchase_order_number|str, cost|dec, cost_currency|str, cost_source|str, cost_year|int, gpe_spec_number|str, gpe_spec_status|str, specification_priority|str, approval_drawing_received_date|date, approval_drawing_return_date|date, certified_drawing_received_date|date, delivery_date|date, actual_received_date|date, forecast_on_site|date, actual_on_site|date, storage_location|str, installation_contract_number|str, installation_notes|str, installation|str, unloading|str, loading_by|str, empty_weight|float, full_weight|float, weigh_cells|bool, in_package|bool, data_sources|str, tag_in_3d|bool, tag_in_esr|bool, equipment_name_cn|str, package_no|str, sub_project|str, unit_no|str, unit_name|str, equipment_sub_type|str, equipment_category|str, is_pressure_vessel|bool, pressure_vessel_category|str, process_engineer|str, detail_engineer|str, pid_drawing_number|str, pid_status|str, dimensions|str, registration_number|str, emts_number|str, mst_number|str, equipment_status|str!, calc_status|str!, actual_data_status|str!, actual_data_json|jsonb, tag_number|str!, sign_status|str!, record_hash|str!, approval_step|int, approval_depth|int!, approval_role|str, approval_chain_snapshot|jsonb, locked_by_deliverable|bool!, change_pending_since|dt, change_resolved_by|str, change_resolved_at|dt, change_abandoned_at|dt, change_abandoned_reason|str, obsoleted_reason|str, obsoleted_by|CHAR, obsoleted_at|dt, obsoleted_via_deliverable_id|CHAR, reversal_requested_at|dt, reversal_requested_by|CHAR, reversal_reason|str, reversal_approved_by|CHAR, reversal_approved_at|dt, stale_resolution_path|str, hash_changed|bool, changed_fields|jsonb, project_id|CHARFK!, workspace_id|CHARFK!, created_by|CHAR, created_at|dt!, updated_at|dt
### equipment_type_codes
  project_id|CHARPKFK, type_code|strPK!, equipment_description|str!, description_cn|str, category|str!, is_process_equipment|bool!, is_pressure_vessel|bool!, source|str, status|str!  [UNIQUE: project_id+type_code]
### suppliers
  supplier_id|CHARPK!, supplier_name|str!, supplier_type|str!, contact_json|jsonb, qualification_json|jsonb, rating|str!, approved_by|CHAR, approved_date|date, created_by|CHAR, created_at|dt!, updated_at|dt

## 流程横切(6)
### data_lineage
  lineage_id|CHARPK!, record_type|str!, record_id|CHAR!, parent_lineage_id|CHARFK, source|str!, source_ref_type|str, source_ref_id|CHAR, actor_user_id|CHAR, actor_ai_agent_id|CHAR, change_summary|text, change_diff_json|jsonb, record_hash_at_track|str, source_record_hash|str, formula_version_at_track|str, config_version|str, occurred_at|dt!
### project_input_checklist
  checklist_id|CHARPK!, project_id|CHARFK!, item_key|str!, item_label|str!, required|bool!, note|text, module|str, input_category|str, input_value_json|jsonb, source_type|str, status|str!, verified_by|CHAR, verified_at|dt, assumption_reason|text, created_by|CHAR, created_at|dt!, updated_at|dt
### workspaces
  workspace_id|CHARPK!, workspace_type|str!, owner_id|CHAR, project_id|CHARFK, name|str!, status|str!, created_at|dt!, last_active_at|dt, retention_days|int
### audit_logs
  audit_id|CHARPK!, user_id|CHAR, action|str!, resource_type|str, resource_id|str, ip|INET, user_agent|str, request_id|str, detail_json|jsonb, occurred_at|dt!
### users
  user_id|CHARPK!, username|str!, display_name|str!, email|str, department|str, roles|jsonb!, ad_groups|jsonb!, status|str!, last_login_at|dt, token_version|int!  [UNIQUE: username]
### system_settings
  setting_key|strPK!, setting_value_json|jsonb!, description|text, updated_at|dt!

## 报表层(2)
### report_definitions
  def_id|CHARPK!, project_id|CHARFK, name|str!, category|str!, description|text!, definition_json|jsonb!, output_format|str!, max_rows|int!, version|str!, status|str!, shared_with|str!, created_by|CHAR, created_at|dt!, updated_at|dt  [UNIQUE: project_id+name]
### report_execution_logs
  log_id|CHARPK!, def_id|CHARFK!, def_version|str!, condition_snapshot|jsonb!, row_count|int!, output_format|str!, executed_by|CHAR, is_temporary_adjust|bool!, task_id|str, report_file_id|CHAR, status|str!, created_by|CHAR, created_at|dt!, updated_at|dt

## AI预留(2)
### document_chunks
  chunk_id|CHARPK!, source_type|str!, source_id|CHAR!, project_id|CHARFK, chunk_text|text!, embedding_vector|jsonb, token_count|int, created_at|dt!
### ai_audit_log
  ai_log_id|CHARPK!, agent_id|CHAR!, session_id|CHAR, user_id|CHAR, operation|str!, prompt_text|text, response_text|text, prompt_tokens|int, response_tokens|int, model|str, cost_usd|float, decision_ref_type|str, decision_ref_id|CHAR, human_approved|bool, human_approver_id|CHAR, occurred_at|dt!

## 许可(1)
### license_configs
  license_id|CHARPK!, license_key|str!, modules_json|jsonb!, issued_at|dt!, expires_at|dt, status|str!  [UNIQUE: license_key]

## 其它(55)
### cepci_index_series
  id|intPK!, year|int!, cepci_value|float!, source|str!, confirmed_by|str, confirmed_at|dt, created_at|dt!, updated_at|dt
### column_sizing
  column_id|CHARPK!, tag_number|str!, column_name|str, hysys_flooding_percent|float, hysys_calc_diameter_mm|float, selected_diameter_mm|float, reference_diameter_mm|float, tray_spacing_mm|float, tray_count|int, theoretical_tray_count|int, overall_efficiency|float, calc_date|dt, design_stage|str!, sign_status|str!, record_hash|str!, approval_step|int, approval_depth|int!, approval_role|str, approval_chain_snapshot|jsonb, locked_by_deliverable|bool!, change_pending_since|dt, change_resolved_by|str, change_resolved_at|dt, change_abandoned_at|dt, change_abandoned_reason|str, obsoleted_reason|str, obsoleted_by|CHAR, obsoleted_at|dt, obsoleted_via_deliverable_id|CHAR, reversal_requested_at|dt, reversal_requested_by|CHAR, reversal_reason|str, reversal_approved_by|CHAR, reversal_approved_at|dt, stale_resolution_path|str, hash_changed|bool, changed_fields|jsonb, project_id|CHARFK!, workspace_id|CHARFK!, created_by|CHAR, created_at|dt!, updated_at|dt  [UNIQUE: project_id+tag_number]
### compound_api521_thresholds
  id|intPK!, threshold_type|str!, flux_kw_m2|float!, source|str!, confirmed_by|str, confirmed_at|dt, created_at|dt!, updated_at|dt  [UNIQUE: threshold_type]
### compound_delta_h_vap_natural_gas
  id|intPK!, convention|str!, dh_vap_kj_kg|float!, notes|str, source|str!, confirmed_by|str!, confirmed_at|dt, created_at|dt!, updated_at|dt  [UNIQUE: convention]
### compound_hammerschmidt_K
  id|intPK!, inhibitor_type|str!, K|float!, source|str!, confirmed_by|str, confirmed_at|dt, created_at|dt!, updated_at|dt  [UNIQUE: inhibitor_type]
### compound_heating_values
  id|intPK!, cas|str!, name|str!, hhv_mj_kg|float!, lhv_mj_kg|float!, mw_g_mol|float!, source|str!, confirmed_by|str, confirmed_at|dt, created_at|dt!, updated_at|dt  [UNIQUE: cas]
### compound_iso9613_atmospheric_absorption
  id|intPK!, temperature_c|float!, humidity_pct|float!, alpha_db_km|float!, source|str!, confirmed_by|str, confirmed_at|dt, created_at|dt!, updated_at|dt  [UNIQUE: temperature_c+humidity_pct]
### compound_pasquill_sigma
  id|intPK!, stability_class|str!, a_y|float!, b_y|float!, a_z|float!, b_z|float!, source|str!, confirmed_by|str, confirmed_at|dt, created_at|dt!, updated_at|dt  [UNIQUE: stability_class]
### config_energy_conversion_factors
  id|intPK!, energy_type|str!, value_type|str, sub_type|str, pressure_level|str, water_type|str, toe_factor|float!, standard_coal_factor|float!, source|str!, confirmed_by|str, confirmed_at|dt, created_at|dt!, updated_at|dt  [UNIQUE: energy_type+value_type+sub_type+pressure_level+water_type]
### cooling_tower_curves
  curve_id|CHARPK!, tower_model|str!, curve_source|str!, c_coefficient|float!, m_exponent|float!, l_g_ratio_min|float, l_g_ratio_max|float, notes|str, source|str!, confirmed_by|str, confirmed_at|dt, created_at|dt!, updated_at|dt  [UNIQUE: tower_model+source]
### cost_correlations
  id|intPK!, equipment_type|str!, version|str!, coefficient_a|dec!, coefficient_b|dec!, scaling_exponent_n|dec!, scale_unit|str!, valid_range_low|dec!, valid_range_high|dec!, base_currency|str!, base_year|int!, notes|text, created_by|CHARFK, created_at|dt!, updated_at|dt  [UNIQUE: equipment_type+version]
### drain_orifice_Cd_Y_cr
  id|intPK!, fluid|str!, beta_range_min|float!, beta_range_max|float!, cd|float!, y_cr|float!, notes|str, source|str!, confirmed_by|str!, confirmed_at|dt, created_at|dt!, updated_at|dt  [UNIQUE: fluid]
### equipment_deletion_audit
  audit_id|CHARPK!, equipment_id|CHAR!, project_id|CHAR!, workspace_id|CHAR!, equipment_tag|str!, deleted_by|CHAR!, orphan_records|jsonb!, occurred_at|dt!, reason|str
### event_idempotency
  event_id|CHARPK!, event_type|str!, payload_hash|str!, before_json|jsonb, processed_at|dt!
### filtration_media_library
  media_id|CHARPK!, medium_type|str!, grade|str!, nominal_rating_um|float!, cake_resistance_alpha|float, specific_resistance_r0|float, permeability_k|float, porosity_eps|float, max_temp_c|float, source|str!, confirmed_by|str, confirmed_at|dt, created_at|dt!, updated_at|dt  [UNIQUE: medium_type+grade]
### flare_radiation_limits
  limit_id|CHARPK!, limit_type|str!, q_kw_m2_limit|float!, distance_m|float, effective_height_m|float, notes|str, source|str!, confirmed_by|str, confirmed_at|dt, created_at|dt!, updated_at|dt  [UNIQUE: limit_type]
### glycol_dehydration_full_system
  id|intPK!, parameter|str!, min_value|float!, max_value|float!, unit|str!, notes|str, source|str!, confirmed_by|str!, confirmed_at|dt, created_at|dt!, updated_at|dt  [UNIQUE: parameter]
### htri_template_schemas
  schema_id|CHARPK!, device_type|str!, column_count|int!, columns_json|jsonb!, tema_type|str, version|str!, source_file_ref|str, created_by|CHAR, created_at|dt!, updated_at|dt
### mixer_results
  mixer_id|CHARPK!, mixer_tag|str!, mixer_name|str, component_1_name|str, component_1_flow|float, component_2_name|str, component_2_flow|float, pressure_drop_kpa|float, check_result|str, tag_number|str, sign_status|str!, record_hash|str!, approval_step|int, approval_depth|int!, approval_role|str, approval_chain_snapshot|jsonb, locked_by_deliverable|bool!, change_pending_since|dt, change_resolved_by|str, change_resolved_at|dt, change_abandoned_at|dt, change_abandoned_reason|str, obsoleted_reason|str, obsoleted_by|CHAR, obsoleted_at|dt, obsoleted_via_deliverable_id|CHAR, reversal_requested_at|dt, reversal_requested_by|CHAR, reversal_reason|str, reversal_approved_by|CHAR, reversal_approved_at|dt, stale_resolution_path|str, hash_changed|bool, changed_fields|jsonb, project_id|CHARFK!, workspace_id|CHARFK!, created_by|CHAR, created_at|dt!, updated_at|dt  [UNIQUE: project_id+mixer_tag]
### notifications
  notification_id|CHARPK!, recipient_id|CHARFK!, kind|str!, title|str!, body|text!, detail_json|jsonb, read_at|dt, created_by|CHAR, created_at|dt!, updated_at|dt
### pcs_toe_conversion_factors
  id|intPK!, fuel_type|str!, toe_conversion_factor|dec!, standard_coal_factor|dec!, effective_year|int!, effective_from|date!, effective_to|date, source|str, version|str!, created_by|CHAR, created_at|dt!, updated_at|dt  [UNIQUE: fuel_type+effective_year]
### pipe_class_import_previews
  import_id|CHARPK!, actor_id|CHAR, file_bytes|bytes!, parsed_json|jsonb!, error_count|int!, warning_count|int!, expires_at|dt!, consumed_at|dt, created_by|CHAR, created_at|dt!, updated_at|dt
### pipe_code_templates
  template_id|CHARPK!, asset_id|CHARFK, template_name|str!, description|str, format_definition_json|jsonb!, status|str!, version|str!, created_by|CHAR, created_at|dt!, updated_at|dt  [UNIQUE: template_name]
### pipe_e_modulus
  id|intPK!, grade|str!, e_psi|float!, spec_source|str!, source|str!, confirmed_by|str!, confirmed_at|dt, created_at|dt!, updated_at|dt!  [UNIQUE: grade]
### project_calculation_standard_profiles
  id|CHARPK!, project_id|CHARFK!, discipline|str!, profile_code|str!, standard_refs_json|jsonb!, approval_json|jsonb, is_default|bool!, migrated_default|bool!, effective_from|dt!, effective_to|dt, approved_by|CHARFK, created_at|dt!, updated_at|dt!
### project_pipe_code_configs
  config_id|CHARPK!, project_id|CHARFK!, source_template_id|CHARFK, config_name|str!, format_definition_json|jsonb!, snapshot_json|jsonb, status|str!, created_by|CHAR, created_at|dt!, updated_at|dt  [UNIQUE: project_id+config_name]
### project_pipe_code_sequences
  config_id|CHARPKFK!, scope_key|strPK!, next_value|int!
### project_stream_symbols
  project_symbol_id|CHARPK!, project_id|CHARFK!, source_symbol_id|CHARFK, symbol|str!, name|str!, category|str, is_active|bool!, snapshot_json|jsonb, override_json|jsonb!, status|str!, created_by|CHAR, created_at|dt!, updated_at|dt  [UNIQUE: project_id+symbol]
### project_template_pipe_classes
  template_id|CHARPKFK!, class_id|strPKFK!, created_by|CHAR, created_at|dt!, updated_at|dt
### record_comments
  comment_id|CHARPK!, project_id|CHARFK!, record_type|str!, record_id|CHAR!, body|text!, author_id|CHAR!, created_at|dt!, created_by|CHAR, updated_at|dt
### relief_results
  relief_id|CHARPK!, source_equipment_id|CHAR!, relief_scenario|str!, reactor_volume|float, reactor_diameter|float, reactor_height|float, gas_tight_pressure|float, safety_factor|float!, relief_rate_tier_1|float!, relief_rate_tier_2|float!, relief_rate_tier_3|float!, required_relief_area|float, selected_psv_id|CHARFK, standard_profile_code|str, standard_refs_json|jsonb, formula_ref_json|jsonb, pending_review|bool!, migrated_default|bool!, override_reason|text, override_approval_json|jsonb, tag_number|str, sign_status|str!, record_hash|str!, approval_step|int, approval_depth|int!, approval_role|str, approval_chain_snapshot|jsonb, locked_by_deliverable|bool!, change_pending_since|dt, change_resolved_by|str, change_resolved_at|dt, change_abandoned_at|dt, change_abandoned_reason|str, obsoleted_reason|str, obsoleted_by|CHAR, obsoleted_at|dt, obsoleted_via_deliverable_id|CHAR, reversal_requested_at|dt, reversal_requested_by|CHAR, reversal_reason|str, reversal_approved_by|CHAR, reversal_approved_at|dt, stale_resolution_path|str, hash_changed|bool, changed_fields|jsonb, project_id|CHARFK!, workspace_id|CHARFK!, created_by|CHAR, created_at|dt!, updated_at|dt
### report_files
  report_file_id|CHARPK!, task_id|str, project_id|CHAR, content_hash|str!, file_path|str!, file_format|str!, size_bytes|int!, doc_no|str, rev|str, style_version|str, data_version|str, status|str!, error_message|text, heartbeat_at|dt!, has_assumption_page|bool!, created_by|CHAR, created_at|dt!, updated_at|dt  [UNIQUE: content_hash]
### report_styles
  style_id|CHARPK!, report_type|str!, project_id|CHARFK, style_json|jsonb!, version|str!, status|str!, created_by|CHAR, created_at|dt!, updated_at|dt  [UNIQUE: report_type+project_id+version]
### sim_calculator_results
  unit_op_id|CHARPKFK!, sequence_streams_json|jsonb!
### sim_compressor_results
  unit_op_id|CHARPKFK!, outlet_pressure_kpa|float, polytropic_exponent|float, work_kw|float, efficiency|float
### sim_cstr_results
  unit_op_id|CHARPKFK!, residence_time_min|float, volume_m3|float, outlet_temperature_k|float
### sim_import_warnings
  warning_id|CHARPK!, import_id|CHARFK!, severity|str!, unit_id|str, message|text!, created_at|dt!
### sim_imports
  import_id|CHARPK!, project_id|CHARFK!, workspace_id|CHARFK!, import_type|str!, status|str!, source_file_name|str!, convergence_status|str, banner_version|str, preview_streams_json|jsonb!, preview_towers_json|jsonb!, conflict_report_json|jsonb, warnings_json|jsonb!, created_by|CHAR!, created_at|dt!, expires_at|dt!, committed_at|dt, committed_by|CHAR
### sim_reactor_results
  unit_op_id|CHARPKFK!, operation_mode|str, rxset_id|str, reactions_count|int, conversions_json|jsonb!
### sim_splitter_results
  unit_op_id|CHARPKFK!, outlets_json|jsonb!
### sim_stca_results
  unit_op_id|CHARPKFK!, ovhd_stream|str, btms_stream|str, actual_reflux_ratio|float, min_reflux_ratio|float, num_theoretical_stages|int
### sim_tower_results
  tower_id|CHARPK!, import_id|CHARFK!, tower_uid|str!, tower_name|str, tower_type|str!, num_stages|int, condenser_type|str, reboiler_type|str, feed_stages_json|jsonb!, product_streams_json|jsonb!, tray_data_json|jsonb!, compositions_json|jsonb!, loading_json|jsonb!, rating_json|jsonb!, is_unreliable|bool!, created_at|dt!
### sim_unit_op_results
  unit_op_id|CHARPK!, import_id|CHARFK!, unit_uid|str!, unit_type|str!, convergence_status|str, iterations|int, raw_summary_json|jsonb!, feed_streams_json|jsonb!, product_streams_json|jsonb!, is_unreliable|bool!, created_at|dt!  [UNIQUE: import_id+unit_uid]
### stream_symbols
  symbol_id|CHARPK!, asset_id|CHARFK, symbol|str!, name|str!, category|str, is_active|bool!, status|str!, version|str!, created_by|CHAR, created_at|dt!, updated_at|dt  [UNIQUE: symbol]
### thermosiphon_circulation_results
  thermosiphon_id|CHARPK!, equipment_tag|str!, equipment_name|str, circulation_type|str!, shell_diameter|float, drum_diameter|float, drum_liquid_level|float, installation_height_calc|float, installation_height_final|float, safety_factor|float!, check_result|str, circulation_drive_ratio|float, inlet_pipe_params|jsonb, outlet_pipe_params|jsonb, shell_side_params|jsonb, other_params|jsonb, tag_number|str, sign_status|str!, record_hash|str!, approval_step|int, approval_depth|int!, approval_role|str, approval_chain_snapshot|jsonb, locked_by_deliverable|bool!, change_pending_since|dt, change_resolved_by|str, change_resolved_at|dt, change_abandoned_at|dt, change_abandoned_reason|str, obsoleted_reason|str, obsoleted_by|CHAR, obsoleted_at|dt, obsoleted_via_deliverable_id|CHAR, reversal_requested_at|dt, reversal_requested_by|CHAR, reversal_reason|str, reversal_approved_by|CHAR, reversal_approved_at|dt, stale_resolution_path|str, hash_changed|bool, changed_fields|jsonb, project_id|CHARFK!, workspace_id|CHARFK!, created_by|CHAR, created_at|dt!, updated_at|dt  [UNIQUE: project_id+equipment_tag]
### two_phase_results
  two_phase_id|CHARPK!, input_json|jsonb!, output_json|jsonb!, Bx|float, By|float, flow_pattern|str, two_phase_check|str, liquid_velocity|float, gas_velocity|float, pressure_gradient|float, void_fraction|float, calc_method|str, created_at|dt!, record_hash|str!
### user_projects
  id|CHARPK!, user_id|CHARFK!, project_id|CHARFK!, role_in_project|str!, granted_by|CHARFK, granted_at|dt!, revoked_at|dt, revoked_by|CHARFK, created_by|CHAR, created_at|dt!, updated_at|dt  [UNIQUE: user_id+project_id]
### util_results
  util_result_id|CHARPK!, project_id|CHARFK!, workspace_id|CHARFK!, business_date|date, consumption_json|jsonb!, jsonb_deprecated|bool!, electrical_power_kwh_yr|float, fuel_gas_consumption_nm3_yr|float, steam_consumption_t_yr|float, cooling_water_consumption_t_yr|float, annual_total_energy|float, total_toe|float, total_standard_coal_kg|float, tolerance_status|str, source|str, created_by|CHAR, created_at|dt!, updated_at|dt
### utility_energy_summary
  id|CHARPK!, project_id|CHARFK!, workspace_id|CHARFK!, business_year|int!, source|str!, electricity_kwh_yr|float, fuel_gas_nm3_yr|float, steam_t_yr|float, water_t_yr|float, gas_nm3_yr|float, low_temp_heat_gj_yr|float, annual_total_energy|float!, electricity_value_type|str, r1_classification_json|jsonb, toe_conversion_factor|float!, standard_coal_factor|float!, total_toe|float!, total_standard_coal_kg|float!, tolerance_pct|float, tolerance_status|str!, computed_at|dt!, created_at|dt!, updated_at|dt  [UNIQUE: project_id+business_year+source]
### utility_fuel_gas
  id|CHARPK!, project_id|CHARFK!, workspace_id|CHARFK!, equipment_id|CHARFK, equipment_tag|str!, fuel_type|str!, gas_source|str, calorific_value_kcal_nm3|float!, consumption_nm3_h|float!, operating_phase|str!, operating_hours_per_year|float!, annual_consumption_nm3|float!, source|str!, created_at|dt!, updated_at|dt  [UNIQUE: project_id+equipment_tag+operating_phase]
### utility_gas_media
  id|CHARPK!, project_id|CHARFK!, workspace_id|CHARFK!, equipment_id|CHARFK, equipment_tag|str!, gas_medium|str!, consumption_nm3_h|float!, operating_hours_per_year|float!, annual_consumption_nm3|float!, source|str!, created_at|dt!, updated_at|dt  [UNIQUE: project_id+equipment_tag+gas_medium]
### utility_heat_exchange
  id|CHARPK!, project_id|CHARFK!, workspace_id|CHARFK!, equipment_id|CHARFK, equipment_tag|str!, steam_pressure_mpa_gauge|float!, steam_quality_pct|float!, return_condensate_pct|float!, temperature_class|str!, pressure_level|str, medium_type|str, steam_consumption_t_h|float!, operating_hours_per_year|float!, annual_consumption_t|float!, source|str!, created_at|dt!, updated_at|dt  [UNIQUE: project_id+equipment_tag]
### utility_low_temp_heat
  id|CHARPK!, project_id|CHARFK!, workspace_id|CHARFK!, equipment_id|CHARFK, equipment_tag|str!, heat_recovery_gj_h|float!, operating_hours_per_year|float!, annual_recovered_heat_gj|float!, source|str!, created_at|dt!, updated_at|dt  [UNIQUE: project_id+equipment_tag]
### utility_power_items
  id|CHARPK!, project_id|CHARFK!, workspace_id|CHARFK!, equipment_id|CHARFK, equipment_tag|str!, motor_power_kw|float!, operating_hours_per_year|float!, load_factor|float!, annual_consumption_kwh|float!, source|str!, created_at|dt!, updated_at|dt  [UNIQUE: project_id+equipment_tag]
### workflow_progress
  progress_id|CHARPK!, project_id|CHARFK!, workflow_type|str!, workflow_id|CHAR!, step_order|int!, step_role|str!, step_status|str!, started_at|dt, completed_at|dt, assignee|CHAR, result_hash|str, created_by|CHAR, created_at|dt!, updated_at|dt  [UNIQUE: workflow_type+workflow_id+step_order]
