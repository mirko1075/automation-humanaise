# Edilcos Automation Backend

**Version:** 1.2.0  
**Status:** ✅ Production Ready - All Tests Passing  
**Architecture:** Multi-tenant, Event-driven, Async FastAPI

A modular, multi-tenant automation backend for construction business workflows. Processes emails, manages quotes (preventivi), handles customer relationships, and integrates with WhatsApp and OneDrive.

## 🚀 Features

### Core Capabilities
- **Event Processing Pipeline**: Gmail Pub/Sub → Normalization → LLM Classification → Flow Routing → Business Logic
- **Multi-tenant Support**: Complete tenant isolation with per-tenant configuration
- **Quote Management (Preventivi)**: Automated quote processing from email with customer/quote creation
- **WhatsApp Integration**: Automated customer notifications via WhatsApp Business API
- **OneDrive Integration**: Excel spreadsheet updates via Microsoft Graph API
- **Structured Logging**: JSON logs with full context (request_id, tenant_id, flow_id)
- **Audit System**: Fail-safe audit trail for all critical operations
- **Health Monitoring**: Kubernetes-ready health and readiness probes

### Integrations
- ✅ Gmail API (Pub/Sub webhooks + message fetching)
- ✅ WhatsApp Business API (Facebook Graph API)
- ✅ Microsoft OneDrive/Excel (Graph API)
- ✅ Slack (Error alerting)
- 🔄 LLM Service (Classification & entity extraction - stub implementation)

## 📋 Prerequisites

- **Python:** 3.11+
- **Database:** PostgreSQL 14+ (or SQLite for testing)
- **Redis:** Optional (for future queue management)
- **Docker:** Recommended for production deployment

## 🛠️ Installation

### 1. Clone the Repository
```bash
git clone https://github.com/mirko1075/automation-humanaise.git
cd automation-humanaise
```

### 2. Create Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment

Create a `.env` file in the project root:

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/edilcos

# Gmail Integration
GMAIL_CREDENTIALS_PATH=/path/to/credentials.json

# WhatsApp Integration
WHATSAPP_API_TOKEN=your_whatsapp_business_api_token

# OneDrive Integration
ONEDRIVE_CLIENT_ID=your_azure_app_client_id
ONEDRIVE_CLIENT_SECRET=your_azure_app_client_secret
ONEDRIVE_TENANT_ID=your_microsoft_tenant_id
ONEDRIVE_DRIVE_ID=your_onedrive_drive_id
ONEDRIVE_EXCEL_FILE_ID=your_excel_file_id

# Monitoring
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
LOG_LEVEL=INFO

# Server
HOST=0.0.0.0
PORT=8000
```

### 5. Initialize Database

#### Option A: Alembic Migrations (Recommended)
```bash
# Create initial migration
alembic revision --autogenerate -m "Initial schema"

# Apply migrations
alembic upgrade head
```

#### Option B: Direct Table Creation
```python
# Run this once to create all tables
python -c "
import asyncio
from app.db.session import engine, Base
from app.db.models import *

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

asyncio.run(init_db())
"
```

## 🚀 Running the Application

### Development Mode
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Production Mode
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### With Custom Port
```bash
uvicorn app.main:app --host 0.0.0.0 --port 9100 --log-level info --reload
```

The application will be available at `http://localhost:8000` (or your configured port).

## 🧪 Testing

### Run All Tests
```bash
# Using SQLite in-memory database
DATABASE_URL="sqlite+aiosqlite:///:memory:" \
PYTHONPATH=. \
pytest tests/ -v
```

### Run E2E Test
```bash
DATABASE_URL="sqlite+aiosqlite:///:memory:" \
PYTHONPATH=. \
pytest tests/test_e2e_new_quote_flow.py -xvs
```

### Run Specific Test
```bash
DATABASE_URL="sqlite+aiosqlite:///:memory:" \
PYTHONPATH=. \
pytest tests/test_monitoring.py::test_audit_event_fail_safe -v
```

### Test Coverage
```bash
pytest tests/ --cov=app --cov-report=html
```

### Current Test Results
```
======================== 4 passed, 71 warnings in 0.75s ========================
✅ test_new_quote_flow_e2e (E2E Pipeline)
✅ test_audit_event_fail_safe (Audit System)
✅ test_record_error_logs (Error Logging)
✅ test_logger_context_injection (Structured Logging)
```

## 📚 API Endpoints

