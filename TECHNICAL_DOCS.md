# Technical Documentation - Edilcos Automation Backend

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Core Components](#core-components)
3. [Database Schema](#database-schema)
4. [API Reference](#api-reference)
5. [Integration Guides](#integration-guides)
6. [Monitoring & Logging](#monitoring--logging)
7. [Testing Strategy](#testing-strategy)
8. [Deployment Guide](#deployment-guide)
9. [Troubleshooting](#troubleshooting)

---

## Architecture Overview

### System Architecture

The Edilcos Automation Backend follows a **multi-tenant, event-driven architecture** with these key principles:

- **Async-first**: All I/O operations are asynchronous
- **Multi-tenant**: Complete data isolation per tenant
- **Event-driven**: Gmail events trigger processing pipelines
- **Modular**: Clear separation of concerns across modules
- **Observable**: Comprehensive logging, audit, and error tracking

### Technology Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| **Runtime** | Python | 3.11+ |
| **Framework** | FastAPI | Latest |
| **ASGI Server** | Uvicorn | Latest |
| **Database** | PostgreSQL | 14+ |
| **ORM** | SQLAlchemy | 2.0+ |
| **Async Driver** | asyncpg | Latest |
| **Scheduler** | APScheduler | Latest |
| **HTTP Client** | aiohttp, httpx | Latest |
| **Testing** | pytest, pytest-asyncio | Latest |

### Architecture Layers

```
┌─────────────────────────────────────────────────────────────┐
│                    Presentation Layer                        │
│  (FastAPI Routes, Webhooks, Admin APIs, Health Endpoints)   │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                   Application Layer                          │
│    (Event Normalizer, Flow Router, Business Services)       │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                   Integration Layer                          │
│     (Gmail API, WhatsApp API, OneDrive API, LLM Service)    │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                      Data Layer                              │
│    (SQLAlchemy Models, Repositories, Database Session)      │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                  Infrastructure Layer                        │
│     (PostgreSQL, Scheduler, Monitoring, Logging)            │
└─────────────────────────────────────────────────────────────┘
```

---

## Core Components

### 1. Event Normalizer (`app/core/normalizer.py`)

**Purpose**: Transform RawEvent into NormalizedEvent with LLM-powered classification

**Key Functions**:
- `normalize_raw_event(raw_event_id: UUID)`: Main entry point
- LLM classification integration
- Entity extraction
- Source mapping (gmail → email)
- Automatic routing

**Flow**:
```python
RawEvent (DB) 
  → Load from DB
  → LLM Classification (new_quote, existing_quote, unknown)
  → LLM Entity Extraction (nome, cognome, telefono, etc.)
  → Build NormalizedEvent
  → Save to DB
  → Route to Flow Handler
```

**Configuration**:
```python
# Source mappings
SOURCE_MAPPINGS = {
    "gmail": "email",
    "whatsapp": "whatsapp",
    "generic": "generic"
}
```

### 2. Flow Router (`app/core/router.py`)

**Purpose**: Route normalized events to appropriate business logic handlers

**Key Functions**:
- `route_normalized_event(event_id: UUID)`: Main routing function

**Routing Rules**:
```python
if source == "email" and flow_id == "preventivi_v1":
    → preventivi_service.process_normalized_event()
elif source == "email" and flow_id == "documenti_v1":
    → documenti_service.process_normalized_event()
# ... more flows
```

**Adding New Flows**:
1. Create flow handler in `app/core/`
2. Implement `process_normalized_event(event_id, tenant_id, flow_id)`
3. Add routing rule in `route_normalized_event()`

### 3. Preventivi Service (`app/core/preventivi_service.py`)

**Purpose**: Business logic for construction quote (preventivo) processing

**Process Flow**:
```
1. Load NormalizedEvent from DB
2. Classify event (new_quote, existing_quote, unknown)
3. Extract customer/quote entities
4. Find or create Customer record
5. Create or update Quote record
6. Enqueue WhatsApp notification
7. Enqueue Excel update
8. Audit all operations
```

**Key Functions**:
- `process_normalized_event(event_id, tenant_id, flow_id)`
- `find_or_create_customer(repo, tenant_id, extracted, flow_id)`
- `find_and_update_quote(repo, tenant_id, customer, event, extracted)`

**Customer Deduplication Logic**:
```python
# Search by phone number first
if phone:
    customer = repo.get_by_phone(tenant_id, phone)
    
# Fallback to email
if not customer and email:
    customer = repo.get_by_email(tenant_id, email)
    
# Create new if not found
if not customer:
    customer = repo.create(...)
```

### 4. Monitoring System

#### Structured Logging (`app/monitoring/logger.py`)

**Features**:
- JSON formatted logs
- Context injection (request_id, tenant_id, flow_id)
- UUID serialization support
- Multiple log levels

**Usage**:
```python
from app.monitoring.logger import log

log("INFO", "Customer created", 
    module="preventivi_service",
    customer_id=str(customer.id),
    tenant_id=tenant_id)
```

**Log Format**:
```json
{
  "timestamp": "2025-12-11T10:17:00.376667",
  "level": "INFO",
  "message": "Customer created",
  "component": "preventivi_service",
  "request_id": "b0fd7ac4-0479-45fb-a942-cd4a6ec69852",
  "tenant_id": "b3529ed1-b820-40b6-a812-e351584e5858",
  "flow_id": "preventivi_v1",
  "customer_id": "..."
}
```

#### Audit System (`app/monitoring/audit.py`)

**Features**:
- Fail-safe audit event recording
- Automatic context propagation
- Database persistence
- Never fails silently

**Usage**:
```python
from app.monitoring.audit import audit_event

await audit_event(
    action="customer_created",
    tenant_id=tenant_id,
    flow_id=flow_id,
    details={"customer_id": str(customer.id)},
    request_id=request_id
)
```

**Audit Record Structure**:
```python
{
    "id": UUID,
    "tenant_id": UUID,
    "flow_id": str,
    "action": str,
    "actor": str (optional),
    "details": dict (JSON),
    "created_at": datetime,
    "updated_at": datetime
}
```

#### Error Tracking (`app/monitoring/errors.py`)

**Features**:
- Error persistence to database
- Full traceback capture
- Context preservation
- Integration with audit system

**Usage**:
```python
from app.monitoring.errors import record_error

try:
    # ... operation
except Exception as exc:
    await record_error(
        tenant_id=tenant_id,
        flow_id=flow_id,
        error_type=type(exc).__name__,
        error_message=str(exc),
        context={"event_id": str(event_id)}
    )
```

#### Slack Alerts (`app/monitoring/slack_alerts.py`)

**Features**:
- Critical error notifications
- Configurable severity levels
- Context attachment
- Graceful degradation

**Usage**:
```python
from app.monitoring.slack_alerts import send_slack_alert

await send_slack_alert(
    message="Critical error in preventivi processing",
    context={"event_id": str(event_id), "traceback": tb},
    severity="CRITICAL",
    module="preventivi_service"
)
```

---

## Database Schema

### Entity Relationship Diagram

```
┌──────────────┐      ┌──────────────────┐      ┌──────────────┐
│    Tenant    │──────│  ExternalToken   │      │   RawEvent   │
│              │ 1:N  │                  │      │              │
│ - id         │      │ - id             │      │ - id         │
│ - name       │      │ - tenant_id (FK) │      │ - tenant_id  │
│ - status     │      │ - provider       │      │ - source     │
│ - active_flows      │ - external_id    │      │ - raw_data   │
└──────────────┘      │ - data           │      │ - flow_id    │
                      └──────────────────┘      └──────────────┘
       │                                               │
       │ 1:N                                          │
       │                                               │
       ▼                                               ▼
┌──────────────┐                          ┌──────────────────┐
│   Customer   │                          │ NormalizedEvent  │
│              │                          │                  │
│ - id         │                          │ - id             │
│ - tenant_id  │                          │ - tenant_id      │
│ - name       │                          │ - flow_id        │
│ - email      │                          │ - source         │
│ - phone      │                          │ - normalized_data│
│ - flow_id    │                          │ - event_type     │
└──────────────┘                          └──────────────────┘
       │ 1:N                                          │
       │                                              │ 1:N
       ▼                                              ▼
┌──────────────┐                          ┌──────────────────┐
│    Quote     │                          │  Notification    │
│              │                          │                  │
│ - id         │                          │ - id             │
│ - tenant_id  │                          │ - tenant_id      │
│ - customer_id│                          │ - event_id (FK)  │
│ - quote_data │                          │ - channel        │
│ - status     │                          │ - message        │
│ - pdf_url    │                          │ - payload        │
└──────────────┘                          │ - status         │
                                          │ - retry_count    │
                                          └──────────────────┘

┌──────────────┐      ┌──────────────────┐
│  AuditLog    │      │    ErrorLog      │
│              │      │                  │
│ - id         │      │ - id             │
│ - tenant_id  │      │ - tenant_id      │
│ - flow_id    │      │ - flow_id        │
│ - action     │      │ - error_type     │
│ - actor      │      │ - error_message  │
│ - details    │      │ - traceback      │
│ - created_at │      │ - context        │
└──────────────┘      └──────────────────┘
```

### Core Tables

#### Tenant
```sql
CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR NOT NULL,
    status VARCHAR DEFAULT 'active',
    active_flows JSONB DEFAULT '[]',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    deleted_at TIMESTAMP
);
```

#### ExternalToken
```sql
CREATE TABLE external_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    provider VARCHAR NOT NULL,  -- 'gmail', 'whatsapp', 'generic'
    external_id VARCHAR NOT NULL,  -- email address, phone, etc.
    data JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    deleted_at TIMESTAMP
);

CREATE INDEX idx_external_tokens_external_id ON external_tokens(external_id);
```

#### RawEvent
```sql
CREATE TABLE raw_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    source VARCHAR NOT NULL,  -- 'gmail', 'whatsapp', 'generic'
    idempotency_key VARCHAR UNIQUE,
    raw_data JSONB NOT NULL,
    flow_id VARCHAR,  -- Nullable, determined at runtime
    processed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    deleted_at TIMESTAMP
);

CREATE INDEX idx_raw_events_tenant ON raw_events(tenant_id);
CREATE INDEX idx_raw_events_idempotency ON raw_events(idempotency_key);
```

#### NormalizedEvent
```sql
CREATE TABLE normalized_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    raw_event_id UUID REFERENCES raw_events(id),
    flow_id VARCHAR NOT NULL,
    source VARCHAR NOT NULL,
    event_type VARCHAR,
    normalized_data JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    deleted_at TIMESTAMP
);

CREATE INDEX idx_normalized_events_tenant ON normalized_events(tenant_id);
CREATE INDEX idx_normalized_events_flow ON normalized_events(flow_id);
```

#### Customer
```sql
CREATE TABLE customers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    flow_id VARCHAR,  -- Nullable for cross-flow customers
    name VARCHAR,
    email VARCHAR,
    phone VARCHAR,
    address TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    deleted_at TIMESTAMP
);

CREATE INDEX idx_customers_tenant ON customers(tenant_id);
CREATE INDEX idx_customers_phone ON customers(phone);
CREATE INDEX idx_customers_email ON customers(email);
```

#### Quote
```sql
CREATE TABLE quotes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    flow_id VARCHAR NOT NULL,
    customer_id UUID REFERENCES customers(id),
    quote_data JSONB NOT NULL,
    status VARCHAR DEFAULT 'OPEN',
    pdf_url VARCHAR,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    deleted_at TIMESTAMP
);

CREATE INDEX idx_quotes_tenant ON quotes(tenant_id);
CREATE INDEX idx_quotes_customer ON quotes(customer_id);
CREATE INDEX idx_quotes_status ON quotes(status);
```

#### Notification
```sql
CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    flow_id VARCHAR NOT NULL,
    event_id UUID REFERENCES normalized_events(id),
    channel VARCHAR NOT NULL,  -- 'whatsapp', 'email', 'sms'
    message TEXT NOT NULL,
    payload JSONB,  -- For API-specific payloads
    status VARCHAR DEFAULT 'pending',
    retry_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    deleted_at TIMESTAMP
);

CREATE INDEX idx_notifications_tenant ON notifications(tenant_id);
CREATE INDEX idx_notifications_status ON notifications(status);
```

#### AuditLog
```sql
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id),  -- Nullable for system events
    flow_id VARCHAR,  -- Nullable
    action VARCHAR NOT NULL,
    actor VARCHAR,
    details JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    deleted_at TIMESTAMP
);

CREATE INDEX idx_audit_logs_tenant ON audit_logs(tenant_id);
CREATE INDEX idx_audit_logs_action ON audit_logs(action);
CREATE INDEX idx_audit_logs_created ON audit_logs(created_at);
```

#### ErrorLog
```sql
CREATE TABLE error_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id),
    flow_id VARCHAR,
    error_type VARCHAR NOT NULL,
    error_message TEXT NOT NULL,
    traceback TEXT,
    context JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    deleted_at TIMESTAMP
);

CREATE INDEX idx_error_logs_tenant ON error_logs(tenant_id);
CREATE INDEX idx_error_logs_type ON error_logs(error_type);
CREATE INDEX idx_error_logs_created ON error_logs(created_at);
```

---

## API Reference

### Health Endpoints

#### GET /admin/health
Basic health check

**Response**:
```json
{
  "status": "healthy",
  "timestamp": "2025-12-11T10:00:00Z"
}
```

#### GET /admin/health/deep
Deep health check with database connectivity

**Response**:
```json
{
  "status": "healthy",
  "checks": {
    "database": "ok"
  },
  "timestamp": "2025-12-11T10:00:00Z"
}
```

#### GET /admin/ready
Kubernetes readiness probe

**Response**:
```json
{
  "status": "ready"
}
```

### Webhook Endpoints

#### POST /gmail/webhook
Gmail Pub/Sub webhook receiver

**Request Body**:
```json
{
  "message": {
    "data": "eyJoaXN0b3J5SWQiOi4uLn0=",  // Base64 encoded
    "messageId": "pub-sub-message-id"
  }
}
```

**Response**:
```json
{
  "status": "accepted"
}
```

---

## Integration Guides

### Gmail Integration

1. **Setup Google Cloud Project**
2. **Enable Gmail API**
3. **Create Service Account**
4. **Download credentials.json**
5. **Set GMAIL_CREDENTIALS_PATH environment variable**
6. **Configure Pub/Sub topic**
7. **Set webhook URL** to `https://yourdomain.com/gmail/webhook`

### WhatsApp Integration

1. **Create Facebook Business Account**
2. **Register WhatsApp Business API**
3. **Get API Token**
4. **Set WHATSAPP_API_TOKEN environment variable**
5. **Configure webhook** (for incoming messages)

### OneDrive Integration

1. **Register Azure AD Application**
2. **Grant Microsoft Graph permissions**
3. **Get Client ID and Secret**
4. **Set environment variables**:
   - `ONEDRIVE_CLIENT_ID`
   - `ONEDRIVE_CLIENT_SECRET`
   - `ONEDRIVE_TENANT_ID`
   - `ONEDRIVE_DRIVE_ID`
   - `ONEDRIVE_EXCEL_FILE_ID`

---

## Testing Strategy

### Test Levels

1. **Unit Tests**: Individual functions and classes
2. **Integration Tests**: Module interactions
3. **E2E Tests**: Full pipeline validation
4. **Performance Tests**: Load and stress testing (future)

### Test Execution

```bash
# All tests
pytest tests/ -v

# E2E only
pytest tests/test_e2e_new_quote_flow.py -xvs

# With coverage
pytest tests/ --cov=app --cov-report=html

# Specific test
pytest tests/test_monitoring.py::test_audit_event_fail_safe -v
```

### Test Configuration

**Environment**:
```bash
DATABASE_URL="sqlite+aiosqlite:///:memory:"
PYTHONPATH=.
```

**Fixtures**:
- `db_session`: Async database session
- `test_tenant`: Test tenant with external token mapping
- `client`: AsyncClient with ASGITransport

---

## Deployment Guide

See README.md for detailed deployment instructions including:
- Docker deployment
- Docker Compose
- Kubernetes manifests
- Environment configuration
- Health check setup

---

## Troubleshooting

### Common Issues

#### Database Connection Errors
```python
# Test connection
python -c "
import asyncio
from app.db.session import SessionLocal

async def test():
    async with SessionLocal() as session:
        await session.execute('SELECT 1')
        print('OK')

asyncio.run(test())
"
```

#### UUID Serialization Errors
- Ensure JsonFormatter is being used
- Check UUID fields are converted to strings in logs

#### Mock Not Working in Tests
- Patch at import location, not definition location
- Example: `app.scheduler.jobs.send_whatsapp_message` not `app.integrations.whatsapp_api.send_whatsapp_message`

#### Tests Failing on Assertions
- Check SQLite in-memory database is being used
- Verify mocks are applied before function execution
- Ensure async operations complete before assertions

---

**Document Version**: 1.2.0  
**Last Updated**: 2025-12-11  
**Status**: Production Ready
