PCS-DICT-007 增补文件十一
文件标识	PCS-DICT-007-SUP-011
当前版本	V1.11
发布日期	2026-08-29
增补基准	PCS-DICT-007 V2.0 + SUP-007/008/009/010
新增参考	流量计工艺条件参数表（PR-W-IC/02，15个FE/FT）+ 调节阀工艺条件参数表（PR-W-IC/01，19个LV/FV/HV/TV/PV）+ HYSYS物流物性数据表（30物流完整物性）
1. 增补说明
1.1 新增素材价值
三份素材覆盖仪表批量委托+模拟物性输出两个领域：

维度	已有结构	本增补新增
流量计	❌ 无	✅ 15个FE/FT批量汇总（flowmeter_condition_table_json）
调节阀批量	SUP-010已有简化版	✅ 带阀前后压力的完整版（19阀）
HYSYS物流物性	DICT-005部分覆盖	✅ 30物流完整物性输出（stream_hysys_property_json）
1.2 HYSYS物性数据表特别说明
素材底部的物性数据表是模拟软件（HYSYS/Aspen Plus）的标准输出格式，每个物流（Name）包含：

总相物性（Vapour Fraction/Temp/Press/Mass Flow/Mass Density）

分相物性（Liquid Phase/Vapour Phase各自的流量/密度/粘度/Cp-Cv/Z/分子量）

热力学数据（Heat of Vapourization/Bubble Point Pressure）

这对应SIM模块（P3阶段）解析HYSYS输出的核心内容。

2. 流量计工艺条件参数表JSON结构（flowmeter_condition_table_json）
2.1 顶层结构
json
{
  "project_no": null,
  "doc_no": null,
  "rev": null,
  "flowmeters": [],
  "notes": []
}
2.2 单个流量计元素结构
json
{
  "instrument_no": "290-FE-10101",
  "service_location": null,
  "pid_no": "PR-02/101",
  "pipe_no": "100-P-101",
  "pipe_class": "2B5",
  "pipe_size_od_id_mm": "114.3/102.26",
  "pipe_material": "20#",
  "fluid_name": "混合C4",
  "fluid_state": "LIQUID",       // LIQUID/GAS/STEAM
  "flow_unit": "KG_H",           // KG_H/NM3_H/M3_H
  "flow": {"max": 22000, "normal": 20000, "min": 14000},
  "operating_pressure_mpag": 0.59,
  "operating_temp_c": 40,
  "operating_density_kg_m3": 550,
  "std_density_kg_nm3": null,
  "kinematic_viscosity_mm2_s": 0.246,
  "dynamic_viscosity_mpa_s": 0.135,
  "isentropic_exponent": null,          // 等熵指数（仅气体）
  "design_pressure_mpag": null,
  "design_temp_c": null,
  "max_allowable_pressure_loss_pa": 30000,
  "compressibility_factor": null,       // 压缩因数（仅高压气体）
  "relative_humidity_pct": null,
  "solid_content_pct": null,
  "saturated_vapor_pressure_mpag": null, // 饱和蒸汽压力
  "saturated_vapor_density_kg_m3": null, // 饱和蒸汽密度
  "remark": null
}
2.3 流量计类型说明
仪表前缀	类型	说明
FE	流量检测元件（孔板/文丘里/喷嘴等）	需要节流计算
FT	流量变送器	将元件信号转换为电信号
FQ	流量积算器	累计流量
3. 调节阀批量条件表（带阀前后压力）——补充SUP-010
3.1 与SUP-010的区别
字段	SUP-010（XMV开关阀）	本增补（LV/FV/HV/TV/PV调节阀）
阀前压力	inlet_pressure_mpag	✅ 相同
阀后压力	❌ 无	✅ outlet_pressure_mpag
最大关闭差压	max_shutoff_dp_mpag	✅ 相同
故障状态	OPEN/CLOSE/LOCK	FC/FO
介质相数	✅	✅
标准密度	✅	✅ 气体填
过热度	❌ 无	✅ superheat_c
饱和蒸汽压力/临界压力	✅	✅
汽化量%	✅	✅
允许噪声	✅	✅

3.2 补充字段定义（调节阀批量条件表完整版）
在SUP-010的cv_batch_condition_table_json基础上，调节阀（LV/FV/HV/TV/PV）增加以下字段：

