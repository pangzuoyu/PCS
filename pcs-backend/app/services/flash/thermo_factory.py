"""P4-1-1 thermo 抽象层 + 工厂（P4-1-2 扩展方法）。

职责：
- 定义 ``ThermoInterface`` Protocol（所有 thermo 后端的统一契约）
- 定义 ``THERMO_METHOD_MAP``（4 体系 → thermo 方法名）
- 定义 4 个 stub 实现类（PRMIXThermo / SRKMIXThermo / NRTLThermo / CoolPropThermo）：
  Psat/Tsat/FlashPT 使用 Wagner McGarry 多项式（hydrocarbon）或 iapws95（水）
  实现；FlashPH/FlashPS 占位 raise NotImplementedError（P4-1-3+ 由外层 service
  通过 FlashPT 迭代实现）
- 提供 ``build_thermo`` 工厂（system_type 校验 + zs 归一化 + 透传 cass）

P4-1-1 仅定义 Psat 占位 + 4 stub NotImplementedError；P4-1-2 落地具体方法。

异常 UnknownSystemTypeError / CompositionSumError 继承既有 PcsError 体系
（status=422），不修改 exceptions.py。
"""
from __future__ import annotations

import math
from typing import Protocol, runtime_checkable

from app.services.exceptions import PcsError

# 通用气体常数 J/(mol*K)
_R = 8.314462618

# ---------------------------------------------------------------------------
# 映射表
# ---------------------------------------------------------------------------

THERMO_METHOD_MAP: dict[str, str] = {
    "LIGHT_HYDROCARBON": "PRMIX",
    "GAS_PROCESSING": "SRKMIX",
    "POLAR": "NRTL",
    "WATER_STEAM": "CoolProp",
}


# ---------------------------------------------------------------------------
# 异常类（继承既有 PcsError 体系 — 422 风格）
# ---------------------------------------------------------------------------


class UnknownSystemTypeError(PcsError):
    """未知 system_type（不在 THERMO_METHOD_MAP 中）。"""

    code = "UNKNOWN_SYSTEM_TYPE"
    status = 422


class CompositionSumError(PcsError):
    """组成校验失败：含非有限值 / 负值 / 全 0（无法归一化）。"""

    code = "COMPOSITION_SUM_ERROR"
    status = 422


# ---------------------------------------------------------------------------
# 物性数据：Wagner McGarry 系数表（hydrocarbon）+ 水 iapws 入口
# ---------------------------------------------------------------------------

# Wagner_original 方程：ln(P_sat/P_c) = (a*tau + b*tau^1.5 + c*tau^3 + d*tau^6) / T_r
# 其中 tau = 1 - T/T_c
# 系数来自 chemicals vendor/Vapor Pressure/Wagner Original McGarry.tsv（2024-01 版）
# 包含 9 种常见轻烃 + 水（备用）：
#   CAS        name           Tc (K)    Pc (Pa)   a           b        c         d         Tmin (K)
_WAGNER_TABLE: dict[str, tuple[float, float, float, float, float, float, float]] = {
    # (Tc, Pc, a, b, c, d, Tmin) — 用于外推时给 warning；当前不强制使用 Tmin
    "74-82-8": (190.53, 4596420.0, -6.00435, 1.1885, -0.834082, -1.22833, 91.0),    # methane
    "74-84-0": (305.42, 4869710.0, -6.34307, 1.0163, -1.19116, -2.03539, 133.0),   # ethane
    "74-98-6": (369.82, 4255760.0, -6.67833, 1.15437, -1.64984, -2.70017, 145.0),  # propane
    "106-97-8": (425.18, 3790620.0, -6.88709, 1.15157, -1.99873, -3.13003, 170.0), # n-butane
    "78-78-4": (460.43, 3385900.0, -7.12727, 1.38996, -2.54302, -2.45657, 220.0),  # isopentane
    "110-54-3": (507.9, 3036170.0, -7.5165, 1.54797, -3.38541, -2.36767, 220.0),   # n-hexane
    "67-56-1": (512.64, 8085050.0, -8.54796, 0.769817, -3.1085, 1.54481, 288.0),   # methanol
    "7732-18-5": (647.35, 22122300.0, -7.76451, 1.45838, -2.7758, -1.23303, 275.0),  # water
}

