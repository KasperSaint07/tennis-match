#!/usr/bin/env python3
"""Telegram bot standalone runner."""

import asyncio
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    """Start the bot."""
    try:
        from app.bot.main import create_bot, start_polling

        bot, dispatcher = await create_bot()
        await start_polling(bot, dispatcher)

    except KeyboardInterrupt:
        logger.info("Bot interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
