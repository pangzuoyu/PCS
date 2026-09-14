"""P4-2-5 PipeChainService 单元测试 + 落库 + API 集成。

覆盖：
1. golden 3 段全液相串联：手算 total_dp / dp_per_segment / Re / f /
   outlet_pressure / pressure_gradient
2. 单段退化：等价于单管
3. 两相段串联：need_two_phase=True + flow_pattern 写入
4. 高程修正：Δz > 0 → +ρgΔz 加进总 dp
5. fittings 累加：K 值表 + 显式 K
6. 边界：空 segments → raise；P1 ≤ 0 → raise；并联 ≠ 1 → raise；
   两相段缺物性 → raise
7. 落库 roundtrip（P4-2-5）：calc → persist → SELECT → 11 字段 + outlet_stream
8. outlet_stream 复用 P4-1-3 helper：source_type=PIPE_CALCULATED →
   upstream_equipment_type="PIPE" + sign_status=DRAFT
9. 守卫：DRAFT → 403 / 不存在 → 404 / 不可靠 → 422
10. API 端点：POST /api/v1/pipe/calc-chain 端到端（client fixture）

Golden 溯源：
- 串联：Σ dp_friction_i（Darcy-Weisbach + Colebrook 复用 sizing_service._colebrook_f）
- 高程：ρgΔz（ISO 80000-3 g=9.80665 m/s²）
- 两相：Lockhart-Martinelli-Baker（复用 P4-2-4）
- 局部阻力：fittings K 值表（Crane TP-410 / Idelchik）
"""
from __future__ import annotations

import json
import math
import uuid
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import dispose_engines_async, get_async_session_factory
from app.services.pipe.pipe_chain_persist import persist_pipe_chain_result
from app.services.pipe.pipe_chain_service import (
    PipeChainInput,
    PipeChainInputError,
    PipeChainResult,
    PipeSegmentInput,
    calc_chain,
)
from app.services.pipe.pressure_drop_service import Fitting

# ---------------------------------------------------------------------------
# Golden fixture 加载
# ---------------------------------------------------------------------------


_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "golden_pipe_chain.json"
GOLDEN = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 辅助构造
# ---------------------------------------------------------------------------


def _liq_seg(**overrides) -> PipeSegmentInput:
    """标准液相段（L=10m, D=0.05m, ρ=1000, μ=1e-3, m=1.0 kg/s, ε=4.6e-5）。"""
    defaults = dict(
        fluid_phase="LIQUID",
        mass_flow_kg_s=1.0,
        density_kg_m3=1000.0,
        viscosity_pa_s=1.0e-3,
        pipe_diameter_m=0.05,
        pipe_roughness_m=4.6e-5,
        length_m=10.0,
    )
    defaults.update(overrides)
    return PipeSegmentInput(**defaults)


def _two_phase_seg(**overrides) -> PipeSegmentInput:
    """标准两相段（水平管气液：水平空气-水简化）。"""
    defaults = dict(
        fluid_phase="TWO_PHASE",
        mass_flow_kg_s=1.05,  # 1.0 l + 0.05 g
        density_kg_m3=500.0,  # 占位；两相段不读
        viscosity_pa_s=5.0e-4,  # 占位
        pipe_diameter_m=0.05,
        pipe_roughness_m=4.5e-5,
        length_m=10.0,
        surface_tension_n_m=0.072,
        liquid_density_kg_m3=1000.0,
        liquid_viscosity_pa_s=1.0e-3,
        gas_density_kg_m3=1.2,
        gas_viscosity_pa_s=1.8e-5,
        liquid_mass_flow_kg_s=1.0,
        gas_mass_flow_kg_s=0.05,
    )
    defaults.update(overrides)
    return PipeSegmentInput(**defaults)


def _golden_input_3_liquid() -> PipeChainInput:
    """golden 3 段全液相串联。"""
    segs = [
        _liq_seg(pipe_diameter_m=0.05, length_m=10.0),
        _liq_seg(pipe_diameter_m=0.08, length_m=5.0),
        _liq_seg(pipe_diameter_m=0.05, length_m=8.0),
    ]
    return PipeChainInput(
        project_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        source_stream_id=uuid.uuid4(),
        tag_number="pipe-001",
        segments=segs,
        inlet_pressure_pa=200_000.0,
    )


# ---------------------------------------------------------------------------
# 1) golden 3 段全液相
# ---------------------------------------------------------------------------


