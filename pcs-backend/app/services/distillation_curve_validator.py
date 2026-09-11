"""P3.x SIM-34：蒸馏曲线 8 种 schema 验证器。

spec V1.1 §变更 8 + ADD-001 §3.9：streams.distillation_curves JSONB 容器
存储 8 种蒸馏曲线（ASTM D86 / TBP / EFV / D86_CRACKING / D1160 / D2887 /
D5236 / D7169），每条曲线 schema：

    {
        "curve_type": "D86" | "TBP" | "EFV" | "D86_CRACKING"
                    | "D1160" | "D2887" | "D5236" | "D7169",
        "points": [
            {"percent_vapor": float (0~100), "temp_c": float (K or C)},
            ...
        ],
        "pressure_mmhg": float | None,  # 减压曲线（EFV/D1160/D5236）必填
    }

设计要点：
- 8 种 curve_type 严格枚举（拒绝未知类型，避免拼写错误）
- points 必须非空 + percent_vapor 严格递增（0→100，含端点）
- temp_c 单调非降（蒸馏曲线定义）
- pressure_mmhg：仅 D1160/D5236/EFV 强制 > 0；其他 None
- schema 验证失败抛 DistillationCurveValidationError
"""
from __future__ import annotations

from typing import Any


# 蒸馏曲线 8 种类型（spec V1.1 §变更 8）
DISTILLATION_CURVE_TYPES: frozenset[str] = frozenset(
    {
        "D86",          # ASTM D86, 常压蒸馏（炼油最常用）
        "TBP",          # True Boiling Point, 真沸点蒸馏
        "EFV",          # Equilibrium Flash Vaporization, 平衡闪蒸
        "D86_CRACKING", # D86 with cracking, 含裂解反应的 D86
        "D1160",        # ASTM D1160, 减压蒸馏（重油）
        "D2887",        # SimDist GC, 气相色谱模拟蒸馏
        "D5236",        # ASTM D5236, 减压蒸馏高温
        "D7169",        # ASTM D7169, 高温 SimDist
    }
)

# 减压蒸馏类型（pressure_mmhg 强制 > 0）
_REDUCED_PRESSURE_TYPES: frozenset[str] = frozenset({"EFV", "D1160", "D5236"})


class DistillationCurveValidationError(ValueError):
    """蒸馏曲线 schema 验证失败（curve_type 未知 / points 不合法 / pressure 缺失）。"""


def _validate_single_curve(curve: dict[str, Any]) -> None:
    """验证单条蒸馏曲线 schema。"""
    if not isinstance(curve, dict):
        raise DistillationCurveValidationError(
            f"曲线项必须为 dict，实际 {type(curve).__name__}"
        )

    # 1. curve_type 严格枚举
    curve_type = curve.get("curve_type")
    if curve_type not in DISTILLATION_CURVE_TYPES:
        raise DistillationCurveValidationError(
            f"curve_type 必须是 {sorted(DISTILLATION_CURVE_TYPES)} 之一"
            f"，实际 {curve_type!r}"
        )

    # 2. points 必须非空 + 字段完整
    points = curve.get("points")
    if not points:
        raise DistillationCurveValidationError(
            f"{curve_type} 曲线 points 必须非空"
        )
    if not isinstance(points, list):
        raise DistillationCurveValidationError(
            f"{curve_type} 曲线 points 必须为 list，实际 {type(points).__name__}"
        )

    # 3. 每点 schema + 单调性
    prev_pct: float | None = None
    prev_temp: float | None = None
    for idx, pt in enumerate(points):
        if not isinstance(pt, dict):
            raise DistillationCurveValidationError(
                f"{curve_type} 点 {idx} 必须为 dict"
            )
        pct = pt.get("percent_vapor")
        temp = pt.get("temp_c")
        if pct is None or temp is None:
            raise DistillationCurveValidationError(
                f"{curve_type} 点 {idx} 缺 percent_vapor 或 temp_c"
            )
        if not (0 <= pct <= 100):
            raise DistillationCurveValidationError(
                f"{curve_type} 点 {idx} percent_vapor={pct} 越界 [0~100]"
            )
        if temp <= 0:
            raise DistillationCurveValidationError(
                f"{curve_type} 点 {idx} temp_c={temp} 必须 > 0"
            )
        # percent_vapor 严格递增
        if prev_pct is not None and pct <= prev_pct:
            raise DistillationCurveValidationError(
                f"{curve_type} 点 {idx} percent_vapor={pct} 必须严格 > 前点 {prev_pct}"
            )
        # temp_c 单调非降
        if prev_temp is not None and temp < prev_temp:
            raise DistillationCurveValidationError(
                f"{curve_type} 点 {idx} temp_c={temp} 必须 ≥ 前点 {prev_temp}"
            )
        prev_pct = pct
        prev_temp = temp

    # 4. pressure_mmhg：减压曲线强制 > 0；其他 None
    pressure = curve.get("pressure_mmhg")
    if curve_type in _REDUCED_PRESSURE_TYPES:
        if pressure is None or pressure <= 0:
            raise DistillationCurveValidationError(
                f"{curve_type} 曲线 pressure_mmhg 必须 > 0，实际 {pressure!r}"
            )
    else:
        if pressure is not None and pressure <= 0:
            raise DistillationCurveValidationError(
                f"{curve_type} 曲线 pressure_mmhg={pressure} 非法（应 None 或 > 0）"
            )


def validate_distillation_curves(curves: Any) -> None:
    """验证 distillation_curves JSONB 容器（list[dict]）。

    容器可为空 list 或 None（不抛）。每条曲线独立校验。
    """
    if curves is None:
        return
    if not isinstance(curves, list):
        raise DistillationCurveValidationError(
            f"distillation_curves 必须为 list，实际 {type(curves).__name__}"
        )
    for idx, curve in enumerate(curves):
        try:
            _validate_single_curve(curve)
        except DistillationCurveValidationError as e:
            raise DistillationCurveValidationError(
                f"曲线 #{idx}: {e}"
            ) from e


__all__ = [
    "DISTILLATION_CURVE_TYPES",
    "DistillationCurveValidationError",
    "validate_distillation_curves",
]