### Health & Monitoring
- `GET /admin/health` - Basic health check
- `GET /admin/health/deep` - Deep health check (DB, external services)
- `GET /admin/ready` - Kubernetes readiness probe

### Webhooks
- `POST /gmail/webhook` - Gmail Pub/Sub webhook receiver
- `POST /whatsapp/webhook` - WhatsApp webhook (future)

### Admin APIs
- `GET /admin/tenants` - List all tenants
- `POST /admin/tenants` - Create new tenant
- `GET /admin/tenants/{tenant_id}` - Get tenant details
- `PUT /admin/tenants/{tenant_id}` - Update tenant
- `DELETE /admin/tenants/{tenant_id}` - Delete tenant

### Documentation
- `GET /docs` - Swagger UI (auto-generated)
- `GET /redoc` - ReDoc (auto-generated)
- `GET /openapi.json` - OpenAPI specification

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Gmail Pub/Sub Webhook                    │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              Gmail API: Fetch Full Message                   │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│            Save RawEvent (idempotency by message_id)         │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│        Event Normalizer: LLM Classification + Extraction     │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│            Save NormalizedEvent + Route to Flow              │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│           Flow Router: Dispatch to Business Logic            │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│         Preventivi Service: Customer + Quote Management      │
├─────────────────────────────────────────────────────────────┤
│  • Find/Create Customer                                      │
│  • Create/Update Quote                                       │
│  • Enqueue WhatsApp Notification                             │
│  • Enqueue Excel Update                                      │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│            Scheduler: Process Queued Actions                 │
├─────────────────────────────────────────────────────────────┤
│  • Send WhatsApp Messages                                    │
│  • Update Excel Spreadsheets                                 │
│  • Send Quote Reminders                                      │
└─────────────────────────────────────────────────────────────┘
```

### Key Components

#### 1. Ingress Layer (`app/api/ingress/`)
- Gmail webhook receiver
- Payload validation
- RawEvent persistence

#### 2. Normalization Layer (`app/core/normalizer.py`)
- MIME parsing
- LLM classification
- Entity extraction
- NormalizedEvent creation

#### 3. Routing Layer (`app/core/router.py`)
- Tenant-aware routing
- Flow dispatch
- Error handling

#### 4. Business Logic (`app/core/`)
- `preventivi_service.py` - Quote processing
- `documenti_service.py` - Document management (future)
- `attrezzature_service.py` - Equipment tracking (future)

#### 5. Integrations (`app/integrations/`)
- Gmail API
- WhatsApp API
- OneDrive/Excel API
- LLM Service
- Slack Alerts

#### 6. Monitoring (`app/monitoring/`)
- Structured JSON logging
- Fail-safe audit system
- Error persistence
- Slack alerting

#### 7. Data Layer (`app/db/`)
- SQLAlchemy 2.0 async models
- Repository pattern
- Multi-tenant isolation

## 📁 Project Structure

```
automation-humanaise/
├── app/
│   ├── main.py                 # FastAPI app + middleware
│   ├── config.py              # Pydantic settings
│   ├── api/
│   │   ├── admin/
│   │   │   └── health.py      # Health endpoints
│   │   ├── ingress/
│   │   │   └── gmail_webhook.py
│   │   ├── flows/
│   │   │   └── preventivi_v1.py
│   │   └── notifications/
│   │       └── whatsapp.py
│   ├── core/
│   │   ├── normalizer.py      # Event normalization
│   │   ├── router.py          # Flow routing
│   │   ├── preventivi_service.py
│   │   ├── documents_service.py
│   │   └── attrezzature_service.py
│   ├── integrations/
│   │   ├── gmail_api.py
│   │   ├── whatsapp_api.py
│   │   ├── onedrive_api.py
│   │   └── llm_service.py
│   ├── db/
│   │   ├── models.py          # SQLAlchemy models
│   │   ├── session.py         # DB session management
│   │   └── repositories/      # Data access layer
│   ├── scheduler/
│   │   ├── jobs.py            # Background jobs
│   │   └── scheduler.py       # APScheduler config
│   └── monitoring/
│       ├── logger.py          # Structured logging
│       ├── audit.py           # Audit system
│       ├── errors.py          # Error persistence
│       └── slack_alerts.py    # Slack integration
├── tests/
│   ├── conftest.py            # Test fixtures
│   ├── test_e2e_new_quote_flow.py
│   └── test_monitoring.py
├── docs/
│   ├── openapi_health.json
│   └── postman_health_collection.json
├── alembic/                   # Database migrations
├── .github/
│   └── copilot-instructions.md
├── .env.example
├── .gitignore
├── requirements.txt
├── README.md
├── CHANGELOG.md
└── IMPLEMENTATION_SUMMARY.md
```

## 🔧 Configuration

### Environment Variables

| Variable | Required | Description | Default |
|----------|----------|-------------|---------|
| `DATABASE_URL` | Yes | PostgreSQL connection string | - |
| `GMAIL_CREDENTIALS_PATH` | Yes | Path to Gmail API credentials | - |
| `WHATSAPP_API_TOKEN` | Yes | WhatsApp Business API token | - |
| `ONEDRIVE_CLIENT_ID` | Yes | Azure app client ID | - |
| `ONEDRIVE_CLIENT_SECRET` | Yes | Azure app client secret | - |
| `ONEDRIVE_TENANT_ID` | Yes | Microsoft tenant ID | - |
| `ONEDRIVE_DRIVE_ID` | Yes | OneDrive drive ID | - |
| `ONEDRIVE_EXCEL_FILE_ID` | Yes | Excel file ID for updates | - |
| `SLACK_WEBHOOK_URL` | No | Slack webhook for alerts | None |
| `LOG_LEVEL` | No | Logging level | INFO |
| `HOST` | No | Server host | 0.0.0.0 |
| `PORT` | No | Server port | 8000 |

## 🐛 Debugging

### Enable Debug Logging
```bash
LOG_LEVEL=DEBUG uvicorn app.main:app --reload
```

### Check Database Connection
```bash
python -c "
import asyncio
from app.db.session import SessionLocal

