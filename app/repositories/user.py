"""User repository."""

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """Repository for User operations."""

    def __init__(self, db: AsyncSession):
        super().__init__(db, User)

    async def get_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """Get user by Telegram ID."""
        result = await self.db.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalars().first()

    async def get_by_telegram_id_or_create(
        self,
        telegram_id: int,
        name: str,
        level: str,
    ) -> User:
        """Get user by telegram ID or create new one."""
        user = await self.get_by_telegram_id(telegram_id)

        if not user:
            user = await self.create(
                telegram_id=telegram_id,
                name=name,
                level=level,
            )

        return user
