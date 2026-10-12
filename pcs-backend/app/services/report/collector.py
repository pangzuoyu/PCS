"""10 类报表的**声明**（SPEC §3.2.1(2)）。

每个 report_type 只声明三件事：**查哪些源、选哪些字段、允许哪些输出格式**。
实际取数与渲染一律不碰 —— 取数是 `query_engine` 的唯一实现（用户
2026-10-09 裁决），渲染是三个 renderer 各自的事。

## 为什么单独一层

15 个操作符、JOIN 白名单、NULL 处理若在 collector 与 REPORT_BUILDER 的
builder_service 各写一遍，两处语义必然漂移。collector 是**声明**，
query_engine 是**执行**；两者混在一起时，「哪些字段可选」会和「怎么查」
互相污染 —— 改查询逻辑会碰到字段契约。

## 字段名一律用注册表里的真名

SPEC 的字段名与 ORM 在 6 处不一致（见 `datasource_registry` 模块 docstring）。
本模块抄的是**注册表里的真名**，不是 SPEC 的原始命名 —— 用户在 UI 里看到的
应该是能查得出的东西。`test_declared_fields_exist_in_registry` 守着这条。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.services.exceptions import PcsError


@dataclass(frozen=True)
class ReportSpec:
    """一个 report_type 的声明。"""

    key: str
    label: str
    formats: str                      # SPEC 的「输出格式」列原文
    primary: str                      # 主源（结果行数由它决定）
    fields: dict[str, list[str]] = field(default_factory=dict)  # 源 -> 字段

    @property
    def sources(self) -> list[str]:
        """全部数据源（主源在前）。多源组装按主源展开（ADR-P8-004 裁决）。"""
        return [self.primary] + [s for s in self.fields if s != self.primary]

    @property
    def extra_sources(self) -> list[str]:
        """除主源外的源 —— 需要按 JOIN 白名单做 Python 组装的那部分。"""
        return [s for s in self.sources if s != self.primary]


REPORT_SPECS: dict[str, ReportSpec] = {
    "PIPING_CALC_BOOK": ReportSpec(
        key="PIPING_CALC_BOOK", label="管道计算书", formats="DOCX/PDF",
        primary="PIPING_RESULTS",
        fields={"PIPING_RESULTS": ["line_no", "line_size", "material_class",
                                   "fluid_code", "design_press", "design_temp"]}),

    "PUMP_DATA_TABLE": ReportSpec(
        key="PUMP_DATA_TABLE", label="泵数据表", formats="DOCX/XLSX/PDF",
        primary="PUMP_RESULTS",
        fields={"PUMP_RESULTS": ["tag_number", "flow_rates_json.flow_m3_s",
                                 "flow_rates_json.head_m",
                                 "suction_calculation_json.npsha_m",
                                 "power_consumption_json.estimated_power_kw"]}),

    "PSV_DATA_TABLE": ReportSpec(
        key="PSV_DATA_TABLE", label="安全阀数据表", formats="DOCX/PDF",
        primary="PSV_RESULTS",
        fields={"PSV_RESULTS": ["tag_number", "set_pressure",
                                "relief_capacity", "orifice_area"]}),

    "VESSEL_DATA_TABLE": ReportSpec(
        key="VESSEL_DATA_TABLE", label="容器数据表", formats="DOCX/PDF",
        primary="VESSEL_RESULTS",
        fields={"VESSEL_RESULTS": ["tag_number",
                                   "output_json.sizing.liquid_volume_m3",
                                   "output_json.hydraulics.diameter_m",
                                   "output_json.hydraulics.length_m",
                                   "residence_time_s"]}),

    "HEAT_SPEC": ReportSpec(
        key="HEAT_SPEC", label="换热器规格书", formats="DOCX/PDF",
        primary="HEAT_RESULTS",
        fields={"HEAT_RESULTS": ["equipment_no", "duty", "effective_area",
                                 "u_overall"]}),

    "EQUIPMENT_LIST": ReportSpec(
        key="EQUIPMENT_LIST", label="设备一览表", formats="XLSX",
        primary="EQUIP_LIST",
        fields={"EQUIP_LIST": ["type_code", "tag_number", "equipment_description",
                               "vendor", "vendor_model", "equipment_status"]}),

    "UTILITY_BALANCE": ReportSpec(
        key="UTILITY_BALANCE", label="公用工程平衡表", formats="XLSX",
        primary="UTIL_RESULTS",
        fields={"UTIL_RESULTS": ["business_date", "electrical_power_kwh_yr",
                                 "fuel_gas_consumption_nm3_yr",
                                 "steam_consumption_t_yr", "annual_total_energy"]}),

    # SPEC 写「UTIL + GB/T 50441」—— GB/T 50441 是计算标准不是一张表，
    # 本仓落地为单一 UTIL_RESULTS 源；标准符合性由引擎侧保证，不在字段层体现。
    "ENERGY_CALC_BOOK": ReportSpec(
        key="ENERGY_CALC_BOOK", label="综合能耗计算书", formats="DOCX/PDF",
        primary="UTIL_RESULTS",
        fields={"UTIL_RESULTS": ["business_date", "annual_total_energy",
                                 "total_toe", "total_standard_coal_kg"]}),

    # SPEC 写「各模块汇总」—— 本仓先落地为 UTIL_RESULTS；
    # 接入电力/水/气各模块的汇总表是后续扩展点（dataviz/TODO），
    # 届时本项 sources 增加即可，query_engine 的批量组装逻辑不用动。
    "ENTRUST_CONDITION": ReportSpec(
        key="ENTRUST_CONDITION", label="委托条件表", formats="XLSX",
        primary="UTIL_RESULTS",
        fields={"UTIL_RESULTS": ["business_date", "electrical_power_kwh_yr",
                                 "steam_consumption_t_yr"]}),

    "PIPING_LIST": ReportSpec(
        key="PIPING_LIST", label="管道一览表", formats="XLSX",
        primary="PIPING_RESULTS",
        fields={"PIPING_RESULTS": ["line_no", "line_size", "material_class",
                                   "fluid_code", "norm_oper_press"]}),
}

REPORT_TYPES: frozenset[str] = frozenset(REPORT_SPECS)


def collector_for(report_type: str) -> ReportSpec:
    """取某个 report_type 的声明。**未知类型显式报错**，不静默降级到默认表 ——
    降级会让用户拿到一份「看起来正常但不是他要的」报表。"""
    spec = REPORT_SPECS.get(report_type)
    if spec is None:
        raise PcsError(
            message=f"未知报表类型：{report_type!r}。支持 {sorted(REPORT_TYPES)}",
            code="REPORT_TYPE_UNKNOWN", status=400)
    return spec


__all__ = ["REPORT_SPECS", "REPORT_TYPES", "ReportSpec", "collector_for"]