def test_calc_chain_golden_three_liquid_segments():
    """golden：3 段全液相串联 → total_dp / dp_per_segment / Re / f / outlet P。"""
    g = GOLDEN["three_liquid_segments"]
    inp = _golden_input_3_liquid()
    res = calc_chain(inp)

    assert isinstance(res, PipeChainResult)
    # total_dp 容差 1%
    assert math.isclose(
        res.total_dp_pa, g["total_dp_pa"], rel_tol=g["tolerance"]
    ), f"total_dp_pa expected≈{g['total_dp_pa']}, got={res.total_dp_pa}"
    # total_length 严格（直接求和）
    assert res.total_length_m == g["total_length_m"]
    # per-segment 容差 1%
    for i, expected in enumerate(g["dp_per_segment_pa"]):
        assert math.isclose(
            res.dp_per_segment_pa[i], expected, rel_tol=g["tolerance"]
        ), f"dp[{i}] expected≈{expected}, got={res.dp_per_segment_pa[i]}"
    # 入口段特征
    assert math.isclose(res.velocity_m_s, g["velocity_m_s"], rel_tol=1e-3)
    assert math.isclose(res.reynolds, g["reynolds"], rel_tol=1e-3)
    assert math.isclose(res.friction_factor, g["friction_factor"], abs_tol=1e-4)
    # outlet P
    assert math.isclose(
        res.outlet_pressure_pa, g["outlet_pressure_pa"], rel_tol=g["tolerance"]
    )
    # gradient
    assert math.isclose(
        res.pressure_gradient_kpa_m, g["pressure_gradient_kpa_m"], rel_tol=g["tolerance"]
    )
    # 全单相路由
    assert res.need_two_phase is False
    assert res.flow_pattern is None
    # P4-2-5：3 态流场 + confidence 聚合
    assert res.flow_regimes == g["flow_regimes"]  # 全 TURBULENT
    assert res.check_result == g["check_result"]  # PASS（无 TRANSITION 段）
    assert res.check_result_reason is None
    assert res.confidence == g["confidence"]  # HIGH（全段 Re>10000）
    assert len(res.flow_regimes) == 3


# ---------------------------------------------------------------------------
# 2) 单段退化
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 1b) P4-2-5：低 Re 边界 + TRANSITION 链路 + confidence 聚合
# ---------------------------------------------------------------------------


def test_calc_chain_transition_segment_warning_propagates_to_chain():
    """过渡区段（2000≤Re≤4000）：链整体 check_result=WARNING(reason="TRANSITION_REGIME")。

    构造 2 段串联：段 1 油 μ=0.04, Q=4.71e-3 → v=2.4, Re=3000 (TRANSITION)；
    段 2 水 μ=1e-3, Q=1.0, D=0.05 → Re≈25465 (TURBULENT HIGH)。
    链整体：
    - flow_regimes = [TRANSITION, TURBULENT]
    - confidence 聚合 = MEDIUM（最差等级）
    - check_result = WARNING（任一 TRANSITION 强制）
    - check_result_reason = "TRANSITION_REGIME"
    """
    seg_transition = _liq_seg(
        fluid_phase="LIQUID",
        mass_flow_kg_s=4.71e-3 * 1000.0,  # 质量流 = ρ×Q = 4.71 kg/s
        density_kg_m3=1000.0,
        viscosity_pa_s=0.04,  # 油
        pipe_diameter_m=0.05,
        length_m=10.0,
    )
    seg_turb = _liq_seg(
        fluid_phase="LIQUID",
        mass_flow_kg_s=1.0,
        density_kg_m3=1000.0,
        viscosity_pa_s=1.0e-3,  # 水
        pipe_diameter_m=0.05,
        length_m=10.0,
    )
    inp = PipeChainInput(
        project_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        source_stream_id=uuid.uuid4(),
        tag_number="pipe-trans",
        segments=[seg_transition, seg_turb],
        inlet_pressure_pa=200_000.0,
    )
    res = calc_chain(inp)

    # P4-2-5 聚合
    assert res.flow_regimes[0] == "TRANSITION"
    assert res.flow_regimes[1] == "TURBULENT"
    # P4-2-3 R1 fix：段 1 TRANSITION (Re<4000) → confidence=LOW 拖累链整体 → LOW
    # （Crane K 表 Re 区间外；任一 LOW → 整体 LOW）
    assert res.confidence == "LOW"
    assert res.check_result == "WARNING"
    assert res.check_result_reason == "TRANSITION_REGIME"
    # 单段 Re 校验
    assert 2000.0 <= res.reynolds <= 4000.0  # 入口段 = TRANSITION


