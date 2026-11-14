import { Component, Suspense, lazy, type ErrorInfo, type ReactNode } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Navigate, Route, Routes, useNavigate } from 'react-router-dom'
import { AlertTriangle, ArrowLeft } from 'lucide-react'
import { AppShell } from './layout/AppShell'
import { Button, LoadingState } from './components'

const OverviewPage = lazy(() => import('./pages/Overview').then((module) => ({ default: module.OverviewPage })))
const ProjectsPage = lazy(() => import('./pages/Projects').then((module) => ({ default: module.ProjectsPage })))
const ProjectDetailPage = lazy(() => import('./pages/Projects').then((module) => ({ default: module.ProjectDetailPage })))
const ExecutionsPage = lazy(() => import('./pages/Executions').then((module) => ({ default: module.ExecutionsPage })))
const ExecutionDetailPage = lazy(() => import('./pages/Executions').then((module) => ({ default: module.ExecutionDetailPage })))
const BugsPage = lazy(() => import('./pages/Intelligence').then((module) => ({ default: module.BugsPage })))
const ReportsPage = lazy(() => import('./pages/Intelligence').then((module) => ({ default: module.ReportsPage })))
const AgentsPage = lazy(() => import('./pages/Intelligence').then((module) => ({ default: module.AgentsPage })))
const AnalyticsPage = lazy(() => import('./pages/Intelligence').then((module) => ({ default: module.AnalyticsPage })))
const KnowledgePage = lazy(() => import('./pages/Knowledge').then((module) => ({ default: module.KnowledgePage })))
const EvaluationsPage = lazy(() => import('./pages/Evaluations').then((module) => ({ default: module.EvaluationsPage })))
const SettingsPage = lazy(() => import('./pages/Settings').then((module) => ({ default: module.SettingsPage })))

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
            <Route index element={<Suspense fallback={<LoadingState />}><OverviewPage /></Suspense>} />
            <Route path="projects" element={<Suspense fallback={<LoadingState />}><ProjectsPage /></Suspense>} />
            <Route path="projects/:projectId" element={<Suspense fallback={<LoadingState />}><ProjectDetailPage /></Suspense>} />
            <Route path="executions" element={<Suspense fallback={<LoadingState />}><ExecutionsPage /></Suspense>} />
            <Route path="executions/:executionId" element={<Suspense fallback={<LoadingState />}><ExecutionDetailPage /></Suspense>} />
            <Route path="bugs" element={<Suspense fallback={<LoadingState />}><BugsPage /></Suspense>} />
            <Route path="knowledge" element={<Suspense fallback={<LoadingState />}><KnowledgePage /></Suspense>} />
            <Route path="agents" element={<Suspense fallback={<LoadingState />}><AgentsPage /></Suspense>} />
            <Route path="evaluations" element={<Suspense fallback={<LoadingState />}><EvaluationsPage /></Suspense>} />
            <Route path="reports" element={<Suspense fallback={<LoadingState />}><ReportsPage /></Suspense>} />
            <Route path="analytics" element={<Suspense fallback={<LoadingState />}><AnalyticsPage /></Suspense>} />
            <Route path="settings" element={<Suspense fallback={<LoadingState />}><SettingsPage /></Suspense>} />
            <Route path="*" element={<NotFound />} />
            <Route path="home" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </ApplicationErrorBoundary>
    </BrowserRouter>
  </QueryClientProvider>
}
