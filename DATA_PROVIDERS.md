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

`RAW`는 `auto_adjust=False`, `TOTAL_RETURN_ADJUSTED`는 `auto_adjust=True`로 요청한다.
yfinance는 split-only 보정 의미를 보장하지 않으므로 `SPLIT_ADJUSTED` 요청을 명시적으로 거부한다.
`TOTAL_RETURN_ADJUSTED`는
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

로컬 `BarRequest.interval`은 `1d`/`1m`/`5m`를 명시한다. 분봉은 **종료 시각** timestamp와
명시적 UTC offset이 필수이며 naive timestamp의 자동 시간대 추론을 거부한다. simulation은 뉴욕
정규장·동일 날짜의 1분/5분 연속 간격을 검사하고 일봉에 하루 여러 bar가 있으면 거부한다.
Yahoo 원격 경로는 일봉만 제공하며 분봉 요청을 자동 일봉으로 바꾸지 않는다.
업로드 파일의 실제 시세 출처·기업 이벤트 의미는 사용자가 확인해야 한다. 25 MiB 업로드 제한과
3,000 bar 실행 제한은 서로 별개다. 파일 전체가 요청 범위 안에 있어야 하며 범위 밖 행은 거부한다.

CSV/Parquet를 읽으며 fixture와 재현성의 기준이다.

필수 컬럼: `timestamp, open, high, low, close, volume`

권장 컬럼: `instrument, exchange, currency, adjusted_close, source, timezone`

파일을 등록할 때 instrument, 가격과 volume 각각의 `RAW`/`SPLIT_ADJUSTED`/
`TOTAL_RETURN_ADJUSTED` 의미를 명시해야 한다. 요청 의미가 등록 값과
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
- 가격과 volume에 `RAW`, `SPLIT_ADJUSTED`, `TOTAL_RETURN_ADJUSTED` 중 하나를 각각 명시
- 공급자 간 차이는 validation job으로 보고하며 자동 병합 금지
- corporate action으로 bar를 검증하는 adapter는 같은 raw acquisition에 둘을 묶고 lineage checksum이
  다르면 snapshot을 게시하지 않음

sidecar 전체는 artifact ID로 integrity binding하며 request option은 immutable tuple로 보존한다. 동일 요청
cache는 TTL 동안 immutable raw artifact를 참조하고 atomic replace로 게시한다. 손상된 cache는 miss로 처리한다.
네트워크 재시도는 알려진 transport/quota 오류에만 bounded exponential backoff와 jitter를 적용하며
`Retry-After`도 policy 최대 delay를 넘지 않는다.

instrument identity는 canonical `instrument_id`와 provider symbol을 분리한다. DB mapping은
`provider + provider_symbol + valid_from`을 key로 사용하여 symbol 재사용과 매핑 변경 이력을 덮어쓰지 않는다.
PostgreSQL exclusion constraint는 같은 provider symbol 또는 같은 provider instrument의 유효 기간 중첩을 막는다.
## 품질 검사와 snapshot

정규화된 bar는 순서를 바꾸거나 누락 값을 채우기 전에 순수 validator를 통과한다. 중복·역순 timestamp,
timezone 추론 provenance, 0 이하 가격, OHLC 범위, 음수 volume, 빈 데이터, 요청 범위 이탈과 Parquet
decimal 38자리로 lossless 저장할 수 없는 가격은 오류다. calendar가 있으면 누락 구간/초과 거래일을,
corporate action이 있으면 split/dividend에 따른 가격·volume
일관성을 검사한다. calendar가 없으면 거래일을 추측하지 않고 `no_exchange_calendar` 경고를 남긴다.
종가 간 50% 초과 변화와 provider 간 같은 timestamp 종가 1% 초과 차이는 경고이며 자동 병합하지 않는다.

유효한 결과만 deterministic Parquet로 content-addressed `normalized/` 영역에 게시한다. write-once JSON
manifest는 `snapshots/` 영역에 분리하고 raw/normalized checksum, 취득 시점, provider/query/symbol,
가격·volume adjustment, 품질 상태와 경고를 기록한다. 같은 provider 결과는 같은 snapshot을 재사용하고
새 취득 시점의 갱신은 새 snapshot id를 만든다. manifest URI는 `snapshot://` logical key라 storage root를
옮겨도 identity가 바뀌지 않으며 실제 filesystem 경로는 API에 노출하지 않는다. 어떤 단계에서도
forward-fill하지 않는다.
