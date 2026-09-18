"""P5-0-7 Task 26: ChEDL 包装层测试（ADR-0030 V1.1 决策 6/9 + V1.9 GSTACK P0/P2）。

7 包装函数：5 函数直调 fluids 顶层 + 2 函数 fallback（time_to_empty / tank_level_to_volume
在 fluids 1.3.1 不存在 → 自研几何 + 伯努利 + 孔口出流）。

provenance 接口：get_chedl_provenance() 返回 {func_name: ChEDLProvenance}，7 项齐全；
每项含 chEDL_function / chEDL_version / known_limitations / fallback_available /
fallback_formula_ref。
ChEDL 版本与 Task 25 锁定一致（fluids==1.3.1）。

与已有 chedl 集成的关联：
- Task 5（VESSEL）/ Task 6（SEP_EQUIP）/ Task 11（HEAT）实施时，调 chedl_wrapper.* 而非
  fluids.*（裁决 #8 + V1.8 F-13-2）；本测试是契约门禁。
"""
from __future__ import annotations

import math

import pytest

from app.services import chedl_wrapper
from app.services.chedl_provenance import ChEDLProvenance

# ============================================================================
# 5 直调函数（fluids 1.3.1 顶层）
# ============================================================================


def test_v_Souders_Brown_known_value():
    """v_Souders_Brown 烟雾速度：经典工况 K=0.1 ft/s、rhol=1000、rhog=1.2。

    API 521 / GPSA 数据手册参考：典型 K=0.1 ft/s → 速度量级 ~0.1 m/s 量级。
    函数签名：v_Souders_Brown(K, rhol, rhog) → m/s。
    """
    result = chedl_wrapper.v_Souders_Brown(K=0.1, rhol=1000.0, rhog=1.2)
    # 返回值应 > 0 且量级合理
    assert isinstance(result, float)
    assert result > 0.0
    # 量级校验（K=0.1 时典型结果约 0.05 ~ 0.5 m/s）
    assert 0.01 < result < 5.0


def test_K_separator_Watkins_known_value():
    """K_separator_Watkins：Watkins 法重力分离 K 值。

    典型工况 x=0.1 m、rhol=850、rhog=1.2 → K 量级 0.05 ~ 0.5 m/s。
    """
    result = chedl_wrapper.K_separator_Watkins(x=0.1, rhol=850.0, rhog=1.2)
    assert isinstance(result, float)
    assert result > 0.0
    assert 0.01 < result < 1.0


def test_K_separator_demister_York_known_value():
    """K_separator_demister_York：York 除雾器 K 值（基于压力 P）。

    典型工况 P=101325 Pa（大气压） → K 量级 0.05 ~ 0.2 m/s。
    """
    result = chedl_wrapper.K_separator_demister_York(P=101325.0)
    assert isinstance(result, float)
    assert result > 0.0
    assert 0.01 < result < 1.0


def test_v_terminal_known_value():
    """v_terminal：终端沉降速度（Stokes 定律 / 通用算法）。

    典型工况 D=100e-6 m（100 μm 颗粒）、rhop=2500、rho=1000、mu=0.001 → 量级 1e-3 m/s。
    """
    result = chedl_wrapper.v_terminal(
        D=100e-6, rhop=2500.0, rho=1000.0, mu=0.001
    )
    assert isinstance(result, float)
    assert result > 0.0
    # 量级合理（典型 1e-5 ~ 1e-1 m/s）
    assert 1e-6 < result < 1.0


def test_API520_round_size_known_value():
    """API520_round_size：API 520 阀门口径圆整。

    面积输入 → 返回圆整到标准口径。
    """
    result = chedl_wrapper.API520_round_size(A=0.001)  # 1 cm² 量级
    assert isinstance(result, float)
    assert result >= 0.0
    # 圆整后应不小于原值（向上圆整）或等于
    assert result >= 0.001


# ============================================================================
# 2 Fallback 函数（fluids 1.3.1 不存在 → 自研）
# ============================================================================


def test_time_to_empty_fallback_path():
    """time_to_empty：fluids 1.3.1 不存在 → 触发 fallback（伯努利 + 孔口出流）。

    fallback 实现：圆柱容器 + 圆孔口 + 孔口系数 Cd=0.62。
    公式：Q = Cd · A · √(2·g·h)，积分得 t = (A_tank / (Cd · A_orifice)) · √(2·h₀/g)。

    典型工况：D_tank=2 m, h₀=2 m, d_orifice=0.05 m → 量级 100~1000 s（合理）。
    """
    # 调用包装层（不直接调 fluids），参数语义：直径/初始液位/孔口直径/Cd
    result = chedl_wrapper.time_to_empty(
        D_tank=2.0, h0=2.0, d_orifice=0.05, Cd=0.62
    )
    assert isinstance(result, float)
    assert result > 0.0
    assert math.isfinite(result)
    # 量级合理：~1e2 ~ 1e4 s
    assert 10.0 < result < 100000.0


def test_tank_level_to_volume_fallback_path():
    """tank_level_to_volume：fluids 1.3.1 不存在 → 触发 fallback（圆柱几何 + 椭圆封头）。

    典型工况：D=2 m, h=1 m → V = π · r² · h = π · 1 · 1 ≈ 3.14 m³（无封头）。
    """
    result = chedl_wrapper.tank_level_to_volume(D=2.0, h=1.0, head_type="ellipse")
    assert isinstance(result, float)
    assert result > 0.0
    # 圆柱段 π·r²·h ≈ 3.14 m³（椭圆封头为圆柱段的修正，本测试无封头段 → 近似 3.14）
    assert 2.5 < result < 4.0


