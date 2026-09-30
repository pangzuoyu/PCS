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
- ``saturation_water_content_service`` 提供显式饱和水含量 service
  （P6-4 C-17 / Task 4；RH=1.0 直调 chedl_wrapper + lru_cache + 三单位换算
  + 酸性气校正）。

Task 26: psychro persist + api（6 calc endpoint + 5 CRUD endpoint）。
Task 4 (P6-4 C-17): saturation_water_content service + 4 nullable DB 列
+ /psychro/saturation-water-content/calculate endpoint。

注意：6 个 calc endpoint 由 app/api/v1/psychro.py 直调 chedl_wrapper 6 函数；
本 service 包**仅**负责 PsychroResult 持久化（不重复 chedl_wrapper 包装）。
饱和水含量 endpoint 同理直调 ``calc_saturation_water_content`` service
（包装层只在 service 内）。
"""
from __future__ import annotations

from app.services.psychro._glycol_dehydration import (  # P6-9-PICKUP-5 5C (REF-P6-8-2)
    ReboilerStrippingInput,
    ReboilerStrippingResult,
    calc_reboiler_stripping,
)
from app.services.psychro.coolprop_version import (  # P6-2 Task 26
    get_coolprop_version,
)
from app.services.psychro.glycol_dehydration_service import (  # P6-5 Task C1 (C-16)
    GlycolDehydrationError,
    GlycolDehydrationInput,
    GlycolDehydrationResult,
    GlycolType,
    calc_glycol_dehydration,
)
from app.services.psychro.hydrate_inhibition_service import (  # P6-5 Task C2 (C-18)
    HydrateInhibitionError,
    HydrateInhibitionInput,
    HydrateInhibitionResult,
    InhibitorModel,
    InhibitorType,
    calc_hydrate_inhibition,
)
from app.services.psychro.psychro_persist_service import (  # P6-2 Task 26
    PsychroPersistInputError,
    get_psychro_result,
    list_psychro_results,
    save_psychro_result,
    soft_delete_psychro_result,
    update_psychro_result,
)
from app.services.psychro.saturation_water_content_service import (  # P6-4 Task 4 (C-17)
    SaturationWaterContentInput,
    SaturationWaterContentInputError,
    SaturationWaterContentResult,
    calc_saturation_water_content,
    calc_saturation_water_content_metric,
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
    # P6-4 Task 4 (C-17) — 显式水含量 service（饱和 W = RH=1.0）
    "SaturationWaterContentInput",
    "SaturationWaterContentInputError",
    "SaturationWaterContentResult",
    "calc_saturation_water_content",
    "calc_saturation_water_content_metric",
    # P6-5 Task C1 (C-16) — TEG/DEG 甘醇脱水 service（接触塔设计）
    "GlycolDehydrationError",
    "GlycolDehydrationInput",
    "GlycolDehydrationResult",
    "GlycolType",
    "calc_glycol_dehydration",
    # P6-9-PICKUP-5 5C (REF-P6-8-2) — 再沸器负荷 + 汽提气率 standalone 服务
    # （实现已移至 psychro/_glycol_dehydration/reboilers.py）
    "ReboilerStrippingInput",
    "ReboilerStrippingResult",
    "calc_reboiler_stripping",
    # P6-5 Task C2 (C-18) — 水合物抑制 service（Hammerschmidt + 注入率）
    "HydrateInhibitionError",
    "HydrateInhibitionInput",
    "HydrateInhibitionResult",
    "InhibitorModel",  # P6-6B T8 — Hammerschmidt/Nielsen 双模型枚举
    "InhibitorType",
    "calc_hydrate_inhibition",
]
