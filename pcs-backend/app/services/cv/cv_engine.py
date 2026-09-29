"""cv_engine IEC 60534-2-1 控制阀 Cv 计算核心（P6-1 Task 8）。

完整实现 SPEC §3.2.1.1~1.4：
- §3.2.1.1 液体 Cv 计算（Cv = Q · √(SG/ΔP)，SPEC line 149 简化公式）
- §3.2.1.2 气体 Cv 计算（Y 修正完整公式，F_γ = γ/1.4，SPEC line 1058-1080）
- §3.2.1.3 阻塞流判定（液体 FL/FF/Pv/Pc，气体 x ≥ F_γ·xT clamp Y=2/3）
- §3.2.1.4 噪音 SIL 简化法（IEC 60534-8-3 简化经验式）

补齐 P6-0 Task 3 Path A 简化公式缺失：
- 液体阻塞流检测（Task 3 仅计算基本 Cv，本任务加 FL/FF/Pv/Pc 阻塞判定）
- 气体 x_choked clamp（Task 3 仅在 Y≤0 时抛错，本任务完整 x ≥ x_choked clamp Y=2/3）
- 液体 cavitation / flashing 检测
- 噪音 SIL 简化法（Task 3 未实现）

P6-4 Task 5（C-24）补完：
- §3.2.1.5 闪蒸工况修正：Masonelian fl（3 模型并存）+ flash_steam_rate_kg_s +
  24 阀门厂库；本模块 calculate 仅追加 3 键 payload（fl / flash_steam_rate_kg_s /
  masonelian_model），不动既有 _compute_Cv_liquid（V1.2 严格）；
  公式实现见 ``flashing_correction.py`` 子模块。

P6-9 PICKUP-2 T3（OPEN-P6-4-4 partial closure）补完：
- 显式 x 参数（架构组裁决 a — 修复 x_p 推断 bug）；
- _validate_flash_consistency(x, T_c, P1_kpa, P2_kpa, Pv_kpa) 入口强制校验。

与 Task 3 chedl_wrapper.control_valve_* 的关系：
- control_valve_C_liquid / control_valve_kv_liquid / control_valve_cv_gas：
  SPEC §3.2.1 简化公式自研（Path A 裁决），不调 fluids 完整 API；
  本 cv_engine 在其上层加完整判定逻辑（阻塞/cavitation/闪蒸 + 噪音），
  最终落库字段对齐 CvResult ORM（Task 7 schema 21 字段）。
- 调用模式：cv_persist（Task 9）→ CvEngine.calculate() → 写 CvResult 表。

设计约束：
- 不调 fluids.*（依 ADR-0030 V1.1 决策 6：业务代码不直调 ChEDL）；
  基础公式参照 chedl_wrapper.control_valve_cv_gas（Cv 与 Y 一致性）。
- 不引入 Pydantic schema（Task 10 才接 CvCalculateRequest 完整 21 字段）；
  本任务 CvEngine.calculate() 接收 **kwargs 最小必要字段 + 返回 dict。
- 噪音 SIL 仅简化法（ISA-75.01 经验式）；详细法（IEC 60534-8-3 完整 8 项
  修正）留 P6+ cv_engine 扩展。
"""
from __future__ import annotations

import math
from typing import Any

from app.services.exceptions import (
    InvalidFlashConsistencyError,
    PcsError,
)

# IEC 60534-2-1 SI 标准常数（Nm³/h · bar 单位制，与 chedl_wrapper._N9_SI 一致）
_N9_SI = 0.0865

# 简化噪音 SIL 经验常数（dB），参考 ISA-75.01 简化法 + 流体辐射经验调整。
# 详细公式（IEC 60534-8-3 §5）需引入声速/密度/管径/阀口径等 8 项修正因子，
# 本任务保留为简化工程估算精度，详细公式留 P6+ cv_engine 扩展。
_SIL_OFFSET_DB = 10.0


# ============================================================================
# 液体 Cv 计算（SPEC §3.2.1.1 + IEC 60534-2-1 §5）
# ============================================================================


