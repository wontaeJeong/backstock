import { z } from "zod"

export type Strategy = {
  name: string
  universe: string[]
  timeframe: string
  entry: { condition: unknown }
  position_sizing: Record<string, unknown>
  [key: string]: unknown
}

export const symbols = [
  "AAPL",
  "MSFT",
  "NVDA",
  "AMZN",
  "GOOGL",
  "META",
  "QQQ",
  "TSLA",
  "AVGO",
  "COST",
  "NFLX",
  "AMD",
  "ADBE",
  "INTC",
  "CSCO",
  "PEP",
  "AMGN",
  "TXN",
  "INTU",
  "QCOM",
] as const
export type Interval = "1d" | "1m" | "5m" | "tick"
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
  | "vwap"
  | "bollinger_middle"
  | "bollinger_upper"
  | "bollinger_lower"
  | "macd"
  | "macd_signal"
  | "macd_histogram"
  | "rolling_high"
  | "rolling_low"
  | "volume_average"
export type Operand = {
  kind: OperandKind
  period: string
  value: string
  fast?: string
  slow?: string
  signal?: string
  multiplier?: string
}
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
  advancedJson?: string
  spread: string
  latency: string
  participation: string
  orderType: "market" | "limit" | "stop" | "stop_limit"
  limitOffset: string
  stopOffset: string
  tif: "day" | "gtc"
  entryStart: string
  entryEnd: string
  flattenAt: string
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
    spread: "0",
    latency: "0",
    participation: "",
    orderType: "market",
    limitOffset: "0",
    stopOffset: "0",
    tif: "day",
    entryStart: "",
    entryEnd: "",
    flattenAt: "",
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
    ...(input.kind.startsWith("macd")
      ? {
          fast_period: periodSchema.parse(input.fast ?? "12"),
          slow_period: periodSchema.parse(input.slow ?? "26"),
          signal_period: periodSchema.parse(input.signal ?? "9"),
        }
      : {}),
    ...(input.kind.startsWith("bollinger") ? { stddev_multiplier: input.multiplier ?? "2" } : {}),
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
  if (draft.advancedJson !== undefined) return JSON.parse(draft.advancedJson) as Strategy
  const stop = (value: string) => {
    if (!value) return undefined
    z.coerce.number().gt(0).max(100).parse(value)
    return { mode: "percent", value }
  }
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
    order: {
      order_type: draft.orderType,
      time_in_force: draft.tif,
      limit_offset_bps: ["limit", "stop_limit"].includes(draft.orderType)
        ? draft.limitOffset
        : null,
      stop_offset_bps: ["stop", "stop_limit"].includes(draft.orderType) ? draft.stopOffset : null,
    },
    session:
      draft.entryStart || draft.entryEnd || draft.flattenAt
        ? {
            entry_start: draft.entryStart || null,
            entry_end: draft.entryEnd || null,
            flatten_at: draft.flattenAt || null,
            weekdays: [0, 1, 2, 3, 4],
          }
        : null,
  }
}

export function buildRequest(draft: Draft, snapshotId?: string) {
  z.coerce.number().gt(0).max(1_000_000_000).parse(draft.initialCash)
  for (const cost of [draft.commission, draft.tax, draft.slippage])
    z.coerce.number().min(0).max(100).parse(cost)
  if (draft.source === "snapshot" && !snapshotId)
    throw new Error("먼저 데이터 파일을 업로드하세요.")
  if (draft.source === "yfinance" && draft.interval === "tick")
    throw new Error("원격 tick은 지원하지 않습니다. 파일 또는 합성 데모를 선택하세요.")
  if (draft.participation) z.coerce.number().gt(0).max(1).parse(draft.participation)
  z.coerce.number().min(0).max(100).parse(draft.spread)
  return {
    source: draft.source,
    symbol: draft.symbol,
    strategy: buildStrategy(draft),
    initial_cash: draft.initialCash,
    commission_bps: draft.commission,
    sell_tax_bps: draft.tax,
    slippage_bps: draft.slippage,
    spread_bps: draft.spread,
    latency_ms: z.coerce.number().int().min(0).max(60000).parse(draft.latency),
    volume_participation: draft.participation || null,
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
        summary: z
          .object({
            initial_cash: decimal,
            final_equity: decimal,
            total_return: decimal,
            realized_pnl: decimal,
            unrealized_pnl: decimal,
            commission: decimal,
            tax: decimal,
            slippage: decimal,
          })
          .passthrough(),
        portfolio: z.array(point).min(1),
        fills: z.array(fill),
        orders: z.array(order),
        benchmark: z.array(z.object({ timestamp: z.string(), value: decimal }).passthrough()),
        metadata: z
          .object({
            strategy_version: z.string(),
            code_revision: z.string(),
            engine_version: z.string(),
          })
          .passthrough(),
      })
      .passthrough(),
    metrics: z
      .object({
        net_profit: decimal,
        max_drawdown: decimal,
        fill_count: z.number(),
        closed_trade_count: z.number(),
        benchmark_return: decimal,
        metric_version: z.string(),
      })
      .passthrough(),
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
