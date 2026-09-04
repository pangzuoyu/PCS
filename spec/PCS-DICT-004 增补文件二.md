PCS-DICT-004 增补文件二
文件标识	PCS-DICT-004-SUP-002
当前版本	V1.2
发布日期	2026-08-29
增补基准	PCS-DICT-004 V1.0 + SUP-001（浙石化）
新增参考	WorleyParsons Basis of Design Template（Oil & Gas, Offshore/Onshore, 2015-10-26）
1. 增补说明
1.1 新增参考文件价值
这是首个海上油气田（Offshore/Onshore Oil & Gas）的BEDD模板，与前四份文档形成完整覆盖：

维度	前四份（炼化/化工）	本模板（油气田）	互补性
行业	炼化/化工/公用工程	海上油气田	全新领域
环境条件	气象/水文	波浪/海流/水深/海生物附着	海上独有
设备平台	工艺装置/储运	井口平台/海底管线/立管	上游独有
流体数据	原油/燃料气	井流物组成/虚拟组分/地层水/乳化物	油田特有
产品	化工产品	天然气/凝析油/LPG	产品规格章节
安全	消防	逃生/救生/井控/火灾气体探测	海上安全
通用信息	—	坐标系统/高程基准	油气田特有
1.2 与现有结构的融合
BEDD字典是通用Schema，不同项目类型按需使用子结构。本模板的海上字段组新增为独立顶层结构或site_conditions下的子结构，不影响已有炼化/化工项目的使用。

2. 新增字段定义
2.1 project_info 新增
字段名	类型	必填	说明	来源
field_name	string	❌	油田/气田名称	BoD §1.2
coordinate_system	string	❌	坐标系统名称	BoD §2.3
elevation_datum	string	❌	高程基准	BoD §2.4
field_coordinates	object	❌	设施坐标	BoD §1.2
field_exploration_history	string	❌	勘探开发历史	BoD §1.4
field_coordinates子结构：

json
[
  {"facility": "Development Well A", "northing": "1 234 567 mN", "easting": "999 999 mE"},
  {"facility": "Development Well B", "northing": "1 234 000 mN", "easting": "999 111 mE"}
]
field_exploration_history示例：

json
{
  "seismic_acquisition": {"year": 1981, "description": "首次地震勘探"},
  "exploration_wells": [
    {"name": "Kupe 1", "year": 1985, "result": "plugged and abandoned"},
    {"name": "Kupe South 1", "year": 1986, "result": "43m gas/condensate + 20m oil"}
  ]
}
2.2 site_conditions 新增顶层子结构
2.2.5 site_conditions.offshore（海上环境条件）🔵🔵
来源：{BoD §4.2}

