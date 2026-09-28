"""水合物抑制（SPEC §3.9.4 V1.8）。

按 SPEC §3.9.4 V1.1 计算水合物抑制：

Hammerschmidt 1934 温降公式：
  ΔT = K·X / (M·(1-X))
  X = 抑制剂在水溶液中的质量分数（0..1）
  K = 温降常数（无量纲；H-2 v1 BLOCKER 锁定 5 种文献值）
  M = 抑制剂分子量（g/mol）

K 因子（按文献，H-2 v1 修定）：
  MEOH = 2335
  EG (MEG) = 2220
  DEG = 2335
  TEG = 2500
  NACL = 1297

Nielsen 1988 现代水合物抑制（备选 path，P6-6B T8 引入）：
  ΔT_F = A + B·x
  x = 抑制剂在水溶液中的摩尔分数（0..1）
  A/B/C 常数按组分（CH4/C2H6/C3H8/I-C4H6/N2/CO2/H2S）从
  ``compound_nielsen_1988_params`` 表加载；C 常数未启用，记 0.0。

GPSA §20.3 抑制剂注入率：
  Q_inhib (lb/d) = Q_gas · (W_inlet - W_target) / X_inhib
  Q_inhib (gal/d) = Q_inhib (lb/d) / ρ_inhib (lb/gal)

单位约定：

  - SI 基准（imperial_units=False default，L-3 v1 BLOCKER 修定）
  - imperial_units=True → dual-unit 输出（hydrate_depression_f + injection_rate_gal_d）

冻结接口（A1-A4 + B1-B5 + C1 批次一致性）：

  - dataclass(frozen=True)：Input + Result
  - PcsError 子类（code/status 字段）
  - formula_ref dict 标注公式来源（Hammerschmidt 1934 + GPSA §20.3）

边界拒绝（F2 / F5）：

  - gas_flow_mmscfd ≤ 0 → HydrateInhibitionError
  - operating_pressure_psia ≤ 0 → HydrateInhibitionError
  - inhibitor_concentration_in_water_wt_pct ∉ (0, 100) → HydrateInhibitionError
  - 温度字段未验证（仅用于结果 docstring；公式不依赖温度）

物理范围（H-2 v1）：

  - ΔT > 0 → is_safe=True（温降为正即有效抑制）

InhibitorModel（P6-6B T8）：默认 ``HAMMERSCHMIDT_1934``（向后兼容）；
``NIELSEN_1988`` 为现代水合物抑制备选 path（需用户提供组分 ``x`` 摩尔分数，
本批用 wt% 近似换算）。
"""
from __future__ import annotations

import enum
import logging
import warnings
from dataclasses import dataclass
from typing import Final, Literal

from app.services._compound_config_cache import (
    get_hammerschmidt_K_table,
    get_nielsen_1988_params,
)
from app.services.exceptions import PcsError

_LOGGER = logging.getLogger(__name__)

# Hammerschmidt 1934 K 因子（按文献；H-2 v1 BLOCKER 锁定）— DB fallback
_HAMMERSCHMIDT_K: Final[dict[str, float]] = {
    "MEOH": 2335.0,
    "EG": 2220.0,
    "DEG": 2335.0,
    "TEG": 2500.0,
    "NACL": 1297.0,
}


def _resolve_hammerschmidt_K() -> dict[str, float]:
    """5 min TTL 缓存加载 Hammerschmidt K 因子；DB 不可达时 fallback 到内联常量。"""
    db_table = get_hammerschmidt_K_table()
    return db_table if db_table else _HAMMERSCHMIDT_K


# Nielsen 1988 A/B/C 常数（7 组分估算值；待工艺工程师二次核对）— DB fallback
_NIELSEN_1988_PARAMS: Final[dict[str, tuple[float, float, float]]] = {
    "CH4":    (0.0227, 0.0067, 0.0),
    "C2H6":   (0.0250, 0.0080, 0.0),
    "C3H8":   (0.0270, 0.0095, 0.0),
    "I-C4H6": (0.0300, 0.0105, 0.0),
    "N2":     (0.0160, 0.0040, 0.0),
    "CO2":    (0.0200, 0.0055, 0.0),
    "H2S":    (0.0290, 0.0090, 0.0),
}


