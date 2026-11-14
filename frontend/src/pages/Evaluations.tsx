import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowDownUp, ChartNoAxesCombined, FlaskConical, Play, Search } from 'lucide-react'
import { evaluationsApi } from '../api/resources'
import { getErrorMessage } from '../api/client'
import { Badge, Button, Card, ConfirmCheckbox, EmptyState, ErrorState, LoadingState, Modal, PageHeader, Pagination, SelectField, StatusBadge, TextField } from '../components'
import { formatDate, formatDuration, shortId, titleCase } from '../lib/format'
import type { Evaluation, EvaluationAgent } from '../types'

const agentLabels: Record<EvaluationAgent, string> = {
  requirement_analysis: 'Requirement analysis',
  planning: 'Planning',
  website_understanding: 'Website understanding',
  test_generation: 'Test generation',
  bug_analysis: 'Bug analysis',
  reporting: 'Reporting',
  rag_retrieval: 'RAG retrieval',
  workflow: 'Full workflow',
}

export function EvaluationsPage() {
  const queryClient = useQueryClient()
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [runOpen, setRunOpen] = useState(false)
  const [selected, setSelected] = useState<Evaluation | null>(null)
  const [baseline, setBaseline] = useState('')
  const [candidate, setCandidate] = useState('')
  const [comparisonVisible, setComparisonVisible] = useState(false)
  const runs = useQuery({ queryKey: ['evaluations', page], queryFn: () => evaluationsApi.list(page) })
  const datasets = useQuery({ queryKey: ['evaluation-datasets'], queryFn: evaluationsApi.datasets })
  const metricDefinitions = useQuery({ queryKey: ['evaluation-metrics'], queryFn: evaluationsApi.metrics })
  const comparison = useQuery({
    queryKey: ['evaluation-comparison', baseline, candidate],
    queryFn: () => evaluationsApi.compare(baseline, candidate),
    enabled: comparisonVisible && Boolean(baseline && candidate && baseline !== candidate),
    retry: false,
  })
  const report = useQuery({ queryKey: ['evaluation-report', selected?.id], queryFn: () => evaluationsApi.report(selected!.id), enabled: Boolean(selected) })
  const visibleRuns = useMemo(() => (runs.data?.items ?? []).filter((run) => `${run.experiment_name} ${run.dataset_id} ${run.agent} ${run.model_identifier}`.toLowerCase().includes(search.toLowerCase())), [runs.data, search])

  return <>
    <PageHeader eyebrow="Intelligence" title="Evaluations" description="Review persisted benchmark experiments. Synthetic benchmark results are not production accuracy claims." action={<Button onClick={() => setRunOpen(true)} disabled={datasets.isError}><Play size={15} /> Run evaluation</Button>} />
    <div className="evaluation-overview">
      <Card className="evaluation-dataset-card"><div className="card-heading"><div><span className="eyebrow">VERSIONED DATASETS</span><h2>Benchmark catalog</h2></div><FlaskConical size={18} className="muted" /></div>
        {datasets.isLoading ? <LoadingState /> : datasets.error ? <p className="muted">Dataset catalog unavailable.</p> : datasets.data?.length ? datasets.data.map((dataset) => <div className="dataset-row" key={dataset.dataset_id}><div><strong>{dataset.name}</strong><span>{dataset.dataset_id} · v{dataset.version}</span></div><Badge tone={dataset.synthetic ? 'warning' : 'success'}>{dataset.synthetic ? 'SYNTHETIC' : 'NON-SYNTHETIC'}</Badge><span className="dataset-count">{dataset.sample_count} samples</span></div>) : <EmptyState title="No datasets" description="The backend returned an empty dataset catalog." />}
      </Card>
      <Card className="evaluation-metric-card"><div className="card-heading"><div><span className="eyebrow">METRIC DEFINITIONS</span><h2>What is measured</h2></div><ChartNoAxesCombined size={18} className="muted" /></div>
        {metricDefinitions.data?.length ? <div className="metric-definition-list">{metricDefinitions.data.slice(0, 4).map((metric) => <div key={metric.name}><strong>{titleCase(metric.name)}</strong><span>{metric.formula}</span></div>)}</div> : <p className="muted">Metric definitions are not available.</p>}
      </Card>
    </div>
    <Card className="toolbar-card"><label className="toolbar-search"><Search size={16} /><input placeholder="Search runs, datasets, agents, models…" value={search} onChange={(event) => setSearch(event.target.value)} aria-label="Search evaluation runs" /></label><span className="muted">{runs.data?.total ?? 0} persisted runs</span></Card>
    {runs.isLoading ? <LoadingState label="Loading experiment history" /> : runs.error ? <ErrorState message={getErrorMessage(runs.error)} retry={() => void runs.refetch()} /> : visibleRuns.length ? <Card><div className="table-scroll"><table><thead><tr><th>Experiment</th><th>Agent</th><th>Dataset</th><th>Provider / model</th><th>Status</th><th>Samples</th><th>Duration</th><th>Created</th><th /></tr></thead><tbody>{visibleRuns.map((run) => <tr key={run.id}><td><button className="table-link" onClick={() => setSelected(run)}>{run.experiment_name}</button><small className="table-subtext">{shortId(run.id)}</small></td><td>{agentLabels[run.agent] ?? run.agent}</td><td>{run.dataset_id} <small>v{run.dataset_version}</small></td><td>{run.provider_name}<small className="table-subtext">{run.model_identifier}</small></td><td><StatusBadge status={run.status} /></td><td>{run.completed_samples}/{run.total_samples}<small className="table-subtext">{run.failed_samples} failed · {run.skipped_samples} skipped</small></td><td>{formatDuration(run.duration_ms)}</td><td>{formatDate(run.created_at)}</td><td><Button variant="ghost" onClick={() => setSelected(run)}>Report</Button></td></tr>)}</tbody></table></div></Card> : <EmptyState title={search ? 'No matching experiments' : 'No evaluation runs yet'} description="Run a benchmark using a backend-approved dataset. The API stores aggregate metrics and sample statuses." />}
    {runs.data && <Pagination page={runs.data.page} pageSize={runs.data.page_size} total={runs.data.total} onChange={setPage} />}
    <Card className="comparison-card"><div className="card-heading"><div><h2>Compare experiments</h2><p className="muted">Metric deltas are only calculated for matching dataset/version, agent, and sample set.</p></div><ArrowDownUp size={18} className="muted" /></div>
      <div className="comparison-controls"><SelectField label="Baseline run" value={baseline} onChange={(event) => { setBaseline(event.target.value); setComparisonVisible(false) }}><option value="">Select a run</option>{(runs.data?.items ?? []).map((run) => <option value={run.id} key={run.id}>{run.experiment_name} · {shortId(run.id)}</option>)}</SelectField><SelectField label="Candidate run" value={candidate} onChange={(event) => { setCandidate(event.target.value); setComparisonVisible(false) }}><option value="">Select a run</option>{(runs.data?.items ?? []).map((run) => <option value={run.id} key={run.id}>{run.experiment_name} · {shortId(run.id)}</option>)}</SelectField><Button variant="secondary" disabled={!baseline || !candidate || baseline === candidate} onClick={() => setComparisonVisible(true)}>Compare</Button></div>
      {comparisonVisible && comparison.isLoading && <LoadingState label="Comparing experiments" />}
      {comparisonVisible && comparison.error && <div className="inline-error">{getErrorMessage(comparison.error)}</div>}
      {comparison.data && <div className="comparison-result"><StatusBadge status={comparison.data.comparable ? 'COMPLETED' : 'PARTIAL'} /><strong>{comparison.data.dataset_id} · v{comparison.data.dataset_version} · {agentLabels[comparison.data.agent]}</strong>{comparison.data.comparable && Object.keys(comparison.data.metric_deltas).length ? <div className="delta-grid">{Object.entries(comparison.data.metric_deltas).map(([key, value]) => <div key={key}><span>{key}</span><strong className={value && value > 0 ? 'positive' : value && value < 0 ? 'negative' : ''}>{value == null ? '—' : `${value > 0 ? '+' : ''}${value.toFixed(4)}`}</strong></div>)}</div> : <p className="muted">Runs are not comparable or share no numeric metrics.</p>}{comparison.data.limitations.map((item) => <p className="muted small-note" key={item}>{item}</p>)}</div>}
    </Card>
    <EvaluationRunModal open={runOpen} datasets={datasets.data ?? []} onClose={() => setRunOpen(false)} onCompleted={() => { setRunOpen(false); void queryClient.invalidateQueries({ queryKey: ['evaluations'] }) }} />
    <Modal open={Boolean(selected)} title="Evaluation report" onClose={() => setSelected(null)} wide>
      {report.isLoading ? <LoadingState /> : report.error ? <ErrorState message={getErrorMessage(report.error)} retry={() => void report.refetch()} /> : report.data ? <EvaluationReport evaluation={report.data} /> : null}
    </Modal>
  </>
}

