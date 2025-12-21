## Edilcos Automation Backend - Docs Index

This repository contains modular integrations for handling inbound emails, WhatsApp, file storage and more.

Top-level modules:
- OneDrive integration: `docs/ONEDRIVE.md` (discovery, OAuth app-only, troubleshooting)
- Activation checklist: `docs/ACTIVATION.md` (setup steps)
- Monitoring & logging: `app/monitoring/` (structured logs + Slack alerts)

Use the files under `docs/` for operational runbooks and developer onboarding.
# Operational Documentation - Automation Humanaise Backend

## PURPOSE
- This backend provides a multi-tenant webhook-based ingestion and processing platform for email (Gmail), messaging (WhatsApp), document management (OneDrive/SharePoint), and related flows (quotes, documents, equipment). It normalizes incoming events, routes them to tenant-specific flows, persists raw and processed events, and integrates with external providers for file storage and notifications.

## CURRENT SYSTEM STATUS
### Modules
- API (FastAPI): READY
- DB (SQLAlchemy): READY (requires migrations applied)
- OneDrive integration: IN PROGRESS (personal-site discovery + integration event logs implemented)
- Gmail ingress: READY (raw events saved, normalizer present)
- WhatsApp integration: IN PROGRESS (webhook + notifications implemented)
- Monitoring & Alerts (Slack): READY (basic alerts implemented)

### Status Legend
- READY: Implemented and test-covered
- IN PROGRESS: Implemented but requiring migrations, further tests, or operational verification
- BLOCKED: Requires external admin action, credentials, or migration

### Current Items
- READY:
  - Core API, routing, and basic flows (`preventivi_v1`, `documenti_v1`)
  - Raw event persistence for Gmail and webhook ingestion
- IN PROGRESS:
  - OneDrive discovery fallbacks and integration events (see `ONEDRIVE.md`)
  - WhatsApp end-to-end operational verification (see `WHATSAPP.md`)
- BLOCKED:
  - Full test-suite integration: test DB migrations need applying (some tests expect existing tables). See migration files in `migrations/` and `docs/ONEDRIVE.md` for `integration_events` migration.

## ACTIVATION ROADMAP (GLOBAL)
Follow these steps to activate the system in a new environment. Each item references the integration document with detailed steps.

1. Provision infrastructure and DB.
   - Apply DB migrations from `migrations/` (See `ONEDRIVE.md` for new migration `003_add_integration_events.sql`).
2. Configure environment variables (see Environment section below and each module doc):
   - `DATABASE_URL`, `REDIS_URL`, `LOG_LEVEL`, `MS_ACCESS_TOKEN`, `MS_DRIVE_ID`, `ONEDRIVE_HOSTNAME`, `ONEDRIVE_BASE_PATH`, `WHATSAPP_API_TOKEN`, `GMAIL_PUBSUB_*` etc. (See `ONEDRIVE.md`, `WHATSAPP.md`, `GMAIL.md`).
3. Create tenant and flow configurations (admin API or DB fixtures). See `app/db/repositories/tenant_repository.py`.
4. Verify integrations:
   - OneDrive: run discovery test with `MS_ACCESS_TOKEN` in `TestTokenAuth` mode (See `ONEDRIVE.md`).
   - Gmail: enable Pub/Sub push/verify signature and send test email. (See `GMAIL.md`).
   - WhatsApp: configure webhook URL/token and send test message (See `WHATSAPP.md`).
5. Start the service (production/wsgi/uvicorn) and verify `/health` and `/ready` endpoints.
6. Validate flows by sending sample events and checking `processed_events`, `preventivi`, and `documents` records.

## INTEGRATIONS OVERVIEW
| Integration | Purpose | Status | Docs |
|---|---|---:|---|
| OneDrive | Store and manage attachments, upload processed docs | IN PROGRESS | `docs/ONEDRIVE.md` |
| Gmail | Receive inbound email, raw event storage, trigger flows | READY | `docs/GMAIL.md` |
| WhatsApp | Send/receive messages, notify tenants | IN PROGRESS | `docs/WHATSAPP.md` |
| Slack Alerts | Send critical alerts and monitoring notifications | READY | `docs/SLACK.md` |

## ENVIRONMENT & CONFIG OVERVIEW
- Core vars: `DATABASE_URL`, `REDIS_URL`, `LOG_LEVEL`.
- OneDrive: `MS_ACCESS_TOKEN` (test), `MS_DRIVE_ID`, `ONEDRIVE_HOSTNAME`, `ONEDRIVE_BASE_PATH`.
- Gmail: Pub/Sub credentials or verification tokens; see `GMAIL.md`.
- WhatsApp: `WHATSAPP_API_TOKEN`, webhook verification token.

Refer to each module doc for exact names and examples.

## OPERATIONAL RULES
- Separation: Use distinct credentials and `tenant_id` values for test vs production.
- Logging: Use structured JSON logs via `app.monitoring.logger` for all events; persist important decision points to DB (e.g., `integration_events`).
- Safety:
  - Never store raw credentials in the DB or commit them to code.
  - All OneDrive file operations must be constrained under `ONEDRIVE_BASE_PATH`.
  - Use idempotency keys for incoming webhook events.

## UPDATE RULES
- When code changes affect integrations, update the respective `docs/*.md` file and this master `docs/README.md`.
- Document any added environment variables in the module file and run the documentation checklist CI (see `docs/MAINTAINING_DOCS.md`).

---

Generated on: 2025-12-13
