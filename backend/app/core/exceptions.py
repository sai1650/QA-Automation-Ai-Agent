import logging
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class ApplicationException(Exception):
    def __init__(
        self,
        message: str,
        status_code: int = HTTPStatus.INTERNAL_SERVER_ERROR,
        code: str = "application_error",
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code


def _error_response(
    status_code: int,
    code: str,
    message: str,
    details: Any = None,
) -> JSONResponse:
    error: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return JSONResponse(
        status_code=status_code,
        content={"error": error},
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApplicationException)
    async def application_exception_handler(
        _: Request, exc: ApplicationException
    ) -> JSONResponse:
        if exc.status_code >= HTTPStatus.INTERNAL_SERVER_ERROR:
            logger.error("Application error: %s", exc.code)
        else:
            logger.warning("Application error: %s", exc.code)
        return _error_response(exc.status_code, exc.code, exc.message)

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        _: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        try:
            code = HTTPStatus(exc.status_code).phrase.lower().replace(" ", "_")
        except ValueError:
            code = "http_error"
        message = exc.detail if isinstance(exc.detail, str) else "Request failed"
        return _error_response(exc.status_code, code, message)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        details = [
            {
                "location": list(error["loc"]),
                "message": error["msg"],
                "type": error["type"],
            }
            for error in exc.errors()
        ]
        return _error_response(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            "validation_error",
            "Request validation failed",
            details,
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        _: Request, exc: Exception
    ) -> JSONResponse:
        logger.error("Unhandled application exception: %s", type(exc).__name__)
        return _error_response(
            HTTPStatus.INTERNAL_SERVER_ERROR,
            "internal_server_error",
            "An unexpected error occurred",
        )
