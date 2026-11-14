# Autonomous QA Intelligence Platform

The backend contains the Phase 0 foundation, Phase 1 core, Phase 2 project
and execution management APIs, and a Phase 3 Playwright browser inspection
engine, plus a Phase 4 LangGraph multi-agent QA workflow. It provides health
checks, project/execution APIs, safe browser inspection, structured QA agents,
human approval gates, and persisted workflow state and reports.

## Architecture

- `app/main.py` creates the FastAPI application and wires middleware, routers,
  exception handlers, and lifecycle logging.
- `app/config.py` loads environment-based settings using Pydantic Settings.
- `app/api/` contains the health, project, and execution endpoints.
- `app/core/` contains shared logging and error handling.
- `app/security/` validates target URLs before a browser request is allowed.
- `app/services/browser_runtime.py` manages one lazy Chromium process and
  isolated per-execution contexts.
- `app/services/browser_inspection.py` extracts bounded page metadata,
  interactive element attributes, screenshots, and redacted browser events.
- `app/services/browser_artifacts.py` writes fixed-name artifacts beneath the
  configured artifact root.
- `app/agents/` contains requirement, planning, website-understanding,
  test-generation, bug-analysis, and reporting agents.
- `app/ai/` provides structured-output provider abstractions and the configured
  local Ollama provider.
- `app/graph/` implements the typed LangGraph state, nodes, and approval/error
  routing.
- `app/services/qa_workflow_service.py` persists and resumes graph state using
  the existing MySQL execution record.
- `app/models/`, `app/schemas/`, and `app/database/` contain the initial
  persistence foundation and API data contracts.
- `migrations/` contains additive Alembic schema changes.
- `docs/api_contract.md` distinguishes implemented endpoints from planned
  future endpoints.
- `app/rag/` implements local embeddings, safe document chunking, persistent
ChromaDB storage, project-scoped retrieval, and bounded historical context.
`app/tools/` and `app/evaluation/` remain reserved for later capabilities.
- `tests/` contains schema, database, API, and integration tests.

## Technology stack

Python 3.11+, FastAPI, Uvicorn, Pydantic v2, SQLAlchemy 2, Alembic, LangGraph,
LangChain Ollama, ChromaDB, Sentence Transformers, PyMySQL, Playwright, SQLite,
MySQL, and Pytest.

## Prerequisites

- Windows 10/11 with PowerShell
- Python 3.11
- Git (optional)

## Install and configure (PowerShell)

From the project root:

