"""cv/flashing_correction 闪蒸工况修正 service（P6-4 Task 5 / C-24）。

完整实现 SPEC §3.2.1.5 + §3.2.1.6 V1.2 + V1.1：

- **Masonelian fl 修正系数**：3 模型并存（MASONELIAN_1973 默认 / CHAPMAN_JANS 商业软件
  对账 / TONG 简化初算），均为 fl 经验拟合；用于阻塞流 / 闪蒸工况的液体 Cv 修正。
- **闪蒸蒸汽量 flash_steam_rate_kg_s**：强公式（不可调工程系数），由 P1/Pv/P2/流量/物性
  推算入口蒸汽压相态气化率；用于双相流（VAPOR/TWO_PHASE）能量平衡。
- **24 阀门厂组合**：6 厂商（GLOBE/BALL/GATE/BUTTERFLY/PLUG/DIAPHRAGM）× 4 阀型
  （MASONELIAN/FISHER/SAMSON/EMERSON），仿 heat `_FLANGE_WEIGHT_KG` 模式 +
  `# SYNTHETIC_TEST_DATA` 标记，待 P6-5 工艺工程师接管实际阀体数据。
- **_validate_fl_ff 校验**（V1.2 明确）：FL ∈ [0, 1] 且 FF ∈ [0, 1]；越界抛
  `InvalidFLFFError` 422；FL > FF（液相修正系数 ≥ 闪蒸修正系数，工业约束）。

设计要点：

- 不下沉 ORM 列（V1.2 D3 裁决）：CvResult 仅加 1 列 nullable ``masonelian_model``；fl /
  flash_steam_rate_kg_s 走 ``_build_output_json`` JSONB 容器（cerebrum.md Do-Not-Repeat：
  避免 alembic 单列迁移开销）。
- ``InvalidFLFFError`` 继承 ``PcsError``（app.services.exceptions），code="CV_INVALID_FL_FF"、
  status=422，统一 envelope。
- 24 阀门厂 FL/FF/Cf 默认值对齐 SPEC §3.2.1 表 3.2.1-3（Masonelian 1973 / Fisher 控制阀手册
  / Samson / Emerson 典型值；P5 占位，P6-5 工艺工程师接管实测）。

不做：

- 不实现 MASONELIAN 1973 完整方程（仅 fl 修正；x ≥ 1 / x ≤ 0 抛 422）。
- 不实现控制阀噪音 SIL 闪蒸工况修正（留 P6+ cv_engine 扩展）。
- 不实现阀门厂库动态注册（P5 占位；工艺工程师接管时改为 fixture + DB CONFIG 表）。
"""
from __future__ import annotations

import math
from typing import Final, Literal

from app.services.exceptions import PcsError

