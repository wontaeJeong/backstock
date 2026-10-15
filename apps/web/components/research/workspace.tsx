/* biome-ignore-all lint/complexity/useLiteralKeys: TypeScript requires indexed access for server JSON records. */
"use client"

import { type ChangeEvent, type FormEvent, useLayoutEffect, useState } from "react"
import { z } from "zod"
import { apiErrorMessage } from "../../lib/api-error"
import { importDraft } from "../../lib/features"
import {
  buildRequest,
  buildStrategy,
  type Draft,
  defaultDraft,
  type SimulationReport,
  simulationReportSchema,
  starterDraft,
} from "../../lib/research"
import { ActionButton, FormField, StatusBadge } from "../ui"
import { AnalysisPanel } from "./analysis-panel"
import { DataControls } from "./data-controls"
import { ExecutionControls } from "./execution-controls"
import { ExperimentPanel } from "./experiment-panel"
import { LibraryPanel } from "./library-panel"
import { PaperPanel } from "./paper-panel"
import { ResultView } from "./result-view"
import { RuleBuilder } from "./rule-builder"
import { StrategyJson } from "./strategy-json"

function focusInMain(target: HTMLElement | null) {
  const main = target?.closest("main")
  if (!target || !main) return
  target.focus({ preventScroll: true })
  main.scrollTo({
    top:
      main.scrollTop + target.getBoundingClientRect().top - main.getBoundingClientRect().top - 16,
    behavior: "instant",
  })
}

async function responseJson(response: Response): Promise<unknown> {
  const data: unknown = await response.json()
  if (!response.ok) {
    throw new Error(apiErrorMessage(data, response.status))
  }
  return data
}

