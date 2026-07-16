from enum import StrEnum


class ProviderErrorCategory(StrEnum):
    NETWORK = "network"
    AUTHENTICATION = "authentication"
    QUOTA = "quota"
    INVALID_REQUEST = "invalid_request"
    NOT_SUPPORTED = "not_supported"
    PARSE = "parse"
    PROVIDER = "provider"


class MarketDataError(Exception):
    provider: str
    category: ProviderErrorCategory
    retryable: bool
    retry_after_seconds: float | None

    def __init__(
        self,
        *,
        provider: str,
        category: ProviderErrorCategory,
        message: str,
        retryable: bool,
        retry_after_seconds: float | None = None,
    ) -> None:
        """Create a sanitized provider failure safe for application boundaries."""
        super().__init__(message)
        self.provider = provider
        self.category = category
        self.retryable = retryable
        self.retry_after_seconds = retry_after_seconds
