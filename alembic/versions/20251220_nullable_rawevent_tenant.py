"""make raw_events.tenant_id nullable

Revision ID: 20251220_nullable_rawevent_tenant
Revises: 20251220_add_contact_channels
Create Date: 2025-12-20 18:40:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20251220_nullable_rawevent_tenant'
down_revision = '20251220_add_contact_channels'
branch_labels = None
depends_on = None


def upgrade():
    # Alter raw_events.tenant_id to be nullable
    op.alter_column('raw_events', 'tenant_id', existing_type=sa.dialects.postgresql.UUID(), nullable=True)


def downgrade():
    # Revert raw_events.tenant_id to NOT NULL (if there are no NULLs this will succeed)
    op.alter_column('raw_events', 'tenant_id', existing_type=sa.dialects.postgresql.UUID(), nullable=False)
