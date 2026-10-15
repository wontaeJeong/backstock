# Functional Research Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 사용자가 전략을 보관·탐색·실험·검증하고 단기매매와 가상매매까지 직접 실행하는 기능 워크벤치를 완성한다.
**Architecture:** 기존 순수 engine과 snapshot을 재사용하고 application use case/API를 확장한다. 기능별 한국어 웹 패널은 서버 계약을 소비하며 금융 계산을 복제하지 않는다.
**Tech Stack:** Python3.12/FastAPI/Pydantic/Decimal/Polars, Next.js16/React19/TypeScript/Zod, 기존 filesystem adapters와 Playwright.
**Spec:** `docs/superpowers/specs/2026-10-16-functional-research-design.md`

## Global Constraints
- Python 3.12 / Node 24 / pnpm 11.1.2, 기존 lockfile과 검증 명령 유지.
- 추가 사용자 질문 없이 진행, 검증 후 커밋·푸시·PR·머지까지 승인됨.
- 한국어 UI, Decimal 계산, immutable snapshot/version, 미래 참조·silent fallback·가짜 성공 금지.
- 실주문·실제 credential·자동 외부 배포 제외. paper는 승인/idempotency/kill switch 필수.
- 390px/1440px, 실제 글자 14px, 25행 페이지, offline fixture와 실제 engine E2E.

## Review Focus
- 모델 필드 확장 뒤 과거 저장 결과가 false corruption으로 바뀌지 않음: Task1 legacy artifact 회귀.
- 학습/검증 구간과 parameter 후보 간 미래 정보·원격 데이터 갱신 누출 금지: Task1 no-future/golden.
- spread/latency/quote 비용을 두 번 차감하거나 bar 시점보다 이르게 체결하지 않음: Task2 execution golden.
- 미체결/실패/미실행, 무거래/분모0를 0% 성공으로 표시하지 않음: Task1/4 null/error 표현.
- paper 승인 우회/중복 요청/재시작/잔고 부족: Task3 offline lifecycle 회귀와 Task4 UI 연동.

### Task 1: 연구 보관함·상세 분석·비교·일괄 실험 backend
**Files:** Create `packages/application/research_library.py`, `research_experiments.py`, `research_analysis.py`, focused model/store helpers, `apps/api/research.py`; extend `packages/application/simulations.py` only for legacy-safe loading and optional trade-start gating; tests under `tests/research/`. Controller/implementer can register router in `apps/api/app.py`.
**Interfaces:** Existing `SimulationService.run(SimulationRequest)->SimulationReport`, verified snapshot reader and fresh `DslStrategyEvaluator` per run. Produce schemas/OpenAPI and `docs/reference/research-features-api.md` consumed by Task4.
Required API:
- `GET /research/library/{strategies|datasets|runs}?q=&page=1&page_size=25&archived=false` returns `{items,total,page,page_size}`.
- `POST /research/library/strategies` body `{definition,description?,tags?}` saves immutable record `{strategy_id,version_id,name,definition,description,tags,created_at}`; `GET /research/library/strategies/{id}`.
- `POST /research/library/{kind}/{id}/archive` body `{archived:bool}` preserves original; run IDs/snapshot IDs are existing hex. Strategy record IDs hex, DSL version retains `sha256:`.
- `GET /research/runs/{run_id}/analysis` returns typed statistics/null reasons, daily/monthly returns, drawdown series, round trips and distributions from actual fills. Definitions/denominators explicit; no double slippage.
- `GET /research/runs/{run_id}/export.csv?kind=fills|equity|orders` full CSV, safe text cells; existing JSON endpoint unchanged.
- `POST /research/compare` body `{run_ids:[...]}` (2..8), comparability and warnings.
- `POST /research/benchmark` body `{run_id,benchmark_symbol:"QQQ",snapshot_id?:str}`; load a separate actual/explicit-demo benchmark dataset and align common timestamps. No implicit same-stock QQQ.
- `POST /research/experiments/grid` body `{base:SimulationRequest,axes:[{path,values}]}`. Numeric path allowlist within strategy/cost fields; max2 axes,16 combinations. Freeze one baseline snapshot, persist real runs and experiment. Return `{experiment_id,kind,rows:[{parameters,run_id,status,total_return,max_drawdown,net_profit,error}],warnings,baseline_snapshot_id}`; failed values null.
- `POST /research/experiments/walk-forward` body `{base,train_bars,test_bars,folds,axes?}` max4 folds/32 runs/30s budget. Train-only selection, untouched test fold, history warmup without training fills; report ranges and actual run IDs, partial/not-run explicitly.
- `POST /research/experiments/portfolio` body `{initial_cash,components:[{weight,request:SimulationRequest}]}` 2..5, sum≤1; fixed independent budget allocation, common-timestamp curve/reserve cash/correlation with exclusions and same-demo-pattern warning.
- `GET /research/experiments/{id}` immutable artifact retrieval.
- [ ] Write/run RED tests for analytics, library immutable/archive/pagination/legacy payload, no-future train/test, same snapshot grid, budgets and invalid IDs.
- [ ] Implement focused models/services/adapters and bounded threadpool API. Keep `SimulationReport` response compatibility; verify stored raw JSON hash before default injection.
- [ ] Test hand-calculated fees/PnL/drawdown/roundtrips, null undefined metrics, actual engine runs and CSV injection; run full Python suite/Ruff/mypy.
- [ ] Document API contract and limitations; commit only owned files and report tests/concerns.

