# Task 4 보고서 — 한국어 연구 워크벤치

## 결과

**DONE_WITH_CONCERNS** — 요청한 기능 그룹을 연결하고 검증·구현 커밋을 완료했다.
아래의 명시적 UX/운영 제한과 controller 최종 검토 항목은 남아 있다. 미완성 stub·가짜 성공·test skip은 없다.

- 작업: 기존 `research-features` 워크트리 / `feat/research-features`, 기준 `d6a6b74` 재사용.
- 구현 커밋: `7c20141` — `feat(web): connect Korean research workbench and verified analysis bridges`.
- 보고서는 이 구현 커밋 뒤의 별도 문서 커밋으로 기록한다.
- 새 워크트리/브랜치·subagent·push·PR·merge는 하지 않았다. 최종 독립 리뷰·원격 CI·PR/merge는 controller 담당이다.

## 기능별 구현·근거

상세 공개 매트릭스는 `docs/reference/research-feature-matrix.md`, 정확한 wire 계약은
`docs/reference/research-features-api.md`에 갱신했다. README/PRD/ARCHITECTURE/assumptions도 현재 상태로 갱신했다.

| 그룹 | 완료 내용 | 주요 검증 |
| --- | --- | --- |
| 편집/버전 | 현재 편집 전략 save/load/clone, JSON import/edit/server validation/export, 새 immutable version, unsupported nested AST 보존 | library reload/archive/restore E2E, 중첩 not+ATR sizing/trailing risk import/export 파일 내용 동일, 불완전 JSON 입력·오류 복귀, import 종목/주기 동기화 unit |
| 전략/실행 설정 | 20종목 및 서버 현재 종목 검색, tick/quote, 새 지표, 실제 MACD fast/slow/signal, Bollinger 배수, 주문 market/limit/stop/stop_limit·offset·DAY/GTC, 뉴욕 세션, spread/latency/nullable participation, 명시적 최근 원격 분봉 기간 preset | 실제 tick 업로드→simulation 요청/결과 execution 설정 전파 E2E, MACD sweep 경로 unit, Decimal 문자열 정밀도 회귀 unit |
| 보관함 | 전략/데이터/실행 서버 검색·25건 페이지·보관/복원·snapshot 재사용·실행 선택 | 실제 API 보관함 E2E와 기존 backend library 테스트; 동일 서버에서 새로고침 후 재조회 |
| 분석/원본 | 서버 통계·null 이유·정의, 월별/일별·drawdown·FIFO roundtrip·분포, 전체 CSV, 정확한 verified OHLC/tick/quote·bar-state slider·25개 가격 창·정확한 timestamp 체결 표식 | 서버 hand calculation/preview cap/integrity 테스트, 분석/CSV E2E, 실제 SVG bounds·font·표/키보드 측정 |
| 비교/QQQ | 지속 선택된 실행 2..8개 서버 비교, 비교 목록 페이지, 별도 QQQ snapshot 페이지/선택 및 genuine symbol 데이터로만 benchmark | 실제 compare 선택/reload E2E, 별도 업로드 QQQ 400→404와 AAPL 100→104 fixture의 독립 snapshot benchmark E2E (`local_file`, return `0.01`, 공통 5점), demo는 별도 synthetic QQQ로 명시 |
| 실험 | 현재 편집 request 기반 최대 2축 grid, 비용 민감도 preset, 순차 walk-forward, fold nested test.error fallback, 2..5개 독립 고정 예산 구성·실제 run 열기·서버 금융 요약·실험 ID 재조회/JSON | 실제 엔진 grid/walk-forward/portfolio E2E, 기존 chronology/경제/상관 backend 회귀, portfolio summary hand calculation·불완전 null |
| Paper | create/list/get, proposal/approve/reject/cancel, 수동 quote mark, portfolio/audit/내부 reconciliation, kill on/off, 같은 키 재시도, 성공/실패 뒤 current GET | 후보 시 현금 1000 유지→승인 cash 799.87999→mark equity 1039.87999/cash 불변→kill 차단 E2E; 위험 거절·취소·거절·대사 E2E; 과거 성공/실패 POST 후 current GET unit |
| 보안/접근성 | exact path/method allowlist·same-origin 유지·안전한 CSV attachment header, response passthrough, 한국어 설명·오류 초점/입력 보존·키보드 복귀·탭 이동 | 기존 16 E2E 유지, proxy unit/기존 cross-origin E2E, 새 오류/JSON/초기 busy 회귀 |

