# 연구 기능 API 계약

Task 1/2 backend 계약. `/openapi.json`에 모든 요청·응답 schema가 등록된다. 아래 타입은 JSON wire
타입이다. 금액·비율·수익률·상관계수는 **Decimal 문자열**, 수익률은 백분율이 아닌 비율이다.
날짜는 offset 있는 ISO 8601이다. `null`은 0이 아니며 `reason`/`error`를 함께 표시한다.
실제 체결·평가·snapshot을 사용하며 실주문은 없다.

## 공통 요청

기존 `POST /simulations`와 `GET /simulations/{run_id}`에 선택 필드를 하위 호환으로 추가한다.
`SimulationRequest`와 `StrategyDefinition`, `SimulationReport`, `SnapshotManifest`의 정확한 schema는
OpenAPI의 같은 이름을 재사용한다. 아래 `base`는 완전한 실행 가능 요청 예시다.

```json
{
  "source": "demo", "symbol": "AAPL", "initial_cash": "1000",
  "commission_bps": "1", "sell_tax_bps": "0", "slippage_bps": "5",
  "strategy": {
    "name": "매수 후 보유", "universe": ["NASDAQ:AAPL"], "timeframe": "1d",
    "entry": {"condition": {"op": "gt", "left": {"type": "bar_field", "field": "close"},
      "right": {"type": "constant", "value": "0"}}},
    "position_sizing": {"method": "fixed_quantity", "quantity": 2}
  }
}
```

이하 예시의 `base`는 위 객체, `definition`은 그 `strategy` 객체, `r1`/`r2`는 실제 실행의
64자리 소문자 hex `run_id`, `s1`은 실제 snapshot id를 뜻한다. 이 변수는 클라이언트 코드에서
객체/문자열로 치환한다. DSL `version_id`만 `sha256:<hex64>`이고 다른 id는 prefix가 없다.

```ts
type DecimalString = string;
type ISODateTime = string;
type Hex64 = string;
type Status = "succeeded" | "failed" | "cancelled" | "not_run";
type LibraryKind = "strategies" | "datasets" | "runs";
type Axis = { path: string; values: (number | DecimalString)[] };
```

## 보관함

| 메서드·경로 | 요청 | 응답 |
| --- | --- | --- |
| `GET /research/library/{strategies\|datasets\|runs}` | `q=""`, `page=1`, `page_size=25`, `archived=false` | `200 LibraryPage` |
| `POST /research/library/strategies` | `{definition, description?: string, tags?: string[]}` | `201 StrategyRecord` |
| `GET /research/library/strategies/{id}` | 없음 | `200 StrategyRecord` |
| `POST /research/library/{kind}/{id}/archive` | `{archived: true}` 또는 `{archived: false}` | `200 ArchiveState` |

```ts
type StrategyRecord = {
  strategy_id: Hex64; version_id: string; name: string;
  definition: StrategyDefinition; description: string; tags: string[]; created_at: ISODateTime;
};
type LibraryPage = {
  items: (StrategyRecord | SnapshotManifest | SimulationReport)[];
  total: number; page: number; page_size: number;
};
type ArchiveState = {kind: LibraryKind; id: Hex64; archived: boolean};
```

호출 예시: `POST .../strategies`에 `{definition: base.strategy, description: "기준 실행", tags: ["demo"]}`.
응답은 위 `StrategyRecord`의 모든 필드이며 기본 description은 `""`, tags는 `[]`다.
빈 목록 예시: `{"items":[],"total":0,"page":1,"page_size":25}`.
archive 응답 예시: `{kind: "runs", id: r1, archived: true}`.

- `q`는 저장된 JSON 전체의 대소문자 무시 부분문자열 검색이다. 정렬은 canonical 내용의 안정적인
  내림차순이며 생성일 순서를 보장하지 않는다. `page_size` 1..100, `q` 최대 200자.
- `archived=true`는 보관된 항목만 조회한다. 삭제·원본 수정이 아니며 기존 실행·snapshot 조회는 유지한다.
- 전략 저장은 매번 별도 immutable record(생성시각 포함)를 만들고 동일 DSL은 동일 version_id를 공유한다.
- 파일 저장소 기반이며 모든 metadata를 검색한다. 대규모 인덱스/DB pagination이나 사용자별 ACL은 아니다.

## 분석·CSV

`GET /research/runs/{r1}/analysis` → `200 Analysis`.