def _resolve_nielsen_1988_params() -> dict[str, tuple[float, float, float]]:
    """5 min TTL 缓存加载 Nielsen 1988 A/B/C 常数；DB 不可达时 fallback 到内联常量。"""
    db_table = get_nielsen_1988_params()
    return db_table if db_table else _NIELSEN_1988_PARAMS

# 抑制剂分子量（g/mol；MEOH=32.04 / EG=62.07 / DEG=106.12 / TEG=150.17 / NACL=58.44）
_INHIBITOR_MW: Final[dict[str, float]] = {
    "MEOH": 32.04,
    "EG": 62.07,
    "DEG": 106.12,
    "TEG": 150.17,
    "NACL": 58.44,
}

# 抑制剂密度（lb/gal；用于 lb/d → gal/d 换算）
# MEOH=6.63 / EG=9.26 / DEG=9.36 / TEG=9.35 / NaCl 饱和溶液≈10.5
_INHIBITOR_DENSITY_LB_PER_GAL: Final[dict[str, float]] = {
    "MEOH": 6.63,
    "EG": 9.26,
    "DEG": 9.36,
    "TEG": 9.35,
    "NACL": 10.5,
}

InhibitorType = Literal["MEOH", "EG", "DEG", "TEG", "NACL"]


class InhibitorModel(enum.Enum):
    """水合物抑制温降模型（P6-6B T8 引入）。

    - ``HAMMERSCHMIDT_1934``（默认，向后兼容 H-2 v1 BLOCKER）：
      ΔT_F = K·X / (M·(1-X))，K 从 ``compound_hammerschmidt_K`` 表加载。
    - ``NIELSEN_1988``（备选 path，P6-6B T8）：
      ΔT_F = A + B·x，A/B/C 从 ``compound_nielsen_1988_params`` 表加载；
      简化模型按 inhibitor 类型（CH4/C2H6/C3H8/I-C4H6/N2/CO2/H2S）选
      常数组；本批 A/B/C 为估算值，待工艺工程师二次核对。
    """

    HAMMERSCHMIDT_1934 = "HAMMERSCHMIDT_1934"
    NIELSEN_1988 = "NIELSEN_1988"


# Nielsen 1988 模型当前默认抑制剂的组分标识（MEOH → CH4 占主导近似）
# 本批简化用 dominant gas component = "CH4"；后续批次按气体组分输入扩展。
_NIELSEN_DEFAULT_COMPONENT: Final[str] = "CH4"


class HydrateInhibitionError(PcsError):
    """水合物抑制输入错误（F2 / F5 边界拒绝）。"""

    code = "HYDRATE_INHIBITION_INPUT_ERROR"
    status = 422


@dataclass(frozen=True)
class HydrateInhibitionInput:
    """水合物抑制输入。

    字段：
      gas_flow_mmscfd: 干气流量（MMscf/day）
      operating_pressure_psia: 操作压力（psia）
      operating_temperature_f: 操作温度（°F；仅用于记录）
      hydrate_inhibitor_type: 抑制剂类型（MEOH/EG/DEG/TEG/NACL）
      inhibitor_concentration_in_water_wt_pct: 抑制剂在水溶液中的质量分数（0..100 wt%）
      water_content_inlet_lb_per_mmscf: 入口水含量（lb water / MMscf dry gas）
      water_content_target_lb_per_mmscf: 目标出口水含量（lb water / MMscf dry gas）
      imperial_units: True → dual-unit 输出（hydrate_depression_f +
        injection_rate_gal_d）；False（默认，L-3 v1 BLOCKER 修定）→ SI 基准仅
    """

    gas_flow_mmscfd: float
    operating_pressure_psia: float
    operating_temperature_f: float
    hydrate_inhibitor_type: InhibitorType
    inhibitor_concentration_in_water_wt_pct: float
    water_content_inlet_lb_per_mmscf: float = 20.0
    water_content_target_lb_per_mmscf: float = 1.0
    imperial_units: bool = False  # L-3 v1 BLOCKER: SI base per Global Constraints