# ============================================================================
# provenance 接口
# ============================================================================


def test_get_chedl_provenance_returns_17_entries():
    """get_chedl_provenance() 必须返回 17 项（5 直调 + 2 fallback + 6 Task 3 + 4 Task 4）。

    P6-0 Task 3 扩展：原 7 项 → 13 项，新增 6 项 CV/RESTRICTION 函数。
    P6-0 Task 4 扩展：13 项 → 17 项，新增 4 项 OPEN_CHANNEL 函数（Manning×2 + 临界水深 + 水跃）。
    """
    prov = chedl_wrapper.get_chedl_provenance()
    assert isinstance(prov, dict)
    assert len(prov) == 17, (
        f"provenance 应有 17 项，实际 {len(prov)}: {list(prov.keys())}"
    )


def test_get_chedl_provenance_contains_all_functions():
    """provenance 字典键必须含全部 17 包装函数名。"""
    prov = chedl_wrapper.get_chedl_provenance()
    expected = {
        # 既有 7 项
        "v_Souders_Brown",
        "K_separator_Watkins",
        "K_separator_demister_York",
        "v_terminal",
        "API520_round_size",
        "time_to_empty",
        "tank_level_to_volume",
        # P6-0 6 项（Task 3）
        "control_valve_C_liquid",
        "control_valve_kv_liquid",
        "control_valve_cv_gas",
        "flow_meter_orifice",
        "flow_meter_venturi",
        "flow_meter_nozzle",
        # P6-0 4 项（Task 4）
        "manning_Q",
        "manning_V",
        "critical_depth_rectangular",
        "hydraulic_jump_y2",
    }
    assert set(prov.keys()) == expected, (
        f"provenance 键不匹配。缺失: {expected - set(prov.keys())}，"
        f"多余: {set(prov.keys()) - expected}"
    )


def test_get_chedl_provenance_version_matches_locked():
    """provenance 中的 ChEDL 版本必须与 Task 25 锁定一致（fluids==1.3.1）。"""
    prov = chedl_wrapper.get_chedl_provenance()
    for name, meta in prov.items():
        assert isinstance(meta, ChEDLProvenance), (
            f"{name} 应为 ChEDLProvenance 实例，实际 {type(meta)}"
        )
        assert meta.chEDL_version == "1.3.1", (
            f"{name} chEDL_version={meta.chEDL_version!r} != 锁定 '1.3.1'"
        )


def test_fallback_provenance_metadata():
    """2 fallback 函数的 provenance 必须显式标注 fallback_available=True + fallback_formula_ref。"""
    prov = chedl_wrapper.get_chedl_provenance()
    for fn_name in ("time_to_empty", "tank_level_to_volume"):
        meta = prov[fn_name]
        assert meta.fallback_available is True, (
            f"{fn_name} fallback_available 应为 True（fluids 1.3.1 缺该函数）"
        )
        assert meta.fallback_formula_ref, (
            f"{fn_name} fallback_formula_ref 必须非空（fallback 实现追溯）"
        )
        assert meta.known_limitations, (
            f"{fn_name} known_limitations 必须列出（用户决策依据）"
        )


def test_direct_provenance_metadata():
    """5 直调函数的 provenance：fallback_available=False + chEDL_function 指向 fluids 函数。"""
    prov = chedl_wrapper.get_chedl_provenance()
    for fn_name in (
        "v_Souders_Brown",
        "K_separator_Watkins",
        "K_separator_demister_York",
        "v_terminal",
        "API520_round_size",
    ):
        meta = prov[fn_name]
        assert meta.fallback_available is False, (
            f"{fn_name} fallback_available 应为 False（直调 fluids）"
        )
        assert meta.fallback_formula_ref is None, (
            f"{fn_name} fallback_formula_ref 应为 None"
        )
        # chEDL_function 应指向 fluids 包
        assert meta.chEDL_function.startswith("fluids."), (
            f"{fn_name} chEDL_function 应指向 fluids，实际 {meta.chEDL_function!r}"
        )


def test_known_limitations_present_all_entries():
    """provenance 中 7 项必须有 known_limitations（空 list 算 None 不可接受 → 测试用 truthy）。"""
    prov = chedl_wrapper.get_chedl_provenance()
    for name, meta in prov.items():
        assert isinstance(meta.known_limitations, list), (
            f"{name} known_limitations 应为 list，实际 {type(meta.known_limitations)}"
        )
        assert len(meta.known_limitations) >= 1, (
            f"{name} known_limitations 应至少 1 项（哪怕 'V1.8 F-13-5' 这种最小声明）"
        )


def test_provenance_runtime_version_matches():
    """provenance 中的 chEDL_version 应与运行时 fluids.__version__ 一致（双证据链）。"""
    import fluids

    prov = chedl_wrapper.get_chedl_provenance()
    for name, meta in prov.items():
        assert meta.chEDL_version == fluids.__version__, (
            f"{name} provenance version {meta.chEDL_version} != 运行时 {fluids.__version__}"
        )


# ============================================================================
# 包装层结构契约
# ============================================================================


