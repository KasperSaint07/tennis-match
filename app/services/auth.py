"""Authentication service."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_jwt_token, verify_jwt_token, verify_telegram_data
from app.core.exceptions import UnauthorizedException, UserNotFoundException
from app.models.user import User
from app.repositories.user import UserRepository
from app.repositories.wallet import WalletRepository


class AuthService:
    """Service for authentication operations."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_repo = UserRepository(db)
        self.wallet_repo = WalletRepository(db)

    async def authenticate_telegram(
        self,
        init_data: str,
        bot_token: str,
    ) -> tuple[User, str]:
        """Authenticate user via Telegram and return user + JWT token.

        Args:
            init_data: Telegram WebApp init data string
            bot_token: Telegram bot token

        Returns:
            (user, jwt_token) tuple

        Raises:
            TelegramVerificationFailedException: If verification fails
        """
        # Verify Telegram data
        user_data = verify_telegram_data(init_data, bot_token)

        telegram_id = user_data.get("id")
        name = user_data.get("first_name", f"User {telegram_id}")
        level = "BEGINNER"  # Default level for new users

        if not telegram_id:
            raise UnauthorizedException("Missing telegram ID")

        # Get or create user
        user = await self.user_repo.get_by_telegram_id_or_create(
            telegram_id=telegram_id,
            name=name,
            level=level,
        )

        # Ensure user has wallet
        await self.wallet_repo.get_or_create_for_user(user.id)

        # Create JWT token
        token = create_jwt_token(user.id)

        return user, token

    async def get_user_from_token(self, token: str) -> User:
        """Get user from JWT token.

        Args:
            token: JWT token string

        Returns:
            User object

        Raises:
            InvalidTokenException: If token is invalid
            UserNotFoundException: If user not found
        """
        user_id = verify_jwt_token(token)

        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise UserNotFoundException(str(user_id))

        return user

    async def refresh_token(self, token: str) -> str:
        """Refresh JWT token.

        Args:
            token: Current JWT token

        Returns:
            New JWT token

        Raises:
            InvalidTokenException: If token is invalid
        """
        user_id = verify_jwt_token(token)
        return create_jwt_token(user_id)
