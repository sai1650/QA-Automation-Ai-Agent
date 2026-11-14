import { api } from './client'
import type {
  Artifact,
  Dataset,
  Evaluation,
  EvaluationAgent,
  EvaluationComparison,
  Execution,
  Inspection,
  KnowledgeDetail,
  KnowledgeDocument,
  KnowledgeHealth,
  MetricInfo,
  Page,
  Project,
  QAWorkflow,
  RetrievedKnowledge,
} from '../types'

export const projectsApi = {
  list: async (params: { page?: number; page_size?: number; search?: string; is_active?: boolean } = {}) =>
    (await api.get<Page<Project>>('/projects', { params })).data,
  get: async (id: string) => (await api.get<Project>(`/projects/${id}`)).data,
  create: async (payload: { name: string; base_url: string; description?: string; authorization_confirmed: true }) =>
    (await api.post<Project>('/projects', payload)).data,
  update: async (id: string, payload: Partial<Pick<Project, 'name' | 'base_url' | 'description'>>) =>
    (await api.patch<Project>(`/projects/${id}`, payload)).data,
  archive: async (id: string) => api.delete(`/projects/${id}`),
}

export const executionsApi = {
  list: async (params: { page?: number; page_size?: number; project_id?: string; status?: string } = {}) =>
    (await api.get<Page<Execution>>('/executions', { params })).data,
  listProject: async (projectId: string, params: { page?: number; page_size?: number } = {}) =>
    (await api.get<Page<Execution>>(`/projects/${projectId}/executions`, { params })).data,
  get: async (id: string) => (await api.get<Execution>(`/executions/${id}`)).data,
  queue: async (projectId: string, payload: { requirements: string; options?: Record<string, unknown>; authorized_target_confirmation: true }) =>
    (await api.post<Execution>(`/projects/${projectId}/executions`, payload)).data,
  cancel: async (id: string) => (await api.post<Execution>(`/executions/${id}/cancel`)).data,
  inspect: async (id: string) => (await api.post<Inspection>(`/executions/${id}/run`, undefined, { timeout: 120_000 })).data,
  inspection: async (id: string) => (await api.get<Inspection>(`/executions/${id}/inspection`)).data,
  artifacts: async (id: string) => (await api.get<{ execution_id: string; items: Artifact[] }>(`/executions/${id}/artifacts`)).data,
  workflow: async (id: string) => (await api.get<QAWorkflow>(`/executions/${id}/qa-workflow`)).data,
  startWorkflow: async (id: string) => (await api.post<QAWorkflow>(`/executions/${id}/qa-workflow`, undefined, { timeout: 180_000 })).data,
  approveWorkflow: async (id: string, decision: 'APPROVED' | 'REJECTED') =>
    (await api.post<QAWorkflow>(`/executions/${id}/qa-workflow/approval`, { decision }, { timeout: 180_000 })).data,
  historicalBugs: async (id: string) =>
    (await api.get(`/executions/${id}/historical-bugs`, { params: { authorization_confirmed: true } })).data,
}

export const knowledgeApi = {
  health: async () => (await api.get<KnowledgeHealth>('/knowledge/health')).data,
  list: async (project_id: string, offset = 0, limit = 50) =>
    (await api.get<{ items: KnowledgeDocument[]; next_offset: number | null }>('/knowledge', {
      params: { project_id, authorization_confirmed: true, offset, limit },
    })).data,
  detail: async (id: string, project_id: string) =>
    (await api.get<KnowledgeDetail>(`/knowledge/${encodeURIComponent(id)}`, {
      params: { project_id, authorization_confirmed: true },
    })).data,
  search: async (payload: { project_id: string; query: string; top_k: number; authorization_confirmed: true }) =>
    (await api.post<RetrievedKnowledge[]>('/knowledge/search', payload)).data,
  ingest: async (payload: { project_id: string; authorization_confirmed: true; title: string; content: string; file_type: 'md' | 'txt' | 'json' }) =>
    (await api.post<{ documents: KnowledgeDocument[]; duplicate_count: number }>('/knowledge/ingest', payload)).data,
  delete: async (id: string, project_id: string) =>
    api.delete(`/knowledge/${encodeURIComponent(id)}`, { params: { project_id, authorization_confirmed: true } }),
}

export const evaluationsApi = {
  list: async (page = 1) =>
    (await api.get<{ items: Evaluation[]; total: number; page: number; page_size: number }>('/evaluations', {
      params: { page, page_size: 20 },
    })).data,
  get: async (id: string) => (await api.get<Evaluation>(`/evaluations/${id}`)).data,
  report: async (id: string) => (await api.get<Evaluation>(`/evaluations/${id}/report`)).data,
  datasets: async () => (await api.get<Dataset[]>('/evaluations/datasets')).data,
  metrics: async () => (await api.get<MetricInfo[]>('/evaluations/metrics')).data,
  run: async (payload: {
    dataset_id: string
    agent: EvaluationAgent
    repeat_count: number
    provider_mode: 'live'
    rag_enabled: boolean
    approval_confirmed?: boolean
  }) => (await api.post<Evaluation>('/evaluations/run', payload, { timeout: 300_000 })).data,
  compare: async (baseline_id: string, candidate_id: string) =>
    (await api.post<EvaluationComparison>('/evaluations/compare', { baseline_id, candidate_id })).data,
}
