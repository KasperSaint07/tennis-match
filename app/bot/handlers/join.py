"""Join, leave, and check-in handlers."""

import logging
from uuid import UUID

from aiogram import F, Router
from aiogram.types import CallbackQuery

from app.bot.deps import build_game_service
from app.bot.keyboards import get_games_list_keyboard
from app.core.exceptions import (
    AppException,
    GameAlreadyJoinedException,
    GameNotAvailableException,
    InsufficientBalanceException,
    NotFoundException,
)
from app.db.session import AsyncSessionLocal
from app.integrations.telegram import edit_message_text
from app.repositories.game import GameRepository
from app.repositories.game_participant import GameParticipantRepository
from app.repositories.user import UserRepository

logger = logging.getLogger(__name__)

router = Router()


@router.callback_query(F.data.startswith("game:join:"))
async def game_join(callback_query: CallbackQuery) -> None:
    """Handle join game."""
    game_id = UUID(callback_query.data.split(":")[-1])
    telegram_id = callback_query.from_user.id

    await callback_query.answer("Processing...", show_alert=False)

    async with AsyncSessionLocal() as session:
        try:
            user_repo = UserRepository(session)
            db_user = await user_repo.get_by_telegram_id(telegram_id)
            if db_user is None:
                raise NotFoundException("User not found")

            game_service = build_game_service(session)
            result = await game_service.join_game(db_user, game_id)

            game = await GameRepository(session).get_by_id(game_id)
            current_players = await GameParticipantRepository(session).count_active(game_id)

            text = (
                "<b>Successfully joined!</b>\n\n"
                f"Charged: {float(result['amount_charged'])} KZT\n"
                f"Balance: {float(result['wallet_balance_after'])} KZT\n\n"
                f"Game status: {game.status.value}\n"
                f"Players: {current_players}/{game.max_players}\n\n"
                f"{game.location}\n"
                f"{game.scheduled_at.strftime('%d.%m.%Y %H:%M')}"
            )

            await edit_message_text(
                callback_query.bot,
                callback_query.message.chat.id,
                callback_query.message.message_id,
                text,
                reply_markup=get_games_list_keyboard(0, True),
            )

            logger.info("User %s joined game %s", telegram_id, game_id)

        except InsufficientBalanceException:
            await edit_message_text(
                callback_query.bot,
                callback_query.message.chat.id,
                callback_query.message.message_id,
                (
                    "<b>Insufficient balance</b>\n\n"
                    "You don't have enough money to join.\n"
                    "Deposit money to your wallet first."
                ),
                reply_markup=get_games_list_keyboard(0, True),
            )
            logger.warning("User %s insufficient balance for game %s", telegram_id, game_id)

        except GameNotAvailableException:
            await edit_message_text(
                callback_query.bot,
                callback_query.message.chat.id,
                callback_query.message.message_id,
                (
                    "<b>Game unavailable</b>\n\n"
                    "This game is no longer available.\n"
                    "Browse other games."
                ),
                reply_markup=get_games_list_keyboard(0, True),
            )
            logger.warning("User %s tried to join unavailable game %s", telegram_id, game_id)

        except GameAlreadyJoinedException:
            await edit_message_text(
                callback_query.bot,
                callback_query.message.chat.id,
                callback_query.message.message_id,
                (
                    "<b>Already joined</b>\n\n"
                    "You're already a participant in this game."
                ),
                reply_markup=get_games_list_keyboard(0, True),
            )
            logger.warning("User %s already in game %s", telegram_id, game_id)

        except NotFoundException as exc:
            await edit_message_text(
                callback_query.bot,
                callback_query.message.chat.id,
                callback_query.message.message_id,
                f"<b>Not found</b>\n\n{exc.message}",
                reply_markup=get_games_list_keyboard(0, True),
            )
            logger.warning("Not found error for user %s: %s", telegram_id, exc)

        except AppException as exc:
            await edit_message_text(
                callback_query.bot,
                callback_query.message.chat.id,
                callback_query.message.message_id,
                f"<b>Error</b>\n\n{exc.message}",
                reply_markup=get_games_list_keyboard(0, True),
            )
            logger.error("App error for user %s joining game %s: %s", telegram_id, game_id, exc)

        except Exception as exc:
            await edit_message_text(
                callback_query.bot,
                callback_query.message.chat.id,
                callback_query.message.message_id,
                "<b>Something went wrong</b>\n\nTry again later.",
                reply_markup=get_games_list_keyboard(0, True),
            )
            logger.exception("Unexpected error for user %s joining game %s: %s", telegram_id, game_id, exc)


@router.callback_query(F.data.startswith("game:leave:"))
async def game_leave(callback_query: CallbackQuery) -> None:
    """Handle leave game."""
    game_id = UUID(callback_query.data.split(":")[-1])
    telegram_id = callback_query.from_user.id

    await callback_query.answer("Processing...", show_alert=False)

    async with AsyncSessionLocal() as session:
        try:
            db_user = await UserRepository(session).get_by_telegram_id(telegram_id)
            if db_user is None:
                raise NotFoundException("User not found")

            result = await build_game_service(session).leave_game(db_user, game_id)

            refund_text = ""
            if result["refund_amount"] > 0:
                refund_text = f"Refund: {float(result['refund_amount'])} KZT\n"

            penalty_text = ""
            if result["penalty_applied"]:
                penalty_text = "Late cancellation penalty applied\n"

            text = (
                "<b>Left the game</b>\n\n"
                f"{refund_text}"
                f"{penalty_text}"
                f"Balance: {float(result['wallet_balance_after'])} KZT"
            )

            await edit_message_text(
                callback_query.bot,
                callback_query.message.chat.id,
                callback_query.message.message_id,
                text,
                reply_markup=get_games_list_keyboard(0, True),
            )

            logger.info("User %s left game %s", telegram_id, game_id)

        except AppException as exc:
            await callback_query.answer(f"Error: {exc.message}", show_alert=True)
            logger.error("App error for user %s leaving game %s: %s", telegram_id, game_id, exc)
        except Exception as exc:
            await callback_query.answer("Error leaving game", show_alert=True)
            logger.exception("Unexpected error for user %s leaving game %s: %s", telegram_id, game_id, exc)


@router.callback_query(F.data.startswith("game:checkin:"))
async def game_checkin(callback_query: CallbackQuery) -> None:
    """Handle check-in."""
    game_id = UUID(callback_query.data.split(":")[-1])
    telegram_id = callback_query.from_user.id

    await callback_query.answer("Processing...", show_alert=False)

    async with AsyncSessionLocal() as session:
        try:
            db_user = await UserRepository(session).get_by_telegram_id(telegram_id)
            if db_user is None:
                raise NotFoundException("User not found")

            checked_in_at = await build_game_service(session).checkin(db_user, game_id)

            text = (
                "<b>Checked in successfully!</b>\n\n"
                f"Checked in at: {checked_in_at.strftime('%H:%M')}\n\n"
                "See you on the court!"
            )

            await edit_message_text(
                callback_query.bot,
                callback_query.message.chat.id,
                callback_query.message.message_id,
                text,
                reply_markup=get_games_list_keyboard(0, True),
            )

            logger.info("User %s checked in for game %s", telegram_id, game_id)

        except AppException as exc:
            await callback_query.answer(f"Error: {exc.message}", show_alert=True)
            logger.error("App error for user %s checking in for game %s: %s", telegram_id, game_id, exc)
        except Exception as exc:
            await callback_query.answer("Error checking in", show_alert=True)
            logger.exception("Unexpected error for user %s checking in for game %s: %s", telegram_id, game_id, exc)
