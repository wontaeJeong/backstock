# Operations Runbook

## Provider 장애
health/rate limit 확인, 기존 snapshot 사용 가능 여부 확인, 자동 provider 변경 금지, 사용자에게 장애 표시.

## Worker 장애
job heartbeat와 중복 실행 방지 확인, 안전한 재시도 판단, partial result를 성공으로 표시하지 않음.

## Broker 불일치
신규 주문 차단, reconciliation 실행, unknown 주문 재전송 금지, 필요 시 kill switch.

## Credential 노출
token revoke, key rotation, 로그·artifact 범위 확인, 주문·접근 audit.

## 백업
PostgreSQL, manifests, strategy versions, run configs/results, audit logs, snapshot storage.

## 복구 검증
빈 환경 restore, checksum, migration, 대표 backtest 재현.
