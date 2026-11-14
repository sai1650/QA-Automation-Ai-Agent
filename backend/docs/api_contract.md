# Frontend API Contract

Base URL in development: `http://127.0.0.1:8000`

The Phase 0 health endpoints, Phase 2 project/execution endpoints, Phase 3
browser inspection endpoints, and Phase 4 QA workflow endpoints below are
implemented, along with Phase 5 knowledge ingestion and retrieval endpoints.
Event streaming, standalone finding/report routes, and authentication remain
planned; this refers to QA execution findings/reports, not the Phase 6
evaluation report endpoint. Phase 6 evaluation APIs are implemented.

All IDs are UUID strings. Timestamps are ISO-8601 JSON strings. Errors use:

```json
{
  "error": {
    "code": "project_not_found",
    "message": "Project not found."
  }
}
```

Validation errors return `422` with `error.code = "validation_error"` and a
`details` array describing invalid fields. No authentication is implemented;
production deployments must add authentication and project-scoped
authorization. Authorization confirmation is an explicit user assertion, not
proof of ownership.

## Phase 5 knowledge APIs

Knowledge is filtered by project ID. The authorization-confirmation field is
only an assertion because this API currently has no authentication; it must not
be treated as proof of project access.

### `POST /api/v1/knowledge/ingest`

Accepts exactly one of:

- `execution_id` and `project_id` for indexing that execution's already
  persisted QA report and findings; or
- `content`, `title`, `file_type` (`md`, `txt`, or `json`), and `project_id`
  for explicitly supplied text documentation.

Both forms require `authorization_confirmed: true`. Execution IDs are checked
against the requested project. Documents are size-bounded, normalized,
credential-redacted, chunked, and upserted using stable source-based IDs.
Retries are idempotent. Deleting a vector document never deletes its source QA
record.

### `GET /api/v1/knowledge`

Requires `project_id` and `authorization_confirmed=true`; supports `offset` and
`limit`. Returns source metadata, not full document text.

### `GET /api/v1/knowledge/{document_id}`

Requires the project scope and authorization assertion. Returns sanitized
content bounded by the configured maximum document size. Arbitrary filesystem
paths and artifact paths are not accepted as source references.

### `DELETE /api/v1/knowledge/{document_id}`

Requires project scope and authorization assertion. Deletes only matching
ChromaDB chunks; it does not modify MySQL execution or report records.

### `POST /api/v1/knowledge/search`

Requires `project_id`, `authorization_confirmed=true`, and a non-empty query.
Optional `top_k` and source-type filters apply within that project. Results
below `RAG_MIN_RELEVANCE_SCORE` are omitted. `similarity_score` is a vector
distance-derived relevance value, not a probability or duplicate verdict.

### `GET /api/v1/executions/{execution_id}/historical-bugs`

Requires `authorization_confirmed=true`. Searches only the execution's project
and returns references to similar ingested bug findings; similarity never
confirms a duplicate.

### `GET /api/v1/knowledge/health`

Checks persistent ChromaDB access and attempts a local embedding health probe.
It may load an already cached embedding model, but never downloads one.

The vector index is local persistent data in `CHROMA_PERSIST_DIRECTORY` and is
ignored by Git. MySQL remains authoritative for persisted QA records. A failed
vector write can be retried by source reference; no source QA record is
removed. Workflow retrieval failures are recorded in `rag_status` and fall
back to the existing Bug Analysis Agent without historical context.

## Phase 6 evaluation APIs

Evaluation is explicitly triggered and separate from production QA execution.
It stores reports in `evaluation_experiments`; it does not modify projects,
executions, QA reports, or production RAG documents. All endpoints currently
have no authentication and must be deployment-restricted.

### `POST /api/v1/evaluations/run`

- **Purpose:** Run a versioned agent, workflow, or RAG evaluation dataset.
- **Body:**

  ```json
  {
    "dataset_id": "qa_synthetic_v1",
    "agent": "bug_analysis",
    "repeat_count": 1,
    "provider_mode": "live",
    "rag_enabled": false,
    "prompt_version": "current"
  }
  ```

