"""Wallet and transaction endpoints."""

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user, get_wallet_service, get_wallet_repo
from app.db.session import get_db
from app.models.user import User
from app.repositories.wallet import WalletRepository
from app.repositories.transaction import TransactionRepository
from app.services.wallet import WalletService
from app.schemas.wallet import (
    DepositRequest,
    DepositResponse,
    WalletResponse,
    TransactionResponse,
)
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/wallet", tags=["wallet"])


@router.get("", response_model=WalletResponse)
async def get_wallet(
    current_user: User = Depends(get_current_user),
    wallet_repo: WalletRepository = Depends(get_wallet_repo),
    db: AsyncSession = Depends(get_db),
) -> WalletResponse:
    """Get current user's wallet.

    Args:
        current_user: Authenticated user
        wallet_repo: Wallet repository
        db: Database session

    Returns:
        Wallet details with transaction history

    Raises:
        WalletNotFoundException: If wallet not found
    """
    wallet = await wallet_repo.get_by_user_id(current_user.id)

    # Get transaction history
    transaction_repo = TransactionRepository(db)
    transactions, _ = await transaction_repo.get_by_wallet(
        wallet.id,
        limit=50,
    )

    transaction_responses = [
        TransactionResponse(
            id=t.id,
            user_id=t.user_id,
            wallet_id=t.wallet_id,
            game_id=t.game_id,
            type=t.type,
            amount=t.amount,
            status=t.status,
            created_at=t.created_at,
        )
        for t in transactions
    ]

    return WalletResponse(
        id=wallet.id,
        user_id=wallet.user_id,
        balance=wallet.balance,
        transactions=transaction_responses,
        updated_at=wallet.updated_at,
    )


@router.post("/deposit", response_model=DepositResponse)
async def deposit(
    request: DepositRequest,
    current_user: User = Depends(get_current_user),
    wallet_service: WalletService = Depends(get_wallet_service),
) -> DepositResponse:
    """Deposit money to wallet (mock for MVP).

    Args:
        request: Deposit amount
        current_user: Authenticated user
        wallet_service: Wallet service

    Returns:
        Deposit result
    """
    transaction = await wallet_service.deposit(current_user.id, request.amount)

    balance = await wallet_service.get_balance(current_user.id)

    return DepositResponse(
        transaction_id=transaction.id,
        amount=request.amount,
        balance_after=balance,
    )
