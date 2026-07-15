# 2단계 — 프로젝트 부트스트랩과 아키텍처

`00_GLOBAL_RULES.md`와 기준 문서를 적용한다.

기존 구조가 없으면 아래 책임 경계를 갖는 모노레포를 만든다.

```text
apps/api
apps/web
apps/worker
apps/mcp
packages/domain
packages/application
packages/market_data
packages/strategy
packages/backtest
packages/risk
packages/broker
packages/shared
infra
docs
```

## 작업

1. Python 3.12 + `uv`, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic을 설정한다.
2. Next.js + TypeScript + `pnpm`을 설정한다.
3. PostgreSQL을 기본 DB로 구성한다.
4. Docker Compose로 API, Web, Worker, DB를 실행한다.
5. `/health/live`, `/health/ready`를 구현한다.
6. 공통 오류 응답 `code/message/details/request_id`를 정의한다.
7. correlation id와 구조화 로그를 적용한다.
8. typed settings와 `.env.example`을 만든다.
9. ruff, mypy, pytest, eslint, typecheck, frontend test를 구성한다.
10. 초기 migration을 만든다.
11. 도메인 계층이 FastAPI, Next.js, SQLAlchemy에 직접 의존하지 않게 한다.
12. `ARCHITECTURE.md`와 ADR을 구현에 맞게 갱신한다.

## 완료 조건

- 한 명령으로 로컬 환경을 실행한다.
- 외부 서비스 없이 smoke test가 통과한다.
- 의존 방향이 문서와 일치한다.
