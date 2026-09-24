"""COOL_TOWER Merkel 方程 Chebyshev 4 点法求冷却数 KaV/L。

按 SPEC §3.2.4.1 P6-CT-001（Chebyshev 4 点法，CTI ATC-105 标准推荐）：
    ΔT = t1_c − t2_c
    Chebyshev 节点 T_i ∈ [−1, +1]（4 节点标准值）：
        T_1 = −0.794498   T_2 = −0.187985
        T_3 = +0.187985   T_4 = +0.794498
    映射到 [t2_c, t1_c]：T_water_i = t2_c + (T_i + 1) × ΔT / 2
    节点处 1 / (i_w − i_a)：i_w(T_water_i) − ia_kj_kg
        其中 i_w(T) = 1.005×T + ws(T) × (2501 + 1.88×T)  [kJ/kg dry air]
        ws(T) = 0.622 × p_ws(T) / (101325 − p_ws(T))  [kg water / kg dry air]
        p_ws(T) = 611.2 × exp(17.67×T / (T + 243.5))  [Pa, Magnus 公式]
        （0~50°C 范围 p_ws 误差 <1%；i_w 误差 <2%）
    KaV/L = (C_w / l_g_ratio) × (ΔT / 4) × Σ(i=1..4) 1 / (i_w(T_water_i) − ia_kj_kg)
        其中 C_w = 4.187 kJ/kg·K（水的比热）

注：i_w(T) 暂用 Magnus + 湿空气焓简化式（避免依赖 PSYCHRO CoolProp 完整库）；
Task 26 PSYCHRO persist + api 落地后可升级为 CoolProp HumidAir HA_enthalpy 调用。

不依赖 DB（纯计算函数）；输入 l_g_ratio 来自 Karoske 联动或上游工程参数。

手算校核（t1=40/t2=30/ia=80/l_g=1.0）：
    T_water_i 节点：31.0275 / 34.0601 / 35.9399 / 38.9725
    i_w 节点值：105.22 / 123.06 / 135.46 / 157.95（Magnus 0~50°C 误差 <2%）
    Σ 1/(i_w − ia) = 0.09373
    KaV/L = (4.187/1.0) × (10/4) × 0.09373 = 0.9811
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from app.services.exceptions import PcsError

# Chebyshev 4 节点 [−1, +1] 标准值（CTI ATC-105 推荐）
_CHEBYSHEV_4_NODES = (-0.794498, -0.187985, 0.187985, 0.794498)
_C_WATER = 4.187  # kJ/kg·K（水的比热，0~50°C 范围近似常数）
_P_ATM_PA = 101325.0  # Pa（标准大气压）


@dataclass(frozen=True)
class MerkelInput:
    """Merkel 方程输入。

    字段：
    - t1_c: 进水温度 °C（塔顶/热水端）
    - t2_c: 出水温度 °C（塔底/冷水端；t2_c < t1_c 物理上必须）
    - ia_kj_kg: 空气焓 kJ/kg dry air（沿塔近似恒定，工程简化）
    - l_g_ratio: 水气比 L/G（无量纲；默认 1.0）
    """

    t1_c: float  # °C
    t2_c: float  # °C
    ia_kj_kg: float  # kJ/kg dry air
    l_g_ratio: float = 1.0  # 水气比（无量纲）


@dataclass(frozen=True)
class MerkelResult:
    """Merkel 方程输出。

    字段：
    - kav_l: 冷却数 KaV/L（无量纲）
    - formula_ref: 公式溯源标记 "API_CTI_ATC-105_§3.2.4.1"
    """

    kav_l: float  # 冷却数（无量纲）
    formula_ref: str = "API_CTI_ATC-105_§3.2.4.1"


class MerkelInputError(PcsError):
    """Merkel 输入不合法（422）。

    触发场景：T1 <= T2 / ia < 0 / l_g_ratio <= 0 / 节点处 i_w(T) <= i_a
    （空气已饱和，物理上无法继续冷却）。
    """

    code = "MERKEL_INPUT_ERROR"
    status = 422


def _iw_sat_kj_kg(t_c: float) -> float:
    """饱和空气焓（kJ/kg dry air），Magnus + 湿空气焓简化式（0~50°C 误差 <2%）。

    公式：
        p_ws(T) = 611.2 × exp(17.67 × T / (T + 243.5))  [Pa]
        ws(T) = 0.622 × p_ws / (P_atm − p_ws)  [kg water / kg dry air]
        i_w(T) = 1.005 × T + ws × (2501 + 1.88 × T)

    Args:
        t_c: 水温 °C。

    Returns:
        饱和湿空气焓 kJ/kg dry air。
    """
    p_ws = 611.2 * math.exp(17.67 * t_c / (t_c + 243.5))
    ws = 0.622 * p_ws / (_P_ATM_PA - p_ws)
    return 1.005 * t_c + ws * (2501.0 + 1.88 * t_c)


def calc_merkel_kav_l(inp: MerkelInput) -> MerkelResult:
    """Chebyshev 4 点法求冷却数 KaV/L（CTI ATC-105）。

    实现步骤（SPEC §3.2.4.1）：
    1. 输入校验：T1 > T2 / ia ≥ 0 / l_g_ratio > 0
    2. ΔT = t1_c − t2_c
    3. 对 4 个 Chebyshev 节点 T_i 计算 T_water_i 并求 i_w(T_water_i) − ia
    4. 节点处差 ≤ 0 → 物理不合理（空气已饱和）→ 抛 MerkelInputError
    5. KaV/L = (C_w / l_g_ratio) × (ΔT / 4) × Σ 1/(i_w − i_a)

    Args:
        inp: MerkelInput（已冻结 dataclass）。

    Returns:
        MerkelResult（含 kav_l 与 formula_ref）。

    Raises:
        MerkelInputError: 输入字段越界或节点处空气已饱和（422）。
    """
    # 输入校验
    if inp.t1_c <= inp.t2_c:
        raise MerkelInputError(
            f"t1_c ({inp.t1_c}) 必须 > t2_c ({inp.t2_c})"
        )
    if inp.ia_kj_kg < 0:
        raise MerkelInputError(
            f"ia_kj_kg ({inp.ia_kj_kg}) 不能为负"
        )
    if inp.l_g_ratio <= 0:
        raise MerkelInputError(
            f"l_g_ratio ({inp.l_g_ratio}) 必须 > 0"
        )

    # Chebyshev 4 点法积分
    delta_t = inp.t1_c - inp.t2_c
    sum_term = 0.0
    for node in _CHEBYSHEV_4_NODES:
        t_water = inp.t2_c + (node + 1.0) * delta_t / 2.0
        iw = _iw_sat_kj_kg(t_water)
        diff = iw - inp.ia_kj_kg
        if diff <= 0:
            # i_w(T) <= i_a 表示该节点空气已饱和，无法继续冷却 → 物理上不合理
            raise MerkelInputError(
                f"节点 T={t_water:.2f}°C 处 i_w ({iw:.2f}) <= i_a "
                f"({inp.ia_kj_kg:.2f})：空气已饱和，物理上无法继续冷却"
            )
        sum_term += 1.0 / diff

    # KaV/L = (C_w / l_g_ratio) × (ΔT / 4) × Σ 1/(i_w − i_a)
    kav_l = (_C_WATER / inp.l_g_ratio) * (delta_t / 4.0) * sum_term
    return MerkelResult(kav_l=kav_l)


__all__ = [
    "MerkelInput",
    "MerkelResult",
    "MerkelInputError",
    "calc_merkel_kav_l",
]
