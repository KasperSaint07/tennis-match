"""Exception hierarchy for TennisMatch API."""

from enum import Enum
from typing import Any, Optional


class ErrorCode(str, Enum):
    """Standard error codes."""

    # Auth errors
    UNAUTHORIZED = "UNAUTHORIZED"
    INVALID_TOKEN = "INVALID_TOKEN"
    TELEGRAM_VERIFICATION_FAILED = "TELEGRAM_VERIFICATION_FAILED"

    # Not found
    NOT_FOUND = "NOT_FOUND"
    USER_NOT_FOUND = "USER_NOT_FOUND"
    GAME_NOT_FOUND = "GAME_NOT_FOUND"
    WALLET_NOT_FOUND = "WALLET_NOT_FOUND"
    TRANSACTION_NOT_FOUND = "TRANSACTION_NOT_FOUND"
    PARTICIPANT_NOT_FOUND = "PARTICIPANT_NOT_FOUND"

    # Validation
    INVALID_INPUT = "INVALID_INPUT"
    VALIDATION_ERROR = "VALIDATION_ERROR"

    # Game errors
    GAME_NOT_AVAILABLE = "GAME_NOT_AVAILABLE"
    GAME_ALREADY_JOINED = "GAME_ALREADY_JOINED"
    GAME_FULL = "GAME_FULL"
    GAME_TIME_CONFLICT = "GAME_TIME_CONFLICT"
    GAME_LEVEL_MISMATCH = "GAME_LEVEL_MISMATCH"
    GAME_CANNOT_LEAVE = "GAME_CANNOT_LEAVE"
    GAME_CANNOT_CANCEL = "GAME_CANNOT_CANCEL"
    GAME_PAST_CUTOFF = "GAME_PAST_CUTOFF"
    GAME_INVALID_TRANSITION = "GAME_INVALID_TRANSITION"

    # Wallet errors
    INSUFFICIENT_BALANCE = "INSUFFICIENT_BALANCE"
    WALLET_OPERATION_FAILED = "WALLET_OPERATION_FAILED"

    # Server errors
    INTERNAL_ERROR = "INTERNAL_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"


