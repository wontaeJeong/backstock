import { useId } from "react"
import { money, type SimulationReport } from "../../lib/research"
import { ScrollRegion } from "./scroll-region"

export function EquityChart({ report }: { report: SimulationReport }) {
  const titleId = useId()
  const descriptionId = useId()
  const points = report.result.portfolio
  const firstPoint = points[0]
  const lastPoint = points.at(-1)
  if (!firstPoint || !lastPoint) return <p>표시할 자산 데이터가 없습니다.</p>
  const all = [
    ...points.map((point) => Number(point.equity)),
    ...report.result.benchmark.map((point) => Number(point.value)),
    Number(report.config.initial_cash),
  ]
  const low = Math.min(...all) * 0.98
  const high = Math.max(...all) * 1.02
  const first = new Date(firstPoint.timestamp).getTime()
  const last = new Date(lastPoint.timestamp).getTime()
  const x = (timestamp: string) =>
    90 + ((new Date(timestamp).getTime() - first) / Math.max(last - first, 1)) * 600
  const y = (value: string | number) => 220 - ((Number(value) - low) / (high - low || 1)) * 180
  const line = points.map((point) => `${x(point.timestamp)},${y(point.equity)}`).join(" ")
  const benchmark = report.result.benchmark
    .map((point) => `${x(point.timestamp)},${y(point.value)}`)
    .join(" ")
  const time = (timestamp: string) =>
    new Date(timestamp).toLocaleString("ko-KR", {
      timeZone: "America/New_York",
      month: "short",
      day: "numeric",
      ...(report.manifest.interval !== "1d" ? { hour: "2-digit", minute: "2-digit" } : {}),
    })
  return (
    <figure className="equity-figure">
      <ScrollRegion className="chart-scroll" label="자산 변화 그래프, 좁은 화면에서 가로 스크롤">
        <svg viewBox="0 0 740 280" role="img" aria-labelledby={`${titleId} ${descriptionId}`}>
          <title id={titleId}>자산 변화 · USD · 뉴욕 시간</title>
          <desc id={descriptionId}>
            {points.length}개 평가 시점. 시작 원금 {money(report.config.initial_cash)}, 최종
            평가금액 {money(report.result.summary.final_equity)}. 청록색은 전략 자산, 점선은 같은
            종목의 비용 없는 단순보유 참고값입니다. 정확한 전체 수치는 결과 JSON에 보존됩니다.
          </desc>
          {[0, 0.5, 1].map((tick) => (
            <g key={tick}>
              <line
                x1="90"
                x2="690"
                y1={40 + tick * 180}
                y2={40 + tick * 180}
                className="chart-grid"
              />
              <text x="80" y={45 + tick * 180} textAnchor="end">
                {money(high - tick * (high - low))}
              </text>
            </g>
          ))}
          <line
            x1="90"
            x2="690"
            y1={y(report.config.initial_cash)}
            y2={y(report.config.initial_cash)}
            className="chart-baseline"
          />
          <polyline points={benchmark} className="chart-benchmark" />
          <polyline points={line} className="chart-equity" />
          <text x="90" y="253">
            {time(firstPoint.timestamp)}
          </text>
          <text x="690" y="253" textAnchor="end">
            {time(lastPoint.timestamp)}
          </text>
        </svg>
      </ScrollRegion>
      <figcaption>
        <span className="legend-strategy">━ 전략 자산</span>
        <span>┄ 같은 종목 단순보유 (비용 없음)</span>
        <span>단위 USD · 뉴욕 시간 · {points.length}개 평가 시점</span>
      </figcaption>
    </figure>
  )
}