def test_calc_chain_laminar_segment_confidence_low_aggregates():
    """层流段（Re<2000）：链整体 confidence=LOW（最差等级）。

    段 1：Q=1e-5 → v=5.09e-3 → Re=254 (LAMINAR, confidence=LOW)
    段 2：水常规 TURBULENT HIGH
    链整体：confidence=LOW（最差）
    """
    seg_lam = _liq_seg(
        mass_flow_kg_s=1.0e-5 * 1000.0,  # 0.01 kg/s
        density_kg_m3=1000.0,
        viscosity_pa_s=1.0e-3,
        pipe_diameter_m=0.05,
        length_m=10.0,
    )
    seg_turb = _liq_seg(
        mass_flow_kg_s=1.0,
        density_kg_m3=1000.0,
        viscosity_pa_s=1.0e-3,
        pipe_diameter_m=0.05,
        length_m=10.0,
    )
    inp = PipeChainInput(
        project_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        source_stream_id=uuid.uuid4(),
        tag_number="pipe-lam",
        segments=[seg_lam, seg_turb],
        inlet_pressure_pa=200_000.0,
    )
    res = calc_chain(inp)

    # P4-2-5 聚合
    assert res.flow_regimes[0] == "LAMINAR"
    assert res.flow_regimes[1] == "TURBULENT"
    assert res.confidence == "LOW"  # 任一 LOW → 整体 LOW
    # LAMINAR 段 check=PASS；无 TRANSITION → 链 check=PASS
    assert res.check_result == "PASS"
    assert res.check_result_reason is None


def test_calc_chain_two_phase_segment_flow_regime_placeholder():
    """两相段 flow_regimes 占位 'TURBULENT'，confidence=MEDIUM（不下钻）。"""
    seg_liq = _liq_seg(pipe_diameter_m=0.05, length_m=5.0)
    seg_tp = _two_phase_seg(length_m=10.0)
    inp = PipeChainInput(
        project_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        source_stream_id=uuid.uuid4(),
        tag_number="pipe-tp-regime",
        segments=[seg_liq, seg_tp],
        inlet_pressure_pa=200_000.0,
    )
    res = calc_chain(inp)

    # 两相段占位 TURBULENT + confidence MEDIUM
    assert res.flow_regimes[0] == "TURBULENT"  # 液相段正常
    assert res.flow_regimes[1] == "TURBULENT"  # 两相段占位
    # 链整体 confidence：液相 HIGH + 两相 MEDIUM → MEDIUM
    assert res.confidence == "MEDIUM"


# ---------------------------------------------------------------------------
# 2) 单段退化
# ---------------------------------------------------------------------------


def test_calc_chain_single_segment_degenerate():
    """单段退化：等价于单管（dp_per_segment = [dp_total]）。"""
    seg = _liq_seg(pipe_diameter_m=0.05, length_m=10.0)
    inp = PipeChainInput(
        project_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        source_stream_id=uuid.uuid4(),
        tag_number="pipe-single",
        segments=[seg],
        inlet_pressure_pa=200_000.0,
    )
    res = calc_chain(inp)

    assert len(res.dp_per_segment_pa) == 1
    assert res.total_dp_pa == pytest.approx(res.dp_per_segment_pa[0], rel=1e-9)
    assert res.total_length_m == 10.0
    # 链梯度 = 段梯度
    expected_grad = res.dp_per_segment_pa[0] / 1000.0 / 10.0
    assert res.pressure_gradient_kpa_m == pytest.approx(expected_grad, rel=1e-9)


# ---------------------------------------------------------------------------
# 3) 两相段串联
# ---------------------------------------------------------------------------


def test_calc_chain_two_phase_segment_sets_need_two_phase():
    """两相段：need_two_phase=True + flow_pattern 写入 + outlet P 减少。"""
    seg_liq = _liq_seg(pipe_diameter_m=0.05, length_m=5.0)
    seg_tp = _two_phase_seg(length_m=10.0)
    inp = PipeChainInput(
        project_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        source_stream_id=uuid.uuid4(),
        tag_number="pipe-tp",
        segments=[seg_liq, seg_tp],
        inlet_pressure_pa=200_000.0,
    )
    res = calc_chain(inp)

    assert res.need_two_phase is True
    assert res.flow_pattern is not None
    assert res.flow_pattern in ("ANNULAR", "MIST", "BUBBLE", "SLUG", "STRATIFIED", "WAVE")
    # outlet P = P1 - total_dp；两相 dp 通常 > 单相 dp → outlet P 减少
    assert res.outlet_pressure_pa < 200_000.0
    # total_dp = Σ dp_i（含两相段）
    assert res.total_dp_pa == pytest.approx(sum(res.dp_per_segment_pa), rel=1e-9)
    assert len(res.dp_per_segment_pa) == 2