function EvaluationRunModal({ open, datasets, onClose, onCompleted }: { open: boolean; datasets: Array<{ dataset_id: string; version: string; name: string; synthetic: boolean; agents: EvaluationAgent[] }>; onClose: () => void; onCompleted: () => void }) {
  const [datasetId, setDatasetId] = useState('')
  const [agent, setAgent] = useState<EvaluationAgent | ''>('')
  const [repeatCount, setRepeatCount] = useState('1')
  const [ragEnabled, setRagEnabled] = useState(false)
  const [approval, setApproval] = useState(false)
  const [errorMessage, setErrorMessage] = useState('')
  const dataset = datasets.find((item) => item.dataset_id === datasetId)
  const agents = dataset?.agents ?? []
  const mutation = useMutation({
    mutationFn: () => {
      if (!datasetId || !agent) throw new Error('Select a dataset and evaluator before starting a run.')
      return evaluationsApi.run({
        dataset_id: datasetId,
        agent,
        repeat_count: Number(repeatCount),
        provider_mode: 'live',
        rag_enabled: agent === 'rag_retrieval' ? true : ragEnabled,
        ...(agent === 'workflow' ? { approval_confirmed: true } : {}),
      })
    },
    onSuccess: onCompleted,
    onError: (error) => setErrorMessage(getErrorMessage(error)),
  })
  return <Modal open={open} title="Run benchmark evaluation" onClose={onClose}>
    <p className="muted form-note">Live runs use the configured local Ollama provider. Models are not downloaded automatically. RAG retrieval uses the configured local embedding model.</p>
    {errorMessage && <div className="form-error" role="alert">{errorMessage}</div>}
    <form className="stack-form" onSubmit={(event) => { event.preventDefault(); if (datasetId && agent) mutation.mutate() }}>
      <SelectField label="Versioned dataset" required value={datasetId} onChange={(event) => { setDatasetId(event.target.value); setAgent('') }}><option value="">Select dataset</option>{datasets.map((item) => <option key={item.dataset_id} value={item.dataset_id}>{item.name} · v{item.version}{item.synthetic ? ' · synthetic' : ''}</option>)}</SelectField>
      <SelectField label="Agent" required value={agent} onChange={(event) => setAgent(event.target.value as EvaluationAgent)}><option value="">Select evaluator</option>{agents.map((item) => <option key={item} value={item}>{agentLabels[item] ?? item}</option>)}</SelectField>
      <TextField label="Repeat count (1–5)" type="number" min={1} max={5} value={repeatCount} onChange={(event) => setRepeatCount(event.target.value)} />
      {agent !== 'rag_retrieval' && <ConfirmCheckbox checked={ragEnabled} onChange={setRagEnabled}>Enable historical context for bug-analysis evaluation where configured.</ConfirmCheckbox>}
      {agent === 'workflow' && <ConfirmCheckbox checked={approval} onChange={setApproval}>I approve this synthetic workflow benchmark to pass its simulated inspection and test-plan gates.</ConfirmCheckbox>}
      <div className="modal-actions"><Button type="button" variant="secondary" onClick={onClose}>Cancel</Button><Button type="submit" disabled={!datasetId || !agent || Number(repeatCount) < 1 || Number(repeatCount) > 5 || (agent === 'workflow' && !approval) || mutation.isPending}>{mutation.isPending ? 'Running…' : 'Run evaluation'}</Button></div>
      <p className="form-note">Synthetic dataset scores are benchmark diagnostics, not production quality claims. Failed samples remain recorded as failures.</p>
    </form>
  </Modal>
}

