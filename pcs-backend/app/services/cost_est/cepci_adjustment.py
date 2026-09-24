"""CEPCI 调整（Chemical Engineering Plant Cost Index，SPEC §3.2.8 第二项）。

公式（时间/通胀调整）：

    C₂ = C₁ × (CEPCI₂ / CEPCI₁)

其中：

- ``C₁`` 基准年份投资（基准货币）。
- ``C₂`` 目标年份投资（基准货币，已含通胀）。
- ``CEPCI₁`` 基准年份 CEPCI 指数。
- ``CEPCI₂`` 目标年份 CEPCI 指数。

CEPCI 数据来源：``cepci_index_series`` CONFIG 表（Task 18 / G-03 落地）。

误差：±5~10%（CEPCI 反映化工设备/材料/人工综合通胀）。

CEPT-V1.0 §3.2.8 — CEPCI 与六十法则联用：先按 0.6 scaling 做容量/
规模调整，再乘 CEPCI 比做时间/通胀调整：

    C_target = C_base × (S_target / S_base)^0.6 × (CEPCI_target / CEPCI_base)
"""
from __future__ import annotations

from dataclasses import dataclass

from app.services.exceptions import PcsError


@dataclass(frozen=True)
class CepciAdjustmentInput:
    """CEPCI 调整输入参数（frozen dataclass）。"""

    reference_cost: float  # C₁（基准货币）
    reference_cepci: float  # CEPCI₁
    target_cepci: float  # CEPCI₂


@dataclass(frozen=True)
class CepciAdjustmentResult:
    """CEPCI 调整结果（frozen dataclass）。"""

    target_cost: float  # C₂（基准货币）
    cepci_ratio: float  # CEPCI₂ / CEPCI₁
    formula_ref: str = "CEPCI_ADJUSTMENT_§3.2.8"


class CepciAdjustmentInputError(PcsError):
    """CEPCI 调整输入不合法（422）。"""

    code = "CEPCI_ADJUSTMENT_INPUT_ERROR"
    status = 422


def calc_cepci_adjustment(inp: CepciAdjustmentInput) -> CepciAdjustmentResult:
    """CEPCI 时间/通胀调整。

    Args:
        inp: ``CepciAdjustmentInput``（已冻结 dataclass）。

    Returns:
        ``CepciAdjustmentResult``（含 C₂ / ratio）。

    Raises:
        ``CepciAdjustmentInputError``：输入字段越界或非正（422）。
    """
    if inp.reference_cost < 0:
        raise CepciAdjustmentInputError("reference_cost 必须 ≥ 0")
    if inp.reference_cepci <= 0:
        raise CepciAdjustmentInputError("reference_cepci 必须 > 0")
    if inp.target_cepci <= 0:
        raise CepciAdjustmentInputError("target_cepci 必须 > 0")

    ratio = inp.target_cepci / inp.reference_cepci
    target_cost = inp.reference_cost * ratio

    return CepciAdjustmentResult(
        target_cost=target_cost,
        cepci_ratio=ratio,
    )
