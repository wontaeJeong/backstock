from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from packages.shared.settings import Settings


def create_engine(settings: Settings) -> AsyncEngine:
    return create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
    )
