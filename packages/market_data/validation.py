from dataclasses import dataclass
from datetime import UTC
from decimal import Decimal
from enum import StrEnum
from itertools import pairwise
from typing import Final
from zoneinfo import ZoneInfo

from packages.domain.market_data import (
    Bar,
    BarRequest,
    CorporateAction,
    ExchangeSession,
    TimestampProvenance,
    corporate_actions_are_consistent,
)

ABNORMAL_MOVE_THRESHOLD: Final = Decimal("0.50")
PROVIDER_DIFFERENCE_THRESHOLD: Final = Decimal("0.01")
PARQUET_DECIMAL_PRECISION: Final = 38


class ValidationStatus(StrEnum):
    VALID = "valid"
    VALID_WITH_WARNINGS = "valid_with_warnings"
    INVALID = "invalid"


class ValidationSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


class ValidationCode(StrEnum):
    DUPLICATE_TIMESTAMP = "duplicate_timestamp"
    OUT_OF_ORDER = "out_of_order"
    NAIVE_TIMEZONE_INFERRED = "naive_timezone_inferred"
    NON_POSITIVE_PRICE = "non_positive_price"
    INVALID_OHLC = "invalid_ohlc"
    NEGATIVE_VOLUME = "negative_volume"
    EMPTY_DATASET = "empty_dataset"
    INCOMPLETE_RANGE = "incomplete_range"
    OUTSIDE_REQUEST_RANGE = "outside_request_range"
    NO_EXCHANGE_CALENDAR = "no_exchange_calendar"
    CALENDAR_MISMATCH = "calendar_mismatch"
    ABNORMAL_MOVE = "abnormal_move"
    CORPORATE_ACTION_MISMATCH = "corporate_action_mismatch"
    ADJUSTMENT_MISMATCH = "adjustment_mismatch"
    PROVIDER_MISMATCH = "provider_mismatch"
    NORMALIZATION_ERROR = "normalization_error"
    UNSUPPORTED_PRICE_PRECISION = "unsupported_price_precision"
    LINEAGE_MISMATCH = "lineage_mismatch"


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    code: ValidationCode
    severity: ValidationSeverity
    message: str


@dataclass(frozen=True, slots=True)
class ValidationReport:
    status: ValidationStatus
    issues: tuple[ValidationIssue, ...]


@dataclass(frozen=True, slots=True)
class DatasetValidationInput:
    request: BarRequest
    bars: tuple[Bar, ...]
    sessions: tuple[ExchangeSession, ...] = ()
    actions: tuple[CorporateAction, ...] = ()


def validate_dataset(dataset: DatasetValidationInput) -> ValidationReport:
    issues: list[ValidationIssue] = []
    _validate_bar_values(dataset, issues)
    _validate_calendar(dataset, issues)
    _validate_moves(dataset.bars, issues)
    if not corporate_actions_are_consistent(dataset.bars, dataset.actions):
        _add(
            issues,
            ValidationCode.CORPORATE_ACTION_MISMATCH,
            ValidationSeverity.WARNING,
            "price or volume move conflicts with a corporate action",
        )
    return _report(issues)


def _validate_bar_values(dataset: DatasetValidationInput, issues: list[ValidationIssue]) -> None:
    bars = dataset.bars
    if not bars:
        _add(issues, ValidationCode.EMPTY_DATASET, ValidationSeverity.ERROR, "dataset has no bars")
    timestamps = [bar.timestamp.astimezone(UTC) for bar in bars]
    if len(timestamps) != len(set(timestamps)):
        _add(
            issues,
            ValidationCode.DUPLICATE_TIMESTAMP,
            ValidationSeverity.ERROR,
            "timestamps repeat",
        )
    if timestamps != sorted(timestamps):
        _add(
            issues,
            ValidationCode.OUT_OF_ORDER,
            ValidationSeverity.ERROR,
            "timestamps are unsorted",
        )
    if any(
        bar.timestamp_provenance is TimestampProvenance.INFERRED_FROM_INSTRUMENT for bar in bars
    ):
        _add(
            issues,
            ValidationCode.NAIVE_TIMEZONE_INFERRED,
            ValidationSeverity.WARNING,
            "source timestamps omitted timezone offsets",
        )
    if any(min(bar.open, bar.high, bar.low, bar.close) <= 0 for bar in bars):
        _add(
            issues,
            ValidationCode.NON_POSITIVE_PRICE,
            ValidationSeverity.ERROR,
            "price is not positive",
        )
    if any(
        bar.low > bar.high
        or not bar.low <= bar.open <= bar.high
        or not bar.low <= bar.close <= bar.high
        for bar in bars
    ):
        _add(issues, ValidationCode.INVALID_OHLC, ValidationSeverity.ERROR, "OHLC bounds conflict")
    if any(bar.volume < 0 for bar in bars):
        _add(issues, ValidationCode.NEGATIVE_VOLUME, ValidationSeverity.ERROR, "volume is negative")
    _validate_price_precision(bars, issues)
    start = dataset.request.start.astimezone(UTC)
    end = dataset.request.end.astimezone(UTC)
    if any(timestamp < start or timestamp >= end for timestamp in timestamps):
        _add(
            issues,
            ValidationCode.OUTSIDE_REQUEST_RANGE,
            ValidationSeverity.ERROR,
            "bars fall outside the requested half-open range",
        )
    if any(
        bar.instrument_id != dataset.request.instrument.instrument_id
        or bar.price_adjustment is not dataset.request.adjustment
        or bar.volume_adjustment is not bars[0].volume_adjustment
        for bar in bars
    ):
        _add(
            issues,
            ValidationCode.ADJUSTMENT_MISMATCH,
            ValidationSeverity.ERROR,
            "bar identity or adjustment semantics are inconsistent",
        )


