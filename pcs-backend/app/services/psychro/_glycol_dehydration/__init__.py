"""PSYCHRO 甘醇脱水子模块包（``_glycol_dehydration/``，P6-9-PICKUP-5 5C）。

REF-P6-8-2：把 ``glycol_dehydration_service.py``（1423 LOC 单体）按工艺段拆为
3 个内聚子模块，私有前缀 ``_`` 表示「非 public API」（仿 ``_DewpointResult``
等私有命名；本包内容本身不被 ``psychro/__init__.py`` 的 public API 直接暴露）。

分章节：

- ``reboilers`` — 再沸器负荷（完整焓平衡 +10% 裕度）+ 汽提气率（GPSA §20.4
  Eq.20-5 + Antoine）+ 贫甘醇浓度（GPSA Fig 20-4 插值）。
  对应 OPEN-P6-6A-6 子任务 1 / 2 / 4。
- ``dewpoint`` — Behr 反函数（给定 W 反算 T_dew；brentq + Newton fallback），
  三态 ``_DewpointResult``。对应 P6-6A-6 v5.1 B-3 / H-3。
- ``behr`` — Behr 正函数（v3 grid 查表 + 双线性插值 + Bukacek 1990 低温延伸
  + 酸气修正 general 线性 placeholder / high_acid 真 Wichert-Aziz）。
  对应 P6-6A-6 v5.1 Day-0 Gate / P6-8 T9r。

依赖方向（无循环）：

    glycol_dehydration_service  ──单向──>  reboilers
                                          dewpoint ──> behr
                                          behr

子模块之间除 ``dewpoint → behr``（反函数复用正函数）外互不引用。

``__all__`` 仅重导出 public API 三件套 ``ReboilerStrippingInput`` /
``ReboilerStrippingResult`` / ``calc_reboiler_stripping``；
所有 ``_`` 前缀私有 helper 不导出（Ruling 9：私有化不入 ``__all__``）。
"""
from __future__ import annotations

from app.services.psychro._glycol_dehydration.reboilers import (
    ReboilerStrippingInput,
    ReboilerStrippingResult,
    calc_reboiler_stripping,
)

__all__ = [
    # P6-8 T1 — Reboiler Duty + Stripping Gas Rate 独立服务（OPEN-P6-6A-6 子任务 1+2）
    "ReboilerStrippingInput",
    "ReboilerStrippingResult",
    "calc_reboiler_stripping",
]
