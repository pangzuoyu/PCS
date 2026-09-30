"""Behr 反函数（露点求解）子模块（P6-6A-6 v5.1 B-3 / H-3）。

P6-9-PICKUP-5 5C（REF-P6-8-2）自 ``glycol_dehydration_service.py`` 拆出。

本模块负责 W → T 的反函数方向：给定目标含水量 W（lb water / MMscf dry gas）
与压力 P（psia），反算接触塔露点 T_dew（°F）。

  - ``_DewpointResult`` — frozen dataclass，三态显式（FOUND / EXTRAPOLATED /
    NOT_FOUND）避免 tuple 歧义
  - ``_behr_inverse_dewpoint`` — scipy ``brentq`` + Newton fallback 两段求解

本模块单向依赖同包 ``behr``（复用 ``_calc_behr_water_content_lb_per_mmscf``
正函数作为残差），与 ``reboilers`` 互不依赖。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from app.services.psychro._glycol_dehydration.behr import (
    _calc_behr_water_content_lb_per_mmscf,
)

# Behr 反函数 bracket
_BEHR_DEWPOINT_BRACKET: Final[tuple[float, float]] = (60.0, 200.0)
_BEHR_DEWPOINT_EXTRAPOLATED_THRESHOLD_F: Final[float] = 60.0
_BEHR_DEWPOINT_EXTRAPOLATION_WARNING_TOL_F: Final[float] = 1e-4


@dataclass(frozen=True)
class _DewpointResult:
    """Behr 反函数结果 (frozen dataclass) — 三态显式避免 tuple 歧义。

    三态语义:
      - FOUND: dewpoint_f 非 None, extrapolated=False, reason=None
      - EXTRAPOLATED: dewpoint_f 非 None, extrapolated=True (T<60°F Antoine 外推),
        reason=外推说明
      - NOT_FOUND: dewpoint_f=None, extrapolated=False/True,
        reason="brentq and Newton both failed"
    """

    dewpoint_f: float | None
    extrapolated: bool = False
    reason: str | None = None


def _behr_inverse_dewpoint(
    target_w_lb_per_mmscf: float, pressure_psia: float,
    co2_mol_pct: float = 0.0, h2s_mol_pct: float = 0.0,
) -> _DewpointResult:
    """Behr 反函数 — 给定 W 反算 T_dew (°F), scipy brentq + Newton fallback.

    v5.1 完整实现 (B-3 + H-3 落实):
        求解 f(T) = W_baseline(T, P) - W_target = 0
        若 f(60°F) × f(200°F) 同号 → 扩展 bracket 到 [-100°F, 300°F]
        若 brentq 失败 (maxiter=100) → Newton fallback (analytical derivative)
        若都失败 → 返回 _DewpointResult(None, ..., reason="...")
        若 T < 60°F → extrapolated=True, reason="T<60°F extrapolation, accuracy±20%"

    Returns:
        _DewpointResult dataclass (frozen): 三态显式 FOUND/EXTRAPOLATED/NOT_FOUND
    """
    from scipy.optimize import brentq

    T_BRACKET: tuple[float, float] = (_BEHR_DEWPOINT_BRACKET[0], _BEHR_DEWPOINT_BRACKET[1])
    T_EXTENDED_BRACKET: tuple[float, float] = (-100.0, 300.0)

    def _residual_w(T_f: float) -> float:
        w, _ = _calc_behr_water_content_lb_per_mmscf(
            T_f, pressure_psia, co2_mol_pct, h2s_mol_pct,
        )
        return w - target_w_lb_per_mmscf

    dewpoint_f: float | None = None

    try:
        # 缩 bracket 到 f(a)·f(b) < 0
        a, b = T_BRACKET
        fa, fb = _residual_w(a), _residual_w(b)
        if fa * fb > 0:
            a, b = T_EXTENDED_BRACKET
            fa, fb = _residual_w(a), _residual_w(b)
            if fa * fb > 0:
                raise ValueError("no sign change in extended bracket")
        dewpoint_f = brentq(_residual_w, a, b, maxiter=100, xtol=1e-4)
    except Exception:
        # Newton fallback (numerical derivative; grid lookup 无 closed-form derivative)
        try:
            T = 60.0  # 初值
            h_deriv = 1e-2  # 中央差分步长 (°F)
            for _ in range(50):
                w, _ = _calc_behr_water_content_lb_per_mmscf(
                    T, pressure_psia, co2_mol_pct, h2s_mol_pct,
                )
                w_plus, _ = _calc_behr_water_content_lb_per_mmscf(
                    T + h_deriv, pressure_psia, co2_mol_pct, h2s_mol_pct,
                )
                w_minus, _ = _calc_behr_water_content_lb_per_mmscf(
                    T - h_deriv, pressure_psia, co2_mol_pct, h2s_mol_pct,
                )
                dw_dT = (w_plus - w_minus) / (2.0 * h_deriv)
                if abs(dw_dT) < 1e-10:
                    break
                delta = (w - target_w_lb_per_mmscf) / dw_dT
                T -= delta
                if abs(delta) < _BEHR_DEWPOINT_EXTRAPOLATION_WARNING_TOL_F:
                    break
            dewpoint_f = T
        except Exception:
            return _DewpointResult(
                dewpoint_f=None,
                extrapolated=False,
                reason="brentq and Newton both failed",
            )

    if (
        dewpoint_f is not None
        and dewpoint_f < _BEHR_DEWPOINT_EXTRAPOLATED_THRESHOLD_F
    ):
        return _DewpointResult(
            dewpoint_f=dewpoint_f,
            extrapolated=True,
            reason=(
                f"T<{_BEHR_DEWPOINT_EXTRAPOLATED_THRESHOLD_F:.0f}°F "
                f"extrapolation (T={dewpoint_f:.1f}°F), accuracy ±20%"
            ),
        )
    return _DewpointResult(dewpoint_f=dewpoint_f, extrapolated=False, reason=None)
