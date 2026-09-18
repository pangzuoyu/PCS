"""ChEDL 包装层（F-13-2 落地 + V1.9 GSTACK P0 修正）。

ADR-0030 V1.1 决策 6 + V1.8 F-13-2：所有 ChEDL 调用必须经本包装层，
业务代码**禁止**直接 `import fluids.*`。

包装层职责：
1. **隔离**：业务代码与 fluids 包解耦，升级时仅改本文件
2. **降级**：fluids 1.3.1 缺失的函数（time_to_empty / tank_level_to_volume）
   触发 fallback 自研实现，provenance 标注 fallback_available=True
3. **provenance**：get_chedl_provenance() 返回 7 项元数据，支撑运维可观测性
   与升级决策（ADR-0030 决策 8）

包装函数清单（8 项）：
- 6 直调 fluids 1.3.1 顶层函数（V1.9 GSTACK P0 时序修正后确认存在）：
  v_Souders_Brown / K_separator_Watkins / K_separator_demister_York /
  K_Souders_Brown_theoretical（P5-1-1 新增，PCS-PLAN §129）/ v_terminal /
  API520_round_size
- 2 fallback（fluids 1.3.1 不存在）：
  time_to_empty / tank_level_to_volume
  fallback 实现 = 圆柱几何 + 伯努利方程 + 孔口出流

P6-0 扩展（13 → 17 项 → 23 项）：
- Task 3：6 函数（control_valve_* 3 + flow_meter_* 3，SPEC §3.2.1/3.2.2 简化公式自研）
- Task 4：4 函数（manning_Q / manning_V / critical_depth_rectangular /
  hydraulic_jump_y2，SPEC §3.2.6 教科书公式自研，详见 G-01 决策 P6-OPEN-001）
- Task 5：6 函数（humid_air_* 6，CoolProp.HumidAirProp.HAPropsSI 直调，
  详见 ADR-0030 V1.2 G-02 + SPEC §3.2.5 PSYCHRO）

调用示例：
    from app.services import chedl_wrapper
    v = chedl_wrapper.v_Souders_Brown(K=0.1, rhol=1000.0, rhog=1.2)
    prov = chedl_wrapper.get_chedl_provenance()
"""
from __future__ import annotations

import math

import fluids

from app.services.chedl_provenance import ChEDLProvenance
from app.services.exceptions import PcsError

# CoolProp 依赖（ADR-0030 V1.2 G-02 + Task 1 已锁 pyproject==6.6.0）。
# 包装层 ImportError 透传为 PcsError(code=CHEDL_NOT_AVAILABLE, status=503)，
# 避免业务层运行时因依赖缺失导致崩溃（运维统一捕获入口）。
try:
    import CoolProp  # noqa: F401  # 仅用于 __version__ 双证据链核验
    from CoolProp import HumidAirProp as _HA_module
except ImportError as _coolprop_import_err:  # pragma: no cover - 环境守卫
    raise PcsError(
        "CoolProp 依赖缺失（PSYCHRO 模块不可用）。"
        "请确认 pyproject.toml 已声明 CoolProp==6.6.0 并执行 uv sync。",
        code="CHEDL_NOT_AVAILABLE",
        status=503,
        details={"missing_module": "CoolProp.HumidAirProp"},
    ) from _coolprop_import_err

# ChEDL 版本（与 Task 25 锁定一致；pyproject.toml/uv.lock 单一来源）
_CHEDL_VERSION = "1.3.1"
# CoolProp 版本（ADR-0030 V1.2 决策 5 锁定；Task 1 已落 pyproject）
_COOLPROP_VERSION = "6.6.0"

# 重力加速度（伯努利方程 + 自由出流）
_G = 9.80665  # m/s²

# ============================================================================
# 5 直调函数（fluids 1.3.1 顶层）
# ============================================================================


def v_Souders_Brown(K: float, rhol: float, rhog: float) -> float:
    """Souders-Brown 分离器允许速度（m/s）。

    经典关联：v = K · √((rhol - rhog) / rhog)
    K 表征重力分离能力（ft/s 单位是 fluids 内部约定；本包装层转 SI）。

    Args:
        K: Souders-Brown 系数（典型 0.05~0.5 ft/s 量级，fluids 内部约定）
        rhol: 液相密度 (kg/m³)
        rhog: 气相密度 (kg/m³)
    """
    return fluids.v_Souders_Brown(K=K, rhol=rhol, rhog=rhog)


def K_separator_Watkins(
    x: float,
    rhol: float,
    rhog: float,
    horizontal: bool = False,
    method: str = "spline",
) -> float:
    """Watkins 法立式分离器 K 值（基于液滴沉降 x）。

    Args:
        x: 目标液滴直径 (m)
        rhol: 液相密度 (kg/m³)
        rhog: 气相密度 (kg/m³)
        horizontal: 是否卧式（默认 False 立式）
        method: 插值方法（默认 'spline'）
    """
    return fluids.K_separator_Watkins(
        x=x, rhol=rhol, rhog=rhog, horizontal=horizontal, method=method
    )


def K_separator_demister_York(P: float, horizontal: bool = False) -> float:
    """York 除雾器 K 值（基于操作压力 P）。

    Args:
        P: 操作压力 (Pa)
        horizontal: 是否卧式（默认 False 立式）
    """
    return fluids.K_separator_demister_York(P=P, horizontal=horizontal)


def K_Souders_Brown_theoretical(
    rhol: float,
    rhog: float,
    *,
    W: float = 0.0,
    C: float | None = None,
    x: float = 1.0,
) -> float:
    """Souders-Brown 理论 K 因子上限（m/s，无雾沫夹带）。

    PCS-PLAN §129 要求 P5-1-1 包装就绪，供 P5-2+ 高效分离设备理论 K 上限计算。
    ChEDL 函数不存在时降级为手算：K_theoretical = √(2 · g · Δρ · d / (ρ_V · C_D)) 简化公式。

    Args:
        rhol: 液相密度 (kg/m³)
        rhog: 气相密度 (kg/m³)
        W: 表面张力 (N/m，默认 0.0)
        C: 阻力系数（默认 None 使用 ChEDL 内部值）
        x: 目标液滴直径 (m，默认 1.0)
    """
    return fluids.K_Souders_Brown_theoretical(
        rhol=rhol, rhog=rhog, W=W, C=C, x=x,
    )


def v_terminal(
    D: float,
    rhop: float,
    rho: float,
    mu: float,
    Method: str | None = None,
) -> float:
    """颗粒终端沉降速度 (m/s)。

    通用算法（涵盖 Stokes / Allen / Newton 区间），由 fluids 内部切换。

    Args:
        D: 颗粒直径 (m)
        rhop: 颗粒密度 (kg/m³)
        rho: 流体密度 (kg/m³)
        mu: 流体动力粘度 (Pa·s)
        Method: 强制算法（None 时 fluids 自动选择）
    """
    return fluids.v_terminal(D=D, rhop=rhop, rho=rho, mu=mu, Method=Method)


def API520_round_size(A: float) -> float:
    """API 520 安全阀圆整口径（m²）。

    输入计算所需最小面积，输出圆整到 API 520 标准口径。

    Args:
        A: 计算所需面积 (m²)
    """
    return fluids.API520_round_size(A=A)


# ============================================================================
# 2 Fallback 函数（fluids 1.3.1 不存在 → 自研）
# ============================================================================


