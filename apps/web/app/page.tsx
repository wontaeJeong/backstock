import { AppShell } from "../components/app-shell"
import { ResearchWorkspace } from "../components/research/workspace"

export default function HomePage() {
  return (
    <AppShell currentPath="/">
      <ResearchWorkspace />
    </AppShell>
  )
}
