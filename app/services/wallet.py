"""Wallet service for financial operations."""

from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InsufficientBalanceException, WalletOperationFailedException
from app.enums.transaction import TransactionType, TransactionStatus
from app.models.transaction import Transaction
from app.repositories.wallet import WalletRepository
from app.repositories.transaction import TransactionRepository


class WalletService:
    """Service for wallet and transaction operations."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.wallet_repo = WalletRepository(db)
        self.transaction_repo = TransactionRepository(db)

    async def charge(
        self,
        user_id: UUID,
        game_id: UUID,
        amount: Decimal,
        idempotency_key: str,
    ) -> Transaction:
        """Charge user's wallet for game participation.

        Idempotent: returns existing transaction if key already exists.

        Args:
            user_id: User UUID
            game_id: Game UUID
            amount: Amount to charge
            idempotency_key: Idempotency key

        Returns:
            Transaction object

        Raises:
            InsufficientBalanceException: If balance is insufficient
        """
        # Check for idempotency
        existing = await self.transaction_repo.get_by_idempotency_key(idempotency_key)
        if existing:
            return existing

        # Get wallet with lock
        wallet = await self.wallet_repo.get_for_update(user_id)

        # Check balance
        if wallet.balance < amount:
            raise InsufficientBalanceException(
                f"Insufficient balance: {wallet.balance} < {amount}"
            )

        # Create transaction
        transaction = await self.transaction_repo.create(
            user_id=user_id,
            wallet_id=wallet.id,
            game_id=game_id,
            type=TransactionType.JOIN_PAYMENT,
            amount=amount,
            status=TransactionStatus.COMPLETED,
            idempotency_key=idempotency_key,
        )

        # Update wallet balance
        wallet.balance -= amount
        self.db.add(wallet)
        await self.db.flush()

        return transaction

    async def refund(
        self,
        user_id: UUID,
        game_id: UUID,
        amount: Decimal,
        idempotency_key: str,
    ) -> Transaction:
        """Refund user's wallet.

        Idempotent: returns existing transaction if key already exists.

        Args:
            user_id: User UUID
            game_id: Game UUID
            amount: Amount to refund
            idempotency_key: Idempotency key

        Returns:
            Transaction object
        """
        # Check for idempotency
        existing = await self.transaction_repo.get_by_idempotency_key(idempotency_key)
        if existing:
            return existing

        # Get wallet with lock
        wallet = await self.wallet_repo.get_for_update(user_id)

        # Create transaction
        transaction = await self.transaction_repo.create(
            user_id=user_id,
            wallet_id=wallet.id,
            game_id=game_id,
            type=TransactionType.REFUND,
            amount=amount,
            status=TransactionStatus.COMPLETED,
            idempotency_key=idempotency_key,
        )

        # Update wallet balance
        wallet.balance += amount
        self.db.add(wallet)
        await self.db.flush()

        return transaction

    async def penalty(
        self,
        user_id: UUID,
        game_id: UUID,
        amount: Decimal,
        idempotency_key: str,
    ) -> Transaction:
        """Charge penalty to user (no refund).

        Idempotent: returns existing transaction if key already exists.

        Args:
            user_id: User UUID
            game_id: Game UUID
            amount: Penalty amount
            idempotency_key: Idempotency key

        Returns:
            Transaction object
        """
        # Check for idempotency
        existing = await self.transaction_repo.get_by_idempotency_key(idempotency_key)
        if existing:
            return existing

        # Get wallet with lock
        wallet = await self.wallet_repo.get_for_update(user_id)

        # Create transaction (allow negative balance for penalties)
        transaction = await self.transaction_repo.create(
            user_id=user_id,
            wallet_id=wallet.id,
            game_id=game_id,
            type=TransactionType.PENALTY,
            amount=amount,
            status=TransactionStatus.COMPLETED,
            idempotency_key=idempotency_key,
        )

        # Update wallet balance (can go negative)
        wallet.balance -= amount
        self.db.add(wallet)
        await self.db.flush()

        return transaction

    async def deposit(
        self,
        user_id: UUID,
        amount: Decimal,
    ) -> Transaction:
        """Deposit money to user's wallet (mock for MVP).

        Args:
            user_id: User UUID
            amount: Deposit amount

        Returns:
            Transaction object
        """
        wallet = await self.wallet_repo.get_for_update(user_id)

        # Create idempotency key based on timestamp
        from datetime import datetime
        idempotency_key = f"deposit:{user_id}:{datetime.utcnow().isoformat()}"

        transaction = await self.transaction_repo.create(
            user_id=user_id,
            wallet_id=wallet.id,
            game_id=None,
            type=TransactionType.DEPOSIT,
            amount=amount,
            status=TransactionStatus.COMPLETED,
            idempotency_key=idempotency_key,
        )

        # Update balance
        wallet.balance += amount
        self.db.add(wallet)
        await self.db.flush()

        return transaction

    async def get_balance(self, user_id: UUID) -> Decimal:
        """Get user's wallet balance.

        Args:
            user_id: User UUID

        Returns:
            Current balance
        """
        wallet = await self.wallet_repo.get_by_user_id(user_id)
        return wallet.balance