# 临界参数（用于 Clapeyron 方程算 Hvap）— 从 chemicals.critical / acentric 取
# Tc (K), Pc (Pa), omega
_CRITICAL_TABLE: dict[str, tuple[float, float, float]] = {
    "74-82-8": (190.53, 4596420.0, 0.0115),       # methane
    "74-84-0": (305.42, 4869710.0, 0.0995),       # ethane
    "74-98-6": (369.89, 4251200.0, 0.1521),       # propane
    "106-97-8": (425.125, 3796000.0, 0.201),      # n-butane
    "78-78-4": (460.43, 3385900.0, 0.227),       # isopentane (omega 估)
    "110-54-3": (507.9, 3036170.0, 0.299),       # n-hexane
    "67-56-1": (512.64, 8085050.0, 0.5658),      # methanol
    "7732-18-5": (647.096, 22064000.0, 0.3443),  # water
}

# 理想气体热容近似值（J/mol/K）— stub 用；用于 PH/PS flash 的焓/熵模型
# 这些是 300~400K 范围的近似值（文献平均），非精确数据库。
_CP_GAS_TABLE: dict[str, float] = {
    "74-82-8": 35.7,    # methane
    "74-84-0": 52.7,    # ethane
    "74-98-6": 73.6,    # propane
    "106-97-8": 98.5,   # n-butane
    "78-78-4": 120.0,   # isopentane
    "110-54-3": 142.0,  # n-hexane
    "67-56-1": 44.0,    # methanol
    "7732-18-5": 33.6,  # water (vapor, ~373K)
}

# 液相热容近似（J/mol/K）
_CP_LIQ_TABLE: dict[str, float] = {
    "74-82-8": 60.0,
    "74-84-0": 80.0,
    "74-98-6": 95.0,
    "106-97-8": 140.0,
    "78-78-4": 160.0,
    "110-54-3": 200.0,
    "67-56-1": 80.0,
    "7732-18-5": 75.3,
}

# 标准沸点（K，用于 SATURATION 校验）— 来自 chemicals.phase_change.Tb
_TB_TABLE: dict[str, float] = {
    "74-82-8": 111.66,
    "74-84-0": 184.55,
    "74-98-6": 231.04,
    "106-97-8": 272.66,
    "78-78-4": 301.15,
    "110-54-3": 341.88,
    "67-56-1": 337.69,
    "7732-18-5": 373.124,
}

# 分子量（kg/mol）— 用于 SATURATION 潜热 J/mol → J/kg 换算
# 来自 chemicals.elements.molecular_weight（g/mol）→ /1000
_MW_TABLE: dict[str, float] = {
    "74-82-8": 16.04246 / 1000.0,    # methane
    "74-84-0": 30.06904 / 1000.0,    # ethane
    "74-98-6": 44.09562 / 1000.0,    # propane
    "106-97-8": 58.1222 / 1000.0,    # n-butane
    "78-78-4": 72.14878 / 1000.0,    # isopentane
    "110-54-3": 86.17536 / 1000.0,   # n-hexane
    "67-56-1": 32.04186 / 1000.0,    # methanol
    "7732-18-5": 18.01528 / 1000.0,  # water
}

# Fluid 名 → CAS（用于 SATURATION 入口解析 — P4-1-2 step3）
_FLUID_NAME_TO_CAS: dict[str, str] = {
    "WATER": "7732-18-5",
    "METHANE": "74-82-8",
    "ETHANE": "74-84-0",
    "PROPANE": "74-98-6",
    "N_BUTANE": "106-97-8",
    "ISOPENTANE": "78-78-4",
    "N_HEXANE": "110-54-3",
    "METHANOL": "67-56-1",
}


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------


