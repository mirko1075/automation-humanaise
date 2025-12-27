"""
Revision ID: 005_preventivi_pipeline
Revises: 
Create Date: 2025-12-27

Alembic migration for PREVENTIVI pipeline and rules engine tables.
"""
from alembic import op
import sqlalchemy as sa
import sqlalchemy.dialects.postgresql as psql
import uuid

# revision identifiers, used by Alembic.
revision = '005_preventivi_pipeline'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # --- ENUMS ---
    op.create_enum('sourcefirstseenenum', 'email', 'whatsapp', 'manual', 'import', schema=None)
    op.create_enum('quoterequeststatusenum', 'NEW', 'TRIAGED', 'NEEDS_INFO', 'CONVERTED', 'REJECTED', schema=None)
    op.create_enum('urgencyenum', 'LOW', 'MEDIUM', 'HIGH', schema=None)
    op.create_enum('quotestatusenum', 'DRAFT', 'SENT', 'ACCEPTED', 'REJECTED', 'EXPIRED', 'CANCELLED', schema=None)
    op.create_enum('actortypeenum', 'system', 'user', 'n8n', schema=None)
    op.create_enum('rulesetscopeenum', 'NORMALIZATION', 'TRIAGE', 'ACTIONS', schema=None)
    op.create_enum('actiontypeenum', 'SEND_EMAIL', 'UPDATE_EXCEL', 'SEND_WHATSAPP', schema=None)
    op.create_enum('executionplanstatusenum', 'PENDING', 'SENT', 'FAILED', schema=None)

    # --- TABLES ---
    op.create_table(
        'customers',
        sa.Column('id', psql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('tenant_id', sa.String, nullable=False, index=True),
        sa.Column('display_name', sa.String, nullable=False),
        sa.Column('email', sa.String, nullable=True),
        sa.Column('phone', sa.String, nullable=True),
        sa.Column('tax_code', sa.String, nullable=True),
        sa.Column('vat_number', sa.String, nullable=True),
        sa.Column('address_line', sa.String, nullable=True),
        sa.Column('city', sa.String, nullable=True),
        sa.Column('province', sa.String, nullable=True),
        sa.Column('zip', sa.String, nullable=True),
        sa.Column('country', sa.String, nullable=True),
        sa.Column('source_first_seen', sa.Enum('email', 'whatsapp', 'manual', 'import', name='sourcefirstseenenum'), nullable=False),
        sa.Column('first_seen_at', sa.DateTime, nullable=False),
        sa.Column('last_seen_at', sa.DateTime, nullable=False),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
        sa.UniqueConstraint('tenant_id', 'email', name='uq_customers_tenant_email'),
        sa.UniqueConstraint('tenant_id', 'phone', name='uq_customers_tenant_phone'),
    )

    op.create_table(
        'quote_requests',
        sa.Column('id', psql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('tenant_id', sa.String, nullable=False, index=True),
        sa.Column('normalized_event_id', psql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column('customer_id', psql.UUID(as_uuid=True), sa.ForeignKey('customers.id'), nullable=True),
        sa.Column('status', sa.Enum('NEW', 'TRIAGED', 'NEEDS_INFO', 'CONVERTED', 'REJECTED', name='quoterequeststatusenum'), nullable=False),
        sa.Column('urgency', sa.Enum('LOW', 'MEDIUM', 'HIGH', name='urgencyenum'), nullable=True),
        sa.Column('confidence', sa.Float, nullable=True),
        sa.Column('contact_name', sa.String, nullable=True),
        sa.Column('contact_email', sa.String, nullable=True),
        sa.Column('contact_phone', sa.String, nullable=True),
        sa.Column('job_type', sa.String, nullable=True),
        sa.Column('job_description', sa.Text, nullable=True),
        sa.Column('location_text', sa.String, nullable=True),
        sa.Column('address_line', sa.String, nullable=True),
        sa.Column('city', sa.String, nullable=True),
        sa.Column('province', sa.String, nullable=True),
        sa.Column('zip', sa.String, nullable=True),
        sa.Column('preferred_date_from', sa.Date, nullable=True),
        sa.Column('preferred_date_to', sa.Date, nullable=True),
        sa.Column('budget_min', sa.Numeric(12,2), nullable=True),
        sa.Column('budget_max', sa.Numeric(12,2), nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
        sa.Index('ix_quote_requests_tenant_status_created', 'tenant_id', 'status', 'created_at'),
    )

    op.create_table(
        'quotes',
        sa.Column('id', psql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('tenant_id', sa.String, nullable=False, index=True),
        sa.Column('quote_request_id', psql.UUID(as_uuid=True), sa.ForeignKey('quote_requests.id'), nullable=False, unique=True),
        sa.Column('customer_id', psql.UUID(as_uuid=True), sa.ForeignKey('customers.id'), nullable=False),
        sa.Column('status', sa.Enum('DRAFT', 'SENT', 'ACCEPTED', 'REJECTED', 'EXPIRED', 'CANCELLED', name='quotestatusenum'), nullable=False),
        sa.Column('title', sa.String, nullable=True),
        sa.Column('summary', sa.Text, nullable=True),
        sa.Column('total_amount', sa.Numeric(12,2), nullable=True),
        sa.Column('currency', sa.String, nullable=False, default='EUR'),
        sa.Column('valid_until', sa.Date, nullable=True),
        sa.Column('assigned_to_user_id', sa.String, nullable=True),
        sa.Column('external_ref_excel', sa.String, nullable=True),
        sa.Column('folder_path', sa.String, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )

    op.create_table(
        'quote_attachments',
        sa.Column('id', psql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('tenant_id', sa.String, nullable=False, index=True),
        sa.Column('quote_request_id', psql.UUID(as_uuid=True), sa.ForeignKey('quote_requests.id'), nullable=False),
        sa.Column('quote_id', psql.UUID(as_uuid=True), sa.ForeignKey('quotes.id'), nullable=True),
        sa.Column('filename', sa.String, nullable=False),
        sa.Column('mime_type', sa.String, nullable=False),
        sa.Column('size_bytes', sa.Integer, nullable=False),
        sa.Column('storage_url', sa.String, nullable=False),
        sa.Column('sha256', sa.String, nullable=False),
        sa.Column('created_at', sa.DateTime, nullable=False),
    )

    op.create_table(
        'quote_events',
        sa.Column('id', psql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('tenant_id', sa.String, nullable=False, index=True),
        sa.Column('quote_request_id', psql.UUID(as_uuid=True), sa.ForeignKey('quote_requests.id'), nullable=False),
        sa.Column('quote_id', psql.UUID(as_uuid=True), sa.ForeignKey('quotes.id'), nullable=True),
        sa.Column('event_type', sa.String, nullable=False),
        sa.Column('actor_type', sa.Enum('system', 'user', 'n8n', name='actortypeenum'), nullable=False),
        sa.Column('actor_id', sa.String, nullable=True),
        sa.Column('payload', psql.JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False),
    )

    op.create_table(
        'rulesets',
        sa.Column('id', psql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('tenant_id', sa.String, nullable=False, index=True),
        sa.Column('name', sa.String, nullable=False),
        sa.Column('scope', sa.Enum('NORMALIZATION', 'TRIAGE', 'ACTIONS', name='rulesetscopeenum'), nullable=False),
        sa.Column('version', sa.Integer, nullable=False),
        sa.Column('active', sa.Boolean, nullable=False, default=True),
        sa.Column('created_at', sa.DateTime, nullable=False),
    )

    op.create_table(
        'rules',
        sa.Column('id', psql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('tenant_id', sa.String, nullable=False, index=True),
        sa.Column('ruleset_id', psql.UUID(as_uuid=True), sa.ForeignKey('rulesets.id'), nullable=False),
        sa.Column('name', sa.String, nullable=False),
        sa.Column('priority', sa.Integer, nullable=False),
        sa.Column('enabled', sa.Boolean, nullable=False, default=True),
        sa.Column('match', psql.JSONB, nullable=False),
        sa.Column('actions', psql.JSONB, nullable=False),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )

    op.create_table(
        'rule_runs',
        sa.Column('id', psql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('tenant_id', sa.String, nullable=False, index=True),
        sa.Column('normalized_event_id', psql.UUID(as_uuid=True), nullable=False),
        sa.Column('ruleset_scope', sa.Enum('NORMALIZATION', 'TRIAGE', 'ACTIONS', name='rulesetscopeenum'), nullable=False),
        sa.Column('ruleset_version', sa.Integer, nullable=False),
        sa.Column('result', psql.JSONB, nullable=False),
        sa.Column('executed_at', sa.DateTime, nullable=False),
    )

    op.create_table(
        'execution_plans',
        sa.Column('id', psql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('tenant_id', sa.String, nullable=False, index=True),
        sa.Column('action_type', sa.Enum('SEND_EMAIL', 'UPDATE_EXCEL', 'SEND_WHATSAPP', name='actiontypeenum'), nullable=False),
        sa.Column('payload', psql.JSONB, nullable=False),
        sa.Column('status', sa.Enum('PENDING', 'SENT', 'FAILED', name='executionplanstatusenum'), nullable=False),
        sa.Column('created_at', sa.DateTime, nullable=False),
    )

def downgrade():
    op.drop_table('execution_plans')
    op.drop_table('rule_runs')
    op.drop_table('rules')
    op.drop_table('rulesets')
    op.drop_table('quote_events')
    op.drop_table('quote_attachments')
    op.drop_table('quotes')
    op.drop_table('quote_requests')
    op.drop_table('customers')
    op.execute('DROP TYPE IF EXISTS sourcefirstseenenum')
    op.execute('DROP TYPE IF EXISTS quoterequeststatusenum')
    op.execute('DROP TYPE IF EXISTS urgencyenum')
    op.execute('DROP TYPE IF EXISTS quotestatusenum')
    op.execute('DROP TYPE IF EXISTS actortypeenum')
    op.execute('DROP TYPE IF EXISTS rulesetscopeenum')
    op.execute('DROP TYPE IF EXISTS actiontypeenum')
    op.execute('DROP TYPE IF EXISTS executionplanstatusenum')
