import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from packages.market_data.errors import MarketDataError, ProviderErrorCategory
from packages.market_data.raw_store import FileRawStore, FileRequestCache
from packages.market_data.retry import RetryPolicy, retry_call


def test_raw_capture_is_immutable_and_request_cache_expires(tmp_path: Path) -> None:
    now = datetime(2024, 1, 2, 12, tzinfo=UTC)
    store = FileRawStore(tmp_path / "raw", clock=lambda: now)
    artifact = store.capture(
        provider="fixture",
        provider_version="1.0",
        request={"symbol": "AAPL"},
        payload=b"unmodified upstream bytes\n",
        media_type="text/csv",
    )

    assert artifact.checksum.startswith("sha256:")
    digest = hashlib.sha256(b"unmodified upstream bytes\n").hexdigest()
    assert artifact.checksum == f"sha256:{digest}"
    assert artifact.payload_path.read_bytes() == b"unmodified upstream bytes\n"
    assert artifact.metadata_path.exists()
    assert dict(artifact.request)["symbol"] == "AAPL"

    cache = FileRequestCache(tmp_path / "cache", store=store, clock=lambda: now)
    cache.put("fixture", {"symbol": "AAPL"}, artifact, ttl=timedelta(minutes=5))
    assert cache.get("fixture", {"symbol": "AAPL"}) == artifact

    expired = FileRequestCache(
        tmp_path / "cache", store=store, clock=lambda: now + timedelta(minutes=6)
    )
    assert expired.get("fixture", {"symbol": "AAPL"}) is None


def test_sidecar_tampering_and_corrupt_cache_are_rejected(tmp_path: Path) -> None:
    now = datetime(2024, 1, 2, 12, tzinfo=UTC)
    store = FileRawStore(tmp_path / "raw", clock=lambda: now)
    artifact = store.capture(
        provider="fixture",
        provider_version="1.0",
        request={"symbol": "AAPL"},
        payload=b"payload",
        media_type="text/plain",
    )
    metadata = artifact.metadata_path.read_text()
    tampered = metadata.replace('"provider_version": "1.0"', '"provider_version": "tampered"')
    _ = artifact.metadata_path.write_text(tampered)
    assert store.load("fixture", artifact.artifact_id) is None

    clean = store.capture(
        provider="fixture",
        provider_version="1.0",
        request={"symbol": "MSFT"},
        payload=b"clean",
        media_type="text/plain",
    )
    cache_dir = tmp_path / "cache"
    cache = FileRequestCache(cache_dir, store=store, clock=lambda: now)
    cache.put("fixture", {"symbol": "MSFT"}, clean, ttl=timedelta(minutes=5))
    _ = next(cache_dir.iterdir()).write_text("{incomplete")
    assert cache.get("fixture", {"symbol": "MSFT"}) is None


def test_cache_rejects_artifact_bound_to_another_request(tmp_path: Path) -> None:
    store = FileRawStore(tmp_path / "raw")
    artifact = store.capture(
        provider="fixture",
        provider_version="1.0",
        request={"symbol": "MSFT"},
        payload=b"msft",
        media_type="text/plain",
    )
    cache = FileRequestCache(tmp_path / "cache", store=store)

    with pytest.raises(ValueError, match="binding must match"):
        cache.put(
            "fixture",
            {"symbol": "AAPL"},
            artifact,
            ttl=timedelta(minutes=5),
        )


def test_retry_is_bounded_and_honors_retry_after() -> None:
    attempts = 0
    delays: list[float] = []

    def operation() -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise MarketDataError(
                provider="fixture",
                category=ProviderErrorCategory.QUOTA,
                message="rate limited",
                retryable=True,
                retry_after_seconds=1.5,
            )
        return "ok"

    result = retry_call(
        operation,
        policy=RetryPolicy(max_attempts=3, initial_delay_seconds=0.1, max_delay_seconds=2),
        sleep=delays.append,
        jitter=lambda: 0.0,
    )

    assert result == "ok"
    assert attempts == 3
    assert delays == [1.5, 1.5]


def test_retry_never_retries_non_retryable_failure() -> None:
    def operation() -> str:
        raise MarketDataError(
            provider="fixture",
            category=ProviderErrorCategory.INVALID_REQUEST,
            message="bad symbol",
            retryable=False,
        )

    with pytest.raises(MarketDataError):
        _ = retry_call(operation, policy=RetryPolicy(max_attempts=3), sleep=lambda _: None)


def test_retry_after_cannot_exceed_policy_maximum() -> None:
    delays: list[float] = []
    attempts = 0

    def operation() -> str:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise MarketDataError(
                provider="fixture",
                category=ProviderErrorCategory.QUOTA,
                message="rate limited",
                retryable=True,
                retry_after_seconds=60,
            )
        return "ok"

    assert (
        retry_call(
            operation,
            policy=RetryPolicy(max_attempts=2, max_delay_seconds=2),
            sleep=delays.append,
            jitter=lambda: 0,
        )
        == "ok"
    )
    assert delays == [2]


def test_jitter_cannot_exceed_policy_maximum() -> None:
    attempts = 0
    delays: list[float] = []

    def operation() -> str:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise MarketDataError(
                provider="fixture",
                category=ProviderErrorCategory.NETWORK,
                message="temporary failure",
                retryable=True,
            )
        return "ok"

    assert (
        retry_call(
            operation,
            policy=RetryPolicy(
                max_attempts=2,
                initial_delay_seconds=2,
                max_delay_seconds=2,
                jitter_seconds=0.5,
            ),
            sleep=delays.append,
            jitter=lambda: 1,
        )
        == "ok"
    )
    assert delays == [2]