def test_calc_chain_two_phase_only_segment_uses_liquid_velocity_as_inlet():
    """首段为两相：inlet_velocity 取 liquid_velocity；Re / f = 0（占位）。"""
    seg_tp = _two_phase_seg(length_m=10.0)
    inp = PipeChainInput(
        project_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        source_stream_id=uuid.uuid4(),
        tag_number="pipe-tp-only",
        segments=[seg_tp],
        inlet_pressure_pa=200_000.0,
    )
    res = calc_chain(inp)

    assert res.need_two_phase is True
    assert res.flow_pattern is not None
    # 首段两相时 inlet_reynolds=0 / inlet_f=0
    assert res.reynolds == 0.0
    assert res.friction_factor == 0.0
    assert res.velocity_m_s > 0.0  # liquid_velocity


# ---------------------------------------------------------------------------
# 4) 高程修正
# ---------------------------------------------------------------------------


def test_calc_chain_elevation_correction_adds_rho_g_dz():
    """高程修正：Δz > 0 → +ρgΔz 加进总 dp（液相 ρ=1000, g=9.80665）。"""
    g_val = 9.80665
    seg_no_elev = _liq_seg(pipe_diameter_m=0.05, length_m=10.0, elevation_change_m=0.0)
    seg_elev = _liq_seg(pipe_diameter_m=0.05, length_m=10.0, elevation_change_m=5.0)

    inp_no = PipeChainInput(
        project_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        source_stream_id=uuid.uuid4(),
        tag_number="pipe-noelev",
        segments=[seg_no_elev],
        inlet_pressure_pa=200_000.0,
    )
    inp_yes = PipeChainInput(
        project_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        source_stream_id=uuid.uuid4(),
        tag_number="pipe-elev",
        segments=[seg_elev],
        inlet_pressure_pa=200_000.0,
    )
    res_no = calc_chain(inp_no)
    res_yes = calc_chain(inp_yes)

    expected_elev = 1000.0 * g_val * 5.0  # 49033.25 Pa
    assert res_yes.total_dp_pa == pytest.approx(
        res_no.total_dp_pa + expected_elev, rel=1e-9
    )


def test_calc_chain_elevation_downward_reduces_total_dp():
    """高程向下（Δz < 0）：重力做功 → total_dp 减少。"""
    seg_up = _liq_seg(pipe_diameter_m=0.05, length_m=10.0, elevation_change_m=2.0)
    seg_down = _liq_seg(pipe_diameter_m=0.05, length_m=10.0, elevation_change_m=-2.0)

    inp_up = PipeChainInput(
        project_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        source_stream_id=uuid.uuid4(),
        tag_number="up",
        segments=[seg_up],
        inlet_pressure_pa=200_000.0,
    )
    inp_down = PipeChainInput(
        project_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        source_stream_id=uuid.uuid4(),
        tag_number="down",
        segments=[seg_down],
        inlet_pressure_pa=200_000.0,
    )
    res_up = calc_chain(inp_up)
    res_down = calc_chain(inp_down)

    # 4×ρg = 4×1000×9.80665 = 39226.6 Pa 差
    assert res_down.total_dp_pa < res_up.total_dp_pa
    assert (res_up.total_dp_pa - res_down.total_dp_pa) == pytest.approx(
        4.0 * 1000.0 * 9.80665, rel=1e-9
    )


# ---------------------------------------------------------------------------
# 5) fittings 累加
# ---------------------------------------------------------------------------


