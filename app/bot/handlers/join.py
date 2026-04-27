"""Join game handler."""

import logging
from uuid import UUID
from decimal import Decimal
from aiogram import Router, F
from aiogram.types import CallbackQuery, User as TelegramUser
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.repositories.user import UserRepository
from app.repositories.game import GameRepository
from app.services.game import GameService
from app.services.wallet import WalletService
from app.services.reliability import ReliabilityService
from app.core.exceptions import (
    AppException,
    NotFoundException,
    InsufficientBalanceException,
    GameNotAvailableException,
    GameAlreadyJoinedException,
)
from app.bot.keyboards import get_main_menu_keyboard, get_games_list_keyboard
from app.integrations.telegram import edit_message_text

logger = logging.getLogger(__name__)

router = Router()


@router.callback_query(F.data.startswith("game:join:"))
async def game_join(callback_query: CallbackQuery, user: TelegramUser) -> None:
    """Handle join game."""
    game_id = UUID(callback_query.data.split(":")[-1])
    telegram_id = user.id

    await callback_query.answer("⏳ Processing...", show_alert=False)

    async with AsyncSessionLocal() as session:
        try:
            # Get current user
            user_repo = UserRepository(session)
            db_user = await user_repo.get_by_telegram_id(telegram_id)

            # Initialize services
            game_service = GameService(db=session)
            wallet_service = WalletService(db=session)
            reliability_service = ReliabilityService(db=session)

            # Join game
            result = await game_service.join_game(db_user.id, game_id)

            # Format success message
            text = (
                f"✅ <b>Successfully joined!</b>\n\n"
                f"💰 Charged: {float(result.amount_charged)}₸\n"
                f"💳 Balance: {float(result.wallet_balance_after)}₸\n\n"
                f"🎾 Game status: {result.game_status}\n"
                f"👥 Players: {result.current_players}/{result.max_players}\n\n"
                f"📍 {result.location}\n"
                f"🕐 {result.scheduled_at.strftime('%d.%m.%Y %H:%M')}"
            )

            await edit_message_text(
                callback_query.bot,
                callback_query.message.chat.id,
                callback_query.message.message_id,
                text,
                reply_markup=get_games_list_keyboard(0, True),
            )

            logger.info(f"User {telegram_id} joined game {game_id}")

        except InsufficientBalanceException:
            await edit_message_text(
                callback_query.bot,
                callback_query.message.chat.id,
                callback_query.message.message_id,
                (
                    "❌ <b>Insufficient balance</b>\n\n"
                    "You don't have enough money to join.\n"
                    "💰 Deposit money to your wallet first."
                ),
                reply_markup=get_games_list_keyboard(0, True),
            )
            logger.warning(f"User {telegram_id} insufficient balance for game {game_id}")

        except GameNotAvailableException:
            await edit_message_text(
                callback_query.bot,
                callback_query.message.chat.id,
                callback_query.message.message_id,
                (
                    "❌ <b>Game full</b>\n\n"
                    "All slots are taken.\n"
                    "🎾 Browse other games."
                ),
                reply_markup=get_games_list_keyboard(0, True),
            )
            logger.warning(f"User {telegram_id} tried to join full game {game_id}")

        except GameAlreadyJoinedException:
            await edit_message_text(
                callback_query.bot,
                callback_query.message.chat.id,
                callback_query.message.message_id,
                (
                    "⚠️ <b>Already joined</b>\n\n"
                    "You're already a participant in this game."
                ),
                reply_markup=get_games_list_keyboard(0, True),
            )
            logger.warning(f"User {telegram_id} already in game {game_id}")

        except NotFoundException as e:
            await edit_message_text(
                callback_query.bot,
                callback_query.message.chat.id,
                callback_query.message.message_id,
                f"❌ <b>Not found</b>\n\n{e.message}",
                reply_markup=get_games_list_keyboard(0, True),
            )
            logger.warning(f"Not found error for user {telegram_id}: {e}")

        except AppException as e:
            await edit_message_text(
                callback_query.bot,
                callback_query.message.chat.id,
                callback_query.message.message_id,
                f"❌ <b>Error</b>\n\n{e.message}",
                reply_markup=get_games_list_keyboard(0, True),
            )
            logger.error(f"App error for user {telegram_id} joining game {game_id}: {e}")

        except Exception as e:
            await edit_message_text(
                callback_query.bot,
                callback_query.message.chat.id,
                callback_query.message.message_id,
                "❌ <b>Something went wrong</b>\n\nTry again later.",
                reply_markup=get_games_list_keyboard(0, True),
            )
            logger.error(f"Unexpected error for user {telegram_id} joining game {game_id}: {e}")