@dataclass(frozen=True)
class HydrateInhibitionResult:
    """水合物抑制结果。

    字段：
      hydrate_depression_f: Hammerschmidt 温降（°F；Hammerschmidt 1934 Eq；主输出）
      hydrate_depression_c: Hammerschmidt 温降（°C；= F × 5/9 派生）
      hydrate_depression_c_legacy: DEPRECATED 向后兼容（旧 `_c` 字段值实际就是 °F；
        新代码请使用 `hydrate_depression_f`；T10 路径 A，OPEN-P6-6A-3 真正关闭）
      inhibitor_injection_rate_gpd: 抑制剂注入率（gal/day；GPSA §20.3）
      inhibitor_injection_rate_lb_d: 抑制剂注入率（lb/day；GPSA §20.3）
      water_removed_lb_d: 水移除量（lb/day；= Q_gas·(W_inlet - W_target)）
      is_safe: 温降 > 0（True=安全抑制；False=无抑制效果）
      inhibitor_k_factor: 该抑制剂的 K 因子（无量纲）
      inhibitor_mw: 该抑制剂的分子量（g/mol）
      imperial_conversion: dual-unit 输出（仅 imperial_units=True）
      formula_ref: 公式引用（Hammerschmidt 1934 + GPSA §20.3）
    """

    hydrate_depression_f: float
    hydrate_depression_c: float
    hydrate_depression_c_legacy: float
    inhibitor_injection_rate_gpd: float
    inhibitor_injection_rate_lb_d: float
    water_removed_lb_d: float
    is_safe: bool
    inhibitor_k_factor: float
    inhibitor_mw: float
    imperial_conversion: dict[str, float] | None
    formula_ref: dict[str, str]


def _validate_input(inp: HydrateInhibitionInput) -> None:
    if inp.gas_flow_mmscfd <= 0:
        raise HydrateInhibitionError(f"Q_gas={inp.gas_flow_mmscfd} 必须 > 0")
    if inp.operating_pressure_psia <= 0:
        raise HydrateInhibitionError(
            f"operating_pressure_psia={inp.operating_pressure_psia} 必须 > 0"
        )
    if not (
        0.0
        < inp.inhibitor_concentration_in_water_wt_pct
        < 100.0
    ):
        raise HydrateInhibitionError(
            f"inhibitor_concentration_in_water_wt_pct="
            f"{inp.inhibitor_concentration_in_water_wt_pct} 必须在 (0, 100) wt%"
        )
    if inp.water_content_inlet_lb_per_mmscf < 0:
        raise HydrateInhibitionError("入口水含量必须 ≥ 0")
    if (
        inp.water_content_target_lb_per_mmscf
        > inp.water_content_inlet_lb_per_mmscf
    ):
        raise HydrateInhibitionError(
            "目标水含量必须 ≤ 入口水含量"
        )


