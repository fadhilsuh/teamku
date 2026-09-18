# Teamku

Teamku, powered by movon digital house, is a modular, API-first HRIS MVP for Indonesian teams. This repository contains independently deployable Next.js and FastAPI applications.

## Local start

1. Copy `.env.example` to `.env`.
2. Run `docker compose -f infra/compose/docker-compose.yml up --build`.
3. Open `http://localhost:3000`; API documentation is at `http://localhost:8000/docs`.

For a quick API-only setup, install from `apps/api` with `uv sync --all-groups`, then run `uv run uvicorn movon_hr.main:app --reload`.

## Persistence

Set `MOVON_DATABASE_URL` (e.g. `postgresql+asyncpg://movon:movon@localhost:5432/movon`) and every input is stored in PostgreSQL: the store is hydrated from the database on startup and written back after each mutating request, so data survives restarts. The docker compose stack wires this automatically and keeps Postgres data in the `postgres_data` volume. When `MOVON_DATABASE_URL` is unset, the API falls back to the ephemeral in-memory demo store (used by the tests).

Demo credentials: `hr@movon.test` / `Demo123!`, `manager@movon.test` / `Demo123!`, and `employee@movon.test` / `Demo123!`. New companies can self-serve at `/signup`. Sessions are stored in an HttpOnly cookie (`teamku_session`); invite and password-reset links are emailed to the process log in development.

Schema changes live in `apps/api/alembic`. Run `uv run alembic upgrade head` from `apps/api` against PostgreSQL. The API still creates missing tables on startup for local compose.

## Architecture and boundaries

The web app only renders UI and calls `/api/v1`; authorization, calculation, validation, audit events, and persistence belong to the Python API. PostgreSQL is the supported production database. The in-memory repository is deliberately a development/demo adapter, not a production path.

Implemented demo vertical slices: authenticated role-aware dashboards; searchable employee directory with HR create/status actions; camera/location attendance with server-side Haversine validation, idempotency and agenda; leave request history, balance impact, cancellation and manager/HR decisions; in-app notifications; and a decimal-safe payroll calculation, finalization, locking and publishing flow.

Without `MOVON_DATABASE_URL` the local demo repository is intentionally in-memory, so data resets whenever the API process restarts. That mode is useful for evaluating the complete UI workflows; configure PostgreSQL (see Persistence above) to keep all input across restarts.

Attendance is browser verification, not liveness or anti-spoofing. A selfie is captured from the live camera (never uploaded from a gallery), location accuracy is recorded, and out-of-range/low-confidence results are review signals.

## Quality commands

```bash
cd apps/api && uv run pytest && uv run ruff check .
cd apps/web && npm run lint && npm run build
```

## Deployment

Repositori tetap monorepo; yang terpisah hanya target deploy-nya.

| Bagian | Target | Catatan |
|---|---|---|
| `apps/web` | Vercel | Root Directory `apps/web`, Build Command `npm run build` |
| `apps/api` | Server Biznet | Wajib **satu instance**. Instance yang dipakai `apps/web` saat ini: `https://api-teamku.movoncreative.dev` |

Browser hanya berbicara ke domain Vercel. `apps/web/next.config.ts` mem-proxy
`/api/*` ke `${MOVON_API_ORIGIN}/api/v1/*`, sehingga cookie sesi tetap
first-party dan tidak ada CORS di jalur browser.

`MOVON_API_ORIGIN` dibutuhkan saat **build**, bukan runtime — Next membakukan
rewrite ke `routes-manifest.json`. Bila kosong, build tetap berhasil namun
mem-proxy ke `localhost`. `apps/web/scripts/require-api-origin.mjs` berjalan
sebagai `prebuild` dan menggagalkan build bila variabel kosong di Vercel/CI.
Karena itu Build Command harus `npm run build`, bukan `next build`.

API tidak boleh di-scale lebih dari satu instance: store-nya in-process dan
`save_store` menulis ulang seluruh baris tenant tiap request mutasi, sehingga
instance kedua akan saling menimpa data.

Langkah lengkap ada di
[docs/plans/2026-09-12-001-migrate-web-to-vercel-plan.md](docs/plans/2026-09-12-001-migrate-web-to-vercel-plan.md).

## Operations

See [docs/architecture.md](docs/architecture.md), [docs/privacy-and-permissions.md](docs/privacy-and-permissions.md), and [docs/runbook.md](docs/runbook.md). In production configure PostgreSQL, Redis, private S3-compatible storage, HTTPS-only cookie settings, encryption at rest, a malware scanning adapter, and worker processes. The MVP intentionally leaves Indonesian tax/BPJS logic as transparent manual/configurable components rather than claiming compliance.
