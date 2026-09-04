PCS-DICT-011：离心泵计算数据字典（V1.1更新版）
文件标识	PCS-DICT-011
当前版本	V1.1
发布日期	2026-09-01
关联文档	PCS-DICT-ALL-003 V3.3（表18 pump_results）、SPEC-P4 §3.2.4、PCS-REQ-2026-DF-001（数据流架构规范）
数据来源	离心泵计算表实例（1169-20-B-35A，FLASH COLUMN BASE PUMP）
本版变更	增加压降引用/物性估算标记/依赖记录（DF-001 §6.2落地）
1. 目的
定义pump_results表完整JSON结构，覆盖离心泵计算全链路（工况定义→吸入侧→排出侧→差压→设计压力→功率→控制阀→等效长度→选型校核）。本版增加上游数据引用字段，确保PUMP不重复计算压降和物性。

2. pump_results完整JSON结构
2.1 顶层结构
json
{
  "general": {},
  "fluid_properties": {},
  "flow_rates": {},
  "dependencies": {},
  "suction_calculation": {},
  "discharge_calculation": {},
  "differential_pressure": {},
  "design_pressure": {},
  "power_consumption": {},
  "control_valve": {},
  "equivalent_length": {},
  "pressure_drop_details": {},
  "line_references": {},
  "vendor_data": {},
  "performance_curve": {},
  "seal_bearing": {},
  "instrumentation": {},
  "test_inspection": {},
  "remarks": []
}
2.2 general（概况）
字段名	类型	必填	说明
service	string	✅	泵服务描述（如"FLASH COLUMN BASE PUMP"）
item_no	string	✅	设备项目编号（如"TX-G-35"）
tag_no	string	✅	泵位号（如"TF-D-35"）
suction_vessel_tag	string	✅	吸入容器位号（如"TX-DC-35"）
design_date	string	❌	设计日期
project_no	string	✅	项目号（如"1169"）
sheet_no	string	❌	计算表编号（如"30"）
demen_case	bool	✅	是否为最小工况核算（Y/N）
suction_loop_no	int	✅	吸入侧环路号
discharge_loop_no	int	✅	排出侧环路号
revision_history	array	❌	修订历史
revision_history子结构：

json
[
  {"rev": "0", "date": null, "description": null, "by": null, "approved_by": null}
]
2.3 fluid_properties（介质物性）
字段名	类型	必填	单位	说明	变更
fluid_name	string	✅	—	介质名称	
operating_temp_c	float	✅	°C	操作温度	
density_kg_m3	float	✅	kg/m³	操作密度	
vapor_pressure_kg_cm2a	float	✅	kg/cm²(A)	操作温度下蒸气压	
viscosity_cp	float	✅	cP	操作粘度	
is_estimated	bool	✅	—	物性是否为FLASH估算（false=从streams直接读取）	V1.1新增
corrosiveness	string	❌	—	腐蚀性	
h2s_ppm	float	❌	ppm	H₂S含量（抗硫选材）	
chloride_ppm	float	❌	ppm	氯化物含量（抗氯选材）	
solid_content_pct	float	❌	%	固体含量（耐磨选型）	
约束（DF-001）：PUMP不计算物性。fluid_properties全部值从streams读取。若streams中物性为NULL，由FLASH补充写回streams（标记estimated）后，PUMP再读取。此处is_estimated是快照标记。

2.4 flow_rates（流量）
字段名	类型	必填	单位	说明
normal_qn_m3h	float	✅	m³/h	正常流量
minimum_qmin_m3h	float	✅	m³/h	最小流量
design_qd_m3h	float	✅	m³/h	设计流量
ratio_qn_qd	float	❌	—	正常/设计比
ratio_qmin_qd	float	❌	—	最小/设计比（最小回流保护校核）
2.5 dependencies（依赖记录）【V1.1新增】

字段名	类型	必填	说明
`stream_id`	UUID	❌	FK→streams.stream_id（物性来源）；DRAFT 可为 NULL
`stream_name`	string	❌	物流名称快照；写入时由 app 层从 streams lazy load
`suction_pipe_id`	UUID	❌	FK→piping_results.pipe_id；管道未计算时为 NULL
`discharge_pipe_id`	UUID	❌	同上
`all_checked`	bool	❌	**派生字段**：状态机提交 CHECKED 前由 app 层计算写入