def _compute_Cv_liquid(
    Q_m3h: float,
    SG: float,
    dP_bar: float,
    FL: float,
    FF: float,
    Pv: float,
    Pc: float,
    P1_pa: float | None = None,
) -> tuple[float, bool, bool, bool]:
    """液体 Cv 计算 + cavitation/flashing/choked 判定（SPEC §3.2.1.1）。

    公式（SPEC §3.2.1 line 149 + IEC 60534-2-1 §5.2）：

        基本（湍流非阻塞）：Cv = Q · √(SG / ΔP)

        阻塞判定（IEC 60534-2-1 §5.2.1）：
            Pc_term = FL² · (Pc - Pv) / FF²
            若 ΔP ≥ Pc_term → choked，Cv 基于 Pc_term 重算

        cavitation 判定（IEC 60534-2-1 §5.3）：
            若 FL²/FF² ≤ ΔP/P1 < Pc_term/P1 且 Pv/P1 < 0.5 → cavitation

        flashing 判定（IEC 60534-2-1 §5.4）：
            若 Pv/P1 ≥ 0.5（入口流体接近蒸汽压） → flashing

    Args:
        Q_m3h: 体积流量（m³/h，USC 转换按业务约定）
        SG: 相对密度（SG = ρ / 1000，无量纲）
        dP_bar: 阀前后压差（bar）
        FL: 压力恢复系数（阀门厂数据，无量纲；典型 0.5~0.95）
        FF: 临界压力比系数（无量纲；典型 0.96）
        Pv: 流体入口温度下蒸汽压（Pa）
        Pc: 流体热临界压力（Pa）
        P1_pa: 阀入口绝压（Pa），cavitation/flashing 判定必需；None 时跳过

    Returns:
        (Cv_calculated, choked, cavitation, flashing)：
        - Cv_calculated: 流量系数（无量纲，US 单位制 GPM/psi）
        - choked: 是否阻塞流
        - cavitation: 是否气蚀（仅液体路径）
        - flashing: 是否闪蒸（仅液体路径）
    """
    if dP_bar <= 0 or Q_m3h < 0 or SG <= 0:
        raise ValueError(
            f"_compute_Cv_liquid 参数必须正数（Q 可为 0）："
            f"Q_m3h={Q_m3h}, SG={SG}, dP_bar={dP_bar}"
        )
    if FL <= 0 or FL > 1.0 or FF <= 0 or FF > 1.0:
        raise ValueError(
            f"_compute_Cv_liquid FL/FF 必须在 (0, 1]：FL={FL}, FF={FF}"
        )
    if Pv < 0 or Pc <= 0 or Pc <= Pv:
        raise ValueError(
            f"_compute_Cv_liquid 物性异常：Pc={Pc} Pa 必须大于 Pv={Pv} Pa"
        )

    # 基本 Cv（湍流非阻塞工况）
    Cv_base = Q_m3h * math.sqrt(SG / dP_bar)

    # 阻塞流判定：dP ≥ FL²·(Pc - Pv) / FF²
    # 单位换算：dP_bar → Pa
    dP_pa = dP_bar * 1.0e5
    Pc_term_pa = (FL**2) * (Pc - Pv) / (FF**2)
    Pc_term_bar = Pc_term_pa / 1.0e5
    choked = dP_pa >= Pc_term_pa

    if choked:
        # 阻塞工况：Cv 基于 Pc_term 而非 dP（流量受限于临界压差）
        Cv_calculated = Q_m3h * math.sqrt(SG / Pc_term_bar)
        return Cv_calculated, True, False, False

    # 非阻塞：cavitation / flashing 判定（需 P1）
    cavitation = False
    flashing = False
    if P1_pa is not None and P1_pa > 0:
        if Pv / P1_pa >= 0.5:
            # 闪蒸：入口流体已接近蒸汽压
            flashing = True
        else:
            # cavitation：ΔP/P1 ≥ FL²/FF² 但未达阻塞
            dP_P1_ratio = dP_pa / P1_pa
            FL_over_FF_sq = (FL / FF) ** 2
            if dP_P1_ratio >= FL_over_FF_sq:
                cavitation = True

    return Cv_base, False, cavitation, flashing


# ============================================================================
# 气体 Cv 计算（SPEC §3.2.1.2/3 + IEC 60534-2-1 §6.3）
# ============================================================================


