"""P4-2-3：单相压降服务（Darcy-Weisbach + Colebrook + fittings K 值表 + 路由）。

P4-2-5 扩展（流态分支 + confidence 字段；不改 Colebrook / K 表数值）：
- flow_regime 3 态：LAMINAR (Re<2000) / TRANSITION (2000≤Re≤4000) / TURBULENT (Re>4000)
- check_result 强制 WARNING for TRANSITION（reason="TRANSITION_REGIME"）
- confidence HIGH/MEDIUM/LOW 聚合（湍流 Re>10000 HIGH；过渡/低 Re MEDIUM/LOW）
- K 表 reynolds_applicable 标注（v2 schema 嵌套对象）；get_fitting_k
  签名预留 Re 参数（P5+ 接入 Hooper 2-K / Darby 3-K 时改内部）

R1 fix（additive 精度护栏升级；不改 P4-2-5 已落地契约）：
- 过渡区 f 策略：Colebrook 迭代 → 线性插值 [2320, 4000]（f_lam=64/Re 与
  f_turb=Colebrook 之间；外推 Re<2320 时沿公式自然趋近 64/Re）
- confidence 阈值收紧：Re<4000 → LOW（Crane K 表 Re 区间外；无论 f 多准）；
  Re∈[4000, 10000) → MEDIUM；Re≥10000 → HIGH（Crane K 表完全适用）
- P4-2-5 透传语义零变更：pipe_chain_service 链式 confidence 聚合规则不变

公式：
- Darcy-Weisbach 直管摩阻：ΔP_friction = f × (L/D) × (ρ × v²/2)
- 摩擦系数 f：
  LAMINAR (Re<2000) → f = 64/Re（解析精确）
  TRANSITION (2000≤Re≤4000) → 线性插值 [2320, 4000]：
    f_lam = 64/Re, f_turb = Colebrook(Re),
    α = (Re - 2320) / (4000 - 2320),
    f = f_lam + α × (f_turb - f_lam)
  TURBULENT (Re>4000) → Colebrook-White 隐式 brentq 求解
  1/√f = -2 log10(ε/(3.7D) + 2.51/(Re√f))，Re = ρvD/μ
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

# P4-2-5：3 态流场（替代 P4-2-3 2 态 lam/turb）
FlowRegime3 = Literal["LAMINAR", "TRANSITION", "TURBULENT"]

# P4-2-5：单管段校核档位
PressureDropCheck = Literal["PASS", "WARNING", "FAIL"]

# P4-2-5：单管段置信度（链式聚合用）
PressureDropConfidence = Literal["HIGH", "MEDIUM", "LOW"]


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
class FittingKMeta:
    """P4-2-5 fittings K 值元数据（K 表 v2 schema）。

    Attributes:
        k: K 值（无量纲；Crane 固定；P5+ 改 Hooper 2-K / Darby 3-K）
        reynolds_applicable: 适用 Re 区间（informational；当前实现忽略）
        k_factor_confidence: K 系数置信度（Crane 表适用度）
        source: 数据源（Crane TP-410 / Idelchik 等）
    """

    k: float
    reynolds_applicable: str
    k_factor_confidence: PressureDropConfidence
    source: str


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
        flow_regime: LAMINAR (Re<2000) / TRANSITION (2000≤Re≤4000) /
            TURBULENT (Re>4000)
        dp_ratio: dp_total / P1（用于路由判断）
        need_two_phase: 是否需路由至 P4-2-4 两相计算
        check_result: 校核档位 PASS / WARNING / FAIL
        check_result_reason: 校核原因（TRANSITION_REGIME 等）
        confidence: 置信度 HIGH / MEDIUM / LOW（链式聚合；任一 LOW → 整体 LOW）
    """

    dp_friction_pa: float
    dp_fittings_pa: float
    dp_total_pa: float
    dp_total_kpa_per_100m: float
    friction_factor: float
    reynolds: float
    flow_regime: FlowRegime3
    dp_ratio: float
    need_two_phase: bool
    check_result: PressureDropCheck
    check_result_reason: str | None
    confidence: PressureDropConfidence


# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------


# ΔP/P₁ 路由阈值（Crane TP-410 + Perry's Chemical Engineers' Handbook 第 8 版 §6-18）
_TWO_PHASE_RATIO_THRESHOLD: Final[float] = 0.10


# Re 工程经验区间（保留 P4-2-3 既有 100/1e8 极值）
_RE_LO: Final[float] = 100.0
_RE_HI: Final[float] = 1.0e8


