"""Game schemas."""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.enums.game import GameFormat, GameLevel, GameStatus
from app.enums.participant import ParticipantStatus


class CreateGameRequest(BaseModel):
    """Request to create a game."""

    location: str = Field(..., min_length=1, max_length=255)
    scheduled_at: datetime
    format: GameFormat
    level: GameLevel
    price_per_player: Decimal = Field(..., gt=0)


class UpdateGameRequest(BaseModel):
    """Request to update a game."""

    location: Optional[str] = Field(None, max_length=255)
    scheduled_at: Optional[datetime] = None
    price_per_player: Optional[Decimal] = Field(None, gt=0)


class GameParticipantResponse(BaseModel):
    """Participant in a game."""

    id: UUID
    user_id: UUID
    status: ParticipantStatus
    joined_at: datetime
    checked_in_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class GameResponse(BaseModel):
    """Game details."""

    id: UUID
    host_id: UUID
    location: str
    scheduled_at: datetime
    format: GameFormat
    level: GameLevel
    max_players: int
    price_per_player: Decimal
    status: GameStatus
    telegram_chat_link: Optional[str] = None
    participants: list[GameParticipantResponse] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class GameListResponse(BaseModel):
    """List of games with pagination."""

    items: list[GameResponse]
    total: int
    limit: int
    offset: int


class JoinGameRequest(BaseModel):
    """Request to join a game."""

    game_id: UUID


class JoinGameResponse(BaseModel):
    """Response after joining game."""

    participant_id: UUID
    game_id: UUID
    status: ParticipantStatus
    transaction_id: UUID
    amount_charged: Decimal
    wallet_balance_after: Decimal


class LeaveGameRequest(BaseModel):
    """Request to leave a game."""

    game_id: UUID


class LeaveGameResponse(BaseModel):
    """Response after leaving game."""

    status: ParticipantStatus
    penalty_applied: bool
    refund_amount: Decimal
    wallet_balance_after: Decimal


class CancelGameRequest(BaseModel):
    """Request to cancel a game."""

    game_id: UUID


class CancelGameResponse(BaseModel):
    """Response after cancelling game."""

    game_id: UUID
    status: GameStatus
    refunds_processed: int
    host_penalty_applied: bool


class CheckinRequest(BaseModel):
    """Request to check in to game."""

    game_id: UUID


class CheckinResponse(BaseModel):
    """Response after check-in."""

    game_id: UUID
    checked_in_at: datetime
