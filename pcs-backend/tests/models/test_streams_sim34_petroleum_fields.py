"""P3.x SIM-34：炼油专用 5 字段 + 蒸馏曲线 8 种 schema 验证。

spec ADD-001 §3.8-3.9：
- rvp / tvp / watson_k / flash_point（4 Float 字段入 ORM）
- distillation_curves JSONB 容器（spec V1.1 §变更 8 蒸馏曲线 8 种 schema）
  - D86 / TBP / EFV / D86_CRACKING / D1160 / D2887 / D5236 / D7169
"""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio

from app.services.distillation_curve_validator import (
    DISTILLATION_CURVE_TYPES,
    DistillationCurveValidationError,
    validate_distillation_curves,
)


# ---------------------------------------------------------------------------
# 1. 8 种曲线类型枚举
# ---------------------------------------------------------------------------


def test_distillation_curve_types_contains_8_types():
    assert DISTILLATION_CURVE_TYPES == frozenset(
        {
            "D86",
            "TBP",
            "EFV",
            "D86_CRACKING",
            "D1160",
            "D2887",
            "D5236",
            "D7169",
        }
    )


# ---------------------------------------------------------------------------
# 2. 单条曲线合法 + 非法边界
# ---------------------------------------------------------------------------


def _d86_curve() -> dict:
    """合法 D86 曲线（常压，无 pressure_mmhg）。"""
    return {
        "curve_type": "D86",
        "points": [
            {"percent_vapor": 0.0, "temp_c": 35.0},  # IBP
            {"percent_vapor": 50.0, "temp_c": 150.0},
            {"percent_vapor": 100.0, "temp_c": 350.0},  # FBP
        ],
    }


def _d1160_curve() -> dict:
    """合法 D1160 减压曲线（pressure_mmhg 必填 > 0）。"""
    return {
        "curve_type": "D1160",
        "pressure_mmhg": 10.0,
        "points": [
            {"percent_vapor": 0.0, "temp_c": 250.0},
            {"percent_vapor": 50.0, "temp_c": 400.0},
            {"percent_vapor": 100.0, "temp_c": 550.0},
        ],
    }


@pytest.mark.parametrize(
    "curve",
    [
        _d86_curve(),
        _d1160_curve(),
        {
            "curve_type": "TBP",
            "points": [
                {"percent_vapor": 0, "temp_c": 40},
                {"percent_vapor": 100, "temp_c": 360},
            ],
        },
        {
            "curve_type": "EFV",
            "pressure_mmhg": 760,
            "points": [
                {"percent_vapor": 10, "temp_c": 100},
                {"percent_vapor": 90, "temp_c": 300},
            ],
        },
        {
            "curve_type": "D2887",
            "points": [
                {"percent_vapor": 0.5, "temp_c": 50},
                {"percent_vapor": 99.5, "temp_c": 540},
            ],
        },
    ],
)
def test_valid_curves_pass(curve):
    """8 种曲线合法 schema 通过验证。"""
    validate_distillation_curves([curve])  # 不抛


def test_empty_or_none_curves_pass():
    """空 list 或 None 不抛（允许无蒸馏曲线）。"""
    validate_distillation_curves([])
    validate_distillation_curves(None)


# ---------------------------------------------------------------------------
# 3. 非法边界
# ---------------------------------------------------------------------------


def test_unknown_curve_type_rejected():
    with pytest.raises(DistillationCurveValidationError, match="curve_type"):
        validate_distillation_curves(
            [{"curve_type": "D9999", "points": [{"percent_vapor": 0, "temp_c": 100}]}]
        )


def test_empty_points_rejected():
    with pytest.raises(DistillationCurveValidationError, match="points 必须非空"):
        validate_distillation_curves([{"curve_type": "D86", "points": []}])


def test_percent_vapor_must_be_strictly_increasing():
    with pytest.raises(DistillationCurveValidationError, match="严格 > 前点"):
        validate_distillation_curves(
            [
                {
                    "curve_type": "D86",
                    "points": [
                        {"percent_vapor": 0, "temp_c": 30},
                        {"percent_vapor": 50, "temp_c": 150},
                        {"percent_vapor": 50, "temp_c": 200},  # 不增
                    ],
                }
            ]
        )


def test_percent_vapor_out_of_range_rejected():
    with pytest.raises(DistillationCurveValidationError, match="越界"):
        validate_distillation_curves(
            [
                {
                    "curve_type": "D86",
                    "points": [
                        {"percent_vapor": -1, "temp_c": 30},
                    ],
                }
            ]
        )


