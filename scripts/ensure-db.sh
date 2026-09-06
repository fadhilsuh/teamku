#!/usr/bin/env bash

# Ensure a local PostgreSQL database exists for Teamku and expose MOVON_DATABASE_URL.
#
# Can be either:
#   * sourced   -> defines/export MOVON_DATABASE_URL and the ensure_movon_database function
#   * executed  -> ensures the database then prints the connection URL
#
# Overridable via environment:
#   MOVON_DB_HOST (default localhost)   MOVON_DB_PORT (default 5432)
#   MOVON_DB_USER (default movon)       MOVON_DB_PASSWORD (default movon)
#   MOVON_DB_NAME (default movon)       PGADMIN_USER (default current OS user)
#   MOVON_DATABASE_URL (if set, used as-is and no parts are derived)

set -euo pipefail

MOVON_DB_HOST="${MOVON_DB_HOST:-localhost}"
MOVON_DB_PORT="${MOVON_DB_PORT:-5432}"
MOVON_DB_USER="${MOVON_DB_USER:-movon}"
MOVON_DB_PASSWORD="${MOVON_DB_PASSWORD:-movon}"
MOVON_DB_NAME="${MOVON_DB_NAME:-movon}"
PGADMIN_USER="${PGADMIN_USER:-$(whoami)}"

# Derive the async SQLAlchemy URL used by the API unless the caller pinned one.
export MOVON_DATABASE_URL="${MOVON_DATABASE_URL:-postgresql+asyncpg://${MOVON_DB_USER}:${MOVON_DB_PASSWORD}@${MOVON_DB_HOST}:${MOVON_DB_PORT}/${MOVON_DB_NAME}}"

_pg_bin() {
  # Prefer tools already on PATH, then common Homebrew locations.
  if command -v "$1" >/dev/null 2>&1; then
    command -v "$1"
    return 0
  fi
  local candidate
  for candidate in \
    "/usr/local/opt/postgresql@16/bin/$1" \
    "/opt/homebrew/opt/postgresql@16/bin/$1" \
    "/usr/local/opt/postgresql/bin/$1" \
    "/opt/homebrew/opt/postgresql/bin/$1"; do
    if [[ -x "$candidate" ]]; then
      echo "$candidate"
      return 0
    fi
  done
  return 1
}

ensure_movon_database() {
  local psql pg_isready
  if ! psql="$(_pg_bin psql)"; then
    echo "psql not found. Install PostgreSQL (e.g. 'brew install postgresql@16') and retry." >&2
    return 1
  fi
  pg_isready="$(_pg_bin pg_isready || true)"

  # Make sure the server is up; try to start the Homebrew service if it isn't.
  if [[ -n "$pg_isready" ]] && ! "$pg_isready" -h "$MOVON_DB_HOST" -p "$MOVON_DB_PORT" >/dev/null 2>&1; then
    if command -v brew >/dev/null 2>&1; then
      echo "PostgreSQL not reachable on ${MOVON_DB_HOST}:${MOVON_DB_PORT}; attempting 'brew services start postgresql@16'."
      brew services start postgresql@16 >/dev/null 2>&1 || true
      for _ in {1..15}; do
        "$pg_isready" -h "$MOVON_DB_HOST" -p "$MOVON_DB_PORT" >/dev/null 2>&1 && break
        sleep 1
      done
    fi
  fi

  if [[ -n "$pg_isready" ]] && ! "$pg_isready" -h "$MOVON_DB_HOST" -p "$MOVON_DB_PORT" >/dev/null 2>&1; then
    echo "PostgreSQL is not accepting connections on ${MOVON_DB_HOST}:${MOVON_DB_PORT}." >&2
    return 1
  fi

  # Create the login role if missing.
  if ! "$psql" -h "$MOVON_DB_HOST" -p "$MOVON_DB_PORT" -U "$PGADMIN_USER" -d postgres -tAc \
      "SELECT 1 FROM pg_roles WHERE rolname='${MOVON_DB_USER}'" | grep -q 1; then
    "$psql" -h "$MOVON_DB_HOST" -p "$MOVON_DB_PORT" -U "$PGADMIN_USER" -d postgres -v ON_ERROR_STOP=1 -c \
      "CREATE ROLE ${MOVON_DB_USER} LOGIN PASSWORD '${MOVON_DB_PASSWORD}';"
    echo "Created PostgreSQL role '${MOVON_DB_USER}'."
  fi

  # Create the database if missing.
  if ! "$psql" -h "$MOVON_DB_HOST" -p "$MOVON_DB_PORT" -U "$PGADMIN_USER" -d postgres -tAc \
      "SELECT 1 FROM pg_database WHERE datname='${MOVON_DB_NAME}'" | grep -q 1; then
    "$psql" -h "$MOVON_DB_HOST" -p "$MOVON_DB_PORT" -U "$PGADMIN_USER" -d postgres -v ON_ERROR_STOP=1 -c \
      "CREATE DATABASE ${MOVON_DB_NAME} OWNER ${MOVON_DB_USER};"
    echo "Created PostgreSQL database '${MOVON_DB_NAME}'."
  fi

  echo "PostgreSQL ready at ${MOVON_DB_HOST}:${MOVON_DB_PORT} (db=${MOVON_DB_NAME}, user=${MOVON_DB_USER})."
}

# When run directly (not sourced), do the work and print the URL.
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  ensure_movon_database
  echo "MOVON_DATABASE_URL=${MOVON_DATABASE_URL}"
fi
