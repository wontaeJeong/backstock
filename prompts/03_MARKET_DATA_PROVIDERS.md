# 3단계 — 무료 시장 데이터 공급자

`00_GLOBAL_RULES.md`와 이전 구현을 적용한다.

Yahoo Finance 계열 데이터를 기본 개발 공급자로 사용하되 공급자별 차이를 어댑터로 격리한다.

## 공급자

### YFinanceProvider
- MVP 기본 원격 공급자
- 과거 OHLCV와 corporate action
- 한국 symbol 매핑: `005930.KS`, `035720.KQ`
- `auto_adjust`, `actions`, interval, timezone 옵션을 명시
- package version과 요청 옵션 저장
- 빈 응답, rate limit, schema 변화, timeout 처리
- 비공식 연구용 공급자 경고 표시

### LocalFileProvider
- CSV/Parquet
- fixture와 재현성의 기준 공급자

### FinanceDataReaderProvider
- KRX 종목 목록 및 한국 시장 보조 공급자
- 외부 사이트·캐시 변화 가능성 고려

### AlphaVantageProvider
- API key 기반 선택 공급자
- quota와 rate limit 처리

### StooqProvider
- 과거 데이터 보조
- 자동 수집이 불안정하면 파일 import를 우선

## 공통 계약

`search_instruments`, `get_instrument`, `get_bars`, `get_corporate_actions`, `get_trading_calendar`, `healthcheck`를 갖는 `MarketDataProvider`를 정의한다.

## 작업

1. 표준 Instrument, Bar, CorporateAction 모델을 만든다.
2. 내부 canonical symbol과 provider symbol을 분리한다.
3. provider capability를 모델링한다.
4. YFinanceProvider와 LocalFileProvider를 실제 구현한다.
5. 최소 한 개 보조 공급자를 실제 구현한다.
6. retry는 제한된 exponential backoff + jitter를 사용한다.
7. request cache와 raw snapshot 저장을 구현한다.
8. 원격 응답을 공통 OHLCV schema로 정규화한다.
9. 공급자별 offline fixture와 contract test를 작성한다.
10. 공급자 실패 시 자동 fallback하지 않는다.
11. `DATA_PROVIDERS.md`를 갱신한다.

## 완료 조건

- Yahoo Finance 일봉을 수집해 raw snapshot으로 저장할 수 있다.
- 네트워크 없이 fixture 테스트가 통과한다.
- 공급자와 옵션을 역추적할 수 있다.
