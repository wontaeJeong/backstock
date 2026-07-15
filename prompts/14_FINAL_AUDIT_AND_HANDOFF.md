# 14단계 — 최종 감사와 인수인계

`00_GLOBAL_RULES.md`와 전체 문서를 적용한다.

## 검증 흐름

1. 새 환경에서 Docker Compose 시작
2. Yahoo Finance 또는 offline fixture 데이터 수집
3. 데이터 검증과 snapshot
4. 템플릿 전략 생성
5. 백테스트 실행
6. 결과·주문·체결 조회
7. 두 실행 비교
8. paper 주문 생성·승인·체결
9. MCP 실행·조회
10. 네트워크 없는 fixture demo

## 감사

- 전체 lint/type/unit/integration/E2E/benchmark
- 빈 DB migration과 upgrade
- secret/dependency scan
- 로그 민감정보
- 실주문 flag 기본 off
- look-ahead 방지
- raw/adjusted 혼용
- provider silent fallback
- snapshot과 재현성 metadata
- 지표 독립 계산
- worker 재시작과 cancellation
- 성능·메모리 한계

## 결과

1. 확실한 결함은 직접 수정한다.
2. 큰 미해결 항목은 severity, 영향, 재현법, 권장 조치를 기록한다.
3. `docs/validation-report.md`, developer guide, operations runbook을 갱신한다.
4. README quick start를 새 환경에서 검증한다.
5. ROADMAP을 실제 남은 작업으로 갱신한다.

## 완료 조건

- 새 개발자가 문서만 보고 실행한다.
- fixture 전체 demo가 재현된다.
- 실패 검증을 숨기지 않는다.
- 실주문이 안전하게 비활성화되어 있다.
