"""Wallet-related keyboards."""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_wallet_keyboard() -> InlineKeyboardMarkup:
    """Wallet menu with deposit and history."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💵 Deposit", callback_data="wallet:deposit:start")],
            [InlineKeyboardButton(text="📋 Transaction History", callback_data="wallet:history:0")],
            [InlineKeyboardButton(text="🏠 Menu", callback_data="menu:main")],
        ]
    )


def get_wallet_history_keyboard(offset: int, has_more: bool) -> InlineKeyboardMarkup:
    """Keyboard for transaction history pagination."""
    buttons = []

    if offset > 0:
        buttons.append([InlineKeyboardButton(text="◀️ Previous", callback_data=f"wallet:history:{offset - 5}")])

    if has_more:
        buttons.append([InlineKeyboardButton(text="Next ▶️", callback_data=f"wallet:history:{offset + 5}")])

    buttons.append([InlineKeyboardButton(text="💰 Wallet", callback_data="wallet:show")])
    buttons.append([InlineKeyboardButton(text="🏠 Menu", callback_data="menu:main")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_deposit_amounts_keyboard() -> InlineKeyboardMarkup:
    """Quick deposit amount buttons."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="1000₸", callback_data="wallet:deposit:1000"),
                InlineKeyboardButton(text="5000₸", callback_data="wallet:deposit:5000"),
            ],
            [
                InlineKeyboardButton(text="10000₸", callback_data="wallet:deposit:10000"),
                InlineKeyboardButton(text="50000₸", callback_data="wallet:deposit:50000"),
            ],
            [InlineKeyboardButton(text="💰 Wallet", callback_data="wallet:show")],
        ]
    )
