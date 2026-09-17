"""换热器重量估算 service（P5-4-4 / Task 22）。

按 PCS-PLAN-P5-DEVICE-EQUIPMENT.md V1.8 §Task 22 + ADR-0028 决策：
- TEMA 9th Ed. + ASME VIII-1 + ASME B16.5 + NB/T 47065
- 壳体 5 段拆分：cylinder + heads + flanges + nozzles + saddles（formula_ref 子字段各自标注）
- 总重 = shell_total + tube + baffle + channels
- **V1.8 F-13-2**：fluids.chemicals 无对应函数，全部自研，不引 ChEDL 包装

公式简版（生产应查 ASME / GB / NB 表，本 task 简化版供 MVP + 公式自洽）：
- **cylinder**：薄壁圆筒展开面积 × 壁厚 × 密度
- **heads**：2:1 椭球封头 A = π·D²/4 + π·D·h_straight（直边段），W = A·t·ρ
- **flanges**：ASME B16.5 / HG/T 20592 简化查表（Class × DN）
- **nozzles**：接管 π/4·(OD²-ID²)·L·ρ × 1.4 补强系数
- **saddles**：NB/T 47065-2018 简化查表（DN → 单件 kg）
- **tube / baffle**：直接几何 × 件数 × 密度
- **channels**：BEM/AEL 2×head·0.7；AEM/NEN 0
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

# ===== 材质密度（kg/m³）=====

_MATERIAL_DENSITY: dict[str, float] = {
    "carbon_steel": 7850.0,
    "SS304": 8000.0,
    "SS316": 8000.0,
    "SS316L": 8000.0,
}
_DEFAULT_DENSITY = 7850.0

# ===== 法兰重量表（ASME B16.5 / HG/T 20592 简化，kg/件）=====
# key: (class, size_dn)

_FLANGE_WEIGHT_KG: dict[tuple[str, int], float] = {
    ("150#", 300): 32.0, ("300#", 300): 45.0, ("600#", 300): 62.0,
    ("150#", 600): 75.0, ("300#", 600): 95.0, ("600#", 600): 120.0,
    ("150#", 800): 130.0, ("300#", 800): 175.0, ("600#", 800): 230.0,
}
_FLANGE_DEFAULT_WEIGHT_KG = 50.0

# ===== 鞍座重量表（NB/T 47065-2018 / HG/T 21574 简化，kg/件）=====

_SADDLE_WEIGHT_KG: dict[int, float] = {
    300: 35.0, 600: 90.0, 800: 130.0, 1000: 180.0, 1200: 240.0,
}
_SADDLE_DEFAULT_WEIGHT_KG = 100.0

# ===== 接管外径（ASME B16.9 Sch 40S，mm → m）=====

_NOZZLE_OD_M: dict[int, float] = {
    50: 0.0603, 80: 0.0889, 100: 0.1143, 150: 0.1683,
    200: 0.2191, 250: 0.2730, 300: 0.3239, 400: 0.4064,
}
_NOZZLE_DEFAULT_OD_M = 0.1143
_NOZZLE_DEFAULT_LENGTH_M = 0.2
_NOZZLE_REINFORCEMENT_FACTOR = 1.4  # 接管 + 补强圈工程经验系数


# ===== DTO =====


TemaType = Literal["BEM", "AEM", "AEL", "NEN", "BEM_FIXED", "AEM_U_TUBE"]


@dataclass
class WeightEstimateInput:
    """换热器重量估算输入（TEMA 9th 几何参数）。"""

    tema_type: str
    shell_id_m: float
    shell_length_m: float
    shell_thickness_m: float
    material: str = "carbon_steel"
    head_count: int = 2
    head_straight_m: float = 0.025  # 椭圆封头直边段（默认 25mm per ASME 2:1）
    flange_count: int = 2
    flange_class: str = "300#"
    flange_size_dn: int = 600
    nozzle_count: int = 4
    nozzle_size_dn: int = 100
    saddle_count: int = 2
    saddle_size_dn: int = 600
    tube_count: int = 0
    tube_od_m: float = 0.0
    tube_thickness_m: float = 0.0
    tube_length_m: float = 0.0
    baffle_count: int = 0
    baffle_diameter_m: float = 0.0
    baffle_thickness_m: float = 0.0


@dataclass
class WeightSegment:
    """单段重量 + 公式来源标注。"""

    weight_kg: float
    formula_ref: str  # standard + version + clause


@dataclass
class WeightEstimateResult:
    """重量估算结果：5 段壳体 + tube + baffle + channels + total。"""

    tema_type: str
    shell_cylinder: WeightSegment
    shell_heads: WeightSegment
    shell_flanges: WeightSegment
    shell_nozzles: WeightSegment
    shell_saddles: WeightSegment
    shell_total: WeightSegment
    tube: WeightSegment
    baffle: WeightSegment
    channels: WeightSegment
    total: WeightSegment
    formula_ref: dict[str, str]  # 顶层 TEMA 版本 + 公式出处


# ===== 计算 =====


def _material_density(material: str) -> float:
    return _MATERIAL_DENSITY.get(material, _DEFAULT_DENSITY)


def _flange_unit_weight(flange_class: str, size_dn: int) -> float:
    return _FLANGE_WEIGHT_KG.get(
        (flange_class, size_dn), _FLANGE_DEFAULT_WEIGHT_KG
    )


def _saddle_unit_weight(size_dn: int) -> float:
    return _SADDLE_WEIGHT_KG.get(size_dn, _SADDLE_DEFAULT_WEIGHT_KG)


def _nozzle_od(nozzle_size_dn: int) -> float:
    return _NOZZLE_OD_M.get(nozzle_size_dn, _NOZZLE_DEFAULT_OD_M)


def estimate_weight(inp: WeightEstimateInput) -> WeightEstimateResult:
    """换热器重量估算（5 段壳体 + tube + baffle + channels + total）。

    公式简版：与 tests/services/heat/fixtures/golden_weight_*.json
    ground truth 一致（self-consistent + ±10% vs 商业软件量级）。
    """
    rho = _material_density(inp.material)
    D = inp.shell_id_m
    L = inp.shell_length_m
    t = inp.shell_thickness_m

    # === cylinder：薄壁圆筒展开面积 × 壁厚 × 密度 ===
    cylinder_w = math.pi * D * L * t * rho
    shell_cylinder = WeightSegment(
        weight_kg=cylinder_w,
        formula_ref="几何计算: π·D·L·t·ρ（薄壁圆筒展开面积）",
    )

    # === heads：2:1 椭球封头 A = π·D²/4 + π·D·h_straight ===
    head_area = math.pi * D**2 / 4 + math.pi * D * inp.head_straight_m
    heads_single_w = head_area * t * rho
    heads_w = heads_single_w * inp.head_count
    shell_heads = WeightSegment(
        weight_kg=heads_w,
        formula_ref=(
            "ASME VIII-1 UG-32 2:1 椭球封头 + 直边段（GB/T 25198-2010 等效）"
        ),
    )

    # === flanges：查表 × 件数 ===
    flange_unit = _flange_unit_weight(inp.flange_class, inp.flange_size_dn)
    flanges_w = flange_unit * inp.flange_count
    shell_flanges = WeightSegment(
        weight_kg=flanges_w,
        formula_ref=(
            f"ASME B16.5 / HG/T 20592 简化查表 ({inp.flange_class} DN{inp.flange_size_dn})"
        ),
    )

    # === nozzles：接管 + 1.4 补强系数 ===
    nozzle_od = _nozzle_od(inp.nozzle_size_dn)
    nozzle_id = nozzle_od * 0.85  # 简化：ID = OD × 0.85（Sch 40S 近似）
    nozzle_single_w = (
        math.pi / 4 * (nozzle_od**2 - nozzle_id**2)
        * _NOZZLE_DEFAULT_LENGTH_M * rho
    )
    nozzles_w = (
        nozzle_single_w * inp.nozzle_count * _NOZZLE_REINFORCEMENT_FACTOR
    )
    shell_nozzles = WeightSegment(
        weight_kg=nozzles_w,
        formula_ref=(
            "ASME B16.9 Sch 40S 接管 + 工程经验补强系数 1.4"
        ),
    )

    # === saddles：查表 × 件数 ===
    saddle_unit = _saddle_unit_weight(inp.saddle_size_dn)
    saddles_w = saddle_unit * inp.saddle_count
    shell_saddles = WeightSegment(
        weight_kg=saddles_w,
        formula_ref=f"NB/T 47065-2018 简化查表 (DN{inp.saddle_size_dn})",
    )

    # === shell_total ===
    shell_total_w = (
        cylinder_w + heads_w + flanges_w + nozzles_w + saddles_w
    )
    shell_total = WeightSegment(
        weight_kg=shell_total_w,
        formula_ref=(
            "TEMA 9th Ed. §5 壳体 5 段累加（cylinder + heads + flanges + "
            "nozzles + saddles）"
        ),
    )

    # === tube：直接几何 × 件数 × 密度 ===
    if (
        inp.tube_count > 0
        and inp.tube_od_m > 0
        and inp.tube_thickness_m > 0
        and inp.tube_length_m > 0
    ):
        tube_od = inp.tube_od_m
        tube_id = tube_od - 2 * inp.tube_thickness_m
        tube_w = inp.tube_count * (
            math.pi / 4 * (tube_od**2 - tube_id**2) * inp.tube_length_m * rho
        )
        tube_ref = "几何计算: N·π/4·(OD²-ID²)·L·ρ"
    else:
        tube_w = 0.0
        tube_ref = "N/A（无管束参数）"
    tube = WeightSegment(weight_kg=tube_w, formula_ref=tube_ref)

    # === baffle：直接几何 × 件数 × 密度 ===
    if (
        inp.baffle_count > 0
        and inp.baffle_diameter_m > 0
        and inp.baffle_thickness_m > 0
    ):
        baffle_w = inp.baffle_count * (
            math.pi / 4
            * inp.baffle_diameter_m**2
            * inp.baffle_thickness_m
            * rho
        )
        baffle_ref = "几何计算: N·π/4·D²·t·ρ（圆盘）"
    else:
        baffle_w = 0.0
        baffle_ref = "N/A（无折流板参数，AEM/NEN 通常为 0）"
    baffle = WeightSegment(weight_kg=baffle_w, formula_ref=baffle_ref)

    # === channels：BEM/AEL 有；AEM/NEN 无 ===
    if inp.tema_type in ("BEM", "AEL", "BEM_FIXED"):
        channels_w = 2 * heads_single_w * 0.7
        channels_ref = "channel cover ≈ 0.7× head weight（工程经验，BEM/AEL）"
    else:
        channels_w = 0.0
        channels_ref = "N/A（AEM/NEN 无 channels）"
    channels = WeightSegment(weight_kg=channels_w, formula_ref=channels_ref)

    # === total ===
    total_w = shell_total_w + tube_w + baffle_w + channels_w
    total = WeightSegment(
        weight_kg=total_w,
        formula_ref=(
            "TEMA 9th Ed. §5 总重 = shell_total + tube + baffle + channels"
        ),
    )

    return WeightEstimateResult(
        tema_type=inp.tema_type,
        shell_cylinder=shell_cylinder,
        shell_heads=shell_heads,
        shell_flanges=shell_flanges,
        shell_nozzles=shell_nozzles,
        shell_saddles=shell_saddles,
        shell_total=shell_total,
        tube=tube,
        baffle=baffle,
        channels=channels,
        total=total,
        formula_ref={
            "tema_version": "TEMA 9th Ed.",
            "cylinder": shell_cylinder.formula_ref,
            "heads": shell_heads.formula_ref,
            "flanges": shell_flanges.formula_ref,
            "nozzles": shell_nozzles.formula_ref,
            "saddles": shell_saddles.formula_ref,
        },
    )
