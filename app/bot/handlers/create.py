"""Create game handler with multi-step conversation."""

import logging
from datetime import datetime
from decimal import Decimal
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.repositories.user import UserRepository
from app.enums.game import GameFormat, GameLevel
from app.bot.deps import build_game_service
from app.core.exceptions import AppException
from app.bot.keyboards import get_main_menu_keyboard
from app.integrations.telegram import send_message, edit_message_text

logger = logging.getLogger(__name__)

router = Router()


class CreateGameState(StatesGroup):
    """FSM states for game creation."""

    format = State()
    level = State()
    datetime = State()
    price = State()
    location = State()
    confirm = State()


def get_format_keyboard():
    """Keyboard for format selection."""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🎾 Singles (2 players)", callback_data="create:format:SINGLES"),
                InlineKeyboardButton(text="👥 Doubles (4 players)", callback_data="create:format:DOUBLES"),
            ],
            [InlineKeyboardButton(text="❌ Cancel", callback_data="create:cancel")],
        ]
    )


def get_level_keyboard():
    """Keyboard for level selection."""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🟢 Beginner", callback_data="create:level:BEGINNER")],
            [InlineKeyboardButton(text="🟡 Intermediate", callback_data="create:level:INTERMEDIATE")],
            [InlineKeyboardButton(text="🔴 Advanced", callback_data="create:level:ADVANCED")],
            [InlineKeyboardButton(text="❌ Cancel", callback_data="create:cancel")],
        ]
    )