def test_chedl_wrapper_module_exports_all_7():
    """chedl_wrapper 模块必须暴露全部 7 包装函数 + get_chedl_provenance。"""
    import app.services.chedl_wrapper as cw

    required_funcs = [
        "v_Souders_Brown",
        "K_separator_Watkins",
        "K_separator_demister_York",
        "v_terminal",
        "API520_round_size",
        "time_to_empty",
        "tank_level_to_volume",
        "get_chedl_provenance",
    ]
    for fn_name in required_funcs:
        assert hasattr(cw, fn_name), f"chedl_wrapper 缺 {fn_name}"
        assert callable(getattr(cw, fn_name)), f"chedl_wrapper.{fn_name} 不可调用"


def test_chedl_provenance_module_exports_dataclass():
    """chedl_provenance 模块必须暴露 ChEDLProvenance 数据类。"""
    from app.services import chedl_provenance

    assert hasattr(chedl_provenance, "ChEDLProvenance")
    assert hasattr(chedl_provenance.ChEDLProvenance, "__dataclass_fields__"), (
        "ChEDLProvenance 必须是 @dataclass"
    )


def test_chedl_provenance_dataclass_fields():
    """ChEDLProvenance 必须含 5 字段（function/version/limitations/available/ref）。"""
    from dataclasses import fields

    field_names = {f.name for f in fields(ChEDLProvenance)}
    expected = {
        "chEDL_function",
        "chEDL_version",
        "known_limitations",
        "fallback_available",
        "fallback_formula_ref",
    }
    assert field_names == expected, (
        f"ChEDLProvenance 字段不匹配。缺失: {expected - field_names}，"
        f"多余: {field_names - expected}"
    )


def test_chedl_provenance_frozen():
    """ChEDLProvenance 必须是 frozen dataclass（不可变，provenance 是历史快照）。"""
    from dataclasses import FrozenInstanceError

    meta = ChEDLProvenance(
        chEDL_function="fluids.separator.v_Souders_Brown",
        chEDL_version="1.3.1",
        known_limitations=["test"],
        fallback_available=False,
        fallback_formula_ref=None,
    )
    with pytest.raises(FrozenInstanceError):
        meta.chEDL_version = "9.9.9"  # type: ignore[misc]


# ============================================================================
# P5-1-1 包装扩展（PCS-PLAN §129）
# ============================================================================


def test_K_Souders_Brown_theoretical_exists_in_chedl_and_wrapper():
    """PCS-PLAN §129 要求 K_Souders_Brown_theoretical 包装就绪（P5-1-1 前置）。

    ChEDL fluids.separator 必须原生存在此函数 + chedl_wrapper 必须已包装。
    包装函数用于 P5-2+ 旋风分离器 / 高效分离设备理论 K 因子上限计算。
    """
    import fluids.separator

    from app.services import chedl_wrapper

    assert hasattr(fluids.separator, "K_Souders_Brown_theoretical"), (
        "ChEDL fluids.separator 缺 K_Souders_Brown_theoretical（ChEDL 版本不匹配）"
    )
    assert hasattr(chedl_wrapper, "K_Souders_Brown_theoretical"), (
        "包装层 chedl_wrapper 缺 K_Souders_Brown_theoretical（PCS-PLAN §129 未落地）"
    )
    assert callable(chedl_wrapper.K_Souders_Brown_theoretical), (
        "chedl_wrapper.K_Souders_Brown_theoretical 不可调用"
    )
    assert "K_Souders_Brown_theoretical" in chedl_wrapper.__all__, (
        "K_Souders_Brown_theoretical 未加入 chedl_wrapper.__all__"
    )


# ============================================================================
# P6-0 Task 3：CV/RESTRICTION 6 函数（Path A：SPEC §3.2.1/3.2.2 简化公式）
# ============================================================================
#
# 设计依据：
# - R1 ledger 裁决：Path A 自研（不调 fluids 完整 API）
# - SPEC §3.2.1 line 149（液体 Cv 简化）+ §3.2.1.3 line 1058-1080（气体 Cv 含 Y 修正）
# - SPEC §3.2.2.1 line 1382-1397（孔板 Reader-Harris 3 项截断）
# - SPEC §3.2.2.3 line 1495-1511（ISA 1932 喷嘴完整公式）
# - SPEC §3.2.2.2 line 1461（文丘里 C 范围中值）
#
# 验收：6 函数结果与 SPEC 公式手算值一致（rel <1e-9）。


def test_control_valve_C_liquid_spec_formula():
    """control_valve_C_liquid：SPEC §3.2.1 line 149 简化公式 Cv = Q·√(SG/ΔP)。

    手算验证：Q=100, SG=1, ΔP=1 → Cv = 100·√1 = 100。
    边界：Q=100, SG=0.8, ΔP=2.5 → Cv = 100·√(0.8/2.5) = 100·√0.32 = 56.5685。
    """
    # 标准工况（SG=1, ΔP=1 bar）
    Cv_standard = chedl_wrapper.control_valve_C_liquid(Q_m3h=100.0, SG=1.0, dP_bar=1.0)
    assert Cv_standard == pytest.approx(100.0, rel=1e-9), (
        f"标准工况 Cv 应为 100.0，实际 {Cv_standard}"
    )
    # 介质工况（SG=0.8, ΔP=2.5 bar）
    Cv_heavy = chedl_wrapper.control_valve_C_liquid(
        Q_m3h=100.0, SG=0.8, dP_bar=2.5
    )
    expected_heavy = 100.0 * math.sqrt(0.8 / 2.5)
    assert Cv_heavy == pytest.approx(expected_heavy, rel=1e-9), (
        f"介质工况 Cv 应为 {expected_heavy}，实际 {Cv_heavy}"
    )


