"""HeatResultsService 落库（P5-4-2 / Task 20）。

按 PCS-PLAN-P5-DEVICE-EQUIPMENT.md Task 20 + ADR-0027 V1.0 决策 5 + SUP-009 §3.1：

- 39 新标量 + 9 旧 + 3 新 JSONB 平铺字段写入 `heat_results` 表
- DICT V3.7 §3.1.1-3.1.6 字段名映射（与 SUP-009 §3.1 锁定对齐）
- `duty` 共享：9 旧 P4 上游值与 SUP-009 P5 计算结果合并为 1 列
- `map_htri_to_heat_input` 把 HtriParsedData 映射为 HeatCalcInput（与 Task 19 衔接）

不并发锁（与 PSV / vessel 一致）；不写派生表；不入 equipment_list。
"""
from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any, ClassVar

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.calc import HeatResult
from app.services.heat.htri_parser import HtriParsedData

# P5-4-2 formula_version：固定锚点（CIA 引擎版本对齐时一并 bump）
_FORMULA_VERSION = "HTv1.0-p5-4-2"


# ===== DTO =====


@dataclass
class HeatCalcInput:
    """换热器计算输入（39 新 + 9 旧 + 3 新 JSONB + 5 旧 JSONB 兼容）。

    `heat_data_service` 主落库输入；字段顺序与 `HeatResult` ORM 声明对齐。
    """

    # === 9 旧（P4 上游字段，保留兼容）===
    equipment_no: str | None = None
    equipment_name: str | None = None
    duty: float | None = None
    effective_area: float | None = None
    hot_inlet_pressure: float | None = None
    hot_outlet_pressure: float | None = None
    cold_inlet_pressure: float | None = None
    cold_outlet_pressure: float | None = None
    u_overall: float | None = None
    # === §3.1.1 基础标识 7 ===
    exchanger_type: str | None = None  # BEM / AEM / AEL / ACHE
    orientation: str | None = None  # Horizontal / Vertical
    units_series: int | None = None
    units_parallel: int | None = None
    shells_per_unit: int | None = None
    total_area_gross: float | None = None
    total_area_eff: float | None = None
    # === §3.1.2 通用热工 8 ===
    lmtd: float | None = None  # 对数平均温差 °C
    mtd_corrected: float | None = None
    emtd: float | None = None
    overdesign_percent: float | None = None
    u_service: float | None = None
    u_calculated: float | None = None
    u_clean: float | None = None
    heat_exchange_area: float | None = None
    # === §3.1.4 通用几何 9 ===
    tube_count: int | None = None
    tube_od: float | None = None  # mm
    tube_id: float | None = None  # mm
    tube_wall_thickness: float | None = None  # mm
    tube_length: float | None = None  # m
    tube_pitch: float | None = None  # mm
    tube_layout: str | None = None  # 30/45/60/90
    tube_material: str | None = None
    tube_passes: int | None = None
    # === §3.1.5 壳程几何 10 ===
    shell_id: float | None = None  # mm
    shell_design_pressure: float | None = None  # kPaG
    shell_design_temp: float | None = None  # °C
    baffle_type: str | None = None
    baffle_cut_percent: float | None = None
    baffle_spacing: float | None = None  # mm
    baffle_inlet_spacing: float | None = None  # mm
    seal_strip_count: int | None = None
    passlane_seal_rod_count: int | None = None
    impingement_plate: str | None = None  # None / Yes
    # === §3.1.6 热阻分布 5 ===
    thermal_resistance_shell: float | None = None
    thermal_resistance_tube: float | None = None
    thermal_resistance_fouling: float | None = None
    thermal_resistance_metal: float | None = None
    thermal_resistance_bond: float | None = None
    # === 3 新 JSONB ===
    shell_params: dict[str, Any] | None = None
    tube_params: dict[str, Any] | None = None
    ache_params: dict[str, Any] | None = None
    # === 5 旧 JSONB（兼容）===
    air_side_json: dict[str, Any] | None = None
    design_conditions_json: dict[str, Any] = field(default_factory=dict)
    enthalpy_table_json: dict[str, Any] | None = None
    input_json: dict[str, Any] = field(default_factory=dict)
    output_json: dict[str, Any] = field(default_factory=dict)


