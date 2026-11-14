import { Component, type ErrorInfo, type ReactNode } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Navigate, Route, Routes, useNavigate } from 'react-router-dom'
import { AlertTriangle, ArrowLeft } from 'lucide-react'
import { AppShell } from './layout/AppShell'
import { Button } from './components'

import { OverviewPage } from './pages/Overview'
import { ProjectsPage, ProjectDetailPage } from './pages/Projects'
import { ExecutionsPage, ExecutionDetailPage } from './pages/Executions'
import { BugsPage, ReportsPage, AgentsPage, AnalyticsPage } from './pages/Intelligence'
import { KnowledgePage } from './pages/Knowledge'
import { EvaluationsPage } from './pages/Evaluations'
import { SettingsPage } from './pages/Settings'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: false, staleTime: 10_000 },
    mutations: { retry: 0 },
  },
})

class ApplicationErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null }

  static getDerivedStateFromError(error: Error) {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Frontend rendering error', error, info.componentStack)
  }

  render() {
    if (this.state.error) {
      return <div className="fatal-error"><div className="empty-mark"><AlertTriangle size={20} /></div><h1>This view could not render</h1><p>{this.state.error.message}</p><Button variant="secondary" onClick={() => this.setState({ error: null })}>Try again</Button></div>
    }
    return this.props.children
  }
}

function NotFound() {
  const navigate = useNavigate()
  return <div className="not-found"><span className="eyebrow">404 · NOT FOUND</span><h1>This page is not in the workspace.</h1><p className="muted">Use the navigation to return to a supported page.</p><Button variant="secondary" onClick={() => navigate(-1)}><ArrowLeft size={15} /> Go back</Button></div>
}

export default function App() {
  return <QueryClientProvider client={queryClient}>
    <BrowserRouter>
      <ApplicationErrorBoundary>
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={<OverviewPage />} />
            <Route path="projects" element={<ProjectsPage />} />
            <Route path="projects/:projectId" element={<ProjectDetailPage />} />
            <Route path="executions" element={<ExecutionsPage />} />
            <Route path="executions/:executionId" element={<ExecutionDetailPage />} />
            <Route path="bugs" element={<BugsPage />} />
            <Route path="knowledge" element={<KnowledgePage />} />
            <Route path="agents" element={<AgentsPage />} />
            <Route path="evaluations" element={<EvaluationsPage />} />
            <Route path="reports" element={<ReportsPage />} />
            <Route path="analytics" element={<AnalyticsPage />} />
            <Route path="settings" element={<SettingsPage />} />
            <Route path="*" element={<NotFound />} />
            <Route path="home" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </ApplicationErrorBoundary>
    </BrowserRouter>
  </QueryClientProvider>
}