def test_control_valve_kv_liquid_spec_formula():
    """control_valve_kv_liquid：SI Kv 简化公式 Kv = Q·√(ρ/(1000·ΔP))。

    手算验证（水 Q=100, ρ=1000, ΔP=1 bar）：Kv = 100·√(1000/1000) = 100。
    边界（ρ=800, ΔP=2 bar）：Kv = 100·√(800/2000) = 100·√0.4 = 63.2456。
    """
    # 标准工况（水）
    Kv_water = chedl_wrapper.control_valve_kv_liquid(
        Q_m3h=100.0, rho=1000.0, dP_bar=1.0
    )
    assert Kv_water == pytest.approx(100.0, rel=1e-9), (
        f"水工况 Kv 应为 100.0，实际 {Kv_water}"
    )
    # 介质工况（轻质油 ρ=800）
    Kv_oil = chedl_wrapper.control_valve_kv_liquid(
        Q_m3h=100.0, rho=800.0, dP_bar=2.0
    )
    expected_oil = 100.0 * math.sqrt(800.0 / (1000.0 * 2.0))
    assert Kv_oil == pytest.approx(expected_oil, rel=1e-9), (
        f"轻油工况 Kv 应为 {expected_oil}，实际 {Kv_oil}"
    )


def test_control_valve_cv_gas_spec_formula_with_Y_correction():
    """control_valve_cv_gas：SPEC §3.2.1.3 IEC 60534-2-1 §6.3 完整公式。

    测试工况：空气 M=29, Q=100 Nm³/h, P1=10 bar, T1=300 K, Z=1, ΔP=1 bar,
    γ=1.4, xT=0.7。
    手算：
        x = 0.1/1.0 = 0.1
        F_γ = 1.4/1.4 = 1.0
        Y = 1 - 0.1/(3·1.0·0.7) = 1 - 0.04762 = 0.95238
        Cv = 100 / (0.0865·1·10·0.95238·√(0.1/(29·300·1)))
    """
    Cv_gas = chedl_wrapper.control_valve_cv_gas(
        Q_Nm3h=100.0,
        P1_pa=10.0 * 1e5,
        T1_k=300.0,
        M=29.0,
        Z=1.0,
        dP_pa=1.0 * 1e5,
        gamma=1.4,
        xT=0.7,
    )
    # 手算预期值
    x = 0.1
    F_gamma = 1.4 / 1.4
    Y = 1.0 - x / (3.0 * F_gamma * 0.7)
    expected_Cv = 100.0 / (
        0.0865 * 1.0 * 10.0 * Y * math.sqrt(x / (29.0 * 300.0 * 1.0))
    )
    assert Cv_gas == pytest.approx(expected_Cv, rel=1e-9), (
        f"气体 Cv 应为 {expected_Cv}，实际 {Cv_gas}"
    )
    # Y 修正一致性验证：Y 应严格等于 0.95238
    assert Y == pytest.approx(0.95238, rel=1e-4), (
        f"Y 修正系数应约 0.95238，实际 {Y}"
    )


def test_flow_meter_orifice_spec_reader_harris_3term():
    """flow_meter_orifice：SPEC §3.2.2.1 Reader-Harris 3 项截断公式。

    测试工况：D=0.1 m, d=0.05 m（β=0.5）, Re_D=1e6, P1=1 bar, ΔP=0.05 bar。
    手算（β=0.5）：
        β²=0.25, β⁴=0.0625, β⁸=0.00390625
        C = 0.5961 + 0.0261·0.25 - 0.216·0.00390625
          + 0.000521·(10⁶·0.5/1e6)^0.7
          = 0.5961 + 0.006525 - 0.00084375 + 0.000521·0.5^0.7
          = 0.601781 + 0.000521·0.61557
          ≈ 0.602102
    """
    C, epsilon = chedl_wrapper.flow_meter_orifice(
        D_m=0.1,
        d_m=0.05,
        Re_D=1.0e6,
        P1_pa=1.0e5,
        dP_pa=0.05 * 1.0e5,
        rho1=1.2,
    )
    # 手算 C
    beta = 0.5
    beta2 = 0.25
    beta4 = 0.0625
    beta8 = 0.00390625
    expected_C = (
        0.5961
        + 0.0261 * beta2
        - 0.216 * beta8
        + 0.000521 * (1.0e6 * beta / 1.0e6) ** 0.7
    )
    # 手算 ε（κ=1.4 简化）
    x = 0.05  # ΔP/P1 = 0.05
    expected_epsilon = 1.0 - (0.351 + 0.256 * beta4 + 0.93 * beta8) * x
    assert C == pytest.approx(expected_C, rel=1e-9), (
        f"Orifice C 应为 {expected_C}，实际 {C}"
    )
    assert epsilon == pytest.approx(expected_epsilon, rel=1e-9), (
        f"Orifice ε 应为 {expected_epsilon}，实际 {epsilon}"
    )
    # 物理意义校验：β=0.5 典型 C ≈ 0.6，ε ≈ 0.97（5% 压差）
    assert 0.55 < C < 0.65
    assert 0.9 < epsilon < 1.0