금융 수치 계산은 Python에만 있다. 브라우저의 숫자 처리는 입력 범위 검사/표시·차트 좌표뿐이다.
source/model/metadata 식별자·정확한 timestamp 문자열·Decimal·추가 response 필드는 그대로 보존한다.
equity/QQQ 정규화 평가액을 주가로 부르지 않으며 manual quote는 현재 거래소 가격이 아니다.

## 서버 브리지

- `GET /research/datasets/{identity}/bars`: 검증된 manifest row_count≤3000을 **decode 전에** 확인,
  기존 checksum-bound reader 재사용, page 1..1,000,000/page_size 1..1000, 기본 250. Bar 전체 필드 보존,
  실제 filesystem 경로·storage URI를 반환하지 않는다. UI는 page_size=25로 사용한다.
- `Analysis.statistics.payoff_ratio`: 양수/음수 closed-lot **net** PnL 평균 비율. 두 분류 중 하나가
  없으면 null+reason. 합계 비율 profit factor와 별도다. 손계산 +20/+10/−10 → 1.5를 검증했다.
- `GET /research/experiments/{id}/analysis`: portfolio-only 파생 조회. 초기/최종 equity·손익·수익률·낙폭을
  서버 Decimal로 계산한다. curve 없음/실패 구성/제외 timestamp가 있으면 모든 통계를 null+reason으로
  보수적으로 보류한다. 원본 실험을 덮어쓰지 않는다. 1000→1100→990은 PnL −10/return −.01/MDD .1.

기존 execution/paper/experiment 경제 규칙은 바꾸지 않았다. filesystem artifact이므로 DB migration은 없다.

## 실제 RED→GREEN 및 통합 중 발견한 오류

- 최초 bridge 테스트: **4 failures** (404 bars, cap endpoint 없음, payoff KeyError, portfolio analysis 모듈 없음)
  → 구현 뒤 4 passed. 이후 integrity/contract 회귀를 더해 현재 bridge 파일은 6개다.
- 최초 UI unit은 features 모듈 부재로 실패했고 최초 E2E는 보관함 버튼 부재로 실패했다.
  초기 E2E는 `--max-failures=1`이었으므로 나머지 그룹 각각의 최초 RED가 관측됐다고 주장하지 않는다.
- 추가 실제 assertion RED→GREEN: 체결 표식/cursor 없음, import 시 symbol/timeframe 동기화 없음,
  JSON 모드의 간편 폼 비활성화 없음, JSON 오류 뒤 비활성 select로 복귀, 모바일 기본 분석 길이 9048px,
  불완전 portfolio excluded timestamps의 summary 노출, Decimal `0.10000000000000001`→`0.1` 손실,
  초기 조회 중 첫 렌더 변경 버튼 미잠금, 한국어 통계명 없음.
- 새 테스트 locator의 hidden 원본 표/Next route announcer 중복 선택은 trace로 원인을 확인해 정확한
  visible/semantic 대상에 한정했다. 성공 조건을 느슨하게 바꾸거나 테스트를 skip하지 않았다.
- 기존 Python `test_same_key_concurrent_approval_and_read_only_reconciliation`이 전체 실행 중 두 번
  FastAPI/Pydantic lazy route schema의 `UnsupportedFieldAttributeWarning`으로 실패했다.
  `.venv/.../fastapi/_compat/v2.py`의 `warnings.catch_warnings`/전역 filter 사용과 lazy route 생성
  stack을 확인했다. factory에서 public `app.openapi()`를 한 번 구성하는 회귀를 RED→GREEN으로 추가했다.
  warning ignore나 paper 경제 변경 없이 이후 전체 343개가 연속 두 번 및 마지막 추가 실행에서 통과했다.
