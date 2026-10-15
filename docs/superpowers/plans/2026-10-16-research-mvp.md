# Research MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 비개발자가 나스닥 매매 규칙을 편집하고 과거 데이터 시뮬레이션의 순수익·위험을 확인한다.

**Architecture:** 기존 provider/snapshot → application simulation service → 순수 DSL/engine → immutable run artifact를 API가 노출한다. 웹은 한국어 편집기와 결과 뷰이며 금융 계산은 서버에 둔다.

**Tech Stack:** Python 3.12 / uv / FastAPI / Pydantic / Decimal / Polars, Next.js 16 / React 19 / TypeScript / Zod, Playwright, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-10-16-research-mvp-design.md`

## Global Constraints
- Python 3.12, Node 24, pnpm 11.1.2, frozen lockfiles.
- 한국어 UI, USD, 미래 참조 및 silent provider fallback 금지.
- 분봉 결과는 초단타 실전 검증으로 표시하지 않는다.
- 390px/1440px 실제 브라우저, offline fixture E2E.
- 실제 주문·공개 운영 배포 제외, 비용 0도 명시.

## Review Focus
- 빈 데이터/과도한 요청: 명시적 오류, 대체 데이터로 성공시키지 않음 (Task 2).
- 전략 timeframe/universe와 snapshot 불일치: 실행 전 거부 (Task 2).
- 분봉 시가 timestamp와 종가 신호: 다음 bar 체결, DAY는 다음 bar가 아닌 거래일 경계 (Task 2).
- 결과가 이전 설정과 혼동됨: 입력 변경 시 이전 결과 표시/명시적 실행 기준 고정 (Task 3).
- 실패/오프라인/모바일: 입력 보존, 재시도, 키보드 접근과 실제 읽기 크기 (Task 4).

### Task 1: 개발환경·CI/CD 기반
**Files:** `.github/workflows/*`, `package.json`, `apps/web/package.json`, `docker-compose.yml`, `infra/*`, `docs/*`, `.node-version`.
**Interfaces:** 기존 실행 명령 유지; E2E는 root `pnpm exec playwright test` 사용.
- [x] 기존 Python/프런트엔드 baseline 테스트, frozen 설치, 환경 차이 조사.
- [ ] CI에 실제 DB migration과 offline E2E를 연결하고 컨테이너 검증/수동 발행을 추가한다.
- [ ] 환경 명령과 Compose 검증, 관련 workflow 설정을 검토하고 커밋한다.

### Task 2: 재현 가능한 simulation API와 분봉 계약
**Files:** `packages/application/simulations.py`, `packages/backtest/analytics.py`, `packages/market_data/*`, `packages/strategy/schema.py`, `apps/api/simulations.py`, `tests/application/test_simulations.py`, `tests/api/test_simulations.py`, `tests/backtest/*`.
**Interfaces:** `SimulationService.run(request)`는 검증된 snapshot과 DSL로 엔진을 호출하고 run id/summary/metrics/portfolio/orders/fills/warnings를 반환한다. `/simulations` POST와 `/simulations/{run_id}` GET, catalog와 명시적 synthetic demo를 제공한다.
- [ ] 손계산 순수익·낙폭, snapshot mismatch, 불변 저장/재현성, 오류에 대한 실패 테스트를 작성·실행한다.
- [ ] snapshot bar 로딩, 실제 Yahoo 수집과 업로드 snapshot 실행, bounded 동기 API와 지표를 구현한다.
- [ ] 1m/5m 계약과 세션 경계·다음 bar 체결 회귀 테스트를 먼저 작성한 뒤 구현한다.
- [ ] golden/property/no-future/cost 및 provider fixture 검증 후 커밋한다.

### Task 3: 비개발자용 연구 워크스페이스
**Files:** `apps/web/components/research/*`, `apps/web/lib/*`, `apps/web/app/api/research/*`, `apps/web/app/page.tsx`, `apps/web/app/styles/research.css`, 관련 unit tests.
**Interfaces:** Zod 기반 simulation 응답, editable rule form → DSL serializer, 서버 proxy → FastAPI. 금융 지표 재계산 금지.
- [ ] serializer와 입력/결과 상태의 실패 테스트를 작성·실행한다.
- [ ] 한국어 데이터 선택/업로드·조건 편집·비용·실행 UI와 오류 상태를 구현한다.
- [ ] 결과 상단 수익/제한, 지표 카드, 실제 시점 자산 그래프, 상세 거래/재현성/export와 비교를 구현한다.
- [ ] lint/type/unit/build 검증 후 커밋한다.

### Task 4: end-to-end 검증과 문서
**Files:** `playwright.config.ts`, `tests/e2e/*`, `README.md`, `ROADMAP.md`, `PRD.md`, `ARCHITECTURE.md`, `BACKTESTING_ACCURACY.md`, `DATA_PROVIDERS.md`, `STRATEGY_DSL.md`.
- [ ] 실제 API·engine을 호출하는 offline demo E2E, 입력 변경/오류/업로드/단기 실험을 검증한다.
- [ ] 모바일/데스크톱 스크린샷과 표시 글자·그래프·표·키보드·문서 길이를 측정한다.
- [ ] 전체 필수 검증을 실행하고 미지원 기능·실제 provider 가용성·CD 한계를 문서화한다.
- [ ] 독립 리뷰와 회귀 검증 후 커밋·푸시·새 PR을 만들고 머지는 별도 승인을 받는다.
