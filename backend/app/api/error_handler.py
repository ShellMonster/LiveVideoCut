"""Global exception handlers for the FastAPI app."""

import logging
import traceback

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.services.asr_errors import (
    ASRTimeoutError,
    AuthError,
    NoSpeechError,
    TranscriptionError,
)

logger = logging.getLogger(__name__)


def _error_body(code: str, message: str, **extra) -> dict:
    body: dict = {"error": {"code": code, "message": message}}
    if extra:
        body["error"].update(extra)
    return body


def register_error_handlers(app: FastAPI) -> None:
    """Register global exception handlers on the FastAPI app."""

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        details = [
            {
                "loc": err.get("loc", []),
                "msg": err.get("msg", ""),
                "type": err.get("type", ""),
            }
            for err in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content=_error_body(
                "VALIDATION_ERROR",
                "请求参数校验失败",
                details=details,
            ),
        )

    @app.exception_handler(AuthError)
    async def auth_error_handler(
        _request: Request, exc: AuthError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=401,
            content=_error_body("AUTH_ERROR", str(exc)),
        )

    @app.exception_handler(ASRTimeoutError)
    async def timeout_error_handler(
        _request: Request, exc: ASRTimeoutError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=504,
            content=_error_body("TIMEOUT_ERROR", str(exc)),
        )

    @app.exception_handler(NoSpeechError)
    async def no_speech_error_handler(
        _request: Request, exc: NoSpeechError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=_error_body("NO_SPEECH", str(exc)),
        )

    @app.exception_handler(TranscriptionError)
    async def transcription_error_handler(
        _request: Request, exc: TranscriptionError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=502,
            content=_error_body("TRANSCRIPTION_ERROR", str(exc)),
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(
        _request: Request, exc: ValueError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content=_error_body("BAD_REQUEST", str(exc)),
        )

    @app.exception_handler(FileNotFoundError)
    async def file_not_found_handler(
        _request: Request, exc: FileNotFoundError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content=_error_body("NOT_FOUND", "请求的资源不存在"),
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(
        _request: Request, exc: Exception
    ) -> JSONResponse:
        logger.error(
            "Unhandled exception: %s\n%s",
            exc,
            traceback.format_exc(),
        )
        return JSONResponse(
            status_code=500,
            content=_error_body("INTERNAL_ERROR", "服务内部错误，请稍后重试"),
        )
