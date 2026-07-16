from packages.domain.market_data import DataLineage
from packages.market_data.errors import MarketDataError, ProviderErrorCategory
from packages.market_data.raw_store import RawArtifact


def lineage(artifact: RawArtifact) -> DataLineage:
    return DataLineage(
        provider=artifact.provider,
        provider_version=artifact.provider_version,
        acquired_at=artifact.acquired_at,
        request_options=artifact.request,
        raw_checksum=artifact.checksum,
        raw_payload_path=str(artifact.payload_path),
        raw_metadata_path=str(artifact.metadata_path),
    )


def not_supported(provider: str, capability: str) -> MarketDataError:
    return MarketDataError(
        provider=provider,
        category=ProviderErrorCategory.NOT_SUPPORTED,
        message=f"{provider} does not support {capability}",
        retryable=False,
    )
