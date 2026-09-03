# Movon HR

Movon HR is a modular, API-first HRIS MVP for Indonesian teams. This repository contains independently deployable Next.js and FastAPI applications.

## Local start

1. Copy `.env.example` to `.env`.
2. Run `docker compose -f infra/compose/docker-compose.yml up --build`.
3. Open `http://localhost:3000`; API documentation is at `http://localhost:8000/docs`.

For a quick API-only setup, install from `apps/api` with `uv sync --all-groups`, then run `uv run uvicorn movon_hr.main:app --reload`.

Demo credentials: `hr@movon.test` / `Demo123!`, `manager@movon.test` / `Demo123!`, and `employee@movon.test` / `Demo123!`.

## Architecture and boundaries

The web app only renders UI and calls `/api/v1`; authorization, calculation, validation, audit events, and persistence belong to the Python API. PostgreSQL is the supported production database. The in-memory repository is deliberately a development/demo adapter, not a production path.

Implemented vertical slice: authenticated role-aware dashboard; employee directory; camera/location attendance with server-side Haversine validation, idempotency and agenda; leave request submission/approval; and a decimal-safe payroll run calculation/publish flow. The API returns a clear `501` for future modules instead of pretending they are complete.

Attendance is browser verification, not liveness or anti-spoofing. A selfie is captured from the live camera (never uploaded from a gallery), location accuracy is recorded, and out-of-range/low-confidence results are review signals.

## Quality commands

```bash
cd apps/api && uv run pytest && uv run ruff check .
cd apps/web && npm run lint && npm run build
```

## Operations

See [docs/architecture.md](docs/architecture.md), [docs/privacy-and-permissions.md](docs/privacy-and-permissions.md), and [docs/runbook.md](docs/runbook.md). In production configure PostgreSQL, Redis, private S3-compatible storage, HTTPS-only cookie settings, encryption at rest, a malware scanning adapter, and worker processes. The MVP intentionally leaves Indonesian tax/BPJS logic as transparent manual/configurable components rather than claiming compliance.
