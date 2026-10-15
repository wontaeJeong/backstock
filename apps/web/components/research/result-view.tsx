"use client"

import { useState } from "react"
import { money, percent, type SimulationReport } from "../../lib/research"
import { ActionButton, StatusBadge } from "../ui"
import { EquityChart } from "./equity-chart"
import { ScrollRegion } from "./scroll-region"

function saveReport(report: SimulationReport) {
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(report, null, 2)], { type: "application/json" }),
  )
  const link = document.createElement("a")
  link.href = url
  link.download = `simulation-${report.run_id.slice(0, 12)}.json`
  link.click()
  URL.revokeObjectURL(url)
}

const states: Record<string, string> = {
  filled: "체결",
  rejected: "거절",
  expired: "만료",
  cancelled: "취소",
  accepted: "접수",
}
const at = (timestamp: string) =>
  new Date(timestamp).toLocaleString("ko-KR", { timeZone: "America/New_York" })

export function ResultView({
  report,
  history,
  stale,
}: {
  report: SimulationReport
  history: SimulationReport[]
  stale: boolean
}) {
  const [page, setPage] = useState(0)
  const [orderPage, setOrderPage] = useState(0)
  const summary = report.result.summary
  const fills = report.result.fills.slice(page * 25, (page + 1) * 25)
  const orders = report.result.orders.slice(orderPage * 25, (orderPage + 1) * 25)
  const metricCards = [
    ["원금 대비 수익률", percent(summary.total_return), "거래 비용 반영 · 평가손익 포함"],
    ["순손익", money(report.metrics.net_profit), "최종 평가금액 − 원금"],
    ["최종 평가금액", money(summary.final_equity), `원금 ${money(summary.initial_cash)}`],
    ["최대 낙폭", percent(report.metrics.max_drawdown), "자산 고점 대비 최대 하락률"],
  ]
  return (
    <section className="simulation-result" aria-labelledby="result-title">
      <header className="result-heading">
        <div>
          <p className="eyebrow">실행 결과</p>
          <h2 id="result-title" tabIndex={-1}>
            시뮬레이션 결과
          </h2>
        </div>
        <StatusBadge
          label={report.result.status === "succeeded" ? "계산 완료" : "실행 미완료"}
          tone={report.result.status === "succeeded" ? "success" : "error"}
        />
      </header>
      {stale && (
        <p className="notice" role="status">
          설정이 변경되었습니다. 아래는 이전 실행 결과입니다. 다시 실행하면 새 설정을 반영합니다.
        </p>
      )}
      {report.result.status !== "succeeded" && (
        <p className="error-notice" role="alert">
          실행이 완료되지 않았습니다. 부분 결과이며 성과 비교에 사용하지 마세요.{" "}
          {report.result.failure_reason}
        </p>
      )}
      <div className="result-context">
        <strong>
          {report.request.symbol} · {report.request.strategy.name}
        </strong>
        <span>
          {report.manifest.interval} · {report.manifest.row_count}개 bar · USD
        </span>
        <span>
          {report.manifest.provider === "synthetic_demo"
            ? "합성 데이터 · 실제 시세 아님"
            : report.manifest.provider === "local_file"
              ? "사용자 파일 · 시세 출처 미검증"
              : `${report.manifest.provider} 과거 데이터`}
        </span>
      </div>
      <div className="result-limits">
        <p>{report.warnings[0]}</p>
        <p>
          {report.manifest.interval === "1d"
            ? "일봉은 초단타 유효성 검증에 사용할 수 없습니다."
            : "호가·스프레드·실제 지연·부분 체결은 미검증입니다. 분봉 수익을 초단타 실전 성과로 해석하지 마세요."}
        </p>
      </div>
      <dl className="metric-grid">
        {metricCards.map(([label, value, helper], index) => (
          <div
            className={index < 2 ? "metric-card metric-card--primary" : "metric-card"}
            key={label}
          >
            <dt>{label}</dt>
            <dd className={index < 2 && Number(summary.total_return) < 0 ? "negative" : ""}>
              {value}
            </dd>
            <small>{helper}</small>
          </div>
        ))}
      </dl>
      <div className="secondary-metrics">
        <span>
          체결 {report.metrics.fill_count}건 / 청산 {report.metrics.closed_trade_count}건
        </span>
        <span>같은 종목 단순보유 {percent(report.metrics.benchmark_return)}</span>
        <span>미실현 손익 {money(summary.unrealized_pnl)}</span>
      </div>
      {report.metrics.fill_count === 0 && (
        <p className="notice">
          체결이 없습니다. 전략 조건·지표 기간·원금과 주문 거절 사유를 확인하세요.
        </p>
      )}
      <EquityChart report={report} />
      <div className="result-actions">
        <ActionButton onClick={() => saveReport(report)}>결과 JSON 저장</ActionButton>
        <a href="#strategy-editor" className="text-link">
          규칙 수정하기 ↑
        </a>
      </div>
      <details className="result-detail">
        <summary>비용과 체결 가정 확인</summary>
        <dl className="detail-grid">
          <div>
            <dt>수수료</dt>
            <dd>
              {money(summary.commission)} ({report.request.commission_bps} bps)
            </dd>
          </div>
          <div>
            <dt>매도세</dt>
            <dd>
              {money(summary.tax)} ({report.request.sell_tax_bps} bps)
            </dd>
          </div>
          <div>
            <dt>슬리피지</dt>
            <dd>
              {money(summary.slippage)} ({report.request.slippage_bps} bps)
            </dd>
          </div>
        </dl>
        <p className="helper">
          1 bps = 0.01%. 슬리피지는 이미 체결 가격에 포함되어 있으며 순손익에서 다시 차감하지
          않습니다. 기본값은 예시이며 실제 증권사 비용이 아닙니다. 손절·익절은 종가 확정 후 다음
          bar부터 실행되는 조건입니다. 시장가·정수 주식·롱 포지션·전량 체결을 가정하며 장 마감 강제
          청산은 하지 않습니다.
        </p>
      </details>
      <details className="result-detail">
        <summary>체결 내역 ({report.metrics.fill_count}건)</summary>
        {fills.length ? (
          <>
            <ScrollRegion className="table-scroll" label="체결 내역 가로 스크롤">
              <table>
                <caption>체결 시각은 뉴욕 시간, 금액은 USD</caption>
                <thead>
                  <tr>
                    <th>체결 시각</th>
                    <th>구분</th>
                    <th>수량</th>
                    <th>체결가</th>
                    <th>수수료 / 세금</th>
                  </tr>
                </thead>
                <tbody>
                  {fills.map((fill) => (
                    <tr key={fill.fill_id}>
                      <td>{at(fill.timestamp)}</td>
                      <td>{fill.side === "buy" ? "매수" : "매도"}</td>
                      <td>{fill.quantity}주</td>
                      <td>{money(fill.execution_price)}</td>
                      <td>
                        {money(fill.commission)} / {money(fill.tax)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </ScrollRegion>
            <Pagination page={page} total={report.metrics.fill_count} onChange={setPage} />
          </>
        ) : (
          <p>체결 내역이 없습니다.</p>
        )}
      </details>
      <details className="result-detail">
        <summary>주문 상태와 판단 근거 ({report.result.orders.length}건)</summary>
        <ScrollRegion className="table-scroll" label="주문 근거 가로 스크롤">
          <table>
            <caption>원본 판단 근거와 상태를 보존합니다.</caption>
            <thead>
              <tr>
                <th>신호 시각 (뉴욕)</th>
                <th>상태</th>
                <th>판단 / 상태 근거</th>
              </tr>
            </thead>
            <tbody>
              {orders.map((order) => (
                <tr key={order.order_id}>
                  <td>{at(order.intent.submitted_at)}</td>
                  <td>{states[order.state] ?? order.state}</td>
                  <td>
                    {order.intent.reason}
                    <br />
                    <small>{order.state_reason}</small>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollRegion>
        <Pagination page={orderPage} total={report.result.orders.length} onChange={setOrderPage} />
      </details>
      <details className="result-detail">
        <summary>데이터·재현성·모든 제한</summary>
        <ul>
          {report.warnings.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
          {report.manifest.warnings.map((warning) => (
            <li key={`${warning.code}-${warning.message}`}>
              {warning.code}: {warning.message}
            </li>
          ))}
        </ul>
        <dl className="reproducibility">
          <dt>실행 ID</dt>
          <dd>
            <code>{report.run_id}</code>
          </dd>
          <dt>snapshot</dt>
          <dd>
            <code>{report.manifest.snapshot_id}</code>
          </dd>
          <dt>checksum</dt>
          <dd>
            <code>{report.manifest.normalized_checksum}</code>
          </dd>
          <dt>전략 버전</dt>
          <dd>
            <code>{report.result.metadata.strategy_version}</code>
          </dd>
          <dt>엔진 / 지표</dt>
          <dd>
            {report.result.metadata.engine_version} / {report.metrics.metric_version}
          </dd>
          <dt>소스 버전</dt>
          <dd>
            <code>{report.result.metadata.code_revision}</code>
          </dd>
          <dt>데이터 취득 시각</dt>
          <dd>{at(report.manifest.acquired_at)}</dd>
          <dt>요청 범위 (끝 제외)</dt>
          <dd>
            {at(report.manifest.range_start)} ~ {at(report.manifest.range_end)}
          </dd>
        </dl>
        <p>
          실행 ID를 보관하면 같은 서버에서 다시 열 수 있습니다. 전체 전략·비용·원장은 JSON에
          포함됩니다.
        </p>
      </details>
      {history.length > 1 && (
        <details className="result-detail">
          <summary>최근 실행 비교 ({history.length}건)</summary>
          <p className="helper">
            종목·기간·데이터가 다르면 수익률만으로 우열을 판단하지 마세요. 최근 5개 실행을
            표시합니다.
          </p>
          <ScrollRegion className="table-scroll" label="실행 비교 가로 스크롤">
            <table>
              <thead>
                <tr>
                  <th>실행 / 종목</th>
                  <th>데이터</th>
                  <th>수익률</th>
                  <th>최대 낙폭</th>
                  <th>수수료 / 슬리피지 (bps)</th>
                </tr>
              </thead>
              <tbody>
                {history.map((item) => (
                  <tr key={item.run_id}>
                    <td>
                      {item.run_id.slice(0, 8)} / {item.request.symbol}
                    </td>
                    <td>
                      {item.manifest.provider} · {item.manifest.interval} ·{" "}
                      {item.manifest.row_count} bar
                    </td>
                    <td>{percent(item.result.summary.total_return)}</td>
                    <td>{percent(item.metrics.max_drawdown)}</td>
                    <td>
                      {item.request.commission_bps} / {item.request.slippage_bps}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollRegion>
        </details>
      )}
    </section>
  )
}

function Pagination({
  page,
  total,
  onChange,
}: {
  page: number
  total: number
  onChange: (page: number) => void
}) {
  if (total <= 25) return null
  return (
    <div className="pagination">
      <ActionButton disabled={page === 0} onClick={() => onChange(page - 1)}>
        이전 25건
      </ActionButton>
      <span>
        {page + 1} / {Math.ceil(total / 25)}페이지
      </span>
      <ActionButton disabled={(page + 1) * 25 >= total} onClick={() => onChange(page + 1)}>
        다음 25건
      </ActionButton>
    </div>
  )
}
