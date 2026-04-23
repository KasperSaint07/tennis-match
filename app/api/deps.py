"""Dependency injection for FastAPI."""

from typing import AsyncGenerator, Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidTokenException, UnauthorizedException, UserNotFoundException
from app.core.security import verify_jwt_token
from app.db.session import get_db
from app.models.user import User
from app.repositories.game import GameRepository
from app.repositories.game_participant import GameParticipantRepository
from app.repositories.reliability import ReliabilityEventRepository
from app.repositories.transaction import TransactionRepository
from app.repositories.user import UserRepository
from app.repositories.wallet import WalletRepository
from app.services.auth import AuthService
from app.services.game import GameService
from app.services.reliability import ReliabilityService
from app.services.wallet import WalletService

# auto_error=False so missing token raises 401, not 403
security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Get current authenticated user from JWT token."""
    if credentials is None:
        raise UnauthorizedException("Not authenticated")

    try:
        token = credentials.credentials
        user_id: UUID = verify_jwt_token(token)

        user_repo = UserRepository(db)
        user = await user_repo.get_by_id(user_id)

        if not user:
            raise UserNotFoundException(str(user_id))

        # Commit the read-only auth transaction so services can begin their own.
        # expire_on_commit=False keeps user attributes accessible after commit.
        await db.commit()

        return user

    except InvalidTokenException as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )
    except UserNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


async def get_auth_service(
    db: AsyncSession = Depends(get_db),
) -> AuthService:
    """Get AuthService instance."""
    return AuthService(db)


async def get_wallet_service(
    db: AsyncSession = Depends(get_db),
) -> WalletService:
    """Get WalletService instance."""
    return WalletService(db)


async def get_reliability_service(
    db: AsyncSession = Depends(get_db),
) -> ReliabilityService:
    """Get ReliabilityService instance."""
    return ReliabilityService(db)


async def get_game_service(
    db: AsyncSession = Depends(get_db),
) -> GameService:
    """Get GameService instance with all dependencies wired."""
    game_repo = GameRepository(db)
    game_participant_repo = GameParticipantRepository(db)
    wallet_service = WalletService(db)
    reliability_service = ReliabilityService(db)

    return GameService(
        db=db,
        game_repo=game_repo,
        game_participant_repo=game_participant_repo,
        wallet_service=wallet_service,
        reliability_service=reliability_service,
    )


async def get_user_repo(
    db: AsyncSession = Depends(get_db),
) -> UserRepository:
    """Get UserRepository instance."""
    return UserRepository(db)


async def get_wallet_repo(
    db: AsyncSession = Depends(get_db),
) -> WalletRepository:
    """Get WalletRepository instance."""
    return WalletRepository(db)


async def get_game_repo(
    db: AsyncSession = Depends(get_db),
) -> GameRepository:
    """Get GameRepository instance."""
    return GameRepository(db)
