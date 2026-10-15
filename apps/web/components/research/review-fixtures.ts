import { simulationReportSchema } from "../../lib/research"
export const A = "a".repeat(64),
  B = "b".repeat(64),
  C = "c".repeat(64)
export function fixtureReport(id = A, provider = "synthetic_demo") {
  return simulationReportSchema.parse({
    run_id: id,
    request: {
      symbol: "AAPL",
      source: "snapshot",
      strategy: { name: id, timeframe: "1d" },
      commission_bps: "1",
      sell_tax_bps: "0",
      slippage_bps: "5",
    },
    config: { initial_cash: "1000" },
    manifest: {
      snapshot_id: id,
      provider,
      row_count: 2,
      interval: "1d",
      range_start: "2024-01-02T00:00:00Z",
      range_end: "2024-01-04T00:00:00Z",
      normalized_checksum: "checksum",
      acquired_at: "2024-01-04T00:00:00Z",
      price_adjustment: "raw",
      warnings: [],
    },
    result: {
      status: "succeeded",
      failure_reason: null,
      summary: {
        initial_cash: "1000",
        final_equity: "1000",
        total_return: "0",
        realized_pnl: "0",
        unrealized_pnl: "0",
        commission: "0",
        tax: "0",
        slippage: "0",
      },
      portfolio: [
        { timestamp: "2024-01-02T00:00:00Z", equity: "1000", cash: "1000", unrealized_pnl: "0" },
      ],
      fills: [],
      orders: [],
      benchmark: [],
      metadata: { strategy_version: "v", code_revision: "test", engine_version: "test" },
    },
    metrics: {
      net_profit: "0",
      max_drawdown: "0",
      fill_count: 0,
      closed_trade_count: 0,
      benchmark_return: "0",
      metric_version: "test",
    },
    warnings: [],
  })
}
export const fixtureAnalysis = (id: string, label: string) => ({
  run_id: id,
  statistics: { net_profit: { value: "1", reason: null, definition: label } },
  daily_returns: [],
  monthly_returns: [],
  drawdown: [],
  round_trips: [],
  distributions: {},
  warnings: [],
})
export const fixtureBars = (id: string) => ({
  snapshot_id: id,
  interval: "1d",
  total: 2,
  page: 1,
  page_size: 25,
  items: [
    {
      timestamp: "2024-01-02T00:00:00Z",
      open: "100",
      high: "101",
      low: "99",
      close: "100",
      volume: 100,
    },
  ],
})
export const json = (value: unknown, status = 200) =>
  new Response(JSON.stringify(value), { status, headers: { "content-type": "application/json" } })