def test_temp_c_must_be_non_decreasing():
    with pytest.raises(DistillationCurveValidationError, match="≥ 前点"):
        validate_distillation_curves(
            [
                {
                    "curve_type": "D86",
                    "points": [
                        {"percent_vapor": 0, "temp_c": 200},
                        {"percent_vapor": 50, "temp_c": 100},  # 下降
                    ],
                }
            ]
        )


def test_d1160_requires_pressure_positive():
    """D1160（减压）pressure_mmhg 必填 > 0。"""
    with pytest.raises(DistillationCurveValidationError, match="pressure_mmhg 必须"):
        validate_distillation_curves(
            [
                {
                    "curve_type": "D1160",
                    "points": [{"percent_vapor": 0, "temp_c": 250}],
                    # 缺 pressure_mmhg
                }
            ]
        )


def test_d86_with_negative_pressure_rejected():
    """D86（常压）pressure_mmhg 应为 None，负值拒绝。"""
    with pytest.raises(DistillationCurveValidationError, match="pressure_mmhg"):
        validate_distillation_curves(
            [
                {
                    "curve_type": "D86",
                    "pressure_mmhg": -1.0,
                    "points": [{"percent_vapor": 0, "temp_c": 30}],
                }
            ]
        )


def test_curve_index_in_error_message():
    """错误信息含曲线索引（多曲线时定位）。"""
    with pytest.raises(DistillationCurveValidationError, match="曲线 #1"):
        validate_distillation_curves(
            [
                _d86_curve(),
                {"curve_type": "INVALID_TYPE", "points": []},
            ]
        )


def test_curves_must_be_list():
    with pytest.raises(DistillationCurveValidationError, match="必须为 list"):
        validate_distillation_curves({"curve_type": "D86"})  # 错：dict


# ---------------------------------------------------------------------------
# 4. ORM Stream 5 字段 round-trip
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def make_project(db):
    async def _make():
        from app.models.project import Project, Workspace

        ws = Workspace(workspace_type="FORMAL", name=f"ws-{uuid.uuid4().hex[:8]}")
        db.add(ws)
        await db.flush()
        proj = Project(
            project_no=f"P-{uuid.uuid4().hex[:8]}",
            project_name="炼油测试项目",
            owner_company="测试",
            location="测试",
            project_type="PETROLEUM",
            design_phase="FEED",
            unit_system="SI",
            workspace_id=ws.workspace_id,
        )
        db.add(proj)
        await db.commit()
        return proj

    return _make


@pytest.mark.asyncio
async def test_petroleum_fields_round_trip(db, make_project):
    """rvp/tvp/watson_k/flash_point/distillation_curves ORM 读写。"""
    from sqlalchemy import select

    from app.models.project import Stream

    proj = await make_project()
    stream = Stream(
        project_id=proj.project_id,
        workspace_id=proj.workspace_id,
        stream_name="NAPHTHA-101",
        data_mode="PETROLEUM",
        source_type="MANUAL_ENTRY",
        approval_depth=1,
        rvp=10.5,
        tvp=12.3,
        watson_k=11.8,
        flash_point=-5.0,
        distillation_curves={"curves": [_d86_curve()]},
    )
    db.add(stream)
    await db.commit()
    stream_id = stream.stream_id

    loaded = (
        await db.execute(select(Stream).where(Stream.stream_id == stream_id))
    ).scalar_one()
    assert loaded.rvp == pytest.approx(10.5, abs=1e-3)
    assert loaded.tvp == pytest.approx(12.3, abs=1e-3)
    assert loaded.watson_k == pytest.approx(11.8, abs=1e-3)
    assert loaded.flash_point == pytest.approx(-5.0, abs=1e-3)
    assert loaded.distillation_curves["curves"][0]["curve_type"] == "D86"


# ---------------------------------------------------------------------------
# 5. property_conflict_resolver USER_PRIORITY 字段名（SIM-33 同步）
# ---------------------------------------------------------------------------


def test_conflict_resolver_uses_sim33_renamed_field_names():
    """SIM-34 同步：conflict_resolver 用 liquid_surface_tension（SIM-33 新名）。"""
    from app.services.property_conflict_resolver import USER_PRIORITY_FIELDS

    assert "liquid_surface_tension" in USER_PRIORITY_FIELDS
    assert "surface_tension" not in USER_PRIORITY_FIELDS  # 旧名已失效
    assert "rvp" in USER_PRIORITY_FIELDS
    assert "tvp" in USER_PRIORITY_FIELDS