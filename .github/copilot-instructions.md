# Copilot Instructions for Edilcos Automation Backend

You are assisting in the development of a modular, reliable, multi-tenant backend in **Python (FastAPI)**.  
Your goal is to generate **clean, scalable, production-ready code**, following the architecture below.

Focus: clarity, modularity, correctness, and maintainability.

---

## 1. PROJECT ARCHITECTURE (MANDATORY)

The backend follows this folder structure:

app/
  main.py
  config.py
  api/
    ingress/
      gmail_webhook.py
      whatsapp_webhook.py
      generic_webhook.py
    flows/
      preventivi_v1.py
      documenti_v1.py
      attrezzature_v1.py
    notifications/
      whatsapp.py
  core/
    normalizer.py
    router.py
    preventivi_service.py
    documents_service.py
    attrezzature_service.py
  integrations/
    gmail_api.py
    whatsapp_api.py
    onedrive_api.py
  db/
    models.py
    session.py
    repositories/
  scheduler/
    jobs.py
    scheduler.py
  monitoring/
    logger.py
    audit.py
    slack_alerts.py

Follow this architecture strictly unless explicitly instructed otherwise.

---

## 2. CORE PRINCIPLES

Always respect:

### (1) Modularity
- Each module must have a single responsibility.
- No file should exceed ~200–250 lines unless necessary.
- Shared logic → move to `core/` or `utils/`.

### (2) Multi-tenant
Every model and event MUST include:
- `tenant_id`
- `flow_id`

Every query must filter by `tenant_id`.

### (3) Reliability
Backend must:
- never drop events
- log everything important
- save RAW email/webhook payloads
- use idempotency keys (`gmail_message_id`, `whatsapp_message_id`, etc.)
- retry external API failures

### (4) Clean FastAPI structure
- Use routers (`APIRouter`) per module.
- Use dependency injections when appropriate.
- Use Pydantic models for request/response.

### (5) Strict typing
Always include:
- type hints
- return types
- docstrings

### (6) No business logic inside controllers
Controllers only:
- validate input
- identify tenant
- call service modules

All logic goes into:
- `core/*`
- `services/*`

---

## 3. MANDATORY MODULE BEHAVIORS

### 3.1 Ingress Layer (webhooks)
- Receives Gmail Pub/Sub, WhatsApp Webhook, generic webhooks.
- Validates payloads.
- Identifies tenant (from email address, phone number, or URL param).
- Saves RAW event in DB.
- Forwards normalized event to Flow Router.

### 3.2 Event Normalizer
- Converts Gmail MIME / WhatsApp payloads into a unified event structure:

```python
{
  "event_id": "unique_id",
  "tenant_id": "acme_corp",
  "flow_id": "preventivi_v1",
  "source": "gmail" | "whatsapp" | "generic",
  "timestamp": "ISO8601",
  "sender": {
    "email": "...",
    "phone": "...",
    "name": "..."
  },
  "subject": "...",
  "body": "...",
  "attachments": [
    {
      "filename": "...",
      "mime_type": "...",
      "size_bytes": 123,
      "storage_url": "..."
    }
  ],
  "metadata": {
    "gmail_message_id": "...",
    "whatsapp_message_id": "...",
    "thread_id": "..."
  }
}
```

### 3.3 Flow Router
- Receives normalized events.
- Determines which flow to trigger based on:
  - `tenant_id`
  - `flow_id`
  - routing rules (keywords, sender patterns, etc.)
- Dispatches to the appropriate flow handler in `api/flows/`.

### 3.4 Flow Handlers (`api/flows/`)
Each flow (e.g., `preventivi_v1.py`) must:
- Validate event structure.
- Call appropriate service logic from `core/`.
- Handle errors gracefully.
- Return status/result.
- Trigger notifications if needed.

### 3.5 Core Services (`core/`)
Business logic modules:
- **`preventivi_service.py`**: Extract quote data, validate, store, generate responses.
- **`documents_service.py`**: Process documents, OCR, classification, storage.
- **`attrezzature_service.py`**: Equipment tracking, maintenance scheduling.

All services must:
- Accept `tenant_id` and `flow_id`.
- Log all operations.
- Use repository pattern for DB access.
- Return structured results (success/failure + data).

### 3.6 Integrations (`integrations/`)
External API wrappers:
- **Gmail API**: Fetch messages, parse MIME, download attachments.
- **WhatsApp API**: Send messages, handle media.
- **OneDrive API**: Upload/download files, manage folders.

All integrations must:
- Include retry logic (exponential backoff).
- Log requests/responses.
- Handle rate limits.
- Use environment variables for credentials.