- 최종 반복 중 mobile paper create 1개가 최초 GET만 있고 POST가 없는 trace로 실패했다. 패널 mount
  초기 조회의 busy 전환 전에 누른 버튼이 비활성화되며 이벤트가 사라지는 race였다. 초기 busy를 첫 렌더부터
  적용하는 unit RED→GREEN을 추가하고 library/analysis/paper에 적용했다. 이후 production 80개 반복 및
  마지막 40개가 모두 통과했다. create POST 자동 재시도는 추가하지 않았다.

## 최종 검증 결과

Node는 지정된 Node 24 wheel 경로를 PATH 앞에 두었다. dependency 변경은 없다.

| 명령 | 실제 결과 |
| --- | --- |
| `uv run ruff check .` | 통과 |
| `uv run ruff format --check .` | 133 files formatted, 통과 |
| `uv run mypy .` | 133 source files, 통과 |
| `uv run pytest` | 최종 343 passed; 초기 race 수정 후 연속 2회 343 passed |
| `uv run pytest -q` | 마지막 전체 343 passed (19.42s) |
| `pnpm lint` | 46 files, 오류/경고/추가 diagnostic 없이 통과 |
| `pnpm typecheck` | 통과 |
| `pnpm test` | 4 files / 17 tests passed (기존 7개 포함) |
| `pnpm build` | Next.js 16.2.10 production build 통과 |
| `CI=1 pnpm exec playwright test --repeat-each=2` | 80 passed (40개 viewport case ×2); 초기 busy fix 뒤 수행 |
| `CI=1 pnpm exec playwright test` | 마지막 40 passed (36.0s): 기존 16 + 새 24, 실제 production server+API |
| `git diff --check` | 통과 |

80회 반복 뒤 마지막 Decimal-preservation 변경을 추가했고, 그 최종 코드로 17 unit/production build/40 E2E를
다시 통과했다. 마지막 이후 변경은 TypeScript index-signature와 충돌하는 Biome style diagnostic의 설명
comment뿐이며 lint/typecheck/17 unit을 다시 확인했다.

## 실제 Chromium 390/1440 측정

스크린샷을 실제 읽어 첫 결론·수치·표시 크기·내부 스크롤을 확인했다. 테스트 output screenshot/trace 및
`feature-layout` attachment에 근거가 있다. screenshot은 document 전체가 아니라 앱 내부 main scroll
viewport를 담으므로 길이는 DOM scrollHeight로 별도 측정했다.

| 항목 | 390×844 | 1440×1000 |
| --- | --- | --- |
| document scrollWidth | 390px | 1440px |
| 기본 분석 main 길이 | 3367px | 2626px |
| 핵심 수치 시작 viewport y | 464.80px | 277.06px |
| 분석 제목 viewport y | 69.25px | −0.125px (subpixel, 실제 제목 표시 확인) |
| 월별 그래프·OHLC 25행을 펼친 길이 | 5815px | 5074px |
| 실제 표시 SVG font | 16px | 16px |
| SVG text bbox | x≥20, end≤793.46 / viewBox 900 | 동일 |
| 원본 OHLC 표 내부/콘텐츠 너비 | 330 / 1680px | 1084 / 1680px |
| header/row 높이 | 67.875 / 68.375px | 동일 |
| 표 글자 | 14px | 14px |
| 페이지별 표 행 | ≤25 | ≤25 |

가독성 수정 전 실제 mobile 기본 분석은 **9048px**, 핵심 수치는 **1511.23px** 아래였다.
기본 경고/상세 통계/비교 목록을 접고 핵심 수치를 앞으로 옮겨 위 수치로 개선했다.
SVG는 축소하지 않고 내부 스크롤하며, 표도 모바일에 압축하지 않는다. summary Enter, 표 ArrowRight,
오류 focus/Tab/JSON 복귀와 패널 제목 focus를 실제 브라우저에서 검사했다.

## 남은 제한·controller 검토 항목

1. 중첩 AST·fixed quantity/notional·ATR sizing·trailing/ATR risk·요일은 명시적 **고급 JSON 모드**다.
   이 정의를 보존하고 실행할 수 있지만 모든 AST를 시각적 폼으로 역변환하는 편집기는 아니다.
2. 가격 replay는 수동 slider+25-bar 창과 종가/print 선·실제 체결 표식, OHLC/quote·bar-state 표다.
   자동 재생 애니메이션/캔들 wick 렌더러는 없고 OHLC 내부 순서를 추측하지 않는다.
