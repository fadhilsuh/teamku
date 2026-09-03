# Deployment notes

Use PostgreSQL, Redis, and private S3-compatible storage; do not deploy the demo in-memory adapter. Run migrations as a controlled job before an API release, set HTTPS-only Secure HttpOnly cookies, explicit CORS origins, encryption at rest, backups, and worker retry/dead-letter monitoring. Preserve audit history during retention deletion/anonymization. Incident logs must omit HR payloads and secrets.
