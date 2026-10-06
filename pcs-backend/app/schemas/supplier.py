"""供应商实际数据录入 API schemas (P7 Sprint 4 S4-1 / ADR-0025).

录入入口是手工 UI 页面: 设备方逐项填写, 一次提交一整台设备的参数集
(S4-1 裁决 —— 要求供应商填统一 Excel 不现实, 故无批量导入端点)。

请求体只收 `entries`; project/workspace 从 equipment 记录派生 —— 客户端不该
有机会把值写到别的设备/项目上。
"""

from __future__ import annotations

from typing import Literal

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
        max_length=50,
        description=(
            "整台设备的参数集; 整体替换而非合并。"
            "上限 50 = 泵应检集（6-7 项）的约 7 倍余量（审查 #1: "
            "无上限时单次 PUT 可造出任意大的报告，两个导出器都整体物化，"
            "实测 5000 行 xlsx 2.7s / pdf 5.1s 且成本线性）。"
            "⚠️ 暂定值 —— 非泵设备应检参数表落地后复核"
        ),
    )


class ActualDataResponse(BaseModel):
    """设备实测值。`actual_data_json` 为 None 表示尚未录入。"""

    model_config = ConfigDict(from_attributes=True)

    equipment_id: str
    tag_number: str
    actual_data_status: str
    actual_data_json: dict | None = None


class ConfirmRequest(BaseModel):
    """设计人提交校核（SPEC §3.2.4(4)）."""

    model_config = ConfigDict(extra="forbid")

    reason: str = Field(default="", max_length=500)


class CheckRequest(BaseModel):
    """校核人校核（SPEC §3.2.4(4)）.

    `decision` 只有 pass/reject 两值 —— 没有「跳过」：跳过会让「已确认」失去含义。
    """

    model_config = ConfigDict(extra="forbid")

    decision: Literal["pass", "reject"]
    reason: str = Field(default="", max_length=500)


# ---------------------------------------------------------------------------
# 偏差报告 (SPEC V1.4 §3.2.4)
# ---------------------------------------------------------------------------
# 4 档结论。SPEC §3.2.4(3) 定 3 档（合格/警告/不合格）；UNVERDICTABLE 是本系统
# 补充的第 4 档 —— SPEC 的偏差表内含 2 条无数值阈值规则且「以泵为例」，非泵参数
# 必然判不了。判不了 ≠ 合格，故独立成档且阻断确认。
Verdict = Literal["QUALIFIED", "WARNING", "UNQUALIFIED", "UNVERDICTABLE"]


class DeviationRowOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    parameter: str = Field(description="对比项")
    design_value: float | str | None = Field(description="设计值")
    actual_value: float | str | None = Field(description="实际值")
    unit: str = ""
    deviation_pct: float | None = Field(default=None, description="偏差 %; 不可判时 null")
    verdict: Verdict
    label: str = Field(description="结论中文: 合格/警告/不合格/不可判")
    color: str = Field(description="SPEC §3.2.4(3) 颜色: 绿色/黄色/红色/灰色")
    note: str = ""
    spec_ref: str = Field(default="", description="回溯到 SPEC §3.2.4(2) 哪一条")
    requires_recheck: bool = False
    requires_manual_check: bool = False


class DeviationReportOut(BaseModel):
    """偏差报告。`can_confirm` 是 SPEC §3.2.4(4) 的确认门禁，前端据此禁用按钮。"""

    model_config = ConfigDict(from_attributes=True)

    equipment_id: str
    tag_number: str
    actual_data_status: str
    rows: list[DeviationRowOut]
    can_confirm: bool
    blocking_reason: str = ""


__all__ = [
    "ActualDataEntry",
    "ActualDataEntryRequest",
    "ActualDataResponse",
    "CheckRequest",
    "ConfirmRequest",
    "DeviationRowOut",
    "DeviationReportOut",
]