- **Supported agents:** `requirement_analysis`, `planning`,
  `website_understanding`, `test_generation`, `bug_analysis`, `reporting`,
  `rag_retrieval`, and `workflow`.
- **Success (`201`):** A persisted experiment with status `completed`,
  `partial`, or `failed`, plus dataset and model metadata, configuration,
  metrics, sample counts, per-sample status/duration/metrics and limitations.
  Failed samples are retained and are not represented as successful.
- **Workflow runs:** Require `"approval_confirmed": true`, which confirms the
  synthetic inspection and test-plan gates. The runner uses supplied
  inspection evidence and the existing LangGraph graph; it never launches a
  browser.
- **Provider:** `live` uses the configured Ollama provider for agent runs.
  `mock` is accepted only when a provider is injected in tests; no ground-truth
  outputs are used as model responses. RAG retrieval evaluates with the local
  configured embedding model and ephemeral Chroma storage.
- **Errors:** `404` for an unknown dataset; `422` for invalid dataset/sample,
  unsupported mock mode, or invalid configuration; `503` if the evaluation
  service cannot persist or initialize.
- **Privacy:** Raw prompts and model outputs are not persisted. Token usage is
  explicitly unavailable in the current Ollama integration.

### `GET /api/v1/evaluations`

- **Purpose:** Paginated experiment history.
- **Query:** `page` (default `1`, minimum `1`), `page_size` (default `20`,
  range `1..100`), optional `dataset_id`, optional `agent`.
- **Success (`200`):** `{ "items": [...], "total": 0, "page": 1,
  "page_size": 20 }`.

### `GET /api/v1/evaluations/{evaluation_id}`

- **Purpose:** Retrieve experiment metadata, metrics and sample statuses.
- **Errors:** `404` if no evaluation exists; `422` for invalid UUID.

### `GET /api/v1/evaluations/{evaluation_id}/report`

- **Purpose:** Retrieve the structured JSON evaluation report. Same report
  schema as the experiment detail response.
- **Errors:** `404` if no evaluation exists; `422` for invalid UUID.

### `POST /api/v1/evaluations/compare`

- **Body:** `{"baseline_id":"<uuid>","candidate_id":"<uuid>"}`.
- **Purpose:** Return numeric metric deltas for matching dataset/version,
  agent and sample selections. Non-comparable runs return no deltas and explain
  why. Differences in provider/model/prompt label/RAG/repeat count are reported
  as limitations and are not causal evidence.
- **Errors:** `404` if either evaluation is missing; `422` for invalid IDs.

### `GET /api/v1/evaluations/datasets`

- **Purpose:** List validated dataset IDs, versions, provenance flags, sample
  counts and supported agents. Only files under the approved evaluation
  dataset directory can be loaded.

### `GET /api/v1/evaluations/metrics`

- **Purpose:** List metric names, formulas and denominator/interpretation
  policies, including classification, test-generation and retrieval metrics.

The initial `qa_synthetic_v1` dataset is small and explicitly synthetic.
Lexical requirement/root-cause/report scores are proxies rather than semantic
judgments. RAG relevance is judged from dataset labels, never inferred from
similarity scores. The prompt version is currently a label only. Authentication
and authorization are not implemented.

## Implemented endpoints

### `GET /`

- **Purpose:** Application information and API status.
- **Body:** None.
- **Success (`200`):**

  ```json
  {
    "application": "Autonomous QA Intelligence Platform",
    "version": "0.1.0",
    "environment": "development",
    "status": "API is operational"
  }
  ```

- **Errors:** `500` for an unexpected server failure.
- **Authentication:** None.

### `GET /health` and `GET /api/v1/health`

- **Purpose:** API health check.
- **Body:** None.
- **Success (`200`):**

  ```json
  {
    "status": "healthy",
    "application": "Autonomous QA Intelligence Platform",
    "version": "0.1.0",
    "environment": "development"
  }
  ```

- **Errors:** `500` for an unexpected server failure.
- **Authentication:** None.

### `POST /api/v1/projects`

- **Purpose:** Create a project.
- **Body:**

  ```json
  {
    "name": "E-Commerce Testing",
    "base_url": "https://example.com",
    "description": "Automated testing project",
    "authorization_confirmed": true
  }
  ```

