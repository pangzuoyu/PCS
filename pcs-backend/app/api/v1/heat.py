"""P5-4-5 HEAT API：HTRI 导入 + 详情读 + 重量估算 3 端点契约。

按 PCS-PLAN-P5-DEVICE-EQUIPMENT.md V1.0 §Task 23 + ADR-0027 V1.0 + spec V1.2 §3.2.4：

端点：
- POST /api/v1/heat/import-htri
    multipart/form-data：
      file: HTRI Xist v6.0 输出 .txt
      project_id / workspace_id / equipment_no / equipment_name /
      tag_number / exchanger_category
      source_stream_id? （可选；提供则创建 HEAT_CALCULATED outlet）
- GET /api/v1/heat/{heat_id}
    读 HeatResult（input_json / output_json / record_hash）
- POST /api/v1/heat/{heat_id}/weight-estimate
    body: WeightEstimateInputSchema（TEMA 9th 几何参数）
    写入 output_json.total_weight_kg / weight_segments / weight_formula_ref

设计要点：
- ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN（与 psv / vessel 一致）
- 业务异常 → core.errors.PcsError envelope（422/403/404）
- 共用 heat_persist 调度（service 层 import_htri_heat_result / estimate_heat_weight）
- HTRI 文件解析在 service 层（upload 文件 → bytes → HtriParser.parse_bytes）
"""
from __future__ import annotations

import tempfile
import uuid
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.config import _Actor, current_actor, require_roles
from app.core.errors import PcsError as CorePcsError
from app.db.session import get_db
from app.services.exceptions import PcsError
from app.services.heat.heat_persist import (
    estimate_heat_weight,
    import_htri_heat_result,
)
from app.services.heat.htri_parser import HtriParseError, parse_htri
from app.services.heat.weight_estimate_service import (
    WeightEstimateInput,
    WeightEstimateResult,
)

router = APIRouter(prefix="/heat", tags=["heat"])


# ---------------------------------------------------------------------------
# 请求/响应封装
# ---------------------------------------------------------------------------


class ImportHtriResponse(BaseModel):
    """POST /heat/import-htri 响应。"""

    calc_id: uuid.UUID = Field(..., description="HeatResult.heat_exchanger_id")
    calc_type: str = Field("HEAT", description="计算类型（固定 HEAT）")
    record_hash: str = Field(..., description="16 hex 数值规范化哈希")
    project_id: uuid.UUID = Field(..., description="项目 UUID")
    equipment_no: str = Field(..., description="设备位号")
    equipment_name: str | None = Field(
        None, description="设备名（OPEN-7：补足前端 import() 后免 get() roundtrip）"
    )
    tag_number: str = Field(..., description="HeatResult 业务 tag")
    exchanger_category: str = Field(
        ..., description="SHELL_TUBE / AIR_COOL / PLATE"
    )
    duty_w: float | None = Field(None, description="热负荷 W（HTRI）")
    # OPEN-7：HTRI output_json 摘录（total_weight_kg/weight_segments 等），
    # 前端 import() 后免调 get() 即可拿重量估值（P7 UTIL 消费）
    output_json: dict[str, Any] = Field(
        default_factory=dict,
        description="HeatResult.output_json 摘录（OPEN-7 串行优化）",
    )
    outlet_stream_id: uuid.UUID | None = Field(
        None, description="出口流 UUID（source_stream_id 提供时存在）"
    )
    outlet_stream_name: str | None = Field(
        None, description="出口流名称（HEAT_EXCHANGE 后缀）"
    )


class HeatResultResponse(BaseModel):
    """GET /heat/{heat_id} 响应。"""

    calc_id: uuid.UUID = Field(..., description="HeatResult.heat_exchanger_id")
    calc_type: str = Field("HEAT", description="计算类型（固定 HEAT）")
    project_id: uuid.UUID
    workspace_id: uuid.UUID
    tag_number: str
    equipment_no: str | None
    equipment_name: str | None
    exchanger_category: str
    duty: float | None = Field(None, description="热负荷 W（P7 UTIL 消费）")
    record_hash: str | None = Field(None, description="16 hex 数值规范化哈希")
    input_json: dict[str, Any] = Field(
        default_factory=dict, description="原始 HTRI 字段（input_json 双轨）"
    )
    output_json: dict[str, Any] = Field(
        default_factory=dict,
        description="计算输出 + total_weight_kg（P7 UTIL 消费）",
    )


