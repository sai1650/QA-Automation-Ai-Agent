# Autonomous QA Intelligence Platform (QA-Automation-Ai-Agent)

> 🌐 **Live Demo Application**: [https://e89d533bca933a.app.lhr.life](https://e89d533bca933a.app.lhr.life)  
> 📚 **API Documentation (Swagger UI)**: [https://e89d533bca933a.app.lhr.life/docs](https://e89d533bca933a.app.lhr.life/docs)  
> 🩺 **Backend Health Status**: [https://e89d533bca933a.app.lhr.life/health](https://e89d533bca933a.app.lhr.life/health)

An end-to-end AI-powered QA platform integrating agentic test planning, safe browser inspection with Playwright, structured test generation, bug analysis, RAG-assisted historical context, and an interactive React dashboard.

## Key Features

- **Multi-Agent QA Workflow**: Powered by LangGraph and local LLMs (Ollama) with requirement analysis, test planning, website understanding, test case generation, and bug analysis.
- **Safe Browser Inspection Engine**: Playwright-based headless browser runtime extracting DOM metadata, accessibility attributes, console logs, and visual screenshots with security boundaries and URL validation.
- **Historical QA Knowledge (RAG)**: Persistent ChromaDB vector store using local Sentence Transformers embeddings for historical QA reports, findings, and documentation retrieval.
- **Evaluation Benchmark Suite**: Benchmark catalog and metrics for evaluating agent performance, test quality, and retrieval precision.
- **Modern Web Dashboard**: High-performance React 18 + Vite frontend with TanStack Query, Lucide icons, and real-time execution tracking.

## Repository Structure

```
.
├── backend/                  # FastAPI backend service
│   ├── app/
│   │   ├── agents/          # Multi-agent QA workflow implementations
│   │   ├── ai/              # LLM provider abstractions (Ollama)
│   │   ├── api/             # REST API routers & routes
│   │   ├── graph/           # LangGraph state machine & edges
│   │   ├── models/          # SQLAlchemy ORM models
│   │   ├── rag/             # ChromaDB vector store & embeddings
│   │   ├── schemas/         # Pydantic v2 data contracts
│   │   ├── security/        # URL validation & SSRF prevention
│   │   └── services/        # Browser runtime & execution services
│   ├── migrations/          # Alembic schema migrations
│   └── tests/               # Pytest test suite
│
└── frontend/                 # React 18 + Vite dashboard
    ├── src/
    │   ├── api/             # Axios API client & endpoints
    │   ├── layout/          # AppShell & layout components
    │   ├── pages/           # Overview, Projects, Executions, Intelligence, Knowledge, Evaluations
    │   └── types.ts         # TypeScript schema definitions
    └── vite.config.ts       # Vite configuration with backend proxy
```

## Quick Start

### 1. Backend Setup

Prerequisites: Python 3.11+ and MySQL (or default SQLite).

```powershell
cd backend

# Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m playwright install chromium

# Environment configuration
Copy-Item .env.example .env

# Run database migrations
python -m alembic upgrade head

# Start FastAPI server
python -m uvicorn app.main:app --reload --port 8000
```

The backend API documentation is available at `http://127.0.0.1:8000/docs`.

### 2. Frontend Setup

Prerequisites: Node.js 18+.

```powershell
cd frontend

# Install dependencies
npm install

# Start Vite development server
npm run dev
```

Open `http://localhost:5173` in your browser.

## Running Tests

```powershell
cd backend
python -m pytest
```
