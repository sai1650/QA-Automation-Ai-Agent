import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Area, AreaChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { ArrowUpRight, CircleCheck, CircleX, FolderKanban, Play, Plus, ShieldAlert, Workflow } from 'lucide-react'
import { Button, Card, EmptyState, ErrorState, LoadingState, PageHeader, StatusBadge } from '../components'
import { formatDate, formatDuration, shortId } from '../lib/format'
import { useWorkflowFeed, useWorkspaceSnapshot } from '../hooks'
import type { Execution } from '../types'

const chartColors = ['#7c6cf2', '#3c9ce7', '#27b07d', '#d99b39', '#e25c70', '#7b879e']

export function OverviewPage() {
  const navigate = useNavigate()
  const [now] = useState(() => new Date())
  const snapshot = useWorkspaceSnapshot()
  const workflows = useWorkflowFeed(snapshot.data?.executions.items, 30)
  const reportCounts = useMemo(() => {
    const records = workflows.data ?? []
    let passed = 0
    let failed = 0
    const severity: Record<string, number> = {}
    for (const { workflow } of records) {
      for (const result of workflow.qa_report?.execution_results ?? []) {
        if (result.status === 'PASSED') passed += 1
        if (result.status === 'FAILED') failed += 1
      }
      for (const finding of workflow.qa_report?.findings ?? workflow.bug_findings ?? []) {
        severity[finding.severity] = (severity[finding.severity] ?? 0) + 1
      }
    }
    return { passed, failed, severity, workflows: records.length }
  }, [workflows.data])
  const activity = useMemo(() => buildActivity(snapshot.data?.executions.items ?? []), [snapshot.data])
  const recent = snapshot.data?.executions.items.slice(0, 6) ?? []
  const hasData = Boolean(snapshot.data?.projects.total || snapshot.data?.executions.total)

  if (snapshot.isLoading) return <LoadingState label="Loading your QA overview" />
  if (snapshot.error || !snapshot.data) return <ErrorState message="Workspace data could not be loaded from the backend." retry={() => void snapshot.refetch()} />

  return <>
    <PageHeader eyebrow={now.toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' })} title={now.getHours() < 12 ? 'Good morning' : now.getHours() < 18 ? 'Good afternoon' : 'Good evening'} description="Your QA intelligence overview, grounded in your latest backend data." action={<Button onClick={() => navigate('/projects')}><Plus size={16} /> Create project</Button>} />
    {!hasData && <Card className="notice-card"><EmptyState title="Your workspace is ready" description="Create an authorized project to start collecting real QA activity. Dashboard metrics will appear as you run inspections." action={<Button onClick={() => navigate('/projects')}>Go to projects</Button>} /></Card>}
    <div className="metric-grid">
      <Kpi label="Total projects" value={snapshot.data.projects.total} icon={<FolderKanban size={17} />} detail="Backend project records" />
      <Kpi label="Total executions" value={snapshot.data.executions.total} icon={<Play size={17} />} detail="Latest page of 100 used for activity" />
      <Kpi label="Passed tests" value={workflows.isLoading ? '…' : reportCounts.passed} icon={<CircleCheck size={17} />} detail="From retrieved QA reports" />
      <Kpi label="Failed tests" value={workflows.isLoading ? '…' : reportCounts.failed} icon={<CircleX size={17} />} detail="From retrieved QA reports" />
      <Kpi label="Reported findings" value={workflows.isLoading ? '…' : Object.values(reportCounts.severity).reduce((sum, count) => sum + count, 0)} icon={<ShieldAlert size={17} />} detail="In retrieved workflow records" />
      <Kpi label="Workflow records" value={workflows.isLoading ? '…' : reportCounts.workflows} icon={<Workflow size={17} />} detail="Latest 30 executions checked" />
    </div>
    <div className="dashboard-grid">
      <Card className="chart-card"><div className="card-heading"><div><h2>Execution activity</h2><p className="muted">Created executions · latest 100 records</p></div><span className="chart-period">7 days</span></div>
        {activity.some((point) => point.executions > 0) ? <div className="chart-area"><ResponsiveContainer width="100%" height="100%"><AreaChart data={activity} margin={{ left: -20, right: 12, top: 10, bottom: 0 }}><defs><linearGradient id="activity-fill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#7c6cf2" stopOpacity={0.28} /><stop offset="95%" stopColor="#7c6cf2" stopOpacity={0} /></linearGradient></defs><CartesianGrid stroke="var(--border)" strokeDasharray="3 5" vertical={false} /><XAxis dataKey="day" interval={0} tickLine={false} axisLine={false} tick={{ fill: 'var(--text-muted)', fontSize: 11 }} /><YAxis allowDecimals={false} tickLine={false} axisLine={false} tick={{ fill: 'var(--text-muted)', fontSize: 11 }} /><Tooltip contentStyle={{ background: 'var(--surface-raised)', borderColor: 'var(--border)', borderRadius: 10, color: 'var(--text)' }} /><Area type="monotone" dataKey="executions" stroke="#8a7cff" strokeWidth={2} fill="url(#activity-fill)" /></AreaChart></ResponsiveContainer></div> : <EmptyState title="No activity in this window" description="Recent execution records will appear here." />}
      </Card>
      <Card className="chart-card"><div className="card-heading"><div><h2>Test outcomes</h2><p className="muted">From reports found in latest workflows</p></div></div>
        {reportCounts.passed + reportCounts.failed > 0 ? <div className="donut-wrap"><div className="donut-chart"><ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={[{ name: 'Passed', value: reportCounts.passed }, { name: 'Failed', value: reportCounts.failed }]} dataKey="value" innerRadius={62} outerRadius={83} paddingAngle={5} stroke="none">{[0, 1].map((index) => <Cell key={index} fill={index === 0 ? '#31bd8b' : '#e15e72'} />)}</Pie><Tooltip contentStyle={{ background: 'var(--surface-raised)', borderColor: 'var(--border)', borderRadius: 10, color: 'var(--text)' }} /></PieChart></ResponsiveContainer><div className="donut-center"><strong>{reportCounts.passed + reportCounts.failed}</strong><span>tests</span></div></div><div className="legend-stack"><div><span className="legend-dot green" /><span>Passed</span><strong>{reportCounts.passed}</strong></div><div><span className="legend-dot red" /><span>Failed</span><strong>{reportCounts.failed}</strong></div></div></div> : <EmptyState title="No report outcomes yet" description="Complete a QA workflow to populate test results." />}
      </Card>
      <Card className="chart-card severity-chart"><div className="card-heading"><div><h2>Finding severity</h2><p className="muted">AI-generated findings · available reports</p></div></div>
        {Object.keys(reportCounts.severity).length ? <div className="severity-bars">{['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO'].map((name, index) => {
          const value = reportCounts.severity[name] ?? 0
          const max = Math.max(1, ...Object.values(reportCounts.severity))
          return <div className="severity-row" key={name}><span>{name}</span><div className="severity-track"><div style={{ width: `${(value / max) * 100}%`, background: chartColors[index] }} /></div><strong>{value}</strong></div>
        })}</div> : <EmptyState title="No bug findings recorded" description="Severity distribution appears when reports contain findings." />}
      </Card>
      <Card className="recent-card"><div className="card-heading"><div><h2>Recent executions</h2><p className="muted">Latest backend records</p></div><Button variant="ghost" onClick={() => navigate('/executions')}>View all <ArrowUpRight size={14} /></Button></div>
        {recent.length ? <div className="recent-list">{recent.map((item) => <RecentExecution key={item.id} execution={item} projectName={snapshot.data!.projects.items.find((project) => project.id === item.project_id)?.name ?? shortId(item.project_id)} onOpen={() => navigate(`/executions/${item.id}`)} />)}</div> : <EmptyState title="No recent executions" description="Queue an execution from a project to see activity." />}
      </Card>
    </div>
    {workflows.error && <p className="muted small-note">Some workflow records could not be retrieved; report-derived metrics may be incomplete.</p>}
  </>
}

function Kpi({ label, value, icon, detail }: { label: string; value: string | number; icon: React.ReactNode; detail: string }) {
  return <Card className="kpi-card"><div className="kpi-top"><span className="kpi-icon">{icon}</span><span className="kpi-label">{label}</span></div><strong className="kpi-value">{value}</strong><span className="kpi-detail">{detail}</span></Card>
}

function RecentExecution({ execution, projectName, onOpen }: { execution: Execution; projectName: string; onOpen: () => void }) {
  return <button className="recent-row" onClick={onOpen}><div className="recent-type-icon"><Play size={15} /></div><div className="recent-primary"><strong>{projectName}</strong><span>{shortId(execution.id)} · {formatDate(execution.created_at, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}</span></div><StatusBadge status={execution.status} /><span className="recent-duration">{formatDuration(execution.duration_ms)}</span><ArrowUpRight size={15} /></button>
}

function buildActivity(executions: Execution[]) {
  const now = new Date()
  const days = Array.from({ length: 7 }, (_, index) => {
    const date = new Date(now)
    date.setDate(now.getDate() - (6 - index))
    return { iso: localDateKey(date), day: date.toLocaleDateString(undefined, { weekday: 'short' }), executions: 0 }
  })
  const byDay = new Map(days.map((day) => [day.iso, day]))
  for (const execution of executions) {
    const date = new Date(execution.created_at)
    if (Number.isNaN(date.getTime())) continue
    const day = byDay.get(localDateKey(date))
    if (day) day.executions += 1
  }
  return days
}

function localDateKey(date: Date) {
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${date.getFullYear()}-${month}-${day}`
}
