# Data Providers

## 목적

공급자별 차이를 앱 전체에 퍼뜨리지 않고 공통 schema와 snapshot 계약으로 관리한다.

## YFinanceProvider

MVP 기본 원격 공급자다.

장점:
- API key 없이 시작 가능
- 미국·한국 등 다양한 symbol
- OHLCV와 corporate action

주의:
- Yahoo와 제휴된 공식 SDK가 아니다.
- endpoint·응답·기본 옵션이 변경될 수 있다.
- 데이터 사용 조건을 확인해야 한다.
- 실거래 판단 전 별도 데이터로 검증한다.

기록:
- yfinance version
- provider symbol
- start/end/interval
- auto_adjust/actions
- timezone
- fetched_at
- raw checksum

한국 예:
- `KRX:005930` → `005930.KS`
- KOSDAQ symbol은 시장 metadata로 `.KQ` 매핑
- canonical symbol과 provider symbol을 분리

## LocalFileProvider

CSV/Parquet를 읽으며 fixture와 재현성의 기준이다.

필수 컬럼: `timestamp, open, high, low, close, volume`

권장 컬럼: `instrument, exchange, currency, adjusted_close, source, timezone`

## FinanceDataReaderProvider

KRX 종목 목록과 한국 시장 보조 데이터에 사용한다. 외부 사이트 또는 cache 변화 가능성을 고려한다.

## AlphaVantageProvider

API key 기반 선택 공급자다. quota와 rate limit을 처리한다.

## StooqProvider

과거 데이터 보조 공급자다. 자동화가 불안정하면 파일 import로 사용한다.

## 공통 계약

`search_instruments`, `get_bars`, `get_corporate_actions`, `get_trading_calendar`, `healthcheck`.

## 정책

- 실행 전 provider를 명시
- 실패 시 silent fallback 금지
- request cache와 immutable raw/normalized snapshot 분리
- `RAW`, `SPLIT_ADJUSTED`, `TOTAL_RETURN_ADJUSTED` 구분
- 공급자 간 차이는 validation job으로 보고하며 자동 병합 금지
