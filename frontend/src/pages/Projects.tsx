import { useMemo, useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Archive, ArrowUpRight, Grid2X2, List, Plus, Search } from 'lucide-react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'
import { projectsApi, executionsApi } from '../api/resources'
import { Button, Card, ConfirmCheckbox, EmptyState, ErrorState, Modal, PageHeader, Pagination, StatusBadge, TextAreaField, TextField, LoadingState } from '../components'
import { formatDate, formatDuration, shortId } from '../lib/format'
import type { Execution, Project } from '../types'

const PAGE_SIZE = 12

export function ProjectsPage() {
  const queryClient = useQueryClient()
  const location = useLocation()
  const navigate = useNavigate()
  const searchFromUrl = new URLSearchParams(location.search).get('search') ?? ''
  const [page, setPage] = useState(1)
  const [showArchived, setShowArchived] = useState(false)
  const [view, setView] = useState<'grid' | 'list'>('grid')
  const [modal, setModal] = useState(false)
  const [editing, setEditing] = useState<Project | null>(null)
  const projects = useQuery({
    queryKey: ['projects', page, searchFromUrl, showArchived],
    queryFn: () => projectsApi.list({
      page,
      page_size: PAGE_SIZE,
      search: searchFromUrl || undefined,
      is_active: showArchived ? undefined : true,
    }),
    staleTime: 10_000,
  })
  const executions = useQuery({
    queryKey: ['project-latest-executions'],
    queryFn: () => executionsApi.list({ page: 1, page_size: 100 }),
  })
  const archive = useMutation({
    mutationFn: (id: string) => projectsApi.archive(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['projects'] }),
  })
  const projectItems = projects.data?.items ?? []
  const latestByProject = useMemo(() => {
    const map = new Map<string, Execution>()
    for (const execution of executions.data?.items ?? []) {
      if (!map.has(execution.project_id)) map.set(execution.project_id, execution)
    }
    return map
  }, [executions.data])

  function applySearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setPage(1)
    navigate(searchFromUrl ? `/projects?search=${encodeURIComponent(searchFromUrl)}` : '/projects', { replace: true })
  }

  return (
    <>
      <PageHeader
        eyebrow="Workspace"
        title="Projects"
        description="Manage authorized targets and review their latest QA activity."
        action={<Button onClick={() => { setEditing(null); setModal(true) }}><Plus size={16} /> New project</Button>}
      />
      <Card className="toolbar-card">
        <form className="toolbar-search" onSubmit={applySearch}><Search size={16} /><input aria-label="Search projects" placeholder="Search projects…" value={searchFromUrl} onChange={(event) => navigate(event.target.value ? `/projects?search=${encodeURIComponent(event.target.value)}` : '/projects', { replace: true })} /><Button variant="secondary" type="submit">Search</Button></form>
        <label className="filter-check"><input type="checkbox" checked={showArchived} onChange={(event) => { setShowArchived(event.target.checked); setPage(1) }} />Include archived</label>
        <div className="view-switch"><Button variant={view === 'grid' ? 'secondary' : 'ghost'} aria-label="Grid view" onClick={() => setView('grid')}><Grid2X2 size={16} /></Button><Button variant={view === 'list' ? 'secondary' : 'ghost'} aria-label="List view" onClick={() => setView('list')}><List size={16} /></Button></div>
      </Card>
      {projects.isLoading ? <LoadingState label="Loading projects" /> : projects.error ? <ErrorState message="Projects could not be loaded." retry={() => void projects.refetch()} /> : projectItems.length === 0
        ? <EmptyState title={searchFromUrl ? 'No matching projects' : 'No projects yet'} description={searchFromUrl ? 'Try another search or clear the filter.' : 'Create a project to organize authorized QA targets.'} action={!searchFromUrl && <Button onClick={() => { setEditing(null); setModal(true) }}><Plus size={16} /> Create project</Button>} />
        : <div className={view === 'grid' ? 'project-grid' : 'project-list'}>
          {projectItems.map((project) => {
            const latest = latestByProject.get(project.id)
            return <Card className="project-card" key={project.id}>
              <div className="project-card-top"><div className="project-symbol">{project.name.slice(0, 1).toUpperCase()}</div><StatusBadge status={project.is_active ? 'ACTIVE' : 'ARCHIVED'} /></div>
              <Link to={`/projects/${project.id}`} className="project-title-link"><h2>{project.name}<ArrowUpRight size={15} /></h2></Link>
              <p className="muted project-description">{project.description || 'No description provided.'}</p>
              <a className="project-url" href={project.base_url} target="_blank" rel="noreferrer">{project.base_url}</a>
              <div className="project-meta"><span>Created {formatDate(project.created_at, { month: 'short', day: 'numeric', year: 'numeric' })}</span><span>{latest ? `Latest · ${latest.status}` : 'No executions'}</span></div>
              {latest && <div className="latest-run"><StatusBadge status={latest.status} /><span>{formatDate(latest.created_at, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}</span><span>{formatDuration(latest.duration_ms)}</span></div>}
              <div className="project-actions">
                <Button variant="secondary" onClick={() => navigate(`/projects/${project.id}`)}>Open project</Button>
                <Button variant="ghost" onClick={() => { setEditing(project); setModal(true) }}>Edit</Button>
                {project.is_active && <Button variant="ghost" disabled={archive.isPending} onClick={() => {
                  if (window.confirm(`Archive “${project.name}”? Existing execution history will remain.`)) archive.mutate(project.id)
                }} aria-label={`Archive ${project.name}`}><Archive size={15} /></Button>}
              </div>
            </Card>
          })}
        </div>}
      {projects.data && <Pagination page={projects.data.page} pageSize={projects.data.page_size} total={projects.data.total} onChange={setPage} />}
      {modal && <ProjectModal key={editing?.id ?? 'create'} open project={editing} onClose={() => setModal(false)} />}
    </>
  )
}

