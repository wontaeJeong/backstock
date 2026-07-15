# Current State

진단일: 2026-07-16

## 현재 구현

- Git 저장소와 단일 `README.md` 초기 커밋만 존재한다.
- 제품, 아키텍처, 정확성, 데이터 공급자, DSL, broker, MCP, 보안 기준 문서와 단계별 작업 프롬프트가 작성되어 있다.
- 실행 가능한 Python/TypeScript 소스, 패키지 manifest, 테스트, CI, Docker, 데이터베이스 migration은 없다.
- `.env.example`은 목표 설정 경계를 설명하지만 아직 이를 읽는 애플리케이션은 없다.

## 재사용 가능 요소

- `PRD.md`의 기능·비기능 요구사항과 성공 기준
- `ARCHITECTURE.md`의 의존 방향과 adapter 경계
- 정확성, provider, DSL, broker, MCP, security 문서의 계약
- `docs/adr/`의 제품 범위, 이벤트 엔진, immutable snapshot, JSON DSL, 주문 안전 결정
- `docs/reference/`의 데이터 모델, 지표, API, 테스트 계획

## 누락 기능

- Python workspace, FastAPI API, worker와 공통 domain/application package
- Next.js 웹 애플리케이션과 API client
- PostgreSQL schema와 migration
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
