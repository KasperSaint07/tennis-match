"""Telegram bot integration helpers."""

import logging
from aiogram import Bot
from aiogram.types import Message, InlineKeyboardMarkup
from aiogram.exceptions import TelegramBadRequest, TelegramAPIError

logger = logging.getLogger(__name__)


async def send_message(
    bot: Bot,
    chat_id: int,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> Message | None:
    """Send a message to user. Returns Message or None if failed."""
    try:
        return await bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode="HTML",
        )
    except TelegramBadRequest as e:
        logger.warning(f"Failed to send message to {chat_id}: {e}")
        return None
    except TelegramAPIError as e:
        logger.error(f"Telegram API error for {chat_id}: {e}")
        return None


async def send_message_safe(
    bot: Bot,
    chat_id: int,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> bool:
    """Send message, return True if success, False otherwise. Won't raise exceptions."""
    try:
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode="HTML",
        )
        return True
    except TelegramBadRequest as e:
        # User blocked bot or other bad request
        logger.debug(f"Cannot send to {chat_id}: {e}")
        return False
    except TelegramAPIError as e:
        logger.error(f"Telegram API error for {chat_id}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error sending to {chat_id}: {e}")
        return False


async def edit_message_text(
    bot: Bot,
    chat_id: int,
    message_id: int,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> bool:
    """Edit existing message. Return True if success."""
    try:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode="HTML",
        )
        return True
    except TelegramBadRequest as e:
        logger.debug(f"Cannot edit message {message_id} in {chat_id}: {e}")
        return False
    except TelegramAPIError as e:
        logger.error(f"Telegram API error editing {message_id}: {e}")
        return False


async def delete_message(
    bot: Bot,
    chat_id: int,
    message_id: int,
) -> bool:
    """Delete message. Return True if success."""
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
        return True
    except TelegramBadRequest as e:
        logger.debug(f"Cannot delete message {message_id} from {chat_id}: {e}")
        return False
    except TelegramAPIError as e:
        logger.error(f"Telegram API error deleting {message_id}: {e}")
        return False
