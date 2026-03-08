"""add was_missed to meal_logs

Revision ID: add_was_missed
Revises: add_meal_plan_link
Create Date: 2026-03-04

Adds a was_missed boolean column to meal_logs.

A meal log is "missed" when:
  - consumed_datetime IS NULL  (never eaten)
  - was_skipped = False        (never explicitly skipped)
  - planned_datetime is in a past day

A nightly job (NotificationWorker._transition_missed_meals) runs at
00:30 IST (18:30 UTC) and transitions all qualifying past-day rows to
was_missed = True.

Phase 1 impact (no frontend contract changes):
  - Upcoming/pending list queries exclude was_missed rows
  - Status fields in API responses are unchanged ("pending" stays "pending")
  - Phase 2 will add "missed" to status fields when frontend is ready
"""
from alembic import op
import sqlalchemy as sa


revision = 'add_was_missed'
down_revision = 'add_email_verification'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'meal_logs',
        sa.Column('was_missed', sa.Boolean(), nullable=False, server_default='false')
    )
    # Backfill: rows that are already logically missed (past, unresolved)
    # Matches: planned_datetime < today midnight, no action taken, no plan link
    # or from any plan. Conservative — only marks rows from before today.
    op.execute("""
        UPDATE meal_logs
        SET was_missed = true
        WHERE consumed_datetime IS NULL
          AND was_skipped = false
          AND planned_datetime < date_trunc('day', NOW() AT TIME ZONE 'Asia/Kolkata') AT TIME ZONE 'Asia/Kolkata'
    """)


def downgrade():
    op.drop_column('meal_logs', 'was_missed')
