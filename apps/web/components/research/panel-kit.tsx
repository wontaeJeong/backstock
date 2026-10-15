"use client"
import { useCallback, useId, useLayoutEffect, useRef, useState } from "react"
import { z } from "zod"
import { statisticsSchema } from "../../lib/feature-schemas"
import type { JsonObject } from "../../lib/features"
import { ActionButton } from "../ui"
import { ScrollRegion } from "./scroll-region"

export function useOperation(initialBusy = false) {
  const [busy, setBusy] = useState(initialBusy),
    [error, setError] = useState("")
  const ref = useRef<HTMLDivElement>(null)
  const sequence = useRef(0)
  useLayoutEffect(() => {
    if (error) {
      ref.current?.focus()
      ref.current?.scrollIntoView({ block: "nearest" })
    }
  }, [error])
  const act = useCallback(async (operation: () => Promise<void>) => {
    const token = ++sequence.current
    setBusy(true)
    setError("")
    try {
      await operation()
    } catch (e) {
      if (token === sequence.current) setError(e instanceof Error ? e.message : "요청 실패")
    } finally {
      if (token === sequence.current) setBusy(false)
    }
  }, [])
  return {
    busy,
    act,
    feedback: error ? (
      <div ref={ref} role="alert" tabIndex={-1} className="error-notice">
        <strong>요청하지 못했습니다.</strong>
        <p>{error}</p>
        <p>입력은 보존됩니다. Tab으로 설정을 확인하고 다시 실행하세요.</p>
      </div>
    ) : null,
  }
}
export function display(value: unknown): string {
  return value === null || value === undefined
    ? "미정의 / 미실행"
    : typeof value === "object"
      ? JSON.stringify(value)
      : String(value)
}
export function Records({
  title,
  items,
  columns,
}: {
  title: string
  items: JsonObject[]
  columns?: string[]
}) {
  const [page, setPage] = useState(1)
  const keys = columns ?? Object.keys(items[0] ?? {})
  const count = Math.max(1, Math.ceil(items.length / 25)),
    actual = Math.min(page, count)
  return (
    <details className="result-detail">
      <summary>
        {title} · {items.length}건
      </summary>
      {!items.length ? (
        <p>기록 없음 (성공 또는 0수익률을 뜻하지 않습니다.)</p>
      ) : (
        <>
          <ScrollRegion className="feature-scroll" label={`${title} 가로 스크롤`}>
            <table>
              <thead>
                <tr>
                  {keys.map((k) => (
                    <th key={k}>{k}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {items.slice((actual - 1) * 25, actual * 25).map((item) => (
                  <tr key={JSON.stringify(item)}>
                    {keys.map((k) => (
                      <td key={k}>{display(item[k])}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollRegion>
          <div className="starter-buttons">
            <ActionButton disabled={actual === 1} onClick={() => setPage(actual - 1)}>
              이전 25건
            </ActionButton>
            <span>
              {actual} / {count}
            </span>
            <ActionButton disabled={actual === count} onClick={() => setPage(actual + 1)}>
              다음 25건
            </ActionButton>
          </div>
        </>
      )}
    </details>
  )
}
export function Statistics({ value }: { value: unknown }) {
  const stats = statisticsSchema.parse(value)
  const labels: Record<string, string> = {
    initial_cash: "원금 (USD)",
    final_equity: "최종 평가액 (USD)",
    net_profit: "순손익 (USD)",
    total_return: "원금 대비 수익률 (비율)",
    max_drawdown: "최대 낙폭 (비율)",
    cagr: "연환산 성장률 (비율)",
    volatility: "연환산 변동성 (비율)",
    sharpe: "샤프 비율",
    sortino: "소르티노 비율",
    win_rate: "청산 lot 승률 (비율)",
    profit_factor: "총이익/총손실 비율",
    payoff_ratio: "평균 이익/손실 비율",
    expectancy: "청산 lot 평균 손익 (USD)",
    exposure: "보유 bar 비중 (비율)",
    turnover: "양방향 회전율 (비율)",
    holding_seconds: "평균 보유 시간 (초)",
    commission: "수수료 (USD)",
    tax: "매도세 (USD)",
    slippage: "슬리피지 진단 비용 (USD)",
    spread: "스프레드 진단 비용 (USD)",
  }
  return (
    <dl className="feature-statistics">
      {Object.entries(stats).map(([key, stat]) => (
        <div key={key}>
          <dt>
            <span>{labels[key] ?? key}</span>
            <code>{key}</code>
          </dt>
          <dd>{stat.value ?? `미정의 · ${stat.reason ?? "이유 없음"}`}</dd>
          <small>{stat.definition}</small>
        </div>
      ))}
    </dl>
  )
}
export function RawArtifact({ value }: { value: unknown }) {
  return (
    <details className="result-detail">
      <summary>원본 전체 근거 JSON</summary>
      <pre className="json-preview">{JSON.stringify(value, null, 2)}</pre>
    </details>
  )
}
export function Warnings({ items }: { items: string[] }) {
  return items.length ? (
    <div className="notice">
      <strong>해석 제한</strong>
      <ul>
        {[...new Set(items)].map((s) => (
          <li key={s}>{s}</li>
        ))}
      </ul>
    </div>
  ) : null
}
export function Field({
  label,
  value,
  onChange,
  type = "text",
  disabled = false,
}: {
  label: string
  value: string
  onChange: (v: string) => void
  type?: string
  disabled?: boolean
}) {
  const id = useId()
  return (
    <label className="form-field" htmlFor={id}>
      {label}
      <input
        id={id}
        disabled={disabled}
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    </label>
  )
}
export const records = (value: unknown) => z.array(z.record(z.string(), z.unknown())).parse(value)
