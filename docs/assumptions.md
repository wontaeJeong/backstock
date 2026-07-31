# Assumptions

구현 중 선택한 가정을 기록한다. 변경 시 날짜, 이유, 영향 범위를 남긴다.

## 초기 가정

- MVP interval은 일봉이다.
- MVP position은 롱 중심이다.
- 종가 신호의 기본 체결은 다음 거래일 시가다.
- intrabar 모호성은 conservative 정책을 사용한다.
- yfinance는 개발 기본 공급자다.
- LocalFileProvider는 fixture와 재현성의 기준이다.
- PostgreSQL이 기본 DB다.
- 전략은 JSON DSL이며 임의 Python을 실행하지 않는다.
- 실제 주문은 기본 비활성화한다.
- KIS는 모의투자부터 연결한다.
- MCP는 조회와 백테스트부터 제공한다.

## 2026-07-16 저장소 진단

- Python 패키지 관리는 `uv`, 웹 패키지 관리는 `pnpm`을 사용한다. 저장소 규칙의 검증 명령과 맞추기 위한 선택이다.
- PostgreSQL은 운영 목표 DB지만 초기 domain·fixture 테스트는 외부 DB 없이 실행 가능해야 한다.
- 대규모 시계열은 Parquet를 목표로 하되, bootstrap 단계의 smoke path는 작은 고정 fixture를 사용한다.
- job queue 제품 선택 전에는 application port로 경계를 만들고 worker 구현이 특정 queue SDK에 의존하지 않게 한다.

## 변경 템플릿

```text
Date:
Decision:
Reason:
Affected modules:
Migration:
Validation:
```

## 2026-07-31 데이터 품질과 snapshot

- 일봉 close-to-close 절대 변화가 50%를 넘으면 비정상 변화 경고다. corporate action 검사는 별도로 수행한다.
- 같은 timestamp의 provider close가 1%를 초과해 다르면 교차 검증 경고이며 어느 쪽도 자동 선택하거나 병합하지 않는다.
- 거래소 calendar가 없으면 주말/휴장일을 추측하지 않고 `no_exchange_calendar`를 기록한다. calendar가 제공된 경우에만 누락/초과 session을 판정한다.
- naive source timestamp는 instrument IANA timezone으로 정규화하되 provenance와 warning을 남긴다.
- yfinance `auto_adjust=True` 결과는 `TOTAL_RETURN_ADJUSTED` 가격과 `RAW` volume으로 기록한다. split-only 의미는 지원한다고 주장하지 않는다.
- snapshot id는 provider/version/acquired_at/query/range/raw checksum/normalized checksum/schema version에 묶는다. 같은 취득 결과 재게시는 idempotent하고 새 취득은 새 id다.
- snapshot manifest는 storage root를 노출하지 않는 `snapshot://` logical URI를 사용하며 다른 root로
  복원해도 같은 identity를 유지한다.
- 가격 Decimal은 데이터셋의 canonical scale을 계산해 Parquet decimal(precision 38)에 lossless 저장한다.
  공통 scale과 정수부가 38자리를 넘으면 publish하지 않는다.
- upload body는 기본 25 MiB, Parquet는 기본 1,000,000 rows/32 columns로 제한한다. invalid schema나
  resource limit 위반 upload는 immutable raw artifact로 승격하지 않는다.
- 사용자 identity가 없는 현재 단계에서 dataset별 authz/rate limit을 가장하지 않는다. 공개 배포 전
  ingress 또는 Prompt 08 security slice가 이를 강제해야 한다.
- filesystem manifest가 현재 snapshot metadata의 authority다. PostgreSQL 등록과 BacktestRun의
  snapshot id/checksum 고정 transaction은 Prompt 08에서 함께 구현한다.

## 2026-08-01 이벤트 기반 백테스트 엔진

- 일봉 종가에서 만든 주문은 종목별 다음 bar open부터 실행한다. 같은 종가를 본 뒤 같은 종가에
  체결하지 않는다.
- 같은 timestamp의 bar와 주문은 `(timestamp, instrument_id)` 순서로 처리해 입력 배열 순서와 무관한
  결정성을 유지한다.
- 현재 실행 범위는 MARKET/LIMIT, DAY/GTC, long-only, 전량 체결이다. stop/partial fill/volume
  participation과 고급 risk policy는 Prompt 07에서 확장한다.
- limit gap은 주문자에게 유리한 open 가격으로 체결하고, intrabar touch는 limit 가격으로 체결한다.
- 비용은 commission, 매도세, adverse slippage를 Decimal로 분리 기록한다. tick/lot 반올림은 Prompt 07
  execution policy가 소유한다.
- 기본 종료 정책은 미체결 주문 expire와 마지막 close mark다. 명시적 선택 시 마지막 close에서 비용을
  반영해 포지션을 청산한다.
- engine은 DB/API/job queue를 호출하지 않는 순수 library다. run persistence, worker lifecycle,
  snapshot FK transaction은 Prompt 08에서 연결한다.
