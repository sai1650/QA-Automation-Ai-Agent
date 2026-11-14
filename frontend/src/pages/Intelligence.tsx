import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Download, ExternalLink, Search, Workflow as WorkflowIcon } from 'lucide-react'
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Button, Card, EmptyState, ErrorState, PageHeader, SelectField, StatusBadge, LoadingState, Modal } from '../components'
import { formatDate, shortId } from '../lib/format'
import { projectName, useWorkflowFeed, useWorkspaceSnapshot, type WorkflowRecord } from '../hooks'
import type { BugFinding, QAReport } from '../types'

export function BugsPage() {
  const [query, setQuery] = useState('')
  const [severity, setSeverity] = useState('')
  const [projectId, setProjectId] = useState('')
  const snapshot = useWorkspaceSnapshot()
  const workflows = useWorkflowFeed(snapshot.data?.executions.items, 50)
  const findings = useMemo(() => (workflows.data ?? []).flatMap(({ execution, workflow }) =>
    (workflow.qa_report?.findings ?? workflow.bug_findings).map((finding) => ({ finding, execution })),
  ).filter(({ finding, execution }) => {
    const text = `${finding.title} ${finding.description} ${finding.probable_root_cause}`.toLowerCase()
    return (!query || text.includes(query.toLowerCase())) &&
      (!severity || finding.severity === severity) &&
      (!projectId || execution.project_id === projectId)
  }), [workflows.data, query, severity, projectId])
  if (snapshot.isLoading || workflows.isLoading) return <LoadingState label="Loading workflow findings" />
  if (snapshot.error) return <ErrorState message="Execution data could not be loaded." retry={() => void snapshot.refetch()} />
  return <>
    <PageHeader eyebrow="Intelligence" title="Bug intelligence" description="Evidence-linked AI findings retrieved from persisted QA workflows. Findings are hypotheses, not confirmed defects." />
    <Card className="toolbar-card">
      <label className="toolbar-search"><Search size={16} /><input placeholder="Search findings…" aria-label="Search findings" value={query} onChange={(event) => setQuery(event.target.value)} /></label>
      <SelectField label="Severity" value={severity} onChange={(event) => setSeverity(event.target.value)}><option value="">All severities</option>{['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO'].map((value) => <option key={value}>{value}</option>)}</SelectField>
      <SelectField label="Project" value={projectId} onChange={(event) => setProjectId(event.target.value)}><option value="">All projects</option>{snapshot.data?.projects.items.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}</SelectField>
    </Card>
    {workflows.error && <p className="muted small-note">Some workflow states could not be retrieved. Findings shown may be incomplete.</p>}
    {findings.length ? <div className="finding-grid">{findings.map(({ finding, execution }) => <FindingCard key={`${execution.id}-${finding.bug_id}`} finding={finding} executionId={execution.id} project={projectName(snapshot.data?.projects.items, execution.project_id)} createdAt={execution.created_at} />)}</div>
      : <EmptyState title={query || severity || projectId ? 'No matching findings' : 'No findings available'} description="Findings appear after an execution has a persisted QA workflow report. No defects are synthesized for this view." />}
  </>
}

function FindingCard({ finding, executionId, project, createdAt }: { finding: BugFinding; executionId: string; project: string; createdAt: string }) {
  const navigate = useNavigate()
  return <Card className="finding-card-large">
    <div className="finding-title"><span className="bug-id">{finding.bug_id}</span><StatusBadge status={finding.severity} /></div>
    <h2>{finding.title}</h2><p>{finding.description}</p>
    <div className="finding-origin"><span>{project}</span><span>{formatDate(createdAt)}</span><button onClick={() => navigate(`/executions/${executionId}`)}>Execution {shortId(executionId)} <ExternalLink size={13} /></button></div>
    <div className="hypothesis-callout"><strong>AI-generated hypothesis</strong><span>Root cause: {finding.probable_root_cause}</span></div>
    <div className="finding-meta-row"><span>Confidence</span><strong>{(finding.confidence_score * 100).toFixed(0)}%</strong><span className="muted">Model-assessed, not calibrated.</span></div>
    <details className="evidence-details"><summary>Evidence and recommended action</summary><div className="evidence-pills">{finding.supporting_evidence.map((item) => <code key={item}>{item}</code>)}</div><p>{finding.recommended_action}</p>
      {finding.historical_references.length > 0 && <div className="history-note"><strong>Historical references</strong><span>{finding.historical_references.join(', ')}</span><small>Similarity does not confirm a duplicate.</small></div>}
    </details>
  </Card>
}

