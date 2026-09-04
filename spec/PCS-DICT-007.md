PCS-DICT-007：计算模块输入输出JSON字典（完整版）
文件标识	PCS-DICT-007
当前版本	V2.0（完整整合版）
发布日期	2026-08-29
关联文档	PCS-DICT-ALL-003 V3.0（计算模块16表）、SPEC-P4/P5/P6
数据来源	容器数据表（PR-01/D605）、板式塔数据表（PR-01/D204）、球罐数据表（PT-00/D4801）、过滤器数据表（PR-00/D3801）、反应器数据表（W-30-00）、MEC PSV标准、API 2000
第一部分：概述
1.1 目的
定义计算模块（P4-P6）各结果表中JSON字段的内部结构，为各模块的输入表单、计算引擎输出和交付物生成提供权威依据。

1.2 覆盖模块
模块	结果表	本字典章节
VESSEL（容器/塔/球罐）	vessel_results	第二部分
FLASH（闪蒸）	flash_results	第三部分
PIPE_NET（管网）	pipe_network_results	第四部分
FLARE_SYS（火炬）	flare_system_results	第五部分
PSYCHRO（湿空气）	psychro_results	第六部分
OPEN_CHANNEL（明渠）	open_channel_results	第七部分
SEP_EQUIP（分离设备）	sep_equip_results	第八部分
FILTRATION（过滤）	filtration_results	第九部分
RESTRICTION（节流）	restriction_results	第十部分
1.3 已平铺字段的模块
以下模块的完整字段已在PCS-DICT-ALL-003 V3.0表中定义（非JSON，平铺列），本字典不再重复：

piping_results（表16，完整平铺字段）

pump_results（表18，12个JSON子结构已在V3.0定义）

psv_results（表19，平铺字段+data_sheet_json/calc_sheet_json见PCS-DICT-009）

cv_results（表24，平铺字段）

cooling_tower_results（表26，平铺字段）

cost_est_results（表30，平铺字段）

