from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException


class PcsError(Exception):
    def __init__(
        self, code: str, message: str, status: int = 400, detail: Any = None
    ):
        self.code = code
        self.message = message
        self.status = status
        self.detail = detail


class ErrorResponse(BaseModel):
    code: str
    message: str
    detail: Any = None
    trace_id: str


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(PcsError)
    async def _pcs(request: Request, exc: PcsError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status,
            content=ErrorResponse(
                code=exc.code,
                message=exc.message,
                detail=exc.detail,
                trace_id=getattr(request.state, "trace_id", ""),
            ).model_dump(),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                code=f"HTTP_{exc.status_code}",
                message=str(exc.detail),
                detail=None,
                trace_id=getattr(request.state, "trace_id", ""),
            ).model_dump(),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=ErrorResponse(
                code="VALIDATION_ERROR",
                message="request validation failed",
                detail=jsonable_encoder(exc.errors()),
                trace_id=getattr(request.state, "trace_id", ""),
            ).model_dump(),
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                code="INTERNAL_ERROR",
                message="internal server error",
                detail=None,
                trace_id=getattr(request.state, "trace_id", ""),
            ).model_dump(),
        )
