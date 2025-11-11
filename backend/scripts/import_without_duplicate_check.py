"""
Import enriched items WITHOUT any duplicate checking
"""
import json
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models.database import Item, SessionLocal

def import_all_items(json_path: str):
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    items = data["items"]
    print(f"Importing {len(items)} items (NO duplicate checking)...")

    db = SessionLocal()

    try:
        for i, item_data in enumerate(items, 1):
            canonical_name = item_data["canonical_name"]

            # Convert embedding list to JSON string (same as seeder)
            embedding_json = None
            if item_data.get("embedding"):
                embedding_json = json.dumps(item_data["embedding"])

            # Create item exactly like the seeder does
            item = Item(
                canonical_name=canonical_name,
                aliases=item_data.get("aliases", []),
                category=item_data["category"],
                unit="g",
                fdc_id=item_data.get("fdc_id"),
                nutrition_per_100g=item_data["nutrition_per_100g"],
                is_staple=False,
                embedding=embedding_json,
                embedding_model=item_data.get("embedding_model", "text-embedding-3-small"),
                embedding_version=item_data.get("embedding_version", 1),
                source=item_data.get("source", "usda_fdc")
            )

            db.add(item)

            if i % 20 == 0:
                print(f"{i}/{len(items)}...")

        db.commit()
        print(f"✅ Imported {len(items)} items")

    except Exception as e:
        db.rollback()
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python import_without_duplicate_check.py <json_file_path>")
        sys.exit(1)

    import_all_items(sys.argv[1])
