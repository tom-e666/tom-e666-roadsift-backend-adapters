from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine


def normalize_async_postgres_url(database_url: str) -> str:
    """Normalize Supabase/Postgres URLs for SQLAlchemy async + psycopg3."""
    if database_url.startswith("postgresql+psycopg://"):
        return database_url.replace("postgresql+psycopg://", "postgresql+psycopg_async://", 1)
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg_async://", 1)
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+psycopg_async://", 1)
    return database_url


def create_database_engine(
    database_url: str,
    *,
    pool_size: int = 5,
    max_overflow: int = 10,
    pool_recycle_seconds: int = 1800,
) -> AsyncEngine:
    """Create a production-oriented async engine for Supabase Postgres.

    Supabase is treated as managed PostgreSQL, not as a domain SDK dependency.
    Migrations should be applied by Alembic outside request startup.
    """
    return create_async_engine(
        normalize_async_postgres_url(database_url),
        pool_pre_ping=True,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_recycle=pool_recycle_seconds,
        echo=False,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


async def session_dependency(
    factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
