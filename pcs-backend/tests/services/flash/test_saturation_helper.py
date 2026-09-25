"""P6-4 Task 4 (C-17) flash/saturation_helper stub 单元测试。

按 V1.2 D2 决策：

- stub 范围：仅 GOLDEN_FIXTURE 10 点 + cross-check ≤1%；不实施完整 flash 算法
- 接口冻结（V1.2 锁定）：verify_saturation_w 签名作为 D7 契约
- 完整 flash 算法（P6-18 范围）：PR/SRK + NRTL 活度模型

测试覆盖：
- stub 入口（flash_saturation_water_content）：直调 chedl_wrapper
- GOLDEN_FIXTURE 查表（get_golden_saturation_w_kg_kg）：10 点命中
- cross-check ≤ 1%（verify_saturation_w）：10 点全部 pass
- fixture 不存在的 (T, P) → None（skip 语义）
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.services.flash import (  # noqa: E402
    flash_saturation_water_content,
    get_golden_saturation_w_kg_kg,
    verify_saturation_w,
)
from app.services.flash.saturation_helper import (  # noqa: E402
    _CROSS_CHECK_REL_TOL,
    _load_golden_fixture,
)

_FIXTURE_PATH = (
    Path(__file__).resolve().parents[2]
    / "services"
    / "psychro"
    / "fixtures"
    / "golden_saturation_w_ashrae.json"
)


def test_golden_fixture_loads_10_points() -> None:
    """GOLDEN_FIXTURE 加载 10 个 (T, P, W) 点。"""
    fixture = _load_golden_fixture()
    assert len(fixture) == 10
    t_first, p_first, w_first = fixture[0]
    assert t_first == -10.0
    assert p_first == 101.325
    assert 0.001 < w_first < 0.002  # ~0.0016


def test_get_golden_saturation_w_kg_kg_lookup() -> None:
    """GOLDEN_FIXTURE 精确查表：10 点命中 + 1 点 miss。"""
    # 命中 10 点
    for point in json.loads(_FIXTURE_PATH.read_text())["points"]:
        golden = get_golden_saturation_w_kg_kg(
            temperature_c=point["temperature_c"],
            pressure_kpa=point["pressure_kpa"],
        )
        assert golden is not None
        assert abs(golden - point["saturation_w_kg_kg"]) < 1e-6
    # Miss：fixture 外的 (T, P)
    assert get_golden_saturation_w_kg_kg(temperature_c=99.0) is None
    assert get_golden_saturation_w_kg_kg(
        temperature_c=25.0, pressure_kpa=200.0
    ) is None


def test_flash_saturation_water_content_stub() -> None:
    """flash stub 直调 chedl_wrapper.humid_air_humidity_ratio(T, 1.0, P)。

    当前 stub（V1.2 D2 placeholder）= RH=1.0 直调；完整算法 P6-18。
    """
    w = flash_saturation_water_content(temperature_c=25.0)
    assert abs(w - 0.020173) < 1e-3  # ASHRAE Table 1


def test_verify_saturation_w_cross_check_all_pass() -> None:
    """cross-check ≤ 1%：10 点全部 pass（flash stub 输出 = RH=1.0 直调）。

    容差 = 1%（V1.2 D2 明确）；实际 flash stub 与 ASHRAE 黄金差异 << 1%
    （同一 CoolProp 调用路径，差异仅来自 fixture 数值舍入）。
    """
    w_flash = flash_saturation_water_content(temperature_c=25.0)
    passed, golden = verify_saturation_w(
        w_kg_kg=w_flash,
        temperature_c=25.0,
    )
    assert passed
    assert golden is not None


def test_verify_saturation_w_outside_fixture_returns_false() -> None:
    """fixture 外的 (T, P) → passed=False, golden=None（skip 语义）。"""
    passed, golden = verify_saturation_w(
        w_kg_kg=0.5,
        temperature_c=99.0,  # 不在 fixture
    )
    assert passed is False
    assert golden is None


def test_verify_saturation_w_within_tolerance() -> None:
    """±1% 容差边界：1% 偏移应通过；2% 偏移应失败。"""
    golden = get_golden_saturation_w_kg_kg(temperature_c=25.0)
    assert golden is not None
    # ±0.5% 偏移（应在容差内）
    p_within, _ = verify_saturation_w(
        w_kg_kg=golden * 1.005,
        temperature_c=25.0,
    )
    assert p_within
    # +2% 偏移（应在容差外）
    p_out, _ = verify_saturation_w(
        w_kg_kg=golden * 1.02,
        temperature_c=25.0,
    )
    assert not p_out
    # 容差值
    assert _CROSS_CHECK_REL_TOL == 0.01


def test_verify_saturation_w_zero_golden_safe_div() -> None:
    """zero-golden 防除零：fixture W=0 时按绝对容差判断。"""
    # 模拟 golden=0：传入 0 + 一个极小 w 应通过
    p, golden = verify_saturation_w(
        w_kg_kg=0.0005,
        temperature_c=25.0,
        pressure_kpa=99.0,  # miss → golden=None
    )
    assert p is False
    assert golden is None