### Task 2: 단기매매 데이터·지표·체결·세션 기능
**Files:** Extend existing domain market-data/strategy schema, indicators/evaluator, backtest models/execution/processing, simulation models/services, yfinance/local adapters; focused support modules; tests `tests/research/test_execution_features.py`, provider/strategy fixture tests. Extend Task1 API docs contract for Task4.
**Interfaces:** New `SimulationRequest` optional `spread_bps` Decimal0..100 default0, `latency_ms` int0..60000 default0, `volume_participation` Decimal(0,1] or null defaultnull (explicitly no volume cap). `BacktestConfig` carries them; display execution limitations in result warnings. Existing defaults preserve daily results.
- Add timezone-aware `tick` timeframe and local CSV `timestamp,price,size` with optional `bid,ask`, unique strictly ordered timestamps, raw only; compatible Parquet and immutable normalized columns. Tick demo explicit synthetic. No fabricated remote tick support.
- Market fills use provided bid/ask when present, otherwise declared spread scenario, then adverse slippage. Track spread separately without subtracting again. Latency makes earliest execution after signal+delay; bar grid limitations explicit. Volume participation is conservative all-or-none (no advertised partial fills).
  For provided quotes, use quote midpoint as the reference, ask/bid as buy/sell base, and adverse slippage after that; price impact components must not overlap. Quote fields must be paired, positive, bid≤ask and raw. Tick size may be zero for quote-only events; an enabled volume cap then permits no fill from that zero size.
- Add stop/stop-limit order contracts with explicit trigger and limit parameters, adverse gap and conservative intrabar ambiguity. Order/risk tracing and pending dedupe remain. Do not claim OHLC path knowledge.
- Add rolling VWAP, population-std Bollinger bands, MACD configurable fast/slow/signal with metadata/lookback; no lookahead, Decimal tests.
- Add optional strategy session controls for New York entry start/end, weekdays, close-based flatten before session end. No fill at signal close; late flatten may remain unfilled and is warned.
- Remote Yahoo 1m/5m uses explicit interval, converts provider open labels to close, validates current provider range restrictions and records provenance; offline fixtures, no silent fallback. Curated Nasdaq symbol catalog search and existing-symbol compatibility; no claim complete PIT universe.
  Conservative free-source bounds are 1m last7days and 5m last60days; only finalized bars at acquisition are published. Remote tick is rejected. Curated catalog search is labeled limited/current, not an exhaustive historical Nasdaq universe.
- [ ] Write/run failing next-event/latency/spread/quote/volume/stop-gap/intrabar/no-future tests and provider timestamp/range/adjustment/checksum fixtures.
- [ ] Implement and propagate models through simulation config and metadata. Preserve legacy artifact validation established Task1.
- [ ] Full Python regression, lint/type/golden/property tests; document exact price/time policies and unsupported queue/partial fills; commit/report.

