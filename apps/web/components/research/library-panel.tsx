/* biome-ignore-all lint/complexity/useLiteralKeys: TypeScript requires indexed access for server JSON records. */
"use client"
import { useCallback, useEffect, useState } from "react"
import { pageSchema } from "../../lib/feature-schemas"
import { api, downloadJson, type JsonObject } from "../../lib/features"
import { type SimulationReport, simulationReportSchema } from "../../lib/research"
import { ActionButton } from "../ui"
import { display, Field, useOperation } from "./panel-kit"

export function LibraryPanel({
  strategy,
  onStrategy,
  onSnapshot,
  onRun,
}: {
  strategy: () => unknown
  onStrategy: (v: unknown) => void
  onSnapshot: (v: JsonObject) => void
  onRun: (v: SimulationReport) => void
}) {
  const [kind, setKind] = useState("strategies"),
    [q, setQ] = useState(""),
    [page, setPage] = useState(1),
    [archived, setArchived] = useState(false)
  const [data, setData] = useState<ReturnType<typeof pageSchema.parse>>(),
    [notice, setNotice] = useState("")
  const { busy, act, feedback } = useOperation(true)
  const load = useCallback(
    async (p: number) => {
      setData(
        pageSchema.parse(
          await api(
            `research/library/${kind}?${new URLSearchParams({ q, page: String(p), page_size: "25", archived: String(archived) })}`,
          ),
        ),
      )
    },
    [kind, q, archived],
  )
  // A new category always reloads server state; search is explicitly submitted.
  useEffect(() => {
    void act(() => load(1))
    setPage(1)
  }, [load, act])
  const identity = (row: JsonObject) =>
    String(
      row[kind === "strategies" ? "strategy_id" : kind === "datasets" ? "snapshot_id" : "run_id"],
    )
  return (
    <section className="feature-panel" aria-label="서버 보관함">
      <h2 id="workbench-panel-title" tabIndex={-1}>
        보관함
      </h2>
      {feedback}
      <p role="status">{notice}</p>
      <fieldset disabled={busy}>
        <label className="form-field">
          보관함 종류
          <select value={kind} onChange={(e) => setKind(e.target.value)}>
            <option value="strategies">전략 버전</option>
            <option value="datasets">데이터 snapshot</option>
            <option value="runs">실행 결과</option>
          </select>
        </label>
        <Field label="보관함 검색" value={q} onChange={setQ} />
        <label>
          <input
            type="checkbox"
            checked={archived}
            onChange={(e) => setArchived(e.target.checked)}
          />
          보관된 항목
        </label>
        <div className="starter-buttons">
          <ActionButton
            onClick={() =>
              void act(async () => {
                setPage(1)
                await load(1)
              })
            }
          >
            검색
          </ActionButton>
          <ActionButton
            onClick={() =>
              void act(async () => {
                await api("research/library/strategies", { definition: strategy() })
                setNotice("전략 저장 완료")
                await load(page)
              })
            }
          >
            현재 전략 저장
          </ActionButton>
        </div>
        <p>변경 저장은 새 불변 버전입니다. 보관은 삭제가 아니며 원래 실행 근거를 유지합니다.</p>
        {!data?.items.length && <p>일치하는 항목이 없습니다.</p>}
        <ul className="library-list">
          {data?.items.map((row) => (
            <li key={identity(row)}>
              <strong>
                {display(
                  row["name"] ??
                    row["canonical_symbol"] ??
                    (row["request"] as JsonObject | undefined)?.["symbol"],
                )}
              </strong>
              <code>{identity(row)}</code>
              <div className="starter-buttons">
                <ActionButton
                  onClick={() =>
                    void act(async () => {
                      if (kind === "strategies") {
                        const full = await api(`research/library/strategies/${identity(row)}`)
                        onStrategy(full["definition"])
                        setNotice("전략 불러오기 완료 · 고급 JSON에서 전체 AST 편집")
                      } else if (kind === "datasets") {
                        onSnapshot(row)
                        setNotice("snapshot 재사용 선택 완료")
                      } else {
                        onRun(
                          simulationReportSchema.parse(await api(`simulations/${identity(row)}`)),
                        )
                        setNotice("실행 불러오기 완료")
                      }
                    })
                  }
                >
                  {kind === "strategies"
                    ? "전략 불러오기"
                    : kind === "datasets"
                      ? "snapshot 재사용"
                      : "실행 열기"}
                </ActionButton>
                {kind === "strategies" && (
                  <ActionButton
                    onClick={() =>
                      void act(async () => {
                        const full = await api(`research/library/strategies/${identity(row)}`)
                        const def = full["definition"] as JsonObject
                        onStrategy({ ...def, name: `${String(def["name"])} 복제` })
                        setNotice("복제본을 편집 중입니다. 저장하면 새 버전입니다.")
                      })
                    }
                  >
                    전략 복제
                  </ActionButton>
                )}
                <ActionButton onClick={() => downloadJson(row, `${kind}-${identity(row)}.json`)}>
                  항목 JSON
                </ActionButton>
                <ActionButton
                  onClick={() =>
                    void act(async () => {
                      await api(`research/library/${kind}/${identity(row)}/archive`, {
                        archived: !archived,
                      })
                      await load(page)
                    })
                  }
                >
                  {archived ? "항목 복원" : "항목 보관"}
                </ActionButton>
              </div>
            </li>
          ))}
        </ul>
        <div className="starter-buttons">
          <ActionButton
            disabled={page === 1}
            onClick={() =>
              void act(async () => {
                setPage(page - 1)
                await load(page - 1)
              })
            }
          >
            보관함 이전
          </ActionButton>
          <span>
            {page} · 전체 {data?.total ?? "미조회"}건
          </span>
          <ActionButton
            disabled={!data || page * 25 >= data.total}
            onClick={() =>
              void act(async () => {
                setPage(page + 1)
                await load(page + 1)
              })
            }
          >
            보관함 다음
          </ActionButton>
        </div>
      </fieldset>
    </section>
  )
}
