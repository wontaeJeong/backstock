from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from packages.application.research_experiments import _correlations
from tests.research.test_features import client, request


def test_intraday_single_session_has_no_common_daily_returns(tmp_path: Path) -> None:
    base = request().model_dump(mode="json")
    base["strategy"]["timeframe"] = "1m"
    response = client(tmp_path).post(
        "/research/experiments/portfolio",
        json={
            "initial_cash": "1000",
            "components": [
                {"weight": "0.5", "request": base},
                {"weight": "0.5", "request": base},
            ],
        },
    )
    assert response.status_code == 201, response.text
    portfolio = response.json()
    assert len(portfolio["curve"]) == 120
    result = portfolio["correlations"][0]
    assert result["observations"] == 0
    assert result["value"] is None
    assert "daily" in result["reason"]
    assert any("daily" in warning for warning in portfolio["warnings"])
    assert any("same demo price pattern" in warning for warning in portfolio["warnings"])


@pytest.mark.parametrize("wiggle", [Decimal("0.1"), Decimal(10000)])
def test_daily_correlation_uses_last_shared_marks_not_independent_closes(
    wiggle: Decimal,
) -> None:
    zone = ZoneInfo("America/New_York")
    curves: list[dict[datetime, Decimal]] = [{}, {}]
    left_closes = [Decimal(100), Decimal(110), Decimal(88), Decimal("114.4")]
    right_closes = [Decimal(100), Decimal(80), Decimal(88), Decimal("114.4")]
    # Oct 3/5/6 have no shared marks: missing dates must not become zero returns.
    for index, day in enumerate((1, 2, 4, 7)):
        morning = datetime(2024, 10, day, 9, 31, tzinfo=zone).astimezone(UTC)
        noon = morning.replace(hour=16, minute=0)
        last_common = morning.replace(hour=19, minute=59)
        curves[0][morning] = wiggle * (index + 1)
        curves[1][morning] = Decimal(1000) / (index + 1)
        curves[0][noon] = Decimal(500) / (index + 1)
        curves[1][noon] = wiggle * (index + 2)
        curves[0][last_common] = left_closes[index]
        curves[1][last_common] = right_closes[index]
        # Later component closes exist, but at different instants: never pair them.
        curves[0][last_common.replace(hour=20, minute=0)] = wiggle * (index + 3)
        curves[1][last_common.replace(hour=20, minute=1)] = Decimal(2000) / (index + 1)
    curves[0][datetime(2024, 10, 3, 20, tzinfo=UTC)] = Decimal(300)
    common = sorted(curves[0].keys() & curves[1].keys())
    assert len(common) == 12
    result = _correlations(curves, common)[0]
    # Shared daily returns: left [+0.1,-0.2,+0.3], right [-0.2,+0.1,+0.3].
    assert result.observations == 3
    assert result.value is not None
    assert float(result.value) == pytest.approx(11 / 38, abs=1e-14)
    assert result.reason is None


def test_daily_dates_are_new_york_dates_not_utc_dates() -> None:
    # Each pair is one NY date, but straddles UTC midnight.
    marks = [
        datetime(2024, 1, day, hour, tzinfo=UTC)
        for day, hour in ((2, 23), (3, 0), (3, 23), (4, 0), (4, 23), (5, 0))
    ]
    curves = [
        dict(zip(marks, map(Decimal, (1000, 100, 2000, 110, 3000, 88)), strict=True)),
        dict(zip(marks, map(Decimal, (5000, 100, 6000, 80, 7000, 88)), strict=True)),
    ]
    result = _correlations(curves, marks)[0]
    assert result.observations == 2
    assert result.value is not None
    assert float(result.value) == pytest.approx(-1)


def test_nonfinite_statistical_daily_returns_are_null_not_nan() -> None:
    marks = [datetime(2024, 1, day, 21, tzinfo=UTC) for day in (2, 3, 4)]
    curves = [
        dict(zip(marks, map(Decimal, ("1e-500", "100", "110")), strict=True)),
        dict(zip(marks, map(Decimal, ("100", "80", "88")), strict=True)),
    ]
    result = _correlations(curves, marks)[0]
    assert result.observations == 2
    assert result.value is None
    assert result.reason is not None