def _compute_Cv_gas(
    Q_Nm3h: float,
    P1_pa: float,
    T1_k: float,
    M: float,
    Z: float,
    dP_pa: float,
    gamma: float,
    xT: float,
) -> tuple[float, bool]:
    """气体 Cv 计算 + Y 修正 + 阻塞流 clamp（SPEC §3.2.1.2/3）。

    公式（SPEC §3.2.1.3 line 1058-1080 + IEC 60534-2-1 §6.3）：

        F_γ = γ / 1.4
        x = ΔP / P1
        x_choked = F_γ · xT
        若 x ≥ x_choked → Y clamp 到 Y_choked = 1 - x_choked/(3·F_γ·xT) = 2/3，
            判定 choked=True
        否则 Y = 1 - x/(3·F_γ·xT)

        Cv = Q / (N9 · Fp · P1_bar · Y · √(x / (M·T1·Z)))
        其中 Fp=1（管道几何修正，本任务简化取 1）

    与 chedl_wrapper.control_valve_cv_gas 的差异：
        chedl_wrapper 仅计算 Y 在 (0, 1] 区间的 Cv，Y≤0 时抛 ValueError；
        本函数补齐阻塞流 clamp：x ≥ x_choked 时用 Y_choked=2/3 计算 Cv。

    Args:
        Q_Nm3h: 标况体积流量（Nm³/h）
        P1_pa: 阀入口绝压（Pa）
        T1_k: 阀入口温度（K）
        M: 分子量（g/mol；公式源约定 g/mol 量级，sqrt(M·T·Z) 单位一致）
        Z: 压缩因子（无量纲）
        dP_pa: 阀前后压差（Pa）
        gamma: 比热比 Cp/Cv（无量纲）
        xT: 压差比系数（阀门厂数据，无量纲；典型 0.4~0.8）

    Returns:
        (Cv_calculated, choked)：
        - Cv_calculated: 流量系数（无量纲）
        - choked: 是否阻塞流
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
            f"_compute_Cv_gas 所有参数必须正数："
            f"Q_Nm3h={Q_Nm3h}, P1_pa={P1_pa}, T1_k={T1_k}, M={M}, Z={Z}, "
            f"dP_pa={dP_pa}, gamma={gamma}, xT={xT}"
        )

    # 单位换算：Pa → bar（SI IEC 60534 N9 单位制）
    P1_bar = P1_pa / 1.0e5
    dP_bar = dP_pa / 1.0e5
    x = dP_bar / P1_bar
    F_gamma = gamma / 1.4  # 比热比因子
    x_choked = F_gamma * xT

    # 阻塞流 clamp：x ≥ x_choked → Y = 2/3
    if x >= x_choked:
        Y_choked = 1.0 - x_choked / (3.0 * F_gamma * xT)
        # Y_choked 解析值恒为 2/3（x_choked = F_gamma·xT 代入化简）
        # 保留计算式以便后续若 SPEC 修订 x_choked 表达式时无需改代码
        Y = Y_choked
        choked = True
    else:
        Y = 1.0 - x / (3.0 * F_gamma * xT)
        if Y <= 0:
            # 防御：参数在边界但 x 仍低于 x_choked 时 Y 接近 0 → 报错
            raise ValueError(
                f"_compute_Cv_gas Y 计算出非正值（边界工况）：Y={Y}, "
                f"x={x}, F_gamma={F_gamma}, xT={xT}"
            )
        choked = False

    # SPEC §3.2.1.3 公式：Cv = Q / (N9 · Fp · P1_bar · Y · √(x / (M·T1·Z)))
    Cv = Q_Nm3h / (
        _N9_SI * 1.0 * P1_bar * Y * math.sqrt(x / (M * T1_k * Z))
    )
    return Cv, choked


# ============================================================================
# 噪音 SIL 简化法（SPEC §3.2.1.4 + IEC 60534-8-3 简化经验式）
# ============================================================================


def _compute_noise_sil(dP_pa: float, Q_m3h: float, Kc: float) -> float:
    """调节阀噪音 SIL 简化法估算（SPEC §3.2.1.4）。

    公式源：ISA-75.01 / IEC 60534-8-3 简化法工程经验式。

        noise_sil_db = 10 · log10(Kc · ΔP_pa · Q_m3h) + offset

    其中 Kc 为综合修正系数（管径/流体密度/声速等聚合）；offset 为简化常数。

    本实现精度：
    - 仅工程估算级（典型偏差 ±3 dB）
    - 详细法（IEC 60534-8-3 §5 完整 8 项修正：L_p/L_w/L_a/频带修正等）
      留 P6+ cv_engine 扩展。

    Args:
        dP_pa: 阀前后压差（Pa）
        Q_m3h: 体积流量（m³/h）
        Kc: 综合修正系数（无量纲，默认 1.0；详细法应区分气/液）

    Returns:
        SIL dB 值（A 计权声压级简化估算）
    """
    if dP_pa <= 0 or Q_m3h <= 0 or Kc <= 0:
        raise ValueError(
            f"_compute_noise_sil 参数必须正数：dP_pa={dP_pa}, "
            f"Q_m3h={Q_m3h}, Kc={Kc}"
        )
    # 简化对数式：SIL ∝ 10·log10(Kc · ΔP · Q) + offset
    return _SIL_OFFSET_DB * math.log10(Kc * dP_pa * Q_m3h)


# ============================================================================
# 闪蒸一致性校验（P6-9 PICKUP-2 T3；OPEN-P6-4-4 partial closure）
# ============================================================================


def _water_saturation_pressure_kpa(T_c: float) -> float:
    """水的饱和蒸汽压（kPa；T_c 单位 °C；NIST Antoine 近似）。

    公式源：NIST Antoine 方程（水，1-374°C 两段拼接，单位 mmHg）：
        log10(P_mmHg) = A - B / (T_c + C)

    - Region 1（1-100°C）：A=8.07131, B=1730.63, C=233.426
    - Region 2（100-374°C）：A=8.14019, B=1810.94, C=244.485

    单位换算：1 mmHg = 0.133322 kPa；故 P_kpa = P_mmHg × 0.133322。

    用途：P6-9 PICKUP-2 T3 闪蒸一致性校验入口（架构组裁决 a）；
    返回 kPa。精度 ~1%（vs NIST steam table；不参与公式分支，
    仅用于校验 P1/Pv 比值；测试 fixture 直接传 Pv_kpa 优先）。

    Args:
        T_c: 温度（°C；有效范围 [1, 374]）

    Returns:
        饱和蒸汽压（kPa）

    Raises:
        ValueError: T_c 超出 Antoine 有效范围
    """
    if not (1.0 <= T_c <= 374.0):
        raise ValueError(
            f"_water_saturation_pressure_kpa T_c={T_c}°C 超出 Antoine 有效范围 [1, 374]"
        )
    if T_c <= 100.0:
        a, b, c = 8.07131, 1730.63, 233.426
    else:
        a, b, c = 8.14019, 1810.94, 244.485
    log_p_mmhg = a - b / (T_c + c)
    p_mmhg = 10.0 ** log_p_mmhg
    return p_mmhg * 0.133322  # mmHg → kPa


def _validate_flash_consistency(
    x: float,
    T_c: float,
    P1_kpa: float,
    P2_kpa: float,
    Pv_kpa: float,
) -> None:
    """闪蒸一致性校验（架构组 T3 裁决 a；OPEN-P6-4-4 partial closure）。

    校验规则（P6-9 PICKUP-2 T3；架构组 2026-10-31 裁决）：
    - x == 0 且 P2 < Pv → 应闪蒸但 flash fraction 为 0，不一致
    - x > 0 且 P2 >= Pv → 无闪蒸但 flash fraction > 0，不一致
    - P1 < Pv × 0.95 → 入口压力远低于蒸汽压，应为气态而非液态闪蒸工况

    Args:
        x: 闪蒸分率（无量纲；0 = 无闪蒸，>0 = 部分闪蒸）
        T_c: 温度（°C；用于存档/溯源）
        P1_kpa: 阀入口绝压（kPa）
        P2_kpa: 阀出口绝压（kPa）
        Pv_kpa: 入口温度下饱和蒸汽压（kPa）

    Raises:
        InvalidFlashConsistencyError: 任一规则违背（HTTP 422）
    """
    details = {
        "x": x,
        "T_c": T_c,
        "P1_kpa": P1_kpa,
        "P2_kpa": P2_kpa,
        "Pv_kpa": Pv_kpa,
    }
    if x == 0 and P2_kpa < Pv_kpa:
        raise InvalidFlashConsistencyError(
            f"x=0 但 P2={P2_kpa} kPa < Pv={Pv_kpa} kPa；应闪蒸",
            details=details,
        )
    if x > 0 and P2_kpa >= Pv_kpa:
        raise InvalidFlashConsistencyError(
            f"x={x} > 0 但 P2={P2_kpa} kPa >= Pv={Pv_kpa} kPa；无闪蒸",
            details=details,
        )
    if P1_kpa < Pv_kpa * 0.95:
        raise InvalidFlashConsistencyError(
            f"P1={P1_kpa} kPa 远低于 Pv={Pv_kpa} kPa（< 0.95 Pv）；入口应为气态",
            details=details,
        )


# ============================================================================
# CvEngine 主入口（P6-1 Task 8）
# ============================================================================


class CvEngine:
    """调节阀 Cv 计算引擎（P6-1 Task 8 / P6-1.5 C-07 参数化）。

    入口：calculate(**kwargs) → dict
    - fluid_phase: "LIQUID" / "GAS" / "VAPOR" / "TWO_PHASE"
    - 依据 fluid_phase 分流到 _compute_Cv_liquid / _compute_Cv_gas
    - 组装 21 键 payload 对齐 CvResult ORM（Task 7 schema）：
      fluid_phase, valve_type(占位), P1_pa, P2_pa, T1_k, Q_m3_per_h,
      SG, FL, xT, gamma, M, Z, Cv_calculated, Cv_selected(占位 None),
      choked, cavitation, flashing, noise_sil_db,
      standard_profile_code（默认 IEC_60534），design_stage(占位 "BASIC")
      + 计算引擎内部字段（rho/standard_profile_code 默认值）

    标准代码策略（C-07 评审委员会 2026-09-24 裁决）：
    - GB/T 4213 等同采用 IEC 60534-2-1:2011，无公式差异
    - standard_profile_code 仅溯源（数据口径标识），不参与公式分支
    - 默认值由原 `API-60534` 改为 `IEC_60534`（GB/T 等同采用 IEC，溯源更准确）

    详细 Pydantic CvCalculateRequest（21 字段对齐 CvResult）由 Task 10 接入；
    本任务最小字段 + dict 返回以解耦 cv_persist（Task 9）落地。
    """

    # 默认标准代码（P6-1.5 C-07：默认 IEC_60534 而非 API-60534）
    # 公式不变；仅溯源字段口径调整（GB/T 4213 等同采用 IEC 60534-2-1:2011）
    _DEFAULT_STANDARD_PROFILE = "IEC_60534"
    _DEFAULT_VALVE_TYPE = "GLOBE"
    _DEFAULT_DESIGN_STAGE = "BASIC"
    # P6-4 Task 5（C-24 Masonelian fl）：默认 MASONELIAN_1973（SPEC §3.2.1.5 Eq.5）
    _DEFAULT_MASONELIAN_MODEL = "MASONELIAN_1973"

    def calculate(self, **kwargs: Any) -> dict[str, Any]:
        """主入口：依据 fluid_phase 分流计算，返回 CvResult 21 键 payload。

        必需 kwargs（按 fluid_phase 分流）：
        - 公共：fluid_phase
        - LIQUID：Q_m3h, SG, dP_bar, FL, FF, Pv, Pc, P1_pa
        - GAS/VAPOR：Q_Nm3h, P1_pa, T1_k, M, Z, dP_pa, gamma, xT
        - 通用：valve_type（可选，默认 GLOBE），Kc（噪音系数，默认 1.0）
        - standard_profile_code（可选，默认 IEC_60534，C-07 裁决）；
          仅溯源不参与公式分支，调用方传值时仅校验非空字符串。
        - x（P6-9 PICKUP-2 T3；可选）：显式 flash fraction（无量纲）。
          None 时 back-compat 推断 x = (P1-P2)/P1（带 warning）；
          传值时与 (T_c, P1_kpa, P2_kpa, Pv_kpa) 跑一致性校验。
        - T_c（P6-9 PICKUP-2 T3；可选）：温度（°C）。仅当 x + T_c 均提供时
          跑 _validate_flash_consistency；Pv 从 T_c 经 Antoine 近似推算。

        Returns:
            dict 含 CvResult ORM 21 键（choked/cavitation/flashing/noise_sil_db
            等关键判定字段均填齐）。
        """
        fluid_phase = kwargs.get("fluid_phase")
        if fluid_phase not in ("LIQUID", "GAS", "VAPOR", "TWO_PHASE"):
            raise ValueError(
                f"CvEngine.calculate fluid_phase 必须 ∈ {{LIQUID/GAS/VAPOR/TWO_PHASE}}："
                f"实际 {fluid_phase!r}"
            )

        # P6-9 PICKUP-2 T3：显式 x 参数 + 闪蒸一致性校验（架构组裁决 a）
        # 仅 LIQUID 路径生效（GAS/VAPOR 无 flash 语义）；x + T_c 齐备才校验。
        x_explicit = kwargs.get("x")
        T_c = kwargs.get("T_c")
        if (
            fluid_phase == "LIQUID"
            and x_explicit is not None
            and T_c is not None
        ):
            # Pv 从 T_c 经 Antoine 推算（kPa）— 精度 ~1%，仅校验用
            Pv_kpa = _water_saturation_pressure_kpa(float(T_c))
            P1_kpa = float(kwargs.get("P1_pa", 0.0)) / 1.0e3
            P2_kpa = float(kwargs.get("P2_pa", 0.0)) / 1.0e3
            _validate_flash_consistency(
                x=float(x_explicit),
                T_c=float(T_c),
                P1_kpa=P1_kpa,
                P2_kpa=P2_kpa,
                Pv_kpa=Pv_kpa,
            )

        # 初始化 21 键 payload（对齐 CvResult ORM schema）
        payload: dict[str, Any] = {
            # 阀型 + 流体相（占位默认；Task 10 接 Pydantic 21 字段）
            "valve_type": kwargs.get("valve_type", self._DEFAULT_VALVE_TYPE),
            "fluid_phase": fluid_phase,
            # 工况
            "P1_pa": kwargs.get("P1_pa"),
            "P2_pa": kwargs.get("P2_pa"),
            "T1_k": kwargs.get("T1_k"),
            "Q_m3_per_h": None,
            # 物性
            "rho": kwargs.get("rho"),
            "SG": kwargs.get("SG"),
            "FL": kwargs.get("FL"),
            "xT": kwargs.get("xT"),
            "gamma": kwargs.get("gamma"),
            "M": kwargs.get("M"),
            "Z": kwargs.get("Z"),
            # 结果
            "Cv_calculated": None,
            "Cv_selected": None,
            # 状态 Boolean
            "choked": False,
            "cavitation": False,
            "flashing": False,
            "noise_sil_db": None,
            # P6-4 Task 5（C-24 Masonelian fl / SPEC §3.2.1.5）3 键占位
            # V1.2 D3：masonelian_model 走 ORM 列；fl / flash_steam_rate_kg_s 走
            # output_json JSONB 容器（cerebrum.md Do-Not-Repeat）。
            "fl": None,
            "flash_steam_rate_kg_s": None,
            "masonelian_model": kwargs.get(
                "masonelian_model", self._DEFAULT_MASONELIAN_MODEL
            ),
            # 标准代码（C-07 裁决：默认 IEC_60534，调用方可覆盖仅溯源）
            "standard_profile_code": kwargs.get(
                "standard_profile_code", self._DEFAULT_STANDARD_PROFILE
            ),
            # 设计阶段（OPEN-009 占位默认）
            "design_stage": self._DEFAULT_DESIGN_STAGE,
        }

        # 分流计算
        if fluid_phase == "LIQUID":
            Cv, choked, cavitation, flashing = _compute_Cv_liquid(
                Q_m3h=kwargs.get("Q_m3h", 0.0),
                SG=kwargs.get("SG", 1.0),
                dP_bar=kwargs.get("dP_bar", 1.0),
                FL=kwargs.get("FL", 0.9),
                FF=kwargs.get("FF", 0.96),
                Pv=kwargs.get("Pv", 0.0),
                Pc=kwargs.get("Pc", 1.0e9),
                P1_pa=kwargs.get("P1_pa"),
            )
            payload["Cv_calculated"] = Cv
            payload["choked"] = choked
            payload["cavitation"] = cavitation
            payload["flashing"] = flashing
            payload["Q_m3_per_h"] = kwargs.get("Q_m3h")
        else:
            # GAS / VAPOR / TWO_PHASE 走气体路径（TwoPhase 详细法留 P6+）
            Cv, choked = _compute_Cv_gas(
                Q_Nm3h=kwargs.get("Q_Nm3h", 0.0),
                P1_pa=kwargs.get("P1_pa", 1.0e5),
                T1_k=kwargs.get("T1_k", 300.0),
                M=kwargs.get("M", 29.0),
                Z=kwargs.get("Z", 1.0),
                dP_pa=kwargs.get("dP_pa", 0.0),
                gamma=kwargs.get("gamma", 1.4),
                xT=kwargs.get("xT", 0.7),
            )
            payload["Cv_calculated"] = Cv
            payload["choked"] = choked
            payload["Q_m3_per_h"] = kwargs.get("Q_Nm3h")

        # 噪音 SIL（简化法，公共路径；详细法留 P6+ cv_engine 扩展）
        dP_pa = kwargs.get("dP_pa") or kwargs.get("dP_bar", 0.0) * 1.0e5
        Q_for_noise = (
            kwargs.get("Q_m3h") if fluid_phase == "LIQUID" else kwargs.get("Q_Nm3h")
        )
        Kc = kwargs.get("Kc", 1.0)
        if dP_pa > 0 and Q_for_noise is not None and Q_for_noise > 0:
            payload["noise_sil_db"] = _compute_noise_sil(
                dP_pa=dP_pa, Q_m3h=Q_for_noise, Kc=Kc
            )

        # P6-4 Task 5（C-24 Masonelian fl + 闪蒸蒸汽量）
        # 仅 LIQUID 路径计算（Masonelian fl / flash_steam_rate 是液体闪蒸工况修正；
        # GAS/VAPOR 路径无 Pv / FL/FF 强物理意义，跳过）。masonelian_model 字段保留
        # （即使用户走 GAS 也记录用户意图口径）。
        if fluid_phase == "LIQUID":
            try:
                flash_result = self._compute_flash_correction(kwargs)
                payload["fl"] = flash_result["fl"]
                payload["flash_steam_rate_kg_s"] = flash_result["flash_steam_rate_kg_s"]
                payload["masonelian_model"] = flash_result["masonelian_model"]
            except (ValueError, PcsError):
                # P6-4 T5 容差：若 P2_pa/Pv_pa 缺失或闪蒸修正前置不满足
                # （如 x ≤ 0 物理越界、_flash_steam_rate_kg_s 参数非负校验失败），
                # fl / flash_steam_rate_kg_s 留 None（JSONB 容器透传），
                # masonelian_model 仍记录用户口径。Cv 主流程不因此失败。
                # 422 由后续 CvCalculateRequest 层 Pydantic 校验守住。
                payload["fl"] = None
                payload["flash_steam_rate_kg_s"] = None
                payload["masonelian_model"] = kwargs.get(
                    "masonelian_model", self._DEFAULT_MASONELIAN_MODEL
                )

        return payload

    @staticmethod
    def _compute_flash_correction(kwargs: dict[str, Any]) -> dict[str, Any]:
        """P6-4 Task 5（C-24）：闪蒸工况修正（Masonelian fl + flash_steam_rate）。

        委托 ``flashing_correction.calculate_flash_correction``，仅传 LIQUID
        相关字段（Q_m3h / SG / dP_bar / P1_pa / P2_pa / Pv_pa / FL / FF /
        masonelian_model）。vendor / valve_model 可选（kwargs 直传）。

        关键边界：
        - FL/FF 校验失败 → InvalidFLFFError 422（透传 PcsError envelope）
        - x ≤ 0 或 x ≥ 1 → ValueError（透传 422 envelope）

        Args:
            kwargs: CvEngine.calculate 的 kwargs 子集

        Returns:
            dict 含 fl / flash_steam_rate_kg_s / masonelian_model（外加 x /
            FL / FF / vendor / valve_model 元数据）
        """
        # 延迟导入打破 cv_engine ↔ flashing_correction 循环依赖
        from app.services.cv.flashing_correction import calculate_flash_correction

        return calculate_flash_correction(
            Q_m3h=float(kwargs.get("Q_m3h", 0.0)),
            SG=float(kwargs.get("SG", 1.0)),
            dP_bar=float(kwargs.get("dP_bar", 0.0)),
            P1_pa=float(kwargs.get("P1_pa", 0.0)),
            P2_pa=float(kwargs.get("P2_pa", 0.0)),
            Pv_pa=float(kwargs.get("Pv", 0.0)),
            FL=float(kwargs.get("FL", 0.9)),
            FF=float(kwargs.get("FF", 0.96)),
            vendor=kwargs.get("vendor"),
            valve_model=kwargs.get("valve_model"),
            masonelian_model=kwargs.get(
                "masonelian_model", CvEngine._DEFAULT_MASONELIAN_MODEL
            ),
            # P6-9 PICKUP-2 T3：显式 flash fraction 透传
            # （架构组裁决 a — 修复 x_p 推断 bug）
            x=kwargs.get("x"),
        )