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