@router.callback_query(F.data == "create:start")
async def create_start(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Start game creation flow."""
    await state.set_state(CreateGameState.format)

    await edit_message_text(
        callback_query.bot,
        callback_query.message.chat.id,
        callback_query.message.message_id,
        "➕ <b>Create New Game</b>\n\nStep 1/5: Select game format",
        reply_markup=get_format_keyboard(),
    )
    await callback_query.answer()


@router.callback_query(F.data.startswith("create:format:"))
async def create_format(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Handle format selection."""
    format_value = callback_query.data.split(":")[-1]
    await state.update_data(format=format_value)
    await state.set_state(CreateGameState.level)

    await edit_message_text(
        callback_query.bot,
        callback_query.message.chat.id,
        callback_query.message.message_id,
        f"✅ Format: <b>{format_value}</b>\n\nStep 2/5: Select skill level",
        reply_markup=get_level_keyboard(),
    )
    await callback_query.answer()


@router.callback_query(F.data.startswith("create:level:"))
async def create_level(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Handle level selection."""
    level_value = callback_query.data.split(":")[-1]
    await state.update_data(level=level_value)
    await state.set_state(CreateGameState.datetime)

    await edit_message_text(
        callback_query.bot,
        callback_query.message.chat.id,
        callback_query.message.message_id,
        (
            f"✅ Level: <b>{level_value}</b>\n\n"
            f"Step 3/5: Enter date and time\n\n"
            f"Format: <code>YYYY-MM-DD HH:MM</code>\n"
            f"Example: <code>2026-04-22 18:00</code>"
        ),
    )
    await callback_query.answer()


@router.message(CreateGameState.datetime)
async def create_datetime(message: Message, state: FSMContext) -> None:
    """Handle datetime input."""
    try:
        scheduled_at = datetime.strptime(message.text, "%Y-%m-%d %H:%M")
        await state.update_data(datetime=scheduled_at)
        await state.set_state(CreateGameState.price)

        await send_message(
            message.bot,
            message.chat.id,
            (
                f"✅ Date & Time: <b>{scheduled_at.strftime('%d.%m.%Y %H:%M')}</b>\n\n"
                f"Step 4/5: Enter price per player (tenge)\n\n"
                f"Example: <code>3000</code>"
            ),
        )
    except ValueError:
        await send_message(
            message.bot,
            message.chat.id,
            "❌ Invalid format. Please use YYYY-MM-DD HH:MM\n\nExample: 2026-04-22 18:00",
        )


@router.message(CreateGameState.price)
async def create_price(message: Message, state: FSMContext) -> None:
    """Handle price input."""
    try:
        price = Decimal(message.text)
        if price <= 0:
            raise ValueError("Price must be positive")

        await state.update_data(price=price)
        await state.set_state(CreateGameState.location)

        await send_message(
            message.bot,
            message.chat.id,
            (
                f"✅ Price: <b>{float(price)}₸</b>\n\n"
                f"Step 5/5: Enter court location\n\n"
                f"Example: <code>Astana Tennis Club, Court 3</code>"
            ),
        )
    except (ValueError, TypeError):
        await send_message(
            message.bot,
            message.chat.id,
            "❌ Invalid price. Enter a number greater than 0.\n\nExample: 3000",
        )


@router.message(CreateGameState.location)
async def create_location(message: Message, state: FSMContext) -> None:
    """Handle location input and confirm."""
    location = message.text.strip()

    if not location or len(location) < 3:
        await send_message(
            message.bot,
            message.chat.id,
            "❌ Location too short. Please provide more details.\n\nExample: Astana Tennis Club, Court 3",
        )
        return

    await state.update_data(location=location)

    # Get all data
    data = await state.get_data()

    # Format summary
    format_type = data.get("format")
    level = data.get("level")
    datetime_val = data.get("datetime")
    price = float(data.get("price"))
    location_val = data.get("location")

    summary = (
        f"✅ <b>Confirm Game Creation</b>\n\n"
        f"🎾 Format: {format_type}\n"
        f"📊 Level: {level}\n"
        f"🕐 Date & Time: {datetime_val.strftime('%d.%m.%Y %H:%M')}\n"
        f"💰 Price: {price}₸ per player\n"
        f"📍 Location: {location_val}"
    )

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    confirm_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Create", callback_data="create:confirm"),
                InlineKeyboardButton(text="❌ Cancel", callback_data="create:cancel"),
            ],
        ]
    )

    await send_message(
        message.bot,
        message.chat.id,
        summary,
        reply_markup=confirm_keyboard,
    )

    await state.set_state(CreateGameState.confirm)


@router.callback_query(F.data == "create:confirm")
async def create_confirm(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Confirm and create game."""
    user = callback_query.from_user
    telegram_id = user.id

    async with AsyncSessionLocal() as session:
        try:
            user_repo = UserRepository(session)
            game_service = build_game_service(session)

            db_user = await user_repo.get_by_telegram_id(telegram_id)
            if db_user is None:
                await callback_query.answer(
                    "❌ Please send /start first to register.",
                    show_alert=True,
                )
                await state.clear()
                return

            # Get data
            data = await state.get_data()

            # Create game
            from app.schemas.game import CreateGameRequest

            dto = CreateGameRequest(
                location=data.get("location"),
                scheduled_at=data.get("datetime"),
                format=GameFormat(data.get("format")),
                level=GameLevel(data.get("level")),
                price_per_player=Decimal(str(data.get("price"))),
            )

            game = await game_service.create_game(
                user=db_user,
                location=dto.location,
                scheduled_at=dto.scheduled_at,
                format=dto.format,
                level=dto.level,
                price_per_player=dto.price_per_player,
            )

            await session.commit()

            text = (
                f"✅ <b>Game Created!</b>\n\n"
                f"🎮 Game ID: <code>{game.id}</code>\n"
                f"🎾 {game.format.value} ({game.level.value})\n"
                f"🕐 {game.scheduled_at.strftime('%d.%m.%Y %H:%M')}\n"
                f"💰 {float(game.price_per_player)}₸ per player\n"
                f"📍 {game.location}\n\n"
                f"👥 You are the host. Share the game ID with friends!"
            )

            await edit_message_text(
                callback_query.bot,
                callback_query.message.chat.id,
                callback_query.message.message_id,
                text,
                reply_markup=get_main_menu_keyboard(),
            )

            logger.info(f"User {telegram_id} created game {game.id}")

        except AppException as e:
            await callback_query.answer(f"❌ {e.message}", show_alert=True)
            logger.error(f"App error creating game for {telegram_id}: {e}")
        except Exception as e:
            await callback_query.answer("❌ Error creating game", show_alert=True)
            logger.error(f"Unexpected error creating game for {telegram_id}: {e}")
        finally:
            await state.clear()


@router.callback_query(F.data == "create:cancel")
async def create_cancel(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Cancel game creation."""
    await state.clear()

    await edit_message_text(
        callback_query.bot,
        callback_query.message.chat.id,
        callback_query.message.message_id,
        "❌ Game creation cancelled.",
        reply_markup=get_main_menu_keyboard(),
    )
    await callback_query.answer()
