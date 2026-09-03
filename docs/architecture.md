# Architecture

```mermaid
flowchart LR
Browser[Next.js web] -->|REST /api/v1| API[FastAPI modular monolith]
API --> PG[(PostgreSQL)]
API --> Redis[(Redis / worker queue)]
API --> Storage[Private S3 / MinIO]
Worker[Celery worker] --> PG
Worker --> Storage
```

Production repositories implement tenant-scoped SQLAlchemy persistence, with every mutation inside a unit of work and audit/outbox record. API routers remain thin; attendance, requests, approvals, and payroll calculations are application use cases with pure domain rules.