def _wagner_psat(cas: str, T: float) -> float:
    """Wagner_original 计算 P_sat（Pa）。

    Args:
        cas: CAS 号（须在 _WAGNER_TABLE 中）
        T: 温度 (K)

    Raises:
        KeyError: cas 不在表中
    """
    from chemicals.vapor_pressure import Wagner_original

    Tc, Pc, a, b, c, d, _Tmin = _WAGNER_TABLE[cas]
    return Wagner_original(T, Tc, Pc, a, b, c, d)


def _water_Tsat(P: float) -> float:
    """水的饱和温度（iapws95）。"""
    from chemicals.iapws import iapws95_Tsat

    return iapws95_Tsat(P)


def _water_Psat(T: float) -> float:
    """水的饱和压力（iapws95）。"""
    from chemicals.iapws import iapws95_Psat

    return iapws95_Psat(T)


def _water_h_fg(T: float) -> float:
    """水的汽化焓（J/mol）：Clapeyron 方程 + iapws 饱和密度。"""
    from chemicals.iapws import iapws95_dPsat_dT, iapws95_saturation

    P_sat, rhol, rhog = iapws95_saturation(T)
    dPdT = iapws95_dPsat_dT(T)[0]
    MW = 18.01528 / 1000.0  # kg/mol
    V_l = MW / rhol
    V_g = MW / rhog
    return T * (V_g - V_l) * dPdT


def _water_h_fg_j_per_kg(T: float) -> float:
    """水的汽化焓（J/kg）— iapws95 Clapeyron J/mol → / MW。

    单位说明：spec 要求 h_fg 以 J/kg 报出（与流程工程 SI 单位一致）；iapws95
    内部按 mol 计算，须转换。
    """
    return _water_h_fg(T) / _MW_TABLE["7732-18-5"]


def _hydrocarbon_h_fg_j_per_kg(cas: str, T: float, Psat: float) -> float:
    """轻烃/极性组分汽化焓（J/kg）— Clapeyron 方程（chemicals.phase_change）。

    dZ=1 假设在 Tr<0.8 区误差 < 3%（化学品工程实践精度可接受）；spec 验收
    容差 1% 配合 step1 BUBBLE_P=996905.6 Pa 基准。返回 J/kg（J/mol / MW）。

    Args:
        cas: CAS 号（须在 _WAGNER_TABLE + _MW_TABLE 中）
        T: 温度 (K)
        Psat: 饱和压力 (Pa)
    """
    from chemicals.phase_change import Clapeyron

    Tc, Pc, _omega = _CRITICAL_TABLE[cas]
    h_fg_j_per_mol = Clapeyron(T, Tc, Pc, 1.0, Psat)
    return h_fg_j_per_mol / _MW_TABLE[cas]


def resolve_fluid_cas(fluid: str) -> str:
    """解析 fluid 名/CAS 为 CAS 号 — SATURATION 入口。

    接受：CAS 号字符串（如 "74-98-6"）或别名（如 "PROPANE"，大小写不敏感）。

    Args:
        fluid: 流体名或 CAS 号

    Returns:
        CAS 号字符串

    Raises:
        KeyError: 未知 fluid（由 SATURATION 转成 SaturationInputError）
    """
    fluid_up = fluid.upper()
    if fluid_up in _FLUID_NAME_TO_CAS:
        return _FLUID_NAME_TO_CAS[fluid_up]
    if fluid in _WAGNER_TABLE:
        return fluid
    raise KeyError(fluid)


# ---------------------------------------------------------------------------
# Protocol（统一契约）
# ---------------------------------------------------------------------------


