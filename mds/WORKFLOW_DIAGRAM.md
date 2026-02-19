# AI-Assisted Seeding Workflow Diagram

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      AI-ASSISTED ITEM SEEDING                           │
│                                                                         │
│  Input: "I want 500 new items"                                         │
│  Output: JSON file with 487 high-quality items ready for import        │
└─────────────────────────────────────────────────────────────────────────┘
```

## Detailed Workflow

```
╔════════════════════════════════════════════════════════════════════════╗
║ STEP 1: LLM CANDIDATE GENERATION                                       ║
╚════════════════════════════════════════════════════════════════════════╝

    ┌──────────────┐
    │  Database    │
    │  Query       │
    │  (137 items) │
    └──────┬───────┘
           │
           ▼
    ┌──────────────────────────────────────────────┐
    │  GPT-4o Prompt                               │
    │  ────────────────────────────────────────    │
    │  "Here are 137 existing items:               │
    │   [chicken_breast, eggs, ...]                │
    │                                               │
    │  Suggest 500 NEW items that DON'T exist.    │
    │  Use lowercase_underscore format."           │
    └──────┬───────────────────────────────────────┘
           │
           ▼
    ┌──────────────────────────────────────────────┐
    │  LLM Response                                 │
    │  ────────────────────────────────────────    │
    │  [                                            │
    │    "celery",                                  │
    │    "herb_mint",                               │
    │    "japanese_pumpkin",                        │
    │    "rice_noodles",                            │
    │    ...                                        │
    │  ]                                            │
    └──────┬───────────────────────────────────────┘
           │
           ▼
    ┌──────────────────────────────────────────────┐
    │  Python Validation                            │
    │  ────────────────────────────────────────    │
    │  • Check for duplicates                      │
    │  • Normalize format                          │
    │  • Trim to 500                               │
    └──────┬───────────────────────────────────────┘
           │
           ▼
    [ 500 unique candidate names ]


╔════════════════════════════════════════════════════════════════════════╗
║ STEP 2: FDC SEARCH                                                     ║
╚════════════════════════════════════════════════════════════════════════╝

    For each candidate (500 items):

    "celery" ──────────────────────┐
                                    ▼
                        ┌───────────────────────┐
                        │  USDA FDC API         │
                        │  Search "celery"      │
                        └───────┬───────────────┘
                                │
                                ▼
                        ┌───────────────────────────────────────────┐
                        │  Top 3 Matches:                           │
                        │  ─────────────────────────────────────    │
                        │  1. Celery, raw                           │
                        │     fdcId: 169988                         │
                        │     nutrients: [...]                      │
                        │                                            │
                        │  2. Celery, cooked, boiled                │
                        │     fdcId: 168409                         │
                        │     nutrients: [...]                      │
                        │                                            │
                        │  3. Celery salt                           │
                        │     fdcId: 170393                         │
                        │     nutrients: [...]                      │
                        └───────┬───────────────────────────────────┘
                                │
                                ▼
                        ┌───────────────────────┐
                        │  Redis Cache          │
                        │  (7 days TTL)         │
                        └───────────────────────┘

    Result: { "celery": [match1, match2, match3], ... }


╔════════════════════════════════════════════════════════════════════════╗
║ STEP 3: LLM ENRICHMENT (Batch Processing)                             ║
╚════════════════════════════════════════════════════════════════════════╝

    Process in batches of 20 items for token efficiency

    Batch 1 (20 items) ──┐
    Batch 2 (20 items) ──┼─────────────────┐
    ...                  │                  ▼
    Batch 25 (10 items) ─┘      ┌──────────────────────────────────┐
                                 │  GPT-4o Enrichment               │
                                 │  ──────────────────────────────  │
                                 │  "Review these FDC options:      │
                                 │                                   │
                                 │  celery:                         │
                                 │    1. Celery, raw                │
                                 │    2. Celery, cooked             │
                                 │    3. Celery salt                │
                                 │                                   │
                                 │  For each, provide:              │
                                 │  • Best match index (0-2)        │
                                 │  • Canonical name                │
                                 │  • Display name                  │
                                 │  • Category                      │
                                 │  • Aliases                       │
                                 │  • Confidence (0.0-1.0)"         │
                                 └──────────┬───────────────────────┘
                                            │
                                            ▼
                                 ┌──────────────────────────────────┐
                                 │  LLM Response (Batch 1)          │
                                 │  ──────────────────────────────  │
                                 │  {                                │
                                 │    "celery": {                   │
                                 │      "best_fdc_index": 0,        │
                                 │      "canonical_name": "celery", │
                                 │      "display_name": "Celery",   │
                                 │      "category": "vegetables",   │
                                 │      "aliases": [                │
                                 │        "celery stalk",           │
                                 │        "celery stick",           │
                                 │        "celery rib"              │
                                 │      ],                          │
                                 │      "confidence": 0.95          │
                                 │    },                            │
                                 │    ...                           │
                                 │  }                               │
                                 └──────────┬───────────────────────┘
                                            │
                                            ▼
                                 ┌──────────────────────────────────┐
                                 │  Parse FDC Nutrition             │
                                 │  ──────────────────────────────  │
                                 │  Extract from selected match:    │
                                 │  • calories                      │
                                 │  • protein_g                     │
                                 │  • carbs_g                       │
                                 │  • fat_g                         │
                                 │  • fiber_g                       │
                                 │  • sodium_mg                     │
                                 └──────────┬───────────────────────┘
                                            │
                                            ▼
                    [ Enriched items with nutrition + metadata ]


