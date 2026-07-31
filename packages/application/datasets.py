from dataclasses import dataclass
from datetime import UTC
from typing import override

from packages.domain.market_data import (
    Bar,
    BarRequest,
    CorporateAction,
    ExchangeCalendarRequest,
    ExchangeSession,
    MarketDataResult,
)
from packages.market_data.contracts import MarketDataProvider
from packages.market_data.errors import MarketDataError, ProviderErrorCategory
from packages.market_data.snapshots import SnapshotManifest, SnapshotStore
from packages.market_data.validation import (
    DatasetValidationInput,
    ValidationCode,
    ValidationIssue,
    ValidationReport,
    ValidationSeverity,
    ValidationStatus,
    compare_provider_bars,
    validate_dataset,
)


@dataclass(frozen=True, slots=True)
class DatasetInvalidError(Exception):
    report: ValidationReport

    @override
    def __str__(self) -> str:
        return "dataset validation failed"


@dataclass(frozen=True, slots=True)
class SnapshotNotFoundError(Exception):
    snapshot_id: str

    @override
    def __str__(self) -> str:
        return f"dataset snapshot {self.snapshot_id} was not found"


class DatasetSnapshotService:
    _store: SnapshotStore

    def __init__(self, store: SnapshotStore) -> None:
        """Create the use case over an immutable snapshot store."""
        self._store = store

    def create_from_provider(
        self, provider: MarketDataProvider, request: BarRequest
    ) -> SnapshotManifest:
        try:
            bars = provider.get_bars(request)
            actions: tuple[CorporateAction, ...] = ()
            sessions: tuple[ExchangeSession, ...] = ()
            if provider.capabilities.corporate_actions:
                action_result = provider.get_corporate_actions(request)
                if action_result.lineage.raw_checksum != bars.lineage.raw_checksum:
                    raise DatasetInvalidError(
                        ValidationReport(
                            status=ValidationStatus.INVALID,
                            issues=(
                                ValidationIssue(
                                    code=ValidationCode.LINEAGE_MISMATCH,
                                    severity=ValidationSeverity.ERROR,
                                    message="bar and corporate-action acquisitions differ",
                                ),
                            ),
                        )
                    )
                actions = action_result.items
            if provider.capabilities.exchange_calendar:
                calendar_request = ExchangeCalendarRequest(
                    exchange=request.instrument.exchange,
                    start=request.start.astimezone(UTC).date(),
                    end=request.end.astimezone(UTC).date(),
                )
                sessions = provider.get_exchange_calendar(calendar_request).items
        except MarketDataError as error:
            if error.category not in (
                ProviderErrorCategory.INVALID_REQUEST,
                ProviderErrorCategory.PARSE,
            ):
                raise
            report = ValidationReport(
                status=ValidationStatus.INVALID,
                issues=(
                    ValidationIssue(
                        code=ValidationCode.NORMALIZATION_ERROR,
                        severity=ValidationSeverity.ERROR,
                        message=str(error),
                    ),
                ),
            )
            raise DatasetInvalidError(report) from error
        return self.create_from_result(request, bars, actions=actions, sessions=sessions)

    def create_from_result(
        self,
        request: BarRequest,
        result: MarketDataResult[Bar],
        *,
        actions: tuple[CorporateAction, ...] = (),
        sessions: tuple[ExchangeSession, ...] = (),
    ) -> SnapshotManifest:
        report = validate_dataset(
            DatasetValidationInput(
                request=request,
                bars=result.items,
                actions=actions,
                sessions=sessions,
            )
        )
        if report.status is ValidationStatus.INVALID:
            raise DatasetInvalidError(report)
        return self._store.publish(request=request, result=result, report=report)

    def get(self, snapshot_id: str) -> SnapshotManifest:
        manifest = self._store.load(snapshot_id)
        if manifest is None:
            raise SnapshotNotFoundError(snapshot_id)
        return manifest


class CrossProviderValidationJob:
    def run(
        self,
        primary: MarketDataProvider,
        secondary: MarketDataProvider,
        request: BarRequest,
    ) -> ValidationReport:
        primary_bars = primary.get_bars(request).items
        secondary_bars = secondary.get_bars(request).items
        return compare_provider_bars(primary_bars, secondary_bars)
