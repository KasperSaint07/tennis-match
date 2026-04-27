"""Participant-related enums."""

from enum import Enum


class ParticipantStatus(str, Enum):
    """Status of a participant in a game."""

    JOINED = "JOINED"  # Active participant
    LEFT = "LEFT"  # Voluntarily left
    CANCELLED = "CANCELLED"  # Cancelled participation (may have penalty)
    NO_SHOW = "NO_SHOW"  # Did not check in
