import { z } from "zod"

export const symbols = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "QQQ"] as const
export type Interval = "1d" | "1m" | "5m"
export type OperandKind =
  | "close"
  | "open"
  | "volume"
  | "sma"
  | "ema"
  | "rsi"
  | "atr"
  | "volume_ratio"
  | "return"
  | "constant"
export type Operand = { kind: OperandKind; period: string; value: string }
export type Rule = {
  id: string
  left: Operand
  op: "gt" | "gte" | "lt" | "lte" | "crosses_above" | "crosses_below"
  right: Operand
}
export type RuleGroup = { match: "all" | "any"; rules: Rule[] }
export type Draft = {
  name: string
  symbol: (typeof symbols)[number]
  interval: Interval
  source: "yfinance" | "demo" | "snapshot"
  start: string
  end: string
  initialCash: string
  allocation: string
  commission: string
  tax: string
  slippage: string
  stopLoss: string
  takeProfit: string
  holdingBars: string
  entry: RuleGroup
  exit: RuleGroup
}

const operand = (kind: OperandKind, period = "5", value = "30"): Operand => ({
  kind,
  period,
  value,
})
export function defaultDraft(): Draft {
  return {
    name: "나의 첫 전략",
    symbol: "AAPL",
    interval: "1d",
    source: "yfinance",
    start: "2024-01-01",
    end: "2025-01-01",
    initialCash: "10000",
    allocation: "50",
    commission: "1",
    tax: "0",
    slippage: "5",
    stopLoss: "3",
    takeProfit: "6",
    holdingBars: "",
    entry: {
      match: "all",
      rules: [
        {
          id: "entry-1",
          left: operand("sma", "5"),
          op: "crosses_above",
          right: operand("sma", "20"),
        },
      ],
    },
    exit: {
      match: "all",
      rules: [
        {
          id: "exit-1",
          left: operand("sma", "5"),
          op: "crosses_below",
          right: operand("sma", "20"),
        },
      ],
    },
  }
}

export function starterDraft(kind: "trend" | "reversion" | "custom", draft: Draft): Draft {
  if (kind === "trend") return { ...draft, entry: defaultDraft().entry, exit: defaultDraft().exit }
  return {
    ...draft,
    entry: {
      match: "all",
      rules: [
        {
          id: "entry-1",
          left: operand(kind === "reversion" ? "rsi" : "close", "14"),
          op: "lt",
          right: operand("constant", "5", kind === "reversion" ? "30" : "100"),
        },
      ],
    },
    exit: {
      match: "all",
      rules: [
        {
          id: "exit-1",
          left: operand(kind === "reversion" ? "rsi" : "close", "14"),
          op: "gt",
          right: operand("constant", "5", kind === "reversion" ? "70" : "110"),
        },
      ],
    },
  }
}

const periodSchema = z.coerce.number().int().min(1).max(3000)
function valueDefinition(input: Operand) {
  if (input.kind === "constant") {
    z.coerce.number().finite().parse(input.value)
    if (!input.value.trim()) throw new Error("비교 숫자를 입력하세요.")
    return { type: "constant", value: input.value }
  }
  if (["close", "open", "volume"].includes(input.kind))
    return { type: "bar_field", field: input.kind, shift: 0 }
  return {
    type: "indicator",
    indicator: input.kind,
    period: periodSchema.parse(input.period),
    shift: 0,
  }
}

function groupDefinition(group: RuleGroup) {
  if (!group.rules.length || group.rules.length > 4) throw new Error("조건은 1~4개여야 합니다.")
  return {
    op: group.match,
    conditions: group.rules.map((rule) => ({
      op: rule.op,
      left: valueDefinition(rule.left),
      right: valueDefinition(rule.right),
    })),
  }
}

function percentFraction(value: string): string {
  z.coerce.number().gt(0).max(100).parse(value)
  const match = /^(\d+)(?:\.(\d+))?$/.exec(value)
  if (!match) throw new Error("투자 비중은 0 초과 100 이하의 숫자여야 합니다.")
  const digits = (match[1] ?? "").padStart(3, "0")
  return `${Number(digits.slice(0, -2))}.${digits.slice(-2)}${match[2] ?? ""}`
    .replace(/0+$/, "")
    .replace(/\.$/, "")
}

export function buildStrategy(draft: Draft) {
  const stop = (value: string) =>
    value
      ? { mode: "percent", value: z.coerce.number().gt(0).max(100).parse(value).toString() }
      : undefined
  return {
    schema_version: "1",
    name: z.string().trim().min(1).max(200).parse(draft.name),
    universe: [`NASDAQ:${draft.symbol}`],
    timeframe: draft.interval,
    entry: { condition: groupDefinition(draft.entry) },
    exit: { condition: draft.exit.rules.length ? groupDefinition(draft.exit) : null },
    position_sizing: { method: "percent_equity", percent: percentFraction(draft.allocation) },
    risk: {
      stop_loss: stop(draft.stopLoss),
      take_profit: stop(draft.takeProfit),
      max_holding_bars: draft.holdingBars ? periodSchema.parse(draft.holdingBars) : undefined,
    },
    order: { order_type: "market", time_in_force: "day" },
  }
}