3. 비교 선택/실험 ID/선택 paper 계좌만 이 브라우저에 기억한다. 원본 실행·전략·snapshot·계좌는 서버가
   authoritative하다. URL 공유용 workspace state/사용자 계정 동기화는 없다.
4. 이번 검증은 deterministic offline engine/업로드 fixture다. Yahoo 네트워크 가용성을 재검증하거나
   라이선스·실시간 feed·거래소 queue·PIT 목록·corporate-action 원장·auth·분산 운영을 구현했다고 하지 않는다.
5. 기존 Task 3 minor fee-policy forgery reconciliation은 요청대로 건드리지 않았다. controller 최종 triage 대상이다.
6. 초기 전체 UI 그룹 각각의 최초 RED 로그는 분리되지 않았다(위 TDD 기록 참조). 현재 기능 그룹 모두
   실제 API/engine E2E에 포함되지만 모든 제어 조합·브라우저 종류를 exhaustive 검증했다는 뜻은 아니다.
7. 원격 CI/독립 전체 브랜치 리뷰/PR/merge는 이 subagent가 실행하지 않았다. controller가 이어서 수행한다.

---

## Scoped review 수정 1/5 — 기준 `64e24ee`

**DONE** — I1/I2/I3/I4와 Important로 재분류된 M1을 수정했다.
구현 커밋: **`fe68939`** (`fix(web): isolate research results and complete sizing and paper controls`).
이 절은 위의 기본 sizing/risk/요일 JSON 전용 제한(제한 1번)을 **대체**한다. 기본 설정을 JSON으로
작성해야 하는 상태를 완료로 재분류하지 않았다. 임의 중첩 조건의 시각적 역변환만 여전히 범위 밖이다.

### Finding별 RED → GREEN

| Finding | 관측한 실제 RED | 수정 및 GREEN 근거 |
| --- | --- | --- |
| I1 | A→B analysis/bars 실패 전환 직후 `A_ONLY_METRIC`이 남음. 늦은 A 응답이 B 뒤에 `LATE_A_METRIC`으로 표시됨 | `AnalysisPanel`의 run+snapshot keyed 소유자를 동기적으로 교체한다. 분석·가격을 함께 검증/게시하며 응답 run_id/snapshot_id 불일치는 오류로 처리한다. 새 로딩/실패에서는 기존 통계·CSV·replay를 숨긴다. 요청 sequence는 늦은 이전 결과를 버린다. unit의 즉시 rerender/409/bars failure/late A/wrong-ID 및 실제 API 기반 브라우저 409·late 응답 회귀 통과 |
| I2 | fixed quantity 입력인데 생성 결과가 `percent_equity`였음. 가져온 JSON에서 빈 notional 폼을 이전 JSON으로 대신 실행함. % 모드의 숨겨진 잘못된 ATR 기간이 실행을 막음 | 한국어 fixed quantity/notional/percent equity/ATR risk 폼, %/ATR 손절·익절·추적 손절과 유효 기간/배수, 진입 요일 GUI를 구현했다. 현재 폼은 실행·저장·실험의 같은 정의에 연결된다. 가져온 정의는 해당 설정 분기만 갱신하며 중첩 AST·다른 risk·session·Decimal을 보존한다. 불완전 폼은 오류로 막고 예전 JSON으로 실행하지 않는다. ATR 기간은 ATR 모드에서 필수다. 실제 엔진 네 가지 sizing 및 모든 ATR risk 요청·import/form roundtrip E2E와 unit 통과 |
| I3 | 정상 pending 26건 계좌에 “후보 다음 25개”가 없어서 첫 후보 작업에 접근할 수 없음 | action-bearing 목록 전체에 25건 페이지·검색·안정적인 order_id를 적용하고 종료/검색 이후 페이지를 보정한다. 실제 API로 26개 후보를 만든 뒤 kill ON에서 26번째 이전 후보를 취소하고 POST→current GET·cash 1000 불변·cancelled를 확인했다. pending 검색 26→25에서 page 2→1 보정도 검증 |
| I4 | source=snapshot / manifest.provider=yfinance인 실제 컴포넌트가 “사용자 파일 · 시세 출처 미검증”을 표시함 | `lib/provenance.ts`에 synthetic_demo/yfinance/local_file/unknown 분류를 중앙화하고 분석·기존 결과 화면이 같이 사용한다. snapshot 재사용은 별도 표시다. Yahoo reuse·local·unknown unit 및 기존 업로드/demo 실제 E2E 통과. unknown을 Yahoo로 추정하지 않음 |
| M1 (Important) | 검색 버튼을 누르기 전 “Tesla” 입력만으로 GET이 1→2회 발생하고 입력을 잠금 | 편집 q와 submitted q 분리. Enter/검색 버튼만 제출하고 검색 input·scope 선택은 fetch 중에도 편집 가능하다. 페이지는 제출 조건을 유지한다. scope+sequence 소유권으로 늦은 검색/이전 종류 결과를 버린다. unit 및 지연 실제 브라우저 요청에서 GET 목록 `['', 'Tesla', 'TeslaX']`·로딩 중 입력 보존·추가 글자별 GET 없음 검증 |

