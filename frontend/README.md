# CareerLift AI — Frontend

A premium dark-themed React SPA for the CareerLift AI interview-preparation platform. It talks to the
existing local FastAPI backend and keeps **technical** and **communication** scoring visibly separate
(FairScore). No fabricated statistics: every number comes from the backend or is shown as an honest
empty / "not assessed" state.

## Stack
React 18 · Vite 5 · React Router · Tailwind CSS · Lucide icons · Framer Motion · Recharts

## Prerequisites
- Node.js 18+ (tested on 24.x) and npm
- The CareerLift backend running locally (see below)

## Run the backend (from the project root, inside WSL/Ubuntu or any env with the project's venv)

```bash
# port 8000, local SQLite, local auth pepper
CAREERLIFT_DB=./careerlift.db \
CAREERLIFT_AUTH_PEPPER=change-me-locally \
python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

The backend allows the Vite dev origin (`http://localhost:5173`) via CORS. To use a different port,
set `CAREERLIFT_CORS_ORIGINS` (comma-separated) when starting the backend.

> Scoring an answer (`POST /score`) is the only path that calls the model. Running it with real AWS
> credentials will incur charges. The UI works end-to-end without it except for producing a real score;
> inputs containing personal data are rejected deterministically with no model call.

## Run the frontend (from `frontend/`)

```bash
npm install
cp .env.example .env     # optional; defaults to http://localhost:8000
npm run dev              # http://localhost:5173
```

Build / preview:

```bash
npm run build
npm run preview
```

## Configuration
- `VITE_API_BASE` (in `.env`) — backend base URL. Default `http://localhost:8000`.

## How identity works
Registration is anonymous: the **server** generates the student id and a bearer token. The token is
shown once and stored in this browser's `localStorage` for the local prototype. The client never
chooses the identity, and the backend grades against its own stored expected concepts — the client
cannot influence scoring.

## Pages
Landing · Register · Dashboard · Practice Interview · My Progress · Misconceptions · Learning Planner ·
Reports.