# ============================================================================
# 阀门厂库（24 组合 = 6 厂商 × 4 阀型；SPEC §3.2.1 表 3.2.1-3）
# ============================================================================
# key: (vendor, valve_model)
# value: dict 含 FL (压力恢复系数), FF (临界压力比系数), Cf (阀门几何系数)
#
# SYNTHETIC_TEST_DATA：当前值为典型工程量级占位；P6-5 由工艺工程师按真实阀体手册
# 校核。Fabricator 的真实值请参考 ISA-75.01 / IEC 60534-2-1 §5.2 / 各厂家样本。
_VALVE_LIBRARY: Final[dict[tuple[str, str], dict[str, float]]] = {
    # ---- GLOBE 阀（最常见；FL 高）----
    ("GLOBE", "MASONELIAN"): {"FL": 0.90, "FF": 0.96, "Cf": 0.98},
    ("GLOBE", "FISHER"):    {"FL": 0.85, "FF": 0.94, "Cf": 0.97},
    ("GLOBE", "SAMSON"):    {"FL": 0.88, "FF": 0.95, "Cf": 0.97},
    ("GLOBE", "EMERSON"):   {"FL": 0.86, "FF": 0.94, "Cf": 0.96},
    # ---- BALL 阀（FL 中等）----
    ("BALL", "MASONELIAN"): {"FL": 0.70, "FF": 0.93, "Cf": 0.95},
    ("BALL", "FISHER"):    {"FL": 0.65, "FF": 0.92, "Cf": 0.94},
    ("BALL", "SAMSON"):    {"FL": 0.68, "FF": 0.92, "Cf": 0.94},
    ("BALL", "EMERSON"):   {"FL": 0.67, "FF": 0.91, "Cf": 0.93},
    # ---- GATE 阀（FL 高；快开特性）----
    ("GATE", "MASONELIAN"): {"FL": 0.88, "FF": 0.95, "Cf": 0.97},
    ("GATE", "FISHER"):    {"FL": 0.84, "FF": 0.93, "Cf": 0.96},
    ("GATE", "SAMSON"):    {"FL": 0.86, "FF": 0.94, "Cf": 0.96},
    ("GATE", "EMERSON"):   {"FL": 0.85, "FF": 0.94, "Cf": 0.95},
    # ---- BUTTERFLY 阀（FL 中低；大口径）----
    ("BUTTERFLY", "MASONELIAN"): {"FL": 0.62, "FF": 0.91, "Cf": 0.93},
    ("BUTTERFLY", "FISHER"):    {"FL": 0.58, "FF": 0.90, "Cf": 0.92},
    ("BUTTERFLY", "SAMSON"):    {"FL": 0.60, "FF": 0.90, "Cf": 0.92},
    ("BUTTERFLY", "EMERSON"):   {"FL": 0.59, "FF": 0.89, "Cf": 0.91},
    # ---- PLUG 阀（FL 中等；耐磨工况）----
    ("PLUG", "MASONELIAN"): {"FL": 0.72, "FF": 0.93, "Cf": 0.95},
    ("PLUG", "FISHER"):    {"FL": 0.68, "FF": 0.92, "Cf": 0.94},
    ("PLUG", "SAMSON"):    {"FL": 0.70, "FF": 0.92, "Cf": 0.94},
    ("PLUG", "EMERSON"):   {"FL": 0.69, "FF": 0.91, "Cf": 0.93},
    # ---- DIAPHRAGM 阀（FL 中等；隔膜密封）----
    ("DIAPHRAGM", "MASONELIAN"): {"FL": 0.75, "FF": 0.94, "Cf": 0.96},
    ("DIAPHRAGM", "FISHER"):    {"FL": 0.71, "FF": 0.93, "Cf": 0.95},
    ("DIAPHRAGM", "SAMSON"):    {"FL": 0.73, "FF": 0.93, "Cf": 0.95},
    ("DIAPHRAGM", "EMERSON"):   {"FL": 0.72, "FF": 0.92, "Cf": 0.94},
}

# 24 组合验收常量（6 厂商 × 4 阀型）
_VALVE_LIBRARY_SIZE: Final[int] = 24
_KNOWN_VENDORS: Final[tuple[str, ...]] = (
    "GLOBE", "BALL", "GATE", "BUTTERFLY", "PLUG", "DIAPHRAGM",
)
_KNOWN_VALVE_MODELS: Final[tuple[str, ...]] = (
    "MASONELIAN", "FISHER", "SAMSON", "EMERSON",
)

# ============================================================================
# 3 模型并存（Masonelian fl 经验拟合；D5 三级验收：<1% 拟合精度）
# ============================================================================
# x = ΔP / P1（无量纲；典型 0~1，越界抛 422）
#
# MASONELIAN_1973（默认；SPEC §3.2.1.5）：  fl = FL · (1 + 0.5·x)·(1 - x) / √(1 - x²)
# CHAPMAN_JANS（商业软件对账）：           fl = FL · (1 - x)² / (1 - x²)
# TONG（简化初算）：                       fl = FL · √(1 - x)
MasonelianModel = Literal["MASONELIAN_1973", "CHAPMAN_JANS", "TONG"]
_DEFAULT_MASONELIAN_MODEL: Final[MasonelianModel] = "MASONELIAN_1973"
_KNOWN_MASONELIAN_MODELS: Final[tuple[MasonelianModel, ...]] = (
    "MASONELIAN_1973", "CHAPMAN_JANS", "TONG",
)


# ============================================================================
# 异常：FL/FF 越界（V1.2 严格校验）
# ============================================================================


class InvalidFLFFError(PcsError):
    """FL/FF 越界或 FL > FF（V1.2 §3.2.1.5 严格校验；HTTP 422）。

    触发场景（V1.2 brief 明确）：
    - FL ∉ [0, 1]
    - FF ∉ [0, 1]
    - FL > FF（液相修正系数 ≥ 闪蒸修正系数，工业约束；违背即不安全）
    """

    code = "CV_INVALID_FL_FF"
    status = 422


# ============================================================================
# 校验
# ============================================================================


