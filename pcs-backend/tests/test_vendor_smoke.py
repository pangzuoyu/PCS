"""vendor 接线冒烟测试（Task 1.9.0）。"""
import chemicals
import fluids
import thermo


def test_vendored_versions():
    assert chemicals.__version__ == "1.5.2"
    assert fluids.__version__ == "1.3.1"
    assert thermo.__version__ == "0.6.1"


def test_twu_petroleum_viscosity_available():
    from chemicals.viscosity import Twu_1985_internal
    # _internal 签名为 (T, Tb, SG)，T/Tb 单位 Rankine（公共包装 Twu_1985 内部 ×1.8），返回 cSt
    nu = Twu_1985_internal(T=293.15 * 1.8, Tb=447.3 * 1.8, SG=0.73)  # n-癸烷，ν20≈1.26 cSt
    assert 0.3 < nu < 3.0  # Twu 为馏分关联式，纯组分放宽带宽


def test_iapws_water_steam_available():
    from chemicals.iapws import iapws95_Pc, iapws95_Psat, iapws95_Tc
    assert abs(iapws95_Tc - 647.096) < 0.01              # 常量，K
    assert abs(iapws95_Pc - 22064000.0) < 1000.0         # 常量，Pa
    assert abs(iapws95_Psat(373.15) - 101325.0) < 500    # 100°C 饱和蒸气压 ≈ 1 atm