@router.callback_query(F.data.startswith("game:leave:"))
async def game_leave(callback_query: CallbackQuery, user: TelegramUser) -> None:
    """Handle leave game."""
    game_id = UUID(callback_query.data.split(":")[-1])
    telegram_id = user.id

    await callback_query.answer("⏳ Processing...", show_alert=False)

    async with AsyncSessionLocal() as session:
        try:
            user_repo = UserRepository(session)
            db_user = await user_repo.get_by_telegram_id(telegram_id)

            game_service = GameService(db=session)
            result = await game_service.leave_game(db_user.id, game_id)

            refund_text = ""
            if result.refund_amount > 0:
                refund_text = f"💵 Refund: {float(result.refund_amount)}₸\n"

            penalty_text = ""
            if result.penalty_applied:
                penalty_text = "⚠️ Late cancellation penalty applied\n"

            text = (
                f"✅ <b>Left the game</b>\n\n"
                f"{refund_text}"
                f"{penalty_text}"
                f"💳 Balance: {float(result.wallet_balance_after)}₸"
            )

            await edit_message_text(
                callback_query.bot,
                callback_query.message.chat.id,
                callback_query.message.message_id,
                text,
                reply_markup=get_games_list_keyboard(0, True),
            )

            logger.info(f"User {telegram_id} left game {game_id}")

        except AppException as e:
            await callback_query.answer(f"❌ {e.message}", show_alert=True)
            logger.error(f"App error for user {telegram_id} leaving game {game_id}: {e}")
        except Exception as e:
            await callback_query.answer("❌ Error leaving game", show_alert=True)
            logger.error(f"Unexpected error for user {telegram_id} leaving game {game_id}: {e}")


@router.callback_query(F.data.startswith("game:checkin:"))
async def game_checkin(callback_query: CallbackQuery, user: TelegramUser) -> None:
    """Handle check-in."""
    game_id = UUID(callback_query.data.split(":")[-1])
    telegram_id = user.id

    await callback_query.answer("⏳ Processing...", show_alert=False)

    async with AsyncSessionLocal() as session:
        try:
            user_repo = UserRepository(session)
            db_user = await user_repo.get_by_telegram_id(telegram_id)

            game_service = GameService(db=session)
            checked_in_at = await game_service.checkin(db_user.id, game_id)

            text = (
                f"✔️ <b>Checked in successfully!</b>\n\n"
                f"⏰ Checked in at: {checked_in_at.strftime('%H:%M')}\n\n"
                f"See you on the court! 🎾"
            )

            await edit_message_text(
                callback_query.bot,
                callback_query.message.chat.id,
                callback_query.message.message_id,
                text,
                reply_markup=get_games_list_keyboard(0, True),
            )

            logger.info(f"User {telegram_id} checked in for game {game_id}")

        except AppException as e:
            await callback_query.answer(f"❌ {e.message}", show_alert=True)
            logger.error(f"App error for user {telegram_id} checking in for game {game_id}: {e}")
        except Exception as e:
            await callback_query.answer("❌ Error checking in", show_alert=True)
            logger.error(f"Unexpected error for user {telegram_id} checking in for game {game_id}: {e}")
