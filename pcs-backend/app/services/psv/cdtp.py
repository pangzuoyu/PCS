"""SUP-P5-PSV-002 V1.14 §4.4 CDTP 修正。

按 SPEC V1.14 §4.4：

CDTP = Conventional Differential Test Pressure（传统泄放测试压差）
      = 整定压力 - 叠加背压（当 SUPERIMPOSED BP > 0 时）

设计要点：
- 纯函数：set_pressure - superimposed_bp，无副作用
- 单位：Pa（前端透传）；不做单位换算
- 输入校验：set_pressure > 0；superimposed_bp >= 0；CDTP > 0
  （任一不满足 → PcsError；用于 §4.2 G10 拦截前置检查）

不做：
- 不做 built-up BP 修正（§3.5；built-up 用 Kb 单独处理）
- 不做变工况 CDTP 序列（P5 仅单点；连续工况 P6+）
"""
from __future__ import annotations

from app.services.exceptions import PcsError


def apply_cdtp_correction(
    set_pressure_pa: float,
    superimposed_ba_pa: float,
) -> float:
    """CDTP 修正（§4.4）。

    Args:
        set_pressure_pa: 设定压力（Pa gauge；前端透传 stream.max_allowable_pressure_pa）
        superimposed_ba_pa: 叠加背压（Pa gauge；恒定背压部分）

    Returns:
        CDTP（Pa gauge；set_pressure - superimposed_bp）

    Raises:
        PcsError: 输入非法（status=422；code 区分）
            - PSV_INVALID_SET_PRESSURE：set_pressure_pa <= 0
            - PSV_INVALID_SUPERIMPOSED_BP：superimposed_ba_pa < 0
            - PSV_CDTP_NON_POSITIVE：CDTP <= 0（背压超过设定压力，无泄放压差）

    Notes:
        - 不调用时不应触发（G10 拦截在 SPRING_LOADED + SUPERIMPOSED 路径前置）
        - 透传给 PsvResult.cdtp_set_pressure_pa 字段
    """
    if set_pressure_pa <= 0:
        raise PcsError(
            f"设定压力必须 > 0，当前 {set_pressure_pa} Pa",
            code="PSV_INVALID_SET_PRESSURE",
            status=422,
            details={"set_pressure_pa": set_pressure_pa},
        )
    if superimposed_ba_pa < 0:
        raise PcsError(
            f"叠加背压必须 >= 0，当前 {superimposed_ba_pa} Pa",
            code="PSV_INVALID_SUPERIMPOSED_BP",
            status=422,
            details={"superimposed_ba_pa": superimposed_ba_pa},
        )

    cdtp = set_pressure_pa - superimposed_ba_pa
    if cdtp <= 0:
        raise PcsError(
            f"CDTP 必须 > 0（设定压力 {set_pressure_pa} Pa，"
            f"叠加背压 {superimposed_ba_pa} Pa，背压超过设定压力）",
            code="PSV_CDTP_NON_POSITIVE",
            status=422,
            details={
                "set_pressure_pa": set_pressure_pa,
                "superimposed_ba_pa": superimposed_ba_pa,
                "cdtp_pa": cdtp,
            },
        )

    return cdtp


__all__ = ["apply_cdtp_correction"]