╔════════════════════════════════════════════════════════════════════════╗
║ STEP 4: EMBEDDING GENERATION                                           ║
╚════════════════════════════════════════════════════════════════════════╝

    For each enriched item:

    ┌──────────────────────────────────────────────┐
    │  Create Embedding Text                        │
    │  ────────────────────────────────────────    │
    │  "celery Celery vegetables                   │
    │   celery stalk celery stick celery rib"      │
    └──────┬───────────────────────────────────────┘
           │
           ▼
    ┌──────────────────────────────────────────────┐
    │  OpenAI Embeddings API                        │
    │  ────────────────────────────────────────    │
    │  Model: text-embedding-3-small                │
    │  Dimension: 1536                              │
    │  Batch size: 100                              │
    └──────┬───────────────────────────────────────┘
           │
           ▼
    ┌──────────────────────────────────────────────┐
    │  Vector (1536 floats)                         │
    │  ────────────────────────────────────────    │
    │  [0.023, -0.014, 0.008, ..., 0.012]          │
    └──────┬───────────────────────────────────────┘
           │
           ▼
    ┌──────────────────────────────────────────────┐
    │  Complete Item Data                           │
    │  ────────────────────────────────────────    │
    │  {                                            │
    │    "canonical_name": "celery",                │
    │    "display_name": "Celery",                  │
    │    "category": "vegetables",                  │
    │    "aliases": [...],                          │
    │    "nutrition_per_100g": {...},               │
    │    "fdc_id": "169988",                        │
    │    "source": "usda_fdc",                      │
    │    "confidence": 0.95,                        │
    │    "embedding": [0.023, ...],                 │
    │    "embedding_model": "text-embedding-3-small"│
    │  }                                            │
    └──────┬───────────────────────────────────────┘
           │
           ▼
    ┌──────────────────────────────────────────────┐
    │  Save to JSON                                 │
    │  ────────────────────────────────────────    │
    │  backend/data/proposed_items_for_review.json │
    │                                               │
    │  {                                            │
    │    "metadata": {...},                         │
    │    "items": [487 items]                       │
    │  }                                            │
    └───────────────────────────────────────────────┘


╔════════════════════════════════════════════════════════════════════════╗
║ STEP 5: MANUAL REVIEW & IMPORT                                         ║
╚════════════════════════════════════════════════════════════════════════╝

    ┌──────────────────────────────────────────────┐
    │  Human Review                                 │
    │  ────────────────────────────────────────    │
    │  • Open JSON file                            │
    │  • Check canonical names                     │
    │  • Verify categories                         │
    │  • Review nutrition values                   │
    │  • Remove unwanted items                     │
    │  • Edit if needed                            │
    └──────┬───────────────────────────────────────┘
           │
           ▼
    ┌──────────────────────────────────────────────┐
    │  Import Command                               │
    │  ────────────────────────────────────────    │
    │  python scripts/ai_assisted_item_seeding.py  │
    │    import                                     │
    │    --file proposed_items_for_review.json     │
    │    --min-confidence 0.70                     │
    └──────┬───────────────────────────────────────┘
           │
           ▼
    ┌──────────────────────────────────────────────┐
    │  Import Process                               │
    │  ────────────────────────────────────────    │
    │  1. Load JSON                                │
    │  2. Filter by confidence ≥ 0.70              │
    │  3. Check for duplicates                     │
    │  4. Convert embeddings to JSON strings       │
    │  5. Create Item instances                    │
    │  6. Commit transaction                       │
    └──────┬───────────────────────────────────────┘
           │
           ▼
    ┌──────────────────────────────────────────────┐
    │  Database                                     │
    │  ────────────────────────────────────────    │
    │  Items Table:                                │
    │  ┌──────────────────────────────────┐        │
    │  │ id | canonical_name | category   │        │
    │  ├────┼───────────────┼─────────────┤        │
    │  │ 1  | chicken_breast | proteins   │        │
    │  │ 2  | eggs          | proteins    │        │
    │  │... | ...           | ...         │        │
    │  │138 | celery        | vegetables  │  NEW!  │
    │  │139 | herb_mint     | spices      │  NEW!  │
    │  │... | ...           | ...         │  NEW!  │
    │  │625 | coconut_milk  | dairy       │  NEW!  │
    │  └────┴───────────────┴─────────────┘        │
    └───────────────────────────────────────────────┘