json
{
  "offshore": {
    "seawater_temp_profile": {
      "unit": "°C",
      "depth_profiles": [
        {"depth_m": 0, "monthly_avg": {"Jan": null, "Feb": null, "...": null}},
        {"depth_m": 10, "monthly_avg": {}},
        {"depth_m": 20, "monthly_avg": {}}
      ]
    },
    "design_temps": {
      "min_air_temp_95pct": null,
      "max_air_temp_99_5pct_plus3": null,
      "design_air_temp_ac": null,
      "design_air_temp_gt": null,
      "min_rh": null,
      "max_rh": null
    },
    "waves": {
      "return_periods_years": [1, 5, 10, 25, 50, 100],
      "parameters": {
        "hs_m": [],       // Significant wave height
        "tp_s": [],       // Spectral peak period
        "tm_s": [],       // Spectral mean period
        "tz_s": [],       // Average zero-crossing period
        "hmax_m": [],     // Maximum single wave
        "thmax_s": [],    // Period of maximum wave
        "crest_m": []     // Crest elevation
      },
      "wave_direction": {"range1": "240-290°", "condition1": "any Hs", "range2": "90-240°", "condition2": "Hs up to 7m"}
    },
    "wind": {
      "return_periods_years": [1, 5, 10, 25, 50, 100],
      "ten_min_mean": [],    // U10
      "one_min_mean": [],    // U1
      "three_sec_gust": []   // Ug
    },
    "current": {
      "return_periods_years": [1, 5, 10, 25, 50, 100],
      "wind_driven": {
        "surface": [], "upper_25m_asb": [], "mid_14m_asb": [], "lower_2m_asb": []
      },
      "max_steady": {
        "surface": [], "upper_25m_asb": [], "mid_14m_asb": [], "lower_2m_asb": []
      },
      "direction": {"range1": "280-340°", "condition1": "any current", "range2": "60-150°", "condition2": "Hs>7m"}
    },
    "water_depth": {
      "well_a_m": null, "well_b_m": null,
      "storm_surge_1yr_m": null, "storm_surge_100yr_m": null
    },
    "tide_levels": {
      "hat_m": null, "msl_m": 0.0, "lat_m": null
    },
    "installation_conditions": {
      "wind_1min_ms": null, "wave_height_m": null, "wave_period_s": null,
      "tide_m": null, "current_surface_ms": null, "current_bottom_ms": null,
      "wave_kinematics_factor": 1.0, "current_blockage_factor": 1.0,
      "all_members_smooth": true
    },
    "fatigue_wave_data": {
      "unit": "individual wave height range (m) / mean wave period (s)",
      "entries": [
        {"height_range": "0.0-0.5", "mean_period_s": 3.70, "ambient_waves": 30095234, "storm_waves": 0, "total": 30095234}
      ]
    },
    "marine_growth": {
      "profile": [
        {"el_range": "+4.0 to -6.0", "thickness_mm": 100},
        {"el_range": "-6.0 to -4.0", "thickness_mm": 50},
        {"el_range": "-6.0 to mudline", "thickness_mm": 10}
      ],
      "saturated_density_kg_m3": 1400,
      "on_pipelines": false
    },
    "seawater_properties": {
      "density_kg_m3": 1025,
      "kinematic_viscosity_25c_m2_s": 0.96e-6,
      "specific_heat_j_kg_c": 4.0e3
    },
    "offshore_geotechnical": {
      "soils_description": null,
      "pile_recommendation": null,
      "suction_piles_suitable": false,
      "py_data_ref": null
    },
    "offshore_seismic": {
      "analysis_std": null,
      "acceleration_spectrum": null,
      "damping": null
    }
  }
}
2.3 utilities 扩展
2.3.1 新增 water_systems 成员
水系统	字段名	说明	来源
服务水/海水	service_seawater	平台服务水/海水系统	BoD §17.6.7
产出水处理	produced_water	产出水处理与回注	BoD §17.6.10
污水排放	sewage	生活污水处理	BoD §17.6.9
2.3.2 新增 diesel / jet_fuel
系统	字段名	说明	来源
柴油	diesel	柴油储存与分配	BoD §17.6.5
航空煤油	jet_fuel	直升机加油	BoD §17.6.6
2.4 新增顶层字段组：wells_and_completions（井口与完井）🔵🔵
来源：{BoD §8}

json
{
  "wells_and_completions": {
    "completion_design": null,        // 推荐的完井设计
    "intervention_strategy": null,    // 干预策略
    "wireline_equipment": null,       // 钢丝设备要求
    "downhole_pressure_gauges": null, // 永久井下压力计
    "downhole_chemical_injection": null, // 井下化学注入
    "wellhead_metering": null,        // 井口计量
    "operating_configuration": null   // 操作配置
  }
}
2.5 新增顶层字段组：product_specifications（产品规格）🔵
来源：{BoD §7}。前三份文档无此专门章节。

json
{
  "product_specifications": {
    "sales_gas": {
      "delivery_pressure": null,
      "heating_value": null,
      "h2s_ppm": null,
      "co2_pct": null,
      "water_dewpoint": null,
      "hydrocarbon_dewpoint": null,
      "test_methods": []
    },
    "condensate": {
      "api_gravity": null,
      "rvp_kpa": null,
      "sulfur_ppm": null,
      "pour_point_c": null,
      "wax_content_pct": null,
      "test_methods": []
    },
    "lpg": {
      "composition_pct": {},
      "test_methods": []
    }
  }
}
2.6 新增顶层字段组：process_fluid_data（工艺流体/物料数据）🔵
来源：{BoD §6}。油田特有流体数据。