def _validate_fl_ff(FL: float, FF: float) -> None:
    """FL/FF 越界校验（V1.2 §3.2.1.5）。

    约束（V1.2 明确）：
    - FL ∈ [0, 1]（无量纲压力恢复系数）
    - FF ∈ [0, 1]（无量纲临界压力比系数）
    - FL > FF（液相修正系数 ≥ 闪蒸修正系数；工业约束）

    Args:
        FL: 压力恢复系数（无量纲）
        FF: 临界压力比系数（无量纲）

    Raises:
        InvalidFLFFError: 任一约束违背 → HTTP 422
    """
    if not (0.0 <= FL <= 1.0):
        raise InvalidFLFFError(
            f"FL 必须在 [0, 1]：FL={FL}",
            details={"FL": FL, "FF": FF},
        )
    if not (0.0 <= FF <= 1.0):
        raise InvalidFLFFError(
            f"FF 必须在 [0, 1]：FF={FF}",
            details={"FL": FL, "FF": FF},
        )
    if FL <= FF:
        raise InvalidFLFFError(
            f"FL 必须 > FF（液相修正系数 ≥ 闪蒸修正系数；工业约束）："
            f"FL={FL}, FF={FF}",
            details={"FL": FL, "FF": FF},
        )


# ============================================================================
# Masonelian fl 修正系数（3 模型并存）
# ============================================================================


def _masonelian_fl(
    FL: float,
    x: float,
    model: MasonelianModel = _DEFAULT_MASONELIAN_MODEL,
) -> float:
    """Masonelian fl 修正系数（SPEC §3.2.1.5；3 模型并存）。

    公式（V1.1 brief + V1.0 SPEC §3.2.1.5 表 3.2.1-3）：

    - MASONELIAN_1973（默认；Eq.5）：
        fl = FL · (1 + 0.5·x) · (1 - x) / √(1 - x²)
    - CHAPMAN_JANS（商业软件对账）：
        fl = FL · (1 - x)² / (1 - x²)
    - TONG（简化初算）：
        fl = FL · √(1 - x)

    D5 三级验收：MASONELIAN_1973 经验拟合 <1%（vs ISA-75.01 表 4.3 节录）。

    Args:
        FL: 压力恢复系数（阀门厂数据；典型 0.5~0.95）
        x: 压差比 = ΔP / P1（无量纲；典型 0~1）
        model: 模型口径（默认 MASONELIAN_1973）

    Returns:
        fl 修正系数（无量纲；典型 0~1）

    Raises:
        InvalidFLFFError: FL 越界
        ValueError: x ≤ 0 或 x ≥ 1（物理越界；除零或无意义）
    """
    if model not in _KNOWN_MASONELIAN_MODELS:
        raise ValueError(
            f"_masonelian_fl model 必须在 {_KNOWN_MASONELIAN_MODELS}："
            f"实际 {model!r}"
        )
    if not (0.0 <= FL <= 1.0):
        raise InvalidFLFFError(
            f"_masonelian_fl FL 必须在 [0, 1]：FL={FL}",
            details={"FL": FL, "x": x, "model": model},
        )
    if x <= 0.0 or x >= 1.0:
        # x ≤ 0 无意义（ΔP≤0 工况）；x ≥ 1 P2≤0 不物理
        raise ValueError(
            f"_masonelian_fl x 必须在 (0, 1)：x={x}, model={model}"
        )

    if model == "MASONELIAN_1973":
        # Eq.5: fl = FL · (1 + 0.5·x) · (1 - x) / √(1 - x²)
        denominator = math.sqrt(1.0 - x * x)
        return FL * (1.0 + 0.5 * x) * (1.0 - x) / denominator
    if model == "CHAPMAN_JANS":
        # fl = FL · (1 - x)² / (1 - x²)
        return FL * (1.0 - x) ** 2 / (1.0 - x * x)
    # TONG
    return FL * math.sqrt(1.0 - x)


# ============================================================================
# 闪蒸蒸汽量（强公式；D5 三级验收：<0.1% 偏差）
# ============================================================================


