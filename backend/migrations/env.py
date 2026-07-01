"""Alembic environment — async (SQLAlchemy 2.0 + psycopg 3).

The DB URL comes from ``DATABASE_URL`` (loaded from the repo-root ``.env`` for
local runs; injected by Docker Compose in the container). The target metadata is
the ORM models in ``store/`` — keep them in sync when adding migrations.
"""

import asyncio
import os
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

# Load the repo-root .env (two levels up from this file: backend/migrations/env.py).
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from store.models import Base  # noqa: E402  (after load_dotenv / sys.path setup)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

_DATABASE_URL = os.environ["DATABASE_URL"]
config.set_main_option("sqlalchemy.url", _DATABASE_URL)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=_DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(_do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
