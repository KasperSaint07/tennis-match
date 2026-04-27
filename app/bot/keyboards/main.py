"""Main menu keyboard."""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Main menu with browse games, create, and wallet."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎾 Browse Games", callback_data="games:list:0")],
            [InlineKeyboardButton(text="➕ Create Game", callback_data="create:start")],
            [InlineKeyboardButton(text="💰 Wallet", callback_data="wallet:show")],
            [InlineKeyboardButton(text="❓ Help", callback_data="help:show")],
        ]
    )


def get_back_to_menu_keyboard() -> InlineKeyboardMarkup:
    """Single back button to main menu."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Back to Menu", callback_data="menu:main")],
        ]
    )