```ts
type Statistic = {value: DecimalString | null; reason: string | null; definition: string};
type ReturnPoint = {period: string; value: DecimalString}; // YYYY-MM-DD 또는 YYYY-MM
type RoundTrip = {
  instrument_id: string; entry_at: ISODateTime; exit_at: ISODateTime; quantity: number;
  entry_price: DecimalString; exit_price: DecimalString; fees: DecimalString;
  net_profit: DecimalString; return_on_cost: DecimalString; holding_seconds: DecimalString;
};
type Analysis = {
  run_id: Hex64;
  statistics: Record<"net_profit" | "total_return" | "max_drawdown" | "cagr" |
    "volatility" | "sharpe" | "sortino" | "win_rate" | "profit_factor" | "expectancy" |
    "exposure" | "turnover" | "holding_seconds" | "commission" | "tax" | "slippage" | "spread", Statistic>;
  daily_returns: ReturnPoint[]; monthly_returns: ReturnPoint[];
  drawdown: {timestamp: ISODateTime; value: DecimalString}[];
  round_trips: RoundTrip[];
  distributions: {closed_net_profit: DecimalString[]; closed_return: DecimalString[];
    holding_seconds: DecimalString[]};
  warnings: string[];
};
```

수치 예시(실제 4-bar offline golden 실행): 원금 1000, 2주 매수 100.1/매도 89.91,
수수료 0.38002, 매도세 0.35964, 슬리피지 0.38이면
`net_profit={value:"-21.11966",reason:null,definition:...}`이고,
`round_trips[0].fees="0.73966"`, `round_trips[0].net_profit="-21.11966"`다.
미청산 매수 후 보유는 `round_trips=[]`, `win_rate.value=null`,
`win_rate.reason="no closed matched lots"`다. `definition`은 응답에 실제 계산식이 들어간다.

- 순손익은 최종 현금이 아닌 최종 equity−원금이다. 슬리피지는 execution price에 이미 포함되어
  다시 차감하지 않는다. FIFO matched lot에 진입·청산 수수료/세금을 수량 비례 배분한다.
- 열린 lot은 승률·profit factor·expectancy·holding 통계에서 제외한다. 한 sell이 여러 lot을 닫으면
  matched lot 여러 건이다. 승률의 분모는 sell 주문 수가 아니다. 무승부도 분모에 포함한다.
- daily/monthly는 뉴욕 현지 날짜 마지막 관측 equity를 사용한다. 첫 구간의 분모는 원금이며
  이후 구간은 이전 관측 마감 equity다. 누락일을 보간하거나 0수익률로 삽입하지 않는다.
- volatility는 일 수익률 표본표준편차×√252, Sharpe는 무위험 0, Sortino는 목표 0이며
  downside 분모는 전체 관측 일수다. CAGR은 실제 첫/마지막 **평가 구간** 경과일과 365.25를
  사용하고 1일 미만·0 이하 equity·overflow면 null이다. 거래소 calendar 보정은 없다.
- drawdown은 초기 원금도 고점에 포함한다. exposure는 보유 bar 비율, turnover는 양방향 실제
  체결 notional/원금(비연율), holding은 lot당 경과초의 단순 평균이다.
- 실패/취소 실행 분석은 관측된 부분 결과임을 warnings에 표시한다. 성공으로 순위화하지 않는다.

`GET /research/runs/{r1}/export.csv?kind=fills|equity|orders` → `200 text/csv` attachment.
행 제한 없이 모든 원본 기록을 내보낸다. `orders`는 intent를 펼친다. 빈 체결도 헤더를 반환한다.
텍스트 cell의 `= + - @`, 선행 tab/CR/LF를 apostrophe로 보호하며 실제 음수 금액은 숫자로 유지한다.
JSON 상세 조회는 변경하지 않는다. 예시 fills 헤더:

```csv
fill_id,order_id,instrument_id,timestamp,side,quantity,reference_price,execution_price,commission,tax,slippage,spread
```

## 비교·QQQ

`POST /research/compare` body `{run_ids: [r1, r2]}` (2..8) → `200 Comparison`.

```ts
type ComparedRun = {
  run_id: Hex64; status: "succeeded" | "failed" | "cancelled"; snapshot_id: Hex64;
  symbol: string; interval: string; start: ISODateTime | null; end: ISODateTime | null;
  total_return: DecimalString; max_drawdown: DecimalString; net_profit: DecimalString;
};
type Comparison = {comparable: boolean; rows: ComparedRun[]; differences: string[]; warnings: string[]};
```