**约束**：
- **DRAFT 阶段**：所有字段可为 NULL，表示依赖尚未建立
- **提交 CHECKED 时**：`stream_id` / `suction_pipe_id` / `discharge_pipe_id` 必须已填充
- **`all_checked`** 由状态机守卫在 `SUBMIT_FOR_CHECK` 转移前自动计算

### 2.5.1 dependencies FK 完整性策略【V1.1新增】

**问题**：PostgreSQL 无法对 JSONB 内的 UUID 加外键约束。`dependencies_json` 中引用的 `stream_id` / `suction_pipe_id` / `discharge_pipe_id` 不受 DB 级 FK 保护。

**策略**：应用层校验（三层）。

层	时机	校验内容
Service 写入时	P4 计算函数写 dependencies_json	SELECT 验证 stream_id / pipe_id 存在；不存在 → PcsError
状态机提交时	SUBMIT_FOR_CHECK 转移守卫	检查 all_checked；若 false → 拒绝提交
CIA 扫描时	1 分钟增量 + 5 分钟全量	比对 source_record_hash；同时校验引用记录仍存在

**孤儿 UUID 处理**：
- 若上游记录被物理删除（P1 工作区清理），依赖它的 `dependencies_json` 中的 UUID 变为孤儿引用
- CIA 扫描检测到孤儿 → 标记下游记录 STALE → 用户 confirm-recalc 时应用层重新验证并报错

**all_checked 派生规则**：

```
all_checked = (
    stream_id IS NOT NULL
    AND suction_pipe_id IS NOT NULL
    AND discharge_pipe_id IS NOT NULL
    AND 所有引用的上游记录 sign_status == CHECKED
)
```

2.6 suction_calculation（吸入侧计算）
字段名	类型	必填	单位	说明
suction_vessel_pressure_ps_kg_cm2a	float	✅	kg/cm²(A)	吸入容器操作压力
min_liquid_level_h1_m	float	✅	m	最低液位距地面
pump_axis_height_h2_m	float	✅	m	泵轴高度距地面
total_suction_pressure_drop_kg_cm2	float	✅	kg/cm²	吸入侧总压降（从PipingResults引用）
min_suction_liquid_head_m	float	✅	m	最小吸入液体压头（H1-H2-ΔP）
min_absolute_suction_pressure_kg_cm2a	float	✅	kg/cm²(A)	最小绝对吸入压力
available_npsh_m	float	✅	m	有效汽蚀余量
npsha_margin_m	float	✅	m	NPSHa裕量
required_npsh_m	float	❌	m	必需汽蚀余量（供应商数据）
npsha_npshr_ratio	float	❌	—	NPSHa/NPSHr比值
V1.1约束：total_suction_pressure_drop_kg_cm2和total_discharge_pressure_drop_kg_cm2的值必须与引用的PipingResults中压降一致。若管道未计算而使用了估算值，dependencies.suction_pipe_id应为NULL且is_estimated=true。

