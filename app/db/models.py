# --- PREVENTIVI PIPELINE & RULES ENGINE MODELS ---
import enum
from sqlalchemy import Enum, Numeric, JSON as SAJSON, Date
from sqlalchemy.dialects.postgresql import JSONB

# --- ENUMS ---
class SourceFirstSeenEnum(str, enum.Enum):
    email = "email"
    whatsapp = "whatsapp"
    manual = "manual"
    import_ = "import"

class QuoteRequestStatusEnum(str, enum.Enum):
    NEW = "NEW"
    TRIAGED = "TRIAGED"
    NEEDS_INFO = "NEEDS_INFO"
    CONVERTED = "CONVERTED"
    REJECTED = "REJECTED"

class UrgencyEnum(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

class QuoteStatusEnum(str, enum.Enum):
    DRAFT = "DRAFT"
    SENT = "SENT"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"

class ActorTypeEnum(str, enum.Enum):
    system = "system"
    user = "user"
    n8n = "n8n"

class RulesetScopeEnum(str, enum.Enum):
    NORMALIZATION = "NORMALIZATION"
    TRIAGE = "TRIAGE"
    ACTIONS = "ACTIONS"

class ActionTypeEnum(str, enum.Enum):
    SEND_EMAIL = "SEND_EMAIL"
    UPDATE_EXCEL = "UPDATE_EXCEL"
    SEND_WHATSAPP = "SEND_WHATSAPP"

class ExecutionPlanStatusEnum(str, enum.Enum):
    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"

# --- MODELS ---

class PreventiviCustomer(Base):
    __tablename__ = "customers"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(String, nullable=False, index=True)
    display_name = Column(String, nullable=False)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    tax_code = Column(String, nullable=True)
    vat_number = Column(String, nullable=True)
    address_line = Column(String, nullable=True)
    city = Column(String, nullable=True)
    province = Column(String, nullable=True)
    zip = Column(String, nullable=True)
    country = Column(String, nullable=True)
    source_first_seen = Column(Enum(SourceFirstSeenEnum), nullable=False)
    first_seen_at = Column(DateTime, nullable=False)
    last_seen_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="uq_customers_tenant_email"),
        UniqueConstraint("tenant_id", "phone", name="uq_customers_tenant_phone"),
    )

class QuoteRequest(Base):
    __tablename__ = "quote_requests"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(String, nullable=False, index=True)
    normalized_event_id = Column(UUID(as_uuid=True), nullable=False, unique=True)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=True)
    status = Column(Enum(QuoteRequestStatusEnum), nullable=False)
    urgency = Column(Enum(UrgencyEnum), nullable=True)
    confidence = Column(Float, nullable=True)
    contact_name = Column(String, nullable=True)
    contact_email = Column(String, nullable=True)
    contact_phone = Column(String, nullable=True)
    job_type = Column(String, nullable=True)
    job_description = Column(Text, nullable=True)
    location_text = Column(String, nullable=True)
    address_line = Column(String, nullable=True)
    city = Column(String, nullable=True)
    province = Column(String, nullable=True)
    zip = Column(String, nullable=True)
    preferred_date_from = Column(Date, nullable=True)
    preferred_date_to = Column(Date, nullable=True)
    budget_min = Column(Numeric(12, 2), nullable=True)
    budget_max = Column(Numeric(12, 2), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
    __table_args__ = (
        Index("ix_quote_requests_tenant_status_created", "tenant_id", "status", "created_at"),
    )

class Quote(Base):
    __tablename__ = "quotes"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(String, nullable=False, index=True)
    quote_request_id = Column(UUID(as_uuid=True), ForeignKey("quote_requests.id"), nullable=False, unique=True)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    status = Column(Enum(QuoteStatusEnum), nullable=False)
    title = Column(String, nullable=True)
    summary = Column(Text, nullable=True)
    total_amount = Column(Numeric(12, 2), nullable=True)
    currency = Column(String, nullable=False, default="EUR")
    valid_until = Column(Date, nullable=True)
    assigned_to_user_id = Column(String, nullable=True)
    external_ref_excel = Column(String, nullable=True)
    folder_path = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

class QuoteAttachment(Base):
    __tablename__ = "quote_attachments"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(String, nullable=False, index=True)
    quote_request_id = Column(UUID(as_uuid=True), ForeignKey("quote_requests.id"), nullable=False)
    quote_id = Column(UUID(as_uuid=True), ForeignKey("quotes.id"), nullable=True)
    filename = Column(String, nullable=False)
    mime_type = Column(String, nullable=False)
    size_bytes = Column(Integer, nullable=False)
    storage_url = Column(String, nullable=False)
    sha256 = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False)

class QuoteEvent(Base):
    __tablename__ = "quote_events"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(String, nullable=False, index=True)
    quote_request_id = Column(UUID(as_uuid=True), ForeignKey("quote_requests.id"), nullable=False)
    quote_id = Column(UUID(as_uuid=True), ForeignKey("quotes.id"), nullable=True)
    event_type = Column(String, nullable=False)
    actor_type = Column(Enum(ActorTypeEnum), nullable=False)
    actor_id = Column(String, nullable=True)
    payload = Column(JSONB, nullable=True)
    created_at = Column(DateTime, nullable=False)

