"""PCS service 层统一异常。

PcsError 是所有 service 层异常的基类，便于上层（API/中间件）按 code/status
统一响应。PreconditionViolation 是公式 preconditions 评估时的 REJECT-only 异常。

SUP-P5-PSV-002 V1.14 §4.2 G7-G21 错误码 → 13 个 Psv* 子类
（每个子类只固定 code/status，message/details 走基类 __init__）。
"""

from __future__ import annotations

from typing import Any


class PcsError(Exception):
    """PCS 统一异常基类。所有 service 层异常应继承此类。"""

    code: str = "PCS_ERROR"
    status: int = 422

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        status: int | None = None,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        if code is not None:
            self.code = code
        if status is not None:
            self.status = status
        self.details = details or {}


class PreconditionViolation(PcsError):
    """公式前置/后置条件违规。code=PRECONDITION_VIOLATION, status=422, REJECT-only。"""

    code = "PRECONDITION_VIOLATION"
    status = 422


# ---------------------------------------------------------------------------
# SUP-P5-PSV-002 V1.14 §4.2 G7-G21 错误码子类
# ---------------------------------------------------------------------------


class PsvPilotOperatedNotSupported(PcsError):
    """G7：先导式（PILOT_OPERATED）阀型 P5 拦截（valve_validation:127 raise）。"""

    code = "PSV_PILOT_OPERATED_NOT_SUPPORTED"
    status = 422


class PsvRuptureDiscNotSupported(PcsError):
    """G8：爆破膜式（RUPTURE_DISC）阀型 P5 拦截（valve_validation:134 raise）。"""

    code = "PSV_RUPTURE_DISC_NOT_SUPPORTED"
    status = 422


class PsvOrificeOverrideTooSmall(PcsError):
    """G9：orifice_override 选型小于计算面积（unsafe；§4.2）。"""

    code = "PSV_ORIFICE_OVERRIDE_TOO_SMALL"
    status = 422


class PsvBackPressureExceeded(PcsError):
    """G10：背压超阀型上限（弹簧式 BUILT_UP 10% / 平衡波纹管 50%）。"""

    code = "PSV_BACK_PRESSURE_EXCEEDED"
    status = 422


class PsvBlowdownOutOfRange(PcsError):
    """G11：blowdown 超出阀型+介质允许范围（§3.5 BLOWDOWN_RANGE）。"""

    code = "PSV_BLOWDOWN_OUT_OF_RANGE"
    status = 422


class PsvInletOutletMismatch(PcsError):
    """G12：入/出口尺寸不符合 API 526 标准表（candidate mismatch）。"""

    code = "PSV_INLET_OUTLET_MISMATCH"
    status = 422


class PsvMaterialIncompatible(PcsError):
    """G13：平衡波纹管式材料-介质不兼容（阀体材料 vs 介质）。"""

    code = "PSV_MATERIAL_INCOMPATIBLE"
    status = 422


class PsvInletTooSmall(PcsError):
    """G14：入口尺寸 < 1"（API 526 §4.2 G14）。"""

    code = "PSV_INLET_TOO_SMALL"
    status = 422


class PsvOrificeTemperatureLimit(PcsError):
    """G15：Q/R/T 孔口在 T>177°C 且 MW<10 时须业主工程师批准（API 520 §5.3.4）。"""

    code = "PSV_ORIFICE_TEMPERATURE_LIMIT"
    status = 422


class PsvBellowsMaterialRequired(PcsError):
    """G17：平衡波纹管式（BALANCED_BELLOWS）必填波纹管材料。"""

    code = "PSV_BELLOWS_MATERIAL_REQUIRED"
    status = 422


class PsvFlangeClassOrificeMismatch(PcsError):
    """G20：法兰等级与孔口不匹配（§3.4；P5 占位，本批次不阻塞）。"""

    code = "PSV_FLANGE_CLASS_ORIFICE_MISMATCH"
    status = 422


class PsvBellowsIncompatible(PcsError):
    """G21：波纹管材料-介质不兼容（§3.8 BELLOWS_MATERIAL_COMPAT）。"""

    code = "PSV_BELLOWS_INCOMPATIBLE"
    status = 422


class PsvInletOutletRequired(PcsError):
    """Psv 入/出口尺寸必填项缺失（BALANCED_BELLOWS / 候选孔口校验前置）。"""

    code = "PSV_INLET_OUTLET_REQUIRED"
    status = 422


# ---------------------------------------------------------------------------
# Workspace context（HIGH P1-2 — 异常类型统一）
# ---------------------------------------------------------------------------


class WorkspaceNotFoundError(PcsError):
    """Workspace 不存在（HTTP 404）。"""

    code = "WORKSPACE_NOT_FOUND"
    status = 404


class WorkspaceTypeNotAllowedError(PcsError):
    """仅 FORMAL workspace 允许业务记录写（HTTP 403）。"""

    code = "WORKSPACE_TYPE_NOT_ALLOWED"
    status = 403


class WorkspaceContextMissingError(PcsError):
    """请求缺 workspace context（HTTP 422）。"""

    code = "WORKSPACE_CONTEXT_MISSING"
    status = 422


__all__ = [
    "PcsError",
    "PreconditionViolation",
    # SUP-P5-PSV-002 V1.14 G-codes
    "PsvPilotOperatedNotSupported",
    "PsvRuptureDiscNotSupported",
    "PsvOrificeOverrideTooSmall",
    "PsvBackPressureExceeded",
    "PsvBlowdownOutOfRange",
    "PsvInletOutletMismatch",
    "PsvMaterialIncompatible",
    "PsvInletTooSmall",
    "PsvOrificeTemperatureLimit",
    "PsvBellowsMaterialRequired",
    "PsvFlangeClassOrificeMismatch",
    "PsvBellowsIncompatible",
    "PsvInletOutletRequired",
    # Workspace context (HIGH P1-2)
    "WorkspaceNotFoundError",
    "WorkspaceTypeNotAllowedError",
    "WorkspaceContextMissingError",
]
