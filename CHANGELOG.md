## v1.3.0 — Multi-Protocol NAS Provider System (2024-12-11)

### Added

#### Core Infrastructure
- **Protocol-Agnostic Filesystem Interface** (`app/file_access/base_fs.py`)
  - New `FileStorageProvider` abstract base class with 15 async methods
  - `FileInfo`, `FileOperationResult`, `HealthCheckResult` dataclasses
  - Context manager support and streaming methods with default implementations
  - Complete type hints and comprehensive docstrings (350+ lines)

- **NAS Provider Orchestrator** (`app/file_access/nas_provider.py`)
  - Dynamic protocol adapter loading based on tenant configuration
  - Protocol registration mechanism for extensibility
  - Automatic adapter discovery and registration (250+ lines)
  - Health check enrichment with protocol metadata
  - Support for multiple protocols: SMB (implemented), NFS, WebDAV, SFTP, FTP/S (documented)

#### Protocol Adapters
- **SMB/CIFS Protocol Adapter** (`app/file_access/protocols/smb_protocol.py`)
  - Full implementation using `pysmb` library (750+ lines)
  - Connection management with username/password, domain support
  - Complete filesystem operations: list, read, write, delete, move, copy, mkdir, rmdir
  - Path normalization and validation
  - SMB-specific health checks and error handling
  - Async executor pattern for synchronous SMB library

- **Protocol Placeholders** with implementation guides:
  - `protocols/nfs_protocol.py` - NFS support guide
  - `protocols/webdav_protocol.py` - WebDAV support guide
  - `protocols/sftp_protocol.py` - SFTP support guide
  - `protocols/ftp_protocol.py` - FTP/FTPS support guide

#### Document Operations (Protocol-Agnostic)
- **Excel Operations** (`document_ops/excel_ops.py`, 280+ lines)
  - `read_excel()`, `write_excel()`, `update_excel()`, `create_excel_from_data()`
  - `read_excel_as_dict()`, `append_excel_row()`
  - Uses `openpyxl` library

- **PDF Operations** (`document_ops/pdf_ops.py`, 380+ lines)
  - `read_pdf_text()`, `extract_pdf_metadata()`, `merge_pdfs()`
  - `create_pdf()`, `split_pdf()`
  - Uses `pypdf` and `reportlab` libraries

- **Word Operations** (`document_ops/word_ops.py`, 350+ lines)
  - `read_word()`, `write_word()`, `create_word()`, `update_word()`
  - `extract_word_text()`, `add_word_paragraph()`, `add_word_table()`
  - Uses `python-docx` library

#### Testing & Documentation
- **Comprehensive Test Suite** (`tests/test_nas_provider.py`, 550+ lines)
  - 25+ test cases covering orchestration, adapters, operations, error handling
  - Mock-based unit tests with `AsyncMock` and `pytest-asyncio`

- **Complete Documentation**:
  - `docs/NAS_PROVIDER_GUIDE.md` (1000+ lines) - User guide with examples, troubleshooting
  - `docs/NAS_PROVIDER_IMPLEMENTATION_SUMMARY.md` - Technical architecture overview

#### Dependencies
- Added to `requirements.txt`:
  - `pysmb>=1.2.9` - SMB/CIFS protocol
  - `pypdf>=3.17.0` - PDF operations
  - `reportlab>=4.0.0` - PDF generation
  - `python-docx>=1.1.0` - Word documents

### Changed
- **Provider Registry** (`app/file_access/registry.py`)
  - Added `NASProvider` to registry
  - Registry now supports: `localfs`, `onedrive`, `nas`
  - Maintains backward compatibility

### Technical Details
- **Lines of Code**: ~3,500+ new lines
- **Files Created**: 13
- **Files Modified**: 2
- **Test Coverage**: 25+ test cases
- **Documentation**: 2,000+ lines

### Architecture Improvements
- Protocol adapter pattern for clean separation of concerns
- Dynamic loading of protocols on-demand
- Extensibility without modifying existing code
- Full type safety with comprehensive type hints
- Async-first design for optimal performance

### Backward Compatibility
- ✅ All existing LocalFS provider functionality preserved
- ✅ All existing OneDrive provider functionality preserved
- ✅ No breaking changes to public APIs

### Known Limitations
- SMB file watcher not yet implemented (optional feature)
- NFS, WebDAV, SFTP, FTP/S protocols have placeholder implementations with guides

---

## v1.2.0 — Production Readiness + Full Test Coverage (2025-12-11)

