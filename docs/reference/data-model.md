# Data Model Reference

- Instrument: canonical symbol, exchange, currency, active range
- ProviderSymbol: provider symbol과 유효 기간
- DatasetSnapshot: provider, manifest, checksums, storage URI, status
- Strategy/StrategyVersion: immutable canonical JSON과 hash
- BacktestRun: status, strategy version, snapshot, config, versions, seed
- OrderIntent: side, sizing, order type, trigger, reason
- Order: state, requested/filled quantity, prices, TIF
- Fill: timestamp, quantity, price, commission, tax, slippage
- PortfolioSnapshot: cash, market value, equity, realized/unrealized P&L
