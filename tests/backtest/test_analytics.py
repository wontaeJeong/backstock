from datetime import UTC, datetime
from decimal import Decimal

from packages.backtest.analytics import maximum_drawdown
from packages.backtest.models import PortfolioSnapshot


def test_maximum_drawdown_includes_initial_capital() -> None:
    points = tuple(
        PortfolioSnapshot(
            timestamp=datetime(2024, 1, index + 1, tzinfo=UTC),
            cash=Decimal(value),
            market_value=Decimal(0),
            equity=Decimal(value),
            realized_pnl=Decimal(0),
            unrealized_pnl=Decimal(0),
            positions=(),
        )
        for index, value in enumerate(("900", "1200", "960", "1100"))
    )
    assert maximum_drawdown(Decimal(1000), points) == Decimal("0.2")
    assert maximum_drawdown(Decimal(1000), ()) == 0
