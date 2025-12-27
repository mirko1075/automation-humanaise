"""add raw_payload column to imap_raw_events

Revision ID: 20251227_add_raw_payload_imap_raw_events
Revises: 20251221_add_imap_raw_events
Create Date: 2025-12-27 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20251227_add_raw_payload_imap_raw_events'
down_revision = '20251221_add_imap_raw_events'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add nullable JSON/JSONB column `raw_payload` to imap_raw_events
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == 'postgresql':
        op.add_column('imap_raw_events', sa.Column('raw_payload', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    else:
        op.add_column('imap_raw_events', sa.Column('raw_payload', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('imap_raw_events', 'raw_payload')