같은 snapshot·종목·주기·평가 범위·원금·보정 의미·성공 상태이면 `comparable:true`다.
비용/전략은 의도적으로 바꿀 수 있다. 차이가 있으면 `differences`와 warnings를 제공하고 재표본화하지 않는다.
응답 예시: `{comparable:true, rows:[/* ComparedRun 두 건 */], differences:[], warnings:["Synthetic demo results are not actual market performance."]}`.

`POST /research/benchmark` body `{run_id:r1, benchmark_symbol:"QQQ", snapshot_id?:s1}`
→ `200 BenchmarkComparison`. benchmark_symbol 기본값은 QQQ다.

```ts
type BenchmarkComparison = {
  run_id: Hex64; benchmark_symbol: "QQQ"; snapshot_id: Hex64; provider: string;
  points: {timestamp: ISODateTime; run_equity: DecimalString; benchmark_value: DecimalString}[];
  benchmark_return: DecimalString | null; reason: string | null;
  excluded_run_timestamps: number; excluded_benchmark_timestamps: number; warnings: string[];
};
```

응답의 `snapshot_id`는 **별도로 읽은 QQQ 데이터**다. 공통 timestamp만 사용하며 QQQ 첫 공통
종가를 원금으로 정규화한 비용 없는 fractional 단순보유다. 공통 2개 미만이면 return은 null/reason이다.
`run_equity`는 실제 실행 equity이지 QQQ에 맞춰 재계산한 전략 결과가 아니다.
업로드/snapshot 실행은 별도 QQQ snapshot_id가 필수다. 종목·주기가 다르면 거절한다.
Yahoo 실행은 같은 기간의 실제 QQQ를 별도로 취득한다. demo 실행은 명시적인 별도 synthetic_demo
QQQ를 생성하고 **같은 합성 패턴·실제 QQQ 아님** 경고를 제공한다. provider 자동 fallback은 없다.

## 고정 snapshot grid

`POST /research/experiments/grid` body `{base, axes:[{path:"commission_bps",values:[0,10]}]}`
→ `201 GridExperiment`.

```ts
type ExperimentRow = {
  parameters: Record<string, DecimalString>; run_id: Hex64 | null; status: Status;
  total_return: DecimalString | null; max_drawdown: DecimalString | null;
  net_profit: DecimalString | null; error: string | null;
};
type GridRequest = {base: SimulationRequest; axes: Axis[]};
type GridExperiment = {
  experiment_id: Hex64; kind: "grid"; request: GridRequest; rows: ExperimentRow[];
  warnings: string[]; baseline_snapshot_id: Hex64;
};
```

실제 원본 snapshot을 1회 취득해 모든 행이 그 snapshot을 사용한다. 최대 2축·16조합.
실패한 값은 `{parameters:{...},run_id:null,status:"failed",total_return:null,max_drawdown:null,
net_profit:null,error:"..."}`로 보존한다. 엔진 취소/실패로 artifact가 생성된 경우 run_id는 유지한다.
시간이 소진되어 시작하지 않은 값은 `not_run`이며 성공/0수익률로 표시하지 않는다.

허용 path(기존 필드에만 적용, 선택한 DSL 종류에 없는 필드를 생성하지 않음):

- `commission_bps`, `sell_tax_bps`, `slippage_bps`, `spread_bps`, `latency_ms`, `volume_participation`
  (`volume_participation`은 base에서 null이 아닌 값을 먼저 설정해야 sweep 가능)
- `strategy.position_sizing.{quantity|notional|percent|risk_percent|atr_period|atr_multiple}`
- `strategy.risk.max_holding_bars`
- `strategy.risk.{stop_loss|take_profit|trailing_stop}.{value|atr_period}`
- `strategy.order.limit_offset_bps`, `strategy.order.stop_offset_bps`
- 진입/청산 condition 안의 `constant.value`,
  `indicator.{period|fast_period|slow_period|signal_period|stddev_multiplier}`.
  예: `strategy.entry.condition.right.value`, `strategy.entry.condition.left.period`,
  `strategy.entry.condition.conditions.0.left.period` (배열 index는 dot 숫자).

