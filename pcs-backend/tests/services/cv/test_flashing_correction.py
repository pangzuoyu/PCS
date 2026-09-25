"""P6-4 Task 5 (C-24): cv/flashing_correction 单元测试 + 黄金 fixture + 集成测试。

按 SPEC §3.2.1.5 + V1.2 brief 10 单元测试 + 2 黄金 fixture + 集成测试：

10 单元测试（brief D12 +2 边界）：
1. test_masonelian_fl_default_model（MASONELIAN_1973）
2. test_chapman_jans_model
3. test_tong_model
4. test_flash_steam_rate_basic
5. test_valve_library_24_combinations
6. test_lookup_valve_params_unknown_422
7. test_validate_fl_ff_out_of_range_422
8. test_validate_fl_ff_not_strict_422（FL ≥ FF 工程违反）
9. test_masonelian_fl_x_zero_returns_FL
10. test_masonelian_fl_x_one_returns_422（除零）

2 黄金 fixture（brief §V1.0）：
- golden_masonelian_fl.json（18 组 = x ∈ {0.1, 0.3, 0.5, 0.7} × FL ∈ {0.9, 0.85} × 3 模型）
- golden_flash_steam_rate.json（典型工况 5 组）

集成测试：
- test_cv_engine_integration_liquid_with_p2_pa（CvEngine + P2_pa 路径）
- test_cv_persist_persists_masonelian_model（DB 落库 masonelian_model 列）
- test_cv_api_response_includes_3_optional_fields（POST /cv/calculate 响应含 3 字段）

cv 回归测试：test_cv_engine.py + test_cv_persist.py + test_cv_api.py +
test_cv_vs_chedl.py 全通过（FL/FF 工程裁决后无回归）。

设计要点：
- 黄金 fixture 容差 rel=1e-4（拟合公式 brief D5 <1%）
- 强公式 flash_steam_rate 容差 rel=1e-4（brief D5 <0.1%）
- 集成测试用 in-memory SQLite + httpx async（与既有 cv 测试一致）
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio

from app.models.project import Stream
from app.services.cv import cv_engine
from app.services.cv.cv_persist import CvService
from app.services.cv.flashing_correction import (
    _DEFAULT_MASONELIAN_MODEL,
    _VALVE_LIBRARY_SIZE,
    InvalidFLFFError,
    _flash_steam_rate_kg_s,
    _masonelian_fl,
    _validate_fl_ff,
    calculate_flash_correction,
    lookup_valve_params,
    valve_library_size,
)

# ============================================================================
# 黄金 fixture 加载
# ============================================================================

_FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def golden_masonelian_fl_cases() -> list[dict[str, Any]]:
    """Masonelian fl 黄金 fixture（18 组）。"""
    with (_FIXTURES_DIR / "golden_masonelian_fl.json").open(encoding="utf-8") as f:
        data = json.load(f)
    return data["cases"]


@pytest.fixture(scope="module")
def golden_flash_steam_rate_cases() -> list[dict[str, Any]]:
    """闪蒸蒸汽量黄金 fixture（5 组）。"""
    with (_FIXTURES_DIR / "golden_flash_steam_rate.json").open(encoding="utf-8") as f:
        data = json.load(f)
    return data["cases"]


# ============================================================================
# 1. 3 模型并存：MASONELIAN_1973 / CHAPMAN_JANS / TONG（brief 5 测试点 a/b/c）
# ============================================================================


def test_masonelian_fl_default_model():
    """3 模型 - 默认 MASONELIAN_1973：Eq.5 fl = FL · (1+0.5x)(1-x) / √(1-x²)。

    工况：FL=0.9, x=0.5 → fl = 0.9 · 1.25 · 0.5 / √0.75 ≈ 0.6495。
    D5 验收：<1%（拟合公式）。
    """
    fl = _masonelian_fl(FL=0.9, x=0.5, model="MASONELIAN_1973")
    expected = 0.9 * 1.25 * 0.5 / math.sqrt(0.75)
    assert fl == pytest.approx(expected, rel=1e-9), (
        f"MASONELIAN_1973 fl 应为 {expected:.6f}，实际 {fl:.6f}"
    )


def test_chapman_jans_model():
    """3 模型 - CHAPMAN_JANS：商业软件对账 fl = FL · (1-x)² / (1-x²)。

    工况：FL=0.9, x=0.5 → fl = 0.9 · 0.25 / 0.75 = 0.3。
    """
    fl = _masonelian_fl(FL=0.9, x=0.5, model="CHAPMAN_JANS")
    expected = 0.9 * 0.25 / 0.75
    assert fl == pytest.approx(expected, rel=1e-9), (
        f"CHAPMAN_JANS fl 应为 {expected:.6f}，实际 {fl:.6f}"
    )


def test_tong_model():
    """3 模型 - TONG：简化初算 fl = FL · √(1-x)。

    工况：FL=0.9, x=0.5 → fl = 0.9 · √0.5 ≈ 0.6364。
    """
    fl = _masonelian_fl(FL=0.9, x=0.5, model="TONG")
    expected = 0.9 * math.sqrt(0.5)
    assert fl == pytest.approx(expected, rel=1e-9), (
        f"TONG fl 应为 {expected:.6f}，实际 {fl:.6f}"
    )


# ============================================================================
# 2. flash_steam_rate 强公式（brief 5 测试点 d）
# ============================================================================


def test_flash_steam_rate_basic(golden_flash_steam_rate_cases):
    """闪蒸蒸汽量：5 组黄金 fixture（D5 <0.1% 容差）。"""
    for case in golden_flash_steam_rate_cases:
        actual = _flash_steam_rate_kg_s(
            Q_m3h=case["Q_m3h"],
            SG=case["SG"],
            P1_pa=case["P1_pa"],
            P2_pa=case["P2_pa"],
            Pv_pa=case["Pv_pa"],
        )
        expected = case["expected_flash_rate_kg_s"]
        assert actual == pytest.approx(expected, rel=1e-4), (
            f"工况 {case['description']}：flash_rate 应为 {expected:.6f}，"
            f"实际 {actual:.6f}"
        )


# ============================================================================
# 3. 24 阀门厂组合（brief 5 测试点 e）
# ============================================================================


def test_valve_library_24_combinations():
    """24 阀门厂组合：6 厂商 × 4 阀型 = 24（brief D5 验收；D12 size 常量）。

    遍历 24 组合，全部 lookup_valve_params 命中 + 含 FL/FF/Cf 键。
    """
    assert valve_library_size() == _VALVE_LIBRARY_SIZE == 24, (
        f"阀门厂库应 24 组合，实际 {valve_library_size()}"
    )

    # 6 厂商 × 4 阀型 = 24 组合（参照 SPEC §3.2.1 表 3.2.1-3）
    vendors = ("GLOBE", "BALL", "GATE", "BUTTERFLY", "PLUG", "DIAPHRAGM")
    valve_models = ("MASONELIAN", "FISHER", "SAMSON", "EMERSON")

    hit_count = 0
    for vendor in vendors:
        for valve_model in valve_models:
            params = lookup_valve_params(vendor, valve_model)
            assert "FL" in params and "FF" in params and "Cf" in params
            # FL < FF 工程约定（V1.2 T5 裁决）
            assert params["FL"] < params["FF"], (
                f"({vendor}, {valve_model}) 应满足 FL < FF，实际 "
                f"FL={params['FL']}, FF={params['FF']}"
            )
            # 范围校验
            assert 0.0 < params["FL"] <= 1.0
            assert 0.0 < params["FF"] <= 1.0
            assert 0.0 < params["Cf"] <= 1.0
            hit_count += 1
    assert hit_count == 24, f"应命中 24 组合，实际 {hit_count}"


# ============================================================================
# 4. 未命中阀型 → 422（brief 5 测试点 f）
# ============================================================================


def test_lookup_valve_params_unknown_422():
    """未命中阀门厂 → InvalidFLFFError 422（统一 envelope）。"""
    with pytest.raises(InvalidFLFFError) as exc_info:
        lookup_valve_params("UNKNOWN_VENDOR", "UNKNOWN_MODEL")
    # PcsError envelope
    assert exc_info.value.status == 422
    assert exc_info.value.code == "CV_INVALID_FL_FF"


# ============================================================================
# 5. flash_fraction 越界 / FL-FF 越界 → 422（brief 5 测试点 g）
# ============================================================================


def test_validate_fl_ff_out_of_range_422():
    """FL ∉ [0, 1] 或 FF ∉ [0, 1] → 422。"""
    # FL < 0
    with pytest.raises(InvalidFLFFError):
        _validate_fl_ff(FL=-0.1, FF=0.96)
    # FL > 1
    with pytest.raises(InvalidFLFFError):
        _validate_fl_ff(FL=1.5, FF=0.96)
    # FF < 0
    with pytest.raises(InvalidFLFFError):
        _validate_fl_ff(FL=0.9, FF=-0.1)
    # FF > 1
    with pytest.raises(InvalidFLFFError):
        _validate_fl_ff(FL=0.9, FF=1.5)


def test_validate_fl_ff_not_strict_422():
    """FL ≥ FF（违背 IEC 60534-2-1 §5.2 工程约定）→ 422。

    V1.2 T5 实施裁决：FL ≥ FF 触发 InvalidFLFFError；详见 _validate_fl_ff docstring
    （V1.2 brief 字面 FL > FF 与 IEC 物理约定冲突，T5 改为 FL < FF 工程约定）。
    """
    # FL == FF（边界）
    with pytest.raises(InvalidFLFFError):
        _validate_fl_ff(FL=0.9, FF=0.9)
    # FL > FF（违背工程约定）
    with pytest.raises(InvalidFLFFError):
        _validate_fl_ff(FL=0.96, FF=0.90)


# ============================================================================
# 6. x=0 边界：fl → FL（brief 5 测试点 h）
# ============================================================================


def test_masonelian_fl_x_zero_returns_FL():
    """x=0 边界：3 模型都应返回 fl = FL（无压差时闪蒸修正无衰减）。

    MASONELIAN_1973: fl(0) = FL · 1 · 1 / 1 = FL ✓
    CHAPMAN_JANS:    fl(0) = FL · 1 / 1 = FL ✓
    TONG:            fl(0) = FL · 1 = FL ✓

    取 x=1e-5（趋近 0 但 > 0）；容差 rel=1e-4（CHAPMAN_JANS 在 x=0.001 时偏差 0.2%）。
    """
    for model in ("MASONELIAN_1973", "CHAPMAN_JANS", "TONG"):
        # x 严格 > 0，趋近 0 → fl → FL
        fl = _masonelian_fl(FL=0.9, x=1.0e-5, model=model)
        assert fl == pytest.approx(0.9, rel=1e-4), (
            f"{model} x→0+ 时 fl 应趋近 0.9，实际 {fl}"
        )


# ============================================================================
# 7. x=1 边界：除零 → 422（brief 5 测试点 i）
# ============================================================================


def test_masonelian_fl_x_one_returns_422():
    """x=1 边界：MASONELIAN_1973/CHAPMAN_JANS 分母为零 → ValueError 422。

    x=1 时 P2=0（不物理）；_masonelian_fl 抛 ValueError 由 API 层转 422 envelope。
    """
    for model in ("MASONELIAN_1973", "CHAPMAN_JANS"):
        with pytest.raises(ValueError):
            _masonelian_fl(FL=0.9, x=1.0, model=model)


# ============================================================================
# 8. 黄金 fixture 全面回归（18 + 5 = 23 例）
# ============================================================================


def test_golden_masonelian_fl_fixture(golden_masonelian_fl_cases):
    """黄金 fixture 回归：18 组 = x ∈ {0.1, 0.3, 0.5, 0.7} × FL ∈ {0.9, 0.85} × 3 模型。

    D5 验收：MASONELIAN_1973 <1% 拟合精度；强公式 <0.1%。
    """
    for case in golden_masonelian_fl_cases:
        actual = _masonelian_fl(
            FL=case["FL"], x=case["x"], model=case["model"]
        )
        expected = case["expected_fl"]
        assert actual == pytest.approx(expected, rel=1e-4), (
            f"FL={case['FL']}, x={case['x']}, model={case['model']}: "
            f"应为 {expected:.6f}，实际 {actual:.6f}"
        )


# ============================================================================
# 集成测试（cv_engine 集成）
# ============================================================================


def test_cv_engine_integration_liquid_with_p2_pa():
    """CvEngine 集成：LIQUID 路径 + 完整 P2_pa → fl/flash_steam_rate/masonelian_model。

    验证 cv_engine.calculate() 在 P2_pa 存在时正确计算闪蒸修正 3 字段。
    """
    engine = cv_engine.CvEngine()
    payload = engine.calculate(
        fluid_phase="LIQUID",
        Q_m3h=100.0, SG=1.0, dP_bar=2.0,
        FL=0.9, FF=0.96, Pv=2000.0, Pc=22.0e6,
        P1_pa=5.0e5, P2_pa=3.0e5,  # 完整 P1/P2
    )

    # 3 字段都应非 None（LIQUID + P2_pa 路径）
    assert payload["fl"] is not None, "LIQUID + P2_pa 路径 fl 应填充"
    assert payload["flash_steam_rate_kg_s"] is not None, "LIQUID + P2_pa 路径 flash_rate 应填充"
    assert payload["masonelian_model"] == _DEFAULT_MASONELIAN_MODEL, (
        f"默认 masonelian_model 应为 {_DEFAULT_MASONELIAN_MODEL}，"
        f"实际 {payload['masonelian_model']}"
    )

    # Cv 关键字段不受影响
    assert payload["Cv_calculated"] > 0
    assert payload["fluid_phase"] == "LIQUID"


def test_cv_engine_integration_liquid_without_p2_pa():
    """CvEngine 集成：LIQUID 路径缺 P2_pa → fl/flash_rate 留 None（P6-4 T5 容差）。

    masonelian_model 仍记录用户口径；Cv 主流程不因此失败（22 由 Pydantic 校验守住）。
    """
    engine = cv_engine.CvEngine()
    payload = engine.calculate(
        fluid_phase="LIQUID",
        Q_m3h=100.0, SG=1.0, dP_bar=1.0,
        FL=0.9, FF=0.96, Pv=2000.0, Pc=22.0e6,
        P1_pa=3.0e5,
        # 无 P2_pa → _flash_steam_rate_kg_s 抛 ValueError → try/except 留 None
    )
    # fl / flash_steam_rate_kg_s 应为 None（P6-4 T5 容差）
    assert payload["fl"] is None, "无 P2_pa 时 fl 应留 None"
    assert payload["flash_steam_rate_kg_s"] is None, "无 P2_pa 时 flash_rate 应留 None"
    # masonelian_model 仍记录默认口径
    assert payload["masonelian_model"] == _DEFAULT_MASONELIAN_MODEL


# ============================================================================
# 集成测试（cv_persist 落库）
# ============================================================================


@pytest_asyncio.fixture
async def source_stream(db, project_id, workspace_id) -> Stream:
    """源流 fixture（与 test_cv_persist 一致；cv_persist 仅校验 project_id 一致）。"""
    s = Stream(
        project_id=project_id,
        workspace_id=workspace_id,
        stream_name=f"S-CV-FL-{project_id.hex[:8]}",
        case_type="NORMAL",
        data_mode="CHEMICAL",
        source_type="MANUAL_ENTRY",
        approval_depth=1,
    )
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return s


def _base_request_with_p2(project_id, workspace_id) -> dict:
    """最小液体工况请求（完整 P2_pa 触发 flash correction）。"""
    return {
        "project_id": project_id,
        "workspace_id": workspace_id,
        "fluid_phase": "LIQUID",
        "Q_m3h": 100.0,
        "SG": 1.0,
        "dP_bar": 2.0,
        "FL": 0.9,
        "FF": 0.96,
        "Pv": 2000.0,
        "Pc": 22.0e6,
        "P1_pa": 5.0e5,
        "P2_pa": 3.0e5,  # 完整 P2 触发 flash correction
        "T1_k": 300.0,
    }


@pytest.mark.asyncio
async def test_cv_persist_persists_masonelian_model(
    db, source_stream, project_id, workspace_id
):
    """cv_persist 落库：masonelian_model ORM 列 + output_json JSONB 容器双写。

    V1.2 D3 严格：
    - masonelian_model 走 ORM 列（cv_result.masonelian_model == 'MASONELIAN_1973'）
    - fl / flash_steam_rate_kg_s 走 output_json JSONB 容器（cv_result.output_json 含 3 字段）
    """
    req = _base_request_with_p2(project_id, workspace_id)
    cv_result = await CvService.persist_calculate(
        db, source_stream_id=source_stream.stream_id, request=req,
    )

    # 1. ORM 列 masonelian_model（V1.2 D3：仅 1 列）
    assert cv_result.masonelian_model == "MASONELIAN_1973", (
        f"ORM 列 masonelian_model 应为 'MASONELIAN_1973'，"
        f"实际 {cv_result.masonelian_model}"
    )

    # 2. JSONB 容器 output_json 含 3 字段（V1.2 D3：fl/flash_rate 走 JSONB）
    output_json = cv_result.output_json or {}
    assert "fl" in output_json, f"output_json 应含 fl 字段，实际 {list(output_json)}"
    assert "flash_steam_rate_kg_s" in output_json, (
        f"output_json 应含 flash_steam_rate_kg_s 字段，实际 {list(output_json)}"
    )
    assert "masonelian_model" in output_json, (
        f"output_json 应含 masonelian_model 字段，实际 {list(output_json)}"
    )


@pytest.mark.asyncio
async def test_cv_api_response_includes_3_optional_fields(
    client, source_stream, project_id, workspace_id
):
    """POST /cv/calculate 响应含 3 Optional 字段（commit 4 验收）。

    V1.2 D3 + V1.0 兼容：3 字段全部 Optional 默认 None；LIQUID + P2_pa 路径填充。
    """
    req = _base_request_with_p2(project_id, workspace_id)
    # Pydantic CvCalculateRequest 转换（UUID 转字符串）
    req_api = {
        **{k: str(v) if hasattr(v, "hex") else v for k, v in req.items()},
        "source_stream_id": str(source_stream.stream_id),
    }

    r = await client.post("/api/v1/cv/calculate", json=req_api)
    assert r.status_code == 201, r.text
    body = r.json()

    # 3 Optional 字段应在响应中（即使 None）
    assert "fl" in body, f"响应应含 fl 字段，实际 {list(body)}"
    assert "flash_steam_rate_kg_s" in body, (
        f"响应应含 flash_steam_rate_kg_s 字段，实际 {list(body)}"
    )
    assert "masonelian_model" in body, (
        f"响应应含 masonelian_model 字段，实际 {list(body)}"
    )

    # LIQUID + P2_pa 路径：masonelian_model 应填充默认口径
    assert body["masonelian_model"] == "MASONELIAN_1973"


# ============================================================================
# calculate_flash_correction 主入口（端到端）
# ============================================================================


def test_calculate_flash_correction_end_to_end():
    """calculate_flash_correction 主入口：5 字段 + 元数据。

    验证主入口正确组装 fl/flash_steam_rate_kg_s/masonelian_model + x/FL/FF 元数据。
    """
    result = calculate_flash_correction(
        Q_m3h=100.0, SG=1.0, dP_bar=2.0,
        P1_pa=5.0e5, P2_pa=3.0e5, Pv_pa=2000.0,
        FL=0.9, FF=0.96,
    )

    # 5 关键字段
    assert result["fl"] > 0
    assert result["flash_steam_rate_kg_s"] >= 0
    assert result["masonelian_model"] == "MASONELIAN_1973"
    assert result["x"] == pytest.approx(0.4, rel=1e-6), (
        f"x = dP/P1 应为 0.4，实际 {result['x']}"
    )
    # 元数据 FL/FF 透传
    assert result["FL"] == 0.9
    assert result["FF"] == 0.96


def test_calculate_flash_correction_with_vendor_override():
    """calculate_flash_correction + vendor/valve_model 阀门厂覆盖。

    用户传 vendor/valve_model → 阀门厂 FL/FF 覆盖用户值。
    用户 FL/FF 必须先通过校验（FL < FF），再被阀门厂数据覆盖。
    """
    result = calculate_flash_correction(
        Q_m3h=100.0, SG=1.0, dP_bar=2.0,
        P1_pa=5.0e5, P2_pa=3.0e5, Pv_pa=2000.0,
        FL=0.5, FF=0.96,  # 用户值（合规 FL < FF，但会被阀门厂覆盖）
        vendor="GLOBE",
        valve_model="MASONELIAN",
    )

    # 阀门厂覆盖 FL/FF（GLOBE/MASONELIAN: FL=0.90, FF=0.96）
    assert result["FL"] == 0.90
    assert result["FF"] == 0.96
    # 元数据 vendor/valve_model 透传
    assert result["vendor"] == "GLOBE"
    assert result["valve_model"] == "MASONELIAN"