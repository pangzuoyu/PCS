"""P3.2 SIM-10 + P3.x SIM-14：PRO/II + Excel 导入 stateful preview/commit API。

P3.x SIM-14 D-4 等价闭环（用户 2026-09-09 裁决）：
- preview 阶段：解析后写入 sim_imports（status=PREVIEW），返回 import_id
- commit 阶段：通过 import_id 读取 sim_imports，校验未过期，落库后更新 status=COMMITTED

端点（4 个）：
- POST /api/v1/projects/{project_id}/imports/proii/preview
    multipart/form-data: file_inp + file_out → {import_id, preview}
- POST /api/v1/projects/{project_id}/imports/proii/commit
    application/json: {import_id} → StreamImportResult
- POST /api/v1/projects/{project_id}/imports/excel/preview
    multipart/form-data: file_xlsx → {import_id, preview}
- POST /api/v1/projects/{project_id}/imports/excel/commit
    application/json: {import_id} → StreamImportResult

设计要点：
- preview 写临时文件 + parse + 持久化到 sim_imports
- commit 接收 import_id（不再接收 preview_streams）→ sim_imports 读取 → 落库
- 24h 过期机制：expires_at < now → 410 Gone
- 业务错走 core.errors.PcsError envelope
- ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
"""
from __future__ import annotations

import uuid
from io import BytesIO
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.config import _Actor, current_actor, require_roles
from app.api.v1.streams import _load_project, _to_http
from app.core.errors import PcsError as CorePcsError
from app.core.upload_size_limit import enforce_upload_size
from app.db.session import get_db
from app.schemas.stream import StreamImportResult
from app.services.exceptions import PcsError
from app.services.import_service import (
    ImportService,
    generate_excel_template,
    write_temp_upload,
)

router = APIRouter(prefix="/projects/{project_id}/imports", tags=["imports"])


# ---------------------------------------------------------------------------
# 请求/响应封装
# ---------------------------------------------------------------------------


class CommitByImportIdRequest(BaseModel):
    """commit 请求体：仅含 import_id（preview 阶段已返回并持久化到 sim_imports）。"""

    import_id: uuid.UUID = Field(
        ..., description="preview 阶段返回的 import_id（sim_imports PK）"
    )


class StatefulPreviewResponse(BaseModel):
    """stateful preview 响应：import_id + 预览内容。"""

    import_id: uuid.UUID = Field(..., description="sim_imports PK；commit 阶段传入")
    preview: dict = Field(..., description="预览内容（与原 stateless preview 同结构）")


# ---------------------------------------------------------------------------
# PRO/II endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/proii/preview",
    response_model=StatefulPreviewResponse,
)
async def preview_proii(
    project_id: uuid.UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
    file_inp: UploadFile = File(..., description="PRO/II .inp 输入文件"),
    file_out: UploadFile = File(..., description="PRO/II .out 输出文件"),
) -> StatefulPreviewResponse:
    """PRO/II 双文件导入预览（stateful）：解析 → 持久化到 sim_imports（status=PREVIEW）。"""
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    project = await _load_project(db, project_id)

    inp_path: Path | None = None
    out_path: Path | None = None
    try:
        inp_bytes = await file_inp.read()
        out_bytes = await file_out.read()
        # SIM-13 D-2 闭环：单文件 10MB 上限
        enforce_upload_size(len(inp_bytes), label=".inp")
        enforce_upload_size(len(out_bytes), label=".out")
        if not inp_bytes or not out_bytes:
            raise HTTPException(status_code=400, detail="空文件")
        inp_path = write_temp_upload(inp_bytes, suffix=".inp")
        out_path = write_temp_upload(out_bytes, suffix=".out")
        try:
            result = await ImportService.preview_proii_stateful(
                db,
                project_id=project_id,
                workspace_id=project.workspace_id,
                inp_path=inp_path,
                out_path=out_path,
                source_file_name=file_inp.filename or "proii.inp",
                actor=user.user_id,
            )
        except ValueError as e:
            # parser banner / 缺文件 等结构错
            raise CorePcsError(
                code="SIM_IMPORT_PARSE_ERROR",
                message=str(e),
                status=422,
            ) from e
        except FileNotFoundError as e:
            raise CorePcsError(
                code="SIM_IMPORT_FILE_MISSING",
                message=str(e),
                status=404,
            ) from e
        await db.commit()
        return StatefulPreviewResponse(
            import_id=result["import_id"], preview=result["preview"]
        )
    finally:
        if inp_path is not None:
            inp_path.unlink(missing_ok=True)
        if out_path is not None:
            out_path.unlink(missing_ok=True)


