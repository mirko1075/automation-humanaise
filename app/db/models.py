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
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=True, index=True)
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
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    flow_id = Column(String, nullable=True)
    source = Column(String, nullable=False)
    payload = Column(JSON, nullable=False)
    processed = Column(Boolean, default=False)
    idempotency_key = Column(String, nullable=False, unique=True)
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