# ===== 落库 =====


async def save_heat_calc_result(
    db: AsyncSession,
    *,
    project_id: uuid.UUID,
    workspace_id: uuid.UUID,
    tag_number: str,
    exchanger_category: str,
    inp: HeatCalcInput,
    record_hash: str = "",
) -> HeatResult:
    """HeatResult 落库：47 字段平铺写入 + record_hash 占位（待 Task 23 finalize）。

    Args:
        db: async session
        project_id / workspace_id: FK（TaggedRecordMixin 强制）
        tag_number: 设备位号（NOT NULL；空字符串会触发 IntegrityError）
        exchanger_category: SHELL_TUBE / AIR_COOL / PLATE
        inp: 47 字段计算输入
        record_hash: 透传（Task 23 调 finalize_calc_record 时再算）

    Returns:
        HeatResult 实例（未 commit，调用方负责 commit）
    """
    record = HeatResult(
        # 必备 FK
        project_id=project_id,
        workspace_id=workspace_id,
        tag_number=tag_number,
        # 类别
        exchanger_category=exchanger_category,
        # 9 旧
        equipment_no=inp.equipment_no,
        equipment_name=inp.equipment_name,
        duty=inp.duty,
        effective_area=inp.effective_area,
        hot_inlet_pressure=inp.hot_inlet_pressure,
        hot_outlet_pressure=inp.hot_outlet_pressure,
        cold_inlet_pressure=inp.cold_inlet_pressure,
        cold_outlet_pressure=inp.cold_outlet_pressure,
        u_overall=inp.u_overall,
        # §3.1.1
        exchanger_type=inp.exchanger_type,
        orientation=inp.orientation,
        units_series=inp.units_series,
        units_parallel=inp.units_parallel,
        shells_per_unit=inp.shells_per_unit,
        total_area_gross=inp.total_area_gross,
        total_area_eff=inp.total_area_eff,
        # §3.1.2
        lmtd=inp.lmtd,
        mtd_corrected=inp.mtd_corrected,
        emtd=inp.emtd,
        overdesign_percent=inp.overdesign_percent,
        u_service=inp.u_service,
        u_calculated=inp.u_calculated,
        u_clean=inp.u_clean,
        heat_exchange_area=inp.heat_exchange_area,
        # §3.1.4
        tube_count=inp.tube_count,
        tube_od=inp.tube_od,
        tube_id=inp.tube_id,
        tube_wall_thickness=inp.tube_wall_thickness,
        tube_length=inp.tube_length,
        tube_pitch=inp.tube_pitch,
        tube_layout=inp.tube_layout,
        tube_material=inp.tube_material,
        tube_passes=inp.tube_passes,
        # §3.1.5
        shell_id=inp.shell_id,
        shell_design_pressure=inp.shell_design_pressure,
        shell_design_temp=inp.shell_design_temp,
        baffle_type=inp.baffle_type,
        baffle_cut_percent=inp.baffle_cut_percent,
        baffle_spacing=inp.baffle_spacing,
        baffle_inlet_spacing=inp.baffle_inlet_spacing,
        seal_strip_count=inp.seal_strip_count,
        passlane_seal_rod_count=inp.passlane_seal_rod_count,
        impingement_plate=inp.impingement_plate,
        # §3.1.6
        thermal_resistance_shell=inp.thermal_resistance_shell,
        thermal_resistance_tube=inp.thermal_resistance_tube,
        thermal_resistance_fouling=inp.thermal_resistance_fouling,
        thermal_resistance_metal=inp.thermal_resistance_metal,
        thermal_resistance_bond=inp.thermal_resistance_bond,
        # 3 新 JSONB
        shell_params=inp.shell_params,
        tube_params=inp.tube_params,
        ache_params=inp.ache_params,
        # 5 旧 JSONB
        air_side_json=inp.air_side_json,
        design_conditions_json=inp.design_conditions_json,
        enthalpy_table_json=inp.enthalpy_table_json,
        input_json=inp.input_json,
        output_json=inp.output_json,
        # record_hash（P4-0-1 审计列，默认空串由 finalize_calc_record 覆盖）
        record_hash=record_hash,
    )
    db.add(record)
    await db.flush()
    return record