def test_calc_chain_fittings_k_accumulates_across_segments():
    """fittings K 值累加：2 段都带 elbow_90 → total_K = 2×0.9 = 1.8。"""
    from app.services.pipe.pressure_drop_service import _K_TABLE

    seg1 = _liq_seg(length_m=5.0, fittings=[Fitting(type="elbow_90")])
    seg2 = _liq_seg(length_m=5.0, fittings=[Fitting(type="elbow_90")])
    inp = PipeChainInput(
        project_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        source_stream_id=uuid.uuid4(),
        tag_number="pipe-fittings",
        segments=[seg1, seg2],
        inlet_pressure_pa=200_000.0,
    )
    res = calc_chain(inp)

    # P4-2-5 K 表 v2 schema：meta.k 取值
    expected_K = 2.0 * _K_TABLE["elbow_90"].k
    assert res.total_K == pytest.approx(expected_K, rel=1e-9)
    assert res.total_K > 0.0  # dp_fittings > 0


# ---------------------------------------------------------------------------
# 6) 边界 + 异常
# ---------------------------------------------------------------------------


def test_calc_chain_empty_segments_raises():
    """空 segments → PipeChainInputError（422）。"""
    inp = PipeChainInput(
        project_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        source_stream_id=uuid.uuid4(),
        tag_number="empty",
        segments=[],
        inlet_pressure_pa=200_000.0,
    )
    with pytest.raises(PipeChainInputError) as exc_info:
        calc_chain(inp)
    assert exc_info.value.code == "PIPE_CHAIN_INPUT_ERROR"
    assert exc_info.value.status == 422


def test_calc_chain_inlet_pressure_non_positive_raises():
    """P1 ≤ 0 → PipeChainInputError（422）。"""
    seg = _liq_seg()
    inp = PipeChainInput(
        project_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        source_stream_id=uuid.uuid4(),
        tag_number="p1-zero",
        segments=[seg],
        inlet_pressure_pa=0.0,
    )
    with pytest.raises(PipeChainInputError):
        calc_chain(inp)


def test_calc_chain_parallel_branches_not_one_raises():
    """parallel_branches ≠ 1 → PipeChainInputError（仅串联支持）。"""
    seg = _liq_seg()
    inp = PipeChainInput(
        project_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        source_stream_id=uuid.uuid4(),
        tag_number="parallel",
        segments=[seg],
        inlet_pressure_pa=200_000.0,
        parallel_branches=2,
    )
    with pytest.raises(PipeChainInputError):
        calc_chain(inp)


def test_calc_chain_two_phase_segment_missing_props_raises():
    """两相段缺 surface_tension / liquid_/gas_ 物性 → PipeChainInputError。"""
    seg = PipeSegmentInput(
        fluid_phase="TWO_PHASE",
        mass_flow_kg_s=1.0,
        density_kg_m3=500.0,
        viscosity_pa_s=5.0e-4,
        pipe_diameter_m=0.05,
        pipe_roughness_m=4.5e-5,
        length_m=10.0,
        # 故意缺 surface_tension_n_m + liquid_/gas_ props
    )
    inp = PipeChainInput(
        project_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        source_stream_id=uuid.uuid4(),
        tag_number="tp-bad",
        segments=[seg],
        inlet_pressure_pa=200_000.0,
    )
    with pytest.raises(PipeChainInputError) as exc_info:
        calc_chain(inp)
    # 异常信息列出 missing 字段
    assert "missing" in str(exc_info.value.details)


# ---------------------------------------------------------------------------
# 7) 落库 roundtrip（pcs_test DB）
# ---------------------------------------------------------------------------


_ONLY_PCS_TEST = pytest.mark.skipif(
    not get_settings().database_url.rstrip("/").endswith("pcs_test"),
    reason="落库 roundtrip 仅允许 pcs_test 库；"
    "需 DATABASE_URL=postgresql+psycopg://pcs:pcs_dev@localhost:5432/pcs_test",
)


@pytest_asyncio.fixture(autouse=True)
async def _reset_async_engine() -> None:
    """每次用例 reset 全局 async engine（绑定当前 event loop）。"""
    await dispose_engines_async()
    yield
    await dispose_engines_async()


