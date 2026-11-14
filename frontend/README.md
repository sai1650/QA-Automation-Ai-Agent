# Autonomous QA Intelligence Platform — Frontend

Responsive React + TypeScript frontend for the existing FastAPI backend.

## Requirements

- Node.js 20.19+ or 22.12+
- Backend running locally at `http://127.0.0.1:8000` by default

## Run locally

```powershell
cd frontend
npm install
Copy-Item .env.example .env
npm run dev
```

Open the Vite URL shown in the terminal (normally `http://localhost:5173`).
The Vite development server proxies API and health requests to
`http://127.0.0.1:8000`, avoiding local CORS configuration changes. Set
`VITE_API_BASE_URL` in `.env` if the backend is hosted elsewhere. It should
point to the versioned API root, for example:

```dotenv
VITE_API_BASE_URL=https://your-backend.example/api/v1
```

For direct browser-to-backend requests (such as a production deployment), the
backend's `CORS_ORIGINS` setting must allow the frontend's origin.

## Validate / build

```powershell
npm run lint
npm run build
npm run preview
```

## Backend integration notes

The UI uses the existing API; it does not add backend routes or simulate
successful operations. Its project, execution, knowledge, and evaluation
actions are limited to operations exposed by the backend. Approval confirmations
are shown before protected actions. Browser inspection remains subject to the
backend's safe GET/HEAD-only restrictions.

Some backend capabilities do not have corresponding endpoints. Agent telemetry
and editable system settings are therefore presented as architectural or
read-only information. Bug and report views derive from persisted workflow
responses, and can be incomplete when the backend has no workflow response for
an execution.
