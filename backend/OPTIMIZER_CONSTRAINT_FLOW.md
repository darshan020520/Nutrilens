# Complete Optimizer Constraint Flow - Recipe Nutrition Requirements

## Constraint Flow Pipeline

```
User Profile Data (height, weight, age, sex, activity_level)
    ↓
BMR Calculation (Mifflin-St Jeor Formula)
    ↓
TDEE = BMR × Activity Multiplier
    ↓
Goal Calories = TDEE + Goal Adjustment
    ↓
Daily Macro Grams = Goal Calories × Macro Ratios
    ↓
Per-Meal Targets = Daily Targets / Meals Per Day
    ↓
Recipe Filtering & Scoring
```

## 1. Goal-Based Calorie Adjustments

Source: `onboarding.py` lines 20-27

| Goal Type | TDEE Adjustment | Purpose |
|-----------|----------------|---------|
| MUSCLE_GAIN | +500 cal | Caloric surplus for muscle building |
| FAT_LOSS | -500 cal | Caloric deficit for fat loss |
| BODY_RECOMP | 0 cal | Maintenance (body recomposition) |
| WEIGHT_TRAINING | +300 cal | Slight surplus for strength |
| ENDURANCE | +200 cal | Slight surplus for endurance |
| GENERAL_HEALTH | 0 cal | Maintenance |

## 2. Macro Ratios by Goal

Source: `onboarding.py` lines 30-37

| Goal | Protein | Carbs | Fat |
|------|---------|-------|-----|
| MUSCLE_GAIN | 30% | 45% | 25% |
| FAT_LOSS | 35% | 35% | 30% |
| BODY_RECOMP | 35% | 40% | 25% |
| WEIGHT_TRAINING | 30% | 50% | 20% |
| ENDURANCE | 20% | 55% | 25% |
| GENERAL_HEALTH | 25% | 45% | 30% |

## 3. Optimizer Constraint Calculation

Source: `final_meal_optimizer.py` lines 659-714

### From User Data:
- **goal_calories** (from UserProfile): TDEE + goal_adjustment
- **macro_targets** (from UserGoal): JSON like `{"protein": 0.35, "carbs": 0.40, "fat": 0.25}`
- **meals_per_day** (from UserPath): 1-6 meals depending on path type
- **dietary_restrictions** (from UserPreference): vegetarian, vegan, non_vegetarian
- **allergens** (from UserPreference): List of allergens

### Constraint Building:
```python
daily_calories_min = goal_calories * 0.95  # 5% tolerance
daily_calories_max = goal_calories * 1.05  # 5% tolerance

daily_protein_g = (goal_calories * protein_ratio) / 4   # 4 cal/g
daily_carbs_g = (goal_calories * carb_ratio) / 4        # 4 cal/g
daily_fat_g = (goal_calories * fat_ratio) / 9           # 9 cal/g

# With flexibility:
daily_protein_min = daily_protein_g * 0.9  # 10% tolerance
daily_carbs_min = daily_carbs_g * 0.8      # 20% tolerance
daily_carbs_max = daily_carbs_g * 1.2
daily_fat_min = daily_fat_g * 0.8
daily_fat_max = daily_fat_g * 1.2
```

### LP Solver Additional Relaxation:
Source: `final_meal_optimizer.py` lines 111-129

When LP constraints are applied:
```python
# Calories - 20% tolerance for feasibility
min_cal = daily_calories_min * 0.8  # Total: 0.95 * 0.8 = 0.76 of goal
max_cal = daily_calories_max * 1.2  # Total: 1.05 * 1.2 = 1.26 of goal

# Protein - 15% tolerance
min_protein = daily_protein_min * 0.85  # Total: 0.9 * 0.85 = 0.765 of target

# Carbs & Fat - 20% tolerance
max_carbs = daily_carbs_max * 1.2  # Total: 1.2 * 1.2 = 1.44 of target
max_fat = daily_fat_max * 1.2
```

## 4. Recipe Filtering

Source: `final_meal_optimizer.py` lines 138-153, 381-462

### Step 1: Goal Filtering
```python
query = query.filter(Recipe.goals.contains(user_goal_type))
# Recipe must have user's goal in its goals JSON array
```

### Step 2: Dietary Filtering
```python
if dietary_type == 'vegetarian':
    query = query.filter(Recipe.dietary_tags.contains('vegetarian'))
elif dietary_type == 'vegan':
    query = query.filter(Recipe.dietary_tags.contains('vegan'))
```

### Step 3: Prep Time Filtering
```python
query = query.filter(
    (Recipe.prep_time_min + Recipe.cook_time_min) <= max_prep_time_minutes
)
```

### Step 4: Calorie Range Filtering
```python
min_cal_per_meal = daily_calories_min / meals_per_day * 0.5  # 50% flexibility
max_cal_per_meal = daily_calories_max / meals_per_day * 1.5  # 150% flexibility

# Only include recipes that fit in this range
if min_cal_per_meal <= recipe_calories <= max_cal_per_meal:
    include_recipe()
```

## 5. Recipe Scoring

Source: `final_meal_optimizer.py` lines 549-656

