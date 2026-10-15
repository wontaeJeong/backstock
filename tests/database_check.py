"""Explicit disposable-PostgreSQL integration check; never uses a default database."""

import asyncio
import logging
import os
from uuid import uuid4

import asyncpg  # type: ignore[import-untyped]


async def main() -> None:
    url = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
    connection = await asyncpg.connect(url)
    transaction = connection.transaction()
    await transaction.start()
    try:
        key = f"test-{uuid4().hex}"
        await connection.execute(
            "INSERT INTO instruments (instrument_id, symbol, exchange, currency, timezone, "
            "asset_class, active, created_at) VALUES ($1, $1, 'NASDAQ', 'USD', "
            "'America/New_York', 'equity', true, now())",
            key,
        )
        query = (
            "INSERT INTO provider_symbol_mappings "
            "(provider, provider_symbol, instrument_id, valid_from, valid_to, created_at) "
            "VALUES ($1, $2, $3, $4::text::timestamptz, $5::text::timestamptz, now())"
        )
        await connection.execute(query, key, key, key, "2024-01-01Z", "2024-02-01Z")
        await connection.execute(query, key, key, key, "2024-02-01Z", None)
        cases = (
            (asyncpg.ExclusionViolationError, key, key, key, "2024-01-15Z", "2024-01-20Z"),
            (asyncpg.ExclusionViolationError, key, key + "other", key, "2024-01-15Z", None),
            (asyncpg.CheckViolationError, key + "bad", key, key, "2024-02-02Z", "2024-02-01Z"),
            (
                asyncpg.ForeignKeyViolationError,
                key + "missing",
                key,
                key + "missing",
                "2024-01-01Z",
                None,
            ),
        )
        for expected, *values in cases:
            try:
                async with connection.transaction():
                    await connection.execute(query, *values)
            except expected:
                continue
            message = f"database did not enforce {expected.__name__}"
            raise AssertionError(message)
        logging.getLogger(__name__).warning(
            "PostgreSQL integration: adjacent windows accepted; "
            "overlaps, invalid windows and FK rejected"
        )
    finally:
        await transaction.rollback()
        await connection.close()


if __name__ == "__main__":
    asyncio.run(main())