```powershell
cd .\backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m playwright install chromium
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

If PowerShell prevents environment activation, either allow activation for the
current user according to your organization's policy, or use the venv
interpreter directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Edit `.env` to override development settings. Do not commit `.env`; `.env.example`
documents the non-secret defaults.

The QA workflow uses `LLM_PROVIDER`, `OLLAMA_BASE_URL`, `OLLAMA_MODEL`,
`LLM_TIMEOUT_SECONDS`, and `LLM_MAX_PROMPT_CHARS`. The default provider is
local Ollama, using the existing configured model. Install and start Ollama
separately, and make the configured model available yourself; application
startup and workflow errors never trigger model downloads. If Ollama is
unavailable, the workflow returns an actionable provider error rather than
fabricating agent responses.

The browser uses Chromium in headless mode by default. Configure
`BROWSER_HEADLESS`, navigation/action/execution timeouts, element/event limits,
screenshot byte/pixel limits, and maximum concurrent inspections in `.env`.
`ARTIFACT_DIR` is resolved relative to the backend directory unless it is an
absolute path.

## Phase 5 historical QA knowledge (RAG)

The knowledge system indexes only explicitly ingested, sanitized text from
persisted QA reports/findings or caller-provided Markdown, TXT, or JSON
documentation. It chunks text, generates local Sentence Transformers
embeddings, and stores vectors and source metadata in the persistent ChromaDB
collection. MySQL remains the source of truth for QA reports and execution
records; no schema migration is required. Re-ingestion is idempotent by source
reference and updates the existing vector document without deleting the source
record.

RAG settings are configured through `.env`:

```text
RAG_ENABLED=true
RAG_EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
RAG_EMBEDDING_DEVICE=cpu
RAG_CHUNK_SIZE=800
RAG_CHUNK_OVERLAP=120
RAG_MAX_CHUNKS_PER_DOCUMENT=100
RAG_TOP_K=5
RAG_MIN_RELEVANCE_SCORE=0.35
RAG_MAX_DOCUMENT_CHARS=100000
RAG_MAX_CONTEXT_CHARS=6000
CHROMA_PERSIST_DIRECTORY=./storage/chroma
CHROMA_COLLECTION_NAME=qa_historical_knowledge
```

The embedding model is loaded lazily and is distinct from the Ollama chat
model. Runtime model downloads are disabled. Before using embeddings, explicitly
cache the configured model in the selected Python environment if it is not
already present (for example, using the Hugging Face CLI's `download`
operation). The health endpoint performs an embedding check; normal application
startup does not load or download the model. The configured device defaults to
CPU for compatibility. No real model download or live embedding was performed
as part of the automated tests.

The existing bug-analysis node retrieves same-project historical knowledge
after read-only execution coordination. Historical text is treated as
untrusted context; current evidence citations are validated separately from
historical references. Similarity scores are vector relevance scores, not
probabilities, and never confirm duplicates. If ChromaDB or the local model is
unavailable, the workflow records `rag_status=unavailable` and continues the
existing bug analysis without historical context.

Retrieval is always filtered to the current project; there is no automatic
cross-project retrieval. Authentication and project authorization are not
implemented in this backend. The API requires an explicit authorization
assertion, but this is not proof of ownership and is not a security boundary.
Deploy only behind an authenticated authorization layer. Sensitive-looking
credentials and email addresses are redacted before chunking; browser artifacts,
screenshots, cookies, headers, and binary files are not ingested. ChromaDB data
is ignored by Git at `storage/chroma/`.

## Database migrations

From `backend` with the virtual environment active:

Phase 3 adds nullable execution fields for inspection data. Phase 4 adds nullable
JSON fields for resumable QA workflow state and its report in the additive
migration `20261109_0003`; it preserves existing execution rows.

```powershell
python -m alembic upgrade head
python -m alembic current
```

The application defaults to a SQLite file named `qa_agent.db` in the current
working directory. For MySQL, configure `DB_USER`, `DB_PASSWORD`, `DB_HOST`,
`DB_PORT`, and `DB_NAME` in `.env`. SQLAlchemy's `URL.create()` safely composes
the connection even when credentials contain reserved characters. Legacy
`DATABASE_URL` settings remain supported; PostgreSQL connection URLs can also
use `DATABASE_URL`. Alembic is the schema
migration mechanism; do not use `initialize_database()` for production schema
management. The initialization helper only creates missing tables for
disposable local/test databases and does not drop existing tables.

To reverse the most recent migration (only when appropriate for that database):

```powershell
python -m alembic downgrade -1
```

Migration tests use temporary SQLite databases and never target the configured
development database.

To check the active database settings and connectivity without printing the
password, run from `backend`:

```powershell
python -m scripts.check_database
```


## Run the backend

With the virtual environment active and the working directory set to `backend`:

```powershell
python -m uvicorn app.main:app --reload
```

The service listens at `http://127.0.0.1:8000`.

## Endpoints and API documentation

- `GET /` — application information and API status
- `GET /health` — health status
- `GET /api/v1/health` — versioned health status
- `GET /api/v1/projects` — list and filter projects
- `POST /api/v1/projects` — create a project
- `GET /api/v1/projects/{project_id}` — retrieve a project
- `PATCH /api/v1/projects/{project_id}` — update a project
- `DELETE /api/v1/projects/{project_id}` — archive a project
- `POST /api/v1/projects/{project_id}/executions` — queue an execution
- `GET /api/v1/executions` — list executions
- `GET /api/v1/executions/{execution_id}` — retrieve an execution
- `POST /api/v1/executions/{execution_id}/cancel` — cancel a queued or
  approval-waiting execution