Recipes are scored on 5 dimensions:

### 1. Goal Alignment (30% weight)
- Recipe has user's goal: 100 points
- Recipe has "general_health": 60 points
- Other: 30 points

### 2. Macro Fit (25% weight)
```python
target_cal_per_meal = daily_calories / meals_per_day
target_protein_per_meal = daily_protein / meals_per_day
target_carbs_per_meal = daily_carbs / meals_per_day
target_fat_per_meal = daily_fat / meals_per_day

# Calculate deviation
cal_diff = |recipe_cal - target_cal| / target_cal
protein_diff = |recipe_protein - target_protein| / target_protein
...

# Average weighted deviation
avg_diff = cal_diff * 0.4 + protein_diff * 0.3 + carbs_diff * 0.2 + fat_diff * 0.1

# Score (0-100, higher is better)
macro_fit = max(0, 100 - (avg_diff * 50))
```

### 3. Timing Appropriateness (15% weight)
- Flexible (3+ meal times): 100 points
- Moderate (2 meal times): 75 points
- Restricted (1 meal time): 50 points

### 4. Complexity (10% weight, inverted)
- ≤15 min: 0 complexity (best)
- ≤30 min: 30 complexity
- ≤45 min: 60 complexity
- >45 min: 90 complexity

### 5. Inventory Coverage (20% weight)
- % of ingredients available in user's pantry

## 6. Worked Examples

### Example 1: Muscle Gain User

**User Profile:**
- Male, 75kg, 180cm, 25 years, Moderately Active
- BMR: 1795 cal
- TDEE: 1795 × 1.55 = 2782 cal
- Goal: MUSCLE_GAIN
- **goal_calories: 2782 + 500 = 3282 cal**

**Macro Targets (30% protein, 45% carbs, 25% fat):**
- Protein: 3282 × 0.30 / 4 = **246g/day**
- Carbs: 3282 × 0.45 / 4 = **369g/day**
- Fat: 3282 × 0.25 / 9 = **91g/day**

**Path:** TRADITIONAL (4 meals: breakfast, lunch, snack, dinner)

**Optimizer Constraints:**
```python
daily_calories_min = 3282 * 0.95 = 3118 cal
daily_calories_max = 3282 * 1.05 = 3446 cal
daily_protein_min = 246 * 0.9 = 221g
meals_per_day = 4
```

**Per-Meal Targets:**
- Calories: 3282 / 4 = **821 cal/meal** (target)
- Protein: 246 / 4 = **61.5g/meal** (target)

**Recipe Calorie Range (for filtering):**
- Min: 3118 / 4 * 0.5 = **389 cal**
- Max: 3446 / 4 * 1.5 = **1292 cal**

**Recipe Requirements:**
- Must contain "muscle_gain" in `goals` JSON
- Calories: 389-1292 cal/serving (for filtering)
- Ideal: ~821 cal/serving (for scoring)
- High protein: ~61.5g/serving preferred

### Example 2: Fat Loss User

**User Profile:**
- Female, 65kg, 165cm, 30 years, Lightly Active
- BMR: 1399 cal
- TDEE: 1399 × 1.375 = 1923 cal
- Goal: FAT_LOSS
- **goal_calories: 1923 - 500 = 1423 cal**

**Macro Targets (35% protein, 35% carbs, 30% fat):**
- Protein: 1423 × 0.35 / 4 = **125g/day**
- Carbs: 1423 × 0.35 / 4 = **125g/day**
- Fat: 1423 × 0.30 / 9 = **47g/day**

**Path:** IF_16_8 (3 meals: lunch, snack, dinner)

**Optimizer Constraints:**
```python
daily_calories_min = 1423 * 0.95 = 1352 cal
daily_calories_max = 1423 * 1.05 = 1494 cal
daily_protein_min = 125 * 0.9 = 113g
meals_per_day = 3
```

**Per-Meal Targets:**
- Calories: 1423 / 3 = **474 cal/meal** (target)
- Protein: 125 / 3 = **42g/meal** (target)

**Recipe Calorie Range:**
- Min: 1352 / 3 * 0.5 = **225 cal**
- Max: 1494 / 3 * 1.5 = **747 cal**

**Recipe Requirements:**
- Must contain "fat_loss" in `goals` JSON
- Calories: 225-747 cal/serving
- Ideal: ~474 cal/serving
- Moderate protein: ~42g/serving

## 7. Critical Recipe Seeding Requirements

### Recipe MUST Have:

1. **goals** (JSON array): MUST include at least one goal type
   - Examples: `["muscle_gain", "general_health"]`
   - Required for filtering in `_get_filtered_recipes_fixed()`

2. **macros_per_serving** (JSON object): Complete nutrition data
   ```json
   {
     "calories": 650,
     "protein_g": 45,
     "carbs_g": 52,
     "fat_g": 22,
     "fiber_g": 6,
     "sodium_mg": 480
   }
   ```

3. **suitable_meal_times** (JSON array): When recipe can be eaten
   - Examples: `["breakfast"]`, `["lunch", "dinner"]`, `["breakfast", "lunch", "dinner"]`
   - Used in `_is_recipe_suitable_for_meal()`