def compare_provider_bars(primary: tuple[Bar, ...], secondary: tuple[Bar, ...]) -> ValidationReport:
    issues: list[ValidationIssue] = []
    secondary_by_time = {bar.timestamp.astimezone(UTC): bar for bar in secondary}
    shared = 0
    for bar in primary:
        peer = secondary_by_time.get(bar.timestamp.astimezone(UTC))
        if peer is None:
            continue
        shared += 1
        if bar.close and abs(peer.close / bar.close - 1) > PROVIDER_DIFFERENCE_THRESHOLD:
            _add(
                issues,
                ValidationCode.PROVIDER_MISMATCH,
                ValidationSeverity.WARNING,
                "provider close prices differ",
            )
    if shared != len(primary) or shared != len(secondary):
        _add(
            issues,
            ValidationCode.PROVIDER_MISMATCH,
            ValidationSeverity.WARNING,
            "provider timestamp coverage differs",
        )
    return _report(issues)


def _validate_calendar(dataset: DatasetValidationInput, issues: list[ValidationIssue]) -> None:
    if not dataset.sessions:
        _add(
            issues,
            ValidationCode.NO_EXCHANGE_CALENDAR,
            ValidationSeverity.WARNING,
            "exchange calendar was unavailable; missing sessions were not inferred",
        )
        return
    timezone = ZoneInfo(dataset.request.instrument.timezone)
    actual = {bar.timestamp.astimezone(timezone).date() for bar in dataset.bars}
    expected = {session.session_date for session in dataset.sessions}
    if expected - actual:
        _add(
            issues,
            ValidationCode.INCOMPLETE_RANGE,
            ValidationSeverity.WARNING,
            "expected exchange sessions are missing",
        )
    if actual - expected:
        _add(
            issues,
            ValidationCode.CALENDAR_MISMATCH,
            ValidationSeverity.WARNING,
            "bars occur outside supplied sessions",
        )


def _validate_moves(bars: tuple[Bar, ...], issues: list[ValidationIssue]) -> None:
    ordered = sorted(bars, key=lambda bar: bar.timestamp)
    if any(
        previous.close > 0 and abs(current.close / previous.close - 1) > ABNORMAL_MOVE_THRESHOLD
        for previous, current in pairwise(ordered)
    ):
        _add(
            issues,
            ValidationCode.ABNORMAL_MOVE,
            ValidationSeverity.WARNING,
            "large move detected",
        )


def parquet_decimal_scale(bars: tuple[Bar, ...]) -> int | None:
    scale = 0
    integer_digits = 0
    for bar in bars:
        for value in (bar.open, bar.high, bar.low, bar.close, bar.bid, bar.ask):
            if value is None:
                continue
            exponent = _decimal_exponent(value)
            if exponent is None:
                return None
            digits = value.as_tuple().digits
            while digits and digits[-1] == 0:
                digits = digits[:-1]
                exponent += 1
            value_scale = max(0, -exponent)
            value_integer_digits = max(0, len(digits) + exponent)
            scale = max(scale, value_scale)
            integer_digits = max(integer_digits, value_integer_digits)
    return scale if scale + integer_digits <= PARQUET_DECIMAL_PRECISION else None


def _decimal_exponent(value: Decimal) -> int | None:
    match value.as_tuple().exponent:
        case int() as exponent:
            return exponent
        case "n" | "N" | "F":
            return None


def _validate_price_precision(bars: tuple[Bar, ...], issues: list[ValidationIssue]) -> None:
    if parquet_decimal_scale(bars) is None:
        _add(
            issues,
            ValidationCode.UNSUPPORTED_PRICE_PRECISION,
            ValidationSeverity.ERROR,
            "prices exceed the lossless Parquet decimal precision",
        )


def _add(
    issues: list[ValidationIssue],
    code: ValidationCode,
    severity: ValidationSeverity,
    message: str,
) -> None:
    if any(issue.code is code for issue in issues):
        return
    issues.append(ValidationIssue(code=code, severity=severity, message=message))


def _report(issues: list[ValidationIssue]) -> ValidationReport:
    if any(issue.severity is ValidationSeverity.ERROR for issue in issues):
        status = ValidationStatus.INVALID
    elif issues:
        status = ValidationStatus.VALID_WITH_WARNINGS
    else:
        status = ValidationStatus.VALID
    return ValidationReport(status=status, issues=tuple(issues))