- `POST /api/v1/executions/{execution_id}/run` — explicitly inspect a queued
  execution with Chromium
- `GET /api/v1/executions/{execution_id}/inspection` — retrieve inspection
  status and result
- `GET /api/v1/executions/{execution_id}/artifacts` — retrieve artifact
  metadata without exposing local filesystem paths
- `POST /api/v1/executions/{execution_id}/qa-workflow` — start requirement
  analysis and planning; returns at the inspection approval gate
- `POST /api/v1/executions/{execution_id}/qa-workflow/approval` — approve or
  reject the current inspection or generated-test-plan gate
- `GET /api/v1/executions/{execution_id}/qa-workflow` — retrieve persisted
  workflow state, outcomes, findings, and report
- `POST /api/v1/knowledge/ingest` — ingest an existing execution report or an
  explicitly supplied authorized Markdown, TXT, or JSON document
- `GET /api/v1/knowledge` — list knowledge metadata in a project scope
- `GET /api/v1/knowledge/{document_id}` — retrieve sanitized knowledge content
- `DELETE /api/v1/knowledge/{document_id}` — remove vector entries only; source
  execution records and reports are retained
- `POST /api/v1/knowledge/search` — perform project-scoped semantic search
- `GET /api/v1/executions/{execution_id}/historical-bugs` — retrieve similar
  project-scoped historical bug findings
- `GET /api/v1/knowledge/health` — check ChromaDB and local embedding readiness
- `POST /api/v1/evaluations/run` — run an explicit agent, workflow, or RAG benchmark
- `GET /api/v1/evaluations` — list persisted evaluation experiments
- `GET /api/v1/evaluations/{evaluation_id}` — retrieve experiment metadata and metrics
- `GET /api/v1/evaluations/{evaluation_id}/report` — retrieve the structured JSON report
- `POST /api/v1/evaluations/compare` — compare compatible saved experiments
- `GET /api/v1/evaluations/datasets` — list approved versioned benchmark datasets
- `GET /api/v1/evaluations/metrics` — list metric formulas and interpretations
- `GET /docs` — Swagger UI
- `GET /redoc` — ReDoc
- `GET /openapi.json` — OpenAPI schema

## Tests

From the `backend` directory:

```powershell
python -m pytest
```

RAG tests use deterministic fake embeddings by default. ChromaDB storage tests
use a temporary local directory; tests do not access the internet or Ollama.

## Browser inspection

Browser execution is explicit; creating an execution only queues its database
record. After creating a project and a queued execution, start inspection with:

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/api/v1/executions/<execution-id>/run
```

Retrieve its result and artifact metadata at
`GET /api/v1/executions/{execution_id}/inspection` and
`GET /api/v1/executions/{execution_id}/artifacts`. Artifacts are stored under
`ARTIFACT_DIR/{execution_id}/` with fixed paths for screenshots, inspection
JSON, and browser logs. Event capture omits request headers, cookies, and
query strings; form values and full page HTML are not collected.

Target validation allows only HTTP(S), rejects credentials and non-public
DNS/IP results, and validates every browser request, including redirect
destinations. It also blocks WebSocket and non-GET/HEAD HTTP requests to reduce
the chance of side effects. Browser routing validates DNS before allowing
requests but cannot pin Chromium's resolver result against a DNS-rebinding
time-of-check / time-of-use race. Deployments that inspect untrusted URLs must
additionally enforce outbound network restrictions or a controlled egress
proxy; this code alone is not a complete network sandbox. GET endpoints can
themselves have side effects, and page scripts execute as part of normal
rendering.

## LangGraph QA workflow

The workflow is started for an existing queued execution. It analyzes the
requirements and creates a test plan, then pauses for approval before any
browser request. After approval, it calls the existing Phase 3 inspection
service, maps only observed evidence, and creates structured test cases. A
second approval gate presents those cases before coordination and reporting.
Approval state, inspection evidence, outcomes, and the final report are stored
on the execution record so approval can resume after an application restart.

```powershell
$workflowUrl = "http://127.0.0.1:8000/api/v1/executions/<execution-id>/qa-workflow"
$approvalUrl = "$workflowUrl/approval"

