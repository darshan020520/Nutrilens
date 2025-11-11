"""add meal_plan_id and day_index to meal_logs

Revision ID: add_meal_plan_link
Revises: add_enrichment_fields
Create Date: 2025-11-03

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_meal_plan_link'
down_revision = 'add_enrichment_fields'
branch_labels = None
depends_on = None


def upgrade():
    """
    Add meal_plan_id and day_index columns to meal_logs table.
    This creates a direct link between meal logs and meal plans,
    making it easier to track and update logs when meals are swapped.
    """
    # Add meal_plan_id column (nullable for existing logs)
    op.add_column('meal_logs',
        sa.Column('meal_plan_id', sa.Integer(), nullable=True))

    # Add day_index column (0-6 for day of week in plan)
    op.add_column('meal_logs',
        sa.Column('day_index', sa.Integer(), nullable=True))

    # Add foreign key constraint
    # ondelete='SET NULL' because meal plans are disabled, not deleted
    op.create_foreign_key(
        'fk_meal_logs_meal_plan_id',
        'meal_logs',
        'meal_plans',
        ['meal_plan_id'],
        ['id'],
        ondelete='SET NULL'
    )

    # Add composite index for fast lookups during meal swaps
    op.create_index(
        'idx_meal_logs_plan_day_meal',
        'meal_logs',
        ['meal_plan_id', 'day_index', 'meal_type']
    )


def downgrade():
    """
    Rollback migration: remove meal_plan_id and day_index.
    """
    # Drop index
    op.drop_index('idx_meal_logs_plan_day_meal', table_name='meal_logs')

    # Drop foreign key
    op.drop_constraint('fk_meal_logs_meal_plan_id', 'meal_logs', type_='foreignkey')

    # Drop columns
    op.drop_column('meal_logs', 'day_index')
    op.drop_column('meal_logs', 'meal_plan_id')
