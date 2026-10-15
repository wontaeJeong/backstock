# Stock Strategy Lab

과거 시장 데이터로 조건주문 전략을 설계·백테스트하고 주문·체결·포트폴리오 변화를 분석하는 웹 애플리케이션이다.

초기 버전은 연구 및 paper trading을 제공한다. 실제 주문은 기본 비활성화하며 한국투자증권 OpenAPI와 MCP는 격리된 어댑터로 추가한다.

## 핵심 기능

- Yahoo Finance 기반 과거 시세 조회
- CSV/Parquet 업로드
- 데이터 품질 검증과 immutable snapshot
- JSON 조건주문 DSL
- 이벤트 기반 주문·체결 백테스트
- 수수료·세금·슬리피지
- 전략 버전 관리
- 성과·위험 분석 및 실행 비교
- 한국어 조건 편집·템플릿과 원금 대비 순손익·최대 낙폭·거래 근거
- 최근 Yahoo 1m/5m, 파일 raw tick/quote 재생, spread·latency·전량 거래량 상한 시나리오
- 서버 보관함 검색·25건 페이지·보관/복원, 손실 없는 전략 JSON 가져오기·복제·버전 저장
- 서버 통계·월별/청산 lot·가격 replay·CSV·별도 QQQ snapshot·지속 실행 비교
- 고정 snapshot grid/비용 민감도, 순차 walk-forward, 독립 고정 예산 포트폴리오·서버 요약
- 승인·거절·취소·수동 가격 평가·kill switch·내부 대사를 제공하는 오프라인 paper 연습

현재는 로컬 연구 MVP다. 실시간 feed·거래소 queue·부분 체결·PIT universe·corporate-action 원장,
KIS/MCP 실거래 통합·다중 사용자 인증·비동기 job queue·분산 운영은 미구현이다.
실제 주문은 하지 않는다. 합성 데모는 실제 나스닥 시세가 아니며 결과 화면에서 구분한다.

## 빠른 시작

```bash
cp .env.example .env
docker compose up --build
```

API는 `http://localhost:8000`, Web은 `http://localhost:3000`에서 실행된다. 확인:

```bash
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready
```

포트는 localhost에만 바인딩한다. 이미 사용 중이면 `API_PORT=28000 WEB_PORT=23000 docker compose up --build`처럼
변경한다. migration이 성공한 후 API/worker를 시작하며 snapshot과 실행 결과는 `research-data` volume에 남는다.
`down --volumes`는 데이터를 지우므로 일반 종료는 `docker compose down`을 사용한다.

### 처음 사용하기

1. 현재 curated 종목과 원금(USD)을 선택한다. Yahoo는 일봉과 최근 1m(7일)/5m(60일)만 지원한다.
2. 한국어 폼에서 지표·기간·비교 조건을 바꾼다. 매수·매도 각각 최대 4개 조건을 결합할 수 있다.
3. 수수료·매도세·슬리피지를 확인하고 실행한다. 1 bps = 0.01%, 기본값은 예시다.
4. 순수익·원금 대비 수익률·최대 낙폭·거래 근거를 확인한다. 비용을 높여 재실행하면 최근 5개 결과를 비교한다.
5. **보관함**에서 전략·데이터·실행을 검색하고 재사용한다. **상세 분석**, **실험**, **Paper 연습**으로 이동한다.

중첩 조건·fixed quantity/notional·ATR sizing·trailing/ATR risk·요일은 **전략 JSON 편집**을 사용한다.
고급 JSON 모드에서는 간편 전략 폼을 비활성화하며 전체 AST가 실행·저장·실험의 기준이다. 원금과 실행 비용은
별도 설정이다. 서버 검증을 사용하며 JSON 내보내기로 전체 원본을 보존할 수 있다.
Paper는 수동 과거 가격만 사용한다. 후보 생성은 현금을 바꾸지 않고 승인 때만 연습 체결한다.
생성 요청은 자동 재시도하지 않으며, 나머지 동일 키 재시도 뒤에도 현재 GET 계좌를 다시 읽는다.

네트워크 없이 체험하려면 **합성 데모로 실행**을 누른다. 실제 시세 조회 실패를 데모 성공으로 바꾸지 않는다.
분봉 연구는 CSV/Parquet 파일을 업로드한다. timestamp는 bar 종료 시각과 UTC offset을 포함해야 한다.
예: `2024-01-02T09:31:00-05:00`은 09:30~09:31의 1분 bar다. 형식 예시는 UI에서 받을 수 있으며 **합성**이다.
분봉도 다음 bar 체결의 근사이며 초단타 실전 수익성 검증은 아니다. 선택적 세션 청산은 close에서 신호를
만들고 다음 이벤트에만 체결하므로 미청산될 수 있다. tick은 `timestamp,price,size`와 선택적 `bid,ask` 쌍이다.

정확한 구현·검증 범위와 제외 항목은 [기능 매트릭스](docs/reference/research-feature-matrix.md),
서버 계약은 [연구 API](docs/reference/research-features-api.md)를 참조한다.

### 호스트 개발

`.node-version`/`.nvmrc`의 Node 24와 Python 3.12를 사용한다. `.env.example`의 호스트 DB URL은
`postgresql+asyncpg://...@localhost:5432/...`이며 Compose 안에서는 자동으로 `db` hostname을 사용한다.
Compose DB 포트는 외부에 노출하지 않는다. 호스트에서 DB migration을 실행하려면 별도 개발 DB를 준비한다.
bounded simulation API 자체는 filesystem 저장소를 사용하므로 호스트 API/웹 개발에 DB 연결이 필요하지 않다.

```bash
uv sync --frozen
pnpm install --frozen-lockfile
uv run uvicorn apps.api.app:app --reload --host 127.0.0.1 --port 8000
# 다른 터미널
API_INTERNAL_URL=http://127.0.0.1:8000 pnpm dev
```

호스트에서 검증하려면 Python 3.12, `uv`, Node.js 24, `pnpm` 11이 필요하다.

```bash
uv sync
pnpm install
uv run pytest
pnpm test
pnpm exec playwright install chromium
pnpm exec playwright test
```

전체 검증·운영 제한은 [개발환경과 CI/CD](docs/development.md)를 참조한다.

## 데이터 주의

개발 기본값은 `yfinance`지만 Yahoo와 제휴된 공식 SDK가 아니다. 공급자, 옵션, 버전, 원본 checksum을 실행 이력에 저장하고 실거래 판단 전 별도 데이터로 교차 검증한다.

## 기준 문서

- [PRD](PRD.md)
- [Agent 규칙](AGENTS.md)
- [Architecture](ARCHITECTURE.md)
- [Roadmap](ROADMAP.md)
- [Data Providers](DATA_PROVIDERS.md)
- [Backtesting Accuracy](BACKTESTING_ACCURACY.md)
- [Strategy DSL](STRATEGY_DSL.md)
- [Broker Integration](BROKER_INTEGRATION.md)
- [MCP Integration](MCP_INTEGRATION.md)
- [Security](SECURITY.md)
