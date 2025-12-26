# chriseon
Multi-model AI orchestrator (web-first, desktop-ready).

## What it is
- Runs a multi-model round-robin refinement pipeline (A/B/C) and produces a synthesized final answer.
- Stores all intermediate artifacts and scoring for full transparency.
- Supports both BYOK and platform-managed provider keys.

## Repo layout
- `apps/web`: Next.js UI
- `services/api`: FastAPI API (SSE progress stream)
- `services/worker`: orchestration worker
- `infra`: local docker-compose

## Local development
Prereqs: Docker Desktop (daemon running), Node/pnpm, Python 3.

0) Verify Docker is running
- `docker ps`
If you see: `Cannot connect to the Docker daemon at unix:///.../docker.sock`, start Docker Desktop and retry.

1) Start Postgres + Redis
- `docker compose -f infra/docker-compose.yml up -d`

2) API + Worker (two terminals)
- API: `python3 -m venv services/api/.venv && services/api/.venv/bin/pip install -r services/api/requirements.txt && services/api/.venv/bin/uvicorn app.main:app --app-dir services/api --reload --port 8090`
- Worker: `python3 -m venv services/worker/.venv && services/worker/.venv/bin/pip install -r services/worker/requirements.txt && PYTHONPATH=services/worker services/worker/.venv/bin/python -m worker`

3) Web
- `pnpm -C apps/web install`
- `pnpm -C apps/web dev`

## Environment
Copy `.env.example` to `.env` and fill in:
- DB/Redis connection strings
- Encryption key for stored provider keys
- Optional platform-managed provider keys
