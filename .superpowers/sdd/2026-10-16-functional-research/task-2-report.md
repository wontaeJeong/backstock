# Task 2 구현 보고서

## 결과

**DONE** — 데이터·지표·체결·세션 backend 기능과 정확한 API 계약을 구현했다.
구현 커밋: `a2a5016` (`feat(research): add tick data and conservative execution scenarios`).
보고서는 별도 커밋으로 기록한다. push/merge/새 worktree/branch 전환/하위 agent 실행은 하지 않았다.
실주문·실제 credential·원격 시세 네트워크 호출은 하지 않았다.

작업 기준은 기존 `/Users/wt.jeong/.local/share/opencode/worktree/a2b52a/research-features`,
`feat/research-features`, 시작 HEAD `5e0d1f3`이다. 기본 checkout은
`/Users/wt.jeong/workspace/backstock`의 `main`이며 변경하지 않았다.
다른 작업에서 변경한 `docs/superpowers/plans/2026-10-16-functional-research.md`는 stage/commit하지 않았다.

## 전달 계약

- `SimulationRequest`와 `BacktestConfig`에 `spread_bps: Decimal[0,100]=0`,
  `latency_ms: int[0,60000]=0`, `volume_participation: Decimal(0,1] | null=null`.
  null은 volume 제한 없음이다. 기존 daily economics는 유지된다. 0 spread/latency baseline grid 지원.
  Task 1의 전체 요청 복사를 유지하고 grid/walk-forward/portfolio의 실제 하위 config까지 검증했다.
  `SimulationService.run(trade_start, trade_end, deadline)`와 warmup 계약도 유지했다.
- `tick` timeframe: raw price/size, optional paired raw bid/ask, 명시적 aware timestamp,
  unique ascending order. size는 0 이상 정수다. CSV와 Parquet를 정규화하고 기존 OHLCV 컬럼에
  OHLC=price/volume=size로 보존한다. quote는 별도 lossless Decimal bid/ask 컬럼으로 추가한다.
  raw/normalized checksum과 immutable reader를 유지한다. 28자리 Decimal context 때문에 quote
  저장 정밀도가 잘리던 경계를 exact digit/exponent 검사로 수정하고 31자리 quote round-trip을 검증했다.
  demo tick은 synthetic_demo의 명시적 1초 합성 print다. remote tick은 거부한다.
- 시장가: quote가 있으면 midpoint reference → buy ask/sell bid → 별도 adverse slippage.
  quote가 없으면 declared full spread의 half를 adverse side에 적용한 뒤 slippage를 적용한다.
  `Fill.spread`, `BacktestSummary.spread`, fill event spread, analysis spread를 별도로 기록한다.
  slippage와 spread는 겹치지 않고 ledger에서 다시 공제하지 않는다. fills/orders CSV 헤더도 확장했다.
- Tick은 신호보다 나중인 eligible event, 분봉은 signal+latency 이후 첫 eligible open이다.
  bar 중간 시각을 보간하지 않는다. volume cap은 전량 또는 미체결뿐이며 size=0은 cap을 켰을 때
  체결 불가다. queue·실제 잔량·partial fill 지원으로 표시하지 않는다.
- `stop`, `stop_limit` 및 explicit stop_price/limit_price 계약, DSL stop_offset_bps를 추가했다.
  adverse stop gap은 open, intrabar stop touch는 close timestamp로 기록한다. intrabar stop-limit은
  같은 bar에서 limit 체결하지 않고 trigger state를 보존한다. open trigger는 이후 range를 사용할
  수 있다. `triggered_at`과 `order_triggered` event를 기록하고 pending dedupe/long-only를 유지한다.
- `vwap`, `bollinger_middle/upper/lower`(population std), `macd/macd_signal/macd_histogram`.
  MACD fast/slow/signal 파라미터·SMA seed·lookback metadata·Decimal 계산·warmup null·shift가 있다.
  period는 기존 IndicatorRef 필수 필드이며 MACD 계산만 별도 fast/slow/signal을 사용한다.
- `StrategyDefinition.session`: optional NY `entry_start`, `entry_end`, `weekdays`, `flatten_at`.
  필터는 signal 시각에 적용한다. flatten은 별도 market intent이고 같은 close 강제 청산하지 않는다.
  daily date label에서 intraday clock controls를 거부한다. 늦은 flatten의 expired order/남은 포지션과
  미체결 가능성 경고를 검증했다.
- Yahoo 1m/5m explicit interval/prepost=False, 보수적인 last7/last60days 제한, no fallback.
  SDK open label → canonical close 변환, close≤acquired_at finalization, [start,end) 범위를 적용한다.
  canonical/upstream 범위·timestamp label·adjustment·raw checksum provenance를 기록한다.
  기존 daily client fixture signature는 그대로이며 intraday client만 interval을 추가로 받는다.
  과거 run 읽기에 현재 날짜의 provider range 제한을 재적용하지 않는다.
