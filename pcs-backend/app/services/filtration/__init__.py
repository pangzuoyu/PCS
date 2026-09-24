"""FILTRATION 过滤计算模块（SPEC §3.2.7）。

依据：Ruth 恒压/恒速过滤方程 + Ergun 介质阻力方程。

模块导出：

- ``ruth_constant_pressure`` 提供 ``calc_ruth_constant_pressure``：Ruth 恒压过滤方程
  (V + V₀)² = k · A² · t + V₀²
- ``ruth_constant_rate`` 提供 ``calc_ruth_constant_rate``：Ruth 恒速过滤方程
  ΔP = μ · Q · R_total / A²，R_total = α · c₀ · V / A + Rm
- ``ergun`` 提供 ``calc_ergun_pressure_drop``：Ergun 方程
  ΔP / L = 150 · μ · (1−ε)² / ε³ · v_s / dp² + 1.75 · ρ · (1−ε) / ε³ · v_s² / dp

不含 endpoint 挂载（Task 34）+ 不含落库（Task 34）+ 不含 G-05 数据录入（Task 29）。

P6-OPEN-001（G-01 degraded）决议：禁止 import fluids.filtration（子模块不存在）；
禁止 import chedl_wrapper 中 FILTRATION 函数（无；本任务自研）。
"""
from app.services.filtration.ergun import (
    ErgunInput,
    ErgunInputError,
    ErgunResult,
    calc_ergun_pressure_drop,
)
from app.services.filtration.ruth_constant_pressure import (
    RuthConstantPressureInput,
    RuthConstantPressureInputError,
    RuthConstantPressureResult,
    calc_ruth_constant_pressure,
)
from app.services.filtration.ruth_constant_rate import (
    RuthConstantRateInput,
    RuthConstantRateInputError,
    RuthConstantRateResult,
    calc_ruth_constant_rate,
)

__all__ = [
    # ruth constant pressure（§3.2.7 第一项 — 恒压过滤）
    "RuthConstantPressureInput",
    "RuthConstantPressureResult",
    "RuthConstantPressureInputError",
    "calc_ruth_constant_pressure",
    # ruth constant rate（§3.2.7 第二项 — 恒速过滤）
    "RuthConstantRateInput",
    "RuthConstantRateResult",
    "RuthConstantRateInputError",
    "calc_ruth_constant_rate",
    # ergun（§3.2.7 第三项 — 深层过滤介质阻力）
    "ErgunInput",
    "ErgunResult",
    "ErgunInputError",
    "calc_ergun_pressure_drop",
]