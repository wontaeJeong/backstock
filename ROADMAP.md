# Roadmap

1. **완료 — 기준 문서와 진단**: PRD, ADR, 위험, 가정, 저장소 현황
2. **완료 — 개발 기반**: Python/Next.js, API/Web/Worker/DB, Compose, CI
3. **완료 — 시장 데이터**: YFinance/Local provider, symbol, 품질, snapshot
4. **완료 — 백테스트 엔진**: event clock, order/fill, Decimal ledger, 비용, golden/property/no-future tests
5. **완료 — 전략 DSL**: schema, indicator, entry/exit/risk/sizing/order, canonical hash version,
   validation/metadata API, 템플릿 4종
6. **구현 — 로컬 웹 MVP**: 나스닥 Yahoo 일봉/파일·분봉, 한국어 전략 편집, bounded 동기 실행,
   immutable run 조회·JSON export, 실제 API/engine을 호출하는 offline E2E
7. **일부 구현 — 분석**: 원금 대비 순수익·수익률·최대 낙폭·동일 종목 단순보유·최근 실행 비교.
   비용을 바꿔 재실행할 수 있으며 Sharpe/Sortino·자동 민감도 sweep·비동기 job/DB 영속화는 후속
8. **Paper Broker**: approval, idempotency, reconciliation, audit
9. **외부 연동**: KIS 모의투자, MCP 조회·백테스트 tool
10. **운영 준비**: backup, observability, RBAC, secrets, Kubernetes/GitOps
11. **고급 연구**: 분봉, walk-forward, parameter sweep, point-in-time universe, 공매도

우선순위는 정확성 → 재현성 → 실주문 안전 → UX → 성능 → 기능 범위다.

각 단계는 해당 `prompts/` 문서의 완료 조건과 검증 명령을 통과한 뒤 완료로 표시한다.
