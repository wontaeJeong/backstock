# Task 1 구현 보고

## 상태·커밋

- 상태: **DONE**. brief의 보관함·분석·CSV·실행 비교·별도 QQQ·grid·walk-forward·고정 예산
  portfolio·immutable experiment 조회를 구현했다. placeholder/가짜 성공/skip은 없다.
- 기준: `deef12c`, 기존 전용 worktree `research-features`, 브랜치 `feat/research-features` 재사용.
- 구현 커밋: `f128fa3` — `feat(research): add immutable library analytics and bounded experiments`.
- 이 보고서 자체는 별도 문서 커밋으로 보존한다. push/merge/새 worktree/subagent 실행은 하지 않았다.
- 부모 세션이 편집 중인 `docs/superpowers/plans/2026-10-16-functional-research.md`와
  `docs/feature-matrix.md`는 staging/수정하지 않았다.

## 제공 API / Task 4 연결 지점

**전체 JSON wire 타입, 완전한 실행 가능 base 요청 예시, body 조합 예시, 응답 타입/수치 예시,
path allowlist와 모든 제한은 `docs/reference/research-features-api.md`에 있다.**
OpenAPI에는 실제 Pydantic schema가 등록되어 있다. Task 4는 Decimal 문자열을 표시용으로만
변환하고 통계를 다시 계산하지 않아야 한다. undefined는 null/reason, 실패/미실행은 status/error다.

| Endpoint | 실제 구현 / 응답 |
| --- | --- |
| `GET /research/library/{strategies|datasets|runs}` | q/page/page_size/archived, `{items,total,page,page_size}` |
| `POST /research/library/strategies` | definition/description/tags, immutable `StrategyRecord`, 201 |
| `GET /research/library/strategies/{id}` | 저장된 정의·version·설명·태그·생성시각 |
| `POST /research/library/{kind}/{id}/archive` | `{archived:bool}` → `{kind,id,archived}`, 원본 보존 |
| `GET /research/runs/{run_id}/analysis` | 16개 통계·null 이유·계산식, 일/월 수익률, drawdown, FIFO round trips, 원본 분포 표본 |
| `GET /research/runs/{run_id}/export.csv?kind=fills|equity|orders` | 모든 기록 CSV, text formula injection 차단, 실제 음수 금액 보존 |
| `POST /research/compare` | 2..8 run IDs, rows/comparable/differences/warnings |
| `POST /research/benchmark` | 별도 실제/명시적 demo QQQ snapshot, 공통 timestamp와 제외 수 |
| `POST /research/experiments/grid` | 최대 2 axes/16조합, 한 기준 snapshot, 실제 run IDs/실패/null/미실행 |
| `POST /research/experiments/walk-forward` | 최대 4 folds/32회/30초 cooperative 예산, train-only 선택, fresh test capital |
| `POST /research/experiments/portfolio` | 2..5 components, 비중 합≤1, 독립 예산·현금 reserve·공통 curve·상관/제외 |
| `GET /research/experiments/{id}` | hash 검증한 immutable 생성 응답 |

## 설계·경계

- `apps/api/research.py`: thin adapter, streaming 64 KiB POST 제한, 모든 application 호출을
  event loop 밖 AnyIO capacity limiter(동시 2개)에서 수행한다. typed OpenAPI 응답을 제공한다.
- `research_library.py` / `research_store.py`: 기존 snapshot/run reader를 재사용한다.
  새 전략/실험은 hash-addressed write-once JSON, archive는 atomic replace sidecar다.
  filesystem authority 유지 결정이므로 DB migration은 없으며 `docs/assumptions.md`에 기록했다.
- `research_analysis.py`: engine artifact만 사용하는 순수 계산, Decimal 금액, FIFO matched lot
  수수료 배분. 슬리피지는 execution price에 있으므로 두 번 빼지 않는다.
- `research_comparison.py`: 비교 차원 검증과 별도 QQQ acquisition/verified reader.
  업로드 실행에서 QQQ snapshot이 없으면 거절하고 AAPL 데이터를 QQQ라 부르지 않는다.
- `research_parameters.py`: 숫자 DSL/비용 경로 allowlist. 이름/metadata/universe/timeframe/
  shift/임의 path/원금 편집은 거절한다. 각 조합을 원래 Pydantic schema로 다시 검증한다.
- `research_experiment_models.py` / `research_experiments.py`: 요청·결과 모델과 실제 순차 실행.
  실패한 후보의 수익/손익/낙폭은 null, 시작하지 않은 후보는 not_run이다.
- `simulation_history.py`: execution에 들어가지 않는 사전 history를 indicator context에만 제공한다.
  엔진은 test bar만 받고 evaluator와 원금은 매번 새로 만든다.
- `SimulationService.run(request)` 기존 호출은 그대로 동작한다. 선택적 keyword-only
  `trade_start`, `trade_end`(exclusive), `deadline`만 추가했다. 정상 실행의 response schema는
  변경하지 않았다. history는 warmup에만 쓰고 benchmark/portfolio/annualization은 test만 포함한다.
- run get은 **저장된 raw JSON hash부터 검증한 후** schema 기본값을 주입한다. 이후 execution
  필드 기본값 추가가 기존 run hash를 깨지 않도록 하는 load-bearing 호환 처리다.
- frontend, execution engine core, provider, request/config schema, broker는 수정하지 않았다.

## 정확성 정의

