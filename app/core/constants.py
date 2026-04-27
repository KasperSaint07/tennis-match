"""Application constants."""

# Game duration and timing
GAME_DURATION_MINUTES = 60
CANCEL_CUTOFF_HOURS = 3
CHECKIN_WINDOW_MINUTES = 60
LAST_CALL_MINUTES_BEFORE = 60
AUTO_CANCEL_MINUTES_BEFORE = 15
REMINDER_HOURS_BEFORE = 2
NO_SHOW_DETECTION_OFFSET_MINUTES = 60

# Player classification
NEW_PLAYER_GAMES_THRESHOLD = 5

# State machine allowed transitions
from app.enums import GameStatus

ALLOWED_TRANSITIONS: dict[GameStatus, list[GameStatus]] = {
    GameStatus.CREATED: [GameStatus.FILLING],
    GameStatus.FILLING: [
        GameStatus.READY,
        GameStatus.CANCELLED,
    ],
    GameStatus.READY: [
        GameStatus.IN_PROGRESS,
        GameStatus.FILLING,  # participant left
        GameStatus.CANCELLED,
    ],
    GameStatus.IN_PROGRESS: [
        GameStatus.COMPLETED,
        GameStatus.CANCELLED,  # system only
    ],
    GameStatus.COMPLETED: [],
    GameStatus.CANCELLED: [],
}


def validate_transition(current: GameStatus, next: GameStatus) -> bool:
    """Validate if state transition is allowed."""
    return next in ALLOWED_TRANSITIONS.get(current, [])
