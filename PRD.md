# PRD — Stock Strategy Lab

## 1. 제품 개요

Stock Strategy Lab은 과거 주식 데이터로 프로그램 매매의 진입·청산·리스크·조건주문 규칙을 검증하는 웹 앱이다.

현재 저장소는 1단계 문서 기준선만 존재하며 실행 가능한 애플리케이션, 패키지, 데이터베이스, 테스트, CI는 아직 없다. 아래 요구사항은 2단계 이후 구현 목표다.

사용자는 종목, 기간, 데이터 snapshot, 전략 버전, 비용, 체결 가정을 선택해 백테스트를 실행한다. 시스템은 수익률뿐 아니라 주문 후보, 체결, 현금, 포지션, 비용, 낙폭을 재현 가능한 형태로 제공한다.

초기 목적은 연구와 paper trading이다. 실제 주문은 후속 단계에서 한국투자증권 OpenAPI 또는 MCP/주문 서비스로 연결한다.

## 2. 문제

- 조건주문 아이디어를 반복 검증하기 어렵다.
- 단순 차트 검토는 수수료, 세금, 슬리피지, 미체결을 반영하지 않는다.
- 미래 데이터 참조로 결과가 과대평가될 수 있다.
- 전략과 데이터 버전이 남지 않아 재현이 어렵다.
- 백테스트와 실주문 코드가 결합되면 안전 위험이 커진다.

## 3. 목표

1. 무료 과거 데이터로 빠르게 실험한다.
2. 주문과 체결을 명시적으로 시뮬레이션한다.
3. 데이터·전략·설정 버전을 고정한다.
4. 수익률과 위험·비용을 함께 분석한다.
5. paper trading으로 주문 lifecycle을 검증한다.
6. KIS OpenAPI와 MCP를 안전하게 확장한다.

## 4. 비목표

- 수익 보장 또는 종목 추천
- 틱 기반 고빈도 엔진
- 주문장 완전 재현
- 임의 Python 코드 실행
- 자동 실주문
- 세무·법률 자문
- 기관급 데이터 정확도 보장

## 5. 대상 사용자

- 조건주문과 프로그램 매매 아이디어를 검증하는 개발자·개인 투자자
- 리스크·성과를 검토하는 사용자
- KIS 또는 MCP 연동을 개발하는 엔지니어

## 6. 핵심 흐름

### 데이터
종목·기간·provider 선택 → 데이터 조회 또는 파일 업로드 → 품질 검사 → immutable snapshot

### 전략
템플릿 또는 신규 전략 → 진입·청산·sizing·risk 조건 → validation → immutable version

### 백테스트
전략 버전·snapshot·자본·비용·체결 정책 → 사전 검증 → 실행 → 진행률·경고

### 분석
성과·위험 지표 → equity/drawdown → 주문·체결·포지션 → benchmark → 실행 비교 → export

### Paper trading
OrderIntent → risk check → 주문 후보 → 승인/거절 → paper broker → reconciliation

## 7. MVP 범위

MVP는 일봉, 롱 중심, 단일·다중 종목, JSON DSL, 비용·슬리피지, 웹 UI로 고정한다. 분봉, 공매도, ML, 자동 실주문은 후속 범위다.

### 시장 데이터
- 일봉 OHLCV
- YFinanceProvider
- LocalFileProvider
- 한국·미국 symbol
- corporate action
- adjusted/raw 구분
- 품질 검사
- snapshot과 checksum

### 전략
- JSON DSL
- 폼과 JSON 편집기
- SMA, EMA, RSI, ATR, rolling high/low, volume ratio
- all/any/not
- 시장가, 지정가, stop, stop-limit, 익절, trailing stop
- fixed quantity/notional, equity %, ATR sizing
- immutable version

### 백테스트
- 이벤트 기반 일봉 엔진
- 롱 포지션
- 단일·다중 종목
- 비용·슬리피지
- 주문 상태와 체결
- cash/position ledger
- 결정적 실행과 상세 이벤트

### 분석
- total return, CAGR, volatility
- Sharpe, Sortino, max drawdown
- win rate, profit factor, expectancy
- turnover, exposure, holding period
- equity, drawdown, monthly return
- benchmark와 실행 비교

### 플랫폼
- FastAPI
- Next.js
- PostgreSQL
- Worker
- Docker Compose
- OpenAPI
- unit/integration/E2E tests

## 8. 후속 범위

분봉, 공매도, walk-forward, parameter sweep, KIS 모의투자·실전투자, MCP, RBAC, Kubernetes/GitOps, 유료 데이터.

## 9. 기능 요구사항

- FR-1: provider·종목·기간·interval로 데이터 수집
- FR-2: CSV/Parquet 업로드
- FR-3: 데이터 품질 검사
- FR-4: immutable snapshot 사용
- FR-5: 조건 DSL 작성
- FR-6: immutable 전략 버전
- FR-7: 주문·체결·원장 기반 백테스트
- FR-8: 수수료·세금·슬리피지·체결 정책
- FR-9: 지표·차트·주문·체결·포지션 조회
- FR-10: 여러 실행 비교
- FR-11: 승인 기반 paper order
- FR-12: provider/broker adapter

## 10. 비기능 요구사항

### 정확성
- look-ahead 방지
- 동일 snapshot·설정에서 동일 결과
- 거래 근거 추적
- 금액 오차 제어

### 보안
- secret 미커밋
- broker credential 격리
- 실주문 기본 off
- 승인·주문 감사 로그

### 운영
- health/readiness
- 구조화 로그
- migration
- worker 상태 보존
- offline fixture demo

## 11. 데이터 원칙

- 원격 응답을 raw로 보존한다.
- provider, version, 옵션, 범위, checksum을 기록한다.
- adjusted/raw를 구분한다.
- 자동 fallback으로 데이터가 섞이지 않게 한다.
- 무료 데이터는 연구용으로 취급한다.

## 12. 실주문 안전

- 전략은 OrderIntent만 만든다.
- risk engine과 approval을 거친다.
- idempotency와 reconciliation을 사용한다.
- production은 별도 credential, flag, 상한, kill switch가 필요하다.

## 13. 성공 기준

1. Yahoo 또는 fixture로 snapshot 생성
2. 코드 없이 전략 작성
3. 재현 가능한 백테스트
4. 주문·체결·원장 설명 가능
5. 비용·위험 분석
6. 실행 비교
7. paper lifecycle
8. 실주문 기본 차단
9. 정확성 테스트 CI 통과
10. 문서만으로 로컬 실행

## 14. 위험

무료 API 가용성, survivorship bias, corporate action 오류, intrabar 순서, 슬리피지 과소평가, 거래 정지·가격 제한, timezone, 데이터 라이선스, 과최적화, 백테스트·실거래 차이.

## 15. 마일스톤

- M1: 문서·모노레포·개발 환경
- M2: 데이터 provider·검증·snapshot
- M3: 엔진·원장·golden test
- M4: DSL·웹 MVP
- M5: 지표·비교
- M6: paper broker
- M7: KIS 모의투자·MCP
