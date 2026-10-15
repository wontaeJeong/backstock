# Strategy DSL

## 목적

안전하고 검증 가능한 JSON AST로 전략을 표현한다. 임의 Python 코드를 실행하지 않는다.
`packages/strategy`가 schema, indicator, evaluator를 구현하며 `packages/backtest`의
`StrategyEvaluator` protocol을 통해 순수 `OrderIntent`만 생성한다.

## 상위 구조

```json
{
  "schema_version": "1",
  "name": "example",
  "universe": ["KRX:005930"],
  "timeframe": "1d",
  "entry": { "condition": {} },
  "exit": { "condition": null },
  "position_sizing": {},
  "risk": {},
  "order": {}
}
```

`entry`, `exit`, `position_sizing`, `risk`, `order`는 서로 다른 책임을 갖는다.

- `entry.condition`: 포지션이 없을 때 매수 조건.
- `exit.condition`: 포지션 보유 중 조건 기반 매도(선택, 생략 가능).
- `risk`: stop-loss/take-profit/trailing-stop/최대 보유 기간처럼 조건식이 아닌 포지션 리스크 청산.
- `position_sizing`: 진입 수량 계산.
- `order`: 생성되는 주문의 유형(`market`/`limit`/`stop`/`stop_limit`)과 `time_in_force`.
- `session`: 선택적 뉴욕 진입 시각/요일·close 기반 마감 청산. 기본 null로 기존 행동 유지.

## 값(Value)

- `constant`: 고정 숫자.
- `bar_field`: `open`/`high`/`low`/`close`/`volume`, `shift`(0 이상, 과거로 이동한 bar 개수).
- `indicator`: 아래 지표 중 하나 + `period` + `shift`.
- `position`: `quantity`/`average_cost`/`unrealized_pnl_percent`/`holding_bars`. 포지션이 없으면
  `null`로 평가되어 비교 조건은 false가 된다.
- `portfolio`: `cash`/`equity`.
- `calendar`: `day_of_week`/`day_of_month`/`month` (해당 bar의 timestamp 기준).

`shift`는 0 이상만 허용한다(미래 참조 금지). `indicator.period`는 1 이상만 허용한다.

## 조건(Condition)

- 논리: `all`(전체 true), `any`(하나 이상 true), `not`(단항 부정).
- 비교: `gt`/`gte`/`lt`/`lte`/`eq` — 두 값을 비교. 어느 한쪽이라도 `null`(warm-up 미충족, 포지션
  없음 등)이면 false로 평가한다.
- 교차: `crosses_above`/`crosses_below` — 이전 bar와 현재 bar에서의 좌/우 값을 비교해 부호 반전을
  감지한다.

조건 트리의 최대 깊이는 8, 진입·청산 합계 node 수는 64, all/any의 자식은 각각 8개까지다.
지표 period/shift는 5,000 이하이며 universe는 50개 이하다(웹 simulation은 단일 종목).
고정 수량은 10억 주 이하, notional은 1조 이하, limit offset은 10,000 bps 미만으로 제한한다.
숫자 literal의 자릿수와 소수 자리도 제한하여 과도한 Decimal 계산을 거부한다.

## 지표 (MVP)

| 지표 | 파라미터 | 최소 lookback | 비고 |
| --- | --- | --- | --- |
| `sma` | period | period | 단순 이동평균 |
| `ema` | period | period | period bar SMA로 seed 후 재귀 계산 |
| `rsi` | period | period + 1 | Wilder 평활 |
| `atr` | period | period + 1 | Wilder 평활, true range 기반 |
| `rolling_high` | period | period | 구간 최고 high |
| `rolling_low` | period | period | 구간 최저 low |
| `volume_average` | period | period | 구간 평균 거래량 |
| `volume_ratio` | period | period + 1 | 현재 거래량 / 이전 period 평균 거래량 |
| `return` | period | period + 1 | `close_t / close_{t-period} - 1` |
| `vwap` | period | period | rolling typical price × volume / total volume; zero volume은 null |
| `bollinger_middle/upper/lower` | period, stddev_multiplier(default 2) | period | close SMA ± 모집단 표준편차 × multiplier |
| `macd` | fast_period(default 12), slow_period(default 26) | slow_period | SMA-seeded fast EMA − slow EMA |
| `macd_signal/macd_histogram` | fast/slow, signal_period(default 9) | slow + signal − 1 | MACD EMA / MACD − signal |

