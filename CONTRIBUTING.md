# Contributing

## 절차

1. 기준 문서와 ADR을 읽는다.
2. 작은 범위 branch를 만든다.
3. 재현 test 또는 fixture를 만든다.
4. 구현과 문서를 함께 수정한다.
5. lint, typecheck, tests를 실행한다.
6. 정확성·보안 영향을 PR에 적는다.

## Commit 예

```text
feat(data): add yfinance daily bars provider
fix(backtest): prevent same-close execution
test(risk): add insufficient-cash invariant
docs(adr): record adjusted-price policy
```

## PR 체크

문제·범위, 설계, 테스트, migration, API 변경, 데이터 호환성, 정확성 영향, 실주문 영향, 제한, UI/API 예시.

## Review 우선순위

미래 데이터 → 원장 불일치 → 중복 주문 → secret → lineage → schema drift → 테스트 → 성능 → 스타일.