추가 소유권 검증: QQQ는 기준 실행+QQQ snapshot 선택에 묶고 선택 변경 즉시 숨긴다. 비교는 정렬된
선택 run ID 집합에 묶고 response rows의 실제 ID도 확인한다. 늦은 이전 비교가 적용되지 않는 unit이 있다.
paper 계좌 선택이 바뀌면 기존 계좌를 즉시 숨기고, GET/POST 후 current GET의 실제 account_id와 현재
선택이 일치할 때만 적용한다. 계좌 전환/늦은 이전 GET unit도 통과했다. 보관함 종류 변경 뒤 이전 객체를
새 종류의 action 대상으로 사용하지 않는 회귀도 있다. `useOperation`의 busy/error는 최신 작업만 소유한다.

### 안전·정확성 보존

- 금융 계산은 서버에만 있다. 추가 클라이언트 처리는 폼 입력 검증과 %↔비율의 **문자열 자릿수 이동**뿐이다.
  notional/risk 배수·값을 binary float로 다시 직렬화하지 않는다.
- 기존 percent-equity 기본값과 기존 한국어 기본 라벨을 유지했다. 새 기본 설정은 raw DSL 작성이 필요 없다.
  고급 JSON의 미지원 중첩 조건은 그대로 두면서 sizing/risk/session 폼을 사용할 수 있다.
- response passthrough·전체 JSON·CSV proxy/header·same-origin·null/실패 구분·paper 모든 POST 뒤 current GET·
  create 자동 retry 없음은 유지했다. Task 3 fee-policy minor와 backend 경제 규칙/계약은 수정하지 않았다.
- README, `docs/assumptions.md`, `docs/reference/research-feature-matrix.md`, API reference를 갱신했다.

### 최종 실제 검증

| 명령 | 결과 |
| --- | --- |
| `uv run ruff check .` | 통과 |
| `uv run ruff format --check .` | 133 files, 통과 |
| `uv run mypy .` | 133 source files, 통과 |
| `uv run pytest` | **343 passed**, 18.55s (backend 변경 없음) |
| `pnpm lint` | **52 files**, diagnostic 없이 통과 |
| `pnpm typecheck` | 통과 |
| `pnpm test` | **5 files / 33 passed** (기존 17 + 새 회귀 16) |
| `pnpm build` | production build 통과 |
| `CI=1 pnpm exec playwright test` | **52 passed**, 약 1.2m. 기존 40 + 새 12 viewport 실행, 실제 production server+API |
| `git diff --check` | 통과 |

신규 브라우저 테스트: `tests/e2e/task4-review.spec.ts`. 마지막 전체 실행에는 숨겨진 % 모드 ATR 기간
회귀 수정까지 포함한다. 초기 집중 브라우저 10개 실행에서 mobile import test가 파일 읽기 완료 전에
다음 폼 편집을 시작해 timeout 1개가 발생했다. 기존 import 완료 status를 기다리도록 테스트 동기화를
수정했으며 timeout 증가/skip/경제 값 변경 없이 이후 전체 52개가 반복 통과했다.
I1 브라우저 회귀의 A/B는 실제 엔진 생성 artifact이며, 보관함 목록만 그 실제 응답으로 제한했다.
409와 지연은 browser route에서 의도적으로 주입한 네트워크 경계 테스트다. 서버 파일을 실제 손상시킨
브라우저 테스트나 Yahoo 현재 네트워크 smoke로 주장하지 않는다. I3의 26개 후보와 취소/GET은 실제 API다.