class Ruleset(Base):
    __tablename__ = "rulesets"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    scope = Column(Enum(RulesetScopeEnum), nullable=False)
    version = Column(Integer, nullable=False)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False)

class Rule(Base):
    __tablename__ = "rules"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(String, nullable=False, index=True)
    ruleset_id = Column(UUID(as_uuid=True), ForeignKey("rulesets.id"), nullable=False)
    name = Column(String, nullable=False)
    priority = Column(Integer, nullable=False)
    enabled = Column(Boolean, nullable=False, default=True)
    match = Column(JSONB, nullable=False)
    actions = Column(JSONB, nullable=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

class RuleRun(Base):
    __tablename__ = "rule_runs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(String, nullable=False, index=True)
    normalized_event_id = Column(UUID(as_uuid=True), nullable=False)
    ruleset_scope = Column(Enum(RulesetScopeEnum), nullable=False)
    ruleset_version = Column(Integer, nullable=False)
    result = Column(JSONB, nullable=False)
    executed_at = Column(DateTime, nullable=False)

class ExecutionPlan(Base):
    __tablename__ = "execution_plans"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(String, nullable=False, index=True)
    action_type = Column(Enum(ActionTypeEnum), nullable=False)
    payload = Column(JSONB, nullable=False)
    status = Column(Enum(ExecutionPlanStatusEnum), nullable=False)
    created_at = Column(DateTime, nullable=False)
# app/db/models.py
"""
Tenant-aware SQLAlchemy models for Edilcos Automation Backend.
"""
from sqlalchemy import Column, String, DateTime, Boolean, JSON, ForeignKey, Text, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from uuid import uuid4
from datetime import datetime, timezone
from app.db.session import Base

class Tenant(Base):
    __tablename__ = "tenants"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String, nullable=False)
    status = Column(String, nullable=False, default="active")
    active_flows = Column(JSON, nullable=True)
    # Contact channels used for tenant resolution (ingress)
    # Example: {"email": ["mirko.siddi@gmail.com"], "whatsapp": ["+39..."]}
    contact_channels = Column(JSON, nullable=True)
    file_provider = Column(String, nullable=True)  # "localfs", "onedrive", "gdrive", etc.
    file_config = Column(JSON, nullable=True)  # Provider-specific configuration
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)


# Best-effort: if tests use a SQLite in-memory DB, create tables now that models are defined.
try:
    from app.db.session import engine, DATABASE_URL

    if DATABASE_URL and DATABASE_URL.startswith("sqlite"):
        try:
            # create_all using the sync engine to avoid async context during import
            Base.metadata.create_all(bind=engine.sync_engine)
        except Exception:
            pass
except Exception:
    pass

class ExternalToken(Base):
    __tablename__ = "external_tokens"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    flow_id = Column(String, nullable=True)
    provider = Column(String, nullable=False)
    external_id = Column(String, nullable=True)
    data = Column(JSON, nullable=True)
    token = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)

class RawEvent(Base):
    __tablename__ = "raw_events"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    # tenant_id is nullable to allow unassigned/unknown-tenant ingress events
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=True, index=True)
    flow_id = Column(String, nullable=True)
    source = Column(String, nullable=False)
    payload = Column(JSON, nullable=False)
    processed = Column(Boolean, default=False)
    idempotency_key = Column(String, nullable=False, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)


class ReceivedEmail(Base):
    __tablename__ = "received_emails"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=True, index=True)
    channel = Column(String, nullable=False)  # 'email', 'whatsapp', etc.
    identifier = Column(String, nullable=True)  # e.g., email address or phone number
    external_ref = Column(String, nullable=True)  # historyId or external message reference
    outcome = Column(String, nullable=False, default="received")
    processed = Column(Boolean, default=False)
    raw_payload = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)

class NormalizedEvent(Base):
    __tablename__ = "normalized_events"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    flow_id = Column(String, nullable=False)
    event_type = Column(String, nullable=False)
    normalized_data = Column(JSON, nullable=False)
    status = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)

class Customer(Base):
    __tablename__ = "customers"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    flow_id = Column(String, nullable=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)

class Quote(Base):
    __tablename__ = "quotes"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    flow_id = Column(String, nullable=False)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    quote_data = Column(JSON, nullable=False)
    status = Column(String, nullable=False)
    pdf_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)

class Notification(Base):
    __tablename__ = "notifications"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    flow_id = Column(String, nullable=False)
    event_id = Column(UUID(as_uuid=True), ForeignKey("normalized_events.id"), nullable=False)
    channel = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    payload = Column(JSON, nullable=True)  # For WhatsApp API payload
    status = Column(String, nullable=False)
    retry_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=True, index=True)
    flow_id = Column(String, nullable=True)
    action = Column(String, nullable=False)
    actor = Column(String, nullable=True)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)


class ErrorLog(Base):
    __tablename__ = "error_logs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    request_id = Column(String, nullable=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=True, index=True)
    flow_id = Column(String, nullable=True)
    component = Column(String, nullable=True)
    function = Column(String, nullable=True)
    severity = Column(String, nullable=False, default="ERROR")
    message = Column(Text, nullable=False)
    details = Column(JSON, nullable=True)
    stacktrace = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)


class IntegrationEvent(Base):
    __tablename__ = "integration_events"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    integration = Column(String, nullable=False, index=True)
    event_type = Column(String, nullable=False, index=True)
    level = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    context = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