export function ReportsPage() {
  const snapshot = useWorkspaceSnapshot()
  const workflows = useWorkflowFeed(snapshot.data?.executions.items, 100)
  const [search, setSearch] = useState('')
  const [selected, setSelected] = useState<WorkflowRecord | null>(null)
  const reports = useMemo(() => (workflows.data ?? []).filter(({ workflow }) => workflow.qa_report)
    .filter(({ execution, workflow }) => `${execution.id} ${workflow.qa_report?.summary ?? ''}`.toLowerCase().includes(search.toLowerCase())),
  [workflows.data, search])
  if (snapshot.isLoading || workflows.isLoading) return <LoadingState label="Loading persisted QA reports" />
  if (snapshot.error) return <ErrorState message="Execution data could not be loaded." retry={() => void snapshot.refetch()} />
  return <>
    <PageHeader eyebrow="Reporting" title="Test reports" description="Browse QA reports persisted by the multi-agent workflow. Reports are shown only when returned by the backend." />
    <Card className="toolbar-card"><label className="toolbar-search"><Search size={16} /><input aria-label="Search reports" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search report summary or execution ID…" /></label><span className="muted">{reports.length} reports loaded from latest executions</span></Card>
    {reports.length ? <Card><div className="table-scroll"><table><thead><tr><th>Report</th><th>Project</th><th>Status</th><th>Tests</th><th>Findings</th><th>Generated</th><th /></tr></thead><tbody>{reports.map((record) => {
      const report = record.workflow.qa_report!
      const failed = (report.status_counts.FAILED ?? 0) > 0
      return <tr key={record.execution.id}><td><button className="table-link" onClick={() => setSelected(record)}>{shortId(record.execution.id)}</button></td><td>{projectName(snapshot.data?.projects.items, record.execution.project_id)}</td><td><StatusBadge status={failed ? 'FAILED' : 'COMPLETED'} /></td><td>{report.execution_results.length}</td><td>{report.findings.length}</td><td>{formatDate(report.generated_at)}</td><td><Button variant="ghost" onClick={() => setSelected(record)}>View report</Button></td></tr>
    })}</tbody></table></div></Card> : <EmptyState title="No persisted reports" description="Start a QA workflow for a queued execution and complete its approval gates to produce a report." />}
    {selected?.workflow.qa_report && <ReportModal report={selected.workflow.qa_report} executionId={selected.execution.id} onClose={() => setSelected(null)} />}
  </>
}

function ReportModal({ report, executionId, onClose }: { report: QAReport; executionId: string; onClose: () => void }) {
  function download() {
    const url = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' }))
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `qa-report-${executionId}.json`
    anchor.click()
    URL.revokeObjectURL(url)
  }
  return <Modal open title="QA report" onClose={onClose} wide>
    <div className="report-modal-meta"><span>Execution <code>{shortId(executionId)}</code></span><span>{formatDate(report.generated_at)}</span><Button variant="secondary" onClick={download}><Download size={15} /> Download JSON</Button></div>
    <h3>Summary</h3><p>{report.summary}</p>
    <div className="report-counts">{Object.entries(report.status_counts).filter(([, count]) => count > 0).map(([status, count]) => <div key={status}><StatusBadge status={status} /><strong>{count}</strong></div>)}</div>
    <h3 className="subheading">Findings</h3>{report.findings.length ? report.findings.map((item) => <div className="finding-inline" key={item.bug_id}><div className="finding-title"><strong>{item.title}</strong><StatusBadge status={item.severity} /></div><p>{item.description}</p><small>AI-generated hypothesis · {(item.confidence_score * 100).toFixed(0)}% confidence</small></div>) : <p className="muted">No findings in this report.</p>}
    {report.recommendations.length > 0 && <><h3 className="subheading">Recommendations</h3><ul>{report.recommendations.map((item) => <li key={item}>{item}</li>)}</ul></>}
    {report.observed_facts.length > 0 && <details className="json-panel"><summary>Observed facts with evidence references</summary><pre>{JSON.stringify(report.observed_facts, null, 2)}</pre></details>}
  </Modal>
}

