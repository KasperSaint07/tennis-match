"""Games browse handler."""

import logging
from datetime import datetime, date
from uuid import UUID
from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.repositories.user import UserRepository
from app.repositories.game import GameRepository
from app.repositories.game_participant import GameParticipantRepository
from app.core.exceptions import AppException, NotFoundException
from app.bot.keyboards import get_games_list_keyboard, get_game_details_keyboard
from app.integrations.telegram import send_message, edit_message_text

logger = logging.getLogger(__name__)

router = Router()

GAMES_PAGE_SIZE = 10


def _format_game_text(game, current_players: int, max_players: int, is_joined: bool = False) -> str:
    """Format game details as text."""
    level = game.level.value
    format_type = game.format.value
    status = game.status.value
    participants_info = f"{current_players}/{max_players} players"

    if is_joined:
        participants_info += " ✅ (you are joined)"

    scheduled = game.scheduled_at.strftime("%d.%m %H:%M")
    price = float(game.price_per_player)

    return (
        f"🎾 <b>{level} {format_type}</b>\n"
        f"📍 {game.location}\n"
        f"🕐 {scheduled}\n"
        f"👥 {participants_info}\n"
        f"💰 {price}₸ per player\n"
        f"📊 {status}"
    )


@router.callback_query(F.data.startswith("games:list:"))
async def games_list(callback_query: CallbackQuery) -> None:
    """Browse available games with pagination."""
    offset = int(callback_query.data.split(":")[-1])
    user = callback_query.from_user
    telegram_id = user.id

    async with AsyncSessionLocal() as session:
        try:
            game_repo = GameRepository(session)
            participant_repo = GameParticipantRepository(session)

            # Get available games
            games, total = await game_repo.get_available(limit=GAMES_PAGE_SIZE, offset=offset)

            if not games:
                await edit_message_text(
                    callback_query.bot,
                    callback_query.message.chat.id,
                    callback_query.message.message_id,
                    "📭 No games available right now.\n\nCheck back later! ⏰",
                    reply_markup=get_games_list_keyboard(offset, False),
                )
                await callback_query.answer()
                return

            # Format games list
            text = "🎾 <b>Available Games</b>\n\n"
            for i, game in enumerate(games, 1):
                current = await participant_repo.count_active(game.id)
                max_players = game.max_players
                text += f"{i}. /{i} {game.level.value} {game.format.value} — {game.scheduled_at.strftime('%d.%m %H:%M')}\n"

            text += f"\n💡 Select a game to see details or join.\n\nShowing {offset + 1}-{min(offset + GAMES_PAGE_SIZE, total)} of {total}"

            # Create inline buttons for each game
            buttons = []
            for i, game in enumerate(games, 1):
                buttons.append([
                    {
                        "text": f"{i}. {game.level.value}",
                        "callback_data": f"game:show:{game.id}",
                    }
                ])

            # Add pagination
            has_more = (offset + GAMES_PAGE_SIZE) < total

            await edit_message_text(
                callback_query.bot,
                callback_query.message.chat.id,
                callback_query.message.message_id,
                text,
                reply_markup=get_games_list_keyboard(offset, has_more),
            )
            await callback_query.answer()

        except AppException as e:
            await callback_query.answer(f"❌ {e.message}", show_alert=True)
            logger.error(f"App error browsing games for {telegram_id}: {e}")
        except Exception as e:
            await callback_query.answer("❌ Error loading games", show_alert=True)
            logger.error(f"Unexpected error browsing games for {telegram_id}: {e}")


@router.callback_query(F.data.startswith("game:show:"))
async def game_show(callback_query: CallbackQuery) -> None:
    """Show game details."""
    game_id = UUID(callback_query.data.split(":")[-1])
    user = callback_query.from_user
    telegram_id = user.id

    async with AsyncSessionLocal() as session:
        try:
            game_repo = GameRepository(session)
            participant_repo = GameParticipantRepository(session)
            user_repo = UserRepository(session)

            # Get game
            game = await game_repo.get_by_id(game_id)
            current_players = await participant_repo.count_active(game_id)
            max_players = game.max_players

            # Check if current user is joined
            db_user = await user_repo.get_by_telegram_id(telegram_id)
            participant = await participant_repo.get_by_user_and_game(db_user.id, game_id)
            is_joined = participant is not None

            # Get participants
            participants = await participant_repo.get_active(game_id)

            # Format message
            text = _format_game_text(game, current_players, max_players, is_joined)

            if participants:
                text += "\n\n👥 <b>Players:</b>\n"
                for p in participants:
                    text += f"• {p.user.first_name or 'User'}\n"

            await edit_message_text(
                callback_query.bot,
                callback_query.message.chat.id,
                callback_query.message.message_id,
                text,
                reply_markup=get_game_details_keyboard(game_id, is_joined),
            )
            await callback_query.answer()

        except NotFoundException:
            await callback_query.answer("❌ Game not found", show_alert=True)
        except AppException as e:
            await callback_query.answer(f"❌ {e.message}", show_alert=True)
            logger.error(f"App error showing game {game_id} for {telegram_id}: {e}")
        except Exception as e:
            await callback_query.answer("❌ Error loading game", show_alert=True)
            logger.error(f"Unexpected error showing game {game_id} for {telegram_id}: {e}")
