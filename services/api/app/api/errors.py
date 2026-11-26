"""Định dạng lỗi chung {error_code, message_vi, details} (docs/06 mục 4)."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

MAX_BODY_BYTES = 64 * 1024  # docs/06 mục 6


def error_body(code: str, message_vi: str, details: Any = None) -> dict[str, Any]:
    return {"error_code": code, "message_vi": message_vi, "details": details}


def install(app: FastAPI) -> None:
    from app.store.repo import Forbidden, NotFound

    @app.exception_handler(NotFound)
    async def _not_found(_: Request, exc: NotFound) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content=error_body("NOT_FOUND", "Không tìm thấy phiên sandbox (có thể đã hết hạn). Bấm \"Vào sandbox\" để tạo phiên mới."),
        )

    @app.exception_handler(Forbidden)
    async def _forbidden(_: Request, exc: Forbidden) -> JSONResponse:
        return JSONResponse(
            status_code=403,
            content=error_body("FORBIDDEN", f"Luật {exc} là luật pháp lý bị khóa, không sửa qua giao diện.", {"rule_id": str(exc)}),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = [{"loc": [str(p) for p in e["loc"]], "type": e["type"]} for e in exc.errors()]
        return JSONResponse(
            status_code=422,
            content=error_body("VALIDATION_ERROR", "Dữ liệu gửi lên không đúng định dạng.", details),
        )

    @app.middleware("http")
    async def _limit_body(request: Request, call_next):
        length = request.headers.get("content-length")
        if length and length.isdigit() and int(length) > MAX_BODY_BYTES:
            return JSONResponse(
                status_code=413,
                content=error_body("VALIDATION_ERROR", f"Dữ liệu gửi lên quá lớn (tối đa {MAX_BODY_BYTES // 1024} KB)."),
            )
        return await call_next(request)