def _calculate_nielsen_depression(
    component: str,
    inhibitor_wt_pct: float,
    inhibitor_mw: float,
) -> tuple[float, dict[str, tuple[float, float, float]]]:
    """Nielsen 1988 简化 ΔT_F 计算（C-18 备选 path；P6-6B T8 引入）。

    简化模型：ΔT_F = A + B·x
      - x = 抑制剂在水溶液中的 **摩尔分数**（本批按 wt% 近似换算
        x ≈ X_wt × MW_water / (X_wt × MW_water + (1 − X_wt) × MW_inhib)，
        MW_water=18.015 g/mol）；
      - A/B/C 常数从 ``compound_nielsen_1988_params`` 表加载（C 常数
        本批记 0.0，留待工艺工程师扩展完整 Nielsen 方程）。

    返回 ``(delta_t_f, params_table)``；后者供 formula_ref 引用。
    DB 加载失败由 ``_resolve_nielsen_1988_params`` fallback 到内联估算
    常量；fallback 触发 ``warnings.warn`` + 日志 WARNING。

    ⚠️ **简化模型**：A/B/C 为估算值（user ruling 2026-09-27），待工艺
    工程师从 Nielsen 1988 PDF 二次核对；本函数不替代完整 Nielsen 1988
    论文 Table 2-3 方程组。
    """
    params_table = _resolve_nielsen_1988_params()
    if component not in params_table:
        raise HydrateInhibitionError(
            f"Nielsen 1988 model 不支持的组分 '{component}'"
            f"；支持：{sorted(params_table.keys())}"
        )
    a, b, _c = params_table[component]
    # wt% → 摩尔分数近似（按 inhibitor MW 标定）
    x_wt = inhibitor_wt_pct / 100.0
    mw_water = 18.015
    x_mol = (
        (x_wt / inhibitor_mw)
        / ((x_wt / inhibitor_mw) + ((1.0 - x_wt) / mw_water))
    )
    delta_t_f = a + b * x_mol
    return delta_t_f, params_table


