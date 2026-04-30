"""Dependency wiring helpers for Telegram bot handlers."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.game import GameRepository
from app.repositories.game_participant import GameParticipantRepository
from app.services.game import GameService
from app.services.reliability import ReliabilityService
from app.services.wallet import WalletService


def build_game_service(db: AsyncSession) -> GameService:
    """Build GameService with the same dependencies used by the HTTP API."""
    return GameService(
        db=db,
        game_repo=GameRepository(db),
        game_participant_repo=GameParticipantRepository(db),
        wallet_service=WalletService(db),
        reliability_service=ReliabilityService(db),
    )