def test_flow_meter_venturi_spec_c_range_midpoint():
    """flow_meter_venturi：SPEC §3.2.2.2 文丘里 C 取范围中值 0.99。

    测试工况：D=0.1, d=0.06（β=0.6）, Re_D=2e6, P1=2 bar, ΔP=0.1 bar。
    验证：
        C = 0.99（铸造标准值）
        ε = 1 - (0.65·β⁶ + 0.002)·x, 其中 x=0.05
    """
    C, epsilon = chedl_wrapper.flow_meter_venturi(
        D_m=0.1,
        d_m=0.06,
        Re_D=2.0e6,
        P1_pa=2.0e5,
        dP_pa=0.1 * 1.0e5,
        rho1=5.0,
    )
    assert C == pytest.approx(0.99, rel=1e-9), (
        f"Venturi C 应为 0.99（SPEC 范围中值），实际 {C}"
    )
    # 手算 ε
    beta = 0.6
    x = 0.1 / 2.0  # = 0.05
    expected_epsilon = 1.0 - (0.65 * beta ** 6 + 0.002) * x
    assert epsilon == pytest.approx(expected_epsilon, rel=1e-9), (
        f"Venturi ε 应为 {expected_epsilon}，实际 {epsilon}"
    )


def test_flow_meter_nozzle_spec_isa_1932_full_formula():
    """flow_meter_nozzle：SPEC §3.2.2.3 ISA 1932 喷嘴完整公式。

    测试工况：D=0.1 m, d=0.05 m（β=0.5）, Re_D=1e6, P1=1 bar, ΔP=0.05 bar。
    手算：
        β²=0.25, β^4.1, β^4.15
        C = 0.9900 - 0.2262·0.5^4.1 - (0.00175·0.25 - 0.0033·0.5^4.15)·(10⁶/1e6)^1.15
          = 0.9900 - 0.2262·0.05809 - (0.0004375 - 0.0033·0.05590)·1.0
          = 0.9900 - 0.01314 - 0.0004375 + 0.0033·0.05590
          ≈ 0.97643
    """
    C, epsilon = chedl_wrapper.flow_meter_nozzle(
        D_m=0.1,
        d_m=0.05,
        Re_D=1.0e6,
        P1_pa=1.0e5,
        dP_pa=0.05 * 1.0e5,
        rho1=1.2,
    )
    # 手算 C（ISA 1932 完整）
    beta = 0.5
    beta2 = 0.25
    expected_C = (
        0.9900
        - 0.2262 * (beta ** 4.1)
        - (0.00175 * beta2 - 0.0033 * (beta ** 4.15))
        * (1.0e6 / 1.0e6) ** 1.15
    )
    # 手算 ε（ISO 5167-3 κ=1.4 简化）
    beta4 = 0.5 ** 4
    beta8 = 0.5 ** 8
    x = 0.05
    expected_epsilon = 1.0 - (0.7 * beta4 - 0.3 * beta8) * x
    assert C == pytest.approx(expected_C, rel=1e-9), (
        f"Nozzle C 应为 {expected_C}，实际 {C}"
    )
    assert epsilon == pytest.approx(expected_epsilon, rel=1e-9), (
        f"Nozzle ε 应为 {expected_epsilon}，实际 {epsilon}"
    )
    # 物理意义校验：ISA 1932 典型 C ≈ 0.95~0.99
    assert 0.9 < C < 1.0


# ============================================================================
# P6-0 provenance 接口扩展
# ============================================================================


def test_get_chedl_provenance_contains_p6_0_six_functions():
    """provenance 字典键必须含全部 6 个 P6-0 新增函数名。"""
    prov = chedl_wrapper.get_chedl_provenance()
    expected_p6_0 = {
        "control_valve_C_liquid",
        "control_valve_kv_liquid",
        "control_valve_cv_gas",
        "flow_meter_orifice",
        "flow_meter_venturi",
        "flow_meter_nozzle",
    }
    assert expected_p6_0.issubset(set(prov.keys())), (
        f"provenance 缺 P6-0 函数：{expected_p6_0 - set(prov.keys())}"
    )


def test_p6_0_provenance_fallback_metadata():
    """P6-0 6 函数 provenance 必须显式标注 fallback_available=True + fallback_formula_ref。

    Path A 设计决策：fluids 完整 API 不匹配 brief 简化签名，自研实现依赖 SPEC 简化公式。
    """
    prov = chedl_wrapper.get_chedl_provenance()
    for fn_name in (
        "control_valve_C_liquid",
        "control_valve_kv_liquid",
        "control_valve_cv_gas",
        "flow_meter_orifice",
        "flow_meter_venturi",
        "flow_meter_nozzle",
    ):
        meta = prov[fn_name]
        assert meta.fallback_available is True, (
            f"{fn_name} fallback_available 应为 True（Path A 自研）"
        )
        assert meta.fallback_formula_ref, (
            f"{fn_name} fallback_formula_ref 必须非空（SPEC § 公式追溯）"
        )
        assert meta.fallback_formula_ref.startswith("spec_p6_"), (
            f"{fn_name} fallback_formula_ref 应以 'spec_p6_' 开头，"
            f"实际 {meta.fallback_formula_ref!r}"
        )
        assert meta.known_limitations, (
            f"{fn_name} known_limitations 必须列出（Path A 决策依据）"
        )


def test_chedl_wrapper_module_exports_all_13():
    """chedl_wrapper 模块必须暴露全部 13 包装函数 + get_chedl_provenance。"""
    import app.services.chedl_wrapper as cw

    required_funcs = [
        # 既有 7 项
        "v_Souders_Brown",
        "K_separator_Watkins",
        "K_separator_demister_York",
        "K_Souders_Brown_theoretical",
        "v_terminal",
        "API520_round_size",
        "time_to_empty",
        "tank_level_to_volume",
        # P6-0 6 项
        "control_valve_C_liquid",
        "control_valve_kv_liquid",
        "control_valve_cv_gas",
        "flow_meter_orifice",
        "flow_meter_venturi",
        "flow_meter_nozzle",
        "get_chedl_provenance",
    ]
    for fn_name in required_funcs:
        assert hasattr(cw, fn_name), f"chedl_wrapper 缺 {fn_name}"
        assert callable(getattr(cw, fn_name)), f"chedl_wrapper.{fn_name} 不可调用"


