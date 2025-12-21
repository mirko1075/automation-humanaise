# TODO List & Tech Specs

This file aggregates actionable TODO anchors that were added as code comments across the repository. Each entry contains: area tag, concise description, and technical acceptance criteria / suggested implementation notes.

---

- **TODO(monitoring)**: Expose `raw_events_received_total` counter
  - Description: Track number of raw events received per tenant and flow.
  - File/Location: app/api/ingress/gmail_webhook.py
  - Tech spec: Prometheus counter `raw_events_received_total{tenant,flow,outcome}`; increment on each incoming webhook. Expose via existing metrics endpoint.
  - Acceptance: Metric emits with tenant label in integration test; visible in `/metrics`.

- **TODO(monitoring)**: Expose `raw_event_processing_latency_seconds` histogram
  - Description: Measure end-to-end normalization latency.
  - File/Location: app/core/normalizer/service.py
  - Tech spec: Prometheus histogram buckets [0.1, 0.5, 1, 5, 10, 30, 60]; label by `tenant,flow,outcome`.
  - Acceptance: Histogram records per-normalizer run; tests assert latency sample existence.

- **TODO(monitoring)**: Expose `in_flight_normalizations` gauge
  - Description: Gauge of concurrent normalizer runs.
  - File/Location: app/core/normalizer/service.py
  - Tech spec: Increment at start, decrement on finish (success/failure). Label `tenant`.

- **TODO(alerting)**: Alert on commit failures
  - Description: Trigger alert if DB commit fails repeatedly for the same tenant.
  - File/Location: app/core/normalizer/service.py
  - Tech spec: Alert when `raw_event_failures_total{tenant,phase="commit"}` > 3 in 5m. Pager duty / Slack webhook integration required.
  - Acceptance: Simulated commit failure increments metric and fires alert rule in staging.

- **TODO(alerting)**: Alert on dead-letter spike
  - Description: Alert if dead-letter events exceed threshold.
  - File/Location: app/scheduler/jobs.py and monitoring config
  - Tech spec: Alert when `dead_letter_events_total{tenant}` increases by >10 in 10m or rate spike > baseline*3.

- **TODO(replay)**: Admin replay endpoint
  - Description: Provide safe admin endpoint to re-run normalization for a `raw_event_id` or a time window.
  - File/Location: app/api/admin/replay.py (new)
  - Tech spec: `POST /admin/raw_events/{raw_event_id}/replay` with JSON body `{force: bool}`. Requires admin role (`get_current_admin`). Audited in `audit` table. Response returns job id. Rate-limit to avoid thundering herd.
  - Acceptance: Endpoint exists in tests and re-enqueues normalization run; audit row created.

- **TODO(replay)**: Durable raw payload storage fallback
  - Description: If DB persistence repeatedly fails, store raw payload to durable object storage (S3/MinIO) with reference in DB.
  - File/Location: app/api/ingress/gmail_webhook.py
  - Tech spec: On second consecutive persistence failure for same idempotency key, write payload to configured `OBJECT_STORE_BUCKET` and store `raw_storage_url` in a `raw_event_fallbacks` table or `RawEvent` JSON field (v2).

- **TODO(observability)**: Persist classifier decision trace
  - Description: Emit or persist classifier `reason` for audit and debugging.
  - File/Location: app/core/classifier.py and app/core/normalizer/service.py
  - Tech spec: Add optional `classification_reason` in `NormalizedEvent.normalized_data` (or attach to logs/traces). Redact PII. v2 candidate.

- **TODO(v2)**: Persist classification outcome on RawEvent/NormalizedEvent
  - Description: Add structured storage for classifier outcome for later analytics and debugging.
  - File/Location: app/core/normalizer/service.py and db models (schema change required in v2)
  - Tech spec: Add `classification_outcome`, `classification_reason`, timestamp fields (JSONB) to `ProcessedEvent`/`NormalizedEvent` in planned migration.

- **TODO(v2)**: Dispatcher DB-level UPSERTs
  - Description: Replace application-level existence checks with `ON CONFLICT` upserts to reduce race windows.
  - File/Location: app/core/dispatcher.py
  - Tech spec: Use SQLAlchemy `insert().on_conflict_do_update()` or raw SQL for Postgres to atomically upsert by natural keys (customer email + tenant, quote.external_ref). Add migration if needed.

- **TODO(perf)**: Batch dispatcher writes for high throughput
  - Description: For high-volume tenants, offer a batched mode to apply multiple dispatch writes in a single transaction.
  - File/Location: app/core/dispatcher.py and scheduler/worker implementation
  - Tech spec: API to accept list of DTOs and write them in vectorized fashion; measure memory/latency tradeoffs.

- **TODO(perf)**: Cache tenant routing/rules
  - Description: Cache tenant-specific classifier rules/config to avoid DB lookup per event.
  - File/Location: app/core/classifier.py
  - Tech spec: in-memory LRU with TTL, or Redis cache; invalidation on admin flow updates.

- **TODO(ops)**: Worker queue depth and replay job runbook
  - Description: Document runbook for resolving stuck worker queues and how to manually re-enqueue events.
  - File/Location: docs/OP_RUNBOOK.md (new) and app/scheduler/jobs.py
  - Tech spec: Steps to inspect DB queries, check `RawEvent.processed=false` rows older than threshold, re-run worker, manually call replay endpoint.

- **TODO(ops)**: Expose admin metrics and UIs
  - Description: Provide simple admin pages or endpoints to list `RawEvent` statuses, `NormalizedEvent` per tenant, and dead-letter queue.
  - File/Location: app/api/admin/*
  - Tech spec: Pagination, filtering by `tenant_id`, `created_at`, `outcome`. API protected by admin auth.

- **TODO(monitoring)**: Instrument dispatcher external API failures
  - Description: Track failures to OneDrive/WhatsApp/etc. per-tenant and per-external-system.
  - File/Location: app/integrations/* and app/core/dispatcher.py
  - Tech spec: Counters `external_api_failures_total{tenant,provider,error_type}`, with labels for HTTP status or exception class.

---

Guidance
- Place TODO anchors (exact text) next to the corresponding function/class in the referenced file so they are visible in code review.
- These TODOs are non-blocking; they are anchors and should not change runtime behavior.

If you want, I can now apply these TODO anchors into the actual files (`apply_patch`) so they appear inline where developers expect them. Tell me to proceed and I'll patch the listed modules.
