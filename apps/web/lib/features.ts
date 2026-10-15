/* biome-ignore-all lint/complexity/useLiteralKeys: TypeScript requires indexed access for full-fidelity JSON records. */
import { z } from "zod"
import { apiErrorMessage } from "./api-error"
import { type Draft, symbols } from "./research"
import { readStrategySettings } from "./strategy-form"

export const objectSchema = z.record(z.string(), z.unknown())
export type JsonObject = z.infer<typeof objectSchema>
export const strategySchema = z
  .object({
    name: z.string().min(1),
    universe: z.array(z.string()).min(1),
    timeframe: z.enum(["1d", "1m", "5m", "tick"]),
    entry: objectSchema,
    position_sizing: objectSchema,
  })
  .passthrough()
export const strategyJson = (text: string) => strategySchema.parse(JSON.parse(text))
export function importDraft(draft: Draft, text: string): Draft {
  let next: ReturnType<typeof strategyJson>
  try {
    next = strategyJson(text)
  } catch {
    return { ...draft, advancedJson: text }
  }
  const symbol = next.universe.length === 1 ? next.universe[0]?.replace(/^NASDAQ:/, "") : undefined
  return {
    ...readStrategySettings(draft, next),
    advancedJson: text,
    formError: undefined,
    interval: next.timeframe,
    ...(symbols.includes(symbol as Draft["symbol"]) ? { symbol: symbol as Draft["symbol"] } : {}),
  }
}
export const endpoint = (path: string) => `/api/research/${path}`
export async function api(path: string, body?: unknown): Promise<JsonObject> {
  const response = await fetch(endpoint(path), {
    method: body === undefined ? "GET" : "POST",
    ...(body === undefined
      ? {}
      : { headers: { "content-type": "application/json" }, body: JSON.stringify(body) }),
  })
  const data: unknown = await response.json()
  if (!response.ok)
    throw new Error(
      apiErrorMessage(data, response.status) +
        ` (${objectSchema.safeParse(data).success ? String(objectSchema.parse(data)["code"] ?? response.status) : response.status})`,
    )
  return objectSchema.parse(data)
}
export async function paperMutation(
  account: string,
  path: string,
  body: unknown,
  current: (value: unknown) => void,
  fetcher: (path: string, init?: RequestInit) => Promise<Response> = fetch,
) {
  let failure: unknown
  try {
    const response = await fetcher(endpoint(`paper/accounts/${account}/${path}`), {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    })
    const result: unknown = await response.json()
    if (!response.ok)
      throw new Error(
        `${apiErrorMessage(result, response.status)} (${String(objectSchema.parse(result)["code"] ?? response.status)})`,
      )
  } catch (error) {
    failure = error
  }
  try {
    const response = await fetcher(endpoint(`paper/accounts/${account}`))
    const value: unknown = await response.json()
    if (!response.ok) throw new Error(apiErrorMessage(value, response.status))
    current(value)
  } catch (error) {
    throw new Error(
      `현재 계좌 조회 실패 · 이전 화면을 최신 상태로 신뢰하지 마세요. ${failure instanceof Error ? failure.message : ""} ${error instanceof Error ? error.message : ""}`,
    )
  }
  if (failure) throw failure
}
const hex = "[a-f0-9]{64}"
const account = "paper_[a-f0-9]{32}"
export function allowedResearchPath(method: string, path: string) {
  const get = new RegExp(
    `^(research/catalog|strategies/metadata|simulations/${hex}|research/library/(strategies|datasets|runs)|research/library/strategies/${hex}|research/runs/${hex}/(analysis|export\\.csv)|research/datasets/${hex}/bars|research/experiments/${hex}(/analysis)?|paper/accounts|paper/accounts/${account}(/reconciliation)?)$`,
  )
  const post = new RegExp(
    `^(simulations|datasets|strategies/validate|research/library/strategies|research/library/(strategies|datasets|runs)/${hex}/archive|research/(compare|benchmark)|research/experiments/(grid|walk-forward|portfolio)|paper/accounts|paper/accounts/${account}/(proposals|quotes|kill-switch)|paper/accounts/${account}/orders/paper_order_[a-f0-9]{32}/(approve|reject|cancel))$`,
  )
  return method === "GET" ? get.test(path) : method === "POST" && post.test(path)
}
export function numericPaths(input: unknown, prefix = ""): string[] {
  if (typeof input !== "object" || input === null) return []
  const obj = input as JsonObject
  return Object.entries(obj).flatMap(([key, value]) => {
    const path = prefix ? `${prefix}.${key}` : key
    if (
      key === "period" &&
      typeof obj["indicator"] === "string" &&
      obj["indicator"].startsWith("macd")
    )
      return []
    if (typeof value === "object" && value !== null) return numericPaths(value, path)
    const allowed =
      /^(commission_bps|sell_tax_bps|slippage_bps|spread_bps|latency_ms|volume_participation)$/.test(
        path,
      ) ||
      /^strategy\.(position_sizing\.(quantity|notional|percent|risk_percent|atr_period|atr_multiple)|risk\.(max_holding_bars|(stop_loss|take_profit|trailing_stop)\.(value|atr_period))|order\.(limit_offset_bps|stop_offset_bps))$/.test(
        path,
      ) ||
      (/^strategy\.(entry|exit)\.condition\./.test(path) &&
        ((obj["type"] === "constant" && key === "value") ||
          (obj["type"] === "indicator" &&
            ["period", "fast_period", "slow_period", "signal_period", "stddev_multiplier"].includes(
              key,
            ))))
    return allowed && value !== null && value !== undefined ? [path] : []
  })
}
export function downloadJson(value: unknown, name: string) {
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(value, null, 2)], { type: "application/json" }),
  )
  const link = document.createElement("a")
  link.href = url
  link.download = name
  link.click()
  URL.revokeObjectURL(url)
}