- **Success (`201`):** Project object with `id`, `name`, `base_url`,
  `description`, `is_active`, `created_at`, and `updated_at`.
- **Errors:** `422` for invalid fields, non-HTTP(S) URLs, blank/overlong name,
  or missing/false authorization confirmation; `500` for unexpected failures.
- **Authentication:** None currently; required in production.

### `GET /api/v1/projects`

- **Purpose:** List and filter projects.
- **Query:** `page` (default `1`), `page_size` (default `20`, range `1..100`),
  `search` (optional name/description substring), `is_active` (optional
  boolean), and `sort_order` (`asc` or `desc`, default `desc`).
- **Body:** None.
- **Success (`200`):**

  ```json
  {
    "items": [],
    "total": 0,
    "page": 1,
    "page_size": 20
  }
  ```

- **Errors:** `422` for invalid query values; `500` for unexpected failures.
- **Authentication:** None currently; required in production.

### `GET /api/v1/projects/{project_id}`

- **Purpose:** Retrieve a project, including archived projects.
- **Body:** None.
- **Success (`200`):** Project object.
- **Errors:** `404` if no project exists; `422` if the path ID is not a UUID.
- **Authentication:** None currently; required in production.

### `PATCH /api/v1/projects/{project_id}`

- **Purpose:** Partially update a project.
- **Body:** Any non-empty subset of `name`, `base_url`, `description`. For
  example: `{"name":"Updated name"}`.
- **Success (`200`):** Updated project object.
- **Errors:** `404` if missing; `422` for an empty patch or invalid fields.
- **Authentication:** None currently; required in production.

### `DELETE /api/v1/projects/{project_id}`

- **Purpose:** Archive (soft-delete) a project; project and execution records
  are preserved.
- **Body:** None.
- **Success (`200`):** `{"id":"<uuid>","is_active":false,"message":"Project archived."}`.
- **Errors:** `404` if the project does not exist.
- **Authentication:** None currently; required in production.

### `POST /api/v1/projects/{project_id}/executions`

- **Purpose:** Persist a new execution in `QUEUED` state. This does not start
  an agent, browser automation, or background worker.
- **Body:**

  ```json
  {
    "requirements": "Test login, registration and product search functionality.",
    "options": {
      "browser": "chromium",
      "capture_screenshots": true
    },
    "authorized_target_confirmation": true
  }
  ```

- **Success (`201`):** Execution object with `id`, `project_id`, `status`,
  `requirements`, `options`, `created_at`, `started_at`, and `completed_at`.
- **Errors:** `404` if the project does not exist; `409` if archived; `422` for
  invalid/blank requirements, invalid options shape, or missing/false
  authorization confirmation.
- **Authentication:** None currently; required in production.

### `GET /api/v1/executions`

- **Purpose:** List executions.
- **Query:** `project_id` (optional UUID), `status` (optional enum:
  `QUEUED`, `RUNNING`, `WAITING_APPROVAL`, `COMPLETED`, `FAILED`, `CANCELLED`),
  `page` (default `1`), `page_size` (default `20`, range `1..100`), and
  `sort_order` (`asc` or `desc`, default `desc`).
- **Body:** None.
- **Success (`200`):** `{"items":[...],"total":0,"page":1,"page_size":20}`.
- **Errors:** `422` for invalid query values.
- **Authentication:** None currently; required in production.

### `GET /api/v1/executions/{execution_id}`

- **Purpose:** Retrieve an execution.
- **Body:** None.
- **Success (`200`):** Execution object.
- **Errors:** `404` if missing; `422` if the path ID is not a UUID.
- **Authentication:** None currently; required in production.

### `POST /api/v1/executions/{execution_id}/cancel`

- **Purpose:** Cancel an execution that is `QUEUED` or waiting for human
  approval.
- **Body:** None.
- **Success (`200`):** Updated execution object with `status = "CANCELLED"` and
  `completed_at` populated.
- **Errors:** `404` if missing; `409` if it is running or terminal.
- **Authentication:** None currently; required in production.

### `POST /api/v1/executions/{execution_id}/run`

- **Purpose:** Explicitly run a bounded, read-only browser inspection for a
  queued execution. Creating an execution does not launch a browser.
