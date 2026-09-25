"""PSYCHRO 湿空气计算 service（§3.2.5 P6-PSY-001）。

按 SPEC §3.2.5 PSYCHRO 实施湿空气物性计算 + 持久化：

- ``chedl_wrapper``（Task 5 已落地）提供 6 个 ``humid_air_*`` 包装函数，
  直调 CoolProp.HumidAirProp.HAPropsSI（ADR-0030 V1.2 G-02 锁定包装层）。
- ``coolprop_version`` 提供 ``get_coolprop_version()`` helper
  （Task 26 新增；PcsError 兜底 'unknown'）。
- ``psychro_persist_service`` 提供 5 service 函数
  （save / list / get / update / soft_delete）镜像 Task 25
  cool_tower_persist_service pattern，PsychroResult ORM 落库 +
  record_hash reflection（ADR-0028 §决策 4）+ coolprop_version 自动填。

Task 26: psychro persist + api（6 calc endpoint + 5 CRUD endpoint）。

注意：6 个 calc endpoint 由 app/api/v1/psychro.py 直调 chedl_wrapper 6 函数；
本 service 包**仅**负责 PsychroResult 持久化（不重复 chedl_wrapper 包装）。
"""
from __future__ import annotations

from app.services.psychro.coolprop_version import (  # P6-2 Task 26
    get_coolprop_version,
)
from app.services.psychro.psychro_persist_service import (  # P6-2 Task 26
    PsychroPersistInputError,
    get_psychro_result,
    list_psychro_results,
    save_psychro_result,
    soft_delete_psychro_result,
    update_psychro_result,
)

__all__ = [
    # P6-2 Task 26 — coolprop_version 溯源 helper
    "get_coolprop_version",
    # P6-2 Task 26 — psychro_persist_service（CRUD + sign_status 流）
    "PsychroPersistInputError",
    "save_psychro_result",
    "list_psychro_results",
    "get_psychro_result",
    "update_psychro_result",
    "soft_delete_psychro_result",
]