第二部分：VESSEL模块JSON结构
2.1 设备类型枚举
枚举值	设备类型	对应data_sheet_json
HORIZONTAL_VESSEL	卧式容器	vessel_data_sheet_json
VERTICAL_VESSEL	立式容器	vessel_data_sheet_json
TRAY_COLUMN	板式塔	tray_column_data_sheet_json
PACKED_COLUMN	填料塔	packed_column_data_sheet_json
SPHERICAL_TANK	球罐	spherical_tank_data_sheet_json
REACTOR	反应器	reactor_data_sheet_json
2.2 vessel_data_sheet_json（卧式/立式容器）
json
{
  "general": {
    "item_number": "1222-V-106",
    "service": "剩余C4罐",
    "specification": "Φ1600X5000(T-T)",
    "quantity": 1,
    "pid_no": "PR-02/106",
    "position": "HORIZONTAL",
    "operating_mode": "CONTINUOUS"
  },
  "process_design": {
    "medium_name": "剩余C4",
    "fluid_characteristic": {
      "explosive_fluid": true,
      "toxicity_level": "中度危害",
      "max_h2s_partial_pressure_mpaa": null,
      "max_h2_partial_pressure_mpaa": null,
      "other_corrosive_agent_mol_pct": null
    },
    "total_flow_kg_h": 22097,
    "vapor_phase_kg_h": null,
    "oil_phase_kg_h": 22097,
    "water_phase_kg_h": null,
    "operating_temp_c": {"max": 45, "normal": 41, "min": null},
    "operating_pressure_mpag": {"max": 1.02, "normal": 0.34, "min": null},
    "density_kg_m3": {"vapor_phase": null, "oil_phase": 564.93, "water_phase": null},
    "oil_in_water_wt_pct": null,
    "solid_in_oil_wt_pct": null,
    "water_in_oil_wt_pct": null,
    "velocity_m_s": {"gaseous_phase": null, "liquid_phase": null},
    "packing_factor": 0.80,
    "vessel_volume_m3": 11.23,
    "vessel_diameter_id_mm": {"calculated": null, "employed": 1600},
    "tangent_length_mm": 5000,
    "residence_time_min": {"oil_phase": 8.99, "water_phase": null},
    "normal_liquid_level_mm": 800,
    "normal_interface_level_mm": null,
    "operating_medium_weight_kg": 4543,
    "heating_cooling_medium": null,
    "heating_cooling_max_flow_kg_h": null,
    "heat_transfer_area_m2": null,
    "insulation_type": "HEAT",
    "relief_set_pressure_mpag": 1.2
  },
  "mechanical_design": {
    "regulation": null,
    "vessel_class": null,
    "design_pressure_mpag": null,
    "design_temp_c": null,
    "mdmt_c": null,
    "expecting_life_years": null,
    "corrosion_allowance_mm": null,
    "joint_efficiency": null,
    "head_top_type": null,
    "head_bottom_type": null,
    "support_type": null,
    "volume_m3": null,
    "fireproofing": {"internal": null, "external": null},
    "insulation_material": null,
    "insulation_thickness_mm": null,
    "lining_material": "30",
    "lining_thickness_mm": null,
    "design_wind_pressure_pa": null,
    "exposure_category": null,
    "seismic_intensity_degree": null,
    "earthquake_response_accel_g": null,
    "site_class": null,
    "seismic_group": null,
    "codes_specs": null
  },
  "materials": {
    "shell": {"material": null, "std": null},
    "head_left": {"material": null, "std": null},
    "head_bottom": {"material": null, "std": null},
    "jacket": {"material": null, "std": null},
    "drop_leg": {"material": null, "std": null},
    "drum": {"material": null, "std": null},
    "bolt_external": {"material": null, "std": null},
    "nut_external": {"material": null, "std": null},
    "gasket_external": {"material": null, "std": null},
    "reinforcing_rings": {"material": null, "std": null},
    "saddle": {"material": null, "std": null},
    "base_ring": {"material": null, "std": null},
    "stiffening_ring": {"material": null, "std": null},
    "nozzles": {"material": null, "std": null},
    "nozzle_flange": {"material": null, "std": null},
    "bolt_internal": {"material": null, "std": null},
    "nut_internal": {"material": null, "std": null},
    "gasket_internal": {"material": null, "std": null},
    "insulation_support_rings": {"material": null, "std": null},
    "steel_plate_application": null,
    "steel_plate_ut": null,
    "material_recheck": null
  },
  "fabrication_inspection": {
    "welding_specification": null,
    "product_welded_test_coupons": null,
    "nde": {
      "category_ab": {"rt": false, "ut": false},
      "category_cd": {"mt": false, "pt": false}
    },
    "postweld_heat_treatment": null,
    "hydro_test_pressure_mpa": {"vertical": null, "horizontal": null},
    "gas_leak_test_pressure_mpa": null,
    "outer_anticorrosion_spec": null,
    "nameplate_language": null,
    "coating_packing_transport": null
  },
  "weights": {
    "total_metal_kg": null,
    "internals_kg": null,
    "platform_ladder_kg": null,
    "filled_water_kg": null,
    "erection_shipping_kg": null,
    "insulation_kg": null,
    "nonmetal_lining_kg": null,
    "fireproofing_kg": null
  },
  "nozzles": [],
  "remarks": [],
  "sketch_ref": null
}
2.3 tray_column_data_sheet_json（板式塔）
json
{
  "general": {
    "item_number": "132-C-301",
    "service": "低分气脱硫塔",
    "specification": "Φ1600/2000×17150(T-T)",
    "quantity": 1,
    "pid_no": "PR-02/037",
    "tangent_length_mm": 17150,
    "total_trays": 15,
    "operating_mode": "CONTINUOUS",
    "position": "VERTICAL"
  },
  "process_operating": {
    "sections": {
      "top": {
        "fluid_name": "脱硫低分气",
        "operating_temp_c": {"max": null, "normal": null, "min": null},
        "operating_pressure_mpag": {"max": null, "normal": null, "min": null},
        "fluid_state": "VAPOR",
        "density_kg_m3": 9.6
      },
      "feed": {
        "fluid_name": "低分气、贫胺液",
        "operating_temp_c": {"max": null, "normal": 51, "min": null},
        "fluid_state": "LIQUID",
        "density_kg_m3": {"gas": 15.7, "liquid": 1009.3}
      },
      "bottom": {
        "fluid_name": "富胺液",
        "operating_pressure_mpag": {"max": null, "normal": 2.80, "min": null},
        "fluid_state": "LIQUID",
        "density_kg_m3": 1046.6
      }
    },
    "feed_tray_number": "15#下",
    "explosive_fluid": true,
    "toxicity_level": "中度危害",
    "max_h2s_partial_pressure_mpaa": 0.56,
    "max_h2_partial_pressure_mpaa": 2.18,
    "prv_set_pressure_mpag": 3.8,
    "operating_liquid_level_mm": {"max": 5100, "normal": 3100, "min": 900},
    "operating_fluid_weight_kg": 15000
  },
  "tray_operating": [
    {
      "tray_no": "1#",
      "trays_in_section": 1,
      "fluid_description": "胺液、低分气",
      "operating_temp_c": {"max": 56, "normal": 56, "min": 56},
      "operating_pressure_mpag": {"max": 2.79, "normal": 2.79, "min": 2.79},
      "liquid_from_tray": {
        "flow_rate_kg_h": 164022, "density_kg_m3": 1009.3,
        "viscosity_mpa_s": 1.3, "molecular_weight_g_mol": 24.18,
        "surface_tension_dyne_cm": 57.56
      },
      "vapor_to_tray": {
        "flow_rate_kg_h": 6075, "density_kg_m3": 9.1,
        "viscosity_mpa_s": 0.01, "molecular_weight_g_mol": 9.03,
        "compressibility": 1.01
      }
    }
  ],
  "tray_efficiency": {
    "operating_flexibility_pct": 30,
    "nominal_capacity_x10000_ta": 260,
    "operating_flexibility_range_pct": "50~115",
    "system_factor": 0.73,
    "min_oper_pressure_check": true,
    "allowable_column_pressure_drop_kpa": 10
  },
  "hydraulics": [
    {
      "tray_no": "1#",
      "max_acceptable_superficial_gas_velocity_m_s": null,
      "superficial_gas_velocity_m_s": null,
      "gas_velocity_through_hole_m_s": null,
      "gas_kinetics_factor": null,
      "weir_load_side_m3_hm": null,
      "dry_drop_mmhg": null,
      "total_drop_per_tray_mmhg": null,
      "liquid_height_on_plate_mm": null,
      "liquid_height_in_weir_mm": null,
      "allowable_leakage_pct": null,
      "entrainment_pct": null,
      "jet_flood_pct": null,
      "downcomer_flood_pct": null,
      "downcomer_clear_liquid_mm": null,
      "downcomer_residence_time_s": null,
      "downcomer_clearance_velocity_m_s": null
    }
  ],
  "tray_structure": [
    {
      "tray_no": "1#",
      "vessel_id_mm": {"calculated": null, "employed": 1600},
      "tray_type": "FLOATING_VALVE",
      "tray_spacing_mm": 600,
      "number_of_passes": 1,
      "furnish_seal_pan": true
    }
  ],
  "tray_layout": {
    "number_of_passes": 1,
    "dimensions_mm": {"a": null, "b": null, "c": null, "d": null, "e": null, "f": null, "g": null}
  },
  "internals_specs": [
    {
      "tray_no": "1#",
      "parts": [
        {"part": "阀 Valve", "spec": null, "material": "S30408", "qty": "供应商设计"},
        {"part": "塔盘板 Tray", "spec": "3mm", "material": "06Cr13(GB/T4237)", "qty": "15层"},
        {"part": "侧面降液板 Side Downcomer", "spec": "4mm", "material": "06Cr13(GB/T4237)", "qty": "15层"},
        {"part": "降液板连接板 Downcomer Bar", "spec": "12mm", "material": "Q345R(GB713)", "qty": "15层"},
        {"part": "受液盘 Recessed Pan", "spec": "4mm", "material": "06Cr13(GB/T4237)", "qty": "15层"},
        {"part": "支承圈 Support Ring", "spec": "12mm", "material": "Q345R(GB713)", "qty": "15层"},
        {"part": "螺栓螺母 Bolt/Nut", "spec": null, "material": "S30408", "qty": "供应商设计"},
        {"part": "垫片 Gasket", "spec": null, "material": "S30408", "qty": "供应商设计"},
        {"part": "卡子 Hold-down Clamp", "spec": null, "material": "S30408", "qty": "供应商设计"}
      ]
    }
  ],
  "mechanical_design": {
    "regulation": "TSG R0004",
    "vessel_class": "CLASS_III",
    "codes_specs": "GB150.1~150.4 JB/T4710",
    "design_pressure_mpag": "3.8/FV",
    "design_temp_c": "150/0.7",
    "mdmt_c": null,
    "expecting_life_years": 15,
    "corrosion_allowance_mm": 6,
    "joint_efficiency": 1,
    "head_top_type": "ELLIPSOIDAL",
    "head_bottom_type": "ELLIPSOIDAL",
    "support_type": "SKIRT",
    "volume_m3": 43,
    "design_wind_pressure_pa": 714,
    "exposure_category": "A",
    "seismic_intensity_degree": 7,
    "earthquake_response_accel_g": 0.15,
    "site_class": "II",
    "seismic_group": "第二组",
    "insulation_material": "硅酸铝纤维",
    "insulation_thickness_mm": 60
  },
  "materials": {
    "shell": {"material": "Q345R(R-HIC)", "std": "见注"},
    "head_top": {"material": "Q345R(R-HIC)", "std": "见注"},
    "head_bottom": {"material": "Q345R(R-HIC)", "std": "见注"},
    "nozzles": {"material": "20", "std": null},
    "nozzle_flange": {"material": "16Mn(R-HIC)", "std": "见注"},
    "skirt": {"material": "Q345R", "std": "GB713"},
    "base_ring": {"material": "Q345R", "std": "GB713"},
    "stiffening_ring": {"material": "Q345R", "std": "GB713"},
    "insulation_support_rings": {"material": "Q235B/Q345R", "std": null},
    "steel_plate_application": "正火",
    "steel_plate_ut": "100%-Ⅱ",
    "material_recheck": "按标准"
  },
  "fabrication_inspection": {
    "welding_specification": "NB/T47015",
    "product_welded_test_coupons": true,
    "nde": {
      "category_ab": {"rt": true, "rt_grade": "AB级", "rt_ratio": "100%-Ⅱ"},
      "category_cd": {"mt": true, "mt_ratio": "100%-Ⅰ"}
    },
    "postweld_heat_treatment": true,
    "hydro_test_pressure_mpa": {"vertical": 4.81, "horizontal": 4.98},
    "outer_anticorrosion_spec": "SH/T3022",
    "nameplate_language": "中文",
    "coating_packing_transport": "JB/T4711"
  },
  "weights": {
    "total_metal_kg": 33760,
    "internals_kg": 3000,
    "platform_ladder_kg": 13400,
    "filled_water_kg": 43000,
    "insulation_kg": 1600,
    "fireproofing_kg": 1020
  },
  "nozzles": [
    {"mark":"N1","service":"安全阀口","quantity":1,"pressure_rating":300,"size_dn":50,"flange_std":"HG/T20615","mating_flange_type":"RF"},
    {"mark":"N2","service":"富胺液出口","quantity":1,"pressure_rating":300,"size_dn":200,"flange_std":"HG/T20615","mating_flange_type":"RF"},
    {"mark":"N3","service":"脱硫低分气出口","quantity":1,"pressure_rating":300,"size_dn":200,"flange_std":"HG/T20615","mating_flange_type":"RF"},
    {"mark":"N7","service":"贫胺液入口","quantity":1,"pressure_rating":300,"size_dn":200,"flange_std":"HG/T20615","mating_flange_type":"RF"},
    {"mark":"N8","service":"低分气入口","quantity":1,"pressure_rating":300,"size_dn":200,"flange_std":"HG/T20615","mating_flange_type":"RF"},
    {"mark":"M1","service":"人孔","quantity":1,"size_dn":500},
    {"mark":"M2","service":"人孔","quantity":1,"size_dn":500},
    {"mark":"M3","service":"人孔","quantity":1,"size_dn":500},
    {"mark":"L1","service":"伺服液位计口","quantity":1,"size_dn":150}
  ],
  "remarks": [],
  "sketch_ref": null
}
2.4 spherical_tank_data_sheet_json（球罐）
json
{
  "general": {
    "item_number": "324-TK-01/02",
    "service": "催化液化气球罐",
    "quantity": 2,
    "volume_m3": 2000,
    "diameter_id_mm": 15700,
    "structural_type": "MIXED",
    "support_leg_count": 10,
    "support_leg_height_mm": 9800,
    "pid_no": null,
    "operating_mode": "CONTINUOUS"
  },
  "process_design": {
    "medium_name": "催化液化气",
    "fluid_flammable": "INFLAMMABLE",
    "fluid_hazard_level": "LIGHT",
    "max_h2s_partial_pressure_mpaa": null,
    "max_h2_partial_pressure_mpaa": null,
    "other_corrosive_agent": "H2S不大于10ppm",
    "aromatic_content_vpct": null,
    "operating_temp_c": 40,
    "operating_pressure_mpag": 1.37,
    "max_min_operating_level_mm": {"max": 12620, "min": 1000},
    "filling_ratio": 0.9,
    "saturated_vapor_pressure_50c_mpaa": 1.71,
    "density_kg_m3": 568,
    "viscosity_mpa_s": 0.11,
    "max_input_output_flow_m3h": null
  },
  "fire_protection": {
    "cooling_medium": "消防冷却水",
    "supply_strength_l_min_m2": 9,
    "sprayer_rated_pressure_mpag": 0.35,
    "cooling_medium_temp_c": "常温",
    "cooling_area_m2": 779.31,
    "calculated_cooling_flow_l_s": 116.90,
    "system_requirements": {
      "system_type": "固定式水喷雾系统",
      "riser_pipe_count": 2,
      "riser_pipe_arrangement": "对称布置",
      "independent_supply": "上下半球2个独立供水系统",
      "pipeline_material": "镀锌管"
    }
  },
  "mechanical_design": {
    "regulation": "固定式压力容器安全技术监察规程",
    "vessel_class": "CLASS_III",
    "codes_specs": "GB150.1~150.4 GB12337 GB50094",
    "design_pressure_mpag": 1.77,
    "design_temp_c": 50,
    "mdmt_c": -19,
    "corrosion_allowance_mm": 2,
    "joint_efficiency": 1,
    "insulation_material": "凉凉隔热胶DT22-2",
    "insulation_thickness_mm": 30,
    "insulation_density_kg_m3": null,
    "design_wind_pressure_pa": 850,
    "exposure_category": "A",
    "seismic_intensity_degree": 7,
    "earthquake_response_accel_g": 0.1,
    "site_class": "II",
    "seismic_group": "第一组",
    "expecting_life_years": 20,
    "min_monthly_avg_temp_c": 14
  },
  "materials": {
    "shell_plate": {"material": "Q370R", "std": "GB713"},
    "support_column": {"material": "Q370R", "std": "GB713"},
    "nozzle_flange": {"material": "20MnMo", "std": "NB/T47008"},
    "ear_plate": {"material": "Q345R", "std": "GB713"},
    "wing_plate": {"material": "Q345R", "std": "GB713"},
    "base_plate": {"material": "Q345R", "std": "GB713"},
    "tie_rod": {"material": "16Mn", "std": "NB/T47008"},
    "support_plate": {"material": "Q370R", "std": "GB713"}
  },
  "nozzles": [
    {"mark":"A","service":"进出油口","quantity":1,"pressure_rating":40.0,"size_dn":150,"flange_std":"HG/T20592-2009","mating_flange_type":"WN/M"},
    {"mark":"C1","service":"排水口","quantity":1,"pressure_rating":40.0,"size_dn":50,"flange_std":"HG/T20592-2009","mating_flange_type":"WN/M"},
    {"mark":"C8","service":"放空口","quantity":1,"pressure_rating":40.0,"size_dn":200,"flange_std":"HG/T20592-2009","mating_flange_type":"WN/M"},
    {"mark":"M1-M2","service":"人孔","quantity":2,"size_dn":500},
    {"mark":"P1","service":"压力表口","quantity":1,"pressure_rating":40.0,"size_dn":15,"flange_std":"HG/T20592-2009","mating_flange_type":"WN/M"},
    {"mark":"P2","service":"压力变送器口","quantity":1,"pressure_rating":40.0,"size_dn":15,"flange_std":"HG/T20592-2009","mating_flange_type":"WN/M"},
    {"mark":"T1","service":"双金属温度计套管口","quantity":1,"pressure_rating":40.0,"size_dn":25,"overhang_mm":200,"flange_std":"HG/T20592-2009","mating_flange_type":"WN/FM"},
    {"mark":"T2","service":"热电阻套管口","quantity":1,"pressure_rating":40.0,"size_dn":25,"overhang_mm":200,"flange_std":"HG/T20592-2009","mating_flange_type":"WN/FM"},
    {"mark":"L1","service":"伺服液位计口","quantity":1,"pressure_rating":40.0,"size_dn":150,"flange_std":"HG/T20592-2009","mating_flange_type":"WN/M"},
    {"mark":"L3","service":"浮球式液位开关口","quantity":1,"pressure_rating":40.0,"size_dn":80,"overhang_mm":200,"flange_std":"HG/T20592-2009","mating_flange_type":"WN/FM"}
  ],
  "remarks": [
    "球罐的消防喷淋冷却装置及平台梯子由设备厂家负责设计，储运工艺确定方位及分界法兰高度",
    "液态烃球罐支腿从地面到支腿与球体交叉处以下0.2m的部位应覆盖耐火涂层，其耐火极限不应低于2h",
    "工艺管道、仪表开口及消防冷却水管道上罐由储运汇总提供附图",
    "自然条件由业主提供"
  ],
  "sketch_ref": null
}
2.5 reactor_data_sheet_json（反应器）
json
{
  "general": {
    "item_number": "R1002",
    "service": "氧化锌反应器",
    "quantity_required": 1,
    "vessel_class": null,
    "position": "VERTICAL"
  },
  "process_operating": {
    "fluid_name": "天然气",
    "operating_temp_c": {"max": 390, "normal": 380, "min": null},
    "operating_pressure_mpag": {"max": 3.22, "normal": 3.12, "min": null},
    "vapor_phase": {
      "mass_flow_kg_h": 2003,
      "molecular_weight_inlet_g_mol": 23.087,
      "molecular_weight_outlet_g_mol": 23.087,
      "density_inlet_kg_m3": 13.31,
      "density_outlet_kg_m3": 13.61
    }
  },
  "catalyst_beds": {
    "total_bed_height_mm": null,
    "segments": [
      {"segment_no": 1, "bed_height_mm": null, "filling_specification": null, "filling_type": "CATALYST"},
      {"segment_no": 2, "bed_height_mm": null, "filling_specification": null, "filling_type": "CATALYST"},
      {"segment_no": 3, "bed_height_mm": null, "filling_specification": null, "filling_type": "CATALYST"}
    ],
    "ceramic_ball": {"spec": "15KK开孔瓷球", "density_kg_m3": 1500},
    "catalyst": {"density_kg_m3": 1000}
  },
  "construction": {
    "shell_diameter_mm": {"od": null, "id": 1000},
    "tangent_length_mm": null,
    "skirt_support_height_mm": null,
    "head_type": null,
    "total_volume_m3": null,
    "normal_operating_liquid_volume_m3": null,
    "level_control_volume_range_m3": null
  },
  "safety_valve": {
    "type_spec": null,
    "set_pressure_mpag": null,
    "quantity": null
  },
  "mechanical_design": {
    "design_temp_c": {"upper": null, "lower": null},
    "design_pressure_mpag": {"internal": null, "external": null},
    "test_pressure_mpag": {"hydrostatic": null, "pneumatic": null},
    "wall_thickness_mm": {"shell": null, "head": null},
    "corrosion_allowance_mm": null,
    "lining_clad_layer_mm": null
  },
  "insulation": {
    "required": true,
    "type": "隔热",
    "thickness_mm": null
  },
  "platform": {"layers": null, "total_area_m2": null},
  "remarks": [
    "15KK开孔瓷球密度为1500kg/m³",
    "催化剂的密度为1000kg/m³"
  ]
}
2.6 VESSEL模块通用枚举
枚举名	值
VesselPosition	HORIZONTAL/VERTICAL
StructuralType（球罐）	MIXED/ORANGE_PEEL/FOOTBALL
TrayType	FLOATING_VALVE/SIEVE/BUBBLE_CAP/BAFFLE
HeadType	ELLIPSOIDAL/HEMISPHERICAL/TORISPHERICAL/FLAT
SupportType	SADDLE/SKIRT/LEG/RING
VesselClass	CLASS_I/CLASS_II/CLASS_III/NON_CLASSIFIED
第三部分：FLASH模块（flash_results）
3.1 input_json（按calc_type变化）
json
// PT_FLASH
{"temperature_c": 300, "pressure_mpaa": 1.0, "composition": {"basis":"molar","components":[]}, "method": "PR"}