### Task 3: 승인 기반 가상매매 backend
**Files:** Create focused `packages/domain/paper.py`, `packages/application/paper.py`, `packages/broker/paper_store.py`, `apps/api/paper.py`, tests `tests/paper/`, update `BROKER_INTEGRATION.md` and API contract. Register in app.
**Interfaces:** `/paper/accounts` POST `{name,initial_cash}` / GET list, GET `/{id}` state; POST `/{id}/proposals` `{symbol,side,quantity,reference_price,quote_at,idempotency_key}`; POST `/{id}/orders/{order_id}/approve|reject|cancel` with idempotency key; POST `/{id}/kill-switch` `{enabled}`. Return full typed account `{account_id,name,cash,positions,orders,audit,kill_switch,mode:"paper"}` with Decimal strings.
- Also `POST /paper/accounts/{id}/quotes` `{symbol,price,quote_at,idempotency_key}` for explicit manual valuation marks, and `GET /paper/accounts/{id}/reconciliation` for internal initial-cash/fill/position ledger consistency (not external broker reconciliation). Quotes/proposals do not themselves fill orders; display valuation quote/source separately from cash/realized money. Kill switch blocks new order risk, not safe reject/cancel or read-only checks.
- Pure domain money/position logic, no live SDK/credentials/network. User-supplied/snapshot quote is explicitly historical/manual, not live. Proposed orders do not change balances; approval applies risk and executes a labeled paper fill at the reference quote with declared costs. Long-only, no negative cash/positions, bounded notional/order size. Reject/cancel are real state transitions.
- File lock + atomic mutable account state, immutable audit/event records, persistent request-id binding; reusing key with changed payload is rejected, exact retry returns same result after restart. Kill switch blocks proposals/approval, production flags cannot turn this into real broker.
- [ ] RED approval-bypass, insufficient cash/position, idempotency conflict/exact retry/restart, concurrent approvals, quote marks/unchanged cash, internal reconciliation, kill-switch and audit redaction tests.
- [ ] Implement domain→application→store/API boundaries with bounded input/threadpool and documented Korean semantics.
- [ ] Full Python suite/lint/type, architecture dependency tests; commit/report contracts for UI.

### Task 4: 모든 기능의 한국어 워크벤치 UI·통합 검증
**Files:** Focused `apps/web/components/research/*` and `apps/web/lib/*`, research route proxy allowlist, workspace/draft/schema, styles, `tests/e2e/features.spec.ts`, documentation and feature matrix. No financial calculation duplication.
**Interfaces:** Read Task1/2/3 `docs/reference/research-features-api.md` and report files; bind all implemented endpoints. Extend Zod preserving all artifact fields. Keep original workspace/simulation routes and offline E2E passing.
- Connect library search/pagination/archive/restore, strategy save/load/clone/JSON import/export and validated JSON editing to current draft.
- Extend symbols/indicators/order/session/tick/quote/spread/latency/participation controls, remote minute limits and clear data provenance.
- Server-backed detailed stats/null explanations, monthly returns/drawdown, trades, bar-state replay with trade markers, CSV exports, persistent run selection/comparison and genuine QQQ benchmark.
  Add a thin verified data-preview use case/API `GET /research/datasets/{snapshot_id}/bars?page=1&page_size=250` (1..1000, max3000-row research snapshot before decoding) returning `{snapshot_id,interval,items:Bar[],total,page,page_size}` if the earlier backend contract lacks bars. Use it for OHLC/tick price inspection and replay; preserve Decimal/quote/timestamp fields and do not expose filesystem paths. Display chart windows rather than compressing thousands of candles into unreadable widths.
- Grid/cost scenarios, chronological walk-forward and fixed-budget portfolio controls/results use current edited strategy and actual run IDs. In-sample/failed/not-run/zero-trade distinctions visible.
- Paper account/propose/approve/reject/cancel/kill-switch/portfolio/audit controls with explicit paper/manual quote labels and no live-order controls.
- [ ] RED unit and E2E for every feature group, input preservation/failure viewport, reload/library versions and API errors.
- [ ] Implement Korean accessible controls with 25-row pages and readable min14px chart/table regions; no decorative dead controls.
- [ ] Full required lint/type/unit/Python/production build/E2E at390/1440, real engine fixture flows, contract regressions and precise feature/limit matrix.
- [ ] Commit/report; independent whole-branch review, fix covering tests, remote CI then PR merge (already authorized).