# ============================================================================
# P6-0 参数校验（防御性编程）
# ============================================================================


def test_control_valve_C_liquid_rejects_invalid_dP():
    """control_valve_C_liquid 必须拒绝非正 ΔP（物理意义：零压差无穷大 Cv）。"""
    with pytest.raises(ValueError, match="参数必须正数"):
        chedl_wrapper.control_valve_C_liquid(Q_m3h=100.0, SG=1.0, dP_bar=0.0)
    with pytest.raises(ValueError, match="参数必须正数"):
        chedl_wrapper.control_valve_C_liquid(Q_m3h=100.0, SG=1.0, dP_bar=-1.0)


def test_flow_meter_orifice_rejects_d_ge_D():
    """flow_meter_orifice 必须拒绝 d ≥ D（β 范围 [0, 1]）。"""
    with pytest.raises(ValueError, match="参数异常"):
        chedl_wrapper.flow_meter_orifice(
            D_m=0.1, d_m=0.1, Re_D=1e6, P1_pa=1e5, dP_pa=1e3, rho1=1.0
        )
    with pytest.raises(ValueError, match="参数异常"):
        chedl_wrapper.flow_meter_orifice(
            D_m=0.1, d_m=0.2, Re_D=1e6, P1_pa=1e5, dP_pa=1e3, rho1=1.0
        )


def test_control_valve_cv_gas_rejects_choked_negative_Y():
    """control_valve_cv_gas 在 Y ≤ 0 时（极端压差比）必须报错而非返回 NaN。"""
    # x = 0.5 (ΔP/P1), F_γ=1.0, xT=0.7 → Y = 1 - 0.5/(3·1·0.7) = 1 - 0.238 = 0.762 > 0
    # 触发 Y ≤ 0：xT 极小，x = 0.9 → Y = 1 - 0.9/(3·1·0.1) = 1 - 3 = -2
    with pytest.raises(ValueError, match="Y 计算出非正值"):
        chedl_wrapper.control_valve_cv_gas(
            Q_Nm3h=100.0,
            P1_pa=10.0e5,
            T1_k=300.0,
            M=29.0,
            Z=1.0,
            dP_pa=9.0e5,  # x=0.9
            gamma=1.4,
            xT=0.1,  # 极端小 xT
        )


# ============================================================================
# P6-0 Task 4：OPEN_CHANNEL 4 函数（Path A：SPEC §3.2.6 教科书简化公式）
# ============================================================================
#
# 设计依据：
# - R1 ledger 裁决：Path A 自研（不调 fluids.open_flow，brief 工程单位签名不匹配）
# - SPEC §3.2.6 line 256-279：OPEN_CHANNEL 明渠流（Manning 公式、临界水深、水跃计算）
# - P6-OPEN-001 决策：fluids.open_channel 缺失 4/5 函数，自研兜底（ADR-0030 决策 7 模式）
# - 教科书公式：
#     manning_Q(n, A, Rh, S) = (1/n) · A · Rh^(2/3) · S^(1/2)
#     manning_V(n, Rh, S) = (1/n) · Rh^(2/3) · S^(1/2)
#     critical_depth_rectangular(Q, b) = (Q²/(g·b²))^(1/3)   [矩形断面 y_c = (q²/g)^(1/3)]
#     hydraulic_jump_y2(y1, Fr1) = y1 · 0.5·(√(1+8·Fr1²) - 1)   [共轭水深 Bélanger 方程]
#
# 验收：4 函数结果与教科书公式手算值一致（rel <1e-9）。


def test_manning_Q_spec_formula():
    """manning_Q：SPEC §3.2.6 Manning 流量 Q = (1/n)·A·Rh^(2/3)·S^(1/2)。

    手算验证（典型混凝土渠道）：
        n=0.013, A=2 m², Rh=1 m, S=0.001
        Q = (1/0.013)·2·1·0.001^0.5 = 76.923·2·1·0.03162 ≈ 4.8661 m³/s
    边界（n=0.025 天然土渠）：
        n=0.025, A=2, Rh=1, S=0.001
        Q = 40·2·1·0.03162 = 2.5298 m³/s
    """
    # 标准工况（混凝土 n=0.013）
    Q_concrete = chedl_wrapper.manning_Q(n=0.013, A_m2=2.0, Rh_m=1.0, S=0.001)
    expected_concrete = (1.0 / 0.013) * 2.0 * (1.0 ** (2.0 / 3.0)) * math.sqrt(0.001)
    assert Q_concrete == pytest.approx(expected_concrete, rel=1e-9), (
        f"混凝土渠道 Q 应为 {expected_concrete}，实际 {Q_concrete}"
    )
    # 量级合理（2 m², Rh=1m, S=0.001 典型数 m³/s 量级）
    assert 4.0 < Q_concrete < 5.0

    # 介质工况（天然土渠 n=0.025）—— 糙率大流量小
    Q_earth = chedl_wrapper.manning_Q(n=0.025, A_m2=2.0, Rh_m=1.0, S=0.001)
    expected_earth = (1.0 / 0.025) * 2.0 * (1.0 ** (2.0 / 3.0)) * math.sqrt(0.001)
    assert Q_earth == pytest.approx(expected_earth, rel=1e-9), (
        f"土渠 Q 应为 {expected_earth}，实际 {Q_earth}"
    )
    # n 增大 → Q 减小（物理意义：糙率大流阻大）
    assert Q_earth < Q_concrete


