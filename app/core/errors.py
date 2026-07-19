import logging
import re
from collections.abc import Mapping
from enum import StrEnum
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.datastructures import (
    Headers,
    MutableHeaders,
)
from starlette.exceptions import (
    HTTPException as StarletteHTTPException,
)
from starlette.types import (
    ASGIApp,
    Message,
    Receive,
    Scope,
    Send,
)

logger = logging.getLogger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"

_SAFE_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


class ErrorCode(StrEnum):
    """对客户端保持稳定的公共错误代码。"""

    BAD_REQUEST = "bad_request"
    UNAUTHORIZED = "unauthorized"
    FORBIDDEN = "forbidden"
    NOT_FOUND = "not_found"
    METHOD_NOT_ALLOWED = "method_not_allowed"
    CONFLICT = "conflict"
    HTTP_ERROR = "http_error"
    VALIDATION_ERROR = "validation_error"
    INTERNAL_ERROR = "internal_error"
    CHAT_SESSION_NOT_FOUND = "chat_session_not_found"
    AI_SERVICE_UNAVAILABLE = "ai_service_unavailable"


class AppError(Exception):
    """带有稳定公共响应信息的应用错误。"""

    def __init__(
        self,
        *,
        status_code: int,
        code: ErrorCode,
        detail: str,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        super().__init__(detail)

        self.status_code = status_code
        self.code = code
        self.detail = detail
        self.headers = dict(headers or {})


def _safe_or_generated_request_id(
    candidate: str | None,
) -> str:
    if candidate is not None and _SAFE_REQUEST_ID_PATTERN.fullmatch(candidate):
        return candidate

    return uuid4().hex


class RequestIdMiddleware:
    """为 HTTP 请求设置标识；只包装响应，不捕获异常。"""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_headers = Headers(scope=scope)
        request_id = _safe_or_generated_request_id(
            request_headers.get(REQUEST_ID_HEADER)
        )

        state = scope.setdefault("state", {})
        state["request_id"] = request_id

        async def send_with_request_id(
            message: Message,
        ) -> None:
            if message["type"] == "http.response.start":
                response_headers = MutableHeaders(scope=message)
                response_headers[REQUEST_ID_HEADER] = request_id

            await send(message)

        await self.app(
            scope,
            receive,
            send_with_request_id,
        )


def _request_id(request: Request) -> str:
    current = getattr(
        request.state,
        "request_id",
        None,
    )

    if isinstance(current, str):
        return current

    request_id = _safe_or_generated_request_id(request.headers.get(REQUEST_ID_HEADER))

    request.state.request_id = request_id

    return request_id


def _safe_route(request: Request) -> str:
    route = request.scope.get("route")
    route_path = getattr(route, "path", None)

    if isinstance(route_path, str):
        return route_path

    return "<unmatched>"


def _response(
    *,
    status_code: int,
    code: ErrorCode,
    detail: Any,
    request_id: str,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    response_headers = dict(headers or {})
    response_headers[REQUEST_ID_HEADER] = request_id

    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(
            {
                "code": code.value,
                "detail": detail,
                "request_id": request_id,
            }
        ),
        headers=response_headers,
    )


def _http_error_code(
    status_code: int,
) -> ErrorCode:
    return {
        status.HTTP_400_BAD_REQUEST: (ErrorCode.BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: (ErrorCode.UNAUTHORIZED),
        status.HTTP_403_FORBIDDEN: (ErrorCode.FORBIDDEN),
        status.HTTP_404_NOT_FOUND: (ErrorCode.NOT_FOUND),
        status.HTTP_405_METHOD_NOT_ALLOWED: (ErrorCode.METHOD_NOT_ALLOWED),
        status.HTTP_409_CONFLICT: (ErrorCode.CONFLICT),
    }.get(
        status_code,
        ErrorCode.HTTP_ERROR,
    )


def _public_validation_detail(
    error: RequestValidationError,
) -> list[dict[str, Any]]:
    public_errors: list[dict[str, Any]] = []

    for validation_error in error.errors():
        public_error = {
            "type": validation_error["type"],
            "loc": list(validation_error["loc"]),
            "msg": validation_error["msg"],
        }

        public_errors.append(public_error)

    return public_errors


async def app_error_handler(
    request: Request,
    error: Exception,
) -> JSONResponse:
    if not isinstance(error, AppError):
        raise TypeError("app_error_handler requires AppError.")

    request_id = _request_id(request)

    logger.debug(
        (
            "Handled application error "
            "request_id=%s method=%s route=%s "
            "status_code=%s code=%s"
        ),
        request_id,
        request.method,
        _safe_route(request),
        error.status_code,
        error.code.value,
    )

    return _response(
        status_code=error.status_code,
        code=error.code,
        detail=error.detail,
        request_id=request_id,
        headers=error.headers,
    )


async def http_exception_handler(
    request: Request,
    error: Exception,
) -> JSONResponse:
    if not isinstance(
        error,
        StarletteHTTPException,
    ):
        raise TypeError("http_exception_handler requires StarletteHTTPException.")

    request_id = _request_id(request)

    return _response(
        status_code=error.status_code,
        code=_http_error_code(error.status_code),
        detail=error.detail,
        request_id=request_id,
        headers=error.headers,
    )


async def validation_error_handler(
    request: Request,
    error: Exception,
) -> JSONResponse:
    if not isinstance(
        error,
        RequestValidationError,
    ):
        raise TypeError("validation_error_handler requires RequestValidationError.")

    request_id = _request_id(request)

    return _response(
        status_code=(status.HTTP_422_UNPROCESSABLE_ENTITY),
        code=ErrorCode.VALIDATION_ERROR,
        detail=_public_validation_detail(error),
        request_id=request_id,
    )


async def unexpected_error_handler(
    request: Request,
    error: Exception,
) -> JSONResponse:
    request_id = _request_id(request)

    logger.error(
        ("Unhandled request error request_id=%s method=%s route=%s exception_type=%s"),
        request_id,
        request.method,
        _safe_route(request),
        type(error).__name__,
        exc_info=(
            type(error),
            error,
            error.__traceback__,
        ),
    )

    return _response(
        status_code=(status.HTTP_500_INTERNAL_SERVER_ERROR),
        code=ErrorCode.INTERNAL_ERROR,
        detail="Internal server error.",
        request_id=request_id,
    )


def register_exception_handlers(
    application: FastAPI,
) -> None:
    """为应用注册统一公共错误响应。"""

    application.add_exception_handler(
        AppError,
        app_error_handler,
    )

    application.add_exception_handler(
        StarletteHTTPException,
        http_exception_handler,
    )

    application.add_exception_handler(
        RequestValidationError,
        validation_error_handler,
    )

    application.add_exception_handler(
        Exception,
        unexpected_error_handler,
    )