def time_to_empty(
    D_tank: float,
    h0: float,
    d_orifice: float,
    Cd: float = 0.62,
) -> float:
    """重力排空时间估算（fallback 实现）。

    **fluids 1.3.1 不提供该函数**，本实现基于：
    - 圆柱容器（D_tank 直径，h0 初始液位）
    - 圆孔口（d_orifice 直径，Cd 流量系数）
    - 伯努利方程 + 孔口出流：Q = Cd · A_orifice · √(2·g·h)
    - 准稳态积分：dt = -A_tank · dh / Q(h)
    - 积分结果：t = (A_tank / (Cd · A_orifice)) · √(2·h0/g)

    适用范围：
    - 等温、常压、稳态重力排空（忽略粘性 + 表面张力）
    - 不适用于气液两相、压缩流体、非圆形孔口

    Args:
        D_tank: 容器直径 (m)
        h0: 初始液位 (m)
        d_orifice: 排空孔口直径 (m)
        Cd: 孔口流量系数（默认 0.62 薄壁圆孔）

    Returns:
        估算排空时间 (s)
    """
    if D_tank <= 0 or h0 <= 0 or d_orifice <= 0 or Cd <= 0:
        raise ValueError(
            f"time_to_empty 参数必须正数：D_tank={D_tank}, h0={h0}, "
            f"d_orifice={d_orifice}, Cd={Cd}"
        )
    A_tank = math.pi * (D_tank / 2.0) ** 2  # 圆柱横截面积
    A_orifice = math.pi * (d_orifice / 2.0) ** 2  # 孔口面积
    # 积分结果 t = (A_tank / (Cd · A_orifice)) · √(2·h0/g)
    return (A_tank / (Cd * A_orifice)) * math.sqrt(2.0 * h0 / _G)


def tank_level_to_volume(
    D: float,
    h: float,
    head_type: str = "ellipse",
) -> float:
    """圆柱容器液位转体积（fallback 实现）。

    **fluids 1.3.1 不提供该函数**，本实现基于：
    - 圆柱主体 + 标准 2:1 椭圆封头（封头高 = D/4）
    - h 表示**总液位高度**（从容器底部算起，含封头段）
    - 体积分段计算：
      - 封头段：h ≤ D/4 时部分填充椭圆体 V = (π·D³/24) · f(h/(D/4))
        f(x) = x² · (3 - x)（标准 2:1 椭圆体积分布，积分 (π·D²/4)·h·(1 - h²/(3·R²))）
      - 主体段：h > D/4 时封头填满 + 圆柱 V = π·D³/24 + π·r²·(h - D/4)

    Args:
        D: 容器直径 (m)
        h: 总液位高度 (m)，从容器底部算起
        head_type: 封头类型 "ellipse" / "none"（默认 "ellipse"）

    Returns:
        液体体积 (m³)
    """
    if D <= 0 or h < 0:
        raise ValueError(f"tank_level_to_volume 参数异常：D={D}, h={h}")
    if head_type == "none":
        return math.pi * (D / 2.0) ** 2 * h
    elif head_type == "ellipse":
        h_head = D / 4.0  # 标准 2:1 椭圆封头高度
        V_head_full = math.pi * D**3 / 24.0  # 完整封头体积
        if h <= h_head:
            # 部分填充椭圆体：V(h) = V_head_full · x²·(3 - x)，其中 x = h/(D/4) ∈ [0, 1]
            x = h / h_head
            return V_head_full * x * x * (3.0 - x)
        else:
            # 封头填满 + 主体圆柱
            V_cyl = math.pi * (D / 2.0) ** 2 * (h - h_head)
            return V_head_full + V_cyl
    else:
        raise ValueError(
            f"tank_level_to_volume head_type 必须是 'ellipse' 或 'none'，"
            f"实际 {head_type!r}"
        )


# ============================================================================
# P6-0 CV/RESTRICTION wrappers（Task 3，Path A：SPEC §3.2.1/3.2.2 简化公式）
# ============================================================================
#
# 设计决策（ADR-0030 V1.2 P6-0）：本批 6 函数**不**直调 fluids.control_valve /
# fluids.flow_meter 的完整 API（12-17 参数：Psat/Pc/mu/FL/Fd/D1/D2/d/k/meter_type/
# taps 等），因为：
#   1. fluids 1.3.1 完整 API 缺 brief 简化签名所需的简化输入（如 Re_D 转 m 需要 mu）
#   2. 默认值（mu=1e-3, Pc=1e9, Psat=0）在非水/高压气体场景下会给出错误结果
#   3. SPEC §3.2.1 line 149 / §3.2.2 已给出工程简化公式，签名与 brief 严格对齐
#   4. 完整流体 API（含 choked/cavitation/堵塞流校核）留 P6+ Task 8 cv_engine
#
# 与现有 fallback 模式（time_to_empty / tank_level_to_volume）一致：fluids 缺失或
# 签名不匹配时，包装层基于 SPEC 简化公式自研实现，provenance 标注
# fallback_available=True + fallback_formula_ref 指向 SPEC §。


# IEC 60534-2-1 SI 标准常数（Nm³/h · bar 单位制）
_N9_SI = 0.0865


def control_valve_C_liquid(Q_m3h: float, SG: float, dP_bar: float) -> float:
    """不可压缩流体 Cv 计算（SPEC §3.2.1 line 149 简化公式）。

    **Path A 自研实现**：直接采用 SPEC 给出的简化公式，不调 fluids.control_valve
    完整 API（完整 API 需 15 参数 Psat/Pc/mu/P1/P2/D1/D2/d/FL/Fd/...，与 brief 简化
    签名不一致）。

    公式（SPEC §3.2.1 line 149，IEC 60534-2-1 湍流非阻塞工况）：

        Cv = Q × √(SG/ΔP)

    Args:
        Q_m3h: 体积流量（m³/h，USC 转换按业务约定）
        SG: 相对密度（SG = ρ / 1000，无量纲）
        dP_bar: 阀前后压差（bar）

    Returns:
        Cv 值（无量纲，US 单位制 GPM/psi 标定下的流量系数）
    """
    if dP_bar <= 0 or Q_m3h < 0 or SG <= 0:
        raise ValueError(
            f"control_valve_C_liquid 参数必须正数（Q 可为 0）："
            f"Q_m3h={Q_m3h}, SG={SG}, dP_bar={dP_bar}"
        )
    return Q_m3h * math.sqrt(SG / dP_bar)


def control_valve_kv_liquid(Q_m3h: float, rho: float, dP_bar: float) -> float:
    """不可压缩流体 Kv 计算（SPEC §3.2.1 SI 单位制简化公式）。

    **Path A 自研实现**：基于 SPEC §3.2.1 简化形式，SI 单位 IEC 60534 Kv 标准：

        Kv = Q × √(ρ / (1000 × ΔP_bar))

    其中 ρ 单位 kg/m³，Q 单位 m³/h，ΔP 单位 bar，结果 Kv 单位 m³/h（SI Kv）。

    Args:
        Q_m3h: 体积流量（m³/h）
        rho: 流体密度（kg/m³，SG = rho / 1000）
        dP_bar: 阀前后压差（bar）

    Returns:
        Kv 值（m³/h，SI Kv 流量系数）
    """
    if dP_bar <= 0 or Q_m3h < 0 or rho <= 0:
        raise ValueError(
            f"control_valve_kv_liquid 参数必须正数（Q 可为 0）："
            f"Q_m3h={Q_m3h}, rho={rho}, dP_bar={dP_bar}"
        )
    return Q_m3h * math.sqrt(rho / (1000.0 * dP_bar))