### 실제 390/1440 레이아웃

스크린샷(`sizing-risk-controls.png`, `pending-pages-kill.png`)과 DOM 수치를 실제 읽었다.
분석 화면 SVG·표·키보드·오류 focus 검증도 기존 E2E에서 다시 수행했다.

| 측정 | 390px | 1440px |
| --- | --- | --- |
| 문서 가로 폭 | 390px | 1440px |
| 수량/risk 폼 input/select 실제 글자 | 14–16px | 14–16px |
| risk와 JSON을 사용자가 펼친 편집 흐름 main 길이 | 6483px | 4904px |
| 작업 가능한 후보 페이지 | 25건 | 25건 |
| 후보 card 행 높이 | 230.56px | 182.58px |
| 기본 분석 main 길이 | 3367px | 2626px |
| 핵심 수치 viewport y | 464.80px | 277.06px |
| 기존 분석 실제 SVG 글자/경계 | 16px, x≥20/end≤793.46 of 900 | 동일 |
| 원본 OHLC 표 viewport/content 폭 | 330/1680px | 1084/1680px |

6483px는 모든 risk와 고급 JSON을 **직접 펼친** 편집 상태의 길이다. 기본 분석을 길게 펼치거나 표를
압축해 숫자를 줄인 것이 아니다. 기본 legacy 실행 E2E의 main<6000 조건도 그대로 통과했다.

### Controller에게 남기는 문서 갱신 안내

`docs/feature-matrix.md`는 **읽기만 했고 수정·stage하지 않았다**. 확인한 SHA256은
`a4ac65fa7475df1292e5d006b5bdf655df54ae7c04448d954171d7691326d559`로 작업 중 동일했다.
controller가 자신의 미커밋 문서 변경에 아래를 반영하면 된다:

- **23–24행**: fixed 수량/금액·ATR sizing·trailing/ATR risk·요일을 “JSON 전용”으로 묶은 제한을 제거하고,
  한국어 기본 폼 및 import 이후 해당 분기만 수정함을 명시. 임의 중첩 조건의 고급 JSON 제한만 남김.
- **10행**: 네 가지 sizing와 %/ATR risk·기간/배수·요일 GUI 및 실제 엔진 요청/import 회귀를 추가.
- **11–13행**: snapshot 원래 provider 분류·unknown 미추정, 제출 검색/페이지 scope, 분석 run/snapshot identity
  및 지연/실패 전환 회귀 근거를 추가할 수 있음.
- **21행**: 모든 후보에 대한 25건 작업 페이지/검색과 실제 26번째 이전 후보의 kill 상태 취소+current GET 근거 추가.

이 round에 미해결로 남겨 둔 I1–I4/M1 기능 항목은 없다. 최종 독립 whole-branch review·원격 CI·PR/merge와
기존 Task 3 minor triage는 여전히 controller 담당이다. 새 worktree/branch/subagent·push/merge는 수행하지 않았다.

---

## Scoped review 수정 2/5 — R1 / I2 잔여, 기준 `ea5ab26`

**DONE** — 미완성 분기를 사이에 둔 다중 편집 손실을 수정했다.
구현 커밋: **`37ee40a`** (`fix(web): preserve cross-branch edits while imported forms are incomplete`).
이 절은 1회차의 I2 완료 판단 중 다중 분기 미완성 복구 경계를 보완한다.

### 실제 RED → GREEN

- 수정 전에 `apps/web/lib/strategy-form.test.ts`의 신규 **19개가 모두 실패**했다. 최초 재현은
  fixed_notional `500.00000001`/손절 `3`을 import → 금액 비움 → 손절 `9`·요일 수정 → 금액
  `600.00000001` 복구 후 `formError`는 없지만 실행 정의 손절은 `3`인 경우다.