def calc_hydrate_inhibition(
    inp: HydrateInhibitionInput,
    *,
    inhibitor_model: InhibitorModel = InhibitorModel.HAMMERSCHMIDT_1934,
) -> HydrateInhibitionResult:
    """水合物抑制主计算入口。

    计算步骤：
      1. _validate_input 边界拒绝（F2/F5）
      2. 根据 ``inhibitor_model`` 选温降模型：
         - HAMMERSCHMIDT_1934（默认，H-2 v1 BLOCKER 向后兼容）：
           ΔT_F = K·X / (M·(1-X))，K = Hammerschmidt 1934 文献 °F 标度
         - NIELSEN_1988（P6-6B T8 备选 path）：
           ΔT_F = A + B·x，A/B 从 ``compound_nielsen_1988_params`` 表
           加载；DB 不可达 fallback 内联估算常量 + warnings.warn + WARNING 日志
      3. ΔT_C = ΔT_F × 5/9
      4. 水移除量 W_removed = Q_gas·(W_inlet - W_target)（lb/d）
      5. 注入率（lb/d）= W_removed / X_inhib（GPSA §20.3）
      6. 注入率（gal/d）= injection_lb_d / ρ_inhib（GPSA §20.3）
      7. 封装 result（imperial 双单位若启用）
    """
    _validate_input(inp)

    mw = _INHIBITOR_MW[inp.hydrate_inhibitor_type]
    rho = _INHIBITOR_DENSITY_LB_PER_GAL[inp.hydrate_inhibitor_type]

    X = inp.inhibitor_concentration_in_water_wt_pct / 100.0

    # C5: 5 min TTL cache 加载；DB 失败 fallback 到内联 _HAMMERSCHMIDT_K
    K_table = _resolve_hammerschmidt_K()

    if inhibitor_model == InhibitorModel.NIELSEN_1988:
        # DB fallback 到内联常量时发 WARNING（mirror Hammerschmidt fallback）
        if get_nielsen_1988_params() is None:
            warnings.warn(
                "Nielsen 1988 model: compound_nielsen_1988_params 表不可达，"
                "fallback 到内联估算 A/B/C 常量（待工艺工程师二次核对）",
                stacklevel=2,
            )
            _LOGGER.warning(
                "Nielsen 1988 fallback to inlined A/B/C constants (TBD engineer verify)"
            )
        delta_t_f, nielsen_params = _calculate_nielsen_depression(
            component=_NIELSEN_DEFAULT_COMPONENT,
            inhibitor_wt_pct=inp.inhibitor_concentration_in_water_wt_pct,
            inhibitor_mw=mw,
        )
        # Nielsen path 不依赖 Hammerschmidt K；K 报告为 -1 标记备用 path
        K_reported = -1.0
    else:
        # 1. Hammerschmidt 1934 ΔT（°F）= K·X / (M·(1-X))
        #    K 是 °F 标度（OPEN-P6-6A-3 fix；Hammerschmidt 1934 paper convention）
        K = K_table[inp.hydrate_inhibitor_type]
        delta_t_f = K * X / (mw * (1.0 - X))
        K_reported = K
        nielsen_params = None

    # 2. °F → °C
    delta_t_c = delta_t_f * 5.0 / 9.0

    # 3. 水移除量（lb/d）= Q_gas (MMscf/d) × (W_inlet - W_target) (lb/MMscf)
    water_removed_lb_d = inp.gas_flow_mmscfd * (
        inp.water_content_inlet_lb_per_mmscf
        - inp.water_content_target_lb_per_mmscf
    )

    # 4. 注入率（lb/d）= W_removed / X_inhib（GPSA §20.3）
    injection_lb_d = water_removed_lb_d / X
    # 5. 注入率（gal/d）= injection_lb_d / ρ_inhib
    injection_gpd = injection_lb_d / rho

    is_safe = delta_t_c > 0

    # 6. imperial dual-unit 输出（L-3 v1 BLOCKER：默认 False）
    imperial: dict[str, float] | None = None
    if inp.imperial_units:
        imperial = {
            "hydrate_depression_f": delta_t_f,
            "injection_rate_gal_d": injection_gpd,
        }

    # 7. formula_ref 依 inhibitor_model 拼接（P6-6B T8 双模型公式引用）
    if inhibitor_model == InhibitorModel.NIELSEN_1988:
        a, b, _c = nielsen_params[_NIELSEN_DEFAULT_COMPONENT] if nielsen_params else (0.0, 0.0, 0.0)
        formula_ref: dict[str, str] = {
            "inhibitor_model": (
                "Nielsen 1988 (备选 path；P6-6B T8 引入；估算 A/B/C，"
                "待工艺工程师二次核对)"
            ),
            "nielsen": (
                f"ΔT_F = A + B·x [Nielsen 1988 paper Table 1]"
                f"；component={_NIELSEN_DEFAULT_COMPONENT}"
                f" A={a} B={b}（无量纲）"
            ),
            "injection_rate": (
                "Q_inhib = Q_gas·(W_inlet - W_target)/C [GPSA §20.3]"
            ),
            "density": (
                f"ρ_inhib = {rho} lb/gal"
                f"（MEOH=6.63/EG=9.26/DEG=9.36/TEG=9.35/NACL=10.5）"
            ),
        }
    else:
        formula_ref = {
            "hammerschmidt": (
                "ΔT_F = K·X / (M·(1-X)) [Hammerschmidt 1934, K in °F scale]"
            ),
            "k_factor": (
                f"K = {K_reported} °F（OPEN-P6-6A-3: MEOH/DEG=2335; EG=2220; "
                f"TEG=2500; NACL=1297 — 文献 °F 标度）"
            ),
            "injection_rate": (
                "Q_inhib = Q_gas·(W_inlet - W_target)/C [GPSA §20.3]"
            ),
            "density": (
                f"ρ_inhib = {rho} lb/gal"
                f"（MEOH=6.63/EG=9.26/DEG=9.36/TEG=9.35/NACL=10.5）"
            ),
        }

    return HydrateInhibitionResult(
        hydrate_depression_f=delta_t_f,
        hydrate_depression_c=delta_t_c,
        hydrate_depression_c_legacy=delta_t_f,  # DEPRECATED: 旧 `_c` 字段值实际是 °F
        inhibitor_injection_rate_gpd=injection_gpd,
        inhibitor_injection_rate_lb_d=injection_lb_d,
        water_removed_lb_d=water_removed_lb_d,
        is_safe=is_safe,
        inhibitor_k_factor=K_reported,
        inhibitor_mw=mw,
        imperial_conversion=imperial,
        formula_ref=formula_ref,
    )


__all__ = [
    "HydrateInhibitionError",
    "HydrateInhibitionInput",
    "HydrateInhibitionResult",
    "InhibitorModel",
    "InhibitorType",
    "calc_hydrate_inhibition",
]