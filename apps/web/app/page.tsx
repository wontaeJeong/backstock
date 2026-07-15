import { ApiHealthCheck } from "../components/api-health-check"
import { AppShell } from "../components/app-shell"
import { ResearchPanel, StatusBadge } from "../components/ui"

const foundationChecks = [
  ["API contract", "Health and error schemas are available"],
  ["Worker boundary", "Background process runs independently"],
  ["Trading safety", "Production orders are disabled"],
] as const

export default function HomePage() {
  return (
    <AppShell currentPath="/">
      <main id="main-content" className="main-content">
        <header className="page-header">
          <div>
            <p className="page-kicker" lang="en">
              BOOTSTRAP / 02
            </p>
            <h1 lang="en">Research foundation</h1>
            <p>
              데이터·전략·주문을 <span className="no-break">재현 가능하게</span> 연결합니다.
            </p>
          </div>
          <ApiHealthCheck />
        </header>

        <div className="foundation-grid">
          {foundationChecks.map(([title, description], index) => (
            <ResearchPanel key={title} title={title} description={description} language="en">
              <div className="metric-line">
                <span className="metric-line__value">{String(index + 1).padStart(2, "0")}</span>
                <StatusBadge label="Configured" tone="success" />
              </div>
            </ResearchPanel>
          ))}
        </div>

        <ResearchPanel
          title="Architecture boundary"
          description="Adapters point inward; domain logic remains framework independent."
          language="en"
          tone="recessed"
        >
          <ol className="flow-list">
            <li>Browser / API / Worker</li>
            <li>Application services</li>
            <li>Domain and interfaces</li>
            <li>Provider / broker adapters</li>
          </ol>
        </ResearchPanel>
      </main>
    </AppShell>
  )
}
