/* biome-ignore-all lint/complexity/useLiteralKeys: TypeScript requires indexed access for server JSON records. */
"use client"

import { type ChangeEvent, useState } from "react"
import { z } from "zod"
import { api } from "../../lib/features"
import { type Draft, symbols } from "../../lib/research"
import { ActionButton, FormField } from "../ui"
import { Field, useOperation } from "./panel-kit"

export function DataControls({
  draft,
  update,
  onUpload,
  snapshotId,
  adjustment,
  onAdjustment,
}: {
  draft: Draft
  update: <K extends keyof Draft>(key: K, value: Draft[K]) => void
  onUpload: (event: ChangeEvent<HTMLInputElement>) => void
  snapshotId: string | undefined
  adjustment: string
  onAdjustment: (value: "raw" | "total_return_adjusted") => void
}) {
  const [query, setQuery] = useState("")
  const [matches, setMatches] = useState<string[]>()
  const { busy, act, feedback } = useOperation()
  return (
    <section className="editor-section" aria-labelledby="data-heading">
      <h3 id="data-heading">
        <span className="editor-step">01</span> 데이터와 원금
      </h3>
      <details className="editor-disclosure">
        <summary>현재 종목 검색 (제한된 목록)</summary>
        {feedback}
        <Field label="현재 종목 검색" value={query} onChange={setQuery} />
        <ActionButton
          disabled={busy}
          onClick={() =>
            void act(async () => {
              const result = await api(`research/catalog?q=${encodeURIComponent(query)}`)
              setMatches(z.array(z.string()).parse(result["symbols"]))
            })
          }
        >
          종목 검색
        </ActionButton>
        {matches?.map((s) => (
          <ActionButton key={s} onClick={() => update("symbol", s as Draft["symbol"])}>
            {s} 선택
          </ActionButton>
        ))}
        {matches?.length === 0 && <p>검색 결과 없음</p>}
        <p className="helper">
          현재 curated 목록이며 전체 Nasdaq·상장폐지 포함 과거 universe가 아닙니다.
        </p>
      </details>
      <div className="form-grid">
        <label className="form-field">
          나스닥 종목
          <select
            disabled={draft.advancedJson !== undefined}
            value={draft.symbol}
            onChange={(event) => update("symbol", event.target.value as Draft["symbol"])}
          >
            {symbols.map((symbol) => (
              <option key={symbol}>{symbol}</option>
            ))}
          </select>
        </label>
        <label className="form-field">
          데이터 주기
          <select
            disabled={draft.advancedJson !== undefined}
            value={draft.interval}
            onChange={(event) => update("interval", event.target.value as Draft["interval"])}
          >
            <option value="1d">일봉 · 중장기 연구</option>
            <option value="1m">1분봉 · 단기 근사 연구</option>
            <option value="5m">5분봉 · 단기 근사 연구</option>
            <option value="tick">Tick / quote · 로컬 이벤트 재생</option>
          </select>
        </label>
      </div>
      <label className="form-field">
        데이터 출처
        <select
          value={draft.source}
          onChange={(event) => update("source", event.target.value as Draft["source"])}
        >
          <option value="yfinance">Yahoo 실제 과거 시세 (일봉·최근 분봉)</option>
          <option value="snapshot">내 CSV / Parquet 파일</option>
          <option value="demo">합성 데모 (실제 시세 아님)</option>
        </select>
      </label>
      {draft.source !== "demo" && (
        <div className="form-grid">
          <FormField
            id="start-date"
            label="시작일"
            type="date"
            value={draft.start}
            onChange={(event) => update("start", event.target.value)}
            required
          />
          <FormField
            id="end-date"
            label="종료일 (해당일 제외)"
            type="date"
            value={draft.end}
            min={draft.start}
            onChange={(event) => update("end", event.target.value)}
            required
          />
        </div>
      )}
      {draft.source === "demo" && (
        <p className="notice">
          고정된 합성 가격 120개 bar로 기능을 체험합니다. 실제 나스닥 시세를 검증하려면 Yahoo 일봉
          또는 과거 시세 파일을 선택하세요.
        </p>
      )}
      {draft.source === "yfinance" && (
        <p className="helper">
          Yahoo 무료 데이터는 소급 보정 가격입니다. 공급자 오류 시 데모나 다른 공급자로 자동
          전환하지 않습니다. 전체 종목 검색·과거 상장 목록은 지원하지 않습니다.
        </p>
      )}
      {draft.source === "yfinance" && ["1m", "5m"].includes(draft.interval) && (
        <div className="notice">
          <p>
            원격 제한: 1m 최근 7일 / 5m 최근 60일. 가용성을 보장하지 않으며 기존 기간을 자동
            변경하지 않습니다.
          </p>
          <ActionButton
            onClick={() => {
              const end = new Date()
              end.setUTCDate(end.getUTCDate() - 1)
              const start = new Date(end)
              start.setUTCDate(start.getUTCDate() - (draft.interval === "1m" ? 3 : 14))
              update("start", start.toISOString().slice(0, 10))
              update("end", end.toISOString().slice(0, 10))
            }}
          >
            최근 분봉 기간 선택
          </ActionButton>
        </div>
      )}
      {draft.interval !== "1d" && (
        <p className="notice">
          분봉은 종료 시각, tick은 event 시각과 명시적 UTC offset이 필요합니다. tick CSV는
          timestamp,price,size 및 선택 bid,ask 쌍입니다. 원격 tick은 없으며 호가·체결 지연은
          시나리오만 검증합니다.
        </p>
      )}
      {draft.source === "snapshot" && (
        <div className="upload-box">
          <label className="form-field">
            파일 가격 보정 의미
            <select
              value={adjustment}
              onChange={(event) =>
                onAdjustment(event.target.value as "raw" | "total_return_adjusted")
              }
            >
              <option value="raw">원시 가격 (raw)</option>
              <option value="total_return_adjusted">배당 포함 보정 가격</option>
            </select>
          </label>
          <label className="form-field">
            과거 시세 파일 업로드
            <input type="file" accept=".csv,.parquet" onChange={onUpload} />
          </label>
          <p className="helper">
            timestamp, open, high, low, close, volume 컬럼. USD·실제 거래량(raw)을 사용합니다. 최대
            25 MiB, 시뮬레이션 최대 3,000 bar. 기간 밖 행은 거부하며 자동으로 자르지 않습니다.
          </p>
          {snapshotId && (
            <p className="upload-success" role="status">
              파일 검증 완료 · {snapshotId.slice(0, 12)}
            </p>
          )}
          <a className="text-link" href="/sample-minute-bars.csv" download>
            분봉 CSV 형식 예시 (합성) 받기
          </a>
        </div>
      )}
      <div className="form-grid">
        <FormField
          id="initial-cash"
          label="원금 (USD)"
          type="number"
          min="1"
          max="1000000000"
          step="0.01"
          value={draft.initialCash}
          onChange={(event) => update("initialCash", event.target.value)}
          required
        />
        <FormField
          id="allocation"
          disabled={draft.advancedJson !== undefined}
          label="매수 시 자산 사용 비중 (%)"
          type="number"
          min="0.01"
          max="100"
          step="0.01"
          value={draft.allocation}
          onChange={(event) => update("allocation", event.target.value)}
          helper="다음 시가 상승·비용으로 현금이 부족하면 주문이 거절될 수 있습니다."
          required
        />
      </div>
    </section>
  )
}