class WeightEstimateRequest(BaseModel):
    """POST /heat/{heat_id}/weight-estimate 请求体。"""

    tema_type: str = Field(..., description="BEM / AEM / AEL / NEN / BEM_FIXED / AEM_U_TUBE")
    shell_id_m: float = Field(..., gt=0, description="壳体内径 m")
    shell_length_m: float = Field(..., gt=0, description="壳体长度 m")
    shell_thickness_m: float = Field(..., gt=0, description="壳体壁厚 m")
    material: str = Field(
        default="carbon_steel", description="carbon_steel / SS304 / SS316 / SS316L"
    )
    head_count: int = Field(default=2, ge=0, description="封头数（默认 2）")
    head_straight_m: float = Field(default=0.025, ge=0, description="椭圆封头直边段 m")
    flange_count: int = Field(default=2, ge=0)
    flange_class: str = Field(default="300#", description="ASME B16.5 Class")
    flange_size_dn: int = Field(default=600, gt=0)
    nozzle_count: int = Field(default=4, ge=0)
    nozzle_size_dn: int = Field(default=100, gt=0)
    saddle_count: int = Field(default=2, ge=0)
    saddle_size_dn: int = Field(default=600, gt=0)
    tube_count: int = Field(default=0, ge=0)
    tube_od_m: float = Field(default=0.0, ge=0)
    tube_thickness_m: float = Field(default=0.0, ge=0)
    tube_length_m: float = Field(default=0.0, ge=0)
    baffle_count: int = Field(default=0, ge=0)
    baffle_diameter_m: float = Field(default=0.0, ge=0)
    baffle_thickness_m: float = Field(default=0.0, ge=0)


class WeightSegmentResponse(BaseModel):
    """单段重量 + 公式来源标注。"""

    weight_kg: float
    formula_ref: str


