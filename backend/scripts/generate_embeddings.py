"""
generate_embeddings.py
-----------------------
Generates and stores embeddings for:
  1. Items where embedding IS NULL
  2. Recipes where embedding IS NULL

Uses text-embedding-3-small (1536 dims), same model as the rest of the pipeline.

Run inside the api container:
  docker compose exec api python scripts/generate_embeddings.py

Options:
  --items-only    Only process items
  --recipes-only  Only process recipes
  --dry-run       Show counts without writing
"""

import asyncio
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from openai import AsyncOpenAI
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.models.database import SessionLocal, Item, Recipe, RecipeIngredient

EMBEDDING_MODEL = "text-embedding-3-small"
BATCH_SIZE = 100  # Max per OpenAI API call


def _item_embedding_text(item: Item) -> str:
    """Rich text used to generate item embedding for semantic matching."""
    parts = [item.canonical_name]
    if item.aliases:
        parts.extend(item.aliases)
    if item.category:
        parts.append(item.category)
    return " ".join(parts).lower().strip()


def _recipe_embedding_text(recipe: Recipe) -> str:
    """Title + cuisine + up to 5 main ingredient names."""
    parts = [recipe.title]
    if recipe.cuisine:
        parts.append(recipe.cuisine)
    ingredient_names = [
        ri.item.canonical_name
        for ri in (recipe.ingredients or [])
        if ri.item
    ][:5]
    parts.extend(ingredient_names)
    return " ".join(parts).lower().strip()


async def generate_embeddings_batch(
    client: AsyncOpenAI,
    texts: list[str],
) -> list[list[float]]:
    """Call OpenAI embeddings API in batches and return list of embedding vectors."""
    all_embeddings: list[list[float]] = []
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i : i + BATCH_SIZE]
        response = await client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=[t or "unknown" for t in batch],
        )
        batch_embeddings = [d.embedding for d in sorted(response.data, key=lambda x: x.index)]
        all_embeddings.extend(batch_embeddings)
    return all_embeddings


async def process_items(db: Session, client: AsyncOpenAI, dry_run: bool) -> int:
    items = db.query(Item).filter(Item.embedding.is_(None)).all()
    print(f"  Items missing embeddings: {len(items)}")
    if not items or dry_run:
        return len(items)

    texts = [_item_embedding_text(item) for item in items]
    print(f"  Generating {len(texts)} item embeddings in batches of {BATCH_SIZE}...")
    embeddings = await generate_embeddings_batch(client, texts)

    for item, embedding in zip(items, embeddings):
        item.embedding = json.dumps(embedding)
        item.embedding_model = EMBEDDING_MODEL
        item.embedding_version = 1

    db.commit()
    print(f"  ✓ {len(items)} item embeddings saved.")
    return len(items)


async def process_recipes(db: Session, client: AsyncOpenAI, dry_run: bool) -> int:
    recipes = (
        db.query(Recipe)
        .options(joinedload(Recipe.ingredients).joinedload(RecipeIngredient.item))
        .filter(Recipe.embedding.is_(None))
        .all()
    )
    print(f"  Recipes missing embeddings: {len(recipes)}")
    if not recipes or dry_run:
        return len(recipes)

    texts = [_recipe_embedding_text(r) for r in recipes]
    print(f"  Generating {len(texts)} recipe embeddings in batches of {BATCH_SIZE}...")
    embeddings = await generate_embeddings_batch(client, texts)

    for recipe, embedding in zip(recipes, embeddings):
        recipe.embedding = json.dumps(embedding)

    db.commit()
    print(f"  ✓ {len(recipes)} recipe embeddings saved.")
    return len(recipes)


async def main(items_only: bool, recipes_only: bool, dry_run: bool):
    mode = "DRY RUN" if dry_run else "LIVE"
    print(f"\n{'='*55}")
    print(f"  Generate Embeddings  [{mode}]  model={EMBEDDING_MODEL}")
    print(f"{'='*55}\n")

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    db: Session = SessionLocal()

    try:
        if not recipes_only:
            print("── Items ──")
            await process_items(db, client, dry_run)
            print()

        if not items_only:
            print("── Recipes ──")
            await process_recipes(db, client, dry_run)
            print()

        print("Done.")
    finally:
        db.close()
        await client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--items-only", action="store_true")
    parser.add_argument("--recipes-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(args.items_only, args.recipes_only, args.dry_run))
