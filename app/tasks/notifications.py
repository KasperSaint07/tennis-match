"""Background notification tasks."""

import logging
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.constants import LAST_CALL_MINUTES_BEFORE, REMINDER_HOURS_BEFORE
from app.db.session import async_session
from app.enums.game import GameStatus
from app.enums.participant import ParticipantStatus
from app.models.game import Game
from app.models.game_participant import GameParticipant
from app.repositories.game import GameRepository
from app.repositories.game_participant import GameParticipantRepository

logger = logging.getLogger(__name__)


async def _load_participants_with_users(db, game_id) -> list[GameParticipant]:
    """Load active participants with user relationship eager-loaded."""
    result = await db.execute(
        select(GameParticipant)
        .where(
            GameParticipant.game_id == game_id,
            GameParticipant.status == ParticipantStatus.JOINED,
        )
        .options(selectinload(GameParticipant.user))
    )
    return result.scalars().all()


async def _send_to_participants(participants: list[GameParticipant], text: str) -> int:
    """Send text to all participants. Returns number of successful sends."""
    from app.tasks.scheduler import get_task_bot
    from app.integrations.telegram import send_message_safe

    bot = get_task_bot()
    if not bot:
        return 0

    count = 0
    for participant in participants:
        user = participant.user
        if user and user.telegram_id:
            if await send_message_safe(bot, user.telegram_id, text):
                count += 1
    return count


async def send_game_reminders() -> None:
    """Send reminders for games starting in ~2 hours.

    Window: [now + 1h55m, now + 2h05m] to handle 5-min polling intervals.
    Uses game.reminded_at to avoid duplicate sends.
    """
    now = datetime.utcnow()
    window_start = now + timedelta(hours=REMINDER_HOURS_BEFORE) - timedelta(minutes=5)
    window_end = now + timedelta(hours=REMINDER_HOURS_BEFORE) + timedelta(minutes=5)

    async with async_session() as db:
        game_repo = GameRepository(db)
        games = await game_repo.get_in_time_window(
            status_list=[GameStatus.FILLING, GameStatus.READY],
            scheduled_at_gte=window_start,
            scheduled_at_lte=window_end,
        )

        for game in games:
            # Skip if already reminded
            if game.reminded_at is not None:
                continue

            try:
                participants = await _load_participants_with_users(db, game.id)

                text = (
                    f"⏰ <b>Напоминание: через 2 часа игра!</b>\n\n"
                    f"📍 {game.location}\n"
                    f"🕐 {game.scheduled_at.strftime('%d.%m.%Y %H:%M')}\n"
                    f"👥 {game.format} · {game.level}\n\n"
                    f"Не опаздывайте! 🎾"
                )

                sent = await _send_to_participants(participants, text)

                async with db.begin():
                    refreshed = await game_repo.get_for_update(game.id)
                    if refreshed and refreshed.reminded_at is None:
                        refreshed.reminded_at = now
                        db.add(refreshed)
                        await db.flush()

                logger.info(
                    "Reminder sent for game %s to %d/%d participants",
                    game.id, sent, len(participants),
                )

            except Exception:
                logger.exception("Failed to send reminder for game %s", game.id)


async def send_last_call() -> None:
    """Send last-call notification for FILLING games starting in ~1 hour.

    Window: [now + 55m, now + 65m] to handle 5-min polling intervals.
    Uses game.last_call_sent_at to avoid duplicate sends.
    """
    now = datetime.utcnow()
    window_start = now + timedelta(minutes=LAST_CALL_MINUTES_BEFORE - 5)
    window_end = now + timedelta(minutes=LAST_CALL_MINUTES_BEFORE + 5)

    async with async_session() as db:
        game_repo = GameRepository(db)
        participant_repo = GameParticipantRepository(db)

        games = await game_repo.get_in_time_window(
            status_list=[GameStatus.FILLING],
            scheduled_at_gte=window_start,
            scheduled_at_lte=window_end,
        )

        for game in games:
            # Skip if already sent last-call
            if game.last_call_sent_at is not None:
                continue

            try:
                current_players = await participant_repo.count_active(game.id)
                missing = game.max_players - current_players

                if missing <= 0:
                    continue

                participants = await _load_participants_with_users(db, game.id)

                text = (
                    f"⚠️ <b>До игры 1 час, но не хватает {missing} игрок(ов)!</b>\n\n"
                    f"📍 {game.location}\n"
                    f"🕐 {game.scheduled_at.strftime('%d.%m.%Y %H:%M')}\n\n"
                    f"Поделитесь игрой с друзьями или игра будет отменена."
                )

                sent = await _send_to_participants(participants, text)

                async with db.begin():
                    refreshed = await game_repo.get_for_update(game.id)
                    if refreshed and refreshed.last_call_sent_at is None:
                        refreshed.last_call_sent_at = now
                        db.add(refreshed)
                        await db.flush()

                logger.info(
                    "Last-call sent for game %s (%d missing) to %d/%d participants",
                    game.id, missing, sent, len(participants),
                )

            except Exception:
                logger.exception("Failed to send last-call for game %s", game.id)
