import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { FilePlus2, Search, Trash2 } from 'lucide-react'
import { knowledgeApi, projectsApi } from '../api/resources'
import { getErrorMessage } from '../api/client'
import { Badge, Button, Card, ConfirmCheckbox, EmptyState, ErrorState, LoadingState, Modal, PageHeader, SelectField, TextAreaField, TextField } from '../components'
import { formatDate } from '../lib/format'
import type { KnowledgeDocument, RetrievedKnowledge } from '../types'

export function KnowledgePage() {
  const queryClient = useQueryClient()
  const [projectId, setProjectId] = useState('')
  const [authorized, setAuthorized] = useState(false)
  const [query, setQuery] = useState('')
  const [searchResults, setSearchResults] = useState<RetrievedKnowledge[] | null>(null)
  const [selected, setSelected] = useState<KnowledgeDocument | null>(null)
  const [ingestOpen, setIngestOpen] = useState(false)
  const projects = useQuery({ queryKey: ['projects-for-knowledge'], queryFn: () => projectsApi.list({ page: 1, page_size: 100 }) })
  const health = useQuery({ queryKey: ['knowledge-health'], queryFn: knowledgeApi.health, retry: 0 })
  const documents = useQuery({
    queryKey: ['knowledge', projectId],
    queryFn: () => knowledgeApi.list(projectId),
    enabled: Boolean(projectId && authorized),
    retry: 0,
  })
  const detail = useQuery({
    queryKey: ['knowledge-document', selected?.document_id, projectId],
    queryFn: () => knowledgeApi.detail(selected!.document_id, projectId),
    enabled: Boolean(selected && projectId && authorized),
    retry: 0,
  })
  const search = useMutation({
    mutationFn: () => knowledgeApi.search({ project_id: projectId, query, top_k: 5, authorization_confirmed: true }),
    onSuccess: setSearchResults,
  })
  const remove = useMutation({
    mutationFn: (id: string) => knowledgeApi.delete(id, projectId),
    onSuccess: async () => {
      setSelected(null)
      setSearchResults(null)
      await queryClient.invalidateQueries({ queryKey: ['knowledge', projectId] })
    },
  })

  const resultRows = useMemo(() => searchResults === null ? null : searchResults, [searchResults])
  const projectItems = projects.data?.items ?? []

  return <>
    <PageHeader eyebrow="Intelligence" title="Knowledge base" description="Project-scoped historical QA knowledge stored in the local retrieval index." action={<Button onClick={() => setIngestOpen(true)} disabled={!projectId || !authorized}><FilePlus2 size={16} /> Add document</Button>} />
    <div className={`health-strip ${health.data?.available ? 'health-ok' : health.data?.enabled === false ? 'health-muted' : 'health-warning'}`}><span className="status-dot" /><div><strong>{health.isLoading ? 'Checking knowledge services…' : health.data?.available ? 'Knowledge services available' : health.data?.enabled === false ? 'Retrieval disabled by backend' : health.data ? 'Knowledge service unavailable' : 'Knowledge health unavailable'}</strong><span>{health.data ? `${health.data.embedding_model} · ${health.data.collection_name}` : 'Health endpoint could not be reached.'}</span></div>{health.data?.error_category && <Badge tone="warning">{health.data.error_category}</Badge>}</div>
    <Card className="knowledge-scope">
      <SelectField label="Project scope" value={projectId} onChange={(event) => { setProjectId(event.target.value); setSearchResults(null) }}><option value="">Select a project</option>{projectItems.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}</SelectField>
      <ConfirmCheckbox checked={authorized} onChange={(value) => { setAuthorized(value); if (!value) { setSearchResults(null); setSelected(null) } }}>I am authorized to view and manage knowledge for this project. This is an assertion, not an access-control check.</ConfirmCheckbox>
    </Card>
    {!projectId || !authorized ? <EmptyState title="Confirm a project scope" description="Choose a project and explicitly confirm authorization before retrieving project-scoped knowledge." /> :
      <>
        <Card className="knowledge-search-card"><form className="knowledge-search" onSubmit={(event) => { event.preventDefault(); if (query.trim()) search.mutate() }}><label className="toolbar-search"><Search size={16} /><input value={query} onChange={(event) => setQuery(event.target.value)} aria-label="Semantic knowledge search" placeholder="Search past findings and QA documents…" /></label><Button type="submit" disabled={!query.trim() || search.isPending}>{search.isPending ? 'Searching…' : 'Semantic search'}</Button></form>
          {search.error && <div className="inline-error">{getErrorMessage(search.error)}</div>}
          {resultRows && <div className="retrieval-results"><div className="card-heading"><h2>Search results</h2><Button variant="ghost" onClick={() => setSearchResults(null)}>Clear</Button></div>{resultRows.length ? resultRows.map((item) => <div className="retrieval-result" key={`${item.document_id}-${item.source_reference}`}><div className="finding-title"><strong>{item.source_type.replaceAll('_', ' ')}</strong><Badge tone="blue">Similarity {(item.similarity_score * 100).toFixed(0)}%</Badge></div><p>{item.content}</p><small className="muted">{item.source_reference}</small></div>) : <p className="muted">No documents matched this query above the backend relevance threshold.</p>}</div>}
        </Card>
        <Card><div className="card-heading"><div><h2>Indexed documents</h2><p className="muted">Source metadata · content opens only after scope confirmation</p></div><span className="muted">{documents.data?.items.length ?? 0} shown</span></div>
          {documents.isLoading ? <LoadingState label="Loading project knowledge" /> : documents.error ? <ErrorState message={getErrorMessage(documents.error)} retry={() => void documents.refetch()} /> : documents.data?.items.length ? <div className="table-scroll"><table><thead><tr><th>Title</th><th>Source</th><th>Chunks</th><th>Status</th><th>Created</th><th /></tr></thead><tbody>{documents.data.items.map((document) => <tr key={document.document_id}><td><button className="table-link" onClick={() => setSelected(document)}>{document.title}</button><small className="table-subtext">{document.source_reference}</small></td><td>{document.source_type.replaceAll('_', ' ')}</td><td>{document.chunk_count}</td><td><Badge tone={document.ingestion_status === 'indexed' ? 'success' : 'warning'}>{document.ingestion_status}</Badge></td><td>{formatDate(document.created_at)}</td><td><Button variant="ghost" aria-label={`Delete ${document.title}`} onClick={() => { if (window.confirm(`Remove “${document.title}” from the vector index? Source QA data will remain unchanged.`)) remove.mutate(document.document_id) }}><Trash2 size={15} /></Button></td></tr>)}</tbody></table></div> : <EmptyState title="No indexed documents" description="Ingest an execution report or an authorized Markdown, text, or JSON document to build project knowledge." />}
        </Card>
      </>}
    <Modal open={Boolean(selected)} title={selected?.title ?? 'Knowledge document'} onClose={() => setSelected(null)} wide>
      {detail.isLoading ? <LoadingState /> : detail.error ? <ErrorState message={getErrorMessage(detail.error)} retry={() => void detail.refetch()} /> : detail.data ? <><div className="document-detail-meta"><Badge>{detail.data.summary.source_type}</Badge><span>{formatDate(detail.data.summary.created_at)}</span><code>{detail.data.summary.source_reference}</code></div><pre className="document-content">{detail.data.content}</pre></> : null}
    </Modal>
    <IngestModal projectId={projectId} open={ingestOpen} onClose={() => setIngestOpen(false)} onSaved={() => { setIngestOpen(false); void queryClient.invalidateQueries({ queryKey: ['knowledge', projectId] }) }} />
  </>
}

