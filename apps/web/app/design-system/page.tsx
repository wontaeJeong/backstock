import { AppShell } from "../../components/app-shell"
import { ActionButton, FormField, ResearchPanel, StatusBadge } from "../../components/ui"

export default function DesignSystemPage() {
  return (
    <AppShell currentPath="/design-system">
      <main id="main-content" className="main-content">
        <div className="showcase">
          <header className="showcase__header">
            <p className="page-kicker" lang="en">
              DESIGN SYSTEM
            </p>
            <h1 lang="en">Primitives</h1>
            <p>
              제품 화면에 앞서 <span className="no-break">핵심 primitive 상태</span>를 검증합니다.
            </p>
          </header>

          <ResearchPanel
            title="Actions"
            description="Variant hierarchy and action feedback."
            language="en"
          >
            <div className="action-grid" lang="en">
              <ActionButton variant="primary">Primary action</ActionButton>
              <ActionButton>Secondary</ActionButton>
              <ActionButton variant="quiet">Quiet action</ActionButton>
              <ActionButton variant="destructive">Delete draft</ActionButton>
              <ActionButton disabled>Disabled</ActionButton>
              <ActionButton loading>Loading</ActionButton>
            </div>
          </ResearchPanel>

          <ResearchPanel
            title="Status"
            description="Every color state carries an explicit label."
            language="en"
          >
            <div className="component-cluster status-grid" lang="en">
              <StatusBadge label="Valid" tone="success" />
              <StatusBadge label="Warning" tone="warning" />
              <StatusBadge label="Failed" tone="error" />
              <StatusBadge label="Running" tone="info" />
              <StatusBadge label="Draft" tone="neutral" />
            </div>
          </ResearchPanel>

          <ResearchPanel title="Form fields" description="Labels and field states." language="en">
            <div className="form-grid">
              <FormField id="symbol" label="종목 코드" helper="숫자 6자리" defaultValue="005930" />
              <FormField id="disabled" label="비활성 입력" disabled defaultValue="KOSPI" />
              <FormField id="readonly" label="읽기 전용" readOnly defaultValue="KRW" />
              <FormField
                id="invalid"
                label="조회 시작일"
                error="오늘보다 앞선 날짜를 입력하세요."
                defaultValue="2026-07-16"
              />
              <FormField id="loading" label="데이터 검증" loading defaultValue="fixture.csv" />
            </div>
          </ResearchPanel>

          <div className="showcase-grid">
            <ResearchPanel title="Loading state" language="en" loading />
            <ResearchPanel title="Empty state" language="en">
              <div className="empty-state">
                <strong>아직 snapshot이 없습니다.</strong>
                <span>fixture로 첫 snapshot을 만드세요.</span>
                <ActionButton variant="quiet">수집 설정 열기</ActionButton>
              </div>
            </ResearchPanel>
            <ResearchPanel title="Error state" language="en" tone="highlighted">
              <div className="error-state">
                <strong>Provider 응답 검증에 실패했습니다.</strong>
                <span>
                  자동 fallback 없이 <span className="no-break">요청·응답</span> 원본을 점검합니다.
                </span>
                <ActionButton>다시 시도</ActionButton>
              </div>
            </ResearchPanel>
          </div>
        </div>
      </main>
    </AppShell>
  )
}
