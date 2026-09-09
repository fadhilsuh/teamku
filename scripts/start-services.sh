#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_DIR="$ROOT_DIR/.service-pids"
LOG_DIR="$ROOT_DIR/.service-logs"

# Ensure PostgreSQL is ready and export MOVON_DATABASE_URL so the backend
# persists every input instead of using the ephemeral in-memory store.
# shellcheck source=/dev/null
source "$ROOT_DIR/scripts/ensure-db.sh"
ensure_movon_database

port_is_listening() {
  lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1
}

run_database_migrations() {
  local log_file="$LOG_DIR/migrations.log"

  echo "Checking backend database migrations..."
  if (
    cd "$ROOT_DIR/apps/api"
    env PYTHONPATH=src MOVON_DATABASE_URL="$MOVON_DATABASE_URL" uv run alembic upgrade head
  ) >"$log_file" 2>&1; then
    echo "Database migrations are up to date."
    return
  fi

  echo "Database migration failed." >&2
  echo >&2
  echo "----- Last 40 log lines -----" >&2
  tail -n 40 "$log_file" >&2
  echo "-----------------------------" >&2
  echo >&2
  echo "Full migration log: $log_file" >&2
  return 1
}

start_service() {
  local name="$1"
  local workdir="$2"
  local port="$3"
  local command="$4"
  local clear_cache="${5:-false}"
  local pid_file="$PID_DIR/$name.pid"
  local log_file="$LOG_DIR/$name.log"
  local pid=""

  if [[ -f "$pid_file" ]]; then
    pid="$(<"$pid_file")"
    if kill -0 "$pid" 2>/dev/null; then
      if port_is_listening "$port"; then
        echo "$name is already running (PID $pid, port $port)."
        return
      fi

      echo "$name process (PID $pid) exists but is not listening on port $port. Run ./scripts/stop-services.sh, then retry." >&2
      return 1
    fi

    echo "Removed stale $name PID file."
    rm -f "$pid_file"
  fi

  if port_is_listening "$port"; then
    echo "Port $port is already in use; $name was not started. Stop the process using that port before retrying." >&2
    return 1
  fi

  if [[ "$clear_cache" == "true" ]]; then
    rm -rf "$workdir/.next"
    echo "Cleared frontend cache: $workdir/.next"
  fi

  : >"$log_file"
  (
    cd "$workdir"
    nohup bash -c "exec $command" >"$log_file" 2>&1 &
    echo $! >"$pid_file"
  )

  pid="$(<"$pid_file")"
  for _ in {1..15}; do
    if port_is_listening "$port"; then
      echo "Started $name (PID $pid, port $port). Logs: $log_file"
      return
    fi

    if ! kill -0 "$pid" 2>/dev/null; then
      break
    fi
    sleep 1
  done

  echo "Failed to start $name. Check $log_file" >&2
  rm -f "$pid_file"
  return 1
}

mkdir -p "$PID_DIR" "$LOG_DIR"

run_database_migrations
start_service "backend" "$ROOT_DIR/apps/api" 8000 "env PYTHONPATH=src MOVON_DATABASE_URL=$MOVON_DATABASE_URL uv run uvicorn movon_hr.main:app --reload --host 0.0.0.0 --port 8000"
start_service "frontend" "$ROOT_DIR/apps/web" 3000 "npm run dev -- --hostname 0.0.0.0 --port 3000" true

echo "Teamku is available at http://localhost:3000 (API: http://localhost:8000/docs)."