function IngestModal({ projectId, open, onClose, onSaved }: { projectId: string; open: boolean; onClose: () => void; onSaved: () => void }) {
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [fileType, setFileType] = useState<'md' | 'txt' | 'json'>('md')
  const [confirmed, setConfirmed] = useState(false)
  const [errorMessage, setErrorMessage] = useState('')
  const mutation = useMutation({
    mutationFn: () => knowledgeApi.ingest({ project_id: projectId, authorization_confirmed: true, title, content, file_type: fileType }),
    onSuccess: onSaved,
    onError: (error) => setErrorMessage(getErrorMessage(error)),
  })
  return <Modal open={open} title="Ingest knowledge document" onClose={onClose} wide>
    <p className="muted form-note">The backend sanitizes and chunks supplied content. Do not include passwords, tokens, private user data, or sensitive account information.</p>
    {errorMessage && <div className="form-error" role="alert">{errorMessage}</div>}
    <form className="stack-form" onSubmit={(event) => { event.preventDefault(); if (confirmed) mutation.mutate() }}>
      <TextField label="Document title" required maxLength={300} value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Release checklist" />
      <SelectField label="Document type" value={fileType} onChange={(event) => setFileType(event.target.value as 'md' | 'txt' | 'json')}><option value="md">Markdown</option><option value="txt">Plain text</option><option value="json">JSON</option></SelectField>
      <TextAreaField label="Content" required minLength={1} maxLength={500000} rows={10} value={content} onChange={(event) => setContent(event.target.value)} placeholder="Paste approved QA documentation…" />
      <ConfirmCheckbox checked={confirmed} onChange={setConfirmed}>I am authorized to ingest and store this material for the selected project.</ConfirmCheckbox>
      <div className="modal-actions"><Button type="button" variant="secondary" onClick={onClose}>Cancel</Button><Button type="submit" disabled={!confirmed || !title.trim() || !content.trim() || mutation.isPending}>{mutation.isPending ? 'Indexing…' : 'Ingest document'}</Button></div>
    </form>
  </Modal>
}