// PH_FLASH
{"pressure_mpaa": 1.0, "enthalpy_kj_kg": 500.0, "composition": {...}, "method": "PR"}

// BUBBLE_T
{"pressure_mpaa": 1.0, "liquid_composition": {...}, "method": "PR"}

// DEW_T
{"pressure_mpaa": 1.0, "vapor_composition": {...}, "method": "PR"}

// SATURATION
{"temperature_c": 100.0, "fluid": "Water"}
3.2 output_json
json
{
  "vapor_fraction": 0.35,
  "vapor_composition": {"basis":"molar","components":[]},
  "liquid_composition": {"basis":"molar","components":[]},
  "enthalpy_kj_kg": null,
  "entropy_kj_kg_k": null,
  "k_values": [{"component":"C6H14","k": 1.5}],
  "converged": true,
  "iterations": 15,
  "method_used": "PR"
}
第四部分：PIPE_NET模块（pipe_network_results）
4.1 topology_json
json
{
  "nodes": [{"node_id": "N1", "label": "泵出口", "type": "JUNCTION"}],
  "pipes": [
    {
      "pipe_id": "P1",
      "from_node": "N1",
      "to_node": "N2",
      "length_m": 100,
      "diameter_mm": 100,
      "roughness_mm": 0.046,
      "fittings_count": 3
    }
  ]
}
4.2 convergence_log_json
json
{
  "solver": "Hardy-Cross",
  "max_iterations": 100,
  "tolerance": 1e-6,
  "iterations_used": 25,
  "converged": true,
  "residual_history": [0.5, 0.1, 0.02, 0.004, 0.0005]
}
4.3 flow_distribution_json
json
[
  {"pipe_id": "P1", "flow_kg_h": 50000, "velocity_m_s": 1.77, "pressure_drop_kpa": 31.2}
]
第五部分：FLARE_SYS模块（flare_system_results）
5.1 radiation_check_json
json
{
  "total_relief_load_kg_h": null,
  "header_size_inch": null,
  "header_mach": null,
  "kod_diameter_mm": null,
  "stack_height_m": null,
  "radiation_at_grade_kw_m2": null,
  "radiation_limit_kw_m2": null,
  "pass": true,
  "flare_type": null,
  "steam_for_smokeless_kg_h": null
}
第六部分：PSYCHRO模块（psychro_results）
6.1 input_json / output_json（按calc_type）
calc_type	input_json	output_json
HUMIDITY_RATIO	{"temp_c":30,"rh_pct":60,"pressure_kpa":101.325}	{"humidity_ratio_kg_kg":null}
DEW_POINT	{"temp_c":30,"rh_pct":60}	{"dew_point_c":null}
WET_BULB	{"temp_c":30,"rh_pct":60}	{"wet_bulb_c":null}
ENTHALPY	{"temp_c":30,"rh_pct":60}	{"enthalpy_kj_kg":null}
SPECIFIC_VOLUME	{"temp_c":30,"rh_pct":60}	{"specific_volume_m3_kg":null}
COOLING_COIL	{"inlet":{"temp_c":35,"rh_pct":70},"outlet":{"temp_c":15,"rh_pct":90}}	{"sensible_kw":null,"latent_kw":null}
第七部分：OPEN_CHANNEL模块（open_channel_results）
7.1 cross_section_json
json
// 梯形
{"type":"TRAPEZOIDAL","bottom_width_m":1.0,"side_slope_h_v":2.0,"depth_m":0.5}

