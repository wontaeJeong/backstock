# 12단계 — 한국투자증권 OpenAPI 어댑터

`00_GLOBAL_RULES.md`와 이전 구현을 적용한다.

공식 API 문서와 credential이 없는 부분은 추측 구현하지 않는다. 실제 endpoint 호출 대신 adapter boundary와 fake contract test를 완성한다.

## 작업

1. `KisBrokerAdapter` 패키지를 만든다.
2. HTTP, auth, account, quote, order client를 분리한다.
3. 모의투자와 실전투자 base URL·credential을 완전히 분리한다.
4. 모의투자를 기본값으로 한다.
5. token 발급·만료·cache를 캡슐화한다.
6. 계좌, 포지션, 주문 응답을 내부 표준 모델로 변환한다.
7. 증권사 오류 코드와 내부 오류를 매핑한다.
8. rate limit과 제한된 retry를 구현한다.
9. 주문 조회와 reconciliation을 먼저 구현한다.
10. 주문 전송은 fake server contract test로 검증한다.
11. 계좌번호와 token을 마스킹한다.
12. kill switch와 일일 주문 상한을 설계한다.

## 실주문 활성화 조건

- 공식 명세 contract 검증
- 모의투자 E2E
- 수동 승인
- 주문 상한
- kill switch
- audit log
- credential 격리
- reconciliation
- 운영 runbook
- 사용자 명시적 활성화

## 완료 조건

- production credential 없이 앱이 정상 동작한다.
- 실주문은 기본적으로 절대 활성화되지 않는다.