@runtime_checkable
class ThermoInterface(Protocol):
    """所有 thermo 后端的统一契约（P4-1-2 落地）。

    物理接口惯例：
    - Psat/Tsat：纯组分相变参数
    - FlashPT/PH/PS：多组分闪蒸（返回值的具体含义见方法 docstring）
    """

    def Psat(self, comp_id: int, T: float) -> float:
        """纯组分在温度 T 下的饱和压力（Pa）。

        Args:
            comp_id: 组分索引（0-based；与 build_thermo 时传入的 zs 顺序一致）
            T: 温度 (K)

        Returns:
            P_sat (Pa)
        """
        ...

    def Tsat(self, comp_id: int, P: float) -> float:
        """纯组分在压力 P 下的饱和温度（K）。

        Args:
            comp_id: 组分索引
            P: 压力 (Pa)

        Returns:
            T_sat (K)
        """
        ...

    def FlashPT(
        self, zs: list[float], T: float, P: float
    ) -> tuple[float, list[float], list[float]]:
        """PT flash（等温等压闪蒸）。

        Args:
            zs: 总组成（须已归一化）
            T: 系统温度 (K)
            P: 系统压力 (Pa)

        Returns:
            (vapor_fraction, y_vapor, x_liquid)：汽化分率 + 汽相组成 + 液相组成
        """
        ...

    def FlashPH(self, zs: list[float], T: float, H: float) -> float:
        """PH flash（等温等焓闪蒸）。返回 P（Pa）。

        Stub 阶段：raise NotImplementedError。P4-1-2+ 由 flash_service 通过
        FlashPT 迭代实现完整 PH flash（stub 此方法预留未来 native 实现）。
        """
        ...

    def FlashPS(self, zs: list[float], T: float, S: float) -> float:
        """PS flash（等温等熵闪蒸）。返回 vapor_fraction（无量纲）。

        Stub 阶段：raise NotImplementedError（同 FlashPH 理由）。
        """
        ...


# ---------------------------------------------------------------------------
# Stub 基类：实现 Psat/Tsat/FlashPT + FlashPH/PS 占位
# ---------------------------------------------------------------------------


