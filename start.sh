#!/usr/bin/env bash
# start.sh - Production entrypoint for Render
# - Runs Alembic migrations (reads DATABASE_URL from env)
# - Starts the FastAPI app with uvicorn on $PORT
# - Exits on any error to avoid starting with an inconsistent DB

set -euo pipefail

# PORT provided by Render; default to 8000 for local testing
: "${PORT:=8000}"

echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] start.sh: Running DB migrations (alembic upgrade head)"
# Alembic reads DATABASE_URL from the environment; prefer platform-provided value
alembic upgrade head

echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] start.sh: Migrations completed; starting uvicorn"
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT}" --proxy-headers
