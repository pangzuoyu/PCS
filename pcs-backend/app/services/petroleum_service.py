# pcs-backend/app/services/petroleum_service.py
"""PetroleumService — 炼油馏分物性估算 + 虚拟组分切割（Task 1.9.3 / ADR-0019）。

关联式常数来源（执行者勿改数值）：
- RD80 广义式 θ = a·Tb(°R)^b·SG^c：Riazi & Daubert (1980) Hydrocarbon Processing 59:115；
  本文件常数为文献值，已对 n-癸烷（Tb 174.1°C/SG 0.73）数值验证。
- Kesler-Lee f0/f1：Lee & Kesler (1975) AIChE J 21:510（ω 与蒸汽压通用式）。
单位约定：入参/出参外部一律 °C、MPa；内部换算 °R、psia、bar。
"""
from __future__ import annotations

import math

from app.services.exceptions import PcsError

RD80_CONSTANTS: dict[str, dict[str, float]] = {
    # property: (a, b, c) — Tb 用 °R，结果单位见 _CONVERT
    "mw": {"a": 4.5673e-5, "b": 2.1962, "c": -1.0164},   # g/mol
    "tc": {"a": 24.078, "b": 0.58848, "c": 0.35936},      # °R
    "pc": {"a": 3.1228e9, "b": -2.3125, "c": 2.3201},     # psia
}

_SG_RANGE = (0.5, 1.2)
_TB_C_RANGE = (-100.0, 800.0)


def _f0(tr: float) -> float:
    return 5.92714 - 6.09648 / tr - 1.28862 * math.log(tr) + 0.169347 * tr**6


def _f1(tr: float) -> float:
    return 15.2518 - 15.6875 / tr - 13.4721 * math.log(tr) + 0.43577 * tr**6


class PetroleumService:
    @classmethod
    def _validate(cls, tb_c: float, sg: float) -> None:
        if not (_SG_RANGE[0] < sg < _SG_RANGE[1]):
            raise PcsError(f"SG 越界 {sg}（有效 {_SG_RANGE}）", code="PETRO_INVALID_SG", status=422)
        if not (_TB_C_RANGE[0] < tb_c < _TB_C_RANGE[1]):
            raise PcsError(
                f"Tb 越界 {tb_c}°C（有效 {_TB_C_RANGE}）", code="PETRO_INVALID_TB", status=422
            )

    @classmethod
    def estimate(cls, tb_c: float, sg: float) -> dict:
        """馏程沸点(°C) + 比重 → MW/Tc/Pc/ω/粘度（RD80 + Kesler-Lee + Twu-1985）。"""
        from chemicals.viscosity import Twu_1985_internal  # vendor（Task 1.9.0 接线）

        cls._validate(tb_c, sg)
        tb_r = (tb_c + 273.15) * 9.0 / 5.0
        mw = (RD80_CONSTANTS["mw"]["a"] * tb_r ** RD80_CONSTANTS["mw"]["b"]
              * sg ** RD80_CONSTANTS["mw"]["c"])
        tc_r = (RD80_CONSTANTS["tc"]["a"] * tb_r ** RD80_CONSTANTS["tc"]["b"]
                * sg ** RD80_CONSTANTS["tc"]["c"])
        pc_psia = (RD80_CONSTANTS["pc"]["a"] * tb_r ** RD80_CONSTANTS["pc"]["b"]
                   * sg ** RD80_CONSTANTS["pc"]["c"])
        tc_k = tc_r * 5.0 / 9.0
        pc_bar = pc_psia / 14.5038
        pc_mpa = pc_bar / 10.0
        tbr = (tb_c + 273.15) / tc_k
        omega = (math.log(1.01325 / pc_bar) - _f0(tbr)) / _f1(tbr)
        # 注意：Twu_1985_internal 入参/沸点单位为 °R
        # （Task 1.9.0 实证，vendor 源码 docstring 复现验证）
        nu_20 = Twu_1985_internal(T=293.15 * 1.8, Tb=(tb_c + 273.15) * 1.8, SG=sg)
        return {"tb_k": tb_c + 273.15, "mw": mw, "tc_k": tc_k, "pc_mpa": pc_mpa,
                "omega": omega, "nu_20c_cst": nu_20}

    @classmethod
    def vapor_pressure(cls, tb_c: float, sg: float, t_c: float) -> float:
        """Lee-Kesler：ln Pr = f0(Tr) + ω·f1(Tr)，返回 MPa。"""
        est = cls.estimate(tb_c, sg)
        tr = (t_c + 273.15) / est["tc_k"]
        if not (0.3 < tr < 1.0):
            raise PcsError(
                f"Tr={tr:.3f} 超出蒸汽压式适用域 (0.3,1.0)", code="PETRO_TR_RANGE", status=422
            )
        ln_pr = _f0(tr) + est["omega"] * _f1(tr)
        pr = math.exp(ln_pr)
        return pr * est["pc_mpa"]

    @classmethod
    def cut_pseudo_components(
        cls, t_start_c: float, t_end_c: float, *, cut_width_c: float = 25.0, sg: float | None = None
    ) -> list[dict]:
        """沸程切割（ADR-0019：默认 25°C/段，末段吸收余数）。

        sg 缺省 0.85（P2 简化：全段共用整体 SG；P3 向导可传分段 SG）。
        """
        if t_start_c >= t_end_c:
            raise PcsError("切割起点须小于终点", code="PETRO_BAD_RANGE", status=422)
        if cut_width_c <= 0:
            raise PcsError("切割宽度须 >0", code="PETRO_BAD_WIDTH", status=422)
        sg = 0.85 if sg is None else sg
        edges = []
        t = t_start_c
        while t < t_end_c - 1e-9:
            edges.append(t)
            t += cut_width_c
        edges.append(t_end_c)  # 末段吸收余数
        cuts = []
        for i in range(len(edges) - 1):
            mid = (edges[i] + edges[i + 1]) / 2.0
            cuts.append({
                "index": i, "tb_start_c": edges[i], "tb_end_c": edges[i + 1],
                "tb_mid_c": mid, "sg": sg, **cls.estimate(mid, sg),
            })
        return cuts