// 矩形
{"type":"RECTANGULAR","width_m":1.5,"depth_m":0.6}

// 圆形
{"type":"CIRCULAR","diameter_m":0.8}
第八部分：SEP_EQUIP模块（sep_equip_results）
json
{
  "equip_type": "CYCLONE",
  "dimensions": {"diameter_mm": 800, "height_mm": 2400, "inlet_w_mm": 200, "inlet_h_mm": 400},
  "efficiency_pct": 95.5,
  "pressure_drop_kpa": 1.2,
  "cut_diameter_micron": 10,
  "method": "Lapple"
}
第九部分：FILTRATION模块（filtration_results）
9.1 data_sheet_json完整结构
json
{
  "general": {
    "item_number": "112-SR-106AB",
    "service": "蜡油封油过滤器",
    "quantity_total": 2,
    "quantity_operating": 1,
    "quantity_spare": 1,
    "filter_type": "Y_TYPE"
  },
  "process_conditions": {
    "fluid_name": "蜡油",
    "fluid_state": "LIQUID",
    "toxicity_level": "MIDDLE",
    "explosive_fluid": true,
    "backwash_medium": "蒸汽",
    "operating_temp_c": 169,
    "operating_pressure_mpag": 1.45,
    "density_kg_m3": 940,
    "viscosity_mpa_s": 10,
    "allowable_pressure_drop_mpa": 0.0689,
    "design_flow_m3h": 12.5,
    "max_flow_m3h": 17.5,
    "vent_drain_required": true
  },
  "construction": {
    "design_temp_c": null,
    "design_pressure_mpag": null,
    "shell_od_mm": null,
    "shell_length_mm": null,
    "filtration_rating_micron": 100,
    "sight_glass": false,
    "differential_pressure_gauge": true,
    "level_gauge": true
  },
  "screen_mesh_table": [
    {"mesh_width_mm": 2.0, "wire_diameter_mm": 0.450, "mesh_per_inch": 10, "holes_per_inch2": 100, "open_area_pct": 66.60},
    {"mesh_width_mm": 1.0, "wire_diameter_mm": 0.315, "mesh_per_inch": 20, "holes_per_inch2": 400, "open_area_pct": 54.70},
    {"mesh_width_mm": 0.6, "wire_diameter_mm": 0.280, "mesh_per_inch": 30, "holes_per_inch2": 900, "open_area_pct": 46.50},
    {"mesh_width_mm": 0.4, "wire_diameter_mm": 0.224, "mesh_per_inch": 40, "holes_per_inch2": 1600, "open_area_pct": 40.90},
    {"mesh_width_mm": 0.3, "wire_diameter_mm": 0.200, "mesh_per_inch": 50, "holes_per_inch2": 2500, "open_area_pct": 36.00},
    {"mesh_width_mm": 0.1, "wire_diameter_mm": 0.071, "mesh_per_inch": 120, "holes_per_inch2": 14400, "open_area_pct": 44.00},
    {"mesh_width_mm": 0.1, "wire_diameter_mm": 0.081, "mesh_per_inch": 140, "holes_per_inch2": 19600, "open_area_pct": 30.80}
  ],
  "nozzles": [
    {"mark":"N1","service":"入口","quantity":1,"pressure_rating":5.0,"size_dn":50,"flange_std":"HG/T20615","mating_flange_type":"WN/RF"},
    {"mark":"N2","service":"出口","quantity":1,"pressure_rating":5.0,"size_dn":50,"flange_std":"HG/T20615","mating_flange_type":"WN/RF"},
    {"mark":"N3","service":"蒸汽吹扫口","quantity":1,"pressure_rating":5.0,"size_dn":50,"flange_std":"HG/T20615","mating_flange_type":"WN/RF"},
    {"mark":"N4","service":"排污口","quantity":1,"pressure_rating":5.0,"size_dn":50,"flange_std":"HG/T20615","mating_flange_type":"WN/RF"},
    {"mark":"N5","service":"放空口","quantity":1,"pressure_rating":5.0,"size_dn":50,"flange_std":"HG/T20615","mating_flange_type":"WN/RF"}
  ],
  "materials": {
    "shell": null,
    "internals": null,
    "nozzle_pipe": "20#",
    "flange": "20#",
    "gasket": "缠绕垫0Cr18Ni9/柔性石墨带（HG/T20631）带内环和对中环型",
    "fastener": "双头螺柱/螺母35CrMoA/35#（HG/T20634）"
  },
  "notes": [
    "除去干中的焦粉等固体小颗粒，过滤器需带液位计及进出口差压表",
    "过滤器出口过滤精度：≤100μm，要求大于100μm的颗粒除去率不小于95%"
  ]
}
第十部分：版本历史
版本	日期	修改内容
V1.0	2026-08-29	初始版本（FLASH/PIPE_NET/FLARE_SYS/PSYCHRO/OPEN_CHANNEL/SEP_EQUIP/FILTRATION基础结构）
V1.1	2026-08-29	增补容器数据表vessel_data_sheet_json（SUP-001，卧式容器实例）
V1.2	2026-08-29	增补板式塔数据表tray_column_data_sheet_json（SUP-002，15层浮阀塔实例）
V1.3	2026-08-29	增补球罐数据表spherical_tank_data_sheet_json+反应器数据表（SUP-003）
V2.0	2026-08-29	完整整合版：VESSEL四种设备类型+8个计算模块JSON结构，完整枚举定义
PCS-DICT-007 V2.0完。 本文档覆盖：

内容	章节
VESSEL模块（4种设备类型完整数据表）	第二部分
FLASH模块（8种计算类型）	第三部分
PIPE_NET（拓扑/收敛/分配）	第四部分
FLARE_SYS（辐射校核）	第五部分
PSYCHRO（6种计算类型）	第六部分
OPEN_CHANNEL（3种断面）	第七部分
SEP_EQUIP（旋风/丝网等）	第八部分
FILTRATION（含筛网参数表）	第九部分
P4-P6阶段计算模块开发严格以此为准。


