"""P6-4 T3 D7 接口冻结签名快照测试（item 37 + ADR-0040）。

按 SPEC §3.4.4 C-12 + ADR-0040 V1.0：
calc_partial_volume / calc_wetted_area / mass_iteration_loop 三个公共函数
签名 + 行为冻结至 2027-03-25。本测试用 inspect.signature 锁定函数签名：
任何参数重命名 / 类型变更 / 默认值变更 / 新增必填参数 = 测试失败
→ 需新 ADR-0041+ 解除冻结。

冻结范围（详见 ADR-0040 §"Contract"）：
- 函数名（calc_partial_volume / calc_wetted_area / mass_iteration_loop）
- 参数名 + 类型注解 + 默认值
- 返回值结构（PartialVolumeResult / WettedAreaResult / MassIterationResult）
- 异常类型（VesselInputError / MassIterationNotConvergedError）
"""
from __future__ import annotations

import inspect

from app.services.vessel.vessel_service import (
    MassIterationInput,
    MassIterationNotConvergedError,
    MassIterationResult,
    PartialVolumeInput,
    PartialVolumeResult,
    VesselInputError,
    WettedAreaInput,
    WettedAreaResult,
    calc_partial_volume,
    calc_wetted_area,
    mass_iteration_loop,
)

# ============================================================================
# 1. 函数签名冻结（inspect.signature 快照）
# ============================================================================


def _signature_dict(func):
    """提取 inspect.signature 到 dict，便于对比。"""
    sig = inspect.signature(func)
    return {
        "name": func.__name__,
        "params": {
            name: {
                "kind": str(param.kind),
                "default": (
                    param.default if param.default is not inspect.Parameter.empty
                    else "<no-default>"
                ),
                "annotation": (
                    str(param.annotation)
                    if param.annotation is not inspect.Parameter.empty
                    else "<no-annotation>"
                ),
            }
            for name, param in sig.parameters.items()
        },
        "return_annotation": (
            str(sig.return_annotation)
            if sig.return_annotation is not inspect.Signature.empty
            else "<no-return>"
        ),
    }


def test_freeze_calc_partial_volume_signature():
    """calc_partial_volume 签名冻结（item 37）。"""
    expected_params = {
        "inp": {
            "kind": "POSITIONAL_OR_KEYWORD",
            "default": "<no-default>",
            "annotation": "PartialVolumeInput",
        },
    }
    sig = _signature_dict(calc_partial_volume)
    assert sig["name"] == "calc_partial_volume"
    assert sig["params"] == expected_params
    assert sig["return_annotation"] == "PartialVolumeResult"


def test_freeze_calc_wetted_area_signature():
    """calc_wetted_area 签名冻结（item 37）。"""
    expected_params = {
        "inp": {
            "kind": "POSITIONAL_OR_KEYWORD",
            "default": "<no-default>",
            "annotation": "WettedAreaInput",
        },
    }
    sig = _signature_dict(calc_wetted_area)
    assert sig["name"] == "calc_wetted_area"
    assert sig["params"] == expected_params
    assert sig["return_annotation"] == "WettedAreaResult"


def test_freeze_mass_iteration_loop_signature():
    """mass_iteration_loop 签名冻结（item 37）。"""
    expected_params = {
        "inp": {
            "kind": "POSITIONAL_OR_KEYWORD",
            "default": "<no-default>",
            "annotation": "MassIterationInput",
        },
        "tol": {
            "kind": "POSITIONAL_OR_KEYWORD",
            "default": 1e-06,
            "annotation": "float",
        },
        "max_iter": {
            "kind": "POSITIONAL_OR_KEYWORD",
            "default": 50,
            "annotation": "int",
        },
    }
    sig = _signature_dict(mass_iteration_loop)
    assert sig["name"] == "mass_iteration_loop"
    assert sig["params"] == expected_params
    assert sig["return_annotation"] == "MassIterationResult"


# ============================================================================
# 2. dataclass 字段冻结（frozen + 字段名集合）
# ============================================================================


def test_freeze_partial_volume_input_fields():
    """PartialVolumeInput 字段冻结（5 字段：含 n_vessels 默认 1）。"""
    from dataclasses import fields

    field_names = {f.name for f in fields(PartialVolumeInput)}
    assert field_names == {"D_m", "L_m", "head_type", "H_m", "n_vessels"}
    # n_vessels 默认 1（其余必填）
    n_vessels_field = next(f for f in fields(PartialVolumeInput) if f.name == "n_vessels")
    assert n_vessels_field.default == 1


def test_freeze_wetted_area_input_fields():
    """WettedAreaInput 字段冻结。"""
    from dataclasses import fields

    field_names = {f.name for f in fields(WettedAreaInput)}
    assert field_names == {"D_m", "L_m", "head_type", "H_m", "n_vessels"}