2.7 discharge_calculation（排出侧计算）
字段名	类型	必填	单位	说明
discharge_vessel_pressure_pd_kg_cm2a	float	✅	kg/cm²(A)	排出容器/界区压力
static_head_above_pump_axis_m	float	✅	m	静压头
total_discharge_pressure_drop_kg_cm2	float	✅	kg/cm²	排出侧总摩擦压降（从PipingResults引用）
discharge_pressure_kg_cm2a	float	✅	kg/cm²(A)	排出压力
pressure_at_battery_limit_kg_cm2	float	❌	kg/cm²	界区压力
2.8 differential_pressure（压差计算）
字段名	类型	必填	单位	说明
differential_pressure_qd_kg_cm2	float	✅	kg/cm²	设计流量下差压
selected_differential_head_m	float	✅	m	选定差压扬程
estimated_dp_qn_kg_cm2	float	✅	kg/cm²	正常流量下估算差压
dhmin_factor	float	✅	—	最小差压系数
shutoff_head_m	float	❌	m	关闭扬程（按泵曲线估算）
shutoff_pressure_kg_cm2a	float	❌	kg/cm²(A)	关闭压力
2.9 design_pressure（设计压力估算）
字段名	类型	必填	单位	说明
max_suction_level_m	float	✅	m	最高吸入液位
suction_vessel_design_pressure_kg_cm2a	float	✅	kg/cm²(A)	吸入容器设计压力
max_suction_pressure_kg_cm2a	float	✅	kg/cm²(A)	最大吸入压力
percent_differential_head_pct	float	✅	%	差压扬程百分比
pump_design_pressure_kg_cm2a	float	✅	kg/cm²(A)	泵设计压力
2.10 power_consumption（功率估算）
字段名	类型	必填	单位	说明
pump_efficiency_pct	float	✅	%	泵效率
bhp_kw	float	✅	kW	轴功率
motor_efficiency_pct	float	✅	%	电机效率
absorbed_power_kw	float	✅	kW	吸收功率
specific_steam_consumption_kg_hr_kw	float	❌	kg/hr/kW	蒸汽比耗（透平驱动时）
estimated_steam_consumption_kg_hr	float	❌	kg/hr	估算蒸汽消耗
min_flow_thermal_kw	float	❌	kW	最小热控流量对应功率
motor_margin_pct	float	❌	%	电机功率裕量
2.11 control_valve（控制阀定义）
字段名	类型	必填	单位	说明
design_flow_rate_m3h	float	✅	m³/h	设计流量
normal_flow_rate_m3h	float	✅	m³/h	正常流量
min_flow_rate_m3h	float	✅	m³/h	最小流量
pump_dp_design_kg_cm2	float	✅	kg/cm²	泵差压设计
pump_dp_normal_kg_cm2	float	✅	kg/cm²	泵差压正常
pump_dp_min_kg_cm2	float	✅	kg/cm²	泵差压最小
friction_dp_total_kg_cm2	float	✅	kg/cm²	总摩擦压降
cv_dp_final	object	✅	kg/cm²	{design, normal, min}
min_cv_dp_kg_cm2	float	❌	kg/cm²	最小Cv对应压降
cv_dp_final子结构：

json
{
  "design": 2.20,
  "normal": 3.17,
  "min": 3.30
}
2.12 equivalent_length（等效长度）
字段名	类型	必填	说明
suction_nominal_diameter_inch	float	✅	吸入侧公称管径
discharge_nominal_diameter_inch	float	✅	排出侧公称管径
suction_equivalent_length_total_m	float	❌	吸入侧总等效长度
discharge_equivalent_length_total_m	float	❌	排出侧总等效长度
fittings	array	✅	管件明细
fittings子结构：

json
[
  {"fitting_type": "TUBE", "side": "SUCTION", "count": 11, "eq_length_m": 64},
  {"fitting_type": "BENDS", "side": "SUCTION", "count": 4, "eq_length_m": 6},
  {"fitting_type": "VALVES", "side": "SUCTION", "count": 1, "eq_length_m": 8},
  {"fitting_type": "TEE", "side": "SUCTION", "count": 3, "eq_length_m": 10},
  {"fitting_type": "REDUCER", "side": "SUCTION", "count": 1, "eq_length_m": 7},
  {"fitting_type": "CHECK_VALVE", "side": "DISCHARGE", "count": 1, "eq_length_m": 0}
]
2.13 pressure_drop_details（压降明细）
字段名	类型	必填	单位	说明
suction_strainer_dp_kg_cm2	float	❌	kg/cm²	吸入过滤器压降
discharge_exchanger_dp_kg_cm2	float	❌	kg/cm²	换热器压降
discharge_heater_dp_kg_cm2	float	❌	kg/cm²	加热器压降
discharge_reactor_dp_kg_cm2	float	❌	kg/cm²	反应器压降
discharge_orifice_dp_kg_cm2	float	❌	kg/cm²	孔板压降
discharge_misc_dp_kg_cm2	float	❌	kg/cm²	其他压降
suction_total_dp	object	✅	kg/cm²	{design, normal, min}
discharge_total_friction_dpd	object	✅	kg/cm²	{design, normal, min}
discharge_total_with_cv	float	✅	kg/cm²	含控制阀总压降
2.14 line_references（管线引用）【V1.1更新】
字段名	类型	必填	说明	变更
suction_line_no	string	✅	吸入管线号	
discharge_line_no	string	✅	排出管线号	
suction_vessel_tag	string	✅	吸入容器位号	
discharge_vessel_tag	string	❌	排出容器/界区位号	
suction_pipe_record_id	UUID nullable	❌	FK→piping_results.pipe_id（吸入侧压降来源）	V1.1新增
discharge_pipe_record_id	UUID nullable	❌	FK→piping_results.pipe_id（排出侧压降来源）	V1.1新增
is_pressure_drop_estimated	bool	✅	压降为估算而非引用时为true	V1.1新增
V1.1约束：当管道尚未计算（suction_pipe_record_id/discharge_pipe_record_id为NULL）时，is_pressure_drop_estimated=true，且计算记录不可提交CHECKED（状态机守卫检查依赖完整）。

