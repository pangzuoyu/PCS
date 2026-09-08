"""P3.2 SIM-10：PRO/II + Excel 导入预览与 commit API（spec V1.6 §5.5）。

端点（4 个）：
- POST /api/v1/projects/{project_id}/imports/proii/preview
    multipart/form-data: file_inp + file_out → StreamImportPreview
- POST /api/v1/projects/{project_id}/imports/proii/commit
    application/json: {preview_streams: [...]} → StreamImportResult
- POST /api/v1/projects/{project_id}/imports/excel/preview
    multipart/form-data: file_xlsx → StreamImportPreview
- POST /api/v1/projects/{project_id}/imports/excel/commit
    application/json: {preview_streams: [...]} → StreamImportResult

设计要点：
- preview 写临时文件 + parse + 立即 unlink（不持久化）
- commit 接收 preview 内容（含 unreliable 标记）→ StreamService.create 复用
- 业务错走 core.errors.PcsError envelope
- ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
"""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.config import _Actor, current_actor, require_roles
from app.api.v1.streams import _load_project, _to_http
from app.core.errors import PcsError as CorePcsError
from app.db.session import get_db
from app.schemas.stream import StreamImportPreview, StreamImportResult
from app.services.exceptions import PcsError
from app.services.import_service import ImportService, write_temp_upload

router = APIRouter(prefix="/projects/{project_id}/imports", tags=["imports"])


# ---------------------------------------------------------------------------
# 请求/响应封装
# ---------------------------------------------------------------------------


class CommitRequest(BaseModel):
    """commit 请求体：preview 阶段返回的 preview_streams 列表。

    workspace_id 可选（缺省取 Project.workspace_id）。
    """

    workspace_id: uuid.UUID | None = Field(
        None, description="所属工作区 ID（缺省取 Project.workspace_id）"
    )
    preview_streams: list[dict[str, Any]] = Field(
        ..., min_length=1, description="preview 阶段返回的 preview_streams 列表"
    )


# ---------------------------------------------------------------------------
# PRO/II endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/proii/preview",
    response_model=StreamImportPreview,
)
async def preview_proii(
    project_id: uuid.UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
    file_inp: UploadFile = File(..., description="PRO/II .inp 输入文件"),
    file_out: UploadFile = File(..., description="PRO/II .out 输出文件"),
) -> StreamImportPreview:
    """PRO/II 双文件导入预览：parser + ConflictResolver（不落库）。"""
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    await _load_project(db, project_id)

    inp_path: Path | None = None
    out_path: Path | None = None
    try:
        inp_bytes = await file_inp.read()
        out_bytes = await file_out.read()
        if not inp_bytes or not out_bytes:
            raise HTTPException(status_code=400, detail="空文件")
        inp_path = write_temp_upload(inp_bytes, suffix=".inp")
        out_path = write_temp_upload(out_bytes, suffix=".out")
        try:
            preview_dict = ImportService.preview_proii(inp_path, out_path)
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
        return StreamImportPreview(**preview_dict)
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
    req: CommitRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> StreamImportResult:
    """PRO/II preview → 落库（复用 StreamService.create）。"""
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    project = await _load_project(db, project_id)
    workspace_id = req.workspace_id or project.workspace_id
    try:
        result = await ImportService.commit_proii(
            db,
            project_id=project_id,
            workspace_id=workspace_id,
            preview_streams=req.preview_streams,
            actor=user.user_id,
        )
    except PcsError as e:
        raise _to_http(e) from e
    return StreamImportResult(**result)


# ---------------------------------------------------------------------------
# Excel endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/excel/preview",
    response_model=StreamImportPreview,
)
async def preview_excel(
    project_id: uuid.UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
    file_xlsx: UploadFile = File(..., description="Excel .xlsx 双 Sheet"),
) -> StreamImportPreview:
    """Excel 双 Sheet 导入预览。"""
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    await _load_project(db, project_id)
    xlsx_path: Path | None = None
    try:
        content = await file_xlsx.read()
        if not content:
            raise HTTPException(status_code=400, detail="空文件")
        xlsx_path = write_temp_upload(content, suffix=".xlsx")
        try:
            preview_dict = ImportService.preview_excel(xlsx_path)
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
        return StreamImportPreview(**preview_dict)
    finally:
        if xlsx_path is not None:
            xlsx_path.unlink(missing_ok=True)


@router.post(
    "/excel/commit",
    response_model=StreamImportResult,
)
async def commit_excel(
    project_id: uuid.UUID,
    req: CommitRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> StreamImportResult:
    """Excel preview → 落库。"""
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    project = await _load_project(db, project_id)
    workspace_id = req.workspace_id or project.workspace_id
    try:
        result = await ImportService.commit_excel(
            db,
            project_id=project_id,
            workspace_id=workspace_id,
            preview_streams=req.preview_streams,
            actor=user.user_id,
        )
    except PcsError as e:
        raise _to_http(e) from e
    return StreamImportResult(**result)


__all__ = ["router"]