"""Background tasks for game status transitions."""

import logging
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.constants import GAME_DURATION_MINUTES
from app.db.session import async_session
from app.enums.game import GameStatus
from app.enums.participant import ParticipantStatus
from app.enums.reliability import ReliabilityEventType
from app.models.game import Game
from app.models.game_participant import GameParticipant
from app.repositories.game import GameRepository
from app.repositories.game_participant import GameParticipantRepository
from app.repositories.wallet import WalletRepository
from app.repositories.transaction import TransactionRepository
from app.services.game import GameService
from app.services.reliability import ReliabilityService
from app.services.wallet import WalletService

logger = logging.getLogger(__name__)


def _build_game_service(db) -> GameService:
    """Construct a GameService with all dependencies wired."""
    wallet_service = WalletService(db)
    reliability_service = ReliabilityService(db)
    return GameService(
        db=db,
        game_repo=GameRepository(db),
        game_participant_repo=GameParticipantRepository(db),
        wallet_service=wallet_service,
        reliability_service=reliability_service,
    )


async def _load_participants_with_users(db, game_id) -> list[GameParticipant]:
    """Load active participants with their user relationship eager-loaded."""
    result = await db.execute(
        select(GameParticipant)
        .where(
            GameParticipant.game_id == game_id,
            GameParticipant.status == ParticipantStatus.JOINED,
        )
        .options(selectinload(GameParticipant.user))
    )
    return result.scalars().all()


async def _notify_participants(game: Game, participants: list[GameParticipant], message: str) -> None:
    """Send a Telegram message to all participants who have a telegram_id."""
    from app.tasks.scheduler import get_task_bot
    from app.integrations.telegram import send_message_safe

    bot = get_task_bot()
    if not bot:
        return

    for participant in participants:
        user = participant.user
        if user and user.telegram_id:
            await send_message_safe(bot, user.telegram_id, message)


async def start_games() -> None:
    """Transition READY games to IN_PROGRESS when scheduled_at is reached."""
    now = datetime.utcnow()
    async with async_session() as db:
        game_repo = GameRepository(db)
        games = await game_repo.get_by_status_and_time(
            status=GameStatus.READY,
            scheduled_at_lte=now,
        )

        for game in games:
            try:
                async with db.begin():
                    locked = await game_repo.get_for_update(game.id)
                    if not locked or locked.status != GameStatus.READY:
                        continue
                    locked.status = GameStatus.IN_PROGRESS
                    db.add(locked)
                    await db.flush()

                participants = await _load_participants_with_users(db, game.id)
                await _notify_participants(
                    game,
                    participants,
                    f"🎾 <b>Игра началась!</b>\n\n📍 {game.location}\n\nУдачи на корте!",
                )
                logger.info("Game %s started (IN_PROGRESS)", game.id)

            except Exception:
                logger.exception("Failed to start game %s", game.id)


async def complete_games() -> None:
    """Transition IN_PROGRESS games to COMPLETED after game duration."""
    cutoff = datetime.utcnow() - timedelta(minutes=GAME_DURATION_MINUTES)
    async with async_session() as db:
        game_repo = GameRepository(db)
        games = await game_repo.get_by_status_and_time(
            status=GameStatus.IN_PROGRESS,
            scheduled_at_lte=cutoff,
        )

        for game in games:
            try:
                async with db.begin():
                    locked = await game_repo.get_for_update(game.id)
                    if not locked or locked.status != GameStatus.IN_PROGRESS:
                        continue
                    locked.status = GameStatus.COMPLETED
                    db.add(locked)
                    await db.flush()

                logger.info("Game %s completed", game.id)

            except Exception:
                logger.exception("Failed to complete game %s", game.id)


async def detect_no_shows() -> None:
    """Detect no-shows for recently completed games (60–70 min after start)."""
    now = datetime.utcnow()
    window_start = now - timedelta(minutes=70)
    window_end = now - timedelta(minutes=60)

    async with async_session() as db:
        game_repo = GameRepository(db)
        participant_repo = GameParticipantRepository(db)
        reliability_service = ReliabilityService(db)

        games = await game_repo.get_completed_in_window(start=window_start, end=window_end)

        for game in games:
            try:
                participants = await _load_participants_with_users(db, game.id)

                for participant in participants:
                    try:
                        async with db.begin():
                            if participant.checked_in_at is None:
                                participant.status = ParticipantStatus.NO_SHOW
                                db.add(participant)
                                await db.flush()
                                await reliability_service.apply_event(
                                    user_id=participant.user_id,
                                    game_id=game.id,
                                    event_type=ReliabilityEventType.NO_SHOW,
                                )
                                logger.info(
                                    "NO_SHOW recorded for user %s in game %s",
                                    participant.user_id,
                                    game.id,
                                )
                            else:
                                await reliability_service.apply_event(
                                    user_id=participant.user_id,
                                    game_id=game.id,
                                    event_type=ReliabilityEventType.GAME_COMPLETED,
                                )
                    except Exception:
                        logger.exception(
                            "Failed to process no-show for participant %s in game %s",
                            participant.id,
                            game.id,
                        )

            except Exception:
                logger.exception("Failed to process no-shows for game %s", game.id)


async def auto_cancel_unfilled() -> None:
    """Auto-cancel FILLING games that won't reach min players before start."""
    cutoff = datetime.utcnow() + timedelta(minutes=15)

    async with async_session() as db:
        game_repo = GameRepository(db)
        games = await game_repo.get_unfilled_before(scheduled_at_lte=cutoff)

        for game in games:
            try:
                # Load participants before cancel for notification
                participants = await _load_participants_with_users(db, game.id)

                game_service = _build_game_service(db)
                await game_service.cancel_game_by_system(game_id=game.id)

                await _notify_participants(
                    game,
                    participants,
                    (
                        f"❌ <b>Игра отменена</b>\n\n"
                        f"📍 {game.location}\n"
                        f"🕐 {game.scheduled_at.strftime('%d.%m.%Y %H:%M')}\n\n"
                        f"Не хватило участников. Деньги возвращены на баланс."
                    ),
                )
                logger.info("Game %s auto-cancelled (unfilled)", game.id)

            except Exception:
                logger.exception("Failed to auto-cancel game %s", game.id)