字段名	类型	必填	单位	说明
outlet_pressure_mpag	float	❌	MPa(G)	阀后压力（开关阀通常为空）
max_shutoff_dp_mpag	float	✅	MPa(G)	最大关闭差压
fail_action	enum	✅	—	FC/FO（替代SUP-010的FailPosition）
superheat_c	float	❌	°C	过热度Δt（仅水蒸气）
saturated_vapor_pressure_mpag	float	❌	MPa(G)	饱和蒸汽压力
critical_pressure_mpag	float	❌	MPa(G)	临界压力
vaporization_pct	float	❌	%	汽化量
allowable_noise_dba	float	❌	dBA	允许噪声
3.3 完整示例（节选）
json
{
  "tag_number": "290-LV-10101",
  "pid_no": "PR-02/101",
  "pipe_no": "100-P-101",
  "pipe_class": "2B5",
  "pipe_size_od_id_mm": "114.3/102.26",
  "pipe_material": "20#",
  "fluid_name": "混合C4",
  "fluid_state": "LIQUID",
  "fluid_phase_count": 1,
  "flow_unit": "KG_H",
  "flow": {"max": 22000, "normal": 20000, "min": 14000},
  "inlet_pressure_mpag": 0.56,
  "outlet_pressure_mpag": 0.51,
  "operating_temp_c": 40,
  "operating_density_kg_m3": 550,
  "max_shutoff_dp_mpag": 0.90,
  "kinematic_viscosity_mm2_s": 0.246,
  "dynamic_viscosity_mpa_s": 0.135,
  "fail_action": "FC"
}
气体工况示例（含标准密度和等熵指数）：

json
{
  "tag_number": "290-HV-10101",
  "pid_no": "PR-02/101",
  "pipe_no": "100-FLG-102/1",
  "fluid_name": "混合C4",
  "fluid_state": "GAS",
  "fluid_phase_count": 1,
  "flow_unit": "NM3_H",
  "flow": {"max": 1727, "normal": 1570, "min": 1099},
  "inlet_pressure_mpag": 0.59,
  "outlet_pressure_mpag": 0.06,
  "operating_temp_c": 40,
  "std_density_kg_nm3": 2.63,
  "max_shutoff_dp_mpag": 0.83,
  "kinematic_viscosity_mm2_s": 0.692,
  "fail_action": "FC"
}
水蒸气工况示例（含过热度/饱和蒸汽压力）：

json
{
  "tag_number": "290-FV-10601",
  "pid_no": "PR-02/106",
  "pipe_no": "200-LS-115",
  "fluid_name": "蒸汽",
  "fluid_state": "GAS",
  "fluid_phase_count": 1,
  "flow_unit": "KG_H",
  "flow": {"max": 9679, "normal": 6452.56, "min": 4517},
  "inlet_pressure_mpag": 0.97,
  "outlet_pressure_mpag": 0.92,
  "operating_temp_c": 250,
  "operating_density_kg_m3": 4.21,
  "max_shutoff_dp_mpag": 1.00,
  "dynamic_viscosity_mpa_s": 0.018,
  "fail_action": "FC"
}
4. HYSYS物流物性数据表JSON结构（stream_hysys_property_json）
4.1 顶层结构
json
{
  "source": "HYSYS_EXPORT",       // 模拟软件来源
  "version": null,                // 软件版本
  "streams": [],                  // 物流数组
  "timestamp": null               // 导出时间
}
4.2 单个物流元素结构
json
{
  "name": "001",
  "vapor_fraction": 0.0,
  "temperature_c": 40.0,
  "pressure_mpag": 0.59,
  "mass_flow_kg_h": 20000.00,
  "mass_density_kg_m3": 549.8013,
  "liquid_phase": {
    "mass_flow_kg_h": 20000.00,
    "mass_density_kg_m3": 549.8013,
    "kinematic_viscosity_cst": 0.2460,
    "viscosity_cp": 0.1353,
    "cp_cv": 1.4581,
    "z_factor": 0.0275,
    "molecular_weight": 57.0565
  },
  "vapor_phase": {
    "mass_flow_kg_h": null,
    "mass_density_kg_m3": null,
    "kinematic_viscosity_cst": null,
    "viscosity_cp": null,
    "cp_cv": null,
    "z_factor": null,
    "molecular_weight": null
  },
  "heat_of_vaporization_kj_kgmole": 19060.445,
  "bubble_point_pressure_bar": 4.95
}
4.3 字段定义
字段名	类型	必填	单位	说明
name	string	✅	—	物流名称
vapor_fraction	float	✅	—	汽化分率（0~1）
temperature_c	float	✅	°C	温度
pressure_mpag	float	✅	MPa(g)	压力
mass_flow_kg_h	float	✅	kg/h	总质量流量
mass_density_kg_m3	float	✅	kg/m³	混合密度
liquid_phase.mass_flow_kg_h	float	❌	kg/h	液相质量流量（单相液体=总流量）
liquid_phase.mass_density_kg_m3	float	❌	kg/m³	液相密度
liquid_phase.kinematic_viscosity_cst	float	❌	cSt	液相运动粘度
liquid_phase.viscosity_cp	float	❌	cP	液相动力粘度
liquid_phase.cp_cv	float	❌	—	液相Cp/Cv
liquid_phase.z_factor	float	❌	—	液相压缩因子
liquid_phase.molecular_weight	float	❌	g/mol	液相分子量
vapor_phase.*	object	❌	—	气相物性（同liquid结构）
heat_of_vaporization_kj_kgmole	float	❌	kJ/kgmole	蒸发潜热
bubble_point_pressure_bar	float	❌	bar	泡点压力
4.4 与Streams表的映射
stream_hysys_property_json	streams表
name	stream_name
vapor_fraction	vapor_fraction
temperature_c	temp
pressure_mpag	press
mass_flow_kg_h	mass_flow
mass_density_kg_m3	density
liquid_phase.viscosity_cp	viscosity_dynamic
liquid_phase.kinematic_viscosity_cst	viscosity_kinematic
liquid_phase.molecular_weight	molecular_weight
liquid_phase.z_factor	compressibility_factor
vapor_phase.molecular_weight	气相组成相关
heat_of_vaporization_kj_kgmole	焓值相关
bubble_point_pressure_bar	泡点数据
5. 枚举定义
5.1 FailAction（调节阀故障状态）
枚举值	中文	说明
FC	失气关闭	Fail Close（调节阀标准）
FO	失气打开	Fail Open（调节阀标准）
与SUP-010的FailPosition（开关阀：OPEN/CLOSE/LOCK）区分，调节阀使用FailAction（FC/FO）。

