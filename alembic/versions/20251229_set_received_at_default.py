"""set default for imap_raw_events.received_at

Revision ID: 20251229_set_received_at_default
Revises: 20251228_imap_raw_events_uid_to_text
Create Date: 2025-12-29 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20251229_set_received_at_default'
down_revision = '20251228_imap_raw_events_uid_to_text'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    # Backfill any existing NULL received_at with now(), then set a server default
    if dialect == 'postgresql':
        # backfill NULLs
        op.execute("UPDATE imap_raw_events SET received_at = now() WHERE received_at IS NULL;")
        # set server default to now()
        op.execute("ALTER TABLE imap_raw_events ALTER COLUMN received_at SET DEFAULT now();")
    else:
        # SQLite/fallback: set values for existing rows; altering defaults on SQLite is limited
        op.execute("UPDATE imap_raw_events SET received_at = CURRENT_TIMESTAMP WHERE received_at IS NULL;")
        # For SQLite, attempt to set default using batch_alter_table
        with op.batch_alter_table('imap_raw_events') as batch_op:
            batch_op.alter_column('received_at', existing_type=sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"))


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == 'postgresql':
        op.execute("ALTER TABLE imap_raw_events ALTER COLUMN received_at DROP DEFAULT;")
    else:
        # SQLite: remove server_default by recreating table in batch (best-effort)
        with op.batch_alter_table('imap_raw_events') as batch_op:
            batch_op.alter_column('received_at', existing_type=sa.DateTime(), server_default=None)