# P4-2-5：3 态流场边界
# - LAMINAR:  Re < 2000（Crane TP-410 + White, "Viscous Fluid Flow" 第 3 版 §3-3）
# - TRANSITION: 2000 ≤ Re ≤ 4000（线性插值 [2320, 4000] + check=WARNING；非稳态）
# - TURBULENT: Re > 4000（Crane TP-410 标准湍流范围下限）
_RE_LAMINAR_MAX: Final[float] = 2000.0
# R1 fix: 过渡区 f 线性插值下限（Nikuradse 物理临界 Re；Re<2320 时沿插值公式
# 外推 → 趋近 64/Re，不退化）
_RE_TRANSITION_LO: Final[float] = 2320.0
_RE_TRANSITION_HI: Final[float] = 4000.0

# R1 fix: confidence 阈值（Crane K 表 Re 适用度决定性因素；f 精度次要）
# - HIGH: Re ≥ 10000（Crane K 表完全适用 + f Colebrook 高精度）
# - MEDIUM: Re ∈ [4000, 10000)（过渡区尾部湍流；f 适用但 K 表部分适用）
# - LOW: Re < 4000（Crane K 表 Re 区间外，无论 f 多准）
_RE_CONFIDENCE_HIGH_MIN: Final[float] = 10_000.0
_RE_CONFIDENCE_LOW_MAX: Final[float] = 4000.0


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
# 内部工具：Re → 流态 + confidence
# ---------------------------------------------------------------------------


def _classify_flow_regime(Re: float) -> FlowRegime3:
    """Re → 3 态流场分类（P4-2-5）。"""
    if Re < _RE_LAMINAR_MAX:
        return "LAMINAR"
    if Re <= _RE_TRANSITION_HI:
        return "TRANSITION"
    return "TURBULENT"


def _classify_confidence(
    regime: FlowRegime3, Re: float
) -> PressureDropConfidence:
    """流态 + Re → confidence（R1 fix）。

    R1 fix：Crane K 表 Re 适用度为决定性因素（f 精度次要）。
    - HIGH: Re ≥ 10000（Crane K 表完全适用 + f Colebrook 高精度）
    - MEDIUM: Re ∈ [4000, 10000)（过渡区尾部湍流；f 适用但 K 表部分适用）
    - LOW: Re < 4000（Crane K 表 Re 区间外；无论 f 多准 → LOW）

    说明：TRANSITION（无论 Re 在 [2000, 4000] 哪个位置）→ LOW（Crane K 不可信）。
    """
    if Re < _RE_CONFIDENCE_LOW_MAX:
        return "LOW"
    if Re >= _RE_CONFIDENCE_HIGH_MIN:
        return "HIGH"
    return "MEDIUM"


def _transition_friction_factor(
    reynolds: float,
    D_m: float,
    v_ms: float,
    rho: float,
    mu: float,
    eps_m: float,
) -> float:
    """过渡区 f 线性插值 [2320, 4000]（R1 fix）。

    公式：
        f_lam = 64 / Re（层流解析精确）
        f_turb = _colebrook_f(...)（湍流区 Colebrook brentq 迭代）
        α = (Re - 2320) / (4000 - 2320)
        f = f_lam + α × (f_turb - f_lam)

    说明：
    - Re ∈ [2320, 4000] 区间内严格线性插值
    - Re < 2320 时沿公式外推（α<0；f→f_lam=64/Re 自然趋近）
    - 区间外推范围 [2000, 2320] 仍可用，docstring 注明非严格物理定义；
      物理上 Nikuradse 临界 Re≈2320，故该区间插值仅作平滑过渡近似
    - 保证：Re=2320 时 f=f_lam=64/2320；Re=4000 时 f=f_turb（连续过渡）

    Args:
        reynolds: 雷诺数 Re（应满足 2000 ≤ Re ≤ 4000；外推可放宽）
        D_m: 管径 (m)
        v_ms: 流速 (m/s)
        rho: 流体密度 (kg/m³)
        mu: 动力粘度 (Pa·s)
        eps_m: 绝对粗糙度 (m)

    Returns:
        Darcy 摩擦系数 f
    """
    f_lam = 64.0 / reynolds
    f_turb = _colebrook_f(
        D_m=D_m,
        v_ms=v_ms,
        rho=rho,
        mu=mu,
        eps_m=eps_m,
    )
    alpha = (reynolds - _RE_TRANSITION_LO) / (_RE_TRANSITION_HI - _RE_TRANSITION_LO)
    return f_lam + alpha * (f_turb - f_lam)


