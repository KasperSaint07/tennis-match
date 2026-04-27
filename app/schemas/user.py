"""User schemas."""

from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, Field

from app.enums.game import GameLevel


class UserResponse(BaseModel):
    """User details."""

    id: UUID
    telegram_id: int
    name: str
    level: GameLevel
    reliability_score: float
    games_played: int
    games_cancelled: int
    no_shows: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UpdateUserRequest(BaseModel):
    """Request to update user profile."""

    name: str = Field(..., min_length=1, max_length=100)
    level: GameLevel


class MeResponse(BaseModel):
    """Current user details."""

    id: UUID
    telegram_id: int
    name: str
    level: GameLevel
    reliability_score: float
    games_played: int
    games_cancelled: int
    no_shows: int

    class Config:
        from_attributes = True
