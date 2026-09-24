"""水跃共轭水深 + 能量损失（SPEC §3.2.6 第四项）。

矩形断面水跃方程（Bélanger 方程）：

    h₂/h₁ = 0.5 × (√(1 + 8 × Fr₁²) − 1)

其中：

- ``h₁``：跃前水深（急流），m
- ``h₂``：跃后水深（缓流），m
- ``Fr₁``：跃前 Froude 数（v₁ / √(g × h₁)），无量纲

能量损失（Bélanger 方程推导）：

    ΔE = (h₂ − h₁)³ / (4 × h₁ × h₂)

跃型判定（基于 Fr₁；标准教科书五档分类）：

- Fr₁ ∈ [1.0, 1.7)：WAVY（波状水跃）
- Fr₁ ∈ [1.7, 2.5)：WEAK（弱水跃）
- Fr₁ ∈ [2.5, 4.5)：OSCILLATING（振荡水跃）
- Fr₁ ∈ [4.5, 9.0)：STEADY（稳定水跃）
- Fr₁ ≥ 9.0：STRONG（强水跃）

手算独立校核：

例 1（h₁=0.5/v₁=5/g=9.81）：

    Fr₁ = 5/√(9.81×0.5) = 5/2.2150 = 2.258
    h₂ = (0.5/2) × (√(1 + 8×2.258²) − 1)
      = 0.25 × (√41.79 − 1)
      = 0.25 × (6.464 − 1)
      = 0.25 × 5.464
      = 1.366 m
    ΔE = (1.366 − 0.5)³ / (4 × 0.5 × 1.366)
       = 0.6496 / 2.732
       = 0.2378 m
    Fr₁=2.258 ∈ [1.7, 2.5) → WEAK（弱水跃）✓

例 2（h₁=0.5/Fr₁=5.0）：

    h₂ = (0.5/2) × (√(1 + 8×25) − 1)
      = 0.25 × (√201 − 1)
      = 0.25 × (14.178 − 1)
      = 0.25 × 13.178
      = 3.295 m
    ΔE = (3.295 − 0.5)³ / (4 × 0.5 × 3.295)
       = 21.81 / 6.590
       = 3.310 m
    Fr₁=5.0 ∈ [4.5, 9.0) → STEADY（稳定水跃）✓

例 3（h₁=0.5/Fr₁=1.5）：

    h₂ = (0.5/2) × (√(1 + 8×2.25) − 1)
      = 0.25 × (√19 − 1)
      = 0.25 × (4.359 − 1)
      = 0.25 × 3.359
      = 0.8398 m
    ΔE = (0.8398 − 0.5)³ / (4 × 0.5 × 0.8398)
       = 0.04612 / 1.680
       = 0.02746 m
    Fr₁=1.5 ∈ [1.0, 1.7) → WAVY（波状水跃）✓

P6-OPEN-001（G-01 degraded）决议：禁止 import fluids.open_channel，
本模块采用自研兜底（参照 ADR-0030 V1.2 决策 7）。
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from app.services.exceptions import PcsError

GRAVITY = 9.80665  # m/s²（标准重力加速度，CODATA 2018）


# 跃型枚举
JumpType = str  # "WAVY" / "WEAK" / "OSCILLATING" / "STEADY" / "STRONG"


@dataclass(frozen=True)
class JumpInput:
    """水跃计算输入（§3.2.6）。

    字段：

    - ``h1``：跃前水深 h₁（m，>0；急流水深）
    - ``v1``：跃前流速 v₁（m/s，>0）
    - ``gravity``：重力加速度（m/s²，默认 9.80665）
    """

    h1: float
    v1: float
    gravity: float = GRAVITY


@dataclass(frozen=True)
class JumpResult:
    """水跃计算输出（§3.2.6）。

    字段：

    - ``h2``：跃后水深 h₂（m）
    - ``fr1``：跃前 Froude 数
    - ``energy_loss``：ΔE = (h₂ − h₁)³ / (4 × h₁ × h₂)（m）
    - ``jump_type``："WAVY" / "WEAK" / "OSCILLATING" / "STEADY" / "STRONG"
    - ``v2``：跃后流速 v₂ = v₁ × h₁ / h₂（m/s）
    - ``formula_ref``：公式溯源标记，恒等于 "JUMP_§3.2.6"
    """

    h2: float
    fr1: float
    energy_loss: float
    jump_type: str
    v2: float
    formula_ref: str = "JUMP_§3.2.6"


class JumpInputError(PcsError):
    """水跃输入不合法（422）。

    触发场景：

    - h1 / v1 / gravity 非正
    - Fr1 < 1（无水跃，缓流到缓流不形成经典水跃）
    """

    code = "JUMP_INPUT_ERROR"
    status = 422


def _classify_jump(fr1: float) -> str:
    """基于 Fr₁ 五档跃型判定（标准教科书分类）。"""
    if fr1 < 1.0:
        return "WAVY"  # 物理上无跃，但兜底
    if fr1 < 1.7:
        return "WAVY"
    if fr1 < 2.5:
        return "WEAK"
    if fr1 < 4.5:
        return "OSCILLATING"
    if fr1 < 9.0:
        return "STEADY"
    return "STRONG"


def calc_hydraulic_jump(inp: JumpInput) -> JumpResult:
    """矩形断面水跃共轭水深 + 能量损失 + 跃型判定（§3.2.6）。

    实现步骤：

    1. 输入校验：h1 > 0 / v1 > 0 / gravity > 0
    2. Fr₁ = v₁ / √(g × h₁)
    3. h₂ = (h₁/2) × (√(1 + 8 × Fr₁²) − 1)（Bélanger 方程）
    4. ΔE = (h₂ − h₁)³ / (4 × h₁ × h₂)
    5. v₂ = v₁ × h₁ / h₂（连续性方程）
    6. 跃型分类（5 档）

    Args:
        inp: JumpInput（已冻结 dataclass）。

    Returns:
        JumpResult（含 h2 / fr1 / energy_loss / jump_type / v2 / formula_ref）。

    Raises:
        JumpInputError: 输入字段非正或 Fr1 < 1（422）。
    """
    # 1. 输入校验
    if inp.h1 <= 0:
        raise JumpInputError(f"h1 ({inp.h1}) 必须 > 0")
    if inp.v1 <= 0:
        raise JumpInputError(f"v1 ({inp.v1}) 必须 > 0")
    if inp.gravity <= 0:
        raise JumpInputError(f"gravity ({inp.gravity}) 必须 > 0")

    # 2. 跃前 Fr₁
    fr1 = inp.v1 / math.sqrt(inp.gravity * inp.h1)
    if fr1 < 1.0 - 1e-3:
        raise JumpInputError(
            f"Fr1 ({fr1:.6f}) < 1，无经典水跃（要求急流→缓流 Fr1≥1）"
        )

    # 3. Bélanger 方程反解 h₂
    h2 = (inp.h1 / 2.0) * (math.sqrt(1.0 + 8.0 * fr1 * fr1) - 1.0)

    # 4. 能量损失
    delta_h = h2 - inp.h1
    energy_loss = (delta_h ** 3) / (4.0 * inp.h1 * h2)

    # 5. 跃后流速（连续性：v₁ × h₁ = v₂ × h₂）
    v2 = inp.v1 * inp.h1 / h2

    # 6. 跃型判定
    jump_type = _classify_jump(fr1)

    return JumpResult(
        h2=h2,
        fr1=fr1,
        energy_loss=energy_loss,
        jump_type=jump_type,
        v2=v2,
    )


__all__ = [
    "GRAVITY",
    "JumpInput",
    "JumpResult",
    "JumpInputError",
    "calc_hydraulic_jump",
]