3. 补充内容（供应商选型+校核）
3.1 vendor_data（供应商选型数据）
字段名	类型	单位	说明
pump_model	string	—	泵型号
pump_manufacturer	string	—	制造商
pump_type	enum	—	泵型（OH1/OH2/BB1/BB2等，按API 610）
impeller_diameter_mm	float	mm	叶轮直径（额定/最大）
impeller_type	enum	—	叶轮型式
no_stages	int	—	级数
speed_rpm	float	rpm	转速
specific_speed_ns	float	—	比转速
suction_specific_speed_nss	float	—	吸入比转速
seal_type	enum	—	密封类型
seal_plan	enum	—	冲洗方案
bearing_type	string	—	轴承型式
lubrication	enum	—	润滑方式
coupling_type	string	—	联轴器型式
motor_model	string	—	电机型号
motor_power_kw	float	kW	电机额定功率
motor_frame	string	—	电机机座号
motor_explosion_proof	string	—	防爆等级
motor_protection	string	—	防护等级
motor_insulation	string	—	绝缘等级
estimated_weight_kg	float	kg	估算重量
3.2 performance_curve（性能曲线数据）
json
{
  "curve_points": [
    {
      "flow_m3h": 0.0,
      "head_m": null,
      "efficiency_pct": 0,
      "npshr_m": null,
      "power_kw": null
    }
  ],
  "min_continuous_flow_m3h": null,
  "thermal_min_flow_m3h": null,
  "preferred_operating_region": {"from_m3h": null, "to_m3h": null},
  "allowable_operating_region": {"from_m3h": null, "to_m3h": null},
  "shutoff_head_m": null,
  "rated_flow_m3h": null,
  "rated_head_m": null,
  "rated_power_kw": null
}
3.3 seal_bearing（密封与轴承）
字段名	类型	说明
seal_type	enum	SINGLE_MECHANICAL/DOUBLE_MECHANICAL/TANDEM/PACKING/MAGNETIC
seal_plan	enum	PLAN_11/PLAN_21/PLAN_23/PLAN_32/PLAN_52/PLAN_53A/PLAN_53B/PLAN_54
seal_flush_fluid	string	冲洗液名称
seal_flush_flow_m3h	float	冲洗液流量
bearing_radial	string	径向轴承型式
bearing_thrust	string	止推轴承型式
lubrication_method	enum	GREASE/OIL_BATH/PURE_OIL_MIST/PURGE_OIL_MIST/PRESSURE_LUBE
oil_viscosity_iso	int	ISO粘度等级
oil_heater_required	bool	是否需要油加热器
3.4 instrumentation（仪表）
字段名	类型	说明
suction_pressure_gauge	bool	吸入侧压力表
discharge_pressure_gauge	bool	排出侧压力表
suction_pressure_transmitter	bool	吸入压力变送器
discharge_pressure_transmitter	bool	排出压力变送器
bearing_temp_sensor	bool	轴承温度传感器
vibration_sensor	bool	振动传感器
vibration_switch	bool	振动开关
seal_leak_detector	bool	密封泄漏检测
3.5 test_inspection（试验与检验）
字段名	类型	说明
hydrostatic_test	bool	水压试验
performance_test	bool	性能试验
npsh_test	bool	NPSH试验
vibration_test	bool	振动试验
noise_test	bool	噪声试验
balance_test	bool	动平衡试验
material_certificates	bool	材料证书
inspection_std	string	检验标准
4. 计算公式汇总
计算项	公式
有效汽蚀余量NPSHa	NPSHa = (Ps - Pv)×10.2/ρ + H1 - H2 - ΔPfriction
最小吸入液体压头	Hmin = H1 - H2 - ΔP
排出压力	Pd_total = Pvessel + ρ×g×(Hstatic)/10.197 + ΔPfriction
差压	ΔP = Pd_total - Ps_abs
轴功率BHP	BHP = Q×H×ρ/(102×η_pump)
吸收功率	P_absorbed = BHP/η_motor
泵设计压力	P_design = P_suction_max + 1.25×ΔP
比转速Ns	Ns = n×√Q / H^(3/4)
吸入比转速Nss	Nss = n×√Q / NPSHr^(3/4)
最小连续热控流量	Qthermal = 3600×P/(ρ×Cp×ΔT)
5. 与PumpResults DB列的映射

