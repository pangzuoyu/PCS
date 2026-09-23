"""限制装置计算 Pydantic schema（P6-1 Task 14 / SPEC §3.2.2）。

RestrictionCalculateRequest 14 字段对齐 SPEC §3.2.2.1~4（孔板/文丘里/喷嘴/多级降压）
+ §3.2.2.6（13 列 ORM schema）+ 上下文；RestrictionCalculateResponse 回填
RestrictionResult 主键 + outlet stream。

设计要点：
- `extra='forbid'` 拒绝未知字段（V1.14 PsvCalculateRequest 历史教训；
  .wolf/cerebrum.md Do-Not-Repeat）
- 所有 Field description 含中文
- standard_profile_code 默认 ISO-5167
- design_stage 默认 BASIC（OPEN-009）

不做：
- 不实现 record_hash 算法（service 层复用 calc_lineage.compute_record_hash）
- 不实现 RestrictionEngine 计算（Task 12 已交付）
- 不实现 outlet stream（Task 13 已交付；本 schema 仅返回 outlet_stream_id）
"""
from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RestrictionCalculateRequest(BaseModel):
    """限制装置计算请求体（POST /api/v1/restriction/calculate）。

    字段对齐 SPEC §3.2.2.1~4 孔板/文丘里/喷嘴/多级降压 + §3.2.2.6 schema。

    严格模式：未知字段 → 422 ValidationError（不静默吞）。
    """

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    # 上下文（5 字段）
    project_id: uuid.UUID = Field(..., description="项目 ID")
    workspace_id: uuid.UUID = Field(..., description="工作区 ID")
    tag_number: str | None = Field(
        None,
        description="设备位号（RES- 前缀在 outlet.properties.device 补；缺省自动生成 8 hex）",
    )
    design_stage: Literal["BASIC", "DETAIL"] = Field(
        "BASIC", description="设计阶段 BASIC（基础设计）/ DETAIL（详细设计）"
    )
    standard_profile_code: str = Field(
        "ISO-5167",
        description="执行标准 profile code（ISO 5167 系列；默认 ISO-5167）",
    )

    # 装置类型 + 流体相态（2 字段）
    device_type: Literal["ORIFICE", "VENTURI", "NOZZLE", "MULTI_STAGE"] = Field(
        ...,
        description=(
            "限制装置类型：ORIFICE 孔板 / VENTURI 文丘里 / "
            "NOZZLE 喷嘴 / MULTI_STAGE 多级降压"
        ),
    )
    fluid_phase: Literal["LIQUID", "GAS"] = Field(
        "LIQUID", description="流体相态：LIQUID 液体 / GAS 气体"
    )

    # 工况（6 字段，必填核心六件套）
    D_pipe_m: float = Field(..., description="管道内径 m")
    d_solved_m: float = Field(..., description="孔径 m（求解后）")
    Re_D: float = Field(..., description="管道雷诺数")
    P1_pa: float = Field(..., description="上游绝压 Pa")
    dP_pa: float = Field(..., description="压差 Pa")
    rho1: float = Field(..., description="上游密度 kg/m³")

    # 可选修正（2 字段）
    mu: float | None = Field(None, description="动力粘度 Pa·s（备用，当前未启用）")
    stages: int = Field(1, description="降压级数（仅 MULTI_STAGE 路径生效；其他装置默认 1）")

    # 来源流（1 字段；outlet 链锚点）
    source_stream_id: uuid.UUID = Field(
        ..., description="源流 UUID（outlet.upstream_stream_id 锚点）"
    )


class RestrictionCalculateResponse(BaseModel):
    """限制装置计算响应（POST /api/v1/restriction/calculate 201）。

    回填 RestrictionResult 主键 orifice_id + 关键结果字段 + outlet stream 锚点。
    """

    model_config = ConfigDict(protected_namespaces=())

    restriction_result_id: uuid.UUID = Field(
        ..., description="RestrictionResult 主键 orifice_id（计算记录 UUID）"
    )
    tag_number: str = Field(..., description="设备位号（RES-{tag_number} 为 outlet device 名）")
    device_type: str = Field(..., description="限制装置类型 ORIFICE/VENTURI/NOZZLE/MULTI_STAGE")
    C_discharge: float = Field(..., description="流出系数（ISO 5167 C）")
    beta_ratio: float = Field(..., description="直径比 d/D")
    epsilon: float | None = Field(None, description="可膨胀性系数（液体 ≈ 1）")
    delta_P_pa: float = Field(..., description="压差 Pa")
    choked: bool = Field(..., description="是否阻塞流")
    flashing: bool = Field(False, description="是否闪蒸（液体 + 低 P1 启发式判据）")
    stages: int | None = Field(None, description="多级时级数（仅 MULTI_STAGE）")
    standard_profile_code: str = Field(..., description="执行标准 profile code（ISO 5167 系列）")
    record_hash: str = Field(..., description="16 hex 数值规范化哈希（SHA-256 截断）")
    outlet_stream_id: uuid.UUID = Field(..., description="出口流 UUID（RESTRICTION_CALCULATED）")


__all__ = ["RestrictionCalculateRequest", "RestrictionCalculateResponse"]