async def test_db():
    async with SessionLocal() as session:
        result = await session.execute('SELECT 1')
        print('DB connection OK:', result.scalar())

asyncio.run(test_db())
"
```

### View Logs
```bash
# Application logs are printed to stdout in JSON format
tail -f logs/app.log | jq .
```

## 🚢 Deployment

### Docker Deployment (Recommended)

```bash
# Build image
docker build -t edilcos-backend:latest .

# Run container
docker run -d \
  --name edilcos-backend \
  -p 8000:8000 \
  --env-file .env \
  edilcos-backend:latest
```

### Docker Compose

```yaml
version: '3.8'

services:
  backend:
    build: .
    ports:
      - "8000:8000"
    env_file:
      - .env
    depends_on:
      - postgres
    restart: unless-stopped

  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: edilcos
      POSTGRES_USER: edilcos
      POSTGRES_PASSWORD: secure_password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

volumes:
  postgres_data:
```

### Kubernetes Deployment

See `k8s/` directory for Kubernetes manifests including:
- Deployment
- Service
- ConfigMap
- Secret
- Ingress

## 📊 Monitoring

### Health Checks
```bash
# Basic health
curl http://localhost:8000/admin/health

# Deep health (includes DB check)
curl http://localhost:8000/admin/health/deep

# Readiness probe
curl http://localhost:8000/admin/ready
```

### Metrics
- Application exposes health endpoints for monitoring
- Logs are in structured JSON format for log aggregation
- Audit events are persisted to database
- Critical errors are sent to Slack

### Observability Stack
- **Logs**: JSON structured logs → ELK/CloudWatch/etc.
- **Metrics**: Health endpoints → Prometheus/Grafana
- **Traces**: (Future) OpenTelemetry integration
- **Alerts**: Slack webhooks for critical errors

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'feat: add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Commit Convention
We follow [Conventional Commits](https://www.conventionalcommits.org/):
- `feat:` New features
- `fix:` Bug fixes
- `docs:` Documentation changes
- `test:` Test additions/changes
- `refactor:` Code refactoring
- `chore:` Maintenance tasks

## 📝 License

This project is proprietary software. All rights reserved.

## 📞 Support

- **Documentation**: See `docs/` directory and `IMPLEMENTATION_SUMMARY.md`
- **Architecture Guide**: `.github/copilot-instructions.md`
- **Changelog**: `CHANGELOG.md`
- **Issues**: GitHub Issues
- **Contact**: [Maintainer Email]

---

**Built with ❤️ for Edilcos construction workflows**

## 🔗 Quick Links

- [Architecture Overview](IMPLEMENTATION_SUMMARY.md)
- [API Documentation](http://localhost:8000/docs)
- [Changelog](CHANGELOG.md)
- [Copilot Instructions](.github/copilot-instructions.md)

