# API Reference

구현 시 OpenAPI에서 생성하거나 실제 endpoint와 일치하도록 갱신한다.

## 오류 형식

```json
{
  "code": "DATASET_INVALID",
  "message": "Dataset validation failed",
  "details": {},
  "request_id": "..."
}
```

## 주요 리소스

- `/instruments`
- `/datasets`
- `/dataset-snapshots`
- `/strategies`
- `/strategy-versions`
- `/backtest-runs`
- `/backtest-results`
- `/paper-accounts`
- `/proposed-orders`

긴 목록은 pagination하고 BacktestRun은 job status와 progress를 제공한다.

## 구현된 dataset endpoint

`POST /datasets`는 CSV 또는 Parquet bytes를 body로 받고 `X-Filename`과 정확한 `Content-Type`을 검사한다.
instrument, `[start,end)`, timezone, 가격/volume adjustment는 query parameter다. 파일명은 경로 구분자를
허용하지 않고 임시 생성 경로만 사용한다. body는 streaming으로 기록하며 기본 최대 크기는 25 MiB다.
Parquet는 signature, column 수와 row 수를 decode 전에 제한하고 필요한 bar column만 읽는다. schema 또는
품질 오류는 422 `DATASET_INVALID`, path/type/size 오류는 각각 400/415/413이다.

성공하면 201로 immutable snapshot manifest를 반환한다. `GET /dataset-snapshots/{snapshot_id}`는 같은
manifest를 반환하고 normalized checksum을 재검증한다. manifest에는 provider 취득 시점과 query,
canonical/provider symbol, timezone, 가격·volume adjustment, row count, raw/normalized checksum,
validation status/warnings와 storage root를 노출하지 않는 `snapshot://` logical URI가 포함된다.