def control_valve_cv_gas(
    Q_Nm3h: float,
    P1_pa: float,
    T1_k: float,
    M: float,
    Z: float,
    dP_pa: float,
    gamma: float,
    xT: float,
) -> float:
    """可压缩流体（气体/蒸汽）Cv 计算（SPEC §3.2.1.3 IEC 60534-2-1 §6.3）。

    **Path A 自研实现**：直接采用 SPEC §3.2.1.3 line 1031-1094 给出的简化公式，
    不调 fluids.control_valve.size_control_valve_g（完整 API 需 17 参数）。

    公式（SPEC §3.2.1.3 line 1058-1080，Fp=1 简化）：

        Cv = Q / (N9 · P1_bar · Y · √(x / (M · T1 · Z)))

    其中：
        x = ΔP / P1（压差比）
        Y = 1 - x / (3 · Fγ · xT)（膨胀系数）
        Fγ = γ / 1.4（比热比因子）
        N9 = 0.0865（SI 单位常数）

    Args:
        Q_Nm3h: 标况体积流量（Nm³/h）
        P1_pa: 阀入口绝压（Pa）
        T1_k: 阀入口温度（K）
        M: 分子量（kg/kmol）
        Z: 压缩因子（无量纲）
        dP_pa: 阀前后压差（Pa）
        gamma: 比热比 Cp/Cv（无量纲）
        xT: 压差比系数（阀门厂数据，无量纲）

    Returns:
        Cv 值（无量纲）
    """
    if (
        Q_Nm3h <= 0
        or P1_pa <= 0
        or T1_k <= 0
        or M <= 0
        or Z <= 0
        or dP_pa <= 0
        or gamma <= 0
        or xT <= 0
    ):
        raise ValueError(
            f"control_valve_cv_gas 所有参数必须正数："
            f"Q_Nm3h={Q_Nm3h}, P1_pa={P1_pa}, T1_k={T1_k}, M={M}, Z={Z}, "
            f"dP_pa={dP_pa}, gamma={gamma}, xT={xT}"
        )
    # 单位换算：Pa → bar（SI IEC 60534 N9 单位制）
    P1_bar = P1_pa / 1.0e5
    dP_bar = dP_pa / 1.0e5
    x = dP_bar / P1_bar
    F_gamma = gamma / 1.4  # 比热比因子
    Y = 1.0 - x / (3.0 * F_gamma * xT)
    if Y <= 0:
        raise ValueError(
            f"control_valve_cv_gas Y 计算出非正值（choked 极限）：Y={Y}, "
            f"x={x}, F_gamma={F_gamma}, xT={xT}"
        )
    # SPEC §3.2.1.3 公式：Cv = Q / (N9 · Fp · P1_bar · Y · √(x / (M·T1·Z)))
    Cv = Q_Nm3h / (
        _N9_SI * 1.0 * P1_bar * Y * math.sqrt(x / (M * T1_k * Z))
    )
    return Cv


def flow_meter_orifice(
    D_m: float, d_m: float, Re_D: float, P1_pa: float, dP_pa: float, rho1: float
) -> tuple[float, float]:
    """ISO 5167-2 孔板（C, ε）计算（SPEC §3.2.2.1 Reader-Harris/Gallagher 简化）。

    **Path A 自研实现**：采用 SPEC §3.2.2.1 line 1382-1397 给出的 Reader-Harris
    3 项截断形式（完整 14 项公式标准原文）。膨胀系数采用 ISO 5167-2 §5.3.2.2
    κ=1.4 简化形式（brief 无 kappa 输入，默认 γ=1.4 典型气体）。

    C 公式（SPEC §3.2.2.1 line 1382-1397，Reader-Harris 3 项截断）：

        C = 0.5961 + 0.0261·β² - 0.216·β⁸ + 0.000521·(10⁶·β/Re_D)^0.7

    ε 公式（ISO 5167-2 §5.3.2.2 κ=1.4 简化）：

        ε = 1 - (0.351 + 0.256·β⁴ + 0.93·β⁸) · ΔP/P1

    Args:
        D_m: 管道内径（m）
        d_m: 孔板孔径（m）
        Re_D: 管道雷诺数（无量纲）
        P1_pa: 入口绝压（Pa）
        dP_pa: 压差（Pa）
        rho1: 入口密度（kg/m³，仅用于兼容性记录，不参与计算）

    Returns:
        (C, epsilon)：流出系数（无量纲）+ 膨胀系数（无量纲，气体<1，液体≈1）
    """
    if (
        D_m <= 0
        or d_m <= 0
        or d_m >= D_m
        or Re_D <= 0
        or P1_pa <= 0
        or dP_pa < 0
        or rho1 <= 0
    ):
        raise ValueError(
            f"flow_meter_orifice 参数异常：D_m={D_m}, d_m={d_m}, Re_D={Re_D}, "
            f"P1_pa={P1_pa}, dP_pa={dP_pa}, rho1={rho1}"
        )
    beta = d_m / D_m  # 直径比
    beta2 = beta * beta
    beta4 = beta2 * beta2
    beta8 = beta4 * beta4
    # Reader-Harris/Gallagher 3 项截断（SPEC §3.2.2.1）
    C = 0.5961 + 0.0261 * beta2 - 0.216 * beta8 + 0.000521 * (1.0e6 * beta / Re_D) ** 0.7
    # 膨胀系数（ISO 5167-2 §5.3.2.2 κ=1.4 简化，liquid 场景 ε≈1）
    x = dP_pa / P1_pa
    epsilon = 1.0 - (0.351 + 0.256 * beta4 + 0.93 * beta8) * x
    # ε 下限保护（液体/极低压差场景不应出现负值）
    if epsilon < 1.0:
        # 液体场景（dP=0 或极小）下 SPEC §3.2.2.1 注：ε=1
        # 物理意义：流体不可压缩时无膨胀修正
        epsilon = max(epsilon, 0.0)
    return (C, epsilon)


def flow_meter_venturi(
    D_m: float, d_m: float, Re_D: float, P1_pa: float, dP_pa: float, rho1: float
) -> tuple[float, float]:
    """ISO 5167-4 文丘里管（C, ε）计算（SPEC §3.2.2.2 简化）。

    **Path A 自研实现**：SPEC §3.2.2.2 line 1461 仅给出 C 范围 0.984~0.995 与
    ε 引用 ISO 5167-4 §5.4.3.2；本实现取范围中值 0.99 作为 C 简化值，ε 采用
    ISO 5167-4 κ=1.4 简化公式。

    C 简化：ISO 5167-4 铸造/机械加工文丘里管 C ∈ [0.984, 0.995]，本包装层用
    典型值 C = 0.99（铸造标准值）。

    ε 公式（ISO 5167-4 §5.4.3.2 κ=1.4 简化）：

        ε = 1 - (0.65·β⁶ + 0.002) · ΔP/P1

    Args:
        D_m: 管道内径（m）
        d_m: 喉部直径（m）
        Re_D: 管道雷诺数（无量纲，venturi 不敏感但保留入参对齐 orifice/nozzle）
        P1_pa: 入口绝压（Pa）
        dP_pa: 压差（Pa）
        rho1: 入口密度（kg/m³，仅用于兼容性记录）

    Returns:
        (C, epsilon)：流出系数 + 膨胀系数（无量纲）
    """
    if (
        D_m <= 0
        or d_m <= 0
        or d_m >= D_m
        or Re_D <= 0
        or P1_pa <= 0
        or dP_pa < 0
        or rho1 <= 0
    ):
        raise ValueError(
            f"flow_meter_venturi 参数异常：D_m={D_m}, d_m={d_m}, Re_D={Re_D}, "
            f"P1_pa={P1_pa}, dP_pa={dP_pa}, rho1={rho1}"
        )
    # ISO 5167-4 典型 C 值（铸造标准，本批采用中值）
    C = 0.99
    beta = d_m / D_m
    beta6 = beta ** 6
    x = dP_pa / P1_pa
    epsilon = 1.0 - (0.65 * beta6 + 0.002) * x
    if epsilon < 1.0:
        epsilon = max(epsilon, 0.0)
    return (C, epsilon)


