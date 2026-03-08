# Recipe Database Audit — Analysis Notes
Generated: 2026-02-28

## Summary
- **Total recipes in DB**: 213
- **Total recipe_ingredient rows**: ~1,100
- **Unique items used across all recipes**: 72
- **Recipes with NO ingredients**: 5 (IDs 1–5)
- **Recipes with macro mismatch > 50 kcal**: 182

---

## Recipe Group Breakdown & Verdict

| ID Range | Group | Count | Verdict | Root Cause |
|---|---|---|---|---|
| 1–5 | Named (manual) | 5 | DELETE | Zero ingredients linked |
| 6–35 | Muscle Builder Meals | 30 | DELETE | Olive oil 58–200g/serving; placeholder instructions "Step N"; macros fabricated |
| 36–65 | Lean Meals | 30 | DELETE | Reasonable quantities but placeholder instructions; only 5 ingredients, no real recipe |
| 66–105 | Balanced Meals | 40 | DELETE | Same 5-ingredient template repeated 40 times; no instructions |
| 106–115 | Power Breakfast | 10 | DELETE | All 10 are identical ingredient lists, only stored macro differs (which is also wrong) |
| 116–125 | Power Lunch | 10 | DELETE | All 10 identical |
| 126–135 | Power Dinner | 10 | DELETE | All 10 identical |
| 136–145 | Lean Breakfast | 10 | DELETE | All 10 identical |
| 146–155 | Balanced Lunch | 10 | DELETE | All 10 identical |
| 156–165 | Balanced Dinner | 10 | DELETE | All 10 identical |
| 166–185 | Flexible Meals | 20 | DELETE | All 20 identical (dal+roti template) |
| 186–213 | Named (generated) | 28 | DELETE | Macros severely off (e.g. 1040 stored vs 372 calc); quantities nonsensical (500g chicken per serving) |

**Decision: Delete ALL 213 existing recipes and replace with 45 properly designed ones.**

---

## Key Issues Found

### 1. Olive Oil Abuse (Recipes 6–35, Muscle Builder group)
22 recipes have olive oil quantities of 58–200g per serving.
- 200g olive oil = ~1768 kcal from fat alone in one meal
- Normal cooking use: 5–15g (1–2 teaspoons)
- Root cause: quantities were randomly assigned during seeding

### 2. No Real Instructions
Recipes 6–185 all have instructions like:
```
"Step 1 for recipe N"
"Step 2 for recipe N"
```
These are completely useless placeholder text.

### 3. Duplicate Templates
Recipes 106–185 (80 recipes) all share the exact same ingredients with the same quantities
within each group. Only the stored macros differ (and those are wrong). These are not real recipes.

### 4. Empty Ingredient Recipes (1–5)
These were seeded with nutrition data manually entered but no RecipeIngredient rows were ever
created, so calculated macros are always 0.

### 5. Protein Target Problem (Achievement Service)
`achievement_service.py` line 117 defaults protein_target to 50g. This is unrealistically low —
any user eating 3 meals will exceed 50g protein trivially. Realistic targets:
- Fat loss: ~120–140g/day
- Muscle gain: ~150–180g/day
- General health: ~80–100g/day
This default makes the protein achievement notification fire too easily. **Fix separately.**

---

## Items Available in Database (Confirmed 27 items)
These are the items used in our new recipes — all confirmed to exist with good nutrition data:

| canonical_name | category | Notes |
|---|---|---|
| brown_rice | grains | Raw weight, 370 cal/100g |
| quinoa | grains | Raw weight, 368 cal/100g |
| oats | grains | Raw weight |
| roti | grains | Cooked, ~300 cal/100g |
| dal_lentils | legumes | Dry weight |
| chicken_breast | proteins | Cooked, 106 cal/100g |
| eggs | proteins | Whole egg, 148 cal/100g (~50g each) |
| tofu | proteins | Firm tofu |
| fish_salmon / salmon | proteins | 2 entries — check canonical |
| greek_yogurt | dairy | 61 cal/100g, 10.3g protein |
| almonds | nuts | 579 cal/100g |
| avocado | fruits | |
| banana | fruits | |
| broccoli | vegetables | 31 cal/100g |
| spinach | vegetables | 26.6 cal/100g |
| tomato | vegetables | |
| cucumber | vegetables | |
| bell_pepper | vegetables | |
| sweet_potato | vegetables | |
| zucchini | vegetables | |
| green_onion | vegetables | Incomplete nutrition data |
| olive_oil | oils | 884 cal/100g — USE SPARINGLY |
| garlic | spices | |
| ginger | spices | |
| black_pepper | spices | |
| lemon_juice | condiments | |
| salt | spices | All-zero nutrition (expected) |

---

## Missing Items (Needed for realistic Indian + varied recipes)

See `missing_items.json` for full details. Summary:

| Item | Why Needed | Priority |
|---|---|---|
| onion | Core Indian cooking base; negligible macros but critical for taste | HIGH |
| paneer | Primary vegetarian Indian protein; ~265 cal, 18g P per 100g | HIGH |
| chickpeas | High-protein legume; Mediterranean + Indian use | HIGH |
| chicken_thigh | Different fat profile from breast; 177 cal, 19g P, 10g F | MEDIUM |
| turmeric | Indian spice; zero macro impact but required for authenticity | HIGH |
| cumin | Indian/Mediterranean spice | HIGH |
| coriander_powder | Indian spice | HIGH |
| chili_powder | Indian spice | MEDIUM |
| low_fat_milk | For oats/smoothies; ~42 cal, 3.4g P per 100g | MEDIUM |
| cottage_cheese | Western equivalent of paneer; 98 cal, 11g P per 100g | LOW |
| kidney_beans | Rajma; 127 cal, 8.7g P per 100g cooked | MEDIUM |
| whole_wheat_flour | For making rotis from scratch | LOW |

**Without these items, we can still create 45 good recipes using confirmed DB items.**
**Once these are added, we can extend to 60+ recipes.**
