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
