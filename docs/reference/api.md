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

## 구현된 strategy endpoint

`POST /strategies/validate`는 임의 JSON body를 `StrategyDefinition`으로 검증하고 성공하면 canonical
JSON과 `sha256:<hex>` `version_id`를 가진 `StrategyVersion`을 200으로 반환한다. 실패하면 422
`STRATEGY_INVALID`와 `details.issues`(필드 경로 + 메시지 목록)를 반환한다. 저장은 하지 않으며 같은
정의는 항상 같은 `version_id`를 만든다.

`GET /strategies/metadata`는 `StrategyDefinition`의 JSON Schema(`json_schema`), operator/indicator
metadata(`operators`, `indicators`), 4개 템플릿의 canonical JSON(`templates`)을 반환한다.

`/strategies`, `/strategy-versions`의 영속화 CRUD, `/backtest-runs` 이하는 Prompt 08에서 구현한다.
# 연구용 시뮬레이션 API

- `GET /research/catalog`: 지원 종목·주기·제한·시간대 계약.
- `POST /simulations`: `{source, symbol, strategy, initial_cash, commission_bps, sell_tax_bps, slippage_bps}`.
  `source=yfinance`는 timezone-aware `start/end`와 일봉, `source=snapshot`은 업로드 `snapshot_id`,
  `source=demo`는 명시적 합성 고정 시세를 사용한다. 최대 64 KiB JSON, 단일 USD 종목, 3,000 bar.
- `GET /simulations/{run_id}`: 저장한 불변 실행 조회. 잘못된 ID/없는 결과는 404, 손상 결과는 409.
- 응답: `run_id`, `request`, `config`, `manifest`, `result`, `metrics`, `warnings`.
  Decimal은 JSON 문자열이며 `total_return`, `max_drawdown`, `benchmark_return`는 소수 비율이다.
  `metrics.net_profit = final_equity - initial_cash`. `result.status`가 succeeded가 아니면 부분 결과다.
  rate 입력은 bps이고 모든 비용을 표시한다. 슬리피지를 summary 손익에서 다시 차감하지 않는다.
- `/datasets` query의 `interval=1d|1m|5m`는 파일의 실제 주기다. 분봉 timestamp는 종료 시각이며
  explicit UTC offset이 필요하다. 원래 filename을 서버 경로로 사용하지 않는다.
