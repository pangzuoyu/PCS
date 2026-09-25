"""P6-2 Task 20 FLARE_SYS header_sizing 测试。

按 SPEC §3.2.3 P6-FLR-001 + API 521 §5.15.4（Mach 数法 + 等温可压缩管流）：

- 6 单元测试（不依赖 DB；纯计算函数）：
  1. test_basic_air_n2：空气（N2 简化 MW=28.97/k=1.4）+ W=10 kg/s + T=300 K
     + P=101325 Pa → D ≈ 0.27 m（手算校核）
  2. test_target_mach_0_3_vs_0_5：同输入 target_mach=0.3 vs 0.5 → Mach 0.3 D 更大
  3. test_input_validation_negative：relief_mass_flow_kgs=0 / T=0 / k=1.0 等 → 422
  4. test_target_mach_out_of_range：target_mach=1.5 / 0.01 → 422
  5. test_formula_ref_api_521：所有结果 formula_ref == "API_521_§5.15.4"
  6. test_density_sound_speed_consistency：ρ × R × T / MW ≈ P（验证理想气体假设）

测试模式参照 ``tests/services/flare/test_relief_aggregator.py``（Mock session
+ 构造 row-like 对象）。本模块纯计算，无需 DB / Mock session。

设计要点：

- 不依赖 DB（纯计算函数）。
- 单元测试用 dataclass 直接构造输入；不引入 httpx / pytest_asyncio。
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.services.flare import (  # noqa: E402
    HeaderSizingInput,
    HeaderSizingInputError,
    HeaderSizingResult,
    calc_header_sizing,
)

# 通用气体常数（与 service 一致；用于手算校核）
_R_UNIVERSAL = 8314.462618  # J/(kmol·K)


# ============================================================================
# 1. 基础空气工况（手算校核）
# ============================================================================


def test_basic_air_n2() -> None:
    """空气（N2 简化 MW=28.97/k=1.4）+ W=10 kg/s + T=300 K + P=101325 Pa → D ≈ 0.27 m。

    手算校核：
        ρ = P * MW / (R * T) = 101325 * 28.97 / (8314.462618 * 300) ≈ 1.177 kg/m³
        a = sqrt(k * R * T / MW) = sqrt(1.4 * 8314.462618 * 300 / 28.97) ≈ 347.2 m/s
        A = W / (M_target * ρ * a) = 10 / (0.5 * 1.177 * 347.2) ≈ 0.0489 m²
        D = sqrt(4 * A / π) = sqrt(4 * 0.0489 / π) ≈ 0.2496 m
    """
    inp = HeaderSizingInput(
        relief_mass_flow_kgs=10.0,
        avg_temperature_k=300.0,
        avg_pressure_pa=101325.0,
        mw_kg_kmol=28.97,
        specific_heat_ratio=1.4,
        target_mach=0.5,
    )
    r = calc_header_sizing(inp)
    assert isinstance(r, HeaderSizingResult)
    assert 0.24 < r.diameter_m < 0.26, f"diameter_m={r.diameter_m:.4f} 不在预期 [0.24, 0.26]"
    assert r.actual_mach == pytest.approx(0.5, abs=1e-9)
    assert r.formula_ref == "API_521_§5.15.4"
    # 期望 D ≈ 0.2496 m（手算）
    assert r.diameter_m == pytest.approx(0.2496, abs=1e-3)


# ============================================================================
# 2. target_mach 比较（Mach 数越小 → D 越大）
# ============================================================================


def test_target_mach_0_3_vs_0_5() -> None:
    """同输入 target_mach=0.3 vs 0.5 → Mach 0.3 D 更大（保守口径反推）。"""
    base_kwargs = {
        "relief_mass_flow_kgs": 10.0,
        "avg_temperature_k": 300.0,
        "avg_pressure_pa": 101325.0,
        "mw_kg_kmol": 28.97,
        "specific_heat_ratio": 1.4,
    }
    r_low_mach = calc_header_sizing(HeaderSizingInput(**base_kwargs, target_mach=0.3))
    r_high_mach = calc_header_sizing(HeaderSizingInput(**base_kwargs, target_mach=0.5))

    # Mach 0.3 < 0.5 → 反求面积更大 → D 更大
    assert r_low_mach.diameter_m > r_high_mach.diameter_m
    # actual_mach 应等于各自 target_mach
    assert r_low_mach.actual_mach == pytest.approx(0.3, abs=1e-9)
    assert r_high_mach.actual_mach == pytest.approx(0.5, abs=1e-9)


# ============================================================================
# 3. 输入校验（正数 + 工程范围）
# ============================================================================


@pytest.mark.parametrize(
    ("kwargs", "expected_substr"),
    [
        ({"relief_mass_flow_kgs": 0}, "relief_mass_flow_kgs"),
        ({"relief_mass_flow_kgs": -1.0}, "relief_mass_flow_kgs"),
        ({"avg_temperature_k": 0}, "avg_temperature_k"),
        ({"avg_pressure_pa": 0}, "avg_pressure_pa"),
        ({"mw_kg_kmol": 0}, "mw_kg_kmol"),
        ({"specific_heat_ratio": 1.0}, "specific_heat_ratio"),
        ({"specific_heat_ratio": 0.9}, "specific_heat_ratio"),
    ],
)
def test_input_validation_negative(kwargs: dict, expected_substr: str) -> None:
    """输入字段非正或比热比 <= 1.0 → 422 HeaderSizingInputError。"""
    base_kwargs = {
        "relief_mass_flow_kgs": 10.0,
        "avg_temperature_k": 300.0,
        "avg_pressure_pa": 101325.0,
        "mw_kg_kmol": 28.97,
        "specific_heat_ratio": 1.4,
    }
    base_kwargs.update(kwargs)
    with pytest.raises(HeaderSizingInputError) as exc_info:
        calc_header_sizing(HeaderSizingInput(**base_kwargs))
    assert exc_info.value.status == 422
    assert exc_info.value.code == "FLARE_HEADER_INPUT_ERROR"
    assert expected_substr in str(exc_info.value)


# ============================================================================
# 4. target_mach 越界
# ============================================================================


@pytest.mark.parametrize("bad_target_mach", [1.5, 1.01, 0.04, 0.0, -0.1])
def test_target_mach_out_of_range(bad_target_mach: float) -> None:
    """target_mach 超出 [0.05, 1.0] 工程范围 → 422 HeaderSizingInputError。"""
    inp = HeaderSizingInput(
        relief_mass_flow_kgs=10.0,
        avg_temperature_k=300.0,
        avg_pressure_pa=101325.0,
        mw_kg_kmol=28.97,
        specific_heat_ratio=1.4,
        target_mach=bad_target_mach,
    )
    with pytest.raises(HeaderSizingInputError) as exc_info:
        calc_header_sizing(inp)
    assert exc_info.value.status == 422
    assert exc_info.value.code == "FLARE_HEADER_INPUT_ERROR"
    assert "target_mach" in str(exc_info.value)


# ============================================================================
# 5. formula_ref 一致性
# ============================================================================


@pytest.mark.parametrize(
    "inp",
    [
        HeaderSizingInput(
            relief_mass_flow_kgs=10.0,
            avg_temperature_k=300.0,
            avg_pressure_pa=101325.0,
            mw_kg_kmol=28.97,
            specific_heat_ratio=1.4,
            target_mach=0.5,
        ),
        HeaderSizingInput(
            relief_mass_flow_kgs=5.0,
            avg_temperature_k=400.0,
            avg_pressure_pa=200000.0,
            mw_kg_kmol=44.01,  # CO2
            specific_heat_ratio=1.3,
            target_mach=0.7,
        ),
        HeaderSizingInput(
            relief_mass_flow_kgs=20.0,
            avg_temperature_k=500.0,
            avg_pressure_pa=500000.0,
            mw_kg_kmol=16.04,  # CH4
            specific_heat_ratio=1.31,
            target_mach=0.05,  # 边界
        ),
    ],
)
def test_formula_ref_api_521(inp: HeaderSizingInput) -> None:
    """所有结果 formula_ref == "API_521_§5.15.4"（公式溯源）。"""
    r = calc_header_sizing(inp)
    assert r.formula_ref == "API_521_§5.15.4"


# ============================================================================
# 6. 理想气体一致性（ρ × R × T / MW ≈ P）
# ============================================================================


def test_density_sound_speed_consistency() -> None:
    """等温理想气体一致性：ρ × R × T / MW ≈ P（误差 <1e-6）。

    验证 service 输出的 gas_density_kg_m3 严格满足 ρ = P * MW / (R * T)
    关系；这是 Mach 数法反求面积的基础假设。
    """
    inp = HeaderSizingInput(
        relief_mass_flow_kgs=10.0,
        avg_temperature_k=350.0,  # 非室温
        avg_pressure_pa=250000.0,  # 非大气压
        mw_kg_kmol=44.01,  # CO2
        specific_heat_ratio=1.3,
        target_mach=0.5,
    )
    r = calc_header_sizing(inp)

    # 反推压力
    P_recovered = r.gas_density_kg_m3 * _R_UNIVERSAL * inp.avg_temperature_k / inp.mw_kg_kmol
    assert P_recovered == pytest.approx(inp.avg_pressure_pa, rel=1e-6)

    # 等温声速 a = sqrt(k * R * T / MW) 应与 service 计算一致
    kRT_over_MW = inp.specific_heat_ratio * _R_UNIVERSAL * inp.avg_temperature_k / inp.mw_kg_kmol
    a_expected = math.sqrt(kRT_over_MW)
    assert r.sound_speed_m_s == pytest.approx(a_expected, rel=1e-9)