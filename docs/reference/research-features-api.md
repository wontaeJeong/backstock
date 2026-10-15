# 연구 기능 API 계약

Task 1 backend 계약. `/openapi.json`에 모든 요청·응답 schema가 등록된다. 아래 타입은 JSON wire
타입이다. 금액·비율·수익률·상관계수는 **Decimal 문자열**, 수익률은 백분율이 아닌 비율이다.
날짜는 offset 있는 ISO 8601이다. `null`은 0이 아니며 `reason`/`error`를 함께 표시한다.
실제 체결·평가·snapshot을 사용하며 실주문은 없다.

## 공통 요청

기존 `POST /simulations`와 `GET /simulations/{run_id}`의 계약은 변경하지 않는다.
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
    "exposure" | "turnover" | "holding_seconds" | "commission" | "tax" | "slippage", Statistic>;
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
fill_id,order_id,instrument_id,timestamp,side,quantity,reference_price,execution_price,commission,tax,slippage
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

- `commission_bps`, `sell_tax_bps`, `slippage_bps`
- `strategy.position_sizing.{quantity|notional|percent|risk_percent|atr_period|atr_multiple}`
- `strategy.risk.max_holding_bars`
- `strategy.risk.{stop_loss|take_profit|trailing_stop}.{value|atr_period}`
- `strategy.order.limit_offset_bps`
- 진입/청산 condition 안의 `constant.value`, `indicator.period`.
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
각 실행별 제외 timestamp 수를 보존한다. 공통 per-bar 수익률 Pearson 상관계수는 관측 2개 미만/
분산 0이면 null/reason이다. 동일 demo 가격 패턴 경고를 반드시 표시한다.
실패한 component가 있으면 curve와 correlations 모두 비운다. 실패 예산을 무손실 현금으로 가장하지 않는다.

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
