"""add enrichment fields to receipt_pending_items

Revision ID: add_enrichment_fields
Revises:
Create Date: 2025-11-01

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_enrichment_fields'
down_revision = '6e8f2a4b9c3d'
branch_labels = None
depends_on = None


def upgrade():
    # Add enrichment fields to receipt_pending_items
    op.add_column('receipt_pending_items',
        sa.Column('canonical_name', sa.String(100), nullable=True))
    op.add_column('receipt_pending_items',
        sa.Column('category', sa.String(50), nullable=True))
    op.add_column('receipt_pending_items',
        sa.Column('fdc_id', sa.String(20), nullable=True))
    op.add_column('receipt_pending_items',
        sa.Column('nutrition_data', postgresql.JSON, nullable=True))
    op.add_column('receipt_pending_items',
        sa.Column('enrichment_confidence', sa.Float, nullable=True))
    op.add_column('receipt_pending_items',
        sa.Column('enrichment_reasoning', sa.Text, nullable=True))


def downgrade():
    # Remove enrichment fields
    op.drop_column('receipt_pending_items', 'enrichment_reasoning')
    op.drop_column('receipt_pending_items', 'enrichment_confidence')
    op.drop_column('receipt_pending_items', 'nutrition_data')
    op.drop_column('receipt_pending_items', 'fdc_id')
    op.drop_column('receipt_pending_items', 'category')
    op.drop_column('receipt_pending_items', 'canonical_name')