### 3.7 Database Layer (`db/`)
- **`models.py`**: SQLAlchemy models (all include `tenant_id`, `created_at`, `updated_at`).
- **`session.py`**: Database session management, connection pooling.
- **`repositories/`**: Data access layer (CRUD operations per entity).

Example models:
- `RawEvent`: Store all incoming webhooks.
- `ProcessedEvent`: Store normalized events.
- `Preventivo`: Quote/estimate data.
- `Document`: Document metadata.
- `Attrezzatura`: Equipment records.
- `Tenant`: Tenant configuration.
- `FlowConfig`: Flow routing rules per tenant.

### 3.8 Scheduler (`scheduler/`)
- **`jobs.py`**: Define background jobs (retries, cleanups, reports).
- **`scheduler.py`**: APScheduler configuration.

Jobs must:
- Be idempotent.
- Include error handling.
- Log execution.

### 3.9 Monitoring (`monitoring/`)
- **`logger.py`**: Structured logging (JSON format).
- **`audit.py`**: Audit trail for critical operations.
- **`slack_alerts.py`**: Send alerts for failures/anomalies.

---

## 4. DATABASE MODELS - REQUIRED FIELDS

Every model MUST include:

```python
class BaseModel:
    id: UUID (primary key)
    tenant_id: str (indexed, non-nullable)
    created_at: datetime (auto)
    updated_at: datetime (auto)
    deleted_at: datetime (nullable, soft delete)
```

Additional fields per entity:
- **RawEvent**: `source`, `payload` (JSONB), `processed` (bool), `idempotency_key`.
- **ProcessedEvent**: `event_type`, `flow_id`, `normalized_data` (JSONB), `status`.
- **Preventivo**: `customer_name`, `email`, `phone`, `quote_data` (JSONB), `status`, `pdf_url`.

---

## 5. ERROR HANDLING STRATEGY

### (1) Never fail silently
- Log every error with context (`tenant_id`, `flow_id`, event data).
- Store failed events in a `failed_events` table for retry.

### (2) Use try-except everywhere
```python
try:
    result = service.process(data)
except ValidationError as e:
    logger.error(f"Validation failed: {e}", extra={"tenant_id": tenant_id})
    return {"error": "invalid_data", "details": str(e)}
except ExternalAPIError as e:
    logger.error(f"API call failed: {e}", extra={"tenant_id": tenant_id})
    # Queue for retry
    return {"error": "api_failure", "retry": True}
except Exception as e:
    logger.exception(f"Unexpected error: {e}")
    # Alert to Slack
    return {"error": "internal_error"}
```

### (3) Retry logic
For external API calls:
```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def call_external_api():
    # API call here
    pass
```

---

## 6. CONFIGURATION MANAGEMENT

Use **Pydantic Settings** (`config.py`):

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    GMAIL_CREDENTIALS_PATH: str
    WHATSAPP_API_TOKEN: str
    ONEDRIVE_CLIENT_ID: str
    ONEDRIVE_CLIENT_SECRET: str
    SLACK_WEBHOOK_URL: str
    LOG_LEVEL: str = "INFO"
    
    class Config:
        env_file = ".env"

settings = Settings()
```

Never hardcode credentials. Always use environment variables.

---

## 7. TESTING REQUIREMENTS

For every module, provide:

### (1) Unit tests
- Test individual functions in isolation.
- Mock external dependencies.
- Use `pytest`.

### (2) Integration tests
- Test full flows end-to-end.
- Use a test database.
- Mock external APIs.

### (3) Test structure
```python
def test_preventivi_flow_success(db_session, mock_gmail_api):
    # Arrange
    event = create_test_event()
    
    # Act
    result = preventivi_service.process(event, tenant_id="test_tenant")
    
    # Assert
    assert result["status"] == "success"
    assert db_session.query(Preventivo).count() == 1
```

---

## 8. API DESIGN STANDARDS

### (1) Webhook endpoints
```python
@router.post("/webhooks/gmail")
async def gmail_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    # Validate signature/token
    # Save raw payload
    # Queue processing
    return {"status": "accepted"}