function ProjectModal({ open, project, onClose }: { open: boolean; project: Project | null; onClose: () => void }) {
  const queryClient = useQueryClient()
  const [name, setName] = useState(project?.name ?? '')
  const [url, setUrl] = useState(project?.base_url ?? '')
  const [description, setDescription] = useState(project?.description ?? '')
  const [authorized, setAuthorized] = useState(false)
  const mutation = useMutation({
    mutationFn: () => project
      ? projectsApi.update(project.id, { name, base_url: url, description })
      : projectsApi.create({ name, base_url: url, description: description || undefined, authorization_confirmed: true }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['projects'] })
      setAuthorized(false)
      onClose()
    },
  })
  return <Modal open={open} title={project ? 'Edit project' : 'Create project'} onClose={onClose}>
    {mutation.error && <div className="form-error" role="alert">{mutation.error instanceof Error ? mutation.error.message : 'Project could not be saved.'}</div>}
    <form className="stack-form" onSubmit={(event) => {
      event.preventDefault()
      if (project) {
        const payload: { name?: string; base_url?: string; description?: string } = {}
        if (name !== project.name) payload.name = name
        if (url !== project.base_url) payload.base_url = url
        if (description !== (project.description ?? '')) payload.description = description
        if (!Object.keys(payload).length) return onClose()
        mutation.mutate()
      } else if (authorized) {
        mutation.mutate()
      }
    }}>
      <TextField label="Project name" required maxLength={120} value={name} onChange={(event) => setName(event.target.value)} placeholder="e.g. Customer portal" />
      <TextField label="Target URL" required type="url" value={url} onChange={(event) => setUrl(event.target.value)} placeholder="https://example.com" />
      <TextAreaField label="Description" maxLength={5000} value={description} onChange={(event) => setDescription(event.target.value)} placeholder="What should this project validate?" rows={3} />
      {!project && <ConfirmCheckbox checked={authorized} onChange={setAuthorized}>I am authorized to assess this target. This confirms intent, not ownership verification.</ConfirmCheckbox>}
      <div className="modal-actions"><Button type="button" variant="secondary" onClick={onClose}>Cancel</Button><Button type="submit" disabled={mutation.isPending || (!project && !authorized)}>{mutation.isPending ? 'Saving…' : project ? 'Save changes' : 'Create project'}</Button></div>
      {!project && <p className="form-note">The backend validates target safety before browser requests. Creating a project does not start an inspection.</p>}
    </form>
  </Modal>
}