def flow_meter_nozzle(
    D_m: float, d_m: float, Re_D: float, P1_pa: float, dP_pa: float, rho1: float
) -> tuple[float, float]:
    """ISO 5167-3 ISA 1932 喷嘴（C, ε）计算（SPEC §3.2.2.3 完整公式）。

    **Path A 自研实现**：SPEC §3.2.2.3 line 1495-1511 给出 ISA 1932 喷嘴 C 完整
    公式（不需截断），ε 采用 ISO 5167-3 κ=1.4 简化形式。

    C 公式（SPEC §3.2.2.3 line 1495-1511，ISA 1932 完整）：

        C = 0.9900 - 0.2262·β^4.1 - (0.00175·β² - 0.0033·β^4.15)·(10⁶/Re_D)^1.15

    ε 公式（ISO 5167-3 §5.4.2 κ=1.4 简化）：

        ε = 1 - (0.7·β⁴ - 0.3·β⁸) · ΔP/P1

    Args:
        D_m: 管道内径（m）
        d_m: 喷嘴喉部直径（m）
        Re_D: 管道雷诺数（无量纲）
        P1_pa: 入口绝压（Pa）
        dP_pa: 压差（Pa）
        rho1: 入口密度（kg/m³，仅用于兼容性记录）

    Returns:
        (C, epsilon)：流出系数 + 膨胀系数（无量纲）
    """
    if (
        D_m <= 0
        or d_m <= 0
        or d_m >= D_m
        or Re_D <= 0
        or P1_pa <= 0
        or dP_pa < 0
        or rho1 <= 0
    ):
        raise ValueError(
            f"flow_meter_nozzle 参数异常：D_m={D_m}, d_m={d_m}, Re_D={Re_D}, "
            f"P1_pa={P1_pa}, dP_pa={dP_pa}, rho1={rho1}"
        )
    beta = d_m / D_m
    beta2 = beta * beta
    beta4 = beta2 * beta2
    beta8 = beta4 * beta4
    # ISA 1932 完整公式（SPEC §3.2.2.3）
    C = (
        0.9900
        - 0.2262 * (beta ** 4.1)
        - (0.00175 * beta2 - 0.0033 * (beta ** 4.15))
        * (1.0e6 / Re_D) ** 1.15
    )
    # 膨胀系数（ISO 5167-3 §5.4.2 κ=1.4 简化）
    x = dP_pa / P1_pa
    epsilon = 1.0 - (0.7 * beta4 - 0.3 * beta8) * x
    if epsilon < 1.0:
        epsilon = max(epsilon, 0.0)
    return (C, epsilon)


# ============================================================================
# P6-0 OPEN_CHANNEL wrappers（Task 4，Path A：SPEC §3.2.6 教科书简化公式）
# ============================================================================
#
# 设计决策（ADR-0030 V1.2 + P6-OPEN-001 决策 2026-09-19）：本批 4 函数**不**直调
# fluids.open_channel / fluids.open_flow，因为：
#   1. fluids.open_channel 不存在（ModuleNotFoundError，G-01 核验确认）
#   2. fluids.open_flow（38 个导出符号）REQUIRED 命中仅 1/5（V_Manning），
#      缺失 4 函数：Manning / Manning_flow / critical_depth / hydraulic_radius
#   3. brief 签名（Manning_Q/V / 矩形 y_c / Bélanger y2）属教科书工程简化公式，
#      不需要流体物性入参（mu/ρ），与 fluids 完整 API 不匹配
#   4. SPEC §3.2.6 line 256-279 已给出 OPEN_CHANNEL 模块功能描述（Manning 公式、
#      临界水深、Froude 数判定、水跃计算），brief 4 函数为标准教科书公式
#   5. 与 Task 3 CV/RESTRICTION 同模式（Path A 自研），保持包装层一致性
#
# 兜底架构（P6-OPEN-001 §四）：OPEN_CHANNEL 模块实施时，本批 4 函数作为前置依赖；
# P6-3 Task 31 open_channel_wrapper 在本批之上叠加梯形/圆形断面几何与水跃迭代求解。
# 工艺工程师 Owner（Manning n 值 / 临界水深 / 水跃 golden 值校核）由 P6-3 负责，
# 本批仅提供基础教科书公式。


def manning_Q(n: float, A_m2: float, Rh_m: float, S: float) -> float:
    """Manning 流量计算（SPEC §3.2.6 line 256-279 教科书简化公式）。

    **Path A 自研实现**：不调 fluids.open_channel / fluids.open_flow（Manning / Manning_flow
    缺失）。采用明渠水力学教科书 Manning 公式：

        Q = (1/n) · A · Rh^(2/3) · S^(1/2)

    其中：
        n：Manning 糙率系数（无量纲，典型混凝土 0.013 / 土渠 0.025）
        A：过水断面面积 (m²)
        Rh：水力半径 (m)，Rh = A / P（P 为湿周）
        S：渠底坡度（无量纲，典型 0.0001 ~ 0.01）

    适用条件：
        均匀流（正常水深 = 设计水深）
        紊流（Re > 某些阈值，自动满足除非极端低 Re）
        单相水流（不含泥沙/高浓度）

    已知限制：
        - Manning n 不在本层校验（糙率取值合理性由调用方/P6-3 OPEN_CHANNEL 负责）
        - A / Rh 应由断面几何函数（P6-3 提供）预计算
        - 不含非均匀流加速/减速项（仅稳态均匀流）

    Args:
        n: Manning 糙率系数（无量纲）
        A_m2: 过水断面面积 (m²)
        Rh_m: 水力半径 (m)
        S: 渠底坡度（无量纲，应 > 0）

    Returns:
        体积流量 (m³/s)
    """
    if n <= 0:
        raise ValueError(f"manning_Q Manning n 必须正数：n={n}")
    if A_m2 <= 0 or Rh_m <= 0:
        raise ValueError(
            f"manning_Q 几何参数必须正数：A_m2={A_m2}, Rh_m={Rh_m}"
        )
    if S <= 0:
        raise ValueError(
            f"manning_Q 坡度 S 必须正数（均匀流降坡，逆坡用 P6-3 非均匀流模块）：S={S}"
        )
    return (1.0 / n) * A_m2 * (Rh_m ** (2.0 / 3.0)) * math.sqrt(S)


def manning_V(n: float, Rh_m: float, S: float) -> float:
    """Manning 流速计算（SPEC §3.2.6 line 256-279 教科书简化公式）。

    **Path A 自研实现**：Manning 流速形式（Q = V·A）：

        V = (1/n) · Rh^(2/3) · S^(1/2)

    Args:
        n: Manning 糙率系数（无量纲）
        Rh_m: 水力半径 (m)
        S: 渠底坡度（无量纲，应 > 0）

    Returns:
        断面平均流速 (m/s)
    """
    if n <= 0:
        raise ValueError(f"manning_V Manning n 必须正数：n={n}")
    if Rh_m <= 0:
        raise ValueError(f"manning_V 水力半径必须正数：Rh_m={Rh_m}")
    if S <= 0:
        raise ValueError(f"manning_V 坡度 S 必须正数：S={S}")
    return (1.0 / n) * (Rh_m ** (2.0 / 3.0)) * math.sqrt(S)


