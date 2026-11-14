import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowUpRight, CirclePlay, RefreshCw, ShieldAlert, Workflow } from 'lucide-react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { executionsApi, projectsApi } from '../api/resources'
import { getErrorMessage } from '../api/client'
import { Badge, Button, Card, EmptyState, ErrorState, LoadingState, PageHeader, Pagination, SelectField, StatusBadge } from '../components'
import { formatDate, formatDuration, shortId } from '../lib/format'
import type { Execution, QAWorkflow } from '../types'

const PAGE_SIZE = 20

export function ExecutionsPage() {
  const [page, setPage] = useState(1)
  const [status, setStatus] = useState('')
  const [projectId, setProjectId] = useState('')
  const [search, setSearch] = useState('')
  const projects = useQuery({ queryKey: ['projects-for-filter'], queryFn: () => projectsApi.list({ page: 1, page_size: 100 }) })
  const executions = useQuery({
    queryKey: ['executions', page, status, projectId],
    queryFn: () => executionsApi.list({
      page,
      page_size: PAGE_SIZE,
      status: status || undefined,
      project_id: projectId || undefined,
    }),
    staleTime: 10_000,
  })
  const filtered = useMemo(() => (executions.data?.items ?? []).filter((item) => item.id.toLowerCase().includes(search.toLowerCase())), [executions.data, search])

  return <>
    <PageHeader eyebrow="Monitoring" title="Executions" description="Track read-only inspections and multi-agent QA workflows." />
    <Card className="toolbar-card">
      <label className="toolbar-search"><input aria-label="Search execution IDs" placeholder="Filter current page by execution ID…" value={search} onChange={(event) => setSearch(event.target.value)} /></label>
      <SelectField label="Status" value={status} onChange={(event) => { setStatus(event.target.value); setPage(1) }}>
        <option value="">All statuses</option>{['QUEUED', 'RUNNING', 'WAITING_APPROVAL', 'COMPLETED', 'FAILED', 'CANCELLED'].map((value) => <option key={value}>{value}</option>)}
      </SelectField>
      <SelectField label="Project" value={projectId} onChange={(event) => { setProjectId(event.target.value); setPage(1) }}>
        <option value="">All projects</option>{projects.data?.items.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
      </SelectField>
    </Card>
    {executions.isLoading ? <LoadingState label="Loading executions" /> : executions.error ? <ErrorState message={getErrorMessage(executions.error)} retry={() => void executions.refetch()} /> : filtered.length === 0
      ? <EmptyState title={search || status || projectId ? 'No matching executions' : 'No executions yet'} description="Create an execution from a project after confirming you are authorized to assess that target." />
      : <Card><div className="table-scroll"><table><thead><tr><th>Execution</th><th>Project</th><th>Status</th><th>Created</th><th>Started</th><th>Completed</th><th>Duration</th><th /></tr></thead><tbody>
        {filtered.map((item) => <ExecutionRow key={item.id} execution={item} projectName={projects.data?.items.find((project) => project.id === item.project_id)?.name ?? shortId(item.project_id)} />)}
      </tbody></table></div></Card>}
    {executions.data && <Pagination page={executions.data.page} pageSize={executions.data.page_size} total={executions.data.total} onChange={setPage} />}
  </>
}

function ExecutionRow({ execution, projectName }: { execution: Execution; projectName: string }) {
  const navigate = useNavigate()
  return <tr className="clickable-row" onClick={() => navigate(`/executions/${execution.id}`)}>
    <td><code>{shortId(execution.id)}</code></td><td>{projectName}</td><td><StatusBadge status={execution.status} /></td>
    <td>{formatDate(execution.created_at)}</td><td>{formatDate(execution.started_at)}</td><td>{formatDate(execution.completed_at)}</td><td>{formatDuration(execution.duration_ms)}</td><td><ArrowUpRight size={15} /></td>
  </tr>
}

export function ExecutionDetailPage() {
  const { executionId = '' } = useParams()
  const queryClient = useQueryClient()
  const execution = useQuery({ queryKey: ['execution', executionId], queryFn: () => executionsApi.get(executionId), enabled: Boolean(executionId), refetchInterval: (query) => ['RUNNING', 'WAITING_APPROVAL'].includes(query.state.data?.status ?? '') ? 5000 : false })
  const project = useQuery({ queryKey: ['project', execution.data?.project_id], queryFn: () => projectsApi.get(execution.data!.project_id), enabled: Boolean(execution.data?.project_id) })
  const workflow = useQuery({ queryKey: ['workflow', executionId], queryFn: () => executionsApi.workflow(executionId), enabled: Boolean(executionId), retry: false })
  const inspection = useQuery({ queryKey: ['inspection', executionId], queryFn: () => executionsApi.inspection(executionId), enabled: Boolean(executionId), retry: false })
  const artifacts = useQuery({ queryKey: ['artifacts', executionId], queryFn: () => executionsApi.artifacts(executionId), enabled: Boolean(executionId), retry: false })
  const [actionError, setActionError] = useState('')
  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ['execution', executionId] })
    void queryClient.invalidateQueries({ queryKey: ['workflow', executionId] })
    void queryClient.invalidateQueries({ queryKey: ['inspection', executionId] })
    void queryClient.invalidateQueries({ queryKey: ['artifacts', executionId] })
  }
  const mutation = useMutation({
    mutationFn: async (action: 'inspect' | 'workflow' | 'approve' | 'reject' | 'cancel') => {
      if (action === 'inspect') return executionsApi.inspect(executionId)
      if (action === 'workflow') return executionsApi.startWorkflow(executionId)
      if (action === 'approve' || action === 'reject') return executionsApi.approveWorkflow(executionId, action === 'approve' ? 'APPROVED' : 'REJECTED')
      return executionsApi.cancel(executionId)
    },
    onSuccess: () => { setActionError(''); refresh() },
    onError: (error) => setActionError(getErrorMessage(error)),
  })
  if (execution.isLoading) return <LoadingState label="Loading execution" />
  if (execution.error || !execution.data) return <ErrorState message={getErrorMessage(execution.error)} retry={() => void execution.refetch()} />
  const item = execution.data
  const wf = workflow.data
  const canCancel = item.status === 'QUEUED' || item.status === 'WAITING_APPROVAL'
  const inspectionJson = inspection.data?.result ?? item.inspection_result ?? null
  const evidence = inspectionJson && typeof inspectionJson === 'object' ? inspectionJson as Record<string, unknown> : null
  const screenshots = artifacts.data?.items.filter((artifact) => artifact.media_type.startsWith('image/')) ?? []

  return <>
    <PageHeader eyebrow="Execution detail" title={`Run ${shortId(item.id)}`} description={project.data ? `${project.data.name} · ${project.data.base_url}` : `Project ${shortId(item.project_id)}`} action={<>
      <Button variant="secondary" onClick={refresh}><RefreshCw size={15} /> Refresh</Button>
      {item.status === 'QUEUED' && <Button onClick={() => mutation.mutate('inspect')} disabled={mutation.isPending}><CirclePlay size={16} /> Start inspection</Button>}
      {item.status === 'QUEUED' && <Button variant="secondary" onClick={() => mutation.mutate('workflow')} disabled={mutation.isPending}><Workflow size={16} /> Start AI workflow</Button>}
      {canCancel && <Button variant="danger" onClick={() => { if (window.confirm('Cancel this queued or approval-waiting execution?')) mutation.mutate('cancel') }} disabled={mutation.isPending}>Cancel</Button>}
    </>} />
    {actionError && <div className="inline-error" role="alert"><ShieldAlert size={16} />{actionError}</div>}
    <div className="execution-summary-grid">
      <MetricCard label="Status" value={<StatusBadge status={item.status} />} />
      <MetricCard label="Created" value={formatDate(item.created_at)} />
      <MetricCard label="Duration" value={formatDuration(item.duration_ms)} />
      <MetricCard label="Final URL" value={item.final_url ?? inspection.data?.final_url ?? 'Not available'} />
    </div>
    {wf?.workflow_status === 'WAITING_APPROVAL' && <Card className="approval-card"><div className="approval-copy"><Badge tone="warning">Human approval required</Badge><h2>{wf.approval_phase === 'INSPECTION' ? 'Review before browser inspection' : 'Review generated test plan'}</h2><p className="muted">{wf.approval_phase === 'INSPECTION' ? 'Approving authorizes the existing read-only browser inspection.' : 'Review the generated cases before the coordinator proceeds.'}</p></div><div className="inline-actions"><Button onClick={() => mutation.mutate('approve')} disabled={mutation.isPending}>Approve</Button><Button variant="danger" onClick={() => mutation.mutate('reject')} disabled={mutation.isPending}>Reject</Button></div></Card>}
    <div className="detail-layout">
      <div className="detail-main">
        <Card><div className="card-heading"><h2>Execution overview</h2><StatusBadge status={item.status} /></div><div className="execution-requirements">{item.requirements}</div><dl className="details-list compact"><div><dt>Execution ID</dt><dd><code>{item.id}</code></dd></div><div><dt>Project</dt><dd><Link to={`/projects/${item.project_id}`}>{project.data?.name ?? shortId(item.project_id)}</Link></dd></div><div><dt>Started</dt><dd>{formatDate(item.started_at)}</dd></div><div><dt>Completed</dt><dd>{formatDate(item.completed_at)}</dd></div></dl></Card>
        <Card><div className="card-heading"><h2>Website inspection</h2>{inspection.data && <StatusBadge status={inspection.data.status ?? item.status} />}</div>
          {inspection.isLoading ? <LoadingState /> : inspection.error ? <p className="muted">Inspection result is not available yet.</p> : inspectionJson ? <JsonPanel value={inspectionJson} /> : <EmptyState title="No inspection captured" description="A queued execution does not launch a browser. Start inspection to collect read-only page evidence." />}
        </Card>
        <Card><div className="card-heading"><h2>Artifacts</h2><span className="muted">Safe metadata only</span></div>
          {artifacts.isLoading ? <LoadingState /> : screenshots.length ? <div className="artifact-list">{screenshots.map((artifact) => <div className="artifact-item" key={artifact.name}><div className="artifact-thumb"><span>IMG</span></div><div><strong>{artifact.name}</strong><span>{artifact.media_type} · {(artifact.size_bytes / 1024).toFixed(0)} KB</span></div><Badge>Metadata</Badge></div>)}</div> : <EmptyState title="No screenshot artifacts" description="The API returns artifact metadata but does not expose a screenshot download route." />}
        </Card>
        <Card><div className="card-heading"><h2>Inspection evidence</h2></div>{evidence ? <EvidenceSections value={evidence} /> : <p className="muted">Evidence fields appear after a successful inspection.</p>}</Card>
      </div>
      <div className="detail-side">
        <Card><div className="card-heading"><h2>AI workflow</h2>{wf && <StatusBadge status={wf.workflow_status} />}</div>
          {workflow.isLoading ? <LoadingState label="Checking workflow" /> : wf ? <WorkflowPanel workflow={wf} /> : <div className="workflow-empty"><p className="muted">No persisted workflow state was returned for this execution.</p>{workflow.error && item.status !== 'QUEUED' && <small className="muted">The workflow may not have been started.</small>}</div>}
        </Card>
        {wf?.qa_report && <Card><div className="card-heading"><h2>QA report</h2><Badge tone="blue">{wf.qa_report.execution_results.length} tests</Badge></div><p>{wf.qa_report.summary}</p><div className="report-counts">{Object.entries(wf.qa_report.status_counts).filter(([, count]) => count > 0).map(([key, count]) => <div key={key}><StatusBadge status={key} /><strong>{count}</strong></div>)}</div><h3 className="subheading">Bug findings</h3>{wf.qa_report.findings.length ? wf.qa_report.findings.map((finding) => <FindingCard finding={finding} key={finding.bug_id} />) : <p className="muted">No findings in this report.</p>}</Card>}
        {wf?.errors.length ? <Card><div className="card-heading"><h2>Workflow errors</h2><Badge tone="danger">{wf.errors.length}</Badge></div>{wf.errors.map((error, index) => <pre className="compact-json" key={index}>{JSON.stringify(error, null, 2)}</pre>)}</Card> : null}
      </div>
    </div>
  </>
}

