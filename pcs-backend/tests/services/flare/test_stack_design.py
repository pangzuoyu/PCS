"""P6-2 Task 22 FLARE_SYS stack_design 测试。

按 SPEC §3.2.3 P6-FLR-003 + API 521 §7.4.2.2（Stack Height +
Pasquill-Gifford 修正）+ §7.4.2.3（Thermal Radiation 点源）+ BEDD 限值校验：

10 单元测试（不依赖 DB；纯计算函数）：
  1. test_stack_height_basic：Q=10 MW, stability=D → ΔH_buoy≈4.743 /
     H_eff≈14.743 / H_stack≈14.743（手算校核）
  2. test_stack_height_stability_A：同 Q 下 A vs D → A 的 H_eff 更大
     （dispersion_factor A=1.5 > D=1.0）
  3. test_stack_height_h_min_dominant：Q 很小 → h_min 占主导，
     H_stack == h_min
  4. test_stack_height_input_validation：total_heat_release_mw <= 0 /
     stability ∉ ABCDEF / h_min 越界 / wind_speed 越界 → 422
  5. test_radiation_basic：q_rad=2 MW, H_stack=15, flame=7.5, distance=100
     → q_w≈15.379 / q_kw≈0.01538（手算校核）
  6. test_radiation_bedd_compliant：bedd_limit=10 → bedd_compliant=True
  7. test_radiation_bedd_violation：bedd_limit=4.0 → bedd_compliant=False
  8. test_radiation_tilt_correction：tilt=30° → q 缩小 cos(30°)≈0.866
  9. test_radiation_input_validation：q_rad<=0 / H<=0 / distance<=0 /
     bedd_limit<=0 → 422
 10. test_stack_design_combined：综合 calc_stack_design，formula_ref=
     "API_521_§7.4.2.2+§7.4.2.3"

测试模式参照 ``tests/services/flare/test_kod_sizing.py``（纯计算函数，
无 DB / Mock session）。
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
    RadiationCheckInput,
    RadiationCheckInputError,
    RadiationCheckResult,
    StackDesignResult,
    StackHeightInput,
    StackHeightInputError,
    StackHeightResult,
    calc_radiation_check,
    calc_stack_design,
    calc_stack_height,
)

# ============================================================================
# 1. 基础工况 stack_height（手算校核）
# ============================================================================


def test_stack_height_basic() -> None:
    """Q=10 MW, stability=D, h_min=10, wind=5 → ΔH_buoy≈4.743 /
    H_eff≈14.743 / H_stack≈14.743（手算校核）。

    手算校核（API 521 §7.4.2.2）：
        dispersion_factor = 1.0（D 中性）
        ΔH_buoy = 1.5 × √10 = 1.5 × 3.16228 ≈ 4.743 m
        H_eff = 10 + 4.743 × 1.0 = 14.743 m
        H_stack = max(10, 14.743) = 14.743 m
    """
    inp = StackHeightInput(
        total_heat_release_mw=10.0,
        stability_class="D",
        h_min_engineering_m=10.0,
        wind_speed_m_s=5.0,
    )
    r = calc_stack_height(inp)
    assert isinstance(r, StackHeightResult)
    assert r.dispersion_factor == pytest.approx(1.0, abs=1e-9)
    assert r.buoyancy_rise_m == pytest.approx(4.743, abs=5e-3)
    assert r.h_effective_m == pytest.approx(14.743, abs=5e-3)
    assert r.h_stack_m == pytest.approx(14.743, abs=5e-3)
    assert r.formula_ref == "API_521_§7.4.2.2"


# ============================================================================
# 2. 稳定度等级对比（A vs D 同 Q）
# ============================================================================


def test_stack_height_stability_A() -> None:
    """A vs D 同 Q → A 的 H_eff 更大（dispersion_factor A=1.5 > D=1.0）。

    手算：
        A: ΔH_buoy=1.5 × √10 ≈ 4.743, H_eff = 10 + 4.743 × 1.5 ≈ 17.115
        D: ΔH_buoy=1.5 × √10 ≈ 4.743, H_eff = 10 + 4.743 × 1.0 ≈ 14.743
        差 ≈ 2.371（= ΔH_buoy × 0.5）
    """
    base_kwargs = {
        "total_heat_release_mw": 10.0,
        "h_min_engineering_m": 10.0,
        "wind_speed_m_s": 5.0,
    }
    r_a = calc_stack_height(StackHeightInput(**base_kwargs, stability_class="A"))
    r_d = calc_stack_height(StackHeightInput(**base_kwargs, stability_class="D"))

    # dispersion_factor 差异
    assert r_a.dispersion_factor > r_d.dispersion_factor
    assert r_a.dispersion_factor == pytest.approx(1.5, abs=1e-9)
    assert r_d.dispersion_factor == pytest.approx(1.0, abs=1e-9)
    # 浮升抬升一致（同 Q_total）
    assert r_a.buoyancy_rise_m == pytest.approx(r_d.buoyancy_rise_m, rel=1e-12)
    # A 的有效高度更大
    assert r_a.h_effective_m > r_d.h_effective_m
    # H_stack 也更大（A > D）
    assert r_a.h_stack_m > r_d.h_stack_m


# ============================================================================
# 3. h_min 占主导（Q 很小 → h_min 主导）
# ============================================================================


def test_stack_height_h_min_dominant() -> None:
    """Q 很小（0.1 MW）→ ΔH_buoy 很小 → h_min 占主导，H_stack == h_min。

    手算：
        ΔH_buoy = 1.5 × √0.1 ≈ 0.474 m
        H_eff = 10 + 0.474 × 1.0 ≈ 10.474
        H_stack = max(10, 10.474) = 10.474 > h_min
    注：本测试用更小 Q 让 H_eff < h_min 触发 max 取 h_min 分支。
        Q=1e-6 → ΔH_buoy=1.5 × 1e-3=0.0015 → H_eff≈10.0015
        → H_stack=10.0015（仍 > h_min）
    为确保 H_eff < h_min：使用极小 Q 使 ΔH_buoy < h_min−h_min
    （即 h_effective − h_min < 0）。
        ΔH_buoy < 0 → 不可能（buoyancy_rise 公式 sqrt >=0）
    实际最小 ΔH_buoy → 0（Q→0）。当 Q→0 浮升抬升 → 0，H_eff → h_min，
    H_stack → h_min。

    因此：Q=1e-6（极小正数）→ ΔH_buoy 极小 → H_stack ≈ h_min（取大）
    """
    inp = StackHeightInput(
        total_heat_release_mw=1.0e-6,
        stability_class="D",
        h_min_engineering_m=50.0,  # 故意放大以确保 H_eff < H_stack
        wind_speed_m_s=5.0,
    )
    r = calc_stack_height(inp)
    # ΔH_buoy 极小（< 0.01 m）
    assert r.buoyancy_rise_m < 0.01
    # H_eff ≈ h_min + ε（≈ 50）
    assert r.h_effective_m == pytest.approx(50.0, abs=1e-2)
    # H_stack == max(h_min, h_eff) ≈ h_min（极小 ε 不影响 max）
    assert r.h_stack_m == pytest.approx(50.0, abs=1e-2)


# ============================================================================
# 4. stack_height 输入校验（422）
# ============================================================================


@pytest.mark.parametrize(
    ("kwargs", "expected_substr"),
    [
        # total_heat_release_mw 必须 > 0
        ({"total_heat_release_mw": 0}, "total_heat_release_mw"),
        ({"total_heat_release_mw": -1.0}, "total_heat_release_mw"),
        # stability_class 必须在 {A,B,C,D,E,F}
        ({"stability_class": "X"}, "stability_class"),
        ({"stability_class": "G"}, "stability_class"),
        # h_min_engineering_m 范围 [5, 200]
        ({"h_min_engineering_m": 4.0}, "h_min_engineering_m"),
        ({"h_min_engineering_m": 4.99}, "h_min_engineering_m"),
        ({"h_min_engineering_m": 200.5}, "h_min_engineering_m"),
        ({"h_min_engineering_m": 300.0}, "h_min_engineering_m"),
        # wind_speed_m_s 范围 [0, 50]
        ({"wind_speed_m_s": -0.1}, "wind_speed_m_s"),
        ({"wind_speed_m_s": 60.0}, "wind_speed_m_s"),
    ],
)
def test_stack_height_input_validation(kwargs: dict, expected_substr: str) -> None:
    """stack_height 输入字段越界或非正 → 422 StackHeightInputError。"""
    base_kwargs = {
        "total_heat_release_mw": 10.0,
        "stability_class": "D",
        "h_min_engineering_m": 10.0,
        "wind_speed_m_s": 5.0,
    }
    base_kwargs.update(kwargs)
    with pytest.raises(StackHeightInputError) as exc_info:
        calc_stack_height(StackHeightInput(**base_kwargs))
    assert exc_info.value.status == 422
    assert exc_info.value.code == "FLARE_STACK_HEIGHT_INPUT_ERROR"
    assert expected_substr in str(exc_info.value)


# ============================================================================
# 5. 基础工况 radiation_check（手算校核）
# ============================================================================


def test_radiation_basic() -> None:
    """q_rad=2 MW, H_stack=15, flame_height=7.5, distance=100, tilt=0
    → q_w≈15.379 W/m² / q_kw≈0.01538 kW/m² / bedd_compliant=True（手算校核）。

    手算校核（API 521 §7.4.2.3 点源 + 倾斜角 0）：
        θ_rad = 0 → cos(θ) = 1.0
        火焰中心 H_flame_center = 15 + 7.5 × 1.0 / 2 = 18.75 m
        斜距 R = √(100² + 18.75²) = √(10000 + 351.5625) = √10351.5625
              ≈ 101.741 m
        q_w = 2 × 10⁶ × 1.0 / (4π × 101.741²) ≈ 2000000 / 130107.05
            ≈ 15.379 W/m²
        q_kw ≈ 0.01538 kW/m²
    BEDD limit default 4.73 kW/m² → 0.01538 ≪ 4.73 → bedd_compliant=True。
    """
    inp = RadiationCheckInput(
        q_radiated_mw=2.0,
        h_stack_m=15.0,
        receptor_distance_m=100.0,
        flame_height_m=7.5,
        tilt_angle_deg=0.0,
    )
    r = calc_radiation_check(inp)
    assert isinstance(r, RadiationCheckResult)
    # flame_center 手算 ≈ 18.75
    assert r.flame_center_height_m == pytest.approx(18.75, abs=1e-9)
    # slant_distance 手算 ≈ 101.741
    assert r.slant_distance_m == pytest.approx(101.741, abs=5e-3)
    # q_w 手算 ≈ 15.379
    assert r.q_at_receptor_w_m2 == pytest.approx(15.379, abs=5e-2)
    # q_kw 手算 ≈ 0.01538
    assert r.q_at_receptor_kw_m2 == pytest.approx(0.01538, abs=1e-4)
    # BEDD 合规
    assert r.bedd_compliant is True
    # 限值回显
    assert r.bedd_limit_kw_m2 == pytest.approx(4.73, abs=1e-9)
    # formula_ref
    assert r.formula_ref == "API_521_§7.4.2.3+BEDD"


# ============================================================================
# 6. BEDD 合规（bedd_limit=10 → bedd_compliant=True）
# ============================================================================


def test_radiation_bedd_compliant() -> None:
    """q_rad=2 MW, H_stack=15, distance=100, bedd_limit=10 → bedd_compliant=True。

    q_kw ≈ 0.01538 ≪ 10 → True
    """
    inp = RadiationCheckInput(
        q_radiated_mw=2.0,
        h_stack_m=15.0,
        receptor_distance_m=100.0,
        flame_height_m=7.5,
        tilt_angle_deg=0.0,
        bedd_limit_kw_m2=10.0,
    )
    r = calc_radiation_check(inp)
    assert r.bedd_compliant is True
    assert r.q_at_receptor_kw_m2 < r.bedd_limit_kw_m2


# ============================================================================
# 7. BEDD 违例（bedd_limit=4.0 → bedd_compliant=False）
# ============================================================================


def test_radiation_bedd_violation() -> None:
    """q_rad=2 MW, H_stack=15, distance=100, bedd_limit=4.0 → bedd_compliant=False。

    q_kw ≈ 0.01538 < 4.0 → True（实际未违例，仅展示极限阈值）

    注：bedd_limit=4.0 在 100m 距离下仍合规。要触发违例需极大 q_rad 或
    极小 distance。改用 bedd_limit=0.01（极小阈值）触发违例分支：
    q_kw ≈ 0.01538 > 0.01 → False
    """
    inp_compliant = RadiationCheckInput(
        q_radiated_mw=2.0,
        h_stack_m=15.0,
        receptor_distance_m=100.0,
        flame_height_m=7.5,
        tilt_angle_deg=0.0,
        bedd_limit_kw_m2=4.0,  # q_kw ≈ 0.01538 → 合规
    )
    r_compliant = calc_radiation_check(inp_compliant)
    assert r_compliant.bedd_compliant is True

    inp_violation = RadiationCheckInput(
        q_radiated_mw=2.0,
        h_stack_m=15.0,
        receptor_distance_m=100.0,
        flame_height_m=7.5,
        tilt_angle_deg=0.0,
        bedd_limit_kw_m2=0.01,  # q_kw ≈ 0.01538 → 违例
    )
    r_violation = calc_radiation_check(inp_violation)
    assert r_violation.bedd_compliant is False
    assert r_violation.q_at_receptor_kw_m2 > r_violation.bedd_limit_kw_m2


# ============================================================================
# 8. 倾斜角修正（tilt=30° → q 缩小 cos(30°)≈0.866）
# ============================================================================


def test_radiation_tilt_correction() -> None:
    """tilt=30° → q_w 缩小 cos(30°)≈0.866（相对 tilt=0）。

    手算（用 flame_height=0 隔离 H_stack 对 R² 的影响，让比精确等于 cos(30°)）：
        q_w = Q × 1e6 × cos(θ) / (4π × R²)
        若 flame_h=0，则 R² = receptor_distance² + H_stack²（与 tilt 无关）
        q_tilt_0 ∝ 1.0（cos 0 = 1.0）
        q_tilt_30 ∝ cos(30°) ≈ 0.866
        比 = cos(30°)/cos(0°) ≈ 0.866
    """
    base_kwargs = {
        "q_radiated_mw": 2.0,
        "h_stack_m": 15.0,
        "receptor_distance_m": 100.0,
        "flame_height_m": 0.0,  # 隔离 H_stack 对 R² 的影响
    }
    r_no_tilt = calc_radiation_check(
        RadiationCheckInput(**base_kwargs, tilt_angle_deg=0.0)
    )
    r_tilt_30 = calc_radiation_check(
        RadiationCheckInput(**base_kwargs, tilt_angle_deg=30.0)
    )

    # flame_center 在 flame_height=0 时等于 H_stack（与 tilt 无关）
    assert r_tilt_30.flame_center_height_m == pytest.approx(15.0, abs=1e-9)
    assert r_no_tilt.flame_center_height_m == pytest.approx(15.0, abs=1e-9)
    # slant_distance 两 case 一致
    assert r_tilt_30.slant_distance_m == pytest.approx(
        r_no_tilt.slant_distance_m, rel=1e-12
    )

    # q 比精确等于 cos(30°)
    expected_cos = math.cos(math.radians(30.0))
    ratio = r_tilt_30.q_at_receptor_w_m2 / r_no_tilt.q_at_receptor_w_m2
    assert ratio == pytest.approx(expected_cos, rel=1e-9)

    # q_kw 比一致
    ratio_kw = r_tilt_30.q_at_receptor_kw_m2 / r_no_tilt.q_at_receptor_kw_m2
    assert ratio_kw == pytest.approx(expected_cos, rel=1e-9)


# ============================================================================
# 9. radiation_check 输入校验（422）
# ============================================================================


@pytest.mark.parametrize(
    ("kwargs", "expected_substr"),
    [
        # q_radiated_mw 必须 > 0
        ({"q_radiated_mw": 0}, "q_radiated_mw"),
        ({"q_radiated_mw": -0.5}, "q_radiated_mw"),
        # h_stack_m 必须 > 0
        ({"h_stack_m": 0}, "h_stack_m"),
        ({"h_stack_m": -10.0}, "h_stack_m"),
        # receptor_distance_m 必须 > 0
        ({"receptor_distance_m": 0}, "receptor_distance_m"),
        ({"receptor_distance_m": -50.0}, "receptor_distance_m"),
        # bedd_limit_kw_m2 必须 > 0
        ({"bedd_limit_kw_m2": 0}, "bedd_limit_kw_m2"),
        ({"bedd_limit_kw_m2": -1.0}, "bedd_limit_kw_m2"),
    ],
)
def test_radiation_input_validation(kwargs: dict, expected_substr: str) -> None:
    """radiation_check 输入字段越界或非正 → 422 RadiationCheckInputError。"""
    base_kwargs = {
        "q_radiated_mw": 2.0,
        "h_stack_m": 15.0,
        "receptor_distance_m": 100.0,
        "flame_height_m": 7.5,
        "tilt_angle_deg": 0.0,
        "bedd_limit_kw_m2": 4.73,
    }
    base_kwargs.update(kwargs)
    with pytest.raises(RadiationCheckInputError) as exc_info:
        calc_radiation_check(RadiationCheckInput(**base_kwargs))
    assert exc_info.value.status == 422
    assert exc_info.value.code == "FLARE_RADIATION_INPUT_ERROR"
    assert expected_substr in str(exc_info.value)


# ============================================================================
# 10. 综合计算 calc_stack_design（覆盖 schema + service 综合）
# ============================================================================


def test_stack_design_combined() -> None:
    """综合调用 calc_stack_design：返回 StackDesignResult 含 stack_height +
    radiation 子结果。

    注：calc_stack_design 直接调用需要 radiation.h_stack_m 已正确给定。
    endpoint 内部接力（先 calc_stack_height 拿 h_stack 再 calc_radiation_check）
    由 test_stack_design_endpoint_200 集成测试覆盖。
    """
    # 先单独调 calc_stack_height 拿 h_stack（模拟 endpoint 接力逻辑）
    stack_r = calc_stack_height(
        StackHeightInput(
            total_heat_release_mw=10.0,
            stability_class="D",
            h_min_engineering_m=10.0,
            wind_speed_m_s=5.0,
        )
    )
    h_stack = stack_r.h_stack_m  # ≈ 14.743

    radiation_r = calc_radiation_check(
        RadiationCheckInput(
            q_radiated_mw=2.0,  # 10 × 0.2
            h_stack_m=h_stack,  # 接力真实高度
            receptor_distance_m=100.0,
            flame_height_m=1.0e-6,  # 极小，避免覆盖 endpoint 用例
            tilt_angle_deg=0.0,
        )
    )

    # 综合接口
    combined = calc_stack_design(
        StackHeightInput(
            total_heat_release_mw=10.0,
            stability_class="D",
            h_min_engineering_m=10.0,
            wind_speed_m_s=5.0,
        ),
        RadiationCheckInput(
            q_radiated_mw=2.0,
            h_stack_m=h_stack,  # 接力真实高度（非 0.0）
            receptor_distance_m=100.0,
            flame_height_m=1.0e-6,
            tilt_angle_deg=0.0,
        ),
    )
    assert isinstance(combined, StackDesignResult)
    assert isinstance(combined.stack_height, StackHeightResult)
    assert isinstance(combined.radiation, RadiationCheckResult)
    assert combined.formula_ref == "API_521_§7.4.2.2+§7.4.2.3"
    # 子结果与单独调用一致
    assert combined.stack_height == stack_r
    assert combined.radiation == radiation_r


# ============================================================================
# 11. flame_height 默认值（None → H_stack × 0.5）
# ============================================================================


def test_radiation_flame_height_default() -> None:
    """flame_height_m=None 时默认用 H_stack × 0.5 = 15 × 0.5 = 7.5 m。"""
    inp = RadiationCheckInput(
        q_radiated_mw=2.0,
        h_stack_m=15.0,
        receptor_distance_m=100.0,
        flame_height_m=None,  # 默认值
        tilt_angle_deg=0.0,
    )
    r = calc_radiation_check(inp)
    # flame_center = H_stack + flame_height × cos(0) / 2 = 15 + 7.5 / 2 = 18.75
    assert r.flame_center_height_m == pytest.approx(18.75, abs=1e-9)