from decimal import Decimal

from packages.backtest.models import PortfolioSnapshot


def maximum_drawdown(initial_cash: Decimal, points: tuple[PortfolioSnapshot, ...]) -> Decimal:
    """Return the peak-to-trough equity loss as a nonnegative fraction."""
    peak = initial_cash
    maximum = Decimal(0)
    for point in points:
        peak = max(peak, point.equity)
        maximum = max(maximum, (peak - point.equity) / peak)
    return maximum
