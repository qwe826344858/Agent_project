"""统一错误码与异常定义"""

from fastapi import Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    """应用级异常基类"""

    def __init__(self, code: str, message: str, status_code: int = 500):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


# 常用错误码
class InvalidArgumentError(AppError):
    def __init__(self, message: str = "请求参数非法"):
        super().__init__("INVALID_ARGUMENT", message, 400)


class RateLimitedError(AppError):
    def __init__(self, message: str = "请求过于频繁"):
        super().__init__("RATE_LIMITED", message, 429)


class UpstreamTimeoutError(AppError):
    def __init__(self, message: str = "上游服务超时"):
        super().__init__("UPSTREAM_TIMEOUT", message, 504)


class UpstreamError(AppError):
    def __init__(self, message: str = "上游服务异常"):
        super().__init__("UPSTREAM_ERROR", message, 502)


class InternalError(AppError):
    def __init__(self, message: str = "系统内部错误"):
        super().__init__("INTERNAL_ERROR", message, 500)


async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
    """统一异常响应格式"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
            }
        },
    )
