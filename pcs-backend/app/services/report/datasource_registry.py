"""数据源注册表 —— REPORT_BUILDER 可选数据源的**纯元数据**。

SPEC §3.2.2(1) 列了 13 个数据源，这里逐条登记：数据源标识 → ORM 表 → 字段。

## 本文件只放元数据，不放任何查询逻辑

查询统一在 `query_engine`（Task 5b）。理由不是洁癖：JOIN 白名单
（SPEC §1.3）明确说「关联键必须在数据源注册表中预定义」—— 注册表是**声明**，
query_engine 是**执行**。两者混在一起时，「哪些字段可选」就会和「怎么查」
互相污染，改查询逻辑会碰到字段契约。

## 字段名的坑（实测）

SPEC 的字段名与 ORM 列**不是一一同名**。登记时必须核对真实列：

- `PIPING_RESULTS` → `piping_results`（83 列的线表），
  **不是** `pipe_network_results`（水力计算网络结果）。两表只差一个词，
  语义完全不同。
- `PUMP_RESULTS` 的 Flow / NPSHa / Power 在 JSONB 里（`flow_rates_json`、
  `suction_calculation_json`、`power_consumption_json`），不是独立列。
- `VESSEL_RESULTS` 的 Volume / Diameter / Length 同理在 `output_json` 三轨里。
- `HEAT_RESULTS` 的 OverallU 是列 `u_overall`。
- `DATALINEAGE` 用 `source_ref_type` / `source_ref_id`，不是 SPEC 写的
  `source_type` / `source_id`（`source` 列是字符串来源标记，不是类型）。

JSONB 子键用 `is_jsonb_key=True` 标注，键名写成 `容器列.子键`。
`test_registry_fields_exist_in_orm` 会核对容器列存在 —— 免得键名编错了没人发现。
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace

from app.services.exceptions import PcsError


@dataclass(frozen=True)
class FieldSpec:
    """一个可选字段。

    name 用**真实 ORM 列名**（JSONB 子键则 `容器列.子键`），不是 SPEC 的原始
    命名 —— 用户在字段树里看到的应该是能查得出的东西。
    """

    name: str
    type: str  # string | number | date | enum
    label: str
    is_jsonb_key: bool = False


@dataclass(frozen=True)
class DataSource:
    key: str
    label: str
    model: str  # ORM 表名
    fields: dict[str, FieldSpec] = field(default_factory=dict)


@dataclass(frozen=True)
class JoinRule:
    """一条**显式** JOIN 白名单（SPEC §1.3）。

    禁止按名称文本模糊 JOIN —— 那等于让用户能拼出任意笛卡尔积。
    """

    a: str
    a_field: str
    b: str
    b_field: str
    degrade_warn: str | None = None   # SPEC §1.3 第 5 对授权的降级说明


def _f(name: str, type_: str, label: str) -> FieldSpec:
    return FieldSpec(name=name, type=type_, label=label)


def _jf(container: str, key: str, type_: str, label: str) -> FieldSpec:
    return FieldSpec(name=f"{container}.{key}", type=type_, label=label,
                     is_jsonb_key=True)


# --- 13 个数据源（SPEC §3.2.2(1)，字段已逐条核对真实 ORM 列）----------------

DATASOURCES: dict[str, DataSource] = {
    "EQUIP_LIST": DataSource(
        key="EQUIP_LIST", label="设备表", model="equipment_list",
        fields={
            "type_code": _f("type_code", "string", "设备位号"),
            "tag_number": _f("tag_number", "string", "设备编号"),
            "equipment_description": _f("equipment_description", "string", "设备名称"),
            "vendor": _f("vendor", "string", "制造商"),
            "vendor_model": _f("vendor_model", "string", "制造商型号"),
            "equipment_status": _f("equipment_status", "string", "设备状态"),
            "design_parameters_json": _f("design_parameters_json", "string", "设计参数"),
            "actual_data_status": _f("actual_data_status", "string", "实测数据状态"),
        }),

    "PIPING_RESULTS": DataSource(
        key="PIPING_RESULTS", label="管道一览表", model="piping_results",
        fields={
            "line_no": _f("line_no", "string", "管线号"),
            "line_size": _f("line_size", "string", "公称直径"),
            "material_class": _f("material_class", "string", "材质等级"),
            "fluid_code": _f("fluid_code", "string", "流体代号"),
            "design_press": _f("design_press", "number", "设计压力"),
            "design_temp": _f("design_temp", "number", "设计温度"),
            "norm_oper_press": _f("norm_oper_press", "number", "常操作压力"),
        }),

    "STREAMS": DataSource(
        key="STREAMS", label="物流数据", model="streams",
        fields={
            "stream_name": _f("stream_name", "string", "物流名称"),
            "phase": _f("phase", "string", "相态"),
            "temp": _f("temp", "number", "温度"),
            "press": _f("press", "number", "压力"),
            "mass_flow": _f("mass_flow", "number", "质量流量"),
            "composition_json": _f("composition_json", "string", "组成"),
        }),

    "PSV_RESULTS": DataSource(
        key="PSV_RESULTS", label="安全阀结果", model="psv_results",
        fields={
            "tag_number": _f("tag_number", "string", "安全阀位号"),
            "set_pressure": _f("set_pressure", "number", "整定压力"),
            "relief_capacity": _f("relief_capacity", "number", "泄放能力"),
            "orifice_area": _f("orifice_area", "number", "喷嘴面积"),
        }),

    "PUMP_RESULTS": DataSource(
        key="PUMP_RESULTS", label="泵结果", model="pump_results",
        fields={
            "tag_number": _f("tag_number", "string", "泵位号"),
            # SPEC 写的是 Flow / NPSHa / Power，ORM 里是 JSONB 子键
            "flow_rates_json.flow_m3_s": _jf("flow_rates_json", "flow_m3_s",
                                              "number", "流量"),
            "flow_rates_json.head_m": _jf("flow_rates_json", "head_m",
                                          "number", "扬程"),
            "suction_calculation_json.npsha_m": _jf(
                "suction_calculation_json", "npsha_m", "number", "汽蚀余量 NPSHa"),
            "power_consumption_json.estimated_power_kw": _jf(
                "power_consumption_json", "estimated_power_kw", "number", "轴功率"),
            "actual_head": _f("actual_head", "number", "实测扬程"),
        }),

    "VESSEL_RESULTS": DataSource(
        key="VESSEL_RESULTS", label="容器结果", model="vessel_results",
        fields={
            "tag_number": _f("tag_number", "string", "容器位号"),
            # Volume/Diameter/Length 在 output_json 三轨里（sizing / hydraulics / sizing_spec）
            "output_json.sizing.liquid_volume_m3": _jf(
                "output_json", "sizing.liquid_volume_m3", "number", "容积"),
            "output_json.hydraulics.volume_m3": _jf(
                "output_json", "hydraulics.volume_m3", "number", "容器几何容积"),
            "output_json.hydraulics.diameter_m": _jf(
                "output_json", "hydraulics.diameter_m", "number", "直径"),
            "output_json.hydraulics.length_m": _jf(
                "output_json", "hydraulics.length_m", "number", "长度"),
            "residence_time_s": _f("residence_time_s", "number", "停留时间"),
        }),

    "HEAT_RESULTS": DataSource(
        key="HEAT_RESULTS", label="换热器结果", model="heat_results",
        fields={
            "equipment_no": _f("equipment_no", "string", "换热器位号"),
            # SPEC 写 OverallU，ORM 列名是 u_overall
            "duty": _f("duty", "number", "热负荷"),
            "effective_area": _f("effective_area", "number", "有效换热面积"),
            "u_overall": _f("u_overall", "number", "总传热系数"),
        }),

    "UTIL_RESULTS": DataSource(
        key="UTIL_RESULTS", label="能耗汇总", model="util_results",
        fields={
            "electrical_power_kwh_yr": _f("electrical_power_kwh_yr", "number",
                                         "年用电量"),
            "fuel_gas_consumption_nm3_yr": _f("fuel_gas_consumption_nm3_yr",
                                              "number", "年燃料气量"),
            "steam_consumption_t_yr": _f("steam_consumption_t_yr", "number",
                                         "年蒸汽量"),
            "cooling_water_consumption_t_yr": _f("cooling_water_consumption_t_yr",
                                                 "number", "年冷却水量"),
            "annual_total_energy": _f("annual_total_energy", "number", "年综合能耗"),
            # 综合能耗计算书（ENERGY_CALC_BOOK）要的标准煤折算量。
            # ⚠️ 这两列此前**漏登记**了 —— 是 collector 的字段闸发现的：
            # 它们在 ORM 上真实存在，只是注册表没声明，于是「综合能耗计算书」
            # 要的核心指标在字段树上根本选不到。
            "total_toe": _f("total_toe", "number", "年折标煤（tce）"),
            "total_standard_coal_kg": _f("total_standard_coal_kg", "number",
                                         "年标准煤（kg）"),
            "tolerance_status": _f("tolerance_status", "enum", "偏差状态"),
            "business_date": _f("business_date", "date", "统计日期"),
        }),

    "INPUT_CHECKLIST": DataSource(
        key="INPUT_CHECKLIST", label="输入清单", model="project_input_checklist",
        fields={
            "item_label": _f("item_label", "string", "输入项名称"),
            "module": _f("module", "string", "所属模块"),
            "status": _f("status", "enum", "状态"),
            "source_type": _f("source_type", "enum", "来源类型"),
        }),

    "DATALINEAGE": DataSource(
        key="DATALINEAGE", label="血缘关系", model="data_lineage",
        fields={
            # SPEC 写 source_type/source_id，实际列是 *_ref_*
            "record_type": _f("record_type", "string", "记录类型"),
            "record_id": _f("record_id", "string", "记录 ID"),
            "source": _f("source", "string", "来源"),
            "source_ref_type": _f("source_ref_type", "string", "来源类型"),
            "source_ref_id": _f("source_ref_id", "string", "来源 ID"),
            "change_summary": _f("change_summary", "string", "变更摘要"),
            "occurred_at": _f("occurred_at", "date", "发生时间"),
        }),

    "PROJECTS": DataSource(
        key="PROJECTS", label="项目信息", model="projects",
        fields={
            "project_no": _f("project_no", "string", "项目号"),
            "project_name": _f("project_name", "string", "项目名称"),
            "location": _f("location", "string", "地点"),
        }),

    "SUPPLIERS": DataSource(
        key="SUPPLIERS", label="供应商信息", model="suppliers",
        fields={
            "supplier_name": _f("supplier_name", "string", "供应商名称"),
            "supplier_type": _f("supplier_type", "string", "供应商类型"),
            "rating": _f("rating", "string", "资质等级"),
            "contact_json": _f("contact_json", "string", "联系方式"),
        }),

    "CONFIG_ASSETS": DataSource(
        key="CONFIG_ASSETS", label="配置资产", model="config_assets",
        fields={
            "asset_id": _f("asset_id", "string", "资产 ID"),
            "category": _f("category", "enum", "类别"),
            "name": _f("name", "string", "名称"),
            "current_version": _f("current_version", "string", "当前版本"),
            "status": _f("status", "enum", "状态"),
        }),
}


# --- JOIN 白名单（SPEC §1.3，P8-OPEN-005 关闭决议；多一条都不行）-------------

JOINS: tuple[JoinRule, ...] = (
    JoinRule("EQUIP_LIST", "tag_number", "PUMP_RESULTS", "tag_number"),
    JoinRule("EQUIP_LIST", "tag_number", "VESSEL_RESULTS", "tag_number"),
    JoinRule("EQUIP_LIST", "tag_number", "HEAT_RESULTS", "tag_number"),
    JoinRule("EQUIP_LIST", "tag_number", "PSV_RESULTS", "tag_number"),
    # SPEC 原文：equipment_list 无 vendor_id，降级为按名称关联（WARN 级提示）。
    # 已核实 equipment_list 确实没有 vendor_id，suppliers 也没有 vendor_id。
    JoinRule("EQUIP_LIST", "vendor", "SUPPLIERS", "supplier_name",
             degrade_warn="equipment_list 无 vendor_id 列，按供应商名称降级关联"),
)

_JOIN_INDEX: dict[frozenset[str], JoinRule] = {
    frozenset((j.a, j.b)): j for j in JOINS
}


def join_key_for(a: str, b: str) -> tuple[str, str]:
    """返回 `(a 侧键, b 侧键)`；**顺序对称** —— 调用方不该关心谁在前。

    不在白名单内抛 `REPORT_BUILDER_JOIN_NOT_SUPPORTED`（400），
    而不是静默按同名列关联 —— SPEC §1.3 明确禁止名称模糊 JOIN。
    """
    rule = _JOIN_INDEX.get(frozenset((a, b)))
    if rule is None:
        raise PcsError(
            f"不支持的数据源关联：{a} ↔ {b}。"
            f"仅开放 {len(JOINS)} 对白名单（SPEC §1.3）。",
            code="REPORT_BUILDER_JOIN_NOT_SUPPORTED", status=400,
        )
    if a == rule.a:
        return rule.a_field, rule.b_field
    return rule.b_field, rule.a_field

def primary_key_field(source: str) -> str:
    """数据源对应 ORM 表的**主键列名**。

    ⚠️ 不是「第一个声明的字段」—— `record_ids` 装的是主键，
    拿业务列去比会恒为空集（第一版 `collect()` 就这么错的：
    表头渲染出来了但一行数据都没有）。
    """
    from app.db.base import Base

    ds = DATASOURCES.get(source)
    if ds is None:
        raise PcsError(f"未知数据源：{source}",
                       code="REPORT_DATASOURCE_UNKNOWN", status=400)
    for mapper in Base.registry.mappers:
        if mapper.local_table is not None and mapper.local_table.name == ds.model:
            return list(mapper.primary_key)[0].name
    raise PcsError(f"数据源 {source} 的表 {ds.model} 未注册到 ORM",
                   code="REPORT_DATASOURCE_UNKNOWN", status=400)


def _add_primary_keys() -> None:
    """把每个数据源的**主键列**登记为可引用字段。

    为什么必须登记：`query_engine._column` 只接受注册表里的字段（那道闸是
    bug-155 之后防止「registry 与 ORM 漂移」的），而 `collect()` 的
    `IN` 过滤器正是按主键过滤 `record_ids`。

    ⚠️ 早先没登记时报的是
    `字段 EQUIP_LIST.'equipment_id' 不在数据源注册表中` —— 主键是 ORM 上
    真实存在的列，却因为没登记而不可引用。

    用循环而不是逐个手写：13 个数据源手写必然漏，且加新源时又是一次人为
    陷阱。循环保证「主键一定在字段表里」这条不变式。
    """
    from app.db.base import Base

    for key, ds in DATASOURCES.items():
        pk_name = None
        for mapper in Base.registry.mappers:
            lt = mapper.local_table
            if lt is not None and lt.name == ds.model:
                pk_name = list(mapper.primary_key)[0].name
                break
        if pk_name is None or pk_name in ds.fields:
            continue
        DATASOURCES[key] = replace(
            ds, fields={pk_name: FieldSpec(name=pk_name, type="string",
                                            label=f"{ds.label}记录号"),
                        **ds.fields})


_add_primary_keys()

def _add_project_columns() -> None:
    """把每个**有** `project_id` 列的数据源的该列登记为可查询字段。

    为什么必须登记：执行引擎的**项目隔离条件**就靠它（`builder_service
    ._project_field`）。不登记的话 `apply_filters` 会以「字段不在注册表」
    把每一次执行都拒掉 —— 项目隔离是安全边界，不能是「表上有就顺带加上」。

    用循环而非逐个手写：13 个源手写必然漏，而漏掉的那个源会**执行不了**
    （不是执行得不对，是根本跑不起来，用户只看到一个莫名其妙的 400）。
    """
    from app.db.base import Base

    for key, ds in DATASOURCES.items():
        if "project_id" in ds.fields:
            continue
        for mapper in Base.registry.mappers:
            lt = mapper.local_table
            if lt is not None and lt.name == ds.model and "project_id" in lt.columns:
                DATASOURCES[key] = replace(
                    ds, fields={"project_id": FieldSpec(
                        name="project_id", type="string", label="项目 ID"),
                        **ds.fields})
                break


_add_project_columns()