`shift`, 이름·symbol·timeframe·metadata·임의 경로·원금은 sweep 불가다.
정수/양수/상한 등 DSL와 비용 schema 전체를 각 조합마다 다시 검증한다.

## 순차 walk-forward

`POST /research/experiments/walk-forward` body
`{base,train_bars:30,test_bars:10,folds:2,axes:[{path:"commission_bps",values:[0,10]}]}`
→ `201 WalkForwardExperiment`.

```ts
type WalkForwardRequest = {
  base: SimulationRequest; train_bars: number; test_bars: number; folds: number; axes?: Axis[];
};
type WalkFold = {
  fold: number; train_start: ISODateTime | null; train_end: ISODateTime | null;
  test_start: ISODateTime | null; test_end: ISODateTime | null;
  train_run_ids: Hex64[]; training: ExperimentRow[]; selected_parameters: Record<string, DecimalString>;
  test_run_id: Hex64 | null; test: ExperimentRow | null; status: Status; error: string | null;
};
type WalkForwardExperiment = {
  experiment_id: Hex64; kind: "walk_forward"; request: WalkForwardRequest;
  baseline_snapshot_id: Hex64; folds: WalkFold[]; warnings: string[];
  selection_metric: "training_total_return";
};
```

- 최대 4 folds, 학습 후보+테스트 합계 32회, 공통 30초 cooperative 계산 예산.
  각 후보에도 기존 15초 엔진 제한이 있다. train/test 각각 최소 2 bars. axes는 grid와 같은 제한이다.
- rolling train 창 뒤에 연속 test 창을 둔다. 다음 fold는 test_bars만큼 앞으로 이동한다.
  범위 timestamp는 양 끝 포함이며 실제 bar 기준이다. 불완전 창은 `not_run`으로 남긴다.
- **학습 total_return만** 선택하며 동률은 입력 후보 순서다. test를 보고 후보를 재선택하지 않는다.
- 각 train/test 엔진과 evaluator·자본은 새로 시작한다. 이전 history는 지표만 준비한다.
  학습 주문·체결·포지션·수익을 test로 이월하지 않는다. test 최초 bar 종가부터 신호를 생성하고
  다음 bar부터 체결한다. test의 equity·benchmark·annualization은 test 구간만 포함한다.
- fold별 run_id와 실제 training 행을 보존한다. 전체 OOS를 복리 계좌처럼 이어붙이지 않는다.

## 독립 고정 예산 포트폴리오

`POST /research/experiments/portfolio` body
`{initial_cash:"1000",components:[{weight:"0.25",request:base},{weight:"0.5",request:base}]}`
→ `201 PortfolioExperiment`.

```ts
type PortfolioRequest = {
  initial_cash: DecimalString | number;
  components: {weight: DecimalString | number; request: SimulationRequest}[];
};
type PortfolioExperiment = {
  experiment_id: Hex64; kind: "portfolio"; request: PortfolioRequest;
  components: {index:number;weight:DecimalString;budget:DecimalString;run_id:Hex64|null;
    status:Status;error:string|null}[];
  reserve_cash: DecimalString;
  curve: {timestamp:ISODateTime;equity:DecimalString}[];
  correlations: {left:number;right:number;value:DecimalString|null;reason:string|null;
    observations:number}[];
  excluded_timestamps: Record<Hex64,number>; warnings:string[];
};
```

위 예시의 실제 budget은 250/500, reserve_cash는 250이다. 각 request.initial_cash 대신
전체 원금×weight를 쓰며, 현금 공유·재투자·재조정 없이 실제 엔진을 독립 실행한다.
2..5개, 비중은 양수이고 합계≤1이다. 공통 timestamp의 실제 equity 합계+reserve만 반환하고
각 실행별 제외 timestamp 수를 보존한다. 상관계수는 **공통 daily equity 수익률**의 Pearson 계수다.
먼저 모든 component의 공통 timestamp를 찾고, America/New_York 날짜별 **마지막 공통 timestamp**를
선택해 그 동일 시점의 equity로 일간 수익률(비율, `%` 아님)을 계산한다. 각 component의 마지막
시점을 독립 선택해 서로 다른 시각을 짝짓지 않는다. 빠진 날짜는 채우지 않고, 마지막 공통 일간
평가액 사이에서만 수익률을 계산한다. `observations`는 실제 공통 daily 수익률 개수(선택한 날짜 수−1,
최소 0)다. 따라서 한 세션에 분봉이 많아도 observations는 0이며 계수는 null이다.
공통 daily 수익률 2개 미만/한쪽 분산 0/비유한 통계값이면 null/reason이다. 금액은 Decimal로 유지하고
통계 계산에만 float를 사용한다. 유한한 무단위 계수만 Decimal 문자열로 반환한다.
포트폴리오 curve는 여전히 모든 공통 timestamp를 보존한다. 동일 demo 가격 패턴 경고를 반드시 표시한다.
실패한 component가 있으면 curve와 correlations 모두 비운다. 실패 예산을 무손실 현금으로 가장하지 않는다.

