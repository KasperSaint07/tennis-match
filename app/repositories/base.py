"""Base repository with CRUD operations."""

from typing import Generic, TypeVar, Optional, Type, List, Tuple
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.db.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """Base repository providing common CRUD operations."""

    def __init__(self, db: AsyncSession, model: Type[ModelT]):
        self.db = db
        self.model = model

    async def get_by_id(self, id: UUID) -> Optional[ModelT]:
        """Get entity by ID, return None if not found."""
        result = await self.db.execute(select(self.model).where(self.model.id == id))
        return result.scalars().first()

    async def get_or_raise(self, id: UUID) -> ModelT:
        """Get entity by ID, raise NotFoundException if not found."""
        entity = await self.get_by_id(id)
        if not entity:
            raise NotFoundException(f"{self.model.__name__} not found")
        return entity

    async def create(self, **kwargs) -> ModelT:
        """Create new entity."""
        entity = self.model(**kwargs)
        self.db.add(entity)
        await self.db.flush()
        return entity

    async def update(self, entity: ModelT, **kwargs) -> ModelT:
        """Update entity fields."""
        for key, value in kwargs.items():
            if hasattr(entity, key):
                setattr(entity, key, value)
        self.db.add(entity)
        await self.db.flush()
        return entity

    async def delete(self, entity: ModelT) -> None:
        """Delete entity."""
        await self.db.delete(entity)
        await self.db.flush()

    async def get_all(self, limit: int = 100, offset: int = 0) -> Tuple[List[ModelT], int]:
        """Get all entities with pagination."""
        # Count query
        count_result = await self.db.execute(select(func.count(self.model.id)))
        total = count_result.scalar()

        # Fetch query
        result = await self.db.execute(
            select(self.model).limit(limit).offset(offset)
        )
        items = result.scalars().all()
        return items, total

    async def exists(self, **kwargs) -> bool:
        """Check if entity exists with given conditions."""
        query = select(self.model)
        for key, value in kwargs.items():
            if hasattr(self.model, key):
                query = query.where(getattr(self.model, key) == value)
        result = await self.db.execute(query)
        return result.scalars().first() is not None