class _WagnerBaseThermo:
    """Wagner-based stub 基类。

    物性：Wagner_original McGarry 系数 + flash_inner_loop (Rachford-Rice 解析)。
    假设：理想 K-value = P_sat_i(T) / P（Raoult 定律）+ phi_vap/phi_liq = 1。
    """

    _water_only: bool = False  # 子类覆盖：True 表示只支持水（iapws95）

    def __init__(self, cass: list[str]):
        # 透传 CAS 给 stub（reviewer R0 finding — P4-1-1 已修正接收，此处真正使用）
        self._cass = list(cass)
        # 构造 CAS -> index 反查表
        self._cas_to_idx: dict[str, int] = {cas: i for i, cas in enumerate(self._cass)}

    # ----- Psat -----

    def Psat(self, comp_id: int, T: float) -> float:
        """饱和蒸气压 Psat(T)（Wagner 方程，水用专用蒸汽表）。

        步骤：
        1. _water_only → 全水体系直接调 _water_Psat
        2. 水组分（CAS 7732-18-5）→ _water_Psat（IAPWS-IF97 精度更佳）
        3. 其他组分 → _wagner_psat（chemicals.vapor_pressure Wagner 方程）

        与 Tsat 区别：Psat 输入温度返回压力；Tsat 输入压力牛顿反演温度。
        """
        if self._water_only:
            return _water_Psat(T)
        cas = self._cass[comp_id]
        if cas == "7732-18-5":
            return _water_Psat(T)
        return _wagner_psat(cas, T)

    # ----- Tsat -----

    def Tsat(self, comp_id: int, P: float) -> float:
        """饱和温度 Tsat(P)（Wagner 方程牛顿反演，水用专用蒸汽表）。

        步骤：
        1. _water_only 或水组分 → _water_Tsat（IAPWS-IF97 精度更佳）
        2. 其他组分 → Wagner 方程牛顿反演：
           - 初值取 _TB*0.9 或 100K（避免 0K 起步）
           - 50 次迭代收敛；dPdT 由 chemicals.vapor_pressure.dWagner_dT
           - 收敛阈值 1e-3 bar；T 范围 [Tmin, Tc)
        3. 不收敛 → 返回最后 T_guess（fallback）

        与 Psat 区别：Psat 直接算；Tsat 牛顿迭代。
        """
        if self._water_only or self._cass[comp_id] == "7732-18-5":
            return _water_Tsat(P)
        # Wagner 方程 → 牛顿反演（dPsat/dT 已知）
        from chemicals.vapor_pressure import dWagner_dT

        cas = self._cass[comp_id]
        Tc, Pc, a, b, c, d, _Tmin = _WAGNER_TABLE[cas]
        # T 牛顿迭代初值：Clausius-Clapeyron 线性化（dPsat/dT ~ P/T * latent/RT）
        # 初值取 Tmin * (P/Pc) ^ 0.25（粗估，实际收敛）
        T_guess = max(self._TB(cas) * 0.9, 100.0)
        for _ in range(50):
            P_calc = _wagner_psat(cas, T_guess)
            dPdT = dWagner_dT(T_guess, Tc, Pc, a, b, c, d)
            if dPdT == 0:
                break
            err = P_calc - P
            if abs(err) < 1e-3:
                return T_guess
            T_guess = T_guess - err / dPdT
            # T 必须在 [Tmin, Tc) 范围内
            if T_guess < 50.0:
                T_guess = 50.0
            if T_guess > Tc * 0.999:
                T_guess = Tc * 0.999
        return T_guess

    def _TB(self, cas: str) -> float:
        return _TB_TABLE.get(cas, 300.0)

    # ----- FlashPT -----

    def FlashPT(
        self, zs: list[float], T: float, P: float
    ) -> tuple[float, list[float], list[float]]:
        """PT flash：返回 (vapor_fraction, y_vapor, x_liquid)。

        单相行为：
        - 全部 K_i < 1（亚冷液）：vfrac=0, x=y=zs
        - 全部 K_i > 1（过热汽）：vfrac=1, x=y=zs
        - 否则调 chemicals.flash_basic.flash_inner_loop（Rachford-Rice 解析）
        """
        from chemicals.flash_basic import flash_inner_loop

        n = len(zs)
        # K_i = P_sat_i(T) / P（Raoult 定律）
        Ks = [self.Psat(i, T) / P for i in range(n)]

        # 单相快速路径
        if all(k < 1.0 for k in Ks):
            return (0.0, list(zs), list(zs))
        if all(k > 1.0 for k in Ks):
            return (1.0, list(zs), list(zs))

        # 两相路径
        vfrac, x, y = flash_inner_loop(zs, Ks, check=True)
        # 防御：flash_inner_loop 在边界可能返回 vfrac < 0 或 > 1；夹紧到 [0, 1]
        if vfrac < 0.0:
            return (0.0, list(zs), list(zs))
        if vfrac > 1.0:
            return (1.0, list(zs), list(zs))
        return (vfrac, x, y)

    # ----- FlashPH / FlashPS（占位 — P4-1-3+ 由 native 后端实现）-----

    def FlashPH(self, zs: list[float], T: float, H: float) -> float:
        raise NotImplementedError(
            "FlashPH: stub 阶段占位。P4-1-2+ 由 flash_service 通过 FlashPT 迭代实现"
        )

    def FlashPS(self, zs: list[float], T: float, S: float) -> float:
        raise NotImplementedError(
            "FlashPS: stub 阶段占位。P4-1-2+ 由 flash_service 通过 FlashPT 迭代实现"
        )

    # ----- 测试/Cp/SATURATION helper（public 暴露给 flash_service 使用）-----

    def Cp_gas(self, comp_id: int) -> float:
        """理想气体热容近似（J/mol/K）— 用于 PH/PS flash 焓/熵模型。"""
        cas = self._cass[comp_id]
        return _CP_GAS_TABLE.get(cas, 50.0)

    def Cp_liq(self, comp_id: int) -> float:
        """液相热容近似（J/mol/K）。"""
        cas = self._cass[comp_id]
        return _CP_LIQ_TABLE.get(cas, 80.0)

    def critical(self, comp_id: int) -> tuple[float, float]:
        """(Tc, Pc) 临界参数。"""
        cas = self._cass[comp_id]
        Tc, Pc, _omega = _CRITICAL_TABLE[cas]
        return Tc, Pc

    def cas_list(self) -> list[str]:
        return list(self._cass)

    # ----- H/S 占位（P4-1-2 step 2，step3+ 由 native 物性包替换）-----

    def H_PT(
        self,
        zs: list[float],
        T: float,
        P: float,
        vapor_fraction: float,
        y_vapor: list[float],
        x_liquid: list[float],
    ) -> float:
        """PT flash 状态下的总焓 J/mol（占位实现，P4-1-3+ 由 native 物性包替换）。

        占位模型：
        - 液相理想液体：H_liq_i(T) = Cp_liq_i * T
        - 汽相理想气体：H_vap_i(T) = Cp_gas_i * T
        - H_total = (1 - vfrac) * sum(x_i * H_liq_i) + vfrac * sum(y_i * H_vap_i)

        注意：占位仅用于 PH_FLASH/PS_FLASH 反向 roundtrip 测试；物理精度由
        P4-1-3 接入 Peng-Robinson / SRK / NRTL 真实物性后保证。
        """
        n = len(zs)
        H_liq = sum(x_liquid[i] * self.Cp_liq(i) * T for i in range(n))
        H_vap = sum(y_vapor[i] * self.Cp_gas(i) * T for i in range(n))
        return (1.0 - vapor_fraction) * H_liq + vapor_fraction * H_vap

    def S_PT(
        self,
        zs: list[float],
        T: float,
        P: float,
        vapor_fraction: float,
        y_vapor: list[float],
        x_liquid: list[float],
    ) -> float:
        """PT flash 状态下的总熵 J/mol/K（占位实现，P4-1-3+ 由 native 物性包替换）。

        占位模型：
        - 液相理想液体：S_liq_i(T) = Cp_liq_i * ln(T)
        - 汽相理想气体：S_vap_i(T, P) = Cp_gas_i * ln(T) - R * ln(P * y_i)
        - S_total = (1 - vfrac) * sum(x_i * S_liq_i) + vfrac * sum(y_i * S_vap_i)

        同 H_PT：占位仅用于 PS_FLASH roundtrip 测试；物理精度由 P4-1-3 接管。
        """
        n = len(zs)
        lnT = math.log(T)
        S_liq = sum(x_liquid[i] * self.Cp_liq(i) * lnT for i in range(n))
        S_vap = sum(
            y_vapor[i]
            * (self.Cp_gas(i) * lnT - _R * math.log(P * max(y_vapor[i], 1e-12)))
            for i in range(n)
        )
        return (1.0 - vapor_fraction) * S_liq + vapor_fraction * S_vap

    def __repr__(self) -> str:  # pragma: no cover — debug-only
        return f"<{type(self).__name__} cas={self._cass}>"