## 단기매매 데이터·체결·DSL 확장 (Task 2)

### 실행 설정과 결과

```ts
type Timeframe = "1d" | "1m" | "5m" | "tick";
type ExecutionOptions = {
  spread_bps?: DecimalString | number; // 0..100, default "0"; 전체 bid-ask 폭
  latency_ms?: number;                // integer 0..60000, default 0
  volume_participation?: DecimalString | number | null; // (0,1], default null
};
// SimulationRequest와 report.config(BacktestConfig)에 위 세 필드가 존재한다.
// 응답 Decimal은 항상 문자열, 응답 latency_ms는 정수다. config.bar_interval은 Timeframe.
```

- `null`은 **거래량 제한 없음**이다. 기존 일봉 결과의 경제적 기본값을 유지하지만 실제 유동성 보장이
  아니다. 값을 켜면 `주문 전체 수량 <= event size/bar volume × fraction`일 때만 전량 체결한다.
  정수 내림 효과가 있으며 부분 체결·남은 수량의 분할·호가 잔량·queue/시장 충격을 지원하지 않는다.
  quote-only `size=0`은 제한을 켰을 때 체결할 수 없다. OHLC 전체 거래량은 사후 시나리오 상한일 뿐
  open 시점에 관측한 유동성이라는 주장이 아니다.
- 신호 bar/event에서는 체결하지 않는다. tick은 `event timestamp > submitted_at`이면서
  `timestamp >= submitted_at + latency_ms`인 다음 이벤트부터 실행한다. 분봉은 **bar open**
  (`close timestamp - duration`)이 지연 조건을 충족해야 하며, 경계 사이 지연은 다음 open까지 올린다.
  bar 내부 지연 시각에 임의 가격을 보간하지 않는다. 일봉은 기존 다음 bar open 근사다.
- 제공 quote가 없으면 buy/sell 기준가에 `±spread_bps/20000`, 그 다음 adverse slippage를 적용한다.
  제공 quote가 있으면 시나리오 spread를 추가하지 않고 midpoint가 `reference_price`, ask/bid가
  buy/sell base다. 이후 slippage를 적용하며 limit 경계를 넘지 않는다. quote 자체가 limit을 넘으면
  체결하지 않는다. stop trigger는 제공 trade `price`/OHLC touch로 판정한다.
- `Fill.spread`(Decimal 문자열, 과거 artifact 기본 "0")는 `abs(base-reference)×quantity`,
  `Fill.slippage`는 `abs(execution-base)×quantity`다. 둘은 겹치지 않는다. `BacktestSummary.spread`
  는 실제 Fill.spread 합계다. `BacktestEvent.spread`는 Decimal 문자열 또는 null이며 fill event에
  기록된다. 현금·equity는 실제 execution price를 이미 사용하므로 **둘 다 다시 차감하지 않는다**.
  `Analysis.statistics.spread`도 같은 진단값이며 순손익에서 추가 공제하는 비용이 아니다.
- 예: bid=99, ask=101, 수량 2, slippage=10bps면 midpoint=100, buy price=101.101,
  spread=2, slippage=0.202다. 수수료가 없으면 실제 현금 지출은 202.202이며 진단비용을 더 빼지 않는다.
- 결과 warnings에 지연 grid·무제한/전량 체결 가정·호가 queue/실제 지연/달력 미검증을 표시한다.
  미청산 포지션은 마지막 trade/bar close로 평가하며 quote 청산 또는 실주문 체결로 가장하지 않는다.

### Stop / stop-limit

