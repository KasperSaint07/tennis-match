"""Bot notifications for game events."""

import logging
from uuid import UUID
from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.game import GameRepository
from app.repositories.game_participant import GameParticipantRepository
from app.integrations.telegram import send_message_safe

logger = logging.getLogger(__name__)


async def notify_game_ready(
    bot: Bot,
    session: AsyncSession,
    game_id: UUID,
) -> None:
    """Notify all participants that game is ready (all slots filled)."""
    try:
        game_repo = GameRepository(session)
        participant_repo = GameParticipantRepository(session)

        game = await game_repo.get_by_id(game_id)
        participants = await participant_repo.get_active(game_id)

        text = (
            f"🎾 <b>Game Ready!</b>\n\n"
            f"📍 {game.location}\n"
            f"🕐 {game.scheduled_at.strftime('%d.%m.%Y %H:%M')}\n"
            f"👥 All {game.max_players} players joined!\n\n"
            f"✅ See you on the court!"
        )

        success_count = 0
        for participant in participants:
            if participant.user.telegram_id:
                if await send_message_safe(bot, participant.user.telegram_id, text):
                    success_count += 1

        logger.info(f"Game {game_id} ready notification sent to {success_count}/{len(participants)} players")

    except Exception as e:
        logger.error(f"Error notifying game ready for {game_id}: {e}")


async def notify_game_starting_soon(
    bot: Bot,
    session: AsyncSession,
    game_id: UUID,
    hours_until: int = 2,
) -> None:
    """Reminder notification before game starts."""
    try:
        game_repo = GameRepository(session)
        participant_repo = GameParticipantRepository(session)

        game = await game_repo.get_by_id(game_id)
        participants = await participant_repo.get_active(game_id)

        text = (
            f"⏰ <b>Game Starting Soon!</b>\n\n"
            f"🎾 {game.format.value} ({game.level.value})\n"
            f"📍 {game.location}\n"
            f"🕐 {game.scheduled_at.strftime('%d.%m.%Y %H:%M')}\n\n"
            f"👥 {len(participants)} players registered\n"
            f"💰 Price: {float(game.price_per_player)}₸\n\n"
            f"Don't be late! 🏃‍♂️"
        )

        success_count = 0
        for participant in participants:
            if participant.user.telegram_id:
                if await send_message_safe(bot, participant.user.telegram_id, text):
                    success_count += 1

        logger.info(f"Game {game_id} reminder notification sent to {success_count}/{len(participants)} players")

    except Exception as e:
        logger.error(f"Error notifying game starting for {game_id}: {e}")


async def notify_game_cancelled(
    bot: Bot,
    session: AsyncSession,
    game_id: UUID,
    reason: str = "cancelled by host",
) -> None:
    """Notification when game is cancelled."""
    try:
        game_repo = GameRepository(session)
        participant_repo = GameParticipantRepository(session)

        game = await game_repo.get_by_id(game_id)
        participants = await participant_repo.get_active(game_id)

        text = (
            f"❌ <b>Game Cancelled</b>\n\n"
            f"🎾 {game.format.value} ({game.level.value})\n"
            f"📍 {game.location}\n"
            f"🕐 {game.scheduled_at.strftime('%d.%m.%Y %H:%M')}\n\n"
            f"Reason: {reason}\n\n"
            f"💵 Full refund applied to your wallet."
        )

        success_count = 0
        for participant in participants:
            if participant.user.telegram_id:
                if await send_message_safe(bot, participant.user.telegram_id, text):
                    success_count += 1

        logger.info(f"Game {game_id} cancellation notification sent to {success_count}/{len(participants)} players")

    except Exception as e:
        logger.error(f"Error notifying game cancelled for {game_id}: {e}")


async def notify_participant_joined(
    bot: Bot,
    session: AsyncSession,
    game_id: UUID,
    new_participant_name: str,
) -> None:
    """Notify other participants that someone new joined."""
    try:
        game_repo = GameRepository(session)
        participant_repo = GameParticipantRepository(session)

        game = await game_repo.get_by_id(game_id)
        participants = await participant_repo.get_active(game_id)
        current_count = len(participants)
        max_players = game.max_players

        text = (
            f"👤 <b>New Player Joined!</b>\n\n"
            f"🎾 {game.format.value} ({game.level.value})\n"
            f"📍 {game.location}\n"
            f"🕐 {game.scheduled_at.strftime('%d.%m.%Y %H:%M')}\n\n"
            f"New player: <b>{new_participant_name}</b>\n"
            f"👥 {current_count}/{max_players} players"
        )

        if current_count == max_players:
            text += "\n\n✅ Game is now READY!"

        success_count = 0
        for participant in participants:
            if participant.user.telegram_id:
                if await send_message_safe(bot, participant.user.telegram_id, text):
                    success_count += 1

        logger.info(f"Join notification for game {game_id} sent to {success_count}/{len(participants)} players")

    except Exception as e:
        logger.error(f"Error notifying participant joined for {game_id}: {e}")


async def notify_game_checkin_open(
    bot: Bot,
    session: AsyncSession,
    game_id: UUID,
) -> None:
    """Notify participants that check-in is now open."""
    try:
        game_repo = GameRepository(session)
        participant_repo = GameParticipantRepository(session)

        game = await game_repo.get_by_id(game_id)
        participants = await participant_repo.get_active(game_id)

        text = (
            f"✔️ <b>Check-In Now Open!</b>\n\n"
            f"🎾 {game.format.value} ({game.level.value})\n"
            f"📍 {game.location}\n"
            f"🕐 {game.scheduled_at.strftime('%d.%m.%Y %H:%M')}\n\n"
            f"Please check in to confirm your attendance.\n"
            f"Use /checkin command or the bot menu."
        )

        success_count = 0
        for participant in participants:
            if participant.user.telegram_id:
                if await send_message_safe(bot, participant.user.telegram_id, text):
                    success_count += 1

        logger.info(f"Check-in open notification for game {game_id} sent to {success_count}/{len(participants)} players")

    except Exception as e:
        logger.error(f"Error notifying check-in open for {game_id}: {e}")