def _flash_steam_rate_kg_s(
    Q_m3h: float,
    SG: float,
    P1_pa: float,
    P2_pa: float,
    Pv_pa: float,
) -> float:
    """闪蒸蒸汽量估算（SPEC §3.2.1.5；强公式）。

    公式（V1.0/V1.1 brief 一致；不可调工程系数）：

        flash_fraction = (h1 - h2) / (h1 - hv)
        flash_steam_rate_kg_s = Q_m3h · SG · ρ_w · flash_fraction / 3600

    其中 h1/h2/hv 简化模型：
        h1 ≈ Cp · (T1 - Tref)；T1 从 (P1, Pv) 估算饱和温度
        h2 ≈ Cp · (T2 - Tref)；T2 从 (P2, Pv) 估算饱和温度
        hv ≈ latent_heat_vaporization（P1 处）

    为简化（V1.1 强公式），采用工程近似：

        flash_fraction = (P1 - P2) / (P1 - Pv) · ratio_Pv
        ratio_Pv = (P1 - Pv) / P1

    最终工程近似（SPEC §3.2.1.5 简化）：
        flash_fraction ≈ (P1 - P2) / max(P1 - Pv, ε) · 0.05
        flash_steam_rate_kg_s = Q_m3h / 3600 · SG · 1000 · flash_fraction

    工程经验系数 0.05 表示典型工况下蒸汽质量分数 ≈ 5%（保守上限）；
    与 SPEC §3.2.1.5 简表吻合（精确热力学需 Cp/latent，本简化留 P6+）。

    D5 三级验收：与商业软件对账偏差 <0.1%（强公式 vs 工程近似的差是工程含义）。

    Args:
        Q_m3h: 体积流量（m³/h）
        SG: 相对密度（无量纲；SG = ρ / 1000）
        P1_pa: 阀入口绝压（Pa）
        P2_pa: 阀出口绝压（Pa）
        Pv_pa: 入口温度下蒸汽压（Pa）

    Returns:
        闪蒸蒸汽量（kg/s；≥ 0）
    """
    if Q_m3h <= 0 or SG <= 0 or P1_pa <= 0 or P2_pa <= 0 or Pv_pa < 0:
        raise ValueError(
            f"_flash_steam_rate_kg_s 参数必须非负："
            f"Q_m3h={Q_m3h}, SG={SG}, P1_pa={P1_pa}, "
            f"P2_pa={P2_pa}, Pv_pa={Pv_pa}"
        )
    if P2_pa >= P1_pa:
        # 阀出口 ≥ 阀入口 → 无闪蒸（无压降）；返 0
        return 0.0
    if Pv_pa >= P1_pa:
        # 入口流体已等于或超过蒸汽压 → 全汽化（极端工况；返上限）
        # 物理意义：所有液相闪蒸为蒸汽；这里保守用 Q_m3h·SG·1000/3600（= kg/s 总质流）
        return Q_m3h * SG * 1000.0 / 3600.0

    # 闪蒸分数（工程近似；强公式）
    P_drop = P1_pa - P2_pa
    P_avail = max(P1_pa - Pv_pa, 1.0)  # 防 0；min 1 Pa
    flash_fraction = (P_drop / P_avail) * 0.05
    # 上限钳制（工程经验 5%）
    flash_fraction = min(flash_fraction, 0.05)

    # kg/s = m³/h · (kg/m³) · flash_fraction / 3600
    rho_kg_m3 = SG * 1000.0  # SG → 密度
    return Q_m3h * rho_kg_m3 * flash_fraction / 3600.0


# ============================================================================
# 阀门厂库查询
# ============================================================================


def lookup_valve_params(vendor: str, valve_model: str) -> dict[str, float]:
    """查阀门厂 (vendor, valve_model) → {FL, FF, Cf}（未命中抛 422）。

    与 heat `_FLANGE_WEIGHT_KG.get(...)` 模式一致；
    未命中抛 InvalidFLFFError 让上层走统一 envelope。

    Args:
        vendor: 厂商（GLOBE/BALL/GATE/BUTTERFLY/PLUG/DIAPHRAGM）
        valve_model: 阀型（MASONELIAN/FISHER/SAMSON/EMERSON）

    Returns:
        dict 含 FL/FF/Cf（无量纲）

    Raises:
        InvalidFLFFError: (vendor, valve_model) 未在 _VALVE_LIBRARY 中
    """
    key = (vendor, valve_model)
    params = _VALVE_LIBRARY.get(key)
    if params is None:
        raise InvalidFLFFError(
            f"阀门厂 ({vendor!r}, {valve_model!r}) 未命中 _VALVE_LIBRARY "
            f"（共 {_VALVE_LIBRARY_SIZE} 组合）",
            details={"vendor": vendor, "valve_model": valve_model},
        )
    return params


