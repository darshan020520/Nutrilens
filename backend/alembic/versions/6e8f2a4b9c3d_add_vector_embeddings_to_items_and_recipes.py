"""add vector embeddings to items and recipes

Revision ID: 6e8f2a4b9c3d
Revises: 5d6e19f33c21
Create Date: 2025-10-19 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '6e8f2a4b9c3d'
down_revision: Union[str, None] = '5d6e19f33c21'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ========================================
    # STEP 1: Install pgvector extension
    # ========================================
    # This requires PostgreSQL superuser privileges
    # If this fails, you may need to run manually: CREATE EXTENSION IF NOT EXISTS vector;
    try:
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
        print("✅ pgvector extension installed successfully")
    except Exception as e:
        print(f"⚠️  Warning: Could not create vector extension. You may need to run manually: {e}")
        print("   Run this SQL command: CREATE EXTENSION IF NOT EXISTS vector;")

    # ========================================
    # STEP 2: Add embedding columns to items table
    # ========================================
    # All columns are nullable for backward compatibility
    print("Adding embedding columns to items table...")
    op.add_column('items', sa.Column('embedding', sa.Text(), nullable=True))
    op.add_column('items', sa.Column('embedding_model', sa.String(50), nullable=True))
    op.add_column('items', sa.Column('embedding_version', sa.Integer(), nullable=True))
    op.add_column('items', sa.Column('source', sa.String(20), nullable=True))

    # Set default source for existing items
    op.execute("UPDATE items SET source = 'manual' WHERE source IS NULL")
    print("✅ Items table updated")

    # ========================================
    # STEP 3: Add embedding columns to recipes table
    # ========================================
    print("Adding embedding columns to recipes table...")
    op.add_column('recipes', sa.Column('embedding', sa.Text(), nullable=True))
    op.add_column('recipes', sa.Column('source', sa.String(20), nullable=True))
    op.add_column('recipes', sa.Column('external_id', sa.String(100), nullable=True))

    # Set default source for existing recipes
    op.execute("UPDATE recipes SET source = 'manual' WHERE source IS NULL")
    print("✅ Recipes table updated")

    # ========================================
    # STEP 4: Add audit columns to recipe_ingredients (optional)
    # ========================================
    print("Adding audit columns to recipe_ingredients table...")
    op.add_column('recipe_ingredients', sa.Column('normalized_confidence', sa.Float(), nullable=True))
    op.add_column('recipe_ingredients', sa.Column('original_ingredient_text', sa.Text(), nullable=True))
    print("✅ Recipe ingredients table updated")

    # ========================================
    # STEP 5: Create indexes for new columns
    # ========================================
    print("Creating indexes...")
    op.create_index('ix_items_source', 'items', ['source'], unique=False)
    op.create_index('ix_recipes_source', 'recipes', ['source'], unique=False)
    print("✅ Indexes created")

    print("\n" + "="*60)
    print("✅ Migration complete!")
    print("="*60)
    print("\n⚠️  IMPORTANT NEXT STEPS:")
    print("   1. Run seeding script to populate embeddings")
    print("   2. After embeddings are populated, create HNSW indexes:")
    print("      CREATE INDEX items_embedding_idx ON items USING hnsw ((embedding::vector(1536)) vector_cosine_ops);")
    print("      CREATE INDEX recipes_embedding_idx ON recipes USING hnsw ((embedding::vector(1536)) vector_cosine_ops);")
    print("="*60 + "\n")


def downgrade() -> None:
    print("Downgrading migration...")

    # ========================================
    # Remove indexes
    # ========================================
    print("Removing indexes...")
    op.drop_index('ix_recipes_source', table_name='recipes')
    op.drop_index('ix_items_source', table_name='items')

    # ========================================
    # Remove columns from recipe_ingredients
    # ========================================
    print("Removing audit columns from recipe_ingredients...")
    op.drop_column('recipe_ingredients', 'original_ingredient_text')
    op.drop_column('recipe_ingredients', 'normalized_confidence')

    # ========================================
    # Remove columns from recipes
    # ========================================
    print("Removing embedding columns from recipes...")
    op.drop_column('recipes', 'external_id')
    op.drop_column('recipes', 'source')
    op.drop_column('recipes', 'embedding')

    # ========================================
    # Remove columns from items
    # ========================================
    print("Removing embedding columns from items...")
    op.drop_column('items', 'source')
    op.drop_column('items', 'embedding_version')
    op.drop_column('items', 'embedding_model')
    op.drop_column('items', 'embedding')

    # Note: We don't drop the vector extension as other tables might use it
    # If you want to remove it completely, run manually: DROP EXTENSION IF EXISTS vector;

    print("✅ Downgrade complete!")