```ts
type OrderType = "market" | "limit" | "stop" | "stop_limit";
type OrderRule = {
  order_type?: OrderType; // default market
  limit_offset_bps?: DecimalString | number | null; // [0,10000), default null
  stop_offset_bps?: DecimalString | number | null;  // [0,10000), default null
  time_in_force?: "day" | "gtc"; // default day
};
// engine OrderIntent (DSL에서 생성됨)
type TriggerPrices = {
  limit_price: DecimalString | null; // >0; limit/stop_limit에서 필수, 나머지는 금지
  stop_price: DecimalString | null;  // >0; stop/stop_limit에서 필수, 나머지는 금지
};
// report.result.orders의 추가 필드: triggered_at: ISODateTime | null (과거 기본 null).
// 상태 enum은 accepted|filled|cancelled|expired|rejected 그대로다.
// event.kind에는 order_triggered를 추가한다.
```

- DSL의 limit/stop-limit에는 `limit_offset_bps`, stop/stop-limit에는 `stop_offset_bps`가 필수다.
  나머지 주문 종류에서는 해당 필드가 null이어야 한다. 기준은 신호 close이고 buy는 +offset,
  sell은 −offset이다. 예: `{"order_type":"stop_limit","stop_offset_bps":"50",
  "limit_offset_bps":"100","time_in_force":"gtc"}`.
- stop은 buy high≥stop / sell low≤stop에서 발동한다. 불리한 open gap은 stop 가격이 아닌 open에
  체결한다. intrabar touch는 가격 stop에서 시나리오 비용을 적용하고 시각을 bar close에 기록한다.
  실제 intrabar trigger 시각을 아는 것으로 표시하지 않는다.
- stop-limit은 open에서 이미 trigger한 경우에만 같은 bar의 limit touch를 사용할 수 있다.
  intrabar trigger라면 high/low 순서를 알 수 없어 **그 bar는 미체결**로 둔다. `order_triggered`
  event 사유 `stop_limit_intrabar_ambiguous`와 triggered_at을 남기고 이후 bar/event의 limit으로만
  평가한다. 거래량 상한으로 미체결인 stop도 발동 상태를 유지한다. pending 주문의 중복은 거절한다.
- DAY 분봉/tick은 뉴욕 날짜가 바뀌기 전에 만료하고, 일봉 DAY는 다음 eligible bar에서 미체결이면
  만료한다. GTC는 이후 데이터까지 유지한다. 종료 시 기본 만료이며 보유를 임의 강제청산하지 않는다.
  기존 risk.stop_loss/take_profit/trailing_stop은 여전히 close 기반 조건이다.

orders CSV 헤더(추가 필드 포함):

```csv
order_id,state,filled_quantity,state_reason,triggered_at,instrument_id,submitted_at,side,quantity,order_type,limit_price,stop_price,time_in_force,reason,strategy_version,rule_path
```

### 지표와 세션

`IndicatorRef.indicator`는 기존 `sma|ema|rsi|atr|rolling_high|rolling_low|volume_average|volume_ratio|return`
외에 `vwap|bollinger_middle|bollinger_upper|bollinger_lower|macd|macd_signal|macd_histogram`을 허용한다.
`type:"indicator"`, `period` 정수 1..5000(기존 계약대로 필수), `shift` 정수 0..5000(default 0)이다.

| 선택 필드 | 타입·범위·기본값 | 사용 |
| --- | --- | --- |
| `stddev_multiplier` | Decimal 문자열/숫자 (0,10], 기본 "2" | Bollinger |
| `fast_period` | integer 1..5000, 기본 12 | MACD |
| `slow_period` | integer 1..5000, 기본 26; fast보다 커야 함 | MACD |
| `signal_period` | integer 1..5000, 기본 9 | MACD signal/histogram |

- VWAP는 rolling `Σ((high+low+close)/3 × volume) / Σvolume`; zero volume이면 null이다.
  세션 누적 VWAP가 아니며 tick의 typical price는 trade price다. 최소 period개 관측이 필요하다.
- Bollinger middle은 close SMA, upper/lower는 middle±multiplier×**모집단** 표준편차다. 최소 period개.
- MACD는 각각 SMA로 seed한 fast/slow close EMA의 차이, signal은 MACD의 SMA-seeded EMA,
  histogram은 MACD−signal이다. `period`는 MACD 계산에서 사용하지 않고 별도 fast/slow/signal을 쓴다.
  최소 lookback은 MACD=slow, signal/histogram=slow+signal−1이다. shift는 계산하기 전 history를 자른다.
  지표는 Decimal 계산이며 부족한 lookback은 null/available=false로 전파한다.
  `/strategies/metadata`에 이름·파라미터·lookback·가용 시점이 제공된다.

