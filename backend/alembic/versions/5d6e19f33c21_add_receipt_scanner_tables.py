"""add receipt scanner tables

Revision ID: 5d6e19f33c21
Revises: 4c5f18a22d10
Create Date: 2025-10-16 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5d6e19f33c21'
down_revision: Union[str, None] = '4c5f18a22d10'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create receipt_scans table
    op.create_table(
        'receipt_scans',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('s3_url', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=20), server_default='processing', nullable=True),
        sa.Column('items_count', sa.Integer(), nullable=True),
        sa.Column('auto_added_count', sa.Integer(), nullable=True),
        sa.Column('needs_confirmation_count', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_receipt_scans_id'), 'receipt_scans', ['id'], unique=False)
    op.create_index(op.f('ix_receipt_scans_user_id'), 'receipt_scans', ['user_id'], unique=False)
    op.create_index(op.f('ix_receipt_scans_created_at'), 'receipt_scans', ['created_at'], unique=False)

    # Create receipt_pending_items table
    op.create_table(
        'receipt_pending_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('receipt_scan_id', sa.Integer(), nullable=False),
        sa.Column('item_name', sa.Text(), nullable=False),
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('unit', sa.String(length=20), nullable=False),
        sa.Column('suggested_item_id', sa.Integer(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('status', sa.String(length=20), server_default='pending', nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('confirmed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['receipt_scan_id'], ['receipt_scans.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['suggested_item_id'], ['items.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_receipt_pending_items_id'), 'receipt_pending_items', ['id'], unique=False)
    op.create_index(op.f('ix_receipt_pending_items_receipt_scan_id'), 'receipt_pending_items', ['receipt_scan_id'], unique=False)
    op.create_index(op.f('ix_receipt_pending_items_status'), 'receipt_pending_items', ['status'], unique=False)


def downgrade() -> None:
    # Drop tables
    op.drop_index(op.f('ix_receipt_pending_items_status'), table_name='receipt_pending_items')
    op.drop_index(op.f('ix_receipt_pending_items_receipt_scan_id'), table_name='receipt_pending_items')
    op.drop_index(op.f('ix_receipt_pending_items_id'), table_name='receipt_pending_items')
    op.drop_table('receipt_pending_items')

    op.drop_index(op.f('ix_receipt_scans_created_at'), table_name='receipt_scans')
    op.drop_index(op.f('ix_receipt_scans_user_id'), table_name='receipt_scans')
    op.drop_index(op.f('ix_receipt_scans_id'), table_name='receipt_scans')
    op.drop_table('receipt_scans')
