"""Game-related keyboards."""

from uuid import UUID
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_game_details_keyboard(game_id: UUID, is_joined: bool = False) -> InlineKeyboardMarkup:
    """Keyboard for game details (join/leave/checkin)."""
    buttons = []

    if not is_joined:
        buttons.append([InlineKeyboardButton(text="✅ Join Game", callback_data=f"game:join:{game_id}")])
    else:
        buttons.append([InlineKeyboardButton(text="🚪 Leave Game", callback_data=f"game:leave:{game_id}")])
        buttons.append([InlineKeyboardButton(text="✔️ Check In", callback_data=f"game:checkin:{game_id}")])

    buttons.append([InlineKeyboardButton(text="◀️ Back to Games", callback_data="games:list:0")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_games_list_keyboard(offset: int, has_more: bool) -> InlineKeyboardMarkup:
    """Keyboard for paginated games list."""
    buttons = []

    if offset > 0:
        buttons.append([InlineKeyboardButton(text="◀️ Previous", callback_data=f"games:list:{offset - 10}")])

    if has_more:
        buttons.append([InlineKeyboardButton(text="Next ▶️", callback_data=f"games:list:{offset + 10}")])

    buttons.append([InlineKeyboardButton(text="🏠 Menu", callback_data="menu:main")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_game_action_keyboard(game_id: UUID) -> InlineKeyboardMarkup:
    """Keyboard for game actions (cancel, etc)."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Cancel Game", callback_data=f"game:cancel:{game_id}")],
            [InlineKeyboardButton(text="◀️ Back", callback_data="games:list:0")],
        ]
    )