class WeightEstimateResponse(BaseModel):
    """POST /heat/{heat_id}/weight-estimate 响应。"""

    calc_id: uuid.UUID = Field(..., description="HeatResult.heat_exchanger_id")
    total_weight_kg: float = Field(
        ..., description="总重 kg（TEMA 9th 5 段 + tube/baffle/channels）"
    )
    shell_total_kg: float = Field(..., description="壳体 5 段累加 kg")
    segments: dict[str, WeightSegmentResponse] = Field(
        ...,
        description=(
            "9 段：cylinder/heads/flanges/nozzles/saddles/tube/baffle/"
            "channels/shell_total"
        ),
    )
    formula_ref: dict[str, str] = Field(
        ..., description="顶层 formula_ref（含 TEMA 版本 + 各段标准 + clause）"
    )
    record_hash: str = Field(..., description="刷新后的 record_hash（output_json 变更）")
    # OPEN-7 闭环：透传刷新后的 output_json（含 total_weight_kg / weight_segments），
    # 前端 import / weight-estimate 后免去 get() roundtrip 即可直接消费 P7 UTIL 总重。
    output_json: dict[str, Any] = Field(
        default_factory=dict,
        description="HeatResult.output_json 摘录（OPEN-7 串行优化）",
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_http(err: Exception) -> CorePcsError:
    """service PcsError → core PcsError 转换（与 psv.py / vessel.py 一致）。"""
    code = getattr(err, "code", "PCS_ERROR")
    status = getattr(err, "status", 422)
    message = str(err)
    details = getattr(err, "details", None) or None
    return CorePcsError(code=code, message=message, status=status, detail=details)


def _serialize_segment(seg) -> WeightSegmentResponse:
    return WeightSegmentResponse(weight_kg=seg.weight_kg, formula_ref=seg.formula_ref)


def _build_segments(wres: WeightEstimateResult) -> dict[str, WeightSegmentResponse]:
    return {
        "shell_cylinder": _serialize_segment(wres.shell_cylinder),
        "shell_heads": _serialize_segment(wres.shell_heads),
        "shell_flanges": _serialize_segment(wres.shell_flanges),
        "shell_nozzles": _serialize_segment(wres.shell_nozzles),
        "shell_saddles": _serialize_segment(wres.shell_saddles),
        "shell_total": _serialize_segment(wres.shell_total),
        "tube": _serialize_segment(wres.tube),
        "baffle": _serialize_segment(wres.baffle),
        "channels": _serialize_segment(wres.channels),
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/import-htri",
    status_code=201,
    response_model=ImportHtriResponse,
)
async def import_htri(
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
    file: Annotated[UploadFile, File(..., description="HTRI Xist v6.0 .txt 输出")],
    project_id: Annotated[uuid.UUID, Form(...)],
    workspace_id: Annotated[uuid.UUID, Form(...)],
    equipment_no: Annotated[str, Form(..., description="设备位号（如 E-201）")],
    tag_number: Annotated[str, Form(..., description="HeatResult.tag_number（NOT NULL）")],
    exchanger_category: Annotated[
        str, Form(..., description="SHELL_TUBE / AIR_COOL / PLATE")
    ],
    equipment_name: Annotated[str | None, Form()] = None,
    source_stream_id: Annotated[uuid.UUID | None, Form()] = None,
) -> ImportHtriResponse:
    """POST /api/v1/heat/import-htri：HTRI 文件 → HeatResult 落库。

    ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")

    # 1. 读上传文件 → 写 tmp → 解析（parse_htri 接收 Path）
    content = await file.read()
    try:
        with tempfile.NamedTemporaryFile(
            suffix=".txt", delete=False
        ) as tmp:
            tmp.write(content)
            tmp_path = Path(tmp.name)
        try:
            htri = parse_htri(tmp_path)
        finally:
            tmp_path.unlink(missing_ok=True)
    except HtriParseError as e:
        # HTRI 解析失败 → 422 HEAT_INPUT_ERROR
        raise CorePcsError(
            code="HEAT_INPUT_ERROR",
            message=f"HTRI 文件解析失败：{e}",
            status=422,
        ) from e

    # 2. service 层 import
    try:
        record, outlet = await import_htri_heat_result(
            db,
            project_id=project_id,
            workspace_id=workspace_id,
            equipment_no=equipment_no,
            equipment_name=equipment_name,
            tag_number=tag_number,
            exchanger_category=exchanger_category,
            htri=htri,
            source_stream_id=source_stream_id,
        )
    except PcsError as e:
        raise _to_http(e) from e

    # 3. 响应
    return ImportHtriResponse(
        calc_id=record.heat_exchanger_id,
        calc_type="HEAT",
        record_hash=record.record_hash,
        project_id=project_id,
        equipment_no=equipment_no,
        equipment_name=record.equipment_name,  # OPEN-7：透传，import() 后免 get()
        tag_number=tag_number,
        exchanger_category=exchanger_category,
        duty_w=record.duty,
        output_json=record.output_json or {},  # OPEN-7：透传 HTRI 摘录
        outlet_stream_id=outlet.stream_id if outlet else None,
        outlet_stream_name=outlet.stream_name if outlet else None,
    )


@router.get(
    "/{heat_id}",
    response_model=HeatResultResponse,
)
async def get_heat(
    heat_id: uuid.UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> HeatResultResponse:
    """GET /api/v1/heat/{heat_id}：HeatResult 详情（input_json / output_json / record_hash）。

    ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")

    from app.models.calc import HeatResult

    record = await db.get(HeatResult, heat_id)
    if record is None:
        raise CorePcsError(
            code="HEAT_NOT_FOUND",
            message=f"HeatResult {heat_id} 不存在",
            status=404,
        )

    return HeatResultResponse(
        calc_id=record.heat_exchanger_id,
        calc_type="HEAT",
        project_id=record.project_id,
        workspace_id=record.workspace_id,
        tag_number=record.tag_number,
        equipment_no=record.equipment_no,
        equipment_name=record.equipment_name,
        exchanger_category=record.exchanger_category,
        duty=record.duty,
        record_hash=record.record_hash,
        input_json=dict(record.input_json or {}),
        output_json=dict(record.output_json or {}),
    )


@router.post(
    "/{heat_id}/weight-estimate",
    response_model=WeightEstimateResponse,
)
async def estimate_weight_endpoint(
    heat_id: uuid.UUID,
    req: WeightEstimateRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WeightEstimateResponse:
    """POST /api/v1/heat/{heat_id}/weight-estimate：TEMA 9th 重量估算。

    写入 HeatResult.output_json.total_weight_kg / weight_segments /
    weight_formula_ref（P7 UTIL 综合消费）。

    ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")

    weight_input = WeightEstimateInput(**req.model_dump())
    try:
        record, wres = await estimate_heat_weight(
            db, heat_id=heat_id, weight_input=weight_input
        )
    except PcsError as e:
        raise _to_http(e) from e

    return WeightEstimateResponse(
        calc_id=record.heat_exchanger_id,
        total_weight_kg=wres.total.weight_kg,
        shell_total_kg=wres.shell_total.weight_kg,
        segments=_build_segments(wres),
        formula_ref=dict(wres.formula_ref),
        record_hash=record.record_hash,
        output_json=dict(record.output_json or {}),  # OPEN-7：免 get() roundtrip
    )


__all__ = ["router"]
