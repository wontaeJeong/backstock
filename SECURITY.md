# Security

## Secret

API key, broker app secret, token, 계좌번호, DB password를 커밋하지 않는다. 개발은 `.env`, 운영은 secret manager를 사용한다.

## Broker

paper/production credential과 endpoint를 분리하고 최소 권한, 마스킹, rotation을 적용한다.

## 실주문 보호

기본 off, feature flag, production credential, approval, risk limit, idempotency, kill switch, reconciliation, audit, alert.

## API

typed validation, body size와 rate limit, authz, 제한된 CORS, pagination upper bound, file type/size 검사, path traversal와 CSV formula injection 방지.

## DSL

임의 코드 금지, operator allowlist, expression depth/lookback/universe limit, timeout과 cancellation.

## Upload

MIME/schema 검사, 압축 폭탄 방지, 안전한 임시 경로, 사용자 파일명을 path로 직접 사용하지 않음.

## MCP

tool scope, 서버 정책, approval identity, prompt injection 방어, redaction, 실주문 tool 기본 미등록.

## Logging

Authorization, token, secret, 전체 계좌번호, 개인정보, 업로드 원문 전체를 기록하지 않는다.

## Dependency

lockfile, vulnerability scan, 최소 이미지, non-root, 불필요한 포트 미노출.

## 사고 대응

kill switch, token revoke, key rotation, audit export, read-only mode.
