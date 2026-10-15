/* biome-ignore-all lint/complexity/useLiteralKeys: Strategy JSON preserves indexed protocol keys. */
import { type Draft, positionSizing, riskRule, riskSettings } from "./research"

type ObjectValue = Record<string, unknown>
const obj = (v: unknown): ObjectValue =>
  typeof v === "object" && v !== null && !Array.isArray(v) ? (v as ObjectValue) : {}
const text = (v: unknown, fallback: string) =>
  typeof v === "string" || typeof v === "number" ? String(v) : fallback
/** Unit conversion only: move decimal digits without binary floating-point finance. */
function fractionAsPercent(value: unknown, fallback: string) {
  const match = /^([+-]?)(\d+)(?:\.(\d*))?(?:[eE]([+-]?\d+))?$/.exec(String(value))
  if (!match) return fallback
  const digits = (match[2] ?? "") + (match[3] ?? ""),
    position = (match[2]?.length ?? 0) + Number(match[4] ?? 0) + 2
  if (Math.abs(position) > 5000) return fallback
  const shifted =
    position <= 0
      ? `0.${"0".repeat(-position)}${digits}`
      : position >= digits.length
        ? digits + "0".repeat(position - digits.length)
        : `${digits.slice(0, position)}.${digits.slice(position)}`
  return `${match[1] ?? ""}${shifted.replace(/^0+(?=\d)/, "")}`
}
export function readStrategySettings(draft: Draft, definition: unknown): Draft {
  const source = obj(definition),
    sizing = obj(source["position_sizing"]),
    risk = obj(source["risk"]),
    session = obj(source["session"])
  const next = {
    ...draft,
    sizingMethod: sizing["method"] as Draft["sizingMethod"],
    quantity: text(sizing["quantity"], draft.quantity),
    notional: text(sizing["notional"], draft.notional),
    allocation: fractionAsPercent(sizing["percent"], draft.allocation),
    riskPercent: fractionAsPercent(sizing["risk_percent"], draft.riskPercent),
    sizingAtrPeriod: text(sizing["atr_period"], draft.sizingAtrPeriod),
    sizingAtrMultiple: text(sizing["atr_multiple"], draft.sizingAtrMultiple),
    holdingBars: text(risk["max_holding_bars"], ""),
    entryStart: text(session["entry_start"], ""),
    entryEnd: text(session["entry_end"], ""),
    flattenAt: text(session["flatten_at"], ""),
    weekdays: Array.isArray(session["weekdays"])
      ? (session["weekdays"] as number[])
      : [0, 1, 2, 3, 4],
  }
  const loss = obj(risk["stop_loss"]),
    profit = obj(risk["take_profit"]),
    trailing = obj(risk["trailing_stop"])
  return {
    ...next,
    stopLossMode: (loss["mode"] ?? "off") as Draft["stopLossMode"],
    stopLoss: text(loss["value"], draft.stopLoss),
    stopLossPeriod: text(loss["atr_period"], "14"),
    takeProfitMode: (profit["mode"] ?? "off") as Draft["takeProfitMode"],
    takeProfit: text(profit["value"], draft.takeProfit),
    takeProfitPeriod: text(profit["atr_period"], "14"),
    trailingMode: (trailing["mode"] ?? "off") as Draft["trailingMode"],
    trailingStop: text(trailing["value"], draft.trailingStop),
    trailingPeriod: text(trailing["atr_period"], "14"),
  }
}
export function updateDraftSetting<K extends keyof Draft>(
  draft: Draft,
  key: K,
  value: Draft[K],
): Draft {
  const next = {
    ...draft,
    [key]: value,
    ...(key === "advancedJson" ? { formError: undefined } : {}),
  }
  if (draft.advancedJson === undefined) return next
  const sizing = [
    "sizingMethod",
    "quantity",
    "notional",
    "allocation",
    "riskPercent",
    "sizingAtrPeriod",
    "sizingAtrMultiple",
  ]
  const loss = ["stopLossMode", "stopLoss", "stopLossPeriod"],
    profit = ["takeProfitMode", "takeProfit", "takeProfitPeriod"],
    trailing = ["trailingMode", "trailingStop", "trailingPeriod"]
  const session = ["entryStart", "entryEnd", "flattenAt", "weekdays"]
  if (![...sizing, ...loss, ...profit, ...trailing, ...session, "holdingBars"].includes(key))
    return next
  let latestJson = draft.advancedJson
  try {
    const definition = obj(JSON.parse(draft.advancedJson))
    if (sizing.includes(key)) definition["position_sizing"] = positionSizing(next)
    else if (session.includes(key))
      definition["session"] = {
        ...obj(definition["session"]),
        entry_start: next.entryStart || null,
        entry_end: next.entryEnd || null,
        flatten_at: next.flattenAt || null,
        weekdays: next.weekdays,
      }
    else {
      const risk = { ...obj(definition["risk"]) }
      if (loss.includes(key))
        risk["stop_loss"] = riskRule(
          next.stopLossMode,
          next.stopLoss,
          next.stopLossPeriod,
          "stop_loss",
        )
      else if (profit.includes(key))
        risk["take_profit"] = riskRule(
          next.takeProfitMode,
          next.takeProfit,
          next.takeProfitPeriod,
          "take_profit",
        )
      else if (trailing.includes(key))
        risk["trailing_stop"] = riskRule(
          next.trailingMode,
          next.trailingStop,
          next.trailingPeriod,
          "trailing_stop",
        )
      else risk["max_holding_bars"] = next.holdingBars ? Number(next.holdingBars) : null
      definition["risk"] = risk
    }
    // Commit this independently valid branch even while another branch is incomplete.
    // The full-form gate still blocks execution until every current branch is valid.
    latestJson = JSON.stringify(definition, null, 2)
    positionSizing(next)
    riskSettings(next)
    return { ...next, formError: undefined, advancedJson: latestJson }
  } catch {
    return {
      ...next,
      advancedJson: latestJson,
      formError: "수량·위험 폼의 숫자·기간을 완성하세요. 이전 JSON으로 대신 실행하지 않습니다.",
    }
  } // Preserve partial edits without silently executing the old JSON.
}
