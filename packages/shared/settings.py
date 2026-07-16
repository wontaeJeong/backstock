from functools import lru_cache
from pathlib import Path
from typing import ClassVar, Final

from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_DATABASE_URL: Final = "postgresql+asyncpg://postgres:postgres@localhost:5432/stocklab"


class Settings(BaseSettings):
    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_file=".env", extra="ignore", frozen=True
    )

    app_env: str = "development"
    database_url: str = DEFAULT_DATABASE_URL
    data_storage_path: Path = Path("var/data")
    log_level: str = "INFO"
    market_data_default_provider: str = "yfinance"
    yfinance_cache_path: Path = Path("var/cache/yfinance")
    broker_mode: str = "paper"
    broker_production_enabled: bool = False
    mcp_enabled: bool = False
    mcp_production_order_tools_enabled: bool = False


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