- 같은 버그를 production build+실제 API/engine에서 **390/1440 모두 실패**시켰다. 브라우저에서 입력한
  `9` 대신 실제 simulation report의 `request.strategy.risk.stop_loss.value`가 `3`이었다.
  UI 문구만 검사한 RED가 아니다.
- `updateDraftSetting`은 이제 **현재 편집 분기가 유효하면 그 분기만 먼저 JSON에 반영**하고, 그 뒤
  전체 sizing/risk 검증으로 실행 가능 여부를 판단한다. 다른 분기가 미완성이면 오류는 유지하지만
  이미 유효한 다른 분기 편집을 버리지 않는다. 현재 분기 자체가 무효면 해당 분기의 이전 JSON은 유지하되
  전체 실행·저장·실험은 차단한다. 유효하게 복구할 때 그 분기의 현재 필드 전체가 반영된다.
- 전체 import를 template/폼에서 재생성하지 않았다. 미편집 entry/중첩 AST·order·다른 risk/session과
  `12.000000000001` 등의 원래 Decimal 문자열을 그대로 보존한다. 기존 % 모드의 무효·미사용 ATR 기간
  처리와 정확한 %↔비율 문자열 변환도 이전 회귀를 그대로 통과했다.

### 신규 회귀 범위

- unit 19개: sizing 미완성 중 손절·요일 수정, take-profit/trailing/최대 보유 기간/각 session clock 분기,
  그리고 **손절/익절/추적 손절 미완성 × 네 가지 sizing** 12개 조합의 역순 편집·복구를 검사한다.
  미완성 중 getter 차단, 복구 후 `buildStrategy`(save) / `buildRequest.strategy`(run·experiment) /
  현재 JSON의 일치와 미편집 AST·다른 분기 보존을 확인한다.
- `tests/e2e/task4-round2.spec.ts`의 단일 흐름을 390/1440에서 실행한다:
  1. 금액 미완성 → 손절 `9`·요일 편집 → 실행 요청 자체 차단 → 금액 `600.00000001` 복구 → 실제 엔진
     요청/응답 손절 `9`·수정 요일 확인.
  2. 손절 미완성 → 금액 `700.00000001`·진입 `09:45` 편집 → 차단 → 손절 `8` 복구 → 실제 엔진의
     금액/손절/session 일치 확인.
  3. 같은 현재 정의로 실제 strategy save와 grid를 실행한다. GUI 필드·원본 JSON·POST body·정규화된
     simulation request·저장 definition·experiment base가 일치하고 grid 실제 두 행 모두 succeeded다.
     손익 계산을 테스트나 브라우저에서 복제하지 않는다.

### 최종 검증

| 명령 | 실제 결과 |
| --- | --- |
| `uv run ruff check .` / `uv run ruff format --check .` | 통과 / 133 files |
| `uv run mypy .` | 133 source files, 통과 |
| `uv run pytest` | **343 passed**, 18.63s |
| `pnpm lint` / `pnpm typecheck` | 53 files, diagnostic 없음 / 통과 |
| `pnpm test` | **6 files / 52 passed** = 이전 33 + 신규 19 |
| `pnpm build` | production build 통과 |
| `CI=1 pnpm exec playwright test` | **54 passed**, 약 1.4m = 이전 52 + 신규 viewport 2 |
| `git diff --check` | 통과 |

실제 Chromium 390/1440의 `ROUND2_LAYOUT`은 각각 `width=scrollWidth=390`, `1440`이다.
`multi-branch-repaired.png`를 두 화면에서 읽었으며 실제 합성 엔진 결과·가격과 equity 구분·한계 표시를
유지한다. 기존 분석 회귀에서도 SVG 실제 16px/bounds, 표 14px·25행·내부 스크롤과 오류 focus가 유지됐다.

프로덕션 변경은 `apps/web/lib/strategy-form.ts`의 작은 분기 반영/검증 순서 변경뿐이다. controller의
`docs/feature-matrix.md` 및 병행 변경으로 나타난 `docs/superpowers/plans/2026-10-16-functional-research.md`는
수정·stage하지 않았다. 소유한 reference matrix에만 분기 보존 규칙을 덧붙였다. backend·paper·execution·
기존 Minor는 건드리지 않았으며, 새 worktree/agent·push/merge는 없다.
