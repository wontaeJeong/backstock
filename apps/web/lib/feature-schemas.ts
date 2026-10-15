import { z } from "zod"
import { objectSchema } from "./features"
export const statisticSchema = z
  .object({ value: z.string().nullable(), reason: z.string().nullable(), definition: z.string() })
  .passthrough()
export const statisticsSchema = z.record(z.string(), statisticSchema)
export const analysisSchema = z
  .object({
    run_id: z.string(),
    statistics: statisticsSchema,
    daily_returns: z.array(objectSchema),
    monthly_returns: z.array(objectSchema),
    drawdown: z.array(objectSchema),
    round_trips: z.array(objectSchema),
    distributions: z.record(z.string(), z.array(z.string())),
    warnings: z.array(z.string()),
  })
  .passthrough()
export const pageSchema = z
  .object({
    items: z.array(objectSchema),
    total: z.number(),
    page: z.number(),
    page_size: z.number(),
  })
  .passthrough()
export const experimentSchema = z
  .object({
    experiment_id: z.string(),
    kind: z.enum(["grid", "walk_forward", "portfolio"]),
    warnings: z.array(z.string()),
    rows: z.array(objectSchema).optional(),
    folds: z.array(objectSchema).optional(),
    components: z.array(objectSchema).optional(),
    curve: z.array(objectSchema).optional(),
    correlations: z.array(objectSchema).optional(),
  })
  .passthrough()
export const paperSchema = z
  .object({
    account_id: z.string(),
    name: z.string(),
    cash: z.string(),
    equity: z.string(),
    kill_switch: z.boolean(),
    positions: z.array(objectSchema),
    orders: z.array(objectSchema),
    fills: z.array(objectSchema),
    audit: z.array(objectSchema),
  })
  .passthrough()
export const barsSchema = z
  .object({
    snapshot_id: z.string(),
    interval: z.string(),
    total: z.number(),
    page: z.number(),
    page_size: z.number(),
    items: z.array(
      z
        .object({
          timestamp: z.string(),
          open: z.string(),
          high: z.string(),
          low: z.string(),
          close: z.string(),
          volume: z.number(),
          bid: z.string().nullable().optional(),
          ask: z.string().nullable().optional(),
        })
        .passthrough(),
    ),
  })
  .passthrough()
