"""change imap_raw_events.uid to text

Revision ID: 20251228_imap_raw_events_uid_to_text
Revises: 20251227_add_raw_payload_imap_raw_events
Create Date: 2025-12-28 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20251228_imap_raw_events_uid_to_text'
down_revision = '20251227_add_raw_payload_imap_raw_events'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    # Drop existing unique constraint (depends on DB naming)
    try:
        op.drop_constraint('uq_imap_uid', 'imap_raw_events', type_='unique')
    except Exception:
        # best-effort: constraint might have different name in some DBs
        pass

    if dialect == 'postgresql':
        # Alter column type to TEXT using USING cast
        op.execute("ALTER TABLE imap_raw_events ALTER COLUMN uid TYPE TEXT USING uid::text;")
    else:
        # SQLite: recreate table fallback
        # SQLite doesn't support ALTER TYPE; emulate by creating a temp table
        with op.batch_alter_table('imap_raw_events') as batch_op:
            batch_op.alter_column('uid', existing_type=sa.Integer(), type_=sa.String(), existing_nullable=False)

    # Recreate unique constraint but allow uid as text
    op.create_unique_constraint('uq_imap_uid', 'imap_raw_events', ['tenant_id', 'mailbox', 'uid', 'uidvalidity'])


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    # Drop the uniq constraint we created
    try:
        op.drop_constraint('uq_imap_uid', 'imap_raw_events', type_='unique')
    except Exception:
        pass

    if dialect == 'postgresql':
        # Cast back to integer where possible; this may fail if non-numeric uids exist
        op.execute("ALTER TABLE imap_raw_events ALTER COLUMN uid TYPE INTEGER USING uid::integer;")
    else:
        with op.batch_alter_table('imap_raw_events') as batch_op:
            batch_op.alter_column('uid', existing_type=sa.String(), type_=sa.Integer(), existing_nullable=False)

    op.create_unique_constraint('uq_imap_uid', 'imap_raw_events', ['tenant_id', 'mailbox', 'uid', 'uidvalidity'])
