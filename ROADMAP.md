# Roadmap

1. **완료 — 기준 문서와 진단**: PRD, ADR, 위험, 가정, 저장소 현황
2. **완료 — 개발 기반**: Python/Next.js, API/Web/Worker/DB, Compose, CI
3. **다음 — 시장 데이터**: YFinance/Local provider, symbol, 품질, snapshot
4. **백테스트 엔진**: event clock, order/fill, ledger, 비용, golden tests
5. **전략 DSL**: schema, indicator, entry/exit, sizing, version
6. **웹 MVP**: 데이터, 전략, 실행, 결과, E2E
7. **분석**: 성과·위험, benchmark, 비교, 비용 민감도
8. **Paper Broker**: approval, idempotency, reconciliation, audit
9. **외부 연동**: KIS 모의투자, MCP 조회·백테스트 tool
10. **운영 준비**: backup, observability, RBAC, secrets, Kubernetes/GitOps
11. **고급 연구**: 분봉, walk-forward, parameter sweep, point-in-time universe, 공매도

우선순위는 정확성 → 재현성 → 실주문 안전 → UX → 성능 → 기능 범위다.

각 단계는 해당 `prompts/` 문서의 완료 조건과 검증 명령을 통과한 뒤 완료로 표시한다.
