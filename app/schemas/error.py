"""Error response schemas."""

from pydantic import BaseModel


class ErrorDetail(BaseModel):
    """Error detail information."""

    code: str
    message: str
    details: dict = {}


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: ErrorDetail