def test_manning_V_spec_formula():
    """manning_V：SPEC §3.2.6 Manning 流速 V = (1/n)·Rh^(2/3)·S^(1/2)。

    手算验证：
        n=0.013, Rh=1 m, S=0.001
        V = (1/0.013)·1·0.001^0.5 = 76.923·0.03162 ≈ 2.4331 m/s
    """
    V_concrete = chedl_wrapper.manning_V(n=0.013, Rh_m=1.0, S=0.001)
    expected_V = (1.0 / 0.013) * (1.0 ** (2.0 / 3.0)) * math.sqrt(0.001)
    assert V_concrete == pytest.approx(expected_V, rel=1e-9), (
        f"混凝土 V 应为 {expected_V}，实际 {V_concrete}"
    )
    # 物理意义校验：V = Q/A = 4.8661/2 = 2.4331 m/s
    Q_concrete = chedl_wrapper.manning_Q(n=0.013, A_m2=2.0, Rh_m=1.0, S=0.001)
    assert V_concrete == pytest.approx(Q_concrete / 2.0, rel=1e-9), (
        f"V 应等于 Q/A，实际 V={V_concrete} vs Q/A={Q_concrete / 2.0}"
    )


def test_critical_depth_rectangular_spec_formula():
    """critical_depth_rectangular：矩形渠临界水深 y_c = (Q²/(g·b²))^(1/3)。

    手算验证：
        Q=1 m³/s, b=2 m, g=9.80665
        y_c = (1²/(9.80665·4))^(1/3) = (0.02548)^(1/3) ≈ 0.2937 m
    """
    # 单宽流量 q = Q/b = 0.5 m²/s
    y_c = chedl_wrapper.critical_depth_rectangular(Q_m3s=1.0, b_m=2.0)
    g = 9.80665
    expected_y_c = ((1.0 ** 2) / (g * (2.0 ** 2))) ** (1.0 / 3.0)
    assert y_c == pytest.approx(expected_y_c, rel=1e-9), (
        f"矩形 y_c 应为 {expected_y_c}，实际 {y_c}"
    )
    # 量级合理（q=0.5 m²/s 时 y_c ≈ 0.29 m）
    assert 0.28 < y_c < 0.30

    # 边界工况：流量翻倍 → y_c 增长 (2)^(2/3) ≈ 1.587 倍
    y_c_2Q = chedl_wrapper.critical_depth_rectangular(Q_m3s=2.0, b_m=2.0)
    ratio = y_c_2Q / y_c
    assert ratio == pytest.approx(2.0 ** (2.0 / 3.0), rel=1e-9), (
        f"y_c 与 Q^(2/3) 成正比，实际 ratio={ratio}"
    )


def test_hydraulic_jump_y2_spec_formula():
    """hydraulic_jump_y2：共轭水深 y2 = y1·0.5·(√(1+8·Fr1²) - 1)。

    Bélanger 方程（矩形断面水跃共轭水深）。

    手算验证：
        y1=0.5 m, Fr1=2.5
        Fr1²=6.25
        y2 = 0.5·0.5·(√(1+8·6.25) - 1) = 0.25·(√51 - 1)
           = 0.25·(7.1414 - 1) = 0.25·6.1414 ≈ 1.5354 m
    """
    y2 = chedl_wrapper.hydraulic_jump_y2(y1=0.5, Fr1=2.5)
    expected_y2 = 0.5 * 0.5 * (math.sqrt(1.0 + 8.0 * 2.5 ** 2) - 1.0)
    assert y2 == pytest.approx(expected_y2, rel=1e-9), (
        f"水跃共轭水深 y2 应为 {expected_y2}，实际 {y2}"
    )
    # 物理意义校验：Fr1>1（急流）→ y2 > y1（缓流）
    assert y2 > 0.5, f"Fr1=2.5 急流 → y2 应大于 y1，实际 y2={y2}"

    # 边界：Fr1=1（临界流）→ y2=y1（Bélanger 方程退化）
    y2_critical = chedl_wrapper.hydraulic_jump_y2(y1=1.0, Fr1=1.0)
    assert y2_critical == pytest.approx(1.0, rel=1e-9), (
        f"Fr1=1 临界流 → y2 应等于 y1，实际 {y2_critical}"
    )

    # 边界：Fr1=4（强水跃）→ y2/y1 显著增大
    y2_strong = chedl_wrapper.hydraulic_jump_y2(y1=1.0, Fr1=4.0)
    expected_y2_strong = 0.5 * (math.sqrt(1.0 + 8.0 * 16.0) - 1.0)
    assert y2_strong == pytest.approx(expected_y2_strong, rel=1e-9), (
        f"Fr1=4 强水跃 y2 应为 {expected_y2_strong}，实际 {y2_strong}"
    )
    assert y2_strong > 5.0, f"Fr1=4 强水跃 → y2/y1 > 5，实际 {y2_strong}"


# ============================================================================
# P6-0 Task 4 provenance 接口扩展（OPEN_CHANNEL 4 函数）
# ============================================================================


