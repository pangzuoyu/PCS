"""P4-1-1 thermo 抽象层 + 工厂。

职责：
- 定义 ``ThermoInterface`` Protocol（所有 thermo 后端的统一契约骨架）
- 定义 ``THERMO_METHOD_MAP``（4 体系 → thermo 方法名）
- 提供 ``build_thermo`` 工厂：根据 system_type + 归一化组成返回对应 stub 类
- 提供 ``UnknownSystemTypeError`` / ``CompositionSumError``（继承 PcsError 体系）

本模块是 P4-1-1 落地，仅定义协议骨架 + 工厂；具体方法（Psat/Tsat/FlashPT 等）由
P4-1-2 在 stub 类上补全。本文件不修改 PcsError 既有定义，仅扩展使用。
"""
from __future__ import annotations

import math
from typing import Protocol, runtime_checkable

from app.services.exceptions import PcsError

# ---------------------------------------------------------------------------
# 映射表（值是实现名字符串占位；P4-1-2+ 用此 key 选择具体 thermo 后端）
# ---------------------------------------------------------------------------

THERMO_METHOD_MAP: dict[str, str] = {
    "LIGHT_HYDROCARBON": "PRMIX",
    "GAS_PROCESSING": "SRKMIX",
    "POLAR": "NRTL",
    "WATER_STEAM": "CoolProp",
}


# ---------------------------------------------------------------------------
# 异常类（继承既有 PcsError 体系 — 422 风格）
# ---------------------------------------------------------------------------


class UnknownSystemTypeError(PcsError):
    """未知 system_type（不在 THERMO_METHOD_MAP 中）。"""

    code = "UNKNOWN_SYSTEM_TYPE"
    status = 422


class CompositionSumError(PcsError):
    """组成校验失败：含非有限值 / 负值 / 全 0（无法归一化）。"""

    code = "COMPOSITION_SUM_ERROR"
    status = 422


# ---------------------------------------------------------------------------
# Protocol（统一契约骨架 — 完整方法签名由 P4-1-2 补）
# ---------------------------------------------------------------------------


@runtime_checkable
class ThermoInterface(Protocol):
    """所有 thermo 后端的统一契约（P4-1-1 定义骨架；P4-1-2 补具体方法）。

    本 task 仅定义 Psat 占位；其余方法（Tsat/FlashPT/FlashPH 等）由后续
    P4-1-2 在 stub 类上补全。
    """

    def Psat(self, comp_id: int) -> float:
        """纯组分饱和压力（Pa）。P4-1-2 落地具体实现。"""
        ...


# ---------------------------------------------------------------------------
# Stub 类（每个体系一个；全部方法 raise NotImplementedError）
# ---------------------------------------------------------------------------


class _NotImplementedThermo:
    """stub 基类 — 拦截所有 ThermoInterface 方法调用，统一 NotImplementedError。"""

    _msg = "P4-1-2 落地"

    def Psat(self, comp_id: int) -> float:
        raise NotImplementedError(self._msg)

    def __repr__(self) -> str:  # pragma: no cover — debug-only
        return f"<{type(self).__name__} stub>"


class PRMIXThermo(_NotImplementedThermo):
    """LIGHT_HYDROCARBON 体系 stub — Peng-Robinson 混合规则。"""


class SRKMIXThermo(_NotImplementedThermo):
    """GAS_PROCESSING 体系 stub — Soave-Redlich-Kwong 混合规则。"""


class NRTLThermo(_NotImplementedThermo):
    """POLAR 体系 stub — NRTL 活度系数模型。"""


class CoolPropThermo(_NotImplementedThermo):
    """WATER_STEAM 体系 stub — CoolProp 水/蒸汽物性库。"""


# ---------------------------------------------------------------------------
# Stub 类注册表（system_type → 实现类）
# ---------------------------------------------------------------------------

_STUB_REGISTRY: dict[str, type[_NotImplementedThermo]] = {
    "LIGHT_HYDROCARBON": PRMIXThermo,
    "GAS_PROCESSING": SRKMIXThermo,
    "POLAR": NRTLThermo,
    "WATER_STEAM": CoolPropThermo,
}


# ---------------------------------------------------------------------------
# 工厂
# ---------------------------------------------------------------------------


def _validate_and_normalize_zs(zs: list[float]) -> list[float]:
    """校验 + 归一化 zs。

    规则：
    - 空列表 / 全 0 → raise CompositionSumError
    - 含 NaN / inf / 负值 → raise CompositionSumError
    - |sum(zs) - 1| > 1e-6 → 自动归一化（除以 sum），不修改调用方原列表

    Returns:
        归一化后的新 list（不修改入参）
    """
    if not zs:
        raise CompositionSumError("zs 列表为空，无法归一化")

    for i, z in enumerate(zs):
        if not math.isfinite(z) or z < 0:
            raise CompositionSumError(
                f"zs[{i}]={z} 为非有限值或负值，无法归一化"
            )

    total = sum(zs)
    if total == 0:
        raise CompositionSumError("zs 总和为 0，无法归一化")

    # 归一化到 sum=1，返回新列表（不修改入参）
    return [z / total for z in zs]


def build_thermo(
    system_type: str, zs: list[float], cass: list[str]
) -> ThermoInterface:
    """根据体系类型 + 组成归一化，返回对应 thermo stub。

    Args:
        system_type: 体系类型（须在 THERMO_METHOD_MAP 中）
        zs: 摩尔分率列表（会被自动归一化）
        cass: CAS 列表（stub 阶段不使用，仅签名占位 — P4-1-2 接入 CoolProp/chemicals）

    Returns:
        对应 stub 类实例（实现 ThermoInterface）

    Raises:
        UnknownSystemTypeError: system_type 不在 THERMO_METHOD_MAP（422 风格）
        CompositionSumError: zs 含非有限值 / 负值 / 空 / 全 0（422 风格）
    """
    # 1) 体系类型校验
    if system_type not in THERMO_METHOD_MAP:
        raise UnknownSystemTypeError(
            f"未知 system_type={system_type!r}；"
            f"支持的体系：{sorted(THERMO_METHOD_MAP.keys())}",
            details={"system_type": system_type, "supported": sorted(THERMO_METHOD_MAP.keys())},
        )

    # 2) 组成校验 + 归一化（不修改入参）
    _validate_and_normalize_zs(zs)

    # 3) 返回 stub 实例
    stub_cls = _STUB_REGISTRY[system_type]
    return stub_cls()


__all__ = [
    "THERMO_METHOD_MAP",
    "ThermoInterface",
    "build_thermo",
    "UnknownSystemTypeError",
    "CompositionSumError",
    "PRMIXThermo",
    "SRKMIXThermo",
    "NRTLThermo",
    "CoolPropThermo",
]
