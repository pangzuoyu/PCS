"""P4-1-2 step 1：PT_FLASH 最小实现。

仅实现等温等压闪蒸（PT_FLASH），返回 (vapor_fraction, y_vapor, x_liquid)。
其余 7 种 flash（PH_FLASH / PS_FLASH / BUBBLE_P / BUBBLE_T / DEW_P / DEW_T /
SATURATION）留待后续 step（step 2-N）。

实现：
- 薄包装 ``thermo.FlashPT``（thermo 后端用 Raoult K-value + Rachford-Rice
  解析 — 见 ``thermo_factory._WagnerBaseThermo.FlashPT``）
- 归一化由 ``build_thermo`` 入口处理；本函数假定 zs 已归一化（与 Protocol
  契约一致）
"""
from __future__ import annotations

from typing import NamedTuple

from app.services.flash.thermo_factory import ThermoInterface


class PTFlashResult(NamedTuple):
    """PT flash 返回值。"""

    vapor_fraction: float
    y_vapor: list[float]
    x_liquid: list[float]


def PT_FLASH(
    zs: list[float], T: float, P: float, thermo: ThermoInterface
) -> PTFlashResult:
    """PT flash：等温等压闪蒸。

    Args:
        zs: 总组成（须已归一化 — 与 ThermoInterface 契约一致）
        T: 系统温度 (K)
        P: 系统压力 (Pa)
        thermo: thermo 后端实例

    Returns:
        PTFlashResult(vapor_fraction, y_vapor, x_liquid)
    """
    vfrac, x, y = thermo.FlashPT(zs, T, P)
    return PTFlashResult(vapor_fraction=vfrac, y_vapor=list(y), x_liquid=list(x))


__all__ = ["PTFlashResult", "PT_FLASH"]