async def _make_project_workspace_stream(
    db, project_id: uuid.UUID, workspace_id: uuid.UUID, source_stream_id: uuid.UUID
) -> None:
    """最小 Project + Workspace + Stream 构造（供 persist_pipe_chain_result 落库用）。"""
    from app.models.enums import StreamSignStatus
    from app.models.project import Project, Stream, Workspace

    # 顺序：Workspace 先 flush（PK 已生成）→ Project.workspace_id 引用 → Stream
    ws = Workspace(
        workspace_id=workspace_id,
        workspace_type="FORMAL",
        project_id=project_id,
        name="test",
    )
    db.add(ws)
    await db.flush()
    proj = Project(
        project_id=project_id,
        project_no=f"P-{project_id.hex[:8]}",
        project_name="test",
        owner_company="test",
        location="test",
        project_type="test",
        design_phase="BASIC",
        unit_system="SI",
        status="ACTIVE",
        workspace_id=ws.workspace_id,
    )
    stream = Stream(
        stream_id=source_stream_id,
        project_id=project_id,
        workspace_id=workspace_id,
        stream_name=f"S-{source_stream_id.hex[:8]}",
        case_type="NORMAL",
        data_mode="CHEMICAL",
        source_type="MANUAL_ENTRY",
        sign_status=StreamSignStatus.CHECKED,
        approval_depth=1,
        press=200_000.0,
        temp=298.15,
        composition_json={"C1": 1.0},
    )
    db.add_all([proj, stream])
    await db.flush()


@_ONLY_PCS_TEST
@pytest.mark.asyncio
async def test_persist_pipe_chain_result_roundtrip_pcs_test():
    """P4-2-5：calc → persist_pipe_chain_result → SELECT 11 字段 + outlet_stream。

    覆盖：
    - piping_results.line_no = tag_number
    - line_description / pressure_drop_per_100m / selected_diameter 写入
    - cleaning_method JSONB 含完整 chain input/output
    - record_hash 写入（16 hex）
    - outlet_stream.sign_status=DRAFT, source_type=PIPE_CALCULATED,
      upstream_equipment_type="PIPE"
    """
    project_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    source_stream_id = uuid.uuid4()

    inp = PipeChainInput(
        project_id=project_id,
        workspace_id=workspace_id,
        source_stream_id=source_stream_id,
        tag_number="pipe-rt-001",
        segments=[_liq_seg(pipe_diameter_m=0.05, length_m=10.0)],
        inlet_pressure_pa=200_000.0,
    )
    res = calc_chain(inp)

    factory = get_async_session_factory()
    async with factory() as db:
        await _make_project_workspace_stream(
            db, project_id, workspace_id, source_stream_id
        )
        row, outlet = await persist_pipe_chain_result(db, inp, res)
        await db.commit()
        pipe_id = row.pipe_id
        outlet_id = outlet.stream_id
        row_hash = row.record_hash
        outlet_source_type = outlet.source_type
        outlet_upstream_equip = outlet.upstream_equipment_type
        outlet_sign = outlet.sign_status

    # SELECT 11 P4-0-2 字段 + line_no（链标签） + cleaning_method
    async with factory() as db:
        result = await db.execute(
            text(
                """
                SELECT pipe_id, line_no, line_description, pressure_drop_per_100m,
                       selected_diameter, cleaning_method, record_hash
                FROM piping_results
                WHERE pipe_id = :pk
                """
            ),
            {"pk": str(pipe_id)},
        )
        record = result.mappings().one()
    got = dict(record)

    # line_no 写入
    assert got["line_no"] == "pipe-rt-001"
    # line_description 链摘要
    assert "PIPE_CHAIN" in got["line_description"]
    # pressure_drop_per_100m = gradient × 100
    expected_dp100 = res.pressure_gradient_kpa_m * 100.0
    assert abs(float(got["pressure_drop_per_100m"]) - expected_dp100) < 1e-6
    # selected_diameter mm
    assert abs(float(got["selected_diameter"]) - 50.0) < 1e-6  # D=0.05m → 50mm
    # cleaning_method JSONB 包含 chain input/output
    cm = got["cleaning_method"]
    assert isinstance(cm, list) and len(cm) == 1
    chain_data = cm[0]
    assert chain_data["_chain_calc"] is True
    assert chain_data["_tag_number"] == "pipe-rt-001"
    assert "input" in chain_data and "output" in chain_data
    # record_hash 16 hex
    assert len(row_hash) == 16
    # outlet_stream P4-1-3 helper 复用契约
    assert outlet_source_type == "PIPE_CALCULATED"
    assert outlet_upstream_equip == "PIPE"  # source_type.split("_")[0]
    assert outlet_sign.value == "DRAFT" or str(outlet_sign) == "DRAFT"
    # outlet stream 真实落库
    async with factory() as db:
        sr = await db.execute(
            text(
                "SELECT stream_id, source_type, upstream_equipment_type, "
                "sign_status FROM streams WHERE stream_id = :pk"
            ),
            {"pk": str(outlet_id)},
        )
        srow = sr.mappings().one()
    assert srow["source_type"] == "PIPE_CALCULATED"
    assert srow["upstream_equipment_type"] == "PIPE"
    assert srow["sign_status"] == "DRAFT"


