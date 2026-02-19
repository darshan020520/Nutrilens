"""
Embedding Diagnostic Script

Tests stored embeddings vs freshly generated ones to identify
why vector similarity is low for known-identical items.
"""

import asyncio
import sys
import os
import json
import numpy as np

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.models.database import SessionLocal
from app.core.config import settings
import openai


def cosine_similarity(a, b):
    a = np.array(a)
    b = np.array(b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


async def main():
    db = SessionLocal()
    client = openai.OpenAI(api_key=settings.openai_api_key)

    # Items that had low vector similarity in the debug output
    test_items = [
        "olive_oil",
        "brown_rice",
        "chicken_breast",
        "greek_yogurt",
        "lemon_juice",
        "dal_lentils",
        "red_bell_pepper",
        "green_onion",
    ]

    print("=" * 80)
    print("EMBEDDING DIAGNOSTIC")
    print("=" * 80)

    for canonical_name in test_items:
        # 1. Get stored embedding from DB
        row = db.execute(
            text("SELECT id, canonical_name, aliases, category, embedding FROM items WHERE canonical_name = :name"),
            {"name": canonical_name}
        ).fetchone()

        if not row:
            print(f"\n[SKIP] {canonical_name} not found in DB")
            continue

        item_id, name, aliases, category, stored_embedding_str = row

        if not stored_embedding_str:
            print(f"\n[SKIP] {canonical_name} has no embedding")
            continue

        stored_embedding = json.loads(stored_embedding_str)

        print(f"\n{'─' * 80}")
        print(f"ITEM: {canonical_name} (id={item_id})")
        print(f"  Aliases: {aliases}")
        print(f"  Category: {category}")
        print(f"  Stored embedding length: {len(stored_embedding)}")
        print(f"  Stored embedding non-zero: {sum(1 for v in stored_embedding if v != 0.0)}")
        print(f"  Stored embedding sample: {stored_embedding[:5]}")

        # 2. Generate query embedding (what the vector matcher does)
        query_text = canonical_name.replace("_", " ")  # how LLM extraction produces it
        query_response = client.embeddings.create(
            model="text-embedding-3-small",
            input=query_text.lower().strip()
        )
        query_embedding = query_response.data[0].embedding

        # 3. Reconstruct the rich seeding text and generate embedding for it
        rich_parts = [canonical_name]
        display_name = canonical_name.replace("_", " ").title()
        rich_parts.append(display_name)
        if category:
            rich_parts.append(category)
        if aliases:
            rich_parts.extend(aliases)
        rich_text = " ".join(rich_parts)

        rich_response = client.embeddings.create(
            model="text-embedding-3-small",
            input=rich_text.lower().strip()
        )
        rich_embedding = rich_response.data[0].embedding

        # 4. Generate embedding from just canonical name (with underscores)
        underscore_response = client.embeddings.create(
            model="text-embedding-3-small",
            input=canonical_name.lower().strip()
        )
        underscore_embedding = underscore_response.data[0].embedding

        # 5. Compute all similarities
        sim_query_vs_stored = cosine_similarity(query_embedding, stored_embedding)
        sim_rich_vs_stored = cosine_similarity(rich_embedding, stored_embedding)
        sim_query_vs_rich = cosine_similarity(query_embedding, rich_embedding)
        sim_underscore_vs_stored = cosine_similarity(underscore_embedding, stored_embedding)
        sim_query_vs_underscore = cosine_similarity(query_embedding, underscore_embedding)

        # 6. Also check what pgvector returns
        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"
        pg_result = db.execute(
            text("""
                SELECT canonical_name,
                       1 - (embedding::vector(1536) <=> :embedding ::vector(1536)) as similarity
                FROM items
                WHERE id = :item_id AND embedding IS NOT NULL
            """),
            {"embedding": embedding_str, "item_id": item_id}
        ).fetchone()
        pg_similarity = pg_result[1] if pg_result else "N/A"

        print(f"\n  Query text: '{query_text}'")
        print(f"  Rich seeding text: '{rich_text}'")
        print(f"\n  SIMILARITIES:")
        print(f"    query('{query_text}') vs stored DB embedding:     {sim_query_vs_stored:.4f}")
        print(f"    rich('{rich_text[:40]}...') vs stored DB embedding: {sim_rich_vs_stored:.4f}")
        print(f"    underscore('{canonical_name}') vs stored DB embedding: {sim_underscore_vs_stored:.4f}")
        print(f"    query vs fresh rich embedding:                    {sim_query_vs_rich:.4f}")
        print(f"    query vs fresh underscore embedding:              {sim_query_vs_underscore:.4f}")
        print(f"    pgvector similarity (query vs stored):            {pg_similarity}")

        if sim_rich_vs_stored < 0.95:
            print(f"\n  ⚠ STORED EMBEDDING DOES NOT MATCH FRESH RICH EMBEDDING (sim={sim_rich_vs_stored:.4f})")
            print(f"    This means the stored embedding was NOT generated from the expected rich text.")

        if sim_underscore_vs_stored > sim_rich_vs_stored:
            print(f"  → Stored embedding is CLOSER to underscore text than rich text")

    db.close()
    print(f"\n{'=' * 80}")
    print("DIAGNOSTIC COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())