# 4단계 — 데이터 품질과 immutable snapshot

`00_GLOBAL_RULES.md`와 이전 구현을 적용한다.

## 검사 항목

- timestamp 중복·정렬
- timezone 누락
- 0 이하 가격
- `low > high`
- open/close가 high-low 범위 밖
- 음수 volume
- 거래일 캘린더 불일치
- 누락 거래일
- 비정상 급등락
- corporate action과 가격 변화 불일치
- 빈 응답과 불완전 범위

## Snapshot manifest

- id
- provider와 version
- query options
- provider/canonical symbol
- interval, date range, timezone
- adjustment mode
- row count
- raw/normalized checksum
- schema version
- validation status와 warnings
- storage URI

## 작업

1. raw, normalized, snapshot 저장 영역을 분리한다.
2. normalized 데이터는 Parquet를 기본으로 한다.
3. snapshot은 생성 후 수정하지 않는다.
4. 갱신은 새 snapshot으로 만든다.
5. BacktestRun은 snapshot id를 참조한다.
6. `RAW`, `SPLIT_ADJUSTED`, `TOTAL_RETURN_ADJUSTED`를 구분한다.
7. split/dividend와 volume 보정 테스트를 작성한다.
8. 공급자 간 교차 검증 job을 제공하되 자동 병합하지 않는다.
9. 상태를 `VALID`, `VALID_WITH_WARNINGS`, `INVALID`로 표현한다.
10. 업로드·검증·snapshot 생성 API를 구현한다.

## 완료 조건

- 잘못된 데이터가 조용히 실행되지 않는다.
- 동일 snapshot이 시간이 지나도 바뀌지 않는다.
