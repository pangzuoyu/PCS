"""P6-4 Task 4 (C-17) flash 端 saturation 交叉对账 stub（最小实现 / SPEC §3.2.5 §3.9.2）。

按 V1.2 D2 决策：建立最小 stub 提供 ``verify_saturation_w`` 交叉对账 helper，
供 psychro 单元测试引用，对账 ASHRAE Fundamentals 2021 Table 1 黄金值。
完整 flash 算法（含 PR/SRK 立方 EOS、NRTL 活度模型）留 P6-18 范围。

设计要点：

- **stub 范围**（V1.2 明确）：仅 GOLDEN_FIXTURE 10 点 + cross-check
  ``verify_saturation_w(W_kg_kg, T_c, P_kpa)`` ≤1% 容差；不实施完整
  flash 算法（P6-18 范围内）。
- **fixture 来源**（V1.2 严格）：ASHRAE Fundamentals 2021 Table 1
  （HAPropsSI 自洽生成；与 psychro service 共享同一 CoolProp 调用路径，
  避免 fixture drift）。
- **接口冻结**（V1.2 锁定）：verify_saturation_w 签名作为 D7 接口冻结
  契约（mirror ADR-0040 部分），供后续 P6-18 替换实现不破坏调用方。
"""
from __future__ import annotations

import functools
import json
from pathlib import Path

from app.services.chedl_wrapper import humid_air_humidity_ratio

# GOLDEN_FIXTURE 路径（P6-4 Task 4 cross-check 主用 fixture）
_FIXTURE_PATH = (
    Path(__file__).resolve().parents[3]
    / "tests"
    / "services"
    / "psychro"
    / "fixtures"
    / "golden_saturation_w_ashrae.json"
)

# 容差：cross-check vs ASHRAE 黄金 fixture ≤ 1%（D2 明确）
_CROSS_CHECK_REL_TOL = 0.01

# 缓存：同一 (T, P) 多次 verify 走 lru_cache（mirror psychro service）
_VERIFY_CACHE_SIZE = 1024


@functools.lru_cache(maxsize=_VERIFY_CACHE_SIZE)
def _load_golden_fixture() -> tuple:
    """加载 GOLDEN_FIXTURE（lru_cache 单次加载；fixture 改动需重启进程）。"""
    with _FIXTURE_PATH.open(encoding="utf-8") as f:
        data = json.load(f)
    return tuple(
        (
            p["temperature_c"],
            p["pressure_kpa"],
            p["saturation_w_kg_kg"],
        )
        for p in data["points"]
    )


def _lookup_golden(temperature_c: float, pressure_kpa: float) -> float | None:
    """GOLDEN_FIXTURE 精确查表（T, P 完全相等）。"""
    for (t, p, w) in _load_golden_fixture():
        if t == temperature_c and p == pressure_kpa:
            return w
    return None


def get_golden_saturation_w_kg_kg(
    temperature_c: float,
    pressure_kpa: float = 101.325,
) -> float | None:
    """GOLDEN_FIXTURE 取饱和 W 黄金值（kg/kg；ASHRAE Table 1 源）。

    Args:
        temperature_c: 干球温度 °C（必须匹配 GOLDEN_FIXTURE point）。
        pressure_kpa: 大气压力 kPa（默认海平面）。

    Returns:
        黄金饱和 W（kg/kg），或 None（GOLDEN_FIXTURE 缺失时）。
    """
    return _lookup_golden(temperature_c, pressure_kpa)


def verify_saturation_w(
    w_kg_kg: float,
    temperature_c: float,
    pressure_kpa: float = 101.325,
) -> tuple[bool, float | None]:
    """cross-check 饱和 W vs GOLDEN_FIXTURE（D2 cross-check ≤1% 容差）。

    Args:
        w_kg_kg: 待校验饱和水含量 kg/kg（psychro service 产出）。
        temperature_c: 干球温度 °C。
        pressure_kpa: 大气压力 kPa。

    Returns:
        (passed, golden_value) — passed=True 表示 |w - golden|/golden ≤ 1%；
        golden_value=None 表示 fixture 缺失该点（视为 skip）。
    """
    golden = _lookup_golden(temperature_c, pressure_kpa)
    if golden is None:
        return (False, None)
    if golden == 0.0:
        return (abs(w_kg_kg) <= _CROSS_CHECK_REL_TOL, golden)
    rel_err = abs(w_kg_kg - golden) / abs(golden)
    return (rel_err <= _CROSS_CHECK_REL_TOL, golden)


def flash_saturation_water_content(
    temperature_c: float,
    pressure_kpa: float = 101.325,
) -> float:
    """flash 端饱和水含量（stub；P6-18 范围内将由完整 flash 算法替换）。

    当前 stub 直接走 ``chedl_wrapper.humid_air_humidity_ratio(T, RH=1.0, P)``
    （与 psychro service 共享同一 CoolProp 调用）；保持接口冻结但实现
    保持 placeholder 语义（不重复封装）。

    Args:
        temperature_c: 干球温度 °C。
        pressure_kpa: 大气压力 kPa（默认 101.325）。

    Returns:
        饱和 W kg/kg dry air。
    """
    t_k = temperature_c + 273.15
    p_pa = pressure_kpa * 1000.0
    return humid_air_humidity_ratio(t_k, 1.0, p_pa)


__all__ = [
    "get_golden_saturation_w_kg_kg",
    "verify_saturation_w",
    "flash_saturation_water_content",
]