# ADR-0006: Python 중심 서비스와 Next.js 웹 모노레포

- Status: Accepted
- Date: 2026-07-16

## Context

백테스트·데이터·브로커 규칙은 한 언어의 엄격한 타입과 Decimal 모델을 공유해야 하고, 웹은 서버 렌더링과 접근성 있는 React 생태계가 필요하다.

## Decision

Python 3.12와 `uv`가 API, worker, MCP, domain/application package를 관리하고 Next.js와 `pnpm`이 `apps/web`을 관리한다. Python 모듈은 `apps -> packages/application -> packages/domain` 방향을 따르며 외부 시스템은 package interface 뒤의 adapter로 둔다.

PostgreSQL migration은 Alembic으로 관리한다. 로컬 전체 환경은 Docker Compose가 API, Web, Worker, PostgreSQL을 시작한다.

## Consequences

계산 규칙과 주문 안전 계약을 Python에서 공유하면서 웹 배포를 독립적으로 최적화할 수 있다. 두 toolchain을 CI에서 각각 검증해야 하며, 경계 위반을 architecture test로 차단한다.