export function ProjectDetailPage() {
  const { projectId = '' } = useParams()
  const navigate = useNavigate()
  const [tab, setTab] = useState('Overview')
  const [queueOpen, setQueueOpen] = useState(false)
  const project = useQuery({ queryKey: ['project', projectId], queryFn: () => projectsApi.get(projectId), enabled: Boolean(projectId) })
  const executions = useQuery({ queryKey: ['project-executions', projectId], queryFn: () => executionsApi.listProject(projectId, { page: 1, page_size: 50 }), enabled: Boolean(projectId) })
  const tabs = ['Overview', 'Executions', 'Bug findings', 'Reports']
  if (project.isLoading) return <LoadingState label="Loading project" />
  if (project.error || !project.data) return <ErrorState message="Project details could not be loaded." retry={() => void project.refetch()} />
  return <>
    <PageHeader eyebrow="Project workspace" title={project.data.name} description={project.data.description ?? 'No project description.'} action={<><Button variant="secondary" onClick={() => setQueueOpen(true)} disabled={!project.data.is_active}><Plus size={16} /> Queue execution</Button><Button variant="ghost" onClick={() => navigate('/projects')}>All projects</Button></>} />
    <Card className="project-detail-banner"><div><span className="eyebrow">TARGET URL</span><a href={project.data.base_url} target="_blank" rel="noreferrer">{project.data.base_url}</a></div><div><span className="eyebrow">STATUS</span><StatusBadge status={project.data.is_active ? 'ACTIVE' : 'ARCHIVED'} /></div><div><span className="eyebrow">CREATED</span><strong>{formatDate(project.data.created_at)}</strong></div></Card>
    <div className="tabs" role="tablist">{tabs.map((item) => <button key={item} role="tab" aria-selected={tab === item} className={tab === item ? 'tab active' : 'tab'} onClick={() => setTab(item)}>{item}</button>)}</div>
    {executions.isLoading ? <LoadingState label="Loading project activity" /> : executions.error ? <ErrorState message="Project executions could not be loaded." retry={() => void executions.refetch()} /> : tab === 'Overview'
      ? <div className="content-grid"><Card><div className="card-heading"><h2>Execution activity</h2><span className="muted">Latest {executions.data?.items.length ?? 0}</span></div><ExecutionTable items={executions.data?.items ?? []} /></Card><Card><div className="card-heading"><h2>Project summary</h2></div><dl className="details-list"><div><dt>Active</dt><dd>{project.data.is_active ? 'Yes' : 'No'}</dd></div><div><dt>Executions</dt><dd>{executions.data?.total ?? 0}</dd></div><div><dt>Updated</dt><dd>{formatDate(project.data.updated_at)}</dd></div></dl><p className="muted small-note">Findings and reports are available after a QA workflow has been run for an execution.</p></Card></div>
      : tab === 'Executions' ? <Card><ExecutionTable items={executions.data?.items ?? []} /></Card>
        : <Card><EmptyState title={tab === 'Reports' ? 'Reports are execution-based' : 'Findings are workflow-based'} description="Open an execution with a completed QA workflow to view its persisted report and findings. The API does not expose a project-level findings or report listing." action={<Button variant="secondary" onClick={() => setTab('Executions')}>Browse executions</Button>} /></Card>}
    <QueueExecutionModal project={project.data} open={queueOpen} onClose={() => setQueueOpen(false)} onCreated={(id) => navigate(`/executions/${id}`)} />
  </>
}

function ExecutionTable({ items }: { items: Array<{ id: string; status: string; created_at: string; started_at: string | null; completed_at: string | null; duration_ms: number | null }> }) {
  const navigate = useNavigate()
  if (!items.length) return <EmptyState title="No executions yet" description="Queue an execution to begin a QA workflow." />
  return <div className="table-scroll"><table><thead><tr><th>Execution</th><th>Status</th><th>Created</th><th>Started</th><th>Duration</th><th /></tr></thead><tbody>
    {items.map((item) => <tr key={item.id} className="clickable-row" onClick={() => navigate(`/executions/${item.id}`)}><td><code>{shortId(item.id)}</code></td><td><StatusBadge status={item.status} /></td><td>{formatDate(item.created_at)}</td><td>{formatDate(item.started_at)}</td><td>{formatDuration(item.duration_ms)}</td><td><ArrowUpRight size={15} /></td></tr>)}
  </tbody></table></div>
}

export function QueueExecutionModal({ project, open, onClose, onCreated }: { project: Project; open: boolean; onClose: () => void; onCreated: (id: string) => void }) {
  const queryClient = useQueryClient()
  const [requirements, setRequirements] = useState('')
  const [confirmed, setConfirmed] = useState(false)
  const [message, setMessage] = useState('')
  const mutation = useMutation({
    mutationFn: () => executionsApi.queue(project.id, { requirements, options: { browser: 'chromium', capture_screenshots: true }, authorized_target_confirmation: true }),
    onSuccess: async (execution) => {
      await queryClient.invalidateQueries({ queryKey: ['executions'] })
      await queryClient.invalidateQueries({ queryKey: ['project-executions', project.id] })
      setRequirements('')
      setConfirmed(false)
      onCreated(execution.id)
    },
    onError: (error) => setMessage(error instanceof Error ? error.message : 'Could not queue execution.'),
  })
  return <Modal open={open} title="Queue QA execution" onClose={onClose}>
    {message && <div className="form-error" role="alert">{message}</div>}
    <form className="stack-form" onSubmit={(event) => { event.preventDefault(); if (confirmed) mutation.mutate() }}>
      <div className="target-callout"><span className="eyebrow">TARGET</span><strong>{project.name}</strong><span>{project.base_url}</span></div>
      <TextAreaField label="Testing requirements" required minLength={1} maxLength={20000} rows={5} value={requirements} onChange={(event) => setRequirements(event.target.value)} placeholder="Describe the behaviors to inspect…" />
      <ConfirmCheckbox checked={confirmed} onChange={setConfirmed}>I am authorized to assess this target. The execution request does not verify ownership.</ConfirmCheckbox>
      <p className="form-note">Queueing only creates an execution record; it does not start a browser. Inspection and workflow require explicit actions on the execution page.</p>
      <div className="modal-actions"><Button type="button" variant="secondary" onClick={onClose}>Cancel</Button><Button type="submit" disabled={!requirements.trim() || !confirmed || mutation.isPending}>{mutation.isPending ? 'Queueing…' : 'Queue execution'}</Button></div>
    </form>
  </Modal>
}