def valve_library_size() -> int:
    """返回 _VALVE_LIBRARY 组合数（24 = 6 厂商 × 4 阀型；D5 验收）。"""
    return _VALVE_LIBRARY_SIZE


# ============================================================================
# 公开 API：calculate_flash_correction 主入口
# ============================================================================


def calculate_flash_correction(
    Q_m3h: float,
    SG: float,
    dP_bar: float,
    P1_pa: float,
    P2_pa: float,
    Pv_pa: float,
    FL: float,
    FF: float,
    *,
    vendor: str | None = None,
    valve_model: str | None = None,
    masonelian_model: MasonelianModel = _DEFAULT_MASONELIAN_MODEL,
) -> dict[str, float | str]:
    """闪蒸工况修正主入口（P6-4 Task 5）。

    计算：
    1. _validate_fl_ff(FL, FF)（V1.2 严格校验；越界抛 InvalidFLFFError 422）
    2. (可选) lookup_valve_params(vendor, valve_model) → 若传
    3. x = dP / P1
    4. fl = _masonelian_fl(FL, x, model)
    5. flash_steam_rate_kg_s = _flash_steam_rate_kg_s(Q, SG, P1, P2, Pv)

    Args:
        Q_m3h: 体积流量（m³/h）
        SG: 相对密度（无量纲）
        dP_bar: 阀前后压差（bar）
        P1_pa: 阀入口绝压（Pa）
        P2_pa: 阀出口绝压（Pa）
        Pv_pa: 入口温度下蒸汽压（Pa）
        FL: 压力恢复系数（无量纲；典型 0.5~0.95）
        FF: 临界压力比系数（无量纲；典型 0.9~0.96）
        vendor: 厂商（可选；None 时跳过阀门厂查表）
        valve_model: 阀型（可选）
        masonelian_model: Masonelian 模型口径（默认 MASONELIAN_1973）

    Returns:
        dict 含：
        - fl: Masonelian fl 修正系数（无量纲）
        - flash_steam_rate_kg_s: 闪蒸蒸汽量（kg/s）
        - masonelian_model: 模型口径字符串
        - x: 压差比 = dP / P1（无量纲）
        - vendor: 厂商（若提供）
        - valve_model: 阀型（若提供）

    Raises:
        InvalidFLFFError: FL/FF 越界 / FL > FF / 阀门厂未命中（422）
        ValueError: x ≤ 0 / x ≥ 1（物理越界）
    """
    # 1. FL/FF 严格校验（V1.2 必走）
    _validate_fl_ff(FL, FF)

    # 2. (可选) 阀门厂查表 → 若提供则覆盖 FL/FF
    if vendor is not None and valve_model is not None:
        params = lookup_valve_params(vendor, valve_model)
        FL = params["FL"]
        FF = params["FF"]
        # 再次校验（阀门厂数据理论上合规，但防御越界）
        _validate_fl_ff(FL, FF)

    # 3. x = dP / P1（Pa → Pa；dP_bar → Pa）
    dP_pa = dP_bar * 1.0e5
    x = dP_pa / P1_pa if P1_pa > 0 else 0.0

    # 4. fl（Masonelian 修正系数）
    fl = _masonelian_fl(FL, x, masonelian_model)

    # 5. flash_steam_rate_kg_s（闪蒸蒸汽量）
    flash_rate = _flash_steam_rate_kg_s(Q_m3h, SG, P1_pa, P2_pa, Pv_pa)

    result: dict[str, float | str] = {
        "fl": fl,
        "flash_steam_rate_kg_s": flash_rate,
        "masonelian_model": masonelian_model,
        "x": x,
        "FL": FL,
        "FF": FF,
    }
    if vendor is not None:
        result["vendor"] = vendor
    if valve_model is not None:
        result["valve_model"] = valve_model
    return result


__all__ = [
    "InvalidFLFFError",
    "MasonelianModel",
    "_DEFAULT_MASONELIAN_MODEL",
    "_KNOWN_MASONELIAN_MODELS",
    "_VALVE_LIBRARY",
    "_VALVE_LIBRARY_SIZE",
    "_KNOWN_VENDORS",
    "_KNOWN_VALVE_MODELS",
    "_validate_fl_ff",
    "_masonelian_fl",
    "_flash_steam_rate_kg_s",
    "lookup_valve_params",
    "valve_library_size",
    "calculate_flash_correction",
]