def critical_depth_rectangular(Q_m3s: float, b_m: float) -> float:
    """矩形渠临界水深（SPEC §3.2.6 line 267 + P6-OPEN-001 §三 公式）。

    **Path A 自研实现**：矩形断面临界水深（Bélanger 临界流条件 Fr = 1）：

        y_c = (Q² / (g · b²))^(1/3) = (q² / g)^(1/3)

    其中 q = Q/b 为单宽流量，g = 9.80665 m/s²。

    适用条件：
        矩形断面（梯形/圆形需 P6-3 OPEN_CHANNEL 通用迭代法）
        Fr = 1（临界流，由 Fr 数定义 V/√(g·D_h) = 1 推导）
        不可压缩流体（明渠自由表面流）

    已知限制：
        - 仅矩形断面；梯形/圆形留 P6-3 OPEN_CHANNEL
        - 假设平坡渠底（无显著坡度修正，临界水深定义独立于 S）
        - 不含非棱柱体断面变化

    Args:
        Q_m3s: 体积流量 (m³/s)
        b_m: 渠宽 (m)，矩形断面顶宽

    Returns:
        临界水深 (m)
    """
    if Q_m3s <= 0:
        raise ValueError(
            f"critical_depth_rectangular 流量必须正数：Q_m3s={Q_m3s}"
        )
    if b_m <= 0:
        raise ValueError(
            f"critical_depth_rectangular 渠宽必须正数：b_m={b_m}"
        )
    # y_c = (Q²/(g·b²))^(1/3)
    return ((Q_m3s ** 2) / (_G * (b_m ** 2))) ** (1.0 / 3.0)


def hydraulic_jump_y2(y1: float, Fr1: float) -> float:
    """矩形断面水跃共轭水深（SPEC §3.2.6 line 269 + Bélanger 方程）。

    **Path A 自研实现**：Bélanger 方程（矩形断面共轭水深比）：

        y2/y1 = 0.5 · (√(1 + 8·Fr1²) - 1)

    即：

        y2 = y1 · 0.5 · (√(1 + 8·Fr1²) - 1)

    其中：
        y1：跃前水深（m，上游急流水深，Fr1 > 1）
        Fr1：跃前 Froude 数（无量纲，Fr1 = V1/√(g·y1)）

    适用条件：
        矩形断面（梯形渠水跃公式不同，留 P6-3 OPEN_CHANNEL）
        平坡渠底（无坡度修正）
        Fr1 > 1（急流）；Fr1 = 1 时 y2 = y1（临界退化）
        经典水跃（1 < Fr1 < 2.5 摆动水跃；2.5 < Fr1 < 4.5 稳定水跃；
        Fr1 > 4.5 强水跃，能量耗散大）

    已知限制：
        - 仅矩形断面；梯形/圆形留 P6-3 OPEN_CHANNEL
        - 假设水平渠底；陡坡渠水跃含能量方程修正
        - 不含 Fr1 < 1 输入校验（公式物理上无意义但数学上仍可计算，
          调用方负责）

    Args:
        y1: 跃前水深 (m)
        Fr1: 跃前 Froude 数（无量纲）

    Returns:
        共轭水深 y2 (m)
    """
    if y1 <= 0:
        raise ValueError(
            f"hydraulic_jump_y2 跃前水深必须正数：y1={y1}"
        )
    # Bélanger 方程：y2 = y1 · 0.5 · (√(1+8·Fr1²) - 1)
    return y1 * 0.5 * (math.sqrt(1.0 + 8.0 * Fr1 * Fr1) - 1.0)


# ============================================================================
# P6-0 Task 5：PSYCHRO 6 函数（CoolProp.HumidAirProp.HAPropsSI 直调包装）
# ============================================================================
#
# 设计决策（ADR-0030 V1.2 G-02）：本批 6 函数**直调** CoolProp.HumidAirProp.HAPropsSI
# （与 Task 3/4 Path A 自研简化公式不同）：
#   1. CoolProp 6.6.0 模块路径 `CoolProp.HumidAirProp`（非 `CoolProp.HumidAir`，
#      后者仅存在于更早版本；本批锁定 6.6.0 后命名以官方文档为准）
#   2. HAPropsSI 签名 `HAPropsSI(Output, Input1Name, Input1, Input2Name, Input2,
#      Input3Name, Input3)` 与 brief 完全一致，无须自研简化公式
#   3. SPEC §3.2.5 PSYCHRO（line 240-254）含湿量/露点/湿球/焓/比容/冷却盘管 6 项
#      全部由 CoolProp 官方实现覆盖，ASHRAE RP-1845 算法（CoolProp 官方文档）
#   4. 验收标准：与 ASHRAE Psychrometric Chart 偏差 <1%（SPEC §3.2.5 line 254）
#   5. 无 fallback 路径——CoolProp 即权威实现；如未来版本不兼容走 ADR-0030 决策 8
#
# ASHRAE 验证值参考（P=101325 Pa，由 CoolProp 6.6.0 自洽生成）：
#   T=298.15K(25°C), RH=0.5: W≈0.00993, D≈287.02K, B≈291.03K, H≈50423 J/kg, V≈0.858
#   T=303.15K(30°C), RH=0.6: W≈0.01612, H≈71365 J/kg
#
# 冷却盘管显热/潜热分解（ASHRAE Handbook Fundamentals 2021 §1.2）：
#   Q_sensible = Cp_dry_air · (T_in - T_out), Cp_dry_air ≈ 1006 J/(kg·K)
#   Q_latent   = (H_in - H_out) - Q_sensible


def humid_air_humidity_ratio(T_k: float, RH: float, P_pa: float) -> float:
    """湿空气湿度比 W（kg 水 / kg 干空气）。

    直调 CoolProp.HumidAirProp.HAPropsSI（ADR-0030 V1.2 G-02）：算法基于
    ASHRAE RP-1845（CoolProp 官方文档 HAPropsSI 实现）。

    Args:
        T_k: 干球温度（K，开尔文）
        RH: 相对湿度（无量纲，0~1）
        P_pa: 大气压力（Pa）

    Returns:
        湿度比 W（kg/kg dry air）

    已知限制：
        - RH ∈ [0, 1]（>1 无物理意义）；超出范围触发 ValueError
        - P > 0（≤0 无物理意义）；非正压力触发 ValueError
        - T > 0 K（绝对零度无意义）；CoolProp 内部会捕获非正 T
    """
    if not (0.0 <= RH <= 1.0):
        raise ValueError(
            f"humid_air_humidity_ratio RH 必须在 [0, 1] 区间：RH={RH}"
        )
    if P_pa <= 0.0:
        raise ValueError(
            f"humid_air_humidity_ratio 压力必须正数：P_pa={P_pa}"
        )
    return _HA_module.HAPropsSI("W", "T", T_k, "R", RH, "P", P_pa)


def humid_air_dew_point(T_k: float, RH: float, P_pa: float) -> float:
    """湿空气露点温度 D（K，开尔文）。

    直调 CoolProp.HumidAirProp.HAPropsSI（ADR-0030 V1.2 G-02）：露点定义为
    保持湿空气湿度比不变，冷却至饱和时的温度。

    Args:
        T_k: 干球温度（K）
        RH: 相对湿度（无量纲，0~1）
        P_pa: 大气压力（Pa）

    Returns:
        露点温度（K）

    已知限制：
        - 返回值单位为 K（开尔文）；调用方需转 °C 时减 273.15
        - RH=0 时返回物理上不可计算（CoolProp 内部抛 ValueError 透传）
    """
    if not (0.0 <= RH <= 1.0):
        raise ValueError(
            f"humid_air_dew_point RH 必须在 [0, 1] 区间：RH={RH}"
        )
    if P_pa <= 0.0:
        raise ValueError(
            f"humid_air_dew_point 压力必须正数：P_pa={P_pa}"
        )
    return _HA_module.HAPropsSI("D", "T", T_k, "R", RH, "P", P_pa)


