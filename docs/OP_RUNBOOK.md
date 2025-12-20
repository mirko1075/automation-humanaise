# Operator Runbook: Normalizer & Replay

This runbook documents common operational steps for diagnosing and recovering
from stuck or failed normalization runs.

1) Inspect queue and DB
   - Query `raw_events` for unprocessed events:
     ```sql
     SELECT id, tenant_id, created_at, processed, updated_at
     FROM raw_events
     WHERE processed = false
     ORDER BY created_at ASC
     LIMIT 100;
     ```

2) Re-run a specific RawEvent (manual replay)
   - Use admin endpoint `POST /admin/raw_events/{raw_event_id}/replay` (requires admin auth).
   - The endpoint will enqueue a normalization job (or return accepted). Audit logs are created.

3) If many unprocessed events exist
   - Check worker processes: `ps aux | grep normalizer` or inspect supervisor/-systemd/Celery
   - Review logs for errors: grep for `normalizer` or `RawEvent` IDs
   - Consider scaling worker count temporarily

4) Recovering a transaction-aborted RawEvent
   - If normalization repeatedly aborts for the same id, inspect the `normalized_events` and `received_emails` tables for partial writes.
   - Use the replay endpoint after investigating the exception in logs; do not re-run blindly.

5) Dead-letter handling
   - Query `dead_letter_events` (if implemented) or `raw_events` with `attempts >= MAX_RETRIES`.
   - Export payloads for offline inspection and create tickets for developers.

6) Contacts and escalation
   - On DB outage: contact DBA / platform team.
   - On external API rate-limit: contact integrator (WhatsApp/OneDrive) and consider backoff.

Notes
 - Always capture logs and `raw_event_id` when opening an incident.
 - Use the replay endpoint to re-run events; ensure audit logs contain operator id.