def test_freeze_mass_iteration_input_fields():
    """MassIterationInput 字段冻结（9 字段）。"""
    from dataclasses import fields

    field_names = {f.name for f in fields(MassIterationInput)}
    assert field_names == {
        "target_mass_kg",
        "rho_L_kg_m3",
        "rho_V_kg_m3",
        "vessel_shape",
        "head_type",
        "initial_D_m",
        "initial_L_m",
        "variable",
        "mass_model",
    }
    # 默认值校验
    defaults = {f.name: f.default for f in fields(MassIterationInput)}
    assert defaults["initial_D_m"] == 1.0
    assert defaults["initial_L_m"] == 3.0
    assert defaults["variable"] == "D"
    assert defaults["mass_model"] == "OPERATING"


def test_freeze_result_dataclass_fields():
    """Result dataclass 字段冻结（V1.2 接口冻结）。"""
    from dataclasses import fields

    # PartialVolumeResult
    pv_out = {f.name for f in fields(PartialVolumeResult)}
    assert pv_out == {
        "partial_volume_m3",
        "total_volume_m3",
        "head_volume_m3",
        "cylinder_volume_m3",
        "formula_ref",
    }

    # WettedAreaResult
    wa_out = {f.name for f in fields(WettedAreaResult)}
    assert wa_out == {
        "wetted_area_m2",
        "total_wetted_area_m2",
        "head_area_m2",
        "cylinder_area_m2",
        "formula_ref",
    }

    # MassIterationResult
    mi_out = {f.name for f in fields(MassIterationResult)}
    assert mi_out == {
        "converged",
        "iterations",
        "final_variable_m",
        "final_mass_kg",
        "residual_kg",
        "formula_ref",
    }


# ============================================================================
# 3. 异常类型冻结（V1.2 接口冻结）
# ============================================================================


def test_freeze_exception_classes_exist():
    """冻结异常类型：VesselInputError (422) + MassIterationNotConvergedError (422)。"""
    assert VesselInputError.code == "VESSEL_INPUT_ERROR"
    assert VesselInputError.status == 422
    assert MassIterationNotConvergedError.code == "MASS_ITERATION_NOT_CONVERGED"
    assert MassIterationNotConvergedError.status == 422


# ============================================================================
# 4. 行为快照（基础 smoke：调用不抛 + 返回类型正确）
# ============================================================================


def test_freeze_calc_partial_volume_runs():
    """calc_partial_volume 仍能正常调用（行为冻结）。"""
    inp = PartialVolumeInput(
        D_m=1.8, L_m=4.5, head_type="2:1_ELLIPTICAL", H_m=0.45
    )
    result = calc_partial_volume(inp)
    assert isinstance(result, PartialVolumeResult)
    assert result.partial_volume_m3 > 0


def test_freeze_calc_wetted_area_runs():
    """calc_wetted_area 仍能正常调用。"""
    inp = WettedAreaInput(
        D_m=1.8, L_m=4.5, head_type="2:1_ELLIPTICAL", H_m=0.45
    )
    result = calc_wetted_area(inp)
    assert isinstance(result, WettedAreaResult)
    assert result.wetted_area_m2 > 0


def test_freeze_mass_iteration_loop_runs():
    """mass_iteration_loop 仍能正常调用。"""
    inp = MassIterationInput(
        target_mass_kg=5774.0,
        rho_L_kg_m3=1000.0,
        rho_V_kg_m3=1.2,
        vessel_shape="VERTICAL",
        head_type="2:1_ELLIPTICAL",
        initial_D_m=1.5,
        initial_L_m=5.0,
        variable="D",
    )
    result = mass_iteration_loop(inp)
    assert isinstance(result, MassIterationResult)
    assert result.converged


# ============================================================================
# 5. 公共模块导出冻结（vessel_service __init__ 暴露的符号）
# ============================================================================


def test_freeze_vessel_service_public_symbols():
    """vessel_service 公共符号冻结（被 freeze 部分）。"""
    from app.services import vessel

    expected_symbols = {
        "VesselInputError",
        "MassIterationNotConvergedError",
        "PartialVolumeInput",
        "PartialVolumeResult",
        "WettedAreaInput",
        "WettedAreaResult",
        "calc_partial_volume",
        "calc_wetted_area",
        "mass_iteration_loop",
        # 既有符号（P5-1-1/2 冻结前已存在，本测试不强制但确认未移除）
        "calc_vessel_sizing",
        "calc_vessel_hydraulics",
        "VesselSizingInput",
        "VesselSizingResult",
        "VesselHydraulicsInput",
        "VesselHydraulicsResult",
    }
    for sym in expected_symbols:
        assert hasattr(vessel, sym), f"vessel.{sym} 缺失（D7 接口冻结保护）"