# ===== HTRI 映射（与 Task 19 衔接）=====


def map_htri_to_heat_input(
    htri: HtriParsedData,
    *,
    equipment_no: str,
    equipment_name: str | None = None,
) -> HeatCalcInput:
    """HtriParsedData → HeatCalcInput 字段映射。

    单位换算：HTRI shell_dia_m → HeatResult.shell_id（mm，×1000）；
    HTRI baffle_spacing_m → baffle_spacing（mm，×1000）；tube_length 保持 m。
    """
    return HeatCalcInput(
        equipment_no=equipment_no,
        equipment_name=equipment_name or htri.case_name,
        duty=htri.heat_duty_w,
        effective_area=htri.area_required_m2,
        u_overall=htri.overall_u_w_m2k,
        # 管壳字段（mm 转换）
        shell_id=(htri.shell_dia_m * 1000.0) if htri.shell_dia_m is not None else None,
        tube_length=htri.tube_length_m,
        tube_count=htri.tube_count,
        # baffle_spacing 拆行避免 E501
        baffle_spacing=(
            htri.baffle_spacing_m * 1000.0 if htri.baffle_spacing_m is not None else None
        ),
        # §3.1.2 热工
        u_clean=htri.overall_u_w_m2k,
        heat_exchange_area=htri.area_required_m2,
        # 物性 JSONB（§3.1.3）
        shell_params=_htri_hot_side_dict(htri),
        tube_params=_htri_cold_side_dict(htri),
        ache_params=_htri_ache_dict(htri),
        # 5 旧 JSONB（最小填充；P5+ 完整版由 service 层补算）
        design_conditions_json={
            "src_version": htri.version,
            "case_name": htri.case_name,
        },
        input_json={"src": f"htri_{htri.version}"},
        output_json={"status": "OK"},
    )


def _htri_hot_side_dict(htri: HtriParsedData) -> dict[str, Any]:
    return {
        "fluid_name": "hot",
        "temp_in": htri.hot_inlet_t_k,
        "temp_out": htri.hot_outlet_t_k,
        "mass_flow": htri.hot_mass_flow_kgs,
        "cp": htri.hot_cp_j_kgk,
    }


def _htri_cold_side_dict(htri: HtriParsedData) -> dict[str, Any]:
    return {
        "fluid_name": "cold",
        "temp_in": htri.cold_inlet_t_k,
        "temp_out": htri.cold_outlet_t_k,
        "mass_flow": htri.cold_mass_flow_kgs,
        "cp": htri.cold_cp_j_kgk,
    }


def _htri_ache_dict(htri: HtriParsedData) -> dict[str, Any] | None:
    if htri.fan_count is None and htri.air_inlet_t_k is None and htri.bundle_area_m2 is None:
        return None
    return {
        "fan_count": htri.fan_count,
        "air_inlet_temp": htri.air_inlet_t_k,
        "bundle_area": htri.bundle_area_m2,
    }


# ===== ACHE 空冷器 + 焓值表（P5-4-3 / Task 21）=====


@dataclass
class AcheParams:
    """ACHE 空冷器专属参数（spec §3.1.7 + SUP-009 §3.1.3）。

    字段：fan_count / fan_power_kw / bundle_area_m2 / air_inlet_temp_k /
    altitude_m / fin_type / tube_nozzle_count / air_side_resistance_dist。
    """

    fan_count: int
    fan_power_kw: float
    bundle_area_m2: float
    air_inlet_temp_k: float
    altitude_m: float
    fin_type: str  # L-footed / G-embedded / Extruded / Smooth
    tube_nozzle_count: int
    air_side_resistance_dist: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EnthalpyTableEntry:
    """焓值表单点（t_k, h_j_per_kg, cp_j_per_kg_k, phase）。"""

    t_k: float
    h_j_per_kg: float
    cp_j_per_kg_k: float
    phase: str  # LIQUID / VAPOR / TWO_PHASE


