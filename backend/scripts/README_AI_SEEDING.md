# AI-Assisted Item Seeding Workflow

## Overview

This system uses AI to intelligently populate your nutrition database with ~500 common grocery items, complete with:
- ✅ Clean, standardized canonical names
- ✅ Accurate USDA nutrition data
- ✅ Vector embeddings for semantic search
- ✅ Confidence scores for quality control
- ✅ Manual review before database import

## How It Works

### 5-Step Workflow

```
1. LLM Candidate Generation
   ↓ (Suggests 500 new items based on ALL existing items)

2. FDC Search
   ↓ (Searches USDA FDC, gets top 3 matches per item)

3. LLM Enrichment
   ↓ (Selects best match, provides aliases, categories, confidence scores)

4. Embedding Generation
   ↓ (Creates vector embeddings, saves to JSON)

5. Manual Review & Import
   (You review JSON, then import to database)
```

## Usage

### Step 1-4: Generate Seeding Data

```bash
# Navigate to backend directory
cd backend

# Run the generation workflow (creates JSON for review)
python scripts/ai_assisted_item_seeding.py generate --count 500
```

**What happens:**
- Fetches ALL existing items from database (avoids duplicates)
- LLM suggests 500 new common grocery items
- Searches USDA FDC for each item (top 3 matches)
- LLM reviews FDC options and selects best match
- Generates embeddings for semantic search
- Saves everything to `backend/data/proposed_items_for_review.json`

**Time:** ~10-15 minutes (depending on API speed)

**Cost:**
- OpenAI API: ~$0.50-$1.00 (mostly for embeddings)
- USDA FDC API: Free

### Step 5: Manual Review

Open `backend/data/proposed_items_for_review.json` and review:

```json
{
  "metadata": {
    "generated_at": "2025-10-19T12:00:00",
    "total_items": 487,
    "openai_model": "gpt-4o-2024-08-06",
    "embedding_model": "text-embedding-3-small"
  },
  "items": [
    {
      "canonical_name": "celery",
      "display_name": "Celery",
      "category": "vegetables",
      "aliases": ["celery stalk", "celery stick", "celery rib"],
      "nutrition_per_100g": {
        "calories": 16,
        "protein_g": 0.69,
        "carbs_g": 2.97,
        "fat_g": 0.17,
        "fiber_g": 1.6
      },
      "fdc_id": "169988",
      "source": "usda_fdc",
      "confidence": 0.95,
      "fdc_description": "Celery, raw",
      "embedding": [0.023, -0.014, ...],
      "embedding_model": "text-embedding-3-small",
      "embedding_version": 1
    },
    ...
  ]
}
```

**What to check:**
1. ✅ Canonical names are correct (lowercase_underscore)
2. ✅ Categories make sense
3. ✅ Nutrition values look reasonable
4. ✅ No unwanted items
5. ❌ Remove any items you don't want

### Step 6: Import to Database

After reviewing and editing the JSON:

```bash
# Import with default confidence threshold (0.70)
python scripts/ai_assisted_item_seeding.py import --file backend/data/proposed_items_for_review.json

# Or set custom confidence threshold
python scripts/ai_assisted_item_seeding.py import --file backend/data/proposed_items_for_review.json --min-confidence 0.80
```

**What happens:**
- Reads the JSON file
- Filters items by confidence threshold
- Checks for duplicates (skips existing items)
- Inserts new items into database
- Commits all changes in one transaction

## Output Statistics

After generation, you'll see:

```
✅ Review JSON saved to: backend/data/proposed_items_for_review.json
Total items: 487
Average confidence: 0.88

Confidence breakdown:
  High (≥0.90): 312 items
  Medium (0.70-0.89): 145 items
  Low (<0.70): 30 items
```

**Interpretation:**
- **High confidence (≥0.90)**: Perfect matches, safe to import
- **Medium (0.70-0.89)**: Good matches, review recommended
- **Low (<0.70)**: Questionable matches, excluded by default

## Database Schema

Items are created with:

```python
Item(
    canonical_name="celery",              # Unique, lowercase_underscore
    aliases=["celery stalk", ...],        # Alternative names
    category="vegetables",                # Category
    unit="g",                            # Default to grams
    fdc_id="169988",                     # USDA FDC ID (traceable)
    nutrition_per_100g={...},            # Nutrition data
    is_staple=False,                     # Can update manually later
    embedding="[0.023, -0.014, ...]",    # JSON string of vector
    embedding_model="text-embedding-3-small",
    embedding_version=1,
    source="usda_fdc"                    # Source tracking
)
```