4. **dietary_tags** (JSON array): Dietary classifications
   - Examples: `["vegetarian"]`, `["vegan"]`, `["gluten_free"]`, `[]` for non-veg

5. **prep_time_min** + **cook_time_min**: Total time constraints
   - Sum must be ≤ `max_prep_time_minutes` from user preferences

### Recipe Calorie Guidelines by Goal:

| Goal Type | Typical User Calories | Meals/Day | Cal/Meal Target | Recipe Range |
|-----------|---------------------|-----------|-----------------|--------------|
| MUSCLE_GAIN | 2800-3500 | 3-4 | 700-1000 | 350-1500 |
| FAT_LOSS | 1400-1800 | 3 | 450-600 | 225-900 |
| BODY_RECOMP | 2000-2500 | 3 | 650-850 | 325-1275 |
| WEIGHT_TRAINING | 2500-3000 | 3-4 | 625-1000 | 310-1500 |
| ENDURANCE | 2300-2800 | 3-4 | 575-950 | 290-1425 |
| GENERAL_HEALTH | 1800-2400 | 3 | 600-800 | 300-1200 |

### Protein Guidelines by Goal:

| Goal | Protein % | Sample Calories | Daily Protein | Per-Meal (3x) | Per-Meal (4x) |
|------|-----------|-----------------|---------------|---------------|---------------|
| MUSCLE_GAIN | 30% | 3200 | 240g | 80g | 60g |
| FAT_LOSS | 35% | 1600 | 140g | 47g | 35g |
| BODY_RECOMP | 35% | 2200 | 193g | 64g | 48g |
| WEIGHT_TRAINING | 30% | 2800 | 210g | 70g | 53g |
| ENDURANCE | 20% | 2600 | 130g | 43g | 33g |
| GENERAL_HEALTH | 25% | 2000 | 125g | 42g | 31g |

## 8. Recipe Nutrition Validation Rules

### Macro Sanity Check:
```python
# Calories from macros should approximately equal stated calories
calculated_calories = (protein_g * 4) + (carbs_g * 4) + (fat_g * 9)
tolerance = 0.15  # 15% tolerance for cooking losses, rounding

if abs(calculated_calories - stated_calories) / stated_calories > tolerance:
    WARN: "Macro calories don't match stated calories"
```

### Per-Serving Portion Size:
```python
# Total food weight should be reasonable (200-800g typical)
total_weight_g = sum(ingredient.quantity_grams for ingredient in recipe.ingredients) / servings

if total_weight_g < 150:
    WARN: "Very small portion size"
elif total_weight_g > 1000:
    WARN: "Very large portion size"
```

### Nutrient Realism:
- Protein: 0-100g per serving (typical range)
- Carbs: 0-150g per serving
- Fat: 0-80g per serving
- Fiber: 0-30g per serving
- Sodium: 0-2000mg per serving

## 9. Optimizer Failure Modes

If optimizer can't find solution:

1. **Not enough recipes** (< meals_per_day × 3)
   - Need at least 9-12 recipes for 3-meal plan
   - Need variety across different calorie ranges

2. **Recipes don't match calorie constraints**
   - All recipes too high/low calorie
   - Can't sum to daily target

3. **No recipes for specific goal**
   - User has FAT_LOSS goal
   - But no recipes have "fat_loss" in goals array

4. **Vegetarian with no veg recipes**
   - User is vegetarian
   - But no recipes have "vegetarian" in dietary_tags

## 10. Recipe Seeding Strategy

### Coverage Matrix Needed:

| Goal | Breakfast | Lunch | Dinner | Snack | Total |
|------|-----------|-------|--------|-------|-------|
| MUSCLE_GAIN | 3-4 | 3-4 | 3-4 | 2-3 | ~15 |
| FAT_LOSS | 3-4 | 3-4 | 3-4 | 2-3 | ~15 |
| GENERAL_HEALTH | 2-3 | 2-3 | 2-3 | 2-3 | ~10 |

**Total: ~40-50 recipes minimum for basic coverage**

### Calorie Distribution:
- **Low** (250-450 cal): Breakfast, snacks, fat loss recipes
- **Medium** (450-700 cal): Standard meals, general health
- **High** (700-1000+ cal): Muscle gain, post-workout

### Dietary Coverage:
- **Vegetarian**: ~40% of recipes
- **Vegan**: ~20% of recipes
- **Non-vegetarian**: ~60% of recipes (can overlap with veg)

## Summary for Recipe Seeding

When creating recipes, they MUST:

1. Have realistic `macros_per_serving` where macro calories ≈ stated calories
2. Include appropriate `goals` tags based on calorie/protein content
3. Have correct `suitable_meal_times` based on recipe type
4. Have `dietary_tags` if vegetarian/vegan
5. Have reasonable `prep_time_min` + `cook_time_min`
6. Cover calorie range: 250-1200 cal/serving (distributed across recipes)
7. Cover protein range: 10-80g/serving (based on goal alignment)

**The optimizer will fail if recipes don't match these constraints!**
