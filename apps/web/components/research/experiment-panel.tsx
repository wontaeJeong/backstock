/* biome-ignore-all lint/complexity/useLiteralKeys: TypeScript requires indexed access for server JSON records. */
"use client"
import { useEffect, useState } from "react"
import type { z } from "zod"
import { experimentSchema } from "../../lib/feature-schemas"
import { api, downloadJson, type JsonObject, numericPaths } from "../../lib/features"
import { type SimulationReport, simulationReportSchema, symbols } from "../../lib/research"
import { ActionButton } from "../ui"
import { ValueChart } from "./analysis-panel"
import {
  display,
  Field,
  RawArtifact,
  Records,
  Statistics,
  useOperation,
  Warnings,
} from "./panel-kit"

export function ExperimentPanel({
  request,
  onRun,
}: {
  request: () => JsonObject
  onRun: (r: SimulationReport) => void
}) {
  const [path, setPath] = useState("commission_bps"),
    [values, setValues] = useState("0,10"),
    [path2, setPath2] = useState(""),
    [values2, setValues2] = useState("1,5")
  const [train, setTrain] = useState("30"),
    [test, setTest] = useState("10"),
    [folds, setFolds] = useState("2")
  const [components, setComponents] = useState([
    { id: "component-1", symbol: "AAPL", weight: "0.4" },
    { id: "component-2", symbol: "MSFT", weight: "0.4" },
  ])
  const [result, setResult] = useState<z.infer<typeof experimentSchema>>(),
    [summary, setSummary] = useState<JsonObject>(),
    [saved, setSaved] = useState<string[]>([]),
    [chosen, setChosen] = useState("")
  const { busy, act, feedback } = useOperation()
  let paths: string[] = []
  try {
    paths = numericPaths(request())
  } catch {
    /* incomplete draft is preserved */
  }
  useEffect(() => {
    setSaved(JSON.parse(localStorage.getItem("research-experiments") ?? "[]") as string[])
  }, [])
  async function show(value: unknown) {
    const next = experimentSchema.parse(value)
    setResult(next)
    setSummary(undefined)
    const ids = [next.experiment_id, ...saved.filter((s) => s !== next.experiment_id)].slice(0, 25)
    setSaved(ids)
    localStorage.setItem("research-experiments", JSON.stringify(ids))
    if (next.kind === "portfolio")
      setSummary(await api(`research/experiments/${next.experiment_id}/analysis`))
  }
  async function run(kind: "grid" | "walk-forward" | "portfolio") {
    const base = request()
    const axis = (p: string, v: string) => ({
      path: p,
      values: v
        .split(",")
        .map((s) => s.trim())
        .map((s) => {
          if (!s || !Number.isFinite(Number(s)))
            throw new Error("축 값은 쉼표로 구분한 유한 숫자입니다.")
          return s
        }),
    })
    const axes = [axis(path, values), ...(path2 ? [axis(path2, values2)] : [])]
    const body =
      kind === "portfolio"
        ? {
            initial_cash: base["initial_cash"],
            components: components.map((c) => ({
              weight: c.weight,
              request: {
                ...base,
                symbol: c.symbol,
                strategy: { ...(base["strategy"] as JsonObject), universe: [`NASDAQ:${c.symbol}`] },
              },
            })),
          }
        : {
            base,
            axes,
            ...(kind === "walk-forward"
              ? { train_bars: Number(train), test_bars: Number(test), folds: Number(folds) }
              : {}),
          }
    await show(await api(`research/experiments/${kind}`, body))
  }
  const rows = result?.rows ?? result?.folds ?? result?.components ?? []
  const runIds = rows
    .flatMap((row) => [
      row["run_id"],
      row["test_run_id"],
      ...(Array.isArray(row["train_run_ids"]) ? row["train_run_ids"] : []),
    ])
    .filter((v): v is string => typeof v === "string")
  return (
    <section className="feature-panel">
      <h2 id="workbench-panel-title" tabIndex={-1}>
        실험
      </h2>
      {feedback}
      <fieldset disabled={busy}>
        <p>
          현재 편집 전략·원금·비용·실행 옵션을 기준으로 실제 엔진을 호출합니다. Grid는 in-sample이며
          과최적화 위험이 있습니다. 학습 수익률로만 선택하고 순차 test를 독립 실행합니다.
          실패·취소·미실행은 0%가 아닙니다.
        </p>
        <div className="form-grid">
          <label className="form-field">
            첫 번째 실험 축
            <select value={path} onChange={(e) => setPath(e.target.value)}>
              {paths.map((p) => (
                <option key={p}>{p}</option>
              ))}
            </select>
          </label>
          <Field label="첫 축 값 (쉼표 구분)" value={values} onChange={setValues} />
          <label className="form-field">
            두 번째 실험 축
            <select value={path2} onChange={(e) => setPath2(e.target.value)}>
              <option value="">사용 안 함</option>
              {paths.map((p) => (
                <option key={p}>{p}</option>
              ))}
            </select>
          </label>
          {path2 && <Field label="두 번째 축 값" value={values2} onChange={setValues2} />}
        </div>
        <ActionButton onClick={() => void act(() => run("grid"))}>Grid 실행</ActionButton>
        <ActionButton
          onClick={() => {
            setPath("slippage_bps")
            setValues("0,5,20")
            setPath2("spread_bps")
            setValues2("0,10")
          }}
        >
          비용 민감도 시나리오 설정
        </ActionButton>
        <div className="form-grid">
          <Field label="학습 bar" value={train} onChange={setTrain} />
          <Field label="테스트 bar" value={test} onChange={setTest} />
          <Field label="순차 fold (최대 4)" value={folds} onChange={setFolds} />
        </div>
        <ActionButton onClick={() => void act(() => run("walk-forward"))}>
          Walk-forward 실행
        </ActionButton>
        <h3>독립 고정 예산 포트폴리오</h3>
        <p>
          합계 비중 ≤1, 남은 금액은 현금. 재조정·공유 현금은 없습니다. 각 구성은 현재 전략의
          symbol만 바꿉니다. snapshot 모드는 동일 종목 snapshot이므로 다른 종목은 서버에서
          거절합니다.
        </p>
        {components.map((c, i) => (
          <div className="form-grid" key={c.id}>
            <label className="form-field">
              구성 {i + 1} 종목
              <select
                value={c.symbol}
                onChange={(e) =>
                  setComponents(
                    components.map((old, j) =>
                      j === i ? { ...old, symbol: e.target.value } : old,
                    ),
                  )
                }
              >
                {symbols.map((s) => (
                  <option key={s}>{s}</option>
                ))}
              </select>
            </label>
            <Field
              label={`구성 ${i + 1} 비중 (비율)`}
              value={c.weight}
              onChange={(v) =>
                setComponents(components.map((old, j) => (j === i ? { ...old, weight: v } : old)))
              }
            />
            <ActionButton
              disabled={components.length <= 2}
              onClick={() => setComponents(components.filter((_, j) => j !== i))}
            >
              구성 {i + 1} 제거
            </ActionButton>
          </div>
        ))}
        <ActionButton
          disabled={components.length >= 5}
          onClick={() =>
            setComponents([
              ...components,
              { id: crypto.randomUUID(), symbol: "QQQ", weight: "0.1" },
            ])
          }
        >
          구성 추가
        </ActionButton>
        <ActionButton onClick={() => void act(() => run("portfolio"))}>
          고정 예산 포트폴리오 실행
        </ActionButton>
        <h3>저장된 실험 재조회</h3>
        <label className="form-field">
          이 브라우저의 실험
          <select value={chosen} onChange={(e) => setChosen(e.target.value)}>
            <option value="">선택</option>
            {saved.map((id) => (
              <option key={id}>{id}</option>
            ))}
          </select>
        </label>
        <ActionButton
          disabled={!chosen}
          onClick={() => void act(async () => show(await api(`research/experiments/${chosen}`)))}
        >
          실험 불러오기
        </ActionButton>
        {result && (
          <>
            <h3>{result.kind} 결과</h3>
            <p>실험 ID {result.experiment_id}</p>
            <Warnings items={result.warnings} />
            {result.kind === "walk_forward" && (
              <p>학습과 OOS test는 독립 자본입니다. 복리 계좌로 이어 붙인 결과가 아닙니다.</p>
            )}
            <Records
              title="실험 행·실제 상태"
              items={rows.map((r) => ({
                ...r,
                error: r["error"] ?? (r["test"] as JsonObject | undefined)?.["error"] ?? null,
              }))}
            />
            {rows.map((r) => (
              <p key={JSON.stringify(r)}>
                {display(r["status"])} ·{" "}
                {display(r["error"] ?? (r["test"] as JsonObject | undefined)?.["error"])}{" "}
                {r["total_return"] === null ? "수익률 미정의" : ""}
              </p>
            ))}
            {summary && (
              <>
                <h3>서버 금융 요약</h3>
                <Statistics value={summary["statistics"]} />
              </>
            )}
            {result.curve && (
              <>
                <ValueChart
                  title="포트폴리오 평가액 · USD (주가 아님)"
                  points={result.curve}
                  field="equity"
                />
                <Records title="포트폴리오 전체 평가" items={result.curve} />
                <Records
                  title="공통 일별 수익률 상관 · 합성 패턴은 분산 증거 아님"
                  items={result.correlations ?? []}
                />
              </>
            )}
            <details className="result-detail">
              <summary>구성 실행 근거 열기</summary>
              {[...new Set(runIds)].map((id) => (
                <ActionButton
                  key={id}
                  onClick={() =>
                    void act(async () =>
                      onRun(simulationReportSchema.parse(await api(`simulations/${id}`))),
                    )
                  }
                >
                  실행 {id.slice(0, 12)} 열기
                </ActionButton>
              ))}
            </details>
            <ActionButton
              onClick={() => downloadJson(result, `experiment-${result.experiment_id}.json`)}
            >
              실험 JSON 내보내기
            </ActionButton>
            <RawArtifact value={result} />
          </>
        )}
      </fieldset>
    </section>
  )
}
