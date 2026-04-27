"""Alembic environment configuration."""

import asyncio
from logging.config import fileConfig
from sqlalchemy import pool, event
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine

from alembic import context
from app.core.config import get_settings
from app.db.base import Base

# Get settings
settings = get_settings()

# Import all models to register them with Base.metadata
from app.models import (  # noqa: F401
    User,
    Wallet,
    Game,
    GameParticipant,
    Transaction,
    ReliabilityEvent,
)

# this is the Alembic Config object
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set SQLAlchemy URL
config.set_main_option("sqlalchemy.url", settings.database_url)

# Add your model's MetaData object for 'autogenerate' support
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well. By skipping the Engine creation
    we don't even need a DBAPI to be available.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    """Run migrations in 'online' mode."""
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """In the 'online' scenario for async."""
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = settings.database_url

    connectable = create_async_engine(
        settings.database_url,
        poolclass=pool.NullPool,
    )

    async with connectable.begin() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    # For autogenerate, use offline mode
    if context.is_autogenerate():
        run_migrations_offline()
    else:
        asyncio.run(run_async_migrations())