json
{
  "process_fluid_data": {
    "general_description": null,     // 流体特征概述
    "well_stream_composition": {
      "standard_components": [
        {"component": "Propane", "mol_pct": 0.16}
      ],
      "hypothetical_components": [
        {
          "name": "C7*", "boiling_point_c": 92.2, "mw": 96,
          "liquid_density_kg_m3": 728.1,
          "critical_temp_c": 273.2, "critical_pressure_bara": 30.78,
          "critical_volume_m3_kgmole": 0.389, "acentricity": 0.3026
        }
      ]
    },
    "design_compositions": [],       // 不同生产场景的设计组成
    "impurities": {
      "h2s": {"presence": false, "notes": null},
      "sulfur_compounds": {"presence": false, "notes": null},
      "co2": {"presence": false, "notes": null},
      "radioactive_materials": {"presence": false, "notes": null},
      "mercury": {"presence": false, "notes": null},
      "sand_solids": {"presence": false, "notes": null},
      "phenols": {"presence": false, "notes": null},
      "wax": {"presence": false, "notes": null},
      "asphaltenes": {"presence": false, "notes": null}
    },
    "liquid_viscosity": null,
    "formation_water": {
      "composition": {"ca": 290, "mg": 36, "ph": 8.3, "sp_gr_30c": 1.018},
      "units": "mg/l"
    },
    "emulsions": {
      "propensity": null,
      "chemical_injection_required": true
    },
    "chemicals": []
  }
}
2.7 新增顶层字段组：facility_requirements（设施功能需求扩展）🔵🔵
来源：{BoD §5.2~5.9}。前三份文档仅有设计寿命和操作时间，本模板大幅扩展。

json
{
  "facility_requirements": {
    "design_life": {
      "facility_years": null,
      "exceptions": []
    },
    "production_profiles": {
      "sales_gas_pj_annum": null,
      "associated_liquids": null,
      "profile_reference": null
    },
    "design_rates": {
      "facility": {
        "max_design_capacity": null,
        "min_design_capacity": null,
        "unit": null
      }
    },
    "turndown_requirements": {
      "stable_continuous_operation": true,
      "range": null
    },
    "arrival_pressure": {
      "without_compression_kpag": null,
      "with_compression_kpag": null
    },
    "availability": {
      "definition": null,
      "target": null,
      "system_targets": {
        "wellhead_equipment_pct": 97,
        "platform_instruments_pct": 97,
        "shutdown_instrumentation": "SIL determination",
        "platform_electrical_pct": 97,
        "production_station_pct": 98.6,
        "chemical_injection_pct": 99.97
      },
      "scheduled_downtime": {
        "full_esd_testing": "every 6 months",
        "annual_maintenance": "7-9 days initially, 5-7 days every 4 years",
        "maintenance_period_years": 4
      }
    },
    "operability": {
      "swing_factor_pct": 25,
      "mdc_dcq_ratio": 1.25,
      "composition_variation_allowance": true
    },
    "manning": {
      "offshore": {
        "max_pob": 12,
        "normally_unmanned": true
      },
      "onshore": {
        "manned": true,
        "control_from": "Production Station"
      }
    },
    "maintainability": {
      "offshore_strategy": null,
      "onshore_strategy": null
    },
    "sparing_philosophy": {
      "pressure_vessels": "not spared",
      "teg_system": "2 x 50% units",
      "rotating_equipment": "generally spared",
      "chemical_storage_tanks": "not spared",
      "relief_valves": "spared"
    }
  }
}
2.8 新增顶层字段组：safety_and_risk（安全与风险）🔵
来源：{BoD §15~§18}。前三份文档仅有法规清单，本模板增加了完整的安全设计要求。

json
{
  "safety_and_risk": {
    "hse_design": {
      "safety_showers_eyewash": null,
      "escape_routes_refuge": null,
      "escape_craft_equipment": null,
      "hot_surface_protection": null,
      "noise_limits": null,
      "air_discharges": null,
      "land_discharges": null
    },
    "loss_prevention": {
      "fire_prevention_philosophy": null,
      "fire_gas_detection_philosophy": null,
      "fire_fighting_philosophy": {
        "single_fire_concept": true,
        "deluge_vessels": false,
        "bulk_storage_foam": true
      },
      "fire_water_storage": {
        "max_demand_basis": null,
        "hydrant_min_flow_m3_hr": 230
      },
      "fire_water_pumps": {
        "count": 2,
        "independent_power": true,
        "hydrant_pressure_kpag": 1050,
        "most_distant_outlet_kpag": 690,
        "diesel_engine_runtime_hrs": 4,
        "jockey_pump_m3_hr": 20,
        "jockey_pump_pressure_kpag": 500
      },
      "fire_water_piping": {
        "loop_system": true,
        "underground_in_process_areas": true
      },
      "foam_systems": {
        "application_rate_non_soluble_l_min_m2": 4,
        "application_rate_soluble_l_min_m2": 6
      },
      "fire_proofing": {
        "structural_supports": null,
        "vessels": null
      }
    },
    "safety_risk_requirements": null,
    "environmental_requirements": null,
    "sustainability_requirements": null
  }
}
2.9 新增顶层字段组：instrumentation_control（仪表与控制）🔵
来源：{BoD §21}。

