# 개발환경·검증·컨테이너 배포 준비

## 지원 환경

Python 3.12, Node 24, pnpm 11.1.2. Python과 JS 의존성은 frozen lockfile로 설치한다.
Node 25를 설치한 호스트에서도 이 프로젝트는 버전 관리 도구로 24를 선택한다.
Docker Compose는 별도 테스트 project 이름을 사용하면 기존 스택과 볼륨을 건드리지 않는다.

```bash
uv sync --frozen
pnpm install --frozen-lockfile
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
pnpm lint
pnpm typecheck
pnpm test
pnpm build
pnpm exec playwright install chromium
pnpm exec playwright test
```

Playwright는 독립 포트 29000(API), 23001(Web)을 시작하여 offline 합성 데이터와 파일 업로드를 실제
snapshot/DSL/engine으로 처리한다. 다른 서버를 임의 재사용하지 않는다. 390px·1440px에서 결과 위치,
실제 SVG 표시 글자 크기, 문서 길이, 키보드 접기, 오류/JSON export를 확인한다.
Yahoo 네트워크 smoke는 offline CI에 포함하지 않으며 외부 공급자 가용성의 영구 보장은 아니다.

## CI

- backend: Ruff/format/mypy/pytest, offline migration SQL, 실제 PostgreSQL 17 migration,
  exclusion/FK/check 제약 검사, downgrade/re-upgrade, Python wheel build.
- frontend: lint/type/unit/production build.
- e2e: 실제 API와 production Next.js를 실행한 Chromium 데스크톱/모바일. 실패 trace·스크린샷은 7일 보관.
- compose: 모든 이미지 build, migration 이후 stack 시작, web→API health 확인, 실패 시 제한된 로그,
  CI가 만든 disposable volume만 종료 후 삭제.

`tests/database_check.py`는 기본 DB를 자동 선택하지 않고 명시적인 `DATABASE_URL`을 요구한다.
데이터 변경은 transaction에서 rollback한다. migration downgrade는 disposable CI DB에서만 실행한다.
readiness는 filesystem에 실제 쓰기 probe를 실행한다. 현재 연구 실행이 사용하지 않는 DB나
미구현 worker job queue까지 준비되었다고 표시하지 않는다.

## CD 범위

실제 배포 대상·도메인·인증·운영 secret이 정해지지 않아 자동 서비스 배포는 제공하지 않는다.
`Container artifacts (manual)`은 main에서만 수동 실행하며, 기본값은 publish=false다.
publish를 명시적으로 선택하면 GHCR에 commit SHA-tag 이미지와 provenance/SBOM을 발행한다.
GitHub의 `container-release` environment에 required reviewers와 main branch 제한을 설정한 뒤 사용한다.
이 환경의 승인 정책은 저장소 관리자가 설정해야 하며 workflow YAML만으로 자동 설정되지 않는다.
별도 승인 없이 이 세션에서 workflow를 실행하거나 이미지를 발행하지 않는다.

API/worker runtime은 non-root, 웹은 production standalone 빌드다. `.env`와 로컬 artifact를 build
context에서 제외한다. 이미지 base tag는 고정 digest가 아니므로 장기 보관/공개 운영 전 supply-chain
정책과 취약점 검사, 인증·rate limit·스토리지 quota·백업을 추가해야 한다.

## 연구 MVP 제한

- 단일 USD 종목, 일봉 Yahoo 또는 명시적 로컬 파일. 나스닥 전체 과거 universe가 아니다.
- 3,000 bar, 계산 15초 cooperative 제한. provider I/O와 단일 bar 내부 계산의 강제 종료는 아니다.
- 전략·설정·결과는 immutable filesystem JSON, 데이터는 checksum Parquet snapshot이다.
  비동기 job, DB run/strategy CRUD, 사용자 계정/권한은 미구현이다.
- bar 기반 시장가/지정가·정수 수량·롱·전량 체결. 호가·실제 latency·부분 체결·공매도는 미검증이다.
- 일봉/분봉 결과를 틱 기반 초단타 실전 유효성으로 해석할 수 없다.
- 미청산 자산 평가손익 포함, raw 분할/배당 원장 미구현, 보정 가격은 point-in-time 가격이 아니다.
- 비교 기준은 같은 종목의 비용 없는 가격 비율이다. QQQ 데이터를 별도로 수집한 비교가 아니다.
