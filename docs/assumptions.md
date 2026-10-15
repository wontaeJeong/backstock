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

## 2026-10-16 연구 확장 — 보관함·분석·실험

- 기존 filesystem authority를 유지해 전략 record/실험을 content-addressed write-once JSON으로
  보존한다. archive는 원본을 수정하지 않는 atomic sidecar 상태다. DB migration은 없다.
- 분석은 FIFO matched lot 기준이며 열린 lot을 승률에서 제외한다. 일/월 수익률은 뉴욕 날짜의
  마지막 관측 equity, volatility/Sharpe/Sortino는 252일 관례를 쓴다. CAGR은 평가 구간 실제
  경과일을 쓰고 하루 미만은 정의하지 않는다. null 이유와 계산식을 API에 포함한다.
- walk-forward는 rolling train→test, 학습 total return 선택/동률 입력 순서다. 각 test는 새 자본과
  evaluator로 시작하며 사전 history는 지표 warmup에만 쓴다. OOS 복리 계좌를 가장하지 않는다.
- 포트폴리오는 독립 고정 예산이고 비할당 자금은 현금이다. 공통 timestamp만 합치며 실패한
  component가 있으면 합계/상관계수를 제공하지 않는다. demo 상관을 시장 분산효과로 보지 않는다.
- 연구 API는 64 KiB body·동시 2개 threadpool·실험 30초 cooperative 계산 예산을 사용한다.
  공급자 I/O는 별도 timeout이므로 HTTP wall time 30초 보장은 아니다.
- 상세 wire 계약·경로 allowlist·분모·제한은 `docs/reference/research-features-api.md`에 기록한다.

## 2026-10-16 수동 paper 연습

- 실제 broker 연결 대신 별도 paper 계좌/승인/원장을 구현한다. paper 기능은 기본 활성화지만
  feature-off가 가능하며 production broker 플래그는 paper 실행 방식을 바꾸지 못한다.
- 수동 quote는 과거/시나리오 입력으로서 freshness를 검증하지 않는다. 최신 제출 mark로 평가하고
  승인 가격은 후보의 고정 참조가다. 비용 기본값은 commission/sell-tax/slippage 1/0/5 bps다.
- long-only 정수 수량, 계좌 초기 현금 1e9 이하, 주문 참조/실행 notional 1e6 이하를 적용한다.
  보유 원가는 매수 비용을 포함한 이동평균이며 통화별 minor-unit 반올림/환전은 지원하지 않는다.
- 요청 키는 계좌별 operation+target+정규화 payload에 바인딩한다. exact replay는 저장된 당시 응답이고
  클라이언트는 POST 이후 반드시 현재 계좌를 다시 조회한다. 생성 요청은 자동 재시도하지 않는다.
- 같은 계좌 flock과 한 원자적 계좌 JSON에 현금/체결/감사/요청 바인딩을 묶는다. 응답/감사 commit
  사본은 먼저 write-once로 저장하고 해시 참조를 커밋한다. 교체 전 장애의 미참조 사본은 허용한다.
  POSIX 로컬 filesystem용이고 NFS/분산 거래 저장소가 아니다. DB migration은 없다.
- kill switch 중에도 안전한 취소/거절/mark/조회/내부 원장 대사를 유지한다. 대사는 외부 broker
  비교가 아니다. 자세한 오류·한도·재시도·응답 계약은 같은 API reference의 Task 3 절에 고정한다.

## 2026-10-16 워크벤치 통합

- 기존 간편 폼으로 정확히 표현할 수 없는 중첩 조건·sizing·risk는 고급 JSON을 authoritative 편집기로
  사용한다. JSON에서 이름·universe·timeframe을 보존하고 간편 전략 폼을 비활성화한다. 원금·비용은
  별도 실행 설정이다. 자동 폼 변환으로 AST를 잘라내지 않는다.
- 가격은 검증된 snapshot bar/quote만 사용한다. 25개 창의 종가/tick print 선과 정확한 timestamp의
  실제 체결 표식을 제공하며, OHLC 상세와 자산 상태는 별도 표로 읽는다. equity를 주가로 복제하지 않는다.
- portfolio 파생 통계는 보수적으로 모든 component 성공·비어 있지 않은 curve·제외 timestamp 없음일
  때만 제공한다. 공통 구간 일부만으로 전체 예산 성과를 가장하지 않기 위한 결정이다. 원본 curve와
  artifacts는 그대로 보존하며 DB migration이나 과거 artifact rewrite는 없다.
- 비교 선택·최근 실험 ID·선택 paper 계좌만 브라우저에 보존하며 authoritative 결과/계좌는 서버 GET이다.
  원본 전체 JSON·CSV는 서버 기록을 보존한다. 공개 배포용 인증/분산 상태 저장이라고 주장하지 않는다.
