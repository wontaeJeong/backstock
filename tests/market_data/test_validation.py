from datetime import UTC, date, datetime
from decimal import Decimal

from packages.domain.market_data import (
    AdjustmentMode,
    Bar,
    BarRequest,
    CorporateAction,
    CorporateActionKind,
    ExchangeSession,
    Instrument,
    TimestampProvenance,
)
from packages.market_data.validation import (
    DatasetValidationInput,
    ValidationCode,
    ValidationStatus,
    compare_provider_bars,
    validate_dataset,
)


def _instrument() -> Instrument:
    return Instrument(
        instrument_id="US:XNAS:TEST",
        symbol="TEST",
        exchange="XNAS",
        currency="USD",
        timezone="America/New_York",
    )


def _request(adjustment: AdjustmentMode = AdjustmentMode.RAW) -> BarRequest:
    return BarRequest(
        instrument=_instrument(),
        start=datetime(2024, 1, 2, tzinfo=UTC),
        end=datetime(2024, 1, 5, tzinfo=UTC),
        adjustment=adjustment,
    )


def _bar(
    day: int,
    *,
    price: str = "100",
    volume: int = 100,
    provenance: TimestampProvenance = TimestampProvenance.EXPLICIT_OFFSET,
    adjustments: tuple[AdjustmentMode, AdjustmentMode] = (
        AdjustmentMode.RAW,
        AdjustmentMode.RAW,
    ),
) -> Bar:
    parsed = Decimal(price)
    return Bar(
        instrument_id=_instrument().instrument_id,
        timestamp=datetime(2024, 1, day, tzinfo=UTC),
        open=parsed,
        high=parsed + 10,
        low=parsed - 10,
        close=parsed,
        volume=volume,
        price_adjustment=adjustments[0],
        volume_adjustment=adjustments[1],
        timestamp_provenance=provenance,
    )


def _session(day: int) -> ExchangeSession:
    return ExchangeSession(
        exchange="XNAS",
        session_date=date(2024, 1, day),
        opens_at=datetime(2024, 1, day, 14, 30, tzinfo=UTC),
        closes_at=datetime(2024, 1, day, 21, tzinfo=UTC),
    )


def test_validation_reports_structural_errors_after_normalization() -> None:
    # Given
    bars = (
        _bar(3),
        _bar(2),
        _bar(2),
        Bar(
            instrument_id=_instrument().instrument_id,
            timestamp=datetime(2024, 1, 4, tzinfo=UTC),
            open=Decimal(0),
            high=Decimal(1),
            low=Decimal(0),
            close=Decimal(2),
            volume=-1,
            price_adjustment=AdjustmentMode.RAW,
            volume_adjustment=AdjustmentMode.RAW,
        ),
    )

    # When
    report = validate_dataset(DatasetValidationInput(request=_request(), bars=bars))

    # Then
    assert report.status is ValidationStatus.INVALID
    assert {issue.code for issue in report.issues} >= {
        ValidationCode.DUPLICATE_TIMESTAMP,
        ValidationCode.OUT_OF_ORDER,
        ValidationCode.NON_POSITIVE_PRICE,
        ValidationCode.INVALID_OHLC,
        ValidationCode.NEGATIVE_VOLUME,
        ValidationCode.NO_EXCHANGE_CALENDAR,
    }


def test_validation_warns_for_provenance_range_calendar_and_abnormal_move() -> None:
    # Given
    bars = (
        _bar(2, provenance=TimestampProvenance.INFERRED_FROM_INSTRUMENT),
        _bar(4, price="200"),
    )
    sessions = (_session(2), _session(3))

    # When
    report = validate_dataset(
        DatasetValidationInput(request=_request(), bars=bars, sessions=sessions)
    )

    # Then
    assert report.status is ValidationStatus.VALID_WITH_WARNINGS
    assert {issue.code for issue in report.issues} == {
        ValidationCode.NAIVE_TIMEZONE_INFERRED,
        ValidationCode.INCOMPLETE_RANGE,
        ValidationCode.CALENDAR_MISMATCH,
        ValidationCode.ABNORMAL_MOVE,
    }


def test_validation_rejects_empty_and_out_of_range_datasets() -> None:
    # Given / When
    empty = validate_dataset(DatasetValidationInput(request=_request(), bars=()))
    outside = validate_dataset(
        DatasetValidationInput(request=_request(), bars=(_bar(5),), sessions=(_session(2),))
    )

    # Then
    assert empty.status is ValidationStatus.INVALID
    assert ValidationCode.EMPTY_DATASET in {issue.code for issue in empty.issues}
    assert outside.status is ValidationStatus.INVALID
    assert ValidationCode.OUTSIDE_REQUEST_RANGE in {issue.code for issue in outside.issues}


def test_split_action_checks_price_and_volume_consistency() -> None:
    # Given
    bars = (
        _bar(2, price="100", volume=100),
        _bar(3, price="90", volume=110),
    )
    action = CorporateAction(
        instrument_id=_instrument().instrument_id,
        effective_at=datetime(2024, 1, 3, tzinfo=UTC),
        kind=CorporateActionKind.SPLIT,
        value=Decimal(2),
    )

    # When
    report = validate_dataset(
        DatasetValidationInput(
            request=_request(), bars=bars, sessions=(_session(2), _session(3)), actions=(action,)
        )
    )

    # Then
    assert ValidationCode.CORPORATE_ACTION_MISMATCH in {issue.code for issue in report.issues}


