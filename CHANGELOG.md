## v1.1.0 — HealthCheckSuite + TenantRegistry Implemented
- Added /health and /health/deep endpoints for system diagnostics.
- Deep health check covers DB, Gmail, OneDrive, WhatsApp, Scheduler.
- Added /admin/tenants CRUD APIs for tenant management.
- Pydantic models for tenant input/output.
- Structured logging and audit events for all admin operations.
- Modular, async, and ready for future admin features.

## v1.0.0 — SchedulerEngine + Jobs Implemented
- Added APScheduler-based background job system.
- Job for retrying WhatsApp notifications (pending/retry/failed).
- Job for processing queued OneDrive Excel update actions.
- Job for sending reminders for pending/stale quotes.
- Job for daily health reports.
- Integrated structured logging, audit logs, and Slack alerts for all jobs.
- Modular, async, and production-ready.

## v0.9.0 — DocumentiV1 Engine Started
- Initial scaffolding for DocumentiV1 business flow.
- Designed for document ingestion, classification, and metadata extraction.
- Ready for integration with GmailIngress, EventNormalizer, and OneDriveConnector.
- Audit and structured logging hooks in place.
- Modular, async, and multi-tenant ready.

## v0.8.0 — WhatsAppMessenger Implemented
- Added WhatsAppMessenger module for multi-tenant messaging.
- High-level API for enqueueing text, template, and media messages.
- Notification queue entries in DB with status tracking.
- Low-level WhatsApp API connector for sending messages via Facebook Graph API.
- Structured logging and audit logging for all operations.
- Slack alerts for unexpected errors.
- Fully typed, async, modular, and production-ready.

## v0.7.0 — OneDriveConnector Implemented
- Added OneDriveConnector module for Excel integration via Microsoft Graph API.
- Implemented authentication with client credentials.
- Provided update_quote_excel for quote/customer Excel updates.
- Row matching logic by external_reference, quote.id, or new row.
- QuoteDocumentAction queue model for Excel update actions.
- Enqueue function for safe Excel update scheduling.
- Placeholder for queue processor (to be scheduled).
- Full logging, audit, and Slack alert integration.
- Fully typed, async, and reusable for future flows.

## v0.6.0 — PreventiviV1 Engine Implemented
- Added full PreventiviV1 business engine.
- LLM-based classification of incoming messages.
- Entity extraction pipeline (nome, cognome, telefono, indirizzo, descrizione lavori).
- Customer creation + update logic.
- Quote creation + update logic.
- WhatsApp notification enqueueing.
- Excel update enqueueing for OneDriveConnector.
- Complete audit logging for all operations.
- Integrated structured logging and Slack alerts.

## v0.5.0 — FlowRouter Implemented
- Added FlowRouter with route_normalized_event(normalized_event_id).
- Implemented tenant- and flow-aware routing logic.
- Connected NormalizedEvent to PreventiviV1 as the initial active flow.
- Added audit events for routing start, completion, and failures.
- Integrated structured logging and Slack alerts for routing errors.
- Designed extension points for future flows (DocumentiV1, AttrezzatureV1, UrgenzeV1).

## v0.4.0 — EventNormalizer Implemented
- Added complete normalization pipeline converting RawEvent → NormalizedEvent.
- HTML → text extraction with signature and boilerplate cleanup.
- Sender and metadata normalization.
- Tenant-based flow resolution.
- NormalizedEvent persistence with audit logging.
- Automatic routing to FlowRouter.
- Integrated structured logging and Slack alerts.

## v0.3.0 — GmailIngress + GmailConnector
- Implemented Gmail Pub/Sub webhook receiver.
- Added Base64 URL-safe Pub/Sub decoding.
- Full Gmail message fetch via Gmail API.
- Robust MIME parser (text/html, text/plain, attachments metadata).
- RawEvent persistence with idempotency on message_id.
- Automatic routing to EventNormalizer.
- Integrated structured logging, audit logs, and Slack alerts.

## v0.2.0 — MonitoringCenter Implemented
- Added structured JSON logging with request_id, tenant_id, flow_id.
- Implemented audit logging system with persistence to AuditLog.
- Integrated Slack alert notifications for errors and exceptions.
- Global exception handler with logging, audit, and Slack alerts.
- Request_id middleware for automatic injection and propagation.
- Modular and reusable monitoring across all backend modules.

## v0.1.0 — CoreConfig + DataLayer
- Implemented Pydantic Settings for configuration management.
- Added SQLAlchemy 2.0 async session and declarative base.
- Created tenant-aware models: Tenant, ExternalToken, RawEvent, NormalizedEvent, Customer, Quote, Notification, AuditLog.
- Implemented CRUD repositories for all core models.
- Ensured multi-tenant fields and idempotency in data layer.
- No business logic, only structure and DB foundation.
