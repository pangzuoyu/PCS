"""供应商实际数据录入 API schemas (P7 Sprint 4 S4-1 / ADR-0025).

录入入口是手工 UI 页面: 设备方逐项填写, 一次提交一整台设备的参数集
(S4-1 裁决 —— 要求供应商填统一 Excel 不现实, 故无批量导入端点)。

请求体只收 `entries`; project/workspace 从 equipment 记录派生 —— 客户端不该
有机会把值写到别的设备/项目上。
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ActualDataEntry(BaseModel):
    """一项实测值。value 严格数值 —— 字符串数字在 UI 上是录入错误, 不是可容忍的输入。"""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100, description="参数名")
    value: float = Field(description="实测值 (可为负, 如冬季设计温度)")
    unit: str = Field(default="", max_length=32, description="单位; 无量纲可留空")


class ActualDataEntryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entries: list[ActualDataEntry] = Field(
        min_length=1,
        description="整台设备的参数集; 整体替换而非合并",
    )


class ActualDataResponse(BaseModel):
    """设备实测值。`actual_data_json` 为 None 表示尚未录入。"""

    model_config = ConfigDict(from_attributes=True)

    equipment_id: str
    tag_number: str
    actual_data_status: str
    actual_data_json: dict | None = None


__all__ = [
    "ActualDataEntry",
    "ActualDataEntryRequest",
    "ActualDataResponse",
]
