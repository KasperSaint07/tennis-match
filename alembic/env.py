from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import os

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

from app.db.base import Base  # noqa: E402

# Import all models so they register with Base.metadata
from app.models.user import User  # noqa: F401, E402
from app.models.game import Game  # noqa: F401, E402
from app.models.game_participant import GameParticipant  # noqa: F401, E402
from app.models.wallet import Wallet  # noqa: F401, E402
from app.models.transaction import Transaction  # noqa: F401, E402
from app.models.reliability_event import ReliabilityEvent  # noqa: F401, E402

target_metadata = Base.metadata


def get_url() -> str:
    url = os.environ.get("DATABASE_URL", config.get_main_option("sqlalchemy.url"))
    # Alembic needs a sync driver — strip asyncpg in either URL format
    url = url.replace("postgresql+asyncpg://", "postgresql://")
    return url


def run_migrations_offline() -> None:
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = get_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