# Returns WAITING_APPROVAL at the INSPECTION gate; does not launch a browser.
Invoke-RestMethod -Method Post -Uri $workflowUrl

# Approve read-only inspection; response pauses at the TEST_PLAN gate.
Invoke-RestMethod -Method Post -Uri $approvalUrl `
  -ContentType "application/json" -Body '{"decision":"APPROVED"}'

# Approve the generated test plan and complete evidence-based coordination.
Invoke-RestMethod -Method Post -Uri $approvalUrl `
  -ContentType "application/json" -Body '{"decision":"APPROVED"}'

# Retrieve persisted workflow state and the structured QA report.
Invoke-RestMethod -Method Get -Uri $workflowUrl
```

The local Ollama provider must already be running with the configured model
available. No LLM calls run at application startup, and the app does not pull
models automatically. If Ollama is unavailable, the workflow reports an
actionable provider error.

The coordinator can evaluate page-load status and observed element presence
from the single Phase 3 inspection. Clicks, typing, form submissions, custom
API probes, transactions, and destructive actions are never attempted; such
cases are reported as `NOT_SUPPORTED`. `BLOCKED` and `EXECUTED` are distinct
from `PASSED`; unsupported behavior is not reported as a successful test.
Reports separate observed evidence from AI analysis and derive all status
counts from stored execution results.

## Phase 6 AI evaluation and benchmarking

Evaluation is opt-in and separate from normal executions. It reuses the Phase 4
agent classes and, for workflow runs, compiles and invokes the existing
LangGraph graph against supplied synthetic inspection evidence. It does not
create or update Project or Execution rows, launch a browser, access a public
site, or insert benchmark material into the production RAG collection.

### Versioned datasets

The approved dataset directory is `app/evaluation/datasets/`. The initial
`qa_synthetic_v1.json` is version `1.0.0` and explicitly marked `synthetic`.
Its small examples cover requirements, planning, website evidence, test
generation, labeled bug/no-bug cases (including 4xx/5xx, console, transient
network and insufficient evidence), all five severity labels, reporting, a
controlled workflow and relevance-judged RAG documents. The loader accepts
dataset identifiers only, validates the Pydantic contract and labels, rejects
duplicate sample IDs, and resolves files only inside this directory.

Dataset example shape:

```json
{
  "dataset_id": "example_v1",
  "version": "1.0.0",
  "name": "Explicit dataset name",
  "description": "Dataset provenance and scope.",
  "created_at": "2026-11-09T00:00:00Z",
  "synthetic": true,
  "samples": [
    {
      "sample_id": "bug-01",
      "agent": "bug_analysis",
      "inputs": {"execution_results": [], "evidence_index": {}},
      "ground_truth": {"is_bug": false, "severity": "INFO"}
    }
  ]
}
```

Changing expected outputs requires a dataset version change. Synthetic
examples are benchmark-only and are never ingested into historical QA
knowledge. No reference/training corpus is currently shipped separately.

### Metrics and interpretation

- Classification uses deterministic confusion matrices and per-class precision,
  recall and F1. Accuracy is `(TP + TN) / N`; precision is `TP / (TP + FP)`;
  recall is `TP / (TP + FN)`; F1 is their harmonic mean. Macro F1 averages the
  classes equally; weighted F1 weights each class by ground-truth support.
  Undefined/zero-denominator precision, recall and F1 are reported as zero.
- Test generation reports requirement coverage, relevant-and-supported case
  precision, expected scenario-term recall, duplicate rate and unsupported
  rate. Scenario matching is a deterministic lexical proxy, not a semantic
  human judgment. Empty denominators produce zero; empty outputs remain
  measurable and are not silently skipped.
- Retrieval reports Precision@K (`relevant@K / K`), Recall@K
  (`relevant@K / all relevant`), Hit Rate@K, MRR and graded NDCG@K. Relevance
  comes from explicit dataset judgments; embedding similarity is not treated as
  ground truth.
- Bug analysis records severity classification, root-cause term recall,
  recommendation term recall, and evidence support/unsupported-citation
  indicators. These deterministic checks are proxies; no LLM judge or human
  assessment is represented as objective ground truth.
- Latency uses `perf_counter` for each sample, workflow, embedding, indexing,
  and retrieval work. Failure rate and retry count are reported; this runner
  does not retry failed samples. Token usage is marked unavailable because the
  configured provider integration does not expose it.
- Reports identify completed, failed and skipped sample counts. Every selected
  sample is attempted; a failed sample is recorded as failed, not skipped.
  Repeated runs report averages and sample standard deviations where at least
  two observations exist.

### Running an evaluation

The API uses the configured Ollama provider for LLM agents by default and
requires the model to already be installed. It never downloads a model. RAG
retrieval evaluation uses the configured local embedding model, builds
benchmark documents in an ephemeral Chroma collection, and does not touch the
production collection. If the embedding model is not cached, the sample fails
with a categorized error.

```powershell
$body = @{
  dataset_id = "qa_synthetic_v1"
  agent = "bug_analysis"
  repeat_count = 1
  provider_mode = "live"
  rag_enabled = $false
  prompt_version = "current"
} | ConvertTo-Json