### Added
- **Event Normalizer Module** with inline LLM classification and entity extraction
- **Complete E2E Test Suite** covering Gmail webhook → Customer/Quote creation
- **Enhanced Monitoring**: Error persistence (ErrorLog model), fail-safe audit, Slack alerts
- **Health Endpoints**: `/admin/health`, `/admin/health/deep`, `/admin/ready`
- **Structured JSON Logging** with UUID serialization and context injection
- **Integration Stubs**: LLM service, WhatsApp enqueuing, OneDrive enqueuing

### Changed
- **Database Models**: Added nullable fields (RawEvent.flow_id, AuditLog.tenant_id/flow_id)
- **Notification Model**: Added `payload` (JSON) and `retry_count` (Integer) fields
- **Tenant Model**: Added `status` and `active_flows` fields
- **ExternalToken Model**: Added `provider`, `external_id`, `data` fields
- **Customer Model**: Made `flow_id` nullable for cross-flow management

### Fixed
- **Quote Variable Scoping Bug** in preventivi_service (UnboundLocalError)
- **UUID Serialization** in JSON logger for proper log formatting
- **Mock Patching** in tests to target correct import locations
- **OneDrive Action ID Generation** to prevent primary key conflicts
- **Notification Enqueuing** to properly create database records
- **Test Database Schema** creation/teardown for SQLite in-memory

---

## v1.3.1 — Monitoring Enhancements (2025-12-13)

### Added
- **Monitoring Filters**: Added `start_date`, `end_date`, and `event_type` query filters to the admin monitoring endpoints:
  - `GET /admin/monitoring/raw_events`
  - `GET /admin/monitoring/normalized_events`

- **Audit Trail Endpoint**: Added `GET /admin/monitoring/audit_trail?idempotency_key=...` to retrieve the full audit log sequence for a specific idempotency key.

### Changed
- **OpenAPI & Postman**: Updated `openapi.json` and `postman_collection.json` with new query parameters and sample requests for filtered queries and the audit trail endpoint.

### Notes
- All SQL queries for audit retrieval use parameterized statements to avoid SQL injection. Date filters accept ISO-8601 timestamps.


### Testing
- ✅ 4/4 tests passing
- E2E test: Complete pipeline validation
- Unit tests: Monitoring helpers (audit, errors, logging)
- SQLite in-memory database support
- Comprehensive mocking of external dependencies

### Documentation
- Added IMPLEMENTATION_SUMMARY.md with architecture overview
- Updated copilot instructions with full implementation details
- Created OpenAPI/Postman collection for health endpoints

---

## v1.3.2 — OneDrive Discovery & Admin Monitoring (2025-12-13)

### Added
- **OneDrive discovery improvements**: Personal-site discovery fallback added to `app/integrations/onedrive_client.py` to handle SharePoint-backed personal OneDrive sites. Includes `/sites/{hostname}:/personal/{user_segment}:/drive` attempt and `/drives` scanning fallback. Logs every discovery decision to `integration_events`.
- **Integration events persistence**: New `IntegrationEvent` model and repository and corresponding SQL migration (`migrations/003_add_integration_events.sql`).
- **Admin endpoints**: Read-only admin APIs to inspect monitoring and integration logs:
  - `GET /admin/integrations/onedrive/logs` — list OneDrive discovery/integration events (filters: `level`, `event_type`, `since`, pagination).
  - `GET /admin/monitoring/gmail_events` — list Gmail raw events filtered by `processed` and `event_type`.
  - Existing monitoring endpoints extended: `raw_events`, `normalized_events`, `audit_trail` now support additional filters (`start_date`, `end_date`, `event_type`).
- **Operational scripts**: Added `scripts/create_integration_events.py` (idempotent table creation) and `scripts/apply_migrations.py` (async-aware migration helper) to help apply DB changes in dev environments.
- **Documentation**: Added operational docs under `docs/` including `ONEDRIVE.md`, `GMAIL.md`, `WHATSAPP.md`, `SLACK.md`, and the master `docs/README.md`. Also added `docs/GMAIL_EVENTS.md` and `docs/ONE_DRIVE_DISCOVERY_LOGS.md` for quick operator references.

### Changed
- **Postman & OpenAPI**: Updated Postman collection to include admin monitoring and integrations endpoints. OpenAPI updated to reflect new query parameters and admin routes.
- **Monitoring**: Improved logging and error handling in admin monitoring endpoints; fixed an import/indentation bug in `app/api/admin/monitoring.py` that prevented the service from starting.

### Fixed
- Resolved startup error caused by a duplicated/malformed `monitoring.py` module.
- Ensured `integration_events` table exists in developer DB via `scripts/create_integration_events.py` (safe, idempotent).

### Notes
- For production deployments, prefer to integrate these schema changes into a managed Alembic migration rather than running ad-hoc SQL scripts.


---

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
