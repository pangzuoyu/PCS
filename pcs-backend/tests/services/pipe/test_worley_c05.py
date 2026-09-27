"""P6-6A Task 2：C-05 API 14E 两相流管径 vs Worley 真实算例 WS-CA-PR-005 对账测试。

数据源：sample/Process caculation from Worley/…/WS-CA-PR-005.xls（gitignored 只读）；
提取 dump：.superpowers/sdd/2026-09-27-p6-6a-worley-reconciliation/worley_dump/WS-CA-PR-005.json
fixture：tests/services/pipe/fixtures/worley_c05_sizing.json
（含 Worley 原始输入 cell 坐标、输入分解/换算链、容差分级与放宽/收紧理由）

对账范围：
1. API14E_Imp / API14E_SI 双单位同工况 sheet——v_e、d_min（service 直出）+
   链上量（ρ_mix 分解链 vs E32、选定管内混合物流速 vs E45/E46，测试内复算）。
   service 不接收选定管径/不返回混合物流速，链上量由 XLS 自身体积流量 cell
   + 选定管 ID（fixture chain_inputs）复算对账。
2. 两 sheet 各自独立分解链（SI sheet E 列为舍入换算值自成链；Schedule 列索引
   互不相同：Imp→Sch 100 / SI→Sch 80），速度对账各按各 sheet 的 E40。

超出模块契约的 XLS 输出（E47 压降、Turner 校核无 XLS 基准、选型/MAWP/管表区）
登记于 fixture out_of_scope，test_out_of_scope_registered 守卫登记不漂移。

SPEC §5 分级：C-05 经验拟合级 rel≤1e-2；本批两 case 在门槛内收紧至 2e-3
（fixture 注明理由）。处置结论：全部通过，无 Ruling 1(a) 代码修复；
XLS 内部 PVT 常数不可恢复 / 显示 cell 互不一致 ±0.3% / Schedule 列索引
3 项观察登记于 fixture root_cause_notes（Ruling 1(c)，容差内）。
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from app.services.pipe.two_phase_sizing import (
    Api14ePipeSizingInput,
    calc_api14e_pipe_size,
)

_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "worley_c05_sizing.json"
WORLEY = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))

# 服务输出字段名 ← fixture expected 键（SI 与 imperial 两口径）
_RESULT_ATTR = {
    "v_e_m_s": ("v_e_m_s", None),
    "d_min_m": ("d_min_m", None),
    "v_e_ft_s": (None, "v_e_ft_s"),
    "d_min_in": (None, "d_min_in"),
}


def _case_ids() -> list[str]:
    return [c["id"] for c in WORLEY["cases"]]


# ---------------------------------------------------------------------------
# 1) 双 sheet 工况全量对账（fixture 参数化）
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("case_id", _case_ids())
def test_worley_c05_case_reconciliation(case_id: str) -> None:
    """单工况对账：v_e + d_min + 链上量（ρ_mix 分解、选定管内混合物流速）。

    断言覆盖 XLS 中出现的全部本模块契约内输出量：
    Erosional Velocity（E34）、Minimum Pipe ID Required（E35）；
    Mixture Density @ Inlet T,P（E32）与 Mixture Velocity @ Inlet/Outlet T,P
    （E45/E46）为链上量——service 不返回，测试内由 fixture 分解输入 +
    XLS 自身体积流量 cell 复算对账。
    """
    case = next(c for c in WORLEY["cases"] if c["id"] == case_id)
    rel = case["tolerance"]["rel"]

    result = calc_api14e_pipe_size(Api14ePipeSizingInput(**case["service_inputs"]))

    for key, expected in case["expected"].items():
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
    """XLS 链上输出量对账：由 fixture 分解输入 + XLS 体积流量 cell 复算。

    ρ_mix：验证 (ρ_L, ρ_V, ε) 分解链对 XLS E32 的复现度（service 内部同式
    ρ_mix = ρ_L(1-ε) + ρ_V·ε）；流速：V = (Q_g + Q_o)/3600 / (π/4·D_sel²)，
    SI sheet 用 m、English sheet 用 ft（选定管 ID 各 sheet 不同，见 fixture）。
    """
    chain = case.get("expected_chain") or {}
    if not chain:
        return
    si = case["service_inputs"]
    if "rho_mix_kg_m3" in chain:
        rho_mix = si["rho_L_kg_m3"] * (1.0 - si["void_fraction"]) + si["rho_V_kg_m3"] * si[
            "void_fraction"
        ]
        assert rho_mix == pytest.approx(chain["rho_mix_kg_m3"], rel=rel), (
            f"{case['id']}.rho_mix: 分解链={rho_mix!r} vs XLS E32={chain['rho_mix_kg_m3']!r}"
        )
    ci = case["chain_inputs"]
    if "v_inlet_m_s" in chain:  # SI sheet
        area_m2 = math.pi / 4.0 * ci["selected_pipe_id_m"] ** 2
        v_in = (ci["q_gas_inlet_m3_h"] + ci["q_oil_m3_h"]) / 3600.0 / area_m2
        v_out = (ci["q_gas_outlet_m3_h"] + ci["q_oil_m3_h"]) / 3600.0 / area_m2
        assert v_in == pytest.approx(chain["v_inlet_m_s"], rel=rel)
        assert v_out == pytest.approx(chain["v_outlet_m_s"], rel=rel)
    if "v_inlet_ft_s" in chain:  # English sheet
        area_ft2 = math.pi / 4.0 * (ci["selected_pipe_id_in"] / 12.0) ** 2
        v_in = (ci["q_gas_inlet_ft3_h"] + ci["q_oil_ft3_h"]) / 3600.0 / area_ft2
        v_out = (ci["q_gas_outlet_ft3_h"] + ci["q_oil_ft3_h"]) / 3600.0 / area_ft2
        assert v_in == pytest.approx(chain["v_inlet_ft_s"], rel=rel)
        assert v_out == pytest.approx(chain["v_outlet_ft_s"], rel=rel)


# ---------------------------------------------------------------------------
# 2) 对账范围守卫：双 sheet 全覆盖 + 超范围量登记不漂移
# ---------------------------------------------------------------------------


def test_worley_c05_case_coverage_and_out_of_scope_ledger() -> None:
    """fixture 必须覆盖 WS-CA-PR-005 全部两个工况 sheet，且超范围量登记齐全。

    - 工况 sheet：API14E_Imp / API14E_SI 双单位同工况全覆盖（管表查询区
      M25:Z57 非算例，不单独成 case）；
    - 压降（E47：two_phase_sizing 无该输出，P4-2-4 LMB 属另一算法族）、
      Turner 临界携液（XLS 无对应输出）、选型/MAWP/管表查询区 逐项登记
      out_of_scope，防后续 fixture 演进时静默丢失。
    """
    assert {c["sheet"] for c in WORLEY["cases"]} == {"API14E_Imp", "API14E_SI"}
    registered = {o["id"] for o in WORLEY["out_of_scope"]}
    assert registered == {
        "pressure_drop",
        "turner_critical_velocity",
        "selection_mawp_and_pipe_table",
    }