지표는 항상 현재 bar의 close 시점(해당 bar가 확정된 시점)에 평가 가능하다. lookback이 부족하면
지표는 `null`을 반환하고, 이를 사용하는 비교/교차 조건은 명시적으로 false가 되어 warm-up 기간에는
아무 주문도 생성되지 않는다.

준비되지 않은 값을 사용하는 조건은 `available=false`도 전파한다. `not`으로 감싸도 매수하지 않으며,
all/any 내부 조건 중 하나라도 준비되지 않았다면 해당 조건 그룹은 거래를 유발하지 않는다.

## 리스크(Risk)

- `stop_loss` / `take_profit` / `trailing_stop`: `mode`가 `percent`(진입가 대비 %, `trailing_stop`은
  진입 이후 고점 대비 %) 또는 `atr_multiple`(ATR × multiple)이다. `percent` stop_loss/trailing_stop의
  `value`는 100을 초과할 수 없다.
- `max_holding_bars`: 진입 이후 경과 bar 수가 이 값 이상이면 청산한다.

리스크 청산은 조건 기반 `exit.condition`보다 먼저 평가된다.

## Position Sizing

- `fixed_quantity`: 고정 수량.
- `fixed_notional`: 고정 금액 ÷ 현재 close, 정수 내림.
- `percent_equity`: (equity × percent) ÷ 현재 close, 정수 내림. `percent`는 0보다 크고 1 이하다.
- `atr_risk`: (equity × risk_percent) ÷ (ATR(atr_period) × atr_multiple), 정수 내림. `risk_percent`는
  0보다 크고 1 이하다.

계산된 수량이 0 이하이면 주문을 생성하지 않는다(예: 소액 계좌에서 `fixed_notional`이 1주 가격보다
작은 경우).

## 주문(Order)

- `order_type`: `market`, `limit`, `stop`, `stop_limit`.
- `limit_offset_bps`: `limit`/`stop_limit`일 때 필수, 나머지일 때 금지. 매수는 참조가 대비 +offset, 매도는
  -offset에 지정가를 둔다.
- `time_in_force`: `day` 또는 `gtc`.
- `stop_offset_bps`: `stop`/`stop_limit`일 때 필수, 나머지일 때 금지. 매수 +offset, 매도 −offset.
  두 offset은 0 이상 10,000 미만이다. OrderIntent에 양수 stop_price/limit_price로 고정한다.

STOP은 adverse gap open을 사용한다. STOP_LIMIT의 intrabar trigger는 그 bar의 high/low 순서를
추정하지 않고 다음 bar/event부터 limit 평가를 한다. trigger state와 pending 중복 거절을 추적한다.
risk stop-loss/take-profit/trailing-stop은 여전히 종가 조건에서 원래 order 설정의 intent를 생성한다.
`session.flatten_at`만 별도의 market exit intent이며 같은 close에 체결하지 않는다.

### 세션과 새 지표 파라미터

session은 `entry_start`, `entry_end`, `flatten_at`(각 null 또는 HH:MM 09:30..16:00 뉴욕),
`weekdays`(unique Monday=0..Friday=4, 기본 평일 전체)를 받는다. entry start 포함/end 제외이며
필터는 체결일이 아닌 신호 시각에 적용한다. flatten_at 이후 진입도 막는다. 일봉은 weekday-only만
가능하고 intraday clock을 거부한다. 마감 신호가 마지막 이벤트이면 만료/보유가 남을 수 있다.

IndicatorRef의 period/shift 계약은 그대로이며 stddev_multiplier (0,10], fast/slow/signal 기간은
1..5000이다. MACD fast<slow를 검증하고 MACD 계산은 period 대신 fast/slow/signal을 사용한다.
상세 wire schema·예시는 `docs/reference/research-features-api.md`를 따른다.

