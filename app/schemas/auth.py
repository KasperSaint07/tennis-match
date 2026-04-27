"""Authentication schemas."""

from uuid import UUID

from pydantic import BaseModel, Field


class TelegramAuthRequest(BaseModel):
    """Request to authenticate with Telegram."""

    init_data: str = Field(..., min_length=1)


class AuthResponse(BaseModel):
    """Response after authentication."""

    access_token: str
    token_type: str = "bearer"
    user_id: UUID


class TokenRefreshRequest(BaseModel):
    """Request to refresh token."""

    token: str