def test_raw_split_accepts_inverse_price_and_proportional_volume() -> None:
    bars = (_bar(2, price="100", volume=100), _bar(3, price="50", volume=200))
    action = CorporateAction(
        instrument_id=_instrument().instrument_id,
        effective_at=datetime(2024, 1, 3, tzinfo=UTC),
        kind=CorporateActionKind.SPLIT,
        value=Decimal(2),
    )

    report = validate_dataset(
        DatasetValidationInput(
            request=_request(), bars=bars, sessions=(_session(2), _session(3)), actions=(action,)
        )
    )

    assert ValidationCode.CORPORATE_ACTION_MISMATCH not in {issue.code for issue in report.issues}


def test_raw_split_rejects_unadjusted_volume() -> None:
    bars = (_bar(2, price="100", volume=100), _bar(3, price="50", volume=100))
    action = CorporateAction(
        instrument_id=_instrument().instrument_id,
        effective_at=datetime(2024, 1, 3, tzinfo=UTC),
        kind=CorporateActionKind.SPLIT,
        value=Decimal(2),
    )

    report = validate_dataset(
        DatasetValidationInput(
            request=_request(), bars=bars, sessions=(_session(2), _session(3)), actions=(action,)
        )
    )

    assert ValidationCode.CORPORATE_ACTION_MISMATCH in {issue.code for issue in report.issues}


def test_split_adjusted_bars_accept_continuous_price_and_volume() -> None:
    bars = tuple(
        _bar(
            day,
            adjustments=(AdjustmentMode.SPLIT_ADJUSTED, AdjustmentMode.SPLIT_ADJUSTED),
        )
        for day in (2, 3)
    )
    action = CorporateAction(
        instrument_id=_instrument().instrument_id,
        effective_at=datetime(2024, 1, 3, tzinfo=UTC),
        kind=CorporateActionKind.SPLIT,
        value=Decimal(2),
    )

    report = validate_dataset(
        DatasetValidationInput(
            request=_request(AdjustmentMode.SPLIT_ADJUSTED),
            bars=bars,
            sessions=(_session(2), _session(3)),
            actions=(action,),
        )
    )

    assert ValidationCode.CORPORATE_ACTION_MISMATCH not in {issue.code for issue in report.issues}


def test_half_open_request_range_accepts_start_and_rejects_end() -> None:
    request = _request()
    at_start = _bar(2)
    at_end = _bar(5)

    accepted = validate_dataset(DatasetValidationInput(request=request, bars=(at_start,)))
    rejected = validate_dataset(DatasetValidationInput(request=request, bars=(at_end,)))

    assert ValidationCode.OUTSIDE_REQUEST_RANGE not in {issue.code for issue in accepted.issues}
    assert ValidationCode.OUTSIDE_REQUEST_RANGE in {issue.code for issue in rejected.issues}


def test_validation_rejects_prices_that_exceed_parquet_decimal_precision() -> None:
    oversized = Decimal(10**38)
    bar = _bar(2).model_copy(
        update={
            "open": oversized,
            "high": oversized,
            "low": oversized,
            "close": oversized,
        }
    )

    report = validate_dataset(DatasetValidationInput(request=_request(), bars=(bar,)))

    assert report.status is ValidationStatus.INVALID
    assert ValidationCode.UNSUPPORTED_PRICE_PRECISION in {issue.code for issue in report.issues}


def test_cross_provider_comparison_warns_without_merging() -> None:
    # Given
    primary = (_bar(2), _bar(3))
    secondary = (_bar(2), _bar(3, price="105"))

    # When
    report = compare_provider_bars(primary, secondary)

    # Then
    assert report.status is ValidationStatus.VALID_WITH_WARNINGS
    assert [issue.code for issue in report.issues] == [ValidationCode.PROVIDER_MISMATCH]
    assert primary[1].close == Decimal(100)


def test_dividend_consistency_uses_explicit_total_return_semantics() -> None:
    # Given
    raw_bars = (_bar(2), _bar(3))
    adjusted_bars = tuple(
        bar.model_copy(update={"price_adjustment": AdjustmentMode.TOTAL_RETURN_ADJUSTED})
        for bar in raw_bars
    )
    action = CorporateAction(
        instrument_id=_instrument().instrument_id,
        effective_at=datetime(2024, 1, 3, tzinfo=UTC),
        kind=CorporateActionKind.CASH_DIVIDEND,
        value=Decimal(5),
        currency="USD",
    )
    sessions = (_session(2), _session(3))

    # When
    raw = validate_dataset(
        DatasetValidationInput(
            request=_request(), bars=raw_bars, sessions=sessions, actions=(action,)
        )
    )
    adjusted = validate_dataset(
        DatasetValidationInput(
            request=_request(AdjustmentMode.TOTAL_RETURN_ADJUSTED),
            bars=adjusted_bars,
            sessions=sessions,
            actions=(action,),
        )
    )

    # Then
    assert ValidationCode.CORPORATE_ACTION_MISMATCH in {issue.code for issue in raw.issues}
    assert ValidationCode.CORPORATE_ACTION_MISMATCH not in {issue.code for issue in adjusted.issues}
