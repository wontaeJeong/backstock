from dataclasses import dataclass
from datetime import datetime
from typing import Final, Protocol

from packages.market_data.errors import MarketDataError, ProviderErrorCategory

UNAWARE_MAPPING: Final = "provider symbol mapping bounds must be timezone-aware"
INVALID_MAPPING: Final = "provider symbol mapping end must be after start"
OVERLAPPING_MAPPING: Final = "provider symbol mappings must not overlap"


@dataclass(frozen=True)
class EffectiveProviderSymbol:
    provider: str
    instrument_id: str
    symbol: str
    valid_from: datetime
    valid_to: datetime | None = None

    def __post_init__(self) -> None:
        """Reject invalid effective-date windows at construction."""
        bounds = (self.valid_from,) if self.valid_to is None else (self.valid_from, self.valid_to)
        if any(bound.tzinfo is None or bound.utcoffset() is None for bound in bounds):
            raise ValueError(UNAWARE_MAPPING)
        if self.valid_to is not None and self.valid_to <= self.valid_from:
            raise ValueError(INVALID_MAPPING)


class ProviderSymbolResolver(Protocol):
    def resolve(
        self, *, provider: str, instrument_id: str, start: datetime, end: datetime
    ) -> str: ...


class StaticProviderSymbolResolver:
    _mappings: tuple[EffectiveProviderSymbol, ...]

    def __init__(self, mappings: tuple[EffectiveProviderSymbol, ...]) -> None:
        """Build an immutable resolver after rejecting ambiguous mapping windows."""
        self._validate_non_overlapping(mappings)
        self._mappings = mappings

    def resolve(self, *, provider: str, instrument_id: str, start: datetime, end: datetime) -> str:
        matches = tuple(
            mapping
            for mapping in self._mappings
            if mapping.provider == provider
            and mapping.instrument_id == instrument_id
            and mapping.valid_from <= start
            and (mapping.valid_to is None or end <= mapping.valid_to)
        )
        if len(matches) != 1:
            raise MarketDataError(
                provider=provider,
                category=ProviderErrorCategory.INVALID_REQUEST,
                message="request has no unambiguous provider symbol for its entire interval",
                retryable=False,
            )
        return matches[0].symbol

    @staticmethod
    def _validate_non_overlapping(mappings: tuple[EffectiveProviderSymbol, ...]) -> None:
        for index, left in enumerate(mappings):
            for right in mappings[index + 1 :]:
                same_instrument = (
                    left.provider == right.provider and left.instrument_id == right.instrument_id
                )
                same_symbol = left.provider == right.provider and left.symbol == right.symbol
                if (same_instrument or same_symbol) and _overlaps(left, right):
                    raise ValueError(OVERLAPPING_MAPPING)


def _overlaps(left: EffectiveProviderSymbol, right: EffectiveProviderSymbol) -> bool:
    left_before_right_end = right.valid_to is None or left.valid_from < right.valid_to
    right_before_left_end = left.valid_to is None or right.valid_from < left.valid_to
    return left_before_right_end and right_before_left_end