5.2 FlowmeterType（流量计类型）
仪表前缀	中文	说明
FE	流量检测元件	孔板/文丘里/喷嘴/质量流量计传感部分
FT	流量变送器	将元件信号转换为标准信号
FQ	流量积算器	累计/记录流量
6. 与已有结构的映射
6.1 流量计与restriction_results的关系
restriction_results字段	flowmeter_condition_table_json字段
tag_number	instrument_no
restriction_type	由流量计类型确定（ORIFICE/VENTURI/NOZZLE）
bore_diameter	由计算得出
perm_pressure_drop	max_allowable_pressure_loss_pa / 1000
6.2 HYSYS物性与SIM模块的关系
SIM模块（P3）	stream_hysys_property_json
HYSYS解析器输入	本结构为解析输出格式
streams表写入	§4.4映射表
物性估算标记	当某物性为空时，调用COMMON估算
7. 版本历史
版本	日期	修改内容
V1.0~V1.7	2026-08-29	初始+容器+塔+球罐+阀门+起重机+透平+设计条件
V2.0	2026-08-29	完整整合版
V1.8	2026-08-29	增补仪表规格书（SUP-008）
V1.9	2026-08-29	增补计算+规格合并表（SUP-009）
V1.10	2026-08-29	增补批量控制阀工艺条件参数表（SUP-010，XMV开关阀）
V1.11	2026-08-29	增补流量计批量表（SUP-011）+调节阀批量表（带阀前后压力）+HYSYS物流物性输出格式
增补完成。 PCS-DICT-007 SUP-011完整覆盖：

结构	内容
flowmeter_condition_table_json	流量计批量工艺条件表（15个FE/FT实例）
cv_batch_condition_table_json（扩展）	调节阀批量表（19个LV/FV/HV/TV/PV实例，含阀前后压力）
stream_hysys_property_json	HYSYS物流物性输出格式（30物流完整物性+分相数据）
FailAction枚举	FC/FO（调节阀）
FlowmeterType枚举	FE/FT/FQ
PCS-DICT-007最终版本覆盖的CV/仪表文档格式全景：

文档格式	字典结构	来源
设计条件表	cv_design_condition_json	SUP-007
批量开关阀汇总	cv_batch_condition_table_json（简化）	SUP-010
批量调节阀汇总	cv_batch_condition_table_json（扩展）	SUP-011
批量流量计汇总	flowmeter_condition_table_json	SUP-011
计算+规格合并表	cv_calc_spec_json	SUP-009
仪表规格书	control_valve_spec_json	SUP-008
自力式调节阀	regulator_valve_spec_json	SUP-008
阀门数据表	valve_data_sheet_json	SUP-004
HYSYS物流物性	stream_hysys_property_json	SUP-011
P3阶段SIM模块的HYSYS解析器和P6阶段CV/RESTRICTION模块的批量数据表生成以此为准。
