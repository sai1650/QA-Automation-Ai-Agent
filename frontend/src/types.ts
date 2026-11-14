export type Page<T> = {
  items: T[]
  total: number
  page: number
  page_size: number
  skip?: number
  limit?: number
}

export type Project = {
  id: string
  name: string
  base_url: string
  description: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export type ExecutionStatus =
  | 'QUEUED'
  | 'RUNNING'
  | 'WAITING_APPROVAL'
  | 'COMPLETED'
  | 'FAILED'
  | 'CANCELLED'

export type Execution = {
  id: string
  project_id: string
  status: ExecutionStatus
  requirements: string
  options: Record<string, unknown>
  created_at: string
  started_at: string | null
  completed_at: string | null
  duration_ms: number | null
  final_url: string | null
  inspection_result: Inspection | null
}

export type Inspection = {
  execution_id?: string
  status?: ExecutionStatus
  duration_ms?: number | null
  final_url?: string | null
  result?: Record<string, unknown> | null
  [key: string]: unknown
}

export type Artifact = {
  name: string
  media_type: string
  size_bytes: number
}

export type BugFinding = {
  bug_id: string
  title: string
  description: string
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'INFO'
  confidence_score: number
  probable_root_cause: string
  supporting_evidence: string[]
  affected_url: string | null
  recommended_action: string
  historical_references: string[]
}

export type ExecutionResult = {
  test_case_id: string
  status: 'EXECUTED' | 'PASSED' | 'FAILED' | 'BLOCKED' | 'NOT_SUPPORTED' | 'SKIPPED'
  summary: string
  actual_result: string | null
  evidence_references: string[]
  unsupported_reason: string | null
}

export type QAReport = {
  execution_id: string
  generated_at: string
  summary: string
  status_counts: Record<string, number>
  tests: Array<Record<string, unknown>>
  execution_results: ExecutionResult[]
  findings: BugFinding[]
  observed_facts: Array<{ fact: string; evidence_references: string[] }>
  ai_analysis: string[]
  recommendations: string[]
  rag_status: string
  historical_bug_matches: HistoricalBug[]
}

export type HistoricalBug = {
  document_id: string
  title: string
  source_reference: string
  similarity_score: number
  severity: string | null
  execution_id: string | null
  match_type: 'similar_historical_issue'
}

export type QAWorkflow = {
  execution_id: string
  execution_status: ExecutionStatus
  workflow_status: 'RUNNING' | 'WAITING_APPROVAL' | 'COMPLETED' | 'FAILED' | 'CANCELLED'
  approval_status: 'PENDING' | 'APPROVED' | 'REJECTED' | null
  approval_phase: 'INSPECTION' | 'TEST_PLAN' | null
  current_agent: string | null
  requirement_analysis: Record<string, unknown> | null
  testing_plan: Record<string, unknown> | null
  website_understanding: Record<string, unknown> | null
  generated_test_cases: Array<Record<string, unknown>>
  execution_results: ExecutionResult[]
  bug_findings: BugFinding[]
  qa_report: QAReport | null
  rag_status: string
  historical_bug_matches: HistoricalBug[]
  errors: Array<Record<string, string>>
  warnings: string[]
  approval_history: Array<Record<string, unknown>>
}

export type KnowledgeDocument = {
  document_id: string
  title: string
  source_type: 'historical_bug' | 'qa_report' | 'testing_document'
  source_reference: string
  project_id: string
  execution_id: string | null
  chunk_count: number
  created_at: string
  ingestion_status: string
}

export type KnowledgeDetail = { summary: KnowledgeDocument; content: string }

export type RetrievedKnowledge = {
  document_id: string
  content: string
  source_type: KnowledgeDocument['source_type']
  source_reference: string
  similarity_score: number
  metadata: Record<string, unknown>
}

export type KnowledgeHealth = {
  enabled: boolean
  available: boolean
  embedding_model: string
  collection_name: string
  error_category: string | null
}

export type EvaluationAgent =
  | 'requirement_analysis'
  | 'planning'
  | 'website_understanding'
  | 'test_generation'
  | 'bug_analysis'
  | 'reporting'
  | 'rag_retrieval'
  | 'workflow'

export type Evaluation = {
  id: string
  experiment_name: string
  dataset_id: string
  dataset_version: string
  agent: EvaluationAgent
  provider_mode: string
  provider_name: string
  model_identifier: string
  prompt_version: string
  rag_enabled: boolean
  status: 'completed' | 'partial' | 'failed'
  configuration: Record<string, unknown>
  metrics: Record<string, unknown>
  sample_results: Array<{
    sample_id: string
    run_number: number
    status: string
    duration_ms: number
    metrics: Record<string, unknown>
    error_category: string | null
  }>
  total_samples: number
  completed_samples: number
  failed_samples: number
  skipped_samples: number
  run_count: number
  duration_ms: number
  created_at: string
  limitations: string[]
}

export type Dataset = {
  dataset_id: string
  version: string
  name: string
  description: string
  synthetic: boolean
  sample_count: number
  agents: EvaluationAgent[]
}

export type MetricInfo = {
  name: string
  description: string
  formula: string
  interpretation: string
}

export type EvaluationComparison = {
  baseline_id: string
  candidate_id: string
  dataset_id: string
  dataset_version: string
  agent: EvaluationAgent
  metric_deltas: Record<string, number | null>
  comparable: boolean
  limitations: string[]
}