```

### (2) Admin/Management endpoints
```python
@router.get("/admin/tenants/{tenant_id}/flows")
async def list_flows(
    tenant_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    # Return flow configurations
    pass
```

### (3) Response format
Always return:
```python
{
  "status": "success" | "error",
  "data": {...},  # if success
  "error": {...}  # if error
}
```

---

## 9. LOGGING STANDARDS

Use structured logging:

```python
import structlog

logger = structlog.get_logger()

logger.info(
    "event_processed",
    tenant_id=tenant_id,
    flow_id=flow_id,
    event_id=event_id,
    duration_ms=duration
)
```

Log levels:
- **DEBUG**: Detailed diagnostics.
- **INFO**: Important events (event received, flow triggered, etc.).
- **WARNING**: Recoverable issues (retry scheduled, missing optional field).
- **ERROR**: Failures that need attention.
- **CRITICAL**: System-level failures (DB down, critical service unavailable).

---

## 10. SECURITY REQUIREMENTS

### (1) Webhook authentication
- Gmail: Verify Pub/Sub signature.
- WhatsApp: Verify webhook token.
- Generic: Use API keys or JWT.

### (2) Data isolation
- Always filter by `tenant_id`.
- Never allow cross-tenant data access.
- Use database row-level security if possible.

### (3) Secrets management
- Use environment variables.
- Consider HashiCorp Vault or AWS Secrets Manager for production.

### (4) Input validation
- Validate all inputs with Pydantic.
- Sanitize file uploads.
- Limit payload sizes.

---

## 11. DEPLOYMENT CONSIDERATIONS

### (1) Dockerization
Provide a `Dockerfile`:
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### (2) Environment variables
Required:
- `DATABASE_URL`
- `REDIS_URL` (for caching/queues)
- All API credentials
- `LOG_LEVEL`

### (3) Health checks
Implement `/health` and `/ready` endpoints:
```python
@router.get("/health")
async def health():
    return {"status": "healthy"}

@router.get("/ready")
async def ready(db: Session = Depends(get_db)):
    # Check DB connection
    try:
        db.execute("SELECT 1")
        return {"status": "ready"}
    except:
        raise HTTPException(status_code=503, detail="Not ready")
```

---

## 12. CODE GENERATION GUIDELINES

When generating code:

### (1) Always include:
- File path comment at the top (e.g., `# app/api/ingress/gmail_webhook.py`).
- Complete imports.
- Type hints.
- Docstrings (Google style).
- Error handling.

### (2) Example structure:
```python
# app/core/preventivi_service.py
"""
Service for processing preventivi (quotes/estimates).
"""
from typing import Dict, Any, Optional
from uuid import UUID
import structlog

from app.db.repositories.preventivi_repository import PreventiviRepository
from app.core.normalizer import NormalizedEvent
from app.integrations.onedrive_api import OneDriveClient

logger = structlog.get_logger()

class PreventiviService:
    """Handles business logic for preventivi processing."""
    
    def __init__(self, repo: PreventiviRepository, onedrive: OneDriveClient):
        self.repo = repo
        self.onedrive = onedrive
    
    def process_event(
        self,
        event: NormalizedEvent,
        tenant_id: str,
        flow_id: str
    ) -> Dict[str, Any]:
        """
        Process a preventivi event.
        
        Args:
            event: Normalized event data
            tenant_id: Tenant identifier
            flow_id: Flow identifier
            
        Returns:
            Processing result with status and data
        """
        try:
            logger.info("processing_preventivi", tenant_id=tenant_id, event_id=event.event_id)
            
            # Extract quote data
            quote_data = self._extract_quote_data(event)
            
            # Save to database
            preventivo = self.repo.create(
                tenant_id=tenant_id,
                customer_name=quote_data["customer_name"],
                quote_data=quote_data
            )
            
            # Upload attachments to OneDrive
            if event.attachments:
                self._upload_attachments(preventivo.id, event.attachments)
            
            logger.info("preventivi_processed", preventivo_id=str(preventivo.id))
            
            return {
                "status": "success",
                "data": {
                    "preventivo_id": str(preventivo.id),
                    "customer": quote_data["customer_name"]
                }
            }
            
        except Exception as e:
            logger.exception("preventivi_processing_failed", tenant_id=tenant_id)
            return {
                "status": "error",
                "error": str(e)
            }
    
    def _extract_quote_data(self, event: NormalizedEvent) -> Dict[str, Any]:
        """Extract structured quote data from event."""
        # Implementation here
        pass
    
    def _upload_attachments(self, preventivo_id: UUID, attachments: list):
        """Upload attachments to OneDrive."""
        # Implementation here
        pass
```

### (3) Never generate:
- Incomplete code with `# TODO` or `pass` in critical sections.
- Code without error handling.
- Code without logging.
- Code that violates the architecture.

---

## 13. SPECIFIC FLOW IMPLEMENTATIONS

### Preventivi Flow (Quotes/Estimates)
**Trigger**: Email received with subject containing "preventivo" or "quotation".

**Steps**:
1. Extract customer info (name, email, phone).
2. Extract quote items (description, quantity, price).
3. Validate data completeness.
4. Save to database.
5. Upload attachments to OneDrive.
6. Generate response email with confirmation.
7. Notify via WhatsApp if phone number available.

### Documenti Flow (Document Management)
**Trigger**: Email with attachments (PDFs, images).

**Steps**:
1. Download attachments.
2. Classify document type (invoice, contract, etc.).
3. OCR if needed.
4. Extract metadata.
5. Upload to OneDrive in appropriate folder.
6. Create database record with metadata.
7. Send confirmation.

### Attrezzature Flow (Equipment Management)
**Trigger**: WhatsApp message about equipment status.

**Steps**:
1. Parse message for equipment ID.
2. Extract status/maintenance info.
3. Update equipment record.
4. Check if maintenance needed.
5. Schedule job if needed.
6. Reply with status confirmation.

---

## 14. PERFORMANCE OPTIMIZATION

### (1) Database
- Use indexes on `tenant_id`, `flow_id`, `created_at`.
- Use connection pooling.
- Implement query result caching for config tables.

### (2) Background processing
- Use Celery or similar for heavy tasks.
- Process attachments asynchronously.
- Batch database operations when possible.

### (3) API calls
- Cache API responses when appropriate.
- Use async/await for concurrent operations.
- Implement rate limiting.

---

## 15. MONITORING & OBSERVABILITY

### Metrics to track:
- Events received per tenant/flow.
- Processing time per flow.
- Success/failure rates.
- API call latency.
- Queue depths.

### Alerting conditions:
- Error rate > 5% in 5 minutes.
- Processing time > 30 seconds.
- Queue depth > 100.
- External API failures.

---

## 16. DOCUMENTATION REQUIREMENTS

For every module, provide:

### (1) Module docstring
```python
"""
Module: gmail_webhook
Description: Handles Gmail Pub/Sub webhook notifications
Responsibilities:
  - Validate Pub/Sub signature
  - Decode message payload
  - Save raw event
  - Trigger event processing
"""
```

### (2) Function docstrings
Use Google style:
```python
def process_event(event_id: str, tenant_id: str) -> Dict[str, Any]:
    """
    Process a raw event and trigger appropriate flow.
    
    Args:
        event_id: Unique event identifier
        tenant_id: Tenant identifier
        
    Returns:
        Dictionary with processing status and result data
        
    Raises:
        ValidationError: If event data is invalid
        ProcessingError: If processing fails
    """
```

---

## 17. QUICK REFERENCE

### Common patterns:

**Create a new flow handler:**
```python
# app/api/flows/new_flow_v1.py
from fastapi import APIRouter, Depends
from app.core.normalizer import NormalizedEvent
from app.core.new_flow_service import NewFlowService

router = APIRouter(prefix="/flows/new_flow", tags=["flows"])

@router.post("/process")
async def process_new_flow(
    event: NormalizedEvent,
    service: NewFlowService = Depends()
):
    result = service.process(event)
    return result
```

**Add a database model:**
```python
# app/db/models.py
from sqlalchemy import Column, String, JSON, DateTime
from app.db.base import BaseModel

class NewEntity(BaseModel):
    __tablename__ = "new_entities"
    
    tenant_id = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    data = Column(JSON)
```

**Create a repository:**
```python
# app/db/repositories/new_entity_repository.py
from app.db.models import NewEntity
from sqlalchemy.orm import Session

class NewEntityRepository:
    def __init__(self, db: Session):
        self.db = db
    
    def create(self, tenant_id: str, name: str, data: dict) -> NewEntity:
        entity = NewEntity(tenant_id=tenant_id, name=name, data=data)
        self.db.add(entity)
        self.db.commit()
        self.db.refresh(entity)
        return entity
    
    def get_by_tenant(self, tenant_id: str) -> list[NewEntity]:
        return self.db.query(NewEntity).filter(
            NewEntity.tenant_id == tenant_id
        ).all()
```

---

## 18. FINAL CHECKLIST

Before submitting code, verify:

- [ ] Follows project architecture
- [ ] Includes `tenant_id` and `flow_id` where required
- [ ] Has complete type hints
- [ ] Has docstrings
- [ ] Has error handling
- [ ] Has logging
- [ ] Has tests (or test outline)
- [ ] Uses dependency injection
- [ ] No business logic in controllers
- [ ] No hardcoded credentials
- [ ] Includes retry logic for external APIs
- [ ] Validates all inputs
- [ ] Returns structured responses

---

## 19. WHEN IN DOUBT

**Ask yourself:**
1. Does this violate single responsibility?
2. Is this tenant-safe?
3. Will this log enough information for debugging?
4. What happens if this external API fails?
5. Is this testable?

**If unsure**, prefer:
- More modular over monolithic.
- Explicit over implicit.
- Safe over fast.
- Logged over silent.

---

**End of Copilot Instructions**

When generating code, always refer back to these instructions and follow them strictly.
