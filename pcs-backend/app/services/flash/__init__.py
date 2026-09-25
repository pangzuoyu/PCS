"""Flash 计算服务包（P4-1+）。

子模块：
- thermo_factory：P4-1-1 thermo 后端抽象 + 工厂
- flash_service：P4-1-2 step 1~3 PT_FLASH + BUBBLE/DEW/PH/PS + SATURATION
- flash_persist：P4-1-2 step 4 ORM 落库
- saturation_helper：P6-4 Task 4 (C-17 显式水含量) 最小 stub —
  flash 端 ASHRAE 黄金对账 helper（V1.2 D2；接口冻结，
  完整 flash 算法留 P6-18）
"""
from app.services.flash.saturation_helper import (  # P6-4 Task 4 (C-17)
    flash_saturation_water_content,
    get_golden_saturation_w_kg_kg,
    verify_saturation_w,
)

__all__ = [
    # P6-4 Task 4 (C-17) — flash 端饱和水含量 cross-check stub
    "flash_saturation_water_content",
    "get_golden_saturation_w_kg_kg",
    "verify_saturation_w",
]