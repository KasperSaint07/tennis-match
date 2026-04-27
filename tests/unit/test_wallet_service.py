"""Unit tests for WalletService — charge, refund, penalty, idempotency."""

import pytest
from decimal import Decimal
from uuid import uuid4

from app.services.wallet import WalletService
from app.enums.transaction import TransactionType
from app.core.exceptions import InsufficientBalanceException
from app.repositories.wallet import WalletRepository
from tests.conftest import create_user


# ── helpers ───────────────────────────────────────────────────────────────


async def get_balance(db, user_id) -> Decimal:
    return await WalletService(db).get_balance(user_id)


# ── charge ────────────────────────────────────────────────────────────────


async def test_charge_deducts_balance(db):
    async with db.begin():
        user, _ = await create_user(db, telegram_id=200, balance=Decimal("1000"))

    service = WalletService(db)
    game_id = uuid4()

    async with db.begin():
        txn = await service.charge(user.id, game_id, Decimal("300"), "charge:1")

    assert txn.amount == Decimal("300")
    assert txn.type == TransactionType.JOIN_PAYMENT
    balance = await get_balance(db, user.id)
    assert balance == Decimal("700")


async def test_charge_insufficient_balance_raises(db):
    async with db.begin():
        user, _ = await create_user(db, telegram_id=201, balance=Decimal("50"))

    service = WalletService(db)
    with pytest.raises(InsufficientBalanceException):
        async with db.begin():
            await service.charge(user.id, uuid4(), Decimal("100"), "charge:2")


async def test_charge_idempotency_returns_same_transaction(db):
    """Calling charge twice with the same key returns the same transaction."""
    async with db.begin():
        user, _ = await create_user(db, telegram_id=202, balance=Decimal("1000"))

    service = WalletService(db)
    game_id = uuid4()
    key = "charge:idempotent:1"

    async with db.begin():
        txn1 = await service.charge(user.id, game_id, Decimal("100"), key)

    async with db.begin():
        txn2 = await service.charge(user.id, game_id, Decimal("100"), key)

    assert txn1.id == txn2.id
    # Balance should only be deducted once
    balance = await get_balance(db, user.id)
    assert balance == Decimal("900")


async def test_charge_zero_balance_edge(db):
    """Charging exactly the full balance succeeds."""
    async with db.begin():
        user, _ = await create_user(db, telegram_id=203, balance=Decimal("100"))

    service = WalletService(db)
    async with db.begin():
        txn = await service.charge(user.id, uuid4(), Decimal("100"), "charge:exact")

    assert txn.amount == Decimal("100")
    balance = await get_balance(db, user.id)
    assert balance == Decimal("0")


# ── refund ────────────────────────────────────────────────────────────────


async def test_refund_increases_balance(db):
    async with db.begin():
        user, _ = await create_user(db, telegram_id=210, balance=Decimal("500"))

    service = WalletService(db)
    game_id = uuid4()

    async with db.begin():
        txn = await service.refund(user.id, game_id, Decimal("200"), "refund:1")

    assert txn.amount == Decimal("200")
    assert txn.type == TransactionType.REFUND
    balance = await get_balance(db, user.id)
    assert balance == Decimal("700")


async def test_refund_idempotency(db):
    async with db.begin():
        user, _ = await create_user(db, telegram_id=211, balance=Decimal("500"))

    service = WalletService(db)
    game_id = uuid4()
    key = "refund:idempotent:1"

    async with db.begin():
        txn1 = await service.refund(user.id, game_id, Decimal("100"), key)

    async with db.begin():
        txn2 = await service.refund(user.id, game_id, Decimal("100"), key)

    assert txn1.id == txn2.id
    # Balance should only be increased once
    balance = await get_balance(db, user.id)
    assert balance == Decimal("600")


# ── penalty ───────────────────────────────────────────────────────────────


async def test_penalty_deducts_balance(db):
    async with db.begin():
        user, _ = await create_user(db, telegram_id=220, balance=Decimal("500"))

    service = WalletService(db)
    game_id = uuid4()

    async with db.begin():
        txn = await service.penalty(user.id, game_id, Decimal("50"), "penalty:1")

    assert txn.amount == Decimal("50")
    assert txn.type == TransactionType.PENALTY
    balance = await get_balance(db, user.id)
    assert balance == Decimal("450")


async def test_penalty_idempotency(db):
    async with db.begin():
        user, _ = await create_user(db, telegram_id=221, balance=Decimal("500"))

    service = WalletService(db)
    game_id = uuid4()
    key = "penalty:idempotent:1"

    async with db.begin():
        txn1 = await service.penalty(user.id, game_id, Decimal("50"), key)

    async with db.begin():
        txn2 = await service.penalty(user.id, game_id, Decimal("50"), key)

    assert txn1.id == txn2.id
    balance = await get_balance(db, user.id)
    assert balance == Decimal("450")  # deducted only once


async def test_penalty_can_go_below_zero(db):
    """Penalties are allowed to push balance negative."""
    async with db.begin():
        user, _ = await create_user(db, telegram_id=222, balance=Decimal("10"))

    service = WalletService(db)
    async with db.begin():
        await service.penalty(user.id, uuid4(), Decimal("50"), "penalty:neg")

    balance = await get_balance(db, user.id)
    assert balance == Decimal("-40")


# ── deposit ───────────────────────────────────────────────────────────────


async def test_deposit_increases_balance(db):
    async with db.begin():
        user, _ = await create_user(db, telegram_id=230, balance=Decimal("0"))

    service = WalletService(db)
    async with db.begin():
        txn = await service.deposit(user.id, Decimal("500"))

    assert txn.amount == Decimal("500")
    assert txn.type == TransactionType.DEPOSIT
    balance = await get_balance(db, user.id)
    assert balance == Decimal("500")
