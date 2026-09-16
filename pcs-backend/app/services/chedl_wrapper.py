"""ChEDL 包装层（F-13-2 落地 + V1.9 GSTACK P0 修正）。

ADR-0030 V1.1 决策 6 + V1.8 F-13-2：所有 ChEDL 调用必须经本包装层，
业务代码**禁止**直接 `import fluids.*`。

包装层职责：
1. **隔离**：业务代码与 fluids 包解耦，升级时仅改本文件
2. **降级**：fluids 1.3.1 缺失的函数（time_to_empty / tank_level_to_volume）
   触发 fallback 自研实现，provenance 标注 fallback_available=True
3. **provenance**：get_chedl_provenance() 返回 7 项元数据，支撑运维可观测性
   与升级决策（ADR-0030 决策 8）

包装函数清单（7 项）：
- 5 直调 fluids 1.3.1 顶层函数（V1.9 GSTACK P0 时序修正后确认存在）：
  v_Souders_Brown / K_separator_Watkins / K_separator_demister_York /
  v_terminal / API520_round_size
- 2 fallback（fluids 1.3.1 不存在）：
  time_to_empty / tank_level_to_volume
  fallback 实现 = 圆柱几何 + 伯努利方程 + 孔口出流

调用示例：
    from app.services import chedl_wrapper
    v = chedl_wrapper.v_Souders_Brown(K=0.1, rhol=1000.0, rhog=1.2)
    prov = chedl_wrapper.get_chedl_provenance()
"""
from __future__ import annotations

import math

import fluids

from app.services.chedl_provenance import ChEDLProvenance

# ChEDL 版本（与 Task 25 锁定一致；pyproject.toml/uv.lock 单一来源）
_CHEDL_VERSION = "1.3.1"

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
# provenance 接口（运维可观测 + 升级决策依据）
# ============================================================================


def get_chedl_provenance() -> dict[str, ChEDLProvenance]:
    """返回 7 包装函数的 provenance 字典。

    用于：
    1. 运维可观测（metrics / health endpoint）
    2. 升级决策依据（ADR-0030 决策 8 触发条件之一）
    3. 公式溯源字段（formula_ref.source 关联）

    Returns:
        7 项 {func_name: ChEDLProvenance} 字典
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
    return {**prov_direct, **prov_fallback}


__all__ = [
    "v_Souders_Brown",
    "K_separator_Watkins",
    "K_separator_demister_York",
    "v_terminal",
    "API520_round_size",
    "time_to_empty",
    "tank_level_to_volume",
    "get_chedl_provenance",
]