def test_get_chedl_provenance_contains_p6_0_task4_four_functions():
    """provenance 字典键必须含全部 4 个 P6-0 Task 4 新增函数名。"""
    prov = chedl_wrapper.get_chedl_provenance()
    expected_p6_0_t4 = {
        "manning_Q",
        "manning_V",
        "critical_depth_rectangular",
        "hydraulic_jump_y2",
    }
    assert expected_p6_0_t4.issubset(set(prov.keys())), (
        f"provenance 缺 P6-0 Task 4 函数：{expected_p6_0_t4 - set(prov.keys())}"
    )


def test_p6_0_task4_provenance_fallback_metadata():
    """P6-0 Task 4 4 函数 provenance 必须显式标注 fallback_available=True + fallback_formula_ref。

    Path A 设计决策：fluids.open_channel 缺失 4/5 函数，自研实现依赖 SPEC §3.2.6 教科书公式。
    """
    prov = chedl_wrapper.get_chedl_provenance()
    for fn_name in (
        "manning_Q",
        "manning_V",
        "critical_depth_rectangular",
        "hydraulic_jump_y2",
    ):
        meta = prov[fn_name]
        assert meta.fallback_available is True, (
            f"{fn_name} fallback_available 应为 True（Path A 自研）"
        )
        assert meta.fallback_formula_ref, (
            f"{fn_name} fallback_formula_ref 必须非空（SPEC § 公式追溯）"
        )
        assert meta.fallback_formula_ref.startswith("spec_p6_"), (
            f"{fn_name} fallback_formula_ref 应以 'spec_p6_' 开头，"
            f"实际 {meta.fallback_formula_ref!r}"
        )
        assert meta.known_limitations, (
            f"{fn_name} known_limitations 必须列出（Path A 决策依据）"
        )


def test_p6_0_task4_provenance_chedl_function_spec_p6_3_2_6():
    """OPEN_CHANNEL 4 函数 provenance 的 chEDL_function 必须以 spec_p6_3.2.6 开头。

    SPEC §3.2.6 是 OPEN_CHANNEL 明渠流的统一锚点。
    """
    prov = chedl_wrapper.get_chedl_provenance()
    for fn_name in (
        "manning_Q",
        "manning_V",
        "critical_depth_rectangular",
        "hydraulic_jump_y2",
    ):
        meta = prov[fn_name]
        assert meta.chEDL_function.startswith("spec_p6_3.2.6"), (
            f"{fn_name} chEDL_function 应以 'spec_p6_3.2.6' 开头，"
            f"实际 {meta.chEDL_function!r}"
        )


# ============================================================================
# P6-0 Task 4 模块导出契约
# ============================================================================


def test_chedl_wrapper_module_exports_all_17():
    """chedl_wrapper 模块必须暴露全部 17 包装函数 + get_chedl_provenance（13 + 4 Task 4）。"""
    import app.services.chedl_wrapper as cw

    required_funcs = [
        # 既有 7 项
        "v_Souders_Brown",
        "K_separator_Watkins",
        "K_separator_demister_York",
        "K_Souders_Brown_theoretical",
        "v_terminal",
        "API520_round_size",
        "time_to_empty",
        "tank_level_to_volume",
        # P6-0 Task 3 6 项
        "control_valve_C_liquid",
        "control_valve_kv_liquid",
        "control_valve_cv_gas",
        "flow_meter_orifice",
        "flow_meter_venturi",
        "flow_meter_nozzle",
        # P6-0 Task 4 4 项
        "manning_Q",
        "manning_V",
        "critical_depth_rectangular",
        "hydraulic_jump_y2",
        "get_chedl_provenance",
    ]
    for fn_name in required_funcs:
        assert hasattr(cw, fn_name), f"chedl_wrapper 缺 {fn_name}"
        assert callable(getattr(cw, fn_name)), f"chedl_wrapper.{fn_name} 不可调用"


# ============================================================================
# P6-0 Task 4 参数校验（防御性编程）
# ============================================================================


def test_manning_Q_rejects_non_positive_n():
    """manning_Q 必须拒绝非正 Manning n（n≤0 无物理意义）。"""
    with pytest.raises(ValueError, match="Manning"):
        chedl_wrapper.manning_Q(n=0.0, A_m2=2.0, Rh_m=1.0, S=0.001)
    with pytest.raises(ValueError, match="Manning"):
        chedl_wrapper.manning_Q(n=-0.013, A_m2=2.0, Rh_m=1.0, S=0.001)


def test_manning_V_rejects_non_positive_S():
    """manning_V 必须拒绝负坡度 S（S<0 表示逆坡，无物理意义；S=0 视为临界水平态）。"""
    with pytest.raises(ValueError, match="坡度"):
        chedl_wrapper.manning_V(n=0.013, Rh_m=1.0, S=-0.001)


def test_critical_depth_rectangular_rejects_non_positive_b():
    """critical_depth_rectangular 必须拒绝非正渠宽 b（b≤0 无断面）。"""
    with pytest.raises(ValueError, match="渠宽"):
        chedl_wrapper.critical_depth_rectangular(Q_m3s=1.0, b_m=0.0)
    with pytest.raises(ValueError, match="渠宽"):
        chedl_wrapper.critical_depth_rectangular(Q_m3s=1.0, b_m=-1.0)


def test_hydraulic_jump_y2_rejects_non_positive_y1():
    """hydraulic_jump_y2 必须拒绝非正 y1（y1≤0 无上游水深）。"""
    with pytest.raises(ValueError, match="y1"):
        chedl_wrapper.hydraulic_jump_y2(y1=0.0, Fr1=2.5)
    with pytest.raises(ValueError, match="y1"):
        chedl_wrapper.hydraulic_jump_y2(y1=-0.5, Fr1=2.5)