- **Success (`200`):** Inspection status, duration, final URL, and structured
  page inspection result.
- **Errors:** `404` if missing; `409` unless the execution is queued; `422` if
  the target is unsafe; `502` if browser inspection fails.
- **Artifacts:** Stored beneath `ARTIFACT_DIR/{execution_id}/` with generated
  fixed names. No local paths, request headers, cookies, or query strings are
  returned.

### `GET /api/v1/executions/{execution_id}/inspection`

- **Purpose:** Retrieve the execution inspection status and result.
- **Success (`200`):** Inspection response; result is null until a run has
  produced one.
- **Errors:** `404` if the execution does not exist.

### `GET /api/v1/executions/{execution_id}/artifacts`

- **Purpose:** Retrieve metadata for artifacts attached to that execution.
- **Success (`200`):** Artifact names, media types, and byte sizes. Local
  filesystem paths are not exposed and arbitrary file paths are not accepted.
- **Errors:** `404` if the execution does not exist.

### `POST /api/v1/executions/{execution_id}/qa-workflow`

- **Purpose:** Start the LangGraph QA workflow for a queued execution.
- **Success (`200`):** Structured requirement analysis and ordered test plan,
  with `workflow_status = "WAITING_APPROVAL"` and
  `approval_phase = "INSPECTION"`. This first request does not launch a browser.
- **Workflow:** Approving inspection runs the existing safe Phase 3 browser
  inspection. The agents then map the observed evidence and generate test
  cases, after which the workflow pauses again at `approval_phase = "TEST_PLAN"`.
- **Errors:** `404` if missing; `409` unless queued; `422` for an unsafe target;
  `502` for agent/inspection failure; `503` if the configured Ollama provider is
  unavailable or misconfigured.

### `POST /api/v1/executions/{execution_id}/qa-workflow/approval`

- **Body:** `{"decision":"APPROVED","reviewer_comment":"optional"}` or
  `{"decision":"REJECTED","reviewer_comment":"optional"}`.
- **Purpose:** Resume the persisted workflow after the current approval gate.
- **Behavior:** The first approval authorizes only the read-only browser
  inspection. The second reviews generated test cases before coordination.
  Rejection ends the execution using the existing `CANCELLED` status.
- **Errors:** `404` if missing; `409` if approval is not pending; `422` for an
  invalid decision; provider and agent errors as described above.

### `GET /api/v1/executions/{execution_id}/qa-workflow`

- **Purpose:** Retrieve persisted state, approval history, generated tests,
  outcomes, evidence-backed findings, and the structured QA report.
- **Persistence:** Workflow state and report are stored in nullable JSON columns
  on the existing execution row; migration `20261109_0003` adds them without
  replacing existing data or migration history.

The workflow uses local Ollama by default, sequential structured-output calls,
and does not download models. If Ollama is unavailable, it returns an explicit
actionable provider error. The execution coordinator evaluates only evidence
available from Phase 3 page-load and element inspection. It never clicks,
types, submits forms, performs transactions, probes arbitrary APIs, or performs
destructive actions. Unsupported cases are reported as `NOT_SUPPORTED`, not as
passed.

## Planned, not implemented

These endpoints remain future work and do not currently return business data:

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/v1/executions/{execution_id}/events` | Execution events |
| `GET` | `/api/v1/executions/{execution_id}/findings` | Findings |
| `GET` | `/api/v1/approvals/pending` | Pending approvals |

The generated report is currently included in the persisted QA workflow
response; a standalone report endpoint is not implemented.

Browser navigation blocks non-HTTP(S), credential-bearing, local, private,
link-local, and reserved destinations and revalidates browser requests,
including redirect destinations. WebSockets and non-GET/HEAD requests are
blocked. Chromium resolves hosts independently after
the application DNS check, so DNS rebinding cannot be completely prevented by
application routing alone. Use an outbound firewall or controlled egress proxy
for a production network boundary. Inspection is read-only and does not run
arbitrary user-provided scripts or browser actions. LangGraph agents analyze
user requirements and bounded inspection evidence, but do not control the
browser. Page scripts still run during rendering and GET endpoints may
themselves have side effects.
