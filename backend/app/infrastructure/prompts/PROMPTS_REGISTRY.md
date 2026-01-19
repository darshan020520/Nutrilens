# LLM Prompts Registry

This file tracks all prompts that have been migrated from inline code to use the LLMOrchestrator.
When seeding MongoDB, use these exact prompts with the specified slugs.

---

## 1. extract_batch_structures

**Source File:** `batch_normalizer.py` (lines 56-68)
**Slug:** `extract_batch_structures`
**Variables:** `{items_list}`
**Response Model:** `List[ExtractStructureResult]`
**Model:** `gpt-4o-mini`
**Temperature:** `0`
**Max Tokens:** `1000`

### Prompt Template:
```
Extract structured data for these food items:

{items_list}

For EACH item, extract: quantity, unit, and item_text

Examples:
- "2 apples" -> quantity: 2, unit: "unit", item_text: "apples"
- "500g chicken" -> quantity: 500, unit: "g", item_text: "chicken"
- "1 cup rice" -> quantity: 1, unit: "cup", item_text: "rice"

Return as JSON array in the SAME ORDER as input.
```

---

## 2. convert_to_grams

**Source File:** `unit_converter.py` (lines 20-33)
**Slug:** `convert_to_grams`
**Variables:** `{quantity}`, `{unit}`, `{item_name}`
**Response Model:** `ConvertToGramsResult`
**Model:** `gpt-4o-mini`
**Temperature:** `0`
**Max Tokens:** `500`

### Prompt Template:
```
Convert this quantity to grams.

Quantity: {quantity}
Unit: {unit}
Item: {item_name}

Use standard conversions or reasonable estimates based on the item type.

Examples:
- 1 cup rice = 185g
- 2 tbsp butter = 28g
- 1 medium apple = 182g

Provide the conversion.
```

---

## 3. match_or_identify

**Source File:** `llm_matcher.py` (lines 55-110)
**Slug:** `match_or_identify`
**Variables:** `{user_text}`, `{candidates}`, `{has_candidates}`
**Response Model:** `MatchOrIdentifyResult`
**Model:** `gpt-4o-mini`
**Temperature:** `0`
**Max Tokens:** `800`

### COMPLETE Prompt Template (with candidates - has_candidates=true):
```
You are a grocery item matcher. User entered: "{user_text}"

VECTOR SEARCH RESULTS (top candidates from database):
{candidates}

TASK 1: Does user's item match ANY of these candidates?
Examples of matches:
- "Herb Mint" → "mint" = YES (herb is descriptor)
- "Red Capsicum" → "bell_pepper" = YES (capsicum = bell pepper)
- "Loose Bean Shoots" → "bean_sprouts" = YES (shoots = sprouts)
- "Dragon Fruit" → "strawberry" = NO (different fruits)

TASK 2: If NO match, identify what the item actually is.
- Normalize the name: lowercase with underscores (e.g., "Dragon Fruit" → "dragon_fruit")
- Determine category: fruits, vegetables, dairy, meat, grains, herbs, etc.
- Assess if this is a real food item

OUTPUT (strict JSON, no markdown):
{
  "matched": true/false,
  "item_id": <id from candidates> or null,
  "confidence": 0.0-1.0,
  "reasoning": "brief explanation",
  "unknown_item": {
    "name": "normalized_name",
    "category": "category",
    "is_food_item": true/false,
    "confidence": 0.0-1.0
  }
}
```

### COMPLETE Prompt Template (no candidates - has_candidates=false):
```
You are a grocery item identifier. User entered: "{user_text}"

No matching items were found in the database.

TASK: Identify what this item is.
- Normalize the name: lowercase with underscores (e.g., "Dragon Fruit" → "dragon_fruit")
- Determine category: fruits, vegetables, dairy, meat, grains, herbs, etc.
- Assess if this is a real food item (not garbage text)

OUTPUT (strict JSON, no markdown):
{
  "matched": false,
  "item_id": null,
  "confidence": 0.0,
  "reasoning": "brief explanation",
  "unknown_item": {
    "name": "normalized_name",
    "category": "category",
    "is_food_item": true/false,
    "confidence": 0.0-1.0
  }
}
```

### Note on Conditional Prompts:
This prompt has two variants based on `has_candidates`. In MongoDB, you can either:
1. Store two separate prompts: `match_or_identify_with_candidates` and `match_or_identify_no_candidates`
2. Use a single prompt with Jinja2-style conditionals: `{% if has_candidates %}...{% else %}...{% endif %}`

---

## 4. extract_structure (single item)

**Source File:** `structure_extractor.py` (lines 20-29)
**Slug:** `extract_structure`
**Variables:** `{text}`
**Response Model:** `ExtractStructureResult`
**Model:** `gpt-4o-mini`
**Temperature:** `0`
**Max Tokens:** `500`

### Prompt Template:
```
Extract the quantity, unit, and item name from this text.

Text: {text}

Examples:
- "2 apples" -> quantity: 2, unit: "whole", item: "apples"
- "500g chicken" -> quantity: 500, unit: "grams", item: "chicken"
- "1 cup rice" -> quantity: 1, unit: "cup", item: "rice"

Extract the components.
```

---

## MongoDB Seed Document Format

Each prompt in MongoDB should follow this structure:

```json
{
  "slug": "extract_batch_structures",
  "version": 1,
  "active": true,
  "messages": [
    {
      "role": "user",
      "content": "Extract structured data for these food items:\n\n{items_list}\n\nFor EACH item..."
    }
  ],
  "config": {
    "model": "gpt-4o-mini",
    "temperature": 0,
    "max_tokens": 1000,
    "retries": 2
  },
  "metadata": {
    "description": "Batch structure extraction for normalizer",
    "source_file": "batch_normalizer.py",
    "created_at": "2024-01-18"
  }
}
```

---

## Migration Status

| Slug | Source File | Migrated | MongoDB Seeded |
|------|-------------|----------|----------------|
| `extract_batch_structures` | batch_normalizer.py | ✅ | ❌ |
| `convert_to_grams` | unit_converter.py | ✅ | ❌ |
| `match_or_identify` | llm_matcher.py | ⏳ In Progress | ❌ |
| `extract_structure` | structure_extractor.py | ❌ | ❌ |
