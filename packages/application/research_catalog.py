"""Small explicitly curated current catalog, never a historical/PIT universe."""

CATALOG = (
    ("AAPL", "Apple"),
    ("MSFT", "Microsoft"),
    ("NVDA", "NVIDIA"),
    ("AMZN", "Amazon"),
    ("GOOGL", "Alphabet"),
    ("META", "Meta Platforms"),
    ("QQQ", "Invesco QQQ ETF"),
    ("TSLA", "Tesla"),
    ("AVGO", "Broadcom"),
    ("COST", "Costco"),
    ("NFLX", "Netflix"),
    ("AMD", "Advanced Micro Devices"),
    ("ADBE", "Adobe"),
    ("INTC", "Intel"),
    ("CSCO", "Cisco"),
    ("PEP", "PepsiCo"),
    ("AMGN", "Amgen"),
    ("TXN", "Texas Instruments"),
    ("INTU", "Intuit"),
    ("QCOM", "Qualcomm"),
)
SYMBOLS = tuple(symbol for symbol, _ in CATALOG)


def search_catalog(query: str) -> list[dict[str, str]]:
    needle = query.strip().casefold()
    return [
        {"symbol": symbol, "name": name}
        for symbol, name in CATALOG
        if needle in symbol.casefold() or needle in name.casefold()
    ]