export function AgentsPage() {
  const agents = [
    { name: 'Requirement Analysis Agent', id: 'requirement_analysis', description: 'Extracts test objectives, functional requirements, constraints, ambiguities, and missing information.', stage: '01', color: 'violet' },
    { name: 'Planning Agent', id: 'planning', description: 'Builds ordered test objectives with priorities, prerequisites, risks, outcomes, and evidence requirements.', stage: '02', color: 'blue' },
    { name: 'Website Understanding Agent', id: 'website_understanding', description: 'Maps inspected page evidence and available elements to requirements without inventing features.', stage: '03', color: 'blue' },
    { name: 'Test Generation Agent', id: 'test_generation', description: 'Creates structured tests supported by requirements and the collected website evidence.', stage: '04', color: 'violet' },
    { name: 'Execution Coordination Agent', id: 'execution_coordination', description: 'Coordinates supported checks through the existing read-only Playwright inspection service.', stage: '05', color: 'teal' },
    { name: 'Bug Analysis Agent', id: 'bug_analysis', description: 'Analyzes execution outcomes and cites observed evidence; historical context remains distinct.', stage: '06', color: 'amber' },
    { name: 'Reporting Agent', id: 'reporting', description: 'Summarizes outcomes and recommendations while preserving status counts and evidence boundaries.', stage: '07', color: 'teal' },
  ]
  return <>
    <PageHeader eyebrow="Intelligence" title="AI agent architecture" description="Seven specialized roles in the LangGraph QA workflow. Live agent health and per-agent telemetry are not exposed by the backend." />
    <Card className="architecture-card"><div className="architecture-heading"><div><span className="eyebrow">LANGGRAPH PIPELINE</span><h2>One shared, stateful workflow</h2></div><StatusBadge status="APPROVAL GATES" /></div><div className="agent-flow">{agents.map((agent, index) => <div className={`agent-node node-${agent.color}`} key={agent.id}><span>{agent.stage}</span><strong>{agent.name}</strong>{index < agents.length - 1 && <div className="flow-line" />}</div>)}</div><p className="muted architecture-note">Human approval gates pause before browser inspection and again before test coordination. Browser operations remain constrained to the existing safe inspection engine.</p></Card>
    <div className="agent-grid">{agents.map((agent) => <Card className="agent-card" key={agent.id}><div className={`agent-icon node-${agent.color}`}><WorkflowIcon size={18} /></div><div className="agent-card-heading"><h2>{agent.name}</h2><StatusBadge status="WORKFLOW ROLE" /></div><p>{agent.description}</p><div className="agent-card-foot"><code>{agent.id}</code><span>Active in QA workflow</span></div></Card>)}</div>
  </>
}

