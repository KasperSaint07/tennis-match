"""Wallet handler."""

import logging
from decimal import Decimal
from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.repositories.user import UserRepository
from app.repositories.wallet import WalletRepository
from app.repositories.transaction import TransactionRepository
from app.services.wallet import WalletService
from app.core.exceptions import AppException, NotFoundException
from app.bot.keyboards import (
    get_wallet_keyboard,
    get_wallet_history_keyboard,
    get_deposit_amounts_keyboard,
    get_main_menu_keyboard,
)
from app.integrations.telegram import edit_message_text

logger = logging.getLogger(__name__)

router = Router()

HISTORY_PAGE_SIZE = 5


@router.callback_query(F.data == "wallet:show")
async def wallet_show(callback_query: CallbackQuery) -> None:
    """Show wallet balance and quick actions."""
    user = callback_query.from_user
    telegram_id = user.id

    async with AsyncSessionLocal() as session:
        try:
            user_repo = UserRepository(session)
            wallet_repo = WalletRepository(session)

            db_user = await user_repo.get_by_telegram_id(telegram_id)
            if db_user is None:
                db_user = await user_repo.create(
                    telegram_id=telegram_id,
                    name=user.first_name or f"User {telegram_id}",
                    level="BEGINNER",
                )
                await wallet_repo.get_or_create_for_user(db_user.id)
                await session.commit()

            wallet = await wallet_repo.get_by_user_id(db_user.id)

            balance = float(wallet.balance)

            text = (
                f"💰 <b>Wallet Balance</b>\n\n"
                f"💵 Balance: <b>{balance}₸</b>"
            )

            await edit_message_text(
                callback_query.bot,
                callback_query.message.chat.id,
                callback_query.message.message_id,
                text,
                reply_markup=get_wallet_keyboard(),
            )
            await callback_query.answer()

        except AppException as e:
            await callback_query.answer(f"❌ {e.message}", show_alert=True)
            logger.error(f"App error showing wallet for {telegram_id}: {e}")
        except Exception as e:
            await callback_query.answer("❌ Error loading wallet", show_alert=True)
            logger.error(f"Unexpected error showing wallet for {telegram_id}: {e}")


@router.callback_query(F.data == "wallet:deposit:start")
async def wallet_deposit_start(callback_query: CallbackQuery) -> None:
    """Show deposit amount options."""
    await edit_message_text(
        callback_query.bot,
        callback_query.message.chat.id,
        callback_query.message.message_id,
        "💵 <b>Deposit Money</b>\n\nSelect amount:",
        reply_markup=get_deposit_amounts_keyboard(),
    )
    await callback_query.answer()


@router.callback_query(F.data.startswith("wallet:deposit:"))
async def wallet_deposit(callback_query: CallbackQuery) -> None:
    """Handle deposit."""
    try:
        amount = int(callback_query.data.split(":")[-1])
    except (IndexError, ValueError):
        await callback_query.answer("❌ Invalid amount", show_alert=True)
        return

    user = callback_query.from_user
    telegram_id = user.id
    await callback_query.answer("⏳ Processing deposit...", show_alert=False)

    async with AsyncSessionLocal() as session:
        try:
            user_repo = UserRepository(session)
            wallet_service = WalletService(db=session)
            wallet_repo = WalletRepository(session)

            db_user = await user_repo.get_by_telegram_id(telegram_id)

            # Deposit
            transaction = await wallet_service.deposit(db_user.id, Decimal(amount))

            wallet = await wallet_repo.get_by_user_id(db_user.id)

            text = (
                f"✅ <b>Deposit Successful</b>\n\n"
                f"💵 Amount: {float(transaction.amount)}₸\n"
                f"💳 New Balance: {float(wallet.balance)}₸"
            )

            await edit_message_text(
                callback_query.bot,
                callback_query.message.chat.id,
                callback_query.message.message_id,
                text,
                reply_markup=get_wallet_keyboard(),
            )

            logger.info(f"User {telegram_id} deposited {amount}₸")

        except AppException as e:
            await callback_query.answer(f"❌ {e.message}", show_alert=True)
            logger.error(f"App error depositing for {telegram_id}: {e}")
        except Exception as e:
            await callback_query.answer("❌ Error processing deposit", show_alert=True)
            logger.error(f"Unexpected error depositing for {telegram_id}: {e}")


@router.callback_query(F.data.startswith("wallet:history:"))
async def wallet_history(callback_query: CallbackQuery) -> None:
    """Show transaction history with pagination."""
    offset = int(callback_query.data.split(":")[-1])
    user = callback_query.from_user
    telegram_id = user.id

    async with AsyncSessionLocal() as session:
        try:
            user_repo = UserRepository(session)
            wallet_repo = WalletRepository(session)
            transaction_repo = TransactionRepository(session)

            db_user = await user_repo.get_by_telegram_id(telegram_id)
            if db_user is None:
                db_user = await user_repo.create(
                    telegram_id=telegram_id,
                    name=user.first_name or f"User {telegram_id}",
                    level="BEGINNER",
                )
                await wallet_repo.get_or_create_for_user(db_user.id)
                await session.commit()

            wallet = await wallet_repo.get_by_user_id(db_user.id)

            # Get transactions
            transactions, total = await transaction_repo.get_by_wallet(
                wallet.id,
                limit=HISTORY_PAGE_SIZE,
                offset=offset,
            )

            if not transactions:
                text = "📭 No transactions yet."
            else:
                text = "📋 <b>Transaction History</b>\n\n"
                for tx in transactions:
                    date_str = tx.created_at.strftime("%d.%m %H:%M")
                    amount = float(tx.amount)
                    tx_type = tx.type.value
                    balance = float(tx.amount)

                    if tx.type.value == "DEPOSIT":
                        text += f"✅ +{amount}₸ ({tx_type}) - {date_str}\n"
                    elif tx.type.value == "REFUND":
                        text += f"↩️ +{amount}₸ ({tx_type}) - {date_str}\n"
                    else:
                        text += f"❌ -{amount}₸ ({tx_type}) - {date_str}\n"

                text += f"\n💳 Total shown: {len(transactions)} of {total}"

            has_more = (offset + HISTORY_PAGE_SIZE) < total

            await edit_message_text(
                callback_query.bot,
                callback_query.message.chat.id,
                callback_query.message.message_id,
                text,
                reply_markup=get_wallet_history_keyboard(offset, has_more),
            )
            await callback_query.answer()

        except AppException as e:
            await callback_query.answer(f"❌ {e.message}", show_alert=True)
            logger.error(f"App error showing history for {telegram_id}: {e}")
        except Exception as e:
            await callback_query.answer("❌ Error loading history", show_alert=True)
            logger.error(f"Unexpected error showing history for {telegram_id}: {e}")