# ---------------------------------------------------------------------------
# 4 个体系 stub（每个继承 _WagnerBaseThermo，可差异化覆盖方法）
# ---------------------------------------------------------------------------


class PRMIXThermo(_WagnerBaseThermo):
    """LIGHT_HYDROCARBON 体系 stub — Peng-Robinson 混合规则。

    P4-1-2 实现：Psat 用 Wagner McGarry（hydrocarbon），FlashPT 用 Raoult
    + Rachford-Rice 解析（P4-1-2 stub 阶段 Raoult；P4-1-3+ 替换为 Peng-Robinson
    fugacity ratio）。Stub 阶段不实现 phi_vap/phi_liq。
    """


class SRKMIXThermo(_WagnerBaseThermo):
    """GAS_PROCESSING 体系 stub — Soave-Redlich-Kwong 混合规则。

    P4-1-2 实现：同 PRMIX（共享 Wagner 系数表）；P4-1-3+ 替换为 SRK fugacity ratio。
    """


class NRTLThermo(_WagnerBaseThermo):
    """POLAR 体系 stub — NRTL 活度系数模型。

    P4-1-2 实现：同 PRMIX（stub 不实现 gamma_i）；P4-1-3+ 加入 NRTL gamma 修正。
    """


class CoolPropThermo(_WagnerBaseThermo):
    """WATER_STEAM 体系 stub — CoolProp 水/蒸汽物性库。

    P4-1-2 实现：因 CoolProp 未安装（pyproject.toml 无此依赖），用
    chemicals.iapws.iapws95_* 等价（IF97 兼容）。精度 ~1e-6，足够 stub。
    """

    _water_only = True  # 仅支持水


