"""add image_url to recipes

Revision ID: add_image_url_recipes
Revises: add_was_missed
Create Date: 2026-03-05

Adds a nullable image_url column to the recipes table.
This will be populated by the nutrilens-airflow pipeline which
generates food images via Gemini 2.0 Flash and stores them in S3.
"""
from alembic import op
import sqlalchemy as sa


revision = 'add_image_url_recipes'
down_revision = 'add_was_missed'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'recipes',
        sa.Column('image_url', sa.String(500), nullable=True)
    )


def downgrade():
    op.drop_column('recipes', 'image_url')