## Troubleshooting

### Error: "No candidates generated"

**Cause:** LLM failed to respond or returned invalid JSON

**Fix:**
- Check OpenAI API key is valid
- Check network connection
- Retry the command

### Error: "FDC API error"

**Cause:** USDA FDC API rate limiting or downtime

**Fix:**
- Wait a few minutes and retry
- System uses Redis caching, so retries are faster

### Error: "Duplicate item"

**Cause:** Item already exists in database

**Fix:**
- This is expected behavior (safety check)
- Items are skipped, not re-inserted

## Advanced Usage

### Custom Target Count

```bash
# Generate only 100 items
python scripts/ai_assisted_item_seeding.py generate --count 100

# Generate 1000 items (will take longer)
python scripts/ai_assisted_item_seeding.py generate --count 1000
```

### Batch Processing

If you want to seed in multiple rounds:

```bash
# Round 1: Vegetables (edit prompt to focus on vegetables)
python scripts/ai_assisted_item_seeding.py generate --count 100
# Review and import

# Round 2: Proteins (edit prompt to focus on proteins)
python scripts/ai_assisted_item_seeding.py generate --count 100
# Review and import
```

### Manual JSON Editing

You can manually edit the JSON before import:

1. **Remove unwanted items**: Delete entire item objects
2. **Fix canonical names**: Edit `canonical_name` field
3. **Adjust categories**: Change `category` field
4. **Add custom aliases**: Add to `aliases` array
5. **Override nutrition**: Edit `nutrition_per_100g` values

Example:

```json
{
  "canonical_name": "celery",  // ← Can change to "celery_stalk"
  "category": "vegetables",    // ← Can change category
  "aliases": [                 // ← Can add more aliases
    "celery stalk",
    "celery stick",
    "my custom alias"          // ← Added
  ],
  "nutrition_per_100g": {      // ← Can override nutrition
    "calories": 16,
    ...
  }
}
```

## Quality Assurance

The system has multiple safety checks:

1. **Duplicate Prevention**:
   - LLM receives ALL existing items
   - Python validates against existing items
   - Import skips duplicates

2. **Confidence Scoring**:
   - LLM assigns 0.0-1.0 confidence
   - Import filters by minimum threshold
   - Low-confidence items excluded by default

3. **Manual Review**:
   - Nothing imported until you approve
   - JSON is human-readable
   - Easy to remove unwanted items

4. **Transaction Safety**:
   - All inserts in single transaction
   - Rollback on error
   - Database stays consistent

## Next Steps After Seeding

1. **Test Vector Search**:
   ```python
   from app.services.item_normalizer import ItemNormalizer

   normalizer = ItemNormalizer()
   result = normalizer.normalize("celery sticks")  # Should match "celery"
   ```

2. **Populate Recipe Embeddings** (future):
   - Run similar workflow for recipes
   - Enable semantic recipe search

3. **Test Receipt Scanner**:
   - Upload receipt with newly seeded items
   - Verify matching accuracy improved

## Files Created

- `backend/scripts/ai_assisted_item_seeding.py` - Main workflow script
- `backend/data/proposed_items_for_review.json` - Generated seeding data
- `backend/services/embedding_service.py` - Embedding generation service

## Cost Breakdown

**One-time costs (500 items):**
- LLM candidate generation: ~$0.05
- LLM enrichment (20 batches): ~$0.20
- Embeddings (500 items): ~$0.02
- **Total: ~$0.30**

**Ongoing costs:**
- Per receipt scan: ~$0.001-0.005 (depends on items)
- Per recipe search: ~$0.001-0.002
- **Monthly (100 scans): ~$0.10-0.50**

## Support

If you encounter issues:

1. Check logs: Script outputs detailed progress
2. Review JSON: Manually inspect generated data
3. Start small: Try `--count 50` first to test
4. Check database: Verify existing items with SQL query

```sql
-- Check current item count
SELECT COUNT(*) FROM items;

-- Check categories
SELECT category, COUNT(*) FROM items GROUP BY category;

-- Check embeddings
SELECT COUNT(*) FROM items WHERE embedding IS NOT NULL;
```
