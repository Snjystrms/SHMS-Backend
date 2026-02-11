from typing import Optional, Any
from pydantic import BaseModel
from datetime import datetime


class ErrorDetail(BaseModel):
    """Detailed error information."""
    field: Optional[str] = None
    message: str
    code: Optional[str] = None


class ErrorResponse(BaseModel):
    """Standardized error response format."""
    success: bool = False
    error: str
    message: str
    status_code: int
    timestamp: str
    path: Optional[str] = None
    details: Optional[list[ErrorDetail]] = None
    
    class Config:
        schema_extra = {
            "example": {
                "success": False,
                "error": "VALIDATION_ERROR",
                "message": "The provided data is invalid",
                "status_code": 422,
                "timestamp": "2026-02-11T17:42:43+05:30",
                "path": "/api/v1/auth/login",
                "details": [
                    {
                        "field": "mobile_number",
                        "message": "Mobile number is required",
                        "code": "REQUIRED_FIELD"
                    }
                ]
            }
        }
