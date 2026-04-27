"""Bot keyboards."""

from app.bot.keyboards.main import get_main_menu_keyboard, get_back_to_menu_keyboard
from app.bot.keyboards.game import (
    get_game_details_keyboard,
    get_games_list_keyboard,
    get_game_action_keyboard,
)
from app.bot.keyboards.wallet import (
    get_wallet_keyboard,
    get_wallet_history_keyboard,
    get_deposit_amounts_keyboard,
)

__all__ = [
    "get_main_menu_keyboard",
    "get_back_to_menu_keyboard",
    "get_game_details_keyboard",
    "get_games_list_keyboard",
    "get_game_action_keyboard",
    "get_wallet_keyboard",
    "get_wallet_history_keyboard",
    "get_deposit_amounts_keyboard",
]
