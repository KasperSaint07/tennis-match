"""Game-related enums."""

from enum import Enum


class GameStatus(str, Enum):
    """Lifecycle status of a game."""

    CREATED = "CREATED"  # Initial state, not published
    FILLING = "FILLING"  # Accepting participants
    READY = "READY"  # All slots filled
    IN_PROGRESS = "IN_PROGRESS"  # Game is happening now
    COMPLETED = "COMPLETED"  # Game finished
    CANCELLED = "CANCELLED"  # Game was cancelled


class GameFormat(str, Enum):
    """Game format."""

    SINGLES = "SINGLES"  # 2 players
    DOUBLES = "DOUBLES"  # 4 players


class GameLevel(str, Enum):
    """Skill level for a game."""

    BEGINNER = "BEGINNER"
    INTERMEDIATE = "INTERMEDIATE"
    ADVANCED = "ADVANCED"