| pump_results DB 列 | JSON 结构路径 | 类型 |
|---|---|---|
| `tag_number` | `general.tag_no` | String(50)（真·平铺列） |
| `basic_info_json` | `general` | JSONB |
| `fluid_properties_json` | `fluid_properties` | JSONB |
| `flow_rates_json` | `flow_rates` | JSONB |
| `dependencies_json` | `dependencies` | JSONB |
| `suction_calculation_json` | `suction_calculation` | JSONB |
| `discharge_calculation_json` | `discharge_calculation` | JSONB |
| `differential_pressure_json` | `differential_pressure` | JSONB |
| `design_pressure_json` | `design_pressure` | JSONB |
| `power_consumption_json` | `power_consumption` | JSONB |
| `control_valve_json` | `control_valve` | JSONB |
| `equivalent_length_json` | `equivalent_length` | JSONB |
| `pressure_drop_details_json` | `pressure_drop_details` | JSONB |
| `line_references_json` | `line_references` | JSONB |
| `performance_curve_json` | `performance_curve` | JSONB |
| `seal_bearing_json` | `seal_bearing` | JSONB |
| `instrumentation_json` | `instrumentation` | JSONB |
| `test_inspection_json` | `test_inspection` | JSONB |
| `remark` | `remarks`（文本数组连接） | Text |
| `vendor_data_json` | `vendor_data` | JSONB |

**actual_* 归属说明**：

`equipment_list` 的 `actual_head` / `actual_efficiency` / `actual_motor_power` / `actual_npshr` / `vendor_model` / `actual_data_confirmed` 独立列
对应 `vendor_data` JSON 内：
- `actual_head` → `vendor_data.actual_head_m`
- `actual_efficiency` → `vendor_data.actual_efficiency_pct`
- `actual_motor_power` → `vendor_data.actual_motor_power_kw`
- `actual_npshr` → `vendor_data.actual_npshr_m`
- `vendor_model` → `vendor_data.vendor_model`
- `actual_data_confirmed` → `vendor_data.actual_data_confirmed`

> **PUMP 模型列数预期**：18 个 JSONB 列 + 1 个 `remark` Text 列 + 1 个 `tag_number` 平铺列 + 8 个 Mixin 列（sign_status / record_hash / approval_* / created_* / updated_* / created_by / project_id / workspace_id 等）≈ 28 列。
6. 版本历史
版本	日期	修改内容
V1.0	2026-09-01	初始版本，整合计算表实例+补充5模块
V1.1	2026-09-01	增加dependencies子结构 + fluid_properties.is_estimated + line_references管道引用字段（DF-001落地）
PCS-DICT-011 V1.1完。 P4 PUMP模块开发严格以此为准。核心变更：通过dependencies和line_references显式引用上游数据，确保PUMP不重复计算压降和物性。