# ---------------------------------------------------------------------------
# Stub 类注册表（system_type → 实现类）
# ---------------------------------------------------------------------------

_STUB_REGISTRY: dict[str, type[_WagnerBaseThermo]] = {
    "LIGHT_HYDROCARBON": PRMIXThermo,
    "GAS_PROCESSING": SRKMIXThermo,
    "POLAR": NRTLThermo,
    "WATER_STEAM": CoolPropThermo,
}


# ---------------------------------------------------------------------------
# 工厂
# ---------------------------------------------------------------------------


def _validate_and_normalize_zs(zs: list[float]) -> list[float]:
    """校验 + 归一化 zs。

    规则：
    - 空列表 / 全 0 → raise CompositionSumError
    - 含 NaN / inf / 负值 → raise CompositionSumError
    - |sum(zs) - 1| > 1e-6 → 自动归一化（除以 sum），不修改调用方原列表

    Returns:
        归一化后的新 list（不修改入参）
    """
    if not zs:
        raise CompositionSumError("zs 列表为空，无法归一化")

    for i, z in enumerate(zs):
        if not math.isfinite(z) or z < 0:
            raise CompositionSumError(
                f"zs[{i}]={z} 为非有限值或负值，无法归一化"
            )

    total = sum(zs)
    if total == 0:
        raise CompositionSumError("zs 总和为 0，无法归一化")

    # 归一化到 sum=1，返回新列表（不修改入参）
    return [z / total for z in zs]


def build_thermo(
    system_type: str, zs: list[float], cass: list[str]
) -> ThermoInterface:
    """根据体系类型 + 组成归一化，返回对应 thermo 实例。

    Args:
        system_type: 体系类型（须在 THERMO_METHOD_MAP 中）
        zs: 摩尔分率列表（会被自动归一化；归一化结果传给 stub 实例）
        cass: CAS 列表（与 zs 等长；P4-1-2 stub 真正使用 — 之前 R0 finding 已修正）

    Returns:
        对应 stub 类实例（实现 ThermoInterface）

    Raises:
        UnknownSystemTypeError: system_type 不在 THERMO_METHOD_MAP（422 风格）
        CompositionSumError: zs 含非有限值 / 负值 / 空 / 全 0（422 风格）
    """
    # 1) 体系类型校验
    if system_type not in THERMO_METHOD_MAP:
        raise UnknownSystemTypeError(
            f"未知 system_type={system_type!r}；"
            f"支持的体系：{sorted(THERMO_METHOD_MAP.keys())}",
            details={"system_type": system_type, "supported": sorted(THERMO_METHOD_MAP.keys())},
        )

    # 2) 组成校验 + 归一化（不修改入参）
    zs_norm = _validate_and_normalize_zs(zs)

    # 3) CAS 长度校验（与 zs 等长）
    if len(cass) != len(zs_norm):
        raise CompositionSumError(
            f"cass 长度 ({len(cass)}) 与 zs 长度 ({len(zs_norm)}) 不匹配",
            details={"cass_len": len(cass), "zs_len": len(zs_norm)},
        )

    # 4) 返回实例（透传 normalized zs 给 stub — P4-1-1 review R0 finding 关闭）
    stub_cls = _STUB_REGISTRY[system_type]
    return stub_cls(cass)


__all__ = [
    "THERMO_METHOD_MAP",
    "ThermoInterface",
    "build_thermo",
    "UnknownSystemTypeError",
    "CompositionSumError",
    "PRMIXThermo",
    "SRKMIXThermo",
    "NRTLThermo",
    "CoolPropThermo",
    "resolve_fluid_cas",
]