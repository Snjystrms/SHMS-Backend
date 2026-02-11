from fastapi import HTTPException, status, Request
from fastapi.responses import JSONResponse
from datetime import datetime
from typing import Optional, Any


class AppException(HTTPException):
    """Base application exception with standardized error format."""
    
    def __init__(
        self,
        status_code: int,
        error: str,
        message: str,
        details: Optional[list] = None,
        headers: Optional[dict] = None
    ):
        self.status_code = status_code
        self.error = error
        self.message = message
        self.details = details
        super().__init__(status_code=status_code, detail=message, headers=headers)


# Common Error Types
class ValidationException(AppException):
    """Validation error (422)."""
    def __init__(self, message: str = "Validation failed", details: Optional[list] = None):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error="VALIDATION_ERROR",
            message=message,
            details=details
        )


class UnauthorizedException(AppException):
    """Unauthorized error (401)."""
    def __init__(self, message: str = "Authentication required"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error="UNAUTHORIZED",
            message=message,
            headers={"WWW-Authenticate": "Bearer"}
        )


class ForbiddenException(AppException):
    """Forbidden error (403)."""
    def __init__(self, message: str = "Access forbidden"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            error="FORBIDDEN",
            message=message
        )


class NotFoundException(AppException):
    """Not found error (404)."""
    def __init__(self, message: str = "Resource not found", resource: Optional[str] = None):
        if resource:
            message = f"{resource} not found"
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            error="NOT_FOUND",
            message=message
        )


class ConflictException(AppException):
    """Conflict error (409)."""
    def __init__(self, message: str = "Resource already exists"):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            error="CONFLICT",
            message=message
        )


class BadRequestException(AppException):
    """Bad request error (400)."""
    def __init__(self, message: str = "Bad request"):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            error="BAD_REQUEST",
            message=message
        )


class InternalServerException(AppException):
    """Internal server error (500)."""
    def __init__(self, message: str = "Internal server error"):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error="INTERNAL_SERVER_ERROR",
            message=message
        )


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """Global exception handler for AppException."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.error,
            "message": exc.message,
            "status_code": exc.status_code,
            "timestamp": datetime.now().isoformat(),
            "path": str(request.url.path),
            "details": exc.details
        }
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Global exception handler for standard HTTPException."""
    # Map status codes to error types
    error_map = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        422: "VALIDATION_ERROR",
        500: "INTERNAL_SERVER_ERROR",
    }
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": error_map.get(exc.status_code, "ERROR"),
            "message": exc.detail,
            "status_code": exc.status_code,
            "timestamp": datetime.now().isoformat(),
            "path": str(request.url.path),
            "details": None
        }
    )
