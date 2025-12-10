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