export function buildRequest(draft: Draft, snapshotId?: string) {
  z.coerce.number().gt(0).max(1_000_000_000).parse(draft.initialCash)
  for (const cost of [draft.commission, draft.tax, draft.slippage])
    z.coerce.number().min(0).max(100).parse(cost)
  if (draft.source === "snapshot" && !snapshotId)
    throw new Error("먼저 데이터 파일을 업로드하세요.")
  if (draft.source === "yfinance" && draft.interval !== "1d")
    throw new Error("분봉은 파일 업로드 또는 합성 데모를 이용하세요.")
  return {
    source: draft.source,
    symbol: draft.symbol,
    strategy: buildStrategy(draft),
    initial_cash: draft.initialCash,
    commission_bps: draft.commission,
    sell_tax_bps: draft.tax,
    slippage_bps: draft.slippage,
    snapshot_id: draft.source === "snapshot" ? snapshotId : undefined,
    start: draft.source === "yfinance" ? `${draft.start}T00:00:00Z` : undefined,
    end: draft.source === "yfinance" ? `${draft.end}T00:00:00Z` : undefined,
  }
}

const decimal = z.string().regex(/^-?\d+(\.\d+)?([eE][+-]?\d+)?$/)
const point = z
  .object({ timestamp: z.string(), equity: decimal, cash: decimal, unrealized_pnl: decimal })
  .passthrough()
const fill = z
  .object({
    fill_id: z.string(),
    order_id: z.string(),
    timestamp: z.string(),
    side: z.enum(["buy", "sell"]),
    quantity: z.number(),
    execution_price: decimal,
    commission: decimal,
    tax: decimal,
    slippage: decimal,
  })
  .passthrough()
const order = z
  .object({
    order_id: z.string(),
    state: z.string(),
    state_reason: z.string(),
    intent: z.object({ reason: z.string(), submitted_at: z.string() }).passthrough(),
  })
  .passthrough()
export const simulationReportSchema = z
  .object({
    run_id: z.string().regex(/^[a-f0-9]{64}$/),
    request: z
      .object({
        symbol: z.string(),
        source: z.enum(["demo", "yfinance", "snapshot"]),
        strategy: z.object({ name: z.string(), timeframe: z.string() }).passthrough(),
        commission_bps: decimal,
        sell_tax_bps: decimal,
        slippage_bps: decimal,
      })
      .passthrough(),
    config: z.object({ initial_cash: decimal }).passthrough(),
    manifest: z
      .object({
        snapshot_id: z.string(),
        provider: z.string(),
        row_count: z.number(),
        interval: z.string(),
        range_start: z.string(),
        range_end: z.string(),
        normalized_checksum: z.string(),
        acquired_at: z.string(),
        price_adjustment: z.string(),
        warnings: z.array(z.object({ code: z.string(), message: z.string() }).passthrough()),
      })
      .passthrough(),
    result: z
      .object({
        status: z.enum(["succeeded", "failed", "cancelled"]),
        failure_reason: z.string().nullable(),
        summary: z.object({
          initial_cash: decimal,
          final_equity: decimal,
          total_return: decimal,
          realized_pnl: decimal,
          unrealized_pnl: decimal,
          commission: decimal,
          tax: decimal,
          slippage: decimal,
        }),
        portfolio: z.array(point).min(1),
        fills: z.array(fill),
        orders: z.array(order),
        benchmark: z.array(z.object({ timestamp: z.string(), value: decimal })),
        metadata: z
          .object({
            strategy_version: z.string(),
            code_revision: z.string(),
            engine_version: z.string(),
          })
          .passthrough(),
      })
      .passthrough(),
    metrics: z.object({
      net_profit: decimal,
      max_drawdown: decimal,
      fill_count: z.number(),
      closed_trade_count: z.number(),
      benchmark_return: decimal,
      metric_version: z.string(),
    }),
    warnings: z.array(z.string()),
  })
  .passthrough()
export type SimulationReport = z.infer<typeof simulationReportSchema>
export const money = (value: string | number) =>
  new Intl.NumberFormat("ko-KR", {
    style: "currency",
    currency: "USD",
    currencyDisplay: "narrowSymbol",
    maximumFractionDigits: 2,
  }).format(Number(value))
export const percent = (value: string) =>
  new Intl.NumberFormat("ko-KR", { style: "percent", maximumFractionDigits: 2 }).format(
    Number(value),
  )
