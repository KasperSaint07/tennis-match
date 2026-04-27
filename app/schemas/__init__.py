"""Schemas module."""

from app.schemas.auth import AuthResponse, TelegramAuthRequest, TokenRefreshRequest
from app.schemas.error import ErrorDetail, ErrorResponse
from app.schemas.game import (
    CancelGameRequest,
    CancelGameResponse,
    CheckinRequest,
    CheckinResponse,
    CreateGameRequest,
    GameListResponse,
    GameParticipantResponse,
    GameResponse,
    JoinGameRequest,
    JoinGameResponse,
    LeaveGameRequest,
    LeaveGameResponse,
    UpdateGameRequest,
)
from app.schemas.user import MeResponse, UpdateUserRequest, UserResponse
from app.schemas.wallet import (
    DepositRequest,
    DepositResponse,
    TransactionResponse,
    WalletResponse,
)

__all__ = [
    "TelegramAuthRequest",
    "AuthResponse",
    "TokenRefreshRequest",
    "ErrorDetail",
    "ErrorResponse",
    "UserResponse",
    "MeResponse",
    "UpdateUserRequest",
    "GameResponse",
    "GameParticipantResponse",
    "GameListResponse",
    "CreateGameRequest",
    "UpdateGameRequest",
    "JoinGameRequest",
    "JoinGameResponse",
    "LeaveGameRequest",
    "LeaveGameResponse",
    "CancelGameRequest",
    "CancelGameResponse",
    "CheckinRequest",
    "CheckinResponse",
    "WalletResponse",
    "TransactionResponse",
    "DepositRequest",
    "DepositResponse",
]
