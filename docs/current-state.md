# Current State

진단일: 2026-07-16

## 현재 구현

- Python 3.12 `uv` project와 Next.js `pnpm` workspace가 있다.
- FastAPI live/ready health, 공통 error contract, request id, JSON request log가 동작한다.
- Worker entrypoint, PostgreSQL 17 Compose service, 초기 Alembic migration이 있다.
- Web bootstrap과 디자인 시스템 primitive showcase가 있다.
- GitHub Actions가 backend lint/type/test/migration SQL과 frontend lint/type/test/build를 검증한다.

## 재사용 가능 요소

- `PRD.md`의 기능·비기능 요구사항과 성공 기준
- `ARCHITECTURE.md`의 의존 방향과 adapter 경계
- 정확성, provider, DSL, broker, MCP, security 문서의 계약
- `docs/adr/`의 제품 범위, 이벤트 엔진, immutable snapshot, JSON DSL, 주문 안전 결정
- `docs/reference/`의 데이터 모델, 지표, API, 테스트 계획

## 누락 기능

- 실제 market data, strategy, backtest, risk, broker application service
- Web의 typed API client와 제품 화면
- 리소스별 PostgreSQL schema와 repository
- market data provider, 정규화, 품질 검사, immutable snapshot 저장
- strategy DSL, indicator, backtest/risk/broker engine
- analytics, paper approval, KIS adapter, MCP server
- unit/integration/E2E test, CI, Docker Compose와 운영 관측성

## 기술 부채

- 문서에 목표 구조와 현재 구현이 구분되지 않아 기능이 이미 있는 것처럼 읽힐 수 있었다.
- 설치·실행·검증 명령이 실제 project manifest로 뒷받침되지 않는다.
- fixture와 golden 결과가 없어 정확성 기준을 아직 자동 검증할 수 없다.
- persistence, job queue, object storage 선택이 구현으로 검증되지 않았다.

## 정확성·보안 위험

- 현재 계산 코드가 없어 look-ahead, 비용, Decimal 원장, adjusted/raw 정책을 검증할 수 없다.
- provider 원본·manifest·checksum 보존이 구현되지 않아 데이터 lineage가 없다.
- approval, idempotency, kill switch, secret redaction 경계가 문서에만 존재한다.
- 실제 credential은 없으며 `.env.example` 값은 비밀이 아닌 빈 placeholder다.

## 다음 단계 진입 조건

- 목표 모노레포 구조와 Python/TypeScript package manager를 실제 manifest로 고정한다.
- offline fixture로 실행되는 최소 API, worker, web smoke path를 만든다.
- lint, typecheck, unit test, E2E, migration 검증을 CI와 로컬 명령으로 제공한다.
- 모든 외부 서비스는 interface와 adapter 뒤에 두고 기본 실행은 network·broker credential 없이 가능하게 한다.
