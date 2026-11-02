"""系统参数（§7.20.1）。

⚠️ `system_settings` 是**已存在的表**（`app/models/system.py`），此前**零 API**
⇒ 本文件是它的**第一个**对外形状 ⇒ 「表存在」≠「API 存在」。

形状说明：

- `SystemSettingOut` —— 一条参数（键 / 值 / 说明 / 更新时间）。
  `setting_value_json` 是 `Any`（值形态随键而异：数字 / 布尔 / 对象）。
- `SystemSettingBatchIn` —— **一次 PUT 提交全部改动**（委员会硬约束 1）：
  body 是 `{setting_key: 新值}` 的 map，不是逐键 PATCH 列表。
- `SystemSettingBatchOut` —— 回显**本次真正改掉**的那些行。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, RootModel


class SystemSettingOut(BaseModel):
    """一条系统参数。"""

    model_config = ConfigDict(from_attributes=True)

    setting_key: str
    setting_value_json: Any
    description: str | None = None
    updated_at: datetime


class SystemSettingValueMap(RootModel[dict[str, Any]]):
    """`setting_key → 新值` 的映射（值是 JSONB，形态随键而异）。"""

    # ⚠️ **为什么套一层 RootModel，而不是直接写 `dict[str, Any]`**：
    # 直接写会在契约里产生一个**没有结构定义的 object 字段** ⇒
    # `check_openapi_payload_coverage.py` 的裸字段数 +1 ⇒ 撞基线（发布前闸门
    # 必须 RC 0）。套 RootModel 后该字段在契约里是**具名 schema 的引用**（$ref）
    # ⇒ 裸字段计数不变，而 **JSON 形状完全不变**（仍是 `{"settings": {"键": 值}}`），
    # 前端拿到的仍是 `{ [key: string]: unknown }`。
    root: dict[str, Any]


class SystemSettingBatchIn(BaseModel):
    """批量保存的请求体 —— **一次 PUT 提交全部改动**（硬约束 1）。"""

    settings: SystemSettingValueMap = Field(description="setting_key → 新值；整批原子提交")


class SystemSettingBatchOut(BaseModel):
    """批量保存的结果。"""

    updated: list[SystemSettingOut]
