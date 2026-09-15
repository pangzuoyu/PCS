"""P4-TASK0 物理量语义模型（自实现最小集，零依赖）。

三件套：
- Dimension：SI 量纲（基本量 + 指数）
- Quantity：value × dimension 二元组
- 单位换算：常用单位（Pa/bar, m³/s/L/min, K/°C）

设计取舍：
- 不引入 chemicals/pint（"不引入新依赖"约束）。
- Dimension 是语义 SI 维（如 'kg*m^-1*s^-2' 对应压强），不携带单位。
- 单位注册表：每单位映射 (si_dim, factor_to_SI, offset_to_SI)。
- convert(q, target, source_unit=None)：source 默认 SI 基（factor=1, offset=0）。
- 仿射换算（°C↔K）：K = value * factor + offset；反向需显式 source_unit。
- 量纲算术：加/减需同 dimension；乘/除推 dimension。

异常：
- UnitConversionError：单位未注册 / 维度不匹配 / 仿射链断裂。
- DimensionMismatchError：加减时 dimension 不同。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Final

# ============================================================================
# 1. SI base dimensions
# ============================================================================

# SI 7 个基本量（按物理量名 → SI 单位符号）。
SI_BASE: Final[dict[str, tuple[str, int]]] = {
    "length": ("m", 1),
    "mass": ("kg", 1),
    "time": ("s", 1),
    "current": ("A", 1),
    "temperature": ("K", 1),
    "amount": ("mol", 1),
    "luminosity": ("cd", 1),
}

# Dimension 输出时的稳定排序（短符号），与 SI_BASE 物理量名一致：m/kg/s/A/K/mol/cd。
_DIM_SYMBOL_ORDER: Final[tuple[str, ...]] = (
    "m",
    "kg",
    "s",
    "A",
    "K",
    "mol",
    "cd",
)


def si_base_dimensions() -> dict[str, tuple[str, int]]:
    """返回 SI 7 基本量映射（拷贝；外部不可改）。"""
    return dict(SI_BASE)


# ============================================================================
# 2. Dimension
# ============================================================================


class Dimension(dict[str, int]):
    """SI 量纲：{基本量名: 指数}。幂 0 不存。

    解析：'m^2*kg*s^-2' → {'m': 2, 'kg': 1, 's': -2}
    """

    @classmethod
    def parse(cls, expr: str) -> Dimension:
        """解析 'name^exp * name * name^exp' 形式量纲字符串。

        支持：^N（含负）、省略（默认 1）、空串（无量纲）。
        """
        d = cls()
        if not expr.strip():
            return d
        for token in expr.split("*"):
            token = token.strip()
            if not token:
                continue
            m = re.match(r"^([A-Za-z]+)(?:\^(-?\d+))?$", token)
            if not m:
                raise ValueError(f"非法量纲 token: {token!r}")
            name, exp = m.group(1), int(m.group(2)) if m.group(2) else 1
            if exp == 0:
                d.pop(name, None)
            else:
                d[name] = d.get(name, 0) + exp
        return d

    def __str__(self) -> str:
        if not self:
            return "1"
        # 短符号排序（m, kg, s, A, K, mol, cd），其余按字典序
        order = list(_DIM_SYMBOL_ORDER) + sorted(
            k for k in self if k not in _DIM_SYMBOL_ORDER
        )
        parts: list[str] = []
        for k in order:
            v = self.get(k)
            if v is None or v == 0:
                continue
            parts.append(f"{k}^{v}" if v != 1 else k)
        return "*".join(parts) if parts else "1"

    def __repr__(self) -> str:
        return f"Dimension({str(self)!r})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Dimension):
            return NotImplemented
        return dict(self) == dict(other)

    def __hash__(self) -> int:
        return hash(frozenset(self.items()))

    def is_dimensionless(self) -> bool:
        return len(self) == 0


# ============================================================================
# 3. Unit registry
# ============================================================================

# 单位注册表：unit_name → (si_dim_str, factor_to_SI, offset_to_SI)
#   si_value = value_in_unit * factor + offset
_UNITS: Final[dict[str, tuple[str, float, float]]] = {
    # 压强（SI 基 = Pa）
    "Pa": ("kg*m^-1*s^-2", 1.0, 0.0),
    "kPa": ("kg*m^-1*s^-2", 1e3, 0.0),
    "MPa": ("kg*m^-1*s^-2", 1e6, 0.0),
    "bar": ("kg*m^-1*s^-2", 1e5, 0.0),
    "atm": ("kg*m^-1*s^-2", 101325.0, 0.0),
    # 长度（SI 基 = m）
    "m": ("m", 1.0, 0.0),
    "cm": ("m", 1e-2, 0.0),
    "mm": ("m", 1e-3, 0.0),
    "km": ("m", 1e3, 0.0),
    "inch": ("m", 0.0254, 0.0),
    # 体积流量（SI 基 = m³/s）
    "m^3*s^-1": ("m^3*s^-1", 1.0, 0.0),
    "m^3*h^-1": ("m^3*s^-1", 1.0 / 3600.0, 0.0),
    "L*s^-1": ("m^3*s^-1", 1e-3, 0.0),
    "L/min": ("m^3*s^-1", 1e-3 / 60.0, 0.0),
    "L*min^-1": ("m^3*s^-1", 1e-3 / 60.0, 0.0),
    "L*h^-1": ("m^3*s^-1", 1e-3 / 3600.0, 0.0),
    # 质量（SI 基 = kg）
    "kg": ("kg", 1.0, 0.0),
    "g": ("kg", 1e-3, 0.0),
    "t": ("kg", 1e3, 0.0),
    # 时间（SI 基 = s）
    "s": ("s", 1.0, 0.0),
    "min": ("s", 60.0, 0.0),
    "h": ("s", 3600.0, 0.0),
    # 温度（SI 基 = K；°C 是仿射）
    "K": ("K", 1.0, 0.0),
    "°C": ("K", 1.0, 273.15),
}

# SI 基单位映射：si_dim_str → 该维度的 SI 基单位名（factor=1, offset=0）
_SI_BASE_UNIT: Final[dict[str, str]] = {
    dim: unit
    for unit, (dim, factor, offset) in _UNITS.items()
    if factor == 1.0 and offset == 0.0
}


# ============================================================================
# 4. Exceptions
# ============================================================================


class UnitConversionError(ValueError):
    """单位换算失败：单位未注册 / 维度不匹配 / 仿射链断裂。"""


class DimensionMismatchError(ValueError):
    """量纲算术失败：加/减要求 dimension 一致。"""


# ============================================================================
# 5. Quantity
# ============================================================================


@dataclass(frozen=True)
class Quantity:
    """物理量：value × dimension 二元组。

    frozen=True 保证不可变（避免 in-place 修改导致 hash 漂移）。
    dimension 是语义 SI 维（不带单位）。
    """

    value: float
    dimension: Dimension = field(default_factory=Dimension)

    def __post_init__(self) -> None:
        if not isinstance(self.dimension, Dimension):
            object.__setattr__(self, "dimension", Dimension(self.dimension))

    # 加减：同维度
    def __add__(self, other: Quantity) -> Quantity:
        if not isinstance(other, Quantity):
            return NotImplemented
        if self.dimension != other.dimension:
            raise DimensionMismatchError(
                f"cannot add {self.dimension} + {other.dimension}"
            )
        return Quantity(self.value + other.value, Dimension(self.dimension))

    def __sub__(self, other: Quantity) -> Quantity:
        if not isinstance(other, Quantity):
            return NotImplemented
        if self.dimension != other.dimension:
            raise DimensionMismatchError(
                f"cannot subtract {self.dimension} - {other.dimension}"
            )
        return Quantity(self.value - other.value, Dimension(self.dimension))

    # 乘除：维度指数合并
    def __mul__(self, other: Quantity | float) -> Quantity:
        if isinstance(other, Quantity):
            new_dim = Dimension(self.dimension)
            for k, v in other.dimension.items():
                new_dim[k] = new_dim.get(k, 0) + v
                if new_dim[k] == 0:
                    new_dim.pop(k, None)
            return Quantity(self.value * other.value, new_dim)
        if isinstance(other, (int, float)):
            return Quantity(self.value * float(other), Dimension(self.dimension))
        return NotImplemented

    __rmul__ = __mul__

    def __truediv__(self, other: Quantity | float) -> Quantity:
        if isinstance(other, Quantity):
            new_dim = Dimension(self.dimension)
            for k, v in other.dimension.items():
                new_dim[k] = new_dim.get(k, 0) - v
                if new_dim[k] == 0:
                    new_dim.pop(k, None)
            return Quantity(self.value / other.value, new_dim)
        if isinstance(other, (int, float)):
            return Quantity(self.value / float(other), Dimension(self.dimension))
        return NotImplemented


# ============================================================================
# 6. convert
# ============================================================================


def convert(q: Quantity, target_unit: str, source_unit: str | None = None) -> Quantity:
    """单位换算：保持 dimension，变换 value。

    Args:
        q: 源 Quantity（dimension 是语义 SI 维）
        target_unit: 目标单位名（必须在 _UNITS 注册）
        source_unit: 源单位名；None 时默认 SI 基（factor=1, offset=0）。
                     仿射单位（如 °C）反向换算时必须显式传 source_unit。

    Returns:
        Quantity：value 是 target_unit 下的数值，dimension 不变。

    Raises:
        UnitConversionError：单位未注册 / 维度不匹配。
    """
    if target_unit not in _UNITS:
        raise UnitConversionError(f"target unit {target_unit!r} not registered")
    tgt_si_dim, tgt_factor, tgt_offset = _UNITS[target_unit]

    q_dim = q.dimension
    # 语义比对：Dimension 对象相等（dict 比较），不依赖 str() 顺序
    q_si_dim = Dimension.parse(tgt_si_dim)
    if q_dim != q_si_dim:
        raise UnitConversionError(
            f"target unit {target_unit!r} (dim={tgt_si_dim}) incompatible "
            f"with quantity dim={q_dim}"
        )

    # 解析源单位
    if source_unit is None:
        q_dim_str = tgt_si_dim
        if q_dim_str not in _SI_BASE_UNIT:
            raise UnitConversionError(
                f"no SI base unit for dim={q_dim_str}; pass source_unit explicitly"
            )
        src_factor, src_offset = 1.0, 0.0
    else:
        if source_unit not in _UNITS:
            raise UnitConversionError(f"source unit {source_unit!r} not registered")
        src_si_dim, src_factor, src_offset = _UNITS[source_unit]
        if Dimension.parse(src_si_dim) != q_dim:
            raise UnitConversionError(
                f"source unit {source_unit!r} (dim={src_si_dim}) "
                f"incompatible with quantity dim={q_dim}"
            )

    # value_in_SI = value * src_factor + src_offset
    # value_in_target = (value_in_SI - tgt_offset) / tgt_factor
    si_value = q.value * src_factor + src_offset
    target_value = (si_value - tgt_offset) / tgt_factor
    return Quantity(target_value, q.dimension)


__all__ = [
    "Dimension",
    "Quantity",
    "UnitConversionError",
    "DimensionMismatchError",
    "si_base_dimensions",
    "convert",
]
