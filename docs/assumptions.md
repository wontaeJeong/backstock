# Assumptions

구현 중 선택한 가정을 기록한다. 변경 시 날짜, 이유, 영향 범위를 남긴다.

## 초기 가정

- MVP interval은 일봉이다.
- MVP position은 롱 중심이다.
- 종가 신호의 기본 체결은 다음 거래일 시가다.
- intrabar 모호성은 conservative 정책을 사용한다.
- yfinance는 개발 기본 공급자다.
- LocalFileProvider는 fixture와 재현성의 기준이다.
- PostgreSQL이 기본 DB다.
- 전략은 JSON DSL이며 임의 Python을 실행하지 않는다.
- 실제 주문은 기본 비활성화한다.
- KIS는 모의투자부터 연결한다.
- MCP는 조회와 백테스트부터 제공한다.

## 2026-07-16 저장소 진단

- Python 패키지 관리는 `uv`, 웹 패키지 관리는 `pnpm`을 사용한다. 저장소 규칙의 검증 명령과 맞추기 위한 선택이다.
- PostgreSQL은 운영 목표 DB지만 초기 domain·fixture 테스트는 외부 DB 없이 실행 가능해야 한다.
- 대규모 시계열은 Parquet를 목표로 하되, bootstrap 단계의 smoke path는 작은 고정 fixture를 사용한다.
- job queue 제품 선택 전에는 application port로 경계를 만들고 worker 구현이 특정 queue SDK에 의존하지 않게 한다.

## 변경 템플릿

```text
Date:
Decision:
Reason:
Affected modules:
Migration:
Validation:
```