def _classify_check(regime: FlowRegime3) -> tuple[PressureDropCheck, str | None]:
    """流态 → check_result + reason（P4-2-5）。

    - TRANSITION → WARNING（reason="TRANSITION_REGIME"）
    - LAMINAR / TURBULENT → PASS（None）
    """
    if regime == "TRANSITION":
        return "WARNING", "TRANSITION_REGIME"
    return "PASS", None


# ---------------------------------------------------------------------------
# fittings K 值表加载（v2 schema：嵌套对象 + 元数据）
# ---------------------------------------------------------------------------


def load_fittings_k_default() -> dict[FittingType, FittingKMeta]:
    """加载 fittings K 值默认表（Crane TP-410 / Idelchik；v2 schema）。

    Returns:
        dict[type, FittingKMeta]：10 个 FittingType → K 值 + 元数据

    Raises:
        PressureDropInputError: K 表文件缺失 / JSON 损坏 / 类型字段缺失 /
            schema v2 字段缺失
    """
    if not _K_TABLE_FIXTURE_PATH.exists():
        raise PressureDropInputError(
            f"fittings K 值表 fixture 缺失：{_K_TABLE_FIXTURE_PATH}",
            details={"path": str(_K_TABLE_FIXTURE_PATH)},
        )
    raw = json.loads(_K_TABLE_FIXTURE_PATH.read_text(encoding="utf-8"))
    k_table: dict[FittingType, FittingKMeta] = {}
    for ftype in (
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
    ):
        if ftype not in raw:
            raise PressureDropInputError(
                f"fittings K 值表缺 type={ftype!r}",
                details={"missing_type": ftype, "available": list(raw.keys())},
            )
        entry = raw[ftype]
        if not isinstance(entry, dict):
            raise PressureDropInputError(
                f"fittings K 值表 {ftype!r} 期望对象，得到 {type(entry).__name__} "
                f"（v2 schema 要求嵌套 k:v 结构）",
                details={"type": ftype, "got": type(entry).__name__},
            )
        # v2 schema 必填字段
        for field_name in ("k", "reynolds_applicable", "k_factor_confidence", "source"):
            if field_name not in entry:
                raise PressureDropInputError(
                    f"fittings K 值表 {ftype!r} 缺字段 {field_name!r}",
                    details={"type": ftype, "missing_field": field_name},
                )
        k_table[ftype] = FittingKMeta(  # type: ignore[assignment]
            k=float(entry["k"]),
            reynolds_applicable=str(entry["reynolds_applicable"]),
            k_factor_confidence=entry["k_factor_confidence"],  # type: ignore[assignment]
            source=str(entry["source"]),
        )
    return k_table


# 模块加载时固化（单一真源；fixture 缺失 → 启动失败）
_K_TABLE: Final[dict[FittingType, FittingKMeta]] = load_fittings_k_default()


# ---------------------------------------------------------------------------
# fittings K 值查询（带 Re/diameter 签名预留；P5+ 接入 Hooper 2-K / Darby 3-K）
# ---------------------------------------------------------------------------


