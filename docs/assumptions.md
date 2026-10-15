# Assumptions

구현 중 선택한 가정을 기록한다. 변경 시 날짜, 이유, 영향 범위를 남긴다.

## 초기 가정

이 절은 최초 기준선이며 아래 날짜별 변경이 우선한다.

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

## 2026-08-01 전략 DSL과 지표

- `entry`/`exit`/`risk`/`position_sizing`/`order`를 분리한다. stop-loss/take-profit/trailing-stop/
  최대 보유 기간은 `risk`에 두고, 조건식 기반 청산만 `exit.condition`에 둔다.
- `percent` 모드 stop-loss/trailing-stop의 `value`(퍼센트, 0-100)와 `atr_multiple` 모드의 `value`(ATR
  배수)는 같은 필드를 공유하되 의미가 다르다. `percent` 값이 100을 넘으면 거절한다.
- `percent_equity.percent`와 `atr_risk.risk_percent`는 1(계좌 전체) 이하만 허용한다. 이를 초과하는
  sizing은 "위험한 sizing"으로 거절한다.
- 조건 트리의 최대 깊이는 8이다. 초과 시 거절한다.
- 지표 lookback이 부족하면 해당 지표 값은 `null`이며, 이를 사용하는 비교/교차 조건은 명시적으로
  false로 평가된다. 이 방식으로 warm-up 기간을 처리하며 별도 사전 lookback 계산 게이트를 두지
  않는다.
- `DslStrategyEvaluator`는 `EvaluationContext`에 없는 정보(진입가, 진입 시점, 고점)를 종목별 직전
  포트폴리오 수량과 비교해 자체적으로 추론한다. 평지 상태에서만 신규 진입하며 부분 체결/피라미딩은
  가정하지 않는다. 이는 현재 backtest 실행 모델(전량 체결, 롱 온리)과 일치한다.
- `crosses_above`/`crosses_below`가 `portfolio` 값(cash/equity)을 피연산자로 사용하면 evaluator가
  이전 bar의 포트폴리오 상태를 별도로 보관하지 않으므로 사실상 일반 비교와 동일하게 동작한다. 이
  한계는 문서화하고 지표/봉/캘린더 값 기반 교차만 정확한 이전-bar 비교를 제공한다.
- `StrategyVersion`은 현재 API 응답으로만 존재하는 순수 계산 결과다(canonical JSON + sha256 hash).
  DB 영속화, update 금지 제약, `/strategies`·`/strategy-versions` CRUD는 Prompt 08에서 추가한다.
- `POST /strategies/validate`, `GET /strategies/metadata`는 인증/저장 없이 순수 검증·조회만
  수행한다. 사용자 identity 기반 authz는 Prompt 08 보안 slice 범위다.

## 2026-10-16 나스닥 로컬 연구 MVP

- 사용자는 완성된 서비스에서 매매법을 탐색한다. 사전 매매 전략을 요구하지 않고 한국어 조건 폼을 제공한다.
- 단일 USD·뉴욕 시간대 종목으로 범위를 제한한다. snapshot에 currency를 새로 고정하고 기존 currency
  미상 snapshot은 simulation에서 재업로드를 요구한다. 기존 불변 manifest는 변경하지 않는다.
- Yahoo는 실제 일봉, 분봉은 종료 시각/explicit offset 파일 또는 명시적 합성 데모다.
  원격 분봉 가용성에 의존하거나 일봉을 분봉으로 재표시하지 않는다.
- 1m/5m next-open의 지연 0 근사는 초단타 실전 검증이 아니다. 호가·실제 지연·부분 체결과
  거래소 조기폐장 calendar가 없음을 결과 상단에 표시한다. 장 마감 포지션 강제 청산은 하지 않는다.
- 지표 미준비 상태는 not/all/any에 전파해 준비 이전 주문 생성을 막는다. 미체결 주문 중복도 거절한다.
- 실행은 동기 3,000 bar와 bar 사이의 15초 cooperative 제한이다. immutable filesystem에
  request/config/snapshot/전략 hash/소스 hash/결과를 보존한다. DB job queue와 worker는 후속이다.
- 파일 게시에는 같은 filesystem의 임시 파일과 atomic no-replace link를 사용해 동시 조회가
  부분 JSON/Parquet를 성공 결과로 읽지 않게 한다.
- CI는 실제 DB·컨테이너·브라우저를 검증한다. 운영 배포 대상이 없어 CD는 수동 artifact 발행까지이며
  공개 운영 전 인증·quota·백업과 공급망 정책이 필요하다. 새 PR은 별도 승인 없이 병합하지 않는다.
