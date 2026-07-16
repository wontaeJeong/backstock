# Data Providers

## 목적

공급자별 차이를 앱 전체에 퍼뜨리지 않고 공통 schema와 snapshot 계약으로 관리한다.

## 구현된 공급자와 capability

| 공급자 | 일봉 | corporate action | 종목 검색 | 거래소 calendar |
| --- | --- | --- | --- | --- |
| `YFinanceProvider` | 지원 | 지원 | 미지원 | 미지원 |
| `LocalFileProvider` | 지원 | 미지원 | 미지원 | 미지원 |
| `FinanceDataReaderProvider` | 미지원 | 미지원 | 현재 KRX 목록만 지원 | 미지원 |

미지원 capability는 빈 결과가 아니라 typed `NOT_SUPPORTED` 오류를 반환한다. 공급자 오류는
`network`, `authentication`, `quota`, `invalid_request`, `not_supported`, `parse`, `provider`로
분류하며 다른 공급자로 자동 전환하지 않는다.

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

`RAW`는 `auto_adjust=False`, `ADJUSTED`는 `auto_adjust=True`로 요청한다. yfinance의 `ADJUSTED`는
가격 OHLC만 소급 보정하고 volume은 raw share count로 유지하므로 `Bar.price_adjustment`와
`Bar.volume_adjustment`를 별도로 기록한다. 소급 보정 가격은 취득 시점 기준 결과이며 point-in-time
historical value가 아니다. 현재 yfinance가
upstream HTTP response body를 공개하지 않으므로 raw artifact는 yfinance DataFrame을 그대로
CSV로 직렬화한 adapter 입력이다. sidecar의 media type에 `profile=yfinance-history`를 기록하며
Yahoo 원본 HTTP bytes라고 주장하지 않는다.

한국 예:
- `KRX:005930` → `005930.KS`
- KOSDAQ symbol은 시장 metadata로 `.KQ` 매핑
- canonical symbol과 provider symbol을 분리

Yahoo 요청은 canonical symbol을 직접 보내지 않는다. effective-dated provider mapping resolver가 요청
전체 `[start, end)`를 덮는 symbol 하나를 찾아야 하며 mapping 전환 시점을 가로지르는 요청은 거부한다.

## LocalFileProvider

CSV/Parquet를 읽으며 fixture와 재현성의 기준이다.

필수 컬럼: `timestamp, open, high, low, close, volume`

권장 컬럼: `instrument, exchange, currency, adjusted_close, source, timezone`

파일을 등록할 때 instrument, 가격과 volume 각각의 `RAW`/`ADJUSTED` 의미를 명시해야 한다. 요청 의미가 등록 값과
다르면 거부한다. CSV와 Parquet 모두 원본 파일 bytes를 보존하고 Polars로 정규화한다.

## FinanceDataReaderProvider

현재 KRX 종목 목록 검색에만 사용한다. 이 목록은 point-in-time historical universe가 아니며
과거 백테스트 universe로 사용할 수 없다. listing artifact에는 `listing_scope=current`를 기록한다.
취득은 10초 timeout이 있는 HTTPS transport를 사용하며 work-date와 listing HTTP body 원문 두 개를
base64 deterministic JSON envelope로 먼저 저장한 뒤 3-column listing schema로 정규화한다.

## 공통 계약

`search_instruments`, `get_bars`, `get_corporate_actions`, `get_exchange_calendar`.

정규 모델은 `Instrument`, `Bar`, `CorporateAction`, `ExchangeSession`이다. timestamp는 timezone-aware,
가격과 action 값은 `Decimal`, volume은 integer다. bar는 가격·volume adjustment를 분리하고
요청 구간은 `[start, end)`다.

## 정책

- 실행 전 provider를 명시
- 실패 시 silent fallback 금지
- request cache와 immutable raw artifact 분리
- raw payload와 provider/version/request/fetched_at/media type/checksum sidecar 함께 저장
- `RAW`, `ADJUSTED`를 요청과 결과에 명시
- 공급자 간 차이는 validation job으로 보고하며 자동 병합 금지

sidecar 전체는 artifact ID로 integrity binding하며 request option은 immutable tuple로 보존한다. 동일 요청
cache는 TTL 동안 immutable raw artifact를 참조하고 atomic replace로 게시한다. 손상된 cache는 miss로 처리한다.
네트워크 재시도는 알려진 transport/quota 오류에만 bounded exponential backoff와 jitter를 적용하며
`Retry-After`도 policy 최대 delay를 넘지 않는다.

instrument identity는 canonical `instrument_id`와 provider symbol을 분리한다. DB mapping은
`provider + provider_symbol + valid_from`을 key로 사용하여 symbol 재사용과 매핑 변경 이력을 덮어쓰지 않는다.
PostgreSQL exclusion constraint는 같은 provider symbol 또는 같은 provider instrument의 유효 기간 중첩을 막는다.
normalized snapshot manifest와 품질 상태는 Prompt 04 범위다.