$run = Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/api/v1/evaluations/run `
  -ContentType "application/json" -Body $body
$run
Invoke-RestMethod -Method Get `
  -Uri "http://127.0.0.1:8000/api/v1/evaluations/$($run.id)/report"
```

For `agent = "rag_retrieval"`, the request evaluates only the judged synthetic
documents using the real local embedding model. For `agent = "workflow"`, send
`"approval_confirmed": true`; this is an explicit confirmation for the
synthetic inspection and test-plan gates. The workflow runner supplies
pre-recorded evidence to the real LangGraph graph and never opens a browser.
This boolean is not authentication or authorization.

Compare two stored experiment IDs:

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/api/v1/evaluations/compare `
  -ContentType "application/json" `
  -Body (@{ baseline_id = "<uuid>"; candidate_id = "<uuid>" } | ConvertTo-Json)
```

Comparisons calculate metric deltas only when dataset/version, agent, and
sample selection match. Differences in model, prompt label, RAG setting, or run
count are identified as configuration differences; deltas are not causal
proof. `prompt_version` is currently a report label only: the application does
not load old prompt templates. Only Ollama is currently implemented as an LLM
provider; the recorded model identifier is configurable.

### Persistence, safety, and limitations

Experiment summaries, configuration, aggregate metrics, and redacted
sample-level metric/status records are stored in the additive
`evaluation_experiments` table. Full prompts, raw model outputs, secrets,
cookies, and sensitive form values are not persisted by the evaluation runner.
Alembic revision `20261109_0004` creates only this new table and its indexes;
it does not alter project/execution records. Failed provider or parsing cases
remain visible as failed experiment samples.

Evaluation endpoints currently have no authentication; this matches the
backend's existing access-control limitation. Restrict these endpoints at the
deployment boundary until application authentication and authorization exist.
Mock provider mode is accepted only when a provider is explicitly injected by
tests; it cannot fabricate public API benchmark results. A live evaluation is
not a claim of accuracy by itself: interpret results with dataset provenance,
sample counts, model configuration and the report's limitations.
