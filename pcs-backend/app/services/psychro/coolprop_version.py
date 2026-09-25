"""CoolProp 版本溯源 helper（P6-2 Task 26 PSYCHRO 持久化层）。

按 .wolf/cerebrum.md 单一职责：本模块**仅**负责获取 CoolProp 库版本字符串，
业务代码（service / endpoint）**禁止**直接 ``import CoolProp.__version__`` —
经此 helper 便于：

1. **集中 mock 测试**：service 层只依赖 ``get_coolprop_version()`` 单点入口，
   pytest fixture 直接 monkeypatch，无需碰 CoolProp。
2. **降级兜底**：依赖缺失 / 版本查询失败时返回 ``"unknown"``，避免 cascade
   failure 影响 ``PsychroResult`` 落库主链路。
3. **冷却盘管精度溯源**：service 层自动写入 ``coolprop_version`` 字段（STRING(16)
   ORM 列），与 record_hash reflection 配合支撑后续版本漂移审计
   （ADR-0030 V1.2 决策 5）。

设计要点（与 chedl_wrapper 既有 ``_COOLPROP_VERSION`` 常量关系）：

- chedl_wrapper._COOLPROP_VERSION = "6.6.0" 是**编译期**常量（pyproject 锁定）。
- 本 helper 是**运行时**查询，返回实际安装版本；如与锁定不符由运维感知。
"""
from __future__ import annotations


def get_coolprop_version() -> str:
    """获取 CoolProp 库版本字符串（如 '6.6.0'）。

    Returns:
        str: 版本号（如 '6.6.0'），失败时返回 'unknown'。

    失败兜底：
        try/except ImportError / AttributeError → return 'unknown'
        不抛异常，避免 cascade failure 影响 PsychroResult 落库主链路。
    """
    try:
        # 优先使用 CoolProp.get_global_param_string('version')（官方推荐）
        # 注：部分版本仅暴露 CoolProp.__version__，故 fallback 双路径
        from CoolProp import CoolProp as _CP  # noqa: PLC0415
        try:
            return str(_CP.get_global_param_string("version"))
        except Exception:  # pragma: no cover - 极端环境守卫
            try:
                return str(_CP.__version__)
            except AttributeError:
                return "unknown"
    except ImportError:
        return "unknown"


__all__ = ["get_coolprop_version"]
