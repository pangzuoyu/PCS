"""P6-6A Task 1：C-03 API 14E 冲蚀速度 vs Worley 真实算例 WS-CA-PR-003 对账测试。

数据源：sample/Process caculation from Worley/…/WS-CA-PR-003.xls（gitignored 只读）；
提取 dump：.superpowers/sdd/2026-09-27-p6-6a-worley-reconciliation/worley_dump/WS-CA-PR-003.json
fixture：tests/services/pipe/fixtures/worley_c03_erosion.json
（含 Worley 原始输入 cell 坐标、英制→SI 换算链、容差分级与放宽/收紧理由）

对账范围：
1. API14E (SI) / API14E (English) / GT-format-API14E 三个工况 sheet——
   v_e、actual_v、is_erosion_safe + XLS 链上输出量（截面积、体积流量，测试内复算）。
2. C 因子表（XLS Z31:Z34 假设区）vs service 默认 C（经公共 API 反解，不 import 私有 dict）。

超出模块契约的 XLS 输出（压降→C-05、Salama & Venkatesh 冲蚀、GT 选型导出量等）
登记于 fixture out_of_scope，test_out_of_scope_registered 守卫登记不漂移。

SPEC §5 分级：C-03 经验拟合级 rel≤1e-2；本批各 case 在门槛内收紧（fixture 注明理由）。
处置结论：全部通过，无 Ruling 1(a) 代码修复；π=3.1416 / C 取整 / GT 链路舍入
3 项手算舍入观察登记于 fixture root_cause_notes（Ruling 1(c)，容差内）。
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from app.services.pipe.two_phase_erosion import (
    Api14eErosionInput,
    calc_api14e_erosion_velocity,
)

_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "worley_c03_erosion.json"
WORLEY = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))

_IN_TO_M = 0.0254
_FT3_TO_M3 = 0.3048**3

# 服务输出字段名 ← fixture expected 键（SI 与 imperial 两口径）
_RESULT_ATTR = {
    "v_e_m_s": ("v_e_m_s", None),
    "actual_v_m_s": ("actual_v_m_s", None),
    "v_e_ft_s": (None, "v_e_ft_s"),
    "actual_v_ft_s": (None, "actual_v_ft_s"),
}


def _case_ids() -> list[str]:
    return [c["id"] for c in WORLEY["cases"]]


# ---------------------------------------------------------------------------
# 1) 三工况 sheet 全量对账（fixture 参数化）
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("case_id", _case_ids())
def test_worley_c03_case_reconciliation(case_id: str) -> None:
    """单工况对账：v_e + actual_v + is_erosion_safe + 链上量（面积/体积流量）。

    断言覆盖 XLS 中出现的全部本模块契约内输出量：
    Erosional Velocity、Mixture Velocity（=actual_v）、
    Pipe Cross-sectional Area、Actual Volumetric Flow Rate（链上量，测试内同输入复算）。
    """
    case = next(c for c in WORLEY["cases"] if c["id"] == case_id)
    rel = case["tolerance"]["rel"]

    result = calc_api14e_erosion_velocity(Api14eErosionInput(**case["service_inputs"]))

    for key, expected in case["expected"].items():
        if key.endswith("_note"):  # 说明字段非断言对象
            continue
        if key == "is_erosion_safe":
            assert result.is_erosion_safe is expected, (
                f"{case_id}: is_erosion_safe={result.is_erosion_safe}，XLS 推断={expected}"
            )
            continue
        attr, imperial_key = _RESULT_ATTR[key]
        if attr is not None:
            actual = getattr(result, attr)
        else:
            assert result.imperial_conversion is not None, f"{case_id}: imperial 输出缺失"
            actual = result.imperial_conversion[imperial_key]
        assert actual == pytest.approx(expected, rel=rel), (
            f"{case_id}.{key}: PCS={actual!r} vs XLS={expected!r}（rel 门槛 {rel}）"
        )

    _assert_chain_quantities(case, rel)


def _assert_chain_quantities(case: dict, rel: float) -> None:
    """XLS 链上输出量对账：由同一 service 输入复算（service 不返回这些中间量）。

    SI 工况：A=π/4·D²[m²]、Q=ṁ/ρ×3600[m³/h]；
    English 工况：A=π/4·(D/0.0254)²[in²]、Q=(ṁ/ρ)×3600/0.3048³[ft³/h]。
    """
    chain = case.get("expected_chain") or {}
    if not chain:
        return
    si = case["service_inputs"]
    d_m = si["pipe_diameter_m"]
    q_m3_s = si["mass_flow_kg_s"] / si["rho_mix_kg_m3"]
    if "area_m2" in chain:
        assert math.pi / 4.0 * d_m**2 == pytest.approx(chain["area_m2"], rel=rel)
        assert q_m3_s * 3600.0 == pytest.approx(chain["vol_flow_m3_h"], rel=rel)
    if "area_in2" in chain:
        d_in = d_m / _IN_TO_M
        assert math.pi / 4.0 * d_in**2 == pytest.approx(chain["area_in2"], rel=rel)
        assert q_m3_s * 3600.0 / _FT3_TO_M3 == pytest.approx(chain["vol_flow_ft3_h"], rel=rel)


# ---------------------------------------------------------------------------
# 2) C 因子表对账（XLS 假设区 Z31:Z34 vs service 默认值）
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("service_type", "mode", "expected"),
    [
        (s["service_type"], s["mode"], s.get("xls_si_value", s.get("xls_si_range")))
        for s in WORLEY["c_factor_table"]["services"]
    ],
    ids=[s["service_type"] for s in WORLEY["c_factor_table"]["services"]],
)
def test_worley_c03_c_factor_defaults(service_type: str, mode: str, expected: float | list) -> None:
    """service 各 service_type 默认 C 因子须与 Worley XLS C 表（SI sheet）一致。

    反解口径：ρ_mix=100 kg/m³ → v_e = C/10（经公共 API，c_factor 不显式传）。
    CORROSIVE_CONTINUOUS：XLS 给区间 183~244，SPEC 默认 200 须落在区间内。
    CORROSIVE_INTERMITTENT：XLS "up to 305"，SPEC 取上界 305。
    """
    result = calc_api14e_erosion_velocity(
        Api14eErosionInput(rho_mix_kg_m3=100.0, service_type=service_type)  # type: ignore[arg-type]
    )
    c_resolved = result.v_e_m_s * 10.0
    if mode == "exact":
        assert c_resolved == pytest.approx(expected, rel=1e-12), (
            f"{service_type}: 默认 C={c_resolved} vs XLS={expected}"
        )
    elif mode == "in_range":
        lo, hi = expected
        assert lo <= c_resolved <= hi, (
            f"{service_type}: 默认 C={c_resolved} 不在 XLS 区间 [{lo},{hi}]"
        )
    elif mode == "upper_bound":
        assert c_resolved == pytest.approx(expected, rel=1e-12), (
            f"{service_type}: 默认 C={c_resolved} vs XLS 上界 {expected}"
        )
    else:  # pragma: no cover - fixture 模式字段防漂移
        raise AssertionError(f"未知 mode={mode}")


# ---------------------------------------------------------------------------
# 3) 对账范围守卫：3 工况 sheet 全覆盖 + 超范围量登记不漂移
# ---------------------------------------------------------------------------


def test_worley_c03_case_coverage_and_out_of_scope_ledger() -> None:
    """fixture 必须覆盖全部含 API 14E 算例的 sheet，且超范围量登记齐全。

    - 工况 sheet：API14E (SI) / (English) / GT-format-API14E 三 sheet 全覆盖；
    - Sal&Vent 两 sheet 为 Salama & Venkatesh 模型（未实现），必须登记 out_of_scope；
    - 压降归 C-05、GT 选型导出量、空 sheet 逐项登记，防后续 fixture 演进时静默丢失。
    """
    assert {c["sheet"] for c in WORLEY["cases"]} == {
        "API14E (SI)",
        "API14E (English)",
        "GT-format-API14E",
    }
    registered = {o["id"] for o in WORLEY["out_of_scope"]}
    assert registered == {
        "pressure_drop",
        "salama_venkatesh",
        "gt_min_pipe_id",
        "gt_other_outputs",
        "empty_sheets",
    }
