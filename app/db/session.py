"""Database session management."""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.core.config import get_settings

settings = get_settings()

# Normalize URL — Railway provides postgresql://, asyncpg requires postgresql+asyncpg://
_db_url = settings.database_url
if _db_url.startswith("postgresql://"):
    _db_url = _db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

# Create async engine
engine = create_async_engine(
    _db_url,
    echo=settings.debug,
    future=True,
    pool_pre_ping=True,  # Test connections before using them
    pool_size=20,
    max_overflow=0,
)

# Session factory
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency provider for database session."""
    session = async_session()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
    finally:
        await session.close()
