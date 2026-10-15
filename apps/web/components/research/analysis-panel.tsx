/* biome-ignore-all lint/complexity/useLiteralKeys: TypeScript noPropertyAccessFromIndexSignature requires brackets for full-fidelity JSON records. */
"use client"
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react"
import { z } from "zod"
import { analysisSchema, barsSchema, pageSchema } from "../../lib/feature-schemas"
import { api, endpoint, type JsonObject } from "../../lib/features"
import { type SimulationReport, simulationReportSchema } from "../../lib/research"
import { ActionButton } from "../ui"
import { display, RawArtifact, Records, Statistics, useOperation, Warnings } from "./panel-kit"
import { ScrollRegion } from "./scroll-region"

export function ValueChart({
  title,
  points,
  field,
  markers = [],
  cursor,
}: {
  title: string
  points: JsonObject[]
  field: string
  markers?: JsonObject[]
  cursor?: number
}) {
  const shown = points.slice(0, 25),
    values = shown.map((p) => Number(p[field])),
    visibleMarkers = markers.filter((m) => shown.some((p) => p["timestamp"] === m["timestamp"])),
    extent = [...values, ...visibleMarkers.map((m) => Number(m["execution_price"]))],
    low = Math.min(...extent),
    high = Math.max(...extent)
  const y = (n: number) => 220 - ((n - low) / (high - low || 1)) * 150
  if (!shown.length) return <p>{title} · 관측 없음</p>
  return (
    <ScrollRegion className="feature-scroll" label={`${title} 가로 스크롤`}>
      <svg width="900" height="280" viewBox="0 0 900 280" role="img" aria-label={title}>
        <title>{title} · 최대 25개 관측. 정확한 값은 아래 원본 표.</title>
        <text x="20" y="25" fontSize="16">
          {title}
        </text>
        <text x="20" y="65" fontSize="16">
          {String(high)}
        </text>
        <text x="20" y="242" fontSize="16">
          {String(low)}
        </text>
        <polyline
          fill="none"
          stroke="var(--accent, #4f46e5)"
          strokeWidth="2"
          points={values.map((n, i) => `${160 + i * 28},${y(n)}`).join(" ")}
        />
        {cursor !== undefined && (
          <line
            x1={160 + (cursor - 1) * 28}
            x2={160 + (cursor - 1) * 28}
            y1="60"
            y2="225"
            stroke="currentColor"
            strokeDasharray="4 4"
          >
            <title>선택 bar {cursor}</title>
          </line>
        )}
        {visibleMarkers.map((m) => (
          <circle
            key={String(m["fill_id"])}
            cx={160 + shown.findIndex((p) => p["timestamp"] === m["timestamp"]) * 28}
            cy={y(Number(m["execution_price"]))}
            r="5"
            fill={m["side"] === "buy" ? "#2563eb" : "#c2410c"}
          >
            <title>{`${m["side"] === "buy" ? "매수" : "매도"} ${String(m["timestamp"])} · 체결가 ${String(m["execution_price"])}`}</title>
          </circle>
        ))}
        <text x="160" y="267" fontSize="16">
          첫 관측
        </text>
        <text x="720" y="267" fontSize="16">
          마지막 관측
        </text>
      </svg>
    </ScrollRegion>
  )
}
export function AnalysisPanel({
  report,
  onRun,
}: {
  report: SimulationReport | undefined
  onRun: (r: SimulationReport) => void
}) {
  const [analysis, setAnalysis] = useState<z.infer<typeof analysisSchema>>(),
    [bars, setBars] = useState<z.infer<typeof barsSchema>>(),
    [page, setPage] = useState(1),
    [cursor, setCursor] = useState(1)
  const [runs, setRuns] = useState<JsonObject[]>([]),
    [qqq, setQqq] = useState<JsonObject[]>([]),
    [snapshot, setSnapshot] = useState("")
  const [runPage, setRunPage] = useState(1),
    [runTotal, setRunTotal] = useState(0),
    [qqqPage, setQqqPage] = useState(1),
    [qqqTotal, setQqqTotal] = useState(0)
  const [selected, setSelected] = useState<string[]>([]),
    [compare, setCompare] = useState<JsonObject>(),
    [benchmark, setBenchmark] = useState<JsonObject>()
  const { busy, act, feedback } = useOperation(true)
  const titleRef = useRef<HTMLHeadingElement>(null)
  const analyzedRun = analysis?.run_id
  useLayoutEffect(() => {
    if (analyzedRun) {
      titleRef.current?.focus({ preventScroll: true })
      titleRef.current?.scrollIntoView({ block: "start", behavior: "instant" })
    }
  }, [analyzedRun])
  const load = useCallback(
    async (p = 1) => {
      if (!report) return
      const [a, b] = await Promise.all([
        api(`research/runs/${report.run_id}/analysis`),
        api(`research/datasets/${report.manifest.snapshot_id}/bars?page=${p}&page_size=25`),
      ])
      setAnalysis(analysisSchema.parse(a))
      setBars(barsSchema.parse(b))
      setPage(p)
      setCursor(1)
    },
    [report],
  )
  useEffect(() => {
    void act(async () => {
      setSelected(JSON.parse(localStorage.getItem("research-compare") ?? "[]") as string[])
      const runList = pageSchema.parse(await api("research/library/runs?page_size=25"))
      setRuns(runList.items)
      setRunTotal(runList.total)
      setRunPage(1)
      const qqqList = pageSchema.parse(await api("research/library/datasets?q=QQQ&page_size=25"))
      setQqq(qqqList.items)
      setQqqTotal(qqqList.total)
      setQqqPage(1)
      await load()
    })
  }, [load, act])
  const bar = bars?.items[cursor - 1]
  const state = report?.result.portfolio.find((p) => p.timestamp === bar?.timestamp)
  return (
    <section className="feature-panel">
      <h2 id="workbench-panel-title" tabIndex={-1} ref={titleRef}>
        상세 분석
      </h2>
      {feedback}
      <fieldset disabled={busy}>
        <p>
          통계는 서버의 실제 평가·FIFO 청산 lot 결과입니다. null은 0이 아닙니다. 합성 데이터와 같은
          패턴 상관은 실제 성과·분산 효과가 아닙니다.
        </p>
        {!report && <p>보관함에서 실행을 열거나 먼저 시뮬레이션하세요.</p>}
        {analysis && (
          <>
            <p className="notice">
              {report?.manifest.provider === "synthetic_demo"
                ? "합성 데이터 · 실제 시세 아님"
                : report?.request.source === "snapshot"
                  ? "사용자 파일 · 시세 출처 미검증"
                  : "Yahoo 과거 시세 · 현재 거래소 가격 아님"}{" "}
              · 실행 상태 {report?.result.status} · {report?.manifest.provider}
            </p>
            <h3>핵심 결과 · 서버 계산</h3>
            <p className="helper">
              비율 0.1은 10%입니다. 순손익은 현금 잔액이 아니라 미실현 평가손익을 포함하며,
              spread·slippage는 체결가에 이미 반영되어 다시 차감하지 않습니다.
            </p>
            <Statistics
              value={Object.fromEntries(
                Object.entries(analysis.statistics).filter(([key]) =>
                  ["net_profit", "total_return", "max_drawdown"].includes(key),
                ),
              )}
            />
            <details className="result-detail">
              <summary>전체 출처·해석 제한</summary>
              <Warnings items={[...(report?.warnings ?? []), ...analysis.warnings]} />
            </details>
            <details className="result-detail">
              <summary>모든 성과·위험·비용 통계 (null 이유 포함)</summary>
              <Statistics
                value={Object.fromEntries(
                  Object.entries(analysis.statistics).filter(
                    ([key]) => !["net_profit", "total_return", "max_drawdown"].includes(key),
                  ),
                )}
              />
            </details>
            <div className="starter-buttons">
              {[
                ["fills", "체결"],
                ["equity", "자산"],
                ["orders", "주문"],
              ].map(([kind, label]) => (
                <a
                  key={kind}
                  className="text-link"
                  href={endpoint(`research/runs/${analysis.run_id}/export.csv?kind=${kind}`)}
                  download
                >
                  {label} CSV
                </a>
              ))}
            </div>
            <ValueChart title="낙폭 · 비율 (0.1 = 10%)" points={analysis.drawdown} field="value" />
            <Records title="낙폭 전체 관측" items={analysis.drawdown} />
            <Records title="월별 수익률 · 비율" items={analysis.monthly_returns} />
            <details className="result-detail">
              <summary>월별 수익률·청산 손익 분포 그래프 (첫 25개)</summary>
              <ValueChart
                title="월별 수익률 · 비율 (0.1 = 10%)"
                points={analysis.monthly_returns}
                field="value"
              />
              <ValueChart
                title="닫힌 lot 손익 분포 관측 · USD"
                points={(analysis.distributions["closed_net_profit"] ?? []).map((value, index) => ({
                  index,
                  value,
                }))}
                field="value"
              />
            </details>
            <Records title="일별 수익률 · 비율" items={analysis.daily_returns} />
            <Records title="청산 lot" items={analysis.round_trips} />
            <Records
              title="분포 원본 (닫힌 lot만)"
              items={Object.entries(analysis.distributions).flatMap(([kind, values]) =>
                values.map((value, index) => ({ kind, index, value })),
              )}
            />
            <RawArtifact value={analysis} />
          </>
        )}
        {bars && (
          <>
            <h3>가격·bar 상태 재생</h3>
            <p>
              출처: {report?.manifest.provider} · 검증된 원본 snapshot 종가 / tick print (USD). 과거
              데이터이며 현재 거래소 가격이 아닙니다. microsecond 시각은 원본 문자열로 보존합니다.
            </p>
            <ValueChart
              title="검증된 snapshot 가격 · USD"
              points={bars.items}
              field="close"
              markers={report?.result.fills ?? []}
              cursor={cursor}
            />
            <p className="helper">
              선은 종가/tick print, 점선은 선택 bar입니다. 같은 정확한 timestamp의 체결가는
              파랑=매수·주황=매도 표식입니다. bar 내부 순서·호가 경로를 보간하지 않습니다.
            </p>
            <label className="form-field">
              재생 bar
              <input
                type="range"
                min="1"
                max={bars.items.length}
                value={cursor}
                onChange={(e) => setCursor(Number(e.target.value))}
              />
            </label>
            <p>현재 bar {cursor}</p>
            <p>
              {bar?.timestamp} · O {bar?.open} H {bar?.high} L {bar?.low} C {bar?.close} · bid{" "}
              {display(bar?.bid)} / ask {display(bar?.ask)}
            </p>
            <Records title="현재 bar 자산 상태 (주가 아님)" items={state ? [state] : []} />
            <Records
              title="가격 창 체결 표식 (정확한 체결 시각)"
              items={
                report?.result.fills.filter((f) =>
                  bars.items.some((b) => b.timestamp === f.timestamp),
                ) ?? []
              }
            />
            <Records title="원본 OHLC / tick·quote" items={bars.items} />
            <div className="starter-buttons">
              <ActionButton disabled={page === 1} onClick={() => void act(() => load(page - 1))}>
                이전 가격 창
              </ActionButton>
              <span>
                {page} · 전체 {bars.total}개
              </span>
              <ActionButton
                disabled={page * 25 >= bars.total}
                onClick={() => void act(() => load(page + 1))}
              >
                다음 가격 창
              </ActionButton>
            </div>
          </>
        )}
        <details className="result-detail">
          <summary>실행 비교·QQQ 설정</summary>
          <h3>지속 실행 비교</h3>
          <ActionButton
            disabled={!report || selected.includes(report.run_id)}
            onClick={() => {
              if (!report) return
              const next = [...selected, report.run_id].slice(-8)
              setSelected(next)
              localStorage.setItem("research-compare", JSON.stringify(next))
            }}
          >
            현재 실행을 비교에 추가
          </ActionButton>
          <ActionButton
            onClick={() => {
              setSelected([])
              localStorage.setItem("research-compare", "[]")
            }}
          >
            비교 선택 초기화
          </ActionButton>
          <ActionButton
            onClick={() =>
              void act(async () =>
                setRuns(pageSchema.parse(await api("research/library/runs?page_size=25")).items),
              )
            }
          >
            실행 목록 새로고침
          </ActionButton>
          <p>
            서버 보관함 선택 창 (최대 25건). 2~8개 선택, snapshot·범위 차이는 서버가 경고합니다.
          </p>
          <ul className="library-list">
            {runs.map((r) => (
              <li key={String(r["run_id"])}>
                <label>
                  <input
                    type="checkbox"
                    checked={selected.includes(String(r["run_id"]))}
                    onChange={(e) => {
                      const id = String(r["run_id"])
                      const next = e.target.checked
                        ? [...selected, id].slice(-8)
                        : selected.filter((v) => v !== id)
                      setSelected(next)
                      localStorage.setItem("research-compare", JSON.stringify(next))
                    }}
                  />
                  {String(r["run_id"]).slice(0, 16)} ·{" "}
                  {display((r["request"] as JsonObject)["symbol"])}
                </label>
                <ActionButton onClick={() => onRun(simulationReportSchema.parse(r))}>
                  분석할 실행 선택
                </ActionButton>
              </li>
            ))}
          </ul>
          <div className="starter-buttons">
            <ActionButton
              disabled={runPage === 1}
              onClick={() =>
                void act(async () => {
                  const result = pageSchema.parse(
                    await api(`research/library/runs?page=${runPage - 1}&page_size=25`),
                  )
                  setRuns(result.items)
                  setRunPage(runPage - 1)
                  setRunTotal(result.total)
                })
              }
            >
              비교 실행 이전
            </ActionButton>
            <span>
              {runPage} · {runTotal}건
            </span>
            <ActionButton
              disabled={runPage * 25 >= runTotal}
              onClick={() =>
                void act(async () => {
                  const result = pageSchema.parse(
                    await api(`research/library/runs?page=${runPage + 1}&page_size=25`),
                  )
                  setRuns(result.items)
                  setRunPage(runPage + 1)
                  setRunTotal(result.total)
                })
              }
            >
              비교 실행 다음
            </ActionButton>
          </div>
          <ActionButton
            disabled={selected.length < 2}
            onClick={() =>
              void act(async () => setCompare(await api("research/compare", { run_ids: selected })))
            }
          >
            선택 실행 비교
          </ActionButton>
          {compare && (
            <>
              <p>
                {compare["comparable"] === true ? "동일 기준 비교 가능" : "동일 기준 비교 불가"}
              </p>
              <Warnings items={z.array(z.string()).parse(compare["warnings"])} />
              <p>{display(compare["differences"])}</p>
              <Records
                title="실행 비교 결과"
                items={z.array(z.record(z.string(), z.unknown())).parse(compare["rows"])}
              />
            </>
          )}
          <h3>QQQ 별도 데이터</h3>
          <div className="starter-buttons">
            <ActionButton
              disabled={qqqPage === 1}
              onClick={() =>
                void act(async () => {
                  const result = pageSchema.parse(
                    await api(`research/library/datasets?q=QQQ&page=${qqqPage - 1}&page_size=25`),
                  )
                  setQqq(result.items)
                  setQqqPage(qqqPage - 1)
                  setQqqTotal(result.total)
                })
              }
            >
              QQQ snapshot 이전
            </ActionButton>
            <span>
              {qqqPage} · {qqqTotal}건
            </span>
            <ActionButton
              disabled={qqqPage * 25 >= qqqTotal}
              onClick={() =>
                void act(async () => {
                  const result = pageSchema.parse(
                    await api(`research/library/datasets?q=QQQ&page=${qqqPage + 1}&page_size=25`),
                  )
                  setQqq(result.items)
                  setQqqPage(qqqPage + 1)
                  setQqqTotal(result.total)
                })
              }
            >
              QQQ snapshot 다음
            </ActionButton>
          </div>
          <label className="form-field">
            QQQ snapshot 선택 (업로드 실행은 필수)
            <select value={snapshot} onChange={(e) => setSnapshot(e.target.value)}>
              <option value="">Yahoo 별도 취득 / demo 별도 합성</option>
              {snapshot && !qqq.some((s) => s["snapshot_id"] === snapshot) && (
                <option value={snapshot}>
                  다른 페이지에서 선택한 QQQ · {snapshot.slice(0, 12)}
                </option>
              )}
              {qqq.map((s) => (
                <option key={String(s["snapshot_id"])} value={String(s["snapshot_id"])}>
                  {display(s["provider"])} · {display(s["interval"])} ·{" "}
                  {String(s["snapshot_id"]).slice(0, 12)}
                </option>
              ))}
            </select>
          </label>
          <ActionButton
            disabled={!report}
            onClick={() =>
              void act(async () => {
                setBenchmark(
                  await api("research/benchmark", {
                    run_id: report?.run_id,
                    benchmark_symbol: "QQQ",
                    ...(snapshot ? { snapshot_id: snapshot } : {}),
                  }),
                )
              })
            }
          >
            QQQ 별도 데이터 비교
          </ActionButton>
          {benchmark && (
            <>
              <p>
                QQQ · {display(benchmark["provider"])} · {display(benchmark["snapshot_id"])}
              </p>
              <p>
                수익률 (비율): {display(benchmark["benchmark_return"])} ·{" "}
                {display(benchmark["reason"])}
              </p>
              <Warnings items={z.array(z.string()).parse(benchmark["warnings"])} />
              <Records
                title="QQQ 정규화 평가액 · 주가 아님"
                items={z.array(z.record(z.string(), z.unknown())).parse(benchmark["points"])}
              />
              <RawArtifact value={benchmark} />
            </>
          )}
        </details>
      </fieldset>
    </section>
  )
}