- net profit = final equity−원금, 초기 원금 포함 max drawdown.
- 일/월 마지막 관측 equity의 구간 수익률. 날짜 누락 보간 없음.
- volatility: 일 수익률 표본표준편차×√252. Sharpe 무위험 0, Sortino 목표 0/전체 관측일 분모.
- CAGR: 평가 구간 경과일과 365.25 기준, 1일 미만/비양수/overflow는 null.
- win rate/profit factor/expectancy는 닫힌 FIFO matched lot만 사용한다. 열린 포지션을 승리로 세지 않는다.
- exposure는 보유 bar 비율, turnover는 양방향 execution notional/초기 자본, holding은 lot당 경과초.
- walk-forward는 rolling train→test이며 train total_return만 선택, 동률은 첫 후보다.
  test 미래 가격을 바꿔도 training 손익/선택이 바뀌지 않는 fixture로 검증했다.
- portfolio는 재조정/현금 공유 없는 고정 예산이다. 실패한 component가 있으면 합계 curve와
  correlations를 모두 비우며 그 예산이 무손실 현금이었다고 가장하지 않는다.

## RED → GREEN 증거

1. `uv run pytest tests/research -q`: 최초 **6 failed**.
   신규 endpoint는 404, legacy payload는 저장 당시 없던 `config.bar_interval` 기본값 때문에
   hash 검증에서 ValueError였다. 구현 후 동일 6개 테스트가 통과했다.
2. 추가 정확성/CSV/무결성 테스트: **8 failed, 15 passed**.
   실제 엔진 golden 계산의 비용 통계 누락, 숫자 음수까지 apostrophe 처리, malformed JSON의
   잘못된 422를 확인했다. 비용 통계·text-only escape·409 무결성 분류 후 통과했다.
3. `test_partial_portfolio_withholds_correlations_and_total_curve`: **failed**.
   missing snapshot component가 전체 404로 종료되어 나머지 실제 실행/실패 행을 보존하지 못했다.
   typed acquisition 실패를 component failed 행으로 보존하고 불완전 합계/상관을 비운 후 통과했다.
4. `test_grid_rejects_oversized_baseline_before_decoding_for_runs`: **failed**(201, 실패 행).
   `test_benchmark_rejects_oversized_separate_qqq`: **failed**(200).
   두 baseline에 동일 3,000 bar 사전 상한을 적용한 후 통과했다.
5. 최종 기존 전체 테스트+새 연구 테스트 **197 passed**, skip/실패 없음.

새 연구 테스트는 30개(파라미터화 포함)다. 실제 offline snapshot·실제 engine runs를 사용하며
실제 credentials, 네트워크 시세, live orders는 사용하지 않는다. clock 주입은 예산 소진 경계만
결정적으로 검증하며, 결과 성공을 mock하지 않는다.

주요 검증: immutable/archive/pagination, 기존 run/dataset 조회, raw legacy hash/tamper,
실제 수수료·세금·슬리피지·FIFO partial fee 배분, hand-calculated PnL/DD/수익률 복리 일치,
null 이유·분봉 연율화 제한, 전체 CSV/injection, 별도 QQQ 실제 fixture 가격,
grid 같은 snapshot/실패 null, test warmup·fresh capital·미래 perturbation,
budget not_run, portfolio reserve·부분 실패·상관, body/run/axis/ID/bar 상한, experiment tamper.

## 최종 검증 결과

구현 커밋 직전 전체 명령을 실행해 실제 출력을 확인했다.

```text
uv run pytest                  197 passed in 3.15s
uv run ruff check .            All checks passed!
uv run ruff format --check .   116 files already formatted
uv run mypy .                  Success: no issues found in 116 source files
```

초기/종료 worktree 확인: 기본 `/Users/wt.jeong/workspace/backstock`는 `main`, 현재 작업은
전용 `feat/research-features`다. 다른 worktree/브랜치를 전환하거나 수정하지 않았다.
웹을 수정하지 않아 이번 하위 작업에서는 pnpm/browser 검증을 실행하지 않았다. 전체 통합 검증은
부모 세션의 후속 UI·engine 작업 뒤 필요하다.

## 제한·후속 통합 주의

- 30초는 **bar 사이 cooperative 계산 budget**이다. provider I/O/파일 읽기의 별도 bounded timeout을
  포함한 HTTP hard wall time 30초를 주장하지 않는다. API 동시 작업 한도는 프로세스별 2개다.
- 보관함 pagination은 로컬 파일 metadata 검색 후 slicing이다. 대용량 DB 인덱스·authz·사용자 quota는
  구현했다고 주장하지 않는다. 모든 run/실험은 현재 파일 authority 모델을 따른다.
- demo QQQ/다종목 demo는 동일 합성 패턴이므로 독립 시세/분산투자 증거가 아니다. warnings에 명시한다.
- 상관은 공통 per-bar equity returns다. calendar 기반 missing-session 보정/통계적 유의성 검정은 없다.
- 미래 데이터가 evaluator에 전달되지 않음을 검증했지만 무료 시세의 point-in-time 보정, corporate action
  cash ledger, tick/호가/부분 체결 등 기존 engine 정확성 제한은 새 통계로 해결됐다고 주장하지 않는다.
- API 문서의 타입은 Task 1 상태다. Task 2에서 execution 필드를 추가할 때 연구 요청의 base는 기존
  `SimulationRequest` 전체 schema를 재사용하므로 자동 전달된다. raw artifact hash loading은 기본값
  주입 전에 끝나야 한다는 순서를 유지해야 한다.
- 부모 세션이 최종 UI 문구를 한국어로 구성할 수 있도록 원시 key/통계 definition은 보존했다.
