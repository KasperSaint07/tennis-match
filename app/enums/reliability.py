"""Reliability-related enums."""

from enum import Enum


class ReliabilityEventType(str, Enum):
    """Type of event affecting user reliability score."""

    GAME_COMPLETED = "GAME_COMPLETED"  # +1 score
    LATE_CANCEL = "LATE_CANCEL"  # -2 score (cancel < 3 hours before)
    NO_SHOW = "NO_SHOW"  # -4 score (didn't check in)
    HOST_FAILURE = "HOST_FAILURE"  # -5 score (host cancelled < 3 hours before)


# Score delta for each event type
SCORE_DELTAS = {
    ReliabilityEventType.GAME_COMPLETED: 1,
    ReliabilityEventType.LATE_CANCEL: -2,
    ReliabilityEventType.NO_SHOW: -4,
    ReliabilityEventType.HOST_FAILURE: -5,
}