function EvaluationReport({ evaluation }: { evaluation: Evaluation }) {
  const flatten = (value: Record<string, unknown>, prefix = ''): Array<[string, number]> => Object.entries(value).flatMap(([key, child]) => {
    const path = prefix ? `${prefix}.${key}` : key
    if (typeof child === 'number' && Number.isFinite(child)) return [[path, child] as [string, number]]
    if (child && typeof child === 'object' && !Array.isArray(child)) return flatten(child as Record<string, unknown>, path)
    return []
  })
  const metrics = flatten(evaluation.metrics)
  return <div className="evaluation-report">
    <div className="report-modal-meta"><span>{evaluation.dataset_id} · v{evaluation.dataset_version}</span><span>{formatDate(evaluation.created_at)}</span><StatusBadge status={evaluation.status} /></div>
    <div className="evaluation-report-config"><span>{agentLabels[evaluation.agent] ?? evaluation.agent}</span><span>{evaluation.provider_name} · {evaluation.model_identifier}</span><span>{evaluation.rag_enabled ? 'RAG enabled' : 'RAG disabled'}</span><span>{evaluation.completed_samples}/{evaluation.total_samples} completed</span></div>
    <h3>Metrics returned by the backend</h3>
    {metrics.length ? <div className="delta-grid">{metrics.map(([key, value]) => <div key={key}><span>{titleCase(key.replaceAll('.', ' / '))}</span><strong>{Number.isInteger(value) ? value : value.toFixed(4)}</strong></div>)}</div> : <p className="muted">No numeric metrics were returned.</p>}
    <h3 className="subheading">Sample outcomes</h3><div className="sample-outcomes">{evaluation.sample_results.map((sample, index) => <div key={`${sample.sample_id}-${sample.run_number}-${index}`}><code>{sample.sample_id}</code><StatusBadge status={sample.status} /><span>{formatDuration(sample.duration_ms)}</span>{sample.error_category && <small>{sample.error_category}</small>}</div>)}</div>
    {evaluation.limitations.length > 0 && <><h3 className="subheading">Limitations</h3><ul>{evaluation.limitations.map((item) => <li key={item}>{item}</li>)}</ul></>}
  </div>
}
