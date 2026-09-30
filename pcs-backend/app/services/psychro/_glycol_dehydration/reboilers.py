"""再沸器负荷 + 汽提气率 + 贫甘醇浓度子模块（P6-8 T1 / T4）。

P6-9-PICKUP-5 5C（REF-P6-8-2）自 ``glycol_dehydration_service.py`` 拆出。

对应 OPEN-P6-6A-6 子任务 1（Reboiler Duty）+ 2（Stripping Gas Rate）
+ 4（Lean Glycol Concentration）：

  - ``ReboilerStrippingInput`` / ``ReboilerStrippingResult`` — 独立服务的
    {Input, Result} 二元组（与 ``GlycolDehydrationInput`` 解耦）
  - ``_calc_reboiler_duty_btu_hr`` — 完整焓平衡 Q_total = (Q_evap + Q_cond
    + Q_TEG) × 1.10（+10% 设计裕度）
  - ``_calc_stripping_gas_rate_scf_gal_teg`` — GPSA §20.4 Eq.20-5 简式
    + Antoine 真 P_sat,TEG
  - ``_calc_lean_glycol_concentration_wt_pct`` — GPSA Fig 20-4 数据点插值
  - ``calc_reboiler_stripping`` — 主入口

Path A1A1 决议（工艺 2026-11-15 前未对账）：完整焓平衡 +10% 设计裕度 +
WARNING 字段透出（``TEG_CIRCULATION_RATE_UNVERIFIED``）。

本模块仅依赖 stdlib + pydantic，与同包 ``behr`` / ``dewpoint`` 互不依赖。

注：``glycol_dehydration_service`` 内仍保留 v5.1 占位版
``_calc_stripping_gas_rate_scf_per_gal_teg``——它填的是**另一个** result 字段
``stripping_gas_scf_per_gal_teg``（非本模块的 ``stripping_gas_rate_scf_gal``），
两者公式与语义均不同，**不可**互相替代（详见 REF-P6-8-1 5C report）。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel, ConfigDict, Field

# =============================================================================
# P6-8 T1 — Reboiler Duty + Stripping Gas Rate 独立服务路径
# (OPEN-P6-6A-6 子任务 1+2)
#
# 与 glycol_dehydration_service.calc_glycol_dehydration 内嵌的 v5.1 简式版不同：
#   * 完整焓平衡 Q_total = Q_evap + Q_cond + Q_TEG (+10% 设计裕度)
#   * GPSA §20.4 Eq.20-5 + v5 plan Antoine (A=15.30 / B=8500) 真 P_sat_TEG
#   * WARNING 字段透出：TEG 循环量待对账
#
# 这是 Path A1A1 决议（OPEN-P6-6A-6 工艺 2026-11-15 前未对账）的 standalone 服务。
# =============================================================================


class ReboilerStrippingInput(BaseModel):
    """Reboiler Duty + Stripping Gas Rate 输入（OPEN-P6-6A-6 子任务 1+2）。

    与 GlycolDehydrationInput 解耦：直接以水脱除量 (lb H2O/hr) 与 TEG 循环量
    (gal TEG / lb H2O) 为入口，不绑定气体流量 / 入口水含量 / 塔盘数。
    """

    model_config = ConfigDict(frozen=False, extra="forbid")

    # 水脱除（默认值 = XLS PR-018 E80 基准 2377 lb/hr；stripping-gas-only 算例可省略）
    water_removal_rate_lb_hr: float = Field(default=2377.0, gt=0)
    # TEG 循环
    teg_circulation_rate_gal_lb: float = Field(default=3.0, gt=0)
    teg_density_lb_gal: float = Field(default=9.32, gt=0)
    # 操作条件
    reboiler_temperature_f: float = Field(default=400.0, ge=300.0, le=450.0)
    contactor_temperature_f: float = Field(default=120.0, ge=60.0, le=300.0)
    contactor_pressure_psia: float = Field(default=1000.0, ge=100.0, le=3000.0)
    # 回流比（GPSA 推荐 0.20–0.35）
    reflux_ratio: float = Field(default=0.25, ge=0.0, le=1.0)
    # 贫甘醇浓度（质量分率；XLS E29 default 0.9938；98–100 wt% TEG）
    lean_glycol_concentration_wt_pct: float = Field(default=0.9938, gt=0.0, le=1.0)


@dataclass(frozen=True)
class ReboilerStrippingResult:
    """Reboiler Duty + Stripping Gas Rate 输出（OPEN-P6-6A-6）。

    WARNING 字段（OPEN-P6-6A-6 工艺 2026-11-15 前未对账）：
      * te_circulation_rate_unverified: bool  — 标记 TEG 循环量未对账
      * warnings: list[str]                   — 透出的人类可读 warning 列表
    """

    # Reboiler Duty（BTU/hr）
    q_evap_btu_hr: float
    q_cond_btu_hr: float
    q_teg_btu_hr: float
    q_total_btu_hr: float
    # Stripping Gas Rate
    p_sat_te_mmhg: float
    sgr_scf_gal_teg: float
    # 公式溯源
    formula_ref: dict[str, str]
    # WARNING 字段（OPEN-P6-6A-6 工艺 2026-11-15 前未对账）
    te_circulation_rate_unverified: bool
    warnings: list[str] = field(default_factory=list)


def _calc_reboiler_duty_btu_hr(
    water_removal_rate_lb_hr: float,
    teg_circulation_rate_gal_lb: float,
    teg_density_lb_gal: float,
    reboiler_temperature_f: float,
    contactor_temperature_f: float,
    reflux_ratio: float,
) -> tuple[float, float, float, float, bool, list[str]]:
    """完整焓平衡 Reboiler Duty 计算（OPEN-P6-6A-6 子任务 1）。

    Q_total = (Q_evap + Q_cond + Q_TEG) × 1.10   (+10% 设计裕度)

    Q_evap  = m_H2O × (Cp_H2O · ΔT + ΔH_vap_H2O)
        Cp_H2O   = 1.00 BTU/(lb·°F)
        ΔH_vap   = 826 BTU/lb @ 400°F (steam tables)
        ΔT       = reboiler_T - contactor_T
    Q_cond  = reflux_ratio × Q_evap
    Q_TEG   = m_TEG × Cp_TEG × ΔT
        Cp_TEG   = 0.57 BTU/(lb·°F) @ 98–100 wt%
        m_TEG    = water_removal × teg_circulation × teg_density

    Returns:
        (q_evap, q_cond, q_teg, q_total, te_circulation_unverified, warnings)
    """
    warnings: list[str] = []

    # Q_evap
    cp_h2o = 1.00  # BTU/(lb·°F)
    delta_h_h2o = 826.0  # BTU/lb @ 400°F (steam tables)
    delta_t = reboiler_temperature_f - contactor_temperature_f
    q_evap = water_removal_rate_lb_hr * (cp_h2o * delta_t + delta_h_h2o)

    # Q_cond
    q_cond = reflux_ratio * q_evap

    # Q_TEG
    cp_teg = 0.57  # BTU/(lb·°F) @ 98–100 wt%
    m_teg = water_removal_rate_lb_hr * teg_circulation_rate_gal_lb * teg_density_lb_gal
    q_teg = m_teg * cp_teg * delta_t

    # Q_total 含 +10% 设计裕度
    q_total = (q_evap + q_cond + q_teg) * 1.10

    # WARNING：TEG 循环量未对账（OPEN-P6-6A-6 工艺 2026-11-15）
    te_circulation_unverified = bool(teg_circulation_rate_gal_lb == 3.0)
    if te_circulation_unverified:
        warnings.append(
            "TEG_CIRCULATION_RATE_UNVERIFIED: "
            "default 3.0 gal/lb 与 XLS 实际值可能不同"
            "（工艺室 2026-11-15 对账）"
        )

    return (
        q_evap,
        q_cond,
        q_teg,
        q_total,
        te_circulation_unverified,
        warnings,
    )


def _calc_stripping_gas_rate_scf_gal_teg(
    reboiler_temperature_f: float,
    contactor_temperature_f: float,
    contactor_pressure_psia: float,
    lean_glycol_concentration_wt_pct: float,
) -> tuple[float, float]:
    """Stripping Gas Rate 计算（OPEN-P6-6A-6 子任务 2, F2 P6-9-PICKUP-2 patch）。

    GPSA §20.4 Eq.20-5 简式（工艺室 2026-10-31 复盘后确认）：
        SGR = k_strip × (P_sat,TEG / P_total) × (1 - X) / X
            k_strip ≈ 6.5（经验常数）
            P_sat,TEG via Antoine 简式（v5 plan 原值 A=15.30 / B=8500）：
                log10(P_mmHg) = A − B / T_K
            X = 贫甘醇质量分率

    ⚠️ F2 patch (2026-10-31): 修复前公式 `k×(P_total/P_sat)×X/(1−X)` 比例项
    和 X-fraction 项双双反向，残差 4e12% vs XLS。修复后形式与 GPSA §20.4 Eq.20-5
    标准形式一致（OPEN-P6-9-PICKUP-2-1 工艺室复盘跟踪）。

    注：函数名 `_scf_gal_teg`（无 `per_`）区别于 calc_glycol_dehydration 内
    占位版 _calc_stripping_gas_rate_scf_per_gal_teg（用 P6-6B 占位 P_sat）。
    """
    k_strip = 6.5
    a_te = 15.30  # Antoine A (log10 P_mmHg = A - B/T_K), v5 plan 原值
    b_te = 8500.0  # Antoine B, v5 plan 原值

    # T_K 转换：°F → K
    t_k = (reboiler_temperature_f - 32.0) * 5.0 / 9.0 + 273.15

    # log10(P_sat,TEG [mmHg]) = A − B/T_K
    log10_p_sat_mmhg = a_te - b_te / t_k
    p_sat_te_mmhg = 10.0 ** log10_p_sat_mmhg

    # SGR = k_strip × (P_sat / P_total) × (1 - X) / X（GPSA §20.4 Eq.20-5）
    # P_total 单位转换：psi → mmHg (1 psi = 51.7149 mmHg)
    p_total_mmhg = contactor_pressure_psia * 51.7149
    x_frac = lean_glycol_concentration_wt_pct  # 已是质量分率 (0..1)
    sgr = k_strip * (p_sat_te_mmhg / p_total_mmhg) * (1.0 - x_frac) / x_frac

    return p_sat_te_mmhg, sgr


@dataclass(frozen=True)
class LeanGlycolDataPoint:
    """GPSA Fig 20-4 数据点（再沸器温度 + 汽提气速率 → 贫 TEG 浓度）。"""

    reboiler_temperature_f: float
    stripping_gas_scf_gal: float
    lean_glycol_concentration_wt_pct: float


# GPSA Fig 20-4 数据点（工艺室 2026-10-31 抄录 4 数据点；完整曲线待 2026-11-15）
_GPSA_FIG_20_4_DATA_POINTS: tuple[LeanGlycolDataPoint, ...] = (
    # (T_reboiler_F, SGR_scf_gal, lean_glycol_wt_pct)
    LeanGlycolDataPoint(380.0, 0.0, 98.8),
    LeanGlycolDataPoint(400.0, 0.0, 99.3),
    LeanGlycolDataPoint(400.0, 3.0, 99.7),
    LeanGlycolDataPoint(400.0, 6.0, 99.9),
)


def _calc_lean_glycol_concentration_wt_pct(
    reboiler_temperature_f: float,
    stripping_gas_scf_gal: float,
) -> tuple[float, list[str]]:
    """贫 TEG 浓度（GPSA Fig 20-4 数据点 + 插值, OPEN-P6-6A-6 子任务 4）。

    T_reboiler 维度：双线性插值（先 T 后 SGR）
    T=400°F 段用 SGR 线性插值；T≠400°F 用 T=380/400 两段线性

    Returns:
        (lean_glycol_concentration_wt_pct, warnings)
    """
    warnings: list[str] = []

    # 按 T 分组
    if reboiler_temperature_f <= 380.0:
        # T=380°F 段：仅 SGR=0 数据点
        return _GPSA_FIG_20_4_DATA_POINTS[0].lean_glycol_concentration_wt_pct, warnings
    elif reboiler_temperature_f >= 400.0:
        # T=400°F 段：SGR 线性插值（3 个数据点）
        T = 400.0
        points = [p for p in _GPSA_FIG_20_4_DATA_POINTS if p.reboiler_temperature_f == T]
        if stripping_gas_scf_gal <= points[0].stripping_gas_scf_gal:
            return points[0].lean_glycol_concentration_wt_pct, warnings
        elif stripping_gas_scf_gal >= points[-1].stripping_gas_scf_gal:
            return points[-1].lean_glycol_concentration_wt_pct, warnings
        # 线性插值
        for i in range(len(points) - 1):
            x1 = points[i].stripping_gas_scf_gal
            y1 = points[i].lean_glycol_concentration_wt_pct
            x2 = points[i + 1].stripping_gas_scf_gal
            y2 = points[i + 1].lean_glycol_concentration_wt_pct
            if x1 <= stripping_gas_scf_gal <= x2:
                lean_glycol = y1 + (stripping_gas_scf_gal - x1) * (y2 - y1) / (x2 - x1)
                return lean_glycol, warnings
    else:
        # T=380~400°F 段：T 线性插值（仅 SGR=0 数据点可用）
        # 注：完整 Fig 20-4 曲线待工艺室 2026-11-15 抄录
        T = reboiler_temperature_f
        # 双线性插值（sgr=0 段）
        lean_at_380 = _GPSA_FIG_20_4_DATA_POINTS[0].lean_glycol_concentration_wt_pct  # 98.8
        lean_at_400 = _GPSA_FIG_20_4_DATA_POINTS[1].lean_glycol_concentration_wt_pct  # 99.3
        lean_glycol = lean_at_380 + (T - 380.0) * (lean_at_400 - lean_at_380) / (400.0 - 380.0)
        warnings.append(
            "LEAN_GLYCOL_INTERPOLATION_PARTIAL: "
            "仅 380/400°F 两数据点线性插值；完整 Fig 20-4 待工艺室 2026-11-15 抄录"
        )
        return lean_glycol, warnings


def calc_reboiler_stripping(inp: ReboilerStrippingInput) -> ReboilerStrippingResult:
    """Reboiler Duty + Stripping Gas Rate 主入口（OPEN-P6-6A-6 子任务 1+2）。

    Path A1A1 决议（工艺 2026-11-15 前未对账）：
      * 完整焓平衡 +10% 设计裕度
      * WARNING 字段透出：TEG_CIRCULATION_RATE_UNVERIFIED
      * Antoine v5 plan 原值 A=15.30 / B=8500
    """
    q_evap, q_cond, q_teg, q_total, te_circ_unverif, warnings = (
        _calc_reboiler_duty_btu_hr(
            inp.water_removal_rate_lb_hr,
            inp.teg_circulation_rate_gal_lb,
            inp.teg_density_lb_gal,
            inp.reboiler_temperature_f,
            inp.contactor_temperature_f,
            inp.reflux_ratio,
        )
    )

    p_sat, sgr = _calc_stripping_gas_rate_scf_gal_teg(
        inp.reboiler_temperature_f,
        inp.contactor_temperature_f,
        inp.contactor_pressure_psia,
        inp.lean_glycol_concentration_wt_pct,
    )

    return ReboilerStrippingResult(
        q_evap_btu_hr=q_evap,
        q_cond_btu_hr=q_cond,
        q_teg_btu_hr=q_teg,
        q_total_btu_hr=q_total,
        p_sat_te_mmhg=p_sat,
        sgr_scf_gal_teg=sgr,
        formula_ref={
            "reboiler": (
                "Q_total = (Q_evap + Q_cond + Q_TEG) × 1.10 "
                "(+10% 设计裕度; GPSA §20.4)"
            ),
            "stripping": (
                "SGR = k_strip × (P_sat,TEG/P_total) × (1-X)/X "
                "[GPSA §20.4 Eq.20-5; P_sat via Antoine v5 plan A=15.30/B=8500]"
            ),
        },
        te_circulation_rate_unverified=te_circ_unverif,
        warnings=warnings,
    )