```json
{"type":"indicator","indicator":"macd_signal","period":26,"fast_period":12,
 "slow_period":26,"signal_period":9,"shift":0}
```

```ts
type SessionControls = {
  entry_start?: string | null; // HH:MM, inclusive; default null
  entry_end?: string | null;   // HH:MM, exclusive; default null
  weekdays?: number[];        // unique integer 0..4 (Mon..Fri), default [0,1,2,3,4]
  flatten_at?: string | null;  // HH:MM, inclusive close-based signal; default null
};
// StrategyDefinition.session?: SessionControls | null (default null)
```

clock은 09:30..16:00 뉴욕 시간이고 start<end, weekdays는 1..5개다. weekday와 entry clock은
**신호 가용 시각**에 적용한다. 체결일을 미리 보고 필터하지 않는다. flatten_at 이후 신규 진입도 막는다.
보유 중 첫 해당 close/event에서 market exit 신호를 만들며 다음 eligible event에서만 체결한다.
마지막 close에 신호만 생기거나 지연/거래량 상한으로 미체결일 수 있고 warnings와 실제 expired order/
남은 포지션을 확인해야 한다. 일봉 date label은 시계가 아니므로 entry_start/end/flatten_at을 거부한다.
일봉 weekday-only controls는 허용한다. session=null이면 기존 필터 없는 행동을 유지한다.

### Tick/quote 업로드와 원격 분봉

`DatasetUploadRequest.interval`, `BarRequest.interval`, `StrategyDefinition.timeframe`,
`BacktestConfig.bar_interval` 모두 `1d|1m|5m|tick`을 지원하며 default는 기존 `1d`다.
`source`는 `demo|snapshot|yfinance` 그대로이며 remote tick은 거부한다.

틱 CSV(Parquet도 같은 컬럼/타입):

```csv
timestamp,price,size,bid,ask
2024-01-02T09:30:00.001-05:00,100,0,99.99,100.01
2024-01-02T09:30:00.002-05:00,100.1,5,100.09,100.11
```

- 필수 `timestamp`는 명시적 offset의 ISO 8601(Parquet aware datetime도 가능), `price`는 유한한
  양수 Decimal 문자열/정수/숫자, `size`는 0 이상의 정수다. 입력은 unique·strictly ascending이며
  raw 가격/거래량만 허용한다. Python datetime의 microsecond 해상도로 정규화된다.
- `bid,ask`는 함께 생략하거나 함께 제공하며 유한 양수·bid≤ask·raw여야 한다. size=0 quote-only 이벤트를
  허용한다. quote가 주문장 전체나 거래 가능 잔량을 뜻하지 않는다. 원격 tick API가 있다고 주장하지 않는다.
- normalized Parquet는 기존 `instrument_id,timestamp,open,high,low,close,volume,price_adjustment,
  volume_adjustment,timestamp_provenance`를 유지하고 tick의 OHLC=price, volume=size로 저장한다.
  quote가 있으면 lossless Decimal `bid,ask` 컬럼을 추가하며 snapshot interval=tick,
  timestamp_label=event로 구분한다. 원본 raw checksum과 normalized checksum을 읽을 때 검증한다.
  기존 snapshot을 다시 쓰지 않는다. USD/America/New_York의 평일 정규장 tick만 simulation 가능하다.
- `POST /datasets`는 기존 raw bytes upload다(multipart 아님). query에 instrument_id=NASDAQ:AAPL,
  symbol=AAPL, exchange=NASDAQ, currency=USD, timezone=America/New_York, aware start/end,
  price_adjustment=raw, volume_adjustment=raw, interval=tick을 보내고 헤더는
  `Content-Type: text/csv`, `X-Filename: ticks.csv`다. Parquet는
  `application/vnd.apache.parquet`와 `.parquet` 파일명이다. 응답 snapshot_id로 source=snapshot을 실행한다.
- source=demo,timeframe=tick은 명시적 `synthetic_demo` 1초 간격의 합성 print 재생이다. 실제 tick이 아니다.
- Yahoo는 pinned yfinance **1.5.1**의 explicit interval, prepost=False, auto_adjust 의미를 유지한다.
  보수적 앱 정책은 **1m 최근 7일 / 5m 최근 60일**, end≤취득 요청 시각이며 가용성을 보장하지 않는다.
  지원되지 않는 범위/remote tick/공급자 실패는 자동 fallback하지 않는다. 과거 저장 결과를 읽을 때
  현재 날짜로 범위를 재검증하지 않는다.
