#!/usr/bin/env bash

# Run the API on its own (foreground) with PostgreSQL persistence enabled.
# Ensures the local database exists, then starts uvicorn with reload.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# shellcheck source=/dev/null
source "$ROOT_DIR/scripts/ensure-db.sh"
ensure_movon_database

cd "$ROOT_DIR/apps/api"
exec env PYTHONPATH=src MOVON_DATABASE_URL="$MOVON_DATABASE_URL" \
  uv run uvicorn movon_hr.main:app --reload --host 0.0.0.0 --port 8000
