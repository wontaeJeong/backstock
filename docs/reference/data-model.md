# Data Model Reference

- Instrument: canonical symbol, exchange, currency, active range
- ProviderSymbol: provider symbol과 유효 기간
- DatasetSnapshot: provider/version/acquired_at/query, canonical/provider symbol, `[start,end)`, timezone,
  가격·volume adjustment, row count, immutable logical manifest/Parquet URI, raw/normalized checksum, schema
  version, `VALID`/`VALID_WITH_WARNINGS` status와 warning. 현재 authority는 write-once manifest이며 Prompt 08의
  DB record는 update/delete를 금지한다.
- Strategy/StrategyVersion: immutable canonical JSON과 hash
- BacktestRun: status, strategy version, immutable snapshot id/checksum, config, versions, seed. Prompt 08에서
  snapshot DB 등록과 같은 transaction boundary로 고정한다.
- OrderIntent: side, sizing, order type, trigger, reason
- Order: state, requested/filled quantity, prices, TIF
- Fill: timestamp, quantity, price, commission, tax, slippage
- PortfolioSnapshot: cash, market value, equity, realized/unrealized P&L
