"""P5-3-5 PSV 选型（API 526 标准孔口表 D~T）。

按 PCS-PLAN-P5-DEVICE-EQUIPMENT.md §370-394 + SUP-P5-PSV-001 §4.1：

API 526 7th Ed. 标准孔口面积表（D~T）：
- D: 0.000710 in²
- E: 0.001260 in²
- F: 0.002010 in²
- G: 0.003140 in²
- H: 0.004540 in²
- J: 0.006390 in²
- K: 0.009170 in²
- L: 0.013050 in²
- M: 0.017650 in²
- N: 0.024760 in²
- P: 0.033770 in²
- Q: 0.046330 in²
- R: 0.061720 in²
- T: 0.079170 in²

策略（保守选型 + 不超 5% 过裕量）：
- 选 ≥ area_required 的最小标准孔口
- 实际面积 / 所需面积 ≤ 1.05（5% 过裕量上限，避免浪费）
- 实际面积 / 所需面积 ≥ 1.0（不能欠选）

单位换算（V1 简化）：
- 1 in² = 0.00064516 m²
- 输入 area_required_m2 → 选 m² 系列孔口

formula_ref 结构化（F-09）：API_526 + 7th + 表格条款。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

from app.services.exceptions import PcsError

# ---------- 类型别名 ----------


OrificeSize = Literal["D", "E", "F", "G", "H", "J", "K", "L", "M", "N", "P", "Q", "R", "T"]


@dataclass(frozen=True)
class OrificeFormulaRef:
    """孔口选型公式溯源（F-09）。"""

    standard: str
    version: str
    clause: str


# ---------- API 526 标准孔口面积表（V1 简化：in² → m²）----------


_IN2_TO_M2: Final[float] = 0.00064516  # 1 in² = 0.00064516 m²


_API526_ORIFICE_TABLE_IN2: Final[tuple[tuple[OrificeSize, float], ...]] = (
    ("D", 0.000710),
    ("E", 0.001260),
    ("F", 0.002010),
    ("G", 0.003140),
    ("H", 0.004540),
    ("J", 0.006390),
    ("K", 0.009170),
    ("L", 0.013050),
    ("M", 0.017650),
    ("N", 0.024760),
    ("P", 0.033770),
    ("Q", 0.046330),
    ("R", 0.061720),
    ("T", 0.079170),
)


# 缓存 m² 数组（启动时一次性转换）
def _build_table_m2() -> tuple[tuple[OrificeSize, float], ...]:
    return tuple((size, area_in2 * _IN2_TO_M2) for size, area_in2 in _API526_ORIFICE_TABLE_IN2)


_API526_TABLE_M2: Final = _build_table_m2()

# 5% 过裕量上限（V1 锁定）
_MAX_OVERSIZE_RATIO: Final[float] = 1.05


# ---------- 输入输出 ----------


@dataclass(frozen=True)
class OrificeInput:
    """孔口选型输入。

    物理量 SI 单位：
      - area_required_m2: 所需泄放面积 m²（来自 P5-3-4 ReliefAreaResult.area_required_m2）
    """

    area_required_m2: float


@dataclass(frozen=True)
class OrificeResult:
    """孔口选型结果。

    字段：
      - selected_size: 选中的标准孔口 D~T
      - actual_area_m2: 实际标准孔口面积 m²
      - required_area_m2: 输入所需面积 m²（透传）
      - oversize_ratio: 实际/所需（≥ 1.0，≤ 1.05）
      - formula_ref: 公式溯源
    """

    selected_size: OrificeSize
    actual_area_m2: float
    required_area_m2: float
    oversize_ratio: float
    formula_ref: OrificeFormulaRef


# ---------- 异常 ----------


class PsvOrificeInputError(PcsError):
    """PSV 孔口选型输入不合法（422）。"""

    code = "PSV_INPUT_ERROR"
    status = 422


# ---------- 选型实现 ----------


def orifice_area_m2(size: OrificeSize) -> float:
    """按 OrificeSize（D~T）查 API 526 面积 m²。V1.14 §4.2 G9 使用。"""
    for s, a in _API526_TABLE_M2:
        if s == size:
            return a
    raise ValueError(f"未知孔口 {size}（API 526 D~T）")


def select_orifice_api526(inp: OrificeInput) -> OrificeResult:
    """API 526 §5.1 标准孔口选型。

    策略（保守选型）：
    - 选 ≥ area_required 的最小标准孔口
    - 实际面积 / 所需面积 ≥ 1.0（不能欠选）
    - 实际面积 / 所需面积 > 1.05 仅记录到 oversize_ratio（API 526 实际允许）
    - 若所需面积 > T 最大孔口 → 抛错（需双 PSV 并联，P5-3-6）
    """
    if inp.area_required_m2 <= 0:
        raise PsvOrificeInputError(
            f"area_required_m2={inp.area_required_m2} 必须 > 0"
        )

    # 选 ≥ area_required 的最小标准孔口
    selected: OrificeSize | None = None
    actual_area: float = 0.0
    for size, area in _API526_TABLE_M2:
        if area >= inp.area_required_m2:
            selected = size
            actual_area = area
            break

    if selected is None:
        # 超出 T 孔口 → required > T 最大面积 = 欠选（抛错）
        t_area = _API526_TABLE_M2[-1][1]
        raise PsvOrificeInputError(
            f"area_required_m2={inp.area_required_m2:.6e} 超过 API 526 最大孔口 T "
            f"({t_area:.6e} m²)；建议选双 PSV 并联（待 P5-3-6 实施）"
        )

    oversize_ratio = actual_area / inp.area_required_m2

    return OrificeResult(
        selected_size=selected,
        actual_area_m2=actual_area,
        required_area_m2=inp.area_required_m2,
        oversize_ratio=oversize_ratio,
        formula_ref=OrificeFormulaRef(
            standard="API_526",
            version="7th",
            clause="Table 1 / Table 2",
        ),
    )


__all__ = [
    "OrificeSize",
    "OrificeFormulaRef",
    "OrificeInput",
    "OrificeResult",
    "select_orifice_api526",
    "PsvOrificeInputError",
]