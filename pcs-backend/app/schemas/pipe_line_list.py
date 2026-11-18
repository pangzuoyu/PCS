"""管道一览表响应 schema（P10-C · T2 · TODO-159）。

## 列清单的来源

⚠️ **逐条照抄 UI SPEC §7.11.2「管道一览表列（完整）」**（43 列）⇒
⇒ **不是**前端手挑的列 ⇒ ⇒ 前端想加列 ⇒ 先改 SPEC。

后端 `piping_results` 表（`app/models/calc.py::PipingResult`）**这 43 列都有**
⇒ ⇒ 本 schema 是那张表的**投影**，不是新造的形状。

## 为什么此前没有这个端点

前端「管道一览表」页调 `GET /projects/{id}/pipe-line-list`
⇒ ⇒ **契约里根本没有这个端点** ⇒ ⇒ 真后端下 **404**
（mock 通道有 MSW handler ⇒ 一路绿灯 ⇒ 只有真后端通道抓得到）⇒ ⇒ TODO-159。
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class PipeLineListRow(BaseModel):
    """管道一览表的一行（SPEC §7.11.2 的列清单 · 逐条对应）。"""

    # —— 前 10 列（SPEC 的 BASIC 档核心）——
    seq: int = Field(..., description="序号")
    pipe_no: str = Field(..., description="管道号")
    size: str = Field(..., description="尺寸")
    material: str = Field(..., description="材料等级")
    fluid_code: str = Field(..., description="介质代号")
    fluid_name: str = Field(..., description="介质名称")
    phase: str = Field(..., description="相态")
    fluid_class: str = Field(..., description="流体分类（D/M/NORMAL）")
    toxicity: str | None = Field(None, description="毒性级别")
    pipe_class: str | None = Field(None, description="管道级别")
    # —— 绝热 / 涂漆 / 伴管 / 维持温度 ——
    insulation_code: str | None = Field(None, description="绝热代号")
    insulation_thickness: float | None = Field(None, description="绝热厚度（mm）")
    paint_code: str | None = Field(None, description="涂漆代号")
    tracing_type: str | None = Field(None, description="伴管类型（J/T/TE/NONE）")
    holding_temp: float | None = Field(None, description="维持温度（°C）")
    # —— 位置与图号 ——
    pid_ref: str = Field(..., description="PID 图号")
    start_point: str = Field(..., description="起点")
    end_point: str = Field(..., description="终点")
    # —— 操作条件 ——
    norm_oper_press: float = Field(..., description="正常操作压力（MPaG）")
    max_oper_press: float = Field(..., description="最大操作压力（MPa）")
    norm_oper_temp: float = Field(..., description="正常操作温度（°C）")
    max_oper_temp: float = Field(..., description="最大操作温度（°C）")
    # —— 备用工况 ——
    alt_norm_oper_press: float | None = Field(None, description="备用工况 · 正常操作压力")
    alt_max_oper_press: float | None = Field(None, description="备用工况 · 最大操作压力")
    alt_norm_oper_temp: float | None = Field(None, description="备用工况 · 正常操作温度")
    alt_max_oper_temp: float | None = Field(None, description="备用工况 · 最大操作温度")
    # —— 设计条件 ——
    design_pressure_mpa: float = Field(..., description="设计压力（MPaG）")
    design_vacuum: float | None = Field(None, description="设计真空")
    design_temperature_c: float = Field(..., description="设计温度（°C）")
    design_min_temperature_c: float | None = Field(None, description="设计最小温度（°C）")
    # —— 分类与试验 ——
    piping_category: str = Field(..., description="压力管道类别（GC1/GC2/GC3）")
    pressure_test_medium: str = Field(..., description="压力试验介质（WATER/AIR）")
    pressure_test_press: float = Field(..., description="压力试验压力")
    ndt_method: str | None = Field(None, description="NDT 方法（RT/UT/MT/PT/NONE）")
    ndt_ratio: float | None = Field(None, description="NDT 比例（%）")
    ndt_tech_level: str | None = Field(None, description="NDT 技术等级")
    leak_test_medium: str | None = Field(None, description="泄漏试验介质（AIR/WATER）")
    leak_test_press: float | None = Field(None, description="泄漏试验压力")
    check_class: str = Field(..., description="检查等级（I~V）")
    cleaning_method: list[str] | None = Field(None, description="清洗方法（PI/PA/DG/SO 多选）")
    stress_analysis_level: str | None = Field(None, description="应力分析级别")
    remark: str | None = Field(None, description="备注")
    # —— 审计三列（UI 的「状态 / 更新人 / 更新时间」）——
    sign_status: str = Field(..., description="记录门禁 9 态")
    updated_by: str | None = Field(None, description="更新人（用户 ID）")
    updated_at: datetime | None = Field(None, description="更新时间")