# ---------------------------------------------------------------------------
# 8) API 端到端（client fixture + in-memory SQLite）
# ---------------------------------------------------------------------------


async def _build_full_project_workspace_stream(
    db, project_id: uuid.UUID, workspace_id: uuid.UUID, source_stream_id: uuid.UUID
) -> None:
    """API 测试用：创建完整 Project + Workspace + Stream（CHECKED）。"""
    from app.models.enums import StreamSignStatus
    from app.models.project import Project, Stream, Workspace

    # 顺序：Workspace 先 flush → Project.workspace_id 引用 → Stream
    ws = Workspace(
        workspace_id=workspace_id,
        workspace_type="FORMAL",
        project_id=project_id,
        name="test",
    )
    db.add(ws)
    await db.flush()
    proj = Project(
        project_id=project_id,
        project_no=f"P-{project_id.hex[:8]}",
        project_name="test",
        owner_company="test",
        location="test",
        project_type="test",
        design_phase="BASIC",
        unit_system="SI",
        status="ACTIVE",
        workspace_id=ws.workspace_id,
    )
    stream = Stream(
        stream_id=source_stream_id,
        project_id=project_id,
        workspace_id=workspace_id,
        stream_name=f"S-{source_stream_id.hex[:8]}",
        case_type="NORMAL",
        data_mode="CHEMICAL",
        source_type="MANUAL_ENTRY",
        sign_status=StreamSignStatus.CHECKED,
        approval_depth=1,
        press=200_000.0,
        temp=298.15,
        composition_json={"C1": 1.0},
    )
    db.add_all([proj, stream])
    await db.flush()


