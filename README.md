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
- mock/paper broker
- KIS 및 MCP 확장 경계

## 빠른 시작 목표

구현 완료 후 실제 명령으로 검증하고 갱신한다.

```bash
cp .env.example .env
docker compose up --build
```

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
