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

# Run alembic upgrade and capture errors. If upgrade fails due to existing
# schema objects (DuplicateColumn/DuplicateTable) we optionally auto-stamp the
# DB to the current head when AUTO_STAMP=true to recover from manual schema
# application (use with caution).
TMP_ERR=$(mktemp)
if python -m alembic upgrade head 2>"$TMP_ERR"; then
	echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] start.sh: alembic upgrade succeeded"
else
	echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] start.sh: alembic upgrade failed; inspecting error" >&2
	# Read error and look for common 'already exists' patterns
	ERR_TEXT=$(sed -n '1,200p' "$TMP_ERR" | tr '\n' ' ')
	echo "alembic error: ${ERR_TEXT}" >&2
	if echo "$ERR_TEXT" | grep -E "already exists|DuplicateColumn|DuplicateTable" >/dev/null 2>&1; then
		if [ "${AUTO_STAMP:-false}" = "true" ]; then
			echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] start.sh: Detected existing schema objects and AUTO_STAMP=true; stamping alembic head"
		  # Ensure alembic_version.version_num can hold longer revision identifiers
		  echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] start.sh: Ensuring alembic_version.version_num column is large enough"
		  python - <<'PY'
	import os
	from sqlalchemy import create_engine, text
	url = os.environ.get('DATABASE_URL')
	if not url:
		raise SystemExit('DATABASE_URL missing')
	# Convert async URL to sync for SQLAlchemy engine if needed
	sync_url = url.replace('+asyncpg','')
	try:
		engine = create_engine(sync_url)
		with engine.connect() as conn:
			try:
				conn.execute(text("ALTER TABLE IF EXISTS alembic_version ALTER COLUMN version_num TYPE VARCHAR(255)"))
			except Exception:
				# best-effort; continue
				pass
	finally:
		try:
			engine.dispose()
		except Exception:
			pass
	PY
		  python -m alembic stamp head
			echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] start.sh: alembic stamped head successfully"
		else
			echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] start.sh: Migration failed due to existing schema objects." >&2
			echo "If this is intentional (schema already created), set AUTO_STAMP=true to mark migrations as applied." >&2
			echo "Captured alembic error:" >&2
			sed -n '1,200p' "$TMP_ERR" >&2
			rm -f "$TMP_ERR"
			exit 1
		fi
	else
		echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] start.sh: alembic upgrade failed with unexpected error" >&2
		sed -n '1,200p' "$TMP_ERR" >&2
		rm -f "$TMP_ERR"
		exit 1
	fi
fi
rm -f "$TMP_ERR"

echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] start.sh: Migrations completed; starting uvicorn"
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT}" --proxy-headers