function MetricCard({ label, value }: { label: string; value: React.ReactNode }) {
  return <Card className="metric-card"><span className="muted">{label}</span><strong>{value}</strong></Card>
}

function JsonPanel({ value }: { value: unknown }) {
  return <details className="json-panel"><summary>View structured inspection data</summary><pre>{JSON.stringify(value, null, 2)}</pre></details>
}

function EvidenceSections({ value }: { value: Record<string, unknown> }) {
  const entries = Object.entries(value)
  return <div className="evidence-grid">{entries.map(([key, item]) => <div key={key}><span className="evidence-key">{key.replaceAll('_', ' ')}</span><span className="evidence-value">{typeof item === 'object' ? JSON.stringify(item) : String(item ?? '—')}</span></div>)}</div>
}

function WorkflowPanel({ workflow }: { workflow: QAWorkflow }) {
  const stages = [
    ['Requirement analysis', workflow.requirement_analysis],
    ['Test planning', workflow.testing_plan],
    ['Website understanding', workflow.website_understanding],
    ['Test generation', workflow.generated_test_cases.length ? workflow.generated_test_cases : null],
    ['Execution coordination', workflow.execution_results.length ? workflow.execution_results : null],
    ['Bug analysis', workflow.bug_findings.length ? workflow.bug_findings : null],
    ['Reporting', workflow.qa_report],
  ] as const
  return <><ol className="workflow-timeline">{stages.map(([label, data]) => <li key={label} className={data ? 'stage-complete' : ''}><span className="timeline-dot" /><div><strong>{label}</strong><span className="muted">{data ? 'Available' : 'Pending or not reached'}</span></div></li>)}</ol><dl className="details-list compact"><div><dt>Current agent</dt><dd>{workflow.current_agent ?? '—'}</dd></div><div><dt>RAG status</dt><dd>{workflow.rag_status}</dd></div><div><dt>Historical matches</dt><dd>{workflow.historical_bug_matches.length}</dd></div></dl>{workflow.warnings.map((warning) => <p className="warning-note" key={warning}>{warning}</p>)}</>
}

function FindingCard({ finding }: { finding: import('../types').BugFinding }) {
  return <div className="finding-card"><div className="finding-title"><strong>{finding.title}</strong><StatusBadge status={finding.severity} /></div><p className="muted">{finding.description}</p><div className="finding-meta">Confidence {(finding.confidence_score * 100).toFixed(0)}% · AI-generated hypothesis</div><details><summary>Root cause and evidence</summary><p>{finding.probable_root_cause}</p><p className="muted">Evidence: {finding.supporting_evidence.join(', ')}</p><p>Recommended: {finding.recommended_action}</p></details></div>
}