json
{
  "instrumentation_control": {
    "systems": [
      {"name": "PCS", "function": "monitors and controls normal operation"},
      {"name": "ESD", "function": "reacts to abnormal conditions by shutdown"},
      {"name": "FG", "function": "reacts to fire/gas by shutdown and fire protection"}
    ],
    "physical_independence": true,
    "data_highway": {
      "dual_redundant": true,
      "shutdown_signals_via_hardwired_only": true
    }
  }
}
2.10 新增顶层字段组：electrical_requirements（电气扩展）🔵
来源：{BoD §22}。前三份已有基础电气数据，本模板增加了系统层面要求。

json
{
  "electrical_requirements": {
    "incoming_supply": {
      "voltage_kv": 11,
      "phase": 3,
      "frequency_hz": 50,
      "variation_pct": "±5%",
      "normal_mva": 11,
      "max_mva": 23,
      "supply_system": "remote 11kV single subsea cable",
      "generator_mva": 25,
      "emergency_generator_kva": 2000
    },
    "black_start": {
      "startup_auxiliaries_from_emergency_switchboard": true
    },
    "transient_conditions": {
      "automatic_load_transfers": true,
      "load_shedding": "underfrequency relays on 11kV bus",
      "external_voltage_dips_restart_s": 2,
      "power_loss_detection": "no-volt relay <50% volts >2s"
    },
    "future_expansion": {
      "feeder_bus_spare_pct": 20,
      "transformer_spare_pct": 20
    }
  }
}
2.11 新增顶层字段组：pipelines（管线）🔵
来源：{BoD §12/§14}。油气田项目特有。

json
{
  "pipelines": {
    "offshore_pipelines": [
      {
        "name": null,
        "diameter_inch": null,
        "design_pressure": null,
        "design_code": null,
        "contents": null,
        "pigging_required": false,
        "pigging_purpose": null
      }
    ],
    "chemical_service_lines": [
      {"service": "MEG with corrosion inhibitor", "included": true},
      {"service": "LDHI", "included": true},
      {"service": "PPD", "included": true}
    ],
    "onshore_pipelines": [
      {"name": null, "route": null, "diameter_inch": null, "design_pressure": null}
    ]
  }
}
3. 与前四份文档的字段覆盖对比
字段组	1239	KAIMEN	浙石化	本模板
海上波浪数据	❌	❌	❌	✅
海流数据	❌	❌	❌	✅
海生物附着	❌	❌	❌	✅
疲劳波浪数据	❌	❌	❌	✅
安装条件	❌	❌	❌	✅
井口平台	❌	❌	❌	✅
井流物组成	❌	❌	❌	✅
虚拟组分	❌	❌	❌	✅
地层水	❌	❌	❌	✅
产品规格	❌	❌	❌	✅
可用性目标	❌	❌	❌	✅
备件理念	❌	❌	❌	✅
逃生救生	❌	❌	❌	✅
黑启动	❌	❌	❌	✅
海底管线	❌	❌	❌	✅
坐标系统	❌	❌	❌	✅
4. 版本历史
版本	日期	修改内容
V1.0	2026-08-29	初始版本（三份炼化/化工BEDD）
V1.1	2026-08-29	增补浙石化设计基础（SUP-001）
V1.2	2026-08-29	增补WorleyParsons海上油气田BoD模板（SUP-002），新增11个海上油气田特有字段组
增补完成。 PCS-DICT-004现覆盖炼化、化工、公用工程、海上油气田四大领域，含三份实际项目BEDD和一份国际工程公司标准模板共四份参考文件。BEDD字典的通用Schema结构保持不变，海上油气田特有字段以可选子结构添加，不影响既有项目类型使用。


