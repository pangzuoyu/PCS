"""调节阀 Cv 计算 Pydantic schema（P6-1 Task 10 / SPEC §3.2.1）。

CvCalculateRequest 21+ 字段对齐 SPEC §3.2.1.1~1.4（液体/气体/阻塞流/噪音）+ §3.2.1.6
（21 列 ORM schema）；CvCalculateResponse 回填 CvResult 主键 + outlet stream。

设计要点：
- `extra='forbid'` 拒绝未知字段（V1.14 PsvCalculateRequest 历史教训；
  .wolf/cerebrum.md Do-Not-Repeat）
- 所有 Field description 含中文
- standard_profile_code 默认 API-60534（ADR-0028 V1.1）
- design_stage 默认 BASIC（OPEN-009）

不做：
- 不实现 record_hash 算法（service 层复用 calc_lineage.compute_record_hash）
- 不实现 CvEngine 计算（Task 8 已交付）
- 不实现 outlet stream（Task 9 已交付；本 schema 仅返回 outlet_stream_id）
"""
from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CvCalculateRequest(BaseModel):
    """调节阀 Cv 计算请求体（POST /api/v1/cv/calculate）。

    字段对齐 SPEC §3.2.1.1~1.4 液体/气体/阻塞流/噪音 + §3.2.1.6 schema。

    严格模式：未知字段 → 422 ValidationError（不静默吞）。
    """

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    # 上下文（5 字段）
    project_id: uuid.UUID = Field(..., description="项目 ID")
    workspace_id: uuid.UUID = Field(..., description="工作区 ID")
    tag_number: str | None = Field(
        None,
        description="设备位号（CV- 前缀在 outlet.properties.device 补；缺省自动生成 8 hex）",
    )
    design_stage: Literal["BASIC", "DETAIL"] = Field(
        "BASIC", description="设计阶段 BASIC（基础设计）/ DETAIL（详细设计）"
    )
    standard_profile_code: str = Field(
        "API-60534",
        description="执行标准 profile code（ADR-0028 V1.1；默认 API-60534）",
    )

    # 流体相态（1 字段，必填）
    fluid_phase: Literal["LIQUID", "GAS", "TWO_PHASE"] = Field(
        ..., description="流体相态：LIQUID 液体 / GAS 气体 / TWO_PHASE 两相流"
    )

    # 工况（10 字段，必填核心三项 + 工况扩展）
    Q_m3h: float = Field(..., description="体积流量 m³/h（LIQUID 路径用 SI 实流量）")
    P1_pa: float = Field(..., description="阀前绝压 Pa")
    P2_pa: float = Field(..., description="阀后绝压 Pa")
    T1_k: float = Field(..., description="入口温度 K")
    SG: float | None = Field(None, description="液体相对密度（SG = ρ/1000，LIQUID 必填）")
    rho: float | None = Field(None, description="密度 kg/m³（与 SG 二选一）")
    M: float | None = Field(None, description="分子量 kg/kmol（GAS 必填）")
    Z: float | None = Field(None, description="压缩因子（GAS 必填）")
    gamma: float | None = Field(None, description="气体绝热指数 Cp/Cv（GAS 必填）")
    dP_bar: float | None = Field(
        None, description="压差 bar（LIQUID 专用；GAS 路径用 dP_pa）"
    )
    dP_pa: float | None = Field(
        None, description="压差 Pa（GAS 专用；LIQUID 路径用 dP_bar）"
    )

    # 阀门修正（5 字段；默认值覆盖 IEC 60534-2-1 典型）
    FL: float | None = Field(0.9, description="液体临界压力比恢复系数（IEC 60534-2-1 §5.2）")
    FF: float | None = Field(0.96, description="阀门几何系数（典型 0.96）")
    Pv: float | None = Field(None, description="蒸汽压 Pa（LIQUID 阻塞判定用）")
    Pc: float | None = Field(None, description="临界压力 Pa（LIQUID 阻塞判定用）")
    xT: float | None = Field(0.7, description="临界压差比（GAS 阻塞判定用，典型 0.4~0.8）")

    # 来源流（1 字段；outlet 链锚点）
    source_stream_id: uuid.UUID = Field(
        ..., description="源流 UUID（outlet.upstream_stream_id 锚点）"
    )


class CvCalculateResponse(BaseModel):
    """调节阀 Cv 计算响应（POST /api/v1/cv/calculate 201）。

    回填 CvResult 主键 + 关键结果字段 + outlet stream 锚点。
    """

    model_config = ConfigDict(protected_namespaces=())

    cv_result_id: uuid.UUID = Field(..., description="CvResult 主键 cv_id（计算记录 UUID）")
    tag_number: str = Field(..., description="设备位号（CV-{tag_number} 为 outlet device 名）")
    fluid_phase: str = Field(..., description="流体相态 LIQUID/GAS/TWO_PHASE")
    Cv_calculated: float = Field(..., description="计算 Cv（流量系数，US 单位制 GPM/psi）")
    Cv_selected: float | None = Field(None, description="圆整到标准系列的 Cv")
    choked: bool = Field(..., description="是否阻塞流（IEC 60534-2-1 §5.2.1/§6.3）")
    cavitation: bool = Field(False, description="液体空化标记（IEC 60534-2-1 §5.3，LIQUID 路径）")
    flashing: bool = Field(False, description="液体闪蒸标记（IEC 60534-2-1 §5.4，LIQUID 路径）")
    noise_sil_db: float | None = Field(None, description="简化法噪音估算 dB（IEC 60534-8-3）")
    standard_profile_code: str = Field(..., description="执行标准 profile code（ADR-0028）")
    design_stage: str = Field(..., description="设计阶段 BASIC/DETAIL（OPEN-009）")
    record_hash: str = Field(..., description="16 hex 数值规范化哈希（SHA-256 截断）")
    outlet_stream_id: uuid.UUID = Field(..., description="出口流 UUID（DEVICE_CALCULATED）")


__all__ = ["CvCalculateRequest", "CvCalculateResponse"]