@router.post(
    "/proii/commit",
    response_model=StreamImportResult,
)
async def commit_proii(
    project_id: uuid.UUID,
    req: CommitByImportIdRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> StreamImportResult:
    """PRO/II stateful commit：通过 import_id 读取 sim_imports，落库 + 更新状态=COMMITTED。"""
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    await _load_project(db, project_id)
    try:
        result = await ImportService.commit_proii_stateful(
            db, import_id=req.import_id, actor=user.user_id
        )
    except PcsError as e:
        raise _to_http(e) from e
    await db.commit()
    return StreamImportResult(**result)


# ---------------------------------------------------------------------------
# Excel endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/excel/preview",
    response_model=StatefulPreviewResponse,
)
async def preview_excel(
    project_id: uuid.UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
    file_xlsx: UploadFile = File(..., description="Excel .xlsx 双 Sheet"),
) -> StatefulPreviewResponse:
    """Excel 双 Sheet 导入预览（stateful）：解析 → 持久化到 sim_imports（status=PREVIEW）。"""
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    project = await _load_project(db, project_id)
    xlsx_path: Path | None = None
    try:
        content = await file_xlsx.read()
        # SIM-13 D-2 闭环：单文件 10MB 上限
        enforce_upload_size(len(content), label=".xlsx")
        if not content:
            raise HTTPException(status_code=400, detail="空文件")
        xlsx_path = write_temp_upload(content, suffix=".xlsx")
        try:
            result = await ImportService.preview_excel_stateful(
                db,
                project_id=project_id,
                workspace_id=project.workspace_id,
                path=xlsx_path,
                source_file_name=file_xlsx.filename or "streams.xlsx",
                actor=user.user_id,
            )
        except ValueError as e:
            raise CorePcsError(
                code="SIM_IMPORT_PARSE_ERROR",
                message=str(e),
                status=422,
            ) from e
        except FileNotFoundError as e:
            raise CorePcsError(
                code="SIM_IMPORT_FILE_MISSING",
                message=str(e),
                status=404,
            ) from e
        await db.commit()
        return StatefulPreviewResponse(
            import_id=result["import_id"], preview=result["preview"]
        )
    finally:
        if xlsx_path is not None:
            xlsx_path.unlink(missing_ok=True)


@router.post(
    "/excel/commit",
    response_model=StreamImportResult,
)
async def commit_excel(
    project_id: uuid.UUID,
    req: CommitByImportIdRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> StreamImportResult:
    """Excel stateful commit：通过 import_id 读取 sim_imports，落库 + 更新状态=COMMITTED。"""
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    await _load_project(db, project_id)
    try:
        result = await ImportService.commit_excel_stateful(
            db, import_id=req.import_id, actor=user.user_id
        )
    except PcsError as e:
        raise _to_http(e) from e
    await db.commit()
    return StreamImportResult(**result)


# ---------------------------------------------------------------------------
# P3.x SIM-25：Excel 导入模板下载（GET /imports/excel/template）
# ---------------------------------------------------------------------------


@router.get("/excel/template")
async def get_excel_template(
    project_id: uuid.UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> StreamingResponse:
    """Excel 导入模板下载（SIM-25；spec 附录 A）。

    返回 3 sheet 的 .xlsx：
    1. 物流列表（spec §附录 A 8 列）
    2. 组分组成（4 列）
    3. 别名表（Group / Alias / Standard；当前 17 条 COMPONENT_NAME，SIM-30 扩 50+）

    ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN / VIEWER（只读模板）。
    """
    require_roles(
        user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN", "VIEWER"
    )
    await _load_project(db, project_id)
    content = generate_excel_template()
    return StreamingResponse(
        BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": (
                "attachment; filename=pcs_stream_import_template.xlsx"
            )
        },
    )


__all__ = ["router"]