class AppException(Exception):
    """Base application exception."""

    def __init__(
        self,
        message: str,
        code: ErrorCode = ErrorCode.INTERNAL_ERROR,
        status_code: int = 500,
        details: Optional[dict[str, Any]] = None,
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class UnauthorizedException(AppException):
    """Raised when user is not authenticated."""

    def __init__(self, message: str = "Not authenticated"):
        super().__init__(
            message=message,
            code=ErrorCode.UNAUTHORIZED,
            status_code=401,
        )


class InvalidTokenException(AppException):
    """Raised when JWT token is invalid."""

    def __init__(self, message: str = "Invalid token"):
        super().__init__(
            message=message,
            code=ErrorCode.INVALID_TOKEN,
            status_code=401,
        )


class TelegramVerificationFailedException(AppException):
    """Raised when Telegram data verification fails."""

    def __init__(self, message: str = "Telegram verification failed"):
        super().__init__(
            message=message,
            code=ErrorCode.TELEGRAM_VERIFICATION_FAILED,
            status_code=401,
        )


class NotFoundException(AppException):
    """Base exception for not found errors."""

    def __init__(
        self,
        message: str,
        code: ErrorCode = ErrorCode.NOT_FOUND,
    ):
        super().__init__(
            message=message,
            code=code,
            status_code=404,
        )


class UserNotFoundException(NotFoundException):
    """Raised when user is not found."""

    def __init__(self, user_id: str = None):
        message = f"User {user_id} not found" if user_id else "User not found"
        super().__init__(
            message=message,
            code=ErrorCode.USER_NOT_FOUND,
        )


class GameNotFoundException(NotFoundException):
    """Raised when game is not found."""

    def __init__(self, game_id: str = None):
        message = f"Game {game_id} not found" if game_id else "Game not found"
        super().__init__(
            message=message,
            code=ErrorCode.GAME_NOT_FOUND,
        )


class WalletNotFoundException(NotFoundException):
    """Raised when wallet is not found."""

    def __init__(self, wallet_id: str = None):
        message = f"Wallet {wallet_id} not found" if wallet_id else "Wallet not found"
        super().__init__(
            message=message,
            code=ErrorCode.WALLET_NOT_FOUND,
        )


class TransactionNotFoundException(NotFoundException):
    """Raised when transaction is not found."""

    def __init__(self, transaction_id: str = None):
        message = (
            f"Transaction {transaction_id} not found"
            if transaction_id
            else "Transaction not found"
        )
        super().__init__(
            message=message,
            code=ErrorCode.TRANSACTION_NOT_FOUND,
        )


class ParticipantNotFoundException(NotFoundException):
    """Raised when participant is not found."""

    def __init__(self, participant_id: str = None):
        message = (
            f"Participant {participant_id} not found"
            if participant_id
            else "Participant not found"
        )
        super().__init__(
            message=message,
            code=ErrorCode.PARTICIPANT_NOT_FOUND,
        )


class BadRequestException(AppException):
    """Raised for invalid input data."""

    def __init__(self, message: str, details: dict = None):
        super().__init__(
            message=message,
            code=ErrorCode.INVALID_INPUT,
            status_code=400,
            details=details,
        )


class ValidationException(AppException):
    """Raised for validation errors."""

    def __init__(self, message: str, details: dict = None):
        super().__init__(
            message=message,
            code=ErrorCode.VALIDATION_ERROR,
            status_code=422,
            details=details,
        )


class GameNotAvailableException(AppException):
    """Raised when game status doesn't allow the operation."""

    def __init__(self, message: str = "Game is not available"):
        super().__init__(
            message=message,
            code=ErrorCode.GAME_NOT_AVAILABLE,
            status_code=409,
        )


class GameAlreadyJoinedException(AppException):
    """Raised when user already joined the game."""

    def __init__(self, message: str = "Already joined this game"):
        super().__init__(
            message=message,
            code=ErrorCode.GAME_ALREADY_JOINED,
            status_code=409,
        )


class GameFullException(AppException):
    """Raised when game has no free slots."""

    def __init__(self, message: str = "No free slots in game"):
        super().__init__(
            message=message,
            code=ErrorCode.GAME_FULL,
            status_code=409,
        )


class GameTimeConflictException(AppException):
    """Raised when user has time conflict with another game."""

    def __init__(self, message: str = "Time conflict with another game"):
        super().__init__(
            message=message,
            code=ErrorCode.GAME_TIME_CONFLICT,
            status_code=409,
        )


class GameLevelMismatchException(AppException):
    """Raised when user level doesn't match game level."""

    def __init__(self, message: str = "Your level doesn't match game level"):
        super().__init__(
            message=message,
            code=ErrorCode.GAME_LEVEL_MISMATCH,
            status_code=409,
        )


class GameCannotLeaveException(AppException):
    """Raised when user cannot leave game (e.g., host)."""

    def __init__(self, message: str = "Cannot leave this game"):
        super().__init__(
            message=message,
            code=ErrorCode.GAME_CANNOT_LEAVE,
            status_code=409,
        )


class GameCannotCancelException(AppException):
    """Raised when game cannot be cancelled."""

    def __init__(self, message: str = "Cannot cancel this game"):
        super().__init__(
            message=message,
            code=ErrorCode.GAME_CANNOT_CANCEL,
            status_code=409,
        )


class GamePastCutoffException(AppException):
    """Raised when game operation is past cutoff time."""

    def __init__(self, message: str = "Operation is past cutoff time"):
        super().__init__(
            message=message,
            code=ErrorCode.GAME_PAST_CUTOFF,
            status_code=409,
        )


class GameInvalidTransitionException(AppException):
    """Raised when game status transition is invalid."""

    def __init__(self, message: str = "Invalid game status transition"):
        super().__init__(
            message=message,
            code=ErrorCode.GAME_INVALID_TRANSITION,
            status_code=409,
        )


class InsufficientBalanceException(AppException):
    """Raised when wallet has insufficient balance."""

    def __init__(self, message: str = "Insufficient balance"):
        super().__init__(
            message=message,
            code=ErrorCode.INSUFFICIENT_BALANCE,
            status_code=409,
        )


class WalletOperationFailedException(AppException):
    """Raised when wallet operation fails."""

    def __init__(self, message: str = "Wallet operation failed"):
        super().__init__(
            message=message,
            code=ErrorCode.WALLET_OPERATION_FAILED,
            status_code=500,
        )


class DatabaseException(AppException):
    """Raised for database errors."""

    def __init__(self, message: str = "Database error"):
        super().__init__(
            message=message,
            code=ErrorCode.DATABASE_ERROR,
            status_code=500,
        )