def get_fitting_k(
    fitting_type: FittingType,
    *,
    diameter_m: float,
    reynolds: float,
) -> tuple[float, PressureDropConfidence]:
    """按 (fitting_type, diameter, Re) 取 K 值 + K 系数置信度。

    当前实现：返回 Crane 固定 K（P4-2-5 不变 K 表数值；约束"不重写 K 表"）。
    P5+ 接入：
    - Hooper 2-K 法（K = K1 / Re + K_inf(1 + 1/D)²；恒定 K1/K_inf 表）
    - Darby 3-K 法（K = K1/Re + K2(1 + K3/(D^(0.3)))²；分段 K1/K2/K3 表）
    接口签名已预留 diameter / reynolds 参数；内部届时改按 Re/D 算 K。

    Args:
        fitting_type: 管件类型（FittingType 之一）
        diameter_m: 管内径 (m；P5+ Hooper 2-K 用 1/D 项)
        reynolds: 雷诺数（P5+ Hooper 2-K / Darby 3-K 用 1/Re 项）
            当前实现忽略（保留 Crane 固定 K）

    Returns:
        (K, K 系数置信度)

    Raises:
        PressureDropInputError: fitting_type 不在 K 表 / diameter / Re 非法
    """
    if fitting_type not in _K_TABLE:
        raise PressureDropInputError(
            f"fittings K 值表无 type={fitting_type!r}",
            details={"type": fitting_type, "available": list(_K_TABLE.keys())},
        )
    if diameter_m <= 0.0:
        raise PressureDropInputError(
            f"diameter_m={diameter_m} 必须 > 0",
            details={"diameter_m": diameter_m},
        )
    if reynolds < 0.0:
        raise PressureDropInputError(
            f"reynolds={reynolds} 不能为负（物理非法）",
            details={"reynolds": reynolds},
        )
    meta = _K_TABLE[fitting_type]
    return meta.k, meta.k_factor_confidence


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

    P4-2-5 流态 + confidence + check_result：
    - LAMINAR (Re<2000) → f=64/Re；confidence=LOW（Crane K 表 Re 区间外）
    - TRANSITION (2000≤Re≤4000) → f=线性插值 [2320, 4000]；
      check_result=WARNING (reason="TRANSITION_REGIME")；confidence=LOW
      （R1 fix：Crane K 表 Re<4000 不可信，无论 f 精度如何）
    - TURBULENT (Re>4000) → Colebrook；
      Re≥10000 → confidence=HIGH；
      Re∈[4000, 10000) → confidence=MEDIUM

    Args:
        seg: 管道段（直管 + fittings 集合 + 流体物性）
        P1_pa: 上游压力 (Pa；入口压力)
        fluid_phase: 流相（LIQUID / GAS / STEAM / TWO_PHASE）

    Returns:
        PressureDropResult：含直管 / fittings / 总压降 + f + Re + 流态 + confidence + check

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
            flow_regime="LAMINAR",  # 占位；两相不走单相
            dp_ratio=0.0,
            need_two_phase=True,
            check_result="PASS",
            check_result_reason=None,
            confidence="LOW",
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
            flow_regime="LAMINAR",  # 占位；零流量
            dp_ratio=0.0,
            need_two_phase=False,
            check_result="PASS",
            check_result_reason=None,
            confidence="LOW",
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

    # P4-2-5：3 态流场分类
    flow_regime = _classify_flow_regime(Re)

    # 摩擦系数 f
    if flow_regime == "LAMINAR":
        # 层流：f = 64/Re 解析精确（Crane TP-410 + White §3-3）
        f = 64.0 / Re
    elif flow_regime == "TRANSITION":
        # R1 fix：过渡区 f 线性插值 [2320, 4000]（保证数值连续性 + f 平滑过渡）
        f = _transition_friction_factor(
            reynolds=Re,
            D_m=seg.D_m,
            v_ms=v,
            rho=seg.fluid_density,
            mu=seg.fluid_viscosity,
            eps_m=seg.roughness_m,
        )
    else:
        # TURBULENT：Colebrook 隐式 brentq 求解（复用 sizing_service）
        f = _colebrook_f(
            D_m=seg.D_m,
            v_ms=v,
            rho=seg.fluid_density,
            mu=seg.fluid_viscosity,
            eps_m=seg.roughness_m,
        )

    # Darcy-Weisbach 直管摩阻
    dp_friction = f * (seg.L_m / seg.D_m) * (seg.fluid_density * v ** 2 / 2.0)

    # fittings 局部阻力累加（get_fitting_k 签名预留 Re；当前按 Crane 固定 K）
    K_sum = 0.0
    for fit in seg.fittings:
        if fit.K is not None:
            K_sum += fit.K
        else:
            k_val, _k_conf = get_fitting_k(
                fit.type, diameter_m=seg.D_m, reynolds=Re
            )
            K_sum += k_val
    dp_fittings = K_sum * seg.fluid_density * v ** 2 / 2.0

    dp_total = dp_friction + dp_fittings
    dp_total_kpa_per_100m = dp_total / 1000.0 * (100.0 / seg.L_m)

    # 路由：dp_total / P1 ≥ 10% → need_two_phase=True
    dp_ratio = dp_total / P1_pa
    need_two_phase = dp_ratio >= _TWO_PHASE_RATIO_THRESHOLD

    # P4-2-5：confidence + check_result
    confidence = _classify_confidence(flow_regime, Re)
    check_result, check_reason = _classify_check(flow_regime)

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
        check_result=check_result,
        check_result_reason=check_reason,
        confidence=confidence,
    )


__all__ = [
    "Fitting",
    "FittingKMeta",
    "FittingType",
    "FlowRegime3",
    "PipeSegment",
    "PressureDropCheck",
    "PressureDropConfidence",
    "PressureDropInputError",
    "PressureDropRangeError",
    "PressureDropResult",
    "calc_pressure_drop",
    "get_fitting_k",
    "load_fittings_k_default",
]