export function ResearchWorkspace() {
  const [draft, setDraft] = useState(defaultDraft)
  const [snapshotId, setSnapshotId] = useState<string>()
  const [adjustment, setAdjustment] = useState<"raw" | "total_return_adjusted">("raw")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")
  const [failureId, setFailureId] = useState(0)
  const [failedAttempt, setFailedAttempt] = useState(false)
  const [report, setReport] = useState<SimulationReport>()
  const [history, setHistory] = useState<SimulationReport[]>([])
  const [signature, setSignature] = useState("")
  const [restoreId, setRestoreId] = useState("")
  const [panel, setPanel] = useState("전략 편집")
  useLayoutEffect(() => {
    if (panel !== "전략 편집") focusInMain(document.getElementById("workbench-panel-title"))
  }, [panel])
  useLayoutEffect(() => {
    if (!report || panel !== "전략 편집") return
    focusInMain(document.getElementById("result-title"))
  }, [report, panel])
  useLayoutEffect(() => {
    if (error && !busy && failureId > 0) focusInMain(document.getElementById("execution-error"))
  }, [error, busy, failureId])
  const fingerprint = JSON.stringify({ draft, snapshotId })
  const update = <K extends keyof Draft>(key: K, value: Draft[K]) => {
    const next =
      key === "advancedJson" && typeof value === "string"
        ? importDraft(draft, value)
        : { ...draft, [key]: value }
    setDraft(next)
    if (next.symbol !== draft.symbol || next.interval !== draft.interval) setSnapshotId(undefined)
    if (["symbol", "interval", "start", "end"].includes(key)) setSnapshotId(undefined)
    setError("")
  }

  function showResult(next: SimulationReport, nextSignature: string) {
    setFailedAttempt(false)
    setReport(next)
    setSignature(nextSignature)
    if (next.result.status === "succeeded")
      setHistory((previous) =>
        [next, ...previous.filter((item) => item.run_id !== next.run_id)].slice(0, 5),
      )
  }

  function showError(message: string) {
    setError(message)
    setFailureId((previous) => previous + 1)
    setFailedAttempt(true)
  }

  async function run(demo = false) {
    setError("")
    const chosen = demo ? { ...draft, source: "demo" as const } : draft
    try {
      const payload = buildRequest(chosen, snapshotId)
      setBusy(true)
      if (demo) setDraft(chosen)
      const response = await fetch("/api/research/simulations", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload),
      })
      const next = simulationReportSchema.parse(await responseJson(response))
      showResult(next, JSON.stringify({ draft: chosen, snapshotId }))
    } catch (failure) {
      showError(
        failure instanceof z.ZodError
          ? "숫자·조건 입력값 또는 API 응답 형식을 확인하세요. 잘못된 결과는 표시하지 않습니다."
          : failure instanceof Error
            ? failure.message
            : "실행 중 오류가 발생했습니다.",
      )
    } finally {
      setBusy(false)
    }
  }

  async function upload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    if (!file) return
    setSnapshotId(undefined)
    setError("")
    if (file.size > 25 * 1024 * 1024) {
      showError("파일은 25 MiB 이하여야 합니다.")
      return
    }
    setBusy(true)
    try {
      const query = new URLSearchParams({
        instrument_id: `NASDAQ:${draft.symbol}`,
        symbol: draft.symbol,
        exchange: "NASDAQ",
        currency: "USD",
        timezone: "America/New_York",
        interval: draft.interval,
        price_adjustment: adjustment,
        volume_adjustment: "raw",
        start: `${draft.start}T00:00:00Z`,
        end: `${draft.end}T00:00:00Z`,
      })
      const response = await fetch(`/api/research/datasets?${query}`, {
        method: "POST",
        headers: {
          "content-type": file.name.toLowerCase().endsWith(".parquet")
            ? "application/vnd.apache.parquet"
            : "text/csv",
          "x-filename": encodeURIComponent(file.name),
        },
        body: file,
      })
      const data = z
        .object({ snapshot_id: z.string().regex(/^[a-f0-9]{64}$/) })
        .parse(await responseJson(response))
      setSnapshotId(data.snapshot_id)
    } catch (failure) {
      showError(
        failure instanceof Error && !(failure instanceof z.ZodError)
          ? failure.message
          : "파일 검증에 실패했습니다. 컬럼·시간대·주기·기간을 확인하세요.",
      )
    } finally {
      setBusy(false)
      event.target.value = ""
    }
  }

  async function restore() {
    if (!/^[a-f0-9]{64}$/.test(restoreId)) {
      showError("64자리 실행 ID를 입력하세요.")
      return
    }
    setBusy(true)
    setError("")
    try {
      const response = await fetch(`/api/research/simulations/${restoreId}`)
      showResult(simulationReportSchema.parse(await responseJson(response)), "restored")
    } catch (failure) {
      showError(failure instanceof Error ? failure.message : "실행 결과를 불러오지 못했습니다.")
    } finally {
      setBusy(false)
    }
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    void run()
  }
  let preview = "입력을 완료하면 JSON 전략을 확인할 수 있습니다."
  try {
    preview = JSON.stringify(buildStrategy(draft), null, 2)
  } catch {
    /* Keep partial form edits. */
  }

  return (
    <main id="main-content" className="main-content research-main">
      <header className="research-header">
        <div>
          <p className="eyebrow">나스닥 전략 연구실</p>
          <h1>
            내 규칙으로,
            <br className="mobile-break" /> 과거를 검증하다
          </h1>
          <p>코드 없이 매매 조건을 만들고, 원금 대비 수익과 손실 위험을 확인하세요.</p>
        </div>
        <StatusBadge label="실주문 없음 · 연구용 MVP" tone="info" />
      </header>
      <p className="research-disclaimer">
        과거 성과는 미래 수익을 보장하지 않습니다. 분봉·tick/quote 재생은 연구 시나리오이며 실제
        호가 queue·체결 지연·초단타 실전 유효성을 검증하지 않습니다.
      </p>
      <nav className="workbench-nav" aria-label="연구 작업 선택">
        {["전략 편집", "보관함", "상세 분석", "실험", "Paper 연습"].map((name) => (
          <ActionButton key={name} aria-pressed={panel === name} onClick={() => setPanel(name)}>
            {name}
          </ActionButton>
        ))}
      </nav>
      {panel === "보관함" && (
        <LibraryPanel
          strategy={() => buildStrategy(draft)}
          onStrategy={(value) => update("advancedJson", JSON.stringify(value, null, 2))}
          onSnapshot={(value) => {
            setSnapshotId(String(value["snapshot_id"]))
            setDraft((previous) => ({
              ...previous,
              source: "snapshot",
              symbol: String(value["canonical_symbol"]) as Draft["symbol"],
              interval: String(value["interval"]) as Draft["interval"],
            }))
          }}
          onRun={(value) => {
            showResult(value, "restored")
            setPanel("전략 편집")
          }}
        />
      )}
      {panel === "상세 분석" && (
        <AnalysisPanel report={report} onRun={(value) => showResult(value, "restored")} />
      )}
      {panel === "실험" && (
        <ExperimentPanel
          request={() => buildRequest(draft, snapshotId)}
          onRun={(value) => {
            showResult(value, "restored")
            setPanel("상세 분석")
          }}
        />
      )}
      {panel === "Paper 연습" && <PaperPanel />}
      {error && (
        <div className="error-notice" id="execution-error" role="alert" tabIndex={-1}>
          <strong>실행하지 못했습니다.</strong>
          <p>{error}</p>
          <p>입력은 보존되어 있습니다. 설정을 확인한 뒤 다시 시도하세요.</p>
          <ActionButton
            onClick={() =>
              focusInMain(
                document.querySelector<HTMLElement>(
                  draft.advancedJson !== undefined
                    ? "#strategy-editor textarea"
                    : "#strategy-editor select",
                ),
              )
            }
          >
            입력 다시 확인
          </ActionButton>
        </div>
      )}
      {busy && (
        <p className="notice" role="status">
          데이터를 확인하고 계산하고 있습니다. 완료 전까지 중복 실행을 막습니다.
        </p>
      )}
      <div className="research-grid" hidden={panel !== "전략 편집"}>
        <form className="strategy-editor" id="strategy-editor" onSubmit={submit}>
          <fieldset disabled={busy} className="editor-fieldset">
            <legend className="visually-hidden">전략과 실행 설정</legend>
            <DataControls
              draft={draft}
              update={update}
              onUpload={(event) => void upload(event)}
              snapshotId={snapshotId}
              adjustment={adjustment}
              onAdjustment={(value) => {
                setAdjustment(value)
                setSnapshotId(undefined)
              }}
            />
            <ExecutionControls draft={draft} update={update} />
            <details
              className="editor-disclosure"
              open={draft.advancedJson !== undefined || undefined}
            >
              <summary>전략 JSON 편집·가져오기·내보내기</summary>
              <StrategyJson draft={draft} onChange={(text) => update("advancedJson", text)} />
            </details>
            <section className="editor-section" aria-labelledby="strategy-heading">
              <fieldset className="editor-fieldset" disabled={draft.advancedJson !== undefined}>
                <h3 id="strategy-heading">
                  <span className="editor-step">02</span> 나의 매매 규칙
                </h3>
                <FormField
                  id="strategy-name"
                  label="전략 이름"
                  value={draft.name}
                  onChange={(event) => update("name", event.target.value)}
                  maxLength={200}
                  required
                />
                <p className="helper">
                  템플릿에서 시작하거나 모든 조건을 직접 바꾸세요. 어떤 전략도 수익을 보장하지
                  않습니다.
                </p>
                <div className="starter-buttons">
                  <ActionButton onClick={() => setDraft(starterDraft("trend", draft))}>
                    이동평균 교차
                  </ActionButton>
                  <ActionButton onClick={() => setDraft(starterDraft("reversion", draft))}>
                    RSI 되돌림
                  </ActionButton>
                  <ActionButton onClick={() => setDraft(starterDraft("custom", draft))}>
                    직접 조건 만들기
                  </ActionButton>
                </div>
                <details className="editor-disclosure" open>
                  <summary>매수 조건</summary>
                  <RuleBuilder
                    title="매수"
                    group={draft.entry}
                    onChange={(value) => update("entry", value)}
                  />
                </details>
                <details className="editor-disclosure">
                  <summary>매도 조건</summary>
                  <RuleBuilder
                    title="매도"
                    group={draft.exit}
                    onChange={(value) => update("exit", value)}
                  />
                </details>
              </fieldset>
            </section>
            <details className="editor-section editor-disclosure">
              <summary>03 · 손절·익절·보유 기간</summary>
              <fieldset className="editor-fieldset" disabled={draft.advancedJson !== undefined}>
                <div className="form-grid">
                  <FormField
                    id="stop-loss"
                    label="손절 (%)"
                    helper="비우면 사용 안 함"
                    type="number"
                    min="0.01"
                    max="100"
                    step="0.01"
                    value={draft.stopLoss}
                    onChange={(event) => update("stopLoss", event.target.value)}
                  />
                  <FormField
                    id="take-profit"
                    label="익절 (%)"
                    type="number"
                    min="0.01"
                    max="100"
                    step="0.01"
                    value={draft.takeProfit}
                    onChange={(event) => update("takeProfit", event.target.value)}
                  />
                </div>
                <FormField
                  id="holding-bars"
                  label="최대 보유 bar 수"
                  helper="비우면 기간 제한 없음. 장 마감 자동 청산은 하지 않습니다."
                  type="number"
                  min="1"
                  max="3000"
                  value={draft.holdingBars}
                  onChange={(event) => update("holdingBars", event.target.value)}
                />
                <p className="helper">
                  종가로 판단하는 청산 조건입니다. 장중 stop 주문이나 손실 상한 보장이 아닙니다.
                </p>
              </fieldset>
            </details>
            <details className="editor-section editor-disclosure" open>
              <summary>04 · 매매 비용과 불리한 체결 가정</summary>
              <div className="form-grid">
                <FormField
                  id="commission"
                  label="수수료 (bps / 매수·매도 각각)"
                  type="number"
                  min="0"
                  max="100"
                  step="0.1"
                  value={draft.commission}
                  onChange={(event) => update("commission", event.target.value)}
                  required
                />
                <FormField
                  id="slippage"
                  label="슬리피지 (bps / 매수·매도 각각)"
                  type="number"
                  min="0"
                  max="100"
                  step="0.1"
                  value={draft.slippage}
                  onChange={(event) => update("slippage", event.target.value)}
                  required
                />
              </div>
              <FormField
                id="sell-tax"
                label="매도세 (bps)"
                type="number"
                min="0"
                max="100"
                step="0.1"
                value={draft.tax}
                onChange={(event) => update("tax", event.target.value)}
                required
              />
              <p className="helper">
                1 bps = 0.01%. 기본값은 예시입니다. 비용을 높여 다시 실행하면 잦은 매매가 비용에
                얼마나 민감한지 비교할 수 있습니다.
              </p>
            </details>
            <div className="run-actions">
              <ActionButton type="submit" variant="primary" loading={busy}>
                시뮬레이션 실행
              </ActionButton>
              <ActionButton onClick={() => void run(true)} disabled={busy}>
                합성 데모로 실행
              </ActionButton>
            </div>
            <details className="editor-section editor-disclosure">
              <summary>전략 JSON 확인</summary>
              <pre className="json-preview">{preview}</pre>
            </details>
          </fieldset>
        </form>
        <div className="research-output">
          {report ? (
            <ResultView
              key={report.run_id}
              report={report}
              history={history}
              stale={signature !== fingerprint}
              failedAttempt={failedAttempt}
            />
          ) : (
            <section className="empty-result">
              <div className="empty-chart" aria-hidden="true">
                <span />
                <span />
                <span />
                <span />
                <span />
                <span />
                <span />
              </div>
              <p className="eyebrow">아이디어에서 근거로</p>
              <h2>아직 실행한 시뮬레이션이 없습니다.</h2>
              <p>
                종목과 원금을 선택하고 매수·매도 조건을 바꿔보세요. 실제 엔진이 주문·비용·포지션을
                계산한 뒤 결과를 보여줍니다.
              </p>
              <ol>
                <li>조건과 데이터 선택</li>
                <li>비용을 반영한 과거 시뮬레이션</li>
                <li>순수익·낙폭·거래 근거 확인</li>
              </ol>
              <p className="helper">
                빠른 체험은 ‘합성 데모로 실행’을 사용하세요. 합성 결과와 실제 시세 결과는 명확히
                구분합니다.
              </p>
            </section>
          )}
          <details className="result-detail restore-panel">
            <summary>저장한 실행 다시 열기</summary>
            <FormField
              id="restore-id"
              label="실행 ID"
              value={restoreId}
              onChange={(event) => setRestoreId(event.target.value.trim())}
              maxLength={64}
              helper="같은 서버의 저장소에 결과가 남아 있어야 합니다. 편집 중인 폼을 덮어쓰지 않습니다."
            />
            <ActionButton disabled={busy} onClick={() => void restore()}>
              실행 결과 불러오기
            </ActionButton>
          </details>
        </div>
      </div>
    </main>
  )
}