@pytest.mark.asyncio
async def test_api_calc_chain_happy_path(client, db_session, sample_designer_token):
    """POST /api/v1/pipe/calc-chain：3 段全液相 → 200/201 + outlet 流。"""
    project_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    source_stream_id = uuid.uuid4()
    await _build_full_project_workspace_stream(
        db_session, project_id, workspace_id, source_stream_id
    )

    body = {
        "project_id": str(project_id),
        "workspace_id": str(workspace_id),
        "source_stream_id": str(source_stream_id),
        "tag_number": "pipe-api-001",
        "inlet_pressure_pa": 200_000.0,
        "inlet_temperature_K": 298.15,
        "parallel_branches": 1,
        "segments": [
            {
                "fluid_phase": "LIQUID",
                "mass_flow_kg_s": 1.0,
                "density_kg_m3": 1000.0,
                "viscosity_pa_s": 1e-3,
                "pipe_diameter_m": 0.05,
                "pipe_roughness_m": 4.6e-5,
                "length_m": 10.0,
            },
            {
                "fluid_phase": "LIQUID",
                "mass_flow_kg_s": 1.0,
                "density_kg_m3": 1000.0,
                "viscosity_pa_s": 1e-3,
                "pipe_diameter_m": 0.08,
                "pipe_roughness_m": 4.6e-5,
                "length_m": 5.0,
            },
            {
                "fluid_phase": "LIQUID",
                "mass_flow_kg_s": 1.0,
                "density_kg_m3": 1000.0,
                "viscosity_pa_s": 1e-3,
                "pipe_diameter_m": 0.05,
                "pipe_roughness_m": 4.6e-5,
                "length_m": 8.0,
            },
        ],
    }
    r = await client.post(
        "/api/v1/pipe/calc-chain",
        json=body,
        headers={"Authorization": f"Bearer {sample_designer_token}"},
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert "chain_result_id" in data
    assert "outlet_stream_id" in data
    assert "record_hash" in data
    assert len(data["record_hash"]) == 16
    # result dict 字段齐
    res = data["result"]
    assert "total_dp_pa" in res
    assert "dp_per_segment_pa" in res
    assert "outlet_pressure_pa" in res
    assert "pressure_gradient_kpa_m" in res
    # golden 容差
    assert math.isclose(
        res["total_dp_pa"], GOLDEN["three_liquid_segments"]["total_dp_pa"], rel_tol=0.01
    )


@pytest.mark.asyncio
async def test_api_calc_chain_stream_not_found_404(
    client, sample_designer_token
):
    """源流不存在 → 404 SIM_STREAM_NOT_FOUND。"""
    body = {
        "project_id": str(uuid.uuid4()),
        "workspace_id": str(uuid.uuid4()),
        "source_stream_id": str(uuid.uuid4()),  # 不存在
        "tag_number": "pipe-404",
        "inlet_pressure_pa": 200_000.0,
        "parallel_branches": 1,
        "segments": [
            {
                "fluid_phase": "LIQUID",
                "mass_flow_kg_s": 1.0,
                "density_kg_m3": 1000.0,
                "viscosity_pa_s": 1e-3,
                "pipe_diameter_m": 0.05,
                "pipe_roughness_m": 4.6e-5,
                "length_m": 10.0,
            }
        ],
    }
    r = await client.post(
        "/api/v1/pipe/calc-chain",
        json=body,
        headers={"Authorization": f"Bearer {sample_designer_token}"},
    )
    assert r.status_code == 404
    assert r.json()["code"] == "SIM_STREAM_NOT_FOUND"


@pytest.mark.asyncio
async def test_api_calc_chain_stream_draft_403(
    client, db_session, sample_designer_token
):
    """源流 sign_status=DRAFT → 403 STREAM_NOT_CHECKED。"""
    from app.models.enums import StreamSignStatus
    from app.models.project import Project, Stream, Workspace

    project_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    source_stream_id = uuid.uuid4()
    # 顺序：Workspace 先 flush → Project.workspace_id 引用
    ws = Workspace(
        workspace_id=workspace_id,
        workspace_type="FORMAL",
        project_id=project_id,
        name="t",
    )
    db_session.add(ws)
    await db_session.flush()
    proj = Project(
        project_id=project_id,
        project_no=f"P-{project_id.hex[:8]}",
        project_name="t",
        owner_company="t",
        location="t",
        project_type="t",
        design_phase="BASIC",
        unit_system="SI",
        status="ACTIVE",
        workspace_id=ws.workspace_id,
    )
    stream = Stream(
        stream_id=source_stream_id,
        project_id=project_id,
        workspace_id=workspace_id,
        stream_name=f"S-{source_stream_id.hex[:8]}",
        case_type="NORMAL",
        data_mode="CHEMICAL",
        source_type="MANUAL_ENTRY",
        sign_status=StreamSignStatus.DRAFT,  # DRAFT → 守卫拒
        approval_depth=1,
        press=200_000.0,
        composition_json={"C1": 1.0},
    )
    db_session.add_all([proj, stream])
    await db_session.flush()

    body = {
        "project_id": str(project_id),
        "workspace_id": str(workspace_id),
        "source_stream_id": str(source_stream_id),
        "tag_number": "pipe-403",
        "inlet_pressure_pa": 200_000.0,
        "parallel_branches": 1,
        "segments": [
            {
                "fluid_phase": "LIQUID",
                "mass_flow_kg_s": 1.0,
                "density_kg_m3": 1000.0,
                "viscosity_pa_s": 1e-3,
                "pipe_diameter_m": 0.05,
                "pipe_roughness_m": 4.6e-5,
                "length_m": 10.0,
            }
        ],
    }
    r = await client.post(
        "/api/v1/pipe/calc-chain",
        json=body,
        headers={"Authorization": f"Bearer {sample_designer_token}"},
    )
    assert r.status_code == 403
    assert r.json()["code"] == "STREAM_NOT_CHECKED"


@pytest.mark.asyncio
async def test_api_calc_chain_empty_segments_422(
    client, db_session, sample_designer_token
):
    """空 segments → 422 PIPE_CHAIN_INPUT_ERROR。"""
    project_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    source_stream_id = uuid.uuid4()
    await _build_full_project_workspace_stream(
        db_session, project_id, workspace_id, source_stream_id
    )

    body = {
        "project_id": str(project_id),
        "workspace_id": str(workspace_id),
        "source_stream_id": str(source_stream_id),
        "tag_number": "pipe-empty",
        "inlet_pressure_pa": 200_000.0,
        "parallel_branches": 1,
        "segments": [],
    }
    r = await client.post(
        "/api/v1/pipe/calc-chain",
        json=body,
        headers={"Authorization": f"Bearer {sample_designer_token}"},
    )
    assert r.status_code == 422
    # 422 来自 Pydantic 验证（segments min_length 隐式 ≥ 1）或业务；任一
    # 422 即通过
    assert r.json()["code"] in (
        "PIPE_CHAIN_INPUT_ERROR",
        "VALIDATION_ERROR",
    )
