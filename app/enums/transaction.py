"""Transaction-related enums."""

from enum import Enum


class TransactionType(str, Enum):
    """Type of financial transaction."""

    DEPOSIT = "DEPOSIT"  # Balance top-up
    JOIN_PAYMENT = "JOIN_PAYMENT"  # Debit for joining game
    REFUND = "REFUND"  # Credit for cancelled/left game
    PENALTY = "PENALTY"  # Debit for late cancel / no-show


class TransactionStatus(str, Enum):
    """Status of a transaction."""

    PENDING = "PENDING"  # Processing
    COMPLETED = "COMPLETED"  # Success
    FAILED = "FAILED"  # Error
