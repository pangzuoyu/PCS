"""P4-2-3：单相压降服务（Darcy-Weisbach + Colebrook + fittings K 值表 + 路由）。

公式：
- Darcy-Weisbach 直管摩阻：ΔP_friction = f × (L/D) × (ρ × v²/2)
- 摩擦系数 f：Colebrook-White 隐式方程，brentq 求解
  1/√f = -2 log10(ε/(3.7D) + 2.51/(Re√f))，Re = ρvD/μ
  层流（Re < 2300）→ f = 64/Re
- fittings 局部阻力：ΔP_fittings = (ΣK_i) × ρ × v²/2
- Colebrook 求解复用 sizing_service._colebrook_f（P4-2-1 已实现，本模块不重复造轮子）

路由：
- ΔP/P₁ < 10% → 不可压缩近似（need_two_phase=False），返回 dp_total
- ΔP/P₁ ≥ 10% → 标记 need_two_phase=True，P4-2-4 接管两相压降
- fluid_phase='TWO_PHASE' → 直接短路 need_two_phase=True（不进入单相计算）

K 值表来源（Crane TP-410 / Idelchik 'Handbook of Hydraulic Resistance' 第 4 版）：
- 加载自 tests/services/pipe/fixtures/fittings_k_default.json
- 单元测试与 service 共享同一 fixture → 单一真源
- 用户可在 Fitting(type=..., K=...) 显式覆盖默认 K

默认物性（LIQUID / GAS / STEAM）按 sizing_service 已有物性表，避免重复造表。
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final, Literal

from app.services.exceptions import PcsError
from app.services.pipe.sizing_service import _colebrook_f

# ---------------------------------------------------------------------------
# 异常
# ---------------------------------------------------------------------------


class PressureDropInputError(PcsError):
    """PressureDrop 输入错误（业务非法 / 公式除零）。

    触发场景：
    - P1 ≤ 0（压降分母退化；物理意义：上游压力必须 > 0）
    - D_m ≤ 0（管径退化 / 无效）
    - ρ ≤ 0（密度退化 / 无效）
    - μ ≤ 0（粘度退化 / 无效）
    - flow_rate_m3s < 0（负流量物理非法；= 0 视为零流量返回零 dp）
    - fluid_phase 未识别
    """

    code = "PRESSURE_DROP_INPUT_ERROR"
    status = 422


class PressureDropRangeError(PcsError):
    """PressureDrop Reynolds 数越界（工程经验区间外）。

    触发场景：
    - Re < 100（极低雷诺数 → 微观尺度 / 非连续介质假设失效）
    - Re > 1e8（极高雷诺数 → Darcy-Weisbach 经验公式失效）
    """

    code = "PRESSURE_DROP_RANGE_ERROR"
    status = 422


# ---------------------------------------------------------------------------
# 类型：Fitting / PipeSegment / PressureDropResult
# ---------------------------------------------------------------------------


FittingType = Literal[
    "elbow_90",
    "elbow_45",
    "tee_branch",
    "tee_through",
    "valve_gate",
    "valve_ball",
    "reducer",
    "expander",
    "entrance",
    "exit",
]


@dataclass(frozen=True)
class Fitting:
    """管件（局部阻力件）。

    Attributes:
        type: 管件类型（Crane TP-410 分类）
        K: 显式局部阻力系数；None 时按 type 查默认 K 值表
    """

    type: FittingType
    K: float | None = None


@dataclass(frozen=True)
class PipeSegment:
    """管道段：直管 + fittings 集合。

    Attributes:
        L_m: 直管长度 (m)
        D_m: 管内径 (m)
        roughness_m: 绝对粗糙度 (m)（Crane TP-410 / 种子 pipe_roughness_default）
        fluid_density: 流体密度 (kg/m³)
        fluid_viscosity: 流体动力粘度 (Pa·s)
        flow_rate_m3s: 体积流量 (m³/s)
        fittings: 管件列表（局部阻力）
    """

    L_m: float
    D_m: float
    roughness_m: float
    fluid_density: float
    fluid_viscosity: float
    flow_rate_m3s: float
    fittings: list[Fitting] = field(default_factory=list)


@dataclass(frozen=True)
class PressureDropResult:
    """单相压降计算结果。

    Attributes:
        dp_friction_pa: 直管摩阻压降 (Pa)
        dp_fittings_pa: fittings 局部阻力压降 (Pa)
        dp_total_pa: 总压降 (Pa) = dp_friction_pa + dp_fittings_pa
        dp_total_kpa_per_100m: 总压降折算 (kPa/100m 当量) = dp_total_pa/1000 × 100/L_m
        friction_factor: Darcy 摩擦系数 f（Colebrook 求解或层流 64/Re）
        reynolds: 雷诺数 Re
        flow_regime: "laminar" (Re<2300) 或 "turbulent" (Re≥2300)
        dp_ratio: dp_total / P1（用于路由判断）
        need_two_phase: 是否需路由至 P4-2-4 两相计算
    """

    dp_friction_pa: float
    dp_fittings_pa: float
    dp_total_pa: float
    dp_total_kpa_per_100m: float
    friction_factor: float
    reynolds: float
    flow_regime: Literal["laminar", "turbulent"]
    dp_ratio: float
    need_two_phase: bool


# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------


# ΔP/P₁ 路由阈值（Crane TP-410 + Perry's Chemical Engineers' Handbook 第 8 版 §6-18）
_TWO_PHASE_RATIO_THRESHOLD: Final[float] = 0.10


# Re 工程经验区间
_RE_LO: Final[float] = 100.0
_RE_HI: Final[float] = 1.0e8


# laminar / turbulent 临界
_RE_LAMINAR_MAX: Final[float] = 2300.0


# 默认物性（按 fluid_phase；与 sizing_service 对齐）
_DEFAULT_PHASE_PROPERTIES: Final[dict[str, tuple[float, float]]] = {
    # fluid_phase: (density_kg_m3, viscosity_Pa_s)
    "LIQUID": (1000.0, 1.0e-3),     # 水
    "GAS": (10.0, 1.0e-5),          # 常压气体近似
    "STEAM": (10.0, 1.0e-5),        # 饱和蒸汽近似
    "TWO_PHASE": (500.0, 1.0e-4),   # 简化的两相混合物近似（实际由 P4-2-4 接管）
}


# fittings K 值表 JSON 路径（tests/services/pipe/fixtures 共享；与单测同一 fixture
# → 单一真源；service 模块位于 app/services/pipe/，向上 3 级到 pcs-backend/）
_K_TABLE_FIXTURE_PATH: Final[Path] = (
    Path(__file__).resolve().parents[3]
    / "tests"
    / "services"
    / "pipe"
    / "fixtures"
    / "fittings_k_default.json"
)


# ---------------------------------------------------------------------------
# fittings K 值表加载
# ---------------------------------------------------------------------------


def load_fittings_k_default() -> dict[FittingType, float]:
    """加载 fittings K 值默认表（Crane TP-410 / Idelchik）。

    Returns:
        dict[type, K]：10 个 FittingType → K 值（无量纲）

    Raises:
        PressureDropInputError: K 表文件缺失 / JSON 损坏 / 类型字段缺失
    """
    if not _K_TABLE_FIXTURE_PATH.exists():
        raise PressureDropInputError(
            f"fittings K 值表 fixture 缺失：{_K_TABLE_FIXTURE_PATH}",
            details={"path": str(_K_TABLE_FIXTURE_PATH)},
        )
    raw = json.loads(_K_TABLE_FIXTURE_PATH.read_text(encoding="utf-8"))
    k_table: dict[FittingType, float] = {}
    for ftype in ("elbow_90", "elbow_45", "tee_branch", "tee_through",
                  "valve_gate", "valve_ball", "reducer", "expander",
                  "entrance", "exit"):
        if ftype not in raw:
            raise PressureDropInputError(
                f"fittings K 值表缺 type={ftype!r}",
                details={"missing_type": ftype, "available": list(raw.keys())},
            )
        k_table[ftype] = float(raw[ftype])  # type: ignore[assignment]
    return k_table


# 模块加载时固化（单一真源；fixture 缺失 → 启动失败）
_K_TABLE: Final[dict[FittingType, float]] = load_fittings_k_default()


# ---------------------------------------------------------------------------
# 入口：calc_pressure_drop
# ---------------------------------------------------------------------------


def calc_pressure_drop(
    seg: PipeSegment,
    *,
    P1_pa: float,
    fluid_phase: str,
) -> PressureDropResult:
    """单相压降计算（Darcy-Weisbach + Colebrook + fittings K 值表）。

    公式：
    - dp_friction = f × (L/D) × (ρ × v²/2)，f = Colebrook（Re≥2300）或 64/Re（Re<2300）
    - dp_fittings = (ΣK_i) × ρ × v²/2
    - dp_total = dp_friction + dp_fittings
    - dp_total_kpa_per_100m = dp_total / 1000 × 100 / L_m

    路由：
    - fluid_phase='TWO_PHASE' → need_two_phase=True（短路，P4-2-4 接管）
    - dp_total / P1 ≥ 10% → need_two_phase=True（路由至 P4-2-4）
    - 否则 → need_two_phase=False（不可压缩近似）

    Args:
        seg: 管道段（直管 + fittings 集合 + 流体物性）
        P1_pa: 上游压力 (Pa；入口压力)
        fluid_phase: 流相（LIQUID / GAS / STEAM / TWO_PHASE）

    Returns:
        PressureDropResult：含直管 / fittings / 总压降 + f + Re + 路由标记

    Raises:
        PressureDropInputError: P1 ≤ 0 / D ≤ 0 / ρ ≤ 0 / μ ≤ 0 / Q < 0 /
            fluid_phase 未识别
        PressureDropRangeError: Re < 100 或 Re > 1e8
    """
    # 输入校验
    if P1_pa <= 0:
        raise PressureDropInputError(
            f"P1_pa={P1_pa} 必须 > 0（上游压力退化 / 无效）",
            details={"P1_pa": P1_pa},
        )
    if seg.D_m <= 0:
        raise PressureDropInputError(
            f"seg.D_m={seg.D_m} 必须 > 0（管径退化 / 无效）",
            details={"D_m": seg.D_m},
        )
    if seg.fluid_density <= 0:
        raise PressureDropInputError(
            f"seg.fluid_density={seg.fluid_density} 必须 > 0",
            details={"fluid_density": seg.fluid_density},
        )
    if seg.fluid_viscosity <= 0:
        raise PressureDropInputError(
            f"seg.fluid_viscosity={seg.fluid_viscosity} 必须 > 0",
            details={"fluid_viscosity": seg.fluid_viscosity},
        )
    if seg.flow_rate_m3s < 0:
        raise PressureDropInputError(
            f"seg.flow_rate_m3s={seg.flow_rate_m3s} 不能为负（物理非法）",
            details={"flow_rate_m3s": seg.flow_rate_m3s},
        )
    if fluid_phase not in _DEFAULT_PHASE_PROPERTIES:
        raise PressureDropInputError(
            f"fluid_phase={fluid_phase!r} 未识别；支持："
            f"{sorted(_DEFAULT_PHASE_PROPERTIES.keys())}",
            details={"fluid_phase": fluid_phase},
        )

    # TWO_PHASE 短路：路由至 P4-2-4，不进入单相计算
    if fluid_phase == "TWO_PHASE":
        return PressureDropResult(
            dp_friction_pa=0.0,
            dp_fittings_pa=0.0,
            dp_total_pa=0.0,
            dp_total_kpa_per_100m=0.0,
            friction_factor=0.0,
            reynolds=0.0,
            flow_regime="laminar",
            dp_ratio=0.0,
            need_two_phase=True,
        )

    # 流量为 0：返回零 dp，不触发 Re 越界检查
    if seg.flow_rate_m3s == 0.0:
        return PressureDropResult(
            dp_friction_pa=0.0,
            dp_fittings_pa=0.0,
            dp_total_pa=0.0,
            dp_total_kpa_per_100m=0.0,
            friction_factor=0.0,
            reynolds=0.0,
            flow_regime="laminar",
            dp_ratio=0.0,
            need_two_phase=False,
        )

    # 计算速度 + 雷诺数
    A = math.pi * seg.D_m ** 2 / 4.0
    v = seg.flow_rate_m3s / A
    Re = seg.fluid_density * v * seg.D_m / seg.fluid_viscosity

    # Re 越界检查
    if Re < _RE_LO:
        raise PressureDropRangeError(
            f"Re={Re:.2f} < {_RE_LO}（极低雷诺数；非连续介质假设失效）",
            details={"reynolds": Re, "min_Re": _RE_LO},
        )
    if Re > _RE_HI:
        raise PressureDropRangeError(
            f"Re={Re:.2e} > {_RE_HI:.0e}（极高雷诺数；Darcy-Weisbach 经验失效）",
            details={"reynolds": Re, "max_Re": _RE_HI},
        )

    flow_regime: Literal["laminar", "turbulent"] = (
        "laminar" if Re < _RE_LAMINAR_MAX else "turbulent"
    )

    # Colebrook 求解（复用 sizing_service._colebrook_f）
    f = _colebrook_f(
        D_m=seg.D_m,
        v_ms=v,
        rho=seg.fluid_density,
        mu=seg.fluid_viscosity,
        eps_m=seg.roughness_m,
    )

    # Darcy-Weisbach 直管摩阻
    dp_friction = f * (seg.L_m / seg.D_m) * (seg.fluid_density * v ** 2 / 2.0)

    # fittings 局部阻力累加
    K_sum = 0.0
    for fit in seg.fittings:
        K_sum += fit.K if fit.K is not None else _K_TABLE[fit.type]
    dp_fittings = K_sum * seg.fluid_density * v ** 2 / 2.0

    dp_total = dp_friction + dp_fittings
    dp_total_kpa_per_100m = dp_total / 1000.0 * (100.0 / seg.L_m)

    # 路由：dp_total / P1 ≥ 10% → need_two_phase=True
    dp_ratio = dp_total / P1_pa
    need_two_phase = dp_ratio >= _TWO_PHASE_RATIO_THRESHOLD

    return PressureDropResult(
        dp_friction_pa=dp_friction,
        dp_fittings_pa=dp_fittings,
        dp_total_pa=dp_total,
        dp_total_kpa_per_100m=dp_total_kpa_per_100m,
        friction_factor=f,
        reynolds=Re,
        flow_regime=flow_regime,
        dp_ratio=dp_ratio,
        need_two_phase=need_two_phase,
    )


__all__ = [
    "Fitting",
    "FittingType",
    "PipeSegment",
    "PressureDropInputError",
    "PressureDropRangeError",
    "PressureDropResult",
    "calc_pressure_drop",
    "load_fittings_k_default",
]