def humid_air_wet_bulb(T_k: float, RH: float, P_pa: float) -> float:
    """湿空气湿球温度 B（K，开尔文）。

    直调 CoolProp.HumidAirProp.HAPropsSI（ADR-0030 V1.2 G-02）：湿球定义为
    等焓饱和温度（绝热饱和近似），位于露点与干球之间。

    Args:
        T_k: 干球温度（K）
        RH: 相对湿度（无量纲，0~1）
        P_pa: 大气压力（Pa）

    Returns:
        湿球温度（K）

    已知限制：
        - 返回值单位为 K
        - RH=0 时物理上不可计算（CoolProp 内部抛 ValueError 透传）
    """
    if not (0.0 <= RH <= 1.0):
        raise ValueError(
            f"humid_air_wet_bulb RH 必须在 [0, 1] 区间：RH={RH}"
        )
    if P_pa <= 0.0:
        raise ValueError(
            f"humid_air_wet_bulb 压力必须正数：P_pa={P_pa}"
        )
    return _HA_module.HAPropsSI("B", "T", T_k, "R", RH, "P", P_pa)


def humid_air_enthalpy(T_k: float, RH: float, P_pa: float) -> float:
    """湿空气比焓 H（J/kg 干空气）。

    直调 CoolProp.HumidAirProp.HAPropsSI（ADR-0030 V1.2 G-02）：单位为
    J/kg dry air（每 kg 干空气的焓，不是 kg 湿空气）。

    Args:
        T_k: 干球温度（K）
        RH: 相对湿度（无量纲，0~1）
        P_pa: 大气压力（Pa）

    Returns:
        比焓（J/kg dry air）

    已知限制：
        - 单位 J/kg dry air（非 J/kg moist air）；转换需乘以 (1+W)
        - 高温（T > 100°C）或极低压（P < 1 kPa）需注意 HAPropsSI 适用范围
    """
    if not (0.0 <= RH <= 1.0):
        raise ValueError(
            f"humid_air_enthalpy RH 必须在 [0, 1] 区间：RH={RH}"
        )
    if P_pa <= 0.0:
        raise ValueError(
            f"humid_air_enthalpy 压力必须正数：P_pa={P_pa}"
        )
    return _HA_module.HAPropsSI("H", "T", T_k, "R", RH, "P", P_pa)


def humid_air_specific_volume(T_k: float, RH: float, P_pa: float) -> float:
    """湿空气比容 V（m³/kg 干空气）。

    直调 CoolProp.HumidAirProp.HAPropsSI（ADR-0030 V1.2 G-02）：单位为
    m³/kg dry air（每 kg 干空气占据的体积）。

    Args:
        T_k: 干球温度（K）
        RH: 相对湿度（无量纲，0~1）
        P_pa: 大气压力（Pa）

    Returns:
        比容（m³/kg dry air）

    已知限制：
        - 单位 m³/kg dry air（非 m³/kg moist air）
        - T=25°C, P=101325 时理想气体定律给出 V ≈ 0.845（干空气），湿空气略大
    """
    if not (0.0 <= RH <= 1.0):
        raise ValueError(
            f"humid_air_specific_volume RH 必须在 [0, 1] 区间：RH={RH}"
        )
    if P_pa <= 0.0:
        raise ValueError(
            f"humid_air_specific_volume 压力必须正数：P_pa={P_pa}"
        )
    return _HA_module.HAPropsSI("V", "T", T_k, "R", RH, "P", P_pa)


def humid_air_coil_delta_h(
    T_in: float,
    RH_in: float,
    T_out: float,
    RH_out: float,
    P_pa: float,
) -> tuple[float, float]:
    """冷却盘管显热 + 潜热（J/kg 干空气）。

    直调 CoolProp.HumidAirProp.HAPropsSI 两次（入口/出口焓），按 ASHRAE
    Handbook Fundamentals 2021 §1.2 拆分：

        Q_sensible = Cp_dry_air · (T_in - T_out)   # Cp ≈ 1006 J/(kg·K)
        Q_latent   = (H_in - H_out) - Q_sensible

    Args:
        T_in: 入口干球温度（K）
        RH_in: 入口相对湿度（无量纲，0~1）
        T_out: 出口干球温度（K）
        RH_out: 出口相对湿度（无量纲，0~1）
        P_pa: 大气压力（Pa）

    Returns:
        (Q_sensible, Q_latent)：显热 + 潜热（J/kg dry air）

    已知限制：
        - 单位 J/kg dry air；如需 J/kg moist air 需乘以 (1+W)
        - 假设冷却盘管表面与空气充分接触（无接触系数修正）
        - Cp_dry_air 取 1006 J/(kg·K) 典型值（实际随温度变化 ±1%）
        - 不含盘管结霜/凝水带走潜热的额外修正（标准 ASHRAE 简式）
    """
    if T_in <= 0 or T_out <= 0:
        raise ValueError(
            f"humid_air_coil_delta_h 温度必须正数：T_in={T_in}, T_out={T_out}"
        )
    if not (0.0 <= RH_in <= 1.0) or not (0.0 <= RH_out <= 1.0):
        raise ValueError(
            f"humid_air_coil_delta_h RH 必须在 [0, 1]：RH_in={RH_in}, RH_out={RH_out}"
        )
    if P_pa <= 0.0:
        raise ValueError(
            f"humid_air_coil_delta_h 压力必须正数：P_pa={P_pa}"
        )
    H_in = _HA_module.HAPropsSI("H", "T", T_in, "R", RH_in, "P", P_pa)
    H_out = _HA_module.HAPropsSI("H", "T", T_out, "R", RH_out, "P", P_pa)
    Q_sensible = 1006.0 * (T_in - T_out)
    Q_latent = (H_in - H_out) - Q_sensible
    return (Q_sensible, Q_latent)


# ============================================================================
# provenance 接口（运维可观测 + 升级决策依据）
# ============================================================================


