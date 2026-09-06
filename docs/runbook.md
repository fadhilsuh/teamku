# Deployment notes

Use PostgreSQL, Redis, and private S3-compatible storage; do not deploy the demo in-memory adapter. Run `alembic upgrade head` as a controlled job before an API release. Set `MOVON_SESSION_COOKIE_SECURE=true` behind HTTPS, keep cookies HttpOnly, restrict CORS origins, enable encryption at rest, backups, and worker retry/dead-letter monitoring. Invite and reset emails currently log to the API process; wire SMTP before production onboarding. Preserve audit history during retention deletion/anonymization. Incident logs must omit HR payloads and secrets.
