"""六十法则（0.6 Power Scaling Rule，SPEC §3.2.8 第一项）。

经典化工投资估算经验式：

    C₂ = C₁ × (S₂ / S₁)^n

其中：

- ``C₁`` 已知设备/工厂投资（基准货币）。
- ``S₁`` 已知规模参数（capacity / throughput / area / volume 等）。
- ``S₂`` 待估算规模参数。
- ``C₂`` 待估算投资。

指数 ``n`` 默认 0.6（大量化工设备统计回归的平均值，适用于大多数单元
操作）；对部分特定设备（泵/压缩机/换热器）有专用 n 值（0.3~0.9），可
由外部调用方覆盖，或由成本关联式 CONFIG 提供（Task 35 第三节）。

误差范围：±30%（参考级），SPEC §3.2.8 验收。

CEPT-V1.0 §3.2.8 — 六法则为投资估算阶段 1 工具，不替代详细工程报价。
"""
from __future__ import annotations

from dataclasses import dataclass

from app.services.exceptions import PcsError


@dataclass(frozen=True)
class SixTenthsRuleInput:
    """六十法则输入参数（frozen dataclass）。"""

    reference_cost: float  # C₁（基准货币）
    reference_scale: float  # S₁（规模参数）
    target_scale: float  # S₂（规模参数）


@dataclass(frozen=True)
class SixTenthsRuleResult:
    """六十法则计算结果（frozen dataclass）。"""

    target_cost: float  # C₂（基准货币）
    scaling_exponent: float  # n（默认 0.6，可由外部覆盖）
    ratio: float  # S₂ / S₁
    formula_ref: str = "SIX_TENTHS_RULE_§3.2.8"


class SixTenthsRuleInputError(PcsError):
    """六十法则输入不合法（422）。"""

    code = "SIX_TENTHS_RULE_INPUT_ERROR"
    status = 422


def calc_six_tenths_rule(
    inp: SixTenthsRuleInput,
    scaling_exponent: float = 0.6,
) -> SixTenthsRuleResult:
    """六十法则规模/容量 scaling。

    Args:
        inp: ``SixTenthsRuleInput``（已冻结 dataclass，含 C₁/S₁/S₂）。
        scaling_exponent: scaling 指数（默认 0.6；特定设备可覆盖
            0.3~0.9 区间）。允许上限 1.5（成本关联式中极端值）。

    Returns:
        ``SixTenthsRuleResult``（含 C₂ / n / ratio）。

    Raises:
        ``SixTenthsRuleInputError``：输入字段越界或非正（422）。
    """
    if inp.reference_cost < 0:
        raise SixTenthsRuleInputError("reference_cost 必须 ≥ 0")
    if inp.reference_scale <= 0:
        raise SixTenthsRuleInputError("reference_scale 必须 > 0")
    if inp.target_scale <= 0:
        raise SixTenthsRuleInputError("target_scale 必须 > 0")
    if scaling_exponent <= 0 or scaling_exponent > 1.5:
        raise SixTenthsRuleInputError("scaling_exponent 必须在 (0, 1.5]")

    ratio = inp.target_scale / inp.reference_scale
    target_cost = inp.reference_cost * (ratio ** scaling_exponent)

    return SixTenthsRuleResult(
        target_cost=target_cost,
        scaling_exponent=scaling_exponent,
        ratio=ratio,
    )
