"""Start command handler."""

import logging
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command

from app.db.session import AsyncSessionLocal
from app.repositories.user import UserRepository
from app.repositories.wallet import WalletRepository
from app.core.exceptions import AppException, TelegramVerificationFailedException
from app.bot.keyboards import get_main_menu_keyboard
from app.integrations.telegram import send_message

logger = logging.getLogger(__name__)

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    """Handle /start command. Authenticate and show main menu."""
    user = message.from_user
    telegram_id = user.id

    async with AsyncSessionLocal() as session:
        try:
            # Get or create user
            user_repo = UserRepository(session)
            db_user = await user_repo.get_by_telegram_id(telegram_id)

            if db_user is None:
                db_user = await user_repo.create(
                    telegram_id=telegram_id,
                    name=user.first_name,
                    level="BEGINNER",
                )

            # Ensure wallet exists (handles both new and existing users)
            wallet_repo = WalletRepository(session)
            await wallet_repo.get_or_create_for_user(db_user.id)

            await session.commit()

            # Welcome message
            await send_message(
                message.bot,
                message.chat.id,
                (
                    f"👋 Welcome, {user.first_name}!\n\n"
                    f"🎾 TennisMatch — find and join tennis games in Astana.\n\n"
                    f"What would you like to do?"
                ),
                reply_markup=get_main_menu_keyboard(),
            )

            logger.info(f"User {telegram_id} ({user.first_name}) started bot")

        except TelegramVerificationFailedException:
            await send_message(
                message.bot,
                message.chat.id,
                "❌ Authentication failed. Please try again.",
            )
            logger.warning(f"Auth failed for user {telegram_id}")

        except AppException as e:
            await send_message(
                message.bot,
                message.chat.id,
                f"❌ Error: {e.message}",
            )
            logger.error(f"App error for user {telegram_id}: {e}")

        except Exception as e:
            await send_message(
                message.bot,
                message.chat.id,
                "❌ Something went wrong. Please try again later.",
            )
            logger.error(f"Unexpected error for user {telegram_id}: {e}")


@router.callback_query(F.data == "menu:main")
async def menu_main(callback_query) -> None:
    """Handle back to main menu."""
    await callback_query.message.edit_text(
        (
            f"🎾 TennisMatch Main Menu\n\n"
            f"What would you like to do?"
        ),
        reply_markup=get_main_menu_keyboard(),
    )
    await callback_query.answer()
