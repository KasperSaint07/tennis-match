"""Telegram bot initialization and startup."""

import logging
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.core.config import get_settings
from app.bot.handlers import (
    start,
    games,
    join,
    create,
    wallet,
)

logger = logging.getLogger(__name__)


async def set_commands(bot: Bot) -> None:
    """Set bot commands in menu."""
    commands = [
        BotCommand(command="start", description="Start the bot"),
        BotCommand(command="menu", description="Open main menu"),
    ]
    await bot.set_my_commands(commands)


async def setup_dispatcher(dispatcher: Dispatcher) -> None:
    """Register all routers."""
    dispatcher.include_router(start.router)
    dispatcher.include_router(games.router)
    dispatcher.include_router(join.router)
    dispatcher.include_router(create.router)
    dispatcher.include_router(wallet.router)


async def create_bot() -> tuple[Bot, Dispatcher]:
    """Create bot and dispatcher instances."""
    settings = get_settings()

    if not settings.telegram_bot_token:
        raise ValueError("TELEGRAM_BOT_TOKEN not configured")

    # Create bot
    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML,
        ),
    )

    # Create dispatcher
    dispatcher = Dispatcher()

    # Setup
    await set_commands(bot)
    await setup_dispatcher(dispatcher)

    logger.info("Bot initialized successfully")

    return bot, dispatcher


async def start_polling(bot: Bot, dispatcher: Dispatcher) -> None:
    """Start bot polling."""
    logger.info("Starting bot polling...")
    try:
        await dispatcher.start_polling(bot)
    except Exception as e:
        logger.error(f"Error in polling: {e}")
    finally:
        await bot.session.close()
        logger.info("Bot session closed")