- 외부 open label에 1/5분을 더해 canonical close로 변환하고 요청 close 범위 `[start,end)` 및
  `close <= acquired_at`인 확정 bar만 게시한다. upstream query start/end는 canonical 범위에서
  duration을 뺀 값이다. lineage에 upstream_start/end, upstream_timestamp_label=open,
  timestamp_label=close, interval, prepost, finalization_policy를 저장한다. 가격 보정은 raw 또는
  total_return_adjusted, volume은 raw다. 소급 보정은 당시/PIT 가격이 아니다.

### 제한된 현재 종목 검색

`GET /research/catalog?q=Tesla`는 symbol/영문명 부분문자열을 대소문자 무시로 검색한다.
기존 `symbols`를 유지하고 `instruments:[{symbol,name}]`,
`listing_scope:"curated_current_not_point_in_time"`, `warnings:string[]`를 추가한다.
결과 예시는 symbols=["TSLA"]다. 빈 q는 제한된 전체 curated 목록이며 빈 일치는 빈 배열이다.
전체 Nasdaq·상장폐지 포함 과거 universe·거래소 시점별 분류가 아니다. QQQ도 기존 호환을 위해 포함한다.
SimulationRequest.symbol은 이 목록의 문자열을 허용하고 universe는 NASDAQ:<symbol> 하나와 일치해야 한다.
현재 목록: AAPL,MSFT,NVDA,AMZN,GOOGL,META,QQQ,TSLA,AVGO,COST,NFLX,AMD,ADBE,INTC,CSCO,PEP,AMGN,TXN,INTU,QCOM.
응답에는 intervals=[1d,1m,5m,tick], remote_intervals=[1d,1m,5m],
remote_range_days={1m:7,5m:60}, tick_timestamp_label=event, intraday_timestamp_label=close도 제공한다.

새 실행 필드는 grid/walk-forward/portfolio의 전체 SimulationRequest 복사 및 config에 유지한다.
지연/비용 baseline은 같은 snapshot에서 `spread_bps` 또는 `latency_ms`의 0과 비영 값을 grid로 비교할 수
있다. legacy run은 raw JSON hash를 **기본값 주입 전에** 검증하며 새 Fill/Order/Summary/Event 기본값으로
읽는다. 새 실행 JSON 조회/export에는 실제 새 설정과 비용 필드가 보존된다.

## 저장·오류·운영 제한

`GET /research/experiments/{id}` → `200 GridExperiment | WalkForwardExperiment | PortfolioExperiment`.
생성 응답을 checksum 검증 후 그대로 돌려준다. 원본 요청·각 실행 ID·상태를 함께 저장한다.

- 모든 새 POST body는 streaming 64 KiB 제한이다. 모든 연구 filesystem/CPU/provider 작업은
  event loop 밖 전용 capacity limiter(동시 2개)로 실행한다. 프로세스별 한도이며 job queue가 아니다.
- 개별 실행과 grid/walk-forward 기준 snapshot, 별도 QQQ 데이터는 기존과 같이 3,000 bars까지다.
- 실험 30초는 bar 사이 cooperative deadline이다. 외부 공급자 I/O와 filesystem 읽기는 별도
  adapter timeout/기존 bar 제한의 적용을 받으며 엄격한 HTTP wall-time 30초 보장은 아니다.
- 잘못된 요청/지원하지 않는 path는 422, body 초과 413, 없는/잘못된 ID는 404,
  저장 artifact/snapshot 무결성 오류는 409, 공급자 오류는 502다. 기존 API의 공통 오류 envelope
  `{code,message,details,request_id}`를 사용한다. field validation의 상세 공개는 기존 정책을 따른다.
- run JSON은 **저장 당시 raw JSON의 hash를 먼저 검증한 뒤** Pydantic 기본값을 주입한다.
  후속 execution 필드의 기본값 때문에 기존 실행의 hash를 재계산해 거절하지 않는다.
- filesystem immutable artifact 모델을 유지하므로 DB schema migration은 없다. 공개 서비스의
  인증/사용자별 quota/대용량 검색 인덱스·실제 시세 라이선스 검증은 별도 운영 과제다.