@dataclass
class EnthalpyTable:
    """焓值表（P5-OPEN-004 来自 Licensor，Task 21 强校验 ≥10 温度点）。

    覆盖 LOW / AMBIENT / OPERATING 三段区间：每个 phase 至少 3 点（避免
    插值穿越相变区时精度塌陷）。min_entries = 10 满足该最低门槛。
    """

    fluid_name: str
    licensor: str
    source_doc: str
    valid_from: date
    valid_to: date | None
    entries: list[EnthalpyTableEntry]

    MIN_ENTRIES: ClassVar[int] = 10
    # t_k 物理合理区间（K）：覆盖深冷到裂解炉管壁温；
    # 工艺典型操作：cryogenic ~100K / ambient ~300K / fired-heater ~1000K
    T_KELVIN_MIN: ClassVar[float] = 50.0
    T_KELVIN_MAX: ClassVar[float] = 1500.0

    def __post_init__(self) -> None:
        if len(self.entries) < self.MIN_ENTRIES:
            raise ValueError(
                f"EnthalpyTable requires ≥{self.MIN_ENTRIES} temperature points, "
                f"got {len(self.entries)} (覆盖 LIQUID/TWO_PHASE/VAPOR 三段)"
            )
        # 温度点必须按 t_k 升序排列（插值前提）；边界 + 单调性双重校验
        prev_t: float | None = None
        for entry in self.entries:
            if not (self.T_KELVIN_MIN <= entry.t_k <= self.T_KELVIN_MAX):
                raise ValueError(
                    f"EnthalpyTable entry t_k={entry.t_k} K 越界"
                    f"[{self.T_KELVIN_MIN}, {self.T_KELVIN_MAX}] K"
                )
            if prev_t is not None and entry.t_k <= prev_t:
                raise ValueError(
                    f"EnthalpyTable entries 必须按 t_k 严格升序排列，"
                    f"t_k={entry.t_k} <= prev={prev_t}"
                )
            prev_t = entry.t_k

    def to_dict(self) -> dict[str, Any]:
        """EnthalpyTable → 可序列化 dict。

        字段映射：
        - fluid_name / licensor / source_doc：直传字符串
        - valid_from → isoformat 字符串（date → ISO）
        - valid_to → isoformat（可能 None，开放区间表）
        - entries → list[dict]（每条 EnthalpyEntry asdict 序列化）

        返回 dict 直接 JSON-friendly；用于缓存写入（stream_properties_json 容器）
        与对外 API 响应。
        """
        return {
            "fluid_name": self.fluid_name,
            "licensor": self.licensor,
            "source_doc": self.source_doc,
            "valid_from": self.valid_from.isoformat(),
            "valid_to": self.valid_to.isoformat() if self.valid_to else None,
            "entries": [asdict(e) for e in self.entries],
        }


async def save_ache_params(
    db: AsyncSession,
    *,
    heat_exchanger_id: uuid.UUID,
    params: AcheParams,
) -> HeatResult:
    """更新已落库 HeatResult 的 ache_params JSONB 列。

    Args:
        db: async session
        heat_exchanger_id: 既有 HeatResult 主键
        params: ACHE 8 字段参数

    Returns:
        更新后的 HeatResult 实例（未 commit，调用方负责 commit）

    Raises:
        ValueError: heat_id 不存在
    """
    record = await db.get(HeatResult, heat_exchanger_id)
    if record is None:
        raise ValueError(f"HeatResult {heat_exchanger_id} not found")
    record.ache_params = params.to_dict()
    await db.flush()
    return record


async def save_enthalpy_table(
    db: AsyncSession,
    *,
    heat_exchanger_id: uuid.UUID,
    table: EnthalpyTable,
) -> HeatResult:
    """更新已落库 HeatResult 的 enthalpy_table_json JSONB 列。

    Args:
        db: async session
        heat_exchanger_id: 既有 HeatResult 主键
        table: ≥10 温度点焓值表（EnthalpyTable.__post_init__ 已校验）

    Returns:
        更新后的 HeatResult 实例（未 commit，调用方负责 commit）

    Raises:
        ValueError: heat_id 不存在
    """
    record = await db.get(HeatResult, heat_exchanger_id)
    if record is None:
        raise ValueError(f"HeatResult {heat_exchanger_id} not found")
    record.enthalpy_table_json = table.to_dict()
    await db.flush()
    return record