"""add contact_channels to tenants

Revision ID: 20251220_add_contact_channels
Revises: 
Create Date: 2025-12-20 18:30:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20251220_add_contact_channels'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('tenants', sa.Column('contact_channels', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")))


def downgrade():
    op.drop_column('tenants', 'contact_channels')