```

## Data Flow Summary

```
┌─────────────┐    ┌──────────┐    ┌─────────┐    ┌───────────┐    ┌──────────┐
│  Database   │───▶│  GPT-4o  │───▶│   FDC   │───▶│   GPT-4o  │───▶│  OpenAI  │
│  (137       │    │  (Suggest│    │   API   │    │  (Enrich) │    │ Embeddings│
│   items)    │    │   500)   │    │ (Search)│    │           │    │           │
└─────────────┘    └──────────┘    └─────────┘    └───────────┘    └──────────┘
                         │              │               │                 │
                         ▼              ▼               ▼                 ▼
                    [ 500 names ]  [FDC results]  [Enriched data]  [Embeddings]
                                                                           │
                                                                           ▼
                    ┌──────────────────────────────────────────────────────┐
                    │           proposed_items_for_review.json             │
                    │                    (487 items)                       │
                    └──────────────────────┬───────────────────────────────┘
                                           │
                                           ▼
                                    [ Human Review ]
                                           │
                                           ▼
                                    ┌──────────────┐
                                    │   Database   │
                                    │  (625 items) │
                                    └──────────────┘
```

## Confidence Score Flow

```
                           LLM Enrichment
                                 │
                                 ▼
            ┌────────────────────────────────────┐
            │  LLM assigns confidence score      │
            │  based on match quality            │
            └────────────┬───────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         │               │               │
         ▼               ▼               ▼
    ┌────────┐     ┌─────────┐     ┌────────┐
    │ ≥ 0.90 │     │0.70-0.89│     │ < 0.70 │
    │  HIGH  │     │ MEDIUM  │     │  LOW   │
    └───┬────┘     └────┬────┘     └────┬───┘
        │               │               │
        │               │               │
        ▼               ▼               ▼
   Auto-approve    Review         Excluded
    (312 items)   recommended     (30 items)
                  (145 items)
        │               │
        └───────┬───────┘
                │
                ▼
         [ JSON Review File ]
                │
                ▼
         [ User Decision ]
                │
                ▼
      ┌──────────────────────┐
      │  Import Command      │
      │  --min-confidence    │
      │  (default: 0.70)     │
      └──────────┬───────────┘
                 │
                 ▼
          [ Database ]
```

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Nutrilens Backend                           │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
              ▼               ▼               ▼
    ┌─────────────────┐ ┌──────────┐ ┌─────────────┐
    │  EmbeddingService│ │FDCService│ │   OpenAI    │
    │  ──────────────  │ │──────────│ │   Client    │
    │  • get_embedding │ │ • search │ │  ─────────  │
    │  • get_batch     │ │ • cache  │ │ • GPT-4o    │
    └─────────────────┘ └──────────┘ └─────────────┘
              │               │               │
              └───────────────┼───────────────┘
                              ▼
                  ┌──────────────────────┐
                  │  IntelligentSeeder   │
                  │  ──────────────────  │
                  │  • generate()        │
                  │  • search_fdc()      │
                  │  • enrich()          │
                  │  • create_json()     │
                  │  • import()          │
                  └──────────┬───────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
        ┌──────────┐  ┌──────────┐  ┌──────────┐
        │PostgreSQL│  │  Redis   │  │   JSON   │
        │(Items DB)│  │ (Cache)  │  │ (Review) │
        └──────────┘  └──────────┘  └──────────┘
```

## Error Handling Flow

```
                      ┌─────────────┐
                      │  Operation  │
                      └──────┬──────┘
                             │
                    ┌────────▼────────┐
                    │   Try Block     │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
              ╔═════╪═══════════════╪═════╗
              ║     │   Success?    │     ║
              ╚═════╪═══════════════╪═════╝
                    │               │
               Yes  │               │  No
                    │               │
                    ▼               ▼
            ┌───────────┐    ┌────────────┐
            │ Continue  │    │Log Error   │
            │ Next Step │    │Rollback DB │
            └───────────┘    │Return []   │
                             └────────────┘
                                   │
                                   ▼
                            [ Skip & Continue ]
                            or [ Retry ] or [ Abort ]
```

## Timeline

```
┌──────────────────────────────────────────────────────────────────┐
│                   Execution Timeline                             │
└──────────────────────────────────────────────────────────────────┘

0:00  ─┬─  Start workflow
      │
0:30  ─┼─  Step 1: LLM generates 500 candidates (30 sec)
      │
1:00  ─┼─  Step 2: FDC search begins (500 items × 0.5 sec = ~4 min)
      │
5:00  ─┼─  Step 3: LLM enrichment (25 batches × 10 sec = ~4 min)
      │
9:00  ─┼─  Step 4: Embeddings (500 items × 0.5 sec = ~4 min)
      │
13:00 ─┴─  Complete! JSON saved

      [ Human Review: 5-30 minutes ]

      ─┬─  Step 5: Import command
      │
      ─┴─  Database updated (10 sec)

Total automated time: ~13 minutes
Total with review: ~20-45 minutes
```
