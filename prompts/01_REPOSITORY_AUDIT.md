# 1단계 — 저장소 진단과 문서 정합성

`00_GLOBAL_RULES.md`를 적용한다.

현재 저장소를 조사하고 기준 문서가 실제 코드와 맞도록 정리한다. 아직 대규모 구현은 시작하지 않는다.

## 작업

1. 디렉터리, 언어, 패키지 관리자, 테스트, CI, Docker, DB 설정을 조사한다.
2. 기존 데이터·백테스트·주문 코드의 재사용 가능성과 문제를 평가한다.
3. `PRD.md`, `AGENTS.md`, `ARCHITECTURE.md`, `ROADMAP.md`를 저장소 현실에 맞게 수정한다.
4. `docs/current-state.md`를 작성한다.
   - 현재 구현
   - 재사용 요소
   - 누락 기능
   - 기술 부채
   - 보안·정확성 위험
   - 다음 단계 진입 조건
5. `docs/assumptions.md`에 선택한 기본값을 기록한다.
6. 용어를 통일한다: DatasetSnapshot, StrategyVersion, Signal, OrderIntent, Order, Fill, Position, Portfolio, BacktestRun.
7. 상충되는 결정은 ADR로 기록한다.
8. MVP는 일봉, 롱 중심, 단일·다중 종목, DSL, 비용·슬리피지, 웹 UI로 고정한다.
9. 분봉, 공매도, ML, 자동 실주문은 후속 범위로 둔다.

## 완료 조건

- 문서와 저장소 상태가 일치한다.
- MVP와 제외 범위가 명확하다.
- 다음 단계 구조가 구체적이다.
