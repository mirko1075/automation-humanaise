#!/usr/bin/env bash
# start.sh - Production entrypoint for Render
# - Runs Alembic migrations (reads DATABASE_URL from env)
# - Starts the FastAPI app with uvicorn on $PORT
# - Exits on any error to avoid starting with an inconsistent DB

set -euo pipefail

# PORT provided by Render; default to 8000 for local testing
: "${PORT:=8000}"

echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] start.sh: Running DB migrations (alembic upgrade head)"
# If a local virtualenv exists, activate it so installed packages (alembic) are available
if [ -f ".venv/bin/activate" ]; then
	# shellcheck disable=SC1091
	. .venv/bin/activate
	echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] start.sh: Activated .venv"
fi

# Prefer running Alembic via the current Python interpreter to avoid relying on
# a system-wide `alembic` entrypoint being on PATH.
echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] start.sh: Running 'python -m alembic upgrade head'"
if [ -z "${DATABASE_URL-}" ]; then
	echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] start.sh: ERROR - DATABASE_URL is not set in the environment" >&2
	echo "To run locally, set DATABASE_URL, for example: export DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/dbname" >&2
	exit 1
fi

python -m alembic upgrade head

echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] start.sh: Migrations completed; starting uvicorn"
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT}" --proxy-headers