- `/research/catalog?q=`에 symbol/영문명 검색, 20개 curated current 목록, limited/not-PIT label을
  제공한다. 기존 7개 symbol과 QQQ 호환을 유지한다. 전수 Nasdaq/historical universe가 아니다.
- `SimulationService.get`의 raw JSON hash 검증은 모델 검증/기본값 주입 **이전** 그대로다.
  새 request/config/fill/order/summary/event 필드를 제거한 legacy artifact를 원래 raw hash로 읽고,
  현재 JSON은 새 필드까지 정확히 round-trip하는 회귀 테스트를 추가했다.

정확한 wire 필드/타입/enum/default/범위·CSV/DSL 예시는
`docs/reference/research-features-api.md`에 모두 기록했다. PRD/Architecture/Accuracy/DSL/Provider 문서도
갱신했다. DB schema 변경은 없으므로 migration은 없다.

## RED → GREEN 증거

실제 실행한 focused red/green 기록이다. 원래 202-pass baseline은 controller가 제공했으며 본 작업에서
편집 전 별도로 재실행하지 않았다. 최종 전체 suite에서 기존 테스트도 모두 재검증했다.

1. `uv run pytest tests/research/test_execution_features.py -q`
   - 최초 RED: **7 failed, 5 passed** — quote 필드/latency/volume kwargs/stop enum 미지원.
   - GREEN: **12 passed** — quote 100→ask101→101.101, spread2/slippage0.202 golden,
     latency next-event, all-or-none Hypothesis, sell spread, stop gap/ambiguous stop-limit.
   - 이후 intrabar stop timestamp RED와 engine filled-stop trigger trace RED를 각각 관측 후 수정했다.
     최종 이 파일은 **16 passed**다. 비용 component 합계 property와 pending dedupe도 포함한다.
2. `uv run pytest tests/research/test_strategy_features.py -q`
   - 최초 RED: **11 failed** — VWAP/Bollinger/MACD/session/config 필드 미지원.
   - GREEN: **11 passed**. metadata 미지원 RED 추가 후 metadata를 구현했다.
   - 마지막 flatten 미체결 및 7개 지표의 미래 가격 변경에 대한 event prefix 동일성 회귀를 추가했다.
     최종 **20 passed**다. 초기 MACD golden의 recursive rounding은 delta-form EMA로 개선했고
     timezone 표현 테스트는 UTC 변환으로 바로잡았다.
3. `uv run pytest tests/research/test_tick_provider_features.py -q`
   - 최초 RED: **3 failed, 5 passed** — tick CSV/Parquet normalization과 1초 demo 미지원.
   - GREEN: **8 passed**. 이어 28자리 context에서 quote 손실 RED를 관측하고 exact precision 계산으로
     수정했다. 최종 **9 passed**. timezone/order/size/price 검증, raw/Parquet와 checksum 손상도 포함한다.
4. `uv run pytest tests/research/test_remote_minute_features.py -q`
   - 최초 RED: **5 failed** — provider clock/intraday interval 계약 미지원.
   - GREEN: 분봉 변환·finalization·bounds·remote tick rejection 통과.
   - 실제 pinned 1.5.1 DefaultYFinanceClient의 SDK 옵션을 offline transport로 검증했다.
     최종 **6 passed**, raw checksum은 fixture bytes의 SHA-256과 정확히 비교한다.
5. `uv run pytest tests/research/test_feature_contracts.py -q`
   - 최초 RED: **2 failed, 1 passed** — catalog 제한 label/search, spread sweep 미지원.
   - GREEN: **3 passed** — legacy raw hash와 3종 실험 config propagation 포함.
   - tick raw request validation RED를 추가해 domain 검증을 구현했다.
     실제 HTTP upload→verified snapshot→quote fill→analysis/CSV 통합을 포함해 최종 **5 passed**다.

초기 lint/type/format 실패는 모두 수정했다. 최종 전체 회귀 중 새 raw-only tick 검증에 기존 새 fixture가
adjusted tick을 만들던 오류 1건도 raw fixture로 바로잡았다. 실패를 skip/xfail로 숨기지 않았다.

## 최종 실제 전체 검증

구현 커밋 직전, 동일 작업 트리에서 실행:

| 명령 | 실제 결과 |
| --- | --- |
| `uv run pytest` | **258 passed in 3.56s**, 수집 258, skip/xfail 없음 |
| `uv run ruff check .` | **All checks passed!** |
| `uv run ruff format --check .` | **123 files already formatted** |
| `uv run mypy .` | **Success: no issues found in 123 source files** |
| `git diff --check` | exit 0, 출력 없음 |

기존 202개 + 본 작업 56개 테스트다. Python 3.12.12 / pytest 8.4.2 / Hypothesis 6.164.0.
새 tests는 5개 파일이며 실제 도메인/엔진/adapter/API를 사용한다. 외부 SDK 호출은 offline transport
fixture로만 검증했다. live Yahoo 가용성을 주장하지 않는다. frontend/paper 파일은 변경하지 않았으며
pnpm/Playwright 검증은 controller의 통합/UI 단계 소관으로 **본 작업에서는 실행하지 않았다**.

## 남은 제한 / controller 참고

- 실제 queue·market impact·partial fills·실시간 tick feed·exchange calendar/조기폐장·corporate-action
  현금원장 재현은 범위 밖이다. bar volume cap은 전체 bar의 사후 시나리오이며 open 실제 유동성이 아니다.
- tick timestamp는 microsecond 해상도다. 그 해상도에서 중복되는 sub-microsecond 입력은 unique
  계약에 의해 거부된다. quote midpoint는 fill reference이고 보유 평가액은 마지막 trade price다.
- stop-limit의 intrabar ambiguity 정책은 의도적으로 체결 기회를 놓칠 수 있다. flatten은 실제 다음
  데이터·지연·cap에 따라 남을 수 있다. 결과를 실제 보호 주문/마감 보장으로 표시하면 안 된다.
- provider last7/last60days는 보수적인 앱 정책이지 공급자 가용성 보장이 아니다. pinned SDK 옵션과
  timestamp/adjustment/checksum은 offline 검증했지만 live fetch는 실행하지 않았다.
- API/catalog/session/new indicator fields는 구현됐으나 frontend editor·결과 UI 연결은 Task 4 소관이다.
  특히 spread와 slippage를 합산 진단한 뒤 순손익에서 재차 빼지 말고 volume=null을 0 cap으로 표시하지 말 것.
- Task 1 deferred Minor `fold.error/null`은 요청대로 건드리지 않았다. nested test.error 표시는 UI/final
  review에서 처리한다. 다른 작업의 plan 변경도 그대로 남겼다.
- 구현 blocker나 누락된 요청 기능은 없다. 새 worktree/branch 생성·push·merge는 명시적 작업 금지에 따라
  controller가 수행한다.

## Review fix round 1/5 — BASE `427b8ed`

**DONE** — `.superpowers/sdd/2026-10-16-functional-research/task-2-review.md`의 I1/I2/M1을
모두 수정했다. M1은 controller의 재분류대로 Important로 처리했다. 앞선 완료 판정은 이 리뷰에서
확인된 세 결함에 대해 불충분했으며, 아래 수정/재검증 증거가 해당 부분을 대체한다.

수정 커밋: **`0b83cde`** — `fix(research): correct spread limits flatten priority and trigger timing`.
이 보고서 추가는 별도 문서 커밋으로 남긴다. frontend/paper 및 deferred Task1 fold.error는 변경하지 않았다.
controller의 plan/design/verification 문서 미커밋 변경도 stage/commit하지 않았다.

### I1 — spread-adjusted OHLC limit 관통

- 실제 quote가 없는 limit/활성화 stop-limit은 선언된 spread의 **실행-side range**로 판정한다.
  buy는 low×(1+half-spread)≤limit, sell은 high×(1−half-spread)≥limit이어야 한다.
  open의 실행-side 가격이 유리하면 기존 open improvement를 유지한다. 그 외 충분한 intrabar
  관통은 reference=limit/factor, base=정확한 limit이며 이후 slippage만 limit으로 제한한다.
  Decimal 경계 나눗셈/곱셈 roundoff를 보정할 뿐 실제 quote를 잘라 가짜 체결하지 않는다.
- quote side-price bound는 별도 검사다. 제공 ask/bid가 limit 밖이면 깊은 print 또는 declared
  scenario와 무관하게 미체결이다. midpoint→side quote→별도 slippage 정책은 유지한다.
- spread/slippage는 여전히 서로 겹치지 않으며 합계가 실제 reference→execution 가격 차이×수량과
  일치한다. 수수료·원장·부분 체결 의미는 변경하지 않았다.
- RED: 새 집중 파일 최초 **4 failed / 8 passed**. buy/sell deep cross 및 activated stop-limit의
  실제 FilledExecution 기대가 기존 PendingExecution 때문에 실패했다.
  GREEN: 같은 파일 **12 passed**, 기존 execution 두 파일까지 함께 **32 passed**.
  이후 insufficient penetration의 activated 조합과 open improvement/limit-clamped slippage
  reconciliation을 추가 검증했다. 기존 spread=0 golden/parity도 전체 회귀에서 유지된다.

### I2 — flatten cancel/replace 우선순위

- 내부 immutable context에 `EvaluationContext.pending_orders: tuple[Order, ...] = ()`를 추가했다.
  엔진은 해당 이벤트의 기존 주문 실행 후 아직 accepted인 주문들의 immutable tuple을 제공한다.
  default 빈 tuple로 기존 context fixture와 사용자 evaluator 호출을 유지하며 HistoryEvaluator도
  pending context를 손실 없이 전달한다. session 회귀의 지연/cap 12조합은 실제 이 wrapper를 거친다.
- DslStrategyEvaluator 반환은 protocol의 `tuple[StrategyDecision, ...]`와 일치하도록 확장했다.
  flatten 경계에서는 같은 종목의 pending entry/exit에 CancelIntent를 먼저 발행하고 실제 보유
  전체 수량의 market exit 하나를 뒤에 둔다. 일반 pending dedupe와 long-only 검사에는 손대지 않았다.
- 이미 같은 수량의 `session/flatten` market sell이 accepted면 취소/재제출하지 않는다. 따라서
  cap/latency 대기 중 주문 id와 submitted_at이 유지되고 latency가 끝없이 재시작되지 않는다.
  미보유이면 pending entry만 취소하며 매도하지 않는다. 그 이벤트에서 기존 주문이 먼저 이미
  체결됐다면 소급 취소하지 않고 실제 보유를 다음 eligible 이벤트로 청산한다.
- RED: session 집중 **16 failed** — 후속 이벤트가 충분해도 매도 fill 부재, flatten rejected,
  pending entry의 경계 이후 체결을 실제 엔진으로 재현했다.
  GREEN: **16 passed** — limit/stop/stop-limit exits × delay/cap, cancel trace 선후관계,
  단일 실제 market exit·중복 매도 없음·보유 수량 불변식, no-next-event expired/잔여 포지션,
  경계 pending entry 취소를 확인했다. same-close 강제 청산은 추가하지 않았다.
- 반환 union 확장에 따라 기존 `tests/strategy/test_evaluator.py`의 알려진 OrderIntent 결과에
  실제 `isinstance(..., OrderIntent)` assertion을 추가했다. type ignore/가짜 cast로 숨기지 않았다.

### M1 (Important) — cap/limit 대기의 trigger 시각

- internal FilledExecution/PendingExecution에 optional `triggered_at: datetime | None = None`을
  추가했다. 최초 gap trigger는 bar open, 순서를 알 수 없는 intrabar trigger는 close를 전달한다.
  processing은 이 시각을 Order.triggered_at과 order_triggered event에 그대로 기록한다.
  이미 발동한 주문은 최초 시각을 유지한다. report의 기존 필드 이름/타입은 바꾸지 않았다.
- RED: timestamp 테스트 추가 후 execution 집중 **21 failed / 12 passed**. 새 decision 필드 부재와
  엔진이 known open보다 1분 늦은 close를 기록하는 실패를 모두 관측했다.
  GREEN: execution 집중 33개 및 기존 execution 두 파일, 합계 **53 passed**.
  buy/sell × stop/stop-limit × 1m/5m × gap/intrabar cap 대기, 양방향 limit-bound 대기와
  실제 엔진 trigger→나중 fill trace를 포함한다.

### 최종 실제 검증

새 정확성 회귀는 2개 파일 **53개**이며 기존 258개와 함께 전부 통과했다.

| 명령 | 실제 결과 |
| --- | --- |
| `uv run pytest tests/research/test_execution_review_fixes.py tests/research/test_session_review_fixes.py -q` | **53 passed in 0.34s** |
| `uv run pytest` | **311 passed in 3.41s**, 수집 311, skip/xfail 없음 |
| `uv run ruff check .` | **All checks passed!** |
| `uv run ruff format --check .` | **125 files already formatted** |
| `uv run mypy .` | **Success: no issues found in 125 source files** |
| `git diff --check` / `git diff --cached --check` | exit 0, whitespace 오류 없음 |

중간 전체 실행은 307 passed였지만 mypy가 기존 테스트의 union narrowing 8건을 발견해 위 assertion으로
수정했다. 최종 311 suite는 추가 4개 spread 경계 회귀까지 포함한다. lint/format도 모두 수정 후
전체 명령으로 재검증했다. runtime 테스트를 skip하거나 기대치를 결함 동작에 맞추지 않았다.

제한은 기존과 같다. OHLC 내부 경로/정확한 limit touch 시각·queue·부분 체결을 재현하지 않는다.
flatten은 관측 경계의 명시적 취소/교체 정책이며 같은 close 또는 미래 데이터 없는 청산 보장이 아니다.
실제 provider/credential 호출, frontend/paper 변경·검증, push/merge/새 worktree/agent 실행은 하지 않았다.