## Validation

거절 대상:

- 알 수 없는 operator/indicator/field 이름 (discriminated union이 미스매치를 거절).
- 잘못된 타입 (Pydantic 타입 검증).
- 0 이하의 period.
- 음수 shift(미래 참조).
- 지원하지 않는 timeframe(`1d`, `1m`, `5m`, `tick` 허용; simulation의 snapshot 주기와 일치해야 함).
- 위험한 sizing(`percent_equity.percent` 또는 `atr_risk.risk_percent`가 1 초과, `percent` 모드
  stop_loss/trailing_stop의 `value`가 100 초과).
- 8을 초과하는 조건 트리 깊이.
- 빈 universe.
- order_type과 limit_offset_bps 불일치.

`packages.strategy.validation.validate_definition()`이 Pydantic `ValidationError`를 필드 경로(`path`)와
메시지를 가진 `StrategyValidationError`로 변환한다. API는 `POST /strategies/validate`에서 이를
422 `STRATEGY_INVALID` 응답으로 노출한다.

## Versioning

`packages.strategy.validation.create_strategy_version()`이 다음을 수행한다.

1. `StrategyDefinition.model_dump(mode="json")`으로 JSON-safe 구조를 만든다.
2. `sort_keys=True`, 구분자 없는 `json.dumps`로 canonical 문자열을 만든다(`canonical_json`).
3. `sha256:<hex>` 형태의 `version_id`를 계산한다.

동일한 전략 정의는 key 순서나 호출 시점과 무관하게 항상 같은 `version_id`를 만든다. 필드가 하나라도
바뀌면 다른 `version_id`가 된다. 현재 `StrategyVersion`은 API 응답으로만 존재하며, DB에 영속화하는
`strategy_versions` 테이블과 update 금지 제약은 Prompt 08에서 추가한다.

## 추적(Trace)

`DslStrategyEvaluator`가 생성하는 `OrderIntent`는 다음을 포함한다.

- `strategy_version`: 평가에 사용한 `StrategyVersion.version_id`.
- `rule_path`: 트리거된 조건/리스크 경로(`entry/crosses_above`, `risk/stop_loss` 등).
- `reason`: 사람이 읽을 수 있는 요약과 평가에 사용된 값(예: `entry: crosses_above(left=..., right=...)`).

## API

- `POST /strategies/validate`: 임의 JSON body를 검증하고 성공 시 `StrategyVersion`을 반환한다.
- `GET /strategies/metadata`: `StrategyDefinition`의 JSON Schema, operator/indicator metadata, 4개
  템플릿(canonical JSON)을 반환한다.

`/strategies`, `/strategy-versions`의 CRUD/영속화 API는 Prompt 08 범위다.

## 템플릿

`packages.strategy.templates`가 4개 템플릿을 제공한다.

1. `moving_average_crossover`: SMA(20)/SMA(60) 교차.
2. `mean_reversion`: RSI(14) 과매도 진입 / 과매수 청산 + percent stop-loss.
3. `volatility_breakout`: 20일 고점 돌파 + 거래량 확인, ATR 기반 sizing/stop-loss/trailing-stop.
4. `calendar_rebalancing`: 매월 첫 5거래일 진입, `max_holding_bars`로 주기적 청산.

## 제한 사항

- 평가기는 `EvaluationContext`가 제공하는 포트폴리오 스냅샷만 사용하므로, `portfolio` 값 기반
  `crosses_above`/`crosses_below`는 이전 bar의 포트폴리오 상태를 별도로 보관하지 않아 사실상
  비교 조건과 동일하게 동작한다(현재가 vs 현재가). 지표/봉/캘린더 값의 교차는 정상적으로 이전
  bar 값을 사용한다.
- 진입가/보유 기간/고점은 evaluator가 매 bar `EvaluationContext.portfolio`의 수량 변화로부터
  추론한다. 부분 체결이나 피라미딩은 지원하지 않으며(평지 상태에서만 진입), 이는 현재
  `packages.backtest`의 전량 체결/롱 온리 실행 모델과 일치한다.