export function AnalyticsPage() {
  const [now] = useState(() => Date.now())
  const snapshot = useWorkspaceSnapshot()
  const workflows = useWorkflowFeed(snapshot.data?.executions.items, 50)
  const trend = useMemo(() => {
    const result = Array.from({ length: 7 }, (_, index) => {
      const day = new Date(now)
      day.setDate(day.getDate() - (6 - index))
      return { key: day.toISOString().slice(0, 10), day: day.toLocaleDateString(undefined, { weekday: 'short' }), completed: 0, failed: 0, passedTests: 0, failedTests: 0 }
    })
    const lookup = new Map(result.map((item) => [item.key, item]))
    for (const execution of snapshot.data?.executions.items ?? []) {
      const bucket = lookup.get(new Date(execution.created_at).toISOString().slice(0, 10))
      if (!bucket) continue
      if (execution.status === 'COMPLETED') bucket.completed += 1
      if (execution.status === 'FAILED') bucket.failed += 1
    }
    for (const { execution, workflow } of workflows.data ?? []) {
      const bucket = lookup.get(new Date(execution.created_at).toISOString().slice(0, 10))
      if (!bucket) continue
      for (const item of workflow.qa_report?.execution_results ?? []) {
        if (item.status === 'PASSED') bucket.passedTests += 1
        if (item.status === 'FAILED') bucket.failedTests += 1
      }
    }
    return result
  }, [now, snapshot.data, workflows.data])
  if (snapshot.isLoading || workflows.isLoading) return <LoadingState label="Aggregating actual activity" />
  if (snapshot.error) return <ErrorState message="Analytics data could not be loaded." retry={() => void snapshot.refetch()} />
  return <>
    <PageHeader eyebrow="Reporting" title="Analytics" description="Derived from the latest backend records and persisted workflow reports; no synthetic dashboard data." />
    <div className="metric-grid analytics-metrics">
      <Card className="kpi-card"><span className="kpi-label">Projects in API page</span><strong className="kpi-value">{snapshot.data?.projects.total ?? 0}</strong><span className="kpi-detail">Total count returned by backend</span></Card>
      <Card className="kpi-card"><span className="kpi-label">Executions in API page</span><strong className="kpi-value">{snapshot.data?.executions.total ?? 0}</strong><span className="kpi-detail">Total count returned by backend</span></Card>
      <Card className="kpi-card"><span className="kpi-label">Reports retrieved</span><strong className="kpi-value">{(workflows.data ?? []).filter((item) => item.workflow.qa_report).length}</strong><span className="kpi-detail">From latest 50 executions</span></Card>
      <Card className="kpi-card"><span className="kpi-label">Failed workflow lookups</span><strong className="kpi-value">{Math.max(0, (snapshot.data?.executions.items.length ?? 0) - (workflows.data?.length ?? 0))}</strong><span className="kpi-detail">Not necessarily workflow failures</span></Card>
    </div>
    <Card className="chart-card analytics-main-chart"><div className="card-heading"><div><h2>Execution activity</h2><p className="muted">Created records and report test outcomes by day</p></div></div><div className="chart-area chart-large"><ResponsiveContainer width="100%" height="100%"><AreaChart data={trend} margin={{ left: -20, right: 12, top: 10, bottom: 0 }}><CartesianGrid stroke="var(--border)" strokeDasharray="3 5" vertical={false} /><XAxis dataKey="day" tickLine={false} axisLine={false} tick={{ fill: 'var(--text-muted)', fontSize: 11 }} /><YAxis allowDecimals={false} tickLine={false} axisLine={false} tick={{ fill: 'var(--text-muted)', fontSize: 11 }} /><Tooltip contentStyle={{ background: 'var(--surface-raised)', borderColor: 'var(--border)', borderRadius: 10, color: 'var(--text)' }} /><Area type="monotone" dataKey="completed" name="Completed executions" stroke="#27b07d" fill="#27b07d" fillOpacity={0.08} /><Area type="monotone" dataKey="failed" name="Failed executions" stroke="#e25c70" fill="#e25c70" fillOpacity={0.06} /><Area type="monotone" dataKey="passedTests" name="Passed tests in reports" stroke="#7c6cf2" fill="#7c6cf2" fillOpacity={0.05} /><Area type="monotone" dataKey="failedTests" name="Failed tests in reports" stroke="#d99b39" fill="#d99b39" fillOpacity={0.04} /></AreaChart></ResponsiveContainer></div><p className="muted chart-footnote">Report metrics are limited to retrieved workflow states. Comparison trends and causal model comparisons require compatible persisted evaluation experiments.</p></Card>
  </>
}