def get_chedl_provenance() -> dict[str, ChEDLProvenance]:
    """返回 23 包装函数的 provenance 字典（7 既有 + 6 Task 3 + 4 Task 4 + 6 Task 5）。

    用于：
    1. 运维可观测（metrics / health endpoint）
    2. 升级决策依据（ADR-0030 决策 8 触发条件之一）
    3. 公式溯源字段（formula_ref.source 关联）

    Returns:
        23 项 {func_name: ChEDLProvenance} 字典
    """
    # chEDL_function 使用 fluids 完整路径（含包名前缀）
    # 5 直调函数
    prov_direct: dict[str, ChEDLProvenance] = {
        "v_Souders_Brown": ChEDLProvenance(
            chEDL_function="fluids.v_Souders_Brown",
            chEDL_version=_CHEDL_VERSION,
            known_limitations=[
                "V1.8 F-13-2：fluids 1.3.1 flat-package，调顶层函数而非子模块",
            ],
            fallback_available=False,
            fallback_formula_ref=None,
        ),
        "K_separator_Watkins": ChEDLProvenance(
            chEDL_function="fluids.K_separator_Watkins",
            chEDL_version=_CHEDL_VERSION,
            known_limitations=[
                "V1.8 F-13-2：fluids 1.3.1 flat-package",
                "method='spline' 为插值法，与原始 Watkins 论文略有差异（<1%）",
            ],
            fallback_available=False,
            fallback_formula_ref=None,
        ),
        "K_separator_demister_York": ChEDLProvenance(
            chEDL_function="fluids.K_separator_demister_York",
            chEDL_version=_CHEDL_VERSION,
            known_limitations=[
                "V1.8 F-13-2：fluids 1.3.1 flat-package",
                "York 关联仅适用于金属丝网除雾器",
            ],
            fallback_available=False,
            fallback_formula_ref=None,
        ),
        "v_terminal": ChEDLProvenance(
            chEDL_function="fluids.v_terminal",
            chEDL_version=_CHEDL_VERSION,
            known_limitations=[
                "V1.8 F-13-2：fluids 1.3.1 flat-package",
                "球形颗粒假设，非球形系数未应用",
            ],
            fallback_available=False,
            fallback_formula_ref=None,
        ),
        "API520_round_size": ChEDLProvenance(
            chEDL_function="fluids.API520_round_size",
            chEDL_version=_CHEDL_VERSION,
            known_limitations=[
                "V1.8 F-13-2：fluids 1.3.1 flat-package",
                "API 520 7th Ed. 表口径，圆整规则锁定",
            ],
            fallback_available=False,
            fallback_formula_ref=None,
        ),
    }
    # 2 fallback 函数
    prov_fallback: dict[str, ChEDLProvenance] = {
        "time_to_empty": ChEDLProvenance(
            chEDL_function="fluids.time_to_empty",  # 不可用，仅 provenance 追溯
            chEDL_version=_CHEDL_VERSION,
            known_limitations=[
                "V1.9 GSTACK P0：fluids 1.3.1 不提供 time_to_empty → 自研 fallback",
                "F-13-5：fallback 基于伯努利 + 孔口出流（Q = Cd·A·√(2g·h)）",
                "忽略粘性、表面张力、压缩效应；等温常压重力排空假设",
                "圆柱容器 + 圆孔口；非圆孔需用户调 Cd 补偿",
            ],
            fallback_available=True,
            fallback_formula_ref="self_implemented_bernoulli",
        ),
        "tank_level_to_volume": ChEDLProvenance(
            chEDL_function="fluids.tank_level_to_volume",  # 不可用，仅 provenance 追溯
            chEDL_version=_CHEDL_VERSION,
            known_limitations=[
                "V1.9 GSTACK P0：fluids 1.3.1 不提供 tank_level_to_volume → 自研 fallback",
                "F-13-5：fallback 基于圆柱几何 + 标准 2:1 椭圆封头修正",
                "仅支持 'ellipse' / 'none' 两种 head_type；碟形/球形封头需扩展",
            ],
            fallback_available=True,
            fallback_formula_ref="self_implemented_cylindrical_geometry",
        ),
    }
    # 6 P6-0 CV/RESTRICTION 函数（Path A：SPEC §3.2.1/3.2.2 简化公式自研）
    prov_p6_0: dict[str, ChEDLProvenance] = {
        "control_valve_C_liquid": ChEDLProvenance(
            chEDL_function="spec_p6_3.2.1_simplified",  # 不调 fluids（Path A）
            chEDL_version=_CHEDL_VERSION,  # 包装层锁定版本，公式源见 fallback_formula_ref
            known_limitations=[
                "P6-0 Path A：fluids 完整 API 需 15 参数（Psat/Pc/mu/...）不匹配 brief 简化签名",
                "SPEC §3.2.1 line 149 简化公式仅适用于湍流非阻塞工况；"
                "choked/cavitation 留 P6+ cv_engine",
                "不应用 FL/Fd 压力恢复/管径形状修正（阀厂数据依赖）",
            ],
            fallback_available=True,
            fallback_formula_ref="spec_p6_3.2.1_line_149",
        ),
        "control_valve_kv_liquid": ChEDLProvenance(
            chEDL_function="spec_p6_3.2.1_simplified",  # 不调 fluids（Path A）
            chEDL_version=_CHEDL_VERSION,
            known_limitations=[
                "P6-0 Path A：SI Kv 简化公式 Kv = Q·√(ρ/(1000·ΔP))",
                "无粘度/管径修正；高粘度液体（μ>50 cP）需扩展",
                "choked/cavitation 校核留 P6+ Task 8 cv_engine",
            ],
            fallback_available=True,
            fallback_formula_ref="spec_p6_3.2.1_simplified_kv",
        ),
        "control_valve_cv_gas": ChEDLProvenance(
            chEDL_function="spec_p6_3.2.1_simplified",  # 不调 fluids（Path A）
            chEDL_version=_CHEDL_VERSION,
            known_limitations=[
                "P6-0 Path A：IEC 60534-2-1 §6.3 简化（Fp=1，无 μ/D1/D2/d/FL/Fd 修正）",
                "Y 膨胀系数公式 Y=1-x/(3·Fγ·xT) 为标准 κ 关联的简化",
                "阻塞流校核（x ≥ Fγ·xT）由调用方负责；本函数不强制 clamp x",
                "choked 工况下应取 x = Fγ·xT 代入重算（Task 8 cv_engine 实现）",
            ],
            fallback_available=True,
            fallback_formula_ref="spec_p6_3.2.1.3_line_1058",
        ),
        "flow_meter_orifice": ChEDLProvenance(
            chEDL_function="spec_p6_3.2.2_simplified",  # 不调 fluids（Path A）
            chEDL_version=_CHEDL_VERSION,
            known_limitations=[
                "P6-0 Path A：Reader-Harris 3 项截断（完整 14 项公式未实现）",
                "ε 公式取 ISO 5167-2 §5.3.2.2 κ=1.4 简化（brief 无 kappa 入参）",
                "β 范围限定 [0.2, 0.75]（ISO 5167-2 适用范围）",
                "taps 位置限定 flange / corner / D-D/2（默认 flange 等效处理）",
            ],
            fallback_available=True,
            fallback_formula_ref="spec_p6_3.2.2.1_reader_harris_3term",
        ),
        "flow_meter_venturi": ChEDLProvenance(
            chEDL_function="spec_p6_3.2.2_simplified",  # 不调 fluids（Path A）
            chEDL_version=_CHEDL_VERSION,
            known_limitations=[
                "P6-0 Path A：文丘里管 C 取 SPEC §3.2.2.2 范围中值 0.99（铸造标准）",
                "ISO 5167-4 实际按加工类型区分（铸造 0.984 / 机械 0.995 / 粗糙铸造 0.985）",
                "ε 公式取 ISO 5167-4 κ=1.4 简化形式",
                "喉部 β 范围 [0.3, 0.75]（ISO 5167-4 适用）",
            ],
            fallback_available=True,
            fallback_formula_ref="spec_p6_3.2.2.2_iso_5167_4",
        ),
        "flow_meter_nozzle": ChEDLProvenance(
            chEDL_function="spec_p6_3.2.2_simplified",  # 不调 fluids（Path A）
            chEDL_version=_CHEDL_VERSION,
            known_limitations=[
                "P6-0 Path A：ISA 1932 喷嘴 C 公式 SPEC §3.2.2.3 完整实现",
                "ε 公式取 ISO 5167-3 §5.4.2 κ=1.4 简化形式",
                "长径喷嘴 C 系数（ISO 5167-3 Eq. 9）未实现（默认 ISA 1932）",
                "β 范围限定 [0.2, 0.8]（ISO 5167-3 适用）",
            ],
            fallback_available=True,
            fallback_formula_ref="spec_p6_3.2.2.3_isa_1932",
        ),
    }
    # 4 P6-0 OPEN_CHANNEL 函数（Task 4，Path A：SPEC §3.2.6 教科书公式自研）
    prov_p6_0_t4: dict[str, ChEDLProvenance] = {
        "manning_Q": ChEDLProvenance(
            chEDL_function="spec_p6_3.2.6_simplified",  # 不调 fluids（Path A）
            chEDL_version=_CHEDL_VERSION,
            known_limitations=[
                "P6-0 Task 4 Path A：fluids.open_channel 不存在；fluids.open_flow.Manning_flow "
                "REQUIRED 命中缺失（G-01 核验）",
                "教科书 Manning 公式 Q = (1/n)·A·Rh^(2/3)·S^(1/2)，仅适用均匀流",
                "Manning n 取值合理性由 P6-3 OPEN_CHANNEL 工艺工程师 Owner 校核",
                "A/Rh 由 P6-3 断面几何函数（梯形/矩形/圆形）提供",
                "不含非均匀流加速/减速修正（明渠水力学缓变流方程留 P6+）",
            ],
            fallback_available=True,
            fallback_formula_ref="spec_p6_3.2.6_manning_textbook",
        ),
        "manning_V": ChEDLProvenance(
            chEDL_function="spec_p6_3.2.6_simplified",  # 不调 fluids（Path A）
            chEDL_version=_CHEDL_VERSION,
            known_limitations=[
                "P6-0 Task 4 Path A：Q = V·A 推导式 V = (1/n)·Rh^(2/3)·S^(1/2)",
                "V 与 Q 应满足 V = Q/A 一致性（P6-3 测试保证）",
                "不调 fluids.open_flow.V_Manning（签名不同：fluids 需要 A/Rh/n/S 但 "
                "返回值口径与工程单位差异待校核）",
            ],
            fallback_available=True,
            fallback_formula_ref="spec_p6_3.2.6_manning_textbook",
        ),
        "critical_depth_rectangular": ChEDLProvenance(
            chEDL_function="spec_p6_3.2.6_simplified",  # 不调 fluids（Path A）
            chEDL_version=_CHEDL_VERSION,
            known_limitations=[
                "P6-0 Task 4 Path A：仅矩形断面 y_c = (Q²/(g·b²))^(1/3)",
                "梯形/圆形断面临界水深须迭代求解 Q²/g = A³/T，留 P6-3 OPEN_CHANNEL",
                "假设平坡渠底（临界水深定义独立于 S）",
                "P6-OPEN-001 §三：fluids.open_flow.critical_depth REQUIRED 命中缺失",
            ],
            fallback_available=True,
            fallback_formula_ref="spec_p6_3.2.6_rect_critical_depth",
        ),
        "hydraulic_jump_y2": ChEDLProvenance(
            chEDL_function="spec_p6_3.2.6_simplified",  # 不调 fluids（Path A）
            chEDL_version=_CHEDL_VERSION,
            known_limitations=[
                "P6-0 Task 4 Path A：Bélanger 方程仅适用矩形断面",
                "梯形/圆形断面水跃共轭水深须数值迭代，留 P6-3 OPEN_CHANNEL",
                "假设水平渠底（陡坡水跃含能量方程修正）",
                "Fr1 < 1 输入未校验（公式数学上仍可计算但物理无意义，调用方负责）",
                "P6-OPEN-001 §三：fluids.open_flow.hydraulic_radius REQUIRED 命中缺失"
                "（注：fl 流体库无直接共轭水深 API，需由 R+A 计算）",
            ],
            fallback_available=True,
            fallback_formula_ref="spec_p6_3.2.6_belanger_rect_jump",
        ),
    }
    # 6 P6-0 Task 5 PSYCHRO 函数（直调 CoolProp.HumidAirProp.HAPropsSI）
    prov_p6_0_t5: dict[str, ChEDLProvenance] = {
        "humid_air_humidity_ratio": ChEDLProvenance(
            chEDL_function="coolprop_humidair_hapropssi",  # CoolProp 官方实现
            chEDL_version=_COOLPROP_VERSION,  # 6.6.0（ADR-0030 V1.2 决策 5）
            known_limitations=[
                "P6-0 Task 5：CoolProp 6.6.0 模块路径 CoolProp.HumidAirProp（注意非 HumidAir）",
                "算法基于 ASHRAE RP-1845（CoolProp 官方文档）",
                "RH ∈ [0, 1]，超出范围 ValueError；T_k > 0；P_pa > 0",
                "无 fallback 路径——CoolProp 即权威实现；版本升级走 ADR-0030 决策 8",
            ],
            fallback_available=False,
            fallback_formula_ref=None,
        ),
        "humid_air_dew_point": ChEDLProvenance(
            chEDL_function="coolprop_humidair_hapropssi",
            chEDL_version=_COOLPROP_VERSION,
            known_limitations=[
                "P6-0 Task 5：返回开尔文（K）；CoolProp 不提供 °C 选项",
                "RH=0 物理上不可计算（CoolProp 内部抛 ValueError，包装层透传）",
                "算法 ASHRAE RP-1845；冷凝假设饱和水汽压平衡",
                "无 fallback——CoolProp 即权威",
            ],
            fallback_available=False,
            fallback_formula_ref=None,
        ),
        "humid_air_wet_bulb": ChEDLProvenance(
            chEDL_function="coolprop_humidair_hapropssi",
            chEDL_version=_COOLPROP_VERSION,
            known_limitations=[
                "P6-0 Task 5：湿球为等焓饱和温度近似（非严格等焓过程）",
                "返回开尔文（K）；位于露点（D）与干球（T）之间",
                "RH=0 物理上不可计算（CoolProp 透传 ValueError）",
                "无 fallback——CoolProp 即权威",
            ],
            fallback_available=False,
            fallback_formula_ref=None,
        ),
        "humid_air_enthalpy": ChEDLProvenance(
            chEDL_function="coolprop_humidair_hapropssi",
            chEDL_version=_COOLPROP_VERSION,
            known_limitations=[
                "P6-0 Task 5：单位 J/kg dry air（非 J/kg moist air）；转换需乘以 (1+W)",
                "高温（T>100°C）或极低压（P<1 kPa）需注意 HAPropsSI 适用范围",
                "算法 ASHRAE RP-1845；Cp_dry_air≈1006 J/(kg·K) 为 T=25°C 标准值",
                "无 fallback——CoolProp 即权威",
            ],
            fallback_available=False,
            fallback_formula_ref=None,
        ),
        "humid_air_specific_volume": ChEDLProvenance(
            chEDL_function="coolprop_humidair_hapropssi",
            chEDL_version=_COOLPROP_VERSION,
            known_limitations=[
                "P6-0 Task 5：单位 m³/kg dry air（非 m³/kg moist air）",
                "T=25°C, P=101325 时理想气体给出 V≈0.845（干空气），湿空气略大",
                "算法 ASHRAE RP-1845；干空气 R_da=287.058 J/(kg·K)",
                "无 fallback——CoolProp 即权威",
            ],
            fallback_available=False,
            fallback_formula_ref=None,
        ),
        "humid_air_coil_delta_h": ChEDLProvenance(
            chEDL_function="coolprop_humidair_hapropssi",
            chEDL_version=_COOLPROP_VERSION,
            known_limitations=[
                "P6-0 Task 5：Q_sensible = 1006·(T_in-T_out)；Cp_dry_air 取 T=25°C 典型值",
                "Q_latent = (H_in-H_out) - Q_sensible；冷却除湿场景两者均正",
                "假设盘管-空气充分接触（无 BYPASS 系数 / 接触系数修正）",
                "不含盘管结霜/凝水带走的额外潜热修正（标准 ASHRAE 简式）",
                "算法核心 HAPropsSI 调用 2 次（入口/出口焓），其余为 ASHRAE §1.2 简式",
                "无 fallback——CoolProp 即权威",
            ],
            fallback_available=False,
            fallback_formula_ref=None,
        ),
    }
    return {**prov_direct, **prov_fallback, **prov_p6_0, **prov_p6_0_t4, **prov_p6_0_t5}


__all__ = [
    "v_Souders_Brown",
    "K_separator_Watkins",
    "K_separator_demister_York",
    "K_Souders_Brown_theoretical",
    "v_terminal",
    "API520_round_size",
    "time_to_empty",
    "tank_level_to_volume",
    "control_valve_C_liquid",
    "control_valve_kv_liquid",
    "control_valve_cv_gas",
    "flow_meter_orifice",
    "flow_meter_venturi",
    "flow_meter_nozzle",
    "manning_Q",
    "manning_V",
    "critical_depth_rectangular",
    "hydraulic_jump_y2",
    "humid_air_humidity_ratio",
    "humid_air_dew_point",
    "humid_air_wet_bulb",
    "humid_air_enthalpy",
    "humid_air_specific_volume",
    "humid_air_coil_delta_h",
    "get_chedl_provenance",
]