import { useQuery } from '@tanstack/react-query'
import { executionsApi, projectsApi } from './api/resources'
import type { Execution, Project, QAWorkflow } from './types'

export type WorkflowRecord = { execution: Execution; workflow: QAWorkflow }

export async function fetchWorkspaceSnapshot() {
  const [projectPage, executionPage] = await Promise.all([
    projectsApi.list({ page: 1, page_size: 100 }),
    executionsApi.list({ page: 1, page_size: 100 }),
  ])
  return { projects: projectPage, executions: executionPage }
}

export async function fetchWorkflows(executions: Execution[], limit = 30): Promise<WorkflowRecord[]> {
  const candidates = executions.filter((item) => item.status !== 'QUEUED').slice(0, limit)
  const results = await Promise.allSettled(
    candidates.map(async (execution) => ({
      execution,
      workflow: await executionsApi.workflow(execution.id),
    })),
  )
  return results.flatMap((result) => result.status === 'fulfilled' ? [result.value] : [])
}

export function useWorkspaceSnapshot() {
  return useQuery({
    queryKey: ['workspace-snapshot'],
    queryFn: fetchWorkspaceSnapshot,
    staleTime: 15_000,
  })
}

export function useWorkflowFeed(executions: Execution[] | undefined, limit = 30) {
  const candidates = (executions ?? []).filter((item) => item.status !== 'QUEUED').slice(0, limit)
  return useQuery({
    queryKey: ['workflow-feed', candidates.map((item) => item.id).join(',')],
    queryFn: () => fetchWorkflows(executions ?? [], limit),
    enabled: Boolean(candidates.length),
    staleTime: 15_000,
  })
}

export function projectName(projects: Project[] | undefined, projectId: string): string {
  return projects?.find((project) => project.id === projectId)?.name ?? 'Unknown project'
}
