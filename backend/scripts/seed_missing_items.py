"""
seed_missing_items.py
---------------------
Inserts the 12 missing items from recipe_audit/missing_items.json
into the items table. Skips any that already exist (by canonical_name).

Run inside the api container:
  docker compose exec api python scripts/seed_missing_items.py

DRY RUN:
  docker compose exec api python scripts/seed_missing_items.py --dry-run
"""

import json
import os
import sys
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models.database import SessionLocal, Item

ITEMS_FILE = os.path.join(os.path.dirname(__file__), "recipe_audit", "missing_items.json")


def main(dry_run: bool = False):
    mode = "DRY RUN" if dry_run else "LIVE"
    print(f"\n{'='*55}")
    print(f"  Seed Missing Items  —  {mode} MODE")
    print(f"  {datetime.utcnow().isoformat()}")
    print(f"{'='*55}\n")

    with open(ITEMS_FILE, "r", encoding="utf-8") as f:
        items_to_seed = json.load(f)
    print(f"Loaded {len(items_to_seed)} items from design file.\n")

    db = SessionLocal()
    try:
        existing = {
            item.canonical_name
            for item in db.query(Item.canonical_name).all()
        }

        inserted = []
        skipped = []

        for item_data in items_to_seed:
            cname = item_data["canonical_name"]

            if cname in existing:
                skipped.append(cname)
                print(f"  SKIP  {cname} (already exists)")
                continue

            print(f"  ADD   {cname}")
            print(f"        aliases  : {', '.join(item_data.get('aliases', []))}")
            print(f"        category : {item_data.get('category')}")
            print(f"        nutrition: {item_data.get('nutrition_per_100g')}")

            if not dry_run:
                db.add(Item(
                    canonical_name=cname,
                    aliases=item_data.get("aliases", []),
                    category=item_data.get("category"),
                    unit=item_data.get("unit", "g"),
                    is_staple=item_data.get("is_staple", False),
                    nutrition_per_100g=item_data.get("nutrition_per_100g"),
                    source="custom",
                ))

            inserted.append(cname)

        if not dry_run:
            db.commit()

        print(f"\n{'='*55}")
        print(f"  {'COMMITTED' if not dry_run else 'DRY RUN — nothing written'}")
        print(f"  Inserted : {len(inserted)}")
        print(f"  Skipped  : {len(skipped)}")
        print(f"{'='*55}\n")

    except Exception as e:
        db.rollback()
        print(f"\nERROR — rolled back: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
