"""create imap_raw_events table

Revision ID: 20251221_add_imap_raw_events
Revises: 
Create Date: 2025-12-21 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20251221_add_imap_raw_events'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'imap_raw_events',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('tenant_id', sa.String(), nullable=False, index=True),
        sa.Column('mailbox', sa.String(), nullable=False),
        sa.Column('uid', sa.Integer(), nullable=False),
        sa.Column('uidvalidity', sa.String(), nullable=False),
        sa.Column('message_id', sa.String(), nullable=True),
        sa.Column('subject', sa.String(), nullable=True),
        sa.Column('received_at', sa.DateTime(), nullable=False),
        sa.Column('raw', sa.LargeBinary(), nullable=False),
        sa.Column('event_metadata', sa.JSON(), nullable=True),
        sa.UniqueConstraint('tenant_id', 'mailbox', 'uid', 'uidvalidity', name='uq_imap_uid')
    )


def downgrade() -> None:
    op.drop_